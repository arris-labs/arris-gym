import cadquery as cq

s = cq.Workplane("XY").sketch()
tool = cq.Workplane("XY", origin=(17, 19, 0)).sketch()
tool.push([(1, -1)])
tool.rect(2, 2)
s.push([(5, 3)])
s.face(tool)
s.reset()
s.face(tool)
w = s.finalize()
result = w.extrude(2)
