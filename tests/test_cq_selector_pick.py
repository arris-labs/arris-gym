"""`_pick_within` (ADR-0017 rule 2): a selection it returns holds under every shift."""

from __future__ import annotations

import itertools

from hypothesis import given, settings
from hypothesis import strategies as st

from arris_gym.cq._selector import CQ_TOLERANCE, _pick, _pick_within

MARGIN = 2e-4


def test_two_estimated_keys_moved_in_opposite_directions_are_refused() -> None:
    keys = [0.0, CQ_TOLERANCE + 1.5 * MARGIN]
    # Uniform and one-at-a-time shifts keep [1]; moving key 1 down and key 0 up keeps [0, 1].
    assert _pick(keys, True) == [1]
    assert _pick([keys[0] + MARGIN, keys[1] - MARGIN], True) == [0, 1]
    assert _pick_within(keys, [True, True], MARGIN, True) is None


def test_a_selection_clear_of_the_margin_is_kept() -> None:
    assert _pick_within([0.0, 1.0], [True, True], MARGIN, True) == [1]
    assert _pick_within([0.0, 1.0], [True, True], MARGIN, False) == [0]
    assert _pick_within([0.0, 0.0], [False, False], MARGIN, True) == [0, 1]


@settings(max_examples=300, deadline=None)
@given(
    keys=st.lists(
        st.floats(min_value=-1e-3, max_value=1e-3).map(lambda k: round(k, 5)),
        min_size=1,
        max_size=5,
    ),
    flags=st.lists(st.booleans(), min_size=5, max_size=5),
    margin=st.floats(min_value=0.0, max_value=5e-4),
    maximum=st.booleans(),
)
def test_a_returned_selection_holds_at_every_corner_of_the_box(
    keys: list[float], flags: list[bool], margin: float, maximum: bool
) -> None:
    estimated = flags[: len(keys)]
    kept = _pick_within(keys, estimated, margin, maximum)
    if kept is None:
        return
    moving = [i for i, e in enumerate(estimated) if e]
    for signs in itertools.product((-1.0, 0.0, 1.0), repeat=len(moving)):
        moved = list(keys)
        for i, sign in zip(moving, signs, strict=True):
            moved[i] += sign * margin
        assert sorted(_pick(moved, maximum)) == sorted(kept)
