"""Offline contracts for the cone gears' dividing-head index plate (MHA-DT-03-TL-01)."""

from __future__ import annotations

import math

import _config
import build_dt_cone_gear_tl_index_plate as part
import dt_cone_gear_tl_index_plate_spec as spec
import draw_dt_cone_gear_tl_index_plate as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout

INCH = 25.4


def test_each_circle_indexes_its_cone_gear_on_the_40_to_1_head() -> None:
    assert spec.WORM_RATIO == 40
    assert sorted(spec.RING_TEETH.values()) == sorted(spec.GEAR_TEETH) == [96, 102, 114]
    advances = {
        circle: spec.holes_per_tooth(teeth, circle)
        for circle, teeth in spec.RING_TEETH.items()
    }
    assert advances == {57: 20.0, 51: 20.0, 24: 10.0}
    assert spec.HOLE_COUNT == 132 == sum(spec.RING_COUNTS)


def test_no_stock_bs0_plate_indexes_these_gears() -> None:
    stock = (15, 16, 17, 18, 19, 20, 21, 23, 27, 29, 31, 33, 37, 39, 41, 43, 47, 49)
    # 40/96 = 5/12, 40/102 = 20/51 and 40/114 = 20/57 need circles divisible
    # by 12, 51 and 57; no stock circle is.
    for teeth in (96, 102, 114):
        assert not any(
            spec.holes_per_tooth(teeth, circle).is_integer() for circle in stock
        ), teeth


def test_the_model_globals_are_the_spec_sizes() -> None:
    g = spec.GLOBALS
    assert (g["PlateDia"], g["BoreDia"], g["PlateThick"]) == (
        spec.PLATE_DIA,
        spec.BORE_DIA,
        spec.THICKNESS,
    )
    assert {n: g[f"Ring{n}Pcd"] for n in spec.RING_COUNTS} == spec.RING_PCDS
    assert g["IndexHoleDia"] == spec.INDEX_HOLE_DIA
    assert (g["MountPcd"], g["MountHoleDia"], g["CboreDia"], g["CboreDepth"]) == (
        spec.MOUNT_PCD,
        spec.MOUNT_HOLE_DIA,
        spec.CBORE_DIA,
        spec.CBORE_DEPTH,
    )
    assert math.isclose(math.hypot(*spec.MOUNT_SEED), spec.MOUNT_PCD / 2.0)
    assert spec.MOUNT_SEED[0] < 0.0 < spec.MOUNT_SEED[1]


def test_the_hole_circles_stand_inside_the_stock_plates_circle_band() -> None:
    # Owner facts 2026-11-24: "rim to outermost hole edge 0.1030";
    # "innermost hole edge to hto bore 0.5545".
    assert "issues/2157" in spec.TRACKING_ISSUE
    assert math.isclose(spec.STOCK_OUTER_CIRCLE_DIA, 3.614 * INCH)
    assert math.isclose(spec.STOCK_INNER_CIRCLE_DIA, 2.056 * INCH)
    assert spec.RING_PCDS == {57: 3.614 * INCH, 51: 3.217 * INCH, 24: 2.700 * INCH}
    for pcd in spec.RING_PCDS.values():
        assert 2.056 * INCH - 1e-9 <= pcd <= 3.614 * INCH + 1e-9


def test_registry_row_is_tooling_in_inch() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == "MHA-DT-03-TL-01"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 1
    entry = DRAWINGS_BY_NAME["dt_cone_gear_tl_index_plate"]
    assert entry.artifact_stem == spec.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"


def test_only_the_bore_carries_a_model_band() -> None:
    bands = model_toleranced_dimensions(part)
    assert set(bands) == {("PlateProfile", "BoreDia")}
    assert spec.BORE_DEVIATIONS == (0.0, 0.003 * INCH)
    assert spec.DRAWING_PRECISION_BY_NAME[spec.PRINTED_HOLE] == 3


