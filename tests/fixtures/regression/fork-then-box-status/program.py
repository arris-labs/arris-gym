import os

import arris.build as b

os.fork()
result = b.Solid.box((0, 0, 0), (4, 5, 6))
