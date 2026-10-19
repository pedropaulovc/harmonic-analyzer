"""Offline release contracts for separate through hub MHA-DT-31."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import dt_crank_hub_geometry as geometry
import dt_crank_hub_notes
import dt_crank_hub_spec
import dt_crankshaft_spec
import draw_dt_crank_hub as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_outboard_proportions_follow_the_u29_enlargement() -> None:
    unit = geometry.SHAFT_DIA / geometry.PHOTO_SHAFT
    scale = geometry.OUTBOARD_SCALE
    assert scale == 1.3
    assert geometry.PHOTO_HUB_SEAT_DIA == 19.5
    assert geometry.PHOTO_HUB_SEAT_DIA == pytest.approx(2.60 * unit * scale, abs=0.05)
    # Named deviation: 0.1 under the photograph keeps the U29 cheek at 2.0.
    assert geometry.HUB_SEAT_DIA == 19.4
    # Stock sizes: the pin is the dowel just under 1.3x, the arm is 1-in bar.
    assert geometry.AXIAL_PIN_DIA == 4.0 < 0.59 * unit * scale
    assert geometry.ARM_WIDTH == pytest.approx(25.4)
    # Named ratio deviation from the photograph (U29).
    assert geometry.ARM_TO_HUB_RATIO == pytest.approx(1.309, abs=1e-3)
    assert geometry.PHOTO_ARM_TO_HUB_RATIO == pytest.approx(1.208, abs=1e-3)


def test_u27_walls_hold_two_millimetres_at_the_printed_bands() -> None:
    assert geometry.WALL_TARGET_MM == 2.0
    assert geometry.SEAM_WEB_WORST_MM == pytest.approx(2.004, abs=1e-3)
    assert geometry.ARM_CHEEK_WORST_MM == pytest.approx(2.049, abs=1e-3)


def test_arm_shoulder_keeps_its_land_over_the_largest_matched_seat() -> None:
    """Codex P2 on 16146c26f: the arm is pressed to the barrel's front face,
    and the seat is turned to whatever MHA-DT-06 bore it meets.  At the printed
    limits the largest bore (.X) plus the tightest press stands inside the
    smallest barrel the sheet allows; after the arm bore's and the barrel
    corner's edge breaks a land at least one edge break wide must be left."""
    one_place = round(float(_config.title_block("linear_1pl")["value_in"]) * 25.4, 1)
    two_place = round(float(_config.title_block("linear_2pl")["value_in"]) * 25.4, 2)
    edge_break = float(_config.title_block("edge_break")["chamfer_max_mm"])
    band = {1: one_place, 2: two_place}
    seat_max = (
        geometry.HUB_SEAT_DIA
        + band[dt_crank_hub_spec.DRAWING_PRECISION_BY_NAME["SeatDia"]]
        + 0.030
    )
    assert seat_max == pytest.approx(20.23)
    barrel_places = dt_crank_hub_spec.DRAWING_PRECISION_BY_NAME["BarrelDia"]
    barrel_min = geometry.HUB_BARREL_DIA - band[barrel_places]
    land = (barrel_min - seat_max) / 2.0 - 2.0 * edge_break
    assert land >= edge_break
    assert geometry.HUB_SHOULDER_LAND_WORST_MM == pytest.approx(land)
    assert geometry.SHOULDER_LAND_WORST_MIN == edge_break
    assert geometry.SEAT_PRESS_INTERFERENCE[1] == 0.030
    # The same barrel at the title block's .X leaves a 0.11 sliver.
    with pytest.raises(AssertionError, match="shoulder land 0.110"):
        geometry.shoulder_land(geometry.HUB_BARREL_DIA - one_place, seat_max)


def test_mha024_ream_ligaments_meet_rule_12_at_the_printed_bands() -> None:
    # CONTRACT-crank MHA-DT-31: 8 seat + 17.2 of hub behind the shoulder (19
    # until the seat face moved 1.8 forward, ruling 2026-09-30), the ream
    # station unchanged 5.6 from the shoulder at .XX.  The rear 3.85 is the
    # chain-plate relief (Main, 2026-09-30; lengthened from 3.6 for the
    # floated wheel, PR1 Codex review 2), so the barrel is 13.35.  R9-38 took
    # it Ø20.6 -> Ø22.25 at .XX for the arm shoulder's land.
    assert geometry.HUB_BARREL_DIA == 22.25
    assert geometry.HUB_LENGTH == pytest.approx(25.2)
    assert geometry.HUB_BARREL_LENGTH == pytest.approx(13.35)
    assert geometry.SERVICE_PIN_FROM_SHOULDER == 5.6
    assert geometry.SERVICE_PIN_STATION == pytest.approx(13.6)
    assert dt_crank_hub_spec.DRAWING_PRECISION["ServicePinStationReference"] == {
        "ServicePinFromShoulder": 2
    }
    # The contract's nominal walls and ligaments.
    ream_r = geometry.SERVICE_PIN_REAM_RADIUS_MAX
    rear_from_shoulder = geometry.HUB_BARREL_LENGTH - geometry.SERVICE_PIN_FROM_SHOULDER
    assert (geometry.HUB_SEAT_DIA - geometry.HUB_BORE_DIA) / 2 == pytest.approx(
        4.92, abs=0.01
    )
    assert geometry.HUB_BARREL_DIA / 2 - ream_r == pytest.approx(8.155, abs=0.01)
    assert geometry.SERVICE_PIN_FROM_SHOULDER - ream_r == pytest.approx(2.63, abs=0.01)
    # The ream ends at the relief shoulder, not the rear face.
    assert rear_from_shoulder - ream_r == pytest.approx(4.78, abs=0.01)
    # Worst case at the printed bands (drawing-guidelines.md rule 17 (walls and webs)): the shoulder side governs.
    # Behind the ream the relief shoulder is placed from the front face by
    # the .XX overall less the .XX relief, the ream by the .X seat length and
    # the .XX station: 21.25 - 8.8 - 6.11 - 2.97.
    assert geometry.SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM == pytest.approx(
        2.121, abs=1e-3
    )
    assert geometry.SERVICE_PIN_REAR_LIGAMENT_WORST_MM == pytest.approx(3.321, abs=1e-3)
    assert geometry.SERVICE_PIN_BARREL_WALL_WORST_MM == pytest.approx(7.901, abs=1e-3)


