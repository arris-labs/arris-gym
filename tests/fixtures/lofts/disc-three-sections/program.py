from arris.build import Sketch, Workplane

sections = [Workplane.XY().circle(2), Workplane.XY(2).circle(1), Workplane.XY(4).circle(2)]
result = Sketch.loft(sections, kind="smooth")
