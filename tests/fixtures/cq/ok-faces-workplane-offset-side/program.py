import cadquery as cq

result = (
    cq.Workplane("XY").box(4, 6, 8).faces("<X").workplane(offset=2.5).moveTo(1, 1).circle(1).extrude(1)
)
show_object(result)