def test_the_index_holes_are_the_owned_drill_just_over_the_measured_pin() -> None:
    # Owner fact 2026-11-24: "0.117 in dia dividing head pin"; owner ruling
    # 2026-11-23, tool audit Q15: drilled just over the pin, no reamer.
    assert math.isclose(spec.INDEX_PIN_DIA, 0.117 * INCH)
    assert spec.INDEX_HOLE_DRILL == "#31"
    assert math.isclose(spec.INDEX_HOLE_DIA, 0.1200 * INCH)
    # #32 (.1160), the next owned size down, does not pass the pin.
    assert 0.1160 * INCH < spec.INDEX_PIN_DIA < spec.INDEX_HOLE_DIA
    low, high = spec.INDEX_HOLE_DEVIATIONS
    assert low == 0.0
    assert math.isclose(high, 0.004 * INCH)
    least, most = spec.INDEX_PIN_CLEARANCE
    assert math.isclose(least, 0.003 * INCH)
    assert math.isclose(most, 0.007 * INCH)
    callout = spec.CALLOUTS_BELOW[spec.PRINTED_HOLE].split("\n")
    assert callout[:2] == ["#31 DRILL THRU", "BS-0 HEAD INDEX PIN ENTERS"]
    assert "REAM" not in spec.CALLOUTS_BELOW[spec.PRINTED_HOLE]


def test_pin_play_and_position_zone_stay_under_half_a_percent_of_pitch() -> None:
    # The drilled-hole location the shop holds from a datum bore: ±.005.
    assert math.isclose(spec.INDEX_POSITION, 0.014 * INCH)
    assert spec.INDEX_POSITION >= math.hypot(0.005, 0.005) * 2.0 * INCH - 0.001 * INCH
    # Owner fact 2026-11-24: "hub plate sits on 0.8245".
    assert math.isclose(spec.HUB_CLEARANCE[0], 0.0025 * INCH)
    assert math.isclose(spec.HUB_CLEARANCE[1], 0.0055 * INCH)
    # Half of each along the circle: the worst pin play (.007), the position
    # zone (.014) and the bore's clearance on the hub (.0055).
    assert math.isclose(spec.INDEX_ERROR_TANGENTIAL_MM, 0.01325 * INCH)
    for circle, teeth in spec.RING_TEETH.items():
        crank = math.degrees(0.01325 / (spec.RING_PCDS[circle] / INCH / 2.0))
        assert math.isclose(spec.INDEX_ERROR_GEAR_DEG[teeth], crank / 40.0)
    # The 24-hole circle is the smallest radius: the worst of the three.
    assert max(spec.INDEX_ERROR_GEAR_DEG, key=spec.INDEX_ERROR_GEAR_DEG.get) == 96
    assert math.isclose(spec.INDEX_ERROR_GEAR_DEG[96], 0.014059, abs_tol=1e-6)
    assert max(spec.INDEX_ERROR_TOOTH_FRACTION.values()) < 0.004


def test_the_sheet_states_the_web_shortfall_it_carries() -> None:
    assert spec.SHORT_WEBS <= set(spec.WEBS_MM)
    shortest = min(spec.WEBS_MM[name] for name in spec.SHORT_WEBS)
    assert shortest == spec.WEB_MIN_MM
    assert spec.WEB_MIN_PRINTED * INCH <= spec.WEB_MIN_MM
    # At rule 17's .060 floor, under its .080 target (RV-01).
    assert 0.060 * INCH <= spec.WEB_MIN_MM < 0.080 * INCH
    assert spec.WEB_CALLOUT == "WEB .06 MIN"
    assert spec.CALLOUTS_BELOW[spec.PRINTED_HOLE].endswith(spec.WEB_CALLOUT)


def test_callouts_name_counts_and_the_counterbore() -> None:
    assert spec.CALLOUTS_ABOVE[spec.PRINTED_HOLE] == "132X"
    assert spec.CALLOUTS_ABOVE["Ring57Pcd"] == "57X EQ SP ON"
    assert spec.CALLOUTS_ABOVE["MountHoleDia"] == "3X"
    assert spec.CALLOUTS_BELOW["MountHoleDia"].split("\n") == [
        "DRILL THRU",
        "<HOLE-SPOT><MOD-DIAM>.346 <HOLE-DEPTH> .145",
        "BS-0 HEAD SCREWS",
        "WALL .03 MIN",
    ]
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.CALLOUTS_ABOVE) <= marked
    assert set(spec.CALLOUTS_BELOW) <= marked
    assert set(drawing.FACE_KEEP) | set(drawing.EDGE_KEEP) == marked


