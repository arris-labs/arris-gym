import cadquery as cq

tool = cq.Workplane("XY").sketch()
tool.segment((0, 0), (2, 0)).segment((0, 3)).close().assemble()
s = cq.Workplane("XY").sketch().circle(5).face(tool, mode="s")
result = s.finalize().extrude(2)
