import cadquery as cq

ring = cq.Workplane("XY").circle(4).circle(1).extrude(5)
result = ring.edges(">Z").fillet(2)
