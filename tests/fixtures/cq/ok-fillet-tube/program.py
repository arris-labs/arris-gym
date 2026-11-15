import cadquery as cq

result = cq.Workplane("XY").circle(3).circle(1.5).extrude(2).edges(">Z").fillet(0.5)
show_object(result)
