"""Offline contracts for the through-hub crankshaft drawing."""

from __future__ import annotations

import ast
import asyncio
import math
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from solidworks_mcp.adapters.solidworks import drawing as native_drawing

import build_dt_crankshaft as part
import dt_crank_hub_geometry as geometry
import dt_crankshaft_notes as notes
import dt_crankshaft_spec as spec
import draw_dt_crankshaft as drawing
import _drawing_attachment as attachment_helpers
import _drawing_edge_dimensions as edge_dimensions
import _drawing_selection as selection_helpers
import _drawing_common as drawing_common
from _pdf_ink import Glyph, PageInk, Span, Stroke
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, drawing_specification_violations
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from _layout_audit import TEXT_ROW_LIMIT
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crankshaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crankshaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crankshaft_drawing.png")
    assert DRAWINGS_BY_NAME["dt_crankshaft"].script == Path(drawing.__file__).resolve()




def test_policy_migrated_sheet_carries_no_gdt_and_model_owned_places() -> None:
    # drawing-guidelines.md rule 5 (avoid excessive GD&T): a shaft carries no frames, datums or basic dimensions.
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_feature_control_frame",
        "add_datum_feature",
        "set_basic_dimension",
        "set_dimension_precision",
    ):
        assert helper not in source
    # drawing-simplicity-policy.md `How the repository implements the guidelines`: the part authors every printed dimension's places.
    assert "draw_dt_crankshaft.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert {
        "Depth",
        "PinionSeatStation",
        "JournalInboardStation",
        "ReliefInboardStation",
        "ReliefOutboardStation",
        "JournalOutboardStation",
        "CollarRearStation",
        "CollarSeatStation",
    } <= marked - spec.REFERENCE_DIMENSIONS
    assert spec.REFERENCE_DIMENSIONS <= marked
    assert spec.SPHERICAL_DIMENSIONS <= spec.REFERENCE_DIMENSIONS


def test_far_end_stations_restate_the_modelled_geometry() -> None:
    # The StationReference sketch drives each printed station from the same
    # globals as the features; these are the values the equations evaluate to.
    far = spec.SHAFT_LENGTH
    assert far - spec.SEAT_STEP == pytest.approx(spec.PINION_SEAT_STATION)
    # The station the spec chose prints exactly at its places.
    assert spec.dt_crank_pinion_spec.prints_exactly(
        spec.PINION_SEAT_STATION, spec.STATION_PLACES, spec.UNIT
    )
    assert set(part._STATIONS) == set(part._STATION_DRIVES)
    assert set(part._STATIONS) <= spec.DRAWING_DIMENSIONS["StationReference"]
    assert part.DOME_SPHERE_R == pytest.approx(
        (spec.SHAFT_DIA**2 / 4.0 + spec.SHAFT_DOME_HEIGHT**2)
        / (2.0 * spec.SHAFT_DOME_HEIGHT)
    )


def test_notes_stay_within_rule_six() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert all(len(line) <= 66 for line in lines)


def test_shaft_prints_exactly_and_reaches_the_restored_post_boss() -> None:
    # W15 under ruling D1: the shortest one-place shaft whose end stands proud
    # of the 16T at every accepted part set, while the shaft datum
    # independently lands on the post's restored north face.
    pinion = spec.dt_crank_pinion_spec
    assert pinion.prints_exactly(spec.SHAFT_LENGTH, pinion.SHAFT_LENGTH_PLACES, spec.UNIT)
    assert spec.DRAWING_PRECISION["Shaft"]["Depth"] == pinion.SHAFT_LENGTH_PLACES
    least, most = spec.SHAFT_END_PROUD_RANGE
    assert spec.shaft_end_proud_range(spec.SHAFT_LENGTH) == (least, most)
    assert least >= 0.0
    assert least <= spec.SHAFT_END_PROUD_NOMINAL <= most
    # One print step shorter and the end can sit inside the 16T.
    step = pinion.print_step(pinion.SHAFT_LENGTH_PLACES, spec.UNIT)
    assert spec.shaft_end_proud_range(spec.SHAFT_LENGTH - step)[0] < 0.0
    import cone_line
    import dt_cone_pivot_post_spec as post

    post_boss_north = cone_line.cone_station(cone_line.POST_STATION)[2] - post.CRANK_BOSS_START_Z
    assert -183.0 + spec.POST_BORE_END == pytest.approx(post_boss_north)


def test_seat_collar_lands_the_wheel_seat_and_bears_on_the_post_boss() -> None:
    # The collar's front is the Ø17.5 seat spigot, whose face is the removable
    # sprocket's seat on the shared plane, stepping up to the Ø20.6 body; its
    # rear face bears on the post boss's south face (owner ruling D1: no
    # washer), and stays short of the outboard journal land.
    import build_dt_drive_train_assembly as bdt
    import dt_cone_pivot_post_spec as post
    import _sprocket_seat_geometry as removable

    assert bdt.CRANKSHAFT_Z0 + spec.SEAT_COLLAR == pytest.approx(removable.SEAT_FACE_Z)
    # The inch spigot (.689) is the wheel's seat to within its print grid.
    assert spec.SPIGOT_DIA == pytest.approx(removable.SEAT_SPIGOT_DIA, abs=0.001)
    assert spec.SPIGOT_DIA < spec.COLLAR_DIA
    # The blind drive-pin holes end in the spigot, short of its step.
    assert spec.SEAT_COLLAR < spec.DRIVE_PIN_FLOOR < spec.SPIGOT_END
    # The rear face from the post's own boss face, floored to its .XX print.
    boss_south = spec.POST_BORE_END - post.CRANK_BOSS_LENGTH
    assert spec.POST_BOSS_SOUTH == pytest.approx(boss_south)
    places = spec.COLLAR_STATION_PLACES
    pinion = spec.dt_crank_pinion_spec
    assert pinion.prints_exactly(spec.COLLAR_LENGTH, places, spec.UNIT)
    assert 0.0 <= boss_south - spec.COLLAR_REAR < pinion.print_step(places, spec.UNIT)
    assert spec.COLLAR_BOSS_AIR == pytest.approx(boss_south - spec.COLLAR_REAR)
    # The body keeps length at print-worst: both stations and the spigot.
    body_worst = (
        spec.COLLAR_LENGTH
        - spec.SPIGOT_LENGTH
        - 2.0 * spec.COLLAR_STATION_TOL
        - spec.SPIGOT_LENGTH_TOL
    )
    assert body_worst > 0.0
    assert spec.COLLAR_REAR + spec.COLLAR_STATION_TOL < spec.JOURNAL_START
    # The bare land behind the collar spans the bore mouth's edge break at
    # print-worst, so the rear face seats flat on the boss.
    assert (
        spec.JOURNAL_START - spec.STATION_ROW - (spec.COLLAR_REAR + spec.COLLAR_STATION_TOL)
        >= spec.BORE_MOUTH_BREAK_MAX - 1e-9
    )
    assert spec.BORE_MOUTH_BREAK_MAX == 0.25
    # Bottomed dowels stand proud by the drive-train's pin length budget.
    assert (
        bdt.CRANKSHAFT_Z0 + spec.DRIVE_PIN_FLOOR - spec.dt_vn_crank_seat_drive_pin_spec.LENGTH
        == (pytest.approx(removable.DRIVE_PIN_TIP_Z))
    )



def test_spigot_rim_is_the_shortfall_the_sheet_states() -> None:
    # The drive-pin holes' rim to the seat spigot is under the .060 in
    # wall floor (declared shortfall RV-02, owner ruling 2026-10-18): the sheet states the worst case of
    # the printed bands, rounded down so it never claims more rim than exists.
    hole_r = spec.DRIVE_PIN_HOLE_DIA / 2.0
    worst = (spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[1]) / 2.0 - (
        spec.DRIVE_PIN_CIRCLE_RADIUS
        + spec.DRIVE_PIN_OFFSET_TOL
        + hole_r
        + spec.DRIVE_PIN_HOLE_BAND[0] / 2.0
    )
    rim = spec.DRIVE_PIN_SPIGOT_RIM_WORST
    assert worst - 0.0254 < rim <= worst
    assert 0.0 < rim < spec.WALL_FLOOR_MM
    printed = re.search(r"SPIGOT RIM (\.\d{3}) MIN\.", notes.DRIVE_PIN_CALLOUT)
    assert printed
    assert float(printed.group(1)) * 25.4 == pytest.approx(rim)


def test_drive_pin_depth_prints_its_band_after_the_native_depth() -> None:
    # Machinist review of f7c9771b3: the bare 3.95 read under the title
    # block's .XX and left 5.75 - 4.46 = 1.29 of spigot under the holes.  The
    # callout carries the cut's own band, the one the proud stack reads.
    floor = (spec.SPIGOT_LENGTH - spec.SPIGOT_LENGTH_TOL) - (
        spec.DRIVE_PIN_DEPTH + spec.DRIVE_PIN_DEPTH_TOL
    )
    assert floor >= spec.WALL_FLOOR_MM
    band = notes.DRIVE_PIN_DEPTH_BAND
    # The farm's native split: the process and diameter modifier in the
    # prefix, the depth in a later compartment.
    depth = "<HOLE-DEPTH> <hw-depth>"

    def parts(prefix: str = "REAM <MOD-DIAM>", suffix: str = depth) -> dict:
        return {5: prefix, 6: suffix, 7: "", 8: ""}

    assert drawing._depth_banded_definition(parts(), band) == (6, f"{depth} {band}")
    whole = "REAM <MOD-DIAM><hw-diam> <HOLE-DEPTH> <hw-depth>"
    assert drawing._depth_banded_definition(parts(prefix=whole, suffix=""), band) == (
        5,
        f"{whole} {band}",
    )
    for broken in (
        parts(suffix="THRU ALL"),
        parts(suffix=f"{depth} {band}"),
        parts(suffix=f"{depth} PRESS FIT"),
        parts(suffix=f"<HOLE-DEPTH> 1.0 {depth}"),
        parts(prefix=f"REAM {depth}"),
        {5: "REAM <MOD-DIAM>", 6: depth},
    ):
        with pytest.raises(RuntimeError):
            drawing._depth_banded_definition(broken, band)


class _Sheet:
    """A drawing document reporting one linear unit (swLengthUnit_e)."""

    def __init__(self, unit: object) -> None:
        self.unit = unit

    def GetUserPreferenceIntegerValue(self, pref: int) -> object:
        assert pref == drawing._SW_PREF_UNITS_LINEAR
        return self.unit


def test_typed_depth_band_refuses_a_non_inch_sheet() -> None:
    # Codex P2 on #1151: the band is typed text after a native depth, so it
    # is only true on a sheet of its own unit (inches, #290); the callout
    # variables that would carry it natively are unreachable on this
    # cut-extrude callout (farm run 20261003T001156794Z).
    drawing._require_inch_sheet(_Sheet(3), "inch")  # swINCHES
    for unit in (0, 1, None):  # swMM, swCM, an unread preference
        with pytest.raises(RuntimeError, match="typed depth band is inches"):
            drawing._require_inch_sheet(_Sheet(unit), "not inch")

    class _Callout:
        def GetText(self, part: int) -> str:
            raise AssertionError("read the callout before the unit check")

    with pytest.raises(RuntimeError, match="typed depth band is inches"):
        drawing._band_hole_depth(
            _Callout(), notes.DRIVE_PIN_DEPTH_BAND, _Sheet(0), "mm sheet"
        )


def test_integral_dome_is_the_only_outboard_shaft_projection() -> None:
    assert spec.SHAFT_DIA == geometry.SHAFT_DIA
    assert spec.SHAFT_DIA == pytest.approx(9.525, abs=1e-12)
    assert spec.SHAFT_DOME_HEIGHT == geometry.SHAFT_DOME_HEIGHT == 2.0
    assert geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[0] < (
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[1]
    )
    assert not hasattr(spec, "CRANK_END_NOTE")


def test_mha024_station_and_notes_belong_to_hub_and_shaft() -> None:
    assert part.PIN_HOLE_SPEC is spec.PIN_HOLE_SPEC
    assert drawing.PIN_HOLE_SPEC is spec.PIN_HOLE_SPEC
    assert drawing._PIN_HOLE_DIA == blind_cut_dia_mm(spec.PIN_HOLE_SPEC)
    assert spec.PIN_HOLE_HEIGHT == geometry.SERVICE_PIN_STATION == pytest.approx(13.6)
    # The drill size reads first (the prefix of the native callout); the
    # matched fit, naming both mating parts, reads under it.
    assert spec.CROSS_HOLE_PROCESS == "#9 DRILL"
    callout = notes.CROSS_HOLE_CALLOUT
    assert "TAPER-REAM" in callout
    assert "LIGHT DRIVE FIT" in callout
    assert "MHA-DT-31" in callout
    assert "MHA-DT-09" in callout
    assert "MHA-DT-06" not in callout


def test_shaft_end_fiducial_is_a_simple_punch_not_a_dimensioned_dimple() -> None:
    assert spec.FIDUCIAL_MODEL_DIA == geometry.FIDUCIAL_MODEL_DIA == 0.8
    assert spec.FIDUCIAL_MODEL_DEPTH == geometry.FIDUCIAL_MODEL_DEPTH == 0.2
    assert spec.SHAFT_FIDUCIAL_RADIUS == geometry.SHAFT_FIDUCIAL_RADIUS == 2.5
    assert "PUNCH" in notes.FIDUCIAL_NOTE
    assert "BY EYE" in notes.FIDUCIAL_NOTE
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert all("Fiducial" not in name for name in marked)
    assert "DIMPLE" not in notes.FIDUCIAL_NOTE


def test_side_view_sheet_stations_follow_the_model() -> None:
    scale = drawing.SHEET_SCALE[0]
    span = spec.SHAFT_LENGTH + spec.SHAFT_DOME_HEIGHT
    assert drawing.DOME_TIP_X == pytest.approx(
        drawing.SIDE_CENTER[0] - span * scale / 2000.0
    )
    assert drawing.FAR_END_X == pytest.approx(
        drawing.SIDE_CENTER[0] + span * scale / 2000.0
    )
    assert drawing.DOME_ROOT_X == pytest.approx(
        drawing.DOME_TIP_X + spec.SHAFT_DOME_HEIGHT * scale / 1000.0
    )
    assert drawing.PIN_X == pytest.approx(
        drawing.DOME_ROOT_X + spec.PIN_HOLE_HEIGHT * scale / 1000.0
    )


def test_horizontal_profile_and_left_end_view_are_third_angle_aligned() -> None:
    # *Right rotated -90 deg puts model +Y (far end) at paper-right and +Z up;
    # *Bottom (X right, Z up) is then the true left view, on the same axis.
    assert drawing.SIDE_VIEW_ANGLE == pytest.approx(-math.pi / 2.0)
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    # The collar is the end view's largest circle.
    end_radius = spec.COLLAR_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.END_CENTER[0] + end_radius < drawing.DOME_TIP_X


# Measured on the 19e33c6c2 stack-top render (3.5 mm text, 2:1 sheet): the
# "7.000 ±0.025" value is 27.5 mm wide, and the uppercase callout rows run
# 2.75 mm a character ("SPROCKET MHA-PD-09", 44 mm).
_PIN_VALUE_TEXT_WIDTH = 0.0275
_CALLOUT_CHAR_WIDTH = 0.00275


def test_pin_location_texts_end_before_the_dome_extension_lines() -> None:
    # Machinist review of 19e33c6c2: the text block runs right from the
    # dimension line beside the end view, and the old two-row callout carried
    # the value and its mate note across the dome tip's and dome root's
    # extension lines.  Every row must end, with air, before the dome tip;
    # both pin locations name the mate (machinist review of 902433a8d).
    rows = notes.DRIVE_PIN_LOCATION_CALLOUT.splitlines()
    assert "MHA-PD-09" in rows and "SPROCKET" in " ".join(rows)
    block = max(
        _PIN_VALUE_TEXT_WIDTH,
        max(len(row) for row in rows) * _CALLOUT_CHAR_WIDTH,
    )
    for name, (x, _y) in drawing.END_PIN_KEEP.items():
        assert drawing.CALLOUTS_BELOW[name] == notes.DRIVE_PIN_LOCATION_CALLOUT
        assert x + block + 0.001 < drawing.DOME_TIP_X, name


def test_blind_pin_holes_bottom_in_the_collar_body_not_the_spigot_end() -> None:
    # Machinist review of 19e33c6c2 read 5.75 - 4.05 = 1.70 behind the holes,
    # taking the 5.80 spigot step for the end of material.  The holes lie
    # wholly inside the spigot, and the Ø20.6 body continues behind it to the
    # rear face: the floor is the collar's worst-case length less the
    # deepest hole, over the 2.0 wall target.
    assert spec.DRIVE_PIN_CIRCLE_RADIUS + spec.DRIVE_PIN_HOLE_DIA / 2.0 < (
        spec.SPIGOT_DIA / 2.0
    )
    collar_min = spec.COLLAR_LENGTH - 2.0 * spec.COLLAR_STATION_TOL
    deepest = spec.DRIVE_PIN_DEPTH + spec.DRIVE_PIN_DEPTH_TOL
    assert collar_min - deepest >= 2.0


def test_sheet_placements_stay_inside_the_border() -> None:
    inner = (0.0127, 0.0127, 0.4191, 0.2667)  # ASME B landscape inner border
    title_block = (0.218, 0.065)  # x >= and y <=
    points = [
        drawing.END_CENTER,
        drawing.ISO_CENTER,
        drawing.HOLE_CALLOUT_XY,
        drawing.PINION_PIN_NOTE_XY,
        drawing.NOTES_XY,
        drawing.ISO_NOTE_XY,
        drawing.CENTRES_NOTE_XY,
        drawing.OUTBOARD_NECK_DIAMETER_XY,
        *(symbol for _, symbol in drawing.JOURNAL_FINISHES.values()),
        drawing.COLLAR_REAR_FINISH[1],
        drawing.DRIVE_PIN_CALLOUT_XY,
        *drawing.SIDE_KEEP.values(),
        *drawing.END_PIN_KEEP.values(),
        *drawing.DIAMETER_POSITIONS.values(),
    ]
    for x, y in points:
        assert inner[0] < x < inner[2] and inner[1] < y < inner[3]
        assert not (x >= title_block[0] and y <= title_block[1])
    # Both dragged diameters land on the section their profile sketch starts,
    # so their axis-parallel extension lines hide under the silhouette.  The
    # Ø9.525's run from the dome root, so it sits LEFT of the cross-hole: its
    # lines then stop short of the hole the callout's leader leaves (af13c8ff8
    # leader-crosses-line).
    shaft_x = drawing.DIAMETER_POSITIONS["ShaftDiaDim"][0]
    seat_x = drawing.DIAMETER_POSITIONS["PinionSeatDiaDim"][0]
    hole_radius = drawing._PIN_HOLE_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.DOME_ROOT_X < shaft_x < drawing.PIN_X - hole_radius
    pinion_hole_left = drawing.PINION_PIN_HOLE_WINDOW[0]
    assert drawing.SEAT_STEP_X < seat_x < pinion_hole_left
    # The cross-hole callout sits right of the hole so its leader cannot run
    # near-parallel to the station extension line through the hole.
    assert drawing.HOLE_CALLOUT_XY[0] > drawing.PIN_X
    # Each bearing land has its own native control and visible Ra leader; a
    # 2X diameter does not extend the finish symbol across the relief.
    lands = {
        "outboard_journal": (spec.JOURNAL_START, spec.RELIEF_START),
        "inboard_journal": (spec.RELIEF_END, spec.JOURNAL_END),
    }
    journal_controls = [c for c in spec.SURFACE_FINISHES if c.key in lands]
    assert set(drawing.JOURNAL_FINISHES) == set(lands)
    for control in journal_controls:
        start, end = lands[control.key]
        assert control.roughness_um == MACHINED_UM
        assert control.face.diameter_mm == spec.JOURNAL_DIA
        assert start < control.face.contains_y_mm < end
        pick, symbol = drawing.JOURNAL_FINISHES[control.key]
        assert drawing._sheet_x(start) < pick[0] < drawing._sheet_x(end)
        assert pick[1] == pytest.approx(drawing.JOURNAL_FLANK_Y)
        assert drawing._sheet_x(start) < symbol[0] < drawing._sheet_x(end)
    # The collar's rear face runs on the thrust washer: its own control, its
    # leader landing on that face's edge-on line, clear of the corner it
    # shares with the Ø20.6 OD and above the neck it steps down to.
    (washer_face,) = [c for c in spec.SURFACE_FINISHES if c.key not in lands]
    assert washer_face.key == "collar_rear_face"
    pick, _symbol = drawing.COLLAR_REAR_FINISH
    assert pick[0] == pytest.approx(drawing._sheet_x(washer_face.face.offset_mm))
    corner_y = drawing._sheet_y(spec.COLLAR_DIA / 2.0)
    assert drawing._sheet_y(spec.SHAFT_DIA / 2.0) < pick[1] <= corner_y - 0.0015


@pytest.mark.parametrize("case", ["thrust-face", "no-plane", "two-planes", "one-face"])
def test_collar_rear_finish_resolves_the_controlled_thrust_face_from_its_rim(
    monkeypatch: pytest.MonkeyPatch, case: str,
) -> None:
    from _gtol_face import SURFACE_CYLINDER, SURFACE_PLANE, FaceGeometry

    rear_m, radius_m = spec.COLLAR_REAR / 1000.0, spec.COLLAR_DIA / 2000.0
    thrust, od = object(), object()
    geometries = {
        thrust: FaceGeometry(
            thrust, SURFACE_PLANE, (0.0, 1.0, 0.0, 0.0, rear_m, 0.0), (0.0, 1.0, 0.0), (),
        ),
        od: FaceGeometry(
            od, SURFACE_CYLINDER, (0.0, 0.0, 0.0, 0.0, 1.0, 0.0, radius_m), None, (),
        ),
    }
    if case == "no-plane":
        geometries[thrust] = geometries[od]
    elif case == "two-planes":
        geometries[od] = geometries[thrust]
    monkeypatch.setattr(drawing, "face_geometry", lambda face: geometries[face])
    faces = (thrust,) if case == "one-face" else (od, thrust)
    rim = SimpleNamespace(GetTwoAdjacentFaces2=Mock(return_value=faces))
    if case == "thrust-face":
        assert drawing._collar_rear_face(rim) is thrust
    else:
        with pytest.raises(RuntimeError, match="collar rear rim: expected one"):
            drawing._collar_rear_face(rim)


