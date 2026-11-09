import cadquery as cq

foot = cq.Workplane("XY").box(4, 2, 1)
wall = cq.Workplane("XY").transformed(offset=cq.Vector(-1.5, 0, 1.5)).box(1, 2, 3)
result = foot.union(wall)
show_object(result)