def test_rear_relief_clears_the_t12_chain_plates_and_keeps_its_wall() -> None:
    # Ruling 2026-09-30 (bought ANSI #25 chain at print-worst): Ø16.5 x 3.85,
    # rear face at station 25.2 (machine -157.8, 0.7 in front of the T12
    # after the seat face moved 1.8 forward), barrel shoulder at 21.35
    # (machine -161.65).
    assert (geometry.RELIEF_DIA, geometry.RELIEF_LENGTH) == (16.5, 3.85)
    assert geometry.RELIEF_STATION == pytest.approx(21.35)
    assert geometry.RELIEF_STATION == pytest.approx(
        geometry.HUB_SEAT_LENGTH + geometry.HUB_BARREL_LENGTH
    )
    # Title-block .XX on the clearance diameter (R9-37: 0.23 to a real #25
    # plate on the floated T12, 0.08 at .X; test_transgear_removable_seat
    # judges that corner); the length carries the functional ±0.05 that holds
    # the chain's floated axial air exactly at its floor, and the overall that
    # places the rear face it is printed from carries ±0.10.
    assert geometry.RELIEF_DIA_MAX == pytest.approx(17.01)
    assert geometry.RELIEF_LENGTH_TOL == 0.05
    assert geometry.HUB_LENGTH_TOL == 0.10
    assert dt_crank_hub_spec.DRAWING_PRECISION["HubProfile"]["ReliefLength"] == 2
    assert dt_crank_hub_spec.DRAWING_PRECISION["HubProfile"]["HubLength"] == 2
    assert dt_crank_hub_spec.DRAWING_PRECISION["HubProfile"]["ReliefDia"] == 2
    # drawing-guidelines.md rule 17 (walls and webs) wall over the bore: Ø15.99 against the Ø9.580 bore, edges broken.
    assert geometry.RELIEF_WALL_WORST_MM == pytest.approx(2.705, abs=1e-3)
    assert geometry.RELIEF_WALL_WORST_MM >= geometry.WALL_TARGET_MM
    # The MHA-DT-09 ream stays on the full barrel.
    assert (
        geometry.SERVICE_PIN_STATION + geometry.SERVICE_PIN_REAM_RADIUS_MAX
        < geometry.RELIEF_STATION
    )


def test_hub_overall_band_is_loosened_to_what_the_rear_face_stacks_hold() -> None:
    # Machinist review of 19e33c6c2: 25.20 +/-0.05 was tighter than the rear
    # face needs.  At +/-0.10 the drive-pin tips keep air to it and the wheel
    # floated onto it stays on its pins; the title block's .XX +/-0.51 would
    # stand the hub on the pin tips.
    kwargs = dict(
        seat_face=dt_crankshaft_spec.SEAT_COLLAR,
        seat_face_band=dt_crankshaft_spec.SEAT_COLLAR_BAND,
        hub_rear=geometry.HUB_LENGTH,
        plate_min=dt_crankshaft_spec.pd_transgear_removable_spec.PLATE
        + min(dt_crankshaft_spec.pd_transgear_removable_spec.PLATE_BAND),
    )
    air, engagement = dt_crankshaft_spec.drive_pin_front_clearances(
        dt_crankshaft_spec.DRIVE_PIN_PROUD_RANGE,
        hub_rear_tol=geometry.HUB_LENGTH_TOL,
        **kwargs,
    )
    assert geometry.HUB_LENGTH_TOL == 0.10
    assert air == pytest.approx(0.146, abs=1e-9)
    assert engagement == pytest.approx(1.046, abs=1e-9)
    with pytest.raises(AssertionError, match="hub's rear face"):
        dt_crankshaft_spec.drive_pin_front_clearances(
            dt_crankshaft_spec.DRIVE_PIN_PROUD_RANGE,
            hub_rear_tol=geometry.GENERAL_2PL_TOL_MM,
            **kwargs,
        )


def _stack_a(relief_length: float) -> dict[str, float]:
    return geometry.chain_shoulder_axial_air(
        relief_length=relief_length,
        seat_face=dt_crankshaft_spec.SEAT_COLLAR,
        seat_face_band=dt_crankshaft_spec.SEAT_COLLAR_BAND,
    )


def test_chain_clears_the_relief_shoulder_with_the_wheel_floated_onto_the_hub() -> None:
    # Codex PR1 review 2: the wheel may walk forward off its drive pins until
    # its front face meets the hub rear face (the pin check admits it).  The
    # thinnest wheel there, with the shortest relief, brings a bought chain's
    # frontmost envelope nearest the barrel shoulder; the old 3.6 relief let
    # it cut 0.0365 into the shoulder while the seated check passed.  (With the
    # hub's +/-0.10 the seated pose also closes on 3.6, so the seat is set 1.0
    # aft here to leave the floated pose, which ignores it, as the only fault.)
    with pytest.raises(AssertionError, match="floated_worst -0.0365"):
        geometry.chain_shoulder_axial_air(
            relief_length=3.6,
            seat_face=dt_crankshaft_spec.SEAT_COLLAR + 1.0,
            seat_face_band=dt_crankshaft_spec.SEAT_COLLAR_BAND,
        )
    airs = _stack_a(geometry.RELIEF_LENGTH)
    assert airs["floated_worst"] == pytest.approx(0.2135, abs=1e-9)
    assert airs["floated"] == pytest.approx(0.3635, abs=1e-9)
    assert airs["seated_worst"] == pytest.approx(0.4135, abs=1e-9)
    assert airs["seated"] == pytest.approx(1.0635, abs=1e-9)
    # The floated pose governs, and the relief is the shortest .XX length
    # that holds the floor there.
    assert airs["floated_worst"] < airs["seated_worst"]
    with pytest.raises(AssertionError, match="floated_worst"):
        _stack_a(geometry.RELIEF_LENGTH - 0.01)


def test_floated_stack_a_ignores_the_seat_and_hub_stations() -> None:
    # The wheel and the shoulder both ride the hub rear face, so moving the
    # seat moves only the seated pose.
    moved = geometry.chain_shoulder_axial_air(
        relief_length=geometry.RELIEF_LENGTH,
        seat_face=dt_crankshaft_spec.SEAT_COLLAR + 1.0,
        seat_face_band=dt_crankshaft_spec.SEAT_COLLAR_BAND,
    )
    base = _stack_a(geometry.RELIEF_LENGTH)
    assert moved["floated_worst"] == pytest.approx(base["floated_worst"])
    assert moved["seated_worst"] == pytest.approx(base["seated_worst"] + 1.0)


