import arris_gym.cq as cq
stock = cq.Workplane("XY").box(10, 8, 6)
result = stock.faces(">Z").workplane().circle(1).shell(-1).cutBlind(-0.5)
