import cadquery as cq

w = cq.Workplane("XY")
s = w.sketch().face(w.sketch())
result = w.box(1, 1, 1)
