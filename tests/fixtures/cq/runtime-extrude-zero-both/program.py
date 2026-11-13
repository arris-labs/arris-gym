import cadquery as cq

result = cq.Workplane("XY").circle(1).extrude(0, both=True)
show_object(result)
