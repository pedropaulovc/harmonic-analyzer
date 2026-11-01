"""Offline contracts for the keeper-chain anchor eye (MHA-DT-28) part and drawing.

A ``visual_noncritical`` formed-wire eye under ``cad/docs/drawing-guidelines.md``
(#1076): three native model dimensions whose places the PART owns -- the
loop's inside diameter and the tail's length from a blanked reference sketch
in the eye's plane, and the wire as REFERENCE -- every one at the title
block's one place, no GD&T, no roughness symbol, and at most four note lines.
"""

from __future__ import annotations

import math
import re

import pytest

import _config
from _printed_tolerance import printed_band_mm
import dt_crank_pin_eye_notes as notes
import dt_crank_pin_eye_spec as spec
import draw_dt_crank_pin_eye as drawing
import dt_vn_keeper_chain_spec as chain


def test_mating_part_numbers_are_live() -> None:
    registered = {row["number"] for row in _config.parts().values()}
    references = (
        (
            notes.DRAWING_NOTES,
            ("dt-crank-arm", "sh-vn-brass-fillister-screw"),
        ),
        (notes.DIMENSION_CALLOUTS["LoopID"], ("dt-vn-keeper-chain",)),
    )
    for text, mates in references:
        printed = set(re.findall(r"\bMHA-[A-Z0-9]+(?:-[A-Z0-9]+)+\b", text))
        assert printed <= registered, printed - registered
        for mate in mates:
            assert _config.parts(mate)["number"] in printed


def test_printed_sizes_derive_from_the_eye_spec() -> None:
    assert notes.LOOP_ID == pytest.approx(2.0 * spec.LOOP_R - spec.WIRE_DIA)


def test_bead_chain_passes_the_smallest_printed_loop() -> None:
    # The loop's callout says the bead chain passes freely: the loop must
    # admit a bead at the title block's lower limit for the places it prints
    # at, not just at nominal (drawing-guidelines.md: controlled limits must
    # produce the fit).
    places = notes.DRAWING_PRECISION_BY_NAME["LoopID"]
    band = printed_band_mm(places, unit=spec.UNIT)
    smallest = round(notes.LOOP_ID / 25.4, places) * 25.4 - band
    assert spec.LOOP_ID_MIN == pytest.approx(smallest)
    assert (smallest - chain.BEAD_DIA) / 2.0 >= chain.EYE_BEAD_PASS_AIR


def test_side_view_geometry_matches_the_part_frame() -> None:
    # Right view: sheet x runs along model -Z, so the loop centre (Z = -LoopR)
    # is right of the tail (Z = 0) by LoopR, and the tail's end is TailLen
    # above the loop centre.
    s = drawing._S
    assert drawing.LOOP_CENTER_XY[0] - drawing.TAIL_END_XY[0] == pytest.approx(
        spec.LOOP_R * s
    )
    assert drawing.TAIL_END_XY[1] - drawing.LOOP_CENTER_XY[1] == pytest.approx(
        spec.TAIL_LEN * s
    )
    assert drawing.LOOP_CENTER_XY[0] == pytest.approx(drawing.SIDE_CENTER[0])


def test_views_are_in_projection_and_clear_of_the_title_block() -> None:
    assert drawing.TOP_CENTER[0] == drawing.SIDE_CENTER[0]
    assert drawing.TOP_ANGLE == pytest.approx(-math.pi / 2.0)
    for x, y in (
        *drawing.SIDE_KEEP.values(),
        *drawing.TOP_KEEP.values(),
        drawing.NOTES_XY,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)
    loop_x, loop_y = drawing.SIDE_KEEP["LoopID"]
    assert math.dist((loop_x, loop_y), drawing.LOOP_CENTER_XY) > drawing.HALF_OD
    tail_x, tail_y = drawing.SIDE_KEEP["TailLen"]
    assert tail_x < drawing.TAIL_END_XY[0]
    assert drawing.LOOP_CENTER_XY[1] < tail_y < drawing.TAIL_END_XY[1]


class _View:
    """A drawing view whose ``Angle`` write either takes or is refused."""

    def __init__(self, *, refuses_rotation: bool = False) -> None:
        self._refuses = refuses_rotation
        self._angle = 0.0

    @property
    def Angle(self) -> float:
        return self._angle

    @Angle.setter
    def Angle(self, value: float) -> None:
        if not self._refuses:
            self._angle = value


class _DrawingModel:
    def EditRebuild3(self) -> bool:
        return True


@pytest.fixture
def turn_top_view(monkeypatch: pytest.MonkeyPatch):
    """Run ``_turn_top_view`` on fake views. The side view projects model
    points through the sheet layout; the top view projects them to the same
    sheet x, shifted by ``top_shift`` per landmark (the tail's end, y > 0, or
    the loop's far wire, z < 0)."""
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)

    def run(
        *, refuses_rotation: bool = False, top_shift: dict[str, float] | None = None
    ) -> _View:
        shift = top_shift or {}
        side, top = _View(), _View(refuses_rotation=refuses_rotation)

        def project(_adapter, view, point, *, label):
            x, y = drawing._side_xy(point[2] * 1000.0, point[1] * 1000.0)
            if view is top:
                return x + shift.get("tail end" if point[1] > 0.0 else "loop", 0.0), y
            return x, y

        monkeypatch.setattr(drawing, "model_point_in_view", project)
        drawing._turn_top_view(object(), _DrawingModel(), side, top)
        return top

    return run


def test_top_view_turn_accepts_views_in_projection(turn_top_view) -> None:
    assert turn_top_view().Angle == pytest.approx(drawing.TOP_ANGLE)
    near = 0.9 * drawing.ALIGN_TOL_M
    assert turn_top_view(
        top_shift={"tail end": near, "loop": -near}
    ).Angle == pytest.approx(drawing.TOP_ANGLE)


@pytest.mark.parametrize("landmark", ("tail end", "loop"))
def test_top_view_turn_rejects_each_landmark_out_of_projection(
    turn_top_view, landmark: str
) -> None:
    with pytest.raises(RuntimeError):
        turn_top_view(top_shift={landmark: 1.1 * drawing.ALIGN_TOL_M})


def test_top_view_turn_rejects_a_refused_rotation(turn_top_view) -> None:
    with pytest.raises(RuntimeError):
        turn_top_view(refuses_rotation=True)


def test_part_registry_row() -> None:
    config = _config.parts("dt-crank-pin-eye")
    assert int(config["quantity"]) == 1
    assert "brass wire" in str(config["material_specification"]).lower()