def test_named_shaft_fit_class_bounds_the_through_bore() -> None:
    shaft_limits = (
        geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[1],
        geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[0],
    )
    bore_limits = (
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[1],
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[0],
    )
    clearances = (bore_limits[0] - shaft_limits[1], bore_limits[1] - shaft_limits[0])
    assert clearances == pytest.approx(
        tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    )


def test_seat_press_sits_inside_the_iso_locational_interference_fit() -> None:
    # ISO 286-2, 18-30 mm: H7 hole 0/+0.021; p6 shaft +0.022/+0.035.
    assert 18.0 < geometry.HUB_SEAT_DIA <= 30.0
    h7_upper, p6_lower, p6_upper = 0.021, 0.022, 0.035
    iso = (p6_lower - h7_upper, p6_upper)  # 0.001-0.035 diametral
    low, high = dt_crank_hub_notes.SEAT_PRESS_INTERFERENCE
    assert iso[0] < low < high <= iso[1]
    # A real press at the loose end: the match-turned seat never goes
    # line-to-line.
    assert low >= 0.010


def test_hub_shoulder_and_pin_stations_preserve_removal_topology() -> None:
    assert geometry.HUB_SEAT_LENGTH == geometry.ARM_THICKNESS
    assert geometry.HUB_SHOULDER_STATION < geometry.SERVICE_PIN_STATION
    assert geometry.SERVICE_PIN_STATION < geometry.HUB_LENGTH
    assert geometry.AXIAL_PIN_LENGTH == geometry.ARM_THICKNESS / 2.0


