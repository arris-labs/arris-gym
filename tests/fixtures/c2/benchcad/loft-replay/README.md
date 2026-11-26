# BenchCAD loft, taper and mirror replay

The stem lists and verdicts are derived from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` and
shared under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
The replay uses arris 0.12.0 and the existing pinned oracle rows.

Regenerate the checked verdicts from the repository root.

```sh
root=tests/fixtures/c2/benchcad
work=$(mktemp -d .scratch/loft-verdicts.XXXXXX)
uv run --locked --extra corpus tools/cq_closed_forms.py \
  --oracle-rows "$root/oracle.jsonl.gz" --out "$work/verdicts.json" \
  @"$root/loft-replay/verdicts.args"
uv run --locked --extra corpus tools/cq_closed_forms.py \
  --oracle-rows "$root/oracle.jsonl.gz" --out "$work/trim-verdict.json" \
  @"$root/loft-replay/trim-verdict.args"
cmp "$work/verdicts.json" "$root/loft-replay/verdicts.json"
cmp "$work/trim-verdict.json" "$root/loft-replay/trim-verdict.json"
```

The 149 analytic knob verdicts integrate circular cross-sections of the
drafts, flutes and bore. For 32 programs the flutes intersect. The integral
splits at circle tangencies, crossings and cap planes, and uses only
exposed arcs of the stock and the union of the cutters. Green's theorem
gives the section areas and moments. Arc lengths and the slant factors
give the lateral areas. Differences of section areas give the flat
caps. The surviving stock reaches every bound, and the candidate and
pinned oracle count the same number of solids. The candidate agrees with
the integral on 144 programs. The pinned oracle agrees on
`knob_006103_s20260505` and `knob_002035_s20260506`. The remaining three
disagree with the construction on both sides. Their `arris_bug` verdict
uses the reduced intersecting-flute regression under ADR-0006.
Three I-beams, seven propellers, one gusset and one knob with intersecting
flutes use the independent trim integral under ADR-0006. Both quadratures
agree with each other, the candidate agrees with the integral and the
pinned oracle measures differ. Verdict replays use the corpus deadline.

For 41 propellers, the bored hub and the world vertices of the extruded
blades give the exact bounds. The candidate contains that box and extends
past it. Four gussets reproduce the outward-only bound excess of the
chamfer fixture, with the other judged measures within ADR-0005. Twelve
wing nuts reproduce the bore and fillet corner refusal on a pinned
`invalid` oracle row. Their refusal kind, message and two edges and a
vertex are checked against the reduced fixture. The distinct
`OpInternalError` in `wing_nut_016440_s20260505` reproduces the
missing trim edge in `cq-wing-fillet-missing-trim-edge`. Its verdict
records the candidate's internal error. The desired corner geometry
remains open on the reduced case.

The verdicts resolve all 227 initially unclassified rows. Halving the
integration step changed the three dual-failure knob volumes by less
than 8e-14 absolute.

| Knob | Candidate volume gap | Pinned oracle volume gap |
| --- | ---: | ---: |
| `knob_000910_s20260506` | 1.31e-9 | 9.34e-7 |
| `knob_001502_s20260506` | 1.39e-9 | 5.86e-6 |
| `knob_004904_s20260505` | 2.59e-9 | 1.03e-9 |

The eight other propellers use the geometry as written. The integral
clips the coaxial hub and the placed convex blade prisms in axial
sections. Exposed lines and circular arcs give area and first moments
by Green's theorem. Their lengths with the face slant factors give
the lateral areas, and section differences give the hub's flat faces.
The candidate's volume agrees with the construction within 7e-12
relative on every stem. Its area, centroid and bounds also meet
ADR-0005. The pinned oracle volume differs on all eight.

| Propeller | Pinned oracle relative volume gap |
| --- | ---: |
| `propeller_002511_s20260505` | 1.08e-9 |
| `propeller_004461_s20260505` | 1.19e-9 |
| `propeller_012902_s20260505` | 1.08e-9 |
| `propeller_012951_s20260505` | 1.24e-9 |
| `propeller_013267_s20260505` | 2.36e-9 |
| `propeller_017418_s20260505` | 1.08e-9 |
| `propeller_017762_s20260505` | 3.12e-9 |
| `propeller_019164_s20260505` | 4.14e-9 |

The static loft deferral excludes the 392 gear programs from reach
under ADR-0012. The replay retains every gear row and its `cq_bug`
class. The arris findings are recorded in
`../arris/docs/ideas/benchcad-loft-interpolation-and-body-check.md`.
The through-bore refusal in filleted I-beams is reproduced in
`regression/cq-filleted-beam-through-bore`. The consumer report is in
`../arris/docs/ideas/bore-through-a-filleted-beam.md`.

Replaying the 1,568 stems from the three lifts gave 832 agreements
and 736 disagreements, with zero unclassified rows and zero timeouts.
The 1,176 in-subset rows include zero `cq_bug` rows. Every oracle row
matched its pinned report. The table digest is
`eebe8e17988287db6e6000202b74e52a439b7db638915a8291c3445a86b39a96`.
