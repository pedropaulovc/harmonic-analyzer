"""Offline contracts for the separate-hub crank-arm drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_crank_arm as arm
import build_drive_train_assembly as drive
import crank_arm_notes as notes
import crank_arm_spec as spec
import crank_hub_geometry as geometry
import crankshaft_spec
import draw_crank_arm as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import drill_process


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-arm_drawing.png")
    assert DRAWINGS_BY_NAME["crank_arm"].script == Path(drawing.__file__).resolve()


def test_arm_is_a_matched_receiver_for_the_separate_hub() -> None:
    assert spec.ARM_WIDTH == geometry.ARM_WIDTH == pytest.approx(25.4)
    assert spec.ARM_THICKNESS == geometry.ARM_THICKNESS == 8.0
    assert spec.HUB_SEAT_DIA == geometry.HUB_SEAT_DIA == 19.5
    assert spec.HALF_WIDTH == pytest.approx(12.7)
    assert "1 x 5/16 IN CF FLAT BAR AS SUPPLIED" in spec.DRAWING_NOTES
    # The arm bore is made first; the hub is turned to suit it (B1, Main
    # 2026-09-25: the fit is printed functionally, not as "match-fit").
    assert notes.HUB_SEAT_CALLOUT.splitlines() == [
        "MHA-137 HUB IS A LIGHT",
        "PRESS FIT IN THIS BORE;",
        "FACES FLUSH",
    ]
    assert "MATCH" not in notes.HUB_SEAT_CALLOUT
    assert "FACES FLUSH" in notes.HUB_SEAT_CALLOUT
    assert not hasattr(spec, "SHAFT_BORE_DIA")
    assert not hasattr(spec, "PIN_HOLE_SPEC")


def test_axial_seam_key_is_six_oclock_and_stops_halfway_through_arm() -> None:
    assert spec.AXIAL_PIN_DIA == geometry.AXIAL_PIN_DIA == 4.0
    assert spec.AXIAL_PIN_LENGTH == geometry.AXIAL_PIN_LENGTH == spec.ARM_THICKNESS / 2.0
    assert spec.AXIAL_PIN_X == geometry.AXIAL_PIN_RADIUS_FROM_AXIS == 9.75
    assert spec.AXIAL_PIN_Y == 0.0
    assert drive.CRANK_HUB_PIN_ORIGIN == pytest.approx(
        [drive.X_CRANK, drive.Y_CRANK - 9.75, drive.CRANK_FACE_Z]
    )
    assert drive.CRANK_HUB_PIN_ROWS == drive.IDENTITY


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert arm.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) == {"HubSeatDia"}
    assert drawing.DIMENSION_CALLOUTS["HubSeatDia"] == notes.HUB_SEAT_CALLOUT
    assert not hasattr(drawing, "TOP_KEEP")  # the seam callout replaced the view


def test_reference_dimensions_remain_model_owned() -> None:
    assert spec.DRAWING_DIMENSIONS["StationReference"] == {
        "PivotStation",
        "AnchorStation",
        "AnchorOffset",
        "AxisOffset",
        "Width",
    }
    assert spec.DRAWING_DIMENSIONS["HubSeatProfile"] == {"HubSeatDia"}
    assert spec.HALF_WIDTH - spec.ANCHOR_SCREW_Y == pytest.approx(8.2)
    assert spec.ARM_END_X + spec.HALF_WIDTH == pytest.approx(97.7)
    assert spec.DRAWING_REFERENCE_PRECISION == {"overall length reference": 1}


def test_punch_and_seam_operations_are_callouts_not_fake_dimensions() -> None:
    general = spec.DRAWING_NOTES
    assert "MHA-138" not in general and "O'CLOCK" not in general
    assert "MHA-024" not in general
    assert "DIMPLE" not in general
    seam = notes.SEAM_CALLOUT
    assert "MHA-137" in seam and "MHA-138" in seam and "LIGHT DRIVE FIT" in seam
    assert "AT ASSEMBLY" in seam
    assert seam.splitlines()[0] == "(<MOD-DIAM>4.0) <HOLE-DEPTH> 4.0"
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert all("Fiducial" not in name for name in marked)
    assert all("AxialPin" not in name for name in marked)


def test_sheet_uses_imported_part_precision_and_no_gdt() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert set(spec.DRAWING_PRECISION_BY_NAME) == set().union(
        *spec.DRAWING_DIMENSIONS.values()
    )
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {1}
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    assert model_toleranced_dimensions(arm) == {}
    assert spec.SURFACE_FINISHES == ()
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")


def test_anchor_callout_defers_thread_class_to_title_block() -> None:
    class NativeCallout:
        definition = "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH> <hw-threaddepth>"

        def GetText(self, part: int) -> str:
            assert part == 5
            return self.definition

        def SetText(self, part: int, text: str) -> None:
            assert part == 1
            self.definition = text

    callout = NativeCallout()
    drawing._omit_title_block_thread_class(callout)
    assert callout.definition == "<hw-threaddesc> <HOLE-DEPTH> <hw-threaddepth>"
    with pytest.raises(ValueError):
        drill_process(spec.ANCHOR_HOLE_SPEC)


def test_assembly_keeps_common_face_and_established_inboard_stations() -> None:
    assert drive.CRANK_FACE_Z == -183.0
    assert drive.CRANKSHAFT_Z0 == drive.CRANK_HUB_Z0 == drive.CRANK_ARM_Z0 == -183.0
    assert drive.CRANK_ARM_ORIGIN_Z == -175.0
    # MHA-024 moved 1.6 inboard with the rule-12 hub station (13.6).
    assert drive.CRANK_PIN_Z == pytest.approx(-169.4)
    assert drive.CRANK_HUB_REAR_Z == -163.0
    assert drive.REMOVABLE_Z0 - drive.CRANK_HUB_REAR_Z == pytest.approx(5.5)
    # W15: the shaft's length is crankshaft_spec's, never a restated literal.
    assert drive.CRANKSHAFT_LENGTH == crankshaft_spec.SHAFT_LENGTH
    assert drive.CRANKSHAFT_Z0 + drive.CRANKSHAFT_LENGTH == pytest.approx(-46.2)


def test_stock_anchor_still_clamps_eye_without_bottoming() -> None:
    import build_crank_pin_eye as eye
    import build_fillister_screw as screw

    wire_front = drive.EYE_Z - eye.WIRE_DIA / 2.0
    wire_back = drive.EYE_Z + eye.WIRE_DIA / 2.0
    assert drive.ANCHOR_HEAD_Z == pytest.approx(wire_front)
    assert drive.CRANK_ARM_Z0 - wire_back == pytest.approx(0.02)
    insertion = drive.ANCHOR_HEAD_Z + screw.SHANK_LEN - drive.CRANK_ARM_Z0
    assert insertion == pytest.approx(5.33)
    # Tapped THRU the stock bar (rule 12, W7): no drill point, no bottom, and
    # the tip stays inside the inboard face.
    assert spec.ANCHOR_HOLE_SPEC.end == "through_all"
    assert screw.SHANK_DIA < insertion < spec.ARM_THICKNESS
    assert drive.ANCHOR_TIP_RESERVE == pytest.approx(2.67)


def test_part_registry_retains_make_critical_properties() -> None:
    import _config

    part = _config.parts("crank-arm")
    assert part["number"] == "MHA-020"
    assert part["material"] == part["material_specification"]
    assert part["finish"]
    assert int(part["quantity"]) == 1


def test_notes_and_seat_callout_stay_inside_their_sheet_regions() -> None:
    # ~2.5 mm per character at the sheet's note height (measured on the
    # 5b164b70 render, where the old two-line callout ran off the border).
    char_w = 0.0025
    lines = spec.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4
    assert 0.016 + max(len(line) for line in lines) * char_w < 0.218  # title block
    seat_x = drawing.FRONT_KEEP["HubSeatDia"][0]
    half = max(len(line) for line in notes.HUB_SEAT_CALLOUT.splitlines()) * char_w / 2
    assert seat_x - half > 0.0128 + 0.003  # inner border plus air


def test_hub_end_callouts_stand_in_a_row_without_crossing_leaders() -> None:
    char_w = 0.0026  # measured on the U29 render
    scale = drawing.SHEET_SCALE[0] / 1000.0
    # The seam pick lies on the arm's half of the MHA-138 circle.
    seam_x = drawing._sheet_x(spec.AXIAL_PIN_X)
    x, y = drawing.SEAM_EDGE_PICK
    r = spec.AXIAL_PIN_DIA / 2.0 * scale
    assert (x - seam_x) ** 2 + (y - drawing.FRONT_CENTER[1]) ** 2 == pytest.approx(r**2)
    assert x > seam_x
    # Seat block (centred on its keep) ends left of the seam leader, which
    # drops from the seam block's left end to the pick; the anchor offset
    # dimension stands between that leader and the anchor tap.
    seat_x = drawing.FRONT_KEEP["HubSeatDia"][0]
    seat_right = seat_x + max(map(len, notes.HUB_SEAT_CALLOUT.splitlines())) * char_w / 2
    leader_x = min(drawing.SEAM_CALLOUT_XY[0], x)
    assert seat_right + 0.002 < leader_x
    anchor_x = drawing._sheet_x(spec.ANCHOR_SCREW_X)
    assert max(drawing.SEAM_CALLOUT_XY[0], x) < drawing.FRONT_KEEP["AnchorOffset"][0] < anchor_x
    seam_right = drawing.SEAM_CALLOUT_XY[0] + max(
        len(line) for line in notes.SEAM_CALLOUT.splitlines()
    ) * char_w
    assert seam_right < drawing.ANCHOR_CALLOUT_XY[0] or (
        drawing.ANCHOR_CALLOUT_XY[1] < drawing.SEAM_CALLOUT_XY[1] - 0.020
    )


def test_hub_seat_leader_lands_near_side_clear_of_r127_and_the_centre() -> None:
    # Eye pass of w15-301f4bf4e (and the 2026-09-23 review): with both arrows
    # the Ø19.5 leader ran from its text through the bore centre to the far
    # rim, crossing R12.7's leader at the centre. Near-side, one arrow lands
    # on the rim along the ray from the centre toward the text.
    import math

    import _drawing_leaders as leaders

    cx, cy = drawing.BORE_CENTER
    r = spec.HUB_SEAT_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.HUB_SEAT_KEEP_OUT == pytest.approx(r / 2.0)
    tx, ty = drawing.FRONT_KEEP["HubSeatDia"]
    assert tx < cx and ty > cy + r  # above the bore, left of its centre
    angle = math.atan2(ty - cy, tx - cx)
    near = (cx + r * math.cos(angle), cy + r * math.sin(angle))
    far = (cx - r * math.cos(angle), cy - r * math.sin(angle))
    radius = [(drawing.FRONT_KEEP["BossRadius"], (cx, cy))]
    old = [((tx, ty), far)]
    new = [((tx, ty), near)]
    assert leaders.distance_to_point(old[0], (cx, cy)) < drawing.HUB_SEAT_KEEP_OUT
    landing = {"HubSeatDia": drawing.HUB_SEAT_LANDING, "BossRadius": drawing.BOSS_RADIUS_LANDING}
    leaders.assert_leaders_clear(
        {"HubSeatDia": new, "BossRadius": radius},
        centre=(cx, cy),
        keep_out={"HubSeatDia": drawing.HUB_SEAT_KEEP_OUT},
        lands_within=landing,
        label="hub seat layout",
    )
    assert drawing.HUB_SEAT_LANDING[0] <= r <= drawing.HUB_SEAT_LANDING[1]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_hub_seat_leader_clear(adapter, front_annotations)" in source
    assert 'set_near_side_diameter(hub_seat, "hub seat diameter")' in source


def test_hub_seat_is_a_reference_nominal_under_its_match_fit_note() -> None:
    # 2026-09-23 review: a plain one-place Ø19.5 takes the title block's
    # +/-0.8 while the note makes it a match fit; the note alone governs.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        'set_reference_dimension(adapter, hub_seat, label="hub seat nominal", diameter=True)'
        in source
    )
    assert "LIGHT" in notes.HUB_SEAT_CALLOUT and "PRESS FIT" in notes.HUB_SEAT_CALLOUT


def test_no_front_dimension_text_sits_on_the_arm() -> None:
    # 2026-09-23 review: 8.2 sat inside the silhouette, between the top edge
    # and the 4-40 tap. It now reads above the top edge; the sheet-side check
    # reads every front text back.
    import _drawing_leaders as leaders

    x0, y0, x1, y1 = drawing.ARM_SILHOUETTE
    assert (x0, x1) == pytest.approx((drawing._sheet_x(-spec.HALF_WIDTH), drawing._sheet_x(spec.ARM_END_X)))
    assert y1 - y0 == pytest.approx(spec.ARM_WIDTH * drawing.SHEET_SCALE[0] / 1000.0)
    assert leaders.points_inside(list(drawing.FRONT_KEEP.values()), drawing.ARM_SILHOUETTE) == []
    assert leaders.points_inside([(0.106, drawing.FRONT_CENTER[1] + 0.017)], drawing.ARM_SILHOUETTE)
    ax, ay = drawing.FRONT_KEEP["AnchorOffset"]
    assert ay >= y1 + 0.006  # clear above the top edge
    assert "_texts_off_the_part(adapter, front_annotations)" in Path(drawing.__file__).read_text(
        encoding="utf-8"
    )


def test_handle_pivot_is_tapped_for_the_mha139_screw_with_a_2mm_web() -> None:
    assert spec.HANDLE_PIVOT_HOLE_SPEC.kind == "tapped"
    assert spec.HANDLE_PIVOT_HOLE_SPEC.size == "#10-24"
    assert spec.HANDLE_PIVOT_HOLE_SPEC.end == "through_all"
    assert spec.PIVOT_END_WEB_NOMINAL == pytest.approx(7.587)
    assert spec.PIVOT_END_WEB_WORST >= 2.0


def test_station_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880: a reference sketch owns printed dimensions but no geometry, so the
    # part saves it hidden (no assembly instance renders it) and the drawing
    # shows it per view through _drawing_hidden_sketches to import them.
    build = Path(arm.__file__).read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "StationReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source.replace("\r\n", "\n")
    assert "StationReference" in spec.DRAWING_DIMENSIONS


def test_arm_states_the_mha139_engagement_exception_it_is_tapped_for() -> None:
    # User ruling 2026-09-25 (MHA-020 review B2): the tapped arm states the
    # named exception with the same worst case the MHA-139 sheet prints.
    import crank_handle_pivot_screw_spec as screw

    assert spec.DRAWING_NOTES.splitlines()[-1] == screw.DRAWING_NOTES.replace(
        "THREAD ENGAGEMENT", "#10-24 THREAD ENGAGEMENT"
    )
    assert "1.15D MIN: NAMED EXCEPTION TO RULE 12." in spec.DRAWING_NOTES
    # The stock line comes from the one stock constant.
    assert spec.ARM_STOCK_THICKNESS == pytest.approx(7.9375)
    assert spec.STOCK_NOTE == "25.4 x 8.0 SECTION: 1 x 5/16 IN CF FLAT BAR AS SUPPLIED."


def _thinnest_accepted_arm() -> float:
    """The thinnest MHA-020 an inspector reading this sheet would accept.

    A toleranced 8.0 takes the title block's .X band. A reference (8.0) under
    the "AS SUPPLIED" stock line leaves the bar's own mill tolerance.
    """
    if "Depth" in getattr(spec, "REFERENCE_DIMENSIONS", frozenset()):
        return geometry.ARM_STOCK_THICKNESS_MIN
    return spec.ARM_THICKNESS - geometry.GENERAL_1PL_TOL_MM


def test_engagement_exception_holds_at_the_thinnest_accepted_arm() -> None:
    # Codex #892 (PRRT_kwDOPHDy386mMvsy): at a printed 8.0 +/-0.8 an arm
    # accepted at 7.2 leaves min(8.0, 7.2 - 0.25) - 2.01 = 4.94 = 1.02D, under
    # both the note's 1.17D and U33b's 1.15D floor.
    import crank_handle_pivot_screw_spec as screw

    thinnest = _thinnest_accepted_arm()
    worst = (
        min(screw.FULL_THREAD_REACH_MIN, thinnest - screw.TAP_EXIT_BREAK)
        - screw.RELIEF_WIDTH_MAX
    )
    assert worst >= screw.ENGAGEMENT_FLOOR, (thinnest, worst / screw.THREAD_MODEL_DIA)
    # The note never claims more than the thinnest accepted arm delivers.
    assert screw.FULL_THREAD_WORST == pytest.approx(worst)
    assert screw.FULL_THREAD_WORST_DIAMETERS_PRINTED <= worst / screw.THREAD_MODEL_DIA


def test_arm_thickness_prints_as_a_reference_to_the_supplied_stock() -> None:
    # The stock line governs the thickness (the U41 platform precedent), so
    # the 8.0 is parenthesised rather than taking the .X band.
    assert spec.REFERENCE_DIMENSIONS == {"Depth"}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_named(adapter, right_annotations, name)" in source
    assert 'label="arm stock thickness"' in source
