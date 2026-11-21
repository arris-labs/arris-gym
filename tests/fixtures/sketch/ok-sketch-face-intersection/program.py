import cadquery as cq

tool = cq.Workplane("XZ", origin=(17, 19, 23)).sketch().rect(2, 2)
s = cq.Workplane("YZ", origin=(7, 8, 9)).sketch().rect(8, 4)
s.push([(-2, 0), (2, 0)]).face(tool, mode="i")
result = s.finalize().extrude(-2)
