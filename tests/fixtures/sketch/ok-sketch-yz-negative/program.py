import cadquery as cq

s = cq.Workplane("YZ", origin=(7, -3, 5)).sketch()
s.push([(4, 2)]).rect(6, 4).circle(1, mode='s')
result = s.finalize().extrude(-3)
