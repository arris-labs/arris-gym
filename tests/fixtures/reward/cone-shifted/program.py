import math

import arris.build as b

# A cone frustum: radius 2 at z = 0 to radius 1 at z = 3, revolved about z.
frustum = b.Workplane.XZ().polygon([(0, 0), (2, 0), (1, 3), (0, 3)])
result = frustum.revolve(((0, 0), (0, 1)), math.tau)
