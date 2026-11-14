import cadquery as cq

result = (
    cq.Workplane("XY").box(2, 2, 2).union(
        cq.Workplane("XY").transformed(offset=cq.Vector(5, 0, 1)).box(2, 2, 4)
    ).faces(">Z").workplane().circle(0.5).extrude(1)
)
show_object(result)
