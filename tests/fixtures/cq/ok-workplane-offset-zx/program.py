import cadquery as cq

result = cq.Workplane("ZX", origin=(1, 2, 3)).workplane(offset=4).box(2, 4, 6)
