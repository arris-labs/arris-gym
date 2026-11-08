import cadquery as cq

base = cq.Workplane("XY").box(20, 20, 4)
boss = base.union(cq.Workplane("XY").workplane(offset=4).circle(3).extrude(6))
result = boss.faces("<Z").hole(2.5)