def test_the_measured_stock_plate_sets_the_envelope_and_the_screw_seat() -> None:
    # Owner fact 2026-11-24: "plate thickness 0.2770 dia 3.94; hole 0.8270; pin
    # hpoles 0.120 dia blind 0.1635 deep; 3x screw holes thru 15/64 countersunk
    # 0.3455 dia depth 0.1830"; corrected: "not countersunk counterbored;".
    assert math.isclose(spec.PLATE_DIA, 3.94 * INCH)
    assert math.isclose(spec.BORE_DIA, 0.827 * INCH)
    assert spec.BORE_DIA + spec.BORE_DEVIATIONS[0] >= 0.8270 * INCH - 1e-9
    assert math.isclose(spec.STOCK_PIN_HOLE_DIA, spec.INDEX_HOLE_DIA)
    assert spec.MOUNT_COUNT == 3
    assert 0.234 * INCH <= spec.MOUNT_HOLE_DIA <= 15.0 / 64.0 * INCH
    assert spec.MOUNT_HOLE_DIA > spec.MOUNT_SCREW_BODY_DIA
    assert abs(spec.CBORE_DIA - 0.3455 * INCH) <= 0.0005 * INCH + 1e-9
    # Owner fact 2026-11-24: "head dia 0.3235; below plate; why do you care
    # about thread i will use the same screws with all plates".
    assert spec.CBORE_DIA - 0.005 * INCH > spec.MOUNT_SCREW_HEAD_DIA
    assert math.isclose(spec.HEAD_RISE, 0.038 * INCH)
    # Owner fact 2026-11-24: "screw head 0.1380 high": below the face even in
    # the shallowest counterbore the .XXX band allows.
    assert math.isclose(spec.HEAD_BELOW_FACE_MIN, 0.002 * INCH, abs_tol=1e-9)
    # The plate is thinner than stock; the seat under the screw head is not.
    assert spec.THICKNESS < spec.STOCK_PLATE_THICKNESS
    assert math.isclose(spec.CBORE_SEAT, 0.095 * INCH)
    assert abs(spec.CBORE_SEAT - (0.2770 - 0.1830) * INCH) <= 0.0015 * INCH
    assert spec.CBORE_SEAT_MIN >= 0.080 * INCH - 1e-9
    # Owner fact 2026-11-24: "pin goes 0.1555 into blind holes": .037 less in
    # this thinner plate, and never through it.
    assert math.isclose(spec.PIN_ENGAGEMENT, 0.1185 * INCH)
    assert math.isclose(spec.PIN_ENGAGEMENT_MIN, 0.1085 * INCH)
    assert spec.PIN_ENGAGEMENT < spec.THICKNESS - 0.01 * INCH


def test_the_bolt_circle_is_inferred_from_the_owners_two_readings() -> None:
    # Owner fact 2026-11-24: "screw hole outside to outside 1.4445; screw hole
    # edge to bore edge 0.0415"; asked which edges: "Yes, both at the
    # counterbore edges."
    by_chord = (1.4445 - 0.3455) / math.sqrt(3.0)
    by_bore = 0.8270 / 2.0 + 0.0415 + 0.3455 / 2.0
    assert math.isclose(by_chord, 0.6345, abs_tol=1e-4)
    assert math.isclose(by_bore, 0.6278, abs_tol=1e-4)
    assert math.isclose(spec.MOUNT_PCD, 1.260 * INCH)
    assert abs(spec.MOUNT_PCD / INCH - 32.0 / 25.4) < 0.0005
    assert by_bore - 0.005 < spec.MOUNT_PCD / INCH / 2.0 < by_chord + 0.005
    # Owner ruling 2026-11-24 (RV-04): "Accept the .04 wall as an exception,
    # same as the maker's plate."
    assert spec.CBORE_WALL not in spec.WEBS_MM
    assert spec.CBORE_WALL_NOMINAL >= 0.0415 * INCH
    assert math.isclose(spec.CBORE_WALL_MIN_MM, 0.037 * INCH)
    assert spec.CBORE_WALL_CALLOUT == "WALL .03 MIN"


def test_the_build_volume_budget_counts_every_hole() -> None:
    holes = sum(spec.RING_COUNTS) * part.V_INDEX_HOLE
    mounts = spec.MOUNT_COUNT * (part.V_MOUNT_HOLE + part.V_CBORE)
    assert math.isclose(part.V_FINISHED, part.V_PLATE - holes - mounts)
    assert part.V_CBORE > 0.0


def test_builder_declares_the_spec_part_name() -> None:
    assert part.PART_NAME == spec.PART_NAME
