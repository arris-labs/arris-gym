import cadquery as cq

result = cq.Workplane("XY").pushPoints([(0, 0), (2, 2), (2, 0)]).rect(2, 2).center(7, -3).extrude(2)
show_object(result)
