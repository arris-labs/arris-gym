import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().sketch().circle(1).finalize().cutThruAll()
show_object(result)
