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
    # drawing-simplicity-policy.md `How the repository implements the guidelines`: the part authors every printed dimension's places.
    assert "draw_dt_crankshaft.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # The 16T pin hole's REF witness is not printed: its size is on the hole's
    # callout (rule 9: no dimension on its hidden edges).
    assert drawing.UNPRINTED_DIMENSIONS <= spec.REFERENCE_DIMENSIONS
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked - drawing.UNPRINTED_DIMENSIONS
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
    # sprocket's seat on the shared plane, the one diameter of the collar; its
    # rear face bears on the post boss's south face (owner ruling D1: no
    # washer), and stays short of the outboard journal land.
    import build_dt_drive_train_assembly as bdt
    import dt_cone_pivot_post_spec as post
    import _sprocket_seat_geometry as removable

    assert bdt.CRANKSHAFT_Z0 + spec.SEAT_COLLAR == pytest.approx(removable.SEAT_FACE_Z)
    # The inch spigot (.689) is the wheel's seat to within its print grid.
    assert spec.SPIGOT_DIA == pytest.approx(removable.SEAT_SPIGOT_DIA, abs=0.001)
    assert not hasattr(spec, "COLLAR_DIA")
    # The blind drive-pin holes end in the collar, short of its rear face.
    assert spec.SEAT_COLLAR < spec.DRIVE_PIN_FLOOR < spec.COLLAR_REAR
    # The rear face from the post's own boss face, floored to its .XX print.
    boss_south = spec.POST_BORE_END - post.CRANK_BOSS_LENGTH
    assert spec.POST_BOSS_SOUTH == pytest.approx(boss_south)
    places = spec.COLLAR_STATION_PLACES
    pinion = spec.dt_crank_pinion_spec
    assert pinion.prints_exactly(spec.COLLAR_LENGTH, places, spec.UNIT)
    assert 0.0 <= boss_south - spec.COLLAR_REAR < pinion.print_step(places, spec.UNIT)
    assert spec.COLLAR_BOSS_AIR == pytest.approx(boss_south - spec.COLLAR_REAR)
    # The collar's shortest printed length is both stations' bands off it,
    # and its rear face keeps a bearing ring on the boss between the bore
    # mouth's break and its own edge break (the hand crank's end thrust).
    assert spec.COLLAR_LENGTH - 2.0 * spec.COLLAR_STATION_TOL - pinion.print_step(
        places, spec.UNIT
    ) < spec.COLLAR_LENGTH_MIN <= spec.COLLAR_LENGTH - 2.0 * spec.COLLAR_STATION_TOL + 1e-9
    ring = (
        (spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[1]) / 2.0
        - (post.CRANK_BORE_DIA + post.RUNNING_BORE_BAND[0]) / 2.0
        - 2.0 * spec.BORE_MOUTH_BREAK_MAX
    )
    assert spec.COLLAR_BEARING_RING_WORST <= ring + 1e-9
    assert spec.COLLAR_BEARING_RING_WORST >= spec.WALL_TARGET_MM
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


def test_knockout_wall_is_the_shortfall_its_callout_states() -> None:
    # Owner ruling 2026-11-13 (#1679, RV-07): each knockout runs on its pin
    # hole's axis, so its wall to the spigot rim is thicker than the pin
    # hole's and still under the floor; its callout prints the worst case.
    worst = (spec.SPIGOT_DIA + spec.SPIGOT_DIA_BAND[1]) / 2.0 - (
        spec.DRIVE_PIN_CIRCLE_RADIUS
        + spec.DRIVE_PIN_OFFSET_TOL
        + spec._KNOCKOUT_DIA_MAX / 2.0
    )
    wall = spec.DRIVE_PIN_KNOCKOUT_RIM_WORST
    assert worst - 0.0254 < wall <= worst
    assert spec.DRIVE_PIN_SPIGOT_RIM_WORST < wall < spec.WALL_FLOOR_MM
    printed = re.search(r"(\.\d{3}) MIN", notes.KNOCKOUT_CALLOUT_BELOW)
    assert printed
    assert float(printed.group(1)) * 25.4 == pytest.approx(wall)


