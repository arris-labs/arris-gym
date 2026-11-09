"""The zygote process's entry: `python -m arris_gym.sandbox._zygote_main FD`.

It registers the jobs a layer above the sandbox defines, the score job
(`reward/_job.py`), before the zygote serves, so the zygote module itself
never imports `reward`, and every worker starts with the reward loaded. This
module is run, never imported.
"""

import sys

from arris_gym.reward import _job
from arris_gym.sandbox._zygote import JobKind, main, register

if __name__ == "__main__":
    register(JobKind.SCORE, _job.execute)
    sys.exit(main(sys.argv))
