import cadquery as cq

result = (
    cq.Workplane("XY").pushPoints([(0, 0), (3, 0)]).circle(1).extrude(2)
)
show_object(result)
