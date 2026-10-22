"""Offline contracts for the guide-lock drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_pd_guide_lock as lock
import draw_pd_guide_lock as drawing
import pd_guide_lock_spec
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-guide-lock.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-guide-lock.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-guide-lock_drawing.png")
    assert DRAWINGS_BY_NAME["pd_guide_lock"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are
    # BOTH the shared spec's map, and the drawing's view math reads the spec's
    # nominal spans, not a divergent copy.
    assert lock.DRAWING_DIMENSIONS is pd_guide_lock_spec.DRAWING_DIMENSIONS
    marked = set().union(*pd_guide_lock_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.LOCK_WIDTH, drawing.LOCK_HEIGHT) == (
        pd_guide_lock_spec.LOCK_WIDTH,
        pd_guide_lock_spec.LOCK_HEIGHT,
    )
    assert lock.HOLE_XY is pd_guide_lock_spec.HOLE_XY


def test_hole_contract_is_part_owned_and_resolved() -> None:
    spec = pd_guide_lock_spec.HOLE_SPEC
    assert lock.HOLE_SPEC is spec
    assert drawing.HOLE_SPEC is spec
    # R9-49: the fractional 1/8 drill carries both printed hole positions over
    # the screw majors (guide_lock_screw_spec.LOCK_SET_OFFSET).
    assert spec.kind == "drilled_fractional"
    assert spec.size == "1/8"
    assert lock.HOLE_DIA == blind_cut_dia_mm(spec)
    assert drawing.HOLE_R_SHEET == (
        blind_cut_dia_mm(spec) * drawing.SHEET_SCALE[0] / 2000.0
    )


def test_sheet_runs_at_4_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    assert pd_guide_lock_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"


# Title block: .X ±0.8; drilled holes +0.10/-0.
_ONE_PLACE = 0.8
_DRILLED_PLUS = 0.10
_CHAR_WIDTH = 0.00276  # sheet m per character of 3.5-mm note text


def _ligaments(hole_y: float) -> dict[str, float]:
    r_max = (0.125 * 25.4 + _DRILLED_PLUS) / 2.0
    band = 0.035
    xs = [x for x, _ in pd_guide_lock_spec.HOLE_XY]
    return {
        "guide-side edge": hole_y - band - r_max,
        "far edge": (9.6 - _ONE_PLACE) - hole_y - band - r_max,
        "left edge": min(xs) - band - r_max,
        "right edge": (22.0 - _ONE_PLACE) - max(xs) - band - r_max,
    }


def test_screw_holes_keep_the_ligament_floor_at_the_printed_worst_case() -> None:
    """Review of 19e33c6c2 (blocker): 2.5 from the guide-side edge left 0.81
    of ligament under the largest drilled 1/8 hole.  R9-59 laps the plate 1.0
    past the rail, so the holes stand 3.5 from that edge."""
    assert min(_ligaments(2.5).values()) < 1.0
    (hole_y,) = {y for _, y in pd_guide_lock_spec.HOLE_XY}
    assert hole_y == pytest.approx(3.5)
    worst = _ligaments(hole_y)
    assert min(worst.values()) >= 1.5
    assert pd_guide_lock_spec.HOLE_LIGAMENTS_WORST == pytest.approx(worst)
    assert pd_guide_lock_spec.DRAWING_PRECISION_BY_NAME["Height"] == 1
    assert pd_guide_lock_spec.DRAWING_PRECISION_BY_NAME["Width"] == 1


def test_hole_coordinates_print_from_the_corner_without_a_frame() -> None:
    """drawing-guidelines.md rule 5 (avoid excessive GD&T): no frame on this plate; each hole coordinate prints from the
    plate's corner at .XXX under its own band, and the shared Y once, 2X."""
    holes = pd_guide_lock_spec.DRAWING_DIMENSIONS["ScrewHoles"]
    assert holes == {"Hole1X", "Hole2X", "Hole1Y"} <= set(drawing.FRONT_KEEP)
    assert {pd_guide_lock_spec.DRAWING_PRECISION_BY_NAME[name] for name in holes} == {3}
    assert drawing.DIMENSION_PREFIXES["Hole1Y"] == "2X "
    assert len({y for _, y in pd_guide_lock_spec.HOLE_XY}) == 1


def test_the_drill_callout_stands_between_the_plate_and_the_right_view() -> None:
    # Include every mate/reason row: the native drill row is no longer the
    # widest. This is a conservative offline envelope, not native ink proof.
    rows = [
        f"2X {drawing.HOLE_CALLOUT_PROCESS} Ø3.18 THRU ALL",
        *drawing.HOLE_MATE_CALLOUT.splitlines(),
    ]
    half = max(len(row) for row in rows) * _CHAR_WIDTH / 2.0
    left, right = (
        drawing.HOLE_CALLOUT_XY[0] - half,
        drawing.HOLE_CALLOUT_XY[0] + half,
    )
    right_view_left = (
        drawing.RIGHT_CENTER[0]
        - pd_guide_lock_spec.LOCK_THICK * drawing.SHEET_SCALE[0] / 2000.0
    )
    assert drawing.RIGHT_EDGE_X < left and right < right_view_left


