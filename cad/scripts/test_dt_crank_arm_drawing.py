"""Offline contracts for the separate-hub crank-arm drawing."""

from __future__ import annotations

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
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.SECTION_KEEP)
    assert kept == marked
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


# --- Inboard bore-mouth chamfer (MHA-DT-031 seat-root clearance) ------------


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
        ({"leg": 0.1}, "model leg"),
        ({"kind": 6}, "LIMIT band"),
        ({"lower": -0.05}, "LIMIT band"),
        ({"upper": 0.1}, "LIMIT band"),
    ),
)
def test_imported_chamfer_rejects_changed_native_limits(monkeypatch, changed, message):
    values = {
        "leg": spec.BORE_REAR_CHAMFER,
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
    dimension = SimpleNamespace(SystemValue=values["leg"] / 1000.0, Tolerance=tolerance)
    display = SimpleNamespace(GetDimension2=lambda _: dimension)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    if message is None:
        drawing._assert_chamfer_limits(annotation)
    else:
        with pytest.raises(RuntimeError, match=message):
            drawing._assert_chamfer_limits(annotation)


def test_bore_rear_chamfer_callout_identifies_the_face_and_clearance() -> None:
    rows = [row.strip() for row in notes.BORE_REAR_CHAMFER_CALLOUT.splitlines()]
    assert rows == ["X 45 DEG", "INBOARD", "CLEARS HUB"]
    assert all(len(row) <= 10 for row in rows)


def test_section_a_a_stands_in_open_sheet_and_its_line_clears_the_front_view() -> None:
    row_pitch = 0.0055563  # native sol5/sol6 callout row pitch
    sx, sy = drawing.SECTION_CENTER
    k = drawing.SECTION_SCALE[0] / drawing.SECTION_SCALE[1] / 1000.0
    half_w = (spec.HALF_WIDTH - spec.HUB_SEAT_DIA / 2.0) / 2.0 * k  # cheek across
    half_h = spec.ARM_THICKNESS / 2.0 * k  # axial thickness vertical
    # Boxes from the last layout audit (asm-drawings 20261019T024444355Z).
    side_view_right = 0.3136
    iso_note_bottom = 0.1806
    title_block_top = 0.0647
    border_right = 0.4318 - 0.0127
    assert sx - half_w > side_view_right + 0.02
    assert sy + half_h < iso_note_bottom - 0.01
    tx, ty = drawing.SECTION_KEEP["BoreRearChamferSize"]
    # Native text flips right of the cheek. Measured compact rows, rather
    # than translating the old left-growing block, fit entirely in this lane.
    width = drawing.CHAMFER_CALLOUT_WIDTH
    section_outline_right = 0.380788
    assert tx - section_outline_right >= 0.0035
    assert border_right - (tx + width) >= 0.0035
    assert sy - half_h - (ty + row_pitch) > row_pitch
    # The prior native second-row baseline is 10.0819 mm below ty. One more
    # short row still clears the native caption's top by over a text height.
    block_bottom = ty - 0.0100819 - row_pitch
    _cx, cy = drawing.SECTION_CAPTION_XY
    assert block_bottom - (cy + 0.0002385) >= 0.0035
    assert cy - 2.0 * row_pitch > title_block_top
    # The full cut closes across both ends of the arm, in the model XZ plane
    # holding the chamfer's defining -X rim. A partial YZ cut imported no native
    # dimension on sol4; cropping only follows the full native import.
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert y0 == y1 == drawing.BORE_CENTER[1]
    assert x0 < drawing.ARM_SILHOUETTE[0]
    assert x1 > drawing.ARM_SILHOUETTE[2]
    (left, y0, bottom), (right, y1, top) = drawing.SECTION_CROP_MODEL_MM
    ax, ay, az = drawing.SECTION_ANCHOR_MM
    assert y0 == y1 == ay == 0.0
    assert left < -spec.HALF_WIDTH < ax < -spec.HUB_SEAT_DIA / 2.0 < right < 0.0
    assert bottom < 0.0 < az < spec.ARM_THICKNESS < top
