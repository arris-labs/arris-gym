import cadquery as cq

result = cq.Workplane("XY").rect(4, 4).extrude(2.828427110604055, taper=45)
