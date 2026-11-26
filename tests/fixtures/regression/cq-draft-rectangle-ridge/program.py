import math

import cadquery as cq

result = cq.Workplane("XY").rect(4, 3).extrude(-4, taper=45)
