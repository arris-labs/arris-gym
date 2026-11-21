import cadquery as cq

w = cq.Workplane("XY")
tool = w.sketch().rect(2, 2).rect(4, 4, mode="s")
s = w.sketch().rect(2, 2).face(tool, mode="i")
result = s.finalize().extrude(2)
