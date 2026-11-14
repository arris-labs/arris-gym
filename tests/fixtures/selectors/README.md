# What CadQuery's axis selectors select, read on the oracle

ADR-0017's evidence (plans/lift-face-selectors step 2). Written by
`tools/cq_selector_probe.py` (CadQuery 2.3.0 on `cadquery-ocp` 7.9.3.0, oracle
zygotes, outside the gate):

```sh
cd tools
uv run --extra corpus python cq_selector_probe.py --range 0:300   --work-dir W
uv run --extra corpus python cq_selector_probe.py --range 300:620 --work-dir W
uv run --extra corpus python cq_selector_probe.py --range 620:950 --work-dir W
uv run python cq_selector_probe.py --constructed --merge --work-dir W
```

Each program runs with a prelude that wraps CadQuery's `Workplane.faces` and
`Workplane.workplane`. The first `workplane()` called on a stack `faces(sel)`
made records the stack, every candidate face (surface type, centre of mass along
the selector's axis, box along it, a plane's normal), the faces CadQuery kept
(their area, centre of mass, box centre, distance from the centre to the
surface, normal at the centre and at mid-parameter), the selection a box-centre
ranking with CadQuery's clustering would keep, and the plane `workplane()`
builds or the error it raises. Then it stops the program. Two runs give the same
bytes.

- `benchcad.jsonl.gz`: one row per program that `cq.subset()` with `faces(str)`,
  `hole(num)` and the six selectors `>X <X >Y <Y >Z <Z` admits and today's subset
  does not. That is 950 programs, sorted by stem. Each row has the program's
  SHA-256, family, licence and revision, `status` (`record`, or the oracle's
  status when no record was made) and the record. No program text is committed.
- `counts.json`: the rows counted by outcome (selector, number and surface type
  of the faces kept, plane or error, box-centre ranking agreeing or not), overall
  and by family.
- `constructed.json`: the constructions in `CONSTRUCTED` (own programs, text
  included) and their records. Their closed forms are held by
  `tests/test_selector_probe.py`.

What the rows show (held by `tests/test_selector_probe.py`): every one of the
950 reaches `workplane()` with no error. 910 keep one face and 40
(`connecting_rod`) keep two at one offset. Every kept face is planar with its
normal along the selector's signed axis. The plane is the parent plane's origin
moved onto the face along the axis, its x direction is CadQuery's
`_computeXdir`, and the box-centre ranking keeps the same faces. The nearest
key outside the kept cluster is 0.04 away. Every face whose plane is not normal
to the axis has its centre of mass more than 0.5% of the part's extent along
the axis inside the cluster's boundary.

The counts and stems are adapted from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
(`BenchCAD/BenchCAD`, `code_gen`, revision `5919f578ab09ec283603a082fab07c7639ab56eb`)
and shared under its [CC-BY-4.0 licence](https://creativecommons.org/licenses/by/4.0/).
