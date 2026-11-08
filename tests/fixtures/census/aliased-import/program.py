import cadquery as cad
from cadquery import Workplane as WP, Vector
import math

r = 2 * math.sqrt(2)
a = cad.Workplane("XY").polygon(6, r).extrude(1)
b = WP("XZ").center(*Vector(1, 2, 0).toTuple()[:2]).rect(1, 1).extrude(1)
result = a.cut(b)
show_object(result)
