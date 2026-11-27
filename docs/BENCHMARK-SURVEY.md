# CAD code generation: benchmark and RL survey

Survey begun 2026-11-07. Numbers marked with a table or section were checked
in the linked paper. **Verify other figures against the paper before citing
them.** The Hodges survey post from 2026-06-15 is paywalled.

## 1. Landscape

### Benchmarks (2025–2026)

| Benchmark | Task / input → output | Backend | Size | Notable result (unverified unless marked) |
|---|---|---|---|---|
| BenchCAD (2605.10865) | image → code, code edit, visual/code QA | CadQuery (OCCT) | 17,900 parts, 106 industrial families, 52 anchored to 47 industry codes, and 748 edit pairs (Tables 5 and 7) | Data **CC-BY-4.0**, eval code MIT. Table 10 gives an IID-trained Qwen3-VL-2B a Vision2Code total of 0.7682 after SFT and GRPO-style training. CADEvolve v3 scores 0.6014. |
| Text2CAD-Bench (2605.18430) | text → code, 4 levels | CadQuery 2.4 | 600 human-curated examples (Table 5) | Section 4.2.1 reports approximately 70–90% L3 invalidity for most models. Table 1 gives GPT-5.2 L1 IoU of 0.59 on geometric prompts and 0.62 on sequence prompts. Section 4.1.2 uses 256³ voxels and computes IoU and Chamfer only over executed samples. |
| MUSE (2605.28579v2) | text → manufacturable, assemblable B-Rep | CAD code | — | Code execution, geometric validity and design-intent alignment. With GPT-5.5 as judge, Table 9 reports mean design-intent scores of 67.14 for GPT-5.5 and 53.93 for Gemini 3.1 Pro. |
| Parametric CAD Bench / cadbench.ai, v3 (2611.02659) | text + engineering drawings → native FreeCAD parametric model, agentic | FreeCAD (OCCT) | 100 tasks (§3) | Section 4 combines geometry and specification scores by harmonic mean. In the paper's September 24 snapshot (§5.1), Claude Code with Opus 5.5 has the highest overall mean reward at 61.03%. |
| CADWorld (2609.16251) | GUI computer use in FreeCAD, 11 workflow categories | FreeCAD | 200 tasks (§3) | The best tested agent reaches 17.5% task success, against the 87.0% expert reference (§4.2). |
| CADEngBench (2608.09296) | generation, functional edits, FEA, assembly | — | — | "Looks like CAD but does it work": no model leads across checks |
| HistCAD (2602.19171) | constraint-aware history representation + editability benchmark | — | — | Metrics for whether design intent survives a parameter edit; explicit constraints matter |
| RealCADBench (2609.03773) | parametric modelling from industrial design intents | — | — | Executability, IoU and visual-semantic identity scored separately |
| OmniMech (2608.05539) | drawings → parametric programs, agentic | — | — | VLM program synthesis unreliable |
| CadBench (2605.10873) | render → CadQuery | CadQuery | — | Frontier models evaluated (Gemini 3.1 Pro, GPT 5.4, Opus 4.7, Kimi K2.6) |
| Also named | CADGenBench (HF), P3D-Bench, Uni-CAD, CADEngBench, ExeCAD, CADExpert, AutoCAD bench | | | not examined |

### Models and RL work
- **CAD-Recode** (2412.14042): point cloud → CadQuery. Dataset of ~1M
  procedurally generated CadQuery programs (§3.2), released on Hugging
  Face under **CC BY-NC 4.0**. arris-gym uses the original release's
  968-program validation split.
- **cadrille** (2505.22914): multimodal (point cloud / image / text) →
  CadQuery, SFT then online RL; state of the art on DeepCAD, Fusion360 and
  CC3D; RL drives the invalid rate to near zero. RL directly on point
  clouds was unstable.
- **CAD-Coder** (2505.19713, NeurIPS 2025): text → CadQuery, SFT + GRPO,
  chain-of-thought, geometric reward.
- **CME-CAD** (2512.23333): multi-expert GRPO. Argues plain RL with verifiable rewards exploits paths that already pay rather than exploring.
- **ReCAD** (2512.06328): RL + VLM for parametric CAD.
- **RLCAD** (2503.18549): an RL gym on a CAD engine; B-Rep → command
  sequences with revolve. The closest prior to "a kernel as a gym"; no
  public repository confirmed.
- **CADIR** (2608.00891): an executable IR across CAD backends for agentic
  generation and editing.
- Also seen: FEA-as-feedback agents (2605.17448), LLM4CAD-Editor
  (2606.20607), reverse parametrisation STEP → Grasshopper (2611.00777).

## 2. What the field converged on

1. **CadQuery is the lingua franca.** Nearly every benchmark and dataset
   targets CadQuery (OCCT underneath) or FreeCAD (also OCCT). The
   large training corpora are CadQuery programs.
2. **The RL recipe is standard.** SFT, then GRPO with reward = execution
   gate + voxel IoU and/or Chamfer, sometimes with an operation-recall
   term. The arris-gym reward combines IoU with surface, measures and
   topology terms.
3. **Small specialised models beat frontier models in distribution.**
   BenchCAD's IID-trained 2B model after SFT and RL leads the evaluated
   Vision2Code models in Table 10.
