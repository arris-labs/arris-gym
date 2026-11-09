"""The Markdown helper the fidelity and re-scored reports share."""

from __future__ import annotations

import json
import re

_BACKTICKS = re.compile(r"`+")
# A lone surrogate (a message Python decoded with `surrogatepass`) cannot be
# written as UTF-8; in the span it stays a JSON escape.
_SURROGATE = re.compile("[\ud800-\udfff]")


def code_span(text: str) -> str:
    """`text` as one CommonMark code span holding its JSON string literal.

    The literal has no line ending (JSON escapes every control character), so
    the span cannot break the document's blocks; its fence is one backtick
    longer than any run inside, so nothing inside closes it; the padding
    space on each side is the one CommonMark strips. `json.loads` of the
    span's content gives `text` back, character for character, and the
    span encodes as UTF-8 whatever `text` holds.
    """
    literal = json.dumps(text, ensure_ascii=False)
    literal = _SURROGATE.sub(lambda m: f"\\u{ord(m.group()):04x}", literal)
    longest = max((len(run) for run in _BACKTICKS.findall(literal)), default=0)
    fence = "`" * (longest + 1)
    return f"{fence} {literal} {fence}"
