import cadquery as cq

result = cq.Workplane("XY").pushPoints([(0, 0), (0, 1), (1, 0)]).rect(2, 2).extrude(1)
show_object(result)
