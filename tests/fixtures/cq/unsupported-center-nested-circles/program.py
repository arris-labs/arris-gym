import cadquery as cq

result = cq.Workplane("XY").circle(3).center(0,0).circle(1).extrude(1)
show_object(result)
