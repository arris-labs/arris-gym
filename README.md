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

Nothing runs yet: the package is a skeleton, and this is the design it is being
built to. [`SEED.md`](SEED.md) is the charter and
[`docs/ROADMAP.md`](docs/ROADMAP.md) says what comes first.

The intended use:

```python
import arris_gym as ag

target = ag.run(open("target.py").read(), dialect="cq").body
result = ag.run(model_output, dialect="cq", timeout=5.0)

if result.status is ag.Status.OK:
    s = ag.score(result, target)        # deterministic
    print(s.reward, s.iou, s.chamfer, s.field.voxel_iou_256)
else:
    print(result.status, result.message)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Dual-licensed under [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your
option.
