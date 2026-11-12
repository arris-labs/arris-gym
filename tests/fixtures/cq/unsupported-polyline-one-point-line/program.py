import cadquery as cq

result = cq.Workplane("XY").polyline([(3, 1)]).lineTo(4, 1).lineTo(4, 2).close().extrude(1)
