# cq-disjoint-union

The shape, not the text, of five programs of the original
[CAD-Recode corpus](https://huggingface.co/datasets/filapro/cad-recode/tree/17d554bbc50a23de6cf6a742a3e0ed867f000153/val)
validation split at revision `17d554bbc50a23de6cf6a742a3e0ed867f000153`
(stems `466`, `494`, `730`, `786`, `936`), by Danila Rukhovich, Elona Dupont,
Dimitrios Mallis, Kseniya Cherenkova, Anis Kacem and Djamila Aouada,
[CAD-Recode: Reverse Engineering CAD Code from Point
Clouds](https://arxiv.org/abs/2412.14042), shared under
[CC-BY-NC-4.0](https://creativecommons.org/licenses/by-nc/4.0/); this fixture
keeps that restriction. Each writes
`w0.workplane(offset=…).moveTo(x, y).box(…).union(w0.workplane(offset=…)…box(…))`
on `XY` with `origin=`, and its boxes do not meet: CadQuery 2.3.0 builds a
compound of two solids (three for `730`), `cq` ends `unsupported_api`
"a Workplane holding 2 solids" (ADR-0007: a compound is outside the subset),
an in-subset `cq_bug` row. Measured in plans/in-subset-cq-bugs step 8, once
`box` on a `moveTo` point was lifted, 2026-11-13.

Desired: `ok`, the two boxes' closed form in `expected.json` (shells 2, from
the construction; face counts carried, never judged, ADR-0005). ADR-0016
admits a compound as a result: one solid whose body holds a shell per piece,
measured and scored as any body. The lift (plans/in-subset-cq-bugs step 9,
2026-11-13) removes the strict `xfail`; the oracle's report of this program
gives the same volume, area, centroid and bounds with solids 2.
