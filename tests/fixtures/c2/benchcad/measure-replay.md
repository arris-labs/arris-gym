# BenchCAD measure verdicts on arris 0.12.0

`measure-replay.txt` lists the 79 remaining `ok` / `ok` disagreements after
the solid-count check from ADR-0016. The source is the BenchCAD replay at
revision `5919f578ab09ec283603a082fab07c7639ab56eb`, with the committed
`oracle.jsonl.gz`. The full 0.12.0 baseline includes these verdicts
through the `--measure-replay` argument in `verdicts.args`.

```sh
root=tests/fixtures/c2/benchcad
uv run --locked --extra corpus tools/cq_closed_forms.py \
  --measure-replay "$root/measure-replay.txt" \
  --oracle-rows "$root/oracle.jsonl.gz" --out "$root/measure-verdicts.json"
```

The generator reruns arris and requires a matching program hash, two
successful builds, matching solid counts, and a measure disagreement
against the pinned oracle. It checks every cited cause before writing the
file. Two runs produce identical bytes (SHA-256
`3486762e8dd71559d34dd71c3fca7a748ccfe6dde7b294d58c1696b79a2e0307`).

| Family | Rows | Verdict | Evidence |
|---|---:|---|---|
| `bellows` | 40 | `arris_bug` | Circle intersections give the two clipped rims' extents. The pinned oracle bounds agree with the construction. Arris extends beyond it. See `regression/cq-revolved-cone-notches-bounds`. |
| `shaft_collar` | 11 | `arris_bug` | The three cuts repeat one transverse bore at mid-height. Uncut stock above or below the bore reaches the stock radius along the bore axis. The pinned bounds match that radius and arris extends past it on both sides. See `regression/cq-cross-hole-bounds`. |
| `dome_cap` | 25 | `occt_wrong` | The programmed circular arc, pocket, holes and rim blends give volume, area, centroid and bounds. Arris agrees with these measures under ADR-0005. The pinned oracle reports differ. |
| `torus_link` | 3 | `occt_wrong` | Independent boundary integration of the oracle's trim curves at two resolutions gives measures that agree with arris under ADR-0005. The pinned oracle reports differ. For `torus_link_019579_s20260505`, the centroid alone exceeds the agreement limit. |

ADR-0006 covers both evidence types. The bounds fixtures record the arris
defect even where the oracle's mass properties also differ from independent
measurements. The boundary integral uses the oracle's tight bounds as a
common check and independently integrates volume, area and centroid.
