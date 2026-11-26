from arris.build import Solid
stock = Solid.box((-5, -4, -3), (5, 4, 3))
compound = stock.fuse(stock.moved((14, 0, 0)))
result = compound.shell(compound.faces().normal((0, 0, 1)).members, 1)
