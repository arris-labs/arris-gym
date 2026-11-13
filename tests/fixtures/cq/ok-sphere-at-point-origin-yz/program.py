import cadquery as cq

result = cq.Workplane("YZ", origin=(1, 2, 3)).moveTo(-2, 4).sphere(2.5)
