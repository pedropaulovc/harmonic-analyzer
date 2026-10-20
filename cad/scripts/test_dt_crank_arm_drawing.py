"""Offline contracts for the separate-hub crank-arm drawing."""

from __future__ import annotations

import ast
import asyncio
import math
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


@pytest.fixture(autouse=True)
def forensic_calls(monkeypatch):
    """Offline guards must never capture a real seat or write failure artefacts."""
    calls = []
    def capture(adapter, label, message, **context):
        calls.append((adapter, label, message, context))
        raise context["exception"]
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    return calls


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
    kept = set(drawing.FRONT_KEEP) | set(drawing.PROFILE_KEEP)
    assert kept == marked
    assert set(drawing.PROFILE_KEEP) == {"Depth", "BoreRearChamferSize"}
    assert "BoreRearChamferSize" not in drawing.FRONT_KEEP
    assert set(drawing.DIMENSION_CALLOUTS) == {"HubSeatDia", "BoreRearChamferSize"}
    assert drawing.DIMENSION_CALLOUTS["HubSeatDia"] == notes.HUB_SEAT_CALLOUT
    assert (
        drawing.DIMENSION_CALLOUTS["BoreRearChamferSize"]
        == notes.BORE_REAR_CHAMFER_CALLOUT
    )


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


class _NativeHoleText:
    """Native SetText is void; only its independently returned text can pass."""

    def __init__(self, definition, newline, mutate=lambda text: text):
        self.definition = definition
        self.newline = newline
        self.mutate = mutate
        self.written = []

    def GetText(self, part):
        assert part == 5
        return self.definition

    def SetText(self, part, text) -> None:
        assert part == 1
        self.written.append((part, text))
        self.definition = self.mutate(text).replace("\n", self.newline)


@pytest.mark.parametrize("newline", ("\n", "\r\n", "\r"))
def test_thread_class_cleanup_accepts_native_newlines_without_changing_other_whitespace(monkeypatch, newline):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    definition = "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH>  <hw-threaddepth>\n\tKEEP  \n"
    expected = "<hw-threaddesc> <HOLE-DEPTH>  <hw-threaddepth>\n\tKEEP  \n"
    native = _NativeHoleText(definition.replace("\n", newline), newline)
    drawing._omit_title_block_thread_class(native)
    assert native.written == [(1, expected)]
    assert native.definition == expected.replace("\n", newline)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda text: text.replace("<HOLE-DEPTH>", "WRONG"),
        lambda text: text.replace("KEEP  ", "KEEP "),
        lambda text: " " + text,
        lambda text: text + " ",
        lambda text: text.replace("\n", " "),
    ),
)
def test_thread_class_cleanup_rejects_real_content_and_whitespace_changes(monkeypatch, mutate):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    native = _NativeHoleText(
        "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH>\r\nKEEP  ", "\r\n", mutate
    )
    with pytest.raises(RuntimeError, match="retained its redundant thread class"):
        drawing._omit_title_block_thread_class(native)


@pytest.mark.parametrize(
    ("definition_newline", "rows_newline", "readback_newline"),
    (("\n", "\n", "\r\n"), ("\r\n", "\r\n", "\r"), ("\r", "\r", "\n")),
)
def test_appended_native_rows_accept_all_newlines_and_preserve_other_whitespace(
    monkeypatch, definition_newline, rows_newline, readback_newline
):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    definition = "<hw-threaddesc>  <hw-threaddepth> \t\n<HOLE-DEPTH>  <hw-depth>  \t\n"
    rows = "\tFOR MHA-DT-32  \nMOUTH 3.0 MAX \t"
    native = _NativeHoleText(definition.replace("\n", definition_newline), readback_newline)
    drawing._append_callout_rows(native, rows.replace("\n", rows_newline))
    assert native.written == [(1, definition + rows)]
    assert native.definition == (definition + rows).replace("\n", readback_newline)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda text: text.replace("MOUTH", "WRONG"),
        lambda text: text.replace("KEEP  ", "KEEP "),
        lambda text: " " + text,
        lambda text: text + " ",
        lambda text: text.replace("\n", " "),
    ),
)
def test_appended_native_rows_reject_real_content_and_whitespace_changes(monkeypatch, mutate):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    native = _NativeHoleText("<hw-threaddesc>\r\nKEEP  ", "\r\n", mutate)
    with pytest.raises(RuntimeError, match="rows did not persist"):
        drawing._append_callout_rows(native, "FOR MHA-DT-32\r\nMOUTH 3.0 MAX")


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
    assert "_named(adapter, profile_annotations, name)" in source
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


def _check_arm_guard(guard, *args, **kwargs):
    """Exercise a collector at the same single failure boundary as build."""
    errors = []
    result = guard(*args, errors=errors, **kwargs)
    drawing._raise_arm_errors(None, errors)
    return result


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
        _check_arm_guard(drawing._assert_chamfer_limits, annotation)
    else:
        with pytest.raises(RuntimeError, match=message):
            _check_arm_guard(drawing._assert_chamfer_limits, annotation)


def test_bore_rear_chamfer_callout_keeps_principal_front_face_meaning() -> None:
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


def _native_chamfer(monkeypatch, **changed):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    tolerance = SimpleNamespace(
        Type=changed.get("kind", spec.BORE_REAR_CHAMFER_TOL_TYPE),
        GetMinValue=lambda: changed.get("lower", spec.BORE_REAR_CHAMFER_DEVIATIONS[0]) / 1000.0,
        GetMaxValue=lambda: changed.get("upper", spec.BORE_REAR_CHAMFER_DEVIATIONS[1]) / 1000.0,
    )
    dimension = SimpleNamespace(
        Name="BoreRearChamferSize",
        FullName=changed.get("full_name", "BoreRearChamferSize@BoreRearChamfer@dt-crank-arm.SLDPRT"),
        GetType=lambda: changed.get("dimension_type", 0),
        SystemValue=changed.get("leg", spec.BORE_REAR_CHAMFER) / 1000.0,
        Tolerance=tolerance,
    )
    display = SimpleNamespace(
        GetDimension=lambda: dimension,
        GetDimension2=lambda _: dimension,
        GetOverride=lambda: changed.get("override", False),
        ShowDimensionValue=changed.get("show_value", True),
        IsReferenceDim=lambda: changed.get("reference", False),
        GetPrimaryTolPrecision2=lambda: changed.get("precision", 2),
        GetPrimaryPrecision2=lambda: changed.get("primary_precision", 2),
        GetText=lambda _: changed.get("text", notes.BORE_REAR_CHAMFER_CALLOUT),
        OffsetText=changed.get("offset", True),
    )
    stock_dimension = SimpleNamespace(
        Name="Depth",
        FullName="Depth@Arm@dt-crank-arm.SLDPRT",
        GetType=lambda: changed.get("stock_type", 0),
        SystemValue=changed.get("stock_mm", spec.ARM_THICKNESS) / 1000.0,
    )
    stock_runs = changed.get("stock_runs", (changed.get("stock_text", " (8.0) "),))
    stock_data = SimpleNamespace(
        GetTextCount=lambda: len(stock_runs),
        GetTextAtIndex=lambda index: stock_runs[index],
    )
    stock_display = SimpleNamespace(
        GetDimension2=lambda _: stock_dimension,
        GetOverride=lambda: changed.get("stock_override", False),
        ShowDimensionValue=changed.get("stock_show_value", True),
        IsReferenceDim=lambda: changed.get("stock_reference", False),
        GetText=lambda part: changed.get("stock_prefix", "(") if part == 1 else changed.get("stock_suffix", ")") if part == 2 else pytest.fail("reference definition is not displayed text"),
        GetDisplayData=lambda: stock_data,
        GetPrimaryPrecision2=lambda: changed.get("stock_precision", 1),
    )
    def parameter(name):
        if name == "Depth@Arm":
            return changed.get("stock_source", stock_dimension)
        assert name == "BoreRearChamferSize@BoreRearChamfer"
        return changed.get("source_dimension", dimension)
    profile = SimpleNamespace(
        ReferencedDocument=SimpleNamespace(Parameter=parameter),
        GetOrientationName=lambda: changed.get("orientation", "*Top"),
        Angle=changed.get("angle", drawing.PROFILE_ANGLE),
        ScaleRatio=changed.get("scale", drawing.PROFILE_SCALE),
        mode=changed.get("mode", 2),
        GetDisplayMode2=lambda: profile.mode,
        GetOutline=lambda: changed.get("profile_box", (0.2936, 0.0894, 0.3064, 0.1946)),
    )
    stock = SimpleNamespace(
        name="stock thickness",
        GetSpecificAnnotation=lambda: stock_display,
        GetType=lambda: 4,
        Visible=changed.get("stock_visible", 1),
        OwnerType=0,
        Owner=profile,
        IsDangling=lambda: False,
    )
    profile.stock = stock
    annotation = SimpleNamespace(
        GetSpecificAnnotation=lambda: display,
        GetType=lambda: changed.get("annotation_type", 4),
        Visible=changed.get("visible", 1),
        OwnerType=changed.get("owner_type", 0),
        Owner=changed.get("owner", profile),
        IsDangling=lambda: changed.get("dangling", False),
        position=changed.get("position", (*drawing.PROFILE_KEEP["BoreRearChamferSize"], 0.0)),
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
    return adapter, profile, annotation, display


def _project_profile(_adapter, view, points, **_kwargs):
    """Independent Top basis: +X right and +Z down before its native turn."""
    cosine, sine = math.cos(view.Angle), math.sin(view.Angle)
    placement = getattr(view, "projection_placement", drawing.PROFILE_CENTER)
    scale = getattr(view, "projection_scale", 1.0)
    result = []
    for x, _y, z in points:
        dx, dy = x - spec.ARM_C2C / 2000.0, -(z - spec.ARM_THICKNESS / 2000.0)
        result.append((
            placement[0] + scale * (cosine * dx - sine * dy),
            placement[1] + scale * (sine * dx + cosine * dy),
        ))
    return result


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
        {"primary_precision": 1},
        {"text": "FAR SIDE"},
    ),
)
def test_profile_chamfer_rejects_lost_native_ownership_or_display(monkeypatch, changed) -> None:
    adapter, profile, annotation, _display = _native_chamfer(monkeypatch, **changed)
    with pytest.raises(RuntimeError):
        _check_arm_guard(drawing._assert_profile_chamfer, adapter, profile, annotation)


