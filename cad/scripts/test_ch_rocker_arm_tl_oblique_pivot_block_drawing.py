"""Offline contracts for the oblique-trammel pivot block (MHA-CH-06-TL-22)."""

from __future__ import annotations

import asyncio
import ast
import inspect
import json
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_pivot_block as part
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_pivot_block_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_oblique_retention_spec as retention
import draw_ch_rocker_arm_tl_oblique_pivot_block as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
from _drawing_leaders import distance_to_box, segments_cross
from _paths import CAD_ROOT
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_tolerance import printed_band_mm
from machinist_exceptions import load_exceptions

STEM = "ch_rocker_arm_tl_oblique_pivot_block"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    keeps = (
        drawing.PLAN_KEEP,
        drawing.SECTION_A_KEEP,
        drawing.SECTION_B_KEEP,
        drawing.SIDE_KEEP,
        drawing.CAPTURE_KEEP,
        drawing.REGISTER_KEEP,
        drawing.REGISTER_SECTION_KEEP,
    )
    assert set().union(*keeps) == marked
    assert sum(len(keep) for keep in keeps) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.CALLOUTS_ABOVE) | set(spec.CALLOUTS_BELOW) <= marked


def test_block_and_seats_read_the_calculator() -> None:
    assert spec.BLOCK_HEIGHT == trammel.PIVOT_BLOCK_HEIGHT == 24.0
    assert spec.BLOCK_X0 == retention.BLOCK_SPINDLE_END
    assert (spec.BLOCK_X1, spec.BLOCK_WIDTH) == (20.0, 40.0)
    assert spec.BORE_X == trammel.PIN_OFFSET
    assert spec.BORE_DEPTH == trammel.BEARING_RECESS + trammel.BEARING_WIDTH
    assert spec.SHOULDER == trammel.BEARING_SHOULDER
    assert 2.0 * spec.BORE_DEPTH + spec.SHOULDER == spec.BLOCK_HEIGHT
    assert (2.0 * spec.BOLT_X, 2.0 * spec.BOLT_Y) == trammel.CARRIAGE_BOLT_SPAN
    assert len(set(spec.BOLT_POINTS)) == 4


def test_bearing_seat_is_n6_with_its_matched_fit_callout() -> None:
    seat = _features()["top_bearing_seat"]
    assert seat["dia"] == [29.976, 29.989]
    assert _features()["bottom_bearing_seat"]["dia"] == seat["dia"]
    assert (spec.INTERFERENCE_MIN, spec.INTERFERENCE_MAX) == (0.002, 0.024)
    assert seat["note"] == ("0.002-0.024 DIAMETRAL INTERFERENCE ON 6200-2RS OUTER RACE")
    assert spec.CALLOUTS_BELOW["BoreDia"] == spec.BORE_CALLOUT
    assert spec.CALLOUTS_ABOVE["BoreDia"] == "2X"
    bands = model_toleranced_dimensions(part)
    assert bands[("TopBoreProfile", "BoreDia")] == "*deviations(BORE_BAND)"
    for index in (1, 2):
        assert bands[("CAP_REGISTER_PROFILE", f"CapRegister{index}Dia")] == (
            "*deviations(CAP_REGISTER_DIA_BAND)"
        )


def test_web_hole_keeps_the_abutment_and_clears_a_puller() -> None:
    hole = _features()["shoulder_hole"]
    # Within SKF's Da max for the 6200-2RSH at its largest (the outer races
    # keep their abutment), past the inner races' 15.07 shoulder at its
    # smallest (review r6).
    assert spec.BEARING_DA_MAX == 25.8
    assert hole["dia"] == [24.2, 25.8]
    assert hole["dia"][1] <= spec.BEARING_DA_MAX
    assert hole["dia"][0] > spec.BEARING_INNER_SHOULDER_D2
    assert hole["thru"] is True
    # The web between the races, thinnest block and deepest seats, is the
    # room behind the first inner race: over the TMIC C10-12 collet's 3 mm.
    assert math.isclose(spec.PULLER_GAP_MIN, 23.49 - 2 * 10.13, abs_tol=1e-9)
    assert spec.PULLER_GAP_MIN >= spec.PULLER_SPACE_MIN == 3.0
    assert spec.DRAWING_PRECISION_BY_NAME["BlockHeight"] == 2
    # Review r8: the web's minimum stands once on each seat depth (the
    # 3-place sizes that set it), named as the web the Ø25 goes through;
    # the 24.00 is a general size and carries no row.
    assert "BlockHeight" not in spec.CALLOUTS_BELOW
    assert "BlockHeight" not in spec.CALLOUTS_ABOVE
    # Review r12: the three places stay (at two the web could drop to 2.47,
    # under the puller's 3.0), and the rows say what the puller needs.
    for name in ("TopBoreDepth", "BottomBoreDepth"):
        assert spec.CALLOUTS_BELOW[name] == "SETS WEB\n3.23 MIN\nPULLER\nNEEDS 3.0"
        assert spec.CALLOUTS_BELOW[name].endswith(f"NEEDS {spec.PULLER_SPACE_MIN:.1f}")
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 3
    assert _features()["top_bearing_seat"]["depth"] == [9.87, 10.13]


def test_top_seat_is_positioned_to_the_bottom_seat_datum() -> None:
    # Review r8: the seats are bored from opposite faces; datum A on the
    # bottom seat and a Ø0.02 position frame on the top one tie them.
    features = _features()
    top = features["top_bearing_seat"]
    assert "coaxiality_dia" in top["requirements"]
    assert top["coaxiality_dia"] == spec.SEAT_POSITION_DIA == 0.02
    assert top["coaxial_to"] == "bottom_bearing_seat"
    assert top["position_datums"] == [spec.SEAT_DATUM] == ["A"]
    assert "coaxiality_dia" not in features["bottom_bearing_seat"]
    manifest = export_features.requirement_manifest(STEM)
    assert manifest["datums"]["A"]["feature"] == "bottom_bearing_seat"
    assert spec.GEOMETRIC_TOLERANCES_MM == {"top seat position to bottom seat": "0.02"}
    # Half the zone over the 13 between the bearings' centres: 2.6 arcmin,
    # inside a deep-groove bearing's 2..10.
    assert spec.SEAT_SPAN == 13.0
    assert math.isclose(spec.SEAT_TILT_ARCMIN, 2.64, abs_tol=0.005)
    assert spec.SEAT_TILT_ARCMIN <= spec.BEARING_MISALIGNMENT_MAX_ARCMIN


def test_walls_hold_rule_17_from_the_spec_values() -> None:
    # The TL-22 argument, recomputed from the calculator's values.
    r = trammel.BEARING_OD / 2.0
    near = math.hypot(trammel.PIN_OFFSET + spec.BOLT_X, spec.BOLT_Y)
    assert math.isclose(near, 23.02, abs_tol=0.005)
    nominal = {
        "bore to counterbore": near - r - spec.CBORE_DIA / 2.0,
        "bore to hole": near - r - spec.HOLE_DIA / 2.0,
        "counterbore to block side": spec.BLOCK_WIDTH / 2.0
        - spec.BOLT_Y
        - spec.CBORE_DIA / 2.0,
        "counterbore to +X end": spec.BLOCK_X1 - spec.BOLT_X - spec.CBORE_DIA / 2.0,
        "bore to -X end": trammel.PIN_OFFSET - r - spec.BLOCK_X0,
    }
    assert {name: spec.WALLS_MM[name] for name in nominal} == nominal
    assert min(nominal.values()) >= 2.0
    assert math.isclose(nominal["bore to counterbore"], 4.02, abs_tol=0.005)
    assert math.isclose(nominal["bore to hole"], 5.77, abs_tol=0.005)
    # At the printed bands every wall keeps the 1.5 floor and the shoulder
    # web, the puller gap, 23.49 - 2 x 10.13. Only the side counterbores'
    # two pinch walls fall short (stated at the side callout).
    assert min(spec.WORST_WALLS.values()) >= spec.WALL_FLOOR
    assert math.isclose(spec.WORST_WALLS["bearing shoulder"], 3.23, abs_tol=0.005)
    assert set(spec.RULE_20_SHORTFALLS) == {
        "side counterbore to side counterbore",
        "side counterbore to carriage hole",
        "M4 engagement in carriage",
    }
    # The carriage screws' engagement (review r5): the vendor's 5 deep thread.
    assert spec.RULE_20_SHORTFALLS["M4 engagement in carriage"] == 3.85
    # The 70 and 40 hold the counterbores' end and side walls at two places
    # (1.81 at one, under the target), and say so (review r6); the 70, a
    # horizontal dimension, carries it in one row over its value (review r7).
    for name, wall in (
        ("BlockLength", "counterbore to +X end"),
        ("BlockWidth", "counterbore to block side"),
    ):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 2
        assert math.isclose(spec.WORST_WALLS[wall], 2.105, abs_tol=1e-6)
    assert spec.CALLOUTS_BELOW["BlockWidth"] == "SETS C'BORE\nWALL 2.10 MIN"


def test_horizontal_dimensions_keep_their_rows_off_their_lines() -> None:
    # Review r7: a horizontal dimension's line runs along its last row, so
    # B-B's floor height (rows wider than its 15.6 span) carries its row
    # over the value. Close-c4-r5: the 70's row stands under its value, on
    # its own line (over it, it read as the 63.000's).
    assert "CboreFloor" in spec.CALLOUTS_ABOVE
    assert "CboreFloor" not in spec.CALLOUTS_BELOW
    assert "BlockLength" in spec.CALLOUTS_BELOW
    assert "BlockLength" not in spec.CALLOUTS_ABOVE
    # The 70 stands on its own tier, under the 63.000's, with clear space
    # over its two rows (3.5 model mm between the positions = 7 mm sheet
    # more than its value and row).
    keep = drawing.PLAN_KEEP
    assert keep["BlockLength"][1] <= keep["HoleColumn2X"][1] - 6.0


