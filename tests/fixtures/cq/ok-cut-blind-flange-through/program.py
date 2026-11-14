import cadquery as cq

result = cq.Workplane("XY").polyline([(2, 0), (5, 0), (5, 4), (2, 4)]).close().revolve(360, (0, 0, 0), (0, 1, 0)).faces(">Y").workplane().polarArray(3.5, 0, 360, 6).circle(0.5).cutBlind(-4)
show_object(result)
