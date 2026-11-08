#!/usr/bin/env python3
"""Measure the IoU's routes on the C1 slice: the exact route's budget, the sampled route's draw.

docs/plans/m4-reward.md step 2; its numbers are ADR-0008's. Three commands,
each short enough to run in pieces (`--start`/`--stop`) and outside the gate:

- `bodies` runs the slice under `dialect="cq"` in the sandbox (the pinned
  BenchCAD corpus, the `[corpus]` extra) and writes each `ok` body's bytes to
  `<dir>/<stem>.body` and every program's status to `<dir>/statuses.json`.
- `pairs` builds, for each body as the target, candidates by construction
  (the body moved by a fraction of its diagonal, turned about its box's
  centre, and the next body of its family as built), asks the exact route on a
  ladder of budgets, and runs every candidate sampled estimator on each pair
  the exact route answers; one JSON row per pair goes to `<dir>/pairs.jsonl`.
- `summary` prints the tables the ADR holds: every pair counted, the exact
  route's answers by budget, and each estimator's bias and RMSE against the
  exact IoU over the pairs it answered.

Bodies are read in-process on fresh models: the bodies were made in the
sandbox, and only this measuring tool, never the library, scores them here.
Wall-clock seconds are printed for the reader and reach no result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import statistics
import sys
import time
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

import arris
import numpy as np
import numpy.typing as npt

import arris_gym as ag
from arris_gym.reward._iou import exact_iou, inside

ROOT = pathlib.Path(__file__).resolve().parent.parent
C1 = ROOT / "tests" / "fixtures" / "c1"
TIMEOUT = 30.0

# The exact route's ladder: half decades of steps up to the cap, the largest
# the plan measured finishing (1e7 in 8 s on venturi_tube turned 7 degrees).
LADDER = (10**3, 3 * 10**3, 10**4, 3 * 10**4, 10**5, 3 * 10**5, 10**6, 3 * 10**6, 10**7)
# The candidates by construction: moves as fractions of the target's
# diagonal, turns in degrees about its box's centre, each in a direction
# drawn per pair from the stem's seed.
SHIFTS = (0.01, 0.03, 0.1, 0.3)
TURNS = (2.0, 7.0, 20.0)
# The chord fractions and point counts tried.
CHORDS = (1 / 50, 1 / 100, 1 / 200, 1 / 400)
POINTS = (2_000, 5_000, 10_000, 20_000)
# The chord the point-count study holds fixed, and the point count the chord
# study holds fixed (its sampling error then far below the chord's bias).
STUDY_CHORD = 1 / 200
STUDY_POINTS = 20_000
SEED = 20261109

_Floats = npt.NDArray[np.float64]
_Flags = npt.NDArray[np.bool_]
_Mesh = tuple[_Floats, _Floats, _Floats]
Classify = Callable[[_Floats], tuple[_Flags, _Flags]]


def read_slice(path: pathlib.Path) -> list[str]:
    """The stems of a slice file, sorted; `#` lines are its header."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return sorted(line for line in lines if line and not line.startswith("#"))


def bodies(out: pathlib.Path, start: int, stop: int | None, workers: int | None) -> int:
    """Run the slice's programs `start`:`stop` and keep each `ok` body's bytes."""
    from arris_gym.census import benchcad

    stems = read_slice(C1 / "slice.txt")[start:stop]
    by_stem = {p.stem: p for p in benchcad.read()}
    with ag.Sandbox() as sandbox:
        results = sandbox.run_many(
            [by_stem[s].text for s in stems], dialect="cq", timeout=TIMEOUT, workers=workers
        )
    out.mkdir(parents=True, exist_ok=True)
    index = out / "statuses.json"
    statuses: dict[str, str] = (
        json.loads(index.read_text(encoding="utf-8")) if index.is_file() else {}
    )
    for stem, result in zip(stems, results, strict=True):
        statuses[stem] = result.status.value
        if result.status is ag.Status.OK and result.body is not None:
            (out / f"{stem}.body").write_bytes(result.body.data)
    index.write_text(json.dumps(dict(sorted(statuses.items())), indent=1) + "\n", encoding="utf-8")
    print(Counter(statuses.values()), file=sys.stderr)
    return 0


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "little")


def _corners(model: arris.Model, body: arris.Body) -> tuple[_Floats, _Floats]:
    bounds = model.bounds(body)
    assert bounds is not None
    return np.array(bounds[0], dtype=np.float64), np.array(bounds[1], dtype=np.float64)


def _mesh(model: arris.Model, body: arris.Body, chord_fraction: float) -> _Mesh:
    low, high = _corners(model, body)
    diagonal = math.dist(low.tolist(), high.tolist())
    positions, triangles = model.tessellate(body, diagonal * chord_fraction).to_numpy()
    corners = np.asarray(positions, dtype=np.float64)[np.asarray(triangles, dtype=np.intp)]
    return corners[:, 0, :], corners[:, 1, :], corners[:, 2, :]


