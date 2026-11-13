import cadquery as cq

result = cq.Workplane("XY").circle(1).extrude(2, both=True)
show_object(result)
