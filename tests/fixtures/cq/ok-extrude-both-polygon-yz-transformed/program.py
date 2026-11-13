import cadquery as cq

result = (
    cq.Workplane("YZ")
    .transformed(offset=cq.Vector(1, 2, 3), rotate=cq.Vector(0, 0, 0))
    .polygon(4, 4)
    .extrude(1.5, both=True)
)
show_object(result)
