import cadquery as cq

result = cq.Workplane("XZ").circle(2).extrude(-1, both=True)
show_object(result)
