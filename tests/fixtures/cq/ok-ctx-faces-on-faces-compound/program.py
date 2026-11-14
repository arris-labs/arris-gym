import cadquery as cq

result = (
    cq.Workplane("XY").box(10, 8, 4).union(
        cq.Workplane("XY").transformed(offset=cq.Vector(20, 0, 0)).box(10, 8, 4)
    ).faces(">X").faces("<Z").workplane().hole(1)
)
show_object(result)
