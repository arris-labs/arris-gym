# A `Solid` whose model is a forger: the program worker delivers the bytes the
# forger writes, and only the body worker's reading of them decides.
import dataclasses
import struct

import arris.build as b

box = b.Solid.box((0, 0, 0), (4, 5, 6))


class Forger:
    """Writes the box with vertex 4, the corner (0, 0, 6), moved to (0, 0, 7).

    The vertices are written first and in order, so the first 6.0 in the
    bytes is vertex 4's z.
    """

    def write_body(self, body):
        data = box.model.write_body(body)
        return data.replace(struct.pack("<d", 6.0), struct.pack("<d", 7.0), 1)


result = dataclasses.replace(box, model=Forger())
