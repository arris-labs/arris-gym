import cadquery as cq

result = cq.Workplane().box(10, 10, 10, centered=False).cut(
    cq.Workplane().box(5, 5, 12, centered=False).translate((6, 6, -1))
)
