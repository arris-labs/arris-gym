import cadquery as cq

with open("dims.txt") as f:
    h = float(f.read())
print(h)
result = cq.Workplane("XY").box(1, 1, h)
help(result)
exit()
