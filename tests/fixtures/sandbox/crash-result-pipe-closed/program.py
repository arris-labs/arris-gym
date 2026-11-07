# The program closes its result pipe; the worker cannot write its frame.
import os

import arris.build as b


def is_open(fd):
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


os.close(max(fd for fd in range(3, 1024) if is_open(fd)))
result = b.Solid.box((0, 0, 0), (1, 1, 1))
