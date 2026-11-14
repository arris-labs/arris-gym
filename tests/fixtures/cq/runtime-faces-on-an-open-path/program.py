import cadquery as cq

result = (
    cq.Workplane("XY").moveTo(0, 0).lineTo(1, 0).faces(">Z")
)
show_object(result)
