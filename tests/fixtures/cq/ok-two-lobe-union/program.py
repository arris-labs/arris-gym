import cadquery as cq

left = cq.Workplane("XY").circle(1).extrude(1)
right = cq.Workplane("XY").transformed(offset=cq.Vector(1, 0, 0)).circle(1).extrude(1)
show_object(left.union(right))
