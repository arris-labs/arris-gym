from arris.build import Solid
stock = Solid.cylinder((0, 0, 0), (0, 0, 1), 5, 6)
result = stock.shell(stock.faces().normal((0, 0, 1)).members, 1)
