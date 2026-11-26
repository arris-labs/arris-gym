# Adapted from BenchCAD sheet_metal_tray_000130_s20260505, CC-BY-4.0. See ../README.md.
from math import dist, isclose, sqrt

from arris.build import Solid

length, width, height = 235.97, 41.54, 39.03
chamfer, thickness = 0.96, 3.83
outer = (length - 2 * chamfer, width - 2 * chamfer)
inner = tuple(d - 2 * sqrt(2) * thickness for d in outer)
# The opening is on the stock's end plane. Each of its two loops has two
# edges of each transverse length. Check the loops through their edge lengths.
lengths = sorted(2 * list(outer) + 2 * list(inner))

normal = (0, 1, 0)
axis = 1
stock = Solid.box((-117.985, -19.515, -20.77), (117.985, 19.515, 20.77))
stock = stock.chamfer(stock.faces().normal(normal).edges().members, chamfer)
selected = stock.faces().normal(normal)
face = selected.one()
assert isclose(stock.model.surface_properties(face).area, outer[0] * outer[1])
limits = stock.model.tight_bounds(face)
assert limits is not None
assert all(isclose(point[axis], height / 2) for point in limits)

result = stock.shell(selected.members, thickness)
rim = result.faces().extreme(normal).one()
assert isclose(result.model.surface_properties(rim).area, outer[0] * outer[1] - inner[0] * inner[1])
limits = result.model.tight_bounds(rim)
assert limits is not None
assert all(isclose(point[axis], height / 2) for point in limits)
edges = result.model.edges_of(rim)
actual = sorted(dist(*(result.model.point(v) for v in result.model.vertices_of(e))) for e in edges)
assert all(isclose(want, got) for want, got in zip(lengths, actual, strict=True))
