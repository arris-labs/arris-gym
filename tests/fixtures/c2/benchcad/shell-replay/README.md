# BenchCAD shell replay

The 330 stems are the difference between the current reach and the reach
without `Workplane.shell(num)`, using the committed census. The list is
derived from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD),
`code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb`, under
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

```sh
root=tests/fixtures/c2/benchcad
work=$(mktemp -d .scratch/shell-replay.XXXXXX)
uv run --locked --extra corpus tools/cq_corpus.py --corpus benchcad \
  --slice "$root/shell-replay/stems.txt" --oracle-rows "$root/oracle.jsonl.gz" \
  --out-dir "$work/out" --work-dir "$work/chunks" --workers 16
```

The slice on arris 0.12.0 at `8f2be71` has 268 agreements and 62
unclassified rows. All 330 programs build on both sides. There are zero
timeouts and zero `cq_bug` rows. Each oracle row is identical to its
committed counterpart. The uncompressed slice oracle SHA-256 is
`1051c93e573013ee29015b11535be966dffc73b46cd211a7fb5bc6469701baf6`.
The fidelity table digest is
`d2e300c03099472d6e254035b42dfa786ae1240a756eb20fac15885eb9e310e2`.

| Family and operations | Rows | Agree | Unclassified |
|---|---:|---:|---:|
| Enclosure, shell alone | 56 | 56 | 0 |
| Enclosure, shell and floor fillet | 97 | 88 | 9 |
| Enclosure, shell, floor fillet and rectangular bore array | 21 | 19 | 2 |
| Tray, shell alone | 55 | 55 | 0 |
| Tray, rim chamfer before shell and floor holes after | 60 | 33 | 27 |
| Tray, rim chamfer before shell, floor holes and rectangular through-cut slots after | 41 | 17 | 24 |
| Total | 330 | 268 | 62 |

All 101 trays with a rim chamfer also have floor holes. The pinned final
reports exceed ADR-0005's volume limit for all 62 gaps. Sixteen tray rows
also exceed the centroid limit and one exceeds the area limit
(`sheet_metal_tray_010040_s20260505`). The largest relative volume gaps
are 2.28e-9 for enclosures and 1.94e-8 for trays.

Fresh prefix and final runs reproduce the 62 final gaps. The 11 enclosure
shell prefixes agree; the 11 floor fillet prefixes exceed the tolerance.
The [floor fillet regression](../../../regression/oracle-shell-floor-fillet/)
reduces the largest enclosure gap to the fillets alone. Its rectangular
section integral and the remeasured oracle STEP both match the arris build.

The 51 chamfered stock prefixes agree before shelling. In 49 of those
trays the gap appears at shelling, and all 49 also exceed the tolerance
after the holes. The other two, `sheet_metal_tray_002277_s20260505` and
`sheet_metal_tray_017786_s20260505`, first exceed the tolerance after
the through-cut slots. The [bare rim regression](../../../regression/oracle-shell-chamfered-rim-volume/)
checks the offset shell by section integration. The
[cut tray regression](../../../regression/oracle-shell-tray-through-cut/)
holds a trimmed body to the same construction with a floor bore and a
single through-cut across the floor and two walls. The arris build and
remeasured oracle STEP both match its closed form.

The 62 complete oracle STEP exports, read with `arris_gym.read_target`,
all agree with their corresponding arris-built bodies under ADR-0005,
including the solid count. Step 4 binds any verdicts to row evidence under
ADR-0006.
