"""Offline release contracts for MHA-DT-32, the crank handle pivot screw (U33)."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_dt_crank_handle_pivot_screw as part
import dt_crank_handle_butt_cup_spec as cup
import dt_crank_handle_pivot_screw_spec as spec
import dt_crank_handle_spec as handle
import dt_crank_hub_geometry as geometry
import draw_dt_crank_handle_pivot_screw as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import THREAD_MAJOR_MM
from _surface_finish import MACHINED_UM


def test_registry_paths_and_part_name() -> None:
    registered = DRAWINGS_BY_NAME["dt_crank_handle_pivot_screw"]
    assert registered.script == Path(drawing.__file__).resolve()
    assert registered.layout is DrawingLayout.LANDSCAPE
    assert registered.source.as_posix().endswith("/sldprt/dt-crank-handle-pivot-screw.SLDPRT")
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-handle-pivot-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-handle-pivot-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-handle-pivot-screw_drawing.png")
    assert part.PART_NAME == registered.artifact_stem


def test_part_registry_row_is_the_made_screw() -> None:
    row = _config.parts("dt-crank-handle-pivot-screw")
    assert row["number"] == "MHA-DT-32"
    # The title block prints the registry title, not the slug.
    assert row["title"] == "Crank Handle Pivot Screw"
    for grade in ("1018", "12L14", "1/4 in"):
        assert grade in row["material"]
        assert grade in row["material_specification"]
    assert int(row["quantity"]) == 1
    assert row["fit_class"] == "shaft_in_bushing"
    assert row["process"] != "purchased"
    # The SLDPRT Process property comes from this row (Codex review of #921):
    # it names the thread the spec cuts.
    assert row["process"] == f"turned slotted shoulder screw; die-cut {spec.THREAD_SIZE} thread"


def test_spec_is_the_single_source_of_marked_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = [set(drawing.SIDE_KEEP), set(drawing.END_KEEP), set(drawing.DETAIL_KEEP)]
    assert set.union(*views) == marked
    for index, names in enumerate(views):
        assert all(not names & other for other in views[index + 1 :])
    # The threaded section is defined by its callout, not a Ø4.826 dimension.
    assert "ThreadDia" not in marked
    assert {"ReliefLead", "SeatEdgeBreak"} <= spec.DRAWING_DIMENSIONS["ScrewProfile"]
    # The slot width is only true-size in the head-end view.
    assert set(drawing.END_KEEP) == {"SlotWidth"}


def test_model_owns_places_and_bands() -> None:
    assert "draw_dt_crank_handle_pivot_screw.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # The running fit, the head's pocket-clearance/bearing band and the head
    # length that keeps it below the cup face print at two places.  The relief's
    # bounded seating neck and lead, seat-edge break MAX, tip chamfer MAX,
    # slot depth and thread length print at one (MHA-DT-032 r8).
    running_fit = {"ShoulderDia", "HeadDia", "HeadLength"}
    for name, places in spec.DRAWING_PRECISION_BY_NAME.items():
        assert places == (2 if name in running_fit else 1), name
    # User ruling 2026-09-29 (MHA-DT-32 review): the shoulder is turned to suit
    # the bonded handle, so its length is a reference.
    assert spec.REFERENCE_DIMENSIONS == {"OverallLength", "UnderHeadLocation"}
    # Every axial location reads from the tip (re-reviews): the under-head
    # face is located from it, not sized from the seat.
    assert "ShoulderLength" not in spec.DRAWING_PRECISION_BY_NAME
    # Shared-setter bands come from named spec constants.  The native LIMIT
    # writer for the lead has its own readback/refusal contract below.
    assert model_toleranced_dimensions(part) == {
        ("ScrewProfile", "ShoulderDia"): "*deviations(SHOULDER_DIA_BAND)",
        ("ScrewProfile", "HeadDia"): "HEAD_DIA_TOL",
        ("ScrewProfile", "HeadLength"): "HEAD_LENGTH_TOL",
        ("ScrewProfile", "ReliefDia"): "*deviations(RELIEF_DIA_BAND)",
    }
    # swTolMAX prints the nominal then "MAX", so each model value IS its limit.
    assert spec.SINGLE_LIMITS == {
        ("ScrewProfile", "TipChamfer"): (spec.TIP_CHAMFER, 6),
        ("ScrewProfile", "SeatEdgeBreak"): (spec.SEAT_EDGE_BREAK_MAX, 6),
    }
    assert "_single_limits(adapter)" in Path(part.__file__).read_text(encoding="utf-8")
    assert spec.SHOULDER_DIA == 4.00
    assert spec.SHOULDER_DIA_BAND == (-0.03, -0.08)
    assert spec.SHOULDER_LENGTH == pytest.approx(53.0)
    assert not hasattr(spec, "SHOULDER_LENGTH_TOL")
    assert spec.THREAD_LENGTH == 10.0
    assert not hasattr(spec, "THREAD_LENGTH_BAND")


def test_policy_sheet_carries_no_gdt_or_render_time_precision() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_feature_control_frame",
        "add_datum_feature",
        "set_basic_dimension",
        "set_dimension_precision",
        "SetPrecision3",
    ):
        assert helper not in source
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")


def test_geometry_matches_the_u33_ruling() -> None:
    # User ruling 2026-09-30 (ch30 eight-views-4, concept v4): the photographed
    # Ø6 head; #4-40 (user ruling 2026-09-30, local review of fbf82ad96).
    assert spec.HEAD_DIA == 6.0
    assert spec.HEAD_DIA_TOL == 0.10
    # The head retains its established cup interface.  The slot is deeper
    # at the same routine .X tolerance so the driver still seats at least
    # 0.8, while the remaining web meets the 1.5 floor (Codex P2 on #1694).
    assert spec.HEAD_LENGTH == 4.0
    assert spec.SLOT_WIDTH == 1.0
    assert spec.SLOT_DEPTH == 1.6
    assert spec.SLOT_DEPTH_TOL == geometry.GENERAL_1PL_TOL_MM
    assert spec.SLOT_WEB_MIN == pytest.approx(1.5)
    # The tip chamfer is a single MAX limit that never cuts past the thread
    # depth; the tip is filed away at assembly.
    assert spec.TIP_CHAMFER_MAX == spec.TIP_CHAMFER
    assert not hasattr(spec, "TIP_CHAMFER_MIN")
    assert spec.THREAD_SIZE == "#4-40"
    assert spec.THREAD_MODEL_DIA == THREAD_MAJOR_MM["#4-40"] == 2.845
    assert spec.THREAD_PITCH == pytest.approx(25.4 / 40.0)
    assert spec.SEAT_STATION == pytest.approx(57.0)
    assert spec.OVERALL_LENGTH == pytest.approx(67.0)
    assert spec.TIP_CHAMFER == 0.3
    # The largest tip chamfer stays within the 0.39 thread depth (17/24 H).
    assert spec.TIP_CHAMFER_MAX <= 0.61343 * 25.4 / 40.0
    assert spec.HEAD_DIA + spec.HEAD_DIA_TOL < spec.STOCK_DIA == pytest.approx(6.35)


def test_slot_printed_limits_keep_driver_seating_and_the_head_web() -> None:
    assert spec.SLOT_DEPTH_MIN == pytest.approx(spec.SLOT_DEPTH - spec.SLOT_DEPTH_TOL)
    assert spec.SLOT_DEPTH_MAX == pytest.approx(spec.SLOT_DEPTH + spec.SLOT_DEPTH_TOL)
    assert (spec.SLOT_DEPTH_MIN, spec.SLOT_DEPTH_MAX) == pytest.approx((0.8, 2.4))
    assert spec.SLOT_DEPTH_MIN >= 0.8
    assert spec.SLOT_WEB_MIN == pytest.approx(
        spec.HEAD_LENGTH - spec.HEAD_LENGTH_TOL - spec.SLOT_DEPTH_MAX
    )
    assert spec.SLOT_WEB_MIN >= 1.5
    # The rejected 1.0 nominal at the same loose band admitted only 0.2.
    assert 1.0 - spec.SLOT_DEPTH_TOL < 0.8
    # Deepening one more tenth without changing the head would miss the floor.
    assert spec.HEAD_LENGTH - spec.HEAD_LENGTH_TOL - (1.7 + spec.SLOT_DEPTH_TOL) < 1.5


def test_u33_running_fit_end_play_and_engagement() -> None:
    # Handle numbers come from its own spec, the arm thickness from the shared
    # crank interface geometry.
    assert handle.HANDLE_LENGTH == 58.0
    assert handle.PIVOT_BORE_DIA + handle.PIVOT_BORE_BAND[1] == pytest.approx(4.10)
    assert handle.PIVOT_BORE_DIA + handle.PIVOT_BORE_BAND[0] == pytest.approx(4.15)
    assert geometry.ARM_THICKNESS == 8.0

    # The fitted shoulder: the cup face on the 58.0 basic length less the 5.5
    # pocket = 52.5 of bonded handle, plus the modelled 0.5 of end play.
    assert spec.HANDLE_STACK_NOMINAL == pytest.approx(52.5)
    assert spec.END_PLAY_RANGE == (0.25, 1.00)
    assert spec.END_PLAY_NOMINAL == pytest.approx(0.5)
    # Bore 4.10..4.15 over shoulder 3.92..3.97, on diameter.
    assert (spec.SHOULDER_DIA_MIN, spec.SHOULDER_DIA_MAX) == pytest.approx((3.92, 3.97))
    assert spec.DIAMETRAL_CLEARANCE_MIN == pytest.approx(0.13)
    assert spec.DIAMETRAL_CLEARANCE_MAX == pytest.approx(0.23)
    # The threaded section is 10.0 at .X, 9.2..10.8, and always spans the 7.94
    # stock arm.
    assert (spec.THREAD_LENGTH_MIN, spec.THREAD_LENGTH_MAX) == pytest.approx((9.2, 10.8))
    assert spec.THREAD_LENGTH_MIN >= spec.ARM_STOCK_THICKNESS
    # The head retains the handle.
    assert spec.HEAD_DIA > spec.HANDLE_BORE_MAX


def test_thread_relief_sits_below_the_minor_with_a_45_degree_lead() -> None:
    # The one-place relief band preserves the prior 1.8 minimum neck while
    # keeping the largest relief under the root (Codex P2 on #1694).
    assert spec.RELIEF_DIA == 1.9
    assert spec.RELIEF_DIA_BAND == (0.0, -0.1)
    assert (spec.RELIEF_DIA_MIN, spec.RELIEF_DIA_MAX) == pytest.approx((1.8, 1.9))
    assert spec.RELIEF_DIA_MIN == pytest.approx(spec.RELIEF_DIA + spec.RELIEF_DIA_BAND[1])
    assert spec.RELIEF_DIA_MAX == pytest.approx(spec.RELIEF_DIA + spec.RELIEF_DIA_BAND[0])
    assert spec.RELIEF_DIA_CALLOUT == (
        "RELIEF BELOW #4-40 ROOT;\nNECK FOR SEATING ON MHA-DT-006"
    )
    assert drawing.RELIEF_DIA_CALLOUT is spec.RELIEF_DIA_CALLOUT
    for removed in ("RELIEF_CALLOUT", "RELIEF_STRENGTH_CALLOUT"):
        assert not hasattr(spec, removed)
        assert not hasattr(drawing, removed)
    # Under the deepest die-cut root, not just the basic one (local reviews
    # of 747487c71 and 21bb244c5): 2A PD min 0.0925 in less 0.649519 P.
    assert spec.THREAD_MINOR_2A_MIN_EST == pytest.approx(
        (0.0925 - 0.649519 / 40.0) * 25.4, abs=1e-6
    )
    assert spec.THREAD_MINOR_2A_MIN_EST == pytest.approx(1.937, abs=1e-3)
    assert spec.RELIEF_DIA_MAX <= spec.THREAD_MINOR_2A_MIN_EST
    assert spec.RELIEF_WIDTH == 2.2
    assert spec.RELIEF_LEAD == 0.3
    assert spec.RELIEF_LEAD_LIMITS == (0.2, 0.4)
    # The printed limits are the model band's (Codex P2 on #1139).
    assert spec.RELIEF_LEAD_LIMITS == pytest.approx(
        (spec.RELIEF_LEAD - spec.RELIEF_LEAD_TOL, spec.RELIEF_LEAD + spec.RELIEF_LEAD_TOL)
    )
    assert spec.RELIEF_LEAD_CALLOUT == "X 45 DEG LEAD"
    assert drawing.RELIEF_LEAD_CALLOUT is spec.RELIEF_LEAD_CALLOUT
    assert spec.RELIEF_END_STATION == pytest.approx(spec.SEAT_STATION + 2.2)
    # At or below the #4-40 external minor: the P/8-flat UN root
    # (2.845 - 1.299038 x 0.635 = Ø2.020) and the UNR-2A reference max
    # ((0.1114 - 1.226869 / 40) x 25.4 = Ø2.051).
    assert spec.THREAD_MINOR_BASIC_ROOT == pytest.approx(2.0201, abs=1e-4)
    assert spec.THREAD_MINOR_UNR_2A_MAX == pytest.approx(2.0505, abs=1e-4)
    assert spec.RELIEF_DIA_MAX <= spec.THREAD_MINOR_BASIC_ROOT
    # The lead tops out at Ø2.5 (Ø2.7 with the longest lead), inside the
    # Ø2.845 thread major, leaving a flat seat.
    assert spec.SEAT_FLAT_INNER_DIA == pytest.approx(2.5)
    assert spec.SEAT_FLAT_INNER_DIA_MAX == pytest.approx(2.7)
    assert spec.RELIEF_DIA + 2.0 * spec.RELIEF_LEAD_LIMITS[1] < spec.THREAD_MODEL_DIA
    # The seat on the arm face, from printed limits (local reviews of
    # 1f3067ef2, fbf82ad96, 21bb244c5 and aed772158): MHA-DT-06's tapped mouth
    # Ø3.1 max, out to the smallest shoulder broken 0.1 max, 3.92 - 0.2 =
    # Ø3.72, less the screw's float off axis in the 2A/2B fit, (0.0991 -
    # 0.0925) / 2 in = 0.0838: 0.226 radial.  Under the title block's 0.25 on
    # both edges there would be none.
    assert spec.SEAT_EDGE_BREAK_MAX == pytest.approx(0.1)
    assert spec.SEAT_EDGE_BREAK_CALLOUT == "X 45 DEG\nPRESERVES SEAT ON MHA-DT-006"
    assert drawing.SEAT_EDGE_BREAK_CALLOUT is spec.SEAT_EDGE_BREAK_CALLOUT
    assert spec.TAPPED_MOUTH_DIA_MAX == pytest.approx(3.1)
    assert spec.SEAT_CONTACT_INNER_DIA == pytest.approx(3.1)
    assert spec.SEAT_CONTACT_OUTER_DIA_MIN == pytest.approx(3.72)
    assert spec.THREAD_FIT_OFFSET_MAX == pytest.approx((0.0991 - 0.0925) / 2.0 * 25.4)
    assert spec.SEAT_RADIAL_MIN == pytest.approx((3.72 - 3.1) / 2.0 - 0.08382, abs=1e-4)
    assert spec.SEAT_RADIAL_MIN >= 0.2
    assert (3.92 - 0.5) - (2.845 + 0.5) < 0.1
    assert spec.SEAT_FLAT_ANNULUS_AREA == pytest.approx(math.pi / 4.0 * (16.0 - 3.1**2))
    assert spec.SEAT_FLAT_ANNULUS_AREA_MIN == pytest.approx(
        math.pi / 4.0 * (3.72**2 - 3.1**2)
    )
    # The one-piece screw goes in from the butt: nothing on the arm end of it
    # is larger than the bore it passes (local review of fbf82ad96).
    assert not hasattr(spec, "COLLAR_DIA")
    assert spec.SHOULDER_DIA_MAX < spec.HANDLE_BORE_MIN
    assert 0.0 < spec.SEAT_FLAT_ANNULUS_AREA_MIN < spec.SEAT_FLAT_ANNULUS_AREA
    assert spec.CHAMFER_CALLOUT == "X 45 DEG"
    assert drawing.CHAMFER_CALLOUT is spec.CHAMFER_CALLOUT
    # Use the smallest printed neck, not the nominal/maximum: about 65 percent
    # of the #4-40 tensile stress area (0.00604 in^2).  This is not a torque proof.
    assert spec.RELIEF_DIA_MIN >= 1.8
    assert spec.NECK_AREA == pytest.approx(math.pi / 4.0 * spec.RELIEF_DIA_MIN**2)
    assert spec.NECK_AREA == pytest.approx(math.pi / 4.0 * 1.8**2)
    assert spec.NECK_AREA < math.pi / 4.0 * spec.RELIEF_DIA**2
    assert spec.TENSILE_STRESS_AREA == pytest.approx(3.90, abs=0.01)
    assert spec.NECK_TO_STRESS_AREA == pytest.approx(0.653, abs=0.001)
    # The lead's band and printed size are model-owned, not a numeric string
    # on the relief diameter.  The relief width is routine at 2.2: at .X its
    # straight floor past the longest lead keeps 1.5 #4-40 pitches (machinist
    # review of crank-v4-16; local review of 20dac9d3f).
    toleranced = {name for _, name in model_toleranced_dimensions(part)}
    assert "ReliefWidth" not in toleranced
    assert spec.RELIEF_WIDTH_MIN == pytest.approx(1.4)
    assert spec.RELIEF_FLOOR_MIN == pytest.approx(1.4 - 0.4)
    assert spec.RELIEF_FLOOR_MIN >= 1.5 * 25.4 / 40.0
    assert spec.DRAWING_PRECISION["ScrewProfile"]["ReliefLead"] == 1
    assert spec.DRAWING_PRECISION["ScrewProfile"]["SeatEdgeBreak"] == 1


def _native_lead_limit_fixture(monkeypatch, refusal=None):
    class Tolerance:
        def __init__(self):
            self._type = 0
            self.values = (0.0, 0.0)

        @property
        def Type(self):
            return self._type

        @Type.setter
        def Type(self, value):
            if refusal != "type":
                self._type = value

        def SetValues(self, lower, upper):
            if refusal == "values":
                return False
            self.values = (
                lower + (0.0001 if refusal == "lower" else 0.0),
                upper + (0.0001 if refusal == "upper" else 0.0),
            )
            return True

        def GetMinValue(self):
            return self.values[0]

        def GetMaxValue(self):
            return self.values[1]

    class Display:
        def __init__(self):
            self.places = 0
            self.precision_calls = []

        def SetPrecision3(self, primary, dual, tolerance, alternate):
            self.precision_calls.append((primary, dual, tolerance, alternate))
            if refusal != "precision":
                self.places = tolerance

        def GetPrimaryTolPrecision2(self):
            return self.places

    tolerance = Tolerance()
    display = Display()

    class Dimension:
        Tolerance = tolerance
        SystemValue = spec.RELIEF_LEAD / 1000.0

    dimension = Dimension()
    adapter = object()
    lookups = []

    def named_dimension(actual_adapter, feature, name):
        assert actual_adapter is adapter
        lookups.append((feature, name))
        return display, dimension

    def early_bound(value, interface):
        assert value is {
            "IDimensionTolerance": tolerance,
            "IDisplayDimension": display,
        }[interface]
        return value

    monkeypatch.setattr(part, "_named_dimension", named_dimension)
    monkeypatch.setattr(part, "_early_bound", early_bound)
    return adapter, display, dimension, lookups


def test_relief_lead_limits_are_native_and_keep_the_existing_bounds(monkeypatch) -> None:
    adapter, display, dimension, lookups = _native_lead_limit_fixture(monkeypatch)
    part._relief_lead_limits(adapter)
    assert lookups == [("ScrewProfile", "ReliefLead")]
    assert dimension.Tolerance.Type == 3
    assert dimension.Tolerance.values == pytest.approx((-0.0001, 0.0001))
    assert dimension.SystemValue == pytest.approx(0.0003)
    assert display.precision_calls == [(-1, -1, 1, -1)]
    assert display.GetPrimaryTolPrecision2() == 1
    assert (
        dimension.SystemValue + dimension.Tolerance.GetMinValue()
    ) * 1000.0 == pytest.approx(0.2)
    assert (
        dimension.SystemValue + dimension.Tolerance.GetMaxValue()
    ) * 1000.0 == pytest.approx(0.4)
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_relief_lead_limits"
    ]
    assert len(calls) == 1
    assert ast.unparse(calls[0]) == "_relief_lead_limits(adapter)"


@pytest.mark.parametrize(
    ("refusal", "message"),
    [
        ("values", "LIMIT deviations were rejected"),
        ("type", "LIMIT tolerance readback changed"),
        ("lower", "LIMIT tolerance readback changed"),
        ("upper", "LIMIT tolerance readback changed"),
        ("precision", "LIMIT precision did not persist"),
    ],
)
def test_relief_lead_limits_reject_ignored_native_settings(
    monkeypatch, refusal, message
) -> None:
    adapter, _, _, lookups = _native_lead_limit_fixture(monkeypatch, refusal)
    with pytest.raises(RuntimeError, match=message):
        part._relief_lead_limits(adapter)
    assert lookups == [("ScrewProfile", "ReliefLead")]


def test_native_callouts_own_the_relief_lead_and_seat_break() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    callouts = {}
    for node in ast.walk(ast.parse(source)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "set_dimension_callouts"
        ):
            continue
        location = next(
            ast.literal_eval(keyword.value)
            for keyword in node.keywords
            if keyword.arg == "location"
        )
        assert location not in callouts
        mapping = node.args[2]
        assert isinstance(mapping, ast.Dict)
        callouts[location] = {
            ast.literal_eval(key): ast.unparse(value)
            for key, value in zip(mapping.keys, mapping.values, strict=True)
        }
    assert callouts["above"] == {"ShoulderDia": "SHOULDER_CALLOUT"}
    assert callouts["below"] == {
        "ReliefDia": "RELIEF_DIA_CALLOUT",
        "ReliefLead": "RELIEF_LEAD_CALLOUT",
        "SeatEdgeBreak": "SEAT_EDGE_BREAK_CALLOUT",
        "TipChamfer": "CHAMFER_CALLOUT",
        "HeadDia": "HEAD_DIA_CALLOUT",
        "HeadLength": "HEAD_LENGTH_CALLOUT",
        "UnderHeadLocation": "UNDER_HEAD_CALLOUT",
    }
    assert spec.HEAD_DIA_CALLOUT == "CLEARANCE IN MHA-DT-035 POCKET"
    assert spec.HEAD_LENGTH_CALLOUT == "HEAD; KEEPS TOP BELOW MHA-DT-035 FACE"
    assert drawing.HEAD_DIA_CALLOUT is spec.HEAD_DIA_CALLOUT
    assert drawing.HEAD_LENGTH_CALLOUT is spec.HEAD_LENGTH_CALLOUT
    assert spec.DRAWING_NOTES == (
        f"TIP FILED FLUSH WITH MHA-DT-006 AND STAKED AT {spec.FITTED_STEP}."
    )


def test_native_seat_break_preserves_the_functional_shoulder_length() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build("):]
    # The cylinder stops short, but the chamfer ends at the unchanged seat.
    assert "(-(SEAT_STATION - SEAT_EDGE_BREAK_MAX), SHOULDER_R)," in body
    assert "(-SEAT_STATION, SHOULDER_R - SEAT_EDGE_BREAK_MAX)," in body
    assert "(-SEAT_STATION, RELIEF_R + RELIEF_LEAD)," in body
    assert "lines = await add_line_chain(adapter, points)" in body
    assert "head_outline, shoulder_outline = lines[1], lines[3]" in body
    assert "seat_edge_break = lines[4]" in body
    assert '("SeatEdgeBreak", SEAT_EDGE_BREAK_MAX),' in body
    assert (
        '"ShoulderLength",\n'
        '            f"{shoulder_outline}.start",\n'
        '            f"{seat_edge_break}.end",\n'
        "            SHOULDER_LENGTH,"
    ) in body
    assert (
        '"SeatEdgeBreak",\n'
        '            f"{seat_edge_break}.start",\n'
        '            f"{seat_edge_break}.end",\n'
        "            SEAT_EDGE_BREAK_MAX,"
    ) in body
    assert (
        'adapter, start, end, "horizontal_distance", value, f"screw {name}"'
    ) in body
    assert 'profile.record(name, f\'"{name}"\')' in body
    assert (
        'f"{seat_edge_break}.start",\n'
        '        f"{seat_edge_break}.end",\n'
        '        "vertical_distance",\n'
        "        SEAT_EDGE_BREAK_MAX,"
    ) in body
    assert 'profile.record("SeatEdgeBreakRise", \'"SeatEdgeBreak"\')' in body
    assert 'drive_jobs += profile.apply(adapter, "ScrewProfile")' in body


@pytest.mark.parametrize("lower_deviation", [-0.2, -1.9])
def test_printed_relief_limits_reject_a_weaker_seating_neck(lower_deviation: float) -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    previous = "RELIEF_DIA_BAND = (0.0, -0.1)"
    assert source.count(previous) == 1
    probe = source.replace(previous, f"RELIEF_DIA_BAND = (0.0, {lower_deviation})")
    with pytest.raises(AssertionError, match="below the previous 1.8 minimum seating section"):
        exec(compile(probe, spec.__file__, "exec"), {"__name__": "_thin_relief_probe"})


def test_engagement_meets_the_1_5d_rule_governed_by_the_stock_arm() -> None:
    # User ruling 2026-09-30: the #4-40 screw clears the policy's 1.5D rule at
    # the worst case, so the #8-32's U33b exception stays retired.
    assert spec.ENGAGEMENT_RULE_D == 1.5
    assert not hasattr(spec, "ENGAGEMENT_EXCEPTION_FLOOR_D")
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "the #8-32's U33b exception (1.26D) stays" in source
    assert spec.ENGAGEMENT_FLOOR == pytest.approx(1.5 * 2.845)
    # The chamfer's partial threads are excluded: full thread reaches 9.2 - the
    # 0.3 MAX chamfer = 8.9 from the seat face (Codex P2 on #1138).
    assert spec.FULL_THREAD_REACH_MIN == pytest.approx(8.9)
    # Nominal: min(10.0 - 0.3, arm 8.0) - 2.2 = 5.8 of full thread, 2.04 D.
    assert spec.FULL_THREAD_NOMINAL == pytest.approx(5.8)
    assert spec.FULL_THREAD_NOMINAL_DIAMETERS == pytest.approx(5.8 / 2.845)
    # Thinnest stock 5/16-in arm (mill -0.004 in on a 1-in flat): min(8.9,
    # 7.8359 - the 0.25 exit break) - (2.2 + the .X band 0.8) = 4.59,
    # 1.61 D.  The arm governs.
    assert geometry.GENERAL_1PL_TOL_MM == pytest.approx(0.8)
    assert spec.TAP_EXIT_BREAK == pytest.approx(0.25)
    assert spec.ARM_STOCK_THICKNESS == pytest.approx(7.9375)
    assert spec.RELIEF_WIDTH_MAX == pytest.approx(3.0)
    assert spec.ARM_STOCK_THICKNESS_MIN == pytest.approx(7.8359)
    assert spec.FULL_THREAD_WORST == pytest.approx(4.5859)
    assert spec.FULL_THREAD_WORST_DIAMETERS == pytest.approx(4.5859 / 2.845, abs=1e-4)
    assert spec.ENGAGEMENT_GOVERNED_BY == "arm"
    # Arm at its printed maximum 8.8: min(8.9, 8.8 - 0.25) - 3.0 = 5.55,
    # 1.95 D; the arm still governs.
    assert spec.ARM_PRINTED_THICKNESS_MAX == pytest.approx(8.8)
    assert spec.FULL_THREAD_WORST_PRINTED_ARM == pytest.approx(5.55)
    assert spec.FULL_THREAD_WORST_PRINTED_ARM_DIAMETERS == pytest.approx(5.55 / 2.845, abs=1e-3)
    # The MHA-DT-32 review's own count: the shortest section less the widest
    # relief and 1.5 pitches of die run-in still spans the stock arm's
    # full-thread need.
    assert spec.THREAD_LENGTH_MIN - spec.RELIEF_WIDTH_MAX - 1.5 * spec.THREAD_PITCH >= (
        spec.FULL_THREAD_WORST
    )
    for engaged in (spec.FULL_THREAD_WORST, spec.FULL_THREAD_WORST_PRINTED_ARM):
        assert engaged >= spec.ENGAGEMENT_FLOOR
    # The 1.5 D rule itself is met, with no exception to record.
    assert spec.FULL_THREAD_WORST >= 1.5 * 2.845
    # User ruling 2026-09-29: the tip is filed flush at assembly.  Filing
    # removes 10.8 - 7.8359 = 2.96 at most, and even 8.9 of full thread in an
    # 8.0391 stock arm still reaches the face first.
    assert not hasattr(spec, "PROUD_INBOARD_MAX")
    assert spec.FILE_ALLOWANCE_MAX == pytest.approx(10.8 - 7.8359, abs=1e-4)
    assert spec.FILE_ALLOWANCE_MIN == pytest.approx(8.9 - 8.0391, abs=1e-4)
    assert spec.FILE_ALLOWANCE_MIN > 0.0


def test_head_bearing_acceptance_accounts_for_running_offset() -> None:
    assert spec.HEAD_BEARING_RADIAL_CONCENTRIC_MIN == pytest.approx(0.3)
    assert spec.HEAD_RUNNING_OFFSET_MAX == pytest.approx(min(0.4 / 2.0, (4.3 - 3.92) / 2.0))
    assert spec.HEAD_BEARING_RADIAL_MIN == pytest.approx(0.11)


def test_cup_wall_follows_ruling_b_without_changing_the_head_or_fit() -> None:
    # Owner ruling B on #1375 grows the cup, not any MHA-DT-32 geometry.
    assert (spec.HEAD_DIA, spec.HEAD_DIA_TOL) == (6.0, 0.10)
    assert spec.CUP_BODY_DIA == cup.BODY_DIA == 9.6
    assert spec.CUP_BODY_DIA_TOL == cup.BODY_DIA_TOL == 0.10
    assert spec.CUP_POCKET_CLEARANCE == cup.POCKET_CLEARANCE == (0.2, 0.4)
    assert spec.POCKET_MAX == pytest.approx(cup.POCKET_DIA_MAX)
    assert spec.CUP_POCKET_WALL_FLOOR_MM == cup.POCKET_WALL_FLOOR_MM == 1.5
    assert spec.CUP_POCKET_WALL_MIN == cup.POCKET_WALL_MIN
    assert spec.CUP_POCKET_WALL_MIN >= spec.CUP_POCKET_WALL_FLOOR_MM


def test_thread_callout_names_the_size_but_not_the_title_block_class() -> None:
    assert spec.THREAD_CALLOUT == "#4-40 UNC"
    assert "2A" not in spec.THREAD_CALLOUT
    assert drawing.THREAD_CALLOUT is spec.THREAD_CALLOUT


def test_running_shoulder_carries_the_only_finish_symbol() -> None:
    assert len(spec.SURFACE_FINISHES) == 1
    control = spec.SURFACE_FINISHES[0]
    assert control.key == "pivot_shoulder"
    assert control.roughness_um == MACHINED_UM
    assert control.face.diameter_mm == spec.SHOULDER_DIA
    assert (
        spec.HEAD_LENGTH < control.face.contains_z_mm < spec.SEAT_STATION
    )


def test_modelled_volume_is_the_turned_body_less_the_slot() -> None:
    head = math.pi * 3.0**2 * 4.0
    shoulder = math.pi * 2.0**2 * 53.0
    relief = math.pi * (1.9 / 2.0) ** 2 * 2.2
    thread = math.pi * (2.845 / 2.0) ** 2 * 7.8
    # Pappus: the lead's 0.3 x 0.3 corner triangle, centroid 0.95 + 0.3/3
    # out, stays; the tip chamfer's 0.3 x 0.3, centroid 1.4225 - 0.3/3 out,
    # goes.
    lead = 2.0 * math.pi * (0.95 + 0.3 / 3.0) * (0.3 * 0.3 / 2.0)
    tip = 2.0 * math.pi * (2.845 / 2.0 - 0.3 / 3.0) * (0.3 * 0.3 / 2.0)
    # Pappus: the outer seat's 0.1 x 0.1 triangle is removed in both states.
    seat_break = math.pi * 0.1**2 * (2.0 - 0.1 / 3.0)
    assert part.V_LEAD == pytest.approx(lead)
    assert part.V_BODY == pytest.approx(
        head + shoulder + relief + thread + lead - tip - seat_break
    )
    # Filed flush: 5.8 of full thread past the relief, a 0.25 edge break.
    fitted_thread = math.pi * (2.845 / 2.0) ** 2 * 5.8
    fitted_tip = 2.0 * math.pi * (2.845 / 2.0 - 0.25 / 3.0) * (0.25 * 0.25 / 2.0)
    assert part.turned_volume(8.0, 0.25) == pytest.approx(
        head + shoulder + relief + fitted_thread + lead - fitted_tip - seat_break
    )
    assert part.V_INSTALLED == pytest.approx(part.turned_volume(8.0, 0.25) - part.V_SLOT)
    # A 1.0 strip across a Ø6 circle: integrate the chord 2*sqrt(r^2 - y^2)
    # over |y| <= 0.5 independently of the closed form.
    steps = 10_000
    dy = 1.0 / steps
    chords = sum(
        2.0 * math.sqrt(9.0 - (-0.5 + (i + 0.5) * dy) ** 2) for i in range(steps)
    )
    assert part.slot_strip_area(3.0, 1.0) == pytest.approx(chords * dy, abs=1e-6)
    assert part.slot_strip_area(3.0, 1.0) < 1.0 * 6.0
    assert part.V_FINAL == pytest.approx(part.V_BODY - part.V_SLOT)


def test_side_view_stations_follow_the_model() -> None:
    scale = drawing.SHEET_SCALE[0]
    assert drawing.HEAD_FACE_X - drawing.TIP_X == pytest.approx(
        spec.OVERALL_LENGTH * scale / 1000.0
    )
    assert drawing.HEAD_FACE_X - drawing.UNDERHEAD_X == pytest.approx(
        spec.HEAD_LENGTH * scale / 1000.0
    )
    assert drawing.UNDERHEAD_X - drawing.SEAT_X == pytest.approx(
        spec.SHOULDER_LENGTH * scale / 1000.0
    )
    assert drawing.SEAT_X - drawing.RELIEF_END_X == pytest.approx(
        spec.RELIEF_WIDTH * scale / 1000.0
    )
    # Model +Z runs paper-left in *Right: tip left, head right.
    assert (
        drawing.TIP_X
        < drawing.RELIEF_END_X
        < drawing.SEAT_X
        < drawing.UNDERHEAD_X
        < drawing.HEAD_FACE_X
    )


def test_head_end_view_is_the_third_angle_right_view() -> None:
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    head_radius = spec.HEAD_DIA * drawing.SHEET_SCALE[0] / 2000.0
    head_dia_text_x = drawing.SIDE_KEEP["HeadDia"][0]
    assert drawing.HEAD_FACE_X < head_dia_text_x < drawing.END_CENTER[0] - head_radius - 0.010


def test_head_bands_name_their_reason_at_the_callout() -> None:
    # Machinist review of 04b95f481: each head band's reason at its callout,
    # one line under the value, centred on it.  At 2.75 mm a character
    # (measured on the r3 audit) the line clears the head face's extension
    # line by >= 5 mm and the head Ø's clears the end view by >= 5 mm.
    char = 0.00275
    head_radius = spec.HEAD_DIA * drawing.SHEET_SCALE[0] / 2000.0
    callouts = {
        "HeadDia": spec.HEAD_DIA_CALLOUT,
        "HeadLength": spec.HEAD_LENGTH_CALLOUT,
    }
    for name, text in callouts.items():
        assert "\n" not in text and "MHA-DT-035" in text, name
        half = len(text) * char / 2.0
        x = drawing.SIDE_KEEP[name][0]
        assert x - half - drawing.HEAD_FACE_X >= 0.005, name
    head_dia_right = drawing.HEAD_DIA_TEXT_X + len(spec.HEAD_DIA_CALLOUT) * char / 2.0
    assert drawing.END_CENTER[0] - head_radius - head_dia_right >= 0.005
    # The head Ø's value and callout stay between the head's extension lines.
    head_top = drawing.HEAD_TOP_Y
    head_bottom = 2.0 * drawing.SIDE_CENTER[1] - head_top
    value_y = drawing.SIDE_KEEP["HeadDia"][1]
    assert value_y + 0.002 + 0.002 <= head_top
    assert value_y - 0.0065 - 0.002 >= head_bottom
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for constant in ("HEAD_DIA_CALLOUT", "HEAD_LENGTH_CALLOUT", "UNDER_HEAD_CALLOUT"):
        assert f'"{constant}"' not in source
        assert f": {constant}," in source, constant


def test_fitted_shoulder_rule_rides_the_under_head_reference() -> None:
    # The to-suit rule rides its reference dimension; the seat break now
    # belongs to a model dimension in DETAIL A.  The only free note is the
    # assembly finishing instruction.
    lines = spec.UNDER_HEAD_CALLOUT.splitlines()
    assert lines[0].startswith("UNDER-HEAD FACED TO SUIT")
    assert "MHA-DT-008" in spec.UNDER_HEAD_CALLOUT
    assert spec.UNDER_HEAD_CALLOUT.endswith("PLUS 0.25-1.00")
    # 2.5 mm a character (the r3 audit boxed the block 96.5 mm wide): the
    # widest line stays between the seat-face and under-head extension lines,
    # centred on the reference's text.
    half = max(len(line) for line in lines) * 0.0025 / 2.0
    centre = drawing.SIDE_KEEP["UnderHeadLocation"][0]
    assert centre - half > drawing.SEAT_X + 0.010
    assert centre + half < drawing.FINISH_SYMBOL[0] - 0.003
    notes = spec.DRAWING_NOTES.splitlines()
    assert notes == [
        f"TIP FILED FLUSH WITH MHA-DT-006 AND STAKED AT {spec.FITTED_STEP}."
    ]
    # SOLIDWORKS prints no multi-line above-callout (the 04b95f481 sheet).
    assert "\n" not in spec.SHOULDER_CALLOUT
    assert "MHA-DT-008" in spec.SHOULDER_CALLOUT


def test_under_head_witness_lies_on_the_edge_and_prints_black() -> None:
    # Machinist review of 04b95f481: the full-length under-head line under
    # the shank read as a stray feature line.  The reference now ends on a
    # 1.0 witness ON the under-head annulus's edge, drawn in the outline's
    # black.
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert "under_head_v" not in build
    assert "add_line(-HEAD_LENGTH, -HEAD_R, -HEAD_LENGTH, -SHOULDER_R)" in build
    assert drawing.UNDER_HEAD_WITNESS_LEN == pytest.approx(1.0)
    assert drawing.REFERENCE_WITNESS_COLOR == 0
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.index("_blacken_under_head_witness(adapter, side)") < source.index(
        "await finalize_drawing("
    )


def test_sheet_placements_stay_inside_the_border() -> None:
    inner = (0.0127, 0.0127, 0.4191, 0.2667)  # ASME B landscape inner border
    title_block = (0.218, 0.065)  # x >= and y <=
    points = [
        drawing.SIDE_CENTER,
        drawing.END_CENTER,
        drawing.ISO_CENTER,
        drawing.DETAIL_CENTER,
        drawing.DETAIL_LABEL_XY,
        drawing.DETAIL_PARENT_LETTER_XY,
        drawing.NOTES_XY,
        drawing.THREAD_NOTE_XY,
        drawing.FINISH_SYMBOL,
        drawing.ISO_NOTE_XY,
        (drawing.TIP_X, drawing.SIDE_CENTER[1]),
        *drawing.SIDE_KEEP.values(),
        *drawing.END_KEEP.values(),
        *drawing.DETAIL_KEEP.values(),
    ]
    for x, y in points:
        assert inner[0] < x < inner[2] and inner[1] < y < inner[3]
        assert not (x >= title_block[0] and y <= title_block[1])
    # Picks land on the features they annotate.  The thread callout's leader
    # tip lands on the full-thread portion, never on the relief groove.
    assert drawing.THREAD_PICK[0] == drawing.THREAD_START_X
    assert drawing.THREAD_START_X - drawing.TIP_X == pytest.approx(
        spec.TIP_CHAMFER * drawing.SHEET_SCALE[0] / 1000.0
    )
    assert not drawing.RELIEF_END_X <= drawing.THREAD_PICK[0] <= drawing.SEAT_X
    assert drawing.THREAD_PICK[0] < drawing.RELIEF_END_X
    # Only the relief diameter stays in the side view.  Its native near-side
    # arrow must land on the groove floor; the actual ink is checked after
    # rebuild, not approximated by the rejected OffsetText calibration.
    assert {"ReliefWidth", "ReliefLead", "SeatEdgeBreak"}.isdisjoint(drawing.SIDE_KEEP)
    text_x, text_y = drawing.SIDE_KEEP["ReliefDia"]
    half = max(len(line) for line in spec.RELIEF_DIA_CALLOUT.splitlines()) * 0.0028 / 2.0
    assert (text_x - half) - drawing.SEAT_X >= 0.003
    shoulder_bottom = 2.0 * drawing.SIDE_CENTER[1] - drawing.SHOULDER_TOP_Y
    # The value/bilateral stack has no above-callout; its two-line reason is
    # below.  Keep 3 mm under the profile and 5 mm above the under-head block.
    assert shoulder_bottom - (text_y + 0.007) >= 0.003
    assert text_y - 0.0146 - (drawing.SIDE_KEEP["UnderHeadLocation"][1] + 0.010) >= 0.005
    # The thread-length text is left of this lower block, not underneath it.
    assert text_x - half - (drawing.SIDE_KEEP["ThreadLength"][0] + 0.0055) >= 0.003
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_drawing_leaders.set_near_side_diameter(" in source
    assert "_drawing_leaders.dimension_segments(relief_diameter)" in source
    assert "offset_dimension_text" not in source
    for obsolete in (
        "RELIEF_DIA_TEXT_XY",
        "RELIEF_DIA_TEXT_WIDTH",
        "RELIEF_DIA_TEXT_UNDERLINE_DROP",
    ):
        assert not hasattr(drawing, obsolete)
    # The thread note stands up and right of its pick, so the leader slants.
    note_x, note_y = drawing.THREAD_NOTE_XY
    assert note_x - drawing.THREAD_PICK[0] > 0.010
    assert note_y - drawing.THREAD_TOP_Y > 0.015
    # The slot value stands clear of its 3-mm-apart extension lines.
    assert drawing.END_KEEP["SlotWidth"][1] - drawing.END_CENTER[1] > 0.005
    assert (
        drawing.SIDE_KEEP["ThreadLength"][1] + 0.010
        < drawing.SIDE_KEEP["ReliefDia"][1]
        < 2.0 * drawing.SIDE_CENTER[1] - drawing.THREAD_TOP_Y  # below the thread
    )
    thread_half = spec.THREAD_MODEL_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert abs(drawing.THREAD_PICK[1] - drawing.SIDE_CENTER[1]) < thread_half
    assert drawing.SEAT_X < drawing.FINISH_PICK[0] < drawing.UNDERHEAD_X
    assert drawing.SEAT_X < drawing.CENTERLINE_PICK[0] < drawing.UNDERHEAD_X
    shoulder_dim_x = drawing.SIDE_KEEP["ShoulderDia"][0]
    assert drawing.SEAT_X < shoulder_dim_x < drawing.UNDERHEAD_X
    assert abs(drawing.CENTERLINE_PICK[0] - shoulder_dim_x) > 0.010
    assert abs(drawing.FINISH_PICK[0] - shoulder_dim_x) > 0.010


def test_relief_detail_contains_the_actual_native_dimension_endpoints() -> None:
    assert set(drawing.DETAIL_KEEP) == {"ReliefWidth", "ReliefLead", "SeatEdgeBreak"}
    assert drawing.DETAIL_REFERENCE_MM == (0.0, 0.0, drawing.DETAIL_STATION)
    assert drawing.DETAIL_STATION == pytest.approx(
        spec.SEAT_STATION + spec.RELIEF_WIDTH / 2.0
    )
    assert drawing.DETAIL_SCALE == (10.0, 1.0)
    scale = drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1]
    assert drawing.DETAIL_RADIUS == pytest.approx(
        drawing.DETAIL_RADIUS_MM * scale / 1000.0
    )
    endpoints = (
        (spec.SEAT_STATION - spec.SEAT_EDGE_BREAK_MAX, spec.SHOULDER_DIA / 2.0),
        (spec.SEAT_STATION, spec.SHOULDER_DIA / 2.0 - spec.SEAT_EDGE_BREAK_MAX),
        (spec.SEAT_STATION, spec.RELIEF_DIA / 2.0 + spec.RELIEF_LEAD),
        (spec.SEAT_STATION + spec.RELIEF_LEAD, spec.RELIEF_DIA / 2.0),
        (spec.SEAT_STATION + spec.RELIEF_WIDTH, spec.RELIEF_DIA / 2.0),
    )
    for station, radius in endpoints:
        distance = math.hypot(station - drawing.DETAIL_STATION, radius)
        assert drawing.DETAIL_RADIUS_MM - distance >= 0.2
    # The tiny seat break is genuinely enlarged to a 1 mm paper leg.
    assert spec.SEAT_EDGE_BREAK_MAX * scale >= 1.0
    assert drawing.DETAIL_PARENT_RADIUS == pytest.approx(
        drawing.DETAIL_RADIUS_MM * drawing.SHEET_SCALE[0] / 1000.0
    )
    assert drawing.DETAIL_LETTER == "A"
    assert drawing.DETAIL_VIEW_LABEL == "DETAIL A\nSCALE 10:1"


def test_relief_detail_text_and_circle_clear_the_baseline_rows_and_border() -> None:
    cx, cy = drawing.DETAIL_CENTER
    radius = drawing.DETAIL_RADIUS
    assert cx - radius > 0.0127 and cx + radius < 0.218
    assert cy - radius > 0.0127
    assert drawing.SIDE_KEEP["OverallLength"][1] - 0.005 - (cy + radius) >= 0.005
    assert drawing.DETAIL_KEEP["ReliefWidth"][1] - (
        drawing.DETAIL_KEEP["ReliefLead"][1] + 0.004
    ) >= 0.005
    assert drawing.DETAIL_KEEP["ReliefWidth"][1] == pytest.approx(
        drawing.DETAIL_KEEP["SeatEdgeBreak"][1] + 0.009
    )
    scale = drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] / 1000.0
    lead_left = cx + (drawing.DETAIL_STATION - spec.SEAT_STATION - spec.RELIEF_LEAD) * scale
    seat_right = cx + (
        drawing.DETAIL_STATION - spec.SEAT_STATION + spec.SEAT_EDGE_BREAK_MAX
    ) * scale
    lead_half = len(spec.RELIEF_LEAD_CALLOUT) * 0.0028 / 2.0
    seat_half = max(len(line) for line in spec.SEAT_EDGE_BREAK_CALLOUT.splitlines()) * 0.0028 / 2.0
    assert lead_left - (drawing.DETAIL_KEEP["ReliefLead"][0] + lead_half) >= 0.003
    assert drawing.DETAIL_KEEP["SeatEdgeBreak"][0] - seat_half - seat_right >= 0.003


def test_printed_material_fits_one_title_block_line() -> None:
    """Farm 3591da7a: the 51-character material wrapped into the DRAWN PER row.
    Gooseneck measured the MATERIAL cell at 36 characters; the long form stays
    in material_specification."""
    row = _config.parts("dt-crank-handle-pivot-screw")
    assert len(str(row["material"])) <= 36
    assert "cold-finished" in str(row["material_specification"])


def test_assembly_seats_the_shoulder_on_the_arm_and_files_the_tip_flush() -> None:
    """#831 P1 (Codex PRRT_kwDOPHDy386lqC_R): MHA-DT-32 is inserted in the drive
    train with ArmSeat on the arm's outboard face.  User ruling 2026-09-29
    (ch11 p.14): its tip is filed flush with the arm's inboard face, so the
    drive train places the INSTALLED configuration (the MHA-DT-30 precedent)."""
    import build_dt_drive_train_assembly as assembly

    assert assembly.HANDLE_SCREW_Z0 + spec.SEAT_STATION == pytest.approx(
        assembly.CRANK_ARM_Z0
    )
    assert assembly.HANDLE_SCREW_TIP_Z == pytest.approx(assembly.CRANK_ARM_ORIGIN_Z)
    assert spec.INSTALLED_THREAD_LENGTH == pytest.approx(geometry.ARM_THICKNESS)
    assert spec.INSTALLED_TIP_CHAMFER == pytest.approx(geometry.EDGE_BREAK_MAX_MM)
    assert assembly.HANDLE_SCREW_INSTALLED_CONFIG == spec.INSTALLED_CONFIG == "INSTALLED"
    source = Path(assembly.__file__).read_text(encoding="utf-8")
    assert "configuration=HANDLE_SCREW_INSTALLED_CONFIG," in source


def test_installed_configuration_is_split_from_a_finished_default() -> None:
    import build_dt_crank_handle_pivot_screw as part

    source = Path(part.__file__).read_text(encoding="utf-8")
    split = source.index("create_configuration {INSTALLED_CONFIG}")
    for edit in (
        "await apply_material(adapter, MATERIAL)",
        "author_part_pmi(adapter",
        'blank_sketch(adapter, "StationReference")',
        "apply_drawing_precision(adapter, DRAWING_PRECISION)",
    ):
        assert source.index(edit) < split, edit
    assert "assert_saved_configurations_regenerate(adapter, PART_NAME)" in source
    assert "require_material_in_every_configuration(" in source
    assert part.V_INSTALLED < part.V_FINAL
    assert _config.parts("dt-crank-handle-pivot-screw")["description"] == "CRANK HANDLE PIVOT SCREW"


def test_quarter_inch_arm_stock_fails_the_1_5d_rule(monkeypatch) -> None:
    # The arm stock governs the worst-case engagement: 1/4-in bar would leave
    # min(8.9, 6.2484 - 0.25) - 3.0 = 3.00, 1.05D, under the 1.5D rule.
    # Executed as a separate, unregistered module: reloading the real one
    # would swap its band tuples for new objects under every importer
    # (test_fit_bands tracks them by identity).
    import importlib.util
    from fractions import Fraction

    assert spec.ENGAGEMENT_RULE_D == 1.5
    monkeypatch.setattr(geometry, "ARM_STOCK_THICKNESS_IN", Fraction(1, 4))
    monkeypatch.setattr(geometry, "ARM_STOCK_THICKNESS", 0.25 * 25.4)
    monkeypatch.setattr(geometry, "ARM_STOCK_THICKNESS_MIN", 0.246 * 25.4)
    probe_spec = importlib.util.spec_from_file_location("_quarter_inch_probe", spec.__file__)
    probe = importlib.util.module_from_spec(probe_spec)
    with pytest.raises(AssertionError, match="under the 1.5D rule"):
        probe_spec.loader.exec_module(probe)
    assert probe.ARM_STOCK_THICKNESS == pytest.approx(6.35)
    assert probe.FULL_THREAD_WORST == pytest.approx(0.246 * 25.4 - 0.25 - 3.0)
    assert probe.FULL_THREAD_WORST < 1.5 * probe.THREAD_MODEL_DIA


def test_arm_interference_allowance_follows_the_thread_size() -> None:
    # _interference_contracts names the size rather than importing this spec
    # (every assembly imports it); the allowance must still be this thread's.
    import _interference_contracts as contracts
    from _hole_spec import TAP_DRILL_MM

    pair = frozenset(("dt-crank-handle-pivot-screw-1", "dt-crank-arm-1"))
    assert contracts._DRIVE_TRAIN_ALLOWED_PAIRS[pair] == pytest.approx(
        contracts._smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[spec.THREAD_SIZE], TAP_DRILL_MM[spec.THREAD_SIZE], 7.0
        )
    )


def test_worst_engagement_clears_the_novice_margin_by_geometry() -> None:
    # Main 2026-09-25: reach >= 1.25D at the worst case by geometry; the
    # #4-40 (user ruling 2026-09-30) reaches the policy's 1.5D.
    assert spec.FULL_THREAD_WORST_DIAMETERS >= 1.5
    assert spec.RELIEF_WIDTH_MAX == pytest.approx(
        spec.RELIEF_WIDTH + geometry.GENERAL_1PL_TOL_MM
    )



def test_station_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880: a reference sketch owns printed dimensions but no geometry, so the
    # part saves it hidden (no assembly instance renders it) and the drawing
    # shows it per view through _drawing_hidden_sketches to import them.
    build = Path(drawing.__file__).with_name("build_dt_crank_handle_pivot_screw.py").read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "StationReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source.replace("\r\n", "\n")
    assert "StationReference" in spec.DRAWING_DIMENSIONS


@pytest.fixture
def relief_native(monkeypatch):
    """In-memory native-shaped boundary, not a typelib/ABI compatibility proof."""
    from types import SimpleNamespace

    class Point:
        __slots__ = ("ArrayData",)

        def __init__(self, xyz):
            self.ArrayData = tuple(xyz)

        def MultiplyTransform(self, transform):
            assert transform is sketch.ModelToSketchTransform
            x, y, z = self.ArrayData
            return Point((2.0 * x + 0.03, 2.0 * y - 0.04, z))

    class Utility:
        __slots__ = ()

        def CreatePoint(self, xyz):
            return Point(xyz)

    class Sketch:
        __slots__ = ("ModelToSketchTransform",)

        def __init__(self):
            self.ModelToSketchTransform = object()

    class Center:
        __slots__ = ("X", "Y")

        def __init__(self, x, y):
            self.X, self.Y = x, y

    class Arc:
        __slots__ = ("center", "radius")

        def __init__(self, xyz, rim):
            self.center = Center(xyz[0] + manager.center_drift, xyz[1])
            self.radius = math.dist(xyz[:2], rim[:2]) + manager.radius_drift

        def GetCenterPoint2(self):
            return self.center

        def GetRadius(self):
            return self.radius

    class Manager:
        __slots__ = (
            "AddToDB", "center_drift", "radius_drift", "failure",
            "returns_none", "calls", "circle",
        )

        def __init__(self):
            self.AddToDB = False
            self.center_drift = self.radius_drift = 0.0
            self.failure = None
            self.returns_none = False
            self.calls = []
            self.circle = None

        def CreateCircle(self, x, y, z, rx, ry, rz):
            self.calls.append((self.AddToDB, (x, y, z, rx, ry, rz)))
            if self.failure is not None:
                raise self.failure
            if self.returns_none:
                return None
            self.circle = Arc((x, y, z), (rx, ry, rz))
            return self.circle

    class Note:
        __slots__ = ("text",)

        def __init__(self, text):
            self.text = text

        def GetText(self):
            return self.text

    class View:
        __slots__ = (
            "ScaleRatio", "Position", "move_ok", "crop_status", "cropped",
            "moves", "crops", "notes",
        )

        def __init__(self):
            self.ScaleRatio = drawing.DETAIL_SCALE
            self.Position = (0.08, 0.09)
            self.move_ok = self.cropped = True
            self.crop_status = drawing._CROP_NO_ERROR
            self.moves, self.crops, self.notes = [], [], []

        def GetSketch(self):
            return sketch

        def SetViewPosition(self, xy, relative):
            self.moves.append((tuple(xy), relative))
            if self.move_ok:
                self.Position = tuple(xy)
            return self.move_ok

        def Crop2(self, outside, outline, shape):
            self.crops.append((outside, outline, shape))
            return self.crop_status

        def IsCropped(self):
            return self.cropped

        def GetNotes(self):
            return self.notes

    class Model:
        __slots__ = ("SketchManager", "activation_ok", "activations", "clears", "rebuilds")

        def __init__(self):
            self.SketchManager = manager
            self.activation_ok = True
            self.activations, self.clears = [], []
            self.rebuilds = 0

        def ActivateView(self, name):
            self.activations.append(name)
            return self.activation_ok

        def ClearSelection2(self, all_items):
            self.clears.append(all_items)
            # Native void mutators deliberately return None.

        def EditRebuild3(self):
            self.rebuilds += 1
            return True

    class App:
        __slots__ = ()

        def GetMathUtility(self):
            return utility

    sketch, manager, utility = Sketch(), Manager(), Utility()
    view, model = View(), Model()
    adapter = SimpleNamespace(currentModel=model, swApp=App())
    interfaces = {
        "IView": View, "ISketch": Sketch, "IMathPoint": Point,
        "IMathUtility": Utility, "ISketchManager": Manager, "ISketchArc": Arc,
        "ISketchPoint": Center, "IDrawingDoc": Model, "INote": Note,
    }

    def bind(value, interface):
        if interface == "IMathTransform":
            assert value is sketch.ModelToSketchTransform
        else:
            assert isinstance(value, interfaces[interface])
        return value

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "view_name", lambda adapter, owner: "Relief")
    state = SimpleNamespace(
        adapter=adapter, view=view, model=model, manager=manager, Note=Note,
        places=[], projections=[], projection_drift=0.0, note_calls=[],
        note_none=False, note_copies=1,
    )
    reference_offset = (0.011, -0.007)

    def place(adapter, source, orientation, x, y, *, scale):
        state.places.append((adapter, source, orientation, x, y, scale))
        return view

    def project(adapter, owner, reference, *, label):
        assert owner is view
        state.projections.append((reference, label))
        return (
            view.Position[0] + reference_offset[0] + state.projection_drift,
            view.Position[1] + reference_offset[1],
        )

    def add(adapter, text, x, y):
        state.note_calls.append((text, x, y))
        # Refusal fixtures still have valid ownership, so a removed None
        # guard cannot accidentally fail later at the ownership guard.
        view.notes.extend(Note(text) for _ in range(state.note_copies))
        return None if state.note_none else view.notes[-1] if view.notes else Note(text)

    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "add_note", add)
    return state


@pytest.mark.parametrize("prior", [False, True])
def test_sketch_circle_transforms_and_restores_add_to_db(relief_native, prior):
    state = relief_native
    state.manager.AddToDB = prior
    circle = drawing._sketch_circle(
        state.adapter, state.view, (0.1, 0.2), 0.01, label="test crop"
    )
    assert circle is state.manager.circle
    assert state.manager.calls == [
        (True, pytest.approx((0.23, 0.36, 0.0, 0.25, 0.36, 0.0)))
    ]
    assert state.manager.AddToDB is prior


@pytest.mark.parametrize("prior", [False, True])
def test_sketch_circle_restores_add_to_db_when_creation_throws(relief_native, prior):
    state = relief_native
    state.manager.AddToDB = prior
    error = ValueError("circle creation refused")
    state.manager.failure = error
    with pytest.raises(ValueError, match="^circle creation refused$") as caught:
        drawing._sketch_circle(
            state.adapter, state.view, (0.1, 0.2), 0.01, label="test crop"
        )
    assert caught.value is error
    assert state.manager.calls[0][0] is True
    assert state.manager.AddToDB is prior


@pytest.mark.parametrize("fault", ["none", "center", "radius"])
def test_sketch_circle_refuses_missing_or_drifted_geometry(relief_native, fault):
    state = relief_native
    if fault == "none":
        state.manager.returns_none = True
        message = "^cannot sketch the test crop circle$"
    else:
        # The fake transform doubles lengths: sheet tolerance must do so too.
        setattr(state.manager, f"{fault}_drift", drawing.CIRCLE_TOL_M * 4.0)
        message = "^test crop circle landed off its ask: centre "
    with pytest.raises(RuntimeError, match=message):
        drawing._sketch_circle(
            state.adapter, state.view, (0.1, 0.2), 0.01, label="test crop"
        )
    assert state.manager.AddToDB is False


def test_activate_success_clears_selection(relief_native):
    state = relief_native
    assert drawing._activate(state.adapter, state.view, label="test view") == "Relief"
    assert state.model.activations == ["Relief"]
    assert state.model.clears == [True]


def test_activate_refuses_failed_activation(relief_native):
    state = relief_native
    state.model.activation_ok = False
    with pytest.raises(RuntimeError, match="^failed to activate the test view 'Relief'$"):
        drawing._activate(state.adapter, state.view, label="test view")
    assert state.model.clears == []


def test_cropped_relief_view_places_moves_and_crops_real_helper_circle(relief_native):
    state = relief_native
    assert drawing.cropped_relief_view(state.adapter) is state.view
    assert state.places == [
        (state.adapter, str(drawing.SOURCE), "*Right", *drawing.DETAIL_CENTER,
         drawing.DETAIL_SCALE)
    ]
    assert state.view.moves == [
        (pytest.approx((drawing.DETAIL_CENTER[0] - 0.011,
                        drawing.DETAIL_CENTER[1] + 0.007)), False)
    ]
    reference = tuple(value / 1000.0 for value in drawing.DETAIL_REFERENCE_MM)
    assert state.projections == [(reference, "relief view reference")] * 2
    assert state.model.activations == ["Relief"]
    assert state.view.crops == [(False, False, 5)]
    assert len(state.manager.calls) == 1
    assert state.manager.circle.radius == pytest.approx(2.0 * drawing.DETAIL_RADIUS)
    assert state.model.rebuilds == 2


@pytest.mark.parametrize("fault", ["scale", "move", "reference", "status", "cropped"])
def test_cropped_relief_view_individual_readback_refusals(relief_native, monkeypatch, fault):
    state = relief_native
    if fault == "scale":
        state.view.ScaleRatio = (5.0, 1.0)
        message = "^relief view scale "
    elif fault == "move":
        state.view.move_ok = False
        message = "^cannot move the relief view onto its sheet position$"
    elif fault == "reference":
        original = drawing.model_point_in_view

        def displaced(*args, **kwargs):
            point = original(*args, **kwargs)
            if len(state.projections) == 2:
                return (point[0] + 2.0 * drawing.DETAIL_VIEW_POSITION_TOLERANCE_M,
                        point[1])
            return point

        monkeypatch.setattr(drawing, "model_point_in_view", displaced)
        message = "^relief view reference sits at "
    elif fault == "status":
        state.view.crop_status = drawing._CROP_NO_ERROR + 1
        message = (
            f"^relief view is not cropped: Crop2 status {state.view.crop_status}, "
            "IsCropped True$"
        )
    else:
        state.view.cropped = False
        message = (
            f"^relief view is not cropped: Crop2 status {drawing._CROP_NO_ERROR}, "
            "IsCropped False$"
        )
    with pytest.raises(RuntimeError, match=message):
        drawing.cropped_relief_view(state.adapter)


def _relief_leader_geometry():
    """Derive physical floor/seat coordinates, without changing guard constants."""
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1]
    floor_left = drawing.RELIEF_END_X
    floor_right = drawing.SEAT_X - spec.RELIEF_LEAD * scale / 1000.0
    floor = ((floor_left + floor_right) / 2.0,
             drawing.SIDE_CENTER[1] - spec.RELIEF_DIA * scale / 2000.0)
    bottom = drawing.SIDE_CENTER[1] - spec.SHOULDER_DIA * scale / 2000.0
    # Bend before reaching the seat, then run >= 2 mm below its corner.
    bend = ((floor[0] + drawing.SEAT_X) / 2.0, bottom - 0.0021)
    tail = (drawing.SEAT_X + 0.010, bottom - 0.0021)
    return floor, bend, tail, bottom


@pytest.mark.parametrize("reverse", [False, True])
def test_relief_diameter_leader_accepts_floor_and_safe_seat_crossing(reverse):
    floor, bend, tail, _ = _relief_leader_geometry()
    segments = [(floor, bend), (bend, tail)]
    if reverse:
        segments = [(end, start) for start, end in reversed(segments)]
    drawing._assert_relief_diameter_leader(segments)


def test_relief_diameter_leader_refuses_empty_ink():
    with pytest.raises(RuntimeError, match="^MHA-DT-032 relief diameter has no native leader ink$"):
        drawing._assert_relief_diameter_leader([])


def test_relief_diameter_leader_refuses_wrong_lower_floor_landing():
    floor, bend, tail, _ = _relief_leader_geometry()
    wrong = (floor[0], floor[1] - 0.000151)
    with pytest.raises(RuntimeError, match="does not land on the lower groove floor$"):
        drawing._assert_relief_diameter_leader([(wrong, bend), (bend, tail)])


@pytest.mark.parametrize("vertical", [False, True])
def test_relief_diameter_leader_refuses_seat_corner_crossing(vertical):
    floor, bend, _, bottom = _relief_leader_geometry()
    # Keep a valid landing in both cases: only the crossing guard can refuse.
    near_corner = bottom - 0.0019
    if vertical:
        crossing = ((drawing.SEAT_X, bottom - 0.003),
                    (drawing.SEAT_X, near_corner))
    else:
        crossing = ((drawing.SEAT_X - 0.001, near_corner),
                    (drawing.SEAT_X + 0.001, near_corner))
    with pytest.raises(RuntimeError, match="crosses the seat face/witness instead of passing below its corner$"):
        drawing._assert_relief_diameter_leader([(floor, bend), crossing])


@pytest.fixture
def relief_styles(monkeypatch, relief_native):
    from types import SimpleNamespace

    class Display:
        __slots__ = ("_center", "_arrow", "ignore_center", "ignore_arrow")

        def __init__(self):
            self._center = True
            self._arrow = drawing.ARROWS_OUTSIDE + 1
            self.ignore_center = self.ignore_arrow = False

        @property
        def CenterText(self):
            return self._center

        @CenterText.setter
        def CenterText(self, value):
            if not self.ignore_center:
                self._center = value

        @property
        def ArrowSide(self):
            return self._arrow

        @ArrowSide.setter
        def ArrowSide(self, value):
            if not self.ignore_arrow:
                self._arrow = value

    class Annotation:
        __slots__ = ("name", "display", "position_ok", "positions")

        def __init__(self, name):
            self.name = name
            self.display = Display()
            self.position_ok = True
            self.positions = []

        def GetSpecificAnnotation(self):
            return self.display

        def SetPosition2(self, x, y, z):
            self.positions.append((x, y, z))
            return self.position_ok

    annotations = [Annotation(name) for name in
                   ("ReliefDia", "ReliefLead", "SeatEdgeBreak", "ReliefWidth")]
    state = SimpleNamespace(
        native=relief_native, annotations=annotations, near_side=[], ink_reads=[],
    )
    original_bind = drawing._early_bound

    def bind(value, interface):
        if interface in ("IAnnotation", "IDisplayDimension"):
            assert isinstance(value, Annotation if interface == "IAnnotation" else Display)
            return value
        return original_bind(value, interface)

    def near_side(annotation, label):
        state.near_side.append((annotation, label))

    def ink(annotation):
        state.ink_reads.append(annotation)
        floor, bend, tail, _ = _relief_leader_geometry()
        return [(floor, bend), (bend, tail)]

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing._drawing_leaders, "set_near_side_diameter", near_side)
    monkeypatch.setattr(drawing._drawing_leaders, "dimension_segments", ink)
    return state


def test_style_relief_dimensions_positions_and_reads_real_leader_guard(relief_styles):
    state = relief_styles
    drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    diameter, lead, edge, unrelated = state.annotations
    assert state.near_side == [(diameter, "MHA-DT-032 relief diameter")]
    assert state.ink_reads == [diameter]
    for annotation, xy in (
        (diameter, drawing.SIDE_KEEP["ReliefDia"]),
        (lead, drawing.DETAIL_KEEP["ReliefLead"]),
        (edge, drawing.DETAIL_KEEP["SeatEdgeBreak"]),
    ):
        assert annotation.positions == [(*xy, 0.0)]
    for annotation in (lead, edge):
        assert annotation.display.CenterText is False
        assert annotation.display.ArrowSide == drawing.ARROWS_OUTSIDE
    assert unrelated.positions == []
    assert state.native.model.rebuilds == 1


@pytest.mark.parametrize("name", ["ReliefDia", "ReliefLead", "SeatEdgeBreak"])
def test_style_relief_dimensions_refuses_set_position(relief_styles, name):
    state = relief_styles
    next(item for item in state.annotations if item.name == name).position_ok = False
    with pytest.raises(RuntimeError, match=f"^cannot position the MHA-DT-032 {name} text$"):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)


@pytest.mark.parametrize("name", ["ReliefLead", "SeatEdgeBreak"])
@pytest.mark.parametrize("property_name", ["center", "arrow"])
def test_style_relief_dimensions_refuses_ignored_display_property(relief_styles, name, property_name):
    state = relief_styles
    annotation = next(item for item in state.annotations if item.name == name)
    setattr(annotation.display, f"ignore_{property_name}", True)
    with pytest.raises(RuntimeError, match=f"^{name} arrows/centring did not take: ArrowSide "):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)


@pytest.mark.parametrize("name", ["ReliefDia", "ReliefLead", "SeatEdgeBreak"])
def test_style_relief_dimensions_refuses_missing_registered_dimension(relief_styles, name):
    state = relief_styles
    annotations = [item for item in state.annotations if item.name != name]
    with pytest.raises(RuntimeError, match=rf"^relief dimension styles not applied: \['{name}'\]$"):
        drawing.style_relief_dimensions(state.native.adapter, annotations)


def test_style_relief_dimensions_does_not_bypass_leader_guard(relief_styles, monkeypatch):
    state = relief_styles
    monkeypatch.setattr(drawing._drawing_leaders, "dimension_segments", lambda annotation: [])
    with pytest.raises(RuntimeError, match="^MHA-DT-032 relief diameter has no native leader ink$"):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)


@pytest.mark.parametrize("parent", [False, True])
def test_relief_note_is_owned_once_by_its_activated_view(relief_native, parent):
    state = relief_native
    function = drawing.mark_relief_on_side if parent else drawing.label_relief_view
    text = drawing.DETAIL_LETTER if parent else drawing.DETAIL_VIEW_LABEL
    xy = drawing.DETAIL_PARENT_LETTER_XY if parent else drawing.DETAIL_LABEL_XY
    function(state.adapter, state.view)
    assert state.model.activations == ["Relief"]
    assert state.note_calls == [(text, *xy)]
    assert [note.GetText() for note in state.view.notes] == [text]
    assert len(state.manager.calls) == int(parent)
    if parent:
        assert state.manager.circle.radius == pytest.approx(
            2.0 * drawing.DETAIL_PARENT_RADIUS
        )
        reference = tuple(value / 1000.0 for value in drawing.DETAIL_REFERENCE_MM)
        assert state.projections == [(reference, "side relief mark")]
        assert state.model.clears == [True, True]


@pytest.mark.parametrize("parent", [False, True])
def test_relief_note_refuses_add_note_none_with_otherwise_valid_ownership(relief_native, parent):
    state = relief_native
    state.note_none = True
    function = drawing.mark_relief_on_side if parent else drawing.label_relief_view
    message = ("^failed to letter the side view's relief mark$" if parent
               else "^failed to add the relief view label$")
    with pytest.raises(RuntimeError, match=message):
        function(state.adapter, state.view)


@pytest.mark.parametrize("parent", [False, True])
@pytest.mark.parametrize("copies", [0, 2], ids=["missing-owner", "duplicate-owner"])
def test_relief_note_refuses_missing_or_duplicate_view_ownership(relief_native, parent, copies):
    state = relief_native
    state.note_copies = copies
    state.view.notes.append(state.Note("unrelated existing view note"))
    function = drawing.mark_relief_on_side if parent else drawing.label_relief_view
    message = ("^side relief letter did not land in the side view: " if parent
               else "^relief view label did not land in the relief view: ")
    with pytest.raises(RuntimeError, match=message):
        function(state.adapter, state.view)


def test_build_wires_native_relief_helpers_to_the_correct_views():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body
                 if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    expected = {
        "cropped_relief_view": ["adapter"],
        "style_relief_dimensions": ["adapter", "annotations"],
        "label_relief_view": ["adapter", "detail"],
        "mark_relief_on_side": ["adapter", "side"],
    }
    for name, args in expected.items():
        matches = [node for node in calls
                   if isinstance(node.func, ast.Name) and node.func.id == name]
        assert len(matches) == 1, name
        assert [ast.unparse(arg) for arg in matches[0].args] == args, name
    assignment = next(
        node for node in build.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "cropped_relief_view"
    )
    assert [ast.unparse(target) for target in assignment.targets] == ["detail"]