def test_each_bare_neck_has_its_own_native_loose_diameter() -> None:
    # The previous 2X callout reached only the right neck. The collar-side
    # land must now have its own opposite-silhouette full-width measurement, while the
    # original right-hand model dimension retains its authoritative size.
    covers = sorted(
        [
            (spec.SEAT_COLLAR, spec.SEAT_COLLAR + spec.COLLAR_LENGTH),
            (spec.JOURNAL_START, spec.JOURNAL_START + spec.JOURNAL_LENGTH),
            (spec.SEAT_STEP, spec.SHAFT_LENGTH),
        ]
    )
    bare: list[tuple[float, float]] = []
    edge = 0.0
    for start, end in covers:
        if start > edge:
            bare.append((edge, start))
        edge = max(edge, end)
    assert edge == pytest.approx(spec.SHAFT_LENGTH)
    assert spec.RELIEF_DIA > spec.SHAFT_DIA > spec.PINION_SEAT_DIA
    assert [v for land in spec.SHAFT_CORE_LANDS for v in land] == pytest.approx(
        [v for land in bare for v in land]
    )
    assert spec.SHAFT_CORE_LANDS[1] == (spec.COLLAR_REAR, spec.JOURNAL_START)
    assert drawing.CALLOUTS_ABOVE["NeckDiaDim"] == ""
    assert drawing.DIAMETER_POSITIONS["NeckDiaDim"] == (
        drawing.JOURNAL_END_X + 0.0006, 0.230
    )
    assert spec.DRAWING_REFERENCE_PRECISION == {"OutboardNeckDia": spec.NECK_DIA_PLACES}
    assert drawing.DRAWING_REFERENCE_PRECISION is spec.DRAWING_REFERENCE_PRECISION
    assert spec.NECK_DIA_PLACES == 3
    neck_x, neck_y = drawing.OUTBOARD_NECK_DIAMETER_XY
    assert drawing.COLLAR_REAR_X < neck_x < drawing.JOURNAL_START_X
    assert neck_x == pytest.approx((drawing.COLLAR_REAR_X + drawing.JOURNAL_START_X) / 2.0)
    assert neck_y == pytest.approx(0.1948)
    assert drawing._sheet_y(spec.JOURNAL_DIA / 2.0) < neck_y
    assert neck_y < drawing._sheet_y(spec.COLLAR_DIA / 2.0)
    finish_pick, finish_symbol = drawing.COLLAR_REAR_FINISH
    assert neck_y < finish_symbol[1] < finish_pick[1]
    assert finish_symbol[0] == pytest.approx(drawing.COLLAR_REAR_X + 0.0069)
    assert finish_symbol[1] == pytest.approx(0.1983)
    assert finish_pick == (
        drawing.COLLAR_REAR_X, drawing._sheet_y(spec.COLLAR_DIA / 2.0 - 0.8),
    )
    # These relative presentation positions do not certify glyph/leader
    # clearance: the changed native sheet must pass the normal ink audit.
    assert drawing.SIDE_KEEP["JournalOutboardStation"][1] < neck_y
    assert drawing.SIDE_KEEP["CollarRearStation"][1] < neck_y
    for name in ("PinionSeatStation", "JournalInboardStation", "ReliefInboardStation"):
        assert neck_x < drawing._sheet_x({
            "PinionSeatStation": spec.SEAT_STEP,
            "JournalInboardStation": spec.JOURNAL_END,
            "ReliefInboardStation": spec.RELIEF_END,
        }[name])
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename="draw_dt_crankshaft.py")
    assert not drawing.CALLOUTS_ABOVE["ShaftDiaDim"][:1].isdigit()
    assert spec.DRAWING_PRECISION["PinionSeatProfile"]["NeckDiaDim"] == spec.NECK_DIA_PLACES


def test_integral_lands_run_in_the_restored_post_at_every_size_limit() -> None:
    import dt_cone_pivot_post_spec as post

    bore_min = post.CRANK_BORE_DIA + post.RUNNING_BORE_BAND[1]
    bore_max = post.CRANK_BORE_DIA + post.RUNNING_BORE_BAND[0]
    shaft_min = spec.JOURNAL_DIA + spec.JOURNAL_DIA_BAND[1]
    shaft_max = spec.JOURNAL_DIA + spec.JOURNAL_DIA_BAND[0]
    assert (bore_min - shaft_max, bore_max - shaft_min) == pytest.approx(
        spec._RUNNING_CLEARANCE
    )
    assert spec.JOURNAL_START < spec.RELIEF_START < spec.RELIEF_END < spec.JOURNAL_END
    assert min(spec.JOURNAL_LANDS_WORST) >= spec.JOURNAL_DIA
    assert spec.JOURNAL_END + spec.STATION_ROW < spec.POST_BORE_END
    assert spec.STEP_WEB_WORST >= spec.WEB_TARGET_MM - 1e-9
    assert spec.RELIEF_DIA + spec.STATION_ROW < shaft_min
    assert spec.RELIEF_DIA - spec.STATION_ROW > spec.SHAFT_DIA


def test_view_scales_and_linked_notes_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.VIEW_SCALE == (2, 1)
    assert drawing.ISO_SCALE == (1, 1)
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW\nSCALE 1:1"




def test_seat_step_never_pushes_the_pinion_past_its_seat_gap() -> None:
    # The pinion is set on its feeler and pinned; the step never locates it.
    # A step printed at its north limit plus a corner up to the title block's
    # edge break stands the bore edge off, which the seat gap's north range
    # must hold.
    from _printed_tolerance import edge_break_radius_mm

    pinion = spec.dt_crank_pinion_spec
    assert spec.STEP_CORNER_RADIUS_MAX == edge_break_radius_mm(unit=spec.UNIT)
    standoff = spec.SEAT_STEP + spec.STATION_ROW + spec.STEP_CORNER_RADIUS_MAX - part.SEAT_PINION
    assert standoff == pytest.approx(spec.SEAT_STEP_STANDOFF_WORST)
    assert standoff <= pinion.SEAT_GAP_MAX_MM - pinion.SEAT_FEELER_MM
    # The seat is the pinion's bore mate, at the through shaft's size band.
    assert spec.PINION_SEAT_DIA == pinion.BORE_DIA
    assert spec.PINION_SEAT_DIA_BAND == spec.SHAFT_DIA_BAND


def test_retention_pin_note_clears_the_profile_and_title_block() -> None:
    assert drawing.PINION_PIN_X == pytest.approx(
        drawing.DOME_ROOT_X + part.PINION_PIN_STATION_Y * drawing.SHEET_SCALE[0] / 1000.0
    )
    assert drawing.JOURNAL_END_X < drawing.PINION_PIN_X < drawing.FAR_END_X
    # The note block (top-left anchored; sized for up to 3.5 mm note text)
    # stays inside its field: right of the cross-hole callout's text, above
    # the diameter row, left of the isometric and inside the border.
    lines = drawing.CRANKSHAFT_PIN_HOLE_PROCESS.split("\n")
    height = 0.0035
    char_w, line_h = 0.8 * height, 1.7 * height
    x0, y0 = drawing.PINION_PIN_NOTE_XY
    right = x0 + char_w * max(map(len, lines))
    bottom = y0 - line_h * len(lines)
    field_x0, field_y0, field_x1, field_y1 = drawing.PINION_PIN_NOTE_FIELD
    assert field_x0 == pytest.approx(drawing.HOLE_CALLOUT_XY[0] + 0.032)
    assert field_x1 == pytest.approx(drawing.ISO_CENTER[0] - 0.012)
    assert field_y1 < 0.2667
    assert field_x0 < x0 and right < field_x1
    assert y0 <= field_y1
    assert bottom > field_y0
    # Every diameter under the note's span keeps its text below the note.
    for name, (dx, dy) in drawing.DIAMETER_POSITIONS.items():
        if dx > x0 - 0.030:
            assert bottom > dy + 0.010, name


def test_note_text_is_shifted_into_its_field_from_the_measured_box() -> None:
    # run1b-e7fd1a2ec: the note's extent INCLUDES its leader, whose tip sits on
    # the hole below the field floor, so the text is placed from its own box.
    field = (0.26, 0.17, 0.378, 0.2657)
    margin = drawing.NOTE_FIELD_MARGIN
    inside = (0.30, 0.235, 0.35, 0.25)
    assert drawing._shift_into_field(inside, field, margin) == (0.0, 0.0)
    dx, dy = drawing._shift_into_field((0.30, 0.24, 0.35, 0.2665), field, margin)
    assert dx == 0.0 and dy == pytest.approx(0.2657 - margin - 0.2665)
    dx, dy = drawing._shift_into_field((0.25, 0.20, 0.30, 0.21), field, margin)
    assert dx == pytest.approx(0.26 + margin - 0.25) and dy == 0.0
    dx, dy = drawing._shift_into_field((0.34, 0.165, 0.39, 0.18), field, margin)
    assert dx == pytest.approx(0.378 - margin - 0.39)
    assert dy == pytest.approx(0.17 + margin - 0.165)
    with pytest.raises(RuntimeError, match="over by 0.0020 wide"):
        drawing._shift_into_field((0.26, 0.20, 0.378 + 0.0, 0.21), field, margin)


def test_leader_tip_is_the_point_nearest_the_hole_and_must_land_on_it() -> None:
    window = drawing.PINION_PIN_HOLE_WINDOW
    centre = ((window[0] + window[2]) / 2.0, (window[1] + window[3]) / 2.0)
    assert centre[0] == pytest.approx(drawing.PINION_PIN_X)
    assert centre[1] == pytest.approx(drawing.SIDE_CENTER[1])
    # run1b's measured tip, 3.0 mm below the axis on the 2:1 sheet, is on it.
    tip_y = drawing.SIDE_CENTER[1] - 0.00301
    leader = (0.3004, 0.2472, 0.0, drawing.PINION_PIN_X - 0.001, tip_y, 0.0)
    tip = drawing._leader_tip(leader, centre)
    assert tip == (drawing.PINION_PIN_X - 0.001, tip_y)
    assert drawing._inside(tip, window)
    assert not drawing._inside((drawing.PINION_PIN_X, 0.20), window)
    with pytest.raises(RuntimeError, match="no leader points"):
        drawing._leader_tip((), centre)


def test_shaft_length_is_unilateral_and_printed_from_the_model() -> None:
    # The dome-side Depth band carries the hub-air stack through the seat
    # collar's station, so the length only comes out short, and the model's
    # Depth carries the band.
    assert spec.SHAFT_LENGTH_BAND == (0.0, -spec.SHAFT_LENGTH_SHORT_MM)
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Shaft", "Depth", *deviations(SHAFT_LENGTH_BAND)' in build
    assert "Depth" in spec.DRAWING_DIMENSIONS["Shaft"]
    assert "Depth" not in spec.REFERENCE_DIMENSIONS


def test_shaft_band_ruling_holds_because_the_general_tolerance_closes_the_hub_air() -> None:
    # RULING W15-SHAFT-BAND (machinist review of f0c105531 flagged the band as
    # over-specified): the unilateral +0/-0.4 is functional.  The seat face
    # prints from the far end, so the shaft's band moves it against the hub
    # set flush with the dome root; at the title block's .X +/-0.8 the 0.7
    # hub-to-sprocket air closes.
    import build_dt_drive_train_assembly as bdt

    assert spec.SHAFT_LENGTH_BAND == (0.0, -spec.SHAFT_LENGTH_SHORT_MM)
    # Within the printed station's rounding of the model value.
    assert spec.SEAT_COLLAR_BAND == pytest.approx(
        (
            spec.SHAFT_LENGTH_BAND[0] + spec.COLLAR_STATION_TOL,
            spec.SHAFT_LENGTH_BAND[1] - spec.COLLAR_STATION_TOL,
        ),
        abs=spec.dt_crank_pinion_spec.print_step(spec.COLLAR_STATION_PLACES, spec.UNIT) / 2.0,
    )
    assert bdt.CRANK_HUB_SPROCKET_AIR == pytest.approx(0.7)
    assert bdt.CRANK_HUB_SPROCKET_AIR_WORST == pytest.approx(
        bdt.CRANK_HUB_SPROCKET_AIR + min(spec.SEAT_COLLAR_BAND)
    )
    assert bdt.CRANK_HUB_SPROCKET_AIR_WORST > 0.0






def test_station_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880: a reference sketch owns printed dimensions but no geometry, so the
    # part saves it hidden (no assembly instance renders it) and the drawing
    # shows it per view through _drawing_hidden_sketches to import them.
    build = Path(drawing.__file__).with_name("build_dt_crankshaft.py").read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "StationReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source.replace("\r\n", "\n")
    assert "StationReference" in spec.DRAWING_DIMENSIONS


def test_far_end_rim_pick_lands_on_the_front_right_plane_lower_half() -> None:
    pick = drawing.FAR_END_FRONT_RIM_PICK
    assert pick == pytest.approx(
        (drawing.FAR_END_X, drawing._sheet_y(-spec.PINION_SEAT_DIA / 4.0))
    )
    assert drawing.FAR_END_X == pytest.approx(drawing._sheet_x(spec.SHAFT_LENGTH))
    assert drawing._sheet_y(-spec.PINION_SEAT_DIA / 2.0) < pick[1]
    assert pick[1] < drawing.SIDE_CENTER[1]
    window = drawing.FAR_END_FRONT_RIM_WINDOW
    assert window == pytest.approx(
        (pick[0] - 0.0005, pick[1] - 0.0005, pick[0] + 0.0005, pick[1] + 0.0005)
    )
    assert drawing._inside(pick, window)
    assert drawing._sheet_y(-spec.PINION_SEAT_DIA / 2.0) < window[1]
    assert window[3] < drawing.SIDE_CENTER[1]


def test_centres_note_field_clears_front_witnesses_title_block_and_caption() -> None:
    field = drawing._centres_note_field()
    x0, y0, x1, y1 = field
    assert drawing.NOTE_TEXT_GAP >= 0.0035
    assert x0 == pytest.approx(drawing.FAR_END_X + drawing.NOTE_TEXT_GAP)
    assert x0 < x1 < 0.4191  # ASME B inner border
    assert 0.065 < y0 < y1  # above the title block, including the field's floor
    assert y1 == pytest.approx(
        drawing.ISO_NOTE_XY[1] - 2.0 * 0.005 - drawing.NOTE_TEXT_GAP
    )
    assert drawing.CENTRES_NOTE_XY == (0.372, 0.093)
    assert drawing._inside(drawing.CENTRES_NOTE_XY, field)
    assert len(notes.CENTRES_NOTE.splitlines()) <= TEXT_ROW_LIMIT
    # The whole text field and landing window stay below MATCH DRILL's
    # field. These bounds constrain the intended corridor, not native ink.
    match_floor = drawing.PINION_PIN_NOTE_FIELD[1]
    assert max(y1, drawing.FAR_END_FRONT_RIM_WINDOW[3]) < match_floor
    assert drawing.CENTRES_NOTE_XY[0] > drawing.FAR_END_FRONT_RIM_PICK[0]


class _CircleEdge:
    """IEdge double whose ICurve is a circle (or a line) in model mm."""

    def __init__(
        self, centre_mm: tuple[float, float, float], radius_mm: float, *, circle: bool = True
    ) -> None:
        self.curve = SimpleNamespace(
            IsCircle=lambda: circle,
            CircleParams=(*(c / 1000.0 for c in centre_mm), 0.0, 1.0, 0.0, radius_mm / 1000.0),
        )

    def GetCurve(self):  # noqa: N802 - the COM member name
        return self.curve


def _far_rim(**overrides) -> _CircleEdge:
    centre = overrides.pop("centre", (0.0, spec.SHAFT_LENGTH, 0.0))
    radius = overrides.pop("radius", spec.PINION_SEAT_DIA / 2.0)
    return _CircleEdge(centre, radius, **overrides)


def _front_fakes(monkeypatch: pytest.MonkeyPatch, edges: list[_CircleEdge]):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(
        drawing,
        "visible_component_entities",
        lambda view, component, kind: list(edges) if kind == 1 else [],
    )
    view = SimpleNamespace(GetVisibleComponents=lambda: ("dt-crankshaft",))
    adapter = SimpleNamespace(_attempt=lambda operation, **kwargs: operation())
    return adapter, view


def _rim_distractors() -> list[_CircleEdge]:
    # The seat step's two circles share the seat's and shank's radii at
    # SEAT_STEP; the far face's straight seam is no circle.
    return [
        _CircleEdge((0.0, spec.SEAT_STEP, 0.0), spec.PINION_SEAT_DIA / 2.0),
        _CircleEdge((0.0, spec.SEAT_STEP, 0.0), spec.SHAFT_DIA / 2.0),
        _far_rim(circle=False),
    ]


def test_far_end_rim_is_the_one_plain_end_circle(monkeypatch: pytest.MonkeyPatch) -> None:
    rim = _far_rim()
    adapter, view = _front_fakes(monkeypatch, [*_rim_distractors(), rim])
    assert drawing._far_end_rim(adapter, view) is rim


@pytest.mark.parametrize(
    "edges",
    (
        pytest.param([], id="missing"),
        pytest.param([_far_rim(), _far_rim()], id="ambiguous"),
        pytest.param([_far_rim(centre=(0.0, spec.SHAFT_LENGTH - 0.01, 0.0))], id="station"),
        pytest.param([_far_rim(radius=spec.SHAFT_DIA / 2.0)], id="radius"),
        pytest.param([_far_rim(centre=(0.01, spec.SHAFT_LENGTH, 0.0))], id="off-axis"),
    ),
)
def test_far_end_rim_refuses_a_missing_or_ambiguous_rim(
    monkeypatch: pytest.MonkeyPatch, edges: list[_CircleEdge]
) -> None:
    adapter, view = _front_fakes(monkeypatch, [*_rim_distractors(), *edges])
    with pytest.raises(RuntimeError, match="expected exactly one"):
        drawing._far_end_rim(adapter, view)


@pytest.fixture
def centres_note_fakes(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    rim = _far_rim()
    adapter, side = _front_fakes(monkeypatch, [*_rim_distractors(), rim])
    annotation = SimpleNamespace(
        SetLeader3=Mock(return_value=0), SetPosition2=Mock(return_value=True)
    )
    note = SimpleNamespace(GetAnnotation=Mock(return_value=annotation))
    prerequisites: list[str] = []
    select = Mock(side_effect=lambda *args, **kwargs: prerequisites.append("select"))

    def set_landing(*args):
        prerequisites.append("landing")
        return True

    def insert(text):
        # The exact rim and its landing must belong to the selection before
        # insertion; later leader movement cannot establish that ownership.
        assert prerequisites == ["select", "landing"]
        return note

    model = SimpleNamespace(
        SelectionManager=SimpleNamespace(SetSelectionPoint2=Mock(side_effect=set_landing)),
        InsertNote=Mock(side_effect=insert),
        ClearSelection2=Mock(),
    )
    rebuild = Mock()
    place = Mock()
    attached = Mock()
    monkeypatch.setattr(drawing, "_select_view_entity", select)
    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    monkeypatch.setattr(drawing, "_place_note_text_in_field", place)
    monkeypatch.setattr(drawing, "_assert_attached_to", attached)
    return SimpleNamespace(
        adapter=adapter, side=side, rim=rim, model=model, note=note,
        annotation=annotation, select=select, rebuild=rebuild, place=place,
        attached=attached,
    )


def test_centres_note_is_attached_to_the_far_end_rim_on_front(
    centres_note_fakes: SimpleNamespace,
) -> None:
    f = centres_note_fakes
    label = "lathe centre hole end"

    def place(*args, **kwargs):
        f.rebuild.assert_called_once_with(f.adapter, label=label)

    def attached(*args, **kwargs):
        f.place.assert_called_once_with(
            f.model, f.note, drawing._centres_note_field(),
            hole=drawing.FAR_END_FRONT_RIM_WINDOW, label=label,
        )
        f.model.ClearSelection2.assert_not_called()

    f.place.side_effect = place
    f.attached.side_effect = attached
    assert drawing._add_centres_note(f.adapter, f.model, f.side) is f.note
    f.select.assert_called_once_with(
        f.adapter, f.side, "EDGE", None, label=label, entity=f.rim
    )
    f.model.SelectionManager.SetSelectionPoint2.assert_called_once_with(
        1, -1, *drawing.FAR_END_FRONT_RIM_PICK, 0.0
    )
    f.model.InsertNote.assert_called_once_with(notes.CENTRES_NOTE)
    f.note.GetAnnotation.assert_called_once_with()
    f.annotation.SetLeader3.assert_called_once_with(1, 0, True, False, False, False)
    f.annotation.SetPosition2.assert_called_once_with(*drawing.CENTRES_NOTE_XY, 0.0)
    f.attached.assert_called_once_with(
        f.adapter, f.annotation, f.rim, entity_type="EDGE",
        what="attached note", label=label,
    )
    f.model.ClearSelection2.assert_called_once_with(True)


@pytest.mark.parametrize("result", [False, None, 1])
def test_centres_note_refuses_failed_selection_point_before_insertion(
    centres_note_fakes: SimpleNamespace, result: object,
) -> None:
    f = centres_note_fakes
    f.model.SelectionManager.SetSelectionPoint2.side_effect = None
    f.model.SelectionManager.SetSelectionPoint2.return_value = result
    with pytest.raises(RuntimeError, match="failed to set the FRONT plain-end landing"):
        drawing._add_centres_note(f.adapter, f.model, f.side)
    f.model.InsertNote.assert_not_called()
    f.rebuild.assert_not_called()
    f.place.assert_not_called()
    f.attached.assert_not_called()


def test_centres_note_refuses_missing_inserted_note(
    centres_note_fakes: SimpleNamespace,
) -> None:
    f = centres_note_fakes
    f.model.InsertNote.side_effect = None
    f.model.InsertNote.return_value = None
    with pytest.raises(RuntimeError, match="failed to insert the note"):
        drawing._add_centres_note(f.adapter, f.model, f.side)
    f.model.InsertNote.assert_called_once_with(notes.CENTRES_NOTE)
    f.note.GetAnnotation.assert_not_called()
    f.rebuild.assert_not_called()
    f.place.assert_not_called()
    f.attached.assert_not_called()


def test_centres_note_is_only_the_attached_note_and_build_places_it() -> None:
    # The unleadered general-note row is gone, not kept beside the leadered one.
    assert not hasattr(drawing, "add_note")
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    users = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and any(
            isinstance(arg, ast.Name) and arg.id == "CENTRES_NOTE"
            for arg in (*node.args, *(kw.value for kw in node.keywords))
        )
    ]
    assert [ast.unparse(node.func) for node in users] == ["drawing_model.InsertNote"]
    (build,) = [
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    ]
    placements = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "_add_centres_note"
    ]
    assert len(placements) == 1
    assert [ast.unparse(arg) for arg in placements[0].args] == [
        "adapter",
        "drawing_model",
        "side",
    ]
    assert placements[0].keywords == []


