import cadquery as cq

tool = cq.Workplane("XY").sketch().rect(2, 2)
s = cq.Workplane("XY").sketch()
s.face(tool, mode="a")
tool.rect(4, 4)
result = s.finalize().extrude(2)
