import cadquery as cq

opts = {"alpha": 0.5}
result = (
    cq.Workplane(inPlane="XZ")
    .rect(8, 4, centered=(True, False))
    .extrude(-3, both=True, taper=None)
    .translate([0, 0, 1])
    .rotate(axisStartPoint=(0, 0, 0), axisEndPoint=(0, 0, 1), angleDegrees=-45.0)
)
show_object(result, **opts)
