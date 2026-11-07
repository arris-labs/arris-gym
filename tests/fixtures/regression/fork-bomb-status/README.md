# fork-bomb-status

A plain fork bomb: every process forks until `RLIMIT_NPROC` refuses. Found by
the retirement review of plan `m0-sandbox`: each forked child inherited the
result pipe, ran the rest of `classify` and wrote a frame of its own, so the
frames joined into one that does not parse and the job was a `crash` (40 runs
in 40). Desired: the program worker's own `BlockingIOError`, `runtime`, every
run; only the program worker writes a frame.