@pytest.mark.parametrize(
    ("source_newline", "readback_newline"),
    (("\n", "\r\n"), ("\r\n", "\r"), ("\r", "\n")),
)
def test_profile_chamfer_suffix_accepts_only_native_newline_variation(
    monkeypatch, source_newline, readback_newline
):
    monkeypatch.setattr(
        drawing, "BORE_REAR_CHAMFER_CALLOUT",
        notes.BORE_REAR_CHAMFER_CALLOUT.replace("\n", source_newline),
    )
    adapter, profile, annotation, _display = _native_chamfer(
        monkeypatch, text=notes.BORE_REAR_CHAMFER_CALLOUT.replace("\n", readback_newline)
    )
    _check_arm_guard(drawing._assert_profile_chamfer, adapter, profile, annotation)


@pytest.mark.parametrize(
    "text",
    (
        notes.BORE_REAR_CHAMFER_CALLOUT.replace("PRESS", "WRONG").replace("\n", "\r\n"),
        notes.BORE_REAR_CHAMFER_CALLOUT.replace("FAR SIDE", "FAR  SIDE").replace("\n", "\r\n"),
        " " + notes.BORE_REAR_CHAMFER_CALLOUT.replace("\n", "\r\n"),
        notes.BORE_REAR_CHAMFER_CALLOUT.replace("\n", "\r\n") + " ",
        "\r\n" + notes.BORE_REAR_CHAMFER_CALLOUT.replace("\n", "\r\n"),
    ),
)
def test_profile_chamfer_suffix_does_not_strip_real_content_mismatches(monkeypatch, text):
    adapter, profile, annotation, _display = _native_chamfer(monkeypatch, text=text)
    with pytest.raises(RuntimeError, match="callout"):
        _check_arm_guard(drawing._assert_profile_chamfer, adapter, profile, annotation)


@pytest.mark.parametrize(
    "changed",
    (
        {}, {"orientation": "*Right"}, {"orientation": "*Front"},
        {"angle": -math.pi / 2}, {"angle": 0.0},
        {"scale": (2.0, 1.0)}, {"mode": 1},
    ),
)
def test_profile_requires_labelled_native_xz_projection_and_scale(monkeypatch, changed) -> None:
    adapter, profile, _annotation, _display = _native_chamfer(monkeypatch, **changed)
    monkeypatch.setattr(drawing, "model_points_in_view", _project_profile)
    if changed:
        with pytest.raises(RuntimeError, match="projection"):
            _check_arm_guard(drawing._profile_geometry, adapter, profile)
    else:
        # Rear z=0 is the LEFT stock face; the bore's -X mouth is near the
        # profile's lower end. A relabelled Right projection cannot pass.
        assert _check_arm_guard(drawing._profile_geometry, adapter, profile) == pytest.approx((0.296, 0.09455))


@pytest.mark.parametrize("index", (0, 1, 2, 3, 4, 5, 6))
def test_profile_rejects_wrong_actual_projected_axes_stock_or_mouth(monkeypatch, index) -> None:
    adapter, profile, _annotation, _display = _native_chamfer(monkeypatch)
    def project(*args, **kwargs):
        result = _project_profile(*args, **kwargs)
        x, y = result[index]
        result[index] = (x + 0.002, y)
        return result
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    # No requested anchor substitutes for actual stock/rear-mouth projection.
    with pytest.raises(RuntimeError, match="rear-Z mouth"):
        _check_arm_guard(drawing._profile_geometry, adapter, profile)


def test_profile_turn_is_native_ccw_and_refuses_an_ignored_angle(monkeypatch) -> None:
    adapter, profile, _annotation, _display = _native_chamfer(monkeypatch, angle=0.0, mode=1)
    rebuilt = []
    monkeypatch.setattr(drawing, "model_points_in_view", _project_profile)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **kw: rebuilt.append(kw["label"]))
    _check_arm_guard(drawing._turn_profile, adapter, profile)
    assert profile.Angle == pytest.approx(math.pi / 2)
    assert rebuilt == ["turn crank arm Top profile 90 DEG CCW"]
    with pytest.raises(RuntimeError, match="already rotated"):
        _check_arm_guard(drawing._turn_profile, adapter, profile)
    class IgnoredAngle:
        GetOrientationName = staticmethod(profile.GetOrientationName)
        ScaleRatio = profile.ScaleRatio
        GetDisplayMode2 = staticmethod(profile.GetDisplayMode2)
        @property
        def Angle(self):
            return 0.0
        @Angle.setter
        def Angle(self, _value):
            pass
    with pytest.raises(RuntimeError, match="projection"):
        _check_arm_guard(drawing._turn_profile, adapter, IgnoredAngle())


def test_profile_chamfer_offsets_actual_native_leg_without_replacing_it(monkeypatch) -> None:
    adapter, profile, annotation, display = _native_chamfer(monkeypatch)
    monkeypatch.setattr(drawing, "model_points_in_view", _project_profile)
    positions = []
    def offset(adapter_arg, annotations, targets):
        assert adapter_arg is adapter and annotations == [annotation]
        assert display.OffsetText is False
        assert annotation.position[:2] == pytest.approx((0.296, 0.09455))
        positions.append(targets)
        display.OffsetText = True
        annotation.SetPosition2(*targets["BoreRearChamferSize"], 0.0)
    monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    _check_arm_guard(drawing._place_profile_chamfer, adapter, profile, [annotation])
    _check_arm_guard(drawing._assert_profile_chamfer, adapter, profile, annotation)
    assert positions == [{"BoreRearChamferSize": drawing.PROFILE_KEEP["BoreRearChamferSize"]}]
    assert display.GetDimension2(0).SystemValue == spec.BORE_REAR_CHAMFER / 1000.0
    for candidates in ([], [annotation, annotation]):
        with pytest.raises(RuntimeError, match="expected one"):
            _check_arm_guard(drawing._place_profile_chamfer, adapter, profile, candidates)


@pytest.mark.parametrize("refusal", ("offset", "position", "native_line"))
def test_profile_chamfer_refuses_ignored_native_text_placement(monkeypatch, refusal) -> None:
    adapter, profile, annotation, display = _native_chamfer(monkeypatch)
    monkeypatch.setattr(drawing, "model_points_in_view", _project_profile)
    def offset(_adapter, _annotations, targets):
        display.OffsetText = refusal != "offset"
        if refusal != "position":
            annotation.SetPosition2(*targets["BoreRearChamferSize"], 0.0)
    monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    if refusal == "native_line":
        annotation.SetPosition2 = lambda *_args: False
    with pytest.raises(RuntimeError, match="offset leader|dimension line"):
        _check_arm_guard(drawing._place_profile_chamfer, adapter, profile, [annotation])


# Native source signatures and logged point samples from run
# 20261020T112243344Z-8b17a8fe19fd40658a14301a7e2888db (artifact://6715).
# The log retains first-three/last-two samples, NOT the entire 633-double
# packet. Replay those exact samples in a polyline envelope; never invent
# the omitted circle tessellation or its twelve arc-geometry values.
_NATIVE_OUTER = (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.009950000038999998)
_NATIVE_INNER = (0.0, 0.0, 0.0002500000080000002, -0.0, -0.0, -1.0, 0.009700000031)
_NATIVE_STYLE = (0.0, 0.0, -1.0, 1.0, -1.0, 0.0)
_NATIVE_SAMPLES = {
    "stock": (
        (-0.004000000001000004, -0.04844093663488029, 0.006448713577047853),
        (-0.004000000001000004, -0.04889405986941188, 0.005609402908615206),
        (-0.004000000001000004, -0.049282914427867724, 0.0047384521659291825),
        (-0.004000000001000004, -0.05019971082211258, 8.571162396932753e-05),
        (-0.004000000001000004, -0.050200000057, 1.421085471875472e-17),
    ),
    "stock_split": (
        (-0.004000000001000004, -0.037500000057, 0.012700000000000013),
        (-0.004000000001000004, -0.03845874708314772, 0.012663759478916726),
        (-0.004000000001000004, -0.039412022378301007, 0.01255524474643354),
        (-0.004000000001000004, -0.045486402523133615, 0.009874582302504504),
        (-0.004000000001000037, -0.046209063549119724, 0.00924349571808348),
    ),
    "inner": (
        (-0.003749999993000004, -0.04624394172740298, -0.004199224293365415),
        (-0.003749999993000004, -0.0463231325169851, -0.004030177935892764),
        (-0.003749999993000004, -0.04663569760951304, -0.003260219445130464),
        (-0.003749999993000004, -0.04716440560282695, -0.0008302204810705247),
        (-0.003749999993000004, -0.047200000088, 1.7680301670708336e-17),
    ),
    "bevel": (
        (-0.004000000001000002, -0.047450000096, 1.7294807553970557e-17),
        (-0.003749999993000004, -0.047200000088, 1.7680301670708336e-17),
    ),
    "outer": (
        (-0.004000000001000002, -0.047450000096, 1.7294807553970557e-17),
        (-0.004000000001000002, -0.04741409711655973, -0.000844500011680925),
        (-0.004000000001000002, -0.04730664727852588, -0.0016829055376457172),
        (-0.004000000001000002, -0.046565315314656276, -0.004101531428064908),
        (-0.004000000001000004, -0.04621071604262393, -0.004808942481865998),
    ),
}


def _polyline_record(points, style=_NATIVE_STYLE):
    return (0.0, 0.0, *style, float(len(points)), *(value for point in points for value in point))


def _packet(profile, edges, records):
    profile.packet = (tuple(edges), tuple(value for record in records for value in record))


