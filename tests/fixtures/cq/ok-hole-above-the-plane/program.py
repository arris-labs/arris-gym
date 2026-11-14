import cadquery as cq

result = (
    cq.Workplane("XY").box(4, 6, 8).workplane().hole(1)
)
show_object(result)