class _FreshNeckView:
    """Counted native view with an observable, potentially refused transition."""

    def __init__(self) -> None:
        self.GetDimensionCount4 = Mock(return_value=0)
        self.GetAnnotationCount = Mock(return_value=0)
        self.GetAnnotations = Mock(return_value=None)
        self.mode = True
        self.transition_readback = False
        self.writes = []
        self.ScaleRatio = (2.0, 1.0)
        self.ScaleDecimal = 2.0

    @property
    def ProjectedDimensions(self):
        return self.mode

    @ProjectedDimensions.setter
    def ProjectedDimensions(self, value):
        self.writes.append(value)
        self.mode = self.transition_readback


@pytest.fixture
def fresh_neck_view(monkeypatch: pytest.MonkeyPatch) -> _FreshNeckView:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    return _FreshNeckView()


@pytest.mark.parametrize("array", [None, (), []])
def test_fresh_neck_view_initializes_only_after_both_native_empty_inventories(
    fresh_neck_view: _FreshNeckView, array: object,
) -> None:
    view = fresh_neck_view
    view.GetAnnotations.return_value = array
    trace = Mock()
    for name in ("GetDimensionCount4", "GetAnnotationCount", "GetAnnotations"):
        trace.attach_mock(getattr(view, name), name)
    drawing._initialize_neck_true_measurements(view)
    assert trace.mock_calls == [
        call.GetDimensionCount4(), call.GetAnnotationCount(), call.GetAnnotations(),
    ]
    assert view.writes == [False]
    assert view.ProjectedDimensions is False


def test_fresh_neck_view_retains_automatic_non_dimension_marks(
    fresh_neck_view: _FreshNeckView,
) -> None:
    view = fresh_neck_view
    note = SimpleNamespace(GetType=Mock(return_value=6))
    view.GetAnnotationCount.return_value = 1
    view.GetAnnotations.return_value = (note,)
    drawing._initialize_neck_true_measurements(view)
    assert view.writes == [False]
    note.GetType.assert_called_once_with()
    assert view.GetAnnotations.return_value == (note,)


@pytest.mark.parametrize("count", [None, False, True, -1, 1, 0.0, "0", 2147483648, Mock()])
def test_fresh_neck_view_refuses_invalid_or_populated_dimension_count_before_setter(
    fresh_neck_view: _FreshNeckView, count: object,
) -> None:
    view = fresh_neck_view
    view.GetDimensionCount4.return_value = count
    with pytest.raises(RuntimeError, match="expected native dimension count 0"):
        drawing._initialize_neck_true_measurements(view)
    assert view.writes == []
    view.GetAnnotationCount.assert_not_called()


@pytest.mark.parametrize("count", [None, False, True, -1, 0.0, "0", 2147483648, Mock()])
def test_fresh_neck_view_refuses_invalid_annotation_count_before_setter(
    fresh_neck_view: _FreshNeckView, count: object,
) -> None:
    view = fresh_neck_view
    view.GetAnnotationCount.return_value = count
    with pytest.raises(RuntimeError, match="invalid native annotation count"):
        drawing._initialize_neck_true_measurements(view)
    assert view.writes == []
    view.GetAnnotations.assert_not_called()


@pytest.mark.parametrize(
    "count, array",
    [
        (1, None), (0, False), (0, 0), (0, ""), (0, {}),
        (1, ()), (0, (None,)), (1, (None,)),
    ],
)
def test_fresh_neck_view_refuses_null_malformed_or_mismatched_annotation_arrays(
    fresh_neck_view: _FreshNeckView, count: int, array: object,
) -> None:
    view = fresh_neck_view
    view.GetAnnotationCount.return_value = count
    view.GetAnnotations.return_value = array
    with pytest.raises(RuntimeError, match="native annotation"):
        drawing._initialize_neck_true_measurements(view)
    assert view.writes == []


@pytest.mark.parametrize(
    "kind", [None, False, True, 4.0, "4", -2147483649, 2147483648, Mock(), 4]
)
def test_fresh_neck_view_refuses_invalid_types_or_a_type_four_dimension_before_setter(
    fresh_neck_view: _FreshNeckView, kind: object,
) -> None:
    view = fresh_neck_view
    view.GetAnnotationCount.return_value = 1
    view.GetAnnotations.return_value = (SimpleNamespace(GetType=Mock(return_value=kind)),)
    with pytest.raises(RuntimeError, match="annotation type|type-4 dimension exists"):
        drawing._initialize_neck_true_measurements(view)
    assert view.writes == []


@pytest.mark.parametrize("member", ["GetDimensionCount4", "GetAnnotationCount", "GetAnnotations", "GetType"])
@pytest.mark.parametrize("missing", [False, True])
def test_fresh_neck_view_never_turns_an_unavailable_native_getter_into_empty_evidence(
    fresh_neck_view: _FreshNeckView, member: str, missing: bool,
) -> None:
    view = fresh_neck_view
    target = view
    if member == "GetType":
        target = SimpleNamespace(GetType=Mock(return_value=6))
        view.GetAnnotationCount.return_value = 1
        view.GetAnnotations.return_value = (target,)
    if missing:
        delattr(target, member)
        failure = AttributeError
    else:
        getattr(target, member).side_effect = RuntimeError("native inventory getter failed")
        failure = RuntimeError
    with pytest.raises(failure):
        drawing._initialize_neck_true_measurements(view)
    assert view.writes == []


@pytest.mark.parametrize("readback", [True, None, 0, 1, "", Mock()])
def test_fresh_neck_view_refuses_a_non_false_transition_readback(
    fresh_neck_view: _FreshNeckView, readback: object,
) -> None:
    view = fresh_neck_view
    view.transition_readback = readback
    with pytest.raises(RuntimeError, match="did not read back False"):
        drawing._initialize_neck_true_measurements(view)
    assert view.writes == [False]


def _neck_face(*, radius=None, stations=None, axis=(0.0, -1.0, 0.0)):
    radius = spec.SHAFT_DIA / 2000.0 if radius is None else radius
    stations = (
        spec.COLLAR_REAR / 1000.0 - 1.1e-10, spec.JOURNAL_START / 1000.0 + 9e-11
    ) if stations is None else stations
    surface = SimpleNamespace(
        IsCylinder=Mock(return_value=True),
        CylinderParams=(0.0, 0.13629999994199998, 0.0, *axis, radius),
    )
    return SimpleNamespace(
        GetSurface=Mock(return_value=surface),
        GetBox=Mock(return_value=(-radius, stations[0], -radius, radius, stations[1], radius)),
    )


def _neck_silhouette(side, face, sign):
    # Actual 81150dc3 census: lower endpoints increase in Y, upper endpoints
    # decrease. These are native MathPoints, deliberately not IVertex doubles.
    x = sign * 1.662817987624042e-17
    z = sign * spec.SHAFT_DIA / 2000.0
    points = [
        SimpleNamespace(ArrayData=(x, spec.COLLAR_REAR / 1000.0 - 1.1e-10, z)),
        SimpleNamespace(ArrayData=(x, spec.JOURNAL_START / 1000.0 + 9e-11, z)),
    ]
    if sign > 0:
        points.reverse()
    return SimpleNamespace(
        GetStartPoint=Mock(return_value=points[0]), GetEndPoint=Mock(return_value=points[1]),
        GetFace=Mock(return_value=face), GetView=Mock(return_value=side),
    )


def _native_presentation_data(lines, texts=(), arrows=()):
    """SDK-shaped mutable raw doubles, not a precomputed proof result."""
    return SimpleNamespace(
        GetLineCount=Mock(side_effect=lambda: len(lines)),
        GetLineAtIndex3=Mock(side_effect=lambda index: (0, 0, 0, 0, *lines[index])),
        GetTextCount=Mock(side_effect=lambda: len(texts)),
        GetTextAtIndex=Mock(side_effect=lambda index: texts[index]["text"]),
        GetTextPositionAtIndex=Mock(side_effect=lambda index: texts[index]["position"]),
        GetTextHeightAtIndex=Mock(side_effect=lambda index: texts[index]["height"]),
        GetTextInBoxWidthAtIndex=Mock(side_effect=lambda index: texts[index]["width"]),
        GetTextAngleAtIndex=Mock(side_effect=lambda index: texts[index].get("angle", 0.0)),
        GetTextRefPositionAtIndex=Mock(side_effect=lambda index: texts[index].get("reference", 1)),
        GetArrowHeadCount=Mock(return_value=len(arrows)),
        GetArrowHeadAtIndex2=Mock(side_effect=lambda index: arrows[index]),
    )


def _neck_presentation_pdf(
    neck_lines, neck_arrows, texts, foreign_lines, station_lines,
    finish_lines, finish_arrows, finish_texts, options,
):
    """A full raw PageInk with separately attributable glyphs, paths and heads."""
    spans = []
    for row, baseline, height in ((texts[2], 0.1930, 0.0035), (finish_texts[0], 0.2015, 0.002)):
        chars = row["text"].replace(" ", "")
        left = row["position"][0] + 0.0001
        width = (row["width"] - 0.0015) / len(chars)
        glyphs = tuple(
            Glyph(char, left + index * width, baseline, left + (index + 1) * width - 0.0001, baseline + height)
            for index, char in enumerate(chars)
        )
        spans.append(Span(chars, glyphs[0].xmin, baseline, glyphs[-1].xmax, baseline + height, glyphs))
    native_lines = [
        drawing.Segment(raw[0], raw[1], raw[3], raw[4])
        for raw in (*neck_lines, *foreign_lines, *station_lines, *finish_lines)
    ]
    native_lines.extend(
        segment for raw in (*neck_arrows, *finish_arrows) for segment in drawing.arrowhead_segments(raw)
    )
    strokes = [
        Stroke(line.x0, line.y0, line.x1, line.y1, 0.00013, (0, 0, 0), False, False, True)
        for line in native_lines
    ]
    center = texts[1]["position"][0] + texts[1]["width"] / 2.0
    points = tuple(
        (center + 0.0015 * math.cos(index * math.tau / 12),
         0.1948 + 0.0015 * math.sin(index * math.tau / 12))
        for index in range(12)
    )
    token = [
        Stroke(*first, *second, 0.00013, (0, 0, 0), False, False, True)
        for first, second in zip(points, (*points[1:], points[0]))
    ]
    token.append(Stroke(center - 0.0009, 0.19265, center + 0.0009, 0.1970, 0.00013,
                        (0, 0, 0), False, False, True))
    if hasattr(options, "mutate"):
        options.mutate(spans, strokes, token)
    strokes.extend(token)
    return PageInk(0.4318, 0.2794, tuple(glyph for span in spans for glyph in span.glyphs),
                   tuple(spans), tuple(strokes))


