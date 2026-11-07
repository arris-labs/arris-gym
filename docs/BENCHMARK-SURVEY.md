# CAD code generation: benchmark and RL survey

Date: 2026-11-07. Method: web search plus partial reads of BenchCAD and
Text2CAD-Bench. Most numbers below come from abstracts, search snippets or
summaries, not full-paper reads. **Verify any number against the paper before
citing it.** The cadbench.ai survey post (Hodges, 2026-06-15) is paywalled
and was not read.

## 1. Landscape

### Benchmarks (2025–2026)

| Benchmark | Task / input → output | Backend | Size | Notable result (unverified unless marked) |
|---|---|---|---|---|
| BenchCAD (2605.10865) | image → code, code edit, visual/code QA | CadQuery (OCCT) | 17.9k parts, 106 industrial families (52 anchored to ISO/DIN/…), 748 edit pairs | Data **CC-BY-4.0**, eval code MIT (read). A Qwen3-VL-2B trained with SFT + GRPO (reward 0.2·op recall + 0.8·IoU) scores 0.768 on image→code, above frontier models and the CADEvolve v3 specialist (0.601) |
| Text2CAD-Bench (2605.18430) | text → code, 4 levels | CadQuery 2.4 | 600 human-curated | Read: execution failure rate rises from ~11–20% (L1–L2) to 70–90% at L3, driven by sweep/loft/shell. Best L1 IoU 0.59 (GPT-5.2). IoU is a 256³ voxel grid over meshes, computed only over samples that executed |
| MUSE (2605.28579) | text → manufacturable, assemblable B-Rep | CAD code | — | Staged scoring (code → geometry → design intent); project leaderboard; GPT-5.5 67, Gemini 3.1 Pro 54 (self-reported) |
| Parametric CAD Bench / cadbench.ai, v3 (2611.02659) | text + engineering drawings → native FreeCAD parametric model, agentic | FreeCAD (OCCT) | 100 tasks | Editability gate (harmonic mean); scored on geometry, dimensions and history; GPT-5.5 via Codex 0.832; harness changes swing scores ~10% |
| CADWorld (2609.16251) | GUI computer use in FreeCAD, 11 workflow categories | FreeCAD | 200 tasks | Best agent 17.5% vs 87% expert |
| CADEngBench (2608.09296) | generation, functional edits, FEA, assembly | — | — | "Looks like CAD but does it work": no model leads across checks |
| HistCAD (2602.19171) | constraint-aware history representation + editability benchmark | — | — | Metrics for whether design intent survives a parameter edit; explicit constraints matter |
| RealCADBench (2609.03773) | parametric modelling from industrial design intents | — | — | Executability, IoU and visual-semantic identity scored separately |
| OmniMech (2608.05539) | drawings → parametric programs, agentic | — | — | VLM program synthesis unreliable |
| CadBench (2605.10873) | render → CadQuery | CadQuery | — | Frontier models evaluated (Gemini 3.1 Pro, GPT 5.4, Opus 4.7, Kimi K2.6) |
| Also named | CADGenBench (HF), P3D-Bench, Uni-CAD, CADEngBench, ExeCAD, CADExpert, AutoCAD bench | | | not examined |

### Models and RL work
- **CAD-Recode** (2412.14042): point cloud → CadQuery. Dataset of ~1M
  procedurally generated CadQuery programs on HF, **CC BY-NC 4.0**
  (non-commercial).
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
   gate + voxel IoU and/or Chamfer (+ an operation-recall term). Ours
   (SEED §7.1) is the same recipe. **The recipe is not a contribution.**
3. **Small specialised models beat frontier models in distribution.**
   BenchCAD's 2B model after SFT + RL tops its image → code track. "A
   7–14B model on one 5090 beats frontier models" is plausible, and
   others have already shown it.
4. **The field is far from saturated.** Execution failure dominates harder
   tasks (Text2CAD-Bench L3: 70–90%; sweep, loft and shell are the main
   failures). GUI agents get 17.5% of CADWorld. Design-intent and
   engineering-validity scores are low and inconsistent across models.

## 3. Weaknesses the papers share (where arris is strong)

