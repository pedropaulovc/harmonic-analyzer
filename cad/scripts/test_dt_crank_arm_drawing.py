"""Offline data/border gates; the unchanged PNG reviewer owns visible assessment."""

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
import _sprocket_seat_geometry as seat_geometry
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
    assert drawing.DIMENSION_CALLOUTS["BoreRearChamferSize"] == drawing.CHAMFER_CALLOUT_BELOW


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
        seat_geometry.BAND_FRONT_Z - drive.CRANK_HUB_REAR_Z
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
    import sh_vn_brass_fillister_screw_spec as screw

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


def _check_arm_guard(guard, *args, visual_errors=None, **kwargs):
    """Only the explicit gate collector reaches the production failure boundary."""
    gate_errors = []
    visual_errors = [] if visual_errors is None else visual_errors
    if guard in (drawing._assert_profile_chamfer, drawing._assert_profile_dimension,
                 drawing._profile_geometry, drawing._assert_profile_breakout, drawing._profile_chamfer_clear):
        kwargs["visual_errors"] = visual_errors
    result = guard(*args, errors=gate_errors, **kwargs)
    drawing._raise_arm_errors(None, gate_errors)
    return result


def _check_arm_visual(guard, *args, expect_diagnostics=False, **kwargs):
    """Visual faults, including unexpected measurement exceptions, never refuse."""
    visual_errors = []
    if guard in (drawing._assert_profile_chamfer, drawing._profile_geometry):
        kwargs["visual_errors"] = visual_errors
    result = drawing._arm_read(visual_errors, "offline visual metrology",
                               lambda: guard(*args, errors=visual_errors, **kwargs))
    if expect_diagnostics:
        assert visual_errors
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


def test_compact_chamfer_has_native_angle_and_one_functional_side() -> None:
    assert drawing.CHAMFER_SUFFIX == " X 45 DEG"
    assert drawing.CHAMFER_CALLOUT_BELOW == "FAR SIDE PRESS LEAD-IN"
    assert "\n" not in drawing.CHAMFER_CALLOUT_BELOW
    assert "HUB-SIDE" not in drawing.CHAMFER_CALLOUT_BELOW
    assert "MHA-DT-31" in drawing.DIMENSION_CALLOUTS["HubSeatDia"]
    assert "LIGHT PRESS" in drawing.DIMENSION_CALLOUTS["HubSeatDia"]
    assert all(value not in drawing.CHAMFER_CALLOUT_BELOW for value in ("0.25", "0.10", "INBOARD"))


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
    text_parts = {2: changed.get("suffix", drawing.CHAMFER_SUFFIX),
                  4: changed.get("text", drawing.CHAMFER_CALLOUT_BELOW)}
    written = []
    def set_text(part, value):
        written.append((part, value))
        if not changed.get("ignore_text"):
            text_parts[part] = value
    text_data = SimpleNamespace(
        GetTextCount=lambda: 1,
        GetTextAtIndex=lambda _index: "0.10 X 45 DEG\n0.25 X 45 DEG\nFAR SIDE PRESS LEAD-IN",
        GetTextPositionAtIndex=lambda _index: changed.get("chamfer_text_position", (0.104, 0.226, 0.0)),
        GetTextInBoxWidthAtIndex=lambda _index: changed.get("chamfer_width", 0.030),
        GetTextHeightAtIndex=lambda _index: 0.0035,
        GetTextRefPositionAtIndex=lambda _index: 1,
        GetTextAngleAtIndex=lambda _index: 0.0,
    )
    display = SimpleNamespace(
        GetDimension=lambda: dimension,
        GetDimension2=lambda _: dimension,
        GetOverride=lambda: changed.get("override", False),
        ShowDimensionValue=changed.get("show_value", True),
        IsReferenceDim=lambda: changed.get("reference", False),
        GetPrimaryTolPrecision2=lambda: changed.get("precision", 2),
        GetPrimaryPrecision2=lambda: changed.get("primary_precision", 2),
        GetText=lambda part: text_parts[part], SetText=set_text, written=written,
        GetDisplayData=lambda: text_data,
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
        Angle=changed.get("angle", 0.0),
        ScaleRatio=changed.get("scale", drawing.SHEET_SCALE),
        mode=changed.get("mode", 2),
        GetDisplayMode2=lambda: profile.mode,
        GetOutline=lambda: changed.get("profile_box", (0.0422, 0.1916, 0.2478, 0.2124)),
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
    """Independent projected-Top basis, not coupled to metadata readback."""
    placement = getattr(view, "projection_placement", drawing.PROFILE_CENTER)
    scale = getattr(view, "projection_scale", drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1])
    result = []
    for x, _y, z in points:
        result.append((
            placement[0] + scale * (x - spec.ARM_C2C / 2000.0),
            placement[1] - scale * (z - spec.ARM_THICKNESS / 2000.0),
        ))
    return result


@pytest.mark.parametrize("changed", (
    {"source_dimension": None}, {"source_dimension": object()}, {"override": True},
    {"precision": 1}, {"primary_precision": 1},
))
def test_profile_chamfer_refuses_real_source_override_or_precision_faults(monkeypatch, changed):
    adapter, profile, annotation, _display = _native_chamfer(monkeypatch, **changed)
    with pytest.raises(RuntimeError):
        _check_arm_guard(drawing._assert_profile_chamfer, adapter, profile, annotation)


@pytest.mark.parametrize("changed", (
    {"annotation_type": 6}, {"visible": 0}, {"visible": 2}, {"visible": 3},
    {"owner_type": 1}, {"owner": object()}, {"dangling": True},
    {"show_value": False}, {"reference": True}, {"text": "FAR SIDE"},
))
def test_profile_chamfer_presentation_faults_are_logged_not_gated(monkeypatch, changed):
    adapter, profile, annotation, _display = _native_chamfer(monkeypatch, **changed)
    visual_errors = []
    _check_arm_guard(drawing._assert_profile_chamfer, adapter, profile, annotation, visual_errors=visual_errors)
    assert visual_errors


def test_compact_chamfer_writes_correct_native_text_parts_without_override(monkeypatch):
    adapter, profile, annotation, display = _native_chamfer(monkeypatch)
    monkeypatch.setattr(drawing, "model_points_in_view", _project_profile)
    monkeypatch.setattr(drawing, "offset_dimension_text", lambda *_a, **_kw: None)
    _check_arm_visual(drawing._place_profile_chamfer, adapter, profile, [annotation])
    assert display.written == [(2, " X 45 DEG"), (4, "FAR SIDE PRESS LEAD-IN")]
    assert display.GetText(2) == " X 45 DEG" and display.GetText(4) == "FAR SIDE PRESS LEAD-IN"
    assert display.GetOverride() is False
    assert display.GetDimension2(0).SystemValue == spec.BORE_REAR_CHAMFER / 1000.0


