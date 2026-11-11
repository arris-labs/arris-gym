import cadquery as cq
def make():
    return cq.Workplane('XY').box(1, 2, 3)
result = make()