def test_side_screw_walls_at_worst_case() -> None:
    worst = spec.WORST_WALLS
    # 10 - 2 x 0.13 - (7.94 + 0.13): the two counterbores at .XXX.
    assert math.isclose(
        worst["side counterbore to side counterbore"], 1.67, abs_tol=1e-9
    )
    # Counterbore corner (59.165, 34.96) to the Ø4.6 carriage hole at
    # (62.87, 33.13), stations from the -X end and -Y side.
    expected = math.hypot(62.87 - 55.13 - 4.035, 39.49 - 4.53 - 33.13) - 2.3
    assert math.isclose(
        worst["side counterbore to carriage hole"], expected, abs_tol=1e-9
    )
    assert math.isclose(
        worst["side hole to carriage hole"], 7.74 - 2.539 - 2.3, abs_tol=1e-9
    )
    # The carriage counterbore's floor prints from the bottom face (15.6 at
    # .XXX), so its lowest edge is 15.47 over the side holes' highest row.
    for name in (
        "side counterbore to carriage counterbore",
        "side hole to carriage counterbore",
        "side counterbore to bottom face",
        "side counterbore to top face",
        "side hole to bore",
    ):
        assert worst[name] >= spec.WALL_TARGET, name
    # 23.49 - 9.13 - 4.035 on the 24 mm block.
    assert math.isclose(worst["side counterbore to top face"], 10.325, abs_tol=1e-9)
    side_hole = _features()["side_screw_hole_1"]
    assert side_hole["height_from"] == "bottom_face"
    # RV-05: the owner accepted the three-place counterbores that hold the
    # side walls under the target.
    exceptions = {
        e.id: e
        for e in load_exceptions(
            CAD_ROOT / "config", "ch_rocker_arm_tl_oblique_pivot_block", "part"
        )
    }
    accepted = exceptions["RV-05"]
    assert accepted.kind == "accept"
    assert "7.940" in accepted.where and "4.400" in accepted.where
    for name in (
        "side counterbore to side counterbore",
        "side counterbore to carriage hole",
    ):
        assert f"{worst[name]:.2f} min" in accepted.finding, name


def test_side_view_is_a_named_removed_view_with_a_point_reference() -> None:
    # Review c4r3: out of projection, so lettered on the plan's +Y edge (the
    # face it looks at) and captioned; its reference sketch holds points,
    # not the corner-to-hole construction line that printed as a diagonal.
    assert drawing.SIDE_VIEW_CAPTION == "VIEW C"
    x, y, z = drawing.SIDE_VIEW_ARROW_TIP
    assert y == spec.BLOCK_WIDTH / 2.0 and z == spec.BLOCK_HEIGHT
    assert spec.BLOCK_X0 < x < spec.BLOCK_X1
    assert drawing.SIDE_VIEW_LETTER_OFFSET[1] > 0.0
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source.split("async def _side_screw_reference", 1)[1].split(
        "\nasync def ", 1
    )[0]
    assert "add_line_chain" not in body and "_add_reference_point" in body


def test_carriage_callout_routes_right_of_the_removed_view_c_pointer() -> None:
    # Native 6dd691486 failure, sheet metres. Replaying the text-end movement
    # is an offline route regression, not proof of a rebuilt native leader.
    leader = ((0.1722, 0.2166), (0.1581, 0.2388))
    c_text = (0.1618, 0.2289, 0.1651, 0.2325)
    c_leader = ((0.1656, 0.2309), (0.1634, 0.2220))
    assert distance_to_box(leader, c_text) == 0.0
    assert segments_cross(leader, c_leader)

    old_text_xy = (0.188, 0.250)
    delta = tuple(
        new - old
        for new, old in zip(drawing.SCREW_CALLOUT_XY, old_text_xy, strict=True)
    )
    moved = (
        leader[0],  # Retain the actual counterbore landing, not a free pointer.
        tuple(value + shift for value, shift in zip(leader[1], delta, strict=True)),
    )
    assert min(point[0] for point in moved) > max(c_text[2], c_leader[0][0]) + 0.003
    assert distance_to_box(moved, c_text) >= 0.003
    assert not segments_cross(moved, c_leader)


def test_side_screws_are_tl22_owned_and_aliased_by_the_leadscrew_spec() -> None:
    assert spec.SIDE_SCREW_HOLES == ((-5.0, 9.0), (5.0, 9.0))
    assert leadscrew.PIVOT_BLOCK_HOLES == spec.SIDE_SCREW_HOLES
    assert leadscrew.PIVOT_BLOCK_HOLE_SPEC is spec.SIDE_SCREW_HOLE_SPEC
    assert leadscrew.BLOCK_SCREW_X == spec.SIDE_SCREW_X
    assert leadscrew.BLOCK_SCREW_BLOCK_Z == spec.SIDE_SCREW_Z
    assert leadscrew.BLOCK_SCREW_GRIP == spec.SIDE_UNDER_HEAD == 35.6
    hole = spec.SIDE_SCREW_HOLE_SPEC
    assert (hole.kind, hole.size, hole.fit) == ("counterbore_socket", "#8", "normal")
    assert hole.overrides_mm == {
        "HoleDiameter": 4.978,
        "CounterBoreDiameter": 7.94,
        "CounterBoreDepth": 4.40,
    }
    assert spec.SIDE_CALLOUT_PRECISION == {
        "hw-thruholedia": 2,
        "hw-cbdia": 3,
        "hw-cbdepth": 3,
    }


def test_side_screw_head_sinks_and_spacing_fits_the_float() -> None:
    assert 0.1 <= spec.SIDE_HEAD_RECESS_MIN < spec.SIDE_HEAD_RECESS_MAX < 0.4
    cbore = _features()["side_screw_hole_1_counterbore"]
    assert cbore["dia"][0] > spec.SIDE_SCREW_HEAD_DIA
    assert cbore["depth"] == [4.27, 4.53]
    assert _features()["side_screw_hole_1"]["dia"] == [4.98, 5.08]
    # TL-22's two .XXX stations take 0.26 of the pair's 0.812 float.
    assert 2.0 * 0.13 <= spec.SIDE_SCREW_FLOAT
    features = _features()
    assert sorted(
        (
            features[f"side_screw_hole_{i}"]["station_nominal"],
            features[f"side_screw_hole_{i}"]["height_nominal"],
        )
        for i in (1, 2)
    ) == sorted((x - spec.DATUM_X, z) for x, z in spec.SIDE_SCREW_HOLES)


def test_carriage_screws_seat_and_reach_the_carriage_thread() -> None:
    assert spec.CBORE_FLOOR == 15.6
    assert spec.CBORE_DEPTH == round(spec.BLOCK_HEIGHT - spec.CBORE_FLOOR, 6) == 8.4
    assert spec.UNDER_HEAD == 15.6
    assert spec.THREAD_IN_CARRIAGE == 4.4 <= spec.CARRIAGE_THREAD_DEPTH
    # The floor prints from the carriage seat at three places (+/-0.13) and
    # the M4 x 20 is ISO 4762 js15 (+/-0.42): worst-case engagement
    # 3.85..4.95 inside [0.95 D, thread depth - 0.05].
    assert spec.SCREW_LENGTH_TOL == 0.42
    assert spec.DRAWING_PRECISION_BY_NAME["CboreFloor"] == 3
    assert spec.DRAWING_VALUES["CboreFloor"] == 15.6
    assert (spec.ENGAGEMENT_MIN, spec.ENGAGEMENT_MAX) == (3.85, 4.95)
    assert spec.ENGAGEMENT_MIN >= round(0.95 * spec.SCREW_DIA, 6) == 3.8
    assert spec.ENGAGEMENT_MAX <= round(spec.CARRIAGE_THREAD_DEPTH - 0.05, 6) == 4.95
    # The vendor's 5 deep thread keeps it under rule 18's 1.5D; the callout
    # states the same worst case (shortest screw, highest floor) as a fact.
    assert spec.ENGAGEMENT_MAX < spec.ENGAGEMENT_TARGET == 6.0
    cbore = _features()["screw_hole_1_counterbore"]
    assert cbore["dia"][0] > spec.SCREW_HEAD_DIA
    assert cbore["height"] == [15.47, 15.73]
    assert cbore["precision"]["height"] == 3
    assert cbore["depth_ref"] == 8.4
    assert "depth" not in cbore
    # The shallowest counterbore (thinnest block, highest floor) sinks the head.
    assert 23.49 - 15.73 >= spec.SCREW_HEAD_HEIGHT
    assert _features()["screw_hole_1"]["dia"] == [4.5, 4.6]


def test_floor_reference_lies_in_section_b_and_is_saved_hidden() -> None:
    assert spec.REFERENCE_SKETCHES == (
        spec.CBORE_FLOOR_REFERENCE,
        spec.SIDE_SCREW_REFERENCE,
        spec.CAP_TAP_REFERENCE,
        spec.WING_AXIS_REFERENCE,
    )
    assert spec.DRAWING_PRECISION[spec.CBORE_FLOOR_REFERENCE] == {"CboreFloor": 3}
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "blank_reference_sketches(adapter, REFERENCE_SKETCHES)" in source
    assert 'base_plane="Right Plane", offset=-BOLT_X' in source
    assert "'\"BoltX\"'" in source
    # The cut runs along Y on the plane through both -X counterbores, past
    # both side faces: a full section (review r7: the partial cut's open end
    # left no outline and broke the hatch).
    assert (-spec.BOLT_X, spec.BOLT_Y) in spec.BOLT_POINTS
    assert (-spec.BOLT_X, -spec.BOLT_Y) in spec.BOLT_POINTS
    assert drawing.CUT_B_Y[0] < -spec.BLOCK_WIDTH / 2.0
    assert drawing.CUT_B_Y[1] > spec.BLOCK_WIDTH / 2.0
    assert drawing.SECTION_B_ANCHOR == (-spec.BOLT_X, 0.0, spec.BLOCK_HEIGHT / 2.0)
    # Rule 14 (review r5): the whole line stands clear of the Ø29.976 bore,
    # and so do its letters, which stand on its +X side.
    assert -spec.BOLT_X - spec.BORE_X > trammel.BEARING_OD / 2.0 + 3.0
    # Clear of the side counterbores (X -5 +/- 3.97) the plane cuts past.
    assert -spec.BOLT_X < spec.SIDE_SCREW_X[0] - spec.SIDE_CBORE_DIA / 2.0 - 2.0
    # Aligned (review r6): +Y up, so the floor text over the strip stands on
    # the reference line's (+Y) side, past the block's +Y face.
    x, y, z = drawing.SECTION_B_KEEP["CboreFloor"]
    assert x == -spec.BOLT_X and z == spec.CBORE_FLOOR / 2.0
    assert y > spec.BLOCK_WIDTH / 2.0
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "not +Y up" in source and "partial=False" in source
    assert "partial=True" not in source and "SECTION_B_BREAK" not in source


