import arris.build as b

result = b.Workplane.XZ().start((0, -2)).arc_to((0, 2), tangent=(1, 0)).close().revolve('y', 6.283185307179586)
