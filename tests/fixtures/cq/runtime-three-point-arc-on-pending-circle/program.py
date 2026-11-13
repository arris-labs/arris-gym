import cadquery as cq

result = cq.Workplane("XY").moveTo(3, 1).circle(1).threePointArc((1, 1), (2, 0))
show_object(result)
