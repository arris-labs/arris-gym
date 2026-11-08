# ADR-0003: The census parses a program and counts what it writes

- Status: accepted
- Date: 2026-11-08

## Context

M1 (docs/ROADMAP.md) needs, before `cq` exists, the calls, selector strings
and argument forms BenchCAD's 17,900 `code_gen` programs use, by family, so
that the C1 slice is the families that need the least of CadQuery. The
programs are model-written: hostile input (ADR-0001). CadQuery dispatches on
the runtime type of a receiver, which the census cannot know without running
the program.

Measured on CPython 3.12.3: `ast.parse` refuses a NUL byte with a
`SyntaxError`, a too-deep expression with a `RecursionError` ("during ast
construction", at about 5,000 chained calls) or a `MemoryError` (the
parser's own stack, at about 6,000 unary minuses), and emits a
`SyntaxWarning` for an invalid escape such as `"\d"`, which a caller's
`-W error` turns into an exception. The `RecursionError`'s limit counts
from the C stack depth `ast.parse` is called at: it falls by one chained
call per C-level frame the caller is under (4,997 calls at a
script's top level, 4,937 under 60 nested `map` calls), and on a thread
whose stack is too small (256 KiB) the parser overflows it and the process
dies. `ast.unparse` recurses in Python and fails on trees `ast.parse`
accepts.

## Decision

**Parse, never run.** The census reads each program with `ast.parse` and
nothing else: no `compile`, no `exec`, no import of what the program
imports. The hostile-input rule governs running a program, and parsing runs
nothing of it, so the census works in the caller's process. Any exception
out of parsing or counting makes the program **unparsable**, its class name
and `str()` kept verbatim; the census never raises on a program. Warnings
are silenced around the parse, so the caller's warning filters cannot change
an answer. Each program is parsed and counted on a fresh thread started
with a fixed stack size (16 MiB; the deepest programs tried just inside
the parser's limits parse on 1 MiB), so the parser always starts at the
same C stack depth, on a stack no `ulimit -s` shrinks, and every
traversal is iterative (`ast.walk`, loops): the answer depends on the
program and the Python grammar only, never on the caller's stack depth.

**What is counted.** Every call node in the program, wherever it stands
(inside a function that is never called too), names a **receiver**:

- `cq` for a dotted path on the `cadquery` module, whatever alias or
  `from cadquery import …` binds it: `cq.Workplane`, `cq.selectors.BoxSelector`;
- the **root constructor**'s name for a method on a chain whose innermost
  call is a `cadquery` path: `Workplane` in `cq.Workplane("XY").box(…).faces(…)`.
  A chain may pass through names: a name every one of whose bindings is an
  assignment of a chain on one root carries that root (`r = cq.Workplane();
  r = r.hole(1)`). Bindings are collected over the whole program, ignoring
  scope and order; any other binding of the name (a parameter, a loop target,
  an import, a value with another root) leaves it unplaced;
- `builtin` for `show_object` and for Python's builtins, when the program
  binds neither name itself. The builtins are those the interpreter defines,
  not what `site` or a notebook adds (`exit`, `help`, `display`), which
  depends on the caller's process;
- the imported module's name for a dotted path on another import: `math` in
  `math.sqrt`;
- `?` for anything else: a method on a name the census cannot place, on a
  subscript or on a plain attribute (`wp.plane.toWorld(…)`), or a call of a
  function the program defines. A `?` call is counted like any other, and its
  callee is listed as the program writes it.

A call is counted as `receiver.name` (`Workplane.extrude`). Its **argument
form** names each positional argument's literal kind (`str`, `num` with a
sign, `bool`, `none`, `tuple`, `list`, `call`, `name`, `expr`, and `*kind`
for a starred one) and, after `;`, each keyword with its kind, sorted by
name, `**kind` for a `**` argument: `Workplane.extrude(num; both=bool)`.
The call and its argument form together are an **API form**. The **selector
string** of a call to `faces`, `edges`, `vertices`, `wires`, `solids`,
`shells` or `compounds`, on any receiver, is its first positional argument,
or its `selector=` keyword, as the literal holds it (`>Z or <Z`), or
`<non-literal>`; a selector call with neither has none. The program's **end
form** is its last statement: `show_object(name)`, `show_object(…)`,
`name = …`, `empty` or `other`.

The census counts what a program writes, not what CadQuery would dispatch:
`cq.Workplane().val().Volume()` counts `Workplane.Volume`.

**The ranking.** Per family, the triple (distinct calls, distinct selector
strings, distinct API forms), compared in that order, then the family's
name. Calls come first because a call is what `cq` has to implement; a
selector string is grammar, cheaper per item; an API form refines a call.
Calls on `builtin` and on another module's receiver are counted and reported
but not ranked: `cq` does not provide them. A `?` call is ranked, since it
may be CadQuery. Only families with at least 100 programs are eligible for
the **slice**: the first 3 ranked, the first 100 programs of each by stem,
stems sorted as strings.

**The reader.** BenchCAD is read with `huggingface_hub.snapshot_download` of
`code_gen/data/*.parquet` at the pinned revision and `pyarrow` reading only
`stem`, `family` and `code`, both in the optional `[corpus]` extra, rather
than with `datasets` as SEED.md §7 says. `datasets` reads the same Parquet
through `pyarrow` and adds `pandas`, `fsspec` and `multiprocess` for nothing
the census needs.

## Consequences

- No program runs in M1, so no sandbox time and no hostile-input path: a
  program the census cannot parse costs one listed row.
- What is unparsable depends on the Python grammar: the census is as of the
  pinned interpreter's minor version (3.12), and a move to another changes
  it on purpose, with a re-run.
- `?` rows are the census's own blind spot, not the corpus's: each is read
  at the run and either explained or shrunk to a fixture and the counting
  fixed. A program that builds its parts in helper functions shows up there.
- Flow-insensitive binding can only lose a root, never invent one: a name
  bound once to something else is `?` everywhere.
- The receiver is not CadQuery's type: `Workplane.Volume` names a method of
  a `Solid`. M3 maps API forms to `cq` methods with this in mind.

## Alternatives considered

- **Running each program in the sandbox under a tracing `cadquery` shim.**
  Exact receivers and dispatch, at the cost of a CadQuery install inside the
  worker and 17,900 executions; and a program that fails early hides the
  rest of its calls. The non-goal of M1.
- **Type inference over the program** (follow returns of local functions,
  scopes, flow). Fewer `?` rows, and a second interpreter of CadQuery's
  types to keep right; the census's job is to say what programs write.
- **Ranking by the number of distinct API forms alone.** One number, but a
  family with a few calls in many argument forms would rank behind one with
  many calls in one form each, though the first costs `cq` less.
