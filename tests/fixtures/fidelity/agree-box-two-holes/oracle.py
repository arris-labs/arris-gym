import cadquery as cq

result = (
    cq.Workplane().box(20, 10, 5, centered=False)
    .faces('>Z').workplane(centerOption='ProjectedOrigin', origin=(0, 0, 0))
    .pushPoints([(5, 5), (15, 5)]).hole(2)
)
