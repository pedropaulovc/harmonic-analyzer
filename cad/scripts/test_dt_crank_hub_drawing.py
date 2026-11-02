"""Offline release contracts for separate through hub MHA-DT-31."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import _sprocket_seat_geometry as seat_geometry
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
    # Named deviation: the .76 seat under the photograph keeps the U29 cheek
    # and the seam web over the rule-17 wall.
    assert geometry.HUB_SEAT_DIA == pytest.approx(0.76 * 25.4)
    assert geometry.HUB_SEAT_DIA < geometry.PHOTO_HUB_SEAT_DIA
    # Stock sizes: the pin is the 5/32 dowel just under 1.3x, the arm is 1-in bar.
    assert geometry.AXIAL_PIN_DIA == pytest.approx(5 / 32 * 25.4)
    assert geometry.AXIAL_PIN_DIA < 0.59 * unit * scale
    assert geometry.ARM_WIDTH == pytest.approx(25.4)
    # Named ratio deviation from the photograph (U29).
    assert geometry.ARM_TO_HUB_RATIO == pytest.approx(1.316, abs=1e-3)
    assert geometry.PHOTO_ARM_TO_HUB_RATIO == pytest.approx(1.208, abs=1e-3)


def test_u27_walls_hold_the_inch_wall_target_at_the_printed_bands() -> None:
    assert geometry.WALL_TARGET_MM == pytest.approx(0.080 * 25.4)
    assert geometry.SEAM_WEB_WORST_MM == pytest.approx(2.247, abs=1e-3)
    assert geometry.ARM_CHEEK_WORST_MM == pytest.approx(2.362, abs=1e-3)
    assert min(geometry.SEAM_WEB_WORST_MM, geometry.ARM_CHEEK_WORST_MM) >= (
        geometry.WALL_TARGET_MM
    )


def test_arm_shoulder_keeps_its_land_over_the_largest_matched_seat() -> None:
    """Codex P2 on 16146c26f: the arm is pressed to the barrel's front face,
    and the seat is turned to whatever MHA-DT-06 bore it meets.  At the printed
    limits the largest bore (.XX) plus the tightest press stands inside the
    smallest barrel the sheet allows; after the arm bore's and the barrel
    corner's edge breaks a land at least one edge break wide must be left."""
    two_place = 0.01 * 25.4
    edge_break = geometry.EDGE_BREAK_MAX_MM
    assert dt_crank_hub_spec.DRAWING_PRECISION_BY_NAME["SeatDia"] == 2
    assert dt_crank_hub_spec.DRAWING_PRECISION_BY_NAME["BarrelDia"] == 2
    seat_max = geometry.HUB_SEAT_DIA + two_place + 0.0012 * 25.4
    assert geometry.HUB_SEAT_DIA_MAX_MATCHED == pytest.approx(seat_max)
    barrel_min = geometry.HUB_BARREL_DIA - two_place
    land = (barrel_min - seat_max) / 2.0 - 2.0 * edge_break
    assert land >= edge_break
    assert geometry.HUB_SHOULDER_LAND_WORST_MM == pytest.approx(land)
    assert geometry.SHOULDER_LAND_WORST_MIN == edge_break
    # A barrel at the seat's own size leaves no land.
    with pytest.raises(AssertionError, match="shoulder land"):
        geometry.shoulder_land(geometry.HUB_SEAT_DIA + two_place, seat_max)


def test_mha024_ream_ligaments_meet_rule_12_at_the_printed_bands() -> None:
    # CONTRACT-crank MHA-DT-31 in decimal inch (#290): the 5/16 seat, a .990
    # overall, the ream station .53 from the faced outboard end and the .16
    # chain-plate relief at the rear (lengthened for the floated wheel, PR1
    # Codex review 2).  R9-38 sized the barrel at .XX for the arm shoulder's
    # land.
    assert geometry.HUB_BARREL_DIA == pytest.approx(0.88 * 25.4)
    assert geometry.HUB_LENGTH == pytest.approx(0.99 * 25.4)
    assert geometry.SERVICE_PIN_STATION == pytest.approx(0.53 * 25.4)
    assert geometry.HUB_BARREL_LENGTH == pytest.approx(
        geometry.HUB_LENGTH - geometry.HUB_SEAT_LENGTH - geometry.RELIEF_LENGTH
    )
    assert dt_crank_hub_spec.DRAWING_PRECISION["ServicePinStationReference"] == {
        "ServicePinStation": 2
    }
    # Worst case at the printed bands (drawing-guidelines.md rule 17 (walls
    # and webs)): the shoulder side governs.  The ream is placed from the
    # front face by the .XX station; the arm shoulder by the arm itself (the
    # seat length is a fit-up reference), at most the thickest 5/16 stock.
    # Behind the ream the relief shoulder is placed from the front face by the
    # .XX overall less the .XX relief.
    assert geometry.SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM == pytest.approx(
        2.200, abs=1e-3
    )
    assert geometry.SERVICE_PIN_REAR_LIGAMENT_WORST_MM == pytest.approx(3.889, abs=1e-3)
    assert geometry.SERVICE_PIN_BARREL_WALL_WORST_MM == pytest.approx(8.080, abs=1e-3)
    assert min(
        geometry.SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM,
        geometry.SERVICE_PIN_REAR_LIGAMENT_WORST_MM,
        geometry.SERVICE_PIN_BARREL_WALL_WORST_MM,
    ) >= geometry.WALL_TARGET_MM


