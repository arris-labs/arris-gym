from arris.build import Sketch, Workplane

bottom = [(-3, -1), (3, -1), (3, 1), (-3, 1)]
top = [(1, -3), (1, 3), (-1, 3), (-1, -3)]
sections = [Workplane.XY().polygon(bottom), Workplane.XY(4).polygon(top[-1:] + top[:-1])]
result = Sketch.loft(sections, kind="smooth")