@pytest.fixture
def neck_dimension_fakes(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Exercise the real selection, two-entity factory and shared attachment helper."""
    for module in (drawing, edge_dimensions, selection_helpers, attachment_helpers):
        monkeypatch.setattr(module, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(
        edge_dimensions._sw_type_info, "early_bound_or_flag",
        lambda value, interface, *members: value,
    )
    monkeypatch.setattr(
        native_drawing._sw_type_info, "early_bound", lambda value, interface: value,
    )
    for module in (drawing, edge_dimensions, selection_helpers):
        monkeypatch.setattr(module, "view_name", Mock(return_value="FRONT"))
    source_face, view_face, canonical_face = _neck_face(), _neck_face(), _neck_face()
    body = SimpleNamespace(GetFaces=Mock(return_value=(source_face,)))
    canonical = Mock(side_effect=lambda face: canonical_face if face is view_face else None)
    source = SimpleNamespace(
        GetType=Mock(return_value=1), GetBodies2=Mock(return_value=(body,)),
        Extension=SimpleNamespace(GetCorrespondingEntity2=canonical),
    )
    side = SimpleNamespace(
        ReferencedDocument=source, ProjectedDimensions=False,
        ScaleRatio=(2.0, 1.0), ScaleDecimal=2.0,
        GetCorrespondingEntity=Mock(side_effect=AssertionError("no forward-map requirement")),
    )
    lower, upper = (_neck_silhouette(side, view_face, sign) for sign in (-1, 1))
    component = object()
    side.GetVisibleComponents = Mock(return_value=(component,))
    visible = Mock(return_value=[lower, upper])
    side.GetVisibleEntities2 = visible
    projection = Mock(side_effect=lambda adapter, view, points, **kwargs: [
        (drawing._sheet_x(point[1] * 1000.0), drawing._sheet_y(point[2] * 1000.0))
        for point in points
    ])
    monkeypatch.setattr(drawing, "model_points_in_view", projection)
    native = SimpleNamespace(
        SystemValue=spec.SHAFT_DIA / 1000.0, DrivenState=2,
        FullName="RD1@FRONT@Drawing1", Tolerance=SimpleNamespace(Type=4, GetMaxValue=lambda: 0.000254, GetMinValue=lambda: -0.000254, SetValues=lambda *_: True),
    )
    texts = {1: "", 2: "", 3: "", 4: ""}
    x = drawing.OUTBOARD_NECK_DIAMETER_XY[0]
    arrow_rows = [
        (x, drawing._sheet_y(sign * spec.SHAFT_DIA / 2.0), 0.0,
         0.0, float(sign), 0.0, 0.0035, 0.00075, 1.0, 0.0, 0.0, 1.0)
        for sign in (-1, 1)
    ]
    shelf_y = 0.1919951
    neck_lines = [
        (x, shelf_y, 0.0, x + 0.0143298, shelf_y, 0.0),
        (x, shelf_y, 0.0, x, drawing._sheet_y(spec.SHAFT_DIA / 2.0), 0.0),
        (x, drawing._sheet_y(-spec.SHAFT_DIA / 2.0), 0.0,
         x, drawing._sheet_y(spec.SHAFT_DIA / 2.0), 0.0),
    ]
    native_texts = [
        {"text": " ", "position": (x, shelf_y + 0.0000535, 0.0), "height": 0.0035, "width": 0.0012931},
        {"text": "<MOD-DIAM>", "position": (x + 0.0012931, shelf_y, 0.0), "height": 0.0035, "width": 0.0052784},
        {"text": ".375 ", "position": (x + 0.0065715, shelf_y + 0.0000535, 0.0), "height": 0.0035, "width": 0.0077583},
        {"text": "<MOD-PM>.010", "position": (x + 0.0143298, shelf_y + 0.0000535, 0.0), "height": 0.0035, "width": 0.006},
    ]
    arrow_data = _native_presentation_data(neck_lines, native_texts, arrow_rows)
    display = SimpleNamespace(
        Type2=12, ShowParenthesis=True, ShowDimensionValue=True,
        GetDimension2=Mock(return_value=native), SetPrecision3=Mock(return_value=0),
        GetPrimaryPrecision2=Mock(return_value=spec.NECK_DIA_PLACES),
        GetOverride=Mock(return_value=False), GetText=Mock(side_effect=lambda part: texts[part]),
        SetText=Mock(side_effect=lambda part, value: texts.__setitem__(part, value)),
        GetDisplayData=Mock(return_value=arrow_data),
    )
    annotation = SimpleNamespace(
        name="RD1", OwnerType=0, Owner=side, GetType=Mock(return_value=4),
        GetSpecificAnnotation=Mock(return_value=display),
        GetAttachedEntities3=Mock(return_value=(lower, upper)),
        GetAttachedEntityCount3=Mock(return_value=2),
        GetAttachedEntityTypes=Mock(return_value=(46, 46)),
        IsDangling=Mock(return_value=False), GetLeaderCount=Mock(return_value=0),
    )
    display.GetAnnotation = Mock(return_value=annotation)
    right_native = SimpleNamespace(
        SystemValue=spec.SHAFT_DIA / 1000.0, DrivenState=2,
        FullName="NeckDiaDim@PinionSeatProfile@dt-crankshaft", Tolerance=SimpleNamespace(Type=4, GetMaxValue=lambda: 0.000254, GetMinValue=lambda: -0.000254, SetValues=lambda *_: True),
    )
    right_texts = {1: "<MOD-DIAM>", 2: "", 3: "", 4: ""}
    right_display = SimpleNamespace(
        Type2=6, ShowParenthesis=False, GetDimension2=Mock(return_value=right_native),
        GetPrimaryPrecision2=Mock(return_value=spec.NECK_DIA_PLACES),
        GetOverride=Mock(return_value=False), GetText=Mock(side_effect=lambda part: right_texts[part]),
    )
    # Foreign ink recorded beside the neck at 0.17753; it moves with the neck.
    dxn = x - 0.17753
    foreign_lines = [
        (0.1988 + dxn, 0.2139181, 0.0, 0.1988 + dxn, 0.191388, 0.0),
        (0.1797 + dxn, 0.191388, 0.0, 0.1998 + dxn, 0.191388, 0.0),
    ]
    right_display.GetDisplayData = Mock(return_value=_native_presentation_data(foreign_lines))
    right_annotation = SimpleNamespace(
        name="NeckDiaDim", OwnerType=0, Owner=side, GetType=Mock(return_value=4),
        GetSpecificAnnotation=Mock(return_value=right_display),
    )
    station_native = SimpleNamespace(
        SystemValue=0.0, DrivenState=0, FullName="Depth@Stations@dt-crankshaft",
    )
    station_display = SimpleNamespace(GetDimension2=Mock(return_value=station_native))
    station_lines = [(drawing.COLLAR_REAR_X, 0.179, 0.0, drawing.COLLAR_REAR_X, 0.1107219, 0.0)]
    station_display.GetDisplayData = Mock(return_value=_native_presentation_data(station_lines))
    station_annotation = SimpleNamespace(
        name="Depth", OwnerType=0, Owner=side, GetType=Mock(return_value=4),
        GetSpecificAnnotation=Mock(return_value=station_display),
    )
    preexisting_annotations = (
        SimpleNamespace(GetType=Mock(return_value=6)), right_annotation, station_annotation,
    )
    side.GetAnnotations = Mock(return_value=(*preexisting_annotations, annotation))
    side.GetAnnotationCount = Mock(side_effect=lambda: len(side.GetAnnotations()))
    selected = []
    selection = SimpleNamespace(
        CreateSelectData=Mock(side_effect=SimpleNamespace),
        GetSelectedObjectCount2=Mock(side_effect=lambda mark: len(selected)),
        GetSelectedObject6=Mock(side_effect=lambda index, mark: selected[index - 1]),
        GetSelectedObjectType3=Mock(return_value=46),
        GetSelectedObjectsDrawingView2=Mock(return_value=side),
    )

    def select(entity, append, data):
        assert data.View is side
        if not append:
            selected.clear()
        selected.append(entity)
        return True

    lower.Select2 = Mock(side_effect=lambda append, data: select(lower, append, data))
    upper.Select2 = Mock(side_effect=lambda append, data: select(upper, append, data))
    model = SimpleNamespace(
        AddVerticalDimension2=Mock(return_value=display),
        ClearSelection2=Mock(side_effect=lambda clear: selected.clear()),
        ActivateView=Mock(return_value=True), SelectionManager=selection,
        GraphicsRedraw2=Mock(),
    )
    # The factory never calls these alternatives or any coordinate-selection API.
    model.Extension = SimpleNamespace(
        AddSpecificDimension=Mock(side_effect=AssertionError("no circle/type-15 fallback")),
        SelectByID2=Mock(side_effect=AssertionError("no coordinate hit-testing")),
    )

    def same(left, right):
        if left is lower or left is upper or right is lower or right is upper:
            return 0  # native silhouette identity is NOT ISldWorks.IsSame
        if left is right:
            return 1
        if (left is source_face and right is canonical_face
                or left is canonical_face and right is source_face):
            return 1
        return 0

    adapter = SimpleNamespace(currentModel=model, swApp=SimpleNamespace(IsSame=Mock(side_effect=same)))
    rebuild = Mock()
    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, item: item.name)
    factory = Mock(wraps=drawing.add_edge_dimension)
    monkeypatch.setattr(drawing, "add_edge_dimension", factory)
    collar_face = object()
    collar_annotation = SimpleNamespace(
        GetType=Mock(return_value=8),
        GetAttachedEntities3=Mock(return_value=(collar_face,)),
        GetAttachedEntityCount3=Mock(return_value=1),
        GetAttachedEntityTypes=Mock(return_value=(2,)),  # swSelFACES
        GetLeaderCount=Mock(return_value=1), IsDangling=Mock(return_value=False),
        GetLeaderStyle=Mock(return_value=1), SetLeader3=Mock(return_value=0),
        GetSmartArrowHeadStyle=Mock(return_value=False),
        GetArrowHeadStyleAtIndex=Mock(return_value=1),  # swCLOSED_ARROWHEAD
        SetArrowHeadStyleAtIndex=Mock(return_value=0),
        GetLeaderPointsAtIndex=Mock(return_value=(
            *drawing.COLLAR_REAR_FINISH[1], 0.0, *drawing.COLLAR_REAR_FINISH[0], 0.0,
        )),
    )
    # Native symbol legs as read at the corner-landing root (0.18326, 0.1973),
    # carried with the symbol to its current root.
    dx = drawing.COLLAR_REAR_FINISH[1][0] - 0.18326
    dy = drawing.COLLAR_REAR_FINISH[1][1] - 0.1973
    finish_lines = [
        (*drawing.COLLAR_REAR_FINISH[1], 0.0, *drawing.COLLAR_REAR_FINISH[0], 0.0),
        (0.18326 + dx, 0.1973 + dy, 0.0, 0.181095 + dx, 0.20105 + dy, 0.0),
        (0.185425 + dx, 0.20105 + dy, 0.0, 0.181095 + dx, 0.20105 + dy, 0.0),
        (0.18326 + dx, 0.1973 + dy, 0.0, 0.1874735 + dx, 0.2044425 + dy, 0.0),
        (0.1847905 + dx, 0.2029118 + dy, 0.0, 0.1817295 + dx, 0.2029118 + dy, 0.0),
        (0.1874735 + dx, 0.2044425 + dy, 0.0, 0.1977225 + dx, 0.2044425 + dy, 0.0),
    ]
    finish_native_texts = [{
        "text": notes.COLLAR_REAR_FINISH_TEXT, "position": (0.18826 + dx, 0.2008713 + dy, 0.0),
        "height": 0.0025, "width": 0.0098437,
    }]
    finish_arrows = [
        (*drawing.COLLAR_REAR_FINISH[0], 0.0, *(
            root - tip for root, tip in zip(*drawing.COLLAR_REAR_FINISH[::-1])
        ), 0.0, 0.003556, 0.000762, 1.0, 0.0, 0.0, 1.0),
    ]
    finish_data = _native_presentation_data(finish_lines, finish_native_texts, finish_arrows)
    collar_annotation.GetDisplayData = Mock(return_value=finish_data)
    collar_texts = {
        8: f"Ra {drawing.surface_finish_by_key(spec.SURFACE_FINISHES, 'collar_rear_face').roughness_ra}",
    }
    collar_symbol = SimpleNamespace(
        GetSymbol=Mock(return_value=1),
        GetText=Mock(side_effect=lambda part: collar_texts[part]),
        GetAnnotation=Mock(return_value=collar_annotation),
    )
    pdf = SimpleNamespace()
    monkeypatch.setattr(drawing, "read_pdf_ink", Mock(side_effect=lambda path: [
        _neck_presentation_pdf(neck_lines, arrow_rows, native_texts, foreign_lines, station_lines,
                               finish_lines, finish_arrows, finish_native_texts, pdf),
    ]))
    return SimpleNamespace(
        adapter=adapter, model=model, side=side, component=component, source=source, body=body,
        source_face=source_face, view_face=view_face, canonical_face=canonical_face,
        canonical=canonical, lower=lower, upper=upper, visible=visible, projection=projection,
        native=native, display=display, annotation=annotation, texts=texts,
        right_native=right_native, right_display=right_display, right_texts=right_texts,
        right_annotation=right_annotation, station_native=station_native,
        station_display=station_display, station_annotation=station_annotation,
        preexisting_annotations=preexisting_annotations, selection=selection, selected=selected,
        rebuild=rebuild, factory=factory, arrow_data=arrow_data, arrow_rows=arrow_rows,
        native_tolerance=native.Tolerance, right_tolerance=right_native.Tolerance,
        collar_face=collar_face, collar_symbol=collar_symbol,
        collar_annotation=collar_annotation, collar_texts=collar_texts,
        neck_lines=neck_lines, native_texts=native_texts, foreign_lines=foreign_lines,
        station_lines=station_lines, finish_lines=finish_lines, finish_arrows=finish_arrows,
        finish_data=finish_data, finish_native_texts=finish_native_texts, pdf=pdf,
        preexisting=(
            (right_native, right_native.FullName, spec.SHAFT_DIA / 1000.0, 2, right_annotation),
            (station_native, station_native.FullName, 0.0, 0, station_annotation),
        ),
    )


def test_neck_resolver_binds_visible_entities_to_actual_view_and_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the owned resolver through the real SDK helper and raw-fetch chain."""
    events = []

    class NotAView:
        def __getattr__(self, name):
            if name in ("ReferencedDocument", "GetVisibleComponents", "GetVisibleEntities2"):
                raise AssertionError(f"{type(self).__name__} cannot receive IView.{name}")
            raise AttributeError(name)

    class Component(NotAView):
        pass

    class Adapter(NotAView):
        pass

    components = (Component(), Component())

    class View:
        def GetVisibleComponents(self):
            assert self is view
            events.append(("components", self))
            return components

        def GetVisibleEntities2(self, component, kind):
            assert self is view
            assert type(kind) is int and kind == 4
            assert component is components[0] or component is components[1]
            events.append(("entities", self, component, kind))
            # Flat native entity arrays; never (component, entities) pairs.
            return (lower,) if component is components[0] else (upper,)

    view = View()
    source_face, view_face = _neck_face(), _neck_face()
    body = SimpleNamespace(GetFaces=Mock(return_value=(source_face,)))
    canonical = Mock(side_effect=lambda face: source_face if face is view_face else None)
    extension = SimpleNamespace(GetCorrespondingEntity2=canonical)
    source = SimpleNamespace(
        GetType=Mock(return_value=1), GetBodies2=Mock(return_value=(body,)),
        Extension=extension,
    )
    view.ReferencedDocument = source
    lower, upper = (_neck_silhouette(view, view_face, sign) for sign in (-1, 1))
    adapter = Adapter()
    adapter.swApp = SimpleNamespace(IsSame=Mock(side_effect=lambda left, right: int(left is right)))
    allowed = {
        "IView": (view,), "IModelDoc2": (source,), "IPartDoc": (source,),
        "IBody2": (body,), "IFace2": (source_face, view_face),
        "ISurface": (source_face.GetSurface.return_value, view_face.GetSurface.return_value),
        "IModelDocExtension": (extension,), "ISilhouetteEdge": (lower, upper),
        "IMathPoint": (
            lower.GetStartPoint.return_value, lower.GetEndPoint.return_value,
            upper.GetStartPoint.return_value, upper.GetEndPoint.return_value,
        ),
    }
    bindings = []

    def bind(value, interface):
        assert any(value is candidate for candidate in allowed[interface]), (
            f"wrong receiver for {interface}: {type(value).__name__}"
        )
        bindings.append((value, interface))
        return value

    def project(actual_adapter, actual_view, points, *, label):
        assert actual_adapter is adapter
        assert actual_view is view
        assert label == "collar-side neck source"
        return [
            (drawing._sheet_x(point[1] * 1000.0), drawing._sheet_y(point[2] * 1000.0))
            for point in points
        ]

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(native_drawing._sw_type_info, "early_bound", bind)
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    # Neither visible_component_entities nor raw_visible_entities is replaced.
    # The pre-fix adapter/view argument swap therefore fails receiver binding.
    assert drawing.visible_component_entities is native_drawing.visible_component_entities
    physical, pair = drawing._outboard_neck_silhouettes(adapter, view)
    assert physical is source_face
    assert pair[0] is lower and pair[1] is upper
    assert events == [
        ("components", view),
        ("entities", view, components[0], 4),
        ("entities", view, components[1], 4),
    ]
    assert all(receiver is view for receiver, interface in bindings if interface == "IView")
    assert canonical.call_args_list == [call(view_face), call(view_face)]


def _create_neck_dimension(f):
    saved_annotations = f.side.GetAnnotations.return_value
    f.side.GetAnnotations.side_effect = lambda: (
        saved_annotations if f.model.AddVerticalDimension2.called else f.preexisting_annotations
    )
    return drawing._add_outboard_neck_dimension(
        f.adapter, f.model, f.side, f.collar_face, f.collar_symbol,
    )


_NECK_PHASES = (
    "after insertion rebuild", "final settling rebuild", "after_drawing_save", "after_pdf_save",
)


def _neck_proof(f, phase):
    if phase == "before factory":
        return _create_neck_dimension(f)
    f.native.DrivenState = 1
    f.display.ShowParenthesis = False
    f.texts[1] = "<MOD-DIAM>"
    return drawing._outboard_neck_checkpoint(
        f.adapter, f.side, f.native, 2, f.preexisting,
        f.collar_face, f.collar_symbol, phase,
    )


def _neck_result(operation, value):
    operation.side_effect = None
    operation.return_value = value


@pytest.mark.parametrize("native_type", [2, 12])
@pytest.mark.parametrize("right_state", [1, 2])
def test_opposite_neck_factory_measures_native_full_width_with_symbol_only(
    neck_dimension_fakes, native_type, right_state,
) -> None:
    f = neck_dimension_fakes
    f.display.Type2 = native_type
    f.right_native.DrivenState = right_state
    before = vars(f.right_native).copy()

    def factory(x, y, z):
        assert (x, y, z) == (*drawing.OUTBOARD_NECK_DIAMETER_XY, 0.0)
        assert f.selected == [f.lower, f.upper]
        assert f.native.DrivenState == 2
        f.display.SetText.assert_not_called()
        f.display.SetPrecision3.assert_not_called()
        return f.display

    f.model.AddVerticalDimension2.side_effect = factory
    identity, state, preexisting = _create_neck_dimension(f)
    assert identity is f.native and state == right_state
    assert preexisting[0] == (
        f.right_native, before["FullName"], before["SystemValue"],
        before["DrivenState"], f.right_annotation,
    )
    assert preexisting[1] == f.preexisting[1]
    assert f.native.SystemValue == pytest.approx(0.009525, abs=1e-12)
    assert f.native.DrivenState == 1
    assert vars(f.right_native) == before
    f.display.SetText.assert_called_once_with(1, "<MOD-DIAM>")
    f.display.SetPrecision3.assert_called_once_with(spec.DRAWING_REFERENCE_PRECISION["OutboardNeckDia"], -1, -1, -1)
    assert f.display.ShowParenthesis is False
    assert f.display.ShowDimensionValue is True
    f.factory.assert_called_once()
    kwargs = f.factory.call_args.kwargs
    assert kwargs["orientation"] == "vertical"
    assert kwargs["entities"] == (f.lower, f.upper)
    assert kwargs["entity_types"] == ("SILHOUETTE", "SILHOUETTE")
    assert [item.args[0] for item in f.lower.Select2.call_args_list] == [False, False]
    assert [item.args[0] for item in f.upper.Select2.call_args_list] == [False, True]
    assert f.adapter.swApp.IsSame(f.source_face, f.view_face) == 0
    assert f.adapter.swApp.IsSame(f.view_face, f.source_face) == 0
    f.adapter.swApp.IsSame.assert_any_call(f.source_face, f.canonical_face)
    f.adapter.swApp.IsSame.assert_any_call(f.canonical_face, f.source_face)
    f.source.GetBodies2.assert_called_with(-1, False)
    f.side.GetVisibleComponents.assert_called_with()
    f.visible.assert_called_with(f.component, 4)
    f.model.Extension.AddSpecificDimension.assert_not_called()
    f.model.Extension.SelectByID2.assert_not_called()
    f.side.GetCorrespondingEntity.assert_not_called()
    f.rebuild.assert_called_once_with(f.adapter, label="collar-side neck")
    f.model.GraphicsRedraw2.assert_called_once_with()


@pytest.mark.parametrize("phase", ("before factory", *_NECK_PHASES))
@pytest.mark.parametrize("failure", [
    "wrong-station", "wrong-radius", "off-normal", "missing-upper", "duplicate-lower",
    "wrong-source-radius", "wrong-source-station", "wrong-axis", "nonunit-axis",
    "wrong-view-face", "different-face", "null-canonical", "equal-geometry-foreign-source",
    "canonical-forward-zero", "canonical-reverse-zero", "face-forward-zero", "face-reverse-zero",
])
def test_neck_geometry_and_inverse_identity_refuse_at_every_boundary(
    neck_dimension_fakes, phase, failure,
) -> None:
    f = neck_dimension_fakes
    if failure in ("wrong-station", "wrong-radius", "off-normal"):
        point = f.lower.GetStartPoint.return_value
        x, y, z = point.ArrayData
        point.ArrayData = {
            "wrong-station": (x, y + 0.001, z),
            "wrong-radius": (x, y, -spec.JOURNAL_DIA / 2000.0),
            "off-normal": (0.001, y, z),
        }[failure]
    elif failure in ("missing-upper", "duplicate-lower"):
        f.visible.return_value = (
            [f.lower] if failure == "missing-upper" else [f.lower, f.lower, f.upper]
        )
    elif failure.startswith("wrong-source"):
        replacement = _neck_face(
            radius=spec.JOURNAL_DIA / 2000.0 if failure.endswith("radius") else None,
            stations=(spec.JOURNAL_END / 1000.0, spec.SEAT_STEP / 1000.0)
            if failure.endswith("station") else None,
        )
        f.body.GetFaces.return_value = (replacement,)
    elif failure in ("wrong-axis", "nonunit-axis"):
        surface = f.source_face.GetSurface.return_value
        surface.CylinderParams = (
            *surface.CylinderParams[:3],
            *((1.0, 0.0, 0.0) if failure == "wrong-axis" else (0.0, 0.5, 0.0)),
            surface.CylinderParams[6],
        )
    elif failure == "wrong-view-face":
        f.upper.GetFace.return_value = _neck_face(radius=spec.JOURNAL_DIA / 2000.0)
    elif failure == "different-face":
        another = _neck_face()
        f.upper.GetFace.return_value = another
        f.canonical.side_effect = lambda face: f.canonical_face
    elif failure in ("null-canonical", "equal-geometry-foreign-source"):
        _neck_result(f.canonical, None if failure == "null-canonical" else _neck_face())
    elif failure.startswith("canonical-"):
        same = f.adapter.swApp.IsSame.side_effect
        pair = (
            (f.canonical_face, f.source_face) if failure == "canonical-forward-zero"
            else (f.source_face, f.canonical_face)
        )
        f.adapter.swApp.IsSame.side_effect = (
            lambda left, right: 0 if left is pair[0] and right is pair[1] else same(left, right)
        )
    else:
        another = _neck_face()
        f.upper.GetFace.return_value = another
        f.canonical.side_effect = lambda face: f.canonical_face
        same = f.adapter.swApp.IsSame.side_effect
        rejected = (
            (f.view_face, another) if failure == "face-forward-zero" else (another, f.view_face)
        )
        f.adapter.swApp.IsSame.side_effect = lambda left, right: (
            0 if left is rejected[0] and right is rejected[1]
            else 1 if left is f.view_face and right is another or left is another and right is f.view_face
            else same(left, right)
        )
    with pytest.raises(RuntimeError):
        _neck_proof(f, phase)
    f.model.AddVerticalDimension2.assert_not_called()
    f.display.SetText.assert_not_called()
    f.display.SetPrecision3.assert_not_called()
    f.side.GetCorrespondingEntity.assert_not_called()


@pytest.mark.parametrize("phase", ("before factory", *_NECK_PHASES))
@pytest.mark.parametrize("failure", ["axis", "normal", "separation", "missing", "nonfinite"])
def test_neck_requires_actual_native_projection_not_predicted_sheet_math(
    neck_dimension_fakes, phase, failure,
) -> None:
    f = neck_dimension_fakes
    project = f.projection.side_effect

    def drift(*args, **kwargs):
        points = project(*args, **kwargs)
        if failure == "missing":
            return points[:-1]
        index = {"axis": 1, "normal": 5, "separation": 2, "nonfinite": 0}[failure]
        x, y = points[index]
        points[index] = (float("nan"), y) if failure == "nonfinite" else (x + 0.001, y)
        return points

    f.projection.side_effect = drift
    with pytest.raises(RuntimeError, match="projection|geometry"):
        _neck_proof(f, phase)
    f.model.AddVerticalDimension2.assert_not_called()


@pytest.mark.parametrize("source", [None, ""])
def test_neck_requires_referenced_physical_source(neck_dimension_fakes, source) -> None:
    f = neck_dimension_fakes
    f.side.ReferencedDocument = source
    with pytest.raises(RuntimeError, match="no referenced source"):
        _create_neck_dimension(f)
    f.model.AddVerticalDimension2.assert_not_called()


@pytest.mark.parametrize("kind", [None, True, "1", 0, 2, 3])
def test_neck_requires_part_source(neck_dimension_fakes, kind) -> None:
    f = neck_dimension_fakes
    f.source.GetType.return_value = kind
    with pytest.raises(RuntimeError, match="not a part"):
        _create_neck_dimension(f)
    f.source.GetBodies2.assert_not_called()


@pytest.mark.parametrize("failure", ["no-bodies", "null-body", "no-faces", "null-face", "duplicate-face"])
def test_neck_requires_unique_complete_physical_face_inventory(neck_dimension_fakes, failure) -> None:
    f = neck_dimension_fakes
    if failure == "no-bodies":
        f.source.GetBodies2.return_value = ()
    elif failure == "null-body":
        f.source.GetBodies2.return_value = (f.body, None)
    else:
        f.body.GetFaces.return_value = {
            "no-faces": (), "null-face": (None,), "duplicate-face": (f.source_face, f.source_face),
        }[failure]
    with pytest.raises(RuntimeError):
        _create_neck_dimension(f)
    f.model.AddVerticalDimension2.assert_not_called()


@pytest.mark.parametrize("target,member", [
    ("source", "GetBodies2"), ("body", "GetFaces"), ("canonical", None),
    ("lower", "GetStartPoint"), ("lower", "GetFace"), ("lower", "GetView"),
    ("selection", "GetSelectedObjectsDrawingView2"),
])
def test_neck_does_not_suppress_native_geometry_or_mapping_errors(neck_dimension_fakes, target, member) -> None:
    f = neck_dimension_fakes
    operation = getattr(f, target) if member is None else getattr(getattr(f, target), member)
    operation.side_effect = RuntimeError("native geometry access failed")
    with pytest.raises(RuntimeError, match="native geometry access failed"):
        _create_neck_dimension(f)
    f.model.AddVerticalDimension2.assert_not_called()


@pytest.mark.parametrize("target,member,value", [
    ("model", "ActivateView", False), ("lower", "Select2", False),
    ("upper", "Select2", False), ("selection", "GetSelectedObjectCount2", True),
    ("selection", "GetSelectedObjectCount2", 0), ("selection", "GetSelectedObjectCount2", 2),
    ("selection", "GetSelectedObject6", None), ("selection", "GetSelectedObjectType3", 1),
    ("selection", "GetSelectedObjectType3", 46.0),
    ("selection", "GetSelectedObjectsDrawingView2", None),
    ("selection", "GetSelectedObjectsDrawingView2", SimpleNamespace(name="FRONT")),
])
def test_neck_refuses_unqualified_real_selection_before_factory(neck_dimension_fakes, target, member, value) -> None:
    f = neck_dimension_fakes
    _neck_result(getattr(getattr(f, target), member), value)
    with pytest.raises(RuntimeError):
        _create_neck_dimension(f)
    f.model.AddVerticalDimension2.assert_not_called()
    f.display.SetText.assert_not_called()


@pytest.mark.parametrize("phase", ("before factory", *_NECK_PHASES))
@pytest.mark.parametrize("failure", ["missing", "foreign", "forward-zero", "reverse-zero"])
def test_neck_requires_front_owner_in_both_native_identity_directions(neck_dimension_fakes, phase, failure) -> None:
    f = neck_dimension_fakes
    owner = SimpleNamespace(name="FRONT")
    if failure in ("missing", "foreign"):
        owner = None if failure == "missing" else owner
    else:
        same = f.adapter.swApp.IsSame.side_effect
        f.adapter.swApp.IsSame.side_effect = lambda left, right: (
            0 if failure == "forward-zero" and left is owner and right is f.side
            or failure == "reverse-zero" and left is f.side and right is owner
            else 1 if left is owner and right is f.side or left is f.side and right is owner
            else same(left, right)
        )
    if phase == "before factory":
        f.selection.GetSelectedObjectsDrawingView2.return_value = owner
    else:
        f.annotation.Owner = owner
    with pytest.raises(RuntimeError, match="owner is not FRONT"):
        _neck_proof(f, phase)
    f.model.AddVerticalDimension2.assert_not_called()


@pytest.mark.parametrize("value", [0.01905, 0.0047625, 0.0095, -0.009525, None, False, True, float("nan"), float("inf")])
def test_neck_immediate_native_value_precedes_every_state_or_presentation_write(neck_dimension_fakes, value) -> None:
    f = neck_dimension_fakes
    events = []

    class ImmediateDimension:
        @property
        def SystemValue(self):
            events.append("value")
            return value

        @property
        def DrivenState(self):
            return 2

        @DrivenState.setter
        def DrivenState(self, state):
            raise AssertionError("state written before native value qualified")

    f.display.GetDimension2.return_value = ImmediateDimension()
    with pytest.raises(RuntimeError, match="immediate native value"):
        _create_neck_dimension(f)
    assert events == ["value"]
    f.display.SetText.assert_not_called()
    f.display.SetPrecision3.assert_not_called()
    assert f.display.ShowParenthesis is True
    f.rebuild.assert_not_called()


@pytest.mark.parametrize("kind", [6, 15, 11, 5, None, False, "12"])
def test_neck_factory_refuses_non_linear_types_without_fallback(neck_dimension_fakes, kind) -> None:
    f = neck_dimension_fakes
    f.display.Type2 = kind
    with pytest.raises(RuntimeError, match="not linear"):
        _create_neck_dimension(f)
    f.display.SetText.assert_not_called()
    assert f.native.DrivenState == 2
    f.model.Extension.AddSpecificDimension.assert_not_called()


@pytest.mark.parametrize("missing", ["display", "native"])
def test_neck_factory_requires_real_native_objects(neck_dimension_fakes, missing) -> None:
    f = neck_dimension_fakes
    if missing == "display":
        f.model.AddVerticalDimension2.return_value = None
    else:
        f.display.GetDimension2.return_value = None
    with pytest.raises(RuntimeError, match="failed to add|no native IDimension"):
        _create_neck_dimension(f)
    f.display.SetText.assert_not_called()
    f.rebuild.assert_not_called()


@pytest.mark.parametrize("status", [-1, 1, 2, 3, 4, None, False])
def test_neck_refuses_precision_assignment_status(neck_dimension_fakes, status) -> None:
    f = neck_dimension_fakes
    f.display.SetPrecision3.return_value = status
    with pytest.raises(RuntimeError, match="precision assignment failed"):
        _create_neck_dimension(f)
    f.rebuild.assert_not_called()


def test_neck_requires_symbol_prefix_readback(neck_dimension_fakes) -> None:
    f = neck_dimension_fakes
    f.display.SetText.side_effect = None
    with pytest.raises(RuntimeError, match="symbol prefix did not persist"):
        _create_neck_dimension(f)
    f.rebuild.assert_not_called()


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("failure", [
    "duplicate-lower", "extra", "missing", "null", "wrong-type", "count", "dangling",
    "foreign-face", "wrong-endpoint",
])
def test_neck_requires_exactly_both_opposite_attached_silhouettes(neck_dimension_fakes, phase, failure) -> None:
    f = neck_dimension_fakes
    attached = {
        "duplicate-lower": (f.lower, f.lower), "extra": (f.lower, f.upper, f.upper),
        "missing": (f.lower,), "null": (f.lower, None),
    }
    if failure in attached:
        f.annotation.GetAttachedEntities3.return_value = attached[failure]
    elif failure == "wrong-type":
        f.annotation.GetAttachedEntityTypes.return_value = (1, 46)
    elif failure == "count":
        f.annotation.GetAttachedEntityCount3.return_value = 3
    elif failure == "dangling":
        f.annotation.IsDangling.return_value = True
    else:
        replacement = _neck_silhouette(f.side, f.view_face, 1)
        if failure == "foreign-face":
            replacement.GetFace.return_value = _neck_face()
        else:
            replacement.GetStartPoint.return_value.ArrayData = (0.0, spec.JOURNAL_END / 1000.0, spec.SHAFT_DIA / 2000.0)
        f.annotation.GetAttachedEntities3.return_value = (f.lower, replacement)
    with pytest.raises(RuntimeError):
        _neck_proof(f, phase)
    f.display.SetText.assert_not_called()


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("target,member,value,message", [
    ("display", "Type2", 6, "display type"),
    ("display", "Type2", 15, "display type"),
    ("native", "SystemValue", 0.01905, "measures"),
    ("native", "SystemValue", None, "finite native"),
    ("native", "DrivenState", 2, "native driven state"),
    ("display", "GetPrimaryPrecision2", 2, "primary places"),
    ("display", "GetPrimaryPrecision2", True, "primary places"),
    ("native_tolerance", "Type", 2, "explicit tolerance"),
    ("native_tolerance", "Type", False, "explicit tolerance"),
    ("native_tolerance", "Type", 0.0, "explicit tolerance"),
    ("display", "GetOverride", True, "overridden"),
    ("display", "ShowParenthesis", True, "overridden"),
    ("display", "ShowDimensionValue", False, "value is hidden"),
    ("annotation", "OwnerType", 1, "owner is not FRONT"),
    ("right_display", "GetPrimaryPrecision2", 2, "primary places"),
    ("right_native", "SystemValue", 0.0095, "measures"),
    ("right_native", "DrivenState", 1, "native driven state"),
    ("right_tolerance", "Type", 2, "explicit tolerance"),
    ("right_display", "GetOverride", True, "overridden"),
    ("right_display", "ShowParenthesis", True, "overridden"),
])
def test_neck_reacquired_native_size_band_and_state_are_checked_at_all_four_proofs(
    neck_dimension_fakes, phase, target, member, value, message,
) -> None:
    f = neck_dimension_fakes
    _neck_proof(f, phase)
    obj = getattr(f, target)
    old = getattr(obj, member)
    if isinstance(old, Mock):
        _neck_result(old, value)
    else:
        setattr(obj, member, value)
    # Do not use _neck_proof here: it intentionally prepares the positive new state.
    with pytest.raises(RuntimeError, match=message):
        drawing._assert_outboard_neck_dimension(f.adapter, f.side, f.native, 2, f.preexisting, phase=phase)
    f.rebuild.assert_not_called()


@pytest.mark.parametrize("neck", ["new", "right"])
@pytest.mark.parametrize("part,text", [(1, "Ø9.5"), (1, "(<MOD-DIAM>"), (2, ")"), (3, "2X"), (4, "REF")])
def test_neither_neck_accepts_numeric_text_quantity_or_reference_decoration(neck_dimension_fakes, neck, part, text) -> None:
    f = neck_dimension_fakes
    _neck_proof(f, "final settling rebuild")
    (f.texts if neck == "new" else f.right_texts)[part] = text
    with pytest.raises(RuntimeError, match="unexpected native diameter text"):
        drawing._outboard_neck_checkpoint(
            f.adapter, f.side, f.native, 2, f.preexisting,
            f.collar_face, f.collar_symbol, "after_pdf_save",
        )


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("drift", ["value", "state", "null-value", "bool-state", "missing", "extra", "replacement", "wrong-live-name"])
def test_full_preexisting_inventory_cannot_drift_at_any_normal_proof(neck_dimension_fakes, phase, drift) -> None:
    f = neck_dimension_fakes
    if drift in ("value", "state", "null-value", "bool-state"):
        member, value = {
            "value": ("SystemValue", 0.000001), "state": ("DrivenState", 1),
            "null-value": ("SystemValue", None), "bool-state": ("DrivenState", False),
        }[drift]
        setattr(f.station_native, member, value)
    elif drift == "missing":
        f.side.GetAnnotations.return_value = (f.right_annotation, f.annotation)
    elif drift == "extra":
        extra = SimpleNamespace(
            name="Extra",
            GetType=lambda: 4, GetSpecificAnnotation=lambda: SimpleNamespace(
                GetDimension2=lambda index: SimpleNamespace(FullName="Extra", SystemValue=0.0, DrivenState=0),
            ),
        )
        f.side.GetAnnotations.return_value = (*f.side.GetAnnotations.return_value, extra)
    else:
        replacement = SimpleNamespace(**vars(f.station_native))
        f.station_display.GetDimension2.return_value = replacement
        if drift == "wrong-live-name":
            replacement.FullName = "Wrong@Stations@dt-crankshaft"
            same = f.adapter.swApp.IsSame.side_effect
            f.adapter.swApp.IsSame.side_effect = lambda left, right: (
                1 if left is replacement and right is f.station_native
                or left is f.station_native and right is replacement else same(left, right)
            )
    with pytest.raises(RuntimeError, match="preexisting"):
        _neck_proof(f, phase)


@pytest.mark.parametrize("member,value", [
    ("SystemValue", None), ("SystemValue", False), ("SystemValue", "0"), ("SystemValue", float("nan")),
    ("DrivenState", None), ("DrivenState", False), ("DrivenState", 0.0), ("DrivenState", 2147483648),
    ("FullName", None), ("FullName", ""),
])
def test_full_preexisting_inventory_is_captured_strictly_before_factory(neck_dimension_fakes, member, value) -> None:
    f = neck_dimension_fakes
    setattr(f.station_native, member, value)
    with pytest.raises(RuntimeError, match="preexisting"):
        _create_neck_dimension(f)
    f.model.AddVerticalDimension2.assert_not_called()


@pytest.mark.parametrize("count", [1, 8, 32])
def test_preexisting_inventory_reads_each_current_and_live_reference_name_once_per_checkpoint(
    count,
) -> None:
    class NativeDimension:
        def __init__(self, key):
            self.key = key
            self.name = f"Dim{key}@FRONT@Drawing1"
            self.name_reads = 0
            self.SystemValue = key / 1000.0
            self.DrivenState = 0

        @property
        def FullName(self):
            self.name_reads += 1
            return self.name

    references = [NativeDimension(index) for index in range(count)]
    natives = [NativeDimension(index) for index in range(count)]
    owner = object()
    annotations = [SimpleNamespace(Owner=owner, OwnerType=0) for _ in references]
    preexisting = tuple(
        (reference, reference.name, reference.SystemValue, reference.DrivenState, annotation)
        for reference, annotation in zip(references, annotations)
    )
    current = [
        (annotation, object(), native) for annotation, native in zip(annotations, natives)
    ]
    adapter = SimpleNamespace(swApp=SimpleNamespace(
        IsSame=Mock(side_effect=lambda left, right: int(left.key == right.key)),
    ))
    titles = ("Drawing1", "Drawing1", "dt-crankshaft.SLDDRW", "Renamed.SLDDRW")
    for checkpoint, (phase, title) in enumerate(zip(_NECK_PHASES, titles), 1):
        for native in (*references, *natives):
            native.name = f"Dim{native.key}@FRONT@{title}"
        drawing._assert_preexisting_neck_inventory(
            adapter, current, preexisting, label=phase,
        )
        assert [native.name_reads for native in natives] == [checkpoint] * count
        assert [reference.name_reads for reference in references] == [checkpoint] * count
        assert adapter.swApp.IsSame.call_count == 2 * count * checkpoint


@pytest.mark.parametrize(
    "failure", [None, "duplicate-native", "forward-zero", "reverse-zero"],
    ids=["distinct-identities-same-name", "duplicate-native", "forward-zero", "reverse-zero"],
)
def test_preexisting_name_index_retains_duplicate_rows_and_bidirectional_identity(failure) -> None:
    owner = object()
    annotations = [SimpleNamespace(Owner=owner, OwnerType=0) for _ in range(2)]
    references = [
        SimpleNamespace(
            key=index, FullName="Shared@FRONT@Drawing1", SystemValue=index / 1000.0, DrivenState=0,
        )
        for index in range(2)
    ]
    natives = [SimpleNamespace(**vars(reference)) for reference in references]
    if failure == "duplicate-native":
        natives[1] = natives[0]

    def same(left, right):
        if failure == "forward-zero" and left is natives[0] and right is references[0]:
            return 0
        if failure == "reverse-zero" and left is references[0] and right is natives[0]:
            return 0
        return int(left.key == right.key)

    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=Mock(side_effect=same)))
    current = [
        (annotation, object(), native) for annotation, native in zip(annotations, natives)
    ]
    preexisting = tuple(
        (reference, reference.FullName, reference.SystemValue, reference.DrivenState, annotation)
        for reference, annotation in zip(references, annotations)
    )
    if failure is None:
        drawing._assert_preexisting_neck_inventory(
            adapter, current, preexisting, label="duplicate names",
        )
        for native, reference in zip(natives, references):
            adapter.swApp.IsSame.assert_any_call(native, reference)
            adapter.swApp.IsSame.assert_any_call(reference, native)
    else:
        with pytest.raises(RuntimeError, match="expected one preserved preexisting dimension") as exc:
            drawing._assert_preexisting_neck_inventory(
                adapter, current, preexisting, label="duplicate names",
            )
        assert "expected_native_rows=" in str(exc.value)
        assert "current_native_rows=" in str(exc.value)
        assert isinstance(exc.value.__cause__, RuntimeError)