def test_carriage_screws_are_one_native_counterbore_at_the_spec_sizes() -> None:
    hole = spec.SCREW_HOLE_SPEC
    assert (hole.kind, hole.size) == ("counterbore_socket", "#8")
    assert hole.overrides_mm == {
        "HoleDiameter": spec.HOLE_DIA,
        "CounterBoreDiameter": spec.CBORE_DIA,
        "CounterBoreDepth": spec.CBORE_DEPTH,
    }
    assert part.SCREW_HOLE_SPEC is hole


def test_stations_print_from_the_minus_x_end_and_minus_y_side() -> None:
    features = _features()
    seat = features["top_bearing_seat"]
    assert seat["station_nominal"] == spec.BORE_X - spec.BLOCK_X0
    assert seat["width_nominal"] == spec.BLOCK_WIDTH / 2.0 == 20.0
    stations = sorted(
        (
            features[f"screw_hole_{i}"]["station_nominal"],
            features[f"screw_hole_{i}"]["width_nominal"],
        )
        for i in range(1, 5)
    )
    assert stations == sorted(
        (x - spec.DATUM_X, y - spec.DATUM_Y) for x, y in spec.BOLT_POINTS
    )
    assert features["screw_hole_1"]["precision"]["station"] == 3
    # Every printed station is driven from the origin knobs, not a global.
    assert set(part._STATION_DRIVES) <= set(spec.DRAWING_VALUES)
    assert set(part._STATION_DRIVES).isdisjoint(spec.MODEL_KNOBS)


@pytest.mark.parametrize("stale_readback", [False, True])
def test_cap_tap_thread_class_omission_preserves_native_rows(
    monkeypatch, stale_readback: bool
) -> None:
    import _hole_callout_thread_class as thread_class

    original = {
        5: "<NUM_INST>X <hw-threaddesc> - <hw-threadclass> <hw-thru>",
        6: "",
        7: "DRILL <MOD-DIAM><hw-diameter> <hw-thru>",
        8: "",
    }

    class NativeCallout:
        def __init__(self) -> None:
            self.rows = dict(original)
            self.writes = []

        def IsHoleCallout(self):
            return True

        def GetText(self, part):
            return self.rows[part]

        def SetText(self, part, text):
            self.writes.append((part, text))
            if not stale_readback:
                self.rows[part + 4] = text

    native = NativeCallout()
    display = object()

    def early_bound(value, interface):
        assert value is display
        assert interface == "IDisplayDimension"
        return native

    monkeypatch.setattr(thread_class, "_early_bound", early_bound)
    if stale_readback:
        with pytest.raises(RuntimeError, match="four cap receiver taps: tap callout kept"):
            drawing.omit_title_block_thread_class(display, label="four cap receiver taps")
    else:
        drawing.omit_title_block_thread_class(display, label="four cap receiver taps")
        assert native.rows[5] == "<NUM_INST>X <hw-threaddesc> <hw-thru>"
    assert native.writes == [(1, "<NUM_INST>X <hw-threaddesc> <hw-thru>")]
    assert {part: native.rows[part] for part in (6, 7, 8)} == {
        part: original[part] for part in (6, 7, 8)
    }


def test_screw_callout_puts_drill_in_the_thru_row_and_the_mate_below() -> None:
    native = {
        5: "<MOD-CBORE><HOLE-DIA-CBORE> <HOLE-DEPTH><CBORE-DEPTH>",
        6: "",
        7: "<NUM_INST>X <MOD-DIAM><HOLE-DIA> THRU ALL",
        8: "",
    }
    updated = drawing.screw_hole_callout_definitions(
        native, spec.SCREW_MATE_CALLOUT, reference_depth=True
    )
    assert updated[7] == "<NUM_INST>X DRILL <MOD-DIAM><HOLE-DIA> THRU ALL"
    # The counterbore depth prints as the floor's reference complement.
    assert updated[5] == "<MOD-CBORE><HOLE-DIA-CBORE> <HOLE-DEPTH>(<CBORE-DEPTH>)"
    assert updated[8] == spec.SCREW_MATE_CALLOUT
    with pytest.raises(RuntimeError):
        drawing.screw_hole_callout_definitions(
            {**native, 8: "TAKEN"}, "MATE", reference_depth=True
        )
    for refused in (
        # Already bracketed, no depth, or two depths.
        {**native, 5: "<MOD-CBORE><HOLE-DIA-CBORE> <HOLE-DEPTH>(<CBORE-DEPTH>)"},
        {**native, 5: "<MOD-CBORE><HOLE-DIA-CBORE>"},
        {**native, 6: "<HOLE-DEPTH><CBORE-DEPTH>"},
    ):
        with pytest.raises(RuntimeError):
            drawing.screw_hole_callout_definitions(
                refused, spec.SCREW_MATE_CALLOUT, reference_depth=True
            )
    # The side screws print their counterbore depth as a dimension.
    side = drawing.screw_hole_callout_definitions(
        native, spec.SIDE_CALLOUT_BELOW, reference_depth=False
    )
    assert side[5] == native[5]
    assert side[7] == updated[7]
    assert side[8] == spec.SIDE_CALLOUT_BELOW


def test_seat_corners_carry_one_max_radius_under_the_race_chamfer() -> None:
    assert spec.SEAT_FILLET_RADIUS < spec.BEARING_OD_CHAMFER_MIN
    assert spec.CALLOUTS_ABOVE["SeatFilletR"] == "2X"
    assert "SeatFilletR" in drawing.SECTION_A_KEEP
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '_max_limit(adapter, "SeatFillets", "SeatFilletR")' in source


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    config = _config.parts("ch-rocker-arm-tl-oblique-pivot-block")
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", config["number"])
    assert config["number"] == "MHA-CH-06-TL-22"
    assert config["quantity"] == 2


def test_sheet_carries_no_notes() -> None:
    assert spec.DRAWING_NOTES == ""
    assert spec.SURFACE_FINISHES == ()


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (name, requirement)
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement)
            checked += 1
    assert checked


def test_integral_wing_retains_the_original_tail_and_interface_holes() -> None:
    assert spec.WING_LENGTH == spec.WING_X1 - spec.BLOCK_X0
    assert spec.WING_X1 == spec.BORE_X + spec.WING_AXIS_REACH
    assert spec.WING_AXIS_REACH == retention.BLOCK_WING_AXIS_REACH
    assert spec.WING_WIDTH == 2.0 * retention.BLOCK_WING_HALF_WIDTH
    assert spec.SIDE_UNDER_HEAD == 35.6
    assert spec.BORE_X == -32.0
    assert spec.BOLT_POINTS == ((-13.0, -13.0), (-13.0, 13.0), (13.0, -13.0), (13.0, 13.0))
    assert part.V_BLOCK == pytest.approx((
        spec.BLOCK_LENGTH * spec.BLOCK_WIDTH
        + spec.WING_LENGTH * (spec.WING_WIDTH - spec.BLOCK_WIDTH)
    ) * spec.BLOCK_HEIGHT, rel=1e-12, abs=1e-9)
    assert spec.BEARING_AXIS_NAME == "BearingAxis"


def test_wing_step_has_one_direct_manufacturing_authority() -> None:
    assert spec.WING_LENGTH == spec.BORE_STATION_X + spec.WING_AXIS_REACH
    assert "WingLength" not in spec.DRAWING_VALUES
    assert "WingLength" not in spec.MODEL_KNOBS
    assert "WingLength" not in spec.DRAWING_PRECISION_BY_NAME
    assert spec.DRAWING_VALUES["WingAxisReach"] == spec.WING_AXIS_REACH
    assert spec.DRAWING_PRECISION[spec.WING_AXIS_REFERENCE] == {
        "WingAxisReach": spec.WING_AXIS_REACH_PLACES,
        "WingHalfWidth": spec.WING_HALF_WIDTH_PLACES,
    }
    assert "WingAxisReach" in drawing.CAPTURE_KEEP
    features = _features()
    assert "length" not in features["capture_wing"]
    step = features["capture_wing_step"]
    band = printed_band_mm(spec.WING_AXIS_REACH_PLACES)
    assert step["station"] == pytest.approx([
        spec.WING_AXIS_REACH - band, spec.WING_AXIS_REACH + band,
    ])
    assert step["station_nominal"] == spec.WING_AXIS_REACH
    assert step["precision"] == {"station": spec.WING_AXIS_REACH_PLACES}
    assert "BEARING AXIS" in step["note"]
    selector, = export_features.feature_selectors(STEM)["capture_wing_step"]
    assert isinstance(selector, PlanarFace)
    assert selector.normal == (1.0, 0.0, 0.0)
    assert selector.offset_mm == spec.WING_X1


def test_wing_reference_is_associated_to_the_actual_profiles(monkeypatch) -> None:
    native = SimpleNamespace(DrivenState=2)
    display = SimpleNamespace(GetDimension2=lambda _index: native, ShowParenthesis=True)
    selected = []
    registered = []
    relations = []
    authored = []
    definitions = []
    success = SimpleNamespace(is_success=True, data=None)

    def create_point(x, y, z):
        assert manager.AddToDB
        point = SimpleNamespace(x=x, y=y, z=z)
        point.Select4 = lambda append, _data: selected.append((point, append)) or True
        return point

    def register(kind, entity):
        ref = f"{kind}{len(registered)}"
        registered.append((kind, entity, ref))
        adapter._sketch_entities[ref] = entity
        return ref

    def add_dimension(x, y, z, kind, status):
        assert len(selected) == 2
        assert [append for _point, append in selected] == [False, True]
        assert kind in (11, 12) and status == 0
        authored.append((x, y, z))
        return display, 0

    async def create_sketch(plane):
        assert plane == "Front"
        return success

    async def add_relation(first, second, relation):
        relations.append((first, second, relation))
        return success

    async def fully_defined(_adapter, label):
        assert _adapter is adapter and label == spec.WING_AXIS_REFERENCE
        assert len(relations) == 2
        definitions.append(bool(authored))
        if authored:
            assert native.DrivenState == 1

    async def exit_sketch():
        return success

    manager = SimpleNamespace(AddToDB=False, CreatePoint=create_point)
    model = SimpleNamespace(
        ClearSelection2=lambda _all: selected.clear(),
        SelectionManager=SimpleNamespace(CreateSelectData=lambda: object()),
        Extension=SimpleNamespace(AddSpecificDimension=add_dimension),
    )
    adapter = SimpleNamespace(
        currentSketchManager=manager, currentModel=model, _sketch_entities={},
        _register_sketch_entity=register, create_sketch=create_sketch,
        add_sketch_constraint=add_relation, exit_sketch=exit_sketch,
    )
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "_xy_mapper", lambda *_args: lambda x, y: (x, y))
    monkeypatch.setattr(part, "ensure_fully_defined", fully_defined)
    bearing_circle, wing_step = object(), object()
    dims, points = asyncio.run(part._wing_axis_reference(adapter, bearing_circle, wing_step))
    assert [item[:2] for item in registered[:2]] == [
        ("Circle", bearing_circle), ("Line", wing_step),
    ]
    assert relations == [
        (registered[2][2], f"{registered[0][2]}.center", "coincident"),
        (registered[3][2], f"{registered[1][2]}.end", "coincident"),
    ]
    assert points == tuple(item[1] for item in registered[2:])
    assert definitions == [False, True, True]
    assert dims._rows == [("WingAxisReach", None), ("WingHalfWidth", None)]
    assert display.ShowParenthesis is False
    assert manager.AddToDB is False


