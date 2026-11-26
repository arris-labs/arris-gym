from arris.build import Solid
stock = Solid.box((-5, -4, -3), (5, 4, 3))
result = stock.shell(stock.faces().normal((0, 0, 1)).members, 1)