@pytest.mark.parametrize(
    "text",
    (
        drawing.CHAMFER_CALLOUT_BELOW.replace("PRESS", "WRONG"),
        drawing.CHAMFER_CALLOUT_BELOW.replace("FAR SIDE", "HUB-SIDE"),
        " " + drawing.CHAMFER_CALLOUT_BELOW,
        drawing.CHAMFER_CALLOUT_BELOW + " ",
        "\r\n" + drawing.CHAMFER_CALLOUT_BELOW,
    ),
)
def test_profile_chamfer_text_mismatches_are_visible_diagnostics(monkeypatch, text):
    adapter, profile, annotation, _display = _native_chamfer(monkeypatch, text=text)
    visual_errors = []
    _check_arm_guard(drawing._assert_profile_chamfer, adapter, profile, annotation, visual_errors=visual_errors)
    assert visual_errors


@pytest.mark.parametrize(
    "changed",
    (
        {}, {"orientation": "*Right"}, {"orientation": "*Front"},
        {"angle": -math.pi / 2}, {"angle": math.pi / 2},
        {"scale": (1.0, 1.0)}, {"mode": 1},
    ),
)
def test_profile_metadata_mismatch_does_not_remove_a_measured_mouth(monkeypatch, changed):
    adapter, profile, _annotation, _display = _native_chamfer(monkeypatch, **changed)
    monkeypatch.setattr(drawing, "model_points_in_view", lambda a, _v, points, **kw: _project_profile(
        a, SimpleNamespace(), points, **kw,
    ))
    visual_errors = []
    mouth = _check_arm_guard(drawing._profile_geometry, adapter, profile, visual_errors=visual_errors)
    assert mouth == pytest.approx((0.0501, 0.210))
    assert bool(visual_errors) is bool(changed)


def test_derived_top_empty_native_orientation_name_keeps_measured_projection(monkeypatch):
    adapter, profile, _annotation, _display = _native_chamfer(monkeypatch, orientation="")
    monkeypatch.setattr(drawing, "model_points_in_view", _project_profile)
    visual_errors = []
    assert _check_arm_guard(drawing._profile_geometry, adapter, profile, visual_errors=visual_errors) == pytest.approx((0.0501, 0.210))
    assert visual_errors == []


@pytest.mark.parametrize("index", (0, 1, 2, 3, 4, 5, 6))
def test_profile_control_mismatch_returns_actual_native_mouth(monkeypatch, index) -> None:
    adapter, profile, _annotation, _display = _native_chamfer(monkeypatch)
    def project(*args, **kwargs):
        result = _project_profile(*args, **kwargs)
        x, y = result[index]
        result[index] = (x + 0.002, y)
        return result
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    visual_errors = []
    mouth = _check_arm_guard(drawing._profile_geometry, adapter, profile, visual_errors=visual_errors)
    assert mouth == pytest.approx((0.0521 if index == 6 else 0.0501, 0.210))
    assert visual_errors


def test_unreadable_projection_controls_do_not_hide_a_valid_native_mouth(monkeypatch):
    adapter, profile, _annotation, _display = _native_chamfer(monkeypatch)
    def project(*args, **kwargs):
        result = _project_profile(*args, **kwargs)
        result[0] = None
        return result
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    visual_errors = []
    mouth = _check_arm_guard(drawing._profile_geometry, adapter, profile, visual_errors=visual_errors)
    assert mouth == pytest.approx((0.0501, 0.210))
    assert visual_errors


@pytest.mark.parametrize("fault", (None, "missing_child", "scale_read", "scale_assignment", "ignored_inheritance", "parent_read", "wrong_parent"))
def test_projected_top_selects_front_creates_one_aligned_inherited_child(monkeypatch, forensic_calls, fault):
    events = []
    parent = SimpleNamespace(ScaleRatio=drawing.SHEET_SCALE)
    class Derived:
        inherited = False
        def __bool__(self):
            raise AssertionError("never truth-test a COM dispatch")
        @property
        def Angle(self):
            return 0.0  # no setter: production must never rotate this child
        @property
        def UseParentScale(self):
            if fault == "scale_read":
                raise OSError("parent scale unreadable")
            return self.inherited
        @UseParentScale.setter
        def UseParentScale(self, value):
            events.append(("inherit", value))
            if fault == "scale_assignment":
                raise OSError("parent scale assignment unavailable")
            if fault != "ignored_inheritance":
                self.inherited = value
        @property
        def ScaleRatio(self):
            return parent.ScaleRatio if self.inherited else (1.0, 1.0)
        def GetBaseView(self):
            if fault == "parent_read":
                raise OSError("derived parent unreadable")
            return object() if fault == "wrong_parent" else parent
    child = Derived()
    def create(x, y, z, not_aligned):
        assert events == [("select", parent)]
        assert (x, y, z) == (0.145, 0.202, 0.0)
        assert not_aligned is False
        events.append(("create", parent, x, y, z, not_aligned))
        return None if fault == "missing_child" else child
    doc = SimpleNamespace(CreateUnfoldedViewAt3=create, ClearSelection2=lambda all_marks: events.append(("clear", all_marks)))
    adapter = SimpleNamespace(currentModel=doc, swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    def select(actual_adapter, actual_parent, *, label):
        assert actual_adapter is adapter and actual_parent is parent
        assert label == "crank arm projected Top parent"
        events.append(("select", parent))
        return "Front"
    monkeypatch.setattr(drawing, "_activate_and_select_view", select)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda actual_adapter, **kw: events.append(("rebuild", kw["label"])))
    visual_errors = []
    if fault == "missing_child":
        with pytest.raises(RuntimeError, match="failed to create the projected Top"):
            drawing._project_top(adapter, parent, visual_errors=visual_errors)
    else:
        assert drawing._project_top(adapter, parent, visual_errors=visual_errors) is child
        assert bool(visual_errors) is bool(fault)
        assert ("clear", True) in events
        assert events.index(("inherit", True)) < events.index(("rebuild", "crank arm aligned projected Top"))
    assert len([event for event in events if event[0] == "create"]) == 1
    assert forensic_calls == []


def test_profile_chamfer_offsets_actual_native_leg_without_replacing_it(monkeypatch) -> None:
    adapter, profile, annotation, display = _native_chamfer(monkeypatch)
    monkeypatch.setattr(drawing, "model_points_in_view", _project_profile)
    positions = []
    def offset(adapter_arg, annotations, targets):
        assert adapter_arg is adapter and annotations == [annotation]
        assert display.OffsetText is False
        assert annotation.position[:2] == pytest.approx((0.0501, 0.210))
        positions.append(targets)
        display.OffsetText = True
        annotation.SetPosition2(*targets["BoreRearChamferSize"], 0.0)
    monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    _check_arm_visual(drawing._place_profile_chamfer, adapter, profile, [annotation])
    _check_arm_guard(drawing._assert_profile_chamfer, adapter, profile, annotation)
    assert positions == [{"BoreRearChamferSize": drawing.PROFILE_KEEP["BoreRearChamferSize"]}]
    assert display.GetDimension2(0).SystemValue == spec.BORE_REAR_CHAMFER / 1000.0
    for candidates in ([], [annotation, annotation]):
        _check_arm_visual(drawing._place_profile_chamfer, adapter, profile, candidates, expect_diagnostics=True)


