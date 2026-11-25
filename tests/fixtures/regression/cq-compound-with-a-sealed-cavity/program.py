import cadquery as cq

torus = cq.Workplane("XY").moveTo(3, 0).circle(1).revolve(360, (0, 0, 0), (0, 1, 0))
box = cq.Workplane("XY", origin=(6, 0, 0)).box(4, 8, 6)
cavity = cq.Workplane("XZ", origin=(6, 0, 0)).cylinder(6, 1.5)
result = torus.union(box).cut(cavity)