def _wing_native_control(monkeypatch):
    points = (object(), object())
    case = SimpleNamespace(points=points, attached=list(reversed(points)), dangling=False)
    case.dimension = SimpleNamespace(
        SystemValue=spec.WING_AXIS_REACH / 1000.0, DrivenState=1,
        FullName=f"WingAxisReach@{spec.WING_AXIS_REFERENCE}@Block",
        Tolerance=SimpleNamespace(Type=0),
    )
    case.display = SimpleNamespace(
        ShowParenthesis=False, GetDimension2=lambda _index: case.dimension,
        GetAnnotation=lambda: case.annotation, GetText=lambda index: case.text[index],
    )
    case.text = {1: "", 2: ""}
    case.annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: case.attached,
        IsDangling=lambda: case.dangling,
        GetSpecificAnnotation=lambda: case.display,
    )
    case.adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        part, "_named_dimension",
        lambda _adapter, feature, name: (case.display, case.dimension)
        if (feature, name) == (spec.WING_AXIS_REFERENCE, "WingAxisReach") else None,
    )
    monkeypatch.setattr(
        drawing, "dimension_name",
        lambda _adapter, annotation: "WingAxisReach" if annotation is case.annotation else "",
    )
    return case


@pytest.mark.parametrize("failure", [None, "value", "driver", "reference", "dangling", "wrong", "extra", "duplicate"])
def test_wing_native_readback_requires_measured_associated_authority(monkeypatch, failure) -> None:
    case = _wing_native_control(monkeypatch)
    if failure == "value":
        case.dimension.SystemValue += 0.001
    elif failure == "driver":
        case.dimension.DrivenState = 2
    elif failure == "reference":
        case.display.ShowParenthesis = True
    elif failure == "dangling":
        case.dangling = True
    elif failure == "wrong":
        case.attached[0] = object()
    elif failure == "extra":
        case.attached.append(object())
    elif failure == "duplicate":
        case.attached[:] = [case.points[0], case.points[0]]
    if failure is None:
        part._require_wing_axis_dimension(case.adapter, case.points)
    else:
        with pytest.raises(RuntimeError):
            part._require_wing_axis_dimension(case.adapter, case.points)


@pytest.mark.parametrize("failure", [None, "value", "owner", "driver", "dangling", "prefix", "suffix", "band", "missing", "duplicate"])
def test_drawing_reach_remains_ordinary_native_manufacturing_ink(monkeypatch, failure) -> None:
    case = _wing_native_control(monkeypatch)
    case.display.ShowParenthesis = True
    annotations = [case.annotation]
    if failure == "value":
        case.dimension.SystemValue += 0.001
    elif failure == "owner":
        case.dimension.FullName = "WingAxisReach@UnassociatedCopy@Block"
    elif failure == "driver":
        case.dimension.DrivenState = 2
    elif failure == "dangling":
        case.dangling = True
    elif failure == "prefix":
        case.text[1] = "("
    elif failure == "suffix":
        case.text[2] = " REF"
    elif failure == "band":
        case.dimension.Tolerance.Type = 2
    elif failure == "missing":
        annotations.clear()
    elif failure == "duplicate":
        annotations.append(case.annotation)
    if failure is None:
        drawing._wing_axis_manufacturing_dimension(case.adapter, annotations)
        assert case.display.ShowParenthesis is False
    else:
        with pytest.raises(RuntimeError):
            drawing._wing_axis_manufacturing_dimension(case.adapter, annotations)


def test_cap_receiver_taps_are_located_from_the_actual_bearing_axis() -> None:
    assert tuple(
        (x - spec.BORE_X, y) for x, y in spec.CAP_TAP_POINTS
    ) == retention.CAP_BOLT_CENTERS
    assert spec.CAP_TAP_HOLE_SPEC.kind == "tapped"
    assert spec.CAP_TAP_HOLE_SPEC.size == "5/16-18"
    assert spec.CAP_TAP_HOLE_SPEC.end == "through_all"
    assert spec.CAP_TAP_LOCATION_PLACES == 3
    assert set(spec.DRAWING_PRECISION[spec.CAP_TAP_REFERENCE].values()) == {3}
    features = _features()
    for index, (x, y) in enumerate(spec.CAP_TAP_POINTS, start=1):
        tap = features[f"cap_receiver_tap_{index}"]
        band = printed_band_mm(spec.CAP_TAP_LOCATION_PLACES)
        assert tap["station"] == pytest.approx([abs(x - spec.BORE_X) - band, abs(x - spec.BORE_X) + band])
        assert tap["width"] == pytest.approx([abs(y) - band, abs(y) + band])
        assert tap["thru"] is True
        assert tap["precision"] == {"station": 3, "width": 3}
        assert spec.CAP_TAP_HOLE_SPEC.size in tap["note"]


def test_thread_envelope_walls_reject_an_undersized_wing() -> None:
    assert min(spec.cap_receiver_walls().values()) >= spec.WALL_TARGET
    walls = spec.cap_receiver_walls()
    dx = max(abs(x) for x in retention.CAP_BOLT_X_OFFSETS)
    radius = spec.THREAD_MAJOR_MM[spec.CAP_TAP_HOLE_SPEC.size] / 2.0
    sweep = (spec.BLOCK_HEIGHT + printed_band_mm(2)) * math.tan(
        math.radians(spec.GENERAL_ANGULAR_BAND_DEGREES)
    )
    assert walls["cap thread to wing step"] == pytest.approx(
        spec.WING_AXIS_REACH - printed_band_mm(spec.WING_AXIS_REACH_PLACES)
        - dx - printed_band_mm(spec.CAP_TAP_LOCATION_PLACES) - radius - sweep
    )
    assert min(spec.cap_receiver_walls(wing_width=56.0).values()) < spec.WALL_FLOOR
    too_short = spec.WING_AXIS_REACH - walls["cap thread to wing step"] + spec.WALL_FLOOR - 0.01
    assert min(spec.cap_receiver_walls(wing_axis_reach=too_short).values()) < spec.WALL_FLOOR
    mouth = spec.cap_receiver_walls(depth=0.0)
    sweep = spec.BLOCK_HEIGHT * math.tan(
        math.radians(spec.GENERAL_ANGULAR_BAND_DEGREES)
    )
    for wall, minimum in spec.cap_receiver_walls().items():
        assert mouth[wall] - minimum == pytest.approx(sweep)


def test_widened_wing_still_fits_the_declared_flat_bar_without_height_growth() -> None:
    config = _config.parts("ch-rocker-arm-tl-oblique-pivot-block")
    assert "1 x 3 in" in config["material_specification"]
    assert spec.WING_WIDTH + 2.0 * printed_band_mm(spec.WING_HALF_WIDTH_PLACES) < 3.0 * trammel.INCH
    assert spec.BLOCK_HEIGHT + printed_band_mm(2) < trammel.INCH
    assert spec.BLOCK_HEIGHT == trammel.PIVOT_BLOCK_HEIGHT
    assert spec.BLOCK_WIDTH == 40.0


def test_register_receivers_use_the_shared_bearing_relative_contract() -> None:
    assert tuple(
        (x - spec.BORE_X, y) for x, y in spec.REGISTER_POINTS
    ) == retention.CAP_REGISTER_CENTERS
    assert spec.REGISTER_DIA == retention.BLOCK_REGISTER_DIAMETER
    assert spec.REGISTER_DIA_BAND == retention.BLOCK_REGISTER_DIAMETER_BAND
    assert spec.REGISTER_DEPTH == retention.BLOCK_REGISTER_DEPTH
    assert spec.REGISTER_DEPTH_PLACES == retention.BLOCK_REGISTER_DEPTH_PLACES
    assert spec.REGISTER_LOCATION_PLACES == retention.CAP_REGISTER_LOCATION_PLACES
    assert set(spec.DRAWING_PRECISION[spec.CAP_REGISTER_PROFILE]) == set(
        drawing.REGISTER_KEEP
    )
    for name in (
        "CapRegisterLeftX", "CapRegisterRightX",
        "CapRegisterLowerY", "CapRegisterUpperY",
    ):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == spec.REGISTER_LOCATION_PLACES
    assert spec.DRAWING_VALUES["CapRegisterDepth"] == spec.REGISTER_DEPTH
    assert spec.DRAWING_PRECISION_BY_NAME["CapRegisterDepth"] == spec.REGISTER_DEPTH_PLACES


def test_register_recesses_bind_cylinders_and_actual_flat_floors() -> None:
    features = _features()
    selectors = export_features.feature_selectors(STEM)
    for index, (x, y) in enumerate(spec.REGISTER_POINTS, start=1):
        name = f"cap_register_recess_{index}"
        recess = features[name]
        assert recess["at"] == [x, y, spec.BLOCK_HEIGHT]
        assert recess["axis"] == [0.0, 0.0, -1.0]
        dx = abs(x - spec.BORE_X)
        band = printed_band_mm(spec.REGISTER_LOCATION_PLACES)
        assert recess["station"] == pytest.approx([dx - band, dx + band])
        assert recess["width"] == pytest.approx([23.87, 24.13])
        assert recess["dia"] == pytest.approx([7.20, 7.30])
        assert recess["depth"] == pytest.approx([1.87, 2.13])
        assert recess["thru"] is False
        assert set(recess["requirements"]) == {"station", "width", "dia", "depth", "note"}
        assert recess["precision"] == {
            "station": spec.REGISTER_LOCATION_PLACES,
            "width": spec.REGISTER_LOCATION_PLACES,
            "dia": 2,
            "depth": spec.REGISTER_DEPTH_PLACES,
        }
        cylinder, floor = selectors[name]
        assert isinstance(cylinder, CylinderFace)
        assert (cylinder.contains_x_mm, cylinder.contains_y_mm) == (x, y)
        assert isinstance(floor, PlanarFace)
        assert floor.normal == (0.0, 0.0, 1.0)
        assert floor.offset_mm == spec.BLOCK_HEIGHT - spec.REGISTER_DEPTH
        assert floor.contains_x_mm == x
        assert not {"coaxiality_dia", "position_datums", "perpendicularity"} & recess.keys()


