import cadquery as cq

result = (
    cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().cskHole(1, 6, 60)
)
show_object(result)
