"""Offline contracts for the through-hub crankshaft drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import build_dt_crankshaft as part
import _sprocket_seat_geometry as seat_geometry
import dt_crank_hub_geometry as geometry
import dt_crankshaft_notes as notes
import dt_crankshaft_spec as spec
import draw_dt_crankshaft as drawing
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
    # Running/seat fits print at three places; the seat collar's functional
    # bands (drawing-guidelines.md rule 3 (decimal places carry the tolerance)) at the places that hold them; the rest at one.
    functional_places = {
        "ShaftDiaDim": 3,
        "JournalDiaDim": 3,
        "PinionSeatDiaDim": 3,
        "SpigotDiaDim": 2,
        "SpigotLength": 2,
        "CollarSeatStation": 2,
        "CollarRearStation": 2,
        "DrivePinOffset1": 3,
        "DrivePinOffset2": 3,
    }
    for name, places in spec.DRAWING_PRECISION_BY_NAME.items():
        assert places == functional_places.get(name, 1), name
    assert spec.REFERENCE_DIMENSIONS <= marked
    assert spec.SPHERICAL_DIMENSIONS <= spec.REFERENCE_DIMENSIONS


def test_far_end_stations_restate_the_modelled_geometry() -> None:
    # The StationReference sketch drives each printed station from the same
    # globals as the features; these are the values the equations evaluate to.
    far = spec.SHAFT_LENGTH
    assert far - spec.SEAT_STEP == pytest.approx(spec.PINION_SEAT_STATION)
    # The station the spec chose prints exactly at its places.
    assert spec.PINION_SEAT_STATION == round(spec.PINION_SEAT_STATION, spec.STATION_PLACES)
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
    assert spec.SHAFT_LENGTH == round(spec.SHAFT_LENGTH, pinion.SHAFT_LENGTH_PLACES)
    assert spec.DRAWING_PRECISION["Shaft"]["Depth"] == pinion.SHAFT_LENGTH_PLACES
    assert spec.SHAFT_LENGTH == pytest.approx(136.3)
    least, most = spec.SHAFT_END_PROUD_RANGE
    assert spec.shaft_end_proud_range(spec.SHAFT_LENGTH) == (least, most)
    assert least >= 0.0
    assert most - least == pytest.approx(3.4)
    assert least <= spec.SHAFT_END_PROUD_NOMINAL <= most
    # One print step shorter and the end can sit inside the 16T.
    step = 10.0**-pinion.SHAFT_LENGTH_PLACES
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
    assert spec.SPIGOT_DIA == removable.SEAT_SPIGOT_DIA < spec.COLLAR_DIA
    # Ruling 2026-09-30: spigot -154.3..-148.5; the body runs on to the boss.
    assert bdt.CRANKSHAFT_Z0 + spec.SPIGOT_END == pytest.approx(-148.5)
    # The blind drive-pin holes end in the spigot, short of its step.
    assert spec.SEAT_COLLAR < spec.DRIVE_PIN_FLOOR < spec.SPIGOT_END
    # The rear face from the post's own boss face, floored to its .XX print.
    boss_south = spec.POST_BORE_END - post.CRANK_BOSS_LENGTH
    assert spec.POST_BOSS_SOUTH == pytest.approx(boss_south)
    places = spec.COLLAR_STATION_PLACES
    assert spec.COLLAR_LENGTH == round(spec.COLLAR_LENGTH, places)
    assert spec.COLLAR_LENGTH == pytest.approx(12.63)
    assert 0.0 <= boss_south - spec.COLLAR_REAR < 10.0**-places
    assert spec.COLLAR_BOSS_AIR == pytest.approx(boss_south - spec.COLLAR_REAR)
    assert bdt.CRANKSHAFT_Z0 + spec.COLLAR_REAR == pytest.approx(
        bdt.CRANKSHAFT_Z0 + boss_south, abs=10.0**-places
    )
    assert bdt.CRANKSHAFT_Z0 + spec.COLLAR_REAR == pytest.approx(-141.67)
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
    assert spec.SHAFT_LENGTH - spec.JOURNAL_START == pytest.approx(93.8)
    assert spec.JOURNAL_START == pytest.approx(42.5)
    # Bottomed dowels stand proud by the drive-train's pin length budget.
    assert (
        bdt.CRANKSHAFT_Z0 + spec.DRIVE_PIN_FLOOR - spec.dt_vn_crank_seat_drive_pin_spec.LENGTH
        == (pytest.approx(removable.DRIVE_PIN_TIP_Z))
    )



def _floor_2(value: float) -> float:
    return math.floor(value * 100.0 + 1e-9) / 100.0


def test_spigot_rim_is_the_shortfall_the_sheet_states() -> None:
    # The drive-pin holes' rim to the Ø17.5 seat spigot is under the 1.5 mm
    # wall floor (declared shortfall RV-02, owner ruling 2026-10-18): the sheet states the worst case of
    # the printed bands, rounded down so it never claims more rim than exists.
    hole_r = spec.DRIVE_PIN_HOLE_DIA / 2.0
    nominal = spec.SPIGOT_DIA / 2.0 - (spec.DRIVE_PIN_CIRCLE_RADIUS + hole_r)
    worst = (spec.SPIGOT_DIA + seat_geometry.SPIGOT_DIA_BAND[1]) / 2.0 - (
        spec.DRIVE_PIN_CIRCLE_RADIUS
        + seat_geometry.DRIVE_PIN_OFFSET_TOL
        + hole_r
        + seat_geometry.DRIVE_PIN_HOLE_BAND[0] / 2.0
    )
    rim = spec.DRIVE_PIN_SPIGOT_RIM_WORST
    assert rim == _floor_2(worst)
    assert 0.0 < rim < 1.5
    printed = re.search(r"SPIGOT RIM (\d+\.\d\d) MIN\.", notes.DRIVE_PIN_CALLOUT)
    assert printed
    assert float(printed.group(1)) == rim
    assert _floor_2(nominal) == spec.DRIVE_PIN_SPIGOT_RIM


def test_drive_pin_depth_prints_its_band_after_the_native_depth() -> None:
    # Machinist review of f7c9771b3: the bare 3.95 read under the title
    # block's .XX and left 5.75 - 4.46 = 1.29 of spigot under the holes.  The
    # callout carries the cut's own band, the one the proud stack reads.
    assert notes.DRIVE_PIN_DEPTH_BAND == f"<MOD-PM>{spec.DRIVE_PIN_DEPTH_TOL:.2f}"
    floor = (spec.SPIGOT_LENGTH - spec.SPIGOT_LENGTH_TOL) - (
        spec.DRIVE_PIN_DEPTH + spec.DRIVE_PIN_DEPTH_TOL
    )
    assert floor >= 1.5
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


def test_typed_depth_band_refuses_a_non_mm_sheet() -> None:
    # Codex P2 on #1151: the band is mm text after a native depth, so it is
    # only true on a mm sheet; the callout variables that would carry it
    # natively are unreachable on this cut-extrude callout (farm run
    # 20261003T001156794Z).  An inch sheet must stop before the band is typed.
    drawing._require_mm_sheet(_Sheet(0), "mm")  # swMM
    for unit in (3, 1, None):  # swINCHES, swCM, an unread preference
        with pytest.raises(RuntimeError, match="typed depth band is mm"):
            drawing._require_mm_sheet(_Sheet(unit), "not mm")

    class _Callout:
        def GetText(self, part: int) -> str:
            raise AssertionError("read the callout before the unit check")

    with pytest.raises(RuntimeError, match="typed depth band is mm"):
        drawing._band_hole_depth(
            _Callout(), notes.DRIVE_PIN_DEPTH_BAND, _Sheet(3), "inch sheet"
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
    # leader landing on that face's edge-on rim, at the collar's silhouette
    # where SolidWorks lands a point on an edge-on circle.
    (washer_face,) = [c for c in spec.SURFACE_FINISHES if c.key not in lands]
    assert washer_face.key == "collar_rear_face"
    pick, _symbol = drawing.COLLAR_REAR_FINISH
    assert pick[0] == pytest.approx(drawing._sheet_x(washer_face.face.offset_mm))
    assert pick[1] - drawing.SIDE_CENTER[1] == pytest.approx(
        spec.COLLAR_DIA * drawing.SHEET_SCALE[0] / 2000.0
    )


def test_each_bare_neck_has_its_own_native_loose_diameter() -> None:
    # The previous 2X callout reached only the right neck. The collar-side
    # land must now have its own physical-edge measurement, while the
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
    assert spec.NECK_DIA_PLACES == 1
    neck_x, neck_y = drawing.OUTBOARD_NECK_DIAMETER_XY
    assert drawing.COLLAR_REAR_X < neck_x < drawing.JOURNAL_START_X
    assert neck_y < drawing._sheet_y(-spec.COLLAR_DIA / 2.0)
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
    assert spec.DRAWING_PRECISION["PinionSeatProfile"]["NeckDiaDim"] == 1


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
    # R0.25 stands the bore edge off, which the seat gap's north range must
    # hold.
    import _config

    pinion = spec.dt_crank_pinion_spec
    assert spec.STEP_CORNER_RADIUS_MAX == _config.title_block("edge_break")["radius_mm"]
    standoff = spec.SEAT_STEP + spec.STATION_ROW + spec.STEP_CORNER_RADIUS_MAX - part.SEAT_PINION
    assert standoff == pytest.approx(spec.SEAT_STEP_STANDOFF_WORST)
    assert standoff <= pinion.SEAT_GAP_MAX_MM - pinion.SEAT_FEELER_MM
    # At the pinion's own seat the step would stand it off 1.05: too far.
    at_seat = part.SEAT_PINION + spec.STATION_ROW + spec.STEP_CORNER_RADIUS_MAX
    assert at_seat - part.SEAT_PINION > pinion.SEAT_GAP_MAX_MM - pinion.SEAT_FEELER_MM
    # The seat is the pinion's bore mate, at the through shaft's size band.
    assert spec.PINION_SEAT_DIA == pinion.BORE_DIA == 9.0
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
    assert spec.SHAFT_LENGTH_BAND == (0.00, -0.40)
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

    assert spec.SHAFT_LENGTH_BAND == (0.0, -spec.SHAFT_LENGTH_SHORT_MM) == (0.0, -0.4)
    assert spec.SEAT_COLLAR_BAND == pytest.approx(
        (
            spec.SHAFT_LENGTH_BAND[0] + spec.COLLAR_STATION_TOL,
            spec.SHAFT_LENGTH_BAND[1] - spec.COLLAR_STATION_TOL,
        )
    )
    assert bdt.CRANK_HUB_SPROCKET_AIR == pytest.approx(0.7)
    assert bdt.CRANK_HUB_SPROCKET_AIR_WORST == pytest.approx(
        bdt.CRANK_HUB_SPROCKET_AIR + min(spec.SEAT_COLLAR_BAND)
    )
    assert bdt.CRANK_HUB_SPROCKET_AIR_WORST > 0.0
    general = spec.dt_crank_pinion_spec.printed_band_mm(spec.dt_crank_pinion_spec.SHAFT_LENGTH_PLACES)
    assert general == pytest.approx(0.8)
    assert bdt.CRANK_HUB_SPROCKET_AIR - general - spec.COLLAR_STATION_TOL < 0.0






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


def _neck_rim(**overrides) -> _CircleEdge:
    centre = overrides.pop("centre", (0.0, spec.JOURNAL_START, 0.0))
    radius = overrides.pop("radius", spec.SHAFT_DIA / 2.0)
    return _CircleEdge(centre, radius, **overrides)


def test_collar_side_neck_resolves_the_physical_core_circle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rim = _neck_rim()
    distractors = [
        _neck_rim(centre=(0.0, spec.COLLAR_REAR, 0.0)),
        _neck_rim(centre=(0.0, spec.JOURNAL_END, 0.0)),
        _neck_rim(centre=(0.0, 0.0, 0.0)),
        _neck_rim(radius=spec.JOURNAL_DIA / 2.0),
        _neck_rim(circle=False),
    ]
    adapter, side = _front_fakes(monkeypatch, [*distractors, rim])
    assert drawing._outboard_neck_rim(adapter, side) is rim


@pytest.mark.parametrize(
    "edges",
    [
        [],
        [_neck_rim(), _neck_rim()],
        [_neck_rim(centre=(0.0, spec.JOURNAL_START + 0.01, 0.0))],
        [_neck_rim(centre=(0.01, spec.JOURNAL_START, 0.0))],
        [_neck_rim(radius=spec.JOURNAL_DIA / 2.0)],
    ],
    ids=["missing", "ambiguous", "wrong-station", "off-axis", "journal-rim"],
)
def test_collar_side_neck_refuses_a_missing_or_ambiguous_physical_rim(
    monkeypatch: pytest.MonkeyPatch, edges: list[_CircleEdge],
) -> None:
    adapter, side = _front_fakes(monkeypatch, edges)
    with pytest.raises(RuntimeError, match="expected exactly one"):
        drawing._outboard_neck_rim(adapter, side)


@pytest.mark.parametrize("params", [(), (0.0,) * 6, (float("nan"),) * 7])
def test_collar_side_neck_refuses_unreadable_circle_parameters(
    monkeypatch: pytest.MonkeyPatch, params: tuple[float, ...],
) -> None:
    rim = _neck_rim()
    rim.curve.CircleParams = params
    adapter, side = _front_fakes(monkeypatch, [rim])
    with pytest.raises(RuntimeError, match="unreadable circle"):
        drawing._outboard_neck_rim(adapter, side)


@pytest.fixture
def neck_dimension_fakes(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    rim = _neck_rim()
    adapter, side = _front_fakes(monkeypatch, [rim])
    native = SimpleNamespace(
        SystemValue=spec.SHAFT_DIA / 1000.0, DrivenState=2,
        FullName="RD1@FRONT@Drawing1", Tolerance=SimpleNamespace(Type=0),
    )
    texts = {1: "<MOD-DIAM>", 2: "", 3: "", 4: ""}
    arrow_tip = (
        drawing.OUTBOARD_NECK_DIAMETER_XY[0],
        drawing._sheet_y(-spec.SHAFT_DIA / 2.0),
        0.0, 0.0, -1.0, 0.0, 0.0035, 0.00075, 1.0, 0.0, 0.0, 1.0,
    )
    arrow_data = SimpleNamespace(
        GetArrowHeadCount=Mock(return_value=1),
        GetArrowHeadAtIndex2=Mock(return_value=arrow_tip),
    )
    display = SimpleNamespace(
        Type2=6, ShowParenthesis=True,
        GetDimension2=Mock(return_value=native),
        GetPrimaryPrecision2=Mock(return_value=spec.NECK_DIA_PLACES),
        GetOverride=Mock(return_value=False),
        GetText=Mock(side_effect=lambda part: texts[part]),
        SetPrecision3=Mock(return_value=0),
        GetDisplayData=Mock(return_value=arrow_data),
    )
    annotation = SimpleNamespace(
        name="RD1", GetType=Mock(return_value=4),
        GetSpecificAnnotation=Mock(return_value=display),
        GetAttachedEntities3=Mock(return_value=(rim,)),
        GetAttachedEntityCount3=Mock(return_value=1),
        GetAttachedEntityTypes=Mock(return_value=(1,)),
        IsDangling=Mock(return_value=False),
        # Native diameter semantics do not assume the note leader count.
        GetLeaderCount=Mock(return_value=0),
    )
    right_native = SimpleNamespace(
        SystemValue=spec.SHAFT_DIA / 1000.0, DrivenState=2,
        FullName="NeckDiaDim@PinionSeatProfile@dt-crankshaft", Tolerance=SimpleNamespace(Type=0),
    )
    right_texts = {1: "<MOD-DIAM>", 2: "", 3: "", 4: ""}
    right_display = SimpleNamespace(
        Type2=6, ShowParenthesis=False,
        GetDimension2=Mock(return_value=right_native),
        GetPrimaryPrecision2=Mock(return_value=spec.NECK_DIA_PLACES),
        GetOverride=Mock(return_value=False),
        GetText=Mock(side_effect=lambda part: right_texts[part]),
    )
    right_annotation = SimpleNamespace(
        name="NeckDiaDim", GetType=Mock(return_value=4),
        GetSpecificAnnotation=Mock(return_value=right_display),
    )
    unrelated_note = SimpleNamespace(GetType=Mock(return_value=6))
    side.GetAnnotations = Mock(return_value=(unrelated_note, right_annotation, annotation))
    model = SimpleNamespace(
        Extension=SimpleNamespace(AddSpecificDimension=Mock(return_value=(display, 0))),
        ClearSelection2=Mock(),
        GraphicsRedraw2=Mock(),
    )
    adapter.currentModel = model
    adapter.swApp = SimpleNamespace(IsSame=Mock(side_effect=lambda a, b: int(a is b)))
    select, rebuild = Mock(), Mock()
    monkeypatch.setattr(drawing, "_select_view_entity", select)
    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, item: item.name)
    return SimpleNamespace(
        adapter=adapter, side=side, rim=rim, native=native, display=display,
        annotation=annotation, right_native=right_native, right_display=right_display,
        right_texts=right_texts, right_annotation=right_annotation, texts=texts,
        model=model, select=select, rebuild=rebuild,
        native_tolerance=native.Tolerance, right_tolerance=right_native.Tolerance,
        arrow_data=arrow_data, arrow_tip=arrow_tip,
    )


def test_new_neck_dimension_is_a_real_driven_diameter_not_numeric_text(
    neck_dimension_fakes: SimpleNamespace,
) -> None:
    f = neck_dimension_fakes
    original_right = vars(f.right_native).copy()

    def add(*args):
        f.select.assert_called_once_with(
            f.adapter, f.side, "EDGE", None, label="collar-side neck", entity=f.rim
        )
        return f.display, 0

    def rebuilt(*args, **kwargs):
        assert f.native.DrivenState == 1
        assert f.display.ShowParenthesis is False
        f.display.SetPrecision3.assert_called_once_with(
            spec.DRAWING_REFERENCE_PRECISION["OutboardNeckDia"], -1, -1, -1
        )
        f.model.ClearSelection2.assert_called_once_with(True)
        f.annotation.GetAttachedEntities3.assert_not_called()

    f.model.Extension.AddSpecificDimension.side_effect = add
    f.rebuild.side_effect = rebuilt
    assert drawing._add_outboard_neck_dimension(f.adapter, f.model, f.side) == (f.native, 2)
    f.model.Extension.AddSpecificDimension.assert_called_once_with(
        *drawing.OUTBOARD_NECK_DIAMETER_XY, 0.0, 6, 0
    )
    f.rebuild.assert_called_once_with(f.adapter, label="collar-side neck")
    f.model.GraphicsRedraw2.assert_called_once_with()
    f.annotation.GetAttachedEntities3.assert_called_once_with()
    f.adapter.swApp.IsSame.assert_any_call(f.native, f.native)
    f.adapter.swApp.IsSame.assert_any_call(f.rim, f.rim)
    assert f.native.SystemValue == spec.SHAFT_DIA / 1000.0
    assert vars(f.right_native) == original_right
    f.right_display.GetText.assert_any_call(3)  # old quantity explicitly re-read


@pytest.mark.parametrize("status", [-1, 1, None, False])
def test_new_neck_dimension_refuses_unsuccessful_creation(
    neck_dimension_fakes: SimpleNamespace, status: object,
) -> None:
    f = neck_dimension_fakes
    f.model.Extension.AddSpecificDimension.return_value = f.display, status
    with pytest.raises(RuntimeError, match="edge-on circle rejected"):
        drawing._add_outboard_neck_dimension(f.adapter, f.model, f.side)
    f.display.SetPrecision3.assert_not_called()
    f.rebuild.assert_not_called()


@pytest.mark.parametrize("status", [-1, 1, 2, 3, 4, None, False])
def test_new_neck_dimension_refuses_precision_problem_status(
    neck_dimension_fakes: SimpleNamespace, status: object,
) -> None:
    f = neck_dimension_fakes
    f.display.SetPrecision3.return_value = status
    with pytest.raises(RuntimeError, match="precision assignment failed"):
        drawing._add_outboard_neck_dimension(f.adapter, f.model, f.side)
    f.rebuild.assert_not_called()


@pytest.mark.parametrize(
    "target, member, value, message",
    [
        ("display", "Type2", 15, "not a diameter"),
        ("display", "Type2", 5, "not a diameter"),
        ("native", "SystemValue", None, "no native measured value"),
        ("native", "SystemValue", float("nan"), "measures"),
        ("native", "SystemValue", 0.0095, "measures"),
        ("native", "DrivenState", 2, "native driven state"),
        ("native", "DrivenState", 0, "native driven state"),
        ("display", "GetPrimaryPrecision2", 2, "primary places"),
        ("display", "GetPrimaryPrecision2", -2, "primary places"),
        ("native_tolerance", "Type", 2, "explicit tolerance"),
        ("display", "GetOverride", True, "overridden or parenthesized"),
        ("display", "ShowParenthesis", True, "overridden or parenthesized"),
        ("annotation", "GetAttachedEntities3", (), "physical rim attachment"),
        ("annotation", "GetAttachedEntities3", (None,), "physical rim attachment"),
        ("annotation", "GetAttachedEntities3", (_neck_rim(),), "physical rim attachment"),
        ("annotation", "GetAttachedEntityCount3", 2, "physical rim attachment"),
        ("annotation", "GetAttachedEntityTypes", (2,), "physical rim attachment"),
        ("annotation", "IsDangling", True, "physical rim attachment"),
        ("right_display", "GetPrimaryPrecision2", 3, "primary places"),
        ("right_native", "SystemValue", 0.0095, "measures"),
        ("right_tolerance", "Type", 2, "explicit tolerance"),
        ("right_native", "DrivenState", 1, "native driven state"),
        ("right_display", "Type2", 15, "not a diameter"),
        ("right_display", "GetOverride", True, "overridden or parenthesized"),
        ("right_display", "GetOverride", None, "overridden or parenthesized"),
        ("right_display", "ShowParenthesis", True, "overridden or parenthesized"),
    ],
)
def test_neck_contract_refuses_native_or_post_save_drift(
    neck_dimension_fakes: SimpleNamespace,
    target: str, member: str, value: object, message: str,
) -> None:
    f = neck_dimension_fakes
    f.native.DrivenState = 1
    f.display.ShowParenthesis = False
    obj = getattr(f, target)
    existing = getattr(obj, member)
    if isinstance(existing, Mock):
        existing.return_value = value
    else:
        setattr(obj, member, value)
    with pytest.raises(RuntimeError, match=message):
        drawing._assert_outboard_neck_dimension(
            f.adapter, f.side, f.native, 2, phase="after_drawing_save"
        )
    f.display.SetPrecision3.assert_not_called()


@pytest.mark.parametrize(
    "part, text", [(1, "Ø9.5"), (1, "(<MOD-DIAM>"), (2, ")"), (3, "2X"), (4, "REF")]
)
@pytest.mark.parametrize("neck", ["new", "right"])
def test_neither_neck_can_ship_a_quantity_literal_or_reference_decoration(
    neck_dimension_fakes: SimpleNamespace, part: int, text: str, neck: str,
) -> None:
    f = neck_dimension_fakes
    f.native.DrivenState = 1
    f.display.ShowParenthesis = False
    (f.texts if neck == "new" else f.right_texts)[part] = text
    with pytest.raises(RuntimeError, match="unexpected native diameter text"):
        drawing._assert_outboard_neck_dimension(
            f.adapter, f.side, f.native, 2, phase="after_drawing_save"
        )


@pytest.mark.parametrize("leaders", [0, 1, 2])
def test_native_diameter_attachment_does_not_assume_note_leader_count(
    neck_dimension_fakes: SimpleNamespace, leaders: int,
) -> None:
    f = neck_dimension_fakes
    f.native.DrivenState = 1
    f.display.ShowParenthesis = False
    f.annotation.GetLeaderCount.return_value = leaders
    drawing._assert_outboard_neck_dimension(
        f.adapter, f.side, f.native, 2, phase="final settling rebuild"
    )


@pytest.mark.parametrize(
    "phase",
    [
        "after_drawing_save", "after_pdf_save",
    ],
)
def test_neck_checkpoint_rechecks_existing_save_boundaries_without_opening(
    neck_dimension_fakes: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    f = neck_dimension_fakes
    verify = Mock()
    monkeypatch.setattr(drawing, "_assert_outboard_neck_dimension", verify)
    drawing._outboard_neck_checkpoint(f.adapter, f.side, f.native, 2, phase)
    verify.assert_called_once_with(f.adapter, f.side, f.native, 2, phase=phase)
    for unused in (
        "before_drawing_save", "before_pdf_save", "before_drawing_close", "after_drawing_close"
    ):
        drawing._outboard_neck_checkpoint(f.adapter, f.side, f.native, 2, unused)
    verify.assert_called_once()


def test_build_wires_neck_settled_and_save_readbacks_without_value_writes() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(
        item for item in tree.body
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "build"
    )
    calls = [item for item in ast.walk(build) if isinstance(item, ast.Call)]
    assert sum(ast.unparse(item.func) == "_add_outboard_neck_dimension" for item in calls) == 1
    finalizer = next(item for item in calls if ast.unparse(item.func) == "finalize_drawing")
    keywords = {item.arg: item.value for item in finalizer.keywords}
    assert "_assert_outboard_neck_dimension" in ast.unparse(keywords["settled_checks"])
    assert "_outboard_neck_checkpoint" in ast.unparse(keywords["checkpoint"])
    added = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "_add_outboard_neck_dimension"
    )
    writes = [
        target.attr
        for item in ast.walk(added) if isinstance(item, ast.Assign)
        for target in item.targets if isinstance(target, ast.Attribute)
    ]
    assert writes == ["DrivenState", "ShowParenthesis"]


@pytest.mark.parametrize("missing", ["display", "native"])
def test_new_neck_dimension_refuses_missing_native_objects(
    neck_dimension_fakes: SimpleNamespace, missing: str,
) -> None:
    f = neck_dimension_fakes
    if missing == "display":
        f.model.Extension.AddSpecificDimension.return_value = None, 0
        message = "edge-on circle rejected"
    else:
        f.display.GetDimension2.return_value = None
        message = "no native IDimension"
    with pytest.raises(RuntimeError, match=message):
        drawing._add_outboard_neck_dimension(f.adapter, f.model, f.side)
    f.display.SetPrecision3.assert_not_called()
    f.rebuild.assert_not_called()


@pytest.mark.parametrize("which", ["new-missing", "new-duplicate", "right-missing"])
def test_neck_contract_requires_both_native_view_dimensions(
    neck_dimension_fakes: SimpleNamespace, which: str,
) -> None:
    f = neck_dimension_fakes
    f.native.DrivenState = 1
    f.display.ShowParenthesis = False
    annotations = {
        "new-missing": (f.right_annotation,),
        "new-duplicate": (f.right_annotation, f.annotation, f.annotation),
        "right-missing": (f.annotation,),
    }
    f.side.GetAnnotations.return_value = annotations[which]
    with pytest.raises(RuntimeError, match="expected one"):
        drawing._assert_outboard_neck_dimension(
            f.adapter, f.side, f.native, 2, phase="after_drawing_save"
        )


def test_new_neck_rebuild_readback_uses_the_view_not_a_stale_creation_handle(
    neck_dimension_fakes: SimpleNamespace,
) -> None:
    f = neck_dimension_fakes

    def drift(*args, **kwargs):
        settled = SimpleNamespace(**vars(f.display))
        settled.GetPrimaryPrecision2 = Mock(return_value=2)
        f.annotation.GetSpecificAnnotation.return_value = settled

    f.rebuild.side_effect = drift
    with pytest.raises(RuntimeError, match="primary places"):
        drawing._add_outboard_neck_dimension(f.adapter, f.model, f.side)


def test_neck_save_checkpoint_propagates_attachment_loss(
    neck_dimension_fakes: SimpleNamespace,
) -> None:
    f = neck_dimension_fakes
    f.native.DrivenState = 1
    f.display.ShowParenthesis = False
    f.annotation.GetAttachedEntities3.return_value = ()
    with pytest.raises(RuntimeError, match="physical rim attachment"):
        drawing._outboard_neck_checkpoint(f.adapter, f.side, f.native, 2, "after_drawing_save")


@pytest.mark.parametrize("axis", [(1.0, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 1.0, 0.01)])
def test_neck_rim_rejects_a_wrong_or_nonunit_axis(
    monkeypatch: pytest.MonkeyPatch, axis: tuple[float, float, float],
) -> None:
    rim = _neck_rim()
    params = rim.curve.CircleParams
    rim.curve.CircleParams = (*params[:3], *axis, params[6])
    adapter, side = _front_fakes(monkeypatch, [rim])
    with pytest.raises(RuntimeError, match="expected exactly one"):
        drawing._outboard_neck_rim(adapter, side)


def test_neck_rim_accepts_the_opposite_direction_of_the_same_axis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rim = _neck_rim()
    params = rim.curve.CircleParams
    rim.curve.CircleParams = (*params[:3], 0.0, -1.0, 0.0, params[6])
    adapter, side = _front_fakes(monkeypatch, [rim])
    assert drawing._outboard_neck_rim(adapter, side) is rim


def test_neck_contract_refuses_a_type_four_annotation_without_specific_data(
    neck_dimension_fakes: SimpleNamespace,
) -> None:
    f = neck_dimension_fakes
    f.native.DrivenState = 1
    f.display.ShowParenthesis = False
    invalid = SimpleNamespace(GetType=lambda: 4, GetSpecificAnnotation=lambda: None)
    f.side.GetAnnotations.return_value = (invalid, f.right_annotation, f.annotation)
    with pytest.raises(RuntimeError, match="type-4 annotation has no native display"):
        drawing._assert_outboard_neck_dimension(
            f.adapter, f.side, f.native, 2, phase="after_drawing_save"
        )


@pytest.mark.parametrize("state", [1, 2])
def test_new_neck_preserves_the_actual_imported_driven_state(
    neck_dimension_fakes: SimpleNamespace, state: int,
) -> None:
    f = neck_dimension_fakes
    f.right_native.DrivenState = state
    assert drawing._add_outboard_neck_dimension(f.adapter, f.model, f.side) == (f.native, state)
    assert f.right_native.DrivenState == state


def test_neck_identity_follows_live_full_name_after_save_as(
    neck_dimension_fakes: SimpleNamespace,
) -> None:
    f = neck_dimension_fakes
    identity, state = drawing._add_outboard_neck_dimension(f.adapter, f.model, f.side)
    f.native.FullName = "RD1@FRONT@dt-crankshaft.SLDDRW"
    drawing._outboard_neck_checkpoint(f.adapter, f.side, identity, state, "after_drawing_save")


@pytest.mark.parametrize(
    "point",
    [
        (drawing.JOURNAL_START_X + 0.001, drawing.SIDE_CENTER[1]),
        (drawing.COLLAR_REAR_X - 0.001, drawing.SIDE_CENTER[1]),
        (drawing.OUTBOARD_NECK_DIAMETER_XY[0], drawing._sheet_y(spec.JOURNAL_DIA / 2.0)),
    ],
    ids=["journal", "collar", "journal-flank"],
)
def test_neck_arrow_cannot_identify_a_neighbouring_diameter(
    neck_dimension_fakes: SimpleNamespace, point: tuple[float, float],
) -> None:
    f = neck_dimension_fakes
    f.arrow_data.GetArrowHeadAtIndex2.return_value = (*point, *f.arrow_tip[2:])
    with pytest.raises(RuntimeError, match="does not identify the neck"):
        drawing._assert_neck_arrow_landing(f.display, label="neck")


@pytest.mark.parametrize("count", [0, -1, None, False])
def test_neck_requires_readable_rendered_arrowheads(
    neck_dimension_fakes: SimpleNamespace, count: object,
) -> None:
    f = neck_dimension_fakes
    f.arrow_data.GetArrowHeadCount.return_value = count
    with pytest.raises(RuntimeError, match="no readable native diameter arrowheads"):
        drawing._assert_neck_arrow_landing(f.display, label="neck")


@pytest.mark.parametrize("row", [(), (0.0,) * 11, (float("nan"),) * 12])
def test_neck_refuses_malformed_rendered_arrow_data(
    neck_dimension_fakes: SimpleNamespace, row: tuple[float, ...],
) -> None:
    f = neck_dimension_fakes
    f.arrow_data.GetArrowHeadAtIndex2.return_value = row
    with pytest.raises(RuntimeError, match="malformed native arrowhead"):
        drawing._assert_neck_arrow_landing(f.display, label="neck")


def test_native_neck_can_bracket_both_flanks_with_two_arrows(
    neck_dimension_fakes: SimpleNamespace,
) -> None:
    f = neck_dimension_fakes
    f.arrow_data.GetArrowHeadCount.return_value = 2
    f.arrow_data.GetArrowHeadAtIndex2.side_effect = (
        f.arrow_tip,
        (
            f.arrow_tip[0], drawing._sheet_y(spec.SHAFT_DIA / 2.0),
            0.0, 0.0, 1.0, 0.0, *f.arrow_tip[6:],
        ),
    )
    drawing._assert_neck_arrow_landing(f.display, label="neck")


def test_neck_display_is_redrawn_before_rendered_arrow_readback(
    neck_dimension_fakes: SimpleNamespace,
) -> None:
    f = neck_dimension_fakes
    events: list[str] = []
    f.model.GraphicsRedraw2.side_effect = lambda: events.append("redraw")

    def display_data():
        assert events == ["redraw"]
        events.append("display")
        return f.arrow_data

    f.display.GetDisplayData.side_effect = display_data
    drawing._add_outboard_neck_dimension(f.adapter, f.model, f.side)
    assert events == ["redraw", "display"]


def test_neck_display_redraw_failure_is_not_suppressed(
    neck_dimension_fakes: SimpleNamespace,
) -> None:
    f = neck_dimension_fakes
    f.model.GraphicsRedraw2.side_effect = RuntimeError("native redraw failed")
    with pytest.raises(RuntimeError, match="native redraw failed"):
        drawing._add_outboard_neck_dimension(f.adapter, f.model, f.side)
    f.display.GetDisplayData.assert_not_called()


@pytest.mark.parametrize("boundary", ["left", "right", "bottom", "top"])
def test_neck_arrow_accepts_small_sheet_readback_roundoff(
    neck_dimension_fakes: SimpleNamespace, boundary: str,
) -> None:
    f = neck_dimension_fakes
    x0, y0, x1, y1 = drawing.OUTBOARD_NECK_ARROW_WINDOW
    offset = drawing.NECK_ARROW_LANDING_TOLERANCE_M / 2.0
    midpoint = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    points = {
        "left": (x0 - offset, midpoint[1]),
        "right": (x1 + offset, midpoint[1]),
        "bottom": (midpoint[0], y0 - offset),
        "top": (midpoint[0], y1 + offset),
    }
    f.arrow_data.GetArrowHeadAtIndex2.return_value = (*points[boundary], *f.arrow_tip[2:])
    drawing._assert_neck_arrow_landing(f.display, label="neck")


def test_neck_arrow_rejects_drift_beyond_declared_sheet_tolerance(
    neck_dimension_fakes: SimpleNamespace,
) -> None:
    f = neck_dimension_fakes
    x1 = drawing.OUTBOARD_NECK_ARROW_WINDOW[2]
    tip = x1 + 2.0 * drawing.NECK_ARROW_LANDING_TOLERANCE_M, f.arrow_tip[1]
    f.arrow_data.GetArrowHeadAtIndex2.return_value = (*tip, *f.arrow_tip[2:])
    with pytest.raises(RuntimeError, match="does not identify the neck"):
        drawing._assert_neck_arrow_landing(f.display, label="neck")


@pytest.mark.parametrize(
    "direction",
    [
        (0.0, 1.0, 0.0), (0.0, -1.0, 0.0), (-1.0, 0.0, 0.0),
        (-1.0, -1.0, 0.0), (1e-7, -1.0, 0.0),
    ],
)
def test_neck_arrow_allows_vertical_or_neck_side_approach(
    neck_dimension_fakes: SimpleNamespace, direction: tuple[float, float, float],
) -> None:
    f = neck_dimension_fakes
    f.arrow_data.GetArrowHeadAtIndex2.return_value = (
        *f.arrow_tip[:3], *direction, *f.arrow_tip[6:]
    )
    drawing._assert_neck_arrow_landing(f.display, label="neck")


@pytest.mark.parametrize("direction", [(1.0, 0.0, 0.0), (1.0, -1.0, 0.0), (1e-4, 1.0, 0.0)])
def test_neck_arrow_rejects_journal_side_approach(
    neck_dimension_fakes: SimpleNamespace, direction: tuple[float, float, float],
) -> None:
    f = neck_dimension_fakes
    f.arrow_data.GetArrowHeadAtIndex2.return_value = (
        *f.arrow_tip[:3], *direction, *f.arrow_tip[6:]
    )
    with pytest.raises(RuntimeError, match="approaches from the journal side"):
        drawing._assert_neck_arrow_landing(f.display, label="neck")


@pytest.mark.parametrize("direction", [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0)])
def test_neck_arrow_rejects_zero_projected_direction(
    neck_dimension_fakes: SimpleNamespace, direction: tuple[float, float, float],
) -> None:
    f = neck_dimension_fakes
    f.arrow_data.GetArrowHeadAtIndex2.return_value = (
        *f.arrow_tip[:3], *direction, *f.arrow_tip[6:]
    )
    with pytest.raises(RuntimeError, match="unreadable native arrow direction"):
        drawing._assert_neck_arrow_landing(f.display, label="neck")
