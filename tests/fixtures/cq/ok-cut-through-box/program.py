import cadquery as cq

block = cq.Workplane("XY").box(4, 4, 4)
bar = cq.Workplane("XY").box(1, 1, 6)
show_object(block.cut(bar))
