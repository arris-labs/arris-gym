"""The local one-shot Qwen3-VL worker and its text-and-image interface."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager, redirect_stdout
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

_MODEL = "Qwen/Qwen3-VL-4B-Instruct"
_REVISION = "ebb281ec70b05090aa6165b016eac8ec08e71b17"
_LICENCE = "Apache-2.0"
_DECODING = {"do_sample": False, "max_new_tokens": 2048}
_RUNTIME = {
    "torch": "2.10.0+cu128",
    "torchvision": "0.25.0+cu128",
    "transformers": "4.57.6",
    "pillow": "12.1.1",
    "safetensors": "0.8.0",
    "huggingface_hub": "0.36.2",
}


@contextmanager
def _model_process(python: Path) -> Iterator[Callable[[str, str, bytes], str | None]]:
    """Keep the pinned VLM loaded once in its separate Python environment."""
    with subprocess.Popen(
        [str(python.absolute()), str(Path(__file__).resolve())],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding="utf-8",
    ) as process:
        feed, responses = process.stdin, process.stdout
        assert feed is not None
        assert responses is not None

        def generate(system: str, user: str, render: bytes) -> str | None:
            feed.write(
                json.dumps(
                    {"system": system, "user": user, "render": base64.b64encode(render).decode()}
                )
                + "\n"
            )
            feed.flush()
            line = responses.readline()
            if not line:
                raise RuntimeError(f"generation worker exited with status {process.wait()}")
            raw = json.loads(line)
            if raw is not None and not isinstance(raw, str):
                raise ValueError("generation worker returned an invalid response")
            return raw

        try:
            yield generate
        finally:
            feed.close()
        if status := process.wait():
            raise RuntimeError(f"generation worker exited with status {status}")


def _run() -> None:
    import torch  # type: ignore[import-not-found]
    from PIL import Image  # type: ignore[import-not-found]
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration  # type: ignore[import-not-found]

    processor = AutoProcessor.from_pretrained(_MODEL, revision=_REVISION, local_files_only=True)
    model = (
        Qwen3VLForConditionalGeneration.from_pretrained(
            _MODEL, revision=_REVISION, local_files_only=True, dtype=torch.bfloat16
        )
        .to("cuda")
        .eval()
    )
    for line in sys.stdin:
        request = json.loads(line)
        raw = None
        try:
            with Image.open(BytesIO(base64.b64decode(request["render"]))) as opened:
                image = opened.convert("RGB")
            messages = [
                {"role": "system", "content": [{"type": "text", "text": request["system"]}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": request["user"]},
                    ],
                },
            ]
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
            ).to("cuda")
            with torch.inference_mode():
                tokens = model.generate(**inputs, **_DECODING)
            raw = processor.decode(tokens[0, inputs.input_ids.shape[1] :], skip_special_tokens=True)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"generation failed: {exc}", file=sys.stderr)
        # Use the protocol stream even when library output goes to stderr.
        print(json.dumps(raw), file=sys.__stdout__, flush=True)


if __name__ == "__main__":
    with redirect_stdout(sys.stderr):
        for package, expected in _RUNTIME.items():
            actual = version(package)
            if actual != expected:
                raise RuntimeError(f"generation needs {package} {expected}, found {actual}")
        _run()
