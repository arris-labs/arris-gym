raise AssertionError('a census must not execute me')
import cadquery as cq
result = cq.Workplane('XY').box(1, 2, 3)