def test_drawing_registry_and_marks_are_complete() -> None:
    assert DRAWINGS_BY_NAME["dt_crank_hub"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-hub.SLDDRW")
    marked = set().union(*dt_crank_hub_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_matched_fits_and_distinct_pins_live_on_their_feature_callouts() -> None:
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): no general notes; each matched fit sits on its feature.
    assert not hasattr(dt_crank_hub_spec, "DRAWING_NOTES")
    seat = dt_crank_hub_notes.SEAT_CALLOUT
    # B1 (Main 2026-09-25): turned to suit the MHA-DT-06 bore, with the press
    # interference printed from the notes constant; the mate by name and
    # number (rule 4).
    low, high = dt_crank_hub_notes.SEAT_PRESS_INTERFERENCE
    assert seat.splitlines() == [
        "TURN TO SUIT CRANK ARM",
        f"MHA-DT-06 BORE; {low:.3f}-{high:.3f}",
        "DIAMETRAL INTERFERENCE;",
        "FRONT FACES FLUSH",
    ]
    assert "MATCH-FIT" not in seat
    # The arm bore is made first; the hub seat is turned to suit it, so its
    # nominal prints as a reference.
    assert dt_crank_hub_spec.REFERENCE_DIMENSIONS == {"SeatDia"}
    seam = _flat(dt_crank_hub_notes.SEAM_CALLOUT)
    assert "CRANK ARM MHA-DT-06" in seam and "DOWEL MHA-DT-VN-59" in seam
    assert "LIGHT DRIVE FIT" in seam
    assert "AT ASSY" in seam and "SEAM" in seam
    # Size first, then the process, in the order the work is done.
    assert dt_crank_hub_notes.SEAM_CALLOUT.splitlines()[0].startswith(
        "(<MOD-DIAM>4.0) <HOLE-DEPTH> 4.0, MATCH-DRILL/REAM"
    )
    # Blind in the hub: the dowel's pull thread is how it comes out
    # (machinist review r2b of 383c31baa).
    assert "PULL-THREAD DOWEL MHA-VN-029" in seam
    assert "O'CLOCK" not in seam
    # The taper-pin cross-hole names both mates, by name and number, and the
    # fit on its callout; the front face it is drilled at carries its own note.
    cross_hole = _flat(dt_crank_hub_notes.CROSS_HOLE_CALLOUT)
    assert "CRANK PIN MHA-DT-09" in cross_hole
    assert "CRANKSHAFT MHA-DT-11" in cross_hole
    assert "LIGHT DRIVE FIT" in cross_hole
    assert _flat(dt_crank_hub_notes.FRONT_FACE_NOTE).startswith("FRONT FACE:")
    # Native drill row plus three prose rows: the four-row block limit.
    assert len(dt_crank_hub_notes.CROSS_HOLE_CALLOUT.splitlines()) == 3
    # The bore band governs; the clearance is a reference restatement.
    assert dt_crank_hub_notes.BORE_CALLOUT.splitlines()[1].startswith("(")


def _flat(text: str) -> str:
    return " ".join(text.split())


def _names_the_dome_root(datum: str) -> bool:
    words = datum.split()
    return datum.endswith("DOME ROOT") and "MHA-DT-11" in words and "END" not in words


def _sets_hub_on(text: str, datum: str) -> bool:
    """A printed text places the hub on ``datum``, the one source both read."""
    return _flat(datum) in _flat(text)


def test_hub_front_face_is_set_on_the_dome_root_the_model_places_it_at() -> None:
    """The model seats the hub front face on the crankshaft's dome root (the
    shaft part's origin, CRANK_FACE_Z); the dome tip stands proud of it.  Set
    flush with the shaft END, the hub would sit a dome height forward and open
    the hub/T12 air past the drive pins' proud length.  Both texts that place
    the hub -- its front-face note and the MHA-DT-00 hub step -- print the
    one datum, and the step sets it before the shaft is drilled."""
    import build_dt_drive_train_assembly as assembly
    import draw_dt_drive_train_assembly as package

    datum = dt_crank_hub_notes.FRONT_FACE_DATUM
    assert _names_the_dome_root(datum), datum
    assert assembly.CRANK_HUB_Z0 == assembly.CRANKSHAFT_Z0 == assembly.CRANK_FACE_Z
    hub_step = package.CONE_CRANK_STEPS.split("\n6. ")[1].split("\n7. ")[0]
    front_face = dt_crank_hub_notes.FRONT_FACE_NOTE
    for text in (front_face, hub_step):
        assert _sets_hub_on(text, datum), text
    drill = f"ONLY THEN DRILL {dt_crank_hub_notes.CROSS_HOLE_DRILL}"
    assert _flat(hub_step).index(_flat(datum)) < _flat(hub_step).index(drill)
    # Negative controls: the shaft-END texts both once printed name no dome root.
    for old in (
        "FRONT FACE FLUSH WITH\nCRANKSHAFT MHA-DT-11 END;\nMATCH TAPER-REAM 1:48 FOR",
        "SET THE HUB FRONT FACE FLUSH WITH THE\n   SHAFT END, PUNCH MARKS ALIGNED;",
    ):
        assert not _sets_hub_on(old, datum), old
    assert not _names_the_dome_root("CRANKSHAFT MHA-DT-11 END")


def test_shaft_cross_hole_is_drilled_through_the_hub_pilot_at_assembly() -> None:
    """#1678: drilled separately, the shaft's .X station and the hub's own
    location could set the two holes further apart than the 1:48 ream cleans
    up round a #9 hole.  The shaft is drilled at assembly through the hub's
    pilot instead, and the hub, shaft and MHA-DT-000 texts all say so from one
    drill size and one taper."""
    import dt_crank_pin_spec as pin
    import dt_crank_pin_ring_spec as ring
    import dt_crankshaft_notes
    import draw_dt_drive_train_assembly as package
    from _hole_spec import blind_cut_dia_mm
    from _printed_tolerance import drilled_oversize_mm

    drill = dt_crank_hub_notes.CROSS_HOLE_DRILL
    taper = dt_crank_hub_notes.CROSS_HOLE_TAPER
    assert drill == dt_crankshaft_spec.PIN_HOLE_SPEC.size == "#9"
    assert taper == "1:48"
    assert pin.BIG_END_DIA - pin.SMALL_END_DIA == pytest.approx(pin.PIN_LENGTH / 48.0)
    hub = _flat(dt_crank_hub_notes.CROSS_HOLE_CALLOUT)
    assert f"DRILL {drill} THRU CRANKSHAFT" in hub
    assert hub.index(f"DRILL {drill}") < hub.index(f"TAPER-REAM {taper} BOTH")
    shaft = _flat(dt_crankshaft_notes.CROSS_HOLE_CALLOUT)
    assert shaft.startswith("AT ASSY THRU HUB MHA-DT-031 PILOT")
    assert f"TAPER-REAM {taper} BOTH" in shaft
    # The hub sets the station, so the shaft prints it as a reference.
    assert dt_crankshaft_notes.ASSEMBLY_SET_REFERENCES == {"PinHoleStation"}
    marked = {
        n for names in dt_crankshaft_spec.DRAWING_DIMENSIONS.values() for n in names
    }
    assert dt_crankshaft_notes.ASSEMBLY_SET_REFERENCES <= marked
    hub_step = _flat(package.CONE_CRANK_STEPS.split("\n6. ")[1].split("\n7. ")[0])
    drill_step = f"DRILL {drill} THROUGH THE HUB PILOT AND SHAFT"
    assert drill_step in hub_step
    assert hub_step.index(drill_step) < hub_step.index(
        f"TAPER-REAM {taper} THROUGH BOTH"
    )
    # The #9 at its DRILLED HOLES limit stays inside the reamed taper along
    # the whole hub: thinnest where the pin leaves the far barrel wall.
    drilled_max = (
        blind_cut_dia_mm(dt_crankshaft_spec.PIN_HOLE_SPEC) + drilled_oversize_mm()
    )
    far_wall = ring.PIN_PROUD + geometry.HUB_BARREL_DIA
    taper_at_far_wall = pin.BIG_END_DIA - far_wall / 48.0
    assert drilled_max < taper_at_far_wall
    # The hub's own pilot is smaller than the shaft drill it guides.
    assert blind_cut_dia_mm(dt_crank_hub_spec.SERVICE_PIN_HOLE_SPEC) < drilled_max


def test_seam_callout_attaches_to_the_hub_seam_clear_of_the_bore_callout() -> None:
    x, y = drawing.SEAM_EDGE_PICK
    cx, cy = drawing.SEAM_CENTER
    r = geometry.AXIAL_PIN_DIA / 2.0 * drawing._S
    assert (x - cx) ** 2 + (y - cy) ** 2 == pytest.approx(r**2)
    assert cy < drawing.END_CENTER[1] and y > cy  # six o'clock, hub-side arc
    # The seam block sits below the end view, right of the side view's
    # outboard end; the bore block stands right of the end view.
    assert drawing.SEAM_CALLOUT_XY[0] > drawing.OUTBOARD_X
    end_bottom = drawing.END_CENTER[1] - geometry.HUB_BARREL_DIA / 2.0 * drawing._S
    assert drawing.SEAM_CALLOUT_XY[1] < end_bottom
    # Its near (left) end sits just right of the seam, so the leader drops
    # short and clear of the bore leader instead of crossing its own text.
    assert 0.0 < drawing.SEAM_CALLOUT_XY[0] - cx < 0.010
    bore_block_bottom = drawing.END_KEEP["BoreDia"][1] - 3 * 0.006
    assert drawing.SEAM_CALLOUT_XY[1] < bore_block_bottom
    # Its widest row (tokens print one glyph each) ends inside the border.
    widest = max(
        len(row.replace("<MOD-DIAM>", "D").replace("<HOLE-DEPTH>", "D"))
        for row in dt_crank_hub_notes.SEAM_CALLOUT.splitlines()
    )
    assert drawing.SEAM_CALLOUT_XY[0] + widest * 0.00267 < 0.412
    assert drawing.END_KEEP["BoreDia"][0] > drawing.END_CENTER[0]


def test_side_view_lies_as_in_the_lathe_with_one_outboard_baseline() -> None:
    # Axis horizontal, faced outboard end on the right, seam (+Z) at the bottom.
    assert drawing.OUTBOARD_X > drawing.SHOULDER_X > drawing.INBOARD_X
    assert drawing._sheet_y(geometry.AXIAL_PIN_RADIUS_FROM_AXIS) < drawing.SIDE_CENTER[1]
    assert drawing.END_CENTER[0] > drawing.OUTBOARD_X  # third-angle right view
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    # Seat from the faced end, the pin station from the shoulder (drawing-guidelines.md rule 11 (turned parts read like the lathe)
    # ), the relief from the rear face; the toleranced overall, front face to
    # rear face, on the lowest row.  No chained barrel length.
    # Measured on the r1 render (114fa71c1): a kept dimension's line runs
    # 2.8 mm under its keep point and its text stands 1.0-4.5 mm above the
    # line; callout rows stack 5.56 mm apart under the value, the line under
    # the last; ~2.67 mm per character.
    char_w, pitch = 0.00267, 0.00556
    seat_row = drawing.SIDE_KEEP["SeatLength"][1]
    station_row = drawing.SIDE_KEEP["ServicePinFromShoulder"][1]
    relief_row = drawing.SIDE_KEEP["ReliefLength"][1]
    overall_row = drawing.SIDE_KEEP["HubLength"][1]
    # The seat and station both print their arrows outside their spans, so
    # the seat stands a row above: its arrows clear the station's text.
    assert (seat_row - 0.0028) - (station_row + 0.0017) >= 0.002
    # The overall's block (value and two stack rows) stands 2 mm under the
    # station's line, and its rows are narrower than its span by 2 mm a side,
    # so its extension lines strike no text.
    assert (station_row - 0.0028) - (overall_row + 0.0073) >= 0.002
    rows = [
        f"{geometry.HUB_LENGTH:.2f} ±0.1",
        *dt_crank_hub_notes.HUB_LENGTH_CALLOUT.splitlines(),
    ]
    span = drawing.OUTBOARD_X - drawing.INBOARD_X
    assert max(len(row) for row in rows) * char_w < span - 0.004
    # The relief's three-row block stands 2 mm under the barrel diameter's
    # lower extension line, its line (under its last row) above the overall's.
    relief_top = relief_row + 0.0073
    assert relief_top < drawing.BARREL_BOTTOM - 0.002
    relief_lines = 1 + len(dt_crank_hub_notes.RELIEF_LENGTH_CALLOUT.splitlines())
    relief_line = relief_row + 0.0028 - (relief_lines - 1) * pitch
    assert relief_line - (overall_row + 0.0073) >= 0.002
    assert seat_row < drawing.BARREL_BOTTOM
    assert "BarrelLength" not in drawing.SIDE_KEEP
    printed = {
        name for names in dt_crank_hub_spec.DRAWING_DIMENSIONS.values() for name in names
    }
    assert "BarrelLength" not in printed and "HubLength" in printed
    assert drawing.SHOULDER_X > drawing.SERVICE_PIN_CENTER[0] > drawing.RELIEF_X
    # The relief's text and mate callout print outside its span, left of the
    # rear face (~2.5 mm per character, centred on the text).
    widest = max(
        len(line) for line in dt_crank_hub_notes.RELIEF_LENGTH_CALLOUT.splitlines()
    )
    assert drawing.SIDE_KEEP["ReliefLength"][0] + widest * 0.00125 < drawing.INBOARD_X


def test_front_face_note_lands_on_the_front_face_clear_of_its_neighbours() -> None:
    """Machinist review r1 of 114fa71c1: the sheet named a FRONT FACE and a
    REAR FACE without showing which end is which.  The note's leader lands on
    the front face where the end view looks at it."""
    char_w = 0.00267
    cx, cy = drawing.END_CENTER
    x, y = drawing.FRONT_FACE_PICK
    r = math.hypot(x - cx, y - cy)
    assert geometry.HUB_BORE_DIA / 2.0 * drawing._S < r
    assert r < geometry.HUB_SEAT_DIA / 2.0 * drawing._S
    sx, sy = drawing.SEAM_CENTER
    assert math.hypot(x - sx, y - sy) > geometry.AXIAL_PIN_DIA * drawing._S
    note = dt_crank_hub_notes.FRONT_FACE_NOTE.splitlines()
    left, top = drawing.FRONT_FACE_NOTE_XY
    right = left + max(len(row) for row in note) * char_w
    # Right of the overall's front extension line and under the seat
    # length's line (its arrows print outside, past the front face).
    assert left - drawing.OUTBOARD_X >= 0.004
    assert top < drawing.SIDE_KEEP["SeatLength"][1] - 0.0028 - 0.002
    # Under the seat diameter's lower extension line and the end view, left
    # of the seam callout and its leader.
    assert top < drawing._sheet_y(geometry.HUB_SEAT_DIA / 2.0) - 0.002
    assert top < cy - geometry.HUB_BARREL_DIA / 2.0 * drawing._S - 0.002
    assert right < min(drawing.SEAM_CALLOUT_XY[0], drawing.SEAM_EDGE_PICK[0]) - 0.004


@pytest.mark.parametrize(
    "feature, name, radius_name, band_name, expected_max",
    [
        ("SeatRootFillet", "SeatRootRadius", "SEAT_ROOT_FILLET_R", "SEAT_ROOT_FILLET_BAND", 0.1),
        (
            "ReliefRootFillet",
            "ReliefRootRadius",
            "RELIEF_ROOT_FILLET_R",
            "RELIEF_ROOT_FILLET_BAND",
            0.3,
        ),
    ],
)
def test_inside_corners_carry_their_own_approved_native_max_limits(
    feature: str, name: str, radius_name: str, band_name: str, expected_max: float
) -> None:
    radius = getattr(geometry, radius_name)
    assert radius == expected_max
    assert getattr(dt_crank_hub_spec, band_name) == (0.0, -radius)
    assert dt_crank_hub_spec.ROOT_FILLET_TOL_TYPE == 6  # swTolMAX
    assert dt_crank_hub_spec.DRAWING_DIMENSIONS[feature] == {name}
    assert dt_crank_hub_spec.DRAWING_PRECISION[feature] == {name: 1}
    assert name in drawing.SIDE_KEEP and name not in drawing.END_KEEP


def test_arm_bore_chamfer_clears_the_seat_root_and_preserves_shoulder_land() -> None:
    # The seat's clearance controls the matched arm mouth; the larger relief
    # radius has no mating bore mouth and must not enlarge this chamfer.
    assert geometry.SEAT_ROOT_FILLET_R < geometry.RELIEF_ROOT_FILLET_R
    chamfer_min, chamfer_max = geometry.ARM_BORE_REAR_CHAMFER_LEG
    assert chamfer_min >= geometry.SEAT_ROOT_FILLET_R
    assert chamfer_max == geometry.EDGE_BREAK_MAX_MM
    step = (geometry.HUB_BARREL_DIA_MIN - geometry.HUB_SEAT_DIA_MAX_MATCHED) / 2.0
    land = step - chamfer_max - geometry.EDGE_BREAK_MAX_MM
    assert land >= geometry.SHOULDER_LAND_WORST_MIN - 1e-9
    assert geometry.ARM_BORE_REAR_CHAMFER_LEG == (0.1, geometry.EDGE_BREAK_MAX_MM)
    # Charging the relief's larger radius to the arm would eat the land.
    assert (
        step - geometry.RELIEF_ROOT_FILLET_R - geometry.EDGE_BREAK_MAX_MM
        < geometry.SHOULDER_LAND_WORST_MIN
    )


def test_seat_root_radius_text_clears_the_barrel_corner_and_the_seat_diameter() -> None:
    char_w = 0.00267
    text = f"R{geometry.SEAT_ROOT_FILLET_R:.1f} MAX"
    cx, cy = drawing.SEAT_ROOT_RADIUS_TEXT_XY
    left = cx - len(text) * char_w / 2.0
    right = cx + len(text) * char_w / 2.0
    corner_x, corner_y = drawing.SEAT_ROOT_CORNER
    assert corner_y == pytest.approx(drawing._sheet_y(-geometry.HUB_SEAT_DIA / 2.0))
    # The leader from the text's left end to the arc rises no steeper than
    # the cap, so it passes the barrel's top front corner on its right.
    slope = (cy - corner_y) / (left - corner_x)
    assert 0.0 < slope <= drawing.SEAT_ROOT_LEADER_MAX_SLOPE
    barrel_corner_rise = drawing.BARREL_TOP - corner_y
    assert barrel_corner_rise / slope >= 0.0015
    # The text clears the barrel top and stands under the cross-hole block,
    # right of the cross-hole leader and left of the seat diameter's line.
    assert cy - 0.00175 - drawing.BARREL_TOP >= 0.005
    assert left > drawing.SERVICE_PIN_TOP_RIM[0] + 0.010
    assert drawing.SIDE_KEEP["SeatDia"][0] - right >= 0.004


def test_relief_root_radius_has_its_own_clear_native_annotation_lane() -> None:
    char_w = 0.00267
    text = f"R{geometry.RELIEF_ROOT_FILLET_R:.1f} MAX"
    cx, cy = drawing.RELIEF_ROOT_RADIUS_TEXT_XY
    left = cx - len(text) * char_w / 2.0
    right = cx + len(text) * char_w / 2.0
    corner_x, corner_y = drawing.RELIEF_ROOT_CORNER
    assert corner_x == drawing.RELIEF_X
    assert corner_y == drawing._sheet_y(-geometry.RELIEF_DIA / 2.0)
    # Text above both diameter extension lines, left of the relief's end face;
    # its leader enters from the open left side, not through the barrel.
    assert cy - 0.00175 >= drawing.BARREL_TOP + 0.002
    assert right <= drawing.INBOARD_X - 0.001
    slope = (cy - corner_y) / (corner_x - right)
    assert slope > 0.0
    assert (drawing.BARREL_TOP - corner_y) / slope >= 0.0015
    # Native audit 20261019T025313732Z-ad1b9b1828584f61b9685592171681c4:
    # the cross-hole block's underline is Y210.8608 and its leader stays
    # right of X187.5809 above the barrel.  Leave 2 mm to both.
    assert cy + 0.00175 <= 0.2108608 - 0.002
    assert max(right, corner_x) <= 0.1875809 - 0.002
    # Neither diameter's vertical dimension line can meet this radius leader.
    assert right > max(
        drawing.SIDE_KEEP["BarrelDia"][0], drawing.SIDE_KEEP["ReliefDia"][0]
    ) + 0.002
    assert left > drawing.SIDE_KEEP["BarrelDia"][0] + 0.002


class _RootTolerance:
    interface = "IDimensionTolerance"

    def __init__(self) -> None:
        self.Type = 0
        self.lower = 0.0
        self.upper = 0.0

    def SetValues(self, lower: float, upper: float) -> bool:
        self.lower, self.upper = lower, upper
        return True

    def GetMinValue(self) -> float:
        return self.lower

    def GetMaxValue(self) -> float:
        return self.upper


def _bind_root_native(value, interface: str):
    assert value.interface == interface
    return value


@pytest.mark.parametrize(
    "feature, name, radius, band",
    [
        ("SeatRootFillet", "SeatRootRadius", 0.1, dt_crank_hub_spec.SEAT_ROOT_FILLET_BAND),
        ("ReliefRootFillet", "ReliefRootRadius", 0.3, dt_crank_hub_spec.RELIEF_ROOT_FILLET_BAND),
    ],
)
def test_each_native_root_max_is_authored_and_read_back_independently(
    monkeypatch, feature: str, name: str, radius: float, band: tuple[float, float]
) -> None:
    import build_dt_crank_hub as part

    tolerance = _RootTolerance()
    dimension = SimpleNamespace(SystemValue=radius / 1000.0, Tolerance=tolerance)

    def named_dimension(_adapter, actual_feature, actual_name):
        assert (actual_feature, actual_name) == (feature, name)
        return None, dimension

    monkeypatch.setattr(part, "_named_dimension", named_dimension)
    monkeypatch.setattr(part, "_early_bound", _bind_root_native)
    part._root_fillet_max_limit(None, feature, name, radius, band)
    assert tolerance.Type == 6
    assert (tolerance.lower, tolerance.upper) == pytest.approx((-radius / 1000.0, 0.0))
    dimension.SystemValue += 0.0001
    with pytest.raises(RuntimeError, match="is not the band's max"):
        part._root_fillet_max_limit(None, feature, name, radius, band)
    dimension.SystemValue = radius / 1000.0
    monkeypatch.setattr(tolerance, "GetMaxValue", lambda: 0.0001)
    with pytest.raises(RuntimeError, match="MAX-limit tolerance readback changed"):
        part._root_fillet_max_limit(None, feature, name, radius, band)


def test_root_fillet_volume_charges_each_roots_actual_radius() -> None:
    import build_dt_crank_hub as part

    # Integrate the corner spandrel's area and first moment about the smaller
    # step, independently of the builder's centroid expression.
    expected = 2.0 * math.pi * sum(
        step * radius**2 * (1.0 - math.pi / 4.0)
        + radius**3 * (5.0 / 6.0 - math.pi / 4.0)
        for step, radius in (
            (geometry.HUB_SEAT_DIA / 2.0, geometry.SEAT_ROOT_FILLET_R),
            (geometry.RELIEF_DIA / 2.0, geometry.RELIEF_ROOT_FILLET_R),
        )
    )
    assert part.V_ROOT_FILLETS == pytest.approx(expected)


@pytest.fixture
def native_root_annotations(monkeypatch):
    annotations = []
    for name, radius in (("SeatRootRadius", 0.1), ("ReliefRootRadius", 0.3)):
        tolerance = _RootTolerance()
        tolerance.Type = 6
        tolerance.SetValues(-radius / 1000.0, 0.0)
        dimension = SimpleNamespace(
            interface="IDimension", SystemValue=radius / 1000.0, Tolerance=tolerance
        )
        text_parts = {1: "R", 2: ""}
        display = SimpleNamespace(
            interface="IDisplayDimension",
            Diametric=False,
            ArcExtensionLineOrOppositeSide=True,
            GetDimension2=lambda _index, dimension=dimension: dimension,
            GetText=text_parts.__getitem__,
            text_parts=text_parts,
        )
        annotations.append(
            SimpleNamespace(
                interface="IAnnotation",
                name=name,
                GetSpecificAnnotation=lambda display=display: display,
            )
        )
    monkeypatch.setattr(drawing, "_early_bound", _bind_root_native)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: ann.name)
    return annotations


