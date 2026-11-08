import cadquery as cq

result = (
    cq.Workplane().box(10, 10, 10, centered=False)
    .faces('>Z').workplane(centerOption='ProjectedOrigin', origin=(0, 0, 0))
    .pushPoints([(5, 5)]).hole(4, 6)
)
