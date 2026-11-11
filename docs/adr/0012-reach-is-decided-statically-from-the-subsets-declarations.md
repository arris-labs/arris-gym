# ADR-0012: Reach is decided statically from the subset's declarations

- Status: accepted
- Date: 2026-11-11

## Context

C1 measured agreement on 200 of 300 programs. C2 needs to distinguish how
much of a corpus the subset admits from whether those programs agree with
the oracle. Deciding membership from successful runs would drop failures
from the denominator and hide `cq` bugs. ADR-0003 already supplies a census
of each program, including its argument kinds and unknown receivers;
ADR-0007 checks runtime arguments through `census_form` decorators.

The two descriptions differ deliberately. The census calls an argument
`name`, `expr` or `call` before its value is known. A decorator sees the
value's runtime kind. A variable holding a number must not lower reach
merely because a literal number would have been easier to classify.

## Decision

An **in-subset program** meets all these conditions, without being run:

1. It is a parsed `ProgramCensus`, not `Unparsable`.
2. Every non-foreign `forms` key matches a **subset declaration**: its call
   name and positional count match, each literal kind is accepted by that
   slot, and every keyword is declared with an accepted kind. `name`,
   `expr` and `call` may supply any runtime kind; they match any nonempty
   allowed-kinds tuple. A positional declaration of `None` accepts any
   kind. Starred arguments and keyword expansion are outside: their counts
   and keyword names are not known. Form strings use the census's canonical
   spelling; malformed strings and duplicated or unsorted keywords do not
   match.
3. Every selector string is admitted by the subset. Today the list is empty.
4. Its end form is `result = …` or a final `show_object` call, with a name
   or expression as its argument. `show_object(…)` in the declarations
   admits the census's `show_object(name)` family too. A valued annotation
   of `result` counts as assignment; a bare annotation, another assignment
   name, `empty` and `other` do not. This is the last statement's static
   shape, not proof that a solid is produced. A program ending in `pass`
   is outside even if an earlier statement bound `result`.
5. `unknown` is empty. Declaring a form for `?.method` cannot admit it.
6. Foreign calls belong to Python's builtins or the fixed standard-library
   roots in `census/_foreign.py`. Builtins are ADR-0003's written-out
   CPython 3.12 names, with `builtin.show_object` supplied by the worker;
   `builtins.<name>` uses the same names, without `show_object`. The
   standard-library list records CPython 3.12 Linux roots having an import
   spec, excluding unavailable platform modules. It is data in the repo,
   never recomputed from the caller's installed packages. This admits the
   Python module's scope, not the existence of an attribute or the success
   of a call under the sandbox's limits. Other modules, including third-party
   packages, are outside. A program's modules are never imported to decide.

`cq.CensusForm` holds each declaration (name, positional kinds, optional
keywords). The decorator's runtime check closes over this same frozen
record and attaches it to the method. `cq.subset()` reads those records
from `Vector` and `Workplane`, without building a model, and returns a
frozen `cq.Subset` with its forms, selectors and end forms. Its
`admits(form)` applies clause 2. Nested collections are copied to tuples.
The two types use standard-library frozen dataclasses: importing pydantic
into `cq` would break the dependency boundary. This is the narrow exception
to the usual frozen pydantic record rule; `census.Reach` uses pydantic.

The caller's `arris_gym.cq` exports the metadata types and function. The
program worker installs a separate module exposing `UnsupportedApi`,
`Vector` and `Workplane`, with the existing attribute and submodule refusals.
This keeps the CadQuery API unchanged. The module remains mutable and
introspectable; it is no security boundary (ADR-0002).

`census.reach(programs, subset)` accepts program text records or already
computed census outcomes. It returns a frozen `Reach`: `programs` is every
input program, `in_subset` its admitted count, and `stems` those admitted
stems sorted once. Duplicate stems are a caller error. An empty corpus
returns zero counts. No fraction is defined at denominator zero.

## Consequences

- **Reach is static, not an execution prediction.** Literal values are
  absent from API forms: `Workplane('XZ')` and `Workplane('XY')` have the
  same form. Tuple lengths, complex versus real `num`, argument values,
  control flow, attribute access without a call and stack context remain
  unproved. Runtime refusals and all other failures remain in the table.
- **Context does not excuse an in-subset `cq` bug.** A declined behaviour
  whose form is admitted cannot be classed `by_design` inside the subset.
  It is a `cq_bug` until fixed, or its whole form is removed and reach
  falls. This also applies to a limitation hidden by a census kind or
  value. Kernel failures keep their own disagreement classes.
- The initial static cross-check admits **300/300** C1 slice programs.
  `tests/fixtures/c1/reach-programs.jsonl.gz` holds their per-program census
  rows, program hashes, source, revision and CC-BY-4.0 licence, no source
  programs. The gate checks these rows offline. Clause fixtures live in
  `tests/fixtures/reach/`; a property generates programs from declarations
  and removes one used declaration to make each program outside.
- This decision sets membership, not T, and lifts no CadQuery form. Reach
  and plain agreement over all programs are separate figures. The reach
  curves and the two full-corpus measurements decide T in a later ADR.

## Alternatives considered

- **Decide from runtime statuses.** A `cq` defect could improve reported
  fidelity by excluding the programs that expose it.
- **Compare census keys with only literal kinds.** Excludes variables and
  arithmetic that supply values the same declarations accept at runtime.
- **Infer values and follow helper functions.** A second interpreter with
  different failure modes; ADR-0003 counts what the program writes.
- **Duplicate the accepted calls in a reach table.** Lets runtime checks
  and the published subset drift. The decorators already own that data.
- **Admit all foreign calls or import them to check.** The former promises
  arbitrary installed packages; the latter executes untrusted imports
  outside a program worker and depends on the caller's environment.