@pytest.mark.parametrize("phase", _NECK_PHASES)
def test_neck_and_all_preexisting_references_follow_live_saved_full_names(neck_dimension_fakes, phase) -> None:
    f = neck_dimension_fakes
    identity, state, preexisting = _create_neck_dimension(f)
    f.native.FullName = "RD1@FRONT@dt-crankshaft.SLDDRW"
    f.station_native.FullName = "Depth@Stations@dt-crankshaft.SLDDRW"
    drawing._assert_outboard_neck_dimension(f.adapter, f.side, identity, state, preexisting, phase=phase)
    assert f.station_native.SystemValue == 0.0 and f.station_native.DrivenState == 0


@pytest.mark.parametrize("member,value", [("SystemValue", 0.000001), ("DrivenState", 1)])
def test_factory_cannot_change_any_old_dimension(neck_dimension_fakes, member, value) -> None:
    f = neck_dimension_fakes

    def factory(*args):
        setattr(f.station_native, member, value)
        return f.display

    f.model.AddVerticalDimension2.side_effect = factory
    with pytest.raises(RuntimeError, match="preexisting dimension .* changed value/state"):
        _create_neck_dimension(f)
    f.rebuild.assert_called_once()


@pytest.mark.parametrize("phase", ("crankshaft SIDE after angle rebuild", *_NECK_PHASES))
@pytest.mark.parametrize("mode", [True, None, 0, 1, "", Mock()])
def test_neck_true_mode_is_read_only_after_empty_initialization(neck_dimension_fakes, phase, mode) -> None:
    f = neck_dimension_fakes
    f.side.ProjectedDimensions = mode
    with pytest.raises(RuntimeError, match="ProjectedDimensions must remain False"):
        if phase == "crankshaft SIDE after angle rebuild":
            drawing._assert_neck_measurement_domain(f.side, label=phase)
        else:
            _neck_proof(f, phase)
    assert f.side.ProjectedDimensions is mode
    f.model.GraphicsRedraw2.assert_not_called()


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("member,value", [
    ("ScaleRatio", None), ("ScaleRatio", (2.0,)), ("ScaleRatio", (1.0, 1.0)),
    ("ScaleRatio", (4.0, 2.0)), ("ScaleRatio", (2.0, True)),
    ("ScaleDecimal", None), ("ScaleDecimal", True), ("ScaleDecimal", 1.0),
])
def test_neck_scale_is_never_measurement_compensation(neck_dimension_fakes, phase, member, value) -> None:
    f = neck_dimension_fakes
    setattr(f.side, member, value)
    with pytest.raises(RuntimeError, match="native scale must remain 2:1 / 2"):
        _neck_proof(f, phase)
    assert getattr(f.side, member) == value


@pytest.mark.parametrize("failure", [
    "inside-not-flank", "journal", "collar", "one-flank-twice", "not-same-x",
    "nonvertical", "zero-direction", "wrong-normal", "malformed", "nonfinite",
])
def test_native_full_width_arrow_readback_requires_both_actual_physical_flanks(neck_dimension_fakes, failure) -> None:
    f = neck_dimension_fakes
    row = list(f.arrow_rows[0])
    if failure == "inside-not-flank":
        row[1] = drawing.SIDE_CENTER[1]
    elif failure == "journal":
        row[0] = drawing.JOURNAL_START_X + 0.001
    elif failure == "collar":
        row[0] = drawing.COLLAR_REAR_X - 0.001
    elif failure == "one-flank-twice":
        row[1] = f.arrow_rows[1][1]
    elif failure == "not-same-x":
        row[0] += 2.0 * drawing.NECK_ARROW_LANDING_TOLERANCE_M
    elif failure == "nonvertical":
        row[3] = 1.0
    elif failure == "zero-direction":
        row[3:6] = [0.0, 0.0, 0.0]
    elif failure == "wrong-normal":
        row[9:12] = [1.0, 0.0, 0.0]
    elif failure == "malformed":
        row.pop()
    else:
        row[0] = float("nan")
    f.arrow_rows[0] = tuple(row)
    with pytest.raises(RuntimeError):
        drawing._assert_neck_arrow_landing(f.display, label="neck")


@pytest.mark.parametrize("count", [0, 1, 3, -1, None, False])
def test_full_width_dimension_requires_exactly_two_native_arrowheads(neck_dimension_fakes, count) -> None:
    f = neck_dimension_fakes
    f.arrow_data.GetArrowHeadCount.return_value = count
    with pytest.raises(RuntimeError, match="two readable"):
        drawing._assert_neck_arrow_landing(f.display, label="neck")


def test_neck_accepts_only_declared_small_arrow_readback_roundoff(neck_dimension_fakes) -> None:
    f = neck_dimension_fakes
    offset = drawing.NECK_ARROW_LANDING_TOLERANCE_M / 2.0
    f.arrow_rows[:] = [
        (row[0] + offset, row[1] + offset, *row[2:]) for row in f.arrow_rows
    ]
    drawing._assert_neck_arrow_landing(f.display, label="neck")


def test_neck_redraw_precedes_arrow_readback_without_extra_rebuild(neck_dimension_fakes) -> None:
    f = neck_dimension_fakes
    events = []
    f.model.GraphicsRedraw2.side_effect = lambda: events.append("redraw")
    f.display.GetDisplayData.side_effect = lambda: (events.append("display"), f.arrow_data)[1]
    _create_neck_dimension(f)
    assert events == ["redraw", "display"]
    f.rebuild.assert_called_once()


def test_neck_redraw_failure_is_not_suppressed(neck_dimension_fakes) -> None:
    f = neck_dimension_fakes
    f.model.GraphicsRedraw2.side_effect = RuntimeError("native redraw failed")
    with pytest.raises(RuntimeError, match="native redraw failed"):
        _create_neck_dimension(f)
    f.display.GetDisplayData.assert_not_called()


def test_neck_reacquires_display_after_insertion_rebuild(neck_dimension_fakes) -> None:
    f = neck_dimension_fakes

    def drift(*args, **kwargs):
        replacement = SimpleNamespace(**vars(f.display))
        replacement.GetPrimaryPrecision2 = Mock(return_value=2)
        f.annotation.GetSpecificAnnotation.return_value = replacement

    f.rebuild.side_effect = drift
    with pytest.raises(RuntimeError, match="primary places"):
        _create_neck_dimension(f)


@pytest.mark.parametrize("failure", ["new-missing", "new-duplicate", "right-missing", "no-specific", "identity-replaced"])
def test_neck_requires_both_original_and_exact_new_native_view_dimensions(neck_dimension_fakes, failure) -> None:
    f = neck_dimension_fakes
    if failure == "new-missing":
        f.side.GetAnnotations.return_value = f.preexisting_annotations
    elif failure == "new-duplicate":
        f.side.GetAnnotations.return_value = (*f.side.GetAnnotations.return_value, f.annotation)
    elif failure == "right-missing":
        f.side.GetAnnotations.return_value = (f.annotation, f.station_annotation)
    elif failure == "no-specific":
        f.annotation.GetSpecificAnnotation.return_value = None
    else:
        f.display.GetDimension2.return_value = SimpleNamespace(**vars(f.native))
    with pytest.raises(RuntimeError, match="expected one|no native display"):
        _neck_proof(f, "after_drawing_save")


@pytest.mark.parametrize("phase", _NECK_PHASES)
def test_neck_checkpoint_uses_only_existing_rebuild_and_post_save_boundaries(
    neck_dimension_fakes, monkeypatch, phase,
) -> None:
    f = neck_dimension_fakes
    verify = Mock(wraps=drawing._assert_outboard_neck_dimension)
    monkeypatch.setattr(drawing, "_assert_outboard_neck_dimension", verify)
    _neck_proof(f, phase)
    verify.assert_called_once_with(f.adapter, f.side, f.native, 2, f.preexisting, phase=phase)
    f.collar_symbol.GetAnnotation.assert_called_once_with()
    f.collar_annotation.GetLeaderPointsAtIndex.assert_called_with(0)
    for unused in ("before_drawing_save", "before_pdf_save", "before_drawing_close", "after_drawing_close"):
        drawing._outboard_neck_checkpoint(
            f.adapter, f.side, f.native, 2, f.preexisting,
            f.collar_face, f.collar_symbol, unused,
        )
    verify.assert_called_once()
    f.collar_symbol.GetAnnotation.assert_called_once()
    f.model.GraphicsRedraw2.assert_called_once_with()
    f.rebuild.assert_not_called()


def test_build_retains_empty_init_full_inventory_and_all_four_normal_proofs() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(item for item in tree.body if isinstance(item, ast.AsyncFunctionDef) and item.name == "build")
    calls = [item for item in ast.walk(build) if isinstance(item, ast.Call)]
    assert sum(ast.unparse(item.func) == "_add_outboard_neck_dimension" for item in calls) == 1
    finalizer = next(item for item in calls if ast.unparse(item.func) == "finalize_drawing")
    keywords = {item.arg: item.value for item in finalizer.keywords}
    for key, function in (("settled_checks", "_outboard_neck_checkpoint"), ("checkpoint", "_outboard_neck_checkpoint")):
        assert function in ast.unparse(keywords[key])
        assert "preexisting_side_dimensions" in ast.unparse(keywords[key])
    initialization = next(
        index for index, item in enumerate(build.body)
        if isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
        and ast.unparse(item.value.func) == "_initialize_neck_true_measurements"
    )
    assert ast.unparse(build.body[initialization - 1]) == "native_side = _early_bound(side, 'IView')"
    assert ast.unparse(build.body[initialization + 1]) == "native_side.Angle = SIDE_VIEW_ANGLE"
    angle_rebuild = next(
        index for index, item in enumerate(build.body)
        if isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
        and ast.unparse(item.value.func) == "drawing_model.EditRebuild3"
    )
    assert ast.unparse(build.body[angle_rebuild + 1].value.func) == "_assert_neck_measurement_domain"
    imports = [
        index for index, item in enumerate(build.body)
        if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call)
        and ast.unparse(item.value.func) == "curate_view_dimensions"
    ]
    assert imports and all(index > angle_rebuild for index in imports)
    added = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == "_add_outboard_neck_dimension")
    writes = [
        target.attr for item in ast.walk(added) if isinstance(item, ast.Assign)
        for target in item.targets if isinstance(target, ast.Attribute)
    ]
    assert writes == ["DrivenState", "ShowParenthesis"]
    source = ast.unparse(added)
    assert "AddSpecificDimension" not in source and "Diametric" not in source
    assert not hasattr(drawing, "_outboard_neck_rim")
    assert not hasattr(drawing, "_assert_outboard_neck_view_rim")


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("index", [0, 1], ids=["lower", "upper"])
@pytest.mark.parametrize("boundary", ["left", "right"])
@pytest.mark.parametrize(
    "overhang", [1e-6, 0.0002], ids=["below-tip-tolerance", "visible-crossing"],
)
def test_neck_rejects_full_head_crossing_physical_x_trim_with_tip_inside(
    neck_dimension_fakes, phase, index, boundary, overhang,
) -> None:
    f = neck_dimension_fakes
    row = list(f.arrow_rows[index])
    x0, _y0, x1, _y1 = drawing.OUTBOARD_NECK_ARROW_WINDOW
    inset = row[7] / 2.0 - overhang
    row[0] = x0 + inset if boundary == "left" else x1 - inset
    assert x0 < row[0] < x1
    f.arrow_rows[index] = tuple(row)
    with pytest.raises(RuntimeError, match="complete native arrowhead X envelope"):
        _neck_proof(f, phase)


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("field", [6, 7], ids=["width-along", "height-across"])
@pytest.mark.parametrize("value", [0.0, -0.001, None, False, float("nan"), float("inf")])
def test_neck_requires_positive_finite_native_head_dimensions(
    neck_dimension_fakes, phase, field, value,
) -> None:
    f = neck_dimension_fakes
    row = list(f.arrow_rows[0])
    row[field] = value
    f.arrow_rows[0] = tuple(row)
    with pytest.raises(RuntimeError, match="arrowhead"):
        _neck_proof(f, phase)


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("inside", [False, True], ids=["outside", "inside"])
def test_neck_records_actual_normalized_head_bounds_and_positive_x_clearance(
    neck_dimension_fakes, monkeypatch, phase, inside,
) -> None:
    f = neck_dimension_fakes
    for index, native in enumerate(f.arrow_rows):
        row = list(native)
        row[4] *= -7.0 if inside else 7.0
        f.arrow_rows[index] = tuple(row)
    telemetry = Mock()
    monkeypatch.setattr(drawing._telemetry, "info", telemetry)
    _neck_proof(f, phase)
    message = next(
        item.args[0] for item in telemetry.call_args_list if "head_bounds_m=" in item.args[0]
    )
    bounds = ast.literal_eval(re.search(r"head_bounds_m=(.*), min_physical", message).group(1))
    for row, actual in zip(f.arrow_rows, bounds):
        base_y = row[1] + math.copysign(row[6], row[4])
        assert actual == pytest.approx((
            row[0] - row[7] / 2.0, min(row[1], base_y),
            row[0] + row[7] / 2.0, max(row[1], base_y),
        ))
    clearance = float(message.split("min_physical_x_clearance_mm=")[1])
    expected = (
        drawing.JOURNAL_START_X - f.arrow_rows[0][0] - f.arrow_rows[0][7] / 2.0
    ) * 1000.0
    assert clearance == pytest.approx(expected)
    assert clearance > 0.0
    assert phase in message