def test_register_recipe_cuts_the_actual_cylindrical_volume() -> None:
    expected = (
        len(spec.REGISTER_POINTS) * math.pi * (spec.REGISTER_DIA / 2.0) ** 2
        * spec.REGISTER_DEPTH
    )
    assert part.V_CAP_REGISTERS == pytest.approx(expected)
    tree = ast.parse(inspect.getsource(part.build))
    cuts = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create_cut_extrude"
    ]
    receiver_cuts = [
        node for node in cuts
        if node.args
        and isinstance(node.args[0], ast.Call)
        and any(
            kw.arg == "depth" and isinstance(kw.value, ast.Name)
            and kw.value.id == "CAP_REGISTER_DEPTH"
            for kw in node.args[0].keywords
        )
    ]
    assert len(receiver_cuts) == 1
    assert {kw.arg for kw in receiver_cuts[0].args[0].keywords} == {"depth"}
    assert any(
        isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub)
        and isinstance(node.right, ast.Name) and node.right.id == "V_CAP_REGISTERS"
        for node in ast.walk(tree)
    )
    sketch = ast.parse(inspect.getsource(part._cap_register_sketch))
    assert any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "dimension_between"
        and isinstance(node.args[1], ast.Name) and node.args[1].id == "centre"
        for node in ast.walk(sketch)
    )
    assert any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_register_sketch_entity"
        and len(node.args) == 2 and isinstance(node.args[1], ast.Name)
        and node.args[1].id == "bearing_circle"
        for node in ast.walk(sketch)
    )
    assert not any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in ("anchor_point_to_origin", "_add_reference_point")
        for node in ast.walk(sketch)
    )


def test_register_material_gaps_charge_source_bands_without_tightening_body() -> None:
    margins = spec.cap_register_margins()
    assert margins == spec.CAP_REGISTER_MARGINS
    assert min(margins.values()) >= spec.WALL_TARGET
    assert margins["receiver floor to bottom face"] > 0.0
    for index in (1, 2):
        for feature in (
            "spindle end", "wing step", "wing side", "bearing pockets",
            "cap threads", "carriage holes", "nut-bracket holes",
        ):
            assert margins[f"register {index} to {feature}"] >= spec.WALL_TARGET
    for name in ("WingHalfWidth", "BlockHeight", "BoreStationX", "BoreStationY"):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 2
    shallow = spec.cap_register_margins(depth=0.0)
    assert shallow["register 1 to wing side"] > margins["register 1 to wing side"]
    location = printed_band_mm(spec.REGISTER_LOCATION_PLACES)
    radius = (spec.REGISTER_DIA + spec.REGISTER_DIA_BAND[0]) / 2.0
    deepest = spec.REGISTER_DEPTH + printed_band_mm(spec.REGISTER_DEPTH_PLACES)
    drift = deepest * math.tan(math.radians(spec.GENERAL_ANGULAR_BAND_DEGREES))
    for index, (dx, _dy) in enumerate(spec.CAP_REGISTER_CENTERS, start=1):
        assert margins[f"register {index} to wing step"] == pytest.approx(
            spec.WING_AXIS_REACH - printed_band_mm(spec.WING_AXIS_REACH_PLACES)
            - dx - location - radius - drift
        )
    expected_side = (
        spec.WING_WIDTH / 2.0 - printed_band_mm(spec.WING_HALF_WIDTH_PLACES)
        - abs(retention.CAP_REGISTER_CENTERS[0][1]) - location - radius - drift
    )
    assert margins["register 1 to wing side"] == pytest.approx(expected_side)
    assert margins["receiver floor to bottom face"] == pytest.approx(
        spec.BLOCK_HEIGHT - printed_band_mm(2) - deepest
        - radius * math.tan(math.radians(spec.GENERAL_ANGULAR_BAND_DEGREES))
    )


@pytest.mark.parametrize(
    "changes,key",
    [
        ({"wing_width": 58.0}, "register 1 to wing side"),
        ({"wing_axis_reach": 7.0}, "register 2 to wing step"),
        ({"diameter": 15.0}, "register 1 to cap threads"),
        ({"depth": spec.BLOCK_HEIGHT}, "receiver floor to bottom face"),
        ({"centres": ((0.0, 18.0), (5.0, 24.0))}, "register 1 to bearing pockets"),
        ({"centres": ((19.0, 13.0), (5.0, 24.0))}, "register 1 to carriage holes"),
    ],
)
def test_register_gap_checks_detect_lost_material(changes: dict, key: str) -> None:
    assert spec.cap_register_margins(**changes)[key] < spec.WALL_TARGET


def test_register_section_diametrically_cuts_only_the_dimensioned_flat_floor() -> None:
    # ENFORCE review: the native depth's floor witness rises from register 2,
    # so D-D cuts register 2; its witness then starts on the cut floor.
    start, end = drawing.REGISTER_CUT_START, drawing.REGISTER_CUT_END
    other, cut = spec.REGISTER_POINTS
    assert start[0] == end[0] == cut[0]
    assert start[1] < -spec.WING_WIDTH / 2.0
    assert end[1] > spec.WING_WIDTH / 2.0
    radius = (spec.REGISTER_DIA + spec.REGISTER_DIA_BAND[0]) / 2.0
    assert abs(other[0] - start[0]) > radius
    assert start[1] < cut[1] - radius < cut[1] + radius < end[1]
    # The shown profile remains the actual shared blind cut, not a second
    # handwritten depth or a diagonal cutting plane through both stations.
    assert spec.BLOCK_HEIGHT - spec.REGISTER_DEPTH > 0.0
    assert part.V_CAP_REGISTERS == pytest.approx(
        2.0 * math.pi * (spec.REGISTER_DIA / 2.0) ** 2 * spec.REGISTER_DEPTH
    )


@pytest.mark.parametrize("register", [(0.347, 0.117), (0.347, 0.213)])
@pytest.mark.parametrize("translation", [(0.0, 0.0), (-0.011, 0.007)])
def test_register_paper_layout_follows_the_fitted_outline_and_cut_station(
    translation, register
) -> None:
    dx, dy = translation
    outline = (0.295, 0.087, 0.355, 0.243)
    original = drawing._register_section_layout(outline, register)
    moved = drawing._register_section_layout(
        tuple(value + (dx if axis % 2 == 0 else dy) for axis, value in enumerate(outline)),
        (register[0] + dx, register[1] + dy),
    )
    for original_positions, moved_positions in zip(original[:2], moved[:2], strict=True):
        for name, point in original_positions.items():
            assert moved_positions[name] == pytest.approx((point[0] + dx, point[1] + dy))
    assert moved[2] == pytest.approx((original[2][0] + dx, original[2][1] + dy))
    line = original[0]["CapRegisterDepth"]
    text = original[1]["CapRegisterDepth"]
    assert line[0] == register[0]
    # The line stands outboard of the register (toward the nearer outline
    # end, away from the bore), so both witnesses stay short; the text shelf
    # stands on the other side, right of the outline.
    outboard = 1.0 if register[1] > (outline[1] + outline[3]) / 2.0 else -1.0
    assert 0.0 < outboard * (line[1] - register[1]) < 0.015
    assert outline[1] < line[1] < outline[3]
    assert outboard * (text[1] - register[1]) < 0.0
    assert text[0] > outline[2]
    assert original[2] == pytest.approx(((outline[0] + outline[2]) / 2.0, outline[1]))


def test_overall_height_reference_stands_clear_left_of_the_plan() -> None:
    # ENFORCE review: the 72 overall printed nowhere. Sheet 4's plan carries
    # it as a reference, picked on both wing faces, its line left of -X end.
    assert spec.BLOCK_X0 < drawing.OVERALL_HEIGHT_PICK_X < spec.BLOCK_X0 + 10.0
    assert drawing.OVERALL_HEIGHT_LINE_X <= spec.BLOCK_X0 - 7.0
    assert spec.WING_HALF_WIDTH_PLACES == spec.DRAWING_PRECISION_BY_NAME["WingHalfWidth"]