def test_the_hole_y_text_stays_inside_the_border_and_under_the_plate() -> None:
    x, y = drawing.FRONT_KEEP["Hole1Y"]
    half = len("2X 3.500±0.035") * _CHAR_WIDTH / 2.0
    assert x - 2.0 * half > 0.0127  # right-aligned or centred, inside
    assert y < drawing.BOTTOM_EDGE_Y - 0.004
    assert x + half < drawing.LEFT_EDGE_X  # clear of Hole1X's extension


def test_the_hole_1_x_text_stands_outboard_of_its_extension_lines() -> None:
    """Machinist review of 40e51b9a7: between its extension lines the 4.000's
    text sat on hole 1's own extension line. It now stands left of the plate's
    left edge, under the 2X hole Y text and clear of it."""
    x, y = drawing.FRONT_KEEP["Hole1X"]
    half = len("4.000 ±0.035") * _CHAR_WIDTH / 2.0
    assert x + half < drawing.LEFT_EDGE_X - 0.002
    assert y < drawing.FRONT_KEEP["Hole1Y"][1] - 0.007
    assert y > drawing.FRONT_KEEP["Hole2X"][1] + 0.004


def test_the_height_text_sits_between_its_extension_lines() -> None:
    """Machinist review of 1c9f9b2a6: inboard of the hole Y dimension the
    height's value sat on the plate's top-edge extension line. It now stands
    mid-way between the top and bottom extension lines, left of the hole Y
    dimension line, where the hole Y extension stops, and carries no callout
    (Codex P1 on #1353: drawing-guidelines.md rule 7 (notes: few, flagged, never a method) bars a design-intent note)."""
    assert "Height" not in drawing.DIMENSION_CALLOUTS
    assert not hasattr(drawing, "HEIGHT_BAND_CALLOUT")
    x, y = drawing.FRONT_KEEP["Height"]
    half_w = len("9.6") * _CHAR_WIDTH / 2.0
    assert x - half_w > 0.0127
    assert x + half_w < drawing.FRONT_KEEP["Hole1Y"][0] - 0.002
    half_h = 0.0035 / 2.0
    assert y + half_h < drawing._sheet_y(pd_guide_lock_spec.LOCK_HEIGHT) - 0.005
    assert y - half_h > drawing.BOTTOM_EDGE_Y + 0.005


def test_the_views_sit_centred_between_the_border_and_title_block() -> None:
    """Machinist review of 40e51b9a7: the group sat low and left under an
    empty upper field. The dimension stack's bottom (Width) and the top
    (4X R, the stock callout) stand about equally off the title block's top
    and the border."""
    border_top, title_top = 0.279 - 0.0127, 0.065
    bottom = drawing.FRONT_KEEP["Width"][1]
    top = max(drawing.FRONT_KEEP["CornerR"][1], drawing.RIGHT_KEEP["Depth"][1] + 0.006)
    assert abs((bottom - title_top) - (border_top - top)) < 0.015
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]


def test_the_four_rounded_corners_print_once_4x_clear_of_the_holes() -> None:
    """2026-10-11 (user): the plate's corners are rounded per the ch22 back
    photo (R ~1.75 measured -> R1.8); one printed 4X radius at .X, and the
    holes stay outside every corner's R x R square at the printed worst case,
    so their edge ligaments still run to straight edges."""
    import inspect

    r = pd_guide_lock_spec.CORNER_R
    assert r == pytest.approx(1.8)
    assert pd_guide_lock_spec.DRAWING_DIMENSIONS["Corners"] == {"CornerR"}
    assert pd_guide_lock_spec.DRAWING_PRECISION_BY_NAME["CornerR"] == 1
    # A custom prefix replaces SolidWorks' own "R" (farm run
    # 20261012T061737079Z printed "4X 1.8"), so the prefix carries it.
    assert drawing.DIMENSION_PREFIXES["CornerR"] == "4X R"
    source = inspect.getsource(lock.build)
    assert '("Corners", "CornerR", ((LOCK_WIDTH, LOCK_HEIGHT),))' in source
    assert '"OtherCorners"' in source
    assert source.count("'\"LockCornerR\"'") == 1  # both fillets, one drive loop
    r_max = r + _ONE_PLACE
    x_min = min(x for x, _ in pd_guide_lock_spec.HOLE_XY) - 0.035
    x_from_right = (
        pd_guide_lock_spec.LOCK_WIDTH
        - _ONE_PLACE
        - max(x for x, _ in pd_guide_lock_spec.HOLE_XY)
        - 0.035
    )
    assert min(x_min, x_from_right) > r_max


