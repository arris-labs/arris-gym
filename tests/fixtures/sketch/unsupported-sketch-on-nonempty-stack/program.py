import cadquery as cq

result = cq.Workplane("XY").moveTo(2, 0).sketch().rect(2, 2).finalize().extrude(2)