@pytest.mark.parametrize("qualifier_gap_m", [0.019446875900030136, 0.0075, 0.028])
@pytest.mark.parametrize(
    "failure,arrow_count,reason",
    [
        (None, 2, None),
        ("arrow-count", 1, "arrow_count_mismatch"),
        ("arrow-count", 3, "arrow_count_mismatch"),
        ("off-witness", 2, "arrow_witness_mismatch"),
        ("line-refuses-lane", 2, "line_origin_missed_lane"),
        ("line-origin-clamped", 2, "line_origin_missed_lane"),
        ("text-moves-line", 2, "text_move_changed_dimension_line"),
        ("offset-enable-refused", 2, "offset_text_not_enabled"),
        ("offset-resets", 2, "offset_text_not_enabled"),
        ("text-origin-clamped", 2, "text_origin_missed_shelf"),
        ("post-text-getter-fails", 2, "native_readback_failed"),
        ("text-setter-and-getter-fail", 2, "offset_text_helper_failed"),
        ("reset-setter-throws", 2, "offset_text_reset_failed"),
        ("reset-setter-and-getter-fail", 2, "offset_text_reset_failed"),
        ("line-setter-throws", 2, "line_position_setter_failed"),
        ("line-setter-and-getter-fail", 2, "line_position_setter_failed"),
        ("line-setter-and-unprintable-getter-fail", 2, "line_position_setter_failed"),
        ("serialization-fails", 2, "line_position_setter_failed"),
        ("telemetry-fails", 2, "line_position_setter_failed"),
        ("serialization-and-telemetry-fail", 2, "line_position_setter_failed"),
        ("offset-keeps-old-line", 2, "text_move_changed_dimension_line"),
        ("offset-shifts-origin-line", 2, "text_move_changed_dimension_line"),
        ("offset-enable-throws", 2, "offset_text_helper_failed"),
        ("offset-enable-and-getter-fail", 2, "offset_text_helper_failed"),
    ],
)
def test_register_depth_placement_refuses_bad_native_readbacks(
    monkeypatch, failure, arrow_count, reason, qualifier_gap_m
) -> None:
    import _drawing_dimensions as dimensions

    # 9bb native before/after: FALSE-mode arrows are below their origin; the
    # combined offset/text handoff leaves the line at the pre-text origin.
    # The first gap is the observed 19.4468759 mm; other gaps reject calibration
    # or hardcoded compensation. This does not claim an isolated toggle probe.
    position = [0.347, 0.090, 0.0371]
    tips = [
        [0.349, position[1] - qualifier_gap_m, position[2]],
        [0.345, position[1] - qualifier_gap_m, position[2]],
    ]
    if arrow_count == 1:
        tips.pop()
    elif arrow_count == 3:
        tips.append([0.347, position[1] - qualifier_gap_m, position[2]])
    if failure == "off-witness":
        tips[0][0] += 0.000002  # Two micrometres must fail the unchanged 1 µm guard.
    moves = []
    rebuilds = []
    events = []
    logs = []
    setter_error = RuntimeError("native SetPosition2 rejected text placement")
    getter_error = RuntimeError("native GetPosition became unavailable")
    reset_error = RuntimeError("native OffsetText reset failed")
    enable_error = RuntimeError("native OffsetText enable failed")
    line_error = RuntimeError("native SetPosition2 rejected line placement")
    serialization_error = ValueError("diagnostic serialization failed")
    event_error = OSError("diagnostic event failed")
    log_error = OSError("diagnostic log failed")
    native_failures = []
    reset_setter_fails = failure in ("reset-setter-throws", "reset-setter-and-getter-fail")
    line_setter_fails = failure in (
        "line-setter-throws", "line-setter-and-getter-fail",
        "line-setter-and-unprintable-getter-fail",
        "serialization-fails", "telemetry-fails", "serialization-and-telemetry-fail",
    )
    enable_setter_fails = failure in ("offset-enable-throws", "offset-enable-and-getter-fail")
    serialization_fails = failure in ("serialization-fails", "serialization-and-telemetry-fail")
    telemetry_fails = failure in ("telemetry-fails", "serialization-and-telemetry-fail")
    unavailable_origin = failure in (
        "post-text-getter-fails", "text-setter-and-getter-fail",
        "reset-setter-and-getter-fail", "line-setter-and-getter-fail",
        "line-setter-and-unprintable-getter-fail",
        "offset-enable-and-getter-fail",
    )

    class UnprintableReadbackError(RuntimeError):
        def __str__(self):
            raise ValueError("native exception message is unavailable")

    if failure == "line-setter-and-unprintable-getter-fail":
        getter_error = UnprintableReadbackError()

    class DisplayData:
        def GetArrowHeadCount(self):
            return len(tips)

        def GetArrowHeadAtIndex2(self, index):
            return (
                *tips[index], 1.0, 0.0, 0.0,
                0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0,
            )

    class DisplayDimension:
        _offset_text = False

        @property
        def OffsetText(self):
            return self._offset_text

        @OffsetText.setter
        def OffsetText(self, value):
            if not value and reset_setter_fails:
                native_failures.append("reset")
                raise reset_error
            if value and enable_setter_fails:
                native_failures.append("enable")
                raise enable_error
            if value and failure != "offset-enable-refused":
                # Model the observed combined handoff here; the native trace
                # did not isolate whether the toggle or ensuing move did it.
                if failure == "offset-shifts-origin-line":
                    position[1] += 0.000002
                if failure != "offset-keeps-old-line":
                    for tip in tips:
                        tip[1] = position[1]
            self._offset_text = bool(value) and failure != "offset-enable-refused"

        def GetDisplayData(self):
            return data

    class Annotation:
        def GetSpecificAnnotation(self):
            return display

        def GetPosition(self):
            if unavailable_origin and (native_failures or (moves and moves[-1][0])):
                raise getter_error
            return tuple(position)

        def SetPosition2(self, x, y, z):
            moves.append((display.OffsetText, (x, y, z)))
            if display.OffsetText and failure == "text-setter-and-getter-fail":
                raise setter_error
            if not display.OffsetText and line_setter_fails:
                native_failures.append("line")
                raise line_error
            if not display.OffsetText:
                if failure == "line-refuses-lane":
                    return True  # A successful setter is not placement evidence.
                dy = y - position[1]
                for tip in tips:
                    tip[1] += dy
            elif failure == "text-moves-line":
                for tip in tips:
                    tip[1] += 0.000002
            if display.OffsetText and failure == "text-origin-clamped":
                position[:] = (x - 0.004, y + 0.003, z)
            elif not display.OffsetText and failure == "line-origin-clamped":
                position[:] = (x + 0.000002, y, position[2])
            else:
                position[:] = (x, y, z if display.OffsetText else position[2])
            return True

    data, display, annotation = DisplayData(), DisplayDimension(), Annotation()
    interfaces = {
        "IAnnotation": annotation,
        "IDisplayDimension": display,
        "IDisplayData": data,
    }

    def bind(value, interface, *members):
        assert value is interfaces[interface]
        assert all(hasattr(value, member) for member in members)
        return value

    def name(_adapter, value):
        assert value is annotation
        return "CapRegisterDepth"

    def rebuild(_adapter, *, label):
        rebuilds.append(label)
        if failure == "offset-resets" and display.OffsetText and moves and moves[-1][0]:
            display.OffsetText = False

    adapter = SimpleNamespace(_attempt=lambda operation: operation())
    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(dimensions._sw_type_info, "early_bound_or_flag", bind)
    monkeypatch.setattr(drawing, "dimension_name", name)
    monkeypatch.setattr(dimensions, "dimension_name", name)
    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    monkeypatch.setattr(dimensions, "rebuild_drawing", rebuild)

    def event(name, **attributes):
        events.append((name, attributes))
        if telemetry_fails:
            raise event_error

    def log(message):
        logs.append(message)
        if telemetry_fails:
            raise log_error

    def serialize(*args, **kwargs):
        raise serialization_error

    monkeypatch.setattr(drawing._telemetry, "event", event)
    monkeypatch.setattr(drawing._telemetry, "info", log)
    if serialization_fails:
        monkeypatch.setattr(drawing, "json", SimpleNamespace(dumps=serialize))
    line_xy = (0.347, 0.105)
    text_xy = (0.385, 0.137)
    witnesses = ((0.349, 0.117), (0.345, 0.117))

    def place():
        return drawing._position_register_depth(
            adapter, [annotation],
            line_xy=line_xy,
            text_positions={"CapRegisterDepth": text_xy},
            witnesses=witnesses,
        )

    if reason is None:
        settled = place()
        for tip, expected in zip(
            sorted(tips), ((0.345, 0.105, 0.0371), (0.349, 0.105, 0.0371)), strict=True
        ):
            assert tip == pytest.approx(expected)
        assert position == pytest.approx((*text_xy, 0.0))
        assert display.OffsetText is True
        assert [offset for offset, _position in moves] == [False, True]
        placed_position = tuple(position)
        placed_tips = [tuple(tip) for tip in tips]
        placed_rebuilds = tuple(rebuilds)
        # Re-solve readbacks independently of the setters. Each late drift
        # must refuse without attempting another move, toggle or rebuild.
        for drift, expected_reason in (
            ("line", "text_move_changed_dimension_line"),
            ("witness", "arrow_witness_mismatch"),
            ("text", "text_origin_missed_shelf"),
            ("offset", "offset_text_not_enabled"),
        ):
            position[:] = placed_position
            for tip, original in zip(tips, placed_tips, strict=True):
                tip[:] = original
            display._offset_text = True
            if drift == "line":
                for tip in tips:
                    tip[1] += 0.000002
            elif drift == "witness":
                tips[0][0] += 0.000002
            elif drift == "text":
                position[0] += 0.000002
            else:
                display._offset_text = False
            with pytest.raises(RuntimeError) as raised:
                settled()
            failure_state = json.loads(str(raised.value))
            assert failure_state["stage"] == "settled"
            assert failure_state["reason"] == expected_reason
            assert moves == [(False, (*line_xy, 0.0)), (True, (*text_xy, 0.0))]
            assert tuple(rebuilds) == placed_rebuilds
        position[:] = placed_position
        for tip, original in zip(tips, placed_tips, strict=True):
            tip[:] = original
        display._offset_text = True
        settled()
        assert tuple(rebuilds) == placed_rebuilds
    else:
        with pytest.raises(RuntimeError) as raised:
            place()
        if serialization_fails:
            assert raised.value.__cause__ is line_error
            assert raised.value is not serialization_error
            assert events[-1][1]["stage"] == "line_move_exception"
            assert events[-1][1]["reason"] == reason
            assert reason in str(raised.value)
            assert "serialization_error" in str(raised.value)
            assert [offset for offset, _position in moves] == [False]
            assert moves[0][1] == pytest.approx((*line_xy, 0.0))
            assert position == pytest.approx((0.347, 0.090, 0.0371))
            assert all(tip[1] == pytest.approx(0.090 - qualifier_gap_m) for tip in tips)
            assert native_failures == ["line"]
            assert events and logs
            return
        payload = json.loads(str(raised.value))
        assert payload["reason"] == reason
        assert payload["stage"] == {
            "arrow_count_mismatch": "line_move",
            "arrow_witness_mismatch": "line_move",
            "line_origin_missed_lane": "post_line",
            "text_move_changed_dimension_line": "post_text",
            "offset_text_not_enabled": "post_text",
            "text_origin_missed_shelf": "post_text",
            "native_readback_failed": "post_text",
            "offset_text_helper_failed": "text_move_exception",
            "offset_text_reset_failed": "line_offset_reset_exception",
            "line_position_setter_failed": "line_move_exception",
        }[reason]
        assert payload["requested_line_xy_m"] == pytest.approx(line_xy)
        assert payload["requested_text_xyz_m"] == pytest.approx((*text_xy, 0.0))
        for actual, expected in zip(
            payload["expected_witnesses_xy_m"], witnesses, strict=True
        ):
            assert actual == pytest.approx(expected)
        for actual, expected in zip(
            payload["actual_arrow_tips_m"], sorted(tips), strict=True
        ):
            assert actual == pytest.approx(expected)
        assert payload["arrow_count"] == len(tips)
        assert payload["offset_text"] is display.OffsetText
        assert payload["tolerance_m"] == 1e-6
        assert payload["axis_tolerance_m"] == 1e-7
        assert payload["line_y_misses_m"] == pytest.approx(
            [tip[1] - line_xy[1] for tip in sorted(tips)]
        )
        if unavailable_origin:
            assert payload["actual_annotation_xyz_m"] is None
            assert payload["text_xy_miss_m"] is None
            assert payload["text_distance_m"] is None
            assert payload["line_origin_xy_miss_m"] is None
            assert payload["line_origin_distance_m"] is None
            assert len(payload["read_errors"]) == 1
            read_error = payload["read_errors"][0]
            assert read_error["getter"] == "IAnnotation.GetPosition"
            assert read_error["error_type"] == type(getter_error).__name__
            assert isinstance(read_error["error"], str) and read_error["error"]
            if not isinstance(getter_error, UnprintableReadbackError):
                assert read_error["error"] == str(getter_error)
        else:
            assert payload["read_errors"] == []
            assert payload["actual_annotation_xyz_m"] == pytest.approx(position)
            assert payload["text_xy_miss_m"] == pytest.approx(
                (position[0] - text_xy[0], position[1] - text_xy[1])
            )
            assert payload["text_distance_m"] == pytest.approx(
                math.dist(position[:2], text_xy)
            )
            assert payload["line_origin_xy_miss_m"] == pytest.approx(
                (position[0] - line_xy[0], position[1] - line_xy[1])
            )
            assert payload["line_origin_distance_m"] == pytest.approx(
                math.dist(position[:2], line_xy)
            )
        original = (
            reset_error if reset_setter_fails
            else line_error if line_setter_fails
            else enable_error if enable_setter_fails
            else setter_error if failure == "text-setter-and-getter-fail"
            else getter_error if failure == "post-text-getter-fails"
            else None
        )
        if original is not None:
            assert raised.value.__cause__ is original
            assert payload["cause_type"] == type(original).__name__
            assert payload["cause"] == str(original)
        if telemetry_fails:
            assert payload["telemetry_event_error"].endswith(str(event_error))
            assert payload["telemetry_log_error"].endswith(str(log_error))
        phases = [offset for offset, _position in moves]
        if failure in ("arrow-count", "off-witness"):
            assert phases == []
        elif reset_setter_fails:
            assert phases == []
            assert native_failures == ["reset"]
            assert payload["offset_text"] is False
        elif line_setter_fails:
            assert phases == [False]
            assert native_failures == ["line"]
            assert moves[0][1] == pytest.approx((*line_xy, 0.0))
            assert position == pytest.approx((0.347, 0.090, 0.0371))
            assert all(tip[1] == pytest.approx(0.090 - qualifier_gap_m) for tip in tips)
        elif enable_setter_fails:
            assert phases == [False]
            assert native_failures == ["enable"]
        elif failure == "line-refuses-lane":
            assert phases == [False]
            assert all(tip[1] == pytest.approx(0.090 - qualifier_gap_m) for tip in tips)
            assert payload["line_origin_distance_m"] == pytest.approx(0.015)
        elif failure == "line-origin-clamped":
            assert phases == [False]
            assert payload["line_origin_xy_miss_m"] == pytest.approx((0.000002, 0.0))
            assert payload["line_y_misses_m"] == pytest.approx((-qualifier_gap_m,) * 2)
        elif failure == "offset-enable-refused":
            assert phases == [False, False]
            assert payload["line_y_misses_m"] == pytest.approx((0.032 - qualifier_gap_m,) * 2)
        else:
            assert phases == [False, True]
            if failure == "text-moves-line":
                assert position == pytest.approx((*text_xy, 0.0))
                assert all(tip[1] == pytest.approx(0.105002) for tip in tips)
            elif failure == "text-origin-clamped":
                assert position == pytest.approx((0.381, 0.140, 0.0))
                assert payload["text_distance_m"] == pytest.approx(0.005)
                assert payload["text_xy_miss_m"] == pytest.approx((-0.004, 0.003))
                assert payload["line_y_misses_m"] == pytest.approx((0.0, 0.0))
            elif failure == "offset-resets":
                assert position == pytest.approx((*text_xy, 0.0))
                assert payload["line_y_misses_m"] == pytest.approx((0.0, 0.0))
            elif failure == "offset-keeps-old-line":
                assert position == pytest.approx((*text_xy, 0.0))
                assert payload["line_y_misses_m"] == pytest.approx((-qualifier_gap_m,) * 2)
            elif failure == "offset-shifts-origin-line":
                assert position == pytest.approx((*text_xy, 0.0))
                assert payload["line_y_misses_m"] == pytest.approx((0.000002,) * 2)

    observations = [json.loads(attributes["diagnostics_json"]) for _, attributes in events]
    assert observations[0]["stage"] == "pre_line"
    if reason is None:
        stages = [observation["stage"] for observation in observations]
        assert stages.index("pre_line") < stages.index("post_line") < stages.index("post_text")
        before_handoff = next(
            observation for observation in observations if observation["stage"] == "post_line"
        )
        assert before_handoff["offset_text"] is False
        assert before_handoff["actual_annotation_xyz_m"] == pytest.approx((*line_xy, 0.0371))
        assert before_handoff["line_origin_distance_m"] == pytest.approx(0.0)
        assert before_handoff["line_y_misses_m"] == pytest.approx((-qualifier_gap_m,) * 2)
        assert observations[-1]["actual_annotation_xyz_m"] == pytest.approx((*text_xy, 0.0))
        assert observations[-1]["line_y_misses_m"] == pytest.approx((0.0, 0.0))
        assert observations[-1]["text_distance_m"] == pytest.approx(0.0)
        assert all(tip[2] == 0.0371 for tip in observations[-1]["actual_arrow_tips_m"])
        assert moves == [(False, (*line_xy, 0.0)), (True, (*text_xy, 0.0))]
    else:
        assert observations[-1] == payload
        assert json.dumps(payload, sort_keys=True) in logs[-1]


