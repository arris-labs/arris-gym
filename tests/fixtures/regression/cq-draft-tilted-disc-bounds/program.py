import math

import cadquery as cq

result = cq.Workplane("XY").transformed(rotate=cq.Vector(1, 0, 0)).circle(1).extrude(math.sqrt(2), taper=-45)
