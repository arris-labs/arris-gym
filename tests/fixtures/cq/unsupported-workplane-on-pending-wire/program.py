import cadquery as cq

result = cq.Workplane("XY").moveTo(3, 0).workplane(offset=2).circle(1).extrude(1)
show_object(result)
