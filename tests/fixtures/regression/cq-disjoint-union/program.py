import cadquery as cq

w0 = cq.Workplane("XY")
r = w0.workplane(offset=1).moveTo(-3, 0).box(2, 2, 2).union(
    w0.workplane(offset=2).moveTo(3, 0).box(2, 2, 4)
)
