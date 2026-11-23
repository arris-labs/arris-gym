# Through keyway after overlapping rim chamfers

The fixture reduces `cam_000896_s20260505` from [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb`. It retains the annular boss and the keyway dimensions from the [CC-BY-4.0 corpus](https://creativecommons.org/licenses/by/4.0/).

The rim radii are 3.84 and 1.635, leaving a 2.205-wide annular face. Its two 1.51-deep chamfers consume 3.02 across this face. The bevels intersect below the top face, so the desired result is the same `OpDegenerateError` as for a blend wider than its faces. The arris 0.11.1 full checker rejects the chamfered body. When the chain continues through the rectangular keyway cut, arris returns `OpInternalError` for a hole of the face arrangement with no enclosing region.

The pinned CADQuery and Open CASCADE oracle builds a shape that its checker reports as `invalid`. The exact fixture's report is in `oracle.json`.

arris 0.12.0 returns the expected `arris_refusal` with `OpDegenerateError` at the overlapping chamfers.
