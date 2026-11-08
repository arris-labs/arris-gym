import cadquery as cq

result = cq.Workplane().center(1, 2).circle(2).extrude(5).translate((0, 0, 3))
