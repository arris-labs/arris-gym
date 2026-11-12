import cadquery as cq

result = cq.Workplane("YZ", origin=(3, -5, 7)).box(2, 4, 6)
