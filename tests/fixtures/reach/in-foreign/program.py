import math
from builtins import float
import cadquery as cq
result = cq.Workplane('XY').box(math.sqrt(1), float(2), abs(-3))
