# Rounded outward box shell

The oracle's default join rounds the convex edges of the exterior.
The pinned arris shell keeps them sharp. The sharp control is
`shells/outward-sharp`. The strict regression expects the default arc body.

For unit offset, the expanded horizontal rectangle has area 116 + π.
Its six-unit extrusion meets the lower unit of the offset, where the
horizontal radius is √(1 − u²) at depth u below the original bottom.
Integrate 80 + 36√(1 − u²) + π(1 − u²) there, then subtract the original
box. The arc surfaces add eight cylinders and four spherical octants.
Integrating z times the slice area yields the vertical centroid.
The total area is 628 + 33π, including the cavity and rim.
