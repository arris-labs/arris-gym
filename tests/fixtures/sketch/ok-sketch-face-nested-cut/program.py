import cadquery as cq

ring = cq.Workplane("XY").sketch().circle(4).circle(2, mode="s")
tool = cq.Workplane("XY").sketch().face(ring)
s = cq.Workplane("XY").sketch().circle(1).face(tool)
result = s.finalize().extrude(2)