@pytest.mark.parametrize("boundary", ["left", "right"])
def test_neck_head_envelope_uses_native_width_along_small_actual_direction(
    neck_dimension_fakes, boundary,
) -> None:
    f = neck_dimension_fakes
    row = list(f.arrow_rows[0])
    ux = drawing.NECK_ARROW_DIRECTION_X_SLACK / 2.0
    uy = math.sqrt(1.0 - ux * ux)
    sign = -1.0 if boundary == "left" else 1.0
    row[3:6] = (sign * ux * 3.0, -uy * 3.0, 0.0)
    edge = drawing.COLLAR_REAR_X if boundary == "left" else drawing.JOURNAL_START_X
    # Height alone would fit: native along-direction width crosses the exact trim.
    row[0] = edge - sign * (uy * row[7] / 2.0 + ux * row[6] / 2.0)
    f.arrow_rows[0] = tuple(row)
    with pytest.raises(RuntimeError, match="complete native arrowhead X envelope"):
        drawing._assert_neck_arrow_landing(f.display, label="native small direction")


@pytest.mark.parametrize("boundary", ["left", "right"])
@pytest.mark.parametrize(
    "clearance", [5e-9, -5e-9], ids=["tiny-inside", "tiny-outside"],
)
def test_neck_head_trim_reuses_raw_shared_segments_without_dump_quantization(
    neck_dimension_fakes, monkeypatch, boundary, clearance,
) -> None:
    f = neck_dimension_fakes
    for index, native in enumerate(f.arrow_rows):
        row = list(native)
        row[0] = (
            drawing.COLLAR_REAR_X + row[7] / 2.0 + clearance
            if boundary == "left"
            else drawing.JOURNAL_START_X - row[7] / 2.0 - clearance
        )
        f.arrow_rows[index] = tuple(row)
    shared_geometry = Mock(wraps=drawing.arrowhead_segments)
    monkeypatch.setattr(drawing, "arrowhead_segments", shared_geometry)
    telemetry = Mock()
    monkeypatch.setattr(drawing._telemetry, "info", telemetry)
    if clearance < 0.0:
        with pytest.raises(RuntimeError, match="complete native arrowhead X envelope"):
            drawing._assert_neck_arrow_landing(f.display, label="raw trim")
        assert shared_geometry.call_count == 1
    else:
        drawing._assert_neck_arrow_landing(f.display, label="raw trim")
        assert shared_geometry.call_count == 2
        message = telemetry.call_args.args[0]
        actual_clearance = float(message.split("min_physical_x_clearance_mm=")[1])
        assert actual_clearance == pytest.approx(clearance * 1000.0, abs=1e-10)
        assert actual_clearance > 0.0
    for index, actual in enumerate(shared_geometry.call_args_list):
        assert actual.args == (f.arrow_rows[index],)


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("failure", [
    "missing-symbol", "missing-face", "null-annotation", "wrong-symbol-type", "bool-symbol-type",
    "wrong-roughness", "no-attachment", "duplicate-attachment", "count-mismatch",
    "wrong-entity-type", "foreign-face", "native-identity-zero", "dangling",
    "no-leader", "extra-leader", "unreadable-leader", "nonfinite-leader", "moved-tip",
    "smart-arrowhead", "dot-arrowhead", "dot-head-record",
])
def test_collar_rear_finish_refuses_native_identity_spec_or_leader_drift_at_all_four_proofs(
    neck_dimension_fakes, phase, failure,
) -> None:
    f = neck_dimension_fakes
    annotation = f.collar_annotation
    if failure == "missing-symbol":
        f.collar_symbol = None
    elif failure == "missing-face":
        f.collar_face = None
    elif failure == "null-annotation":
        f.collar_symbol.GetAnnotation.return_value = None
    elif failure in ("wrong-symbol-type", "bool-symbol-type"):
        f.collar_symbol.GetSymbol.return_value = 0 if failure == "wrong-symbol-type" else True
    elif failure == "wrong-roughness":
        f.collar_texts[8] = "Ra 99"
    elif failure == "no-attachment":
        annotation.GetAttachedEntities3.return_value = ()
        annotation.GetAttachedEntityCount3.return_value = 0
    elif failure == "duplicate-attachment":
        annotation.GetAttachedEntities3.return_value = (f.collar_face, f.collar_face)
        annotation.GetAttachedEntityCount3.return_value = 2
    elif failure == "count-mismatch":
        annotation.GetAttachedEntityCount3.return_value = 0
    elif failure == "wrong-entity-type":
        annotation.GetAttachedEntityTypes.return_value = (1,)  # swSelEDGES: the rim
    elif failure == "foreign-face":
        annotation.GetAttachedEntities3.return_value = (object(),)
    elif failure == "native-identity-zero":
        same = f.adapter.swApp.IsSame.side_effect
        f.adapter.swApp.IsSame.side_effect = lambda left, right: (
            0 if left is f.collar_face and right is f.collar_face else same(left, right)
        )
    elif failure == "dangling":
        annotation.IsDangling.return_value = True
    elif failure == "smart-arrowhead":
        annotation.GetSmartArrowHeadStyle.return_value = True
    elif failure == "dot-arrowhead":
        annotation.GetArrowHeadStyleAtIndex.return_value = 3  # swDOT_ARROWHEAD
    elif failure == "dot-head-record":
        f.finish_arrows[0] = (*f.finish_arrows[0][:8], 3.0, *f.finish_arrows[0][9:])
    elif failure in ("no-leader", "extra-leader"):
        annotation.GetLeaderCount.return_value = 0 if failure == "no-leader" else 2
    elif failure == "unreadable-leader":
        annotation.GetLeaderPointsAtIndex.return_value = ()
    else:
        points = list(annotation.GetLeaderPointsAtIndex.return_value)
        points[-3] = float("nan") if failure == "nonfinite-leader" else points[-3] + 0.0015
        annotation.GetLeaderPointsAtIndex.return_value = tuple(points)
    with pytest.raises(RuntimeError):
        _neck_proof(f, phase)
    f.rebuild.assert_not_called()
    assert f.model.GraphicsRedraw2.call_count == 1


@pytest.mark.parametrize("roughness_um", [0.8, 1.6, 3.2])
def test_collar_rear_finish_expected_text_follows_part_owned_control(
    monkeypatch, roughness_um,
) -> None:
    from dataclasses import replace
    import runpy

    from _surface_finish import ra

    control = drawing.surface_finish_by_key(spec.SURFACE_FINISHES, "collar_rear_face")
    assert notes.COLLAR_REAR_FINISH_TEXT == f"Ra {control.roughness_ra}"
    assert drawing.COLLAR_REAR_FINISH_TEXT == notes.COLLAR_REAR_FINISH_TEXT
    controls = tuple(
        replace(item, roughness_um=roughness_um) if item.key == control.key else item
        for item in spec.SURFACE_FINISHES
    )
    monkeypatch.setattr(spec, "SURFACE_FINISHES", controls)
    contract = runpy.run_path(notes.__file__)
    assert contract["COLLAR_REAR_FINISH_TEXT"] == f"Ra {ra(roughness_um, unit=spec.UNIT)}"


@pytest.mark.parametrize("phase", _NECK_PHASES)
def test_collar_rear_finish_records_actual_native_spec_identity_and_last_point_tip(
    neck_dimension_fakes, monkeypatch, phase,
) -> None:
    f = neck_dimension_fakes
    assert f.collar_texts[8] == notes.COLLAR_REAR_FINISH_TEXT
    points = list(f.collar_annotation.GetLeaderPointsAtIndex.return_value)
    points[2] = 0.0103  # actual root Z is not the physical tip, which remains last
    f.collar_annotation.GetLeaderPointsAtIndex.return_value = tuple(points)
    f.finish_lines[0] = tuple(points)
    telemetry = Mock()
    monkeypatch.setattr(drawing._telemetry, "info", telemetry)
    _neck_proof(f, phase)
    message = next(
        item.args[0] for item in telemetry.call_args_list if "native_symbol_type=" in item.args[0]
    )
    actual = ast.literal_eval(re.search(r"leader_points_m=(.*), actual_tip_m=", message).group(1))
    assert actual == tuple(points)
    assert ast.literal_eval(re.search(r"actual_tip_m=(.*), requested_tip_m=", message).group(1)) == tuple(points[-3:])
    assert "same_face=1" in message
    assert f"native_roughness={notes.COLLAR_REAR_FINISH_TEXT!r}" in message
    assert phase in message
    f.adapter.swApp.IsSame.assert_any_call(f.collar_face, f.collar_face)
    f.collar_symbol.GetText.assert_called_once_with(8)
    f.rebuild.assert_not_called()
    assert f.model.GraphicsRedraw2.call_count == 1


@pytest.mark.parametrize(
    "failure", [None, "unexpected-dimension", "bool-status", "float-status", "negative-status", "null-status", "arrow-status", *_NECK_PHASES],
    ids=["preserves-preexisting-callout", "rejects-unexpected-dimension", "bool-status", "float-status", "negative-status", "null-status", "arrow-status", *_NECK_PHASES],
)
def test_build_neck_snapshot_follows_existing_native_annotation_authoring(
    neck_dimension_fakes, monkeypatch: pytest.MonkeyPatch, failure: str | None,
) -> None:
    """Run the real neck/finish proofs and refuse physical landing drift at each phase."""
    f = neck_dimension_fakes
    events = []
    live_annotations = []
    if failure in ("bool-status", "float-status", "negative-status", "null-status"):
        f.collar_annotation.SetLeader3.return_value = {
            "bool-status": False, "float-status": 0.0, "negative-status": -1, "null-status": None,
        }[failure]
    elif failure == "arrow-status":
        f.collar_annotation.SetArrowHeadStyleAtIndex.return_value = -3  # smart style still on

    def drift_finish(phase):
        if failure == phase:
            points = list(f.collar_annotation.GetLeaderPointsAtIndex.return_value)
            points[-3] += 0.0015  # same edge, but outside the unchanged 1 mm landing bound
            f.collar_annotation.GetLeaderPointsAtIndex.return_value = tuple(points)

    f.rebuild.side_effect = lambda *args, **kwargs: drift_finish("after insertion rebuild")
    end, iso = object(), object()
    callout_native = SimpleNamespace(
        FullName="NativeCrossHole@FRONT@Drawing1", SystemValue=0.003, DrivenState=1,
    )
    callout_display = SimpleNamespace(
        GetDimension2=Mock(return_value=callout_native),
        GetDisplayData=Mock(return_value=_native_presentation_data(f.station_lines)),
    )
    callout_annotation = SimpleNamespace(
        name="NativeCrossHole", OwnerType=0, Owner=f.side, GetType=Mock(return_value=4),
        GetSpecificAnnotation=Mock(return_value=callout_display),
    )
    callout_display.GetAnnotation = Mock(return_value=callout_annotation)
    f.side.GetDimensionCount4 = Mock(return_value=0)
    f.side.GetAnnotations.side_effect = lambda: tuple(live_annotations)
    f.side.GetAnnotationCount.side_effect = lambda: len(live_annotations)
    f.model.EditRebuild3 = Mock(return_value=True)

    async def open_model(path):
        events.append("open")
        return True

    f.adapter.open_model = open_model
    monkeypatch.setattr(drawing, "SOURCE", SimpleNamespace(is_file=lambda: True))
    monkeypatch.setattr(drawing, "check", lambda label, result: None)
    monkeypatch.setattr(
        drawing, "read_required_properties",
        lambda *args, **kwargs: {"Pinion Pin Hole Process": drawing.CRANKSHAFT_PIN_HOLE_PROCESS},
    )
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *args, **kwargs: (f.model, object()))
    monkeypatch.setattr(drawing, "place_view", Mock(side_effect=(end, f.side, iso)))
    initialize = drawing._initialize_neck_true_measurements

    def initialize_empty(view):
        assert view is f.side
        assert live_annotations == []
        events.append("empty-init")
        initialize(view)

    monkeypatch.setattr(drawing, "_initialize_neck_true_measurements", initialize_empty)

    def curate(adapter, view, **kwargs):
        if view is end:
            return [SimpleNamespace(name=name) for name in drawing.END_PIN_KEEP]
        assert view is f.side and "empty-init" in events
        events.append("side-import")
        live_annotations.extend(f.preexisting_annotations)
        return [f.right_annotation, f.station_annotation]

    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "REFERENCE_DIMENSIONS", set())

    def hole_callout(adapter, view, **kwargs):
        if view is f.side:
            assert kwargs["label"] == "tapered-pin cross-hole"
            events.append("native-cross-hole")
            live_annotations.append(callout_annotation)
        return callout_display

    monkeypatch.setattr(drawing, "add_native_hole_callout", hole_callout)
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        drawing, "add_property_linked_note",
        lambda adapter, name, *xy: events.append(f"property:{name}"),
    )
    for name in (
        "stamp_drawing_summary", "set_hidden_lines_removed", "set_dimension_callouts",
        "_set_dimension_suffixes", "assert_imported_precision", "add_view_centerline",
        "_visible_cylindrical_face", "_visible_cross_hole_edge", "_set_callout_text",
        "_drop_coaxial_step", "_band_hole_depth", "place_callout_clear", "add_attached_note",
        "_place_note_text_in_field", "_add_centres_note", "set_hole_callout_precision",
    ):
        monkeypatch.setattr(drawing, name, Mock())
    collar_rim = object()
    rim_resolver = Mock(return_value=collar_rim)
    monkeypatch.setattr(drawing, "_collar_rear_rim", rim_resolver)
    face_resolver = Mock(return_value=f.collar_face)
    monkeypatch.setattr(drawing, "_collar_rear_face", face_resolver)

    def finish(adapter, view, **kwargs):
        assert view is f.side
        events.append(f"finish:{kwargs['control'].key}")
        if kwargs["control"].key == "collar_rear_face":
            assert kwargs["entity"] is f.collar_face
            assert kwargs["entity_type"] == "FACE"
            assert "edge_entity" not in kwargs and "edge_xy" not in kwargs
            assert kwargs["leader_attach_xy"] == drawing.COLLAR_REAR_FINISH[0]
            live_annotations.append(f.collar_annotation)
            return f.collar_symbol
        return object()

    monkeypatch.setattr(drawing, "add_surface_finish", finish)

    def factory(*xyz):
        assert events[-2:] == ["property:Manufacturing Notes", "property:Isometric View Note"]
        assert any(item is callout_annotation for item in live_annotations)
        events.append("neck-factory")
        live_annotations.append(f.annotation)
        return f.display

    f.model.AddVerticalDimension2.side_effect = factory
    added = drawing._add_outboard_neck_dimension
    captured = {}

    def capture(*args):
        result = added(*args)
        captured["preexisting"] = result[2]
        return result

    monkeypatch.setattr(drawing, "_add_outboard_neck_dimension", capture)

    async def finalize(adapter, outputs, *, settled_checks, checkpoint, **kwargs):
        assert events[-1] == "neck-factory"
        if failure == "unexpected-dimension":
            foreign = SimpleNamespace(FullName="Unexpected@FRONT@Drawing1", SystemValue=0.002, DrivenState=1)
            live_annotations.append(SimpleNamespace(
                OwnerType=0, Owner=f.side, name="Unexpected", GetType=lambda: 4,
                GetSpecificAnnotation=lambda: SimpleNamespace(GetDimension2=lambda index: foreign),
            ))
        drift_finish("final settling rebuild")
        for settled in settled_checks:
            settled()
        drift_finish("after_drawing_save")
        checkpoint("after_drawing_save")
        drift_finish("after_pdf_save")
        checkpoint("after_pdf_save")
        return {"status": "fixture-finalized"}

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    if failure in ("bool-status", "float-status", "negative-status", "null-status"):
        with pytest.raises(RuntimeError, match="SetLeader3 failed"):
            asyncio.run(drawing.build(f.adapter))
        f.model.AddVerticalDimension2.assert_not_called()
        f.collar_annotation.SetLeader3.assert_called_once_with(1, 0, False, False, False, False)
        f.collar_annotation.SetArrowHeadStyleAtIndex.assert_not_called()
        return
    if failure == "arrow-status":
        with pytest.raises(RuntimeError, match="SetArrowHeadStyleAtIndex failed"):
            asyncio.run(drawing.build(f.adapter))
        f.model.AddVerticalDimension2.assert_not_called()
        f.collar_annotation.SetArrowHeadStyleAtIndex.assert_called_once_with(0, 1)
        return
    if failure == "unexpected-dimension":
        with pytest.raises(RuntimeError, match="preexisting dimension inventory missing/extra") as exc:
            asyncio.run(drawing.build(f.adapter))
        message = str(exc.value)
        assert "expected_native_rows=" in message and "current_native_rows=" in message
        assert "NativeCrossHole@FRONT@Drawing1" in message
        assert "Unexpected@FRONT@Drawing1" in message
        assert "owner_wrapper_id" in message
    elif failure in _NECK_PHASES:
        with pytest.raises(RuntimeError, match="leader attachment moved") as exc:
            asyncio.run(drawing.build(f.adapter))
        assert f"({failure})" in str(exc.value)
        assert "limit=0.001 m" in str(exc.value)
        assert f.model.GraphicsRedraw2.call_count == _NECK_PHASES.index(failure) + 1
        rim_resolver.assert_called_once_with(f.adapter, f.side)
        face_resolver.assert_called_once_with(collar_rim)
        return
    else:
        assert asyncio.run(drawing.build(f.adapter)) == {"status": "fixture-finalized"}
        assert f.model.GraphicsRedraw2.call_count == 4
        rim_resolver.assert_called_once_with(f.adapter, f.side)
        face_resolver.assert_called_once_with(collar_rim)
        assert f.collar_symbol.GetAnnotation.call_count == 5
        f.collar_annotation.SetLeader3.assert_called_once_with(1, 0, False, False, False, False)
        f.collar_annotation.SetArrowHeadStyleAtIndex.assert_called_once_with(0, 1)
        f.collar_symbol.GetSymbol.assert_has_calls([call()] * 4)
        f.collar_symbol.GetText.assert_has_calls([call(8)] * 4)
        assert events.index("finish:collar_rear_face") < events.index("neck-factory")
    snapshot = captured["preexisting"]
    assert len(snapshot) == 3
    assert snapshot[2][0] is callout_native and snapshot[2][4] is callout_annotation
    assert snapshot[2][1:4] == ("NativeCrossHole@FRONT@Drawing1", 0.003, 1)
    assert all(record[0] is not f.native for record in snapshot)
    assert callout_native.SystemValue == 0.003 and callout_native.DrivenState == 1
    assert events.index("empty-init") < events.index("side-import")
    assert events.index("native-cross-hole") < events.index("neck-factory")


def test_preexisting_inventory_receipt_uses_actual_native_rows(neck_dimension_fakes) -> None:
    f = neck_dimension_fakes
    foreign_native = SimpleNamespace(FullName="ActualUnexpected@FRONT@Drawing1", SystemValue=0.0, DrivenState=0)
    foreign_owner = object()
    foreign_annotation = SimpleNamespace(OwnerType=0, Owner=foreign_owner)
    current = [
        (f.right_annotation, f.right_display, f.right_native),
        (f.station_annotation, f.station_display, f.station_native),
        (foreign_annotation, object(), foreign_native),
    ]
    with pytest.raises(RuntimeError, match="preexisting dimension inventory missing/extra") as exc:
        drawing._assert_preexisting_neck_inventory(f.adapter, current, f.preexisting, label="receipt")
    message = str(exc.value)
    assert "expected_native_rows=" in message and "current_native_rows=" in message
    assert f.right_native.FullName in message and f.station_native.FullName in message
    assert foreign_native.FullName in message
    assert hex(id(f.side)) in message and hex(id(foreign_owner)) in message
    assert isinstance(exc.value.__cause__, RuntimeError)
    assert str(exc.value.__cause__) == "receipt: preexisting dimension inventory missing/extra entries"


def test_preexisting_inventory_receipt_failure_preserves_original_refusal(
    neck_dimension_fakes,
) -> None:
    f = neck_dimension_fakes

    class UnreadableOwner:
        @property
        def Owner(self):
            raise RuntimeError("actual owner getter failed")

    baseline = ((*f.preexisting[0][:4], UnreadableOwner()),)
    with pytest.raises(RuntimeError) as exc:
        drawing._assert_preexisting_neck_inventory(f.adapter, [], baseline, label="receipt")
    assert str(exc.value) == "receipt: preexisting dimension inventory missing/extra entries"
    assert exc.value.__cause__ is None
    assert exc.value.__notes__ == [
        "receipt: preexisting inventory receipt getter failed: RuntimeError: actual owner getter failed"
    ]


@pytest.mark.parametrize("phase", ("before factory", *_NECK_PHASES))
@pytest.mark.parametrize("failure", ["missing", "foreign", "forward-zero", "reverse-zero"])
def test_neck_silhouette_itself_requires_front_owner(neck_dimension_fakes, phase, failure) -> None:
    f = neck_dimension_fakes
    owner = None if failure == "missing" else SimpleNamespace(name="FRONT")
    f.upper.GetView.return_value = owner
    if failure.endswith("zero"):
        same = f.adapter.swApp.IsSame.side_effect
        f.adapter.swApp.IsSame.side_effect = lambda left, right: (
            0 if failure == "forward-zero" and left is owner and right is f.side
            or failure == "reverse-zero" and left is f.side and right is owner
            else 1 if left is owner and right is f.side or left is f.side and right is owner
            else same(left, right)
        )
    with pytest.raises(RuntimeError, match="silhouette owner is not FRONT"):
        _neck_proof(f, phase)
    f.model.AddVerticalDimension2.assert_not_called()


