# cq-rivet-edges-across-revolve-axis

Reduced from `rivet_000039_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD)
`code_gen`, revision `5919f578ab09ec283603a082fab07c7639ab56eb`,
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). The shortened
shank preserves the head's circular arc and the edge selector.

On arris 0.12.0 the revolve builds. Before the amendment to ADR-0020,
`edges("<Y")` returned `unsupported_api` because the chain had no seam
placement. The selector ties the three circular rims and both seams in the
drawing plane. Chamfering skips the two seams and leaves one shell of genus
zero.

CadQuery 2.3.0 builds one solid, as recorded in `oracle.json` by
`uv run tools/oracle_run.py` on this program. Its chamfer joins the head
and shoulder at the same meridian coordinates as arris. The measures in
`expected.json` come from `rivet_closed_form` in `tools/cq_closed_forms.py`,
which sweeps the chamfered line and arc segments about the shank axis.
The pinned oracle figures differ from the form outside ADR-0005's limits.
The recorded comparison and the closed-form verdict are held in
`tests/test_cq_closed_forms.py`.

In the pinned BenchCAD corpus, CadQuery keeps all five candidates in
each of the 90 affected programs. The selectors are `<X` on 31 rows,
`<Y` on 32 and `<Z` on 27. The verdict generator checked all 90 as
`occt_wrong` against the existing oracle reports, and two runs over
these rows produced byte-identical verdicts.