def test_drive_pin_depth_prints_its_band_after_the_native_depth() -> None:
    # Machinist review of f7c9771b3: the bare 3.95 read under the title
    # block's .XX and left 5.75 - 4.46 = 1.29 of spigot under the holes.  The
    # callout carries the cut's own band, the one the proud stack reads.
    floor = spec.COLLAR_LENGTH_MIN - (spec.DRIVE_PIN_DEPTH + spec.DRIVE_PIN_DEPTH_TOL)
    assert floor == pytest.approx(spec.DRIVE_PIN_FLOOR_WALL_WORST)
    assert floor >= spec.WALL_FLOOR_MM
    band = notes.DRIVE_PIN_DEPTH_BAND
    process = spec.DRIVE_PIN_HOLE_PROCESS
    # The farm's native split: the count and diameter modifier in the
    # prefix, the depth in a later compartment.  Rule 26: size, process,
    # depth (round-3 machinist review), so REAM joins the depth's part.
    depth = "<HOLE-DEPTH> <hw-depth>"

    def parts(prefix: str = "2X <MOD-DIAM>", suffix: str = depth) -> dict:
        return {5: prefix, 6: suffix, 7: "", 8: ""}

    assert drawing._depth_banded_definition(parts(), band, process) == (
        6,
        f" {process} {depth} {band}",
    )
    whole = "2X <MOD-DIAM><hw-diam> <HOLE-DEPTH> <hw-depth>"
    assert drawing._depth_banded_definition(
        parts(prefix=whole, suffix=""), band, process
    ) == (
        5,
        f"2X <MOD-DIAM><hw-diam> {process} <HOLE-DEPTH> <hw-depth> {band}",
    )
    for broken in (
        parts(suffix="THRU ALL"),
        parts(suffix=f"{depth} {band}"),
        parts(suffix=f"{depth} PRESS FIT"),
        parts(suffix=f"<HOLE-DEPTH> 1.0 {depth}"),
        parts(prefix=f"2X {depth}"),
        parts(prefix=f"2X {process} <MOD-DIAM>"),
        {5: "2X <MOD-DIAM>", 6: depth},
    ):
        with pytest.raises(RuntimeError):
            drawing._depth_banded_definition(broken, band, process)


def test_integral_dome_is_the_only_outboard_shaft_projection() -> None:
    assert spec.SHAFT_DIA == geometry.SHAFT_DIA
    assert spec.SHAFT_DIA == pytest.approx(9.525, abs=1e-12)
    # A cap within the Ø.375: nothing outboard of the shank's own diameter.
    assert 0.0 < spec.SHAFT_DOME_HEIGHT <= spec.SHAFT_DIA / 2.0
    # The REF stub may sit line-on-line with MHA-DT-31's 3/8 drill nominal
    # (D27, delegated ruling 2026-11-25 (Main), precedent: the fit-necessity
    # rule of the owner-approved fit policy (owner ruling 2026-11-24); owner
    # review #2144); it is turned to the measured bore less the fit's clearance.
    assert geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[0] <= (
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[1]
    )
    assert not hasattr(spec, "CRANK_END_NOTE")


def test_sheet_note_rows_end_left_of_the_title_block() -> None:
    # The widest row proven on the farm sheet is note 1's second (73
    # characters, ending 31 mm left of the title block); a 99-character note 2
    # ran across the title block's border (machinist review of 76e4489d85).
    rows = notes.SHEET_NOTES.replace("<MOD-DIAM>", "Ø").splitlines()
    assert max(len(row) for row in rows) <= 73