@pytest.mark.parametrize("refusal", ("offset", "position", "native_line"))
def test_ignored_native_text_placement_is_diagnostic(monkeypatch, refusal) -> None:
    adapter, profile, annotation, display = _native_chamfer(monkeypatch)
    monkeypatch.setattr(drawing, "model_points_in_view", _project_profile)
    def offset(_adapter, _annotations, targets):
        display.OffsetText = refusal != "offset"
        if refusal != "position":
            annotation.SetPosition2(*targets["BoreRearChamferSize"], 0.0)
    monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    if refusal == "native_line":
        annotation.SetPosition2 = lambda *_args: False
    _check_arm_visual(drawing._place_profile_chamfer, adapter, profile, [annotation], expect_diagnostics=True)


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
        historical = changed.get(f"{name}_points", _NATIVE_SAMPLES[name])
        # Synthetic projected-Top envelope, NOT newly measured native ink:
        # undo the historical sample's quarter-turn; GetXform applies 2:1.
        points = tuple((y, -x, z) for x, y, z in historical)
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
    profile.projection_scale = changed.get("projection_scale", drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1])
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
def test_historical_native_samples_in_synthetic_projected_envelope_keep_geometry_diagnostics(monkeypatch, face_attachment):
    adapter, profile, annotation, _outer, _inner, _near = _chamfer_edge_case(monkeypatch, face_attachment=face_attachment)
    assert tuple(profile.GetCorrespondingEntity(edge) for edge in profile.source_edges) == (None, None)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)
    assert math.dist(*_NATIVE_SAMPLES["bevel"]) == pytest.approx(0.00035355340190697883)
    mouths = tuple((0.300 + x, 0.142 + y) for x, y, _z in _NATIVE_SAMPLES["bevel"])
    assert mouths[0] == pytest.approx((0.295999999999, 0.094549999904))
    assert mouths[1] == pytest.approx((0.296250000007, 0.094799999912))
    tx, ty, scale = profile.GetXform()
    projected = tuple((tx + scale * x, ty + scale * y) for x, y, _z in profile.bevel.raw_points)
    assert projected[0] == pytest.approx((0.050099999808, 0.210000000002))
    assert projected[1] == pytest.approx((0.050599999824, 0.209499999986))
    assert any("GetXform raw=" in entry for entry in logged)
    assert any("positive control:" in entry and "measured=True" in entry for entry in logged)
    assert any("flags=(True, True), bevel=True" in entry for entry in logged)


def test_source_matching_is_independent_of_native_record_indices_and_order(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    _packet(profile, reversed(profile.record_edges), reversed(profile.record_data))
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("placement", ((0.413, -0.025), (0.175, 0.205)))
@pytest.mark.parametrize("scale", (1.0, 2.0))
def test_native_getxform_not_layout_constants_places_view_local_ink(monkeypatch, placement, scale):
    adapter, profile, annotation, *_ = _chamfer_edge_case(
        monkeypatch, placement=placement, projection_scale=scale,
    )
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("xform", (
    None, (), (0.3, 0.142), (0.3, 0.142, 1.0, 0.0),
    (0.3, 0.142, 0.0), (0.3, 0.142, -1.0),
    (float("nan"), 0.142, 1.0), (0.3, 0.142, float("inf")),
    lambda: (0.3, 0.142, 1.0), (0.3, 0.142, lambda: 1.0),
))
def test_native_getxform_requires_measured_finite_exact_shape_and_positive_scale(monkeypatch, xform):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, xform=xform)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


def test_getxform_access_failure_cannot_reuse_layout_placement(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    def unreadable():
        raise OSError("native placement unmeasured")
    profile.GetXform = unreadable
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("projection", (None, (), ((float("nan"), 0.0),), ((0.296,),)))
def test_native_projection_cannot_be_missing_or_malformed(monkeypatch, projection):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    monkeypatch.setattr(drawing, "model_points_in_view", lambda *_a, **_kw: projection)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


def test_native_projection_controls_reject_a_fitting_chamfer_in_the_wrong_basis(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    def wrong_axes(adapter, view, points, **kwargs):
        result = _project_profile(adapter, view, points, **kwargs)
        if kwargs["label"] == "view-local native projection controls":
            return tuple((x + 0.000002, y) for x, y in result)
        return result
    monkeypatch.setattr(drawing, "model_points_in_view", wrong_axes)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


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
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


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
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("mapping", ((None, None), (object(), object())))
def test_missing_geometry_is_diagnostic_regardless_of_corresponding_entity_mapping(monkeypatch, mapping):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, mapping=mapping)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)
    _packet(profile, profile.record_edges[:-1], profile.record_data[:-1])
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


def test_mapping_exceptions_are_diagnostic_not_a_postbreakout_gate(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    def unmapped(_source):
        raise OSError("derived edge has no corresponding entity")
    profile.GetCorrespondingEntity = unmapped
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("endpoint", (0, 1))
def test_bevel_requires_each_actual_mouth_endpoint_within_one_micron(monkeypatch, endpoint):
    points = list(_NATIVE_SAMPLES["bevel"])
    x, y, z = points[endpoint]
    points[endpoint] = (x + 0.0000011, y, z)
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, bevel_points=tuple(points))
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("points", (
    (), (_NATIVE_SAMPLES["bevel"][0],) * 2,
    ((-0.00995, 0.0, 0.0), (-0.0097, 0.0, 0.00025)),  # wrong MODEL frame
    ((_NATIVE_SAMPLES["bevel"][0]),
     (-0.0038, -0.046, 0.0), (_NATIVE_SAMPLES["bevel"][1])),
))
def test_bevel_needs_nonzero_whole_view_local_record_not_just_fitting_ends(monkeypatch, points):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, bevel_points=points)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("split", (False, True))
def test_bevel_records_cannot_be_duplicated_or_joined_to_fabricate_coverage(monkeypatch, split):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    first, last = _NATIVE_SAMPLES["bevel"]
    middle = tuple((a + b) / 2 for a, b in zip(first, last))
    pair = ((_polyline_record((first, middle)), _polyline_record((middle, last))) if split
            else (_polyline_record((first, last)),) * 2)
    _packet(profile, (*profile.record_edges[:3], profile.bevel, profile.bevel, profile.record_edges[-1]),
            (*profile.record_data[:3], *pair, profile.record_data[-1]))
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("name", ("stock", "stock_split", "inner", "outer", "bevel"))
def test_native_descriptors_must_agree_with_the_proven_stock_outline(monkeypatch, name):
    changed = {f"{name}_style": (0.0, 8.0, -1.0, 1.0, -1.0, 0.0)}
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, **changed)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("changed", (
    {"stock_points": ()}, {"stock_points": ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0))},
    {"stock_circle": _NATIVE_OUTER}, {"stock_split_circle": (0.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0127)},
    {"stock_style": (0.0, -2.0, -1.0, 1.0, -1.0, 0.0)},
    {"inner_style": (0.0, 0.5, -1.0, 1.0, -1.0, 0.0)},
))
def test_missing_ambiguous_or_unreadable_outline_control_is_diagnostic(monkeypatch, changed):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, **changed)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("frame", ("sheet", "view-local"))
def test_typed_style_uses_independent_stock_endpoint_calibration(monkeypatch, frame):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, placement=(0.421, 0.213))
    _typed_lines(profile, frame=frame)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)
    expected_frame = "sheet" if frame == "sheet" else "view-local/GetXform"
    assert any(f"chosen_frame='{expected_frame}'" in entry for entry in logged)
    assert any("GetLineAtIndex3 native_raw_return=" in entry for entry in logged)


