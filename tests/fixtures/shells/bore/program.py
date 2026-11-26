from arris.build import Solid
stock = Solid.box((-5, -4, -3), (5, 4, 3))
result = stock.shell(stock.faces().normal((0, 0, 1)).members, 1)
result = result.cut(Solid.cylinder((0, 0, -4), (0, 0, 1), 1, 3))
