"""The zygote process's entry: `python -m arris_gym.sandbox._zygote_main FD`."""

import sys

from arris_gym.sandbox._zygote import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
