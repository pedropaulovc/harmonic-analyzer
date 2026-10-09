"""Offline contracts for the through-hub crankshaft drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import build_dt_crankshaft as part
import dt_crank_hub_geometry as geometry
import dt_crankshaft_notes as notes
import dt_crankshaft_spec as spec
import draw_dt_crankshaft as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crankshaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crankshaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crankshaft_drawing.png")
    assert DRAWINGS_BY_NAME["dt_crankshaft"].script == Path(drawing.__file__).resolve()




def test_policy_migrated_sheet_carries_no_gdt_and_model_owned_places() -> None:
    # Rule 3: a shaft carries no frames, datums or basic dimensions.
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_feature_control_frame",
        "add_datum_feature",
        "set_basic_dimension",
        "set_dimension_precision",
    ):
        assert helper not in source
    # Rule 2: the part authors every printed dimension's places.
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
    # bands (rule 12) at the places that hold them; the rest at one.
    functional_places = {
        "ShaftDiaDim": 3,
        "JournalDiaDim": 3,
        "PinionSeatDiaDim": 3,
        "CollarDiaDim": 2,
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
    # W15: the boss recess survives the printed limits, while the shaft
    # datum independently lands on the post's restored north face.
    pinion = spec.dt_crank_pinion_spec
    assert spec.SHAFT_LENGTH == round(spec.SHAFT_LENGTH, pinion.SHAFT_LENGTH_PLACES)
    assert spec.DRAWING_PRECISION["Shaft"]["Depth"] == pinion.SHAFT_LENGTH_PLACES
    assert pinion.SHAFT_END_RECESS_MIN <= spec.SHAFT_END_RECESS <= pinion.SHAFT_END_RECESS_MAX
    import cone_line
    import dt_cone_pivot_post_spec as post

    post_boss_north = cone_line.cone_station(cone_line.POST_STATION)[2] - post.CRANK_BOSS_START_Z
    assert -183.0 + spec.POST_BORE_END == pytest.approx(post_boss_north)


def test_seat_collar_lands_the_wheel_seat_and_leaves_the_washer_its_fit() -> None:
    # The collar's front is the Ø17.5 seat spigot, whose face is the removable
    # sprocket's seat on the shared plane, stepping up to the Ø20.6 body; its
    # rear face stands off the post boss by the gap MHA-DT-036 is faced to fill,
    # and stays short of the outboard journal land.
    import build_dt_drive_train_assembly as bdt
    import dt_cone_pivot_post_spec as post
    import dt_crank_seat_washer_spec as washer
    import pd_transgear_removable_spec as removable

    assert bdt.CRANKSHAFT_Z0 + spec.SEAT_COLLAR == pytest.approx(removable.SEAT_FACE_Z)
    assert spec.SPIGOT_DIA == removable.SEAT_SPIGOT_DIA < spec.COLLAR_DIA
    # Ruling 2026-09-30: spigot -154.3..-148.5; MHA-DT-036 floor 0.5: body
    # -148.5..-144.5.
    assert bdt.CRANKSHAFT_Z0 + spec.SPIGOT_END == pytest.approx(-148.5)
    # The blind drive-pin holes end in the spigot, short of its step.
    assert spec.SEAT_COLLAR < spec.DRIVE_PIN_FLOOR < spec.SPIGOT_END
    assert bdt.CRANKSHAFT_Z0 + spec.COLLAR_REAR == pytest.approx(-144.5)
    # The gap from the post's own boss face, not the washer spec's chain.
    boss_south = spec.POST_BORE_END - post.CRANK_BOSS_LENGTH
    assert boss_south - spec.COLLAR_REAR == pytest.approx(washer.GAP_NOMINAL)
    assert washer.GAP_MIN >= washer.THICKNESS_FLOOR - 1e-9
    # The body keeps length at print-worst: both stations and the spigot.
    body_worst = (
        spec.COLLAR_LENGTH
        - spec.SPIGOT_LENGTH
        - 2.0 * spec.COLLAR_STATION_TOL
        - spec.SPIGOT_LENGTH_TOL
    )
    assert body_worst > 0.0
    assert spec.COLLAR_REAR + spec.COLLAR_STATION_TOL < spec.JOURNAL_START
    # Bottomed dowels stand proud by the drive-train's pin length budget.
    assert (
        bdt.CRANKSHAFT_Z0 + spec.DRIVE_PIN_FLOOR - spec.vn_crank_seat_drive_pin_spec.LENGTH
        == (pytest.approx(removable.DRIVE_PIN_TIP_Z))
    )


_POLICY = (
    Path(spec.__file__).resolve().parents[1] / "docs" / "drawing-simplicity-policy.md"
)


def _floor_2(value: float) -> float:
    return math.floor(value * 100.0 + 1e-9) / 100.0


def test_spigot_rim_is_the_named_exception_the_sheet_states() -> None:
    # The drive-pin holes' rim to the Ø17.5 seat spigot is under the policy's
    # wall floor (a named exception, MHA-DT-011): the worst case of the printed
    # bands is what the sheet states under the holes' callout and what the
    # policy row records, rounded down so neither claims more rim than exists.
    policy = _POLICY.read_text(encoding="utf-8")
    floor = re.search(r"hard floor of \*\*(\d+(?:\.\d+)?) mm\*\*", policy)
    assert floor
    section = policy.split("\n## Named exceptions", 1)[1].split("\n## ", 1)[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("| MHA-DT-011 ")
    ]
    (shortfall,) = [cells[1] for cells in rows if "spigot" in cells[0]]
    recorded = re.search(
        r"spigot rim (\d+\.\d\d) nominal, (\d+\.\d\d) at the worst case",
        shortfall,
        re.IGNORECASE,
    )
    assert recorded, shortfall
    hole_r = spec.DRIVE_PIN_HOLE_DIA / 2.0
    nominal = spec.SPIGOT_DIA / 2.0 - (spec.DRIVE_PIN_CIRCLE_RADIUS + hole_r)
    worst = (spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[1]) / 2.0 - (
        spec.DRIVE_PIN_CIRCLE_RADIUS
        + spec.DRIVE_PIN_OFFSET_TOL
        + hole_r
        + spec.DRIVE_PIN_HOLE_BAND[0] / 2.0
    )
    rim = spec.DRIVE_PIN_SPIGOT_RIM_WORST
    assert rim == _floor_2(worst)
    assert 0.0 < rim < float(floor.group(1))
    printed = re.search(r"SPIGOT RIM (\d+\.\d\d) MIN\.", notes.DRIVE_PIN_CALLOUT)
    assert printed
    assert float(printed.group(1)) == rim
    assert float(recorded.group(2)) == rim
    assert float(recorded.group(1)) == _floor_2(nominal) == spec.DRIVE_PIN_SPIGOT_RIM


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
    assert "MHA-DT-031" in callout
    assert "MHA-DT-009" in callout
    assert "MHA-DT-006" not in callout


def test_shaft_end_fiducial_is_a_simple_punch_not_a_dimensioned_dimple() -> None:
    assert spec.FIDUCIAL_MODEL_DIA == geometry.FIDUCIAL_MODEL_DIA == 0.8
    assert spec.FIDUCIAL_MODEL_DEPTH == geometry.FIDUCIAL_MODEL_DEPTH == 0.2
    assert spec.SHAFT_FIDUCIAL_RADIUS == geometry.SHAFT_FIDUCIAL_RADIUS == 2.5
    assert "PUNCH FIDUCIAL MARK" in spec.DRAWING_NOTES
    assert "BY EYE" in spec.DRAWING_NOTES
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert all("Fiducial" not in name for name in marked)
    assert "DIMPLE" not in spec.DRAWING_NOTES


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
# 2.75 mm a character ("SPROCKET MHA-PD-009", 44 mm).
_PIN_VALUE_TEXT_WIDTH = 0.0275
_CALLOUT_CHAR_WIDTH = 0.00275


def test_lower_pin_location_text_ends_before_the_dome_extension_lines() -> None:
    # Machinist review of 19e33c6c2: the text block runs right from the
    # dimension line beside the end view, and the old two-row callout carried
    # the value and its mate note across the dome tip's and dome root's
    # extension lines.  Every row must end, with air, before the dome tip.
    x, _y = drawing.END_PIN_KEEP["DrivePinOffset2"]
    rows = notes.DRIVE_PIN_LOCATION_CALLOUT.splitlines()
    assert "MHA-PD-009" in rows and "SPROCKET" in " ".join(rows)
    block = max(
        _PIN_VALUE_TEXT_WIDTH,
        max(len(row) for row in rows) * _CALLOUT_CHAR_WIDTH,
    )
    assert x + block + 0.001 < drawing.DOME_TIP_X


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


def test_shaft_diameter_callout_counts_every_bare_core_land() -> None:
    # Machinist review of 8b5e1f354: the 2X Ø9.525 sat with three bare core
    # lands in the side view and did not say which two it meant.  The core
    # runs dome root to far end; the collar, the journal (its relief stays
    # proud of the core) and the Ø9 seat cover the rest, as the build lays
    # them, so the callout counts every land left bare.
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
    assert drawing.CALLOUTS_ABOVE["ShaftDiaDim"] == f"{len(bare)}X" == "3X"


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
    # R0.25 stands the bore edge off, which the seat gap's north range (the
    # range the W15 pin-wall and recess stacks carry) must hold.
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
    # W15 band (a): a long shaft would stand proud of the 16T boss, so the
    # length only comes out short, and the model's Depth carries the band.
    assert spec.SHAFT_LENGTH_BAND == (0.00, -0.40)
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Shaft", "Depth", *deviations(SHAFT_LENGTH_BAND)' in build
    assert "Depth" in spec.DRAWING_DIMENSIONS["Shaft"]
    assert "Depth" not in spec.REFERENCE_DIMENSIONS


def test_shaft_band_ruling_holds_because_the_general_tolerance_fails_both_stacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # RULING W15-SHAFT-BAND (machinist review of f0c105531 flagged the band as
    # over-specified): the unilateral +0/-0.4 is functional. With the shaft at
    # the title block's .X +/-0.8 instead, both W15 stacks fail.
    import build_dt_drive_train_assembly as bdt

    assert spec.SHAFT_LENGTH_BAND == (0.0, -0.4)
    shaft, pinion = spec.SHAFT_LENGTH, bdt.PINION_OVERALL_LENGTH
    edge_nominal, recess_nominal = bdt.PINION_PIN_EDGE_NOMINAL_ACTUAL, bdt.PINION_RECESS_NOMINAL
    assert sum(bdt.pinion_pin_edge_stack(edge_nominal, shaft, pinion).values()) >= (
        bdt.PINION_PIN_EDGE_MIN_WORST
    )
    assert sum(bdt.pinion_recess_stack(recess_nominal, shaft, pinion).values()) >= (
        bdt.PINION_RECESS_MIN_WORST
    )
    monkeypatch.setattr(bdt, "_SHAFT_LENGTH_LIMITS", (-0.8, 0.8))
    edge = sum(bdt.pinion_pin_edge_stack(edge_nominal, shaft, pinion).values())
    recess = sum(bdt.pinion_recess_stack(recess_nominal, shaft, pinion).values())
    assert edge < bdt.PINION_PIN_EDGE_MIN_WORST
    assert recess < bdt.PINION_RECESS_MIN_WORST






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


def test_native_shaft_refuses_an_unselected_or_stale_stock_form_clock(monkeypatch) -> None:
    import dt_crank_pinion_spec as pinion
    import crank_mesh_stack as mesh

    monkeypatch.setattr(pinion._config, "machine", lambda *_keys: {})
    with pytest.raises(RuntimeError, match="UNQUALIFIED crank phase"):
        pinion.require_selected_pin_clocking()
    monkeypatch.setattr(
        pinion._config, "machine",
        lambda *_keys: {"crank_mesh_phase_offset_deg": math.inf},
    )
    with pytest.raises(ValueError, match="must be finite"):
        pinion.require_selected_pin_clocking()
    monkeypatch.setattr(mesh, "require_qualified", lambda: {"phase_seed_deg": -0.5})
    monkeypatch.setattr(
        pinion._config, "machine",
        lambda *_keys: {"crank_mesh_phase_offset_deg": 0.5},
    )
    with pytest.raises(RuntimeError, match="retention clock is stale"):
        pinion.require_selected_pin_clocking()
    monkeypatch.setattr(
        pinion._config, "machine",
        lambda *_keys: {"crank_mesh_phase_offset_deg": -0.5},
    )
    assert pinion.require_selected_pin_clocking() == pytest.approx(pinion._PINION_DATUM_CLOCK_DEG - 0.5)
    def refused():
        raise ValueError("synthetic current-source calibration refusal")
    monkeypatch.setattr(mesh, "require_qualified", refused)
    with pytest.raises(ValueError, match="current-source calibration refusal"):
        pinion.require_selected_pin_clocking()
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(adapter)"):]
    assert body.index("require_selected_pin_clocking()") < body.index("await adapter.create_part()")
