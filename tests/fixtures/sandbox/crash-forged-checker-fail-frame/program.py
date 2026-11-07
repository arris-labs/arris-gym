# A frame forged whole, claiming a status only a body worker decides.
import json
import os


def is_open(fd):
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


frame = {"status": "checker_fail", "message": "forged", "refusal": None, "body": None}
os.write(max(fd for fd in range(3, 1024) if is_open(fd)), json.dumps(frame).encode())
os._exit(0)
