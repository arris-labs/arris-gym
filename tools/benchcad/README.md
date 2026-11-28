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
