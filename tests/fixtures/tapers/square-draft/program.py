import math

import cadquery as cq

result = cq.Workplane("XY").rect(4, 4).extrude(math.sqrt(5), taper=math.degrees(math.atan(1/2)))
