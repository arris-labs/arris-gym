import math

import cadquery as cq

result = cq.Workplane("XY").transformed(rotate=cq.Vector(0, 0, 30)).rect(4, 3).extrude(math.sqrt(5), taper=-math.degrees(math.atan(1/2)))
