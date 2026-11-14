import cadquery as cq

result = (
    cq.Workplane("XY").moveTo(0, 0).lineTo(5, 0).lineTo(5, 4).lineTo(0, 4).close().revolve(360, (0, 0, 0), (0, 1, 0)).faces("<Y").workplane().circle(2).cutBlind(-1).faces("<Y").workplane().polarArray(3, 0, 360, 4).hole(1.4)
)
show_object(result)
