import cadquery as cq

result = cq.Workplane("ZX", origin=(3, -5, 7)).box(2, 4, 6)
