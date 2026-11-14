import cadquery as cq

result = (
    cq.Workplane("XY").box(4, 6, 8).faces(">Z").faces("<Z").workplane().hole(2)
)
show_object(result)
