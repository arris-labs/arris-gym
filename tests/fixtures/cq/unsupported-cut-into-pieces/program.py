import cadquery as cq

bar = cq.Workplane("XY").box(4, 1, 1)
slab = cq.Workplane("XY").box(1, 2, 2)
show_object(bar.cut(slab))
