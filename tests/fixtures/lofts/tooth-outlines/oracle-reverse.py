import cadquery as cq
from math import cos, sin, radians
points = [(-3,-2),(-1,-2),(-1,-3),(1,-3),(1,-2),(3,-2),(3,2),(0,3),(-3,2)]
section = cq.Workplane("XY")
c, s = cos(radians(0)), sin(radians(0))
outline = [(0+1*(x*c-y*s), 0+1*(x*s+y*c)) for x,y in points]
section = section.transformed(offset=(0, 0, 0)).polyline(outline).close()
c, s = cos(radians(11)), sin(radians(11))
outline = [(0.7+0.8*(x*c-y*s), 0.4+0.8*(x*s+y*c)) for x,y in points]
outline = outline[3:]+outline[:3]
outline = outline[::-1]
section = section.transformed(offset=(0, 0, 6)).polyline(outline).close()
result = section.loft(combine=False)
