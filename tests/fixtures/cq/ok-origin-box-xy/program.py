import cadquery as cq

result = cq.Workplane("XY", origin=(3, -5, 7)).box(2, 4, 6)
