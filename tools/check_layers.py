#!/usr/bin/env python3
"""The layer rule (docs/ARCHITECTURE.md §Modules), read from each module's AST.

Sees `import`, `from` (relative ones resolved) and `importlib.import_module`
with a literal name. A computed name evades it, as it would any static check.

Usage: tools/check_layers.py [--root DIR]    (DIR holds src/arris_gym)
Prints `file:line: why` per breach; exit 1 if any.
"""

import argparse
import ast
import pathlib
import sys
from collections.abc import Iterator

PACKAGE = "arris_gym"
# Never in library code: the oracle is run, not imported.
FORBIDDEN_EVERYWHERE = ("cadquery", "OCP", "tools")
# The core must stay usable without what is built on it.
CORE = ("sandbox", "reward", "cq")
FORBIDDEN_IN_CORE = (f"{PACKAGE}.train", f"{PACKAGE}.rescore")
# A score's path takes no BLAS and no vectorised transcendental
# (.agents/rules/gym.md, docs/ARCHITECTURE.md §Determinism): their last bits
# depend on the BLAS build and the CPU. `reward/` is where a score is made.
# The winding number's numpy `arctan2`, which only feeds a threshold, is not
# listed (`math.atan2` is). `**` is banned outright: a float base is invisible to ast.
NUMERIC_LAYER = "reward"
NUMPY_ROOTS = ("np", "numpy")
BANNED_NUMPY = frozenset(
    (
        *("dot", "vdot", "inner", "matmul", "einsum", "tensordot"),
        *("exp", "expm1", "exp2", "sin", "cos", "tan", "sinh", "cosh", "tanh"),
        *("log", "log2", "log10", "log1p", "power", "float_power", "hypot", "cbrt"),
        *("arcsin", "arccos", "arctan", "arcsinh", "arccosh", "arctanh"),
    )
)
BANNED_MATH = frozenset(
    (
        *("exp", "expm1", "exp2", "sin", "cos", "tan", "sinh", "cosh", "tanh"),
        *("log", "log2", "log10", "log1p", "pow", "hypot", "cbrt"),
        *("asin", "acos", "atan", "atan2", "asinh", "acosh", "atanh"),
        *("erf", "erfc", "gamma", "lgamma"),
    )
)


def within(name: str, root: str) -> bool:
    """Whether dotted `name` is `root` or lies under it."""
    return name == root or name.startswith(root + ".")


def resolve(node: ast.ImportFrom, module: str, is_package: bool) -> str:
    """The absolute name a `from` import refers to."""
    if node.level == 0:
        return node.module or ""
    parts = module.split(".")
    base = parts if is_package else parts[:-1]
    base = base[: len(base) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def imports(tree: ast.AST, module: str, is_package: bool) -> Iterator[tuple[int, str]]:
    """Every (line, absolute name) the module imports."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            base = resolve(node, module, is_package)
            yield node.lineno, base
            for alias in node.names:
                yield node.lineno, f"{base}.{alias.name}"
        elif isinstance(node, ast.Call):
            func = node.func
            called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if called in ("import_module", "__import__") and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    yield node.lineno, arg.value


def breach(name: str, layer: str) -> str | None:
    """Why `name` may not be imported from `layer`, if so."""
    for root in FORBIDDEN_EVERYWHERE:
        if within(name, root):
            return f"{name} is never imported by library code"
    if layer in CORE:
        for root in FORBIDDEN_IN_CORE:
            if within(name, root):
                return f"{layer} may not import {name}"
    if layer == "cq":
        top = name.split(".")[0]
        allowed = top == "arris" or top in sys.stdlib_module_names
        if not (allowed or within(name, f"{PACKAGE}.cq")):
            return f"cq imports only arris, not {name}"
    return None


def attribute_chain(node: ast.expr) -> list[str]:
    """The names of `a.b.c` as ["a", "b", "c"]; empty where its root is not a name."""
    names: list[str] = []
    while isinstance(node, ast.Attribute):
        names.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return []
    return [node.id, *reversed(names)]


def numeric_breaches(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Every (line, why) of the `reward` layer's banned operations: `@`, BLAS, libm, `**`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp | ast.AugAssign) and isinstance(node.op, ast.MatMult):
            yield node.lineno, "the matrix product `@` takes a BLAS path"
        elif isinstance(node, ast.BinOp | ast.AugAssign) and isinstance(node.op, ast.Pow):
            yield node.lineno, "`**` on a float calls libm pow: multiply instead"
        elif isinstance(node, ast.Attribute):
            chain = attribute_chain(node)
            if len(chain) < 2:
                continue
            root, name = chain[0], chain[-1]
            if root in NUMPY_ROOTS and (name in BANNED_NUMPY or "linalg" in chain[1:]):
                yield node.lineno, f"{'.'.join(chain)} takes a BLAS or CPU-dispatched path"
            elif root == "math" and name in BANNED_MATH:
                yield node.lineno, f"{'.'.join(chain)} follows the platform's libm"
            elif root == "random":
                yield node.lineno, "the global RNG: use numpy.random.Generator(PCG64(seed))"
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            top = node.module.split(".")[0]
            names = {alias.name for alias in node.names}
            if top == "random":
                yield node.lineno, "the global RNG: use numpy.random.Generator(PCG64(seed))"
            elif top in NUMPY_ROOTS and (
                "linalg" in node.module.split(".") or names & (BANNED_NUMPY | {"linalg"})
            ):
                yield node.lineno, f"{node.module} imports a BLAS or CPU-dispatched path"
            elif top == "math" and names & BANNED_MATH:
                yield node.lineno, "math's transcendentals follow the platform's libm"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "random":
                    yield node.lineno, "the global RNG: use numpy.random.Generator(PCG64(seed))"
                elif alias.name.startswith("numpy.linalg"):
                    yield node.lineno, "numpy.linalg takes a BLAS path"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default = pathlib.Path(__file__).resolve().parent.parent
    parser.add_argument("--root", type=pathlib.Path, default=default)
    root: pathlib.Path = parser.parse_args().root
    src = root / "src"
    bad = 0
    for path in sorted((src / PACKAGE).rglob("*.py")):
        relative = path.relative_to(src).with_suffix("")
        is_package = relative.name == "__init__"
        parts = relative.parts[:-1] if is_package else relative.parts
        module = ".".join(parts)
        layer = parts[1] if len(parts) > 1 else ""
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for line, name in imports(tree, module, is_package):
            why = breach(name, layer)
            if why:
                print(f"{path.relative_to(root)}:{line}: {why}", file=sys.stderr)
                bad += 1
        if layer == NUMERIC_LAYER:
            for line, why in numeric_breaches(tree):
                print(f"{path.relative_to(root)}:{line}: {why}", file=sys.stderr)
                bad += 1
    if bad:
        return 1
    print("check-layers: green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
