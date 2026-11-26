# Adapted from BenchCAD sheet_metal_tray_000130_s20260505, CC-BY-4.0. See ../README.md.
from math import isclose, sqrt

import cadquery as cq

length, width, height = 235.97, 41.54, 39.03
chamfer, thickness = 0.96, 3.83
outer = (length - 2 * chamfer, width - 2 * chamfer)
inner = tuple(d - 2 * sqrt(2) * thickness for d in outer)
# The opening is on the stock's end plane. Each of its two loops has two
# edges of each transverse length. Check the loops through their edge lengths.
lengths = sorted(2 * list(outer) + 2 * list(inner))

stock = cq.Workplane("XZ").box(length, width, height).edges(">Y").chamfer(chamfer)
selected = stock.faces(">Y")
assert selected.size() == 1
face = selected.val()
assert isclose(face.Area(), outer[0] * outer[1])
assert isclose(face.Center().toTuple()[1], height / 2)

result = selected.shell(-thickness)
rim = result.faces(">Y")
assert rim.size() == 1
face = rim.val()
assert isclose(face.Center().toTuple()[1], height / 2)
assert isclose(face.Area(), outer[0] * outer[1] - inner[0] * inner[1])
actual = sorted(e.Length() for e in face.Edges())
assert all(isclose(want, got) for want, got in zip(lengths, actual, strict=True))
