import cadquery as cq

result = cq.Workplane("XY").polyline([(3, 1)]).box(1, 1, 1)
