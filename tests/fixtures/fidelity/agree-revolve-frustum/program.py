import arris.build as b

result = b.Workplane.XZ().polygon([(0, 0), (2, 0), (1, 3), (0, 3)]).revolve('y', 6.283185307179586)