def test_the_printed_radius_owns_the_top_right_arc_its_text_stands_off() -> None:
    """The printed fillet's only edge is the top-right corner, and the text
    lies up-right of that arc's centre (inside the arc's 0-90 deg sweep), so
    the leader runs from the arc straight out to the text over no geometry."""
    import math

    x, y = drawing.FRONT_KEEP["CornerR"]
    r_sheet = pd_guide_lock_spec.CORNER_R * drawing.SHEET_SCALE[0] / 1000.0
    cx = drawing.RIGHT_EDGE_X - r_sheet
    cy = drawing._sheet_y(pd_guide_lock_spec.LOCK_HEIGHT) - r_sheet
    angle = math.degrees(math.atan2(y - cy, x - cx))
    assert 15.0 < angle < 75.0


def test_the_corner_radius_stands_off_the_top_right_corner() -> None:
    """The 4X R text rides above and right of the plate: clear of the Height's
    extension lines (left), the drill callout below it, and the right view."""
    x, y = drawing.FRONT_KEEP["CornerR"]
    half = len("4X R1.8") * _CHAR_WIDTH / 2.0
    top_edge_y = drawing._sheet_y(pd_guide_lock_spec.LOCK_HEIGHT)
    assert y > top_edge_y + 0.010
    assert x - half > drawing.RIGHT_EDGE_X
    assert y > drawing.HOLE_CALLOUT_XY[1] + 0.015
    right_view_left = (
        drawing.RIGHT_CENTER[0]
        - pd_guide_lock_spec.LOCK_THICK * drawing.SHEET_SCALE[0] / 2000.0
    )
    assert x + half < right_view_left


def test_the_plate_is_1_16_sheet_under_its_own_mill_band() -> None:
    """2026-10-11 (user): the lock is 1/16 in sheet as supplied, McMaster
    1388K196 (+/-0.005 in); the band is native on Depth@Lock, printed at
    .XXX with the stock callout above it, and the registry names the sheet."""
    import inspect

    import _config

    assert pd_guide_lock_spec.LOCK_THICK == pytest.approx(25.4 / 16.0)
    assert pd_guide_lock_spec.LOCK_THICK_BAND == pytest.approx(0.005 * 25.4)
    assert pd_guide_lock_spec.DRAWING_PRECISION_BY_NAME["Depth"] == 3
    assert (
        'set_dimension_symmetric_tolerance(adapter, "Lock", "Depth", LOCK_THICK_BAND)'
        in inspect.getsource(lock.build)
    )
    assert drawing.DIMENSION_CALLOUTS == {
        "Depth": pd_guide_lock_spec.LOCK_STOCK_CALLOUT
    }
    assert "AS SUPPLIED" in pd_guide_lock_spec.LOCK_STOCK_CALLOUT
    # An above-callout with a line break never prints.
    assert "\n" not in pd_guide_lock_spec.LOCK_STOCK_CALLOUT
    spec = _config.parts("pd-guide-lock")
    assert pd_guide_lock_spec.LOCK_STOCK_SKU in spec["material_specification"]
    assert "1/16" in spec["material"]


def test_part_registry_row_carries_the_title_block_facts() -> None:
    """Stock, finish and quantity live in the title block, not in notes."""
    import _config

    spec = _config.parts("pd-guide-lock")
    assert spec["material_specification"]
    assert "black oxide" in str(spec["finish"]).lower()
    assert int(spec["quantity"]) == 4


class _NativeHoleCallout:
    def __init__(self, below, *, ignore_write=False, corrupt_part=None):
        self.definitions = {
            5: "DRILL <hw-thruholedia>",
            6: "<hw-thru>",
            7: None,
            8: below,
        }
        self.ignore_write = ignore_write
        self.corrupt_part = corrupt_part
        self.writes = []

    def GetText(self, part):
        return self.definitions[part]

    def SetText(self, part, text):
        self.writes.append((part, text))
        if self.ignore_write:
            return
        assert part == 4
        self.definitions[8] = text.replace("\n", "\r\n")
        if self.corrupt_part is not None:
            self.definitions[self.corrupt_part] = "lost native variable"


@pytest.mark.parametrize("below", [None, "", "<hw-depth>\r\nEXISTING NOTE"])
def test_hole_mate_appends_to_definition_and_preserves_native_variables(monkeypatch, below) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    native = _NativeHoleCallout(below)
    before = {part: native.definitions[part] for part in (5, 6, 7)}
    existing = str(below or "").replace("\r", "").rstrip()
    expected = (
        f"{existing}\n{drawing.HOLE_MATE_CALLOUT}"
        if existing else drawing.HOLE_MATE_CALLOUT
    )
    drawing._name_hole_mate(native)
    assert native.writes == [(4, expected)]
    assert native.GetText(8).replace("\r", "") == expected
    assert {part: native.definitions[part] for part in (5, 6, 7)} == before


@pytest.mark.parametrize(
    "ignore_write,corrupt_part",
    [(True, None), (False, 5), (False, 6), (False, 7)],
)
def test_hole_mate_refuses_ignored_write_or_changed_native_definition(
    monkeypatch, ignore_write, corrupt_part
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    native = _NativeHoleCallout(
        "<hw-depth>", ignore_write=ignore_write, corrupt_part=corrupt_part
    )
    with pytest.raises(RuntimeError, match="mate or native definitions did not persist"):
        drawing._name_hole_mate(native)
