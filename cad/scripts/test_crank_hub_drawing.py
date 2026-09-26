"""Offline release contracts for separate through hub MHA-137."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import crank_hub_geometry as geometry
import crank_hub_notes
import crank_hub_spec
import draw_crank_hub as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_outboard_proportions_follow_the_u29_enlargement() -> None:
    unit = geometry.SHAFT_DIA / geometry.PHOTO_SHAFT
    scale = geometry.OUTBOARD_SCALE
    assert scale == 1.3
    assert geometry.HUB_SEAT_DIA == 19.5
    assert geometry.HUB_SEAT_DIA == pytest.approx(2.60 * unit * scale, abs=0.05)
    # Stock sizes: the pin is the dowel just under 1.3x, the arm is 1-in bar.
    assert geometry.AXIAL_PIN_DIA == 4.0 < 0.59 * unit * scale
    assert geometry.ARM_WIDTH == pytest.approx(25.4)
    # Named ratio deviation from the photograph (U29).
    assert geometry.ARM_TO_HUB_RATIO == pytest.approx(1.303, abs=1e-3)
    assert geometry.PHOTO_ARM_TO_HUB_RATIO == pytest.approx(1.208, abs=1e-3)


def test_u27_walls_hold_two_millimetres_at_the_printed_bands() -> None:
    assert geometry.WALL_TARGET_MM == 2.0
    assert geometry.SEAM_WEB_WORST_MM == pytest.approx(2.054, abs=1e-3)
    assert geometry.ARM_CHEEK_WORST_MM == pytest.approx(2.01, abs=1e-3)


def test_mha024_ream_ligaments_meet_rule_12_at_the_printed_bands() -> None:
    # The hub rear stays at 20 (the T12 air gap), so the ream is centred in the
    # 12-mm barrel and located from the shoulder at .XX: both ligaments 2.12.
    assert geometry.HUB_LENGTH == 20.0 and geometry.HUB_BARREL_LENGTH == 12.0
    assert geometry.SERVICE_PIN_FROM_SHOULDER == 5.6
    assert geometry.SERVICE_PIN_STATION == pytest.approx(13.6)
    assert crank_hub_spec.DRAWING_PRECISION["ServicePinStationReference"] == {
        "ServicePinFromShoulder": 2
    }
    assert geometry.SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM == pytest.approx(2.121, abs=1e-3)
    assert geometry.SERVICE_PIN_REAR_LIGAMENT_WORST_MM == pytest.approx(2.121, abs=1e-3)


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
    # The taper-pin cross-hole names both mates and the fit on its callout.
    cross_hole = crank_hub_notes.CROSS_HOLE_CALLOUT
    assert "MHA-024" in cross_hole and "MHA-026" in cross_hole
    assert "LIGHT DRIVE FIT" in cross_hole
    # The bore band governs; the clearance is a reference restatement.
    assert crank_hub_notes.BORE_CALLOUT.splitlines()[1].startswith("(")


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
    # Seat from the faced end, then the pin station and the barrel from the
    # shoulder (policy rule 12); the parenthesised overall on the bottom row.
    seat_row = drawing.SIDE_KEEP["SeatLength"][1]
    assert drawing.SIDE_KEEP["ServicePinFromShoulder"][1] == seat_row
    rows = [seat_row, drawing.SIDE_KEEP["BarrelLength"][1], drawing._ROW_Y[2]]
    assert rows == sorted(rows, reverse=True) and rows[0] < drawing.BARREL_BOTTOM
    assert all(upper - lower >= 0.010 for lower, upper in zip(rows[1:], rows[:-1]))
    assert drawing.SHOULDER_X > drawing.SERVICE_PIN_CENTER[0] > drawing.INBOARD_X
    assert crank_hub_spec.DRAWING_REFERENCE_PRECISION == {"overall length reference": 1}


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
    assert drawing.SIDE_KEEP["BarrelDia"][0] < drawing.INBOARD_X


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
    assert drawing.INBOARD_X < x < drawing.SHOULDER_X
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
