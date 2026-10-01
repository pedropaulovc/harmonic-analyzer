"""Offline contracts for the transgear hub cap (MHA-160) and its drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_transgear_hub_cap as part
import draw_transgear_hub_cap as drawing
import transgear_disc_hub_spec as disc_hub
import transgear_hub_cap_spec as spec
import transgear_stub_spec as stud
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _gtol_spec import PlanarFace
from _printed_tolerance import printed_band_mm
from _surface_finish import SEAT_UM

SW_TOL_MAX = 6  # swTolType_e.swTolMAX


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-hub-cap.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-hub-cap.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-hub-cap_drawing.png")
    row = DRAWINGS_BY_NAME["transgear_hub_cap"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_prints_in_exactly_one_view() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FACE_KEEP) | set(drawing.SECTION_KEEP) == marked
    assert not set(drawing.FACE_KEEP) & set(drawing.SECTION_KEEP)
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }


def test_no_size_restates_a_title_block_band_on_the_model() -> None:
    """Every size prints its places; the chamfer's single MAX limit is not a
    band and rides its own setter."""
    assert model_toleranced_dimensions(part) == {}


def test_front_chamfer_prints_a_max_that_the_flats_run_out_through() -> None:
    assert spec.FRONT_CHAMFER_TOL_TYPE == SW_TOL_MAX
    assert spec.FRONT_CHAMFER == spec.FRONT_CHAMFER_MAX
    # Smallest O.D. less the largest chamfer stays outside the widest flats.
    od_min = spec.CAP_DIA - printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["CapDia"])
    widest = spec.FLATS_ACROSS + printed_band_mm(
        spec.DRAWING_PRECISION_BY_NAME["FlatsAcross"]
    )
    assert od_min / 2.0 - spec.FRONT_CHAMFER > widest / 2.0


def test_the_drive_flats_leave_no_wall_under_the_target_at_the_printed_worst() -> None:
    """R9-58: the pin-spanner holes left a 0.685 countersink ligament (19e33c6c2
    review); the flats' only wall is flat to thread, 2.0 or more at the worst."""
    band = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["FlatsAcross"])
    narrowest = spec.FLATS_ACROSS - band
    widest = spec.FLATS_ACROSS + band
    thread_major_max = stud.FRONT_THREAD_MAJOR + 0.05
    assert (narrowest - thread_major_max) / 2.0 >= 2.0
    assert spec.FLAT_WALL_WORST == pytest.approx((narrowest - thread_major_max) / 2.0)
    # An 11/32 open-end spanner (basic 0.34375 in) takes the widest flats.
    assert widest <= 0.34375 * 25.4
    # The sleeve nose (the hub's press-seat shank at its largest) thrusts on
    # the rear face inside the narrowest flats.
    nose_max = disc_hub.SHANK_DIA + disc_hub.SHANK_DIA_BAND[0]
    assert narrowest > nose_max
    # Each flat keeps a real bearing chord at the smallest O.D.
    od_min = spec.CAP_DIA - printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["CapDia"])
    assert 2.0 * math.sqrt((od_min / 2.0) ** 2 - (widest / 2.0) ** 2) > 4.0
    # The build's volume gate charges both flats: an independent midpoint
    # sum of the segments over the length, the chamfer's radius included.
    steps = 2000
    removed = 0.0
    for i in range(steps):
        z = (i + 0.5) * spec.CAP_LENGTH / steps
        r = spec.CAP_DIA / 2.0 - max(0.0, z - (spec.CAP_LENGTH - spec.FRONT_CHAMFER))
        h = spec.FLATS_ACROSS / 2.0
        segment = r * r * math.acos(h / r) - h * math.sqrt(r * r - h * h)
        removed += 2.0 * segment * spec.CAP_LENGTH / steps
    assert part.V_FLATS == pytest.approx(removed, rel=1e-4)


def test_the_rear_seat_carries_the_seat_finish_on_its_section_edge() -> None:
    (finish,) = spec.SURFACE_FINISHES
    assert finish.key == "rear_face"
    assert finish.roughness_um == SEAT_UM
    assert finish.face == PlanarFace((0.0, 0.0, -1.0), 0.0)
    # The section lays the front (chamfered) end right: the pick is on the
    # left edge, in the cut wall between the tap drill and the O.D.
    pick_x, pick_y = drawing.REAR_FACE_PICK
    assert pick_x == pytest.approx(
        drawing.SECTION_CENTER[0] - spec.CAP_LENGTH * drawing._S / 2000.0
    )
    radius = (pick_y - drawing.SECTION_CENTER[1]) * 1000.0 / drawing._S
    assert spec.TAP_DRILL_DIA / 2.0 + 0.5 < radius < spec.CAP_DIA / 2.0 - 0.5
    symbol_x, symbol_y = drawing.REAR_FACE_SYMBOL_XY
    assert symbol_x < pick_x and symbol_y > drawing.SECTION_CENTER[1] + drawing.HALF_OD


