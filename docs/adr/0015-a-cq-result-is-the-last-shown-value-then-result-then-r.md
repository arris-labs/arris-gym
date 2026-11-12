# ADR-0015: A `cq` result is the last shown value, then `result`, then `r`

- Status: accepted
- Date: 2026-11-12
- Amends: ADR-0007's result selection and ADR-0012's admitted end forms

## Context

All 968 programs in CAD-Recode's original validation split end in `r = …`.
Neither the `cq` program worker nor the oracle worker reads that name under
the C1 rule. Their two failures therefore agree without measuring fidelity.
The reach curve ranks this end form first (ADR-0014); it unlocks no program
alone because the same programs also need further API forms.

BenchCAD's 17,900 programs end in `show_object(result)`. Accepting the new
name must preserve that result and the order already given to `result`.

## Decision

After execution, both the `cq` program worker and the oracle worker select:

1. the argument of the last `show_object` call, if any;
2. otherwise the module-level binding `result`, if present;
3. otherwise the module-level binding `r`, if present.

Presence decides, never the value's truth or validity. `result = None`
therefore takes precedence over a valid `r`. A last `show_object(None)`
takes precedence over both. Local bindings are not module-level bindings;
a deleted binding is absent. Other names and the last statement's bound
name have no role. The chosen value is resolved exactly as before:
`cq` requires a Workplane holding one solid, and the oracle requires a
shape. A missing or invalid value remains `runtime` under `cq` and
`no_result` on the oracle. No new status is introduced.

`cq.Subset.end_forms` adds `r = …`, including a valued annotation of `r`
through the census's existing assignment rule. The rest of ADR-0012's
static rule is unchanged. Runtime selection reads the final namespace;
static membership still checks the last statement's shape, so a trailing
`pass` can put a program outside the subset even when runtime finds `r`.

The `arris` dialect continues to read only module-level `result` and to
require an `arris.build.Solid`. These are worker conventions, not behaviour
taken from CadQuery's implementation; no CadQuery source was used.

## Consequences

- CAD-Recode programs that finish their modelling calls now expose their
  selected `r` values; a missing result cannot produce the old vacuous agreement.
- `tests/fixtures/cq/ok-result-r/` holds a box's closed form and oracle
  report. Properties compare `result = X` and `r = X` rows, including body
  bytes or STEP text, apart from source hashes and wall-clock time.
- Selection tests cover invalid higher-priority values, the last shown
  value, local and deleted bindings, both names holding solids and the
  unchanged `arris` rule. The slice's 300 oracle rows remain byte-equal.
- The missing-result message under `cq` now also names `r`. Programs that
  only bind `r` can change status, body and digest; existing programs that
  show a result or bind `result` keep their selection.

## Alternatives considered

- **Use the last statement's bound name.** It admits arbitrary names and
  requires runtime syntax inspection, beyond the fixed end form ranked by
  the census. Static end forms describe membership, not result selection.
- **Choose the first valid value.** It masks an invalid explicit result
  with an unrelated solid and changes established precedence.
- **Leave the oracle unchanged.** The two workers would judge different
  results from one program, making the resulting disagreement uninformative.
