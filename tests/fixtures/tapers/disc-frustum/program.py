import math

import cadquery as cq

result = cq.Workplane("XY").circle(2).extrude(math.sqrt(10), taper=math.degrees(math.atan(1/3)))
