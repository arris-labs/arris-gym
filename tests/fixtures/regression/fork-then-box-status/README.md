# fork-then-box-status

A program that forks once and then builds the 4 x 5 x 6 box of
`sandbox/ok-box`, so both processes reach the end of the program. Found by
the retirement review of plan `m0-sandbox`: the child wrote a frame beside
the program worker's and the job was a `crash` in 39 runs of 40, `ok` in one,
by scheduling. Desired: `ok` with the box's measures (volume 4 x 5 x 6,
centroid at half each side), every run; only the program worker writes a frame.
