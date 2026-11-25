import cadquery as cq
from math import cos, sin, radians
result = cq.Workplane("XY").circle(2).workplane(offset=2).circle(1).workplane(offset=2).circle(2).loft(combine=False)
