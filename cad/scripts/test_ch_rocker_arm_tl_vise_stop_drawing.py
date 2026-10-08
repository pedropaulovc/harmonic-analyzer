"""Offline contracts for the rocker arm's vise blank-end stop (MHA-CH-006-TL-01)."""

from __future__ import annotations

import re

import _config
import ch_rocker_arm_spec as arm
import ch_rocker_arm_tl_vise_stop_spec as spec
import draw_ch_rocker_arm_tl_vise_stop as drawing
import export_features
from _printed_tolerance import printed_band_mm

STEM = "ch_rocker_arm_tl_vise_stop"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.ELEVATION_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.ELEVATION_KEEP) & set(drawing.SIDE_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_every_printed_dimension_exports_its_printed_band() -> None:
    """Each printed toleranced dimension has one exported owner whose band is
    exactly the sheet's (the model value rounded to its places, then the
    drilled band for the holes or the title block's general band), with its
    nominal inside, and two dimensions never share an owner."""
    features = _features()
    owners = spec.DIMENSION_OWNERS
    assert set(owners) == set(spec.DRAWING_PRECISION_BY_NAME)
    assert len(set(owners.values())) == len(owners)
    for name, (feature, field) in owners.items():
        places = spec.DRAWING_PRECISION_BY_NAME[name]
        printed = round(spec.DRAWING_MODEL_MM[name], places)
        lower, upper = (
            (spec.DRILLED_BAND[1], spec.DRILLED_BAND[0])
            if name.endswith("HoleDia")
            else (-printed_band_mm(places), printed_band_mm(places))
        )
        exported = features[feature]
        assert field in exported["requirements"], name
        assert exported[field] == [round(printed + lower, 12), round(printed + upper, 12)], name
        nominal = exported[f"{field}_nominal"]
        assert exported[field][0] <= nominal <= exported[field][1], name


def test_nose_stops_the_blank_on_stock_outboard_of_the_finished_arm() -> None:
    """The exported stop point sits on the raw blank end, which lies outboard
    of the parent arm's widest half-span, so the contact mark is cut away."""
    end_x, _y, end_z = _features()["nose_hole"]["end"]
    setup_x = end_x - spec.JAW_HALF_WIDTH
    assert setup_x == spec.BLANK_END_X_SETUP
    assert -setup_x > arm.ROD_TIP_X
    blank_low, blank_high = (z - spec.SETUP_Z_OF_JAW_TOP for z in spec.BLANK_Z_SETUP)
    assert blank_low < end_z - spec.NOSE_PIN_DIA / 2.0
    assert end_z + spec.NOSE_PIN_DIA / 2.0 < blank_high


def test_bonded_nose_pin_ends_at_the_stop_face() -> None:
    """A pin bonded flush with the back face ends at the exported stop X,
    standing proud of the finger front."""
    features = _features()
    back_x = spec.SEAT_X - features["seat_face"]["length_nominal"]
    pin_end_x = back_x + spec.NOSE_PIN_LENGTH
    assert abs(features["nose_hole"]["end"][0] - pin_end_x) < 1e-9
    assert pin_end_x > features["finger_front"]["plane"]["value"]


def test_exported_hole_bands_are_the_printed_drilled_band() -> None:
    """The explicit drilled band applies to the model nominal, so the model
    must equal what the sheet prints or the exported limits drift."""
    features = _features()
    for name, dia in (("nose_hole", spec.NOSE_HOLE_DIA), ("screw_hole", spec.SCREW_HOLE_DIA)):
        printed = round(dia, features[name]["precision"]["dia"])
        assert features[name]["dia"] == [
            round(printed + spec.DRILLED_BAND[1], 12),
            round(printed + spec.DRILLED_BAND[0], 12),
        ]


def test_bond_gap_holds_on_every_pin_and_hole_the_bands_allow() -> None:
    largest_hole = spec.NOSE_HOLE_DIA + spec.DRILLED_BAND[0]
    smallest_hole = spec.NOSE_HOLE_DIA + spec.DRILLED_BAND[1]
    assert largest_hole - spec.NOSE_PIN_DIA <= spec.BOND_GAP_MAX
    assert smallest_hole > spec.NOSE_PIN_MAX


def test_walls_meet_rule_12_at_worst_case() -> None:
    assert min(spec.WALLS.values()) >= spec.RULE12_WALL_TARGET


def test_screw_engagement_and_tip_clearance_hold_at_every_screw_and_grip_corner() -> None:
    """Across the printed grip band and the bought screw's length band, the
    full thread never falls under the ruled 2.7 MIN, the tip never comes
    nearer the tap bottom than the printed clearance, and the sheet never
    states more of either than the corners leave."""
    places = spec.DRAWING_PRECISION_BY_NAME["ScrewGrip"]
    band = printed_band_mm(places)
    engagements, clearances = [], []
    for grip in (spec.SCREW_GRIP - band, spec.SCREW_GRIP + band):
        for length in (spec.SCREW_LENGTH + d for d in spec.SCREW_LENGTH_BAND):
            protrusion = length - grip
            engagements.append(protrusion - spec.SCREW_END_INCOMPLETE)
            clearances.append(spec.BASE_TAP_DEPTH - protrusion)
    assert spec.SCREW_ENGAGEMENT_RULED <= spec.SCREW_ENGAGEMENT_PRINTED <= min(engagements) + 1e-9
    assert spec.SCREW_ENGAGEMENT_PRINTED_D * spec.SCREW_MAJOR <= min(engagements) + 1e-9
    assert 0.0 < spec.SCREW_TIP_CLEARANCE_PRINTED <= min(clearances) + 1e-9
    assert f"ENGAGEMENT {spec.SCREW_ENGAGEMENT_PRINTED:.1f} MIN" in spec.SCREW_HOLE_CALLOUT
    assert f"TIP {spec.SCREW_TIP_CLEARANCE_PRINTED:.1f} MIN CLEAR" in spec.SCREW_HOLE_CALLOUT


def test_screw_hole_exports_as_drilled_clearance_with_the_grip_band() -> None:
    """The lug hole is a drilled clearance (the thread is the base's), and
    the grip that sets the screw's engagement exports its printed band."""
    features = _features()
    assert "thread" not in features["screw_hole"]
    assert features["screw_hole"]["process"] == "drill"
    grip = features["screw_seat"]
    assert grip["length"][0] < spec.SCREW_GRIP < grip["length"][1]
    assert abs(spec.SEAT_X - grip["plane"]["value"] - grip["length_nominal"]) < 1e-9


def test_installed_nose_pin_keeps_the_block_one_piece() -> None:
    """The bought nose pin is stated as installed, but the arm and finger
    are one block: the export must not permit a built-up part."""
    assert spec.NOSE_INSTALLED_NOTE in spec.DRAWING_NOTES
    assert export_features.requirement_manifest("ch_rocker_arm_tl_vise_stop")["construction"] == "one_piece"


def test_magnetic_base_sits_behind_the_rear_jaw_below_its_top() -> None:
    """The base's envelope clears the rear jaw's gripping plane (the blank,
    risers and parallels lie in front of it), stays under the jaw top and
    above the bed slideway, and carries the screw on its tap."""
    (x_lo, x_hi), (y_lo, y_hi), (z_lo, z_hi) = spec.BASE_ENVELOPE
    assert (x_lo, x_hi) == (spec.SEAT_X, 0.0)
    assert y_lo > 0.0 and z_hi < 0.0 and z_lo > -spec.JAW_HEIGHT
    assert (y_lo + y_hi) / 2.0 == spec.SCREW_Y
    assert (z_lo + z_hi) / 2.0 == spec.SCREW_Z


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-vise-stop")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(r"\bGROUND\b|\bGRIND", spec.DRAWING_NOTES)