4. **The field is far from saturated.** Execution failure dominates harder
   tasks (Text2CAD-Bench L3: 70–90%; sweep, loft and shell are the main
   failures). The best tested CADWorld agent completes 17.5% of tasks.
   Design-intent and engineering-validity scores vary across models.

## 3. Weaknesses the papers share (where arris is strong)

| Weakness seen | What arris brings |
|---|---|
| Resolution-bound IoU from meshes (256³ in Text2CAD-Bench, 64³ in the pinned BenchCAD scorer) | B-Rep interference gives IoU where the kernel answers. A seeded mesh estimate covers the other pairs. [Field metrics](adr/0010-the-field-metrics-agree-with-benchcads-scorer-within-a-floor-and-a-tenth.md) |
| Text2CAD-Bench reports geometry metrics over executed samples, so the averages can improve as more executions fail | A typed status and reward for every program, with failures counted in aggregates |
| BenchCAD verifies its parts through execution, non-degenerate volume and expert visual review. Other benchmarks also check CAD artifacts or shape validity. | The invariant checker runs on every body returned by a program |
| Execution deadlines and kernel behaviour affect repeatability | Dependency versions, typed timeouts and digests. Fidelity replay holds oracle reports fixed and matches on Linux x86-64 and AArch64. [Replay evidence](adr/0030-c2-fidelity-replays-committed-oracle-reports.md) |
| Installing a CadQuery/Open CASCADE environment adds dependencies | The runtime uses the arris wheel. The comparison tools keep CadQuery in a separate oracle environment. |
| HistCAD, Parametric CAD Bench and BenchCAD-Edit measure different aspects of how designs respond to edits | The planned provenance-based evaluation would check whether a tagged feature survives a parameter change. |
| Topological naming not addressed anywhere read | Provenance and roles are the kernel's contract |

## 4. What this changes in arris-gym

**Do not launch "yet another benchmark" as the north star.** At least a
dozen appeared in 2026, none is the standard, and a new one from a single
author is unlikely to become it. The open space is **the execution and
verification layer for executable CAD programs**. The survey includes
CadQuery benchmarks and other evaluations, including FreeCAD GUI tasks and
engineering checks on saved artifacts.

Revised strategy:

1. **CadQuery-compatible subset over `arris.build`**. The census guides which
   forms to implement. CAD-Recode uses sketch, extrude and booleans.
   BenchCAD lists 49 CadQuery operations (§2). The subset supports the
   following work.
   - re-score existing benchmarks with checker-validated geometry and a
     reward for every result;
   - run CadQuery programs from existing models within the implemented subset
     and count refusals of unsupported API forms in the scores;
   - use BenchCAD and CAD-Recode data under their respective licences;
   - use the public programs as a stress corpus, with each
     agreement or disagreement with OCCT a measured fact. arris already
     has the OCCT oracle infrastructure to compare them.

   CadQuery and arris can differ in selector behavior, workplane stack
   semantics and tolerances. Fidelity compares each program against
   CadQuery on Open CASCADE and reports the disagreement class.
2. **Execution and scoring library** for external evaluations and training
   loops. The library runs programs in a sandbox and returns typed outcomes
   and deterministic rewards.
3. **One small benchmark of our own, only where the field is weak**:
   editability and design intent measured through provenance (perturb
   parameters; do tagged features survive and do dimensions hold?), and
   exact B-Rep reconstruction. Not a broad text → CAD benchmark.
4. **The trained model stays the proof**: an arris-native model, and a
   CadQuery-on-arris model, against published baselines on re-scored
   existing benchmarks.

Open questions

- Licence boundary for weights trained on CC BY-NC data.
- Whether to contact one benchmark's authors (BenchCAD: CC-BY data, MIT
  eval) about an arris backend in their harness.

## Sources
- BenchCAD — https://arxiv.org/html/2605.10865v1
- Text2CAD-Bench — https://arxiv.org/html/2605.18430v1
- MUSE — https://arxiv.org/html/2605.28579v2
- Parametric CAD Bench v3 — https://arxiv.org/html/2611.02659
- CADWorld — https://arxiv.org/html/2609.16251
- CADEngBench — https://arxiv.org/html/2608.09296v1
- HistCAD — https://arxiv.org/html/2602.19171v3
- RealCADBench — https://arxiv.org/html/2609.03773v1
- OmniMech — https://arxiv.org/abs/2608.05539
- CadBench — https://arxiv.org/html/2605.10873v1
- CAD-Recode — [paper](https://arxiv.org/pdf/2412.14042), [original dataset](https://huggingface.co/datasets/filapro/cad-recode)
- cadrille — https://arxiv.org/html/2505.22914
- CAD-Coder — https://arxiv.org/html/2505.19713v3
- CME-CAD — https://arxiv.org/html/2512.23333v1
- ReCAD — https://arxiv.org/abs/2512.06328
- RLCAD — https://arxiv.org/abs/2503.18549
- CADIR — https://arxiv.org/pdf/2608.00891
- FEA-as-feedback agents — https://arxiv.org/abs/2605.17448
- LLM4CAD-Editor — https://arxiv.org/abs/2606.20607
- Reverse parametrisation — https://arxiv.org/html/2611.00777
- Benchmarks overview (paywalled) — https://hodgesj.substack.com/p/benchmarks-for-ai-models-and-agents
