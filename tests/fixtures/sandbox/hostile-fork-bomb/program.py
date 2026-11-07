# Forks until the namespace's process limit refuses; every child sleeps, so the
# only way out is the parent's exception and PID 1's end killing them all.
import os
import time

while True:
    if os.fork() == 0:
        time.sleep(1000)
