"""`dump_png`: a fixed-size PNG whose silhouette matches the part's closed form."""

from __future__ import annotations

import doctest
import pathlib
import struct
import zlib

import numpy as np
import pytest
from numpy.typing import NDArray

import arris_gym as ag
import fixture_cases
from arris_gym.sandbox import _picture, _render, _sandbox

CASES = {c.slug: c for c in fixture_cases.load("sandbox")}
BOX = (4.0, 5.0, 6.0)  # tests/fixtures/sandbox/ok-box


def decode_png(data: bytes) -> NDArray[np.uint8]:
    """A reader written from the format: 8-bit greyscale, filter 0 only."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, header = 8, b"", b""
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind, body = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length : pos + 12 + length])
        assert crc == zlib.crc32(kind + body)
        if kind == b"IHDR":
            header = body
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    width, height, depth, colour = struct.unpack(">IIBB", header[:10])
    assert (depth, colour) == (8, 0)
    raw = zlib.decompress(idat)
    rows = [raw[r * (width + 1) : (r + 1) * (width + 1)] for r in range(height)]
    assert all(row[0] == 0 for row in rows)
    return np.array([np.frombuffer(row[1:], dtype=np.uint8) for row in rows])


def test_a_box_is_a_png_of_fixed_size(tmp_path: pathlib.Path) -> None:
    (box,) = ag.run_many([CASES["ok-box"].program])
    path = tmp_path / "box.png"
    ag.dump_png(box, path)
    image = decode_png(path.read_bytes())
    side = _render.PANEL * _render.SHEET_COLUMNS
    assert image.shape == (side, side)
    assert (image != _render.BACKGROUND).any()
    again = tmp_path / "again.png"
    ag.dump_png(box, again)
    assert again.read_bytes() == path.read_bytes()


def test_the_top_silhouette_of_a_box_is_its_closed_form_area_within_a_pixel_row() -> None:
    data = ag.run(CASES["ok-box"].program).body
    assert data is not None
    with ag.Sandbox() as sandbox:
        positions, triangles = _picture._mesh(
            sandbox._live_zygote(), data.data, timeout=5.0, memory=512 * 2**20
        )
    top = next(p for p in _render.render(positions, triangles) if p.view.name == "top")
    radius = 0.5 * float(np.sqrt(sum(side * side for side in BOX)))
    assert top.scale == _render.fit_scale(radius)
    expected = BOX[0] * top.scale * BOX[1] * top.scale
    # Pixel centres sample the outline: the count is off by less than one
    # pixel row along each of the two sides.
    row = BOX[0] * top.scale + BOX[1] * top.scale
    assert abs(float(top.covered.sum()) - expected) <= row


def test_a_result_without_a_body_has_nothing_to_draw(tmp_path: pathlib.Path) -> None:
    syntax = ag.run(CASES["syntax-unclosed"].program)
    with pytest.raises(ValueError, match="no body"):
        ag.dump_png(syntax, tmp_path / "none.png")
    assert not (tmp_path / "none.png").exists()


def test_a_body_the_kernel_refuses_is_a_picture_error_with_its_words(
    tmp_path: pathlib.Path,
) -> None:
    box = ag.run(CASES["ok-box"].program)
    assert box.body is not None
    garbage = box.model_copy(update={"body": ag.BodyRef.of(b"not a body")})
    with pytest.raises(RuntimeError, match="Error"):
        ag.dump_png(garbage, tmp_path / "bad.png")


def test_the_doctests_of_the_picture_run() -> None:
    assert doctest.testmod(_sandbox).failed == 0
