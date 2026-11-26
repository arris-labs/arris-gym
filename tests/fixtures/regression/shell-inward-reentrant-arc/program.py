from arris.build import Workplane
stock = Workplane.XY().polygon([(0, 0), (8, 0), (8, 4), (4, 4), (4, 8), (0, 8)]).extrude(6)
result = stock.shell(stock.faces().normal((0, 0, 1)).members, 1)
