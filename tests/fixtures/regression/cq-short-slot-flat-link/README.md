# Flat link with a short slot

The fixture keeps the stock from `flat_link_000690_s20260505` in [BenchCAD](https://huggingface.co/datasets/BenchCAD/BenchCAD) `code_gen` revision `5919f578ab09ec283603a082fab07c7639ab56eb` ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0)).

The slot's 23.9 length is less than its 34.12 diameter. Its semicircles cross, and arris returns `SketchError` at construction. Open CASCADE builds a shape its checker rejects, as recorded in `oracle.json`. Both outcomes are independent of the bores that follow in the full program. ADR-0024 records the corresponding short-slot probe.
