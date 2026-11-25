import cadquery as cq
from math import cos, sin, radians
result = cq.Workplane("XY").circle(2).workplane(offset=3).circle(1).loft(combine=False)
