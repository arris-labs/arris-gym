import cadquery as cq

result = (
    cq.Workplane("XY").box(4, 6, 8).faces(">Z").workplane().hole(1, depth=3)
)
show_object(result)
