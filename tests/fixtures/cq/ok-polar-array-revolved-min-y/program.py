import cadquery as cq

result = cq.Workplane("XY").polyline([(0, 0), (5, 0), (5, 4), (0, 4)]).close().revolve(360, (0, 0, 0), (0, 1, 0)).faces("<Y").workplane().polarArray(3, 0, 360, 4).hole(1)
show_object(result)
