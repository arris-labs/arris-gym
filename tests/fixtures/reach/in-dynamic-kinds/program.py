import cadquery as cq
size = 1
result = cq.Workplane('XY').box(size, size + 1, int('3'))
