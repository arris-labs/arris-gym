import cadquery as cq

result = cq.Workplane("XY").transformed(rotate=cq.Vector(1, 0, 0)).rect(4, 3).extrude(2, taper=20)
