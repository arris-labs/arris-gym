# arris-gym

Run, score and train CAD-code models on a kernel you can trust: exact,
deterministic, every failure counted.

`arris-gym` is a Python library. It runs model-written CAD programs on the
[`arris`](https://pypi.org/project/arris/) B-Rep kernel in a sandbox, returns a
typed outcome for every program, and scores the result against a target. It
speaks `arris.build` and a CadQuery-compatible subset, because CadQuery is what
public CAD-code benchmarks, datasets and models are written in. MIT OR
Apache-2.0.

## Status

Pre-alpha, Linux only (x86-64 and AArch64, with user namespaces, Landlock,
`mount_setattr` and seccomp). What runs today:

- `run`, `run_many` and `Sandbox` execute a program in the `arris` dialect or
  the `cq` subset in an isolated worker and return a frozen `ExecResult` with
  one of eight statuses; results are cached exactly and digested bit for bit.
- `score` gives a result its reward against a target body, with its IoU,
  surface, measures and topology terms and BenchCAD's own field metrics beside
  them; `read_target` reads a STEP as a target.
- `arris-gym census --corpus benchcad` counts the API a corpus writes, and
  `arris-gym rescore benchcad` re-scores a 300-program BenchCAD slice against
  CadQuery's own output (both need the `arris-gym[corpus]` extra).

The `cq` subset is still small (14 API forms: no selectors, `hole`,
`chamfer` or export yet), and nothing for training exists yet.
[`SEED.md`](SEED.md) is the charter, [`docs/ROADMAP.md`](docs/ROADMAP.md) says
what comes next and [`CHANGELOG.md`](CHANGELOG.md) what each change gives.

```python
import arris_gym as ag

target = ag.run(open("target.py").read(), dialect="cq").body
result = ag.run(model_output, dialect="cq", timeout=5.0)

s = ag.score(result, target)    # a failure gets its fixed reward, no kernel call
print(result.status, result.message)
print(s.reward, s.iou, s.iou_route, s.field)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Dual-licensed under [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your
option.
