import cadquery as cq

result = (
    cq.Workplane("XZ").box(4, 4, 4).union(
        cq.Workplane("XZ").transformed(offset=cq.Vector(3, 0, 0.5)).box(2, 2, 2)
    ).hole(1)
)
show_object(result)
