"""Offline contracts for the oblique-trammel pivot block (MHA-CH-06-TL-22)."""

from __future__ import annotations

import asyncio
import ast
import inspect
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
    assert spec.CALLOUTS_BELOW["ShoulderHoleDia"] == (
        "THRU WEB\nPULLER CLEARANCE\nBEHIND 6200\nINNER RACES"
    )
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
    assert spec.CALLOUTS_BELOW["BlockLength"] == "SETS C'BORE WALL 2.10 MIN"
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
    assert "\n" not in spec.CALLOUTS_BELOW["BlockLength"]


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
    assert spec.SIDE_WALL_CALLOUT == "SETS C'BORE WALL 1.67 MIN"
    assert spec.SIDE_CALLOUT_BELOW == (
        "MATCHES MHA-CH-06-TL-29\nSETS C'BORE WALL 1.67 MIN"
    )
    # c4 review: the row's 9.000 says which face it reads from; close-c4-r5:
    # and the mate its three places serve (rule 4), by its short number.
    assert spec.CALLOUTS_BELOW["SideScrewRowZ"] == (
        "FROM\nCARRIAGE\nSEAT FACE;\nMATCHES\nTL-29"
    )
    assert "SideScrewRowZ" in drawing.SECTION_A_KEEP
    assert "SideScrewRowZ" not in drawing.SIDE_KEEP
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
    assert "MHA-CH-06-TL-29" in features["side_screw_hole_1"]["note"]


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
    # One row (review r8: the three-row block never printed), both limits
    # (review r11: the band holds the screw off the thread's bottom too).
    assert spec.CALLOUTS_ABOVE["CboreFloor"] == (
        "SETS M4 X 20 ENGAGEMENT 3.85-4.95 IN 5.0 DEEP THREAD"
    )
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
    assert spec.WING_AXIS_REACH_PLACES == retention.BLOCK_WING_AXIS_REACH_PLACES == 3
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
        assert (kind, status) == (11, 0)
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
    assert definitions == [False, True]
    assert dims._rows == [("WingAxisReach", None)]
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
        part._require_wing_axis_reach(case.adapter, case.points)
    else:
        with pytest.raises(RuntimeError):
            part._require_wing_axis_reach(case.adapter, case.points)


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
    assert min(spec.cap_receiver_walls(wing_axis_reach=20.0).values()) < spec.WALL_FLOOR
    mouth = spec.cap_receiver_walls(depth=0.0)
    sweep = spec.BLOCK_HEIGHT * math.tan(
        math.radians(spec.GENERAL_ANGULAR_BAND_DEGREES)
    )
    for wall, minimum in spec.cap_receiver_walls().items():
        assert mouth[wall] - minimum == pytest.approx(sweep)


def test_widened_wing_still_fits_the_declared_flat_bar_without_height_growth() -> None:
    config = _config.parts("ch-rocker-arm-tl-oblique-pivot-block")
    assert "1 x 3 in" in config["material_specification"]
    assert spec.WING_WIDTH + printed_band_mm(2) < 3.0 * trammel.INCH
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
    for name in ("WingWidth", "BlockHeight", "BoreStationX", "BoreStationY"):
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
        (spec.WING_WIDTH - printed_band_mm(2)) / 2.0
        - abs(retention.CAP_REGISTER_CENTERS[0][1]) - printed_band_mm(2)
        - location - radius - drift
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


def test_register_section_passes_through_both_flat_floors() -> None:
    start, end = drawing.REGISTER_CUT_START, drawing.REGISTER_CUT_END
    dx, dy = end[0] - start[0], end[1] - start[1]
    for x, y in spec.REGISTER_POINTS:
        assert (x - start[0]) * dy - (y - start[1]) * dx == pytest.approx(0.0)
    assert start[1] < -spec.WING_WIDTH / 2.0
    assert end[1] > spec.WING_WIDTH / 2.0
    assert set(drawing.REGISTER_SECTION_KEEP) == {"CapRegisterDepth"}
    assert spec.CAP_REGISTER_PROFILE not in spec.REFERENCE_SKETCHES
