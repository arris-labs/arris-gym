import cadquery as cq

result = cq.Workplane("XY").polyline([(3, 1)]).circle(1).extrude(1)
