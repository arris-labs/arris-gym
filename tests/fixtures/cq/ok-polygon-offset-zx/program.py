import cadquery as cq

result = cq.Workplane("ZX").workplane(offset=2).polygon(3, 6).extrude(-4)