def test_both_native_root_imports_keep_radius_prefix_max_values_and_arc_leaders(
    native_root_annotations,
) -> None:
    dimensions = [
        ann.GetSpecificAnnotation().GetDimension2(0) for ann in native_root_annotations
    ]
    # Repeated dressing must not accumulate an R or combine the unequal roots
    # under one quantity prefix. Both remain the imported model dimensions.
    drawing._dress_root_radii(None, native_root_annotations)
    drawing._dress_root_radii(None, native_root_annotations)
    for annotation, dimension, radius in zip(
        native_root_annotations, dimensions, (0.1, 0.3), strict=True
    ):
        display = annotation.GetSpecificAnnotation()
        assert display.GetDimension2(0) is dimension
        assert display.GetText(1) == "R"
        assert display.GetText(2) == ""
        assert dimension.SystemValue == pytest.approx(radius / 1000.0)
        assert dimension.Tolerance.Type == 6
        assert dimension.Tolerance.GetMinValue() == pytest.approx(-radius / 1000.0)
        assert dimension.Tolerance.GetMaxValue() == 0.0
        assert not display.Diametric
        assert not display.ArcExtensionLineOrOppositeSide


@pytest.mark.parametrize("name", ["SeatRootRadius", "ReliefRootRadius"])
@pytest.mark.parametrize(
    "fault, message",
    [
        ("missing", "must import one"),
        ("duplicate", "must import one"),
        ("nominal", "does not measure its root fillet"),
        ("type", "lost its native MAX type"),
        ("limit", "MAX-limit tolerance readback changed"),
        ("upper", "MAX-limit tolerance readback changed"),
        ("diametric", "is not radial"),
    ],
)
def test_neither_native_root_import_can_be_missing_or_misrepresented(
    native_root_annotations, name: str, fault: str, message: str
) -> None:
    annotation = next(ann for ann in native_root_annotations if ann.name == name)
    display = annotation.GetSpecificAnnotation()
    dimension = display.GetDimension2(0)
    if fault == "missing":
        native_root_annotations.remove(annotation)
    elif fault == "duplicate":
        native_root_annotations.append(annotation)
    elif fault == "nominal":
        dimension.SystemValue += 0.0001
    elif fault == "type":
        dimension.Tolerance.Type = 4
    elif fault == "limit":
        dimension.Tolerance.lower -= 0.0001
    elif fault == "upper":
        dimension.Tolerance.upper += 0.0001
    else:
        display.Diametric = True
    with pytest.raises(RuntimeError, match=message):
        drawing._dress_root_radii(None, native_root_annotations)