def _unit(rng: np.random.Generator) -> _Floats:
    v = rng.normal(size=3)
    return np.asarray(v / math.sqrt(float(v @ v)), dtype=np.float64)


def candidate(
    model: arris.Model, target: arris.Body, kind: str, value: float, seed: int
) -> arris.Body:
    """`target` moved by `value` of its diagonal, or turned `value` degrees about its centre."""
    rng = np.random.Generator(np.random.PCG64(seed))
    low, high = _corners(model, target)
    if kind == "shift":
        step = _unit(rng) * value * math.dist(low.tolist(), high.tolist())
        moved, _ = model.transform(target, tuple(step.tolist()))
        return moved
    centre = (low + high) / 2
    there, _ = model.transform(target, tuple((-centre).tolist()))
    turned, _ = model.transform(
        there, (0.0, 0.0, 0.0), axis=tuple(_unit(rng).tolist()), angle=math.radians(value)
    )
    back, _ = model.transform(turned, tuple(centre.tolist()))
    return back


# --- the candidate estimators -------------------------------------------------
# Each takes the joint box, a classifier (points -> inside A, inside B), the
# point count and a seed, and returns the IoU estimate and the points it
# classified (its cost).


def uniform(
    low: _Floats, high: _Floats, classify: Classify, n: int, seed: int
) -> tuple[float, int]:
    """Step 1's draw: `n` iid uniform points in the joint box, both counts unweighted."""
    rng = np.random.Generator(np.random.PCG64(seed))
    a, b = classify(low + rng.random((n, 3)) * (high - low))
    either = int(np.count_nonzero(a | b))
    return (int(np.count_nonzero(a & b)) / either if either else 0.0), n


def _cells(k: int) -> _Floats:
    i = np.arange(k, dtype=np.float64)
    gx, gy, gz = np.meshgrid(i, i, i, indexing="ij")
    return np.stack([gx.ravel(), gy.ravel(), gz.ravel()], axis=1)


def jittered(
    low: _Floats, high: _Floats, classify: Classify, n: int, seed: int
) -> tuple[float, int]:
    """One uniform point in each of k³ equal cells of the joint box, k the cube root of `n`."""
    k = max(1, round(n ** (1 / 3)))
    rng = np.random.Generator(np.random.PCG64(seed))
    unit = (_cells(k) + rng.random((k**3, 3))) / k
    a, b = classify(low + unit * (high - low))
    either = int(np.count_nonzero(a | b))
    return (int(np.count_nonzero(a & b)) / either if either else 0.0), k**3


