import cadquery as cq

part = cq.Workplane("XZ").moveTo(5, 0).circle(1).revolve(360, (0, 0, 0), (0, 1, 0))
part = part.cut(cq.Workplane("XY", origin=(-15, 0, 0)).box(30, 30, 30))
part.faces(">X").workplane()
show_object(part)
