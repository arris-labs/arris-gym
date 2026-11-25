from arris.build import Sketch, Workplane

sections = [Workplane.XY().circle(2), Workplane.XY(3).circle(1)]
result = Sketch.loft(sections, kind="smooth")
