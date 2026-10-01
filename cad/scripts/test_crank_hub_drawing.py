"""Offline release contracts for separate through hub MHA-137."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import crank_hub_geometry as geometry
import crank_hub_notes
import crank_hub_spec
import crankshaft_spec
import draw_crank_hub as drawing
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


def test_mha024_ream_ligaments_meet_rule_12_at_the_printed_bands() -> None:
    # CONTRACT-crank MHA-137: 8 seat + 17.2 of hub behind the shoulder (19
    # until the seat face moved 1.8 forward, ruling 2026-09-30), the ream
    # station unchanged 5.6 from the shoulder at .XX.  The rear 3.85 is the
    # chain-plate relief (Main, 2026-09-30; lengthened from 3.6 for the
    # floated wheel, PR1 Codex review 2), so the Ø20.6 barrel is 13.35.
    assert geometry.HUB_BARREL_DIA == 20.6
    assert geometry.HUB_LENGTH == pytest.approx(25.2)
    assert geometry.HUB_BARREL_LENGTH == pytest.approx(13.35)
    assert geometry.SERVICE_PIN_FROM_SHOULDER == 5.6
    assert geometry.SERVICE_PIN_STATION == pytest.approx(13.6)
    assert crank_hub_spec.DRAWING_PRECISION["ServicePinStationReference"] == {
        "ServicePinFromShoulder": 2
    }
    # The contract's nominal walls and ligaments.
    ream_r = geometry.SERVICE_PIN_REAM_RADIUS_MAX
    rear_from_shoulder = geometry.HUB_BARREL_LENGTH - geometry.SERVICE_PIN_FROM_SHOULDER
    assert (geometry.HUB_SEAT_DIA - geometry.HUB_BORE_DIA) / 2 == pytest.approx(
        4.92, abs=0.01
    )
    assert geometry.HUB_BARREL_DIA / 2 - ream_r == pytest.approx(7.33, abs=0.01)
    assert geometry.SERVICE_PIN_FROM_SHOULDER - ream_r == pytest.approx(2.63, abs=0.01)
    # The ream ends at the relief shoulder, not the rear face.
    assert rear_from_shoulder - ream_r == pytest.approx(4.78, abs=0.01)
    # Worst case at the printed bands (rule 12): the shoulder side governs.
    # Behind the ream the relief shoulder is placed from the front face by
    # the .XX overall less the .XX relief, the ream by the .X seat length and
    # the .XX station: 21.25 - 8.8 - 6.11 - 2.97.
    assert geometry.SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM == pytest.approx(
        2.121, abs=1e-3
    )
    assert geometry.SERVICE_PIN_REAR_LIGAMENT_WORST_MM == pytest.approx(3.371, abs=1e-3)
    assert geometry.SERVICE_PIN_BARREL_WALL_WORST_MM == pytest.approx(6.931, abs=1e-3)


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
    # the chain's axial air at print-worst, and so does the overall that
    # places the rear face it is printed from.
    assert geometry.RELIEF_DIA_MAX == pytest.approx(17.01)
    assert geometry.RELIEF_LENGTH_TOL == 0.05
    assert geometry.HUB_LENGTH_TOL == 0.05
    assert crank_hub_spec.DRAWING_PRECISION["HubProfile"]["ReliefLength"] == 2
    assert crank_hub_spec.DRAWING_PRECISION["HubProfile"]["HubLength"] == 2
    assert crank_hub_spec.DRAWING_PRECISION["HubProfile"]["ReliefDia"] == 2
    # Rule 12 wall over the bore: Ø15.99 against the Ø9.580 bore, edges broken.
    assert geometry.RELIEF_WALL_WORST_MM == pytest.approx(2.705, abs=1e-3)
    assert geometry.RELIEF_WALL_WORST_MM >= geometry.WALL_TARGET_MM
    # The MHA-024 ream stays on the full barrel.
    assert (
        geometry.SERVICE_PIN_STATION + geometry.SERVICE_PIN_REAM_RADIUS_MAX
        < geometry.RELIEF_STATION
    )


def _stack_a(relief_length: float) -> dict[str, float]:
    return geometry.chain_shoulder_axial_air(
        relief_length=relief_length,
        seat_face=crankshaft_spec.SEAT_COLLAR,
        seat_face_band=crankshaft_spec.SEAT_COLLAR_BAND,
    )


def test_chain_clears_the_relief_shoulder_with_the_wheel_floated_onto_the_hub() -> None:
    # Codex PR1 review 2: the wheel may walk forward off its drive pins until
    # its front face meets the hub rear face (the pin check admits it).  The
    # thinnest wheel there, with the shortest relief, brings a bought chain's
    # frontmost envelope nearest the barrel shoulder; the old 3.6 relief let
    # it cut 0.0365 into the shoulder while the seated check read 0.2135.
    with pytest.raises(AssertionError, match="floated_worst -0.0365"):
        _stack_a(3.6)
    airs = _stack_a(geometry.RELIEF_LENGTH)
    assert airs["floated_worst"] == pytest.approx(0.2135, abs=1e-9)
    assert airs["floated"] == pytest.approx(0.3635, abs=1e-9)
    assert airs["seated_worst"] == pytest.approx(0.4635, abs=1e-9)
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
        seat_face=crankshaft_spec.SEAT_COLLAR + 1.0,
        seat_face_band=crankshaft_spec.SEAT_COLLAR_BAND,
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
    low, high = crank_hub_notes.SEAT_PRESS_INTERFERENCE
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
    assert DRAWINGS_BY_NAME["crank_hub"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-hub.SLDDRW")
    marked = set().union(*crank_hub_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_matched_fits_and_distinct_pins_live_on_their_feature_callouts() -> None:
    # Policy rule 6: no general notes; each matched fit sits on its feature.
    assert not hasattr(crank_hub_spec, "DRAWING_NOTES")
    seat = crank_hub_notes.SEAT_CALLOUT
    # B1 (Main 2026-09-25): turned to suit the MHA-020 bore, with the press
    # interference printed from the notes constant.
    low, high = crank_hub_notes.SEAT_PRESS_INTERFERENCE
    assert seat.splitlines() == [
        "TURN TO SUIT MHA-020 BORE",
        f"FOR LIGHT PRESS: {low:.3f}-{high:.3f}",
        "DIAMETRAL INTERFERENCE;",
        "FACES FLUSH",
    ]
    assert "MATCH-FIT" not in seat
    # The arm bore is made first; the hub seat is turned to suit it, so its
    # nominal prints as a reference.
    assert crank_hub_spec.REFERENCE_DIMENSIONS == {"SeatDia"}
    seam = crank_hub_notes.SEAM_CALLOUT
    assert "MHA-020" in seam and "MHA-138" in seam and "LIGHT DRIVE FIT" in seam
    assert "AT ASSEMBLY" in seam and "SEAM" in seam
    # Size first, then the process, in the order the work is done.
    assert seam.splitlines()[0] == "(<MOD-DIAM>4.0) <HOLE-DEPTH> 4.0"
    assert "O'CLOCK" not in seam
    # The taper-pin cross-hole names both mates and the fit on its callout,
    # after the front face is set flush with the datum it is reamed at.
    cross_hole = crank_hub_notes.CROSS_HOLE_CALLOUT
    assert "MHA-024" in cross_hole and "MHA-026" in cross_hole
    assert "LIGHT DRIVE FIT" in cross_hole
    flush = cross_hole.index("FRONT FACE FLUSH")
    assert flush < cross_hole.index("TAPER-REAM")
    # The bore band governs; the clearance is a reference restatement.
    assert crank_hub_notes.BORE_CALLOUT.splitlines()[1].startswith("(")


def _flat(text: str) -> str:
    return " ".join(text.split())


def _names_the_dome_root(datum: str) -> bool:
    words = datum.split()
    return datum.endswith("DOME ROOT") and "MHA-026" in words and "END" not in words


def _sets_hub_on(text: str, datum: str) -> bool:
    """A printed text places the hub on ``datum``, the one source both read."""
    return _flat(datum) in _flat(text)


def test_hub_front_face_is_set_on_the_dome_root_the_model_places_it_at() -> None:
    """The model seats the hub front face on the crankshaft's dome root (the
    shaft part's origin, CRANK_FACE_Z); the dome tip stands proud of it.  Set
    flush with the shaft END, the hub would sit a dome height forward and open
    the hub/T12 air past the drive pins' proud length.  Both texts that place
    the hub -- its cross-hole callout and the MHA-A03 hub step -- print the
    one datum, and the callout sets it before the taper-ream."""
    import build_drive_train_assembly as assembly
    import draw_drive_train_assembly as package

    datum = crank_hub_notes.FRONT_FACE_DATUM
    assert _names_the_dome_root(datum), datum
    assert assembly.CRANK_HUB_Z0 == assembly.CRANKSHAFT_Z0 == assembly.CRANK_FACE_Z
    hub_step = package.CONE_CRANK_STEPS.split("\n6. ")[1].split("\n7. ")[0]
    cross_hole = crank_hub_notes.CROSS_HOLE_CALLOUT
    for text in (cross_hole, hub_step):
        assert _sets_hub_on(text, datum), text
    assert _flat(cross_hole).index(_flat(datum)) < _flat(cross_hole).index("TAPER-REAM")
    # Negative controls: the shaft-END texts both once printed name no dome root.
    for old in (
        "FRONT FACE FLUSH WITH\nCRANKSHAFT MHA-026 END;\nMATCH TAPER-REAM 1:48 FOR",
        "SET THE HUB FRONT FACE FLUSH WITH THE\n   SHAFT END, PUNCH MARKS ALIGNED;",
    ):
        assert not _sets_hub_on(old, datum), old
    assert not _names_the_dome_root("CRANKSHAFT MHA-026 END")


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
    # Seat from the faced end, the pin station from the shoulder (policy rule
    # 12), the relief from the rear face on one row; the toleranced overall,
    # front face to rear face, on the row below.  No chained barrel length.
    seat_row = drawing.SIDE_KEEP["SeatLength"][1]
    assert drawing.SIDE_KEEP["ServicePinFromShoulder"][1] == seat_row
    assert drawing.SIDE_KEEP["ReliefLength"][1] == seat_row
    overall_row = drawing.SIDE_KEEP["HubLength"][1]
    assert seat_row < drawing.BARREL_BOTTOM and seat_row - overall_row >= 0.010
    assert "BarrelLength" not in drawing.SIDE_KEEP
    printed = {
        name for names in crank_hub_spec.DRAWING_DIMENSIONS.values() for name in names
    }
    assert "BarrelLength" not in printed and "HubLength" in printed
    assert drawing.SHOULDER_X > drawing.SERVICE_PIN_CENTER[0] > drawing.RELIEF_X
    # The relief's toleranced length and the pin station share the seat row
    # without their text meeting (~2.5 mm per character).
    relief_right = drawing.SIDE_KEEP["ReliefLength"][0] + len("3.60±0.05") * 0.00125
    pin_left = drawing.SIDE_KEEP["ServicePinFromShoulder"][0] - len("5.60") * 0.00125
    assert relief_right < pin_left
    # The relief's mate callout reads under its text, on the overall's row;
    # it must end short of the rear face, where that row's dimension line
    # starts (~2.5 mm per character, centred on the text).
    widest = max(
        len(line) for line in crank_hub_notes.RELIEF_LENGTH_CALLOUT.splitlines()
    )
    assert drawing.SIDE_KEEP["ReliefLength"][0] + widest * 0.00125 < drawing.INBOARD_X


def test_callouts_stand_clear_of_views_and_each_other() -> None:
    # ~2.5 mm per character at the sheet's text height; callout lines are
    # centred on their value, so the widest line sets each block's extent.
    char_w = 0.0025

    def half(text: str) -> float:
        return max(len(line) for line in text.splitlines()) * char_w / 2.0

    seat_x, seat_y = drawing.SIDE_KEEP["SeatDia"]
    seat_half = half(crank_hub_notes.SEAT_CALLOUT)
    seat_block = (seat_x - seat_half, seat_x + seat_half)
    hole_x, hole_y = drawing.HOLE_CALLOUT_XY
    hole_text = f"{crank_hub_notes.CROSS_HOLE_CALLOUT}\n#14 DRILL 0 4.62 THRU ALL"
    hole_block = (hole_x - half(hole_text), hole_x + half(hole_text))
    # The cross-hole leader rises from the hole's top rim to the block's
    # right end; the seat callout must start right of that leader.
    assert hole_block[1] < drawing.SERVICE_PIN_TOP_RIM[0] < seat_block[0]
    # The value line plus every callout line stays above the barrel.
    seat_lines = 1 + len(crank_hub_notes.SEAT_CALLOUT.splitlines())
    assert seat_y - seat_lines * 0.006 > drawing.BARREL_TOP
    assert hole_y - 5 * 0.006 > drawing.BARREL_TOP
    end_left = drawing.END_CENTER[0] - geometry.HUB_BARREL_DIA / 2.0 * drawing._S
    end_right = drawing.END_CENTER[0] + geometry.HUB_BARREL_DIA / 2.0 * drawing._S
    bore_x, bore_y = drawing.END_KEEP["BoreDia"]
    # Right of the end view, so its leader enters the bore from the right,
    # clear of the six-o'clock seam and its callout.
    assert bore_x - half(crank_hub_notes.BORE_CALLOUT) > end_right
    assert bore_y < drawing.END_CENTER[1]
    assert seat_block[1] < drawing.ISO_NOTE_XY[0] and end_left > drawing.OUTBOARD_X
    # Both turned diameters stand left of the inboard end, the relief's nearer,
    # their values side by side on the axis without touching.
    relief_x = drawing.SIDE_KEEP["ReliefDia"][0]
    barrel_x = drawing.SIDE_KEEP["BarrelDia"][0]
    assert barrel_x < relief_x < drawing.INBOARD_X
    relief_half = len("Ø16.50") * char_w / 2.0
    assert barrel_x + len("Ø20.6") * char_w / 2.0 < relief_x - relief_half
    assert relief_x + relief_half < drawing.INBOARD_X


def test_station_reference_sketch_lies_in_the_side_view_plane() -> None:
    # A standalone reference sketch imports its dimension natively only on the
    # plane of the view that prints it; on Front, the *Right side view got the
    # sketch but no ServicePinStation (run 20260922T020620997Z-4a7ef16e).
    source = Path(drawing.__file__).with_name("build_crank_hub.py").read_text(
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
    notes = {"crank_hub_notes", "crank_arm_notes", "crankshaft_notes"}

    def reached(stem: str) -> set[str]:
        return {Path(str(dep)).stem for dep in module_deps_of(scripts / f"{stem}.py")}

    for stem in (
        "build_crank_hub",
        "build_crank_arm",
        "build_crank_hub_pin",
        "build_crankshaft",
        "build_crank_handle_pivot_screw",
        "build_drive_train_assembly",
        "_interference_contracts",
    ):
        assert not reached(stem) & notes, stem
    assert "crank_hub_notes" in reached("draw_crank_hub")
    assert "crank_arm_notes" in reached("draw_crank_arm")
    assert "crankshaft_notes" in reached("draw_crankshaft")


# Drawing-simplicity policy rule 6: at most four short lines. Codex #892
# (PRRT_kwDOPHDy386mMQpe): the generated seat callout printed five.
CALLOUT_LINE_CAP = 4


@pytest.mark.parametrize(
    "name, text",
    [
        ("SEAT_CALLOUT", crank_hub_notes.SEAT_CALLOUT),
        ("SEAM_CALLOUT", crank_hub_notes.SEAM_CALLOUT),
        ("BORE_CALLOUT", crank_hub_notes.BORE_CALLOUT),
        ("CROSS_HOLE_CALLOUT", crank_hub_notes.CROSS_HOLE_CALLOUT),
        ("seat_bore_callout", crank_hub_notes.seat_bore_callout("MHA-137")),
    ],
)
def test_every_generated_callout_stays_within_four_lines(name: str, text: str) -> None:
    assert len(text.splitlines()) <= CALLOUT_LINE_CAP, (name, text.splitlines())


def test_u29_walls_hold_at_the_seat_bores_printed_limits() -> None:
    # Main 2026-09-25: the arm is 1-in CF flat, held to 0.004 in on width
    # (OnlineMetals, Speedy Metals), not 0.003; and the cheek must come from
    # the seat bore's REAL limits. MHA-020 bores the seat first at .X; the
    # MHA-137 seat is turned to suit it for a press, so it is never smaller.
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
    build = Path(drawing.__file__).with_name("build_crank_hub.py").read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "ServicePinStationReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source.replace("\r\n", "\n")
    assert "ServicePinStationReference" in crank_hub_spec.DRAWING_DIMENSIONS
