import cadquery as cq

axis = cq.Vector(0, 0, 1).normalized()
s = cq.Sketch().rect(10, 6).vertices().fillet(1)
result = cq.Workplane("XY").placeSketch(s).extrude(axis.z * 3)
show_object(result)
