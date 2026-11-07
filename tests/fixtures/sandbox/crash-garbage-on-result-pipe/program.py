# Garbage ahead of the worker's own frame: the frame is not one whole.
import os

import arris.build as b


def is_open(fd):
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


os.write(max(fd for fd in range(3, 1024) if is_open(fd)), b"\xff garbage \x00")
result = b.Solid.box((0, 0, 0), (1, 1, 1))
