import cadquery as cq

result = cq.Workplane("XY").center(1,2).sketch().circle(1).finalize().extrude(1)
show_object(result)