@pytest.mark.parametrize("name", ["SeatRootRadius", "ReliefRootRadius"])
@pytest.mark.parametrize(
    "prefix", ["", "QTY ", "2X ", "2X R", "RR", "<MOD-DIAM>", "R0.1 MAX"]
)
def test_each_native_root_rejects_counts_missing_r_or_replacement_text(
    native_root_annotations, name: str, prefix: str
) -> None:
    annotation = next(ann for ann in native_root_annotations if ann.name == name)
    annotation.GetSpecificAnnotation().text_parts[1] = prefix
    with pytest.raises(RuntimeError, match=f"{name} must retain a single R prefix"):
        drawing._dress_root_radii(None, native_root_annotations)


def test_callouts_stand_clear_of_views_and_each_other() -> None:
    # ~2.5 mm per character at the sheet's text height; callout lines are
    # centred on their value, so the widest line sets each block's extent.
    char_w = 0.0025

    def half(text: str) -> float:
        return max(len(line) for line in text.splitlines()) * char_w / 2.0

    seat_x, seat_y = drawing.SIDE_KEEP["SeatDia"]
    seat_half = half(dt_crank_hub_notes.SEAT_CALLOUT)
    seat_block = (seat_x - seat_half, seat_x + seat_half)
    hole_x, hole_y = drawing.HOLE_CALLOUT_XY
    hole_text = f"{dt_crank_hub_notes.CROSS_HOLE_CALLOUT}\n#14 DRILL 0 4.62 THRU ALL"
    hole_block = (hole_x - half(hole_text), hole_x + half(hole_text))
    # The cross-hole leader rises from the hole's top rim to the block's
    # right end; the seat callout must start right of that leader.
    assert hole_block[1] < drawing.SERVICE_PIN_TOP_RIM[0] < seat_block[0]
    # The value line plus every callout line stays above the barrel.
    seat_lines = 1 + len(dt_crank_hub_notes.SEAT_CALLOUT.splitlines())
    assert seat_y - seat_lines * 0.006 > drawing.BARREL_TOP
    assert hole_y - 5 * 0.006 > drawing.BARREL_TOP
    end_left = drawing.END_CENTER[0] - geometry.HUB_BARREL_DIA / 2.0 * drawing._S
    end_right = drawing.END_CENTER[0] + geometry.HUB_BARREL_DIA / 2.0 * drawing._S
    bore_x, bore_y = drawing.END_KEEP["BoreDia"]
    # Right of the end view, so its leader enters the bore from the right,
    # clear of the six-o'clock seam and its callout.
    assert bore_x - half(dt_crank_hub_notes.BORE_CALLOUT) > end_right
    assert bore_y < drawing.END_CENTER[1]
    assert seat_block[1] < drawing.ISO_NOTE_XY[0] and end_left > drawing.OUTBOARD_X
    # Both turned diameters stand left of the inboard end, the relief's nearer,
    # their values side by side on the axis without touching.
    relief_x = drawing.SIDE_KEEP["ReliefDia"][0]
    barrel_x = drawing.SIDE_KEEP["BarrelDia"][0]
    assert barrel_x < relief_x < drawing.INBOARD_X
    relief_half = len("Ø16.50") * char_w / 2.0
    barrel_label = f"Ø{geometry.HUB_BARREL_DIA:.2f}"
    assert barrel_x + len(barrel_label) * char_w / 2.0 < relief_x - relief_half
    assert relief_x + relief_half < drawing.INBOARD_X


