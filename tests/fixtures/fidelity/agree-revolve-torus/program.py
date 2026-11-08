import arris.build as b

result = b.Workplane.XZ().circle(1, center=(3, 0)).revolve('y', 6.283185307179586)