# Text heights on the sheet: 3.5 mm dimensions, the A-A caption's large
# 7 mm "SECTION" (farm run 20261001T110844152Z).
DIM_TEXT_H = 0.0035
CAPTION_H = 0.007


def test_section_caption_clears_the_length_dimension() -> None:
    """19e33c6c2 printed SECTION A-A through the 5.80."""
    length_text_bottom = drawing.SECTION_KEEP["CapLength"][1] - DIM_TEXT_H
    # Whether the caption hangs from its anchor or stands on it, it stays
    # under the length text and over the notes.
    assert drawing.CAPTION_XY[1] + CAPTION_H < length_text_bottom
    assert drawing.CAPTION_XY[1] - CAPTION_H > drawing.NOTES_XY[1]


def test_face_view_callouts_stand_clear_of_the_cutting_line() -> None:
    """19e33c6c2: the upper A sat on the drill callout and the hole leaders
    crowded the cutting line."""
    line_x = drawing.SECTION_LINE[0][0]
    line_top = drawing.SECTION_LINE[1][1]
    flat_x = spec.FLATS_ACROSS * drawing._S / 2000.0
    # The thread callout's text block (about 52 x 16 mm about its anchor)
    # lies right of the flats and left of the section's seat symbol.
    callout_x, callout_y = drawing.THREAD_CALLOUT_XY
    assert callout_x - 0.026 > line_x + flat_x + 0.008
    assert callout_x + 0.026 < drawing.REAR_FACE_SYMBOL_XY[0] - 0.005
    assert callout_y + 0.008 < drawing.FACE_CENTER[1]
    # The across-flats text stands above the cutting line's end and its A.
    flats_y = drawing.FACE_KEEP["FlatsAcross"][1]
    assert flats_y - DIM_TEXT_H / 2.0 > line_top + 0.008


def test_cap_threads_onto_the_stud_and_seats_on_its_shoulder() -> None:
    assert spec.TAP_SPEC.size == stud.FRONT_THREAD
    # The stud's thread runs past the cap's worst-case engaged length even at
    # its shortest, so the cap (not the stud) bounds the engagement.
    assert stud.FRONT_THREAD_END_MIN > spec.CAP_LENGTH_MIN - spec.CSK_LOSS_MAX
    assert spec.REAR_FACE_MACHINE_Z == pytest.approx(
        stud.ARM_SEAT_MACHINE_Z - stud.CAP_SHOULDER_STATION
    )


def test_engagement_stack_charges_the_relief_and_the_countersink() -> None:
    nominal = (
        spec.CAP_LENGTH
        - stud.RELIEF_WIDTH
        - (spec.CSK_DIA - stud.FRONT_THREAD_MAJOR) / 2.0
    )
    worst = (
        spec.CAP_LENGTH_MIN
        - stud.RELIEF_WIDTH_MAX
        - (spec.CSK_DIA_MAX - stud.FRONT_THREAD_MAJOR) / 2.0
    )
    assert spec.ENGAGEMENT_NOMINAL == pytest.approx(nominal, abs=1e-6)
    assert spec.ENGAGEMENT_WORST == pytest.approx(worst, abs=1e-6)
    # Short of 1.5D: the policy's named exception carries it at the approved
    # floor.
    assert (
        spec.APPROVED_ENGAGEMENT_FLOOR_D
        <= spec.ENGAGEMENT_WORST_D
        < spec.ENGAGEMENT_NOMINAL_D
        < 1.5
    )


def test_sheet_notes_state_the_spec_engagement() -> None:
    notes = spec.DRAWING_NOTES
    assert f"{spec.ENGAGEMENT_NOMINAL_D_PRINTED:.2f}D NOMINAL" in notes
    assert f"{spec.ENGAGEMENT_WORST_D_PRINTED:.2f}D MIN" in notes
    # A MIN never rounds up past the arithmetic.
    assert spec.ENGAGEMENT_WORST_D_PRINTED <= spec.ENGAGEMENT_WORST_D
    assert all(len(line) <= 70 for line in notes.splitlines())
    assert len(notes.splitlines()) <= 4


def test_registry_row_is_the_turned_brass_mha_160() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-160"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args[:2]] == ["adapter", "PART_NAME"]
    extra = {
        ast.literal_eval(key): getattr(part, value.id)
        for key, value in zip(stamp.args[2].keys, stamp.args[2].values, strict=True)
    }
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
    assert carried["Manufacturing Notes"] == spec.DRAWING_NOTES
    assert carried["Isometric View Note"] == spec.ISOMETRIC_VIEW_NOTE
