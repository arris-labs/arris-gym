# BenchCAD Vision2Code pilot

[ADR-0032](../../docs/adr/0032-freeze-benchcad-vision2code-targets-from-the-pinned-regrader.md)
records the upstream revision, target contract and isolation. The smoke
checks all 300 C1 IDs and reference program hashes, then captures the first
part by stem in each family. It writes reference exports, the candidate
exports from the extracted reference responses, canonical four-view PNGs,
Gym inspection dumps and a hash and parity record to a new output directory.

Run from the arris-gym root on Linux with unprivileged user namespaces,
bubblewrap, util-linux, system CPython 3.12 and software Mesa EGL.

```sh
git clone https://github.com/BenchCAD/BenchCAD-main.git .scratch/benchcad-upstream
uv sync --locked --project tools/oracle --python /usr/bin/python3.12
uv run --locked python tools/benchcad/vision2code.py smoke \
  --upstream .scratch/benchcad-upstream --out .scratch/benchcad-smoke
BENCHCAD_CHECKOUT=.scratch/benchcad-upstream \
  uv run --locked pytest tests/test_benchcad_vision2code.py -m 'oracle or not oracle'
```

The driver reads the upstream sources from the pinned Git object. It fetches
the pinned BenchCAD corpus through the usual Hugging Face cache. Set
`HF_HUB_OFFLINE=1` for a populated cache. The oracle-marked tests run
without the corpus or network after the upstream checkout and oracle venv
are present.

The [smoke fixtures](../../tests/fixtures/benchcad-vision2code/smoke/README.md)
are the frozen captured bytes and the upstream IoU record. Fresh capture
generates fresh STEP headers. Use the frozen files when checking the
recorded full-file hashes.

## One-shot generation

Use a bundle with the frozen manifest and `targets/ID.step` and
`renders/ID.png` for every official record ID. The generation command checks
every target and render hash, including for a smoke that selects a few IDs.
It runs the pinned upstream prompt builder with the default four camera
hints and its cached canonical render. The model gets the system and user
text and one four-view PNG. The pinned extractor converts the raw response
to the UTF-8 program stored for both graders. Generation runs neither grader.

The local worker uses Qwen/Qwen3-VL-4B-Instruct in BF16 on CUDA, with greedy
decoding and up to 2,048 generated tokens per image. Install the worker in
a separate Python 3.12 environment and cache the pinned Apache-2.0 model
once before running offline. [Model snapshot](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/tree/ebb281ec70b05090aa6165b016eac8ec08e71b17)

```sh
uv venv --python 3.12 .scratch/benchcad-vlm
uv pip install --python .scratch/benchcad-vlm/bin/python \
  --index-url https://download.pytorch.org/whl/cu128 \
  'torch==2.10.0+cu128' 'torchvision==0.25.0+cu128'
uv pip install --python .scratch/benchcad-vlm/bin/python \
  'transformers==4.57.6' 'pillow==12.1.1' 'safetensors==0.8.0' 'huggingface_hub==0.36.2'
.scratch/benchcad-vlm/bin/hf download Qwen/Qwen3-VL-4B-Instruct \
  --revision ebb281ec70b05090aa6165b016eac8ec08e71b17
uv run --locked python tools/benchcad/vision2code.py generate \
  --upstream .scratch/benchcad-upstream --bundle BUNDLE \
  --model-python .scratch/benchcad-vlm/bin/python --out BUNDLE/predictions.jsonl
```

The destination must be new. For a smoke, pass `--record-id ID` once per
selected ID and use a separate destination. The command writes one row per
completed attempt in official record ID order, keeping blank responses and
generation or extraction failures. A worker process failure exits with an
error and leaves the completed rows for diagnosis.

## Offline replay

```sh
uv run --locked python tools/benchcad/vision2code.py replay \
  --bundle BUNDLE --out OUT --workers 4 --score-timeout 60
```

Replay uses the main environment and a frozen bundle. It checks the entire
bundle before any scoring, including when `--record-id ID` selects a single
task. Use a new output directory. The score deadline defaults to Gym's 30 s.

- `manifest.json` is an object with `version` (1), `pins` and a nonempty
  `tasks` array. The pins are `code_gen_revision`, `upstream_commit` and
  `oracle_lock_sha256`. Each task records `record_id`, `stem`, `family`,
  `source`, `licence`, `reference_sha256`, `target_sha256`, `step_sha256`
  and `render_sha256`. An official record ID equals its stem.
- `targets/ID.step` holds the exact UTF-8 bytes used by both graders.
  `target_sha256` hashes the whole file and `step_sha256` hashes the data
  section. It is null if the STEP has no data section.
- `predictions.jsonl` contains one object per captured prediction. Each has
  `record_id`, `model`, `model_revision`, `licence`, `prompt`,
  `prompt_sha256`, `render_sha256`, `decoding` (an object), `raw_response`,
  `raw_response_sha256`, `program` and `program_sha256`. The `licence` field
  records the terms of the model snapshot. Text hashes cover
  the recorded UTF-8 bytes, including whitespace. A `generation_failed`
  record has null response and program. An `extraction_failed` record
  keeps the response and has null program. Both use the optional `failure`
  field and null hashes for absent text. A missing prediction row or an
  extracted blank program is counted, with Gym running an empty program.
- `upstream.jsonl` contains one object per manifest ID with `record_id`,
  `target_sha256`, `program_sha256` (null if absent) and `grade`. The grade
  has `outcome`, `iou` and an optional `message`. A `timeout` or `crash`
  also records `stage` as `export` or `scoring`. The hashes link the grade
  to the frozen inputs. A `scored` grade confirms export and a metric
  return. A reported zero can also come from the metric catching a
  failure, so these outcomes alone cannot establish upstream invalidity.

Replay writes `rescore.json` and `rescore.md` for Gym and
`comparison.json` and `comparison.md` for the join. The comparison uses
official record ID order, names timeout stages, counts all tasks, and
shows denominators for paired and survivor means. The digest is the
SHA-256 of sorted-key, compact JSON with ASCII escapes, excluding the
digest field and trailing newline. The comparison omits diagnostic
messages and timings. The Gym JSON and frozen upstream rows retain
diagnostic messages, and run timing belongs with the run evidence.
