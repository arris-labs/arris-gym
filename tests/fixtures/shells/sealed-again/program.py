from arris.build import Solid
stock = Solid.box((-5, -4, -3), (5, 4, 3))
result = stock.shell((), 1)
result = result.shell(result.faces().extreme((0, 0, 1)).members, 0.25)