def test_station_reference_sketch_lies_in_the_side_view_plane() -> None:
    # A standalone reference sketch imports its dimension natively only on the
    # plane of the view that prints it; on Front, the *Right side view got the
    # sketch but no ServicePinStation (run 20260922T020620997Z-4a7ef16e).
    source = Path(drawing.__file__).with_name("build_dt_crank_hub.py").read_text(
        encoding="utf-8"
    )
    head = source[: source.index('name_last_feature(adapter, "ServicePinStationReference")')]
    last_sketch = head[head.rindex("create_sketch(") :].split(")", 1)[0]
    assert last_sketch == 'create_sketch("Right"'
    assert "ServicePinFromShoulder" in drawing.SIDE_KEEP
    assert '"*Right", *SIDE_CENTER' in Path(drawing.__file__).read_text(encoding="utf-8")


def test_centerline_pick_hits_barrel_face_not_the_cross_hole() -> None:
    x, y = drawing.BARREL_FACE_PICK
    assert drawing.RELIEF_X < x < drawing.SHOULDER_X
    assert drawing.BARREL_BOTTOM < y < drawing.BARREL_TOP
    hole_x, hole_y = drawing.SERVICE_PIN_CENTER
    hole_r = drawing.SERVICE_PIN_DIA / 2.0 * drawing._S
    assert (x - hole_x) ** 2 + (y - hole_y) ** 2 > hole_r**2


