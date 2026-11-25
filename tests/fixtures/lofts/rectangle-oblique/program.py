from arris.build import Sketch, Workplane
from math import cos, sin, radians

points = [(-3, -1), (3, -1), (3, 1), (-3, 1)]
sections = []
c, s = cos(radians(0)), sin(radians(0))
outline = [(0 + 1 * (x * c - y * s), 0 + 1 * (x * s + y * c)) for x, y in points]
sections.append(Workplane.XY(0).polygon(outline))
c, s = cos(radians(21)), sin(radians(21))
outline = [(0.7 + 0.8 * (x * c - y * s), 0.4 + 0.8 * (x * s + y * c)) for x, y in points]
sections.append(Workplane.XY(4).polygon(outline))
result = Sketch.loft(sections, kind="smooth")