def test_rear_relief_clears_the_t12_chain_plates_and_keeps_its_wall() -> None:
    # Bought ANSI #25 chain at print-worst: Ø.65 x .16, the barrel shoulder
    # where the seat and barrel end.
    assert geometry.RELIEF_DIA == pytest.approx(0.65 * 25.4)
    assert geometry.RELIEF_LENGTH == pytest.approx(0.16 * 25.4)
    assert geometry.RELIEF_STATION == pytest.approx(
        geometry.HUB_SEAT_LENGTH + geometry.HUB_BARREL_LENGTH
    )
    # Title-block .XX on the clearance diameter and on the relief length (its
    # short side still holds the chain's floated air); the overall that
    # places the rear face it is printed from carries +.004 on its long side
    # (owner ruling 2026-10-31).
    assert geometry.RELIEF_DIA_MAX == pytest.approx(geometry.RELIEF_DIA + 0.254)
    assert geometry.RELIEF_LENGTH_TOL == geometry.GENERAL_2PL_TOL_MM
    assert geometry.HUB_LENGTH_BAND == (0.1016, -geometry.GENERAL_2PL_TOL_MM)
    assert dt_crank_hub_spec.DRAWING_PRECISION["HubProfile"]["ReliefLength"] == 2
    assert dt_crank_hub_spec.DRAWING_PRECISION["HubProfile"]["HubLength"] == 3
    assert dt_crank_hub_spec.DRAWING_PRECISION["HubProfile"]["ReliefDia"] == 2
    # drawing-guidelines.md rule 17 (walls and webs) wall over the bore, edges broken.
    assert geometry.RELIEF_WALL_WORST_MM == pytest.approx(2.838, abs=1e-3)
    assert geometry.RELIEF_WALL_WORST_MM >= geometry.WALL_TARGET_MM
    # The MHA-DT-09 ream stays on the full barrel.
    assert (
        geometry.SERVICE_PIN_STATION + geometry.SERVICE_PIN_REAM_RADIUS_MAX
        < geometry.RELIEF_STATION
    )


