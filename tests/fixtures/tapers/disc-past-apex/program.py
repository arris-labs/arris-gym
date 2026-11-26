import math

import cadquery as cq

result = cq.Workplane("XY").circle(2).extrude(-4, taper=45)
