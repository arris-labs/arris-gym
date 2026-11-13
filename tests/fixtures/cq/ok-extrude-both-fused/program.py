import cadquery as cq

result = cq.Workplane("XY").box(6, 6, 2).union(
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(1, 0, 0), rotate=cq.Vector(0, 0, 0))
    .polygon(6, 2)
    .extrude(2, both=True)
)
show_object(result)