def test_hub_overall_band_is_one_sided_to_what_the_rear_face_stacks_hold() -> None:
    # Machinist reviews of 19e33c6c2 and main 31cea0b73: only the long side
    # is functional.  At +.004 the drive-pin tips keep air to the rear face;
    # at the title block's -.010 the wheel floated onto it stays on its pins.
    # The title block's +.010 would all but close the tip air.
    kwargs = dict(
        seat_face=dt_crankshaft_spec.SEAT_COLLAR,
        seat_face_band=dt_crankshaft_spec.SEAT_COLLAR_BAND,
        hub_rear=geometry.HUB_LENGTH,
        plate_min=seat_geometry.PLATE
        + min(seat_geometry.PLATE_BAND),
    )
    air, engagement = dt_crankshaft_spec.drive_pin_front_clearances(
        dt_crankshaft_spec.DRIVE_PIN_PROUD_RANGE,
        hub_rear_band=geometry.HUB_LENGTH_BAND,
        **kwargs,
    )
    assert air == pytest.approx(0.1984, abs=1e-9)
    assert engagement == pytest.approx(0.838, abs=1e-9)
    title_block_air, _ = dt_crankshaft_spec.drive_pin_front_clearances(
        dt_crankshaft_spec.DRIVE_PIN_PROUD_RANGE,
        hub_rear_band=(geometry.GENERAL_2PL_TOL_MM, -geometry.GENERAL_2PL_TOL_MM),
        **kwargs,
    )
    assert title_block_air < 0.05


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
    # it cut into the shoulder while the seated check passed.  (The seat is
    # set 1.0 aft here to leave the floated pose, which ignores it, as the
    # only fault.)
    with pytest.raises(AssertionError, match="floated_worst"):
        geometry.chain_shoulder_axial_air(
            relief_length=3.6,
            seat_face=dt_crankshaft_spec.SEAT_COLLAR + 1.0,
            seat_face_band=dt_crankshaft_spec.SEAT_COLLAR_BAND,
        )
    airs = _stack_a(geometry.RELIEF_LENGTH)
    assert airs["floated_worst"] == pytest.approx(0.2235, abs=1e-9)
    assert airs["floated"] == pytest.approx(0.5775, abs=1e-9)
    assert airs["seated_worst"] == pytest.approx(0.4759, abs=1e-9)
    assert airs["seated"] == pytest.approx(1.3315, abs=1e-9)
    # The floated pose governs, and the relief is the shortest .XX length
    # that holds the floor there.
    assert airs["floated_worst"] < airs["seated_worst"]
    with pytest.raises(AssertionError, match="floated_worst"):
        _stack_a(geometry.RELIEF_LENGTH - 0.254)


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
    # The cut pin seats flush before it can bottom in the match-reamed seam.
    assert geometry.SEAM_DEPTH > geometry.AXIAL_PIN_LENGTH


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
    # B1 (Main 2026-09-25): turned to suit the MHA-DT-06 bore, with the F10
    # press interference printed in inch; the bore is named as the arm's, and
    # the seat end's acceptance is flush with the arm's front.
    assert len(seat.splitlines()) == 4
    assert "BORE OF CRANK ARM MHA-DT-06" in _flat(seat)
    assert ".0004-.0012 DIAMETRAL INTERFERENCE" in _flat(seat)
    assert seat.splitlines()[-1] == "END FLUSH WITH CRANK ARM FRONT"
    assert "MATCH-FIT" not in seat
    # The arm bore is made first; the hub seat is turned to suit it, so its
    # nominal prints as a reference.
    assert dt_crank_hub_spec.REFERENCE_DIMENSIONS == {"SeatDia"}
    seam = dt_crank_hub_notes.SEAM_CALLOUT
    assert "MHA-DT-06" in seam and "SEAM PIN MHA-DT-VN-59" in _flat(seam)
    assert "LIGHT DRIVE FIT" in seam and len(seam.splitlines()) == 4
    assert "AT ASSEMBLY" in seam and "SEAM" in seam
    # Size first, then the process, in the order the work is done.
    assert seam.splitlines()[0].startswith("(<MOD-DIAM>.156) <HOLE-DEPTH> .17")
    assert "O'CLOCK" not in seam
    # The blind pin makes hub and arm a permanent pair, taken apart at the
    # taper pin (owner rulings 2026-11-01).
    assert "PERMANENT PAIR" in _flat(seam)
    assert "MHA-DT-09" in seam.splitlines()[-1]
    # The seat length is the arm's, a fit-up reference whose callout names
    # the arm (owner ruling 2026-11-01 on the r9 review).
    assert drawing.REFERENCE_LENGTHS == ("SeatLength",)
    assert drawing.DIMENSION_CALLOUTS["SeatLength"] == dt_crank_hub_notes.SEAT_LENGTH_CALLOUT
    assert "CRANK ARM" in _flat(dt_crank_hub_notes.SEAT_LENGTH_CALLOUT)
    # The taper-pin cross-hole names both mates and the fit on its callout,
    # after the front face is set flush with the datum it is reamed at.
    cross_hole = dt_crank_hub_notes.CROSS_HOLE_CALLOUT
    assert "MHA-DT-09" in cross_hole and "MHA-DT-11" in cross_hole
    assert "LIGHT DRIVE FIT" in cross_hole
    flush = cross_hole.index("CRANK-ARM END FLUSH")
    assert flush < cross_hole.index("TAPER-REAM") and "AT ASSEMBLY" in cross_hole
    # The pin-proud MIN names the ream it limits.
    assert "TAPER-REAM" in dt_crank_hub_notes.PIN_PROUD_CALLOUT
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
    the hub -- its cross-hole callout and the MHA-DT-00 hub step -- print the
    one datum, and the callout sets it before the taper-ream."""
    import build_dt_drive_train_assembly as assembly
    import draw_dt_drive_train_assembly as package

    datum = dt_crank_hub_notes.FRONT_FACE_DATUM
    assert _names_the_dome_root(datum), datum
    assert assembly.CRANK_HUB_Z0 == assembly.CRANKSHAFT_Z0 == assembly.CRANK_FACE_Z
    hub_step = package.CONE_CRANK_STEPS.split("\n6. ")[1].split("\n7. ")[0]
    cross_hole = dt_crank_hub_notes.CROSS_HOLE_CALLOUT
    for text in (cross_hole, hub_step):
        assert _sets_hub_on(text, datum), text
    assert _flat(cross_hole).index(_flat(datum)) < _flat(cross_hole).index("TAPER-REAM")
    # Negative controls: the shaft-END texts both once printed name no dome root.
    for old in (
        "FRONT FACE FLUSH WITH\nCRANKSHAFT MHA-DT-11 END;\nMATCH TAPER-REAM 1:48 FOR",
        "SET THE HUB FRONT FACE FLUSH WITH THE\n   SHAFT END, PUNCH MARKS ALIGNED;",
    ):
        assert not _sets_hub_on(old, datum), old
    assert not _names_the_dome_root("CRANKSHAFT MHA-DT-11 END")


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
    assert drawing.END_KEEP["BoreDia"][0] > drawing.END_CENTER[0]


def test_side_view_lies_as_in_the_lathe_with_one_outboard_baseline() -> None:
    # Axis horizontal, faced outboard end on the right, seam (+Z) at the bottom.
    assert drawing.OUTBOARD_X > drawing.SHOULDER_X > drawing.INBOARD_X
    assert drawing._sheet_y(geometry.AXIAL_PIN_RADIUS_FROM_AXIS) < drawing.SIDE_CENTER[1]
    assert drawing.END_CENTER[0] > drawing.OUTBOARD_X  # third-angle right view
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    # The pin station from the faced end (drawing-guidelines.md rule 11
    # (turned parts read like the lathe); machinist review of the inch
    # sheet: no chain through the shoulder), on its own row under the seat
    # length's; the relief from the rear face below the profile; the
    # toleranced overall, front face to rear face, on the lowest row.  No
    # chained barrel length.
    seat_row = drawing.SIDE_KEEP["SeatLength"][1]
    station_row = drawing.SIDE_KEEP["ServicePinStation"][1]
    relief_row = drawing.SIDE_KEEP["ReliefLength"][1]
    overall_row = drawing.SIDE_KEEP["HubLength"][1]
    assert seat_row < drawing.BARREL_BOTTOM and seat_row - overall_row >= 0.016
    assert seat_row > station_row > overall_row
    assert seat_row > relief_row and relief_row - overall_row >= 0.010
    assert "BarrelLength" not in drawing.SIDE_KEEP
    printed = {
        name for names in dt_crank_hub_spec.DRAWING_DIMENSIONS.values() for name in names
    }
    assert "BarrelLength" not in printed and "HubLength" in printed
    assert drawing.SHOULDER_X > drawing.SERVICE_PIN_CENTER[0] > drawing.RELIEF_X
    # The relief's toleranced length and the pin station must not meet across
    # (~2.5 mm per character).
    relief_right = drawing.SIDE_KEEP["ReliefLength"][0] + len(".16") * 0.00125
    pin_left = drawing.SIDE_KEEP["ServicePinStation"][0] - len(".53") * 0.00125
    assert relief_right < pin_left
    # The relief's mate callout reads under its text, on the overall's row;
    # it must end short of the rear face, where that row's dimension line
    # starts (~2.5 mm per character, centred on the text).
    widest = max(
        len(line) for line in dt_crank_hub_notes.RELIEF_LENGTH_CALLOUT.splitlines()
    )
    assert drawing.SIDE_KEEP["ReliefLength"][0] + widest * 0.00125 < drawing.INBOARD_X


def test_callouts_stand_clear_of_views_and_each_other() -> None:
    # ~2.5 mm per character at the sheet's text height; callout lines are
    # centred on their value, so the widest line sets each block's extent.
    char_w = 0.0025

    def half(text: str) -> float:
        return max(len(line) for line in text.splitlines()) * char_w / 2.0

    # The seat Ø's text stands outside its arrows, so its block starts at its
    # dimension line and runs right (farm run 20261101T081735465Z: 245..329
    # mm, the line at 245.2).
    seat_x, seat_y = drawing.SIDE_KEEP["SeatDia"]
    seat_block = (seat_x, seat_x + 2.0 * half(dt_crank_hub_notes.SEAT_CALLOUT))
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
    # The fit-up seat length prints right of the outboard end with its
    # callout, short of the end view.
    seat_len_x, _ = drawing.SIDE_KEEP["SeatLength"]
    seat_len_half = half(dt_crank_hub_notes.SEAT_LENGTH_CALLOUT)
    assert drawing.OUTBOARD_X < seat_len_x - seat_len_half
    assert seat_len_x + seat_len_half < end_left
    # Its value stands clear of the seat diameter's dimension line above.
    value_half = len("(.31)") * char_w / 2.0
    assert seat_len_x - value_half - drawing.SIDE_KEEP["SeatDia"][0] > 0.002
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
    assert "ServicePinStation" in drawing.SIDE_KEEP
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
    # the seat bore's REAL limits. MHA-DT-06 bores the seat first at .XX; the
    # MHA-DT-31 seat is turned to suit it for a press, so it is never smaller.
    mm = 25.4
    assert geometry.ARM_WIDTH_STOCK_MINUS == pytest.approx(0.004 * mm)
    bore_max = geometry.HUB_SEAT_DIA + 0.01 * mm
    bore_min = geometry.HUB_SEAT_DIA - 0.01 * mm
    cheek = geometry.wall_after_edge_break(
        geometry.ARM_WIDTH - geometry.ARM_WIDTH_STOCK_MINUS, bore_max
    )
    web = geometry.wall_after_edge_break(
        bore_min - geometry.AXIAL_PIN_DIA_STOCK_MAX, geometry.HUB_BORE_DIA_MAX
    )
    assert cheek >= geometry.WALL_TARGET_MM
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


def test_pin_proud_min_lands_on_the_phantom_big_end() -> None:
    # r5 review (run 20261101T004958072Z): the 4.45 MIN's outer extension line
    # ended in air. The reference sketch draws MHA-DT-09's proud big end as
    # construction (phantom on the sheet) round the line's outer end: its face
    # centred on the line's end, stubs back to the barrel's outline.
    import dt_crank_pin_spec
    from dt_crank_pin_ring_spec import PIN_PROUD

    build = Path(drawing.__file__).with_name("build_dt_crank_hub.py").read_text(encoding="utf-8")
    sketch = build[
        build.index("async def _pin_proud_reference") : build.index('name_last_feature(adapter, "PinProudReference")')
    ]
    assert 'await adapter.add_line(-BARREL_R, 0.0, tip, 0.0)' in sketch
    assert "(tip, PIN_BIG_END_R),\n                (tip, -PIN_BIG_END_R)," in sketch.replace("\r\n", "\n")
    assert 'add_sketch_constraint(f"{line}.end", face, "midpoint")' in sketch
    assert "segment.ConstructionGeometry = True" in sketch
    assert '["PinProud", "PinProudBarrel", "PinBigEnd", "PinBigEndStub"]' in build
    # Only the MIN prints; the outline's own dimensions stay unmarked.
    assert dt_crank_hub_spec.DRAWING_DIMENSIONS["PinProudReference"] == {"PinProud"}
    # The stubs leave the barrel's outline, and the face stands clear of it.
    barrel_r = geometry.HUB_BARREL_DIA / 2.0
    big_end_r = dt_crank_pin_spec.BIG_END_DIA / 2.0
    stub_x = (barrel_r**2 - big_end_r**2) ** 0.5
    assert barrel_r - 0.5 < stub_x < barrel_r
    assert stub_x < barrel_r + PIN_PROUD
    assert "PIN_STUB_X = math.sqrt(BARREL_R**2 - PIN_BIG_END_R**2)" in build


def test_pin_proud_callout_names_the_pin_big_end_and_ring() -> None:
    # r7 review (run 20261101T022045634Z): the outlined big end and the ring
    # were unnamed; rule 4 wants the mate's name with its number.
    text = " ".join(dt_crank_hub_notes.PIN_PROUD_CALLOUT.split())
    for part in ("MHA-DT-09 TAPER PIN BIG END", "KEEPER RING MHA-DT-27"):
        assert part in text
    lines = dt_crank_hub_notes.PIN_PROUD_CALLOUT.splitlines()
    assert len(lines) == 4 and max(map(len, lines)) <= 29
    # The widest line (2.5 mm a glyph) starts right of the phantom big end.
    big_end_right = drawing.END_CENTER[0] + (geometry.HUB_BARREL_DIA / 2.0 + 4.45) * drawing._S
    left = drawing.END_KEEP["PinProud"][0] - max(map(len, lines)) * 0.0025 / 2.0
    assert left - big_end_right >= 0.00178
