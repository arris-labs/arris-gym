import cadquery as cq

w = cq.Workplane("XY")
s = w.sketch().arc((28, 9), (36, 17), (28, 26))
s.segment((28, 25)).segment((30, 25)).segment((31, 10)).segment((28, 10))
r = s.close().assemble().finalize().extrude(5)