@pytest.mark.parametrize("failure", ["other-flank", "wrong-station", "wrong-face"])
def test_neck_selection_readback_must_be_the_exact_requested_generatrix(neck_dimension_fakes, failure) -> None:
    f = neck_dimension_fakes
    replacement = _neck_silhouette(f.side, f.view_face, -1)
    if failure == "other-flank":
        replacement = f.upper
    elif failure == "wrong-station":
        replacement.GetStartPoint.return_value.ArrayData = (0.0, spec.JOURNAL_END / 1000.0, -spec.SHAFT_DIA / 2000.0)
    else:
        replacement.GetFace.return_value = _neck_face()
    _neck_result(f.selection.GetSelectedObject6, replacement)
    with pytest.raises(RuntimeError):
        _create_neck_dimension(f)
    f.model.AddVerticalDimension2.assert_not_called()
    f.display.SetText.assert_not_called()


@pytest.mark.parametrize("failure", ["ignored", "boolean", "unknown"])
def test_new_neck_driven_assignment_must_read_back_native_one_before_presentation(neck_dimension_fakes, failure) -> None:
    f = neck_dimension_fakes

    class RefusedDriven:
        SystemValue = 0.009525

        @property
        def DrivenState(self):
            return {"ignored": 2, "boolean": True, "unknown": 0}[failure]

        @DrivenState.setter
        def DrivenState(self, value):
            assert value == 1

    f.display.GetDimension2.return_value = RefusedDriven()
    with pytest.raises(RuntimeError, match="did not become driven"):
        _create_neck_dimension(f)
    f.display.SetText.assert_not_called()
    f.display.SetPrecision3.assert_not_called()
    f.rebuild.assert_not_called()


@pytest.mark.parametrize("phase", ("before factory", *_NECK_PHASES))
@pytest.mark.parametrize("target", ["source-surface", "view-surface", "endpoint"])
@pytest.mark.parametrize("raw", [None, (), (float("nan"),), (True,) * 7])
def test_neck_geometry_refuses_incomplete_or_non_native_arrays(neck_dimension_fakes, phase, target, raw) -> None:
    f = neck_dimension_fakes
    if target == "endpoint":
        f.upper.GetStartPoint.return_value.ArrayData = raw
    else:
        face = f.source_face if target == "source-surface" else f.view_face
        face.GetSurface.return_value.CylinderParams = raw
    with pytest.raises(RuntimeError, match="malformed native geometry"):
        _neck_proof(f, phase)
    f.model.AddVerticalDimension2.assert_not_called()


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("failure", [
    "left-shelf", "left-text", "bad-line-count", "extra-line", "null-display",
    "bad-text-count", "no-text", "null-text", "zero-width", "negative-width", "nan-width",
    "bool-height", "rotated-text", "bool-reference", "wrong-value", "foreign-route",
])
def test_native_right_advance_and_ordinary_route_refuse_actual_bad_buffers(
    neck_dimension_fakes, phase, failure,
) -> None:
    f = neck_dimension_fakes
    if failure == "left-shelf":
        row = list(f.neck_lines[0])
        row[0] -= 0.014
        f.neck_lines[0] = tuple(row)
    elif failure == "left-text":
        row = f.native_texts[1]
        row["position"] = (drawing.OUTBOARD_NECK_DIAMETER_XY[0] - 0.001, *row["position"][1:])
    elif failure == "bad-line-count":
        f.arrow_data.GetLineCount.side_effect = None
        f.arrow_data.GetLineCount.return_value = True
    elif failure == "extra-line":
        f.neck_lines.append((0.18, 0.18, 0.0, 0.181, 0.181, 0.0))
    elif failure == "null-display":
        f.display.GetDisplayData.return_value = None
    elif failure in ("bad-text-count", "no-text"):
        f.arrow_data.GetTextCount.side_effect = None
        f.arrow_data.GetTextCount.return_value = True if failure == "bad-text-count" else 0
    elif failure == "null-text":
        f.native_texts[1]["text"] = None
    elif failure in ("zero-width", "negative-width", "nan-width"):
        f.native_texts[1]["width"] = {"zero-width": 0.0, "negative-width": -0.001, "nan-width": float("nan")}[failure]
    elif failure == "bool-height":
        f.native_texts[1]["height"] = True
    elif failure == "rotated-text":
        f.native_texts[1]["angle"] = 0.01
    elif failure == "bool-reference":
        f.native_texts[1]["reference"] = True
    elif failure == "wrong-value":
        f.native_texts[2]["text"] = ".376 "
    else:
        f.foreign_lines.append((0.19, 0.191, 0.0, 0.19, 0.196, 0.0))
    with pytest.raises(RuntimeError):
        _neck_proof(f, phase)
    f.rebuild.assert_not_called()
    assert f.model.GraphicsRedraw2.call_count == 1


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("failure", [
    "bent", "bool-style", "bool-count", "nine-points", "bool-point", "null-display",
    "no-lines", "extra-line", "malformed-line", "extra-arrow", "bad-head-width", "bad-head-height",
    "bad-head-direction", "bad-head-normal", "bad-head-tip", "old-bent-root-self-cross",
])
def test_straight_finish_requires_typed_actual_native_route_and_complete_head(
    neck_dimension_fakes, phase, failure,
) -> None:
    f = neck_dimension_fakes
    if failure in ("bent", "bool-style"):
        f.collar_annotation.GetLeaderStyle.return_value = 0 if failure == "bent" else True
    elif failure == "bool-count":
        f.collar_annotation.GetLeaderCount.return_value = True
    elif failure in ("nine-points", "bool-point"):
        points = list(f.collar_annotation.GetLeaderPointsAtIndex.return_value)
        if failure == "nine-points":
            points[3:3] = [0.18, 0.1973, 0.0]
        else:
            points[2] = False
        f.collar_annotation.GetLeaderPointsAtIndex.return_value = tuple(points)
    elif failure == "null-display":
        f.collar_annotation.GetDisplayData.return_value = None
    elif failure == "no-lines":
        f.finish_lines.clear()
    elif failure == "extra-line":
        f.finish_lines.append((0.18326, 0.1973, 0.0, 0.184, 0.199, 0.0))
    elif failure == "malformed-line":
        f.finish_lines[0] = f.finish_lines[0][:-1]
    elif failure == "extra-arrow":
        f.finish_arrows.append(f.finish_arrows[0])
        f.finish_data.GetArrowHeadCount.return_value = 2
    elif failure.startswith("bad-head-"):
        row = list(f.finish_arrows[0])
        index, value = {
            "bad-head-width": (6, 0.0), "bad-head-height": (7, -0.001),
            "bad-head-direction": (5, 0.01), "bad-head-normal": (11, 0.0),
            "bad-head-tip": (0, row[0] + 0.0001),
        }[failure]
        row[index] = value
        f.finish_arrows[0] = tuple(row)
    else:
        points = list(f.collar_annotation.GetLeaderPointsAtIndex.return_value)
        points[0] += 0.00125
        f.collar_annotation.GetLeaderPointsAtIndex.return_value = tuple(points)
        f.finish_lines[0] = tuple(points)
    with pytest.raises(RuntimeError):
        _neck_proof(f, phase)
    f.rebuild.assert_not_called()
    assert f.model.GraphicsRedraw2.call_count == 1


def test_native_proofs_do_not_claim_glyphs_or_read_pdf_before_existing_export(
    neck_dimension_fakes, monkeypatch,
) -> None:
    f = neck_dimension_fakes
    telemetry = Mock()
    monkeypatch.setattr(drawing._telemetry, "info", telemetry)
    for phase in _NECK_PHASES[:-1]:
        _neck_proof(f, phase)
    drawing.read_pdf_ink.assert_not_called()
    assert sum("native_ADVANCE_only_m=" in item.args[0] for item in telemetry.call_args_list) == 6
    _neck_proof(f, "after_pdf_save")
    drawing.read_pdf_ink.assert_called_once_with(drawing.OUTPUTS.pdf)
    assert any("actual_PDF_diameter_paths_m=" in item.args[0] for item in telemetry.call_args_list)


@pytest.mark.parametrize("failure", [
    "missing-numeric", "wrong-numeric-owner", "missing-ring-edge", "missing-slash", "extra-path",
    "bay-clipped-slash", "negative-pen", "nan-pen", "missing-sf-head", "glyph-inside-head",
])
def test_actual_pdf_requires_complete_owned_numeric_and_vector_diameter_and_painted_head_gap(
    neck_dimension_fakes, failure,
) -> None:
    from dataclasses import replace

    f = neck_dimension_fakes

    def mutate(spans, strokes, token):
        if failure == "missing-numeric":
            spans.pop(0)
        elif failure == "wrong-numeric-owner":
            spans[0] = replace(spans[0], xmin=0.22, xmax=0.23)
        elif failure == "missing-ring-edge":
            token.pop(0)
        elif failure == "missing-slash":
            token.pop()
        elif failure == "extra-path":
            token.append(Stroke(0.18, 0.194, 0.181, 0.194, 0.00013, (0, 0, 0), False, False, True))
        elif failure == "bay-clipped-slash":
            token[-1] = replace(token[-1], y1=0.19719)
        elif failure in ("negative-pen", "nan-pen"):
            token[0] = replace(token[0], width=-0.001 if failure == "negative-pen" else float("nan"))
        elif failure == "missing-sf-head":
            head = drawing.arrowhead_segments(f.finish_arrows[0])[0]
            strokes[:] = [stroke for stroke in strokes if (stroke.x0, stroke.y0, stroke.x1, stroke.y1)
                          != (head.x0, head.y0, head.x1, head.y1)]
        else:
            head = drawing.arrowhead_segments(f.finish_arrows[0])
            x = sum(segment.x0 for segment in head) / 3.0
            y = sum(segment.y0 for segment in head) / 3.0
            glyph = replace(spans[0].glyphs[0], xmin=x, xmax=x + 0.00001, ymin=y, ymax=y + 0.00001)
            spans[0] = replace(spans[0], glyphs=(glyph, *spans[0].glyphs[1:]))

    f.pdf.mutate = mutate
    _neck_proof(f, "final settling rebuild")
    with pytest.raises(RuntimeError, match="PDF|actual"):
        _neck_proof(f, "after_pdf_save")


def test_painted_triangle_interior_and_both_pen_radii_count_in_exact_gap() -> None:
    triangle = (
        drawing.Segment(0.0, 0.0, 0.004, 0.0),
        drawing.Segment(0.004, 0.0, 0.002, 0.004),
        drawing.Segment(0.002, 0.004, 0.0, 0.0),
    )
    owned = {edge: ((edge, 0.000065),) for edge in triangle}
    assert drawing._neck_pdf_head_clearance(
        triangle, owned, (drawing.InkBox(0.0019, 0.001, 0.0021, 0.0011),), (),
    ) == 0.0
    path = drawing.Segment(0.006, 0.0, 0.006, 0.001)
    assert drawing._neck_pdf_head_clearance(triangle, owned, (), ((path, 0.000065),)) == pytest.approx(0.00187)


@pytest.mark.parametrize("primary_save_failure", [False, True])
def test_actual_export_context_propagates_pdf_proof_failure_before_qualification_or_publication(
    neck_dimension_fakes, monkeypatch, tmp_path, primary_save_failure,
) -> None:
    """Use the real finalizer and actual artifact checkpoint context."""
    import contextlib

    f = neck_dimension_fakes
    outputs = SimpleNamespace(slddrw=tmp_path / "crank.SLDDRW", pdf=tmp_path / "crank.pdf", png=tmp_path / "crank.png")
    monkeypatch.setattr(drawing, "OUTPUTS", outputs)
    sheet = SimpleNamespace(
        SetScale=lambda *args: True, GetProperties2=lambda: [0] * 8, CustomPropertyView="FRONT", GetViews=lambda: (),
    )
    model = f.model
    model.GetSheetNames = lambda: ("Sheet1",)
    model.ActivateSheet = lambda name: True
    model.GetCurrentSheet = lambda: sheet
    model.Sheet = lambda name: sheet
    f.side.GetOrientationName = lambda: "*Front"
    f.adapter._get_attr_or_call = lambda obj, name: getattr(obj, name)() if callable(getattr(obj, name)) else getattr(obj, name)
    f.side.ReferencedDocument = f.source
    monkeypatch.setattr(drawing_common, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing_common._sw_type_info, "early_bound_or_flag", lambda value, *args: value)
    monkeypatch.setattr(drawing_common, "iter_views", lambda adapter: (f.side,))
    monkeypatch.setattr(drawing_common, "view_name", lambda adapter, view: "FRONT")
    monkeypatch.setattr(drawing_common, "_build_id", lambda: "test-build")
    for name in ("apply_custom_properties", "assert_asme_b_sheet", "read_required_properties", "rebuild_drawing"):
        monkeypatch.setattr(drawing_common, name, Mock())
    drawing_common.read_required_properties.return_value = {"TOL_LIN_XX": "±0.51"}
    monkeypatch.setattr(drawing_common, "pdf_shaded_raster_dpi", lambda *args: contextlib.nullcontext())
    qualification = Mock()
    publication = Mock()
    monkeypatch.setattr(drawing_common, "assert_precise_isometric_views", qualification)
    monkeypatch.setattr(drawing_common, "sanitize_pdf_metadata", publication)
    monkeypatch.setattr(drawing_common, "render_pdf_png", Mock(side_effect=AssertionError("must not render a refused PDF")))
    monkeypatch.setattr(drawing_common, "run_layout_audit", Mock(side_effect=AssertionError("must not qualify a refused PDF")))
    events = []

    def save(adapter, path, *, pdf_path, artifact_context):
        for kind, target in (("drawing", path), ("pdf", pdf_path)):
            with artifact_context(kind, target):
                Path(target).write_bytes(b"existing export")
                events.append(f"saved-{kind}")
                if kind == "pdf" and primary_save_failure:
                    raise OSError("native PDF export failed")
        return {"drawing": path, "pdf": pdf_path}

    monkeypatch.setattr(drawing_common, "save_drawing", save)
    f.pdf.mutate = lambda spans, strokes, token: token.pop()

    def checkpoint(phase):
        events.append(phase)
        _neck_proof(f, phase)

    with pytest.raises(OSError if primary_save_failure else RuntimeError) as exc:
        asyncio.run(drawing_common.finalize_drawing(
            f.adapter, outputs, layout=drawing.SPEC.layout, pdf_title="Crankshaft", checkpoint=checkpoint,
        ))
    assert outputs.pdf.is_file()
    assert events.index("saved-pdf") < events.index("after_pdf_save")
    if primary_save_failure:
        assert "native PDF export failed" in str(exc.value)
        assert any("after_pdf_save checkpoint also failed" in note for note in exc.value.__notes__)
    else:
        assert "diameter ring or slash" in str(exc.value)
    qualification.assert_not_called()
    publication.assert_not_called()


@pytest.mark.parametrize("phase", _NECK_PHASES)
def test_straight_finish_allows_safe_native_body_vertex_root_without_origin_override(
    neck_dimension_fakes, phase,
) -> None:
    f = neck_dimension_fakes
    root = (0.181095, drawing.COLLAR_REAR_FINISH[1][1] + 0.00375)  # the V's upper-left vertex
    tip = drawing.COLLAR_REAR_FINISH[0]
    points = (*root, 0.0, *tip, 0.0)
    f.collar_annotation.GetLeaderPointsAtIndex.return_value = points
    f.finish_lines[0] = points
    arrow = list(f.finish_arrows[0])
    arrow[3:6] = (root[0] - tip[0], root[1] - tip[1], 0.0)
    f.finish_arrows[0] = tuple(arrow)
    _neck_proof(f, phase)
    f.collar_annotation.SetLeader3.assert_not_called()
    assert drawing.COLLAR_REAR_FINISH[1] != root


@pytest.mark.parametrize("phase", _NECK_PHASES)
def test_actual_neck_tips_must_keep_approved_origin_x_even_when_heads_fit(neck_dimension_fakes, phase) -> None:
    f = neck_dimension_fakes
    for index, native in enumerate(f.arrow_rows):
        row = list(native)
        row[0] += 0.0001
        f.arrow_rows[index] = tuple(row)
    with pytest.raises(RuntimeError, match="actual diameter tips moved"):
        _neck_proof(f, phase)


@pytest.mark.parametrize("kind", ["unpainted", "dashed"])
def test_actual_pdf_ignores_unowned_clip_paths_and_dashed_foreign_ink(neck_dimension_fakes, kind) -> None:
    f = neck_dimension_fakes

    def mutate(spans, strokes, token):
        # It crosses the prefix slot, but is not a solid painted annotation.
        # Its irrelevant width must not contaminate the owned-ink proof.
        strokes.append(Stroke(
            0.180, 0.194, 0.183, 0.194, float("nan"), (0, 0, 0),
            kind == "dashed", False, kind == "dashed",
        ))

    f.pdf.mutate = mutate
    _neck_proof(f, "after_pdf_save")


@pytest.mark.parametrize("kind", ["unpainted", "dashed"])
def test_actual_pdf_refuses_a_head_with_only_unpainted_or_dashed_owner(neck_dimension_fakes, kind) -> None:
    from dataclasses import replace

    f = neck_dimension_fakes
    head = drawing.arrowhead_segments(f.finish_arrows[0])[0]

    def mutate(spans, strokes, token):
        for index, stroke in enumerate(strokes):
            if (stroke.x0, stroke.y0, stroke.x1, stroke.y1) == (head.x0, head.y0, head.x1, head.y1):
                strokes[index] = replace(
                    stroke, dashed=kind == "dashed", filled=False, stroked=kind == "dashed",
                )

    f.pdf.mutate = mutate
    _neck_proof(f, "final settling rebuild")
    with pytest.raises(RuntimeError, match="complete native primitive has no actual PDF owner"):
        _neck_proof(f, "after_pdf_save")


def test_native_line_guard_decodes_active_sdk_ten_field_record_without_style_offset() -> None:
    points = (0.177530000005, 0.1919951, 0.01, 0.1918598, 0.1919951, 0.02)
    data = _native_presentation_data([points])
    data.GetLineAtIndex3.side_effect = None
    data.GetLineAtIndex3.return_value = (255.0, 1.0, 2.0, 3.0, *points)
    assert drawing._neck_native_lines(data, label="active line SDK") == (
        drawing.Segment(points[0], points[1], points[3], points[4]),
    )
    data.GetLineAtIndex3.assert_called_once_with(0)


@pytest.mark.parametrize("phase", _NECK_PHASES)
def test_native_zero_length_sentinels_are_not_ink_or_required_route_primitives(neck_dimension_fakes, phase) -> None:
    f = neck_dimension_fakes
    for rows in (f.neck_lines, f.foreign_lines, f.station_lines, f.finish_lines):
        rows.insert(0, (0.0,) * 6)
    _neck_proof(f, phase)
    f.rebuild.assert_not_called()


@pytest.mark.parametrize("raw", [
    (0.0,) * 9,
    (False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0, 0.0, float("nan"), 0.0, 0.0, 0.0, 0.0, 0.0),
], ids=["short", "bool-field", "nonfinite-field"])
def test_native_sentinel_skip_does_not_accept_malformed_ten_field_records(raw) -> None:
    data = _native_presentation_data([(0.0,) * 6])
    data.GetLineAtIndex3.side_effect = None
    data.GetLineAtIndex3.return_value = raw
    with pytest.raises(RuntimeError, match="malformed native geometry"):
        drawing._neck_native_lines(data, label="sentinel")


@pytest.mark.parametrize("phase", _NECK_PHASES)
def test_native_sentinels_cannot_replace_the_real_ordinary_route(neck_dimension_fakes, phase) -> None:
    f = neck_dimension_fakes
    f.neck_lines[:] = [(0.0,) * 6] * 3
    with pytest.raises(RuntimeError, match="three ordinary native diameter primitives"):
        _neck_proof(f, phase)


def test_owned_pdf_coverage_retains_reversed_and_sub_tolerance_middle_paint() -> None:
    line = drawing.Segment(0.17, 0.19, 0.18, 0.19)
    first, last = line.point_at(0.4975), line.point_at(0.5025)
    strokes = (
        (drawing.Segment(*last, line.x1, line.y1), 0.000065),
        (drawing.Segment(*last, *first), 0.0002),
        (drawing.Segment(line.x0, line.y0, *first), 0.000065),
    )
    assert strokes[1][0].length < drawing.COLLINEAR_TOL_M
    owned = drawing._neck_pdf_owned_lines(strokes, (line,), label="split native line")
    assert owned[line] == strokes


@pytest.mark.parametrize("missing", ["middle", "start", "end"])
def test_owned_pdf_endpoint_fragments_do_not_prove_complete_coverage(missing) -> None:
    line = drawing.Segment(0.17, 0.19, 0.18, 0.19)
    fractions = {
        "middle": ((0.0, 0.2), (0.8, 1.0)),
        "start": ((0.2, 1.0),),
        "end": ((0.0, 0.8),),
    }[missing]
    strokes = tuple(
        (drawing.Segment(*line.point_at(start), *line.point_at(end)), 0.000065)
        for start, end in fractions
    )
    with pytest.raises(RuntimeError, match="complete native primitive has no actual PDF owner"):
        drawing._neck_pdf_owned_lines(strokes, (line,), label="missing paint")


@pytest.mark.parametrize("gap_factor", [0.5, 1.5], ids=["within-existing-attribution", "beyond-existing-attribution"])
def test_owned_pdf_projected_union_uses_only_existing_attribution_tolerance(gap_factor) -> None:
    line = drawing.Segment(0.17, 0.19, 0.18, 0.19)
    half_gap = drawing.COLLINEAR_TOL_M * gap_factor / 2.0
    strokes = (
        (drawing.Segment(line.x0, line.y0, 0.175 - half_gap, line.y0), 0.000065),
        (drawing.Segment(0.175 + half_gap, line.y0, line.x1, line.y1), 0.000065),
    )
    if gap_factor < 1.0:
        assert len(drawing._neck_pdf_owned_lines(strokes, (line,), label="roundoff")[line]) == 2
    else:
        with pytest.raises(RuntimeError, match="complete native primitive has no actual PDF owner"):
            drawing._neck_pdf_owned_lines(strokes, (line,), label="actual gap")


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("overlap", [False, True], ids=["reversed", "reversed-with-intended-overlap"])
def test_native_vertical_route_connects_actual_tips_and_shelf_with_reversal_or_overlap(
    neck_dimension_fakes, phase, overlap,
) -> None:
    f = neck_dimension_fakes
    if overlap:
        row = list(f.neck_lines[2])
        row[4] = f.neck_lines[0][1]
        f.neck_lines[2] = tuple(row)
    for index in (1, 2):
        row = f.neck_lines[index]
        f.neck_lines[index] = (*row[3:], *row[:3])
    _neck_proof(f, phase)


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("missing", ["lower-tip", "junction", "shelf-root"])
def test_native_vertical_fragments_cannot_replace_the_connected_diameter_route(
    neck_dimension_fakes, phase, missing,
) -> None:
    f = neck_dimension_fakes
    extension = list(f.neck_lines[1])
    diameter = list(f.neck_lines[2])
    if missing == "lower-tip":
        diameter[1] += 0.001
    elif missing == "junction":
        diameter[4] -= 0.001
        extension[4] += 0.001
    else:
        extension[1] -= 0.001
    f.neck_lines[1], f.neck_lines[2] = tuple(extension), tuple(diameter)
    with pytest.raises(RuntimeError, match="vertical route does not connect both tips to the shelf"):
        _neck_proof(f, phase)


