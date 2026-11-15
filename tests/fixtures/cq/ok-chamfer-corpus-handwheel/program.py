import cadquery as cq

result = (
    cq.Workplane("YZ")
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(26.08, 13.04)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 16.76), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(16.76, 58.21)
    )
    .cut(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(30.08, 5.59)
    )
    .cut(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 16.76), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(20.76, 44.24)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(0.0, 0.0, 0.0))
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(90.0, 0.0, 0.0))
            .polyline([[11.04, -11.04], [11.04, 11.04], [46.24, 23.14], [46.24, 10.38]])
            .close()
            .extrude(3.26, both=True)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(0.0, 0.0, 120.0))
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(90.0, 0.0, 0.0))
            .polyline([[11.04, -11.04], [11.04, 11.04], [46.24, 23.14], [46.24, 10.38]])
            .close()
            .extrude(3.26, both=True)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(0.0, 0.0, 240.0))
            .transformed(offset=cq.Vector(0.0, 0.0, 0.0), rotate=cq.Vector(90.0, 0.0, 0.0))
            .polyline([[11.04, -11.04], [11.04, 11.04], [46.24, 23.14], [46.24, 10.38]])
            .close()
            .extrude(3.26, both=True)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(51.225, 0.0, 29.14), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(8.0, 6.0)
    )
    .union(
        cq.Workplane("YZ")
            .transformed(offset=cq.Vector(51.225, 0.0, 59.41), rotate=cq.Vector(0.0, 0.0, 0.0))
            .cylinder(52.54, 9.6)
    )
    .edges(">X")
    .chamfer(3.2)
)

# Export
show_object(result)
