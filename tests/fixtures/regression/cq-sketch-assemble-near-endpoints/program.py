import cadquery as cq

s = cq.Workplane("XY").sketch()
s.segment((0, 0), (1, 0)).segment((1.00000001, 0), (0, 1)).segment((0, 0))
result = s.assemble().finalize().extrude(1)