def test_mha024_station_and_notes_belong_to_hub_and_shaft() -> None:
    assert part.PIN_HOLE_SPEC is spec.PIN_HOLE_SPEC
    assert drawing.PIN_HOLE_SPEC is spec.PIN_HOLE_SPEC
    assert drawing._PIN_HOLE_DIA == blind_cut_dia_mm(spec.PIN_HOLE_SPEC)
    assert spec.PIN_HOLE_HEIGHT == geometry.SERVICE_PIN_STATION == pytest.approx(13.462)
    # The drill size reads first (the prefix of the native callout); the
    # callout links numbered note 1, the matched taper ream naming both mating
    # parts and its acceptance.
    assert spec.CROSS_HOLE_PROCESS == "#9 DRILL"
    assert notes.CROSS_HOLE_CALLOUT == f"SEE NOTE {notes.CROSS_HOLE_NOTE_NUMBER}"
    note = " ".join(notes.CROSS_HOLE_NOTE.split())
    assert note.startswith(f"{notes.CROSS_HOLE_NOTE_NUMBER}. ")
    assert note in " ".join(notes.SHEET_NOTES.split())
    assert "TAPER-REAM" in note
    assert "MHA-DT-31" in note
    assert "MHA-DT-09" in note
    assert "MHA-DT-06" not in note


def test_shaft_end_fiducial_is_a_simple_punch_not_a_dimensioned_dimple() -> None:
    assert spec.FIDUCIAL_MODEL_DIA == geometry.FIDUCIAL_MODEL_DIA == 0.8
    assert spec.FIDUCIAL_MODEL_DEPTH == geometry.FIDUCIAL_MODEL_DEPTH == 0.2
    assert spec.SHAFT_FIDUCIAL_RADIUS == geometry.SHAFT_FIDUCIAL_RADIUS == 2.5
    assert "PUNCH" in notes.FIDUCIAL_NOTE
    assert "BY EYE" not in notes.FIDUCIAL_NOTE
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
    end_radius = spec.SPIGOT_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.END_CENTER[0] + end_radius < drawing.DOME_TIP_X


# Measured on the 19e33c6c2 stack-top render (3.5 mm text, 2:1 sheet): the
# "7.000 ±0.025" value is 27.5 mm wide.
_PIN_VALUE_TEXT_WIDTH = 0.0275


def test_pin_locations_print_value_and_band_only() -> None:
    # Rule 7: a location dimension carries its value and band and nothing
    # else; the sprocket the band serves is named once, on the REAM callout.
    # Machinist review of 19e33c6c2: the value must end, with air, before the
    # dome tip's extension lines.
    assert "MHA-PD-09" in notes.DRIVE_PIN_CALLOUT
    for name, (x, _y) in drawing.END_PIN_KEEP.items():
        assert name not in drawing.CALLOUTS_BELOW
        assert name not in drawing.CALLOUTS_ABOVE
        assert x + _PIN_VALUE_TEXT_WIDTH + 0.001 < drawing.DOME_TIP_X, name


def test_blind_pin_holes_bottom_in_the_collar_short_of_its_rear_face() -> None:
    # The holes lie wholly inside the spigot, which runs to the rear face:
    # the floor is the collar's worst-case length less the deepest hole,
    # over the 2.0 wall target.
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
    # shares with the collar's OD and above the neck it steps down to.
    (washer_face,) = [c for c in spec.SURFACE_FINISHES if c.key not in lands]
    assert washer_face.key == "collar_rear_face"
    pick, _symbol = drawing.COLLAR_REAR_FINISH
    assert pick[0] == pytest.approx(drawing._sheet_x(washer_face.face.offset_mm))
    corner_y = drawing._sheet_y(spec.SPIGOT_DIA / 2.0)
    assert drawing._sheet_y(spec.SHAFT_DIA / 2.0) < pick[1] <= corner_y - 0.0015


