# Static reach fixtures

These programs are constructed here, not copied from a corpus. Their
expected in-subset flags follow ADR-0012's clauses, not execution outcomes.
They are parsed only; `in-not-executed` raises if anybody runs it.

- Forms: `in-forms`, `in-dynamic-kinds`; just outside with a keyword,
  incompatible literal kind, starred argument or keyword expansion.
- Selectors: none in `in-no-selectors`; `out-selector` writes `>Z`.
  The test also admits `faces(str)` alone, then its selector, so the
  selector check is exercised independently of the missing call form.
- Parsing: the valid fixtures; `out-unparsable` has an unclosed expression.
- Receivers: the known chains in `in-known-receiver`; a local helper's call
  is unknown in `out-unknown-receiver`, even if its name were declared.
- Foreign calls: builtin `abs`, imported `builtins.float` and `math.sqrt`
  in `in-foreign`; an unavailable module in `out-foreign`.
- Ends: `result` assignment, valued annotation, `show_object` of a name or
  expression; just outside with another assignment name, a bare annotation,
  `pass` or an empty program. End forms can also be removed from the data.
- Context: `in-context-refusal` writes admitted forms on a pending circle;
  it remains in-subset although that stack context is refused at runtime.

`test_reach.py` generates arbitrary programs from every declared form and
checks that removing one used declaration excludes them. It also checks
frozen records, malformed form keys, all-program denominators and order.