def refined(
    low: _Floats, high: _Floats, classify: Classify, n: int, seed: int
) -> tuple[float, int]:
    """Strata by cell, weighted: the cells a surface crosses get the spare points.

    A quarter of `n` classes the centres of k³ cells; a cell whose centre's
    class differs from a face neighbour's (outside the grid counts as outside
    both) is a boundary cell. Every other cell gets one jittered point, the
    boundary cells share the rest equally, and each cell's fraction inside
    both and inside either is weighted by its volume, so the estimate keeps
    the uniform draw's expectation for each volume. The strata come from the
    centres, which are fixed, never from the points that are counted.
    """
    k = max(2, round((n / 4) ** (1 / 3)))
    cells = _cells(k)
    a0, b0 = classify(low + (cells + 0.5) / k * (high - low))
    cls = (a0.astype(np.int8) + 2 * b0.astype(np.int8)).reshape(k, k, k)
    padded = np.pad(cls, 1, constant_values=0)
    edge = np.zeros_like(cls, dtype=np.bool_)
    core = padded[1:-1, 1:-1, 1:-1]
    for axis in range(3):
        for shift in (-1, 1):
            edge |= np.roll(padded, shift, axis=axis)[1:-1, 1:-1, 1:-1] != core
    edge_flat = edge.ravel()
    boundary = int(np.count_nonzero(edge_flat))
    spare = n - k**3 - (k**3 - boundary)
    per = max(1, spare // boundary) if boundary else 1
    counts = np.where(edge_flat, per, 1)
    owner = np.repeat(np.arange(k**3), counts)
    rng = np.random.Generator(np.random.PCG64(seed))
    unit = (cells[owner] + rng.random((len(owner), 3))) / k
    a, b = classify(low + unit * (high - low))
    both = np.bincount(owner, weights=(a & b).astype(np.float64), minlength=k**3) / counts
    either = np.bincount(owner, weights=(a | b).astype(np.float64), minlength=k**3) / counts
    union = math.fsum(either.tolist())
    return (math.fsum(both.tolist()) / union if union else 0.0), k**3 + len(owner)


ESTIMATORS = {"uniform": uniform, "jittered": jittered, "refined": refined}


@dataclass(frozen=True)
class Job:
    """One target body and where its bytes and its family's next body are."""

    stem: str
    path: str
    neighbour: str
    neighbour_path: str


def _exact(model: arris.Model, a: arris.Body, b: arris.Body) -> dict[str, object]:
    """The exact route at the ladder's cap, then the smallest budget that answers."""
    began = time.perf_counter()
    try:
        value = exact_iou(model, a, b, budget=LADDER[-1])
    except arris.ArrisError as error:
        return {
            "exact": None,
            "error": type(error).__name__,
            "exact_seconds": time.perf_counter() - began,
        }
    seconds = time.perf_counter() - began
    for budget in LADDER:
        try:
            again = exact_iou(model, a, b, budget=budget)
        except arris.Interrupted:
            continue
        assert again == value, (again, value)
        return {"exact": value, "budget": budget, "exact_seconds": seconds}
    raise AssertionError("the cap answered but no rung did")


def _pair(
    model: arris.Model, a: arris.Body, b: arris.Body, seed: int, estimate: bool
) -> dict[str, object]:
    row = _exact(model, a, b)
    if not estimate or row["exact"] is None:
        return row
    low_a, high_a = _corners(model, a)
    low_b, high_b = _corners(model, b)
    low, high = np.minimum(low_a, low_b), np.maximum(high_a, high_b)
    meshes = {c: (_mesh(model, a, c), _mesh(model, b, c)) for c in CHORDS}
    row["triangles"] = {f"{c:.4g}": len(m[0][0]) + len(m[1][0]) for c, m in meshes.items()}

    def classify_at(chord: float) -> Classify:
        ma, mb = meshes[chord]
        return lambda p: (inside(p, ma), inside(p, mb))

    estimates: dict[str, float] = {}
    seconds: dict[str, float] = {}
    for chord in CHORDS:
        for name in ("jittered",):
            key = f"{name}/{STUDY_POINTS}/{chord:.4g}"
            t = time.perf_counter()
            estimates[key], _ = ESTIMATORS[name](low, high, classify_at(chord), STUDY_POINTS, seed)
            seconds[key] = time.perf_counter() - t
    for name, estimator in ESTIMATORS.items():
        for n in POINTS:
            key = f"{name}/{n}/{STUDY_CHORD:.4g}"
            if key in estimates:
                continue
            t = time.perf_counter()
            estimates[key], _ = estimator(low, high, classify_at(STUDY_CHORD), n, seed)
            seconds[key] = time.perf_counter() - t
    row["estimates"] = estimates
    row["seconds"] = seconds
    return row


KINDS: tuple[tuple[str, float], ...] = (
    ("self", 0.0),
    *(("shift", f) for f in SHIFTS),
    *(("turn", t) for t in TURNS),
    ("neighbour", 0.0),
)
"""The pairs each target body makes, in order: its index offsets the pair's seed."""


def run_pair(job: Job, index: int) -> dict[str, object]:
    """The row of `job`'s body as the target against its `index`-th candidate."""
    kind, value = KINDS[index]
    seed = _seed(job.stem) + index
    model = arris.Model()
    target = model.read_body(pathlib.Path(job.path).read_bytes()).body
    if kind == "self":
        other = target
    elif kind == "neighbour":
        other = model.read_body(pathlib.Path(job.neighbour_path).read_bytes()).body
    else:
        other = candidate(model, target, kind, value, seed)
    began = time.perf_counter()
    row: dict[str, object] = {"stem": job.stem, "kind": kind, "value": value}
    if kind == "neighbour":
        row["neighbour"] = job.neighbour
    row |= _pair(model, other, target, seed, estimate=kind != "self")
    row["pair_seconds"] = time.perf_counter() - began
    return row


def pairs(directory: pathlib.Path, start: int, stop: int | None, workers: int) -> int:
    """The pairs of bodies `start`:`stop` (in stem order), appended to `pairs.jsonl`."""
    statuses: dict[str, str] = json.loads((directory / "statuses.json").read_text("utf-8"))
    ok = [s for s, status in statuses.items() if status == "ok"]
    family = {s: s.rsplit("_", 2)[0] for s in ok}
    jobs = []
    for stem in ok:
        same = [s for s in ok if family[s] == family[stem]]
        nxt = same[(same.index(stem) + 1) % len(same)]
        jobs.append(Job(stem, str(directory / f"{stem}.body"), nxt, str(directory / f"{nxt}.body")))
    chosen = jobs[start:stop]
    path = directory / "pairs.jsonl"
    rows = [json.loads(line) for line in path.open(encoding="utf-8")] if path.is_file() else []
    measured = {(r["stem"], r["kind"], r["value"]) for r in rows}
    todo = [
        (job, index)
        for job in chosen
        for index, (kind, value) in enumerate(KINDS)
        if (job.stem, kind, value) not in measured
    ]
    done = 0
    began = time.perf_counter()
    # Each pair's row is written as it finishes and a measured pair is never
    # run again, so a run stopped by its deadline resumes where it stopped;
    # `summary` reads rows in any order.
    with ProcessPoolExecutor(max_workers=workers) as pool, path.open("a", encoding="utf-8") as out:
        futures = {pool.submit(run_pair, job, index): job for job, index in todo}
        for future in as_completed(futures):
            out.write(json.dumps(future.result()) + "\n")
            out.flush()
            done += 1
            seconds = time.perf_counter() - began
            print(f"{done}/{len(futures)} {futures[future].stem} {seconds:.0f}s", file=sys.stderr)
    return 0


def _stats(errors: Sequence[float]) -> str:
    bias = math.fsum(errors) / len(errors)
    rmse = math.sqrt(math.fsum(e * e for e in errors) / len(errors))
    worst = max(abs(e) for e in errors)
    return f"{bias:+.4f} | {rmse:.4f} | {worst:.4f}"


def summary(directory: pathlib.Path) -> int:
    """Print the tables: route counts over every pair, then each estimator's errors."""
    statuses: dict[str, str] = json.loads((directory / "statuses.json").read_text("utf-8"))
    rows = [json.loads(line) for line in (directory / "pairs.jsonl").open(encoding="utf-8")]
    print(f"programs {len(statuses)}: {dict(Counter(statuses.values()))}")
    ok = sorted(s for s, v in statuses.items() if v == "ok")
    seen = sorted({r["stem"] for r in rows})
    print(f"targets {len(seen)} of {len(ok)} ok bodies; pairs {len(rows)}")
    family = {s: s.rsplit("_", 2)[0] for s in ok}

    print("\n| family | kind | pairs | exact answers | refused (class) | over cap |")
    print("|---|---|---|---|---|---|")
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for r in rows:
        label = r["kind"] if r["kind"] in ("self", "neighbour") else f"{r['kind']} {r['value']:g}"
        groups.setdefault((family[r["stem"]], label), []).append(r)
    for (fam, label), group in sorted(groups.items()):
        refused = Counter(str(r["error"]) for r in group if r["exact"] is None)
        over = refused.pop("Interrupted", 0)
        answered = sum(r["exact"] is not None for r in group)
        print(f"| {fam} | {label} | {len(group)} | {answered} | {dict(refused)} | {over} |")

    exact = [r for r in rows if r["exact"] is not None]
    print(f"\nexact route: {len(exact)} of {len(rows)} pairs answer under {LADDER[-1]:.0e}")
    print("\n| budget | pairs answered at or under | of all pairs | slowest answer (s) |")
    print("|---|---|---|---|")
    for budget in LADDER:
        within = [r for r in exact if r["budget"] <= budget]
        slowest = max((r["exact_seconds"] for r in within), default=0.0)
        print(f"| {budget:.0e} | {len(within)} | {len(within) / len(rows):.3f} | {slowest:.2f} |")
    stopped = [r["exact_seconds"] for r in rows if r.get("error") == "Interrupted"]
    if stopped:
        print(f"seconds before the cap stopped a pair: median {statistics.median(stopped):.2f}")

    estimated = [r for r in exact if "estimates" in r]
    keys = sorted(
        {k for r in estimated for k in r["estimates"]},
        key=lambda k: (k.split("/")[0], int(k.split("/")[1]), -float(k.split("/")[2])),
    )
    for fam in ["all", *sorted({family[r["stem"]] for r in estimated})]:
        chosen = [r for r in estimated if fam in ("all", family[r["stem"]])]
        print(f"\nestimators, {fam}: {len(chosen)} answered non-self pairs (estimate - exact)")
        print("\n| estimator | points | chord | bias | RMSE | worst | median s |")
        print("|---|---|---|---|---|---|---|")
        for key in keys:
            name, n, chord = key.split("/")
            errors = [r["estimates"][key] - r["exact"] for r in chosen]
            secs = statistics.median(r["seconds"][key] for r in chosen)
            print(f"| {name} | {n} | {chord} | {_stats(errors)} | {secs:.3f} |")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """The three commands: `bodies`, `pairs`, `summary`."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("bodies", "pairs", "summary"))
    parser.add_argument("--dir", type=pathlib.Path, required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int)
    parser.add_argument("--workers", type=int, default=30)
    args = parser.parse_args(argv)
    if args.command == "bodies":
        return bodies(args.dir, args.start, args.stop, args.workers)
    if args.command == "pairs":
        return pairs(args.dir, args.start, args.stop, args.workers)
    return summary(args.dir)


if __name__ == "__main__":
    raise SystemExit(main())