def test_both_bare_necks_print_one_model_loose_diameter() -> None:
    # Every bare land of the Ø.375 core is covered by a model diameter: the
    # shank its hub fit, both necks one 2X witness at the loose band.
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
    assert spec.DRAWING_DIMENSIONS["PinionSeatProfile"] >= {"NeckDiaDim"}
    assert spec.DRAWING_PRECISION_BY_NAME["NeckDiaDim"] == spec.NECK_DIA_PLACES == 3
    necks = len(spec.SHAFT_CORE_LANDS) - 1
    assert drawing.CALLOUTS_ABOVE["NeckDiaDim"] == f"{necks}X"
    assert drawing.JOURNAL_END_X < drawing.DIAMETER_POSITIONS["NeckDiaDim"][0] < drawing.SEAT_STEP_X
    # The loose band keeps the neck under the journal at print-worst.
    assert spec.SHAFT_DIA + spec.NECK_DIA_TOL < spec.JOURNAL_DIA + spec.JOURNAL_DIA_BAND[1]


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
    lines = notes.PINION_PIN_CALLOUT.replace("<MOD-DIAM>", "D").split("\n")
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
    # The leader starts at the end of the last row (farm round 1), so that
    # row is the longest: the leader then drops from the text's right end,
    # right of the Ø.3125's block and still left of the isometric.
    assert len(lines[-1]) == max(map(len, lines))


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
    assert bdt.CRANK_HUB_SPROCKET_AIR == pytest.approx(bdt.CRANK_HUB_SPROCKET_AIR_CONTRACT)
    assert bdt.CRANK_HUB_SPROCKET_AIR_WORST == pytest.approx(
        bdt.CRANK_HUB_SPROCKET_AIR + min(spec.SEAT_COLLAR_BAND)
    )
    assert bdt.CRANK_HUB_SPROCKET_AIR_WORST > 0.0


def test_station_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880: a reference sketch owns printed dimensions but no geometry, so the
    # part saves it hidden (no assembly instance renders it) and the drawing
    # shows it per view through _drawing_hidden_sketches to import them.
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
    # Two rows at most (rule 7), a caption's height and more under the
    # isometric caption's field so it does not read as part of it.
    assert len(notes.CENTRES_NOTE.splitlines()) == 2
    assert y1 - drawing.CENTRES_NOTE_XY[1] >= 0.005
    assert drawing._inside(drawing.CENTRES_NOTE_XY, field)
    assert len(notes.CENTRES_NOTE.splitlines()) <= TEXT_ROW_LIMIT
    # The whole text field and landing window stay below MATCH DRILL's
    # field. These bounds constrain the intended corridor, not native ink.
    match_floor = drawing.PINION_PIN_NOTE_FIELD[1]
    assert max(y1, drawing.FAR_END_FRONT_RIM_WINDOW[3]) < match_floor
    assert drawing.CENTRES_NOTE_XY[0] > drawing.FAR_END_FRONT_RIM_PICK[0]


def test_turned_fits_print_ref_and_the_holes_print_the_reamer() -> None:
    # Fit audit 2026-11-23 (MHA-DT-31.bore__MHA-DT-11.hub_shaft,
    # MHA-DT-11.journals, MHA-DT-10.bore__MHA-DT-11.pinion_seat,
    # MHA-DT-11.drive_pin_holes): the crankshaft is made last, so each fit
    # diameter is a REF turned to its mate's reamed bore (note 3, the one
    # acceptance), and the drive-pin holes print the .0930 reamer with no
    # band, the pressed dowel their acceptance.
    fits = {"ShaftDiaDim", "JournalDiaDim", "PinionSeatDiaDim"}
    assert fits <= spec.REFERENCE_DIMENSIONS
    assert fits <= spec.DIAMETER_REFERENCES
    source = Path(part.__file__).read_text(encoding="utf-8")
    toleranced = set(
        re.findall(
            r"set_dimension_\w+_tolerance\(\s*adapter,\s*\"\w+\",\s*f?\"([A-Za-z]+)", source
        )
    )
    assert "SpigotDiaDim" in toleranced
    assert not toleranced & (fits | {"DrivePinHoleDia"})
    assert notes.FIT_NOTE.startswith("3. TURN EACH FIT TO ITS MATE'S BORE LESS .0010-.0023:")
    assert notes.DRIVE_PIN_CALLOUT.splitlines()[0] == (
        "MHA-DT-VN-67 PRESSES IN, NOT BY HAND; DRIVES MHA-PD-09"
    )
