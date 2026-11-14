import cadquery as cq

result = (
    cq.Workplane("XY").box(4, 6, 8).workplane().faces(">Z")
)
show_object(result)
