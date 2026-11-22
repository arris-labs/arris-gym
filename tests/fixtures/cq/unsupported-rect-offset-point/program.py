import cadquery as cq

result = cq.Workplane("XY").pushPoints([(0, 0, 1)]).rect(2, 1).extrude(2)
show_object(result)
