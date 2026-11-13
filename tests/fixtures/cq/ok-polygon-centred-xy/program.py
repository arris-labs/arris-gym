import cadquery as cq

result = cq.Workplane("XY").polygon(6, 4).extrude(3)
