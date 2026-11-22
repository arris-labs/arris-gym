"""Boundary integrals for analytic faces inside an oracle worker."""

import json
import math
from collections.abc import Iterator

import cadquery as cq
from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Curve2d, BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.GeomAbs import GeomAbs_C1, GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Torus
from OCP.gp import gp_Pnt, gp_Pnt2d, gp_Vec, gp_Vec2d
from OCP.TColStd import TColStd_Array1OfReal
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FORWARD, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

type Nodes = tuple[tuple[float, float], ...]
type Terms = tuple[float, float, float, float, float]

# The CAD-Recode disagreements converge inside ADR-0005's tolerance when
# every smooth pcurve interval is split at these two resolutions.
_SUBDIVISIONS = (128, 256)


def _boundary_terms(
    curve: BRepAdaptor_Curve2d,
    surface: BRepAdaptor_Surface,
    nodes: Nodes,
    subdivisions: int,
    direction: int,
    orientation: int,
) -> Iterator[Terms]:
    """Integrate the exact v-antiderivatives along an oriented UV edge.

    For planes and cylinders x(u,v) = a(u) + v*b, with b constant, and
    n = a'(u) cross b, so x dot n = a dot n. The divergence theorem gives
    x dot n / 3 for volume and x_j * (x dot n) / 4 for first moments.
    Green's theorem reduces each surface integral to minus its
    v-antiderivative times du around the trim. Only the fluxes use the
    face's outward sign. Area uses the magnitude of the Jacobian.
    """
    limits = TColStd_Array1OfReal(1, curve.NbIntervals(GeomAbs_C1) + 1)
    curve.Intervals(limits, GeomAbs_C1)
    uv, tangent = gp_Pnt2d(), gp_Vec2d()
    point, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    for index in range(limits.Lower(), limits.Upper()):
        lo, hi = limits.Value(index), limits.Value(index + 1)
        width = (hi - lo) / subdivisions
        half = width / 2
        for piece in range(subdivisions):
            mid = lo + (piece + 0.5) * width
            for node, weight in nodes:
                curve.D1(mid + half * node, uv, tangent)
                u, v = uv.Coord()
                if surface.GetType() in (GeomAbs_Cone, GeomAbs_Torus):
                    terms = _blend_primitive(surface, u, v, nodes, point, du, dv)
                    scale = -direction * tangent.X() * half * weight
                    yield (
                        scale * terms[0],
                        orientation * scale * terms[1],
                        orientation * scale * terms[2],
                        orientation * scale * terms[3],
                        orientation * scale * terms[4],
                    )
                    continue
                surface.D1(u, 0.0, point, du, dv)
                normal = du.Crossed(dv)
                x, y, z = point.Coord()
                flux = gp_Vec(x, y, z).Dot(normal)
                measure = -direction * tangent.X() * half * weight * v
                moment = orientation * measure * flux / 4
                yield (
                    measure * normal.Magnitude(),
                    orientation * measure * flux / 3,
                    moment * (x + v * dv.X() / 2),
                    moment * (y + v * dv.Y() / 2),
                    moment * (z + v * dv.Z() / 2),
                )


def _blend_primitive(
    surface: BRepAdaptor_Surface,
    u: float,
    v: float,
    nodes: Nodes,
    point: gp_Pnt,
    du: gp_Vec,
    dv: gp_Vec,
) -> Terms:
    """Integrate the fluxes across the cone or torus from a fixed v to the trim."""
    start = surface.FirstVParameter()
    half = (v - start) / 2
    middle = start + half
    terms = []
    for node, weight in nodes:
        surface.D1(u, middle + half * node, point, du, dv)
        normal = du.Crossed(dv)
        x, y, z = point.Coord()
        w = half * weight
        flux = w * gp_Vec(x, y, z).Dot(normal)
        terms.append((w * normal.Magnitude(), flux / 3, flux * x / 4, flux * y / 4, flux * z / 4))
    area, volume, mx, my, mz = map(math.fsum, zip(*terms, strict=True))
    return area, volume, mx, my, mz


def _integrate(
    shape: cq.Shape, nodes: Nodes, subdivisions: int, blends: bool = False
) -> tuple[float, ...]:
    edge_integrals = []
    for face in shape.Faces():
        orientation = 1 if face.wrapped.Orientation() == TopAbs_FORWARD else -1
        oriented = TopoDS.Face_s(face.wrapped.Oriented(TopAbs_FORWARD))
        surface = BRepAdaptor_Surface(oriented)
        supported = (GeomAbs_Cylinder, GeomAbs_Plane)
        if blends:
            supported += (GeomAbs_Cone, GeomAbs_Torus)
        if surface.GetType() not in supported:
            raise ValueError(f"unsupported boundary surface {surface.GetType()}")
        edges = TopExp_Explorer(oriented, TopAbs_EDGE)
        while edges.More():
            edge = TopoDS.Edge_s(edges.Current())
            direction = -1 if edge.Orientation() == TopAbs_REVERSED else 1
            terms = _boundary_terms(
                BRepAdaptor_Curve2d(edge, oriented),
                surface,
                nodes,
                subdivisions,
                direction,
                orientation,
            )
            edge_integrals.append(tuple(map(math.fsum, zip(*terms, strict=True))))
            edges.Next()
    area, volume, mx, my, mz = map(math.fsum, zip(*edge_integrals, strict=True))
    return volume, area, mx / volume, my / volume, mz / volume


class SketchBoundaryRecord(Exception):
    """Carry both boundary integrals through the oracle worker's report."""


def report_sketch_boundary(
    result: cq.Workplane,
    nodes: Nodes,
    blends: bool = False,
    subdivisions: tuple[int, int] = _SUBDIVISIONS,
) -> None:
    """Record a workplane's boundary integrals and tight bounds."""
    shape = cq.Compound.makeCompound(result.vals())
    bounds = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, bounds, False, False)
    raise SketchBoundaryRecord(
        json.dumps([bounds.Get(), *(_integrate(shape, nodes, n, blends) for n in subdivisions)])
    )


def report_signed_solids(
    result: cq.Workplane, nodes: Nodes, subdivisions: tuple[int, int] = _SUBDIVISIONS
) -> None:
    """Record each solid's signed volume, by the blended boundary flux, at both resolutions.

    A solid turned inside out has its faces' normals pointing in, so its flux is negative.
    """
    solids = [solid for shape in result.vals() for solid in shape.Solids()]
    raise SketchBoundaryRecord(
        json.dumps(
            [[_integrate(solid, nodes, n, True)[0] for n in subdivisions] for solid in solids]
        )
    )
