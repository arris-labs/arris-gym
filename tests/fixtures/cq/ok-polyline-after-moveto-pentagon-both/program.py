import cadquery as cq

result = cq.Workplane("XY").moveTo(7.7942, 4.5).polyline([[0.0, 9.0], [-7.7942, 4.5], [-7.7942, -4.5], [-0.0, -9.0], [7.7942, -4.5]]).close().extrude(4.8, both=True)
show_object(result)
