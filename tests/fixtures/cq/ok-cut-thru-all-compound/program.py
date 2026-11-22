import cadquery as cq

result = cq.Workplane("XY").box(10, 8, 4).union(cq.Workplane("XY", origin=(0, 0, 8)).box(10, 8, 4)).workplane(offset=3).circle(1).cutThruAll()
show_object(result)
