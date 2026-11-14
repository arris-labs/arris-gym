import cadquery as cq

result = (
    cq.Workplane("XY").cylinder(2, 6).union(cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, 1)).cylinder(4, 2)).union(cq.Workplane("XY").transformed(offset=cq.Vector(0, 0, 3)).circle(6).circle(5).extrude(0.5)).faces(">Z").workplane().hole(1).faces(">Z").workplane().circle(3).cutBlind(-1)
)
show_object(result)
