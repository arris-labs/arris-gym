import cadquery as cq
from math import cos, sin, radians
points = [(-3, -1), (3, -1), (3, 1), (-3, 1)]
section = cq.Workplane("XY")
c, s = cos(radians(0)), sin(radians(0))
outline = [(0+1*(x*c-y*s), 0+1*(x*s+y*c)) for x,y in points]
section = section.transformed(offset=cq.Vector(0, 0, 0)).polyline(outline).close()
c, s = cos(radians(90)), sin(radians(90))
outline = [(0+1*(x*c-y*s), 0+1*(x*s+y*c)) for x,y in points]
section = section.transformed(offset=cq.Vector(0, 0, 4)).polyline(outline).close()
result = section.loft(combine=False)
