# ADR-0007: A `cq` Workplane is a frozen stack over `arris.build`, its result one solid

- Status: accepted
- Date: 2026-11-08

## Context

`dialect="cq"` runs CadQuery programs on arris. The **subset** is the calls
and API forms `arris_gym.cq` implements, grown in census order; for C1 it is
the 13 forms the slice writes (`tests/fixtures/c1/census.json`). Every
slice program imports `cadquery as cq`, builds with `cq.Workplane("XY")`
chains, binds `result` and ends in `show_object(result)`. Four questions
have to be settled before the first call is written:

- how a program gets the subset when it writes `import cadquery`;
- what a `Workplane` holds, given that CadQuery's mutates a shared context
  while `arris.build`'s values never change;
- what a program's result is, and what happens when it is not one solid;
- what a call outside the subset ends in.

The status of each outcome is decided from a type (ARCHITECTURE.md
§Outcomes), and a disagreement with the oracle needs a status that names
its cause (ADR-0006: `unsupported_api` against an oracle `ok` is a `cq`
bug, `runtime` too, so the two give the same row and the same reward).

## Decision

**The program job carries its dialect.** The payload in the job's memfd
opens with one byte naming the dialect, then the program's text. Under `cq`
the program worker, before the program runs, sets
`sys.modules["cadquery"]` to `arris_gym.cq`, puts a finder first on
`sys.meta_path` that answers `import cadquery.<name>` with
`UnsupportedApi("cq.<name>")`, and binds `show_object` in the program's
namespace. Under `arris` none of this happens: `import cadquery` is
`runtime` (`ModuleNotFoundError`), as is `show_object` (`NameError`). The
cache key already holds the dialect, and `program_sha256` is the hash of
the text alone.

**A `Workplane` is a frozen value** holding its plane (an
`arris.build.Workplane`), its **stack** (the objects its call made: solids,
later a pending sketch or path, newest last) and its parent (the workplane
it was called on). Every call returns a new one; setting or deleting an
attribute raises `UnsupportedApi`, and a copy is the workplane itself. The
module and `Workplane` show a program CadQuery's names alone: anything
else `arris_gym.cq` holds has a leading underscore.

**The result is one solid.** It is the argument of the last `show_object`
call, else the module-level `result`. It resolves as follows:

| The value | Status | Message |
|---|---|---|
| no `show_object` call and no `result` | `runtime` | the program ended without calling `show_object` or binding `result` |
| not a `cq.Workplane` | `runtime` | `<where>` is of type `<type>`, not cadquery.Workplane |
| a `Workplane` with no solid on its stack | `runtime` | `<where>` is a Workplane holding no solid |
| a `Workplane` with one solid on its stack | `ok` once the body worker accepts its body | |
| a `Workplane` with several solids on its stack | `unsupported_api` | a Workplane holding `<n>` solids |

`<where>` is "the last `show_object` argument" or "`result`". The `runtime`
cases are decided by the type `NotASolid`, which `arris_gym.cq` raises. A
CadQuery compound, several solids shown as one, is a value the subset
lacks, not a program error, so it is `unsupported_api`. The slice makes
none: every oracle report holds one solid. A `union` of disjoint solids
counts as several when arris's `fuse` leaves several outer shells; what
`fuse` returns for them is recorded by a fixture before that rule is
written.

**A call outside the subset is `unsupported_api` naming it** as the census
writes it: `cq.Sketch` for a module name, `Workplane.sphere` for a method,
`cq.occ_impl` for a submodule, from `__getattr__` on the module and on
`Workplane`, never `AttributeError` or `TypeError`. A name with a leading
underscore is Python's or arris-gym's (`__deepcopy__`, `__wrapped__`, a
private module) and answers `AttributeError`, because Python's protocols
probe such names with `hasattr`. An implemented call given an API form
outside the census raises `UnsupportedApi` naming the form
(`Workplane.box(num, num, num; centered=bool)`); a value the subset lacks
names the value: `cq.Workplane('XZ')`.

## Consequences

- A slice program runs unchanged: `import cadquery as cq` gets the subset,
  and its `show_object(result)` decides its result.
- A program that shows several solids scores −1.0 as any failure does; a
  corpus that writes compounds shows up as `unsupported_api` rows naming
  the count, and the subset grows a compound when a census asks for one.
- `unsupported_api` against an oracle `ok` is a `cq_bug` row (ADR-0006), so
  every call the slice needs and the subset lacks is counted in the table.
- A program can still reach arris-gym's private names and `arris` itself:
  the worker is the boundary, never the namespace (ADR-0001).

## Alternatives considered

- **Several solids as `runtime`**: the same reward, but it calls a
  CadQuery value the subset lacks a program error, and a census reading
  the table could not tell a compound from a crash of the program.
- **The first solid of several**: an answer the oracle never gave, which
  would hide the case.
- **A mutable `Workplane` sharing a context as CadQuery's does**: a
  program's earlier workplane would change under it, and `arris.build`'s
  values are immutable, so the subset would copy their state back and
  forth.
- **`AttributeError` for a name outside the subset**: `runtime`, the status
  a typo in the program gets; the table could not tell a call the subset
  lacks from a program's mistake.
- **A dialect read from the program's text** (an `import cadquery` line):
  a status would then depend on how a program is written, and the caller
  already says which dialect it means.
