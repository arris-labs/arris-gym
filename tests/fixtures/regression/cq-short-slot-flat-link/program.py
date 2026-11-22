import cadquery as cq

result = cq.Workplane("YZ").slot2D(23.9, 34.12, 0).extrude(9.9)
