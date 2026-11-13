import cadquery as cq

result = cq.Workplane("YZ").moveTo(2, 1).polygon(5, 4).extrude(2)
