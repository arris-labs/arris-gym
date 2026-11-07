# The result pipe is the one descriptor above stdio a program worker holds.
import os


def is_open(fd):
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


fd = max(fd for fd in range(3, 1024) if is_open(fd))
chunk = bytes(2**20)
while True:
    os.write(fd, chunk)
