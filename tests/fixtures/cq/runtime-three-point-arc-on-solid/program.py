import cadquery as cq

result = cq.Workplane("XY").moveTo(5, 0).circle(1).extrude(2).threePointArc((1, 1), (2, 0))
show_object(result)