@pytest.mark.parametrize("name", ("stock", "stock_split", "inner", "outer", "bevel"))
@pytest.mark.parametrize("style", (1, 7, -1, 0.5))
def test_legacy_style_zero_never_implies_typed_continuous_zero(monkeypatch, name, style):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    _typed_lines(profile, styles={name: style})
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("descriptor", (
    (0.0, 23.0, -1.0, 1.0, -1.0, 0.0),
    (0.0, -1.0, 7.0, 1.0, -1.0, 0.0),
))
def test_matching_legacy_descriptor_ids_are_not_typed_style_enum_values(monkeypatch, descriptor):
    adapter, profile, annotation, *_ = _chamfer_edge_case(
        monkeypatch, **{f"{name}_style": descriptor for name in _NATIVE_SAMPLES},
    )
    _typed_lines(profile)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)


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
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("member", ("GetDisplayData4", "GetLineCount", "GetLineAtIndex3"))
def test_typed_access_failure_is_not_documented_optional_absence(monkeypatch, member):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    _typed_lines(profile)
    def unreadable(*_args):
        raise OSError("typed channel unmeasured")
    setattr(profile if member == "GetDisplayData4" else profile.line_data, member, unreadable)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("count", (None, -1, 1.5, lambda: 0))
def test_typed_native_count_must_be_measured_not_coerced_to_empty(monkeypatch, count):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    profile.line_data.GetLineCount = lambda: count
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


def test_absent_display_object_is_unmeasured_not_optional_zero_lines(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    profile.line_data = None
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


def test_typed_coordinate_channel_ambiguity_on_stock_is_diagnostic(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    lines = _typed_lines(profile)
    tx, ty, scale = profile.GetXform()
    sheet_lines = [(*line[:4], tx + scale * line[4], ty + scale * line[5], line[6],
                    tx + scale * line[7], ty + scale * line[8], line[9]) for line in lines]
    lines.extend(sheet_lines)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


def test_typed_raw_payload_is_logged_before_correspondence_diagnostic(monkeypatch):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch)
    lines = _typed_lines(profile)
    lines[3] = (0.0, 0.0, float("nan"))
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)
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
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)


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
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)
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
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)
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
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation)


@pytest.mark.parametrize("corrupt", ("truncated", "fractional", "negative", "trailing", "unsupported"))
def test_chamfer_parser_logs_bad_record_boundaries_without_refusal(monkeypatch, corrupt):
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
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


@pytest.mark.parametrize("changed", (
    {"feature": None}, {"feature_edges": ()}, {"degenerate": True},
    {"inner_degenerate": True}, {"raw": ()}, {"raw": (float("nan"),)},
    {"raw": (3.0, 0.0)}, {"result": None}, {"result": ((),)}, {"result": ((), ())},
))
def test_chamfer_metrology_logs_missing_wrong_or_unrendered_receivers(monkeypatch, changed):
    adapter, profile, annotation, *_ = _chamfer_edge_case(monkeypatch, **changed)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


def test_opposite_mouth_circle_never_proves_the_actual_source_inner(monkeypatch):
    adapter, profile, annotation, _outer, _inner, near = _chamfer_edge_case(monkeypatch)
    edges = list(profile.record_edges)
    edges[2] = near
    _packet(profile, edges, profile.record_data)
    _check_arm_visual(drawing._rendered_chamfer_edges, adapter, profile, annotation, expect_diagnostics=True)


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


def test_projected_top_uses_main_approved_layout_without_part_note_changes() -> None:
    assert drawing.PROFILE_KEEP == {"BoreRearChamferSize": (0.119, 0.226), "Depth": (0.270, 0.202)}
    assert drawing.FRONT_KEEP["EndRadius"] == (0.275, 0.094)
    assert drawing.FRONT_KEEP["HubSeatDia"] == (0.048, 0.181)
    assert drawing.FRONT_KEEP["AnchorStation"][1] == 0.098
    assert drawing.FRONT_KEEP["PivotStation"][1] == 0.088
    assert drawing.FRONT_KEEP["AnchorOffset"][1] == pytest.approx(0.1654)
    assert drawing.ANCHOR_CALLOUT_XY == (0.330, 0.169)
    assert drawing.FIDUCIAL_CALLOUT_XY == (0.016, 0.166)
    assert drawing.PIVOT_CALLOUT_XY == (0.270, 0.181)
    assert drawing.SEAM_CALLOUT_XY == (0.104, 0.190)
    assert drawing.FRONT_KEEP["BossRadius"] == (0.030, drawing.FRONT_CENTER[1])
    assert drawing.FRONT_CENTER == (0.145, 0.132)
    assert drawing.PROFILE_CENTER == (0.145, 0.202)
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.PROFILE_VIEW_CAPTION == "TOP VIEW"
    assert drawing.PROFILE_CAPTION_XY == (0.285, 0.202)
    assert drawing.ISO_CENTER == (0.360, 0.230)


@pytest.mark.parametrize(("box", "passes"), (
    ((0.0127 + 0.003, 0.02, 0.04, 0.03), True), ((0.015699, 0.02, 0.04, 0.03), False),
    ((0.02, 0.02, 0.4191 - 0.003, 0.03), True), ((0.02, 0.02, 0.416101, 0.03), False),
    ((0.02, 0.0127 + 0.003, 0.04, 0.03), True), ((0.02, 0.02, 0.04, 0.263701), False),
    ((0.02, 0.02, 0.02, 0.03), False), (None, False),
))
def test_text_border_gate_uses_existing_three_mm_air_without_clear_lane_thresholds(box, passes):
    region = (0.0127, 0.0127, 0.4191, 0.2667)
    if passes:
        _check_arm_guard(drawing._text_within_sheet, box, region, label="native text")
    else:
        with pytest.raises(RuntimeError, match="sheet border"):
            _check_arm_guard(drawing._text_within_sheet, box, region, label="native text")


