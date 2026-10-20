"""Offline contracts for the separate-hub crank-arm drawing."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_dt_crank_arm as arm
import build_dt_drive_train_assembly as drive
import dt_crank_arm_notes as notes
import dt_crank_arm_spec as spec
import dt_crank_hub_geometry as geometry
import draw_dt_crank_arm as drawing
import pd_transgear_removable_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import drill_process


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-arm_drawing.png")
    assert DRAWINGS_BY_NAME["dt_crank_arm"].script == Path(drawing.__file__).resolve()


def test_arm_is_a_matched_receiver_for_the_separate_hub() -> None:
    assert spec.ARM_WIDTH == geometry.ARM_WIDTH == pytest.approx(25.4)
    assert spec.ARM_THICKNESS == geometry.ARM_THICKNESS == 8.0
    assert spec.HUB_SEAT_DIA == geometry.HUB_SEAT_DIA == 19.4
    assert spec.HALF_WIDTH == pytest.approx(12.7)
    assert "1 x 5/16 IN CF FLAT BAR AS SUPPLIED" in spec.DRAWING_NOTES
    # The arm bore is made first; the hub is turned to suit it (B1, Main
    # 2026-09-25: the fit is printed functionally, not as "match-fit"), to the
    # one interference the hub sheet states (#984 review r1: an acceptance).
    low, high = geometry.SEAT_PRESS_INTERFERENCE
    assert f"{low:.3f}-{high:.3f}" in notes.HUB_SEAT_CALLOUT
    assert "MHA-DT-31" in notes.HUB_SEAT_CALLOUT
    assert "MATCH" not in notes.HUB_SEAT_CALLOUT
    assert "FACES FLUSH" in notes.HUB_SEAT_CALLOUT
    assert not hasattr(spec, "SHAFT_BORE_DIA")
    assert not hasattr(spec, "PIN_HOLE_SPEC")


def test_axial_seam_key_is_six_oclock_and_stops_halfway_through_arm() -> None:
    assert spec.AXIAL_PIN_DIA == geometry.AXIAL_PIN_DIA == 4.0
    assert spec.AXIAL_PIN_LENGTH == geometry.AXIAL_PIN_LENGTH == spec.ARM_THICKNESS / 2.0
    assert spec.AXIAL_PIN_X == geometry.AXIAL_PIN_RADIUS_FROM_AXIS == 9.7
    assert spec.AXIAL_PIN_Y == 0.0
    assert drive.CRANK_HUB_PIN_ORIGIN == pytest.approx(
        [drive.X_CRANK, drive.Y_CRANK - 9.7, drive.CRANK_FACE_Z]
    )
    assert drive.CRANK_HUB_PIN_ROWS == drive.IDENTITY


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert arm.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert "BoreRearChamferSize" in drawing.FRONT_KEEP
    assert set(drawing.DIMENSION_CALLOUTS) == {"HubSeatDia", "BoreRearChamferSize"}
    assert drawing.DIMENSION_CALLOUTS["HubSeatDia"] == notes.HUB_SEAT_CALLOUT
    assert (
        drawing.DIMENSION_CALLOUTS["BoreRearChamferSize"]
        == notes.BORE_REAR_CHAMFER_CALLOUT
    )
    assert not hasattr(drawing, "TOP_KEEP")  # the seam callout replaced the view


def test_reference_dimensions_remain_model_owned() -> None:
    assert spec.DRAWING_DIMENSIONS["StationReference"] == {
        "PivotStation",
        "AnchorStation",
        "AnchorOffset",
        "Width",
    }
    assert spec.DRAWING_DIMENSIONS["HubSeatProfile"] == {"HubSeatDia"}
    assert spec.HALF_WIDTH - spec.ANCHOR_SCREW_Y == pytest.approx(8.2)
    assert spec.ARM_END_X + spec.HALF_WIDTH == pytest.approx(100.4)


def test_handle_end_is_a_semicircle_about_the_pivot() -> None:
    # User ruling 2026-09-29 (ch11 p.14 re-check): both ends are R12.7 caps
    # concentric with their holes; the crank radius stays 75.
    assert spec.ARM_C2C == pytest.approx(75.0)
    assert spec.END_RADIUS == pytest.approx(spec.HALF_WIDTH)
    assert spec.ARM_END_X == pytest.approx(87.7)
    assert spec.DRAWING_DIMENSIONS["ArmOutline"] == {"BossRadius", "EndRadius"}
    assert not hasattr(spec, "SQUARE_END_OVERHANG")
    assert spec.DRAWING_REFERENCE_PRECISION == {"overall length reference": 1}


def test_punch_and_seam_operations_are_callouts_not_fake_dimensions() -> None:
    general = spec.DRAWING_NOTES
    assert "MHA-DT-VN-59" not in general and "O'CLOCK" not in general
    assert "MHA-DT-09" not in general
    assert "DIMPLE" not in general
    seam = notes.SEAM_CALLOUT
    assert "MHA-DT-31" in seam and "MHA-DT-VN-59" in seam and "LIGHT DRIVE FIT" in seam
    assert "AT ASSEMBLY" in seam
    assert "THREAD FOR EXTRACTION" in seam
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
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {1, 2}
    assert {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 2
    } == {"BoreRearChamferSize"}
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
    # MHA-DT-09 moved 1.6 inboard with the drawing-guidelines.md rule 17 (walls and webs) hub station (13.6).
    assert drive.CRANK_PIN_Z == pytest.approx(-169.4)
    # The hub rear reaches the removable: 0.7 air to its front face.
    assert drive.CRANK_HUB_REAR_Z == pytest.approx(-157.8)
    assert (
        pd_transgear_removable_spec.BAND_FRONT_Z - drive.CRANK_HUB_REAR_Z
        == pytest.approx(0.7)
    )
    # Owner ruling D1 (2026-10-15): the shaft end stands proud of the pinion's
    # north face by the spec's stack, past the match-drilled pin.
    import dt_crank_pinion_spec
    import dt_crankshaft_spec

    shaft_end = drive.CRANKSHAFT_Z0 + drive.CRANKSHAFT_LENGTH
    proud = shaft_end - (drive.PINION_Z0 + drive.PINION_OVERALL_LENGTH)
    least, most = dt_crankshaft_spec.SHAFT_END_PROUD_RANGE
    assert 0.0 <= least <= proud <= most
    assert shaft_end > drive.PINION_PIN_Z + dt_crank_pinion_spec.PIN_DIA / 2.0


def test_stock_anchor_still_clamps_eye_without_bottoming() -> None:
    import dt_crank_pin_eye_spec as eye
    import _mcmaster_90114a511 as screw

    wire_front = drive.EYE_Z - eye.WIRE_DIA / 2.0
    wire_back = drive.EYE_Z + eye.WIRE_DIA / 2.0
    assert drive.ANCHOR_HEAD_Z == pytest.approx(wire_front)
    assert drive.CRANK_ARM_Z0 - wire_back == pytest.approx(0.02)
    insertion = drive.ANCHOR_HEAD_Z + screw.SHANK_LEN - drive.CRANK_ARM_Z0
    assert insertion == pytest.approx(5.33)
    # Tapped THRU the stock bar (drawing-guidelines.md rule 17 (walls and webs), W7): no drill point, no bottom, and
    # the tip stays inside the inboard face.
    assert spec.ANCHOR_HOLE_SPEC.end == "through_all"
    assert screw.SHANK_DIA < insertion < spec.ARM_THICKNESS
    assert drive.ANCHOR_TIP_RESERVE == pytest.approx(2.67)


def test_part_registry_retains_make_critical_properties() -> None:
    import _config

    part = _config.parts("dt-crank-arm")
    assert part["number"] == "MHA-DT-06"
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
    # The seam pick lies on the arm's half of the MHA-DT-VN-59 circle.
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


def test_hub_seat_keeps_its_printed_band_under_the_fit_note() -> None:
    # The 2026-09-23 review printed the bore as a reference so the note alone
    # governed.  Main 2026-09-25 (U29 follow-up): the bore is made first, so
    # its .X band is the cheek's real limit and stays printed; the note states
    # the fit MHA-DT-31 is turned to (drawing-guidelines.md rule 4 (tighten only for function, and name the mate): retained limits still apply).
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "hub seat nominal" not in source
    assert spec.DRAWING_PRECISION["HubSeatProfile"]["HubSeatDia"] == 1
    assert "DIAMETRAL" in notes.HUB_SEAT_CALLOUT


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
    import dt_crank_handle_pivot_screw_spec as screw

    # User ruling 2026-09-30: the handle pivot screw is #4-40 (after #6-32
    # left the Ø4 shoulder no seat, local review of fbf82ad96).
    assert spec.HANDLE_PIVOT_HOLE_SPEC.size == screw.THREAD_SIZE == "#4-40"
    assert spec.HANDLE_PIVOT_HOLE_SPEC.end == "through_all"
    assert spec.PIVOT_END_WEB_NOMINAL == pytest.approx(12.7 - 2.845 / 2.0)
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


def test_arm_states_no_engagement_exception_for_the_4_40_pivot() -> None:
    # The #4-40 handle pivot (user ruling 2026-09-30) meets the 1.5D rule, so
    # the tapped arm no longer states the #8-32's named exception.
    assert not hasattr(spec, "PIVOT_ENGAGEMENT_NOTE")
    assert "THREAD ENGAGEMENT" not in spec.DRAWING_NOTES
    assert spec.STOCK_NOTE in spec.DRAWING_NOTES.splitlines()
    # The tapped mouth's limit (MHA-DT-32 shoulder seat, local review of
    # fbf82ad96) rides the pivot's own callout, not a general note (#984 r1).
    import dt_crank_handle_pivot_screw_spec as screw

    assert "MOUTH" not in spec.DRAWING_NOTES
    assert f"{screw.TAPPED_MOUTH_DIA_MAX:.1f} MAX" in notes.PIVOT_TAP_ROWS
    assert "MHA-DT-32" in notes.PIVOT_TAP_ROWS


def test_fiducial_callout_attaches_on_the_punched_mark_rim() -> None:
    # #984 review r2/r3: the fiducial is flagged at the mark, not in a note.
    assert "FIDUCIAL" not in spec.DRAWING_NOTES
    scale = drawing.SHEET_SCALE[0] / 1000.0
    cx = drawing._sheet_x(spec.FIDUCIAL_X)
    cy = drawing.FRONT_CENTER[1] + spec.FIDUCIAL_Y * scale
    x, y = drawing.FIDUCIAL_EDGE_PICK
    r = spec.FIDUCIAL_MODEL_DIA / 2.0 * scale
    assert (x - cx) ** 2 + (y - cy) ** 2 == pytest.approx(r**2)
    # The note stands above the arm's top edge, left of the hub-seat leader.
    assert drawing.FIDUCIAL_CALLOUT_XY[1] > drawing.ARM_SILHOUETTE[3]
    assert drawing.FIDUCIAL_CALLOUT_XY[0] < cx


def test_stock_line_comes_from_the_one_stock_constant() -> None:
    # The stock line comes from the one stock constant.
    assert spec.ARM_STOCK_THICKNESS == pytest.approx(7.9375)
    assert spec.STOCK_NOTE == "25.4 x 8.0 SECTION: 1 x 5/16 IN CF FLAT BAR AS SUPPLIED."


def _thinnest_accepted_arm() -> float:
    """The thinnest MHA-DT-06 an inspector reading this sheet would accept.

    A toleranced 8.0 takes the title block's .X band. A reference (8.0) under
    the "AS SUPPLIED" stock line leaves the bar's own mill tolerance.
    """
    if "Depth" in getattr(spec, "REFERENCE_DIMENSIONS", frozenset()):
        return geometry.ARM_STOCK_THICKNESS_MIN
    return spec.ARM_THICKNESS - geometry.GENERAL_1PL_TOL_MM


def test_engagement_rule_holds_at_the_thinnest_accepted_arm() -> None:
    # Codex #892 (PRRT_kwDOPHDy386mMvsy): at a printed 8.0 +/-0.8 an arm
    # accepted at 7.2 would leave min(9.1, 7.2 - 0.25) - 2.3 = 4.65 = 1.33D,
    # under the 1.5D rule; the stock reference keeps it at 1.51D.
    import dt_crank_handle_pivot_screw_spec as screw

    thinnest = _thinnest_accepted_arm()
    worst = (
        min(screw.FULL_THREAD_REACH_MIN, thinnest - screw.TAP_EXIT_BREAK)
        - screw.RELIEF_WIDTH_MAX
    )
    assert worst >= screw.ENGAGEMENT_FLOOR, (thinnest, worst / screw.THREAD_MODEL_DIA)
    # The spec's worst case is the thinnest accepted arm's.
    assert screw.FULL_THREAD_WORST == pytest.approx(worst)


def test_arm_thickness_prints_as_a_reference_to_the_supplied_stock() -> None:
    # The stock line governs the thickness (the U41 platform precedent), so
    # the 8.0 is parenthesised rather than taking the .X band.
    assert spec.REFERENCE_DIMENSIONS == {"Depth"}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_named(adapter, right_annotations, name)" in source
    assert 'label="arm stock thickness"' in source


# --- Inboard bore-mouth chamfer (MHA-DT-31 seat-root clearance) ------------


def test_bore_rear_chamfer_is_the_hub_contract() -> None:
    least, most = spec.BORE_REAR_CHAMFER_LEG
    assert spec.BORE_REAR_CHAMFER_LEG is geometry.ARM_BORE_REAR_CHAMFER_LEG
    # A 45-degree chamfer of leg c clears a root radius R when c >= R.
    assert least >= geometry.SEAT_ROOT_FILLET_R
    # Its largest leg is the arm-side break the hub's shoulder land assumes.
    assert most == geometry.EDGE_BREAK_MAX_MM
    # The model carries the largest leg; the LIMIT band runs down to the least.
    assert spec.BORE_REAR_CHAMFER == most
    assert spec.BORE_REAR_CHAMFER_TOL_TYPE == 3  # swTolType_e.swTolLIMIT
    lower, upper = spec.BORE_REAR_CHAMFER_DEVIATIONS
    assert upper == 0.0
    assert spec.BORE_REAR_CHAMFER + lower == pytest.approx(least)
    places = spec.DRAWING_PRECISION_BY_NAME["BoreRearChamferSize"]
    assert f"{most:.{places}f}/{least:.{places}f}" == "0.25/0.10"


def test_hub_shoulder_land_keeps_its_floor_under_the_largest_chamfer() -> None:
    land = (
        (geometry.HUB_BARREL_DIA_MIN - geometry.HUB_SEAT_DIA_MAX_MATCHED) / 2.0
        - spec.BORE_REAR_CHAMFER_LEG[1]
        - geometry.EDGE_BREAK_MAX_MM
    )
    assert land >= geometry.SHOULDER_LAND_WORST_MIN - 1e-9
    assert land == pytest.approx(geometry.HUB_SHOULDER_LAND_WORST_MM)  # 0.255


def test_bore_rear_chamfer_costs_no_wall_margin() -> None:
    import math

    from _hole_spec import THREAD_MAJOR_MM

    # The cheek's worst case already takes a full title-block break off each
    # edge, so a chamfer no larger than that break leaves it unchanged.
    assert spec.BORE_REAR_CHAMFER <= geometry.EDGE_BREAK_MAX_MM
    assert geometry.ARM_CHEEK_WORST_MM >= geometry.WALL_TARGET_MM
    # The seam half-hole enters from the outboard face and stops at
    # mid-thickness: 3.75 of solid stands between it and the chamfer.
    seam_gap = spec.ARM_THICKNESS - spec.AXIAL_PIN_LENGTH - spec.BORE_REAR_CHAMFER
    assert seam_gap == pytest.approx(3.75)
    # The keeper anchor tap stands far outside the chamfer's outer edge.
    anchor_r = math.hypot(spec.ANCHOR_SCREW_X, spec.ANCHOR_SCREW_Y)
    chamfer_r = spec.HUB_SEAT_DIA / 2.0 + spec.BORE_REAR_CHAMFER
    web = anchor_r - THREAD_MAJOR_MM[spec.ANCHOR_HOLE_SPEC.size] / 2.0 - chamfer_r
    assert web > geometry.WALL_TARGET_MM
    # The fiducial is punched in the outboard face, the far side of the bar.
    assert spec.FIDUCIAL_MODEL_DEPTH < spec.ARM_THICKNESS - spec.BORE_REAR_CHAMFER


@pytest.mark.parametrize(
    ("changed", "message"),
    (
        ({}, None),
        ({"full_name": "BoreRearChamferSize@OtherChamfer@dt-crank-arm.SLDPRT"}, "identity/type"),
        ({"full_name": "OtherSize@BoreRearChamfer@dt-crank-arm.SLDPRT"}, "identity/type"),
        ({"dimension_type": 1}, "identity/type"),
        ({"leg": 0.1}, "model leg"),
        ({"kind": 6}, "LIMIT band"),
        ({"lower": -0.05}, "LIMIT band"),
        ({"upper": 0.1}, "LIMIT band"),
    ),
)
def test_imported_chamfer_rejects_changed_native_limits(monkeypatch, changed, message):
    values = {
        "leg": spec.BORE_REAR_CHAMFER,
        "full_name": "BoreRearChamferSize@BoreRearChamfer@dt-crank-arm.SLDPRT",
        "dimension_type": 0,
        "kind": spec.BORE_REAR_CHAMFER_TOL_TYPE,
        "lower": spec.BORE_REAR_CHAMFER_DEVIATIONS[0],
        "upper": spec.BORE_REAR_CHAMFER_DEVIATIONS[1],
        **changed,
    }
    tolerance = SimpleNamespace(
        Type=values["kind"],
        GetMinValue=lambda: values["lower"] / 1000.0,
        GetMaxValue=lambda: values["upper"] / 1000.0,
    )
    dimension = SimpleNamespace(
        FullName=values["full_name"],
        GetType=lambda: values["dimension_type"],
        SystemValue=values["leg"] / 1000.0,
        Tolerance=tolerance,
    )
    display = SimpleNamespace(GetDimension2=lambda _: dimension)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    if message is None:
        drawing._assert_chamfer_limits(annotation)
    else:
        with pytest.raises(RuntimeError, match=message):
            drawing._assert_chamfer_limits(annotation)


def test_bore_rear_chamfer_callout_names_front_view_face_mate_and_intent() -> None:
    rows = [row.strip() for row in notes.BORE_REAR_CHAMFER_CALLOUT.splitlines()]
    assert rows == ["X 45 DEG", "FAR SIDE", "HUB SIDE", "PRESS", "LEAD-IN"]
    # The primary native callout names the mate and fit on this SAME bore;
    # repeating its long Number on the chamfer would consume border air.
    assert "MHA-DT-31" in drawing.DIMENSION_CALLOUTS["HubSeatDia"]
    assert "LIGHT PRESS" in drawing.DIMENSION_CALLOUTS["HubSeatDia"]
    assert "MHA-DT-31" not in notes.BORE_REAR_CHAMFER_CALLOUT
    # The angle remains the approved native-dimension suffix. Neither the
    # controlling leg nor either LIMIT value is duplicated as typed prose.
    assert "0.25" not in notes.BORE_REAR_CHAMFER_CALLOUT
    assert "0.10" not in notes.BORE_REAR_CHAMFER_CALLOUT
    assert "INBOARD" not in notes.BORE_REAR_CHAMFER_CALLOUT
    assert all(len(row) <= 8 for row in rows)


def _native_chamfer(**changed):
    tolerance = SimpleNamespace(
        Type=spec.BORE_REAR_CHAMFER_TOL_TYPE,
        GetMinValue=lambda: spec.BORE_REAR_CHAMFER_DEVIATIONS[0] / 1000.0,
        GetMaxValue=lambda: spec.BORE_REAR_CHAMFER_DEVIATIONS[1] / 1000.0,
    )
    dimension = SimpleNamespace(
        Name="BoreRearChamferSize",
        FullName="BoreRearChamferSize@BoreRearChamfer@dt-crank-arm.SLDPRT",
        GetType=lambda: 0,
        SystemValue=spec.BORE_REAR_CHAMFER / 1000.0,
        Tolerance=tolerance,
    )
    display = SimpleNamespace(
        GetDimension=lambda: dimension,
        GetDimension2=lambda _: dimension,
        GetOverride=lambda: changed.get("override", False),
        ShowDimensionValue=changed.get("show_value", True),
        IsReferenceDim=lambda: changed.get("reference", False),
        GetPrimaryTolPrecision2=lambda: changed.get("precision", 2),
        GetText=lambda _: changed.get("text", notes.BORE_REAR_CHAMFER_CALLOUT),
        OffsetText=changed.get("offset", True),
    )
    def parameter(name):
        assert name == "BoreRearChamferSize@BoreRearChamfer"
        return changed.get("source_dimension", dimension)
    front = SimpleNamespace(ReferencedDocument=SimpleNamespace(Parameter=parameter))
    annotation = SimpleNamespace(
        GetSpecificAnnotation=lambda: display,
        GetType=lambda: changed.get("annotation_type", 4),
        Visible=changed.get("visible", 1),
        OwnerType=changed.get("owner_type", 0),
        Owner=changed.get("owner", front),
        IsDangling=lambda: changed.get("dangling", False),
        position=changed.get("position", (*drawing.FRONT_KEEP["BoreRearChamferSize"], 0.0)),
    )
    def set_position(x, y, z):
        annotation.position = (x, y, z)
        return True
    annotation.SetPosition2 = set_position
    annotation.GetPosition = lambda: annotation.position
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(IsSame=lambda a, b: 1 if a is b else 0),
        _attempt=lambda fn: fn(),
        _get_attr_or_call=lambda obj, name: (
            getattr(obj, name)() if callable(getattr(obj, name)) else getattr(obj, name)
        ),
    )
    return adapter, front, annotation, display


@pytest.mark.parametrize(
    "changed",
    (
        {"annotation_type": 6},
        {"visible": 0},
        {"visible": 2},
        {"visible": 3},
        {"owner_type": 1},
        {"owner": object()},
        {"dangling": True},
        {"source_dimension": None},
        {"source_dimension": object()},
        {"override": True},
        {"show_value": False},
        {"reference": True},
        {"precision": 1},
        {"text": "FAR SIDE"},
    ),
)
def test_front_chamfer_rejects_lost_native_ownership_or_display(changed) -> None:
    adapter, front, annotation, _display = _native_chamfer(**changed)
    with pytest.raises(RuntimeError):
        drawing._assert_front_chamfer(adapter, front, annotation)


def test_front_chamfer_offsets_the_actual_model_dimension_without_replacing_it(monkeypatch) -> None:
    adapter, front, annotation, display = _native_chamfer()
    positions = []
    def offset(adapter_arg, annotations, targets):
        assert adapter_arg is adapter and annotations == [annotation]
        assert display.OffsetText is False
        assert annotation.position[:2] == drawing.CHAMFER_MOUTH_XY
        positions.append(targets)
        display.OffsetText = True
        annotation.SetPosition2(*targets["BoreRearChamferSize"], 0.0)
    monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    drawing._place_front_chamfer(adapter, front, [annotation])
    drawing._assert_front_chamfer(adapter, front, annotation)
    assert positions == [{"BoreRearChamferSize": drawing.FRONT_KEEP["BoreRearChamferSize"]}]
    assert display.GetDimension2(0).SystemValue == spec.BORE_REAR_CHAMFER / 1000.0
    with pytest.raises(RuntimeError, match="expected one"):
        drawing._place_front_chamfer(adapter, front, [])
    with pytest.raises(RuntimeError, match="expected one"):
        drawing._place_front_chamfer(adapter, front, [annotation, annotation])


@pytest.mark.parametrize("refusal", ("offset", "position"))
def test_front_chamfer_refuses_ignored_native_text_placement(monkeypatch, refusal) -> None:
    adapter, front, annotation, display = _native_chamfer()
    def offset(_adapter, _annotations, targets):
        display.OffsetText = refusal != "offset"
        if refusal != "position":
            annotation.SetPosition2(*targets["BoreRearChamferSize"], 0.0)
    monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    with pytest.raises(RuntimeError, match="offset leader"):
        drawing._place_front_chamfer(adapter, front, [annotation])


def test_chamfer_lane_uses_the_native_proof_and_preserves_other_layout() -> None:
    # Proof 20261020T042443087Z: border12.7, overall extension44.6,
    # R12.7 shelf139.2219, fiducial's lowest centre-mark ink152.0392 (mm).
    left, bottom, right, top = drawing.CHAMFER_TEXT_LANE
    assert left == pytest.approx(0.0127 + 0.003)
    assert right == pytest.approx(0.0446 - 0.002)
    tx, ty = drawing.FRONT_KEEP["BoreRearChamferSize"]
    # Budget the WHOLE block, not just glyph advance: keep the old block's
    # measured padding beyond its widest row; the angle is now the widest
    # row, without its old two spaces. The live ink readback must prove it.
    width = 0.029864 - 0.0272465 + 0.0245243 - 2.0 * 0.0009443
    half_height = (2 + len(notes.BORE_REAR_CHAMFER_CALLOUT.splitlines())) * 0.0055563 / 2
    assert left <= tx - width / 2 < tx + width / 2 <= right
    assert bottom <= ty - half_height < ty + half_height <= top
    assert bottom > 0.0702219 + 0.003  # overall DIMENSION line, not its witness
    assert top < 0.1392219 - 0.003
    assert drawing.CHAMFER_MOUTH_XY == pytest.approx((0.0506, 0.142))
    assert drawing.FRONT_KEEP["BossRadius"] == pytest.approx((0.030, 0.148))
    assert 0.142 + 0.006 - 0.0027781 + 0.0035 + 0.003 < 0.1520392
    assert drawing.FRONT_CENTER == (0.145, 0.142)
    assert drawing.RIGHT_CENTER == (0.300, 0.142)
    assert drawing.ISO_CENTER == (0.360, 0.230)


@pytest.mark.parametrize(
    ("changed", "message"),
    (
        ({}, None),
        ({"offset": False}, "final offset leader"),
        ({"position": (*drawing.CHAMFER_MOUTH_XY, 0.0)}, "final offset leader"),
        ({"box": (0.0156, 0.090, 0.041, 0.130)}, "clear lane"),
        ({"box": (0.016, 0.090, 0.0427, 0.130)}, "clear lane"),
        ({"box": (0.016, 0.079, 0.041, 0.130)}, "clear lane"),
        ({"box": (0.016, 0.090, 0.041, 0.136)}, "clear lane"),
        ({"route": []}, "land on the seat bore"),
        ({"route": [((0.070, 0.142), (0.041, 0.111))]}, "land on the seat bore"),
        ({"route": [((0.0446, 0.142), (0.041, 0.111))]}, "land on the seat bore"),
        ({"cross": "HubSeatDia"}, "existing callouts"),
        ({"cross": "BossRadius"}, "existing callouts"),
        ({"cross": "seam"}, "existing callouts"),
        ({"cross": "fiducial"}, "existing callouts"),
        ({"text_strike": True}, "existing callouts"),
    ),
)
def test_chamfer_checks_native_ink_landing_and_foreign_callouts(monkeypatch, changed, message) -> None:
    adapter, front, annotation, _display = _native_chamfer(**changed)
    seat = SimpleNamespace(name="HubSeatDia")
    radius = SimpleNamespace(name="BossRadius")
    others = {
        "HubSeatDia": [((0.0730572, 0.1611576), (0.0810243, 0.2110826))],
        "BossRadius": [((0.0227642, 0.1452219), (0.070, 0.142))],
        "seam": [((0.1034507, 0.2485139), (0.0920442, 0.1450013))],
        "fiducial": [((0.0499773, 0.190136), (0.0536482, 0.1584534))],
    }
    if "cross" in changed:
        others[changed["cross"]] = [((0.038, 0.134), (0.060, 0.134))]
    if changed.get("text_strike"):
        others["seam"] = [((0.020, 0.100), (0.030, 0.100))]
    route = changed.get("route", [(drawing.CHAMFER_MOUTH_XY, (0.041, 0.111))])
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, item: (
        "BoreRearChamferSize" if item is annotation else item.name
    ))
    monkeypatch.setattr(drawing, "dimension_segments", lambda item: (
        route if item is annotation else others[item.name]
    ))
    monkeypatch.setattr(drawing, "leader_segments", lambda item: others[item.name])
    monkeypatch.setattr(drawing, "callout_ink", lambda *_a, **_kw: SimpleNamespace(
        text=changed.get("box", (0.016, 0.090, 0.041, 0.130))
    ))
    attached_notes = {
        name: SimpleNamespace(GetAnnotation=lambda name=name: SimpleNamespace(name=name))
        for name in ("seam", "fiducial")
    }
    if message is None:
        drawing._front_chamfer_clear(adapter, front, [annotation, seat, radius], attached_notes)
    else:
        with pytest.raises(RuntimeError, match=message):
            drawing._front_chamfer_clear(adapter, front, [annotation, seat, radius], attached_notes)


def test_build_imports_chamfer_only_into_front_and_creates_no_cut_view(monkeypatch) -> None:
    views, curated, hlr, hlv, text = [], [], [], [], []
    adapter = SimpleNamespace(currentModel=object())
    async def open_model(_path):
        return None
    adapter.open_model = open_model
    monkeypatch.setattr(drawing, "SOURCE", SimpleNamespace(is_file=lambda: True))
    monkeypatch.setattr(drawing, "check", lambda *_a: None)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *_a, **_kw: None)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_a, **_kw: (object(), object()))
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *_a: None)
    def place(_adapter, _source, orientation, *xy, **_kw):
        view = SimpleNamespace(orientation=orientation, xy=xy, mode=None,
                               UpdateViewDisplayGeometry=lambda: None)
        views.append(view)
        return view
    def curate(_adapter, view, *, keep, dimensions_by_feature, **_kw):
        assert dimensions_by_feature is spec.DRAWING_DIMENSIONS
        assert view.mode == (1 if view.orientation == "*Front" else 2)
        if view.orientation == "*Front":
            assert hlv == [view]  # HLV before native model-item import
        curated.append((view.orientation, set(keep)))
        return [SimpleNamespace(name=name) for name in keep]
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    def hidden_removed(_adapter, view):
        view.mode = 2
        hlr.append(view)
    def hidden_visible(_adapter, view):
        view.mode = 1
        hlv.append(view)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", hidden_removed)
    monkeypatch.setattr(drawing, "set_hidden_lines_visible", hidden_visible)
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, annotation: annotation.name)
    monkeypatch.setattr(drawing, "set_dimension_callouts", lambda _a, annotations, rows: (
        text.append((set(item.name for item in annotations), rows))
    ))
    for name in (
        "assert_imported_precision", "set_reference_dimension", "_hub_seat_leader_clear",
        "_texts_off_the_part", "_omit_title_block_thread_class", "_append_callout_rows",
        "set_arc_endpoints_to_max", "_set_reference_precision", "add_property_linked_note",
    ):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    placed = []
    monkeypatch.setattr(drawing, "_place_front_chamfer", lambda _a, view, annotations: (
        placed.append((view, annotations))
    ))
    checked = []
    monkeypatch.setattr(drawing, "_front_chamfer_clear", lambda _a, view, annotations, notes: (
        checked.append((view, annotations, set(notes), view.mode, len(hlv)))
    ))
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *_a, **_kw: True)
    monkeypatch.setattr(drawing, "add_native_hole_callout", lambda *_a, **_kw: object())
    monkeypatch.setattr(drawing, "add_attached_note", lambda *_a, **_kw: object())
    monkeypatch.setattr(drawing, "add_edge_dimension", lambda *_a, **_kw: (
        SimpleNamespace(GetAnnotation=lambda: object())
    ))
    async def finalize(*_a, **_kw):
        return {"drawing": "complete"}
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    assert asyncio.run(drawing.build(adapter)) == {"drawing": "complete"}
    assert [view.orientation for view in views] == ["*Front", "*Right", "*Isometric"]
    assert hlr == views  # retain the isometric in the HLR loop
    assert hlv == [views[0], views[0]]  # reassert after the last annotation
    assert [view.mode for view in views] == [1, 2, 2]
    assert curated == [("*Front", set(drawing.FRONT_KEEP)), ("*Right", {"Depth"})]
    assert placed[0][0] is checked[0][0] is views[0]
    assert placed[0][1] is checked[0][1]
    assert checked[0][2] == {"seam", "fiducial"}
    assert checked[0][3:] == (1, 2)  # native guards follow the final HLV regen
    assert text == [(set().union(*spec.DRAWING_DIMENSIONS.values()), drawing.DIMENSION_CALLOUTS)]
    # Reject residual A-A labels/captions/cut annotations in executable source,
    # without coupling the contract to any deleted helper/constant's name.
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and "A-A" in node.value
        for node in ast.walk(tree)
    )
