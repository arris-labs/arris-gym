import cadquery as cq

w = cq.Workplane("XY")
tool = w.sketch()
try:
    w.transformed(rotate=tool)
except Exception:
    result = w.transformed(offset=tool).box(2, 2, 2)