def _final_profile_case(monkeypatch, *, native_guards=False, **changed):
    if native_guards:
        adapter, profile, annotation, _outer, _inner, near = _chamfer_edge_case(monkeypatch, **changed)
        if changed.get("edge_hidden"):
            edges = list(profile.record_edges)
            edges[2] = near
            _packet(profile, edges, profile.record_data)
    else:
        adapter, profile, annotation, _display = _native_chamfer(monkeypatch, **changed)
    front = SimpleNamespace(GetOutline=lambda: changed.get("front_box", (0.0422, 0.1042, 0.250988, 0.1598)))
    front_dimensions = {name: SimpleNamespace(name=name) for name in drawing.FRONT_KEEP}
    width = front_dimensions["Width"]
    callouts = {name: SimpleNamespace(name=name) for name in ("overall length", "handle pivot", "anchor tap")}
    segments = {
        "Width": [
            ((0.279, 0.1066), (0.279, 0.1574)),
            ((0.221, 0.1066), (0.280, 0.1066)),
        ],
        "EndRadius": [((0.240, 0.132), (0.275, 0.094))],
        "stock thickness": [
            ((0.2454, 0.194), (0.270, 0.194)), ((0.2454, 0.210), (0.270, 0.210)),
            ((0.270, 0.194), (0.270, 0.210)),
        ],
        "overall length": [((0.0446, 0.073), (0.2454, 0.073))],
        "handle pivot": [((0.220, 0.160), (0.234832, 0.181))],
        "anchor tap": [((0.110, 0.145), (0.330, 0.169))],
    }
    for name, anchor in drawing.FRONT_KEEP.items():
        segments.setdefault(name, [((0.145, 0.132), anchor)])
    boxes = {
        "BoreRearChamferSize": changed.get("box", (0.104, 0.226, 0.134, 0.2365)),
        "Width": (0.274, 0.125, 0.279, 0.137),
        "EndRadius": (0.270, 0.092, 0.282, 0.0955),
        "stock thickness": (0.263, 0.197, 0.277, 0.207),
        "overall length": (0.130, 0.070, 0.160, 0.076),
        "handle pivot": (0.234832, 0.169834, 0.305168, 0.190110),
        "anchor tap": (0.315, 0.164, 0.365, 0.179),
    }
    # Synthetic positive text runs for every retained Front dimension.
    for name, (x, y) in drawing.FRONT_KEEP.items():
        boxes.setdefault(name, (x, y, x + 0.010, y + 0.0035))
    boxes.update(changed.get("text_boxes", {}))
    if "cross" in changed:
        segments[changed["cross"]] = [((0.080, 0.225), (0.100, 0.205))]
    if "text_overlap" in changed:
        boxes[changed["text_overlap"]] = (0.110, 0.230, 0.130, 0.235)
    annotation.name = "BoreRearChamferSize"
    route = changed.get("route", [((0.0501, 0.210), (0.119, 0.226))])
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, item: (
        "BoreRearChamferSize" if item is annotation else "Depth" if item is profile.stock else item.name
    ))
    monkeypatch.setattr(drawing, "dimension_segments", lambda item: route if item is annotation else segments[item.name])
    if native_guards:
        for item in (*front_dimensions.values(), profile.stock, *callouts.values()):
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
        text=changed.get("box", (0.104, 0.226, 0.134, 0.2365))
    ))
    monkeypatch.setattr(drawing, "sheet_region", lambda _a: SimpleNamespace(
        xmin=changed.get("region_left", 0.0127), ymin=0.0127, xmax=0.4191, ymax=0.2667
    ))
    caption_annotation = SimpleNamespace(
        GetPosition=lambda: changed.get("caption_position", (*drawing.PROFILE_CAPTION_XY, 0.0)),
        Visible=1, OwnerType=0, Owner=changed.get("caption_owner", profile),
    )
    caption = SimpleNamespace(
        GetText=lambda: changed.get("caption_text", drawing.PROFILE_VIEW_CAPTION),
        GetAnnotation=lambda: caption_annotation,
        GetExtent=lambda: changed.get("caption_extent", (0.285, 0.1985, 0.0, 0.310, 0.202, 0.0)),
    )
    note_extents = {
        "seam callout": (0.104, 0.174, 0.0, 0.135, 0.190, 0.0),
        "fiducial callout": (0.016, 0.159, 0.0, 0.050, 0.166, 0.0),
        **changed.get("note_extents", {}),
    }
    attached_notes = {name: SimpleNamespace(GetExtent=lambda extent=extent: extent)
                      for name, extent in note_extents.items()}
    return adapter, front, profile, list(front_dimensions.values()), [annotation, profile.stock], callouts, caption, attached_notes


@pytest.mark.parametrize("changed", (
    {"offset": False}, {"position": (0.0501, 0.210, 0.0)},
    {"edge_hidden": True}, {"stock_reference": True}, {"stock_prefix": ""}, {"stock_prefix": "(("},
    {"stock_suffix": ""}, {"stock_suffix": "))"}, {"stock_text": "8.0"}, {"stock_text": "(7.2)"},
    {"stock_text": "(8.00)"}, {"stock_text": "( 8.0)"}, {"stock_text": "8.0 (8.0)"},
    {"stock_show_value": False}, {"stock_visible": 3}, {"stock_mm": 7.2}, {"stock_type": 1},
    {"cross": "Width"}, {"cross": "EndRadius"}, {"cross": "stock thickness"},
    {"cross": "overall length"}, {"cross": "handle pivot"}, {"text_overlap": "Width"},
    {"text_overlap": "handle pivot"}, {"caption_text": "TOP VIEW SCALE 1:1"},
    {"caption_text": drawing.PROFILE_VIEW_CAPTION.replace("TOP", "SIDE").replace("\n", "\r\n")},
    {"caption_text": " " + drawing.PROFILE_VIEW_CAPTION}, {"caption_text": drawing.PROFILE_VIEW_CAPTION + " "},
    {"caption_owner": object()}, {"caption_position": (0.316, 0.170, 0.0)},
    {"caption_extent": (0.263, 0.197, 0.0, 0.310, 0.207, 0.0)},
))
def test_profile_visual_mutants_log_but_do_not_refuse(monkeypatch, changed):
    args = _final_profile_case(monkeypatch, native_guards=True, **changed)
    visual_errors = []
    _check_arm_guard(drawing._profile_chamfer_clear, *args, visual_errors=visual_errors)
    # A model reference-classification flag is intentionally not consulted.
    if changed != {"stock_reference": True}:
        assert visual_errors


@pytest.mark.parametrize(("changed", "message"), (
    ({"source_dimension": object()}, "source model dimension"), ({"stock_source": object()}, "source model dimension"),
    ({"override": True}, "override"), ({"stock_override": True}, "override"),
    ({"leg": 0.1}, "model leg"), ({"kind": 6}, "LIMIT band"), ({"lower": -0.05}, "LIMIT band"),
    ({"upper": 0.1}, "LIMIT band"), ({"precision": 1}, "tolerance precision"),
    ({"primary_precision": 1}, "primary precision"), ({"stock_precision": 2}, "primary precision"),
    ({"route": []}, "rear-Z mouth"), ({"route": [((0.0502, 0.210), (0.119, 0.226))]}, "rear-Z mouth"),
    ({"route": [((0.0501, 0.211), (0.119, 0.226))]}, "rear-Z mouth"),
    ({"box": (0.254, 0.078, float("nan"), 0.113)}, "border"),
    ({"box": (0.014, 0.078, 0.030, 0.113)}, "border"), ({"region_left": 0.2506}, "border"),
    ({"caption_extent": (0.014, 0.146, 0.0, 0.350, 0.160, 0.0)}, "border"),
    ({"caption_extent": None}, "caption"), ({"caption_extent": (0.3,) * 6}, "caption"),
    ({"zero_width": True}, "whole bounds"), ({"chamfer_width": 0.0}, "whole bounds"),
    ({"stock_runs": ()}, "no rendered text"),
))
def test_real_data_landing_and_text_border_faults_remain_fail_closed(monkeypatch, changed, message):
    args = _final_profile_case(monkeypatch, native_guards=True, **changed)
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
    route = [((0.0501 - distance, 0.210), (0.119, 0.226))]
    args = _final_profile_case(monkeypatch, route=route)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    if passes:
        _check_arm_guard(drawing._profile_chamfer_clear, *args)
    else:
        with pytest.raises(RuntimeError, match="does not land on the rear-Z mouth"):
            _check_arm_guard(drawing._profile_chamfer_clear, *args)
    assert any("numerical-zero landing distance (abs_tol=1e-8 m)" in entry for entry in logged)