def _native_breakout(monkeypatch, adapter, profile, changed):
    """Model the documented methods without opening a COM document."""
    doc = adapter.currentModel
    doc.breakout_count = changed.get("breakout_count", 1)
    doc.initial_breakout_count = changed.get("initial_breakout_count", 0)
    doc.created = []
    doc.splines = []
    doc.accessed = []
    doc.released = []
    doc.selections = []
    def clear(all_marks):
        assert all_marks is True
        doc.selections.clear()
    doc.ClearSelection2 = clear
    doc.SelectionManager = SimpleNamespace(
        GetSelectedObjectCount2=lambda mark: len(doc.selections) if mark == -1 else pytest.fail("selection mark"),
        GetSelectedObjectType3=lambda index, mark: doc.selections[index - 1] if mark == -1 else pytest.fail("selection mark"),
    )
    def access(draw, component):
        assert draw is doc and component is None and doc.selections == []
        doc.accessed.append(True)
        return changed.get("access_selections", True)
    def release():
        doc.released.append(True)
        if changed.get("release_error"):
            raise OSError("definition release failed")
    data = SimpleNamespace(
        AccessSelections=access, ReleaseSelectionAccess=release,
        Depth=changed.get("breakout_depth", spec.HALF_WIDTH / 1000.0),
        DepthReference=changed.get("depth_reference"),
    )
    feature = SimpleNamespace(GetDefinition=lambda: data)
    profile.GetBreakOutSectionCount = lambda: doc.breakout_count
    profile.GetBreakOutSections = lambda: changed.get("breakout_features", (feature,) if doc.breakout_count else ())
    def create(depth):
        assert doc.selections
        doc.created.append(depth)
        if changed.get("create_error"):
            raise OSError("native breakout creation unavailable")
        result = changed.get("create_breakout", True)
        if result is True:
            doc.breakout_count = changed.get("after_breakout_count", 1)
        return result
    doc.CreateBreakOutSection = create
    def select(append, data_arg):
        assert append is True and data_arg is None
        if changed.get("spline_select", True):
            doc.selections.append(10)
        return changed.get("spline_select", True)
    manager = SimpleNamespace(AddToDB=changed.get("add_to_db", False))
    def spline(points):
        assert manager.AddToDB is True
        doc.splines.append(tuple(points))
        return changed.get("spline", SimpleNamespace(Select4=select))
    manager.CreateSpline = spline
    doc.SketchManager = manager
    transform = object()
    profile.GetSketch = lambda: SimpleNamespace(ModelToSketchTransform=transform)
    doc.math_inputs = []
    def create_point(values):
        doc.math_inputs.append(tuple(values))
        def multiply(actual):
            assert actual is transform
            return SimpleNamespace(ArrayData=changed.get("sketch_xyz", (values[0] - 0.1, values[1] - 0.2, values[2])))
        return SimpleNamespace(MultiplyTransform=multiply)
    adapter.swApp.GetMathUtility = lambda: SimpleNamespace(CreatePoint=create_point)
    monkeypatch.setattr(drawing, "double_array", tuple)
    def activate(adapter_arg, view, *, label):
        assert adapter_arg is adapter and view is profile and label == "crank arm local breakout"
        doc.selections[:] = changed.get("selection_types", (12,))
        return "Drawing View2"
    monkeypatch.setattr(drawing, "_activate_and_select_view", activate)


def _chamfer_edge_case(monkeypatch, **changed):
    adapter, profile, annotation, _display = _native_chamfer(monkeypatch, **changed)
    monkeypatch.setattr(drawing, "model_points_in_view", _project_profile)
    def circle(params):
        curve = SimpleNamespace(IsCircle=lambda: True, CircleParams=params)
        return SimpleNamespace(GetCurve=lambda: curve)
    outer = circle(changed.get("source_outer", _NATIVE_OUTER))
    inner = circle(changed.get("source_inner", _NATIVE_INNER))
    near = circle((0.0, 0.0, 0.008, 0.0, 0.0, 1.0, 0.0097))
    face = SimpleNamespace(GetEdges=lambda: changed.get("feature_edges", (outer, inner)))
    feature = SimpleNamespace(GetFaces=lambda: (face,))
    profile.ReferencedDocument.FeatureByName = lambda name: (
        changed.get("feature", feature) if name == "BoreRearChamfer" else None
    )
    attached = changed.get("attached", (face,) if changed.get("face_attachment") else (outer,))
    annotation.GetAttachedEntities3 = lambda: attached
    annotation.GetAttachedEntityCount3 = lambda: changed.get("attached_count", len(attached))
    annotation.GetAttachedEntityTypes = lambda: changed.get(
        "attached_types", (2,) if changed.get("face_attachment") else (1,)
    )
    view_outer = circle(changed.get("rendered_outer", _NATIVE_OUTER))
    view_inner = circle(changed.get("rendered_inner", _NATIVE_INNER))
    view_near = SimpleNamespace(GetCurve=near.GetCurve)
    stock_params = changed.get("stock_circle", (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0127))
    view_stock = circle(stock_params)
    view_stock_split = circle(changed.get("stock_split_circle", stock_params))
    view_bevel = SimpleNamespace(GetCurve=lambda: SimpleNamespace(IsCircle=lambda: False))
    names = ("stock", "stock_split", "inner", "bevel", "outer")
    rendered = (view_stock, view_stock_split, view_inner, view_bevel, view_outer)
    for name, edge in zip(names, rendered):
        points = changed.get(f"{name}_points", _NATIVE_SAMPLES[name])
        if points and (changed.get("degenerate") or changed.get(f"{name}_degenerate")):
            points = (points[0], points[0])
        edge.raw_points = points
    profile.record_edges = rendered
    profile.record_data = tuple(_polyline_record(edge.raw_points, changed.get(f"{name}_style", _NATIVE_STYLE))
                                for name, edge in zip(names, rendered))
    _packet(profile, rendered, profile.record_data)
    if "raw" in changed:
        profile.packet = (rendered, changed["raw"])
    if "result" in changed:
        profile.packet = changed["result"]
    profile.GetPolylines7 = lambda option: profile.packet if option == 1 else pytest.fail("crosshatch option")
    # The actual breakout maps neither source circle. Mapping is telemetry.
    mapped = changed.get("mapping", (None, None))
    profile.GetCorrespondingEntity = lambda source: mapped[0] if source is outer else mapped[1] if source is inner else None
    profile.source_edges = (outer, inner)
    profile.view_edges = (view_outer, view_inner)
    profile.stock_contour = view_stock
    profile.stock_split = view_stock_split
    profile.bevel = view_bevel
    profile.projection_placement = changed.get("placement", drawing.PROFILE_CENTER)
    profile.projection_scale = changed.get("projection_scale", 1.0)
    profile.GetXform = lambda: changed.get("xform", (*profile.projection_placement, profile.projection_scale))
    # Optional typed-line absence is tested separately from the observed
    # packet; no GetDisplayData4 return was captured in that native run.
    profile.line_data = SimpleNamespace(GetLineCount=lambda: 0)
    profile.GetDisplayData4 = lambda: profile.line_data
    adapter.currentModel = SimpleNamespace(
        GetLineFontInfo=lambda _index: pytest.fail("legacy font must not be decoded"),
        GetLineFontInfo2=lambda _index: pytest.fail("font must use the actual visible outline"),
    )
    _native_breakout(monkeypatch, adapter, profile, changed)
    return adapter, profile, annotation, view_outer, view_inner, view_near


def _typed_lines(profile, *, frame="view-local", styles=None):
    """Synthetic documented channel, independently calibrated on stock ink."""
    styles = styles or {}
    lines = []
    for name, edge in zip(("stock", "stock_split", "inner", "bevel", "outer"), profile.record_edges):
        endpoints = (edge.raw_points[0], edge.raw_points[-1])
        if frame == "sheet":
            tx, ty, scale = profile.GetXform()
            endpoints = tuple((tx + scale * x, ty + scale * y, z) for x, y, z in endpoints)
        lines.append((0.0, 0.0, float(styles.get(name, 0)), 1.0, *endpoints[0], *endpoints[1]))
    profile.line_data = SimpleNamespace(GetLineCount=lambda: len(lines), GetLineAtIndex3=lambda index: lines[index])
    return lines


@pytest.mark.parametrize("face_attachment", (False, True))
def test_actual_native_chamfer_samples_and_complete_record13_pass_without_mapping(monkeypatch, face_attachment):
    adapter, profile, annotation, _outer, _inner, _near = _chamfer_edge_case(monkeypatch, face_attachment=face_attachment)
    assert tuple(profile.GetCorrespondingEntity(edge) for edge in profile.source_edges) == (None, None)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)
    assert math.dist(*_NATIVE_SAMPLES["bevel"]) == pytest.approx(0.00035355340190697883)
    mouths = tuple((0.300 + x, 0.142 + y) for x, y, _z in _NATIVE_SAMPLES["bevel"])
    assert mouths[0] == pytest.approx((0.295999999999, 0.094549999904))
    assert mouths[1] == pytest.approx((0.296250000007, 0.094799999912))
    assert any("GetXform raw=" in entry for entry in logged)
    assert any("positive control:" in entry and "measured=True" in entry for entry in logged)
    assert any("flags=(True, True), bevel=True" in entry for entry in logged)


