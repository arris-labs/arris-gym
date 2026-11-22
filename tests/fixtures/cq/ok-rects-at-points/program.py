import cadquery as cq

result = cq.Workplane("XY").pushPoints([(-3, -1), (2, 2)]).rect(2, 1).extrude(2)
show_object(result)
