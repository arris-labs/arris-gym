"""The oracle's self-test: trusted programs against closed forms.

Run: ``uv run --project tools/oracle tools/oracle/selftest.py``. Every expected
value is a closed form or follows from how the part is built, never the
oracle's own output. The programs are trusted (ours), so they run unisolated.
"""

from __future__ import annotations

import math
import sys
from typing import Any

from worker import run_program

# Open CASCADE's GProp integrates analytic solids to this relative accuracy.
REL = 1e-9

BOX = "import cadquery as cq\nresult = cq.Workplane().box(2, 3, 4)\nshow_object(result)\n"
CYL = "import cadquery as cq\nresult = cq.Workplane().circle(1.5).extrude(4)\nshow_object(result)\n"
# box 4 x 6 x 10 centred on the origin, a through hole of radius 1 on z.
HOLE = (
    "import cadquery as cq\n"
    "result = cq.Workplane().box(4, 6, 10).faces('>Z').workplane().hole(2)\n"
    "show_object(result)\n"
)
# Result left in `result` only, no show_object: the fallback form.
PLAIN = "import cadquery as cq\nresult = cq.Workplane().box(1, 1, 1)\n"
SYNTAX = "def (:\n"
RUNTIME = "import cadquery as cq\nraise ValueError('boom')\n"
NO_RESULT = "import cadquery as cq\nx = cq.Workplane().box(1, 1, 1)\n"


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=REL, abs_tol=REL)


def _check_part(
    name: str,
    text: str,
    volume: float,
    area: float,
    faces: int,
    centroid: tuple[float, float, float],
) -> list[str]:
    r = run_program(text)
    bad: list[str] = []
    if r["status"] != "ok":
        return [f"{name}: status {r['status']}: {r['message']}"]
    m: dict[str, Any] = r["measures"]
    if not _close(m["volume"], volume):
        bad.append(f"{name}: volume {m['volume']} != {volume}")
    if not _close(m["area"], area):
        bad.append(f"{name}: area {m['area']} != {area}")
    if m["faces"] != faces or m["solids"] != 1:
        bad.append(f"{name}: faces/solids {m['faces']}/{m['solids']} != {faces}/1")
    if not all(_close(a, b) for a, b in zip(m["centroid"], centroid, strict=True)):
        bad.append(f"{name}: centroid {m['centroid']} != {centroid}")
    if not (isinstance(r["step_sha256"], str) and len(r["step_sha256"]) == 64):
        bad.append(f"{name}: no step hash")
    if run_program(text)["step_sha256"] != r["step_sha256"]:
        bad.append(f"{name}: step hash differs between runs")
    return bad


def main() -> int:
    bad: list[str] = []
    bad += _check_part("box", BOX, 24.0, 2 * (6 + 8 + 12), 6, (0, 0, 0))
    bad += _check_part("box-result-only", PLAIN, 1.0, 6.0, 6, (0, 0, 0))
    # cylinder r=1.5, h=4, base on z=0: centroid at mid-height.
    bad += _check_part(
        "cylinder", CYL, math.pi * 1.5**2 * 4, 2 * math.pi * 1.5 * (1.5 + 4), 3, (0, 0, 2)
    )
    # box minus hole: lateral wall of the hole is 2*pi*r*h, caps lose pi*r^2 each.
    bad += _check_part(
        "box-minus-hole",
        HOLE,
        4 * 6 * 10 - math.pi * 1**2 * 10,
        2 * (24 + 40 + 60) - 2 * math.pi * 1**2 + 2 * math.pi * 1 * 10,
        7,
        (0, 0, 0),
    )
    for name, text, status in (
        ("syntax", SYNTAX, "syntax"),
        ("runtime", RUNTIME, "runtime"),
        ("no_result", NO_RESULT, "no_result"),
    ):
        r = run_program(text)
        if r["status"] != status:
            bad.append(f"{name}: status {r['status']} != {status}")
    r = run_program(RUNTIME)
    if r["message"] != "ValueError: boom":
        bad.append(f"runtime message not verbatim: {r['message']!r}")
    for line in bad:
        print("FAIL", line)
    print("selftest:", "red" if bad else "green")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
