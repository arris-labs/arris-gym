import cadquery as cq

result = cq.Workplane("XY").polyline([(0, 0), (5, 0), (5, 4), (0, 4)]).close().revolve(360, (0, 0, 0), (0, 1, 0)).faces(">Y").workplane().circle(1).cutBlind(-1)
show_object(result)