def test_callout_prose_stays_out_of_every_part_recipe() -> None:
    # Codex #361: callout wording lives in drawing-only *_notes modules, so a
    # prose edit re-keys drawings, never a crank part or an assembly.
    from _buildgraph import module_deps_of

    scripts = Path(drawing.__file__).parent
    notes = {"dt_crank_hub_notes", "dt_crank_arm_notes", "dt_crankshaft_notes"}

    def reached(stem: str) -> set[str]:
        return {Path(str(dep)).stem for dep in module_deps_of(scripts / f"{stem}.py")}

    for stem in (
        "build_dt_crank_hub",
        "build_dt_crank_arm",
        "build_dt_vn_crank_hub_pin",
        "build_dt_crankshaft",
        "build_dt_crank_handle_pivot_screw",
        "build_dt_drive_train_assembly",
        "_interference_contracts",
    ):
        assert not reached(stem) & notes, stem
    assert "dt_crank_hub_notes" in reached("draw_dt_crank_hub")
    assert "dt_crank_arm_notes" in reached("draw_dt_crank_arm")
    assert "dt_crankshaft_notes" in reached("draw_dt_crankshaft")


# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): at most four short lines. Codex #892
# (PRRT_kwDOPHDy386mMQpe): the generated seat callout printed five.
CALLOUT_LINE_CAP = 4


@pytest.mark.parametrize(
    "name, text",
    [
        ("SEAT_CALLOUT", dt_crank_hub_notes.SEAT_CALLOUT),
        ("SEAM_CALLOUT", dt_crank_hub_notes.SEAM_CALLOUT),
        ("BORE_CALLOUT", dt_crank_hub_notes.BORE_CALLOUT),
        ("CROSS_HOLE_CALLOUT", dt_crank_hub_notes.CROSS_HOLE_CALLOUT),
        ("seat_bore_callout", dt_crank_hub_notes.seat_bore_callout("MHA-DT-31")),
    ],
)
def test_every_generated_callout_stays_within_four_lines(name: str, text: str) -> None:
    assert len(text.splitlines()) <= CALLOUT_LINE_CAP, (name, text.splitlines())


def test_u29_walls_hold_at_the_seat_bores_printed_limits() -> None:
    # Main 2026-09-25: the arm is 1-in CF flat, held to 0.004 in on width
    # (OnlineMetals, Speedy Metals), not 0.003; and the cheek must come from
    # the seat bore's REAL limits. MHA-DT-06 bores the seat first at .X; the
    # MHA-DT-31 seat is turned to suit it for a press, so it is never smaller.
    mm = 25.4
    assert geometry.ARM_WIDTH_STOCK_MINUS == pytest.approx(0.004 * mm)
    bore_max = geometry.HUB_SEAT_DIA + geometry.GENERAL_1PL_TOL_MM
    bore_min = geometry.HUB_SEAT_DIA - geometry.GENERAL_1PL_TOL_MM
    cheek = geometry.wall_after_edge_break(
        geometry.ARM_WIDTH - geometry.ARM_WIDTH_STOCK_MINUS, bore_max
    )
    web = geometry.wall_after_edge_break(
        bore_min - geometry.AXIAL_PIN_DIA_STOCK_MAX, geometry.HUB_BORE_DIA_MAX
    )
    assert cheek >= geometry.WALL_TARGET_MM == 2.0
    assert web >= geometry.WALL_TARGET_MM
    assert geometry.ARM_CHEEK_WORST_MM == pytest.approx(cheek)
    assert geometry.SEAM_WEB_WORST_MM == pytest.approx(web)


def test_service_pin_station_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880: a reference sketch owns printed dimensions but no geometry, so the
    # part saves it hidden (no assembly instance renders it) and the drawing
    # shows it per view through _drawing_hidden_sketches to import them.
    build = Path(drawing.__file__).with_name("build_dt_crank_hub.py").read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "ServicePinStationReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source.replace("\r\n", "\n")
    assert "ServicePinStationReference" in dt_crank_hub_spec.DRAWING_DIMENSIONS
