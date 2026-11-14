import cadquery as cq

result = (
    cq.Workplane("XY").box(10, 8, 4).faces(">Z").workplane().circle(2).cutBlind(-1).faces(">Z").workplane().polarArray(2.5, 0, 360, 4).hole(2)
)
show_object(result)