@pytest.mark.parametrize("label", ("BoreRearChamferSize", "HubSeatDia", "anchor tap", "handle pivot"))
@pytest.mark.parametrize("fault", ("outside", "zero_width", "unreadable"))
def test_new_high_callouts_use_native_positive_width_and_border_gate(monkeypatch, forensic_calls, label, fault):
    native = _final_profile_case(monkeypatch, native_guards=True)
    case = _mock_arm_build(monkeypatch, native_case=native)
    annotations = {drawing.dimension_name(native[0], item): item for item in (*native[3], *native[4])}
    annotations.update(native[5])
    data = annotations[label].GetSpecificAnnotation().GetDisplayData()
    def unavailable(_index):
        raise OSError("high callout width unavailable")
    if fault == "outside":
        data.GetTextPositionAtIndex = lambda _index: (0.100, 0.264, 0.0)
    else:
        data.GetTextInBoxWidthAtIndex = unavailable if fault == "unreadable" else lambda _index: 0.0
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(drawing.build(native[0]))
    assert label in str(caught.value)
    assert "sheet border" in str(caught.value) or "whole bounds" in str(caught.value)
    assert case.finalized == [] and len(forensic_calls) == 1
    assert forensic_calls[0][3]["exception"] is caught.value


@pytest.mark.parametrize("label", ("seam callout", "fiducial callout", "profile caption"))
@pytest.mark.parametrize("extent", (
    None, (0.100, 0.264, 0.0, 0.150, 0.270, 0.0), (0.100, 0.220, 0.0, 0.100, 0.225, 0.0),
))
def test_retained_note_extents_share_positive_bounds_and_border_gate(monkeypatch, forensic_calls, label, extent):
    native = _final_profile_case(monkeypatch, native_guards=True)
    note = native[6] if label == "profile caption" else native[7][label]
    note.GetExtent = lambda: extent
    case = _mock_arm_build(monkeypatch, native_case=native)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(drawing.build(native[0]))
    assert label in str(caught.value)
    assert case.finalized == [] and len(forensic_calls) == 1
    assert forensic_calls[0][3]["exception"] is caught.value


def _mock_arm_build(monkeypatch, *, guard_error=False, native_case=None):
    views, curated, hlr, hlv, text, projected = [], [], [], [], [], []
    adapter = native_case[0] if native_case is not None else SimpleNamespace()
    if native_case is None:
        adapter.currentModel = object()
    native_place = drawing._place_profile_chamfer
    native_guard = drawing._profile_chamfer_clear
    native_breakout = drawing._create_profile_breakout
    if native_case is not None:
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
            else SimpleNamespace()
        )
        view.orientation, view.xy, view.mode, view.scale = orientation, xy, None, scale
        views.append(view)
        return view
    def project_top(_adapter, parent, *, visual_errors):
        assert _adapter is adapter and parent is views[0] and parent.orientation == "*Front"
        view = native_case[2] if native_case is not None else SimpleNamespace()
        view.orientation, view.xy, view.mode, view.scale = "*Top", drawing.PROFILE_CENTER, None, parent.scale
        view.parent = parent
        projected.append(view)
        views.append(view)
        return view
    def curate(_adapter, view, *, keep, dimensions_by_feature, **_kw):
        assert dimensions_by_feature is spec.DRAWING_DIMENSIONS
        assert view.mode == (1 if view.orientation == "*Top" else 2)
        if view.orientation == "*Top":
            assert hlv == [view] and projected == [view]
        curated.append((view.orientation, set(keep)))
        if native_case is not None:
            return native_case[3] if view.orientation == "*Front" else native_case[4]
        return [SimpleNamespace(name=name) for name in keep]
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "_project_top", project_top)
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    def hidden_removed(_adapter, view):
        view.mode = 2
        hlr.append(view)
    def hidden_visible(_adapter, view):
        view.mode = 1
        hlv.append(view)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", hidden_removed)
    monkeypatch.setattr(drawing, "set_hidden_lines_visible", hidden_visible)
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
    def guard(_a, front, profile, front_annotations, profile_annotations, callouts, actual_caption,
              attached_notes, *, errors, visual_errors):
        checked.append((front, profile, front_annotations, profile_annotations, set(callouts), actual_caption, attached_notes))
        assert profile.mode == 2 and hlv == [profile]
        if guard_error:
            errors.append("missing source Parameter identity")
        if native_case is not None:
            native_guard(_a, front, profile, front_annotations, profile_annotations, callouts, actual_caption, attached_notes,
                         errors=errors, visual_errors=visual_errors)
    monkeypatch.setattr(drawing, "_profile_chamfer_clear", guard)
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *_a, **_kw: True)
    def hole_callout(*_a, label, **_kw):
        annotation = native_case[5]["anchor tap" if label == "anchor tap" else "handle pivot"] if native_case is not None else object()
        return SimpleNamespace(GetAnnotation=lambda: annotation)
    monkeypatch.setattr(drawing, "add_native_hole_callout", hole_callout)
    monkeypatch.setattr(drawing, "add_attached_note", lambda *_a, label, **_kw: (
        native_case[7]["seam callout" if label == "MHA-DT-VN-59 seam callout" else "fiducial callout"]
        if native_case is not None else object()
    ))
    monkeypatch.setattr(drawing, "add_edge_dimension", lambda *_a, **_kw: SimpleNamespace(
        GetAnnotation=lambda: native_case[5]["overall length"] if native_case is not None else object(),
    ))
    async def finalize(*_a, **_kw):
        finalized.append(True)
        return {"drawing": "complete"}
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    return SimpleNamespace(
        adapter=adapter, views=views, curated=curated, hlr=hlr, hlv=hlv, text=text,
        projected=projected, placed=placed, checked=checked, finalized=finalized, caption=caption,
    )


@pytest.mark.parametrize("guard_error", (False, True))
def test_build_uses_one_derived_top_and_native_guards_before_finalization(monkeypatch, guard_error) -> None:
    case = _mock_arm_build(monkeypatch, guard_error=guard_error)
    adapter, finalized = case.adapter, case.finalized
    views, curated, hlr, hlv = case.views, case.curated, case.hlr, case.hlv
    placed, checked, text, caption = case.placed, case.checked, case.text, case.caption
    if guard_error:
        with pytest.raises(RuntimeError, match="missing source Parameter identity"):
            asyncio.run(drawing.build(adapter))
        assert finalized == []
    else:
        assert asyncio.run(drawing.build(adapter)) == {"drawing": "complete"}
        assert finalized == [True]
    assert [view.orientation for view in views] == ["*Front", "*Top", "*Isometric"]
    assert [view.scale for view in views] == [(2, 1), (2, 1), (1, 1)]
    assert hlr == [*views, views[1], views[1]]
    assert hlv == [views[1]]  # import only; breakout exposes final solid HLR ink
    assert [view.mode for view in views] == [2, 2, 2]
    assert curated == [("*Front", set(drawing.FRONT_KEEP)), ("*Top", {"Depth", "BoreRearChamferSize"})]
    assert placed[0][0] is checked[0][1] is views[1]
    assert placed[0][1] is checked[0][3]
    assert checked[0][4] == {"overall length", "handle pivot", "anchor tap"}
    assert checked[0][5] is caption
    assert case.projected == [views[1]] and views[1].parent is views[0]
    assert set(checked[0][6]) == {"seam callout", "fiducial callout"}
    assert text == [(set().union(*spec.DRAWING_DIMENSIONS.values()), drawing.DIMENSION_CALLOUTS)]
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and "A-A" in node.value
        for node in ast.walk(tree)
    )


