# arris-gym

Run and score model-written CAD programs with deterministic rewards and
typed outcomes.

`arris-gym` is a Python library. It runs model-written CAD programs on the
[`arris`](https://pypi.org/project/arris/) B-Rep kernel in a sandbox, returns a
typed outcome for every program, and scores the result against a target. It
speaks `arris.build` and a CadQuery-compatible subset for programs from public
CAD-code benchmarks and models. MIT OR Apache-2.0.

## Status

Pre-alpha, Linux only (x86-64 and AArch64, with user namespaces, Landlock,
`mount_setattr` and seccomp). What runs today:

- `run`, `run_many` and `Sandbox` execute a program in the `arris` dialect or
  the `cq` subset in an isolated worker and return a frozen `ExecResult` with
  one of eight statuses. The sandbox caches results and `digest` hashes
  them in order.
- `score` gives every result a reward. Valid bodies receive IoU, surface,
  measures and topology terms alongside BenchCAD's voxel IoU and Chamfer
  metrics. The IoU uses B-Rep interference where the kernel answers and
  seeded mesh sampling otherwise. `read_target` reads a STEP as a target.
- `arris-gym census --corpus benchcad` and `--corpus cadrecode` count the API
  forms and compute static reach without running the programs. From a
  repository checkout, `arris-gym rescore benchcad` scores a 300-program
  slice against committed STEP targets from CadQuery. Use
  `arris-gym rescore benchcad --score-timeout SECONDS` to set the deadline
  per score worker, which defaults to 30 seconds. These commands need
  the `arris-gym[corpus]` extra.

The CadQuery subset covers workplane and sketch operations, booleans,
axis selectors, drilling, blends and supported loft, draft and shell forms.
`arris_gym.cq.subset()` lists the declared forms and selectors. Calls outside
the subset, including CadQuery STEP export, return `unsupported_api`.
The library provides execution and scoring for external training loops.
[Supported forms][forms] · [Changelog][changelog]

With arris 0.12.0, static reach is 15,656 of 17,900 BenchCAD programs and all
968 CAD-Recode validation programs. Against committed CadQuery reports,
12,791 BenchCAD rows and 893 CAD-Recode rows agree. Both fidelity digests
match on x86-64 and AArch64. [BenchCAD fidelity][benchcad] ·
[CAD-Recode fidelity][cadrecode]

```python
import arris_gym as ag

program = """\
import cadquery as cq
result = cq.Workplane("XY").box(10, 8, 6)
"""
target = ag.run(program, dialect="cq")
assert target.body is not None, target.message
result = ag.run(program, dialect="cq", timeout=5.0)

s = ag.score(result, target.body)
print(result.status, result.message)
print(s.reward, s.iou, s.iou_route, s.field)
```

## Contributing

See [CONTRIBUTING.md][contributing].

## Licence

Dual-licensed under [MIT][mit] or [Apache-2.0][apache], at your option.

[forms]: https://github.com/arris-labs/arris-gym/blob/main/docs/ARCHITECTURE.md#dialects
[changelog]: https://github.com/arris-labs/arris-gym/blob/main/CHANGELOG.md
[benchcad]: https://github.com/arris-labs/arris-gym/blob/main/tests/fixtures/c2/benchcad/README.md#the-table
[cadrecode]: https://github.com/arris-labs/arris-gym/blob/main/tests/fixtures/c2/cadrecode/README.md#the-table
[contributing]: https://github.com/arris-labs/arris-gym/blob/main/CONTRIBUTING.md
[mit]: https://github.com/arris-labs/arris-gym/blob/main/LICENSE-MIT
[apache]: https://github.com/arris-labs/arris-gym/blob/main/LICENSE-APACHE
