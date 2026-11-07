# Review: a plan's diff, read against the plan and the standards

Read by the reviewer subagent `/retire-plan` starts, never by the agent
implementing a step: the reviewer gets the commits and has no exploration
to do, so the judgement calls live here instead of in every session's
context. What ruff, `mypy --strict`, the hook and the tests already enforce
is left to them.

## The brief

Two axes, reported apart so one cannot mask the other.

**Plan.** Quote the plan line for each finding:

1. a *Goal*, *Design deltas* or *Acceptance* item the commits leave missing
   or partial;
2. behaviour the commits add that the plan did not ask for, or that its
   *Non-goals* fence out;
3. an item that looks done but looks wrong;
4. a box ticked whose commit carries no fixture or property for it;
5. a *Docs to update* line or a design doc the commits make untrue, and a
   public type or signature change missing from a commit body or from
   `CHANGELOG.md` §Unreleased.

**Standards.** Cite the rule (`.agents/rules/gym.md`, this file, an
ADR) for each finding, and quote the hunk. Mark each **hard** (a stated
rule broken) or **judgement** (a smell worth a look).

Under 500 words in all; nothing found on an axis is reported as such.

## How to read

Every turn re-reads the whole context, so a turn costs more than the bytes
it fetches.

- Take all the commits in the first turn: one `git show` per commit, sent
  as parallel calls in one message. Not one `git log -p`: a large output
  is cut off.
- Batch what follows the same way: every file and grep a round of
  suspicions needs, in one message, not one call per turn.
- Grep `GLOSSARY.md` for the terms the diff adds and for its _Avoid_ lists;
  do not read it whole.

## The standards

`.agents/rules/gym.md` is the hard list: `run` never raises, failures
counted, the kernel's words verbatim, determinism, the process as the
boundary, the layer rule, the oracle never imported, a licence on every row,
every failure a fixture. Beside it:

### Scoring
- A tolerance widened, a timeout raised, a status remapped, a fallback path or
  a special case added to make a fixture pass is a hard finding unless the
  plan's open questions decided it.
- An aggregate whose denominator is not all programs, unlabelled, is a hard
  finding: it is the survivorship bias this project exists to remove.
- A change that can move a reward says so and bumps the reward's version; a
  change that can move a digest says so, and the digests moved with it in the
  same commit, with the reason.
- A numeric constant is named, commented and says why it is not a tolerance.
- A field metric follows the benchmark's own definition, cited; ours and
  theirs are never mixed under one name.
- `numpy` on a score's path keeps to the operations
  `docs/ARCHITECTURE.md` §Determinism allows.

### The sandbox
- A path by which program text runs outside a worker is a hard finding, as is
  a limit the program itself could lift.
- A status decided from a message's wording is a hard finding: it comes from
  an exception's type or the way the process ended.

### Tests
- A fixture's expected values come from a closed form or the part's
  construction, never from arris-gym's own output.
- A changed expectation says in its commit why the behaviour changed.
- A test asserts through the public API, not a private helper, wherever the
  API reaches the case.
- A test does not touch the network, and does not import CadQuery or OCP.

### API and docs
- A docstring says what an item guarantees and refuses, not how it works; a
  public operation has a runnable example.
- Docs change in the commit that changes the behaviour, in present tense,
  without the plan's history; a `CHANGELOG.md` bullet speaks to a reader of
  `README.md` only.
- A term `GLOSSARY.md` defines is used as written; one it lists under
  _Avoid_ is a judgement finding. A new concept named in public API or a
  design doc has its glossary entry.

### Code smells (always judgement)
A name that does not say what it holds; the same logic twice in the diff;
a function reaching into another module's data more than its own;
parameters that always travel together; a `float` or `str` standing for a
concept that deserves a type; abstraction or hooks for a case no fixture
has.
