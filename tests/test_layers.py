"""tools/check_layers.py, run on small trees that break each rule."""

import pathlib
import subprocess
import sys

import pytest

CHECK = pathlib.Path(__file__).resolve().parent.parent / "tools" / "check_layers.py"


def check(root: pathlib.Path) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(CHECK), "--root", str(root)]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def tree(root: pathlib.Path, module: str, text: str) -> pathlib.Path:
    path = root / "src" / "arris_gym" / module
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return root


def test_this_repository_is_green() -> None:
    assert check(CHECK.parent.parent).returncode == 0


@pytest.mark.parametrize(
    ("module", "text"),
    [
        ("census/__init__.py", "import cadquery\n"),
        ("fidelity/x.py", "from OCP.gp import gp_Pnt\n"),
        ("rescore/x.py", "from tools.oracle import run\n"),
        ("sandbox/x.py", "from arris_gym.rescore import report\n"),
        ("sandbox/x.py", "from arris_gym import rescore\n"),
        ("reward/x.py", "import arris_gym.train.grpo\n"),
        ("reward/sub/x.py", "from ...train import grpo\n"),
        ("cq/x.py", "import numpy\n"),
        ("cq/x.py", "from arris_gym.reward import iou\n"),
        ("cq/x.py", "from .. import sandbox\n"),
        ("sandbox/x.py", "import importlib\nimportlib.import_module('arris_gym.rescore')\n"),
    ],
)
def test_a_breach_is_red(tmp_path: pathlib.Path, module: str, text: str) -> None:
    result = check(tree(tmp_path, module, text))
    assert result.returncode == 1
    assert module in result.stderr


@pytest.mark.parametrize(
    ("module", "text"),
    [
        ("cq/x.py", "import math\nimport arris\nfrom arris.build import Solid\n"),
        ("cq/sub/x.py", "from .. import y\nfrom ..y import z\n"),
        ("sandbox/x.py", "import numpy\nfrom arris_gym.cq import Workplane\n"),
        ("rescore/x.py", "from arris_gym.reward import score\n"),
    ],
)
def test_an_allowed_import_is_green(tmp_path: pathlib.Path, module: str, text: str) -> None:
    assert check(tree(tmp_path, module, text)).returncode == 0
