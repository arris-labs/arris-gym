"""What one program writes: its calls, argument forms, selector strings and end (ADR-0003).

A program is parsed with `ast.parse` and never compiled or run: parsing runs
nothing of it, so it may happen in the caller's process. CPython's limit on how
deep a tree `ast.parse` builds counts from the C stack depth it is called at,
so each program is parsed and counted on a fresh thread of a fixed stack size:
whether a program is counted depends on the program and the Python grammar
only, never on how deep the caller's stack is. Every traversal is iterative.
"""

from __future__ import annotations

import ast
import threading
import warnings
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, model_validator

Counts = tuple[tuple[str, int], ...]
"""A count per key, sorted by key, each key once, each count at least 1."""

CQ: Final = "cq"
"""The receiver of a call on the `cadquery` module, whatever alias binds it."""
BUILTIN: Final = "builtin"
"""The receiver of `show_object` and of Python's builtins, when the program leaves them unbound."""
UNKNOWN: Final = "?"
"""The receiver of a call the census cannot place; its callee is listed as written."""
NON_LITERAL: Final = "<non-literal>"
"""The selector string of a selector call whose selector is not a string literal."""

# The methods whose first positional argument (or `selector=`) is a selector string.
SELECTOR_METHODS: Final = ("faces", "edges", "vertices", "wires", "solids", "shells", "compounds")
_CADQUERY: Final = "cadquery"
_SHOW_OBJECT: Final = "show_object"
# The stack of the thread a program is parsed on. A thread's default stack
# comes from the process's `ulimit -s`; a fixed one makes the parser's own
# limits (`RecursionError`, `MemoryError`) the only ones a program meets. The
# deepest programs tried just inside them (about 5,000 chained calls, 6,000
# unary minuses) parse on 1 MiB on CPython 3.12; 256 KiB overflows.
_PARSE_STACK_BYTES: Final = 16 * 1024 * 1024
# `threading.stack_size` is process-wide: held while one parse thread starts.
_STACK_SIZE_LOCK: Final = threading.Lock()
# Python's own builtins: `vars(builtins)` of CPython 3.12 run with `-I -S`,
# less the module's own attributes (`__name__`, `__loader__`, ...). Written
# out, since what `site` or a notebook adds (`exit`, `help`, `display`)
# depends on the caller's process; a test holds it to the interpreter.
# Membership only: no order from this set reaches a result. One string keeps
# the 146 names on 19 lines rather than one per line.
_PYTHON_BUILTINS: Final = frozenset(
    """
ArithmeticError AssertionError AttributeError BaseException BaseExceptionGroup
BlockingIOError BrokenPipeError BufferError BytesWarning ChildProcessError
ConnectionAbortedError ConnectionError ConnectionRefusedError ConnectionResetError
DeprecationWarning EOFError Ellipsis EncodingWarning EnvironmentError Exception
ExceptionGroup False FileExistsError FileNotFoundError FloatingPointError FutureWarning
GeneratorExit IOError ImportError ImportWarning IndentationError IndexError
InterruptedError IsADirectoryError KeyError KeyboardInterrupt LookupError MemoryError
ModuleNotFoundError NameError None NotADirectoryError NotImplemented NotImplementedError
OSError OverflowError PendingDeprecationWarning PermissionError ProcessLookupError
RecursionError ReferenceError ResourceWarning RuntimeError RuntimeWarning
StopAsyncIteration StopIteration SyntaxError SyntaxWarning SystemError SystemExit
TabError TimeoutError True TypeError UnboundLocalError UnicodeDecodeError
UnicodeEncodeError UnicodeError UnicodeTranslateError UnicodeWarning UserWarning
ValueError Warning ZeroDivisionError __build_class__ __debug__ __import__ abs aiter all
anext any ascii bin bool breakpoint bytearray bytes callable chr classmethod compile
complex delattr dict dir divmod enumerate eval exec filter float format frozenset
getattr globals hasattr hash hex id input int isinstance issubclass iter len list locals
map max memoryview min next object oct open ord pow print property range repr reversed
round set setattr slice sorted staticmethod str sum super tuple type vars zip
""".split()  # noqa: SIM905
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _check_counts(name: str, counts: Counts) -> None:
    keys = [key for key, _ in counts]
    if keys != sorted(set(keys)):
        raise ValueError(f"{name} is not sorted by key with each key once")
    if any(count < 1 for _, count in counts):
        raise ValueError(f"{name} has a count below 1")


class CorpusProgram(_Frozen):
    """One program of a corpus: its `stem` (unique in the corpus), its family and its text.

    Guarantees nothing about `text`: it is a model-written program, parsed by
    the census and never run by it.
    """

    stem: str
    family: str
    text: str


class ProgramCensus(_Frozen):
    """What a parsed program writes, counted (ADR-0003).

    `calls` counts each call as `receiver.name` (`Workplane.extrude`); `forms`
    counts each call with its argument form (`Workplane.extrude(num;
    both=bool)`); `selectors` counts each selector string as written;
    `unknown` counts the callee text of each call whose receiver is `?`;
    `foreign` counts the calls (keyed as in `calls`) on `builtin` and on another
    module, which the ranking leaves out;
    `end_form` is the program's last statement, normalised. Guarantees every
    `Counts` sorted by key; refuses one that is not.
    """

    stem: str
    calls: Counts
    forms: Counts
    selectors: Counts
    unknown: Counts
    foreign: Counts
    end_form: str

    @model_validator(mode="after")
    def _counts_sorted(self) -> Self:
        for name in ("calls", "forms", "selectors", "unknown", "foreign"):
            _check_counts(name, getattr(self, name))
        return self


class Unparsable(_Frozen):
    """A program the census could not parse or walk: a census outcome, not a `Status`.

    Guarantees `kind` is the exception's class name and `message` its `str()`,
    both unchanged.
    """

    stem: str
    kind: str
    message: str


def census_program(program: CorpusProgram) -> ProgramCensus | Unparsable:
    """Count what `program` writes, or say why it cannot be parsed. Never raises on a program.

    Parses and never runs: the warning filters in force do not change the
    answer (a `SyntaxWarning` is never raised as an error here).

    >>> text = "import cadquery as cq\\nr = cq.Workplane('XY').box(1, 2, 3).faces('>Z')\\n"
    >>> c = census_program(CorpusProgram(stem="p", family="f", text=text))
    >>> c.calls
    (('Workplane.box', 1), ('Workplane.faces', 1), ('cq.Workplane', 1))
    >>> c.forms[0], c.selectors, c.end_form
    (('Workplane.box(num, num, num)', 1), (('>Z', 1),), 'r = …')
    >>> census_program(CorpusProgram(stem="q", family="f", text="x = (")).kind
    'SyntaxError'
    """
    outcome: list[ProgramCensus | Unparsable] = []
    thread = threading.Thread(target=lambda: outcome.append(_census_here(program)))
    with _STACK_SIZE_LOCK:
        previous = threading.stack_size(_PARSE_STACK_BYTES)
        try:
            thread.start()
        finally:
            threading.stack_size(previous)
    thread.join()
    return outcome[0]


def _census_here(program: CorpusProgram) -> ProgramCensus | Unparsable:
    """`census_program` on the calling thread, whose stack depth moves the parser's limit."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(program.text)
        return _count(program.stem, program.text, tree)
    # Any exception out of parse or walk makes the program unparsable, kept
    # verbatim: the census never raises on a program (ADR-0003).
    except Exception as error:  # noqa: BLE001
        return Unparsable(stem=program.stem, kind=type(error).__name__, message=str(error))


@dataclass(frozen=True)
class _Path:
    """A name bound by an import to a dotted path: `cadquery`, `cadquery.Workplane`, `math`."""

    path: str


_Binding = ast.expr | _Path | None
"""One binding of a name: an assigned value, an import, or None for anything else."""


class _Pending:
    """A chain rooted in a name whose root is not yet known (the fixpoint's bottom)."""


_PENDING: Final = _Pending()


class _Program:
    def __init__(self, tree: ast.Module) -> None:
        self.bindings: dict[str, list[_Binding]] = {}
        self._collect(tree)
        self.roots = self._resolve_roots()
        # The root of each chain link under the final `roots`, filled as calls are placed.
        self.placed: dict[ast.expr, str | _Pending | None] = {}

    def _bind(self, name: str, binding: _Binding) -> None:
        self.bindings.setdefault(name, []).append(binding)

    def _collect(self, tree: ast.Module) -> None:
        direct: dict[ast.Name, ast.expr] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        direct[target] = node.value
            elif (
                isinstance(node, ast.AnnAssign | ast.NamedExpr)
                and isinstance(node.target, ast.Name)
                and node.value is not None
            ):
                direct[node.target] = node.value
        for node in ast.walk(tree):
            match node:
                case ast.Name(id=name, ctx=ast.Store() | ast.Del()):
                    self._bind(name, direct.get(node))
                case ast.Import(names=aliases):
                    for alias in aliases:
                        if alias.asname is None:
                            top = alias.name.split(".")[0]
                            self._bind(top, _Path(top))
                        else:
                            self._bind(alias.asname, _Path(alias.name))
                case ast.ImportFrom(module=module, names=aliases, level=level):
                    for alias in aliases:
                        if alias.name == "*":
                            continue
                        local = alias.asname or alias.name
                        absolute = level == 0 and module is not None
                        self._bind(local, _Path(f"{module}.{alias.name}") if absolute else None)
                case (
                    ast.FunctionDef(name=name)
                    | ast.AsyncFunctionDef(name=name)
                    | ast.ClassDef(name=name)
                    | ast.arg(arg=name)
                    | ast.ExceptHandler(name=str() as name)
                    | ast.MatchAs(name=str() as name)
                    | ast.MatchStar(name=str() as name)
                    | ast.MatchMapping(rest=str() as name)
                ):
                    self._bind(name, None)

    def path_of(self, name: str) -> str | None:
        """The dotted path `name` is bound to, if every binding of it is the same import."""
        bindings = self.bindings.get(name, [])
        paths = {b.path for b in bindings if isinstance(b, _Path)}
        if len(paths) == 1 and all(isinstance(b, _Path) for b in bindings):
            return paths.pop()
        return None

    def dotted(self, node: ast.expr) -> str | None:
        """The import path of `a.b.c` whose `a` an import binds; None for anything else."""
        attrs: list[str] = []
        while isinstance(node, ast.Attribute):
            attrs.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return None
        path = self.path_of(node.id)
        if path is None:
            return None
        return ".".join([path, *reversed(attrs)])

    def chain_root(
        self,
        node: ast.expr,
        roots: dict[str, str | None],
        memo: dict[ast.expr, str | _Pending | None] | None = None,
    ) -> str | _Pending | None:
        """The root constructor of the chain `node` is: `Workplane` for `cq.Workplane(…).box(…)`.

        Every link walked has the same root, so with `memo` each is walked once
        over all the calls of a program, not once per call above it.
        """
        walked: list[ast.expr] = []
        root: str | _Pending | None = None
        while True:
            if memo is not None and node in memo:
                root = memo[node]
                break
            walked.append(node)
            if isinstance(node, ast.Call):
                path = self.dotted(node.func)
                if path is not None:
                    is_constructor = _is_cadquery(path) and "." in path
                    root = path.rsplit(".", 1)[-1] if is_constructor else None
                    break
                if isinstance(node.func, ast.Attribute):
                    node = node.func.value
                    continue
                break
            if isinstance(node, ast.Name) and node.id in roots:
                found = roots[node.id]
                root = _PENDING if found == "" else found
            break
        if memo is not None:
            for link in walked:
                memo[link] = root
        return root

    def _resolve_roots(self) -> dict[str, str | None]:
        # The least fixpoint over bottom ("") < one root < None (no single root).
        # Each name only moves up, so this ends within two passes per name.
        roots: dict[str, str | None] = dict.fromkeys(self.bindings, "")
        changed = True
        while changed:
            changed = False
            for name, bindings in self.bindings.items():
                found = self._root_from(bindings, roots)
                if found != roots[name]:
                    roots[name] = found
                    changed = True
        return {name: (root or None) for name, root in roots.items()}

    def _root_from(self, bindings: Iterable[_Binding], roots: dict[str, str | None]) -> str | None:
        found: set[str] = set()
        for binding in bindings:
            if not isinstance(binding, ast.expr):
                return None
            root = self.chain_root(binding, roots)
            if root is None:
                return None
            if isinstance(root, str):
                found.add(root)
        if len(found) > 1:
            return None
        return found.pop() if found else ""


def _is_cadquery(path: str) -> bool:
    return path == _CADQUERY or path.startswith(_CADQUERY + ".")


def _callee(program: _Program, call: ast.Call) -> tuple[str, bool, bool]:
    """A call as `receiver.name`, whether its receiver is `?`, whether it is foreign.

    Foreign is a call on `builtin` or on another module: not `cq`'s to provide.
    """
    func = call.func
    path = program.dotted(func)
    if path is not None and "." in path:
        if _is_cadquery(path):
            return CQ + path[len(_CADQUERY) :], False, False
        return path, False, True
    if isinstance(func, ast.Name):
        unbound = func.id not in program.bindings
        if unbound and (func.id == _SHOW_OBJECT or func.id in _PYTHON_BUILTINS):
            return f"{BUILTIN}.{func.id}", False, True
        return f"{UNKNOWN}.{func.id}", True, False
    if isinstance(func, ast.Attribute):
        root = program.chain_root(func.value, program.roots, program.placed)
        if isinstance(root, str):
            return f"{root}.{func.attr}", False, False
        return f"{UNKNOWN}.{func.attr}", True, False
    return f"{UNKNOWN}.<expr>", True, False


def _kind(node: ast.expr) -> str:
    """An argument's literal kind: str, num, bool, none, tuple, list, call, name or expr."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        operand = node.operand
        if isinstance(operand, ast.Constant) and _is_number(operand.value):
            return "num"
        return "expr"
    match node:
        case ast.Constant(value=bool()):
            return "bool"
        case ast.Constant(value=str()):
            return "str"
        case ast.Constant(value=None):
            return "none"
        case ast.Constant(value=value) if _is_number(value):
            return "num"
        case ast.Tuple():
            return "tuple"
        case ast.List():
            return "list"
        case ast.Call():
            return "call"
        case ast.Name():
            return "name"
        case ast.Starred(value=value):
            return "*" + _kind(value)
    return "expr"


def _is_number(value: object) -> bool:
    return isinstance(value, int | float | complex) and not isinstance(value, bool)


def _form(name: str, call: ast.Call) -> str:
    """`name(kind, …; keyword=kind, …)`, keywords sorted, `**kind` for a `**` argument."""
    positional = ", ".join(_kind(arg) for arg in call.args)
    keywords = sorted((keyword.arg or "**", _kind(keyword.value)) for keyword in call.keywords)
    named = ", ".join(f"{k}={kind}" if k != "**" else f"**{kind}" for k, kind in keywords)
    inside = f"{positional}; {named}" if positional and named else positional or named
    return f"{name}({inside})"


def _selector(call: ast.Call) -> str | None:
    """The selector string of a selector call, as written; None for any other call."""
    if not (isinstance(call.func, ast.Attribute) and call.func.attr in SELECTOR_METHODS):
        return None
    if call.args:
        argument: ast.expr | None = call.args[0]
    else:
        argument = next((k.value for k in call.keywords if k.arg == "selector"), None)
    if argument is None:
        return None
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    return NON_LITERAL


def _end_form(tree: ast.Module) -> str:
    """`show_object(name)`, `show_object(…)`, `name = …`, `empty` or `other`."""
    if not tree.body:
        return "empty"
    match tree.body[-1]:
        case ast.Expr(value=ast.Call(func=ast.Name(id=name), args=args)) if name == _SHOW_OBJECT:
            if args and isinstance(args[0], ast.Name):
                return f"{_SHOW_OBJECT}({args[0].id})"
            return f"{_SHOW_OBJECT}(…)"
        case ast.Assign(targets=[ast.Name(id=name)]) | ast.AnnAssign(target=ast.Name(id=name)):
            return f"{name} = …"
    return "other"


def _sorted(counter: Counter[str]) -> Counts:
    return tuple(sorted(counter.items()))


def _count(stem: str, text: str, tree: ast.Module) -> ProgramCensus:
    program = _Program(tree)
    calls: Counter[str] = Counter()
    forms: Counter[str] = Counter()
    selectors: Counter[str] = Counter()
    unknown: Counter[str] = Counter()
    foreign: Counter[str] = Counter()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name, is_unknown, is_foreign = _callee(program, node)
        calls[name] += 1
        if is_foreign:
            foreign[name] += 1
        forms[_form(name, node)] += 1
        if is_unknown:
            segment = ast.get_source_segment(text, node.func)
            unknown[segment if segment is not None else name] += 1
        selector = _selector(node)
        if selector is not None:
            selectors[selector] += 1
    return ProgramCensus(
        stem=stem,
        calls=_sorted(calls),
        forms=_sorted(forms),
        selectors=_sorted(selectors),
        unknown=_sorted(unknown),
        foreign=_sorted(foreign),
        end_form=_end_form(tree),
    )
