import cadquery as cq


def peg(h):
    return cq.Workplane("XY").circle(1).extrude(h)


parts = [peg(2), peg(3)]
n = len(parts)
result = parts[0].union(parts[1])
for p in parts:
    result = result.union(p)
show_object(result)