def test_outer_overall_tier_clears_the_recorded_section_and_inner_baseline() -> None:
    # 7f008ec06 actual PDF/audit union, paper metres. This replays source
    # translations only; the main agent must prove the rebuilt native ink.
    overall = (0.1393, 0.1021, 0.1799, 0.1168)
    inner = (0.1416, 0.1182, 0.1553, 0.1217)
    old_a_outline_top = 0.111588
    scale = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]
    overall_dy = (drawing.PLAN_KEEP["BlockLength"][1] - (-55.0)) * scale / 1000.0
    section_dy = drawing.SECTION_A_CENTER[1] - 0.088
    assert overall[1] + overall_dy >= old_a_outline_top + section_dy + 0.003
    assert overall[3] + overall_dy <= inner[1] - 0.003


def test_corner_radius_route_clears_the_recorded_dimension_tiers() -> None:
    # Actual 7f008ec06 arrow/shoulder endpoint, replaying only the requested
    # view and radial-text translations; rebuilt routing remains native proof.
    scale = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1] / 1000.0
    section_dy = drawing.SECTION_A_CENTER[1] - 0.088
    x, _y, z = drawing.SECTION_A_KEEP["SeatFilletR"]
    arrow = (0.129974, 0.0849594 + section_dy)
    shoulder = (
        0.1383076 + (x - (-20.0)) * scale,
        0.1064438 + section_dy - (z - (-4.0)) * scale,
    )
    overall_y = 0.1011656 + (drawing.PLAN_KEEP["BlockLength"][1] - (-55.0)) * scale
    dimensions = [
        ((0.074125, overall_y), (0.185875, overall_y)),
        ((0.075125, 0.106 + section_dy), (0.276875, 0.106 + section_dy)),
        ((0.1398915, 0.0925 + section_dy), (0.276875, 0.0925 + section_dy)),
    ]
    assert all(not segments_cross((arrow, shoulder), line) for line in dimensions)


def test_seat_fit_stack_moves_clear_of_the_recorded_left_outline() -> None:
    # Both printed tolerance limits ended at X74.506 beside the X74.125 edge.
    scale = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]
    dx = (drawing.PLAN_KEEP["BoreDia"][0] - (spec.BLOCK_X0 - 11.5)) * scale / 1000.0
    assert 0.0745059 > 0.074125
    assert 0.0745059 + dx <= 0.074125 - 0.003
    assert 0.0392441 + dx > 0.0127 + 0.003


def test_cap_fastener_text_clears_the_recorded_height_extension() -> None:
    # OffsetText moves this entire printed qualifier, not its native line.
    old_row_bottom = 0.0881558
    extension_y = 0.088
    dy = drawing.CAPTURE_TEXT_POSITIONS["CapTapRightX"][1] - 0.090
    assert old_row_bottom - extension_y < 0.002
    assert old_row_bottom + dy - extension_y > 0.003



def test_upper_register_diameter_shoulder_sits_above_the_y_station() -> None:
    # Native 6dd691486 failure, sheet metres: the complete diameter block's
    # shoulder is 10.1 mm below its requested text anchor. Keep that block,
    # its native diameter and its source tolerance; allocate room above Y24.
    shoulder = ((0.2308, 0.2339), (0.2966, 0.2339))
    upper_y_line = ((0.2945, 0.2380), (0.2945, 0.2168))
    assert segments_cross(shoulder, upper_y_line)

    old_model_xy = (spec.BLOCK_X1 + 10.0, 27.0)
    scale = drawing.CAPTURE_SCALE[0] / drawing.CAPTURE_SCALE[1]
    delta = tuple(
        (new - old) * scale / 1000.0
        for new, old in zip(
            drawing.REGISTER_KEEP["CapRegister2Dia"][:2], old_model_xy, strict=True
        )
    )
    moved = tuple(
        tuple(value + shift for value, shift in zip(point, delta, strict=True))
        for point in shoulder
    )
    assert min(point[1] for point in moved) > max(point[1] for point in upper_y_line) + 0.003
    assert not segments_cross(moved, upper_y_line)


@pytest.mark.parametrize("failure", [None, "oversized", "rejected", "ignored"])
def test_register_section_fits_native_outline_without_rotation(monkeypatch, failure) -> None:
    position = [0.285, 0.064]
    width, height = (0.060, 0.160) if failure != "oversized" else (0.180, 0.160)
    native = SimpleNamespace(
        Position=position, Angle=0.19, ScaleDecimal=2.0,
        UpdateViewDisplayGeometry=lambda: None,
        GetOutline=lambda: (
            position[0] - width / 2.0, position[1] - height / 2.0,
            position[0] + width / 2.0, position[1] + height / 2.0,
        ),
    )
    moves = []

    def move(values, children):
        assert children is False
        moves.append(tuple(values))
        if failure == "rejected":
            return False
        if failure != "ignored":
            position[:] = values
        return True

    native.SetViewPosition = move
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    if failure is None:
        fitted = drawing._fit_register_section(object(), native)
        x0, y0, x1, y1 = drawing.REGISTER_SECTION_REGION
        outline = native.GetOutline()
        assert x0 <= outline[0] < outline[2] <= x1
        assert y0 <= outline[1] < outline[3] <= y1
        assert len(moves) == 1
        assert fitted == outline
    else:
        with pytest.raises(RuntimeError):
            drawing._fit_register_section(object(), native)
        assert len(moves) == (0 if failure == "oversized" else 1 if failure == "rejected" else 4)
    assert native.Angle == 0.19 and native.ScaleDecimal == 2.0




