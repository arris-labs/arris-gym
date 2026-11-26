import cadquery as cq

result = cq.Workplane("XY").rect(4, 3).extrude(2, taper=-1e-10)
