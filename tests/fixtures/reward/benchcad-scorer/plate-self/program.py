import cadquery as cq

plate = cq.Workplane("XY").box(6, 4, 1)
hole = cq.Workplane("XY").circle(1).extrude(1)
result = plate.cut(hole)
show_object(result)
