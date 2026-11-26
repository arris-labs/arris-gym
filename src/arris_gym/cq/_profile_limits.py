"""Profile limits shared by the CadQuery dialect and the census."""

# CadQuery's close adds a segment only when the gap exceeds this threshold
# in drawing units (cq.py). Otherwise the last segment ends at the start.
CLOSE_GAP = 1e-6

# Largest measured agreeing two-section loft under the corpus deadline.
# See curved-side-limit in lofts/runtime-contexts.json.
MAX_CURVED_SIDES = 48