def test_build_aggregates_only_real_gate_faults_and_still_logs_visual_measurements(monkeypatch):
    native = _final_profile_case(
        monkeypatch, native_guards=True,
        full_name="WrongSize@OtherFeature@dt-crank-arm.SLDPRT", dimension_type=1,
        source_dimension=object(), leg=0.10, kind=6, lower=-0.05, upper=0.10,
        edge_hidden=True, zero_width=True,
        caption_text=drawing.PROFILE_VIEW_CAPTION.replace("TOP", "SIDE").replace("\n", "\r\n"),
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
        "Width: native dimension text has no measurable whole bounds (run=0)",
        "Width: native dimension text has no measurable whole bounds (run=1)",
    ):
        assert violation in report
    assert "actual inner rear bore-chamfer edge" not in report
    assert "caption did not persist" not in report
    assert case.finalized == []
    # Both bad runs and every later independent dimension/caption are measured,
    # not merely a list of exceptions from coarse, first-failure helpers.
    for measured in (
        "WIDTH FIRST", "WIDTH SECOND", "EndRadius run 0", "stock thickness run 0",
        "overall length run 0", "handle pivot run 0", "anchor tap run 0",
        "profile chamfer rendered proof:", "cursor=", "rawlen=", "poly_count=",
        "profile caption has no measurable whole bounds",
        "profile caption / anchor tap",
    ):
        assert any(measured in entry for entry in logged)
    assert any("SIDE VIEW" in entry and "raw/normalized text" in entry for entry in logged)


@pytest.mark.parametrize("newline", ("\n", "\r\n"))
@pytest.mark.parametrize("mapped", (False, True))
def test_build_complete_native_guard_positive_control_reaches_finalize_once(monkeypatch, forensic_calls, newline, mapped):
    native = _final_profile_case(
        monkeypatch, native_guards=True,
        mapping=(object(), object()) if mapped else (None, None),
        attached=(), attached_count=0, attached_types=(),
        caption_text=drawing.PROFILE_VIEW_CAPTION.replace("\n", newline),
        text=drawing.CHAMFER_CALLOUT_BELOW,
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
    # These are synthetic projection/creation controls, not a new native render.
    xs, ys = [point[0] for point in doc.math_inputs], [point[1] for point in doc.math_inputs]
    assert max(xs) - min(xs) == pytest.approx(0.006)
    assert (min(ys), max(ys)) == pytest.approx((0.193, 0.211))
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    rx, ry = (max(xs) - min(xs)) / 2.0, (max(ys) - min(ys)) / 2.0
    wall_points = ((0.0501, 0.210), (0.0506, 0.2095), (0.0506, 0.194))
    assert all(abs(x - cx) / rx + abs(y - cy) / ry <= 1.0 for x, y in wall_points)


@pytest.mark.parametrize("fault", (
    "combined_render_font_mapping", "xform", "typed_disagreement", "typed_unmeasured",
    "GetXform", "GetPolylines7", "GetCorrespondingEntity",
    "GetDisplayData4", "GetLineCount", "GetLineAtIndex3", "unexpected_render_exception",
    "unreadable_controls", "orientation", "suffix_write", "callout_text_write",
))
def test_native_packet_visual_corruption_and_access_failures_still_finalize(
    monkeypatch, forensic_calls, fault,
):
    native = _final_profile_case(monkeypatch, native_guards=True)
    adapter, _front, profile, _front_annotations, profile_annotations, *_ = native
    annotation = profile_annotations[0]
    case = _mock_arm_build(monkeypatch, native_case=native)
    def unreadable(*_args, **_kwargs):
        raise OSError(f"visual channel {fault} unavailable")
    if fault == "combined_render_font_mapping":
        edges = profile.packet[0]
        records = list(profile.record_data)
        records[3] = _polyline_record((_NATIVE_SAMPLES["bevel"][0],) * 2, (0.0, 8.0, -1.0, 1.0, -1.0, 0.0))
        _packet(profile, edges, records)
        profile.GetCorrespondingEntity = lambda _source: object()
    elif fault == "xform":
        profile.GetXform = lambda: None
    elif fault in ("typed_disagreement", "typed_unmeasured", "GetLineCount", "GetLineAtIndex3"):
        lines = _typed_lines(profile, styles={"bevel": 1} if fault == "typed_disagreement" else None)
        if fault == "typed_unmeasured":
            lines[3] = None
        elif fault in ("GetLineCount", "GetLineAtIndex3"):
            setattr(profile.line_data, fault, unreadable)
    elif fault == "unexpected_render_exception":
        monkeypatch.setattr(drawing, "_rendered_chamfer_edges", unreadable)
    elif fault == "unreadable_controls":
        def project(*args, **kwargs):
            result = _project_profile(*args, **kwargs)
            if len(result) == 7:
                result[0] = None
            return result
        monkeypatch.setattr(drawing, "model_points_in_view", project)
    elif fault == "orientation":
        profile.GetOrientationName = unreadable
    elif fault == "suffix_write":
        annotation.GetSpecificAnnotation().SetText = unreadable
    elif fault == "callout_text_write":
        monkeypatch.setattr(drawing, "set_dimension_callouts", unreadable)
    else:
        setattr(profile, fault, unreadable)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    assert asyncio.run(drawing.build(adapter)) == {"drawing": "complete"}
    assert case.finalized == [True] and forensic_calls == []
    assert adapter.currentModel.breakout_count == 1 and len(adapter.currentModel.created) == 1
    assert any("visual telemetry only (reviewer owns PNG)" in entry for entry in logged)
    expected = {
        "combined_render_font_mapping": "chamfer section stroke",
        "xform": "profile native GetXform",
        "typed_disagreement": "documented typed style is not continuous",
        "typed_unmeasured": "typed visible line 3 GetLineAtIndex3",
        "unreadable_controls": "projection controls have invalid native points",
    }.get(fault, f"visual channel {fault} unavailable")
    assert any(expected in entry for entry in logged)


@pytest.mark.parametrize("missing", (
    "Parameter", "IsSame", "GetOverride", "GetPrimaryPrecision2", "GetPrimaryTolPrecision2",
    "GetMinValue", "projected_mouth", "leader_segments", "GetBreakOutSectionCount",
    "GetTextInBoxWidthAtIndex",
))
def test_unmeasured_data_for_each_retained_gate_refuses_before_finalize(monkeypatch, forensic_calls, missing):
    native = _final_profile_case(monkeypatch, native_guards=True)
    adapter, _front, profile, _front_annotations, profile_annotations, *_ = native
    annotation = profile_annotations[0]
    display = annotation.GetSpecificAnnotation()
    case = _mock_arm_build(monkeypatch, native_case=native)
    def unreadable(*_args, **_kwargs):
        raise OSError(f"required {missing} unavailable")
    if missing == "Parameter":
        profile.ReferencedDocument.Parameter = unreadable
    elif missing == "IsSame":
        adapter.swApp.IsSame = unreadable
    elif missing in ("GetOverride", "GetPrimaryPrecision2", "GetPrimaryTolPrecision2"):
        setattr(display, missing, unreadable)
    elif missing == "GetMinValue":
        display.GetDimension2(0).Tolerance.GetMinValue = unreadable
    elif missing == "projected_mouth":
        def project(*args, **kwargs):
            result = _project_profile(*args, **kwargs)
            if len(result) == 7:
                result[6] = None
            return result
        monkeypatch.setattr(drawing, "model_points_in_view", project)
    elif missing == "leader_segments":
        original = drawing.dimension_segments
        monkeypatch.setattr(drawing, "dimension_segments", lambda item: unreadable() if item is annotation else original(item))
    elif missing == "GetBreakOutSectionCount":
        profile.GetBreakOutSectionCount = unreadable
    else:
        display.GetDisplayData().GetTextInBoxWidthAtIndex = unreadable
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(drawing.build(adapter))
    assert "UNMEASURED" in str(caught.value)
    assert case.finalized == [] and len(forensic_calls) == 1
    assert forensic_calls[0][3]["exception"] is caught.value


@pytest.mark.parametrize(("changed", "attempts"), (
    ({"create_breakout": False}, 1), ({"create_breakout": None}, 1), ({"create_error": True}, 1),
    ({"spline": None}, 0), ({"spline_select": False}, 0), ({"sketch_xyz": (0.0, 0.0)}, 0),
    ({"sketch_xyz": (0.0, 0.0, 0.0)}, 0), ({"after_breakout_count": 2}, 1),
))
def test_final_breakout_count_refuses_without_retry(monkeypatch, changed, attempts):
    native = _final_profile_case(monkeypatch, native_guards=True, **changed)
    case = _mock_arm_build(monkeypatch, native_case=native)
    with pytest.raises(RuntimeError, match="profile did not retain exactly one local breakout"):
        asyncio.run(drawing.build(case.adapter))
    doc = case.adapter.currentModel
    assert len(doc.created) == attempts
    assert len(doc.splines) <= 1 and case.finalized == []
    assert doc.SketchManager.AddToDB is False
    assert len(case.views) == 3 and case.views[1].mode == 2


@pytest.mark.parametrize(("changed", "attempts"), (
    ({"initial_breakout_count": 1}, 0), ({"breakout_features": ()}, 1),
    ({"breakout_depth": 0.013}, 1), ({"depth_reference": object()}, 1),
    ({"access_selections": False}, 1), ({"release_error": True}, 1),
))
def test_breakout_definition_telemetry_does_not_refuse_a_native_count_of_one(
    monkeypatch, forensic_calls, changed, attempts,
):
    native = _final_profile_case(monkeypatch, native_guards=True, **changed)
    case = _mock_arm_build(monkeypatch, native_case=native)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    assert asyncio.run(drawing.build(case.adapter)) == {"drawing": "complete"}
    doc = case.adapter.currentModel
    assert doc.breakout_count == 1 and len(doc.created) == attempts
    assert len(doc.splines) <= 1 and doc.SketchManager.AddToDB is False
    assert case.finalized == [True] and forensic_calls == []
    assert any("visual telemetry only (reviewer owns PNG)" in entry for entry in logged)
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


def test_breakout_and_width_gate_faults_do_not_promote_visual_diagnostics(monkeypatch):
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
        "profile did not retain exactly one local breakout",
        "Width: native dimension text has no measurable whole bounds (run=0)",
        "Width: native dimension text has no measurable whole bounds (run=1)",
    ):
        assert message in report
    for visual in ("creation failed", "native outline font descriptor", "chamfer section stroke",
                   "native 8 mm reference (prefix)", "caption did not persist"):
        assert visual not in report
    assert case.adapter.currentModel.created == [spec.HALF_WIDTH / 1000.0]
    assert case.finalized == []