| Weakness seen | What arris brings |
|---|---|
| IoU from voxelised meshes (256³) or renders; resolution-bound, normalisation often unstated | Exact B-Rep mass properties and (once bound) exact point classification |
| Metrics only over executed samples, so a high failure rate makes scores look better (Text2CAD-Bench notes this survivorship bias) | A typed status for every sample: refusal kind, checker failure, timeout. Report failures as first-class outcomes, never dropped |
| "Degenerate volume" heuristics instead of a validity check; invalid solids can score | The invariant checker on every result |
| No discussion of nondeterminism, kernel crashes or version pinning | Deterministic bit-for-bit, wasm included; no-panic contract |
| 30–60 s timeouts; heavy conda/OCCT installs | Pure-Rust wheel, `pip install`; cancellation by poll/budget |
| Editability is rare (HistCAD, cadbench.ai's gate, BenchCAD-Edit) and measured by re-rendering | Provenance: whether a tagged feature survives a parameter change is a fact, not a render comparison |
| Topological naming not addressed anywhere read | Provenance and roles are the kernel's contract |

## 4. What this changes in arris-gym

**Do not launch "yet another benchmark" as the north star.** At least a
dozen appeared in 2026, none is the standard, and a new one from a single
author is unlikely to become it. The open space is **the execution and
verification layer underneath them**: every benchmark above runs model code
on OCCT and scores it with mesh heuristics.

Revised strategy:

1. **CadQuery-compatible front end on arris** (`cq` subset over
   `arris.build`; CadQuery is Apache-2.0, an API-compatible
   reimplementation is clean). Start with the subset the corpora actually
   use: CAD-Recode's programs are sketch + extrude + booleans; BenchCAD
   lists 49 operations. Payoff:
   - existing benchmarks re-run on arris: exact, deterministic,
     checker-validated scoring with failures counted ("arris-verified"
     scores of BenchCAD, Text2CAD-Bench, …);
   - existing models (cadrille, CAD-Recode, frontier models prompted for
     CadQuery) run unchanged, so they are baselines on day one;
   - training data on day one: BenchCAD (CC-BY) for anything; CAD-Recode
     (CC BY-NC) for research only;
   - the largest stress corpus arris could get: ~1M programs, each
     agreement or disagreement with OCCT a measured fact. arris already
     has the OCCT oracle infrastructure to compare them.

   Risk: CadQuery's semantics are OCCT's (string selectors like `">Z"`,
   the workplane stack, tolerance behaviour). Fidelity is measured
   against CadQuery-on-OCCT as an oracle, per operation, and every
   difference is reported rather than hidden.
2. **arris-gym = the environment library**: sandbox, typed outcomes,
   exact rewards, determinism, used both for our training and as a
   drop-in scorer for others' benchmarks.
3. **One small benchmark of our own, only where the field is weak**:
   editability and design intent measured through provenance (perturb
   parameters; do tagged features survive and do dimensions hold?), and
   exact B-Rep reconstruction. Not a broad text → CAD benchmark.
4. **The trained model stays the proof**: an arris-native model, and a
   CadQuery-on-arris model, against published baselines on re-scored
   existing benchmarks.

Open questions:
- Front-end language: the `cq` subset first (reach) or `arris.build`
  first (expressiveness, provenance via `tag`)? Suggested: the `cq`
  subset for evaluation and data, `arris.build` for our own model, with a
  translation path between them.
- Licence boundary for weights trained on CC BY-NC data.
- Whether to contact one benchmark's authors (BenchCAD: CC-BY data, MIT
  eval) about an arris backend in their harness.

## Sources
- BenchCAD — https://arxiv.org/html/2605.10865v1
- Text2CAD-Bench — https://arxiv.org/html/2605.18430v1
- MUSE — https://arxiv.org/abs/2605.28579v2
- Parametric CAD Bench v3 — https://arxiv.org/html/2611.02659
- CADWorld — https://arxiv.org/pdf/2609.16251
- CADEngBench — https://arxiv.org/html/2608.09296v1
- HistCAD — https://arxiv.org/html/2602.19171v3
- RealCADBench — https://arxiv.org/html/2609.03773v1
- OmniMech — https://www.alphaxiv.org/abs/2608.05539
- CadBench — https://arxiv.org/html/2605.10873v1
- CAD-Recode — https://arxiv.org/pdf/2412.14042 ; dataset https://huggingface.co/datasets/filapro/cad-recode-v1.5
- cadrille — https://arxiv.org/html/2505.22914
- CAD-Coder — https://arxiv.org/html/2505.19713v3
- CME-CAD — https://arxiv.org/html/2512.23333v1
- ReCAD — https://arxiv.org/pdf/2512.06328
- RLCAD — https://arxiv.org/abs/2503.18549
- CADIR — https://arxiv.org/pdf/2608.00891
- LLM4CAD-Editor — https://arxiv.org/abs/2606.20607
- Reverse parametrisation — https://arxiv.org/html/2611.00777
- Benchmarks overview (paywalled) — https://hodgesj.substack.com/p/benchmarks-for-ai-models-and-agents
