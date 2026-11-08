import arris.build as b

result = b.Workplane.XZ().polygon([(1, 0), (3, 0), (3, 2), (1, 2)]).revolve('y', 6.283185307179586)