def test_opposed_wing_faces_use_direct_axis_location_bands() -> None:
    wing = _features()["capture_wing"]
    half_band = printed_band_mm(spec.WING_HALF_WIDTH_PLACES)
    assert wing["station"] == pytest.approx([35.49, 36.51])
    assert "width" not in wing
    assert spec.WING_WIDTH + 2.0 * half_band == pytest.approx(73.02)
    radius = spec.THREAD_MAJOR_MM[spec.CAP_TAP_HOLE_SPEC.size] / 2.0
    sweep = (spec.BLOCK_HEIGHT + printed_band_mm(2)) * math.tan(
        math.radians(spec.GENERAL_ANGULAR_BAND_DEGREES)
    )
    expected = (
        spec.WING_WIDTH / 2.0 - half_band
        - abs(retention.CAP_BOLT_Y_OFFSETS[0])
        - printed_band_mm(spec.CAP_TAP_LOCATION_PLACES) - radius - sweep
    )
    assert spec.cap_receiver_walls()["cap thread to wing side"] == pytest.approx(expected)
    assert expected >= spec.WALL_TARGET


def test_f441_lower_cap_pattern_caption_clears_the_complete_lower_y_ink() -> None:
    # Actual f441 PDF/native audit, sheet metres: all three right-X text rows,
    # lower-Y extension/dimension lines and the complete lower arrow triangle.
    boxes = (
        (0.303551, 0.108712, 0.3169624, 0.1122774),
        (0.28381, 0.1031558, 0.3360314, 0.1067211),
        (0.2875368, 0.0975995, 0.3325704, 0.1011649),
    )
    strokes = (
        ((0.1264722, 0.103), (0.3005, 0.103)),
        ((0.2995, 0.103), (0.2995, 0.1266656)),
        ((0.2995, 0.103), (0.299119, 0.106556)),
        ((0.299119, 0.106556), (0.299881, 0.106556)),
        ((0.299881, 0.106556), (0.2995, 0.103)),
        ((0.129524, 0.160), (0.3005, 0.160)),
        ((0.2995, 0.160), (0.2995, 0.1433344)),
        ((0.2995, 0.160), (0.299119, 0.156444)),
        ((0.299119, 0.156444), (0.299881, 0.156444)),
        ((0.299881, 0.156444), (0.2995, 0.160)),
    )
    assert distance_to_box(strokes[1], boxes[1]) == 0.0
    dx = drawing.CAPTURE_TEXT_POSITIONS["CapTapRightX"][0] - 0.310
    dy = drawing.CAPTURE_TEXT_POSITIONS["CapTapRightX"][1] - 0.105
    moved = [(x0 + dx, y0 + dy, x1 + dx, y1 + dy) for x0, y0, x1, y1 in boxes]
    assert min(distance_to_box(line, box) for line in strokes for box in moved) >= 0.002
    assert max(box[2] for box in moved) < 0.4191  # actual right inner border
    assert min(box[1] for box in moved) > 0.066  # title block top


def test_cf3_plan_upper_witness_uses_the_actual_row_endpoint(monkeypatch) -> None:
    # cf3's accepted 11.124150 mm gap left the witness crossing A. Keep its
    # measured X175.375 origin independent of the production endpoint choice.
    label = (
        0.188649150266125, 0.171757501372,
        0.194999150266125, 0.178107501372,
    )
    glyph = (0.188905, 0.1717465, 0.194764, 0.1779187)

    class DisplayDimension:
        def __init__(self):
            self.gaps = {0: (True, 0.001), 1: (False, 0.011124150266125)}

        def GetDimension2(self, _configuration):
            return dimension

        def SetWitnessLineGap(self, index, use_doc, gap):
            self.gaps[index] = (use_doc, gap)
            return True

        def GetWitnessLineGap(self, index, _use_doc, _gap):
            return (True, *self.gaps[index])

    dimension = SimpleNamespace(
        FullName="HoleRow1Y@TopBoreProfile@ch-rocker-arm-tl-oblique-pivot-block",
        SystemValue=0.007,
    )
    display = DisplayDimension()
    annotation = SimpleNamespace(
        GetSpecificAnnotation=lambda: display,
        IsDangling=lambda: False,
    )
    cut = SimpleNamespace(
        GetTextInfo=lambda: (
            0.188649150266125, 0.178107501372, 0.0,
            0.040, 0.178107501372, 0.0,
        ),
        GetTextFormat=lambda: SimpleNamespace(CharHeight=0.00635),
    )
    section = SimpleNamespace(GetSection=lambda: cut)

    def on_plan(point):
        return (0.155875 + 0.0015 * point[0], 0.192 + 0.0015 * point[1])

    def native_segments(_annotation):
        # The native gap is measured from the actual row, even if the caller
        # mistakenly budgets it from the block face. Do not use BOLT_X here.
        return [(
            (0.175375 + display.gaps[1][1], 0.1724999999475),
            (0.20187499987549998, 0.1724999999475),
        )]

    monkeypatch.setattr(drawing, "_early_bound", lambda value, *_args: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda *_args: "HoleRow1Y")
    monkeypatch.setattr(drawing, "dimension_segments", native_segments)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    assert distance_to_box(native_segments(annotation)[0], glyph) == 0.0

    drawing._plan_lower_row_witness(None, [annotation], section, on_plan, place=True)
    witness = native_segments(annotation)[0]
    assert witness[0][0] == pytest.approx(0.196999150266125)
    assert distance_to_box(witness, label) >= 0.002 - 1e-8
    assert distance_to_box(witness, glyph) >= 0.002
    assert 0.200875 - witness[0][0] >= 0.002
    drawing._plan_lower_row_witness(None, [annotation], section, on_plan, place=False)
    with pytest.raises(RuntimeError, match="no clear, visible"):
        drawing._lower_row_witness_gap(label, 0.175375, label[2] + 0.003)


@pytest.mark.parametrize("name", ["WingAxisReach", "CapTapLeftX", "CapTapRightX"])
@pytest.mark.parametrize("drift", ["line", "skew", "text", "offset", "arrow-count"])
def test_capture_offset_layout_refuses_late_native_drift_without_repositioning(
    monkeypatch, name, drift
) -> None:
    # These readbacks have no positioning setters. Late native re-solves
    # alter the displayed ink independently of the requested line/text lanes.
    states = {}
    annotations = []

    def on_capture(point):
        return (0.195 + 0.002 * point[0], 0.190 + 0.002 * point[1])

    class DisplayData:
        def __init__(self, state):
            self.state = state

        def GetArrowHeadCount(self):
            return len(self.state.tips)

        def GetArrowHeadAtIndex2(self, index):
            return (*self.state.tips[index], 1.0, 0.0, 0.0,
                    0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0)

    class DisplayDimension:
        def __init__(self, state):
            self.state = state

        @property
        def OffsetText(self):
            return self.state.offset

        def GetDisplayData(self):
            return DisplayData(self.state)

    class Annotation:
        def __init__(self, dimension_name, state):
            self.name = dimension_name
            self.state = state

        def GetSpecificAnnotation(self):
            return DisplayDimension(self.state)

        def GetPosition(self):
            return tuple(self.state.position)

    for dimension_name, text_xy in drawing.CAPTURE_TEXT_POSITIONS.items():
        line_x, line_y = on_capture(drawing.CAPTURE_KEEP[dimension_name])
        state = SimpleNamespace(
            position=[*text_xy, 0.0],
            tips=[[line_x - 0.010, line_y, 0.0], [line_x + 0.010, line_y, 0.0]],
            offset=True,
        )
        states[dimension_name] = state
        annotations.append(Annotation(dimension_name, state))

    def unexpected_rebuild(*_args, **_kwargs):
        pytest.fail("a settled capture check must not rebuild or reposition the drawing")

    monkeypatch.setattr(drawing, "_early_bound", lambda value, *_args: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "rebuild_drawing", unexpected_rebuild)
    drawing._assert_capture_text_layout(None, annotations, on_capture)
    state = states[name]
    if drift == "line":
        for tip in state.tips:
            tip[1] += 0.000002
    elif drift == "skew":
        # Stay inside the 1 µm lane band to isolate the 0.1 µm axis guard.
        state.tips[0][1] += 0.0000005
    elif drift == "text":
        state.position[0] += 0.000002
    elif drift == "offset":
        state.offset = False
    else:
        state.tips.pop()
    with pytest.raises(RuntimeError, match=f"{name} lost its native offset line/text layout"):
        drawing._assert_capture_text_layout(None, annotations, on_capture)


def test_f441_plan_station_columns_clear_the_complete_neighboring_text() -> None:

    # Every actual text row and BOTH edges of each native arrow are retained.
    captured = {
        "HoleRow1Y": (30.0, (0.1953924, 0.1654058, 0.2065444, 0.1689711), 0.200875, 0.162, 0.1725),
        "BoreStationY": (35.0, (0.2026963, 0.1751558, 0.2140444, 0.1787212), 0.208375, 0.162, 0.192),
        "HoleRow2Y": (40.0, (0.2089266, 0.1849058, 0.2228375, 0.1884711), 0.215875, 0.162, 0.2115),
    }
    boxes, arrows = {}, {}
    for name, (old_x, box, column, bottom, top) in captured.items():
        shift = (drawing.PLAN_KEEP[name][0] - old_x) * 0.0015
        boxes[name] = (box[0] + shift, box[1], box[2] + shift, box[3])
        x = column + shift
        outside = name == "HoleRow1Y"
        edges = []
        for y, direction in ((bottom, -1 if outside else 1), (top, 1 if outside else -1)):
            tip = (x, y)
            left = (x - 0.000381, y + direction * 0.003556)
            right = (x + 0.000381, y + direction * 0.003556)
            edges.extend(((tip, left), (left, right), (right, tip)))
        arrows[name] = edges
    for name, edges in arrows.items():
        for other, box in boxes.items():
            if name != other:
                assert min(distance_to_box(edge, box) for edge in edges) >= 0.002
