# A forger whose bytes are not a body at all: reading them back fails with
# something other than the checker's rejection, so the result is runtime.
import dataclasses

import arris.build as b


class Forger:
    def write_body(self, body):
        return b"not a body"


result = dataclasses.replace(b.Solid.box((0, 0, 0), (1, 1, 1)), model=Forger())
