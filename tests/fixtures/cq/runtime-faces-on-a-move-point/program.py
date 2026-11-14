import cadquery as cq

result = (
    cq.Workplane("XY").moveTo(1, 1).faces(">Z")
)
show_object(result)
