# Contributing

## Reports are the most useful contribution

A program that crashes arris-gym, gets the wrong status or scores wrongly is
worth more than any patch. Open an issue with the shortest program that shows
it, the full output, and what you expected. A report that reproduces becomes a
fixture in the test corpus and stays there once fixed.

## Code

arris-gym is developed under written rules that every change follows. Read
them before a pull request:

- [AGENTS.md](AGENTS.md): the project in one page, its setup, and where the
  rest lives;
- [.agents/rules/](.agents/rules/): the gym rules (`run` never raises, failures
  counted, determinism, the sandbox), git, and the docs lifecycle;
- [PROVENANCE.md](PROVENANCE.md): CadQuery is read for behaviour, never copied.

Set up the hook once per clone (`git config core.hooksPath .githooks`). For
anything larger than a fix, open a discussion first: the design may already
be settled in `docs/adr/`.

## Licence

Unless you say otherwise, any contribution you submit for inclusion in
arris-gym is dual-licensed as MIT or Apache-2.0, as the project is, without
any additional terms or conditions.