@pytest.mark.parametrize("newline", ("\n", "\r\n"))
def test_build_caption_wording_mismatch_is_telemetry_under_either_newline(monkeypatch, forensic_calls, newline):
    native = _final_profile_case(
        monkeypatch, native_guards=True,
        caption_text=drawing.PROFILE_VIEW_CAPTION.replace("TOP", "SIDE").replace("\n", newline),
    )
    case = _mock_arm_build(monkeypatch, native_case=native)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    assert asyncio.run(drawing.build(case.adapter)) == {"drawing": "complete"}
    assert case.finalized == [True] and forensic_calls == []
    assert any("caption did not persist" in entry for entry in logged)


def test_early_placement_and_reference_faults_are_visual_only(monkeypatch, forensic_calls):
    native = _final_profile_case(monkeypatch, native_guards=True)
    annotation = native[4][0]
    annotation.SetPosition2 = lambda *_xyz: False
    case = _mock_arm_build(monkeypatch, native_case=native)
    def reject_reference(*_args, label, **_kwargs):
        if label == "arm stock thickness":
            raise OSError("native reference readback rejected")
    monkeypatch.setattr(drawing, "set_reference_dimension", reject_reference)
    logged = []
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    assert asyncio.run(drawing.build(case.adapter)) == {"drawing": "complete"}
    for diagnostic in ("failed to place the native bore-mouth dimension line",
                       "UNMEASURED Depth stock reference placement: OSError: native reference readback rejected"):
        assert any(diagnostic in entry for entry in logged)
    assert len(case.checked) == 1 and case.finalized == [True] and forensic_calls == []


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
    assert "caption did not persist" not in report
    assert any("caption did not persist" in entry for entry in logged)
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
    width_annotation = next(item for item in native[3] if drawing.dimension_name(native[0], item) == "Width")
    width_data = width_annotation.GetSpecificAnnotation().GetDisplayData()
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
    ):
        assert violation in report
    assert "caption did not persist" not in report
    assert any("caption did not persist" in entry for entry in logged)
    assert any("WIDTH SECOND" in entry for entry in logged)
    assert any("anchor tap run 0" in entry for entry in logged)
    assert case.finalized == []


def test_collected_guard_failure_captures_labelled_sheet_before_same_exception(monkeypatch):
    adapter = object()
    errors = ["missing source Parameter identity", "unmeasured native text width", "wrong breakout count"]
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
            "profile did not retain exactly one local breakout", "source model dimension", "LIMIT band (lower)",
            "tolerance precision", "run=0", "run=1",
        ):
            assert violation in message
        for visual in ("creation failed", "actual inner", "native 8 mm reference (prefix)", "caption did not persist"):
            assert visual not in message
        assert message == "crank arm native guard violations:\n- " + "\n- ".join(context["violations"])
        captured.append(context["exception"])
        raise context["exception"]
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(drawing.build(case.adapter))
    assert captured == [caught.value] and captured[0] is caught.value
    assert case.finalized == []
