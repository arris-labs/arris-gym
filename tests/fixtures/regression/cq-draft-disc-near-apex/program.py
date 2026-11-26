import cadquery as cq

result = cq.Workplane("XY").circle(2).extrude(2.828427110604055, taper=45)
