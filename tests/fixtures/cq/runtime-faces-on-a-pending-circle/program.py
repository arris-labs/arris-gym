import cadquery as cq

result = (
    cq.Workplane("XY").circle(1).faces(">Z")
)
show_object(result)
