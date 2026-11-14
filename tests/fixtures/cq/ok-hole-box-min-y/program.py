import cadquery as cq

result = (
    cq.Workplane("XY").box(4, 6, 8).faces("<Y").workplane().hole(2)
)
show_object(result)
