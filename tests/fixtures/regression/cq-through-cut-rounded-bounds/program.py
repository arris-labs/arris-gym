import cadquery as cq

result = cq.Workplane("XY").box(2, 2, 2).workplane(offset=1e17).circle(0.5).cutThruAll()