def test_source_matching_is_independent_of_native_record_indices_and_order(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    _packet(profile, reversed(profile.record_edges), reversed(profile.record_data))
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("placement", ((0.413, -0.025), (0.175, 0.205)))
@pytest.mark.parametrize("scale", (1.0, 2.0))
def test_native_getxform_not_layout_constants_places_view_local_ink(monkeypatch, placement, scale):
    adapter, profile, annotation, *_ = _chamfer_edge_case(
        monkeypatch, placement=placement, projection_scale=scale,
    )
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("xform", (
    None, (), (0.3, 0.142), (0.3, 0.142, 1.0, 0.0),
    (0.3, 0.142, 0.0), (0.3, 0.142, -1.0),
    (float("nan"), 0.142, 1.0), (0.3, 0.142, float("inf")),
    lambda: (0.3, 0.142, 1.0), (0.3, 0.142, lambda: 1.0),
))
def test_native_getxform_requires_measured_finite_exact_shape_and_positive_scale(monkeypatch, xform):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, xform=xform)
    with pytest.raises(RuntimeError, match="GetXform"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


def test_getxform_access_failure_cannot_reuse_layout_placement(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    def unreadable():
        raise OSError("native placement unmeasured")
    profile.GetXform = unreadable
    with pytest.raises(RuntimeError, match="native placement unmeasured"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("projection", (None, (), ((float("nan"), 0.0),), ((0.296,),)))
def test_native_projection_cannot_be_missing_or_malformed(monkeypatch, projection):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    monkeypatch.setattr(drawing, "model_points_in_view", lambda *_a, **_kw: projection)
    with pytest.raises(RuntimeError, match="projection"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


def test_native_projection_controls_reject_a_fitting_chamfer_in_the_wrong_basis(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    def wrong_axes(adapter, view, points, **kwargs):
        result = _project_profile(adapter, view, points, **kwargs)
        if kwargs["label"] == "view-local native projection controls":
            return tuple((x + 0.000002, y) for x, y in result)
        return result
    monkeypatch.setattr(drawing, "model_points_in_view", wrong_axes)
    with pytest.raises(RuntimeError, match="actual native projection controls"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("boundary", ("inner", "outer"))
@pytest.mark.parametrize("fault", ("missing", "duplicate", "wrong_signature", "wrong_ink", "degenerate"))
def test_both_rendered_circles_need_unique_exact_source_params_and_actual_mouth_ink(monkeypatch, boundary, fault):
    adapter, profile, annotation, outer, inner, near = _chamfer_edge_case(monkeypatch)
    target = inner if boundary == "inner" else outer
    edges, records = list(profile.record_edges), list(profile.record_data)
    index = next(index for index, edge in enumerate(edges) if edge is target)
    if fault == "missing":
        edges.pop(index)
        records.pop(index)
    elif fault == "duplicate":
        edges.append(SimpleNamespace(GetCurve=target.GetCurve))
        records.append(records[index])
    elif fault == "wrong_signature":
        # Even a <nominal feature tolerance difference is not the ACTUAL
        # source CircleParams identity. Opposite-mouth circles also fail.
        params = list(target.GetCurve().CircleParams)
        params[6] += 1e-10
        edges[index] = SimpleNamespace(GetCurve=lambda: SimpleNamespace(IsCircle=lambda: True, CircleParams=tuple(params)))
    elif fault == "wrong_ink":
        records[index] = _polyline_record(tuple((x + 0.000002, y, z) for x, y, z in target.raw_points))
    else:
        records[index] = _polyline_record((target.raw_points[0], target.raw_points[0]))
    _packet(profile, edges, records)
    with pytest.raises(RuntimeError, match=f"boundary {0 if boundary == 'outer' else 1}"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("boundary", (0, 1))
@pytest.mark.parametrize("fault", ("missing", "duplicate", "wrong"))
def test_actual_feature_source_circles_must_remain_unique_and_measured(monkeypatch, boundary, fault):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    sources = list(profile.source_edges)
    target = sources[boundary]
    if fault == "missing":
        sources.pop(boundary)
    elif fault == "duplicate":
        sources.append(SimpleNamespace(GetCurve=target.GetCurve))
    else:
        params = list(target.GetCurve().CircleParams)
        params[2] += 0.0001
        sources[boundary] = SimpleNamespace(GetCurve=lambda: SimpleNamespace(IsCircle=lambda: True, CircleParams=tuple(params)))
    face = SimpleNamespace(GetEdges=lambda: sources)
    profile.ReferencedDocument.FeatureByName = lambda _name: SimpleNamespace(GetFaces=lambda: (face,))
    with pytest.raises(RuntimeError, match="cannot identify both actual rear bore-chamfer boundary"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("mapping", ((None, None), (object(), object())))
def test_mapping_is_telemetry_only_but_never_replaces_actual_geometry(monkeypatch, mapping):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, mapping=mapping)
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)
    _packet(profile, profile.record_edges[:-1], profile.record_data[:-1])
    with pytest.raises(RuntimeError, match="actual outer"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


def test_mapping_exceptions_are_diagnostic_not_a_postbreakout_gate(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    def unmapped(_source):
        raise OSError("derived edge has no corresponding entity")
    profile.GetCorrespondingEntity = unmapped
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("endpoint", (0, 1))
def test_bevel_requires_each_actual_mouth_endpoint_within_one_micron(monkeypatch, endpoint):
    points = list(_NATIVE_SAMPLES["bevel"])
    x, y, z = points[endpoint]
    points[endpoint] = (x + 0.0000011, y, z)
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, bevel_points=tuple(points))
    with pytest.raises(RuntimeError, match="chamfer section stroke"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("points", (
    (), (_NATIVE_SAMPLES["bevel"][0],) * 2,
    ((-0.00995, 0.0, 0.0), (-0.0097, 0.0, 0.00025)),  # wrong MODEL frame
    ((_NATIVE_SAMPLES["bevel"][0]),
     (-0.0038, -0.046, 0.0), (_NATIVE_SAMPLES["bevel"][1])),
))
def test_bevel_needs_nonzero_whole_view_local_record_not_just_fitting_ends(monkeypatch, points):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, bevel_points=points)
    with pytest.raises(RuntimeError, match="chamfer section stroke"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("split", (False, True))
def test_bevel_records_cannot_be_duplicated_or_joined_to_fabricate_coverage(monkeypatch, split):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    first, last = _NATIVE_SAMPLES["bevel"]
    middle = tuple((a + b) / 2 for a, b in zip(first, last))
    pair = ((_polyline_record((first, middle)), _polyline_record((middle, last))) if split
            else (_polyline_record((first, last)),) * 2)
    _packet(profile, (*profile.record_edges[:3], profile.bevel, profile.bevel, profile.record_edges[-1]),
            (*profile.record_data[:3], *pair, profile.record_data[-1]))
    with pytest.raises(RuntimeError, match="unique solid actual chamfer section stroke"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("name", ("stock", "stock_split", "inner", "outer", "bevel"))
def test_native_descriptors_must_agree_with_the_proven_stock_outline(monkeypatch, name):
    changed = {f"{name}_style": (0.0, 8.0, -1.0, 1.0, -1.0, 0.0)}
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, **changed)
    with pytest.raises(RuntimeError, match="font|descriptor"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("changed", (
    {"stock_points": ()}, {"stock_points": ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0))},
    {"stock_circle": _NATIVE_OUTER}, {"stock_split_circle": (0.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0127)},
    {"stock_style": (0.0, -2.0, -1.0, 1.0, -1.0, 0.0)},
    {"inner_style": (0.0, 0.5, -1.0, 1.0, -1.0, 0.0)},
))
def test_missing_ambiguous_or_unreadable_outline_control_fails_closed(monkeypatch, changed):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, **changed)
    with pytest.raises(RuntimeError, match="stock|font|descriptor"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("frame", ("sheet", "view-local"))
def test_typed_style_uses_independent_stock_endpoint_calibration(monkeypatch, frame):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, placement=(0.421, 0.213))
    _typed_lines(profile, frame=frame)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)
    expected_frame = "sheet" if frame == "sheet" else "view-local/GetXform"
    assert any(f"chosen_frame='{expected_frame}'" in entry for entry in logged)
    assert any("GetLineAtIndex3 native_raw_return=" in entry for entry in logged)


@pytest.mark.parametrize("name", ("stock", "stock_split", "inner", "outer", "bevel"))
@pytest.mark.parametrize("style", (1, 7, -1, 0.5))
def test_legacy_style_zero_never_implies_typed_continuous_zero(monkeypatch, name, style):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    _typed_lines(profile, styles={name: style})
    with pytest.raises(RuntimeError, match="documented typed style is not continuous"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("descriptor", (
    (0.0, 23.0, -1.0, 1.0, -1.0, 0.0),
    (0.0, -1.0, 7.0, 1.0, -1.0, 0.0),
))
def test_matching_legacy_descriptor_ids_are_not_typed_style_enum_values(monkeypatch, descriptor):
    adapter, profile, annotation, *_ = _chamfer_edge_case(
        monkeypatch, **{f"{name}_style": descriptor for name in _NATIVE_SAMPLES},
    )
    _typed_lines(profile)
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("fault", ("duplicate", "missing", "malformed", "none", "wrong_frame", "stock_unmeasured", "mixed_frames"))
def test_available_typed_line_channel_never_becomes_empty_success(monkeypatch, fault):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    lines = _typed_lines(profile)
    if fault == "duplicate":
        lines.append(lines[3])
    elif fault == "missing":
        lines.pop(3)
    elif fault == "malformed":
        lines[3] = (0.0, 0.0, 0.0)
    elif fault == "none":
        lines[3] = None
    elif fault == "wrong_frame":
        lines[:] = [(0.0, 0.0, 0.0, 1.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0)]
    elif fault == "stock_unmeasured":
        lines[:] = lines[2:]  # fitting chamfer alone cannot calibrate the frame
    else:
        line = lines[3]
        lines[3] = (*line[:4], line[4] + 0.3, line[5] + 0.142, line[6],
                    line[7] + 0.3, line[8] + 0.142, line[9])
    with pytest.raises(RuntimeError, match="typed|GetLineAtIndex3"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("member", ("GetDisplayData4", "GetLineCount", "GetLineAtIndex3"))
def test_typed_access_failure_is_not_documented_optional_absence(monkeypatch, member):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    _typed_lines(profile)
    def unreadable(*_args):
        raise OSError("typed channel unmeasured")
    setattr(profile if member == "GetDisplayData4" else profile.line_data, member, unreadable)
    with pytest.raises(RuntimeError, match="typed channel unmeasured"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("count", (None, -1, 1.5, lambda: 0))
def test_typed_native_count_must_be_measured_not_coerced_to_empty(monkeypatch, count):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    profile.line_data.GetLineCount = lambda: count
    with pytest.raises(RuntimeError, match="typed line channel|GetLineCount"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


def test_absent_display_object_is_unmeasured_not_optional_zero_lines(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    profile.line_data = None
    with pytest.raises(RuntimeError, match="GetDisplayData4|GetLineCount"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


def test_typed_coordinate_channel_ambiguity_on_stock_is_a_refusal(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    lines = _typed_lines(profile)
    sheet_lines = [(*line[:4], line[4] + 0.3, line[5] + 0.142, line[6],
                    line[7] + 0.3, line[8] + 0.142, line[9]) for line in lines]
    lines.extend(sheet_lines)
    with pytest.raises(RuntimeError, match="coordinate channel is unmeasured or ambiguous"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


def test_typed_raw_payload_is_logged_before_correspondence_refusal(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    lines = _typed_lines(profile)
    lines[3] = (0.0, 0.0, float("nan"))
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    with pytest.raises(RuntimeError, match="malformed native data"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)
    raw_index = next(index for index, entry in enumerate(logged) if "line 3 GetLineAtIndex3 native_raw_return=" in entry)
    refusal_index = next(index for index, entry in enumerate(logged) if "line 3 has malformed native data" in entry)
    assert raw_index < refusal_index


def test_irrelevant_native_write_only_circle_stays_diagnostic(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    class WriteOnlyCircle:
        def IsCircle(self):
            return True
        @property
        def CircleParams(self):
            raise OSError("Unable to read write-only property.")
    irrelevant = SimpleNamespace(GetCurve=lambda: WriteOnlyCircle())
    _packet(profile, (irrelevant, *profile.record_edges),
            (_polyline_record(((0.02, 0.0, 0.0), (0.021, 0.0, 0.0))), *profile.record_data))
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize(
    "changed",
    (
        {"attached": (), "attached_types": (), "attached_count": 0},
        {"attached": (None,), "attached_types": (0,), "attached_count": 1},
        {"attached": (object(),), "attached_types": (23,), "attached_count": 1},
        {"attached": (object(),), "attached_types": (), "attached_count": 2},
    ),
)
def test_chamfer_attachment_inventory_is_logged_not_used_as_an_extra_gate(monkeypatch, changed):
    adapter, profile, annotation, _outer, _inner, _near = _chamfer_edge_case(monkeypatch, **changed)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    _check_arm_guard(drawing._assert_profile_chamfer, adapter, profile, annotation)
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)
    assert any(
        f"profile chamfer native attachments: count={changed['attached_count']}, "
        f"types={changed['attached_types']}, entities={len(changed['attached'])}" == entry
        for entry in logged
    )


@pytest.mark.parametrize(
    "unsupported_members",
    (
        ("GetAttachedEntities3",),
        ("GetAttachedEntityTypes",),
        ("GetAttachedEntityCount3",),
        ("GetAttachedEntities3", "GetAttachedEntityTypes", "GetAttachedEntityCount3"),
    ),
)
def test_chamfer_unsupported_attachment_inventory_is_diagnostic_not_gating(monkeypatch, unsupported_members):
    adapter, profile, annotation, _outer, _inner, _near = _chamfer_edge_case(monkeypatch)
    def unsupported():
        raise NotImplementedError("imported dimension attachment inventory unsupported")
    for member in unsupported_members:
        setattr(annotation, member, unsupported)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    _check_arm_guard(drawing._assert_profile_chamfer, adapter, profile, annotation)
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)
    for member in unsupported_members:
        assert any(
            member in entry and "UNMEASURED NotImplementedError" in entry
            and "attachment inventory unsupported" in entry
            for entry in logged
        )
    assert any("profile chamfer native attachments:" in entry for entry in logged)


def test_chamfer_rendered_edge_parser_keeps_arc_and_silhouette_alignment(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    # Synthetic arc envelope tests only parser alignment; its geometry fields
    # are not represented as observations from the native sample packet.
    stock, *remaining = profile.record_data
    arc = (1.0, 12.0, *(0.0 for _ in range(12)), *stock[2:])
    line = _polyline_record(((0.02, 0.0, 0.0), (0.021, 0.0, 0.0)))
    _packet(profile, (None, *profile.record_edges), (line, arc, *remaining))
    _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("corrupt", ("truncated", "fractional", "negative", "trailing", "unsupported"))
def test_chamfer_rendered_edge_parser_refuses_bad_record_boundaries(monkeypatch, corrupt):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    edges, raw = profile.GetPolylines7(1)
    raw = list(raw)
    if corrupt == "truncated":
        raw.pop()
    elif corrupt == "fractional":
        raw[8] = 1.5
    elif corrupt == "negative":
        raw[8] = -1.0
    elif corrupt == "unsupported":
        raw[0] = 3.0
    else:
        raw.append(0.0)
    profile.packet = (edges, tuple(raw))
    with pytest.raises(RuntimeError, match="buffer|render"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("changed", (
    {"feature": None}, {"feature_edges": ()}, {"degenerate": True},
    {"inner_degenerate": True}, {"raw": ()}, {"raw": (float("nan"),)},
    {"raw": (3.0, 0.0)}, {"result": None}, {"result": ((),)}, {"result": ((), ())},
))
def test_chamfer_edge_guard_rejects_missing_wrong_or_unrendered_receivers(monkeypatch, changed):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, **changed)
    with pytest.raises(RuntimeError):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


def test_opposite_mouth_circle_never_proves_the_actual_source_inner(monkeypatch):
    adapter, profile, annotation, _outer, _inner, near = _chamfer_edge_case(monkeypatch)
    edges = list(profile.record_edges)
    edges[2] = near
    _packet(profile, edges, profile.record_data)
    with pytest.raises(RuntimeError, match="actual inner"):
        _check_arm_guard(drawing._rendered_chamfer_edges, adapter, profile, annotation)


def _native_dimension_text(monkeypatch, **changed):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    data = SimpleNamespace(
        GetTextCount=lambda: changed.get("count", 1),
        GetTextAtIndex=lambda _: changed.get("text", "NATIVE 25.4"),
        GetTextPositionAtIndex=lambda _: changed.get("position", (0.279, 0.135, 0.0)),
        GetTextInBoxWidthAtIndex=lambda _: changed.get("width", 0.012),
        GetTextHeightAtIndex=lambda _: changed.get("height", 0.005),
        GetTextAngleAtIndex=lambda _: changed.get("angle", math.pi / 2),
        GetTextRefPositionAtIndex=lambda _: changed.get("reference", 1),
    )
    return SimpleNamespace(GetSpecificAnnotation=lambda: SimpleNamespace(GetDisplayData=lambda: data))


@pytest.mark.parametrize(
    ("reference", "local_box"),
    (
        (0, (0.0, -0.005, 0.012, 0.0)),       # swUPPER_LEFT
        (1, (0.0, 0.0, 0.012, 0.005)),        # swLOWER_LEFT
        (2, (-0.006, -0.0025, 0.006, 0.0025)),  # swCENTER
        (3, (-0.012, -0.005, 0.0, 0.0)),      # swUPPER_RIGHT
        (4, (-0.012, 0.0, 0.0, 0.005)),       # swLOWER_RIGHT
        (5, (-0.006, -0.005, 0.006, 0.0)),    # swUPPER_CENTER
    ),
)
@pytest.mark.parametrize("angle", (0.0, math.pi / 2, -math.pi / 2, math.pi / 4))
def test_dimension_clearance_honours_native_reference_and_rotation(monkeypatch, reference, local_box, angle):
    annotation = _native_dimension_text(monkeypatch, reference=reference, angle=angle)
    x0, y0, x1, y1 = local_box
    cosine, sine = math.cos(angle), math.sin(angle)
    corners = [
        (0.279 + x * cosine - y * sine, 0.135 + x * sine + y * cosine)
        for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))
    ]
    expected = (
        min(x for x, _y in corners), min(y for _x, y in corners),
        max(x for x, _y in corners), max(y for _x, y in corners),
    )
    # This string's default estimated width is NOT 12 mm. Only the positive
    # measured width can produce this box around the correct native corner.
    assert _check_arm_guard(drawing._dimension_text_bounds, annotation, label="Width") == pytest.approx(expected)


@pytest.mark.parametrize(
    "changed",
    (
        {"width": 0.0}, {"width": -0.001}, {"width": float("nan")}, {"width": float("inf")},
        {"height": 0.0}, {"height": -0.001}, {"height": float("nan")}, {"height": float("inf")},
        {"angle": float("nan")}, {"angle": float("inf")},
        {"position": (0.27, 0.14)}, {"position": (0.27, float("nan"), 0.0)},
        {"reference": -1}, {"reference": 6}, {"reference": None},
        {"reference": 1.5}, {"reference": True}, {"count": 0}, {"text": " \t"},
    ),
)
def test_dimension_clearance_refuses_unmeasurable_or_undocumented_native_runs(monkeypatch, changed):
    annotation = _native_dimension_text(monkeypatch, **changed)
    with pytest.raises(RuntimeError, match="whole bounds|no rendered text"):
        _check_arm_guard(drawing._dimension_text_bounds, annotation, label="Width")


def test_chamfer_lane_preserves_border_air_stock_and_named_rotation() -> None:
    left, bottom, right, top = drawing.CHAMFER_TEXT_LANE
    tx, ty = drawing.PROFILE_KEEP["BoreRearChamferSize"]
    # Native final5 block size, translated to the approved anchor. Its ink
    # overlaps EndRadius vertically, so clearance must be proved horizontally.
    width = 0.0219382
    half_height = 0.0184163
    assert left <= tx - width / 2 < tx + width / 2 <= right
    assert bottom <= ty - half_height < ty + half_height <= top
    assert tx - width / 2 >= 0.250988 + 0.002  # measured actual Front outline
    assert tx + width / 2 <= 0.277
    assert ty + half_height <= 0.1166 - 0.002  # actual Width witness
    assert tx - width / 2 >= 0.2492358 + 0.002  # translated native EndRadius right
    assert bottom >= 0.0127 + 0.003  # inner border + 3 mm
    assert drawing.PROFILE_KEEP == {"BoreRearChamferSize": (0.2645, 0.095), "Depth": (0.300, 0.210)}
    assert drawing.FRONT_KEEP["EndRadius"] == (0.242, 0.087)
    assert drawing.PIVOT_CALLOUT_XY == (0.270, 0.225)
    assert drawing.FRONT_KEEP["BossRadius"] == (0.030, drawing.FRONT_CENTER[1])
    assert drawing.FRONT_CENTER == (0.145, 0.142)
    assert drawing.PROFILE_CENTER == (0.300, 0.142)
    assert drawing.PROFILE_SCALE == (1.0, 1.0)
    assert drawing.PROFILE_ANGLE == math.pi / 2
    assert notes.PROFILE_VIEW_CAPTION.splitlines() == [
        "TOP VIEW", "ROTATED 90 DEG CCW", "SCALE 1:1"
    ]
    assert drawing.ISO_CENTER == (0.360, 0.230)


def _final_profile_case(monkeypatch, *, native_guards=False, **changed):
    if native_guards:
        adapter, profile, annotation, _outer, _inner, near = _chamfer_edge_case(monkeypatch, **changed)
        if changed.get("edge_hidden"):
            edges = list(profile.record_edges)
            edges[2] = near
            _packet(profile, edges, profile.record_data)
    else:
        adapter, profile, annotation, _display = _native_chamfer(monkeypatch, **changed)
    profile.initial_angle = changed.get("initial_angle", 0.0)
    front = SimpleNamespace(GetOutline=lambda: changed.get("front_box", (0.0422, 0.1142, 0.250988, 0.1698)))
    width = SimpleNamespace(name="Width")
    end = SimpleNamespace(name="EndRadius")
    callouts = {name: SimpleNamespace(name=name) for name in ("overall length", "handle pivot", "anchor tap")}
    segments = {
        "Width": [
            ((0.279, 0.1166), (0.279, 0.1674)),
            ((0.221, 0.1166), (0.280, 0.1166)),
        ],
        "EndRadius": [((0.240, 0.142), (0.242, 0.087))],
        "stock thickness": [
            ((0.296, 0.20622), (0.304, 0.20622)),
            ((0.296, 0.1785), (0.296, 0.20622)),
            ((0.304, 0.1785), (0.304, 0.20622)),
        ],
        "overall length": [((0.0446, 0.073), (0.2454, 0.073))],
        "handle pivot": [((0.220, 0.170), (0.234832, 0.225))],
        "anchor tap": [((0.110, 0.155), (0.195, 0.200))],
    }
    boxes = {
        "Width": (0.274, 0.135, 0.279, 0.147),
        "EndRadius": (0.235, 0.08422, 0.2492358, 0.08772),
        "stock thickness": (0.293, 0.207, 0.307, 0.213),
        "overall length": (0.130, 0.070, 0.160, 0.076),
        "handle pivot": (0.234832, 0.213834, 0.305168, 0.234110),
        "anchor tap": (0.180, 0.200, 0.230, 0.215),
    }
    if "cross" in changed:
        segments[changed["cross"]] = [((0.260, 0.105), (0.290, 0.080))]
    if "text_overlap" in changed:
        boxes[changed["text_overlap"]] = (0.255, 0.100, 0.265, 0.110)
    route = changed.get("route", [((0.296, 0.09455), (0.276, 0.09455))])
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, item: (
        "BoreRearChamferSize" if item is annotation else "Depth" if item is profile.stock else item.name
    ))
    monkeypatch.setattr(drawing, "dimension_segments", lambda item: route if item is annotation else segments[item.name])
    if native_guards:
        for item in (width, end, profile.stock, *callouts.values()):
            x0, y0, x1, y1 = boxes[item.name]
            runs = [(item.name, (x0, y0, 0.0), x1 - x0, y1 - y0, 1, 0.0)]
            if item is profile.stock:
                texts = changed.get("stock_runs", (changed.get("stock_text", " (8.0) "),))
                runs = [(text, (x0, y0, 0.0), x1 - x0, y1 - y0, 1, 0.0) for text in texts]
            if item is width and changed.get("zero_width"):
                runs = [
                    ("WIDTH FIRST", (x0, y0, 0.0), 0.0, y1 - y0, 1, 0.0),
                    ("WIDTH SECOND", (x0, y0, 0.0), 0.0, y1 - y0, 1, 0.0),
                ]
            data = SimpleNamespace(
                GetTextCount=lambda runs=runs: len(runs),
                GetTextAtIndex=lambda index, runs=runs: runs[index][0],
                GetTextPositionAtIndex=lambda index, runs=runs: runs[index][1],
                GetTextInBoxWidthAtIndex=lambda index, runs=runs: runs[index][2],
                GetTextHeightAtIndex=lambda index, runs=runs: runs[index][3],
                GetTextRefPositionAtIndex=lambda index, runs=runs: runs[index][4],
                GetTextAngleAtIndex=lambda index, runs=runs: runs[index][5],
            )
            if item is profile.stock:
                item.GetSpecificAnnotation().GetDisplayData = lambda data=data: data
            else:
                display = SimpleNamespace(GetDisplayData=lambda data=data: data)
                item.GetSpecificAnnotation = lambda display=display: display
    else:
        monkeypatch.setattr(drawing, "_dimension_text_bounds", lambda item, **_kw: boxes[item.name])
    monkeypatch.setattr(drawing, "model_points_in_view", _project_profile)
    def edges(*_args, errors):
        if changed.get("edge_hidden"):
            errors.append("profile does not render the actual inner rear bore-chamfer edge")
    if not native_guards:
        monkeypatch.setattr(drawing, "_rendered_chamfer_edges", edges)
    monkeypatch.setattr(drawing, "callout_ink", lambda *_a, **_kw: SimpleNamespace(
        text=changed.get("box", (0.2535309, 0.0765837, 0.2754691, 0.1134163))
    ))
    monkeypatch.setattr(drawing, "sheet_region", lambda _a: SimpleNamespace(
        xmin=changed.get("region_left", 0.0127), ymin=0.0127, xmax=0.4191, ymax=0.2667
    ))
    caption_annotation = SimpleNamespace(
        GetPosition=lambda: changed.get("caption_position", (*drawing.PROFILE_CAPTION_XY, 0.0)),
        Visible=1, OwnerType=0, Owner=changed.get("caption_owner", profile),
    )
    caption = SimpleNamespace(
        GetText=lambda: changed.get("caption_text", notes.PROFILE_VIEW_CAPTION),
        GetAnnotation=lambda: caption_annotation,
        GetExtent=lambda: changed.get("caption_extent", (0.316, 0.146, 0.0, 0.365, 0.160, 0.0)),
    )
    return adapter, front, profile, [width, end], [annotation, profile.stock], callouts, caption


@pytest.mark.parametrize(
    ("changed", "message"),
    (
        ({}, None),
        ({"caption_text": notes.PROFILE_VIEW_CAPTION.replace("\n", "\r\n")}, None),
        ({"caption_text": notes.PROFILE_VIEW_CAPTION.replace("\n", "\r")}, None),
        ({"offset": False}, "final offset leader"),
        ({"position": (0.296, 0.09455, 0.0)}, "final offset leader"),
        ({"box": (0.2497, 0.078, 0.275, 0.113)}, "clear profile lane"),
        ({"box": (0.254, 0.078, 0.2771, 0.113)}, "clear profile lane"),
        ({"box": (0.254, 0.0739, 0.275, 0.113)}, "clear profile lane"),
        ({"box": (0.254, 0.078, 0.275, 0.1147)}, "clear profile lane"),
        ({"box": (0.254, 0.078, float("nan"), 0.113)}, "clear profile lane"),
        ({"front_box": (0.04, 0.11, 0.252, 0.17)}, "clear profile lane"),
        ({"profile_box": (0.276, 0.09, 0.306, 0.194)}, "clear profile lane"),
        # Measured ink starts at 253.5309 mm: bracket the existing 3-mm air.
        ({"region_left": 0.2505}, None),
        ({"region_left": 0.2506}, "clear profile lane"),
        ({"route": []}, "rear-Z mouth"),
        ({"route": [((0.304, 0.09455), (0.276, 0.09455))]}, "rear-Z mouth"),
        ({"route": [((0.296, 0.115), (0.276, 0.09455))]}, "rear-Z mouth"),
        ({"edge_hidden": True}, "actual inner rear bore-chamfer edge"),
        ({"stock_reference": False}, None),
        ({"stock_reference": True}, None),
        ({"stock_prefix": ""}, "native 8 mm reference"),
        ({"stock_prefix": "(("}, "native 8 mm reference"),
        ({"stock_suffix": ""}, "native 8 mm reference"),
        ({"stock_suffix": "))"}, "native 8 mm reference"),
        ({"stock_text": "8.0"}, "native 8 mm reference"),
        ({"stock_text": "(7.2)"}, "native 8 mm reference"),
        ({"stock_text": "(8.00)"}, "native 8 mm reference"),
        ({"stock_text": "( 8.0)"}, "native 8 mm reference"),
        ({"stock_text": "8.0 (8.0)"}, "native 8 mm reference"),
        ({"stock_runs": ()}, "native 8 mm reference"),
        ({"stock_override": True}, "native displayed value"),
        ({"stock_show_value": False}, "native displayed value"),
        ({"stock_visible": 3}, "visible and attached"),
        ({"stock_mm": 7.2}, "native 8 mm reference"),
        ({"stock_type": 1}, "native 8 mm reference"),
        ({"stock_precision": 2}, "native 8 mm reference"),
        ({"stock_source": object()}, "source model dimension"),
        ({"cross": "Width"}, "existing callouts"),
        ({"cross": "EndRadius"}, "existing callouts"),
        ({"cross": "stock thickness"}, "existing callouts"),
        ({"cross": "overall length"}, "existing callouts"),
        ({"cross": "handle pivot"}, "existing callouts"),
        ({"text_overlap": "Width"}, "existing callouts"),
        ({"text_overlap": "handle pivot"}, "existing callouts"),
        ({"caption_text": "TOP VIEW SCALE 1:1"}, "caption did not persist"),
        ({"caption_text": notes.PROFILE_VIEW_CAPTION.replace("CCW", "CW").replace("\n", "\r\n")}, "caption did not persist"),
        ({"caption_text": " " + notes.PROFILE_VIEW_CAPTION.replace("\n", "\r\n")}, "caption did not persist"),
        ({"caption_text": notes.PROFILE_VIEW_CAPTION.replace("\n", "\r\n") + " "}, "caption did not persist"),
        ({"caption_owner": object()}, "caption did not persist"),
        ({"caption_position": (0.316, 0.170, 0.0)}, "caption did not persist"),
        ({"caption_extent": (0.295, 0.146, 0.0, 0.350, 0.160, 0.0)}, "existing callouts"),
    ),
)
def test_profile_chamfer_checks_final_native_ink_placement_and_persistence(monkeypatch, changed, message) -> None:
    args = _final_profile_case(monkeypatch, **changed)
    if message is None:
        _check_arm_guard(drawing._profile_chamfer_clear, *args)
    else:
        with pytest.raises(RuntimeError, match=message):
            _check_arm_guard(drawing._profile_chamfer_clear, *args)


@pytest.mark.parametrize("reference", (False, True))
@pytest.mark.parametrize("text", ("(8.0)", " (8.0) ", "\t(8.0)\r\n"))
def test_stock_reference_checks_actual_native_display_without_model_reference_classification(
    monkeypatch, reference, text,
):
    args = _final_profile_case(monkeypatch, native_guards=True, stock_reference=reference, stock_text=text)
    stock_display = args[4][1].GetSpecificAnnotation()
    def unsupported():
        raise AssertionError("imported stock model reference classification must not be used")
    stock_display.IsReferenceDim = unsupported
    _check_arm_guard(drawing._profile_chamfer_clear, *args)


@pytest.mark.parametrize(
    ("distance", "passes"),
    ((0.0, True), (5e-9, True), (1.1e-8, False), (0.0001, False)),
)
def test_chamfer_mouth_landing_requires_numerical_zero_not_one_mm(monkeypatch, distance, passes):
    route = [((0.296 + distance, 0.09455), (0.276, 0.09455))]
    args = _final_profile_case(monkeypatch, route=route)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    if passes:
        _check_arm_guard(drawing._profile_chamfer_clear, *args)
    else:
        with pytest.raises(RuntimeError, match="does not land on the rear-Z mouth"):
            _check_arm_guard(drawing._profile_chamfer_clear, *args)
    assert any("numerical-zero landing distance (abs_tol=1e-8 m)" in entry for entry in logged)


def _mock_arm_build(monkeypatch, *, guard_error=False, native_case=None):
    views, curated, hlr, hlv, text, turned = [], [], [], [], [], []
    adapter = native_case[0] if native_case is not None else SimpleNamespace()
    if native_case is None:
        adapter.currentModel = object()
    native_turn = drawing._turn_profile
    native_place = drawing._place_profile_chamfer
    native_guard = drawing._profile_chamfer_clear
    native_breakout = drawing._create_profile_breakout
    if native_case is not None:
        native_case[2].Angle = native_case[2].initial_angle
        adapter.currentModel.breakout_count = adapter.currentModel.initial_breakout_count
    async def open_model(_path):
        return None
    adapter.open_model = open_model
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(drawing, "SOURCE", SimpleNamespace(is_file=lambda: True))
    monkeypatch.setattr(drawing, "check", lambda *_a: None)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *_a, **_kw: None)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_a, **_kw: (object(), object()))
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *_a: None)
    def place(_adapter, _source, orientation, *xy, scale):
        view = (
            native_case[1] if native_case is not None and orientation == "*Front"
            else native_case[2] if native_case is not None and orientation == "*Top"
            else SimpleNamespace()
        )
        view.orientation, view.xy, view.mode, view.scale = orientation, xy, None, scale
        views.append(view)
        return view
    def curate(_adapter, view, *, keep, dimensions_by_feature, **_kw):
        assert dimensions_by_feature is spec.DRAWING_DIMENSIONS
        assert view.mode == (1 if view.orientation == "*Top" else 2)
        if view.orientation == "*Top":
            assert hlv == [view] and turned == [view]
        curated.append((view.orientation, set(keep)))
        if native_case is not None:
            return native_case[3] if view.orientation == "*Front" else native_case[4]
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
    def turn(_adapter, view, *, errors):
        turned.append(view)
        if native_case is not None:
            native_turn(_adapter, view, errors=errors)
    monkeypatch.setattr(drawing, "_turn_profile", turn)
    def breakout(_adapter, view, *, errors):
        if native_case is not None:
            native_breakout(_adapter, view, errors=errors)
        else:
            hidden_removed(_adapter, view)
    monkeypatch.setattr(drawing, "_create_profile_breakout", breakout)
    if native_case is None:
        monkeypatch.setattr(drawing, "_assert_profile_breakout", lambda *_a, **_kw: None)
    if native_case is None:
        monkeypatch.setattr(drawing, "dimension_name", lambda _a, annotation: annotation.name)
    monkeypatch.setattr(drawing, "set_dimension_callouts", lambda _a, annotations, rows: (
        text.append((set(drawing.dimension_name(_a, item) for item in annotations), rows))
    ))
    for name in (
        "assert_imported_precision", "set_reference_dimension", "_hub_seat_leader_clear",
        "_texts_off_the_part", "_omit_title_block_thread_class", "_append_callout_rows",
        "set_arc_endpoints_to_max", "_set_reference_precision", "add_property_linked_note",
        "rebuild_drawing",
    ):
        monkeypatch.setattr(drawing, name, lambda *_a, **_kw: None)
    placed, checked, finalized = [], [], []
    def place_chamfer(_adapter, view, annotations, *, errors):
        placed.append((view, annotations))
        if native_case is not None:
            native_place(_adapter, view, annotations, errors=errors)
    monkeypatch.setattr(drawing, "_place_profile_chamfer", place_chamfer)
    if native_case is not None:
        def offset(_adapter, annotations, targets):
            for annotation in annotations:
                annotation.GetSpecificAnnotation().OffsetText = True
                annotation.SetPosition2(*targets["BoreRearChamferSize"], 0.0)
        monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    caption = native_case[6] if native_case is not None else object()
    monkeypatch.setattr(drawing, "_profile_caption", lambda _a, view, **_kw: caption)
    def guard(_a, front, profile, front_annotations, profile_annotations, callouts, actual_caption, *, errors):
        checked.append((front, profile, front_annotations, profile_annotations, set(callouts), actual_caption))
        assert profile.mode == 2 and hlv == [profile]
        if guard_error:
            errors.append("missing native chamfer edge")
        if native_case is not None:
            native_guard(_a, front, profile, front_annotations, profile_annotations, callouts, actual_caption, errors=errors)
    monkeypatch.setattr(drawing, "_profile_chamfer_clear", guard)
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *_a, **_kw: True)
    def hole_callout(*_a, label, **_kw):
        annotation = native_case[5]["anchor tap" if label == "anchor tap" else "handle pivot"] if native_case is not None else object()
        return SimpleNamespace(GetAnnotation=lambda: annotation)
    monkeypatch.setattr(drawing, "add_native_hole_callout", hole_callout)
    monkeypatch.setattr(drawing, "add_attached_note", lambda *_a, **_kw: object())
    monkeypatch.setattr(drawing, "add_edge_dimension", lambda *_a, **_kw: SimpleNamespace(
        GetAnnotation=lambda: native_case[5]["overall length"] if native_case is not None else object(),
    ))
    async def finalize(*_a, **_kw):
        finalized.append(True)
        return {"drawing": "complete"}
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    return SimpleNamespace(
        adapter=adapter, views=views, curated=curated, hlr=hlr, hlv=hlv, text=text,
        turned=turned, placed=placed, checked=checked, finalized=finalized, caption=caption,
    )


@pytest.mark.parametrize("guard_error", (False, True))
def test_build_uses_one_replacement_profile_and_native_guards_before_finalization(monkeypatch, guard_error) -> None:
    case = _mock_arm_build(monkeypatch, guard_error=guard_error)
    adapter, finalized = case.adapter, case.finalized
    views, curated, hlr, hlv = case.views, case.curated, case.hlr, case.hlv
    placed, checked, text, caption = case.placed, case.checked, case.text, case.caption
    if guard_error:
        with pytest.raises(RuntimeError, match="missing native chamfer edge"):
            asyncio.run(drawing.build(adapter))
        assert finalized == []
    else:
        assert asyncio.run(drawing.build(adapter)) == {"drawing": "complete"}
        assert finalized == [True]
    assert [view.orientation for view in views] == ["*Front", "*Top", "*Isometric"]
    assert [view.scale for view in views] == [(2, 1), (1.0, 1.0), (1, 1)]
    assert hlr == [*views, views[1], views[1]]
    assert hlv == [views[1]]  # import only; breakout exposes final solid HLR ink
    assert [view.mode for view in views] == [2, 2, 2]
    assert curated == [("*Front", set(drawing.FRONT_KEEP)), ("*Top", {"Depth", "BoreRearChamferSize"})]
    assert placed[0][0] is checked[0][1] is views[1]
    assert placed[0][1] is checked[0][3]
    assert checked[0][4] == {"overall length", "handle pivot", "anchor tap"}
    assert checked[0][5] is caption
    assert text == [(set().union(*spec.DRAWING_DIMENSIONS.values()), drawing.DIMENSION_CALLOUTS)]
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and "A-A" in node.value
        for node in ast.walk(tree)
    )


def test_build_collects_native_identity_limits_rendering_all_bad_runs_and_caption_together(monkeypatch):
    native = _final_profile_case(
        monkeypatch, native_guards=True,
        full_name="WrongSize@OtherFeature@dt-crank-arm.SLDPRT", dimension_type=1,
        source_dimension=object(), leg=0.10, kind=6, lower=-0.05, upper=0.10,
        edge_hidden=True, zero_width=True,
        caption_text=notes.PROFILE_VIEW_CAPTION.replace("CCW", "CW").replace("\n", "\r\n"),
    )
    case = _mock_arm_build(monkeypatch, native_case=native)
    def rejected_precision(*_args):
        raise RuntimeError("imported chamfer precision readback mismatch")
    monkeypatch.setattr(drawing, "assert_imported_precision", rejected_precision)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(drawing.build(case.adapter))
    report = str(caught.value)
    for violation in (
        "UNMEASURED imported model precision: RuntimeError: imported chamfer precision readback mismatch",
        "wrong model identity/type (identity)", "wrong model identity/type (type)",
        "source model dimension", "changed its model leg",
        "LIMIT band (type)", "LIMIT band (lower)", "LIMIT band (upper)",
        "actual inner rear bore-chamfer edge",
        "Width: native dimension text has no measurable whole bounds (run=0)",
        "Width: native dimension text has no measurable whole bounds (run=1)",
        "caption did not persist with its view (raw/normalized text)",
    ):
        assert violation in report
    assert case.finalized == []
    # Both bad runs and every later independent dimension/caption are measured,
    # not merely a list of exceptions from coarse, first-failure helpers.
    for measured in (
        "WIDTH FIRST", "WIDTH SECOND", "EndRadius run 0", "stock thickness run 0",
        "overall length run 0", "handle pivot run 0", "anchor tap run 0",
        "profile chamfer rendered proof:", "cursor=", "rawlen=", "poly_count=",
        "caption did not persist with its view (extent)",
        "profile caption / anchor tap",
    ):
        assert any(measured in entry for entry in logged)
    assert any("\\r\\n" in entry and "raw/normalized text" in entry for entry in logged)


@pytest.mark.parametrize("newline", ("\n", "\r\n"))
@pytest.mark.parametrize("mapped", (False, True))
def test_build_complete_native_guard_positive_control_reaches_finalize_once(monkeypatch, forensic_calls, newline, mapped):
    native = _final_profile_case(
        monkeypatch, native_guards=True,
        mapping=(object(), object()) if mapped else (None, None),
        attached=(), attached_count=0, attached_types=(),
        caption_text=notes.PROFILE_VIEW_CAPTION.replace("\n", newline),
        text=notes.BORE_REAR_CHAMFER_CALLOUT.replace("\n", newline),
    )
    case = _mock_arm_build(monkeypatch, native_case=native)
    assert asyncio.run(drawing.build(case.adapter)) == {"drawing": "complete"}
    assert case.finalized == [True]
    assert forensic_calls == []
    doc = case.adapter.currentModel
    assert len(case.views) == 3 and case.views[1].mode == 2
    assert doc.created == [spec.HALF_WIDTH / 1000.0]
    assert doc.breakout_count == 1 and len(doc.splines) == 1
    assert doc.SketchManager.AddToDB is False
    assert len(doc.accessed) == len(doc.released) == 2
    xyz = doc.splines[0]
    assert len(xyz) == 15 and xyz[:3] == xyz[-3:]


@pytest.mark.parametrize(
    ("changed", "attempts", "message"),
    (
        ({"create_breakout": False}, 1, "creation failed"),
        ({"create_breakout": None}, 1, "creation failed"),
        ({"create_error": True}, 1, "creation unavailable"),
        ({"initial_breakout_count": 1}, 0, "already has a breakout"),
        ({"spline": None}, 0, "closed spline"),
        ({"spline_select": False}, 0, "spline selection failed"),
        ({"sketch_xyz": (0.0, 0.0)}, 0, "spline point"),
        ({"sketch_xyz": (0.0, 0.0, 0.0)}, 0, "nondegenerate closed profile"),
        ({"after_breakout_count": 2}, 1, "zero to one"),
        ({"breakout_features": ()}, 1, "exactly one local breakout"),
        ({"breakout_depth": 0.013}, 1, "depth does not reach the bore axis"),
        ({"depth_reference": object()}, 1, "depth is not numeric"),
        ({"access_selections": False}, 1, "definition selections unavailable"),
        ({"release_error": True}, 1, "definition release failed"),
    ),
)
def test_native_breakout_refusal_blocks_export_without_retry(monkeypatch, changed, attempts, message):
    native = _final_profile_case(monkeypatch, native_guards=True, **changed)
    case = _mock_arm_build(monkeypatch, native_case=native)
    with pytest.raises(RuntimeError, match=message):
        asyncio.run(drawing.build(case.adapter))
    doc = case.adapter.currentModel
    assert len(doc.created) == attempts
    assert len(doc.splines) <= 1 and case.finalized == []
    assert doc.SketchManager.AddToDB is False
    assert len(case.views) == 3 and case.views[1].mode == 2
    if changed.get("release_error"):
        assert len(doc.accessed) == len(doc.released) == 2


@pytest.mark.parametrize("add_to_db", (False, True))
def test_breakout_preserves_database_mode_without_an_arbitrary_selection_count_gate(monkeypatch, add_to_db):
    native = _final_profile_case(
        monkeypatch, native_guards=True, add_to_db=add_to_db,
        selection_types=(12, 10, 10),
    )
    case = _mock_arm_build(monkeypatch, native_case=native)
    assert asyncio.run(drawing.build(case.adapter)) == {"drawing": "complete"}
    assert case.adapter.currentModel.SketchManager.AddToDB is add_to_db
    assert case.adapter.currentModel.created == [spec.HALF_WIDTH / 1000.0]
    assert case.finalized == [True]


def test_breakout_and_ink_faults_collect_with_reference_text_runs_and_caption(monkeypatch):
    native = _final_profile_case(
        monkeypatch, native_guards=True, create_breakout=False,
        stock_prefix="", stock_style=(0.0, 8.0, -1.0, 1.0, -1.0, 0.0), bevel_points=(), zero_width=True,
        caption_text="WRONG\r\nCAPTION",
    )
    case = _mock_arm_build(monkeypatch, native_case=native)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(drawing.build(case.adapter))
    report = str(caught.value)
    for message in (
        "native local breakout creation failed (no retry)",
        "profile breakout count did not change from zero to one",
        "profile did not retain exactly one local breakout",
        "native outline font descriptor", "chamfer section stroke",
        "native 8 mm reference (prefix)",
        "Width: native dimension text has no measurable whole bounds (run=0)",
        "Width: native dimension text has no measurable whole bounds (run=1)",
        "caption did not persist",
    ):
        assert message in report
    assert case.adapter.currentModel.created == [spec.HALF_WIDTH / 1000.0]
    assert case.finalized == []


@pytest.mark.parametrize("newline", ("\n", "\r\n"))
def test_build_refuses_real_caption_content_mismatch_under_either_newline(monkeypatch, newline):
    native = _final_profile_case(
        monkeypatch, native_guards=True,
        caption_text=notes.PROFILE_VIEW_CAPTION.replace("CCW", "CW").replace("\n", newline),
    )
    case = _mock_arm_build(monkeypatch, native_case=native)
    with pytest.raises(RuntimeError, match="caption did not persist"):
        asyncio.run(drawing.build(case.adapter))
    assert case.finalized == []


def test_build_retains_early_turn_placement_and_reference_failures_until_final_readback(monkeypatch):
    native = _final_profile_case(monkeypatch, native_guards=True, initial_angle=drawing.PROFILE_ANGLE)
    annotation = native[4][0]
    annotation.SetPosition2 = lambda *_xyz: False
    case = _mock_arm_build(monkeypatch, native_case=native)
    def reject_reference(*_args, label, **_kwargs):
        if label == "arm stock thickness":
            raise OSError("native reference readback rejected")
    monkeypatch.setattr(drawing, "set_reference_dimension", reject_reference)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(drawing.build(case.adapter))
    report = str(caught.value)
    assert "already rotated" in report
    assert "failed to place the native bore-mouth dimension line" in report
    assert "UNMEASURED Depth stock reference placement: OSError: native reference readback rejected" in report
    assert len(case.checked) == 1
    assert case.finalized == []


def test_absent_annotations_record_unmeasured_dependencies_but_still_measure_ink_and_caption(monkeypatch):
    native = list(_final_profile_case(
        monkeypatch, native_guards=True, caption_text="WRONG\r\nCAPTION",
    ))
    native[4] = []
    case = _mock_arm_build(monkeypatch, native_case=native)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(drawing.build(case.adapter))
    report = str(caught.value)
    assert "UNMEASURED" in report and "expected one BoreRearChamferSize" in report
    assert "UNMEASURED" in report and "expected one Depth" in report
    assert "caption did not persist" in report
    assert any("Width run 0" in entry for entry in logged)
    assert any("EndRadius run 0" in entry for entry in logged)
    assert any("profile chamfer rendered proof:" in entry for entry in logged)
    assert case.finalized == []


def test_failed_native_field_and_text_run_reads_do_not_hide_later_measurements(monkeypatch):
    native = _final_profile_case(
        monkeypatch, native_guards=True, zero_width=True,
        caption_text="WRONG\r\nCAPTION",
    )
    dimension = native[4][0].GetSpecificAnnotation().GetDimension2(0)
    def unreadable_type():
        raise OSError("native type unavailable")
    dimension.GetType = unreadable_type
    width_data = native[3][0].GetSpecificAnnotation().GetDisplayData()
    def unreadable_first_width(index):
        if index == 0:
            raise OSError("native width unavailable")
        return 0.0
    width_data.GetTextInBoxWidthAtIndex = unreadable_first_width
    case = _mock_arm_build(monkeypatch, native_case=native)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(drawing.build(case.adapter))
    report = str(caught.value)
    for violation in (
        "UNMEASURED chamfer dimension type: OSError: native type unavailable",
        "UNMEASURED Width run 0 width: OSError: native width unavailable",
        "Width: native dimension text has no measurable whole bounds (run=1)",
        "caption did not persist",
    ):
        assert violation in report
    assert any("WIDTH SECOND" in entry for entry in logged)
    assert any("anchor tap run 0" in entry for entry in logged)
    assert case.finalized == []


def test_collected_guard_failure_captures_labelled_sheet_before_same_exception(monkeypatch):
    adapter = object()
    errors = ["early placement refusal", "unmeasured native ink", "later caption refusal"]
    events = []
    originals = []
    def capture(actual_adapter, label, message, **context):
        assert actual_adapter is adapter
        assert label == f"{drawing.PART_STEM}-native-guard"
        assert context["api"] == "crank arm native drawing guards"
        assert context["phase"] == "before-finalize"
        assert context["violations"] == tuple(errors)
        assert context["sheet_png"] is True
        exc = context["exception"]
        assert str(exc) == message
        assert all(error in message for error in errors)
        originals.append(exc)
        events.append("forensic sheet PNG")
        raise exc
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    with pytest.raises(RuntimeError) as caught:
        drawing._raise_arm_errors(adapter, errors)
    events.append("original exception")
    assert events == ["forensic sheet PNG", "original exception"]
    assert originals == [caught.value] and caught.value is originals[0]


@pytest.mark.parametrize("capture_outcome", ("raises_original", "raises_secondary", "returns"))
def test_forensic_secondary_failure_or_return_cannot_replace_original_guard(monkeypatch, capture_outcome):
    originals = []
    def capture(_adapter, _label, _message, **context):
        originals.append(context["exception"])
        if capture_outcome == "raises_original":
            raise context["exception"]
        if capture_outcome == "raises_secondary":
            raise OSError("PNG capture failed")
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    with pytest.raises(RuntimeError, match="original collected violation") as caught:
        drawing._raise_arm_errors(object(), ["original collected violation"])
    assert caught.value is originals[0]


def test_no_collected_errors_means_no_forensic_capture(forensic_calls):
    drawing._raise_arm_errors(object(), [])
    assert forensic_calls == []


def test_build_forensic_capture_has_all_independent_errors_and_blocks_approved_export(monkeypatch):
    native = _final_profile_case(
        monkeypatch, native_guards=True, create_breakout=False,
        source_dimension=object(), lower=-0.05, precision=1, edge_hidden=True,
        stock_prefix="", zero_width=True, caption_text="WRONG CAPTION",
    )
    case = _mock_arm_build(monkeypatch, native_case=native)
    captured = []
    def capture(adapter, label, message, **context):
        assert case.finalized == [] and len(case.checked) == 1
        assert adapter is case.adapter and label == f"{drawing.PART_STEM}-native-guard"
        assert context["sheet_png"] is True and context["phase"] == "before-finalize"
        for violation in (
            "creation failed", "source model dimension", "LIMIT band (lower)",
            "tolerance precision", "actual inner", "native 8 mm reference (prefix)",
            "run=0", "run=1", "caption did not persist",
        ):
            assert violation in message
        assert message == "crank arm native guard violations:\n- " + "\n- ".join(context["violations"])
        captured.append(context["exception"])
        raise context["exception"]
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(drawing.build(case.adapter))
    assert captured == [caught.value] and captured[0] is caught.value
    assert case.finalized == []
