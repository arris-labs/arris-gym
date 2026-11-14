import cadquery as cq

result = cq.Workplane("XY").circle(1).circle(2).extrude(1, both=True)
show_object(result)
