import math

import cadquery as cq

result = cq.Workplane("XY").circle(2).extrude(math.sqrt(8), taper=45)