@pytest.mark.parametrize("case", ["clear", "paint-contact", "wide-middle"], ids=[
    "positive-painted-gap", "combined-pen-contact", "split-middle-pen-contact",
])
def test_actual_finish_and_neck_paint_are_checked_against_each_other(neck_dimension_fakes, case) -> None:
    from dataclasses import replace

    f = neck_dimension_fakes
    gap = 0.00012 if case == "paint-contact" else 0.0002
    x = drawing.OUTBOARD_NECK_DIAMETER_XY[0] + gap
    f.finish_lines[-1] = (x, 0.180, 0.0, x, 0.185, 0.0)

    def mutate(spans, strokes, token):
        if case != "wide-middle":
            return
        for index, stroke in enumerate(strokes):
            if (stroke.x0, stroke.y0, stroke.x1, stroke.y1) == (x, 0.180, x, 0.185):
                strokes[index:index + 1] = [
                    replace(stroke, y1=0.181),
                    replace(stroke, y0=0.181, y1=0.184, width=0.0004),
                    replace(stroke, y0=0.184),
                ]
                break

    f.pdf.mutate = mutate
    _neck_proof(f, "final settling rebuild")  # native centre lines do not cross
    if case == "clear":
        _neck_proof(f, "after_pdf_save")
    else:
        with pytest.raises(RuntimeError, match="actual finish and neck primitives intersect"):
            _neck_proof(f, "after_pdf_save")


@pytest.mark.parametrize("joint_roundoff", [False, True], ids=["actual-vertex", "independent-joint-roundoff"])
def test_pdf_diameter_ring_vertex_crossings_count_as_two_geometric_crossings(monkeypatch, joint_roundoff) -> None:
    center, y, radius = 0.1814, 0.1948, 0.0015
    points = ((center - radius, y), (center, y + radius), (center + radius, y), (center, y - radius))
    paths = tuple(
        (drawing.Segment(*first, *last), 0.000065)
        for first, last in zip(points, (*points[1:], points[0]))
    ) + ((drawing.Segment(center - 0.0022, y, center + 0.0022, y), 0.000065),)
    if joint_roundoff:
        crossing = drawing._segment_crossing
        count = 0

        def independently_rounded(first, second):
            nonlocal count
            point = crossing(first, second)
            if point is None:
                return None
            count += 1
            return math.nextafter(point[0], math.inf if count % 2 else -math.inf), point[1]

        monkeypatch.setattr(drawing, "_segment_crossing", independently_rounded)
    prefix = drawing.InkBox(0.1788, 0.1919951, 0.1841, 0.1954951)
    bay = drawing.InkBox(0.17753, 0.1919951, 0.1988, 0.1972)
    assert drawing._neck_pdf_diameter_paths(paths, prefix, bay) == paths


def test_pdf_diameter_tangent_joint_is_not_two_distinct_crossings() -> None:
    center, y, radius = 0.1814, 0.1948, 0.0015
    points = ((center - radius, y), (center, y + radius), (center + radius, y), (center, y - radius))
    paths = tuple(
        (drawing.Segment(*first, *last), 0.000065)
        for first, last in zip(points, (*points[1:], points[0]))
    ) + ((drawing.Segment(center - 0.0022, y + radius, center + 0.0022, y + radius), 0.000065),)
    with pytest.raises(RuntimeError, match="does not cross the complete ring twice"):
        drawing._neck_pdf_diameter_paths(
            paths, drawing.InkBox(0.1788, 0.1919951, 0.1841, 0.1954951),
            drawing.InkBox(0.17753, 0.1919951, 0.1988, 0.1972),
        )


@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reversed"])
@pytest.mark.parametrize("overlap_length", [0.0, 1e-9, 0.001], ids=["point-only", "tiny-positive-overlap", "visible-overlap"])
def test_shared_root_exemption_is_only_a_point_not_a_collinear_stretch(reverse, overlap_length) -> None:
    root = (0.18326, 0.1973)
    leader = drawing.Segment(*root, root[0] + 0.004, root[1] + 0.002)
    if overlap_length:
        point = leader.point_at(overlap_length / leader.length)
    else:
        point = root[0] - 0.004, root[1] - 0.002
    body = drawing.Segment(*root, *point)
    if reverse:
        leader = drawing.Segment(leader.x1, leader.y1, leader.x0, leader.y0)
        body = drawing.Segment(body.x1, body.y1, body.x0, body.y0)
    assert drawing._neck_root_point_contact(leader, body, root) is (overlap_length == 0.0)


@pytest.mark.parametrize("phase", _NECK_PHASES)
def test_native_finish_refuses_collinear_body_overlap_beyond_the_shared_root(neck_dimension_fakes, phase) -> None:
    f = neck_dimension_fakes
    leader = f.finish_lines[0]
    middle = ((leader[0] + leader[3]) / 2.0, (leader[1] + leader[4]) / 2.0)
    f.finish_lines[1] = (*leader[:3], *middle, 0.0)
    with pytest.raises(RuntimeError, match="straight leader crosses its own surface-finish legs"):
        _neck_proof(f, phase)


def test_pdf_finish_refuses_collinear_paint_overlap_at_an_otherwise_valid_native_root(neck_dimension_fakes) -> None:
    from dataclasses import replace

    f = neck_dimension_fakes
    root = drawing.COLLAR_REAR_FINISH[1]
    tip = drawing.COLLAR_REAR_FINISH[0]
    dx, dy = tip[0] - root[0], tip[1] - root[1]
    length = math.hypot(dx, dy)
    middle = ((root[0] + tip[0]) / 2.0, (root[1] + tip[1]) / 2.0)
    native_end = middle[0] - dy / length * 0.00005, middle[1] + dx / length * 0.00005
    f.finish_lines[1] = (*root, 0.0, *native_end, 0.0)

    def mutate(spans, strokes, token):
        for index, stroke in enumerate(strokes):
            if (stroke.x0, stroke.y0, stroke.x1, stroke.y1) == (*root, *native_end):
                strokes[index] = replace(stroke, x1=middle[0], y1=middle[1])

    f.pdf.mutate = mutate
    _neck_proof(f, "final settling rebuild")
    with pytest.raises(RuntimeError, match="straight route crosses its own legs"):
        _neck_proof(f, "after_pdf_save")


def test_split_reversed_pdf_leader_preserves_the_one_actual_native_root(neck_dimension_fakes) -> None:
    from dataclasses import replace

    f = neck_dimension_fakes
    original = f.finish_lines[0]
    f.finish_lines[0] = (*original[3:], *original[:3])

    def mutate(spans, strokes, token):
        for index, stroke in enumerate(strokes):
            if (stroke.x0, stroke.y0, stroke.x1, stroke.y1) == (original[3], original[4], original[0], original[1]):
                dx, dy = stroke.x1 - stroke.x0, stroke.y1 - stroke.y0
                first = stroke.x0 + dx / 3.0, stroke.y0 + dy / 3.0
                last = stroke.x0 + dx * 2.0 / 3.0, stroke.y0 + dy * 2.0 / 3.0
                strokes[index:index + 1] = [
                    replace(stroke, x1=first[0], y1=first[1]),
                    replace(stroke, x0=first[0], y0=first[1], x1=last[0], y1=last[1]),
                    replace(stroke, x0=last[0], y0=last[1]),
                ]
                break

    f.pdf.mutate = mutate
    _neck_proof(f, "after_pdf_save")


def test_owned_pdf_heads_preserve_complete_allowed_displacement_and_pen() -> None:
    native = (
        drawing.Segment(0.170, 0.190, 0.174, 0.190),
        drawing.Segment(0.174, 0.190, 0.172, 0.194),
        drawing.Segment(0.172, 0.194, 0.170, 0.190),
    )
    strokes = tuple(
        (drawing.Segment(edge.x0 + 0.00003, edge.y0 + 0.00002,
                         edge.x1 + 0.00003, edge.y1 + 0.00002), 0.000065 + index * 0.00001)
        for index, edge in enumerate(native)
    )
    owned = drawing._neck_pdf_owned_heads(strokes, native, label="translated head")
    assert owned == {edge: (stroke,) for edge, stroke in zip(native, strokes)}


@pytest.mark.parametrize("target", ["glyph", "primitive"], ids=["two-mm-glyph-gap", "paint-intersection"])
def test_complete_native_head_coverage_cannot_hide_allowed_actual_paint_overhang(target) -> None:
    native = (
        drawing.Segment(0.170, 0.190, 0.174, 0.190),
        drawing.Segment(0.174, 0.190, 0.172, 0.194),
        drawing.Segment(0.172, 0.194, 0.170, 0.190),
    )
    tail = drawing.Segment(native[0].x0, native[0].y0, native[0].x1 + 0.00008, native[0].y1)
    strokes = ((tail, 0.000065), *((edge, 0.000065) for edge in native[1:]))
    route_owned = drawing._neck_pdf_owned_lines(strokes, native, label="coverage intervals")
    head_owned = drawing._neck_pdf_owned_heads(strokes, native, label="complete head paint")
    assert head_owned[native[0]] == ((tail, 0.000065),)
    if target == "glyph":
        boxes = (drawing.InkBox(0.1761, 0.1899, 0.177, 0.1901),)
        paths = ()
        threshold = drawing.ARROW_TEXT_CLEARANCE_M
    else:
        boxes = ()
        paths = ((drawing.Segment(0.17407, 0.1899, 0.17407, 0.1901), 0.000001),)
        threshold = 0.0
    assert drawing._neck_pdf_head_clearance(native, route_owned, boxes, paths) > threshold
    assert drawing._neck_pdf_head_clearance(native, head_owned, boxes, paths) < threshold


@pytest.mark.parametrize("which", ["finish", "neck"])
def test_actual_pdf_refuses_ambiguous_overlong_head_paint_even_with_full_native_coverage(
    neck_dimension_fakes, which,
) -> None:
    from dataclasses import replace

    f = neck_dimension_fakes
    row = f.finish_arrows[0] if which == "finish" else f.arrow_rows[1]
    edge = drawing.arrowhead_segments(row)[0]
    ux, uy = (edge.x1 - edge.x0) / edge.length, (edge.y1 - edge.y0) / edge.length

    def mutate(spans, strokes, token):
        for index, stroke in enumerate(strokes):
            if (stroke.x0, stroke.y0, stroke.x1, stroke.y1) == (edge.x0, edge.y0, edge.x1, edge.y1):
                strokes[index] = replace(stroke, x1=stroke.x1 + ux * 0.002, y1=stroke.y1 + uy * 0.002)

    f.pdf.mutate = mutate
    _neck_proof(f, "final settling rebuild")
    with pytest.raises(RuntimeError, match="ambiguous actual head stroke extends beyond its native edge"):
        _neck_proof(f, "after_pdf_save")


def _assert_neck_bay_native_read_counts(data) -> None:
    expected_calls = {
        "GetLineCount": [call()],
        "GetLineAtIndex3": [call(index) for index in range(3)],
        "GetTextCount": [call()],
        "GetTextAtIndex": [call(index) for index in range(3)],
        "GetTextPositionAtIndex": [call(1), call(2)],
        "GetTextHeightAtIndex": [call(1), call(2)],
        "GetTextInBoxWidthAtIndex": [call(1), call(2)],
        "GetTextAngleAtIndex": [call(1), call(2)],
        "GetTextRefPositionAtIndex": [call(1), call(2)],
        "GetArrowHeadCount": [],
        "GetArrowHeadAtIndex2": [],
    }
    assert set(vars(data)) == set(expected_calls)
    for name, calls in expected_calls.items():
        assert getattr(data, name).call_args_list == calls


@pytest.mark.parametrize("which", [
    "shelf-min-x", "shelf-max-x", "advance-xmin", "advance-xmax", "advance-ymin", "advance-ymax",
])
@pytest.mark.parametrize("outside_ulps", [-3, -2, -1, 0, 1, 2, 3, 4])
def test_native_inclusive_bay_boundaries_accept_only_two_outward_ulps(
    neck_dimension_fakes, which, outside_ulps,
) -> None:
    f = neck_dimension_fakes
    x = drawing.OUTBOARD_NECK_DIAMETER_XY[0]
    right = f.foreign_lines[0][0]
    roof = drawing._sheet_y(drawing.JOURNAL_DIA / 2.0)
    # This actual wall ends at the roof, so it bounds the bay without making
    # a shelf endpoint an independent strict route/foreign-wall intersection.
    foreign = (drawing.Segment(right, roof - 0.001, right, roof),)
    boundaries = {
        "shelf-min-x": x, "shelf-max-x": right,
        "advance-xmin": x, "advance-xmax": right,
        "advance-ymin": f.neck_lines[0][1], "advance-ymax": drawing.COLLAR_REAR_FINISH[1][1],
    }
    lower = which in ("shelf-min-x", "advance-xmin", "advance-ymin")
    direction = -math.inf if lower else math.inf
    if outside_ulps < 0:
        direction = -direction
    target = boundaries[which]
    for _ in range(abs(outside_ulps)):
        target = math.nextafter(target, direction)
    if which.startswith("shelf"):
        row = list(f.neck_lines[0])
        row[0 if lower else 3] = target
        f.neck_lines[0] = tuple(row)
    else:
        row = f.native_texts[1 if lower else 2]
        px, py, pz = row["position"]
        if which == "advance-xmin":
            px = target
        elif which == "advance-xmax":
            px = right - 0.0078125
            row["width"] = target - px
            assert px + row["width"] == target
        elif which == "advance-ymin":
            py = target
        else:
            py = drawing.COLLAR_REAR_FINISH[1][1] - 0.00390625
            row["height"] = target - py
            assert py + row["height"] == target
        row["position"] = (px, py, pz)
    heads = tuple(segment for row in f.arrow_rows for segment in drawing.arrowhead_segments(row))
    if outside_ulps > 2:
        reason = "shelf is not RIGHT" if which.startswith("shelf") else "ADVANCE escaped the RIGHT bay"
        with pytest.raises(RuntimeError, match=reason) as refusal:
            drawing._assert_neck_right_advance(f.arrow_data, heads, foreign, label="inclusive bay")
        if which.startswith("advance"):
            assert "advance_m=" in str(refusal.value)
            assert "inclusive_bay_m=" in str(refusal.value)
            assert "raw_boundary_deltas_m=" in str(refusal.value)
    else:
        lines, texts = drawing._assert_neck_right_advance(f.arrow_data, heads, foreign, label="inclusive bay")
        assert len(lines) == 3
        assert len(texts) == 2
    _assert_neck_bay_native_read_counts(f.arrow_data)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf], ids=["nan", "positive-infinity", "negative-infinity"])
@pytest.mark.parametrize("side", ["left", "right"])
def test_native_inclusive_bay_comparison_refuses_nonfinite_inputs(bad, side) -> None:
    assert not drawing._neck_native_ge(bad, 0.17753) if side == "left" else not drawing._neck_native_ge(0.17753, bad)


@pytest.mark.parametrize("case", ["left", "right-overflow", "both"])
def test_native_right_shelf_refusal_keeps_compact_independent_bounds(neck_dimension_fakes, case) -> None:
    f = neck_dimension_fakes
    x = drawing.OUTBOARD_NECK_DIAMETER_XY[0]
    right = f.foreign_lines[0][0]
    row = list(f.neck_lines[0])
    if case in ("left", "both"):
        row[0] = x - 0.0005
    if case in ("right-overflow", "both"):
        row[3] = right + 0.0005
    f.neck_lines[0] = tuple(row)
    heads = tuple(segment for raw in f.arrow_rows for segment in drawing.arrowhead_segments(raw))
    foreign = tuple(drawing.Segment(raw[0], raw[1], raw[3], raw[4]) for raw in f.foreign_lines)
    with pytest.raises(RuntimeError, match="ordinary native diameter shelf is not RIGHT") as refusal:
        drawing._assert_neck_right_advance(f.arrow_data, heads, foreign, label="genuine shelf escape")
    message = str(refusal.value)
    assert f"LEFT={case in ('left', 'both')}" in message
    assert f"RIGHT_OVERFLOW={case in ('right-overflow', 'both')}" in message
    assert f"shelf_x_m={(row[0], row[3])!r}" in message
    assert f"authored_x_m={x!r}" in message
    assert f"right_wall_m={right!r}" in message
    assert f"raw_min_minus_authored_x_m={row[0] - x!r}" in message
    assert f"raw_max_minus_wall_m={row[3] - right!r}" in message
    _assert_neck_bay_native_read_counts(f.arrow_data)


@pytest.mark.parametrize("boundary", ["roof", "finish"])
@pytest.mark.parametrize("outside", [False, True], ids=["exact-open-boundary", "one-ulp-outside"])
def test_native_bay_roundoff_does_not_relax_open_roof_or_finish_boundaries(
    neck_dimension_fakes, boundary, outside,
) -> None:
    f = neck_dimension_fakes
    roof = drawing._sheet_y(drawing.JOURNAL_DIA / 2.0)
    y = roof if boundary == "roof" else drawing.COLLAR_REAR_FINISH[1][1]
    if outside:
        y = math.nextafter(y, -math.inf if boundary == "roof" else math.inf)
    row = list(f.neck_lines[0])
    row[1] = row[4] = y
    f.neck_lines[0] = tuple(row)
    heads = tuple(segment for raw in f.arrow_rows for segment in drawing.arrowhead_segments(raw))
    foreign = tuple(drawing.Segment(raw[0], raw[1], raw[3], raw[4]) for raw in f.foreign_lines)
    with pytest.raises(RuntimeError, match="unreadable actual journal-roof/right-wall bay"):
        drawing._assert_neck_right_advance(f.arrow_data, heads, foreign, label="strict open bay")


@pytest.mark.parametrize("phase", _NECK_PHASES)
def test_native_bay_replays_record44_actual_one_and_two_ulp_roundoff(phase, monkeypatch) -> None:
    # Actual 01fe374ab native run, complete structured log record 44. Keep the
    # observed raw doubles, including the reversed shelf and prefix below it,
    # and that run's authored neck station (the inch print has since moved it).
    monkeypatch.setattr(drawing, "OUTBOARD_NECK_DIAMETER_XY", (0.17753000000000002, 0.1948))
    lines = [
        (0.19185982739061117, 0.19199513882882896, 0.0, 0.17753, 0.19199513882882896, 0.0),
        (0.17753, 0.19199513882882896, 0.0, 0.17753, 0.189525, 0.0),
        (0.17753, 0.170475, 0.0, 0.17753, 0.189525, 0.0),
    ]
    texts = [
        {"text": " "},
        {"text": "<MOD-DIAM>", "position": (0.1788230555967614, 0.1919951388288289, 0.0),
         "height": 0.0035, "width": 0.005278437398374081},
        {"text": ".375 ", "position": (0.1841014931115508, 0.19204861100548876, 0.0),
         "height": 0.0035, "width": 0.007758333580568433},
    ]
    heads = tuple(drawing.Segment(*row) for row in (
        (0.17753, 0.170475, 0.177149, 0.174031),
        (0.177149, 0.174031, 0.17791099999999999, 0.174031),
        (0.17791099999999999, 0.174031, 0.17753, 0.170475),
        (0.17753, 0.189525, 0.17791099999999999, 0.185969),
        (0.17791099999999999, 0.185969, 0.177149, 0.185969),
        (0.177149, 0.185969, 0.17753, 0.189525),
    ))
    foreign = tuple(drawing.Segment(*row) for row in (
        (0.2506999999999999, 0.2091951388288289, 0.2506999999999999, 0.190400000028),
        (0.32010000000000016, 0.20241805501282215, 0.32010000000000016, 0.18900000003400003),
        (0.3114999999999999, 0.22719513882882894, 0.3114999999999999, 0.18952500000000003),
    ))
    x = drawing.OUTBOARD_NECK_DIAMETER_XY[0]
    assert x == 0.17753000000000002
    assert math.nextafter(x, -math.inf) == lines[0][3]
    assert math.nextafter(math.nextafter(lines[0][1], -math.inf), -math.inf) == texts[1]["position"][1]
    data = _native_presentation_data(lines, texts)
    observed_lines, observed_texts = drawing._assert_neck_right_advance(
        data, heads, foreign, label=f"record 44 ({phase})",
    )
    assert observed_lines == tuple(drawing.Segment(row[0], row[1], row[3], row[4]) for row in lines)
    assert observed_texts[0]["advance"].ymin == texts[1]["position"][1]
    _assert_neck_bay_native_read_counts(data)


@pytest.mark.parametrize("phase", _NECK_PHASES)
@pytest.mark.parametrize("which", ["shelf-x", "advance-y"])
@pytest.mark.parametrize("outside_ulps", [1, 2, 3])
def test_native_bay_roundoff_policy_runs_through_every_actual_checkpoint(
    neck_dimension_fakes, phase, which, outside_ulps,
) -> None:
    f = neck_dimension_fakes
    if which == "shelf-x":
        row = list(f.neck_lines[0])
        for _ in range(outside_ulps):
            row[0] = math.nextafter(row[0], -math.inf)
        f.neck_lines[0] = tuple(row)
    else:
        row = f.native_texts[1]
        px, py, pz = row["position"]
        for _ in range(outside_ulps):
            py = math.nextafter(py, -math.inf)
        row["position"] = (px, py, pz)
    if outside_ulps > 2:
        reason = "shelf is not RIGHT" if which == "shelf-x" else "ADVANCE escaped the RIGHT bay"
        with pytest.raises(RuntimeError, match=reason):
            _neck_proof(f, phase)
    else:
        _neck_proof(f, phase)
