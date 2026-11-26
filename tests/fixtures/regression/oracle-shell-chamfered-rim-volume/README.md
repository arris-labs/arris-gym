# Oracle volume on a chamfered rim

An inward shell of thickness 0.5 opens the top of a 10 × 8 × 6 box with
a one-unit chamfer on its top edges. The difference of the two integrated
rectangular sections in `shells/README.md` gives volume 137.801863863674.
The oracle reports 137.801863613057, about 1.82e-9 relative away.
The strict regression in `test_shell_probe.py` compares the recorded
oracle measure against the construction under ADR-0005.
