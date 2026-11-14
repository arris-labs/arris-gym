import cadquery as cq

result = (
    cq.Workplane("XY").box(10, 10, 2).union(
        cq.Workplane("XY").transformed(offset=cq.Vector(3, 3, 2)).box(2, 2, 4)
    ).faces(">Z").workplane().hole(1)
)
show_object(result)
