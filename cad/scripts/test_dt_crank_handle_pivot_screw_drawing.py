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
    assert {"ReliefDia", "ReliefLead", "ReliefCornerRadius", "SeatEdgeBreak"} <= spec.DRAWING_DIMENSIONS["ScrewProfile"]
    assert spec.DRAWING_PRECISION["ScrewProfile"]["ReliefDia"] == 1
    # The slot width is only true-size in the head-end view.
    assert set(drawing.END_KEEP) == {"SlotWidth"}


def test_model_owns_places_and_bands() -> None:
    assert "draw_dt_crank_handle_pivot_screw.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # The running fit, the head's pocket-clearance/bearing band and the head
    # length that keeps it below the cup face print at two places.  The relief's
    # bounded seating neck and lead, relief-corner MAX, seat-edge break MAX,
    # tip chamfer MAX, slot depth and thread length print at one (r8).
    running_fit = {"ShoulderDia", "HeadDia", "HeadLength", "HeadOuterChamfer"}
    for name, places in spec.DRAWING_PRECISION_BY_NAME.items():
        assert places == (2 if name in running_fit else 1), name
    # Main's r18 ruling adds the existing local 53 REF with its to-suit rule,
    # without changing either tip-based location or the plain 63/67 REFs.
    assert spec.REFERENCE_DIMENSIONS == {"ShoulderLength", "OverallLength", "UnderHeadLocation"}
    assert "ShoulderLength" in spec.DRAWING_DIMENSIONS["ScrewProfile"]
    assert spec.DRAWING_PRECISION["ScrewProfile"]["ShoulderLength"] == 1
    assert spec.DRAWING_PRECISION_BY_NAME["ShoulderLength"] == 1
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
        ("ScrewProfile", "ReliefCornerRadius"): (spec.RELIEF_CORNER_RADIUS_MAX, 6),
        ("ScrewProfile", "UnderHeadCornerRadius"): (spec.UNDER_HEAD_CORNER_RADIUS_MAX, 6),
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
    assert spec.RELIEF_DIA_ROOT_CALLOUT == "BELOW #4-40 ROOT"
    assert "\n" not in spec.RELIEF_DIA_ROOT_CALLOUT
    assert spec.RELIEF_DIA_CALLOUT == "NECK FOR SEATING\nON MHA-DT-06"
    assert drawing.RELIEF_DIA_ROOT_CALLOUT is spec.RELIEF_DIA_ROOT_CALLOUT
    assert max(
        len(line)
        for text in (spec.RELIEF_DIA_ROOT_CALLOUT, spec.RELIEF_DIA_CALLOUT)
        for line in text.splitlines()
    ) <= 16
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
    assert spec.RELIEF_WIDTH == 2.4
    assert spec.RELIEF_CORNER_RADIUS_MAX == 0.2
    assert spec.RELIEF_CORNER_CALLOUT == "DIE RUNOUT"
    assert drawing.RELIEF_CORNER_CALLOUT is spec.RELIEF_CORNER_CALLOUT
    assert spec.RELIEF_LEAD == 0.3
    assert spec.RELIEF_LEAD_LIMITS == (0.2, 0.4)
    # The printed limits are the model band's (Codex P2 on #1139).
    assert spec.RELIEF_LEAD_LIMITS == pytest.approx(
        (spec.RELIEF_LEAD - spec.RELIEF_LEAD_TOL, spec.RELIEF_LEAD + spec.RELIEF_LEAD_TOL)
    )
    assert spec.RELIEF_LEAD_CALLOUT == f"{spec.CHAMFER_CALLOUT}\nLEAD INTO MHA-DT-06"
    assert drawing.RELIEF_LEAD_CALLOUT is spec.RELIEF_LEAD_CALLOUT
    assert spec.RELIEF_END_STATION == pytest.approx(spec.SEAT_STATION + 2.4)
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
    assert spec.SEAT_EDGE_BREAK_CALLOUT == "X 45 DEG\nPRESERVES SEAT ON MHA-DT-06"
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
    # on the relief diameter.  At routine .X the 2.4 width's straight floor
    # excludes the longest lead AND largest thread-side floor radius, keeping
    # 1.5 #4-40 pitches of die run-out.
    toleranced = {name for _, name in model_toleranced_dimensions(part)}
    assert "ReliefWidth" not in toleranced
    assert spec.RELIEF_WIDTH_MIN == pytest.approx(1.6)
    assert spec.RELIEF_FLOOR_MIN == pytest.approx(
        spec.RELIEF_WIDTH_MIN - spec.RELIEF_LEAD_LIMITS[1] - spec.RELIEF_CORNER_RADIUS_MAX
    )
    assert spec.RELIEF_FLOOR_MIN == pytest.approx(1.0)
    assert spec.RELIEF_FLOOR_MIN >= 1.5 * 25.4 / 40.0
    assert spec.DRAWING_PRECISION["ScrewProfile"]["ReliefLead"] == 1
    assert spec.DRAWING_PRECISION["ScrewProfile"]["SeatEdgeBreak"] == 1
    assert spec.DRAWING_PRECISION["ScrewProfile"]["ReliefCornerRadius"] == 1


def _native_corner_limit_fixture(monkeypatch, refusal=None):
    class Tolerance:
        __slots__ = ("_type", "values", "calls")

        def __init__(self):
            self._type = 0
            # A refused call can leave already-zero bounds.  Isolate its
            # boolean result from the independent min/max readback guards.
            self.values = (
                (0.0, 0.0) if refusal in ("values", "void") else (-0.0001, 0.0001)
            )
            self.calls = []

        @property
        def Type(self):
            return self._type

        @Type.setter
        def Type(self, value):
            self.calls.append(("Type", value))
            if refusal != "type":
                self._type = value

        def SetValues(self, lower, upper):
            self.calls.append(("SetValues", lower, upper))
            if refusal == "values":
                return False
            if refusal == "void":
                return None
            self.values = (
                lower - (0.0001 if refusal == "lower" else 0.0),
                upper + (0.0001 if refusal == "upper" else 0.0),
            )
            return True

        def GetMinValue(self):
            return self.values[0]

        def GetMaxValue(self):
            return self.values[1]

    class Dimension:
        __slots__ = ("Tolerance", "SystemValue")

        def __init__(self):
            self.Tolerance = Tolerance()
            self.SystemValue = spec.RELIEF_CORNER_RADIUS_MAX / 1000.0
            if refusal == "nominal":
                self.SystemValue += 0.0001

    dimension = Dimension()
    adapter = object()
    lookups = []
    key = ("ScrewProfile", "ReliefCornerRadius")
    monkeypatch.setattr(part, "SINGLE_LIMITS", {key: spec.SINGLE_LIMITS[key]})

    def named_dimension(actual_adapter, feature, name):
        assert actual_adapter is adapter
        lookups.append((feature, name))
        return None, dimension

    def bind(value, interface):
        assert interface == "IDimensionTolerance"
        assert value is dimension.Tolerance
        return value

    monkeypatch.setattr(part, "_named_dimension", named_dimension)
    monkeypatch.setattr(part, "_early_bound", bind)
    return adapter, dimension, lookups


def test_relief_corner_max_is_authored_on_the_native_radius(monkeypatch):
    adapter, dimension, lookups = _native_corner_limit_fixture(monkeypatch)
    part._single_limits(adapter)
    assert lookups == [("ScrewProfile", "ReliefCornerRadius")]
    assert dimension.SystemValue == pytest.approx(0.0002)
    assert dimension.Tolerance.calls == [("Type", 6), ("SetValues", 0.0, 0.0)]
    assert dimension.Tolerance.Type == 6
    assert dimension.Tolerance.GetMinValue() == 0.0
    assert dimension.Tolerance.GetMaxValue() == 0.0


@pytest.mark.parametrize(
    ("refusal", "message"),
    [
        ("nominal", "is not the limit"),
        ("type", "cannot retain the single limit 6"),
        ("values", "cannot retain the single limit 6"),
        ("void", "cannot retain the single limit 6"),
        ("lower", "cannot retain the single limit 6"),
        ("upper", "cannot retain the single limit 6"),
    ],
)
def test_relief_corner_max_rejects_native_nominal_and_limit_drift(
    monkeypatch, refusal, message
):
    adapter, dimension, lookups = _native_corner_limit_fixture(monkeypatch, refusal)
    with pytest.raises(RuntimeError, match=message):
        part._single_limits(adapter)
    assert lookups == [("ScrewProfile", "ReliefCornerRadius")]
    if refusal == "nominal":
        assert dimension.Tolerance.calls == []


@pytest.fixture
def corner_profile(monkeypatch):
    """Record real builder calls up to the revolve; no native solver is run."""
    from types import SimpleNamespace

    class ProfileComplete(Exception):
        pass

    state = SimpleNamespace(
        lines={}, arcs=[], constraints=[], dimensions=[], globals={}, rows=[],
        events=[], failure=None,
    )

    def result(data=None, *, operation=None):
        return SimpleNamespace(
            is_success=state.failure != operation or operation is None,
            data=data,
            error=f"native {operation} refused",
        )

    class Adapter:
        def __init__(self):
            self.currentSketchManager = SimpleNamespace(AddToDB=False)

        async def create_part(self):
            return result()

        async def create_sketch(self, plane):
            assert plane == "Right"
            return result()

        async def add_centerline(self, *points):
            return result("Axis")

        async def add_line(self, *points):
            assert self.currentSketchManager.AddToDB is True
            name = f"Line{len(state.lines)}"
            state.lines[name] = points
            return result(name)

        async def add_arc(self, *points):
            assert self.currentSketchManager.AddToDB is True
            state.arcs.append(points)
            name = "Corner" if len(state.arcs) == 1 else "UnderHeadCorner"
            return result(name, operation="arc" if len(state.arcs) == 1 else "under-head-arc")

        async def add_sketch_constraint(self, first, second, relation):
            state.constraints.append((first, second, relation))
            return result()

        async def add_sketch_dimension(self, first, second, kind, value):
            state.dimensions.append((first, second, kind, value))
            operation = "under-head-radial" if first == "UnderHeadCorner" else kind
            return result(f"Dimension{len(state.dimensions)}", operation=operation)

        async def exit_sketch(self):
            state.events.append("exit")
            return result()

        async def create_revolve(self, parameters):
            assert parameters.angle == 360.0
            raise ProfileComplete

    class Dimensions(part.SketchDims):
        def apply(self, adapter, feature):
            assert feature == "ScrewProfile"
            state.rows = self._rows.copy()
            return []

    async def set_global(adapter, name, expression):
        state.globals[name] = expression

    async def diameter(adapter, axis, line, xy, name):
        assert axis == "Axis"
        state.dimensions.append((line, None, "diameter", name))

    async def fully_defined(adapter, label):
        assert label == "screw profile sketch"
        assert adapter.currentSketchManager.AddToDB is False
        state.events.append("fully_defined")

    monkeypatch.setattr(part, "SketchDims", Dimensions)
    monkeypatch.setattr(part, "set_global", set_global)
    monkeypatch.setattr(part, "set_sketch_direct_db", lambda adapter, enabled:
                        setattr(adapter.currentSketchManager, "AddToDB", enabled))
    monkeypatch.setattr(part, "add_diametric_linear_dimension", diameter)
    monkeypatch.setattr(part, "ensure_fully_defined", fully_defined)
    monkeypatch.setattr(part, "name_last_feature", lambda adapter, name:
                        state.events.append(name))
    state.adapter = Adapter()
    state.complete = ProfileComplete
    return state


@pytest.mark.asyncio
async def test_builder_uses_the_supported_tangent_arc_and_associative_radius(corner_profile):
    state = corner_profile
    with pytest.raises(state.complete):
        await part.build(state.adapter)
    e = spec.RELIEF_CORNER_RADIUS_MAX
    r = spec.RELIEF_DIA / 2.0
    end = spec.RELIEF_END_STATION
    # The adapter's CCW arc starts on the flank and ends on the floor.
    assert len(state.arcs) == 2
    assert state.arcs[0] == pytest.approx((-(end - e), r + e, -end, r + e, -(end - e), r))
    assert state.lines["Line8"] == pytest.approx(
        (-(spec.SEAT_STATION + spec.RELIEF_LEAD), r, -(end - e), r)
    )
    assert state.lines["Line9"] == pytest.approx((-end, r + e, -end, part.THREAD_R))
    for u, v in (state.arcs[0][2:4], state.arcs[0][4:6]):
        # Contain the endpoints the builder REALLY sends to CreateArc, not
        # the removed sharp floor/flank intersection.
        assert drawing.DETAIL_RADIUS_MM - math.hypot(
            -u - drawing.DETAIL_STATION, v
        ) >= 0.2
    assert state.lines["Line8"][2:] == state.arcs[0][4:6]
    assert state.lines["Line9"][:2] == state.arcs[0][2:4]
    assert state.lines["Line13"][2:] == state.lines["Line0"][:2]
    for connection in (
        ("Line8", "Corner", "tangent"),
        ("Line9", "Corner", "tangent"),
    ):
        assert connection in state.constraints
    assert not any(relation == "fix" for _, _, relation in state.constraints)
    assert ("Corner", None, "radial", e) in state.dimensions
    assert ("ReliefCornerRadius", '"ReliefCornerRadius"') in state.rows
    assert state.globals["ReliefCornerRadius"] == f"{e}mm"
    assert ("Line7.start", "Line9.start", "horizontal_distance", spec.RELIEF_WIDTH) in state.dimensions
    assert ("ReliefWidth", '"ReliefWidth"') in state.rows
    assert ("ReliefDia", '"ReliefDia"') in state.rows
    assert ("Line8", None, "diameter", "ReliefDia") in state.dimensions
    assert state.events == ["fully_defined", "exit", "ScrewProfile"]


@pytest.mark.asyncio
@pytest.mark.parametrize("arc_index", [0, 1], ids=["thread-relief", "inner-under-head"])
async def test_relief_corner_real_adapter_emits_a_90_degree_not_270_degree_arc(corner_profile, arc_index):
    from types import SimpleNamespace

    from solidworks_mcp.adapters.solidworks.sketch import SolidWorksSketchMixin

    state = corner_profile
    with pytest.raises(state.complete):
        await part.build(state.adapter)

    class Manager:
        __slots__ = ("calls", "segment")

        def __init__(self):
            self.calls = []
            self.segment = object()

        def CreateArc(self, xc, yc, zc, x1, y1, z1, x2, y2, z2, direction):
            self.calls.append((xc, yc, zc, x1, y1, z1, x2, y2, z2, direction))
            return self.segment

    class Boundary:
        __slots__ = ("currentSketchManager", "registered")

        def __init__(self):
            self.currentSketchManager = Manager()
            self.registered = []

        def _handle_com_operation(self, name, callback):
            assert name == "add_arc"
            return SimpleNamespace(is_success=True, data=callback())

        def _register_sketch_entity(self, prefix, segment):
            assert prefix == "Arc"
            assert segment is self.currentSketchManager.segment
            self.registered.append((prefix, segment))
            return "Corner"

    native = Boundary()
    # Exercise the installed adapter's PUBLIC add_arc path, including its
    # actual mm-to-metres conversion and CreateArc direction argument.
    made = await SolidWorksSketchMixin.add_arc(native, *state.arcs[arc_index])
    assert made.is_success and made.data == "Corner"
    assert native.registered == [("Arc", native.currentSketchManager.segment)]
    assert len(native.currentSketchManager.calls) == 1
    xc, yc, zc, x1, y1, z1, x2, y2, z2, direction = native.currentSketchManager.calls[0]
    if arc_index == 0:
        e = spec.RELIEF_CORNER_RADIUS_MAX / 1000.0
        r = spec.RELIEF_DIA / 2000.0
        station = spec.RELIEF_END_STATION / 1000.0
        expected = (-(station - e), r + e, 0.0, -station, r + e, 0.0,
                    -(station - e), r, 0.0)
        expected_start, expected_end = (-e, 0.0), (0.0, -e)
    else:
        e = spec.UNDER_HEAD_CORNER_RADIUS_MAX / 1000.0
        expected = (-0.0041, 0.0021, 0.0, -0.0041, 0.0020, 0.0, -0.0040, 0.0021, 0.0)
        expected_start, expected_end = (0.0, -e), (e, 0.0)
    assert (xc, yc, zc, x1, y1, z1, x2, y2, z2) == pytest.approx(expected)
    # Public adapter -> pinned CreateArc centre/start/end in metres; +1 CCW.
    assert direction == 1
    start = (x1 - xc, y1 - yc)
    end = (x2 - xc, y2 - yc)
    assert start == pytest.approx(expected_start)
    assert end == pytest.approx(expected_end)
    signed_turn = math.atan2(
        start[0] * end[1] - start[1] * end[0],
        start[0] * end[0] + start[1] * end[1],
    )
    sweep = (direction * signed_turn) % math.tau
    assert math.degrees(sweep) == pytest.approx(90.0)
    assert math.degrees((-direction * signed_turn) % math.tau) == pytest.approx(270.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["arc", "radial"])
async def test_builder_rejects_a_failed_native_corner_or_radius(corner_profile, failure):
    state = corner_profile
    state.failure = failure
    with pytest.raises(RuntimeError, match=f"native {failure} refused"):
        await part.build(state.adapter)
    assert state.events == []


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


def test_native_callouts_own_the_relief_lead_corner_and_seat_break() -> None:
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
    assert callouts["above"] == {
        "ReliefDia": "RELIEF_DIA_ROOT_CALLOUT",
        "ShoulderDia": "SHOULDER_CALLOUT",
    }
    assert callouts["below"] == {
        "ReliefDia": "RELIEF_DIA_CALLOUT",
        "ReliefLead": "RELIEF_LEAD_CALLOUT",
        "ReliefCornerRadius": "RELIEF_CORNER_CALLOUT",
        "SeatEdgeBreak": "SEAT_EDGE_BREAK_CALLOUT",
        "HeadOuterChamfer": "HEAD_OUTER_CHAMFER_CALLOUT",
        "TipChamfer": "CHAMFER_CALLOUT",
        "HeadDia": "HEAD_DIA_CALLOUT",
        "HeadLength": "HEAD_LENGTH_CALLOUT",
        "ShoulderLength": "UNDER_HEAD_CALLOUT",
    }
    assert spec.HEAD_DIA_CALLOUT == "BEARING ANNULUS ON MHA-DT-35"
    assert spec.HEAD_LENGTH_CALLOUT == "HEAD; KEEPS TOP BELOW MHA-DT-35 FACE"
    assert drawing.HEAD_DIA_CALLOUT is spec.HEAD_DIA_CALLOUT
    assert drawing.HEAD_LENGTH_CALLOUT is spec.HEAD_LENGTH_CALLOUT
    assert spec.DRAWING_NOTES == (
        f"TIP FILED FLUSH WITH MHA-DT-06 AND STAKED AT {spec.FITTED_STEP}."
    )


def test_native_seat_break_preserves_the_functional_shoulder_length() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build("):]
    # The cylinder stops short, but the chamfer ends at the unchanged seat.
    assert "(-(SEAT_STATION - SEAT_EDGE_BREAK_MAX), SHOULDER_R)," in body
    assert "(-SEAT_STATION, SHOULDER_R - SEAT_EDGE_BREAK_MAX)," in body
    assert "(-SEAT_STATION, RELIEF_R + RELIEF_LEAD)," in body
    assert "lines = await add_line_chain(adapter, points, close=False)" in body
    assert "head_outline, head_outer_chamfer, under_head_face = lines[1], lines[2], lines[3]" in body
    assert "shoulder_outline, seat_edge_break, _, relief_lead, relief_floor = shoulder_lines" in body
    assert '("SeatEdgeBreak", SEAT_EDGE_BREAK_MAX),' in body
    assert (
        '"ShoulderLength",\n'
        '            f"{under_head_face}.end",\n'
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


@pytest.mark.parametrize(
    ("previous", "replacement", "message"),
    [
        (
            "RELIEF_CORNER_RADIUS_MAX = 0.2",
            "RELIEF_CORNER_RADIUS_MAX = 0.3",
            "straight floor is under 1.5 pitches",
        ),
        (
            "RELIEF_WIDTH = 2.4",
            "RELIEF_WIDTH = 2.6",
            "stock-arm worst-case engagement is under the 1.5D rule",
        ),
    ],
)
def test_relief_corner_and_width_mutations_trip_their_physical_floors(
    previous, replacement, message
) -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert source.count(previous) == 1
    probe = source.replace(previous, replacement)
    with pytest.raises(AssertionError, match=message):
        exec(compile(probe, spec.__file__, "exec"), {"__name__": "_relief_geometry_probe"})


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
    # Nominal: min(10.0 - 0.3, arm 8.0) - 2.4 = 5.6 of full thread.
    assert spec.FULL_THREAD_NOMINAL == pytest.approx(5.6)
    assert spec.FULL_THREAD_NOMINAL_DIAMETERS == pytest.approx(5.6 / 2.845)
    # Thinnest stock 5/16-in arm: min(8.9, 7.8359 - the 0.25 exit break)
    # - (2.4 + the .X band 0.8) = 4.3859, above the 4.2675 floor.
    # The arm governs; the radius stays inside the groove, not full thread.
    assert geometry.GENERAL_1PL_TOL_MM == pytest.approx(0.8)
    assert spec.TAP_EXIT_BREAK == pytest.approx(0.25)
    assert spec.ARM_STOCK_THICKNESS == pytest.approx(7.9375)
    assert spec.RELIEF_WIDTH_MAX == pytest.approx(3.2)
    assert spec.ARM_STOCK_THICKNESS_MIN == pytest.approx(7.8359)
    assert spec.FULL_THREAD_WORST == pytest.approx(4.3859)
    assert spec.FULL_THREAD_WORST_DIAMETERS == pytest.approx(4.3859 / 2.845, abs=1e-4)
    assert spec.ENGAGEMENT_GOVERNED_BY == "arm"
    # Arm at its printed maximum 8.8: min(8.9, 8.8 - 0.25) - 3.2 = 5.35;
    # the arm still governs.
    assert spec.ARM_PRINTED_THICKNESS_MAX == pytest.approx(8.8)
    assert spec.FULL_THREAD_WORST_PRINTED_ARM == pytest.approx(5.35)
    assert spec.FULL_THREAD_WORST_PRINTED_ARM_DIAMETERS == pytest.approx(5.35 / 2.845, abs=1e-3)
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
    assert spec.HEAD_BEARING_RADIAL_CONCENTRIC_MIN == pytest.approx(0.29)
    assert spec.HEAD_RUNNING_OFFSET_MAX == pytest.approx(min(0.4 / 2.0, (4.3 - 3.92) / 2.0))
    assert spec.HEAD_BEARING_RADIAL_MIN == pytest.approx(0.10)


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


def test_shoulder_finish_resolves_the_part_owned_face_and_pins_the_original_landing(monkeypatch):
    from types import SimpleNamespace

    document, shoulder_face = object(), object()
    view = SimpleNamespace(ReferencedDocument=document)
    adapter = SimpleNamespace(currentModel=object())
    control = drawing.surface_finish_by_key(spec.SURFACE_FINISHES, "pivot_shoulder")
    events = []

    def bind(value, interface):
        assert (value is view and interface == "IView") or (
            value is document and interface == "IModelDoc2"
        )
        events.append(("bind", interface))
        return value

    def resolve(value, selectors):
        assert value is document and value is not adapter.currentModel
        assert selectors == {"pivot_shoulder": control.face}
        events.append(("resolve",))
        return {"pivot_shoulder": shoulder_face}

    def finish(actual_adapter, actual_view, **kwargs):
        assert actual_adapter is adapter and actual_view is view
        assert kwargs == {
            "entity": shoulder_face,
            "entity_type": "FACE",
            "leader_attach_xy": drawing.FINISH_PICK,
            "symbol_xy": drawing.FINISH_SYMBOL,
            "control": control,
            "label": "MHA-DT-32 pivot-shoulder finish",
            "char_height": 0.0025,
        }
        events.append(("finish",))

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing, "resolve_faces", resolve)
    monkeypatch.setattr(drawing, "add_surface_finish", finish)
    drawing._add_shoulder_finish(adapter, view)
    assert events == [("bind", "IView"), ("bind", "IModelDoc2"), ("resolve",), ("finish",)]
    assert drawing.FINISH_PICK == pytest.approx((0.1985, 0.184))
    assert drawing.FINISH_SYMBOL == pytest.approx((0.2105, 0.168))


@pytest.mark.parametrize("count", [0, 2])
def test_shoulder_finish_propagates_failed_exact_one_face_resolution(monkeypatch, count):
    from types import SimpleNamespace

    document = object()
    view = SimpleNamespace(ReferencedDocument=document)
    calls = []

    def resolve(value, selectors):
        assert value is document and set(selectors) == {"pivot_shoulder"}
        raise RuntimeError(f"pivot_shoulder matched {count} faces")

    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "resolve_faces", resolve)
    monkeypatch.setattr(drawing, "add_surface_finish", lambda *args, **kwargs: calls.append(kwargs))
    with pytest.raises(RuntimeError, match=f"^pivot_shoulder matched {count} faces$"):
        drawing._add_shoulder_finish(object(), view)
    assert calls == []


def test_modelled_volume_is_the_turned_body_less_the_slot() -> None:
    head = math.pi * 3.0**2 * 4.0
    shoulder = math.pi * 2.0**2 * 53.0
    relief = math.pi * (1.9 / 2.0) ** 2 * 2.4
    thread = math.pi * (2.845 / 2.0) ** 2 * 7.6
    # Pappus: the lead's 0.3 x 0.3 corner triangle, centroid 0.95 + 0.3/3
    # out, stays; the tip chamfer's 0.3 x 0.3, centroid 1.4225 - 0.3/3 out,
    # goes.
    lead = 2.0 * math.pi * (0.95 + 0.3 / 3.0) * (0.3 * 0.3 / 2.0)
    tip = 2.0 * math.pi * (2.845 / 2.0 - 0.3 / 3.0) * (0.3 * 0.3 / 2.0)
    # Pappus: the outer seat's 0.1 x 0.1 triangle is removed in both states.
    seat_break = math.pi * 0.1**2 * (2.0 - 0.1 / 3.0)
    assert part.V_LEAD == pytest.approx(lead)
    corner = 2.0 * math.pi * (
        0.95 * 0.2**2 * (1.0 - math.pi / 4.0)
        + 0.2**3 * (5.0 / 6.0 - math.pi / 4.0)
    )
    assert part.V_RELIEF_CORNER == pytest.approx(corner)
    inner = 2.0 * math.pi * (2.0 * 0.1**2 * (1.0 - math.pi / 4.0) + 0.1**3 * (5.0 / 6.0 - math.pi / 4.0))
    outer = math.pi * (3.0 * 0.26**2 - 0.26**3 / 3.0)
    assert part.V_BODY == pytest.approx(
        head + shoulder + relief + thread + lead + corner - tip - seat_break + inner - outer
    )
    # Filed flush: 5.6 of full thread past the relief, a 0.25 edge break.
    fitted_thread = math.pi * (2.845 / 2.0) ** 2 * 5.6
    fitted_tip = 2.0 * math.pi * (2.845 / 2.0 - 0.25 / 3.0) * (0.25 * 0.25 / 2.0)
    assert part.turned_volume(8.0, 0.25) == pytest.approx(
        head + shoulder + relief + fitted_thread + lead + corner - fitted_tip - seat_break + inner - outer
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


def test_relief_corner_volume_matches_the_actual_quarter_circle() -> None:
    radius = spec.RELIEF_DIA / 2.0
    corner = spec.RELIEF_CORNER_RADIUS_MAX
    steps = 10_000
    dz = corner / steps
    # The arc replaces the sharp floor with r + e - sqrt(e² - z²), over
    # its last e of width.  Integrate annular slices independently of Pappus.
    filled = sum(
        math.pi * (
            (radius + corner - math.sqrt(corner**2 - ((i + 0.5) * dz)**2))**2
            - radius**2
        ) * dz
        for i in range(steps)
    )
    assert part.V_RELIEF_CORNER == pytest.approx(filled, abs=1e-6)


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
        assert "\n" not in text and "MHA-DT-35" in text, name
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
    # Historical name retained for the mutation harness. The local native
    # seat-to-under-head 53 now owns the to-suit rule; tip-based 63/67 stay
    # plain references. Only the assembly finishing instruction is a note.
    lines = spec.UNDER_HEAD_CALLOUT.splitlines()
    assert lines[0].startswith("UNDER-HEAD FACED TO SUIT")
    assert "MHA-DT-08" in spec.UNDER_HEAD_CALLOUT
    assert spec.UNDER_HEAD_CALLOUT.endswith("PLUS 0.25-1.00")
    # 2.5 mm a character (the r3 audit boxed the block 96.5 mm wide): the
    # widest line stays between the seat-face and under-head extension lines,
    # centred on the reference's text.
    half = max(len(line) for line in lines) * 0.0025 / 2.0
    centre = drawing.SIDE_KEEP["ShoulderLength"][0]
    assert centre - half > drawing.SEAT_X + 0.010
    assert centre + half < drawing.FINISH_SYMBOL[0] - 0.003
    assert drawing.SIDE_KEEP["ShoulderLength"] == pytest.approx((0.154, 0.1575))
    assert centre == drawing.SIDE_KEEP["UnderHeadLocation"][0]
    assert centre <= 0.160
    notes = spec.DRAWING_NOTES.splitlines()
    assert notes == [
        f"TIP FILED FLUSH WITH MHA-DT-06 AND STAKED AT {spec.FITTED_STEP}."
    ]
    # SOLIDWORKS prints no multi-line above-callout (the 04b95f481 sheet).
    assert "\n" not in spec.SHOULDER_CALLOUT
    assert "MHA-DT-08" in spec.SHOULDER_CALLOUT


def test_under_head_witness_lies_on_the_edge_and_prints_black() -> None:
    # The witness is exactly the remaining .64 flat, never a phantom sharp
    # corner through the fillet or bevel. It prints in the outline's black.
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert "under_head_v" not in build
    assert "-HEAD_LENGTH, -(HEAD_R - HEAD_OUTER_CHAMFER)," in build
    assert "-HEAD_LENGTH, -(SHOULDER_R + UNDER_HEAD_CORNER_RADIUS_MAX)," in build
    assert drawing.UNDER_HEAD_WITNESS_LEN == pytest.approx(0.64)
    assert drawing.UNDER_HEAD_WITNESS_LEN == pytest.approx(spec.UNDER_HEAD_FLAT_WITNESS_LENGTH)
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
    # The combined thread/file-tip callout lands on the real tip-face EDGE,
    # not the relief groove or the former upper full-thread junction.
    assert drawing.THREAD_PICK == pytest.approx((drawing.TIP_X, 0.193))
    assert drawing.THREAD_START_X - drawing.TIP_X == pytest.approx(
        spec.TIP_CHAMFER * drawing.SHEET_SCALE[0] / 1000.0
    )
    assert not drawing.RELIEF_END_X <= drawing.THREAD_PICK[0] <= drawing.SEAT_X
    assert drawing.THREAD_PICK[0] < drawing.RELIEF_END_X
    # The four local relief/detail dimensions stay in the enlarged model view;
    # the width remains on SIDE, clear of the rotated neck text.
    assert set(drawing.DETAIL_KEEP).isdisjoint(drawing.SIDE_KEEP)
    assert "ReliefDia" in drawing.DETAIL_KEEP
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_drawing_leaders.dimension_segments(relief_diameter)" in source
    for obsolete in ("set_near_side_diameter", "DisplayAsLinear", "offset_dimension_text",
                     "import_relief_diameter", "move_model_dimension", "delete_view"):
        assert obsolete not in source
    # The complete note, not a centred half-width, stays left of the tip.
    note_x, note_y = drawing.THREAD_NOTE_XY
    assert drawing.TIP_X - (note_x + max(map(len, drawing.THREAD_NOTE_TEXT.splitlines())) * 0.0028) >= 0.004 - 1e-12
    assert note_y == pytest.approx(drawing.SIDE_CENTER[1] - 0.008)
    # The slot value stands clear of its 3-mm-apart extension lines.
    assert drawing.END_KEEP["SlotWidth"][1] - drawing.END_CENTER[1] > 0.005
    assert drawing.DETAIL_KEEP["ReliefDia"][1] < drawing.DETAIL_CENTER[1] - spec.SHOULDER_DIA * drawing.DETAIL_SCALE[0] / 2000.0
    assert drawing.SIDE_KEEP["ThreadLength"][1] > drawing.THREAD_TOP_Y + 0.010
    tip_half = (spec.THREAD_MODEL_DIA / 2.0 - spec.TIP_CHAMFER) * drawing.SHEET_SCALE[0] / 1000.0
    assert abs(drawing.THREAD_PICK[1] - drawing.SIDE_CENTER[1]) < tip_half
    assert drawing.SEAT_X < drawing.FINISH_PICK[0] < drawing.UNDERHEAD_X
    assert drawing.SEAT_X < drawing.CENTERLINE_PICK[0] < drawing.UNDERHEAD_X
    shoulder_dim_x = drawing.SIDE_KEEP["ShoulderDia"][0]
    assert drawing.SEAT_X < shoulder_dim_x < drawing.UNDERHEAD_X
    assert abs(drawing.CENTERLINE_PICK[0] - shoulder_dim_x) > 0.010
    assert abs(drawing.FINISH_PICK[0] - shoulder_dim_x) > 0.010


def test_relief_text_reserves_its_complete_right_block_below_both_shoulders() -> None:
    x, y = drawing.DETAIL_KEEP["ReliefDia"]
    # Historical test name retained for the mutation battery. The native
    # aligned block is ROTATED, not a horizontal block to the anchor's right.
    # Translate actual r17 DisplayData metric-hull extrema, not PDF pixels.
    left, right = x - 0.0236639, x
    bottom, top = y - 0.0220281, y + 0.0220282
    assert (x, y) == pytest.approx((0.320, 0.0905))
    assert bottom > 0.066
    neck_bottom = drawing.DETAIL_CENTER[1] - spec.RELIEF_DIA * 0.010 / 2.0
    assert neck_bottom - top >= 0.0044
    thread_bottom = drawing.DETAIL_CENTER[1] - spec.THREAD_MODEL_DIA * 0.010 / 2.0
    assert thread_bottom - top == pytest.approx(0.0032468)
    assert thread_bottom - top >= 0.003
    assert right < drawing.DETAIL_LABEL_XY[0] - 0.005
    assert right < 0.4191
    assert left > drawing.DETAIL_CENTER[0] - drawing.DETAIL_RADIUS


def test_relief_width_side_full_text_clears_references_head_and_bottom_border():
    x, y = drawing.SIDE_KEEP["ReliefWidth"]
    assert (x, y) == pytest.approx((0.0859, 0.160))
    left, right, bottom, top = x - 0.006, x + 0.006, y - 0.0023, y + 0.0023
    assert left > 0.0127 and bottom > 0.0127
    under_head_top = drawing.SIDE_KEEP["UnderHeadLocation"][1] + 0.014
    assert bottom - under_head_top >= 0.005
    assert bottom - under_head_top == pytest.approx(0.0087)
    head_left = min(
        drawing.SIDE_KEEP["HeadLength"][0] - len(spec.HEAD_LENGTH_CALLOUT) * 0.0028 / 2.0,
        drawing.SIDE_KEEP["HeadDia"][0] - len(spec.HEAD_DIA_CALLOUT) * 0.0028 / 2.0,
    )
    assert head_left - right >= 0.005
    lower_neck = drawing.SIDE_CENTER[1] - spec.RELIEF_DIA * 0.003 / 2.0
    assert lower_neck - top >= 0.005
    assert drawing.SIDE_KEEP["ThreadLength"][1] - top >= 0.005
    assert "ReliefWidth" not in drawing.DETAIL_KEEP


def test_relief_width_side_native_shaped_witnesses_clear_references_thread_note_and_head():
    ink = _side_width_ink()
    assert ink[0][0][1] == pytest.approx(0.1572218750044704)
    assert {ink[1][0][0], ink[2][0][0]} == {drawing.RELIEF_END_X, drawing.SEAT_X}
    reference_ink = _axial_ink()
    for name, strokes in reference_ink.items():
        assert drawing._drawing_leaders.leader_crossings({"ReliefWidth": ink, name: strokes}) == []
    note_right = drawing.THREAD_NOTE_XY[0] + max(map(len, drawing.THREAD_NOTE_TEXT.splitlines())) * 0.0028
    thread_note = [(drawing.THREAD_PICK, (note_right, drawing.THREAD_NOTE_XY[1]))]
    assert drawing.RELIEF_END_X - max(drawing.THREAD_PICK[0], note_right) >= 0.005
    assert drawing._drawing_leaders.leader_crossings({"ReliefWidth": ink, "ThreadNote": thread_note}) == []
    head_line = drawing.SIDE_KEEP["HeadLength"][1] - 0.0055562  # r16 native underline drop
    head_ink = [
        ((drawing.UNDERHEAD_X, head_line), (drawing.HEAD_FACE_X, head_line)),
        ((drawing.UNDERHEAD_X, 0.180), (drawing.UNDERHEAD_X, head_line - 0.0013)),
        ((drawing.HEAD_FACE_X, 0.180), (drawing.HEAD_FACE_X, head_line - 0.0013)),
    ]
    assert drawing._drawing_leaders.leader_crossings({"ReliefWidth": ink, "HeadLength": head_ink}) == []


def test_relief_width_side_witness_reservations_start_below_the_real_profile_with_normal_gap():
    ink = _side_width_ink()
    for stroke, radius in (
        (ink[1], spec.RELIEF_DIA / 2.0 + spec.RELIEF_CORNER_RADIUS_MAX),
        (ink[2], spec.RELIEF_DIA / 2.0 + spec.RELIEF_LEAD),
    ):
        physical_y = drawing.SIDE_CENTER[1] - radius * 0.003
        assert physical_y - max(point[1] for point in stroke) == pytest.approx(0.001)
        assert stroke[0][0] == stroke[1][0]
        assert stroke[1][1] < ink[0][0][1] < stroke[0][1]
    # The long witnesses remain on their own corner stations, not through
    # the straight-floor interior or another view's diameter text corridor.
    floor_left = drawing._sheet_x(spec.RELIEF_END_STATION - spec.RELIEF_CORNER_RADIUS_MAX)
    floor_right = drawing._sheet_x(spec.SEAT_STATION + spec.RELIEF_LEAD)
    assert drawing.RELIEF_END_X < floor_left < floor_right < drawing.SEAT_X


def test_relief_caption_full_block_clears_crop_root_and_title_block():
    x, y = drawing.DETAIL_LABEL_XY
    assert (x, y) == pytest.approx((0.342, 0.0845))
    width = max(map(len, drawing.DETAIL_VIEW_LABEL.splitlines())) * 0.0028
    assert drawing.DETAIL_CENTER[1] - drawing.DETAIL_RADIUS - y >= 0.005
    assert x + width < 0.4191
    # Below the crop, right of the actual rotated ROOT block, above the title.
    assert x - drawing.DETAIL_KEEP["ReliefDia"][0] >= 0.020
    assert y - 2.0 * 0.0046 > 0.066


def test_thread_note_complete_left_block_clears_root_and_tip_witness() -> None:
    x, y = drawing.THREAD_NOTE_XY
    # INote insertion is the upper-left corner, not its centre.
    note_right = x + max(map(len, drawing.THREAD_NOTE_TEXT.splitlines())) * 0.0028
    assert (x, y) == pytest.approx((0.0191, 0.182))
    assert drawing.TIP_X - note_right == pytest.approx(0.004)
    root_x, root_y = drawing.DETAIL_KEEP["ReliefDia"]
    assert root_x - note_right >= 0.005
    assert y - 0.0308 - (root_y + 0.012) >= 0.005
    assert y < drawing.THREAD_PICK[1]


def test_tip_chamfer_header_and_reasons_clear_the_thread_and_relief_block() -> None:
    tip_x, tip_y = drawing.SIDE_KEEP["TipChamfer"]
    assert (tip_x, tip_y) == pytest.approx((0.0395, 0.210))
    assert tip_x == pytest.approx(drawing.TIP_X - 0.020)
    # Its native dimension line is outside the upper thread profile, not
    # laid along the screw axis.  The X45 reason clears that profile too.
    assert tip_y - 0.005 - drawing.THREAD_TOP_Y >= 0.003
    assert tip_y - 0.0065 - drawing.THREAD_TOP_Y >= 0.003
    relief_top = drawing.DETAIL_KEEP["ReliefDia"][1] + 0.0092
    assert tip_y - 0.0065 - relief_top >= 0.005
    # Upper ThreadLength's full native-shaped witness includes a 1 mm gap and
    # a conservative 1.3 mm overrun.  The tip-leg block is wholly to its left.
    tip_right = tip_x + max(len(spec.CHAMFER_CALLOUT), len("0.3 MAX")) * 0.0028 / 2.0
    assert drawing.TIP_X - tip_right >= 0.003
    assert drawing.SIDE_KEEP["ThreadLength"][1] - drawing.THREAD_TOP_Y >= 0.010
    assert tip_x - len(spec.CHAMFER_CALLOUT) * 0.0028 / 2.0 > 0.0127


def test_tip_baselines_keep_reference_rows_and_upper_thread_witnesses() -> None:
    assert drawing.SIDE_KEEP["HeadLength"] == pytest.approx((0.360, 0.1765))
    rows = {
        name: drawing.SIDE_KEEP[name][1]
        for name in ("ThreadLength", "UnderHeadLocation", "OverallLength")
    }
    assert tuple(rows.values()) == pytest.approx((0.225, 0.135, 0.116))
    assert rows["UnderHeadLocation"] - rows["OverallLength"] == pytest.approx(0.019)
    # The lower reference rows retain their established envelope floors.
    assert rows["UnderHeadLocation"] - 0.005 - 0.0013 - (
        rows["OverallLength"] - 0.005
    ) >= 0.005
    assert rows["UnderHeadLocation"] - 0.0094 - (rows["OverallLength"] + 0.006) >= 0.003
    inks = _axial_ink()
    upper = inks["ThreadLength"]
    assert all(min(a[1], b[1]) > drawing.SIDE_CENTER[1] for a, b in upper)
    assert upper[1][0][1] - drawing.THREAD_TOP_Y == pytest.approx(0.001)
    assert upper[1][1][1] - upper[0][0][1] == pytest.approx(0.0013)
    for name in ("UnderHeadLocation", "OverallLength"):
        assert drawing._drawing_leaders.leader_crossings(
            {"ThreadLength": upper, name: inks[name]}
        ) == []


def test_upper_thread_length_clears_short_tip_inner_witness_and_full_text():
    # R10b observed 2.778125 mm from requested ThreadLength text to its
    # horizontal line, not the old fabricated 5 mm.  This source reservation
    # uses that observation plus the conservative 1.3 mm tiny-leg overrun;
    # actual final native ink remains authoritative.
    observed_drop = 0.142 - 0.1392218750044704
    short_text_y = drawing.SIDE_KEEP["TipChamfer"][1]
    long_text_y = drawing.SIDE_KEEP["ThreadLength"][1]
    short_line_y = short_text_y - observed_drop
    long_line_y = long_text_y - observed_drop
    short_witness_top = short_line_y + 0.0013
    short_text_top = short_text_y + 0.0046
    assert long_text_y > short_text_y
    assert long_line_y - short_witness_top >= 0.005
    assert long_line_y - short_text_top >= 0.003
    inner = (
        (drawing.THREAD_START_X, drawing.THREAD_TOP_Y + 0.001),
        (drawing.THREAD_START_X, short_witness_top),
    )
    long_line = ((drawing.TIP_X, long_line_y), (drawing.SEAT_X, long_line_y))
    assert not drawing._drawing_leaders.segments_cross(inner, long_line)
    # The previous .205 text row puts the long line through that inner leg.
    rejected_line_y = drawing.SIDE_CENTER[1] + 0.015 - observed_drop
    assert drawing._drawing_leaders.segments_cross(
        inner, ((drawing.TIP_X, rejected_line_y), (drawing.SEAT_X, rejected_line_y))
    )


def test_upper_thread_length_clears_parent_a_full_letter_reservation():
    observed_drop = 0.142 - 0.1392218750044704
    long_line_y = drawing.SIDE_KEEP["ThreadLength"][1] - observed_drop
    mark_x, mark_y = drawing.DETAIL_PARENT_LETTER_XY
    # Actual r17 INote glyph/extent offsets translated to the adjacent ask.
    circle_x = drawing._sheet_x(drawing.DETAIL_STATION)
    circle_top = drawing.SIDE_CENTER[1] + drawing.DETAIL_PARENT_RADIUS
    assert (mark_x, mark_y) == pytest.approx((0.0839, 0.2045))
    mark_left, mark_right = mark_x - 0.0002827, mark_x + 0.0034514
    mark_bottom, mark_top = mark_y - 0.0044867, mark_y + 0.000279
    assert mark_left < circle_x < mark_right
    assert mark_bottom - circle_top == pytest.approx(0.0010133)
    assert mark_y - 0.0045257 - circle_top == pytest.approx(0.0009743)
    assert drawing.SEAT_X - mark_right >= 0.002
    assert long_line_y - mark_top >= 0.003
    assert mark_right < drawing.SIDE_KEEP["ShoulderDia"][0] - 0.003


def test_thread_note_route_stays_below_upper_thread_length_witnesses():
    note_right = drawing.THREAD_NOTE_XY[0] + max(map(len, drawing.THREAD_NOTE_TEXT.splitlines())) * 0.0028
    note_leader = [(drawing.THREAD_PICK, (note_right, drawing.THREAD_NOTE_XY[1]))]
    assert drawing._drawing_leaders.leader_crossings({
        "ThreadNote": note_leader, "ThreadLength": _axial_ink()["ThreadLength"]
    }) == []


def test_relief_detail_contains_the_actual_native_dimension_endpoints() -> None:
    assert set(drawing.DETAIL_KEEP) == {
        "ReliefDia", "ReliefLead", "ReliefCornerRadius", "SeatEdgeBreak"
    }
    assert drawing.DETAIL_REFERENCE_MM == (0.0, 0.0, drawing.DETAIL_STATION)
    assert drawing.DETAIL_STATION == pytest.approx(
        spec.SEAT_STATION + spec.RELIEF_WIDTH / 2.0
    )
    assert drawing.DETAIL_STATION == pytest.approx(58.2)
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
        (
            spec.RELIEF_END_STATION - spec.RELIEF_CORNER_RADIUS_MAX,
            spec.RELIEF_DIA / 2.0,
        ),
        (
            spec.RELIEF_END_STATION,
            spec.RELIEF_DIA / 2.0 + spec.RELIEF_CORNER_RADIUS_MAX,
        ),
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
    assert cx - radius > 0.0127 and cx + radius < 0.4191
    assert cy - radius > 0.066  # above the title block at this sheet X
    assert cx - radius > drawing.HEAD_FACE_X + 0.005
    scale = drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] / 1000.0
    lead_left = cx + (drawing.DETAIL_STATION - spec.SEAT_STATION - spec.RELIEF_LEAD) * scale
    seat_right = cx + (
        drawing.DETAIL_STATION - spec.SEAT_STATION + spec.SEAT_EDGE_BREAK_MAX
    ) * scale
    seat_half = max(len(line) for line in spec.SEAT_EDGE_BREAK_CALLOUT.splitlines()) * 0.0028 / 2.0
    assert drawing.DETAIL_KEEP["ReliefLead"][0] > lead_left + 0.030
    assert drawing.DETAIL_KEEP["SeatEdgeBreak"][0] - seat_half - seat_right >= 0.003
    assert drawing.DETAIL_KEEP["ReliefCornerRadius"] == pytest.approx((0.320, 0.1635))
    # Historical r16 observed glyph-top offset, translated to the tuned
    # anchor; this is a reservation, not proof from the next native seat.
    radius_top = drawing.DETAIL_KEEP["ReliefCornerRadius"][1] + 0.0044992
    head_underline = drawing.SIDE_KEEP["HeadLength"][1] - 0.0055562
    assert head_underline - radius_top >= 0.0029
    assert (cx, cy) == pytest.approx((0.320, 0.130))


@pytest.mark.parametrize("name", ["ReliefLead", "SeatEdgeBreak"])
def test_relief_upper_leg_full_text_keeps_three_mm_from_cropped_physical_outline(name):
    cx, cy = drawing.DETAIL_CENTER
    scale = drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] / 1000.0
    x, y = drawing.DETAIL_KEEP[name]
    text = {"ReliefLead": spec.RELIEF_LEAD_CALLOUT, "SeatEdgeBreak": spec.SEAT_EDGE_BREAK_CALLOUT}[name]
    half = max(map(len, text.splitlines())) * 0.0028 / 2.0
    # r16 reports the seat's lowest reason/underline at askY - 8.3344 mm.
    # The r17 lead's 7.3038 mm drop grows one 5.5563 mm reason-row pitch.
    drop = 0.0083344 if name == "SeatEdgeBreak" else 0.0128601
    box = (x - half, y - drop, x + half, y + 0.0073)
    upper_shoulder = cy + spec.SHOULDER_DIA * scale / 2.0
    # The shoulder's horizontal outline ends at the actual circular crop,
    # not the rectangular crop bbox's farther-right corner.
    shoulder_right = cx + math.sqrt(drawing.DETAIL_RADIUS**2 - (upper_shoulder - cy)**2)
    seat_break_end = cx + (drawing.DETAIL_STATION - spec.SEAT_STATION + spec.SEAT_EDGE_BREAK_MAX) * scale
    thread_top = cy + spec.THREAD_MODEL_DIA * scale / 2.0
    thread_end = cx + (drawing.DETAIL_STATION - spec.RELIEF_END_STATION) * scale
    floor_left = cx + (drawing.DETAIL_STATION - spec.RELIEF_END_STATION + spec.RELIEF_CORNER_RADIUS_MAX) * scale
    floor_right = cx + (drawing.DETAIL_STATION - spec.SEAT_STATION - spec.RELIEF_LEAD) * scale
    neck_top = cy + spec.RELIEF_DIA * scale / 2.0
    for stroke in (
        ((seat_break_end, upper_shoulder), (shoulder_right, upper_shoulder)),
        ((cx - drawing.DETAIL_RADIUS, thread_top), (thread_end, thread_top)),
        ((floor_left, neck_top), (floor_right, neck_top)),
    ):
        assert drawing._drawing_leaders.distance_to_box(stroke, box) >= 0.003, (stroke, box)


@pytest.mark.parametrize("name", ["ReliefLead", "SeatEdgeBreak"])
def test_relief_radius_text_has_real_2d_air_from_tiny_leg_text(name) -> None:
    radius_x, radius_y = drawing.DETAIL_KEEP["ReliefCornerRadius"]
    radius_text = f"R{spec.RELIEF_CORNER_RADIUS_MAX:g} MAX\n{spec.RELIEF_CORNER_CALLOUT}"
    radius_half = max(map(len, radius_text.splitlines())) * 0.0028 / 2.0
    radius_box = (
        radius_x - radius_half, radius_y - 0.0065,
        radius_x + radius_half, radius_y + 0.006,
    )
    text = {
        "ReliefLead": spec.RELIEF_LEAD_CALLOUT,
        "SeatEdgeBreak": spec.SEAT_EDGE_BREAK_CALLOUT,
    }[name]
    x, y = drawing.DETAIL_KEEP[name]
    half = max(map(len, text.splitlines())) * 0.0028 / 2.0
    drop = 0.0083344 if name == "SeatEdgeBreak" else 0.0128601
    box = (x - half, y - drop, x + half, y + 0.0073)
    horizontal_air = max(radius_box[0] - box[2], box[0] - radius_box[2], 0.0)
    vertical_air = max(radius_box[1] - box[3], box[1] - radius_box[3], 0.0)
    # The lead now reads below-right; the seat reads above-right. Either
    # real axis of separation can supply the unchanged 5 mm text floor.
    assert max(horizontal_air, vertical_air) >= 0.005, (radius_box, box)


@pytest.mark.parametrize("name", ["ReliefLead", "SeatEdgeBreak"])
def test_relief_radius_reason_clears_tiny_leg_witness_ends_in_2d(name) -> None:
    cx, _ = drawing.DETAIL_CENTER
    scale = drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] / 1000.0
    radius_x, radius_y = drawing.DETAIL_KEEP["ReliefCornerRadius"]
    half = len(spec.RELIEF_CORNER_CALLOUT) * 0.0028 / 2.0
    # Historical r16 reported reason baseline and 3.5 mm metric height.
    reason_box = (radius_x - half, radius_y - 0.0055563,
                  radius_x + half, radius_y - 0.0020563)
    stations = {
        "ReliefLead": (spec.SEAT_STATION, spec.SEAT_STATION + spec.RELIEF_LEAD),
        "SeatEdgeBreak": (spec.SEAT_STATION - spec.SEAT_EDGE_BREAK_MAX, spec.SEAT_STATION),
    }[name]
    # Conservative endpoint reservation from r16's actual native offsets,
    # not the old fabricated common -5 mm drop for both tiny dimensions.
    witness_y = {"ReliefLead": 0.1435, "SeatEdgeBreak": 0.1541656}[name]
    for station in stations:
        witness_x = cx + (drawing.DETAIL_STATION - station) * scale
        horizontal_air = max(reason_box[0] - witness_x, witness_x - reason_box[2], 0.0)
        vertical_air = max(reason_box[1] - witness_y, witness_y - reason_box[3], 0.0)
        assert max(horizontal_air, vertical_air) >= 0.003, (reason_box, (witness_x, witness_y))


def test_relief_radius_leader_corridor_has_no_tiny_leg_crossing() -> None:
    cx, cy = drawing.DETAIL_CENTER
    scale = drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] / 1000.0
    tangent_x = cx + (
        drawing.DETAIL_STATION - spec.RELIEF_END_STATION + spec.RELIEF_CORNER_RADIUS_MAX
    ) * scale
    flank_x = cx + (drawing.DETAIL_STATION - spec.RELIEF_END_STATION) * scale
    radius_x, radius_y = drawing.DETAIL_KEEP["ReliefCornerRadius"]
    # Every segment from the real arc up to this text stays left of both
    # tiny-leg witnesses.  Their 3 mm clearance is not traded for the radius.
    corridor_right = max(tangent_x, flank_x, radius_x)
    lead_witness_left = cx + (
        drawing.DETAIL_STATION - spec.SEAT_STATION - spec.RELIEF_LEAD
    ) * scale
    seat_witness_left = cx + (drawing.DETAIL_STATION - spec.SEAT_STATION) * scale
    assert lead_witness_left - corridor_right >= 0.003
    assert seat_witness_left - corridor_right >= 0.003


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
    # min(8.9, 6.2484 - 0.25) - 3.2 = 2.80, under the 1.5D rule.
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
    assert probe.FULL_THREAD_WORST == pytest.approx(0.246 * 25.4 - 0.25 - 3.2)
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


def _axial_ink():
    """Independent synthetic native-shaped ink, not calibrated text offsets.

    The historical r10b/r11 fixtures below are recorded native observations.
    These upper/lower witnesses deliberately include the observed 1 mm gap
    and conservative 1.3 mm overrun without claiming a final native layout.
    """
    upper_line = 0.222
    thread_bottom = 2.0 * drawing.SIDE_CENTER[1] - drawing.THREAD_TOP_Y
    return {
        "ThreadLength": [
            ((drawing.TIP_X, upper_line), (drawing.SEAT_X, upper_line)),
            ((drawing.TIP_X, drawing.THREAD_TOP_Y + 0.001),
             (drawing.TIP_X, upper_line + 0.0013)),
            ((drawing.SEAT_X, drawing.SHOULDER_TOP_Y + 0.001),
             (drawing.SEAT_X, upper_line + 0.0013)),
        ],
        "UnderHeadLocation": [
            ((drawing.TIP_X, 0.130), (drawing.UNDERHEAD_X, 0.130)),
            ((drawing.TIP_X, thread_bottom - 0.001), (drawing.TIP_X, 0.1287)),
            ((drawing.UNDERHEAD_X, 0.180), (drawing.UNDERHEAD_X, 0.1287)),
        ],
        "OverallLength": [
            ((drawing.TIP_X, 0.111), (drawing.HEAD_FACE_X, 0.111)),
            ((drawing.TIP_X, thread_bottom - 0.001), (drawing.TIP_X, 0.1097)),
            ((drawing.HEAD_FACE_X, 0.180), (drawing.HEAD_FACE_X, 0.1097)),
        ],
    }


def _side_width_ink():
    """Synthetic SIDE reservations, not a measured final native width."""
    y = drawing.SIDE_KEEP["ReliefWidth"][1] - (0.142 - 0.1392218750044704)
    cy = drawing.SIDE_CENTER[1]
    end_y = cy - (spec.RELIEF_DIA / 2.0 + spec.RELIEF_CORNER_RADIUS_MAX) * 0.003 - 0.001
    seat_y = cy - (spec.RELIEF_DIA / 2.0 + spec.RELIEF_LEAD) * 0.003 - 0.001
    return [
        ((drawing.RELIEF_END_X, y), (drawing.SEAT_X, y)),
        ((drawing.RELIEF_END_X, end_y), (drawing.RELIEF_END_X, y - 0.0013)),
        ((drawing.SEAT_X, seat_y), (drawing.SEAT_X, y - 0.0013)),
    ]

def _detail_point(x, y):
    """Translate a synthetic old-frame point, preserving physical offsets."""
    return (round(drawing.DETAIL_CENTER[0] + x - 0.115, 12),
            round(drawing.DETAIL_CENTER[1] + y - 0.068, 12))


def _detail_strokes(strokes):
    return [tuple(_detail_point(x, y) for x, y in stroke) for stroke in strokes]



def _diameter_ink():
    """Synthetic native-shaped ink, NOT a calibrated native Option A result."""
    return _detail_strokes([
        ((0.115, 0.01913993001729248), (0.115, 0.08385)),
        ((0.104, 0.0585), (0.1163, 0.0585)),
        ((0.104, 0.0775), (0.1163, 0.0775)),
        ((0.115, 0.01913993001729248), (0.1598, 0.01913993001729248)),
    ])


def _detail_ink():
    """Independent synthetic ink from the three other DETAIL dimensions."""
    return {name: _detail_strokes(strokes) for name, strokes in {
        "ReliefLead": [((0.124, 0.0785), (0.124, 0.0918)),
                       ((0.124, 0.0905), (0.127, 0.0905))],
        "SeatEdgeBreak": [((0.128, 0.089), (0.128, 0.0918)),
                          ((0.127, 0.0905), (0.128, 0.0905))],
        "ReliefCornerRadius": [((0.1044, 0.0781), (0.110, 0.094)),
                               ((0.110, 0.094), (0.115, 0.098))],
    }.items()}


# Actual SIDE IDisplayData strokes; only the affine transform below places
# them in DETAIL paper coordinates.  Neither fixture is native Option A ink.
R10B_WRONG_CARRIER_INK = [
    ((0.08190000027600003, 0.18714999998499998),
     (0.06209999999999999, 0.18714999998499998)),
    ((0.08190000027600003, 0.19285000001499997),
     (0.06209999999999999, 0.19285000001499997)),
    ((0.01904374835491182, 0.15313993001729248),
     (0.06309999999999999, 0.15313993001729248)),
    ((0.06309999999999999, 0.15313993001729248),
     (0.06309999999999999, 0.18714999998499998)),
    ((0.06309999999999999, 0.19285000001499997),
     (0.06309999999999999, 0.19920000001499996)),
]
# Unrounded r11 task.log, artifact://6394:40.
R11_SEAT_CROSSING_INK = [
    ((0.08689999999100008, 0.192850000015),
     (0.10450000000000012, 0.1928500000149999)),
    ((0.08689999999100005, 0.187149999985),
     (0.10450000000000009, 0.18714999998499993)),
    ((0.14755625164508826, 0.1531399300172925),
     (0.10350000000000012, 0.1531399300172925)),
    ((0.10350000000000012, 0.1531399300172925),
     (0.10350000000000009, 0.18714999998499993)),
    ((0.10350000000000012, 0.1928500000149999),
     (0.10350000000000012, 0.1992000000149999)),
]


def _historical_side_ink_in_detail(ink):
    # Unchanged *Right orientation: scale about the same station and axis.
    factor = 10.0 / 3.0
    assert drawing._sheet_x(drawing.DETAIL_STATION) == pytest.approx(0.0859)
    return [
        tuple((drawing.DETAIL_CENTER[0] + (x - 0.0859) * factor, drawing.DETAIL_CENTER[1] + (y - 0.190) * factor)
              for x, y in stroke)
        for stroke in ink
    ]


@pytest.mark.parametrize("reverse", [False, True])
def test_relief_diameter_ink_accepts_both_neck_surfaces_and_normal_extension_gap(reverse):
    ink, detail = _diameter_ink(), _detail_ink()
    if reverse:
        ink = [(b, a) for a, b in reversed(ink)]
        detail = {name: [(b, a) for a, b in reversed(strokes)] for name, strokes in detail.items()}
    drawing._assert_relief_diameter_ink(ink, detail)


def test_relief_diameter_ink_accepts_direct_two_surface_endpoints():
    drawing._assert_relief_diameter_ink(_detail_strokes([((0.115, 0.0585), (0.115, 0.0775))]), _detail_ink())


def test_relief_diameter_ink_does_not_compare_foreign_groups_to_each_other():
    detail = _detail_ink()
    detail["ReliefLead"].append(detail["SeatEdgeBreak"][0])
    assert drawing._drawing_leaders.leader_crossings(detail)
    drawing._assert_relief_diameter_ink(_diameter_ink(), detail)


def test_relief_diameter_ink_refuses_empty_native_ink():
    with pytest.raises(RuntimeError, match="^MHA-DT-32 relief diameter has no native ink;") as caught:
        drawing._assert_relief_diameter_ink([], _detail_ink())
    assert repr({"ReliefDia": [], **_detail_ink()}) in str(caught.value)


@pytest.mark.parametrize("name", ["ReliefLead", "SeatEdgeBreak", "ReliefCornerRadius"])
@pytest.mark.parametrize("missing", [False, True])
def test_relief_diameter_ink_refuses_each_empty_or_missing_detail_group(name, missing):
    detail = _detail_ink()
    if missing:
        del detail[name]
    else:
        detail[name] = []
    prefix = "annotation missing" if missing else "native ink empty"
    with pytest.raises(RuntimeError, match=f"^MHA-DT-32 relief detail {prefix}: {name};") as caught:
        drawing._assert_relief_diameter_ink(_diameter_ink(), detail)
    assert repr({"ReliefDia": _diameter_ink(), **detail}) in str(caught.value)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_relief_diameter_ink_refuses_nonfinite_native_coordinates(bad):
    with pytest.raises(RuntimeError, match="^MHA-DT-32 relief diameter nonfinite native ink;"):
        drawing._assert_relief_diameter_ink(_detail_strokes([((bad, 0.0585), (0.115, 0.0775))]), _detail_ink())


@pytest.mark.parametrize("name", ["ReliefLead", "SeatEdgeBreak", "ReliefCornerRadius"])
def test_relief_diameter_ink_refuses_nonfinite_foreign_native_coordinates(name):
    detail = _detail_ink()
    detail[name] = _detail_strokes([((math.nan, 0.030), (0.115, 0.030))])
    with pytest.raises(RuntimeError, match=f"^MHA-DT-32 relief detail nonfinite native ink: {name};"):
        drawing._assert_relief_diameter_ink(_diameter_ink(), detail)


@pytest.mark.parametrize("x", [0.105, 0.124])
def test_relief_diameter_ink_accepts_exact_straight_floor_boundaries(x):
    drawing._assert_relief_diameter_ink(_detail_strokes([((x, 0.0585), (x, 0.0775))]), _detail_ink())


@pytest.mark.parametrize("x", [0.104999, 0.124001])
def test_relief_diameter_ink_refuses_vertical_stroke_outside_straight_floor(x):
    ink = _detail_strokes([((x, 0.0585), (x, 0.0775))])
    with pytest.raises(RuntimeError, match="lacks a vertical stroke within the straight floor") as caught:
        drawing._assert_relief_diameter_ink(ink, _detail_ink())
    assert "floor_x=" in str(caught.value) and "neck_y=" in str(caught.value)
    assert repr(ink) in str(caught.value)


@pytest.mark.parametrize("surface", ["lower", "upper"])
def test_relief_diameter_ink_refuses_shortened_vertical_span_independently(surface):
    bottom = 0.058651 if surface == "lower" else 0.0585
    top = 0.077349 if surface == "upper" else 0.0775
    ink = [*_detail_strokes([((0.115, bottom), (0.115, top))]), *_diameter_ink()[1:]]
    with pytest.raises(RuntimeError, match="spanning both neck surfaces;"):
        drawing._assert_relief_diameter_ink(ink, _detail_ink())


def test_relief_diameter_ink_refuses_one_arrow_diagonal_surrogate():
    with pytest.raises(RuntimeError, match="lacks a vertical stroke"):
        drawing._assert_relief_diameter_ink(_detail_strokes([((0.115, 0.0585), (0.120, 0.0775))]), _detail_ink())


@pytest.mark.parametrize("surface,index", [("lower", 1), ("upper", 2)])
def test_relief_diameter_ink_refuses_missing_surface_association_independently(surface, index):
    ink = _diameter_ink()
    del ink[index]
    with pytest.raises(RuntimeError, match=f"^MHA-DT-32 relief diameter missing {surface} neck association;") as caught:
        drawing._assert_relief_diameter_ink(ink, _detail_ink())
    assert "expected_surface_y=" in str(caught.value) and repr(ink) in str(caught.value)


@pytest.mark.parametrize("surface,index", [("lower", 1), ("upper", 2)])
@pytest.mark.parametrize("fault", ["y", "disconnected", "wrong-floor-end"])
def test_relief_diameter_ink_refuses_floating_surface_extension(surface, index, fault):
    ink = _diameter_ink()
    (x0, y), (x1, _) = ink[index]
    if fault == "y":
        ink[index] = ((x0, y + 0.000151), (x1, y + 0.000151))
        message = f"missing {surface} neck association;"
    elif fault == "disconnected":
        ink[index] = (_detail_point(0.106, 0.068)[0], y), (_detail_point(0.110, 0.068)[0], y)
        message = f"floating {surface} neck extension;"
    else:
        # Outside the straight floor and NOT one normal gap from its end.
        ink[index] = (_detail_point(0.1045, 0.068)[0], y), (_detail_point(0.1163, 0.068)[0], y)
        message = f"floating {surface} neck extension;"
    with pytest.raises(RuntimeError, match=message) as caught:
        drawing._assert_relief_diameter_ink(ink, _detail_ink())
    assert repr(ink) in str(caught.value)


@pytest.mark.parametrize("surface,index", [("lower", 1), ("upper", 2)])
def test_relief_diameter_ink_never_treats_one_mm_extension_gap_as_surface_y_slack(surface, index):
    ink = _diameter_ink()
    ink[index] = tuple((x, y + 0.001) for x, y in ink[index])
    with pytest.raises(RuntimeError, match=f"missing {surface} neck association;"):
        drawing._assert_relief_diameter_ink(ink, _detail_ink())


@pytest.mark.parametrize("surface,index", [("lower", 1), ("upper", 2)])
def test_relief_diameter_ink_accepts_surface_tolerance_without_one_mm_y_slack(surface, index):
    ink = _diameter_ink()
    ink[index] = tuple((x, y + 0.000149) for x, y in ink[index])
    drawing._assert_relief_diameter_ink(ink, _detail_ink())


def test_relief_diameter_ink_refuses_honestly_transformed_r10b_wrong_floor():
    ink = _historical_side_ink_in_detail(R10B_WRONG_CARRIER_INK)
    with pytest.raises(RuntimeError, match="lacks a vertical stroke within the straight floor") as caught:
        drawing._assert_relief_diameter_ink(ink, _detail_ink())
    assert repr(ink) in str(caught.value)


def test_relief_diameter_ink_refuses_honestly_transformed_r11_seat_crossing():
    ink = _historical_side_ink_in_detail(R11_SEAT_CROSSING_INK)
    with pytest.raises(RuntimeError, match="^MHA-DT-32 relief diameter ink crosses the seat face/witness;") as caught:
        drawing._assert_relief_diameter_ink(ink, _detail_ink())
    assert "crossing=" in str(caught.value) and repr(ink) in str(caught.value)


@pytest.mark.parametrize("corner,x,bottom,top", [
    ("seat face/witness", 0.127, 0.048, 0.088),
    ("thread-side corner", 0.103, 0.053775, 0.082225),
])
@pytest.mark.parametrize("side", ["lower", "upper", "middle"])
@pytest.mark.parametrize("vertical", [False, True])
def test_relief_diameter_ink_refuses_each_corner_and_both_clearance_sides(corner, x, bottom, top, side, vertical):
    y = {"lower": bottom - 0.0019, "upper": top + 0.0019, "middle": (bottom + top) / 2.0}[side]
    crossing = _detail_strokes([((x, y - 0.0002), (x, y + 0.0002)) if vertical else ((x - 0.001, y), (x + 0.001, y))])[0]
    ink = [*_diameter_ink(), crossing]
    with pytest.raises(RuntimeError, match=f"^MHA-DT-32 relief diameter ink crosses the {corner};") as caught:
        drawing._assert_relief_diameter_ink(ink, _detail_ink())
    assert "crossing=" in str(caught.value) and "physical_y=" in str(caught.value)
    assert repr(crossing) in str(caught.value)


@pytest.mark.parametrize("x,bottom,top", [(0.127, 0.048, 0.088), (0.103, 0.053775, 0.082225)])
@pytest.mark.parametrize("upper", [False, True])
def test_relief_diameter_ink_allows_corner_strokes_outside_two_mm_air(x, bottom, top, upper):
    y = top + 0.0021 if upper else bottom - 0.0021
    drawing._assert_relief_diameter_ink([*_diameter_ink(), *_detail_strokes([((x - 0.0002, y), (x + 0.0002, y))])], _detail_ink())


def _foreign_junction(junction):
    midpoint = _detail_point(0.115, 0.030)
    if junction == "crossing":
        return (_detail_point(0.113, 0.030), _detail_point(0.117, 0.030))
    if junction == "tee":
        return (midpoint, _detail_point(0.117, 0.030))
    return (_detail_point(0.115, 0.028), _detail_point(0.115, 0.032))


@pytest.mark.parametrize("name", ["ReliefLead", "SeatEdgeBreak", "ReliefCornerRadius"])
@pytest.mark.parametrize("junction", ["crossing", "tee", "overlap"])
def test_relief_diameter_ink_refuses_each_detail_cross_tee_overlap(name, junction):
    detail = _detail_ink()
    foreign = _foreign_junction(junction)
    detail[name].append(foreign)
    with pytest.raises(RuntimeError, match=f"^MHA-DT-32 relief diameter foreign detail ink: {name};") as caught:
        drawing._assert_relief_diameter_ink(_diameter_ink(), detail)
    assert f"('ReliefDia', '{name}')" in str(caught.value)
    assert repr(foreign) in str(caught.value)
    assert repr({"ReliefDia": _diameter_ink(), **detail}) in str(caught.value)
    assert "crossings=" in str(caught.value) and "crossing_segments=" in str(caught.value)


def test_relief_diameter_ink_allows_horizontal_underline_below_model_with_width_on_side():
    assert "ReliefWidth" in drawing.SIDE_KEEP and "ReliefWidth" not in drawing.DETAIL_KEEP
    drawing._assert_relief_diameter_ink(_diameter_ink(), _detail_ink())


@pytest.fixture
def relief_styles(monkeypatch, relief_native):
    """Strict native members; VOID second-arrow setter, integer leader status."""
    from types import SimpleNamespace

    class Dimension:
        __slots__ = ("FullName", "SystemValue")

        def __init__(self):
            self.FullName = "ReliefDia@ScrewProfile@Part4.Part"
            self.SystemValue = 0.0019

    class Display:
        __slots__ = ("values", "ignore", "_type", "dimension", "native_reads", "writes", "broken_status")

        def __init__(self):
            self.values = {"Diametric": False, "ArrowSide": 2, "CenterText": True,
                           "SolidLeader": False, "GetUseDocBrokenLeader": True,
                           "GetBrokenLeader2": 2, "GetUseDocSecondArrow": True, "GetSecondArrow": False}
            self.ignore = set()
            self._type = 6
            self.dimension = Dimension()
            self.native_reads, self.writes = [], []
            self.broken_status = 0

        def read(self, key):
            self.native_reads.append(key)
            return self.values[key]

        def write(self, key, value):
            self.writes.append((key, value))
            if key not in self.ignore:
                self.values[key] = value

        @property
        def Type2(self):
            self.native_reads.append("Type2")
            return self._type

        def GetDimension2(self, index):
            assert index == 0
            self.native_reads.append(("GetDimension2", index))
            return self.dimension

        Diametric = property(lambda self: self.read("Diametric"), lambda self, value: self.write("Diametric", value))
        ArrowSide = property(lambda self: self.read("ArrowSide"), lambda self, value: self.write("ArrowSide", value))
        CenterText = property(lambda self: self.read("CenterText"), lambda self, value: self.write("CenterText", value))
        SolidLeader = property(lambda self: self.read("SolidLeader"), lambda self, value: self.write("SolidLeader", value))

        def SetSecondArrow(self, use_doc, second):
            assert use_doc is False and second is True
            self.writes.append(("SetSecondArrow", use_doc, second))
            for key, value in (("GetUseDocSecondArrow", use_doc), ("GetSecondArrow", second)):
                if key not in self.ignore:
                    self.values[key] = value
            # Native VOID setter: no invented bool status.

        def SetBrokenLeader2(self, use_doc, style):
            assert use_doc is False and type(style) is int and style == 1
            self.writes.append(("SetBrokenLeader2", use_doc, style))
            for key, value in (("GetUseDocBrokenLeader", use_doc), ("GetBrokenLeader2", style)):
                if key not in self.ignore:
                    self.values[key] = value
            return self.broken_status

        def GetUseDocBrokenLeader(self):
            return self.read("GetUseDocBrokenLeader")

        def GetBrokenLeader2(self):
            return self.read("GetBrokenLeader2")

        def GetUseDocSecondArrow(self):
            return self.read("GetUseDocSecondArrow")

        def GetSecondArrow(self):
            return self.read("GetSecondArrow")

    class Annotation:
        __slots__ = ("name", "display", "position_ok", "positions")

        def __init__(self, name):
            self.name, self.display = name, Display()
            self.position_ok, self.positions = True, []

        def GetSpecificAnnotation(self):
            return self.display

        def SetPosition2(self, x, y, z):
            self.positions.append((x, y, z))
            return self.position_ok

    annotations = [Annotation(name) for name in (
        "ReliefDia", "ReliefWidth", "ReliefLead", "SeatEdgeBreak", "ReliefCornerRadius",
        "ThreadLength", "UnderHeadLocation", "OverallLength",
    )]
    state = SimpleNamespace(
        native=relief_native, annotations=annotations, ink_reads=[],
        inks={"ReliefDia": _diameter_ink(), **_detail_ink()},
    )
    original_bind = drawing._early_bound

    def bind(value, interface):
        classes = {"IAnnotation": Annotation, "IDisplayDimension": Display, "IDimension": Dimension}
        if interface in classes:
            assert isinstance(value, classes[interface])
            return value
        return original_bind(value, interface)

    def ink(annotation):
        assert isinstance(annotation, Annotation)
        assert any(annotation is item for item in state.annotations)
        assert state.native.model.rebuilds == 1
        state.ink_reads.append(annotation)
        return state.inks[annotation.name]

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing._drawing_leaders, "dimension_segments", ink)
    return state


def test_style_relief_dimensions_authors_two_arrows_and_reads_all_four_actual_detail_groups(relief_styles):
    state = relief_styles
    drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    diameter, width, lead, edge, radius, *axial = state.annotations
    assert [item.name for item in state.ink_reads] == ["ReliefDia", "ReliefLead", "SeatEdgeBreak", "ReliefCornerRadius"]
    assert diameter.display.writes == [
        ("Diametric", True), ("ArrowSide", 0), ("CenterText", False),
        ("SetSecondArrow", False, True), ("SolidLeader", True), ("SetBrokenLeader2", False, 1),
    ]
    readback = ["Diametric", "ArrowSide", "CenterText", "SolidLeader", "GetUseDocBrokenLeader",
                "GetBrokenLeader2", "GetUseDocSecondArrow", "GetSecondArrow"]
    assert diameter.display.native_reads == ["Type2", ("GetDimension2", 0), *readback] * 2
    for annotation in (diameter, lead, edge):
        assert annotation.positions == [(*drawing.DETAIL_KEEP[annotation.name], 0.0)]
    for annotation in (lead, edge):
        assert annotation.display.values["CenterText"] is False
        assert annotation.display.values["ArrowSide"] == 1
    for unrelated in (width, radius, *axial):
        assert unrelated.positions == [] and unrelated.display.writes == []
        assert unrelated.display.native_reads == []
    assert state.native.model.rebuilds == 1


def test_r13_detail_diameter_type_6_keeps_ownership_style_and_ink_checks(relief_styles):
    state = relief_styles
    display = state.annotations[0].display
    # R13 observed Type2=6 before the old type-15 guard stopped execution.
    # The remaining fake values are contracts, not native render evidence.
    display._type = 6
    drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    assert display.native_reads.count("Type2") == 2
    assert display.native_reads.count(("GetDimension2", 0)) == 2
    assert display.native_reads.count("GetSecondArrow") == 2
    assert state.native.model.rebuilds == 1
    assert [item.name for item in state.ink_reads] == ["ReliefDia", "ReliefLead", "SeatEdgeBreak", "ReliefCornerRadius"]


def test_relief_style_fake_refuses_nonexistent_or_wrong_owner_members(relief_styles):
    display = relief_styles.annotations[0].display
    for member in ("DisplayAsLinear", "OffsetText", "GetType2"):
        with pytest.raises(AttributeError):
            getattr(display, member)
    with pytest.raises(AttributeError):
        display.Type2 = 6
    with pytest.raises(AssertionError):
        drawing._early_bound(display, "IAnnotation")


@pytest.mark.parametrize("kind", [0, 2, 5, 14, 15])
def test_relief_carrier_refuses_non_diameter_native_type_before_style_or_ink(relief_styles, kind):
    state = relief_styles
    display = state.annotations[0].display
    display._type = kind
    with pytest.raises(RuntimeError, match=f"^MHA-DT-32 relief diameter wrong native type: Type2={kind},"):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    assert display.native_reads == ["Type2"] and display.writes == []
    assert state.ink_reads == [] and state.native.model.rebuilds == 0


@pytest.mark.parametrize("full_name", ["Other@ScrewProfile@Part4.Part", "ReliefDia@OtherProfile@Part4.Part",
                                       "ReliefDia@ScrewProfileSpoof@Part4.Part", "ReliefDia"])
def test_relief_carrier_refuses_wrong_native_name_and_owner_independently(relief_styles, full_name):
    state = relief_styles
    state.annotations[0].display.dimension.FullName = full_name
    with pytest.raises(RuntimeError, match="^MHA-DT-32 relief diameter wrong native owner:") as caught:
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    assert repr(full_name) in str(caught.value)
    assert state.annotations[0].display.writes == [] and state.ink_reads == []
    assert state.native.model.rebuilds == 0


@pytest.mark.parametrize("value", [0.00095, 0.001900002, math.nan, math.inf])
def test_relief_carrier_refuses_wrong_native_value_independently(relief_styles, value):
    state = relief_styles
    state.annotations[0].display.dimension.SystemValue = value
    with pytest.raises(RuntimeError, match="^MHA-DT-32 relief diameter wrong native value:") as caught:
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    assert f"SystemValue={value!r}" in str(caught.value)
    assert state.annotations[0].display.writes == [] and state.ink_reads == []


def test_relief_carrier_refuses_missing_underlying_native_dimension(relief_styles):
    state = relief_styles
    state.annotations[0].display.dimension = None
    with pytest.raises(RuntimeError, match="^MHA-DT-32 relief diameter missing native model dimension$"):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    assert state.annotations[0].display.writes == [] and state.ink_reads == []


@pytest.mark.parametrize("member", ["Diametric", "ArrowSide", "CenterText", "SolidLeader",
                                    "GetUseDocBrokenLeader", "GetBrokenLeader2",
                                    "GetUseDocSecondArrow", "GetSecondArrow"])
def test_relief_two_arrow_style_refuses_each_independent_native_readback(relief_styles, member):
    state = relief_styles
    state.annotations[0].display.ignore.add(member)
    with pytest.raises(RuntimeError, match="^MHA-DT-32 relief diameter native two-arrow style did not persist:") as caught:
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    assert member in str(caught.value) and "actual=" in str(caught.value)
    assert state.ink_reads == [] and state.native.model.rebuilds == 0


@pytest.mark.parametrize("status", [-1, 1])
def test_relief_two_arrow_style_refuses_nonzero_native_leader_status(relief_styles, status):
    state = relief_styles
    state.annotations[0].display.broken_status = status
    with pytest.raises(RuntimeError, match=f"solid aligned leader rejected: SetBrokenLeader2 status={status}"):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    assert state.ink_reads == [] and state.native.model.rebuilds == 0


@pytest.mark.parametrize("fault", ["style", "type", "value", "owner"])
def test_relief_native_readbacks_are_rechecked_after_rebuild(relief_styles, monkeypatch, fault):
    state = relief_styles
    display = state.annotations[0].display
    model_type = type(state.native.model)
    original = model_type.EditRebuild3

    def rebuild(model):
        result = original(model)
        if fault == "style":
            display.values["GetSecondArrow"] = False
        elif fault == "type":
            display._type = 15
        elif fault == "value":
            display.dimension.SystemValue = 0.00095
        else:
            display.dimension.FullName = "Other@ScrewProfile"
        return result

    monkeypatch.setattr(model_type, "EditRebuild3", rebuild)
    with pytest.raises(RuntimeError, match="^MHA-DT-32 relief diameter"):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    assert state.ink_reads == [] and state.native.model.rebuilds == 1


@pytest.mark.parametrize("name", ["ReliefDia", "ReliefLead", "SeatEdgeBreak"])
def test_style_relief_dimensions_refuses_set_position(relief_styles, name):
    state = relief_styles
    next(item for item in state.annotations if item.name == name).position_ok = False
    with pytest.raises(RuntimeError, match=f"^cannot position the MHA-DT-32 {name} text$"):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)


@pytest.mark.parametrize("name", ["ReliefLead", "SeatEdgeBreak"])
@pytest.mark.parametrize("member", ["CenterText", "ArrowSide"])
def test_style_relief_dimensions_refuses_ignored_tiny_leg_property(relief_styles, name, member):
    state = relief_styles
    next(item for item in state.annotations if item.name == name).display.ignore.add(member)
    with pytest.raises(RuntimeError, match=f"^{name} arrows/centring did not take:"):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)


@pytest.mark.parametrize("name", ["ReliefDia", "ReliefLead", "SeatEdgeBreak"])
def test_style_relief_dimensions_refuses_missing_registered_style(relief_styles, name):
    state = relief_styles
    with pytest.raises(RuntimeError, match=rf"^relief dimension styles not applied: \['{name}'\]$"):
        drawing.style_relief_dimensions(state.native.adapter, [item for item in state.annotations if item.name != name])
    assert state.ink_reads == []


@pytest.mark.parametrize("name", ["ReliefCornerRadius"])
def test_style_relief_dimensions_refuses_missing_unstyled_detail_annotation(relief_styles, name):
    state = relief_styles
    with pytest.raises(RuntimeError, match=f"^MHA-DT-32 relief detail annotation missing: {name};"):
        drawing.style_relief_dimensions(state.native.adapter, [item for item in state.annotations if item.name != name])
    assert state.ink_reads == [] and state.native.model.rebuilds == 0


@pytest.mark.parametrize("name", ["ReliefDia", "ReliefLead", "SeatEdgeBreak", "ReliefCornerRadius"])
def test_style_relief_dimensions_refuses_each_empty_actual_native_group(relief_styles, name):
    state = relief_styles
    state.inks[name] = []
    message = "diameter has no native ink;" if name == "ReliefDia" else f"detail native ink empty: {name};"
    with pytest.raises(RuntimeError, match=f"^MHA-DT-32 relief {message}"):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    assert [item.name for item in state.ink_reads] == ["ReliefDia", *drawing.DETAIL_DIMENSIONS]


@pytest.mark.parametrize("name", ["ReliefLead", "SeatEdgeBreak", "ReliefCornerRadius"])
@pytest.mark.parametrize("junction", ["crossing", "tee", "overlap"])
def test_style_relief_dimensions_refuses_each_actual_detail_cross_tee_overlap(relief_styles, name, junction):
    state = relief_styles
    state.inks[name].append(_foreign_junction(junction))
    with pytest.raises(RuntimeError, match=f"^MHA-DT-32 relief diameter foreign detail ink: {name};"):
        drawing.style_relief_dimensions(state.native.adapter, state.annotations)
    assert [item.name for item in state.ink_reads] == ["ReliefDia", *drawing.DETAIL_DIMENSIONS]


@pytest.mark.parametrize("corner,x,y", [("seat face/witness", 0.127, 0.048), ("thread-side corner", 0.103, 0.053775)])
def test_style_relief_dimensions_does_not_bypass_either_corner_guard(relief_styles, corner, x, y):
    state = relief_styles
    state.inks["ReliefDia"].extend(_detail_strokes([((x - 0.001, y), (x + 0.001, y))]))
    with pytest.raises(RuntimeError, match=f"^MHA-DT-32 relief diameter ink crosses the {corner};"):
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


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "native-crlf"])
def test_relief_view_label_accepts_native_line_endings_only(relief_native, monkeypatch, newline):
    state = relief_native
    original = state.Note.GetText
    monkeypatch.setattr(
        state.Note, "GetText", lambda note: original(note).replace("\n", newline)
    )
    drawing.label_relief_view(state.adapter, state.view)
    assert state.note_calls == [(drawing.DETAIL_VIEW_LABEL, *drawing.DETAIL_LABEL_XY)]
    assert [note.GetText() for note in state.view.notes] == [
        drawing.DETAIL_VIEW_LABEL.replace("\n", newline)
    ]
    assert drawing._note_texts(state.view) == [drawing.DETAIL_VIEW_LABEL]


def test_relief_view_label_rejects_duplicate_mixed_lf_and_crlf_notes(relief_native):
    state = relief_native
    native_text = drawing.DETAIL_VIEW_LABEL.replace("\n", "\r\n")
    state.view.notes.append(state.Note(native_text))
    with pytest.raises(RuntimeError, match="^relief view label did not land in the relief view: "):
        drawing.label_relief_view(state.adapter, state.view)
    assert [note.GetText() for note in state.view.notes] == [native_text, drawing.DETAIL_VIEW_LABEL]
    assert drawing._note_texts(state.view) == [drawing.DETAIL_VIEW_LABEL] * 2


@pytest.mark.parametrize("native_text", [
    "DETAIL B\r\nSCALE 10:1",
    "DETAIL A\r\nSCALE 1:1",
    " DETAIL A\r\nSCALE 10:1",
    "DETAIL A\rSCALE 10:1",
    "DETAIL A\r\nSCALE 10:1\n",
])
def test_relief_view_label_rejects_other_native_text_changes(relief_native, monkeypatch, native_text):
    state = relief_native

    def add(adapter, text, x, y):
        assert adapter is state.adapter and text == drawing.DETAIL_VIEW_LABEL
        assert (x, y) == drawing.DETAIL_LABEL_XY
        note = state.Note(native_text)
        state.view.notes.append(note)
        return note

    monkeypatch.setattr(drawing, "add_note", add)
    with pytest.raises(RuntimeError, match="^relief view label did not land in the relief view: "):
        drawing.label_relief_view(state.adapter, state.view)


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
        "style_relief_dimensions": ["adapter", "detail_annotations"],
        "_add_shoulder_finish": ["adapter", "side"],
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


def test_build_imports_profile_diameter_only_directly_into_detail_and_keeps_four_views_hlr():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body
                 if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    curated = {ast.unparse(node.args[1]): node for node in calls
               if isinstance(node.func, ast.Name) and node.func.id == "curate_view_dimensions"}
    assert set(curated) == {"side", "end", "detail"}
    for view, keep_name in (("side", "SIDE_KEEP"), ("end", "END_KEEP"), ("detail", "DETAIL_KEEP")):
        keywords = {keyword.arg: ast.unparse(keyword.value) for keyword in curated[view].keywords}
        assert keywords["keep"] == keep_name
        assert keywords["dimensions_by_feature"] == "DRAWING_DIMENSIONS"
    assert "ReliefDia" not in drawing.SIDE_KEEP
    assert "ReliefDia" in drawing.DETAIL_KEEP
    assert "ReliefWidth" in drawing.SIDE_KEEP and "ReliefWidth" not in drawing.DETAIL_KEEP
    assert drawing.DETAIL_DIMENSIONS == ("ReliefLead", "SeatEdgeBreak", "ReliefCornerRadius")
    hlr = [node for node in build.body
           if isinstance(node, ast.For)
           and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                   and call.func.id == "set_hidden_lines_removed" for call in ast.walk(node))]
    assert len(hlr) == 1
    assert ast.unparse(hlr[0].iter) == "(side, end, detail, iso)"
    style = next(node for node in calls
                 if isinstance(node.func, ast.Name) and node.func.id == "style_relief_dimensions")
    finalize = next(node for node in calls
                    if isinstance(node.func, ast.Name) and node.func.id == "finalize_drawing")
    assert curated["detail"].lineno < style.lineno < finalize.lineno



def _approved_detail_ink():
    """r17 ink translated for r18 text/row changes, not new native-seat proof."""
    return {
        "ReliefDia": [
            ((0.311, 0.1205), (0.321, 0.1205)),
            ((0.311, 0.1395), (0.321, 0.1395)),
            ((0.320, 0.1205), (0.320, 0.0684719)),
            ((0.320, 0.1205), (0.320, 0.1395)),
        ],
        "ReliefCornerRadius": [
            ((0.3094214, 0.1434145), (0.3050299, 0.1579438)),
            ((0.310, 0.1415), (0.3094214, 0.1434145)),
            ((0.3050299, 0.1579438), (0.3333826, 0.1579438)),
        ],
        "ReliefLead": [
            ((0.332, 0.1435), (0.332, 0.0921399)),
            ((0.329, 0.1405), (0.329, 0.0921399)),
            ((0.332, 0.0931399), (0.3947587, 0.0931399)),
            ((0.332, 0.0931399), (0.329, 0.0931399)),
            ((0.329, 0.0931399), (0.32265, 0.0931399)),
        ],
        "SeatEdgeBreak": [
            ((0.333, 0.149), (0.333, 0.1521656)),
            ((0.332, 0.150), (0.332, 0.1541656)),
            ((0.333, 0.1531656), (0.4130875, 0.1531656)),
            ((0.333, 0.1531656), (0.332, 0.1531656)),
            ((0.332, 0.1531656), (0.32565, 0.1531656)),
        ],
    }


def _ink_annotation(name="generated", *, texts=(), lines=(), **extra):
    return {"name": name, "visible": 1, "owner_type": 0,
            "display": {"texts": list(texts), "lines": list(lines)}, **extra}


def _ink_sheet(*annotations, sheet_annotations=(), layers=None):
    return {"sheet": "Sheet1", "views": [{"annotations": list(annotations)}],
            "sheet_annotations": list(sheet_annotations), "layers": layers or {}}


def _actual_text(x=0.1, y=0.1, *, angle=0.0, width=0.02):
    return {"t": "ACTUAL", "pos": [x, y, 0], "h": 0.0035,
            "w": width, "ang": angle, "ref": 1}


def _actual_line(a, b):
    return [0, 0, 0, 0, *a, 0, *b, 0]


def test_approved_actual_offset_reservations_clear_border_and_all_detail_pairs():
    groups = _approved_detail_ink()
    annotations = [_ink_annotation(name, lines=[_actual_line(a, b) for a, b in strokes])
                   for name, strokes in groups.items()]
    drawing._assert_generated_annotation_ink([_ink_sheet(*annotations)], groups)
    drawing._assert_relief_diameter_ink(groups["ReliefDia"], {
        name: groups[name] for name in drawing.DETAIL_DIMENSIONS
    })


@pytest.mark.parametrize("side,x,y", [
    ("left", 0.0126, 0.1), ("right", 0.4192, 0.1),
    ("bottom", 0.1, 0.0126), ("top", 0.1, 0.2668),
])
def test_generated_actual_ink_refuses_every_border_not_just_anchor(side, x, y):
    annotation = _ink_annotation(side, lines=[_actual_line((0.1, 0.1), (x, y))], pos=[0.1, 0.1, 0])
    with pytest.raises(RuntimeError, match=f"Sheet1/{side}: actual ink outside inner border") as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet(annotation)], _approved_detail_ink())
    assert str(x) in str(caught.value) and str(y) in str(caught.value)
    assert "inner=(0.0127, 0.0127, 0.4191, 0.2667)" in str(caught.value)


def test_r16_actual_rotated_root_text_and_line_collect_both_border_offenders():
    # Actual r16 GetDisplayData, not requested (.115,.032) text anchors.
    text = {"t": "BELOW #4-40 ROOT", "pos": [0.0948361, 0.0099719, -0.001],
            "h": 0.0035, "w": 0.0440563, "ang": 1.5707963, "ref": 1}
    line = _actual_line((0.115, 0.0585), (0.115, 0.0099719))
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_generated_annotation_ink([
            _ink_sheet(_ink_annotation("r16 rotated root", texts=[text]),
                       _ink_annotation("r16 root line", lines=[line]))
        ], _approved_detail_ink())
    message = str(caught.value)
    assert "r16 rotated root: actual ink outside" in message
    assert "r16 root line: actual ink outside" in message
    assert message.count("outside inner border") == 2
    moved = {**text, "pos": [text["pos"][0] + 0.205, text["pos"][1] + 0.062, -0.001]}
    drawing._assert_generated_annotation_ink([
        _ink_sheet(_ink_annotation("moved root", texts=[moved]))
    ], _approved_detail_ink())


@pytest.mark.parametrize("first,second", [
    ("ReliefCornerRadius", "ReliefLead"), ("ReliefCornerRadius", "SeatEdgeBreak"),
    ("ReliefLead", "SeatEdgeBreak"), ("ReliefDia", "ReliefCornerRadius"),
    ("ReliefDia", "ReliefLead"), ("ReliefDia", "SeatEdgeBreak"),
])
@pytest.mark.parametrize("junction", ["crossing", "tee", "overlap"])
def test_generated_all_detail_foreign_pairs_refuse_cross_tee_overlap(first, second, junction):
    groups = _approved_detail_ink()
    groups[first] = [((0.2, 0.1), (0.2, 0.12))]
    other = {"crossing": ((0.19, 0.11), (0.21, 0.11)),
             "tee": ((0.2, 0.11), (0.21, 0.11)),
             "overlap": ((0.2, 0.105), (0.2, 0.115))}[junction]
    groups[second] = [other]
    with pytest.raises(RuntimeError, match="foreign ink crossing") as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet()], groups)
    assert first in str(caught.value) and second in str(caught.value)
    assert repr(other) in str(caught.value)


def test_r16_actual_radius_leader_crosses_actual_lead_underline():
    # Unchanged r16 DisplayData line endpoints from the native layout audit.
    groups = _approved_detail_ink()
    radius = ((0.1044214, 0.0814145), (0.1000299, 0.0959438))
    lead = ((0.124, 0.0881962), (0.0582413, 0.0881962))
    groups["ReliefCornerRadius"], groups["ReliefLead"] = [radius], [lead]
    with pytest.raises(RuntimeError, match="ReliefCornerRadius vs ReliefLead") as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet()], groups)
    assert repr(radius) in str(caught.value) and repr(lead) in str(caught.value)


@pytest.mark.parametrize("fault", [
    "missing-display", "empty-display", "missing-width", "missing-height",
    "missing-position", "missing-angle", "nan-text", "inf-line", "short-line",
    "short-arc", "short-polyline", "short-polygon", "short-triangle", "bad-arrow",
    "bad-leader", "bad-note", "unsupported-ellipse",
])
def test_generated_actual_ink_fails_closed_without_guessed_bounds(fault):
    annotation = _ink_annotation(fault, texts=[_actual_text()])
    display = annotation["display"]
    if fault == "missing-display":
        del annotation["display"]
    elif fault == "empty-display":
        annotation["display"] = {}
    elif fault.startswith("missing-"):
        key = {"missing-width": "w", "missing-height": "h",
               "missing-position": "pos", "missing-angle": "ang"}[fault]
        del display["texts"][0][key]
    elif fault == "nan-text":
        display["texts"][0]["pos"][0] = math.nan
    elif fault == "inf-line":
        display["lines"] = [_actual_line((math.inf, 0.1), (0.2, 0.1))]
    elif fault.startswith("short-"):
        key = {"short-line": "lines", "short-arc": "arcs", "short-polyline": "polylines",
               "short-polygon": "polygons", "short-triangle": "triangles"}[fault]
        display[key] = [[0, 0]]
    elif fault == "bad-arrow":
        display["arrows"] = [[0.1, 0.1, 0, 0, 0, 0, 0.003, 0.001]]
    elif fault == "unsupported-ellipse":
        # The shared collector exposes ellipses, but display_box has no
        # ellipse hull. Valid text alongside one must not hide unknown ink.
        display["ellipses"] = [[0.0] * 20]
    elif fault == "bad-leader":
        annotation["leaders"] = [[0.1, 0.1, math.nan, 0.2, 0.2, 0]]
    else:
        annotation["note"] = {"extent": []}
    with pytest.raises(RuntimeError, match=f"Sheet1/{fault}:"):
        drawing._assert_generated_annotation_ink([_ink_sheet(annotation)], _approved_detail_ink())


def test_generated_ink_collects_missing_nonfinite_border_and_every_pair_in_one_refusal():
    groups = {name: [((0.2, 0.1), (0.2, 0.12))] for name in drawing.DETAIL_KEEP}
    groups["ReliefDia"] = []
    groups["ReliefLead"] = [((math.nan, 0.1), (0.2, 0.1))]
    sheet = _ink_sheet(
        _ink_annotation("bad", texts=[{**_actual_text(), "w": math.inf}]),
        _ink_annotation("outside", lines=[_actual_line((0.1, 0.1), (0.1, 0.001))]),
        _ink_annotation("missing", display={}),
    )
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_generated_annotation_ink([sheet], groups, collection_errors=["inventory refusal"])
    message = str(caught.value)
    for label in ("inventory refusal", "Sheet1/bad", "Sheet1/outside", "Sheet1/missing",
                  "DETAIL/ReliefDia", "DETAIL/ReliefLead", "ReliefCornerRadius vs SeatEdgeBreak"):
        assert label in message
    assert message.count("generated annotation ink violations") == 1


def test_generated_border_reuses_printability_visibility_and_sheet_ownership():
    outside = _ink_annotation(lines=[_actual_line((0, 0), (0.001, 0.001))])
    sheet = _ink_sheet(
        {**outside, "visible": 2}, {**outside, "layer": "nonprinting"},
        sheet_annotations=[{**outside, "owner_type": 2}, {**outside, "owner_type": 0}],
        layers={"nonprinting": {"visible": True, "printable": False}},
    )
    drawing._assert_generated_annotation_ink([sheet], _approved_detail_ink())
    # A sheet-owned generated note is NOT template ink, even near the title.
    sheet["sheet_annotations"].append({**outside, "owner_type": 1, "name": "generated sheet note"})
    with pytest.raises(RuntimeError, match="generated sheet note"):
        drawing._assert_generated_annotation_ink([sheet], _approved_detail_ink())


def test_wrapped_tip_instruction_has_one_feature_leader_and_no_floating_copy():
    assert drawing.THREAD_NOTE_TEXT.splitlines() == [
        "#4-40 UNC", "TIP FILED", "FLUSH WITH", "MHA-DT-06 AND",
        "STAKED AT", "MHA-DT-00", "STEP 7.",
    ]
    assert " ".join(drawing.THREAD_NOTE_TEXT.splitlines()[1:]) == spec.DRAWING_NOTES
    x, y = drawing.THREAD_NOTE_XY
    right = x + max(map(len, drawing.THREAD_NOTE_TEXT.splitlines())) * 0.0028
    bottom = y - 0.0308
    assert x > 0.0127
    assert right == pytest.approx(drawing.TIP_X - 0.004)
    assert bottom > drawing.SIDE_KEEP["UnderHeadLocation"][1] + 0.006
    assert bottom > drawing.SIDE_KEEP["OverallLength"][1] + 0.006
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    attached = [node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "add_attached_note"]
    assert len(attached) == 1
    keywords = {kw.arg: ast.unparse(kw.value) for kw in attached[0].keywords}
    assert keywords["text"] == "THREAD_NOTE_TEXT"
    assert keywords["entity_xy"] == "THREAD_PICK"
    assert keywords["note_xy"] == "THREAD_NOTE_XY"
    properties = [node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "add_property_linked_note"]
    assert [ast.literal_eval(node.args[1]) for node in properties] == ["Isometric View Note"]
    assert not hasattr(drawing, "NOTES_XY")


def test_build_runs_collective_actual_ink_guard_as_finalizer_settled_check():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    finalize = next(node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "finalize_drawing")
    settled = next(kw.value for kw in finalize.keywords if kw.arg == "settled_checks")
    assert isinstance(settled, ast.Tuple) and len(settled.elts) == 1
    callback = settled.elts[0]
    assert isinstance(callback, ast.Lambda) and not callback.args.args
    guard = callback.body
    assert isinstance(guard, ast.Call) and ast.unparse(guard.func) == "assert_final_annotation_ink"
    assert [ast.unparse(arg) for arg in guard.args] == ["adapter", "detail_annotations"]
    assert sum(isinstance(node.func, ast.Name) and node.func.id == "assert_final_annotation_ink"
               for node in calls) == 1
    ink_names = {"add_attached_note", "_add_shoulder_finish", "label_relief_view",
                 "mark_relief_on_side", "add_property_linked_note", "style_relief_dimensions"}
    assert all(node.lineno < finalize.lineno for node in calls
               if isinstance(node.func, ast.Name) and node.func.id in ink_names)

def test_generated_ink_keeps_valid_offenders_when_same_annotation_or_group_is_malformed():
    annotation = _ink_annotation("mixed", texts=[{**_actual_text(), "w": math.nan}],
                                 lines=[_actual_line((0.1, 0.1), (0.1, 0.001))])
    groups = _approved_detail_ink()
    groups["ReliefLead"] = [((math.nan, 0.1), (0.2, 0.1)),
                            ((0.19, 0.11), (0.21, 0.11))]
    groups["SeatEdgeBreak"] = [((0.2, 0.1), (0.2, 0.12))]
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet(annotation)], groups)
    message = str(caught.value)
    assert "actual text" in message and "actual ink outside inner border" in message
    assert "DETAIL/ReliefLead: missing/malformed/nonfinite" in message
    assert "ReliefLead vs SeatEdgeBreak" in message


@pytest.mark.parametrize("direction", [0, 1])
def test_generated_arc_bounds_include_true_extreme_between_sample_vertices(direction):
    # A full circle whose start angle is not a cardinal point: sampling alone
    # can miss an arbitrarily small true breach of the unchanged inner border.
    radius, cy = 0.01, 0.1
    cx = 0.4191 - radius + 0.000001
    sx, sy = cx + radius * math.cos(0.04), cy + radius * math.sin(0.04)
    arc = [0, 0, 0, 0, sx, sy, 0, sx, sy, 0, cx, cy, 0, 0, 0, 1, direction]
    annotation = _ink_annotation("arc")
    annotation["display"]["arcs"] = [arc]
    with pytest.raises(RuntimeError, match="arc: actual ink outside inner border"):
        drawing._assert_generated_annotation_ink([_ink_sheet(annotation)], _approved_detail_ink())


def test_final_settled_guard_collects_every_view_and_sheet_without_another_rebuild(monkeypatch):
    from types import SimpleNamespace

    events = []
    visible = _ink_annotation("view dimension", texts=[_actual_text()])
    sheet_note = _ink_annotation("sheet note", texts=[_actual_text()], owner_type=1)
    template = {"owner_type": 2, "display": {}}
    class View:
        def __init__(self, records):
            self.records = records

        def GetAnnotations(self):
            events.append(("annotations", self))
            return self.records

    class Reader:
        def __init__(self, adapter):
            self.adapter = adapter

        def take_errors(self):
            return {}

    sheet_view, side, detail = View([sheet_note, template]), View([visible, *_settled_native_records()]), View([])
    model = SimpleNamespace(
        EditRebuild3=lambda: events.append("rebuild"),
        GetViews=lambda: [[sheet_view, side, detail]],
        GetSheetNames=lambda: ["Sheet1"],
    )
    adapter = SimpleNamespace(currentModel=model)
    groups = _approved_detail_ink()
    monkeypatch.setattr(drawing, "_early_bound", lambda raw, interface: raw)
    monkeypatch.setattr(drawing._drawing_layout_audit, "_Reader", Reader)
    monkeypatch.setattr(drawing._drawing_layout_audit, "_dump_annotation", lambda reader, raw: raw)
    monkeypatch.setattr(drawing._drawing_layout_audit, "_layer_states", lambda reader, dump: {})
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, name: name)
    monkeypatch.setattr(drawing._drawing_leaders, "dimension_segments", lambda name: groups[name])
    drawing.assert_final_annotation_ink(adapter, list(groups))
    assert events == [("annotations", sheet_view), ("annotations", side), ("annotations", detail)]
    # A view inventory failure must not prevent collecting later annotations,
    # later DETAIL groups, or their simultaneous actual-ink violations.
    class BrokenView:
        def GetAnnotations(self):
            raise RuntimeError("inventory refused")

    model.GetViews = lambda: [[sheet_view, BrokenView(), side, detail]]
    visible["display"]["texts"][0]["pos"][0] = 0.001
    groups["ReliefLead"] = []
    with pytest.raises(RuntimeError) as caught:
        drawing.assert_final_annotation_ink(adapter, list(groups))
    message = str(caught.value)
    for expected in ("inventory refused", "view dimension: actual ink outside", "DETAIL/ReliefLead"):
        assert expected in message

def test_head_length_actual_reason_and_underline_clear_border_arrow_stub_and_radius():
    x, y = drawing.SIDE_KEEP["HeadLength"]
    # Actual r16 reason width and native underline drop, translated only.
    reason_left, reason_right = x - 0.0472819, x + 0.0472819
    assert reason_left - 0.3071 >= 0.0056
    assert reason_right < 0.4191
    head_line = y - 0.0055562
    radius_top = drawing.DETAIL_KEEP["ReliefCornerRadius"][1] + 0.0044992
    seat_top = drawing.DETAIL_KEEP["SeatEdgeBreak"][1] + 0.0072774
    assert head_line - radius_top >= 0.0029
    assert head_line - seat_top >= 0.0021
    assert 0.17465 - head_line >= 0.0037


@pytest.mark.parametrize("name", list(drawing.DETAIL_KEEP))
@pytest.mark.parametrize("bad", [None, [], 42, [None], [((math.inf, 0.1), (0.2, 0.1))]])
def test_generated_foreign_pair_guard_collects_every_missing_or_malformed_group(name, bad):
    groups = _approved_detail_ink()
    groups[name] = bad
    with pytest.raises(RuntimeError, match=f"DETAIL/{name}: missing/malformed/nonfinite actual ink"):
        drawing._assert_generated_annotation_ink([_ink_sheet()], groups)

@pytest.mark.parametrize("primitive", ["leader", "note-extent", "arrow", "triangle", "polygon", "polyline"])
def test_generated_border_includes_every_actual_native_ink_carrier(primitive):
    annotation = _ink_annotation(primitive, texts=[_actual_text()])
    if primitive == "leader":
        annotation["leaders"] = [[0.1, 0.1, 0, 0.001, 0.1, 0]]
    elif primitive == "note-extent":
        annotation["note"] = {"extent": [0.001, 0.09, 0, 0.12, 0.11, 0]}
    elif primitive == "arrow":
        annotation["display"]["arrows"] = [[0.014, 0.1, 0, -1, 0, 0, 0.004, 0.001]]
    elif primitive == "triangle":
        annotation["display"]["triangles"] = [[0.1, 0.1, 0, 0.001, 0.1, 0, 0.1, 0.11, 0, 1, 0]]
    elif primitive == "polygon":
        annotation["display"]["polygons"] = [[0, 0, 0, 0, 3, 0.1, 0.1, 0, 0.001, 0.1, 0, 0.1, 0.11, 0]]
    else:
        annotation["display"]["polylines"] = [[0, 0, 0, 0, 0, 0, 2, 0.1, 0.1, 0, 0.001, 0.1, 0]]
    with pytest.raises(RuntimeError, match=f"Sheet1/{primitive}: actual ink outside inner border"):
        drawing._assert_generated_annotation_ink([_ink_sheet(annotation)], _approved_detail_ink())


def test_generated_border_excludes_template_owned_view_records_without_coordinate_exemptions():
    outside = _ink_annotation("format", lines=[_actual_line((0, 0), (0.001, 0.001))], owner_type=2)
    ghost = _ink_annotation("hidden ghost", lines=[_actual_line((0, 0), (0.001, 0.001))], visible=3, owner_type=1)
    invisible_layer = _ink_annotation("hidden layer", lines=[_actual_line((0, 0), (0.001, 0.001))], layer="hidden")
    drawing._assert_generated_annotation_ink([
        _ink_sheet(outside, ghost, invisible_layer, layers={"hidden": {"visible": False, "printable": True}})
    ], _approved_detail_ink())

def test_generated_pair_guard_reports_all_six_simultaneous_foreign_pairs_once():
    groups = {name: [((0.2, 0.1), (0.2, 0.12))] for name in drawing.DETAIL_KEEP}
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet()], groups)
    message = str(caught.value)
    names = list(drawing.DETAIL_KEEP)
    for index, name in enumerate(names):
        for other in names[index + 1:]:
            assert f"DETAIL/{name} vs {other}: foreign ink crossing" in message
    assert message.count("foreign ink crossing") == 6

def test_approved_corridor_tune_keeps_exact_detail_frame_scale_crop_and_anchors():
    assert drawing.DETAIL_CENTER == (0.320, 0.130)
    assert drawing.DETAIL_SCALE == (10.0, 1.0)
    assert drawing.DETAIL_RADIUS_MM == 3.0
    assert drawing.DETAIL_KEEP == {
        "ReliefDia": (0.320, 0.0905),
        "ReliefCornerRadius": (0.320, 0.1635),
        "ReliefLead": (0.378, 0.106),
        "SeatEdgeBreak": (0.378, 0.1615),
    }
    assert drawing.DETAIL_LABEL_XY == (0.342, 0.0845)
    assert drawing.HEAD_LENGTH_TEXT_X == 0.360
    assert drawing.SIDE_KEEP["HeadLength"] == (0.360, 0.1765)


def _r17_root_text(*, shift=0.0):
    """Recorded r17 native metric run; shift is synthetic, never a seat result."""
    return {"t": "BELOW #4-40 ROOT", "pos": [0.2998361, 0.0719719 + shift, -0.001],
            "h": 0.0035, "w": 0.0440563, "ang": 1.5707963, "ref": 1,
            "font": "Century Gothic", "ls": 0.001}


def _settled_native_records(*, r17=False):
    """Native-shaped required records; only r17=True uses the recorded bad route.

    The default is a synthetic clear route in the approved gap and the r17
    text shifted down 3.5 mm. It does not claim native r18 placement proof.
    """
    shift = 0.0 if r17 else -0.0035
    root = _ink_annotation("ReliefDia", type=4, dim={"hole_callout": False}, texts=[
        _r17_root_text(shift=shift),
        {"t": "NECK FOR SEATING", "pos": [0.3144437, 0.0724604 + shift, -0.001],
         "h": 0.0035, "w": 0.0430792, "ang": 1.5707963, "ref": 1},
    ])
    references = []
    for name, right, bottom, row in (
        ("UnderHeadLocation", 0.2485, 0.1228875, 0.1238875),
        ("OverallLength", 0.2605, 0.1122219, 0.1132219),
    ):
        references.append(_ink_annotation(
            name, type=4, dim={"hole_callout": False},
            lines=[_actual_line((0.0595, 0.189), (0.0595, bottom)),
                   _actual_line((right, 0.180 if name == "UnderHeadLocation" else 0.189), (right, bottom)),
                   _actual_line((0.0595, row), (right, row))],
        ))
    if r17:
        start, tip = (0.0559043, 0.1532104), (0.0604, 0.1942675)
        registered = [0.0558983, 0.1530329, 0.0, *tip, 0.0]
        direction = (-0.1088489, -0.9940583)
    else:
        start, tip = (0.0559043, 0.193), (0.0595, 0.193)
        registered = [0.0558983, 0.193, 0.0, *tip, 0.0]
        direction = (-1.0, 0.0)
    widths = [0.0242618, 0.0185403, 0.024991, 0.0363271, 0.0232264, 0.0246604, 0.0147486]
    rows = [0.1774743, 0.1729486, 0.1684229, 0.1638972, 0.1593715, 0.1548458, 0.1503201]
    note = _ink_annotation(
        "DetailItem348", type=6, pos=[0.0191, 0.182, 0.0],
        lines=[_actual_line(start, start), _actual_line(start, tip)],
        texts=[{"t": text, "pos": [0.0191, y, 0.0], "h": 0.0035, "w": width,
                "ang": 0.0, "ref": 1, "font": "Century Gothic", "ls": 0.001}
               for text, y, width in zip(drawing.THREAD_NOTE_TEXT.splitlines(), rows, widths, strict=True)],
        leaders=[registered],
        note={"text": drawing.THREAD_NOTE_TEXT.replace("\n", "\r\n"),
              "extent": [0.0190772, 0.1506611, 0.0, 0.0600621, 0.1945054, 0.0]},
    )
    note["display"]["arrows"] = [[*tip, 0.0, *direction, 0.0, 0.003556, 0.000762, 1, 0, 0, 1]]
    return [root, *references, note, *_under_head_native_records()]


def test_fitted_span_reuses_native_model_carrier_and_all_three_reference_guards():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    loop = next(node for node in build.body
                if isinstance(node, ast.For) and ast.unparse(node.iter) == "sorted(REFERENCE_DIMENSIONS)")
    code = compile(ast.Module(body=[loop], type_ignores=[]), drawing.__file__, "exec")
    names = ["ShoulderLength", "UnderHeadLocation", "OverallLength"]
    calls = []
    context = {"REFERENCE_DIMENSIONS": spec.REFERENCE_DIMENSIONS, "annotations": names,
               "adapter": object(), "dimension_name": lambda adapter, annotation: annotation,
               "set_reference_dimension": lambda adapter, annotation, **kwargs: calls.append((annotation, kwargs))}
    exec(code, context)
    assert {name for name, _ in calls} == set(names)
    assert len(calls) == 3
    assert all(kwargs == {"label": f"MHA-DT-32 {name}"} for name, kwargs in calls)
    for native_annotations in (names[1:], [*names, "ShoulderLength"]):
        with pytest.raises(RuntimeError, match="expected one MHA-DT-32 ShoulderLength reference dimension"):
            exec(code, {**context, "annotations": native_annotations})
    assert spec.SHOULDER_LENGTH == 53.0
    assert "ShoulderLength" not in drawing.DETAIL_KEEP
    assert "ShoulderLength" not in drawing.END_KEEP
    assert drawing.SIDE_KEEP["UnderHeadLocation"] == pytest.approx((0.154, 0.135))
    assert drawing.SIDE_KEEP["OverallLength"] == pytest.approx((0.160, 0.116))


def test_lower_thread_profile_is_spec_projected_and_circle_clipped(monkeypatch):
    profile = drawing._relief_lower_thread_profile()
    (left, lower), (right, same_y) = profile
    cx, cy = drawing.DETAIL_CENTER
    assert lower == same_y == pytest.approx(0.115775)
    assert math.dist((left, lower), (cx, cy)) == pytest.approx(drawing.DETAIL_RADIUS)
    assert left > cx - drawing.DETAIL_RADIUS
    assert right == pytest.approx(0.308)
    monkeypatch.setattr(drawing, "THREAD_MODEL_DIA", spec.THREAD_MODEL_DIA + 0.1)
    changed = drawing._relief_lower_thread_profile()
    assert changed[0][1] == pytest.approx(lower - 0.0005)
    assert changed[0][0] > left


@pytest.mark.parametrize("air,accepted", [(0.0, False), (0.002999, False), (0.003001, True)])
def test_rotated_root_metric_hull_requires_three_mm_from_actual_thread_profile(air, accepted):
    text = _r17_root_text()
    profile = drawing._relief_lower_thread_profile()
    box = drawing._layout_audit.display_box({"texts": [text]})
    text["pos"][1] += profile[0][1] - box.ymax - air
    errors = drawing._relief_text_profile_errors(_ink_annotation("ReliefDia", texts=[text]))
    assert (errors == []) is accepted
    if not accepted:
        assert all("metric text/profile clearance below 0.003" in error for error in errors)
        assert "model_spec_profile=" in errors[0]


def test_r17_root_contact_and_both_tip_reference_crossings_collect_in_one_refusal():
    records = _settled_native_records(r17=True)
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)
    message = str(caught.value)
    assert "BELOW #4-40 ROOT" in message and "metric text/profile clearance below 0.003" in message
    assert "NECK FOR SEATING" in message
    for inventory in ("lines", "leaders"):
        for reference in ("UnderHeadLocation", "OverallLength"):
            assert f"ThreadNote/{inventory} vs {reference}: tip-leader/reference-witness crossing" in message
    assert "missing" not in message and "malformed" not in message
    assert "outside inner border" not in message
    actual = records[-1]["display"]["lines"][1]
    crossing_y = actual[5] + (0.0595 - actual[4]) * (actual[8] - actual[5]) / (actual[7] - actual[4])
    assert crossing_y == pytest.approx(0.186048, abs=0.000001)


def test_synthetic_gap_route_and_shifted_native_metric_text_pass_required_settlement():
    records = _settled_native_records()
    drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)
    root = records[0]["display"]["texts"][0]
    box = drawing._layout_audit.display_box({"texts": [root]})
    assert box.ymin == pytest.approx(0.0684719)
    assert drawing._relief_lower_thread_profile()[0][1] - box.ymax == pytest.approx(0.0032468)
    assert drawing.THREAD_NOTE_XY == pytest.approx((0.0191, 0.182))
    assert drawing.THREAD_PICK == pytest.approx((0.0595, 0.193))


@pytest.mark.parametrize("name", ["ReliefDia", "UnderHeadLocation", "OverallLength", "ThreadNote"])
@pytest.mark.parametrize("count", [0, 2])
def test_required_settled_inventories_refuse_missing_or_duplicate_annotations(name, count):
    records = _settled_native_records()
    index = {"ReliefDia": 0, "UnderHeadLocation": 1, "OverallLength": 2, "ThreadNote": 3}[name]
    annotation = records.pop(index)
    records.extend([annotation] * count)
    with pytest.raises(RuntimeError, match=f"{name}: expected one settled native annotation; count={count}"):
        drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)


@pytest.mark.parametrize("text", [
    drawing.THREAD_NOTE_TEXT + " ", " " + drawing.THREAD_NOTE_TEXT,
    drawing.THREAD_NOTE_TEXT.replace("\n", "\r"), drawing.THREAD_NOTE_TEXT.lower(),
])
def test_settled_tip_note_only_normalizes_crlf_not_wrong_text(text):
    records = _settled_native_records()
    records[-1]["note"]["text"] = text
    with pytest.raises(RuntimeError, match="ThreadNote: expected one settled native annotation; count=0"):
        drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)


def test_settled_tip_note_rejects_mixed_lf_crlf_duplicate():
    records = _settled_native_records()
    records.append({**records[-1], "note": {**records[-1]["note"], "text": drawing.THREAD_NOTE_TEXT}})
    with pytest.raises(RuntimeError, match="ThreadNote: expected one settled native annotation; count=2"):
        drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)


@pytest.mark.parametrize("name,kind", [
    ("ThreadNote", "lines"), ("ThreadNote", "leaders"), ("ThreadNote", "arrows"),
    ("UnderHeadLocation", "lines"), ("OverallLength", "lines"), ("ReliefDia", "texts"),
])
@pytest.mark.parametrize("bad", [None, [], 42, [None], [[math.nan] * 10]])
def test_required_native_ink_refuses_malformed_empty_or_missing_data_without_fallback(name, kind, bad):
    records = _settled_native_records()
    annotation = records[{"ReliefDia": 0, "UnderHeadLocation": 1, "OverallLength": 2, "ThreadNote": 3}[name]]
    target = annotation if kind == "leaders" else annotation["display"]
    if bad is None:
        target.pop(kind)
    else:
        target[kind] = bad
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)
    message = str(caught.value)
    assert name in message and ("missing" in message or "malformed" in message or "empty" in message)


def test_tip_arrow_outline_is_checked_even_when_both_native_leader_routes_miss():
    records = _settled_native_records()
    records[-1]["display"]["arrows"] = [
        [0.0596, 0.1885, 0, -1, 0, 0, 0.003556, 0.000762, 1, 0, 0, 1]
    ]
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)
    message = str(caught.value)
    for reference in ("UnderHeadLocation", "OverallLength"):
        assert f"ThreadNote/arrows vs {reference}: tip-leader/reference-witness crossing" in message
    assert "ThreadNote/lines vs" not in message and "ThreadNote/leaders vs" not in message


def test_required_settlement_collects_malformed_text_routes_border_and_foreign_pairs_together():
    records = _settled_native_records(r17=True)
    records[0]["display"]["texts"].append({**_r17_root_text(), "w": math.nan})
    records[-1]["leaders"].append([math.nan] * 6)
    groups = _approved_detail_ink()
    groups["ReliefLead"].append(groups["SeatEdgeBreak"][0])
    records.append(_ink_annotation("off border", lines=[_actual_line((0.1, 0.1), (0.001, 0.1))]))
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet(*records)], groups, settled=True)
    message = str(caught.value)
    for expected in ("metric text/profile clearance", "ThreadNote/lines vs UnderHeadLocation",
                     "ThreadNote/lines vs OverallLength", "ThreadNote/leaders vs UnderHeadLocation",
                     "malformed/nonfinite", "actual ink outside inner border", "foreign ink crossing"):
        assert expected in message


def test_production_settlement_always_enables_mandatory_dump_inventories():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    callback = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "assert_final_annotation_ink")
    call = next(node for node in ast.walk(callback)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_assert_generated_annotation_ink")
    assert [ast.unparse(arg) for arg in call.args] == ["dumps", "groups"]
    assert next(ast.literal_eval(kw.value) for kw in call.keywords if kw.arg == "settled") is True


@pytest.mark.parametrize("fault", [
    "r17", "missing-ReliefDia", "duplicate-ReliefDia",
    "missing-UnderHeadLocation", "duplicate-UnderHeadLocation",
    "missing-OverallLength", "duplicate-OverallLength",
    "missing-ThreadNote", "duplicate-ThreadNote",
])
def test_production_settled_callback_collects_required_native_records_without_new_reads(monkeypatch, fault):
    from types import SimpleNamespace

    records = _settled_native_records(r17=fault == "r17")
    if fault != "r17":
        action, name = fault.split("-", 1)
        index = {"ReliefDia": 0, "UnderHeadLocation": 1, "OverallLength": 2, "ThreadNote": 3}[name]
        annotation = records.pop(index)
        records.extend([annotation] * (2 if action == "duplicate" else 0))

    class View:
        __slots__ = ("annotations",)

        def __init__(self, annotations):
            self.annotations = annotations

        def GetAnnotations(self):
            return self.annotations

    class Reader:
        __slots__ = ()

        def __init__(self, adapter):
            pass

        def take_errors(self):
            return {}

    model = SimpleNamespace(GetViews=lambda: [[View([]), View(records)]],
                            GetSheetNames=lambda: ["Sheet1"])
    adapter = SimpleNamespace(currentModel=model)
    groups = _approved_detail_ink()
    monkeypatch.setattr(drawing, "_early_bound", lambda raw, interface: raw)
    monkeypatch.setattr(drawing._drawing_layout_audit, "_Reader", Reader)
    monkeypatch.setattr(drawing._drawing_layout_audit, "_dump_annotation", lambda reader, raw: raw)
    monkeypatch.setattr(drawing._drawing_layout_audit, "_layer_states", lambda reader, dump: {})
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, name: name)
    monkeypatch.setattr(drawing._drawing_leaders, "dimension_segments", lambda name: groups[name])
    with pytest.raises(RuntimeError) as caught:
        drawing.assert_final_annotation_ink(adapter, list(groups))
    message = str(caught.value)
    if fault == "r17":
        assert "metric text/profile clearance" in message
        assert "NECK FOR SEATING" in message
        for reference in ("UnderHeadLocation", "OverallLength"):
            assert f"ThreadNote/lines vs {reference}" in message
            assert f"ThreadNote/leaders vs {reference}" in message
        assert "missing" not in message and "malformed" not in message
    else:
        count = 2 if action == "duplicate" else 0
        assert f"{name}: expected one settled native annotation; count={count}" in message


@pytest.mark.parametrize("index", [1, 2], ids=["63", "67"])
def test_required_reference_inventory_refuses_a_missing_witness_not_just_empty_lines(index):
    records = _settled_native_records()
    annotation = records[index]
    del annotation["display"]["lines"][0]
    with pytest.raises(RuntimeError, match=f"{annotation['name']}: expected two actual reference witnesses"):
        drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)


def test_settled_unreadable_text_reference_keeps_all_other_native_offenders():
    records = _settled_native_records(r17=True)
    records[0]["display"]["texts"].append({**_r17_root_text(), "ref": "unreadable"})
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)
    message = str(caught.value)
    assert "unreadable actual metric text hull" in message
    assert "metric text/profile clearance" in message
    for reference in ("UnderHeadLocation", "OverallLength"):
        assert f"ThreadNote/lines vs {reference}" in message
        assert f"ThreadNote/leaders vs {reference}" in message


def test_option2_uses_the_exact_lower_level_mating_requirements_and_actual_inputs():
    assert spec.UNDER_HEAD_CORNER_RADIUS_MAX == cup.MATING_SCREW_UNDER_HEAD_FILLET_MAX == 0.1
    assert spec.HEAD_OUTER_CHAMFER_MIN == cup.MATING_SCREW_HEAD_EDGE_BREAK_MIN == 0.11
    assert spec.HEAD_OUTER_CHAMFER_MAX == cup.MATING_SCREW_HEAD_EDGE_BREAK_MAX == 0.26
    assert spec.HEAD_OUTER_CHAMFER == 0.26
    assert spec.HEAD_OUTER_CHAMFER_BAND == (0.0, -0.15)
    assert spec.HEAD_OUTER_CHAMFER_TOL_TYPE == 3
    assert spec.HEAD_DIA_MIN == cup.MATING_SCREW_HEAD_DIA_MIN == 5.9
    assert spec.SHOULDER_DIA_MIN == cup.MATING_SCREW_SHOULDER_DIA_MIN == 3.92
    assert spec.END_PLAY_RANGE[0] == cup.MATING_SCREW_SEATED_GAP_MIN == 0.25
    assert spec.CUP_FLOOR_HOLE_DIA_MIN == 4.2
    assert spec.CUP_FLOOR_HOLE_DIA_MAX == 4.3
    assert spec.CUP_FLOOR_HOLE_MOUTH_CHAMFER_MIN == 0.11
    assert spec.CUP_FLOOR_HOLE_MOUTH_CHAMFER_MAX == 0.25
    assert spec.CUP_POCKET_FLOOR_CORNER_R_MAX == 0.1
    assert spec.HEAD_BEARING_RADIAL_MIN == cup.MATING_SCREW_HEAD_BEARING_FLOOR == 0.1
    assert spec.HEAD_OUTER_CHAMFER_CALLOUT == "X 45 DEG\nCLEARS MHA-DT-35\nFLOOR RADIUS"
    assert "0.11" not in spec.HEAD_OUTER_CHAMFER_CALLOUT
    assert "0.26" not in spec.HEAD_OUTER_CHAMFER_CALLOUT
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "2.0 * EDGE_BREAK_MAX_MM" not in source
    assert "UNDER_HEAD_CORNER_RADIUS_MAX = MATING_SCREW_UNDER_HEAD_FILLET_MAX" in source
    assert spec.HEAD_OUTER_CHAMFER_MAX > geometry.EDGE_BREAK_MAX_MM


def test_option2_both_corners_have_positive_air_at_a_valid_same_coordinate_state():
    head, shaft, hole, clearance = 5.9, 3.92, 4.3, 0.38
    pocket = head + clearance
    offset = min(clearance / 2.0, (hole - shaft) / 2.0)
    assert pocket == pytest.approx(6.28)
    assert offset == pytest.approx(0.19)
    assert hole / 2.0 - offset == pytest.approx(shaft / 2.0)
    assert pocket / 2.0 - offset == pytest.approx(head / 2.0)
    # Separate tolerance extrema: minimum breaks prove air; maximum breaks
    # prove the far-side bearing floor, not one manufactured tolerance set.
    for r, leg, normal, seated in (
        (spec.UNDER_HEAD_CORNER_RADIUS_MAX, cup.FLOOR_HOLE_MOUTH_CHAMFER_MIN,
         spec.UNDER_HEAD_INNER_NORMAL_AIR_MIN, spec.UNDER_HEAD_INNER_SEATED_AXIAL_AIR_MIN),
        (cup.POCKET_FLOOR_CORNER_R_MAX, spec.HEAD_OUTER_CHAMFER_MIN,
         spec.UNDER_HEAD_OUTER_NORMAL_AIR_MIN, spec.UNDER_HEAD_OUTER_SEATED_AXIAL_AIR_MIN),
    ):
        assert normal == pytest.approx((leg - r) / math.sqrt(2.0))
        assert normal == pytest.approx(0.00707106781186547)
        assert seated == pytest.approx(0.15)
        for index in range(1001):
            angle = index / 1000.0 * math.pi / 2.0
            x, y = r * (1.0 - math.cos(angle)), r * (1.0 - math.sin(angle))
            assert (leg - x - y) / math.sqrt(2.0) >= normal - 1e-14
    bearing = head / 2.0 - 0.26 - hole / 2.0 - offset - 0.25
    assert bearing == pytest.approx(spec.HEAD_BEARING_RADIAL_MIN)
    assert bearing == pytest.approx(0.1)


@pytest.mark.parametrize("shaft", [3.92, 3.945, 3.97])
@pytest.mark.parametrize("hole", [4.2, 4.25, 4.3])
@pytest.mark.parametrize("pocket_clearance", [0.2, 0.3, 0.4])
def test_option2_offset_is_correlated_with_each_physically_allowed_pair(shaft, hole, pocket_clearance):
    offset = min(pocket_clearance / 2.0, (hole - shaft) / 2.0)
    assert hole / 2.0 - offset - shaft / 2.0 >= -1e-14
    assert pocket_clearance / 2.0 - offset >= -1e-14
    assert offset <= spec.HEAD_RUNNING_OFFSET_MAX + 1e-14


@pytest.mark.parametrize("name,value,message", [
    ("FLOOR_HOLE_MOUTH_CHAMFER_MIN", 0.1, "inner under-head corner has no positive"),
    ("POCKET_FLOOR_CORNER_R_MAX", 0.11, "outer under-head corner has no positive"),
    ("FLOOR_HOLE_MOUTH_CHAMFER_MIN", 0.26, "invalid cup floor-hole mouth chamfer range"),
    ("FLOOR_HOLE_MOUTH_CHAMFER_MAX", 0.250002, "under 0.1 of under-head bearing"),
    ("FLOOR_HOLE_DIA_MAX", 4.300002, "under 0.1 of under-head bearing"),
    ("MATING_SCREW_HEAD_EDGE_BREAK_MIN", 0.27, "invalid outer under-head chamfer range"),
    ("MATING_SCREW_HEAD_EDGE_BREAK_MAX", 0.260002, "under 0.1 of under-head bearing"),
    ("MATING_SCREW_UNDER_HEAD_FILLET_MAX", 0.11, "inner under-head corner has no positive"),
    ("MATING_SCREW_UNDER_HEAD_FILLET_MAX", 0.0, "invalid inner under-head fillet"),
    ("MATING_SCREW_SEATED_GAP_MIN", 0.26, "fitted end play is below"),
])
def test_option2_imported_boundary_mutations_fail_the_independent_screw_guard(monkeypatch, name, value, message):
    monkeypatch.setattr(cup, name, value)
    source = Path(spec.__file__).read_text(encoding="utf-8")
    with pytest.raises(AssertionError, match=message):
        exec(compile(source, spec.__file__, "exec"), {"__name__": "_option2_mating_probe"})


@pytest.mark.parametrize("previous,replacement", [
    ("HEAD_DIA_TOL = 0.10", "HEAD_DIA_TOL = 0.11"),
    ("SHOULDER_DIA_BAND = (-0.03, -0.08)", "SHOULDER_DIA_BAND = (-0.03, -0.09)"),
])
def test_option2_actual_screw_minima_cannot_be_replaced_by_acceptance_constants(previous, replacement):
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert source.count(previous) == 1
    with pytest.raises(AssertionError, match="actual head/shoulder minima violate"):
        exec(compile(source.replace(previous, replacement), spec.__file__, "exec"),
             {"__name__": "_option2_actual_inputs_probe"})


@pytest.mark.asyncio
async def test_option2_real_profile_keeps_actual_face_carriers_and_both_45_degree_legs(corner_profile):
    state = corner_profile
    with pytest.raises(state.complete):
        await part.build(state.adapter)
    assert state.arcs[1] == pytest.approx((-4.1, 2.1, -4.1, 2.0, -4.0, 2.1))
    assert state.lines["Line1"] == pytest.approx((0.0, 3.0, -3.74, 3.0))
    assert state.lines["Line2"] == pytest.approx((-3.74, 3.0, -4.0, 2.74))
    assert state.lines["Line3"] == pytest.approx((-4.0, 2.74, -4.0, 2.1))
    assert state.lines["Line4"][:2] == pytest.approx((-4.1, 2.0))
    assert ("Line3", "UnderHeadCorner", "tangent") in state.constraints
    assert ("Line4", "UnderHeadCorner", "tangent") in state.constraints
    assert ("UnderHeadCorner", None, "radial", 0.1) in state.dimensions
    assert ("UnderHeadCornerRadius", '"UnderHeadCornerRadius"') in state.rows
    assert ("HeadOuterChamfer", '"HeadOuterChamfer"') in state.rows
    assert ("HeadOuterChamferRise", '"HeadOuterChamfer"') in state.rows
    assert state.globals["HeadOuterChamfer"] == "0.26mm"
    assert state.globals["UnderHeadCornerRadius"] == "0.1mm"
    assert ("Line1.start", "Line3.start", "horizontal_distance", 4.0) in state.dimensions
    assert ("Line3.end", "Line5.end", "horizontal_distance", 53.0) in state.dimensions
    for kind in ("horizontal_distance", "vertical_distance"):
        assert ("Line2.start", "Line2.end", kind, 0.26) in state.dimensions
    center, start, end = state.arcs[1][:2], state.arcs[1][2:4], state.arcs[1][4:6]
    a = (start[0] - center[0], start[1] - center[1])
    b = (end[0] - center[0], end[1] - center[1])
    assert math.degrees(math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1])) == pytest.approx(90)
    assert spec.SEAT_STATION == 57.0
    assert spec.OVERALL_LENGTH == 67.0
    assert spec.OVERALL_LENGTH - spec.HEAD_LENGTH == 63.0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["under-head-arc", "under-head-radial"])
async def test_option2_builder_rejects_each_new_native_feature_failure(corner_profile, failure):
    state = corner_profile
    state.failure = failure
    with pytest.raises(RuntimeError, match=f"native {failure} refused"):
        await part.build(state.adapter)
    assert state.events == []


def test_option2_both_configuration_volume_deltas_match_independent_radial_integrals():
    steps = 20_000
    r, s, h, c = 0.1, 2.0, 3.0, 0.26
    dz = r / steps
    filled = sum(math.pi * ((s + r - math.sqrt(r*r - ((i + 0.5)*dz - r)**2))**2 - s*s) * dz
                 for i in range(steps))
    dz = c / steps
    removed = sum(math.pi * (h*h - (h - (i + 0.5)*dz)**2) * dz for i in range(steps))
    assert part.V_UNDER_HEAD_CORNER == pytest.approx(filled, abs=1e-6)
    assert part.V_HEAD_OUTER_CHAMFER == pytest.approx(removed, abs=1e-9)
    assert filled > 0.0 and removed > filled
    for length, tip, actual in (
        (spec.THREAD_LENGTH, spec.TIP_CHAMFER, part.V_FINAL),
        (spec.INSTALLED_THREAD_LENGTH, spec.INSTALLED_TIP_CHAMFER, part.V_INSTALLED),
    ):
        sharp_under_head = (
            math.pi * (h*h * spec.HEAD_LENGTH + s*s * spec.SHOULDER_LENGTH + part.THREAD_R**2 * length)
            - part.V_RELIEF - math.pi * tip**2 * (part.THREAD_R - tip / 3.0)
            - math.pi * spec.SEAT_EDGE_BREAK_MAX**2 * (s - spec.SEAT_EDGE_BREAK_MAX / 3.0)
            - part.V_SLOT
        )
        assert actual - sharp_under_head == pytest.approx(filled - removed, abs=1e-6)
    assert spec.SLOT_DEPTH_MAX < spec.HEAD_LENGTH - c
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.index("_head_outer_chamfer_limits(adapter)") < source.index("create_configuration {INSTALLED_CONFIG}")
    assert source.index("_single_limits(adapter)") < source.index("create_configuration {INSTALLED_CONFIG}")
    assert '( "HeadDia" - "ShoulderDia" ) / 2 - "HeadOuterChamfer" - "UnderHeadCornerRadius"' in source


def _under_head_limit_boundary(monkeypatch, *, name="HeadOuterChamfer", refusal=None):
    """Strict in-memory documented COM boundary; not a native-seat result."""
    from types import SimpleNamespace

    class Tolerance:
        __slots__ = ("_type", "values")

        def __init__(self):
            self._type, self.values = 0, (0.0, 0.0)

        @property
        def Type(self):
            return self._type

        @Type.setter
        def Type(self, value):
            if refusal != "type":
                self._type = value

        def SetValues(self, lower, upper):
            if refusal in ("values", "void"):
                return False if refusal == "values" else None
            self.values = (lower + (0.0001 if refusal == "lower" else 0.0),
                           upper + (0.0001 if refusal == "upper" else 0.0))
            return True

        def GetMinValue(self):
            return self.values[0]

        def GetMaxValue(self):
            return self.values[1]

    class Display:
        __slots__ = ("primary", "tolerance", "calls")

        def __init__(self):
            self.primary, self.tolerance, self.calls = 0, 0, []

        def SetPrecision3(self, primary, dual, tolerance, alternate):
            self.calls.append((primary, dual, tolerance, alternate))
            self.primary = primary if refusal != "primary" else 0
            self.tolerance = tolerance if refusal != "precision" else 0
            return -1 if refusal == "status" else 0

        def GetPrimaryPrecision2(self):
            return self.primary

        def GetPrimaryTolPrecision2(self):
            return self.tolerance

    display, tolerance = Display(), Tolerance()
    nominal = 0.26 if name == "HeadOuterChamfer" else 0.1
    dimension = SimpleNamespace(Tolerance=tolerance, SystemValue=nominal / 1000.0 + (0.0001 if refusal == "nominal" else 0.0))
    adapter, lookups = object(), []

    def lookup(actual_adapter, feature, actual_name):
        assert actual_adapter is adapter
        lookups.append((feature, actual_name))
        assert (feature, actual_name) == ("ScrewProfile", name)
        return display, dimension

    def bind(raw, interface):
        assert raw is {"IDimensionTolerance": tolerance, "IDisplayDimension": display}[interface]
        return raw

    monkeypatch.setattr(part, "_named_dimension", lookup)
    monkeypatch.setattr(part, "_early_bound", bind)
    if name == "UnderHeadCornerRadius":
        key = ("ScrewProfile", name)
        monkeypatch.setattr(part, "SINGLE_LIMITS", {key: spec.SINGLE_LIMITS[key]})
    return adapter, display, dimension, lookups


@pytest.mark.parametrize("name", ["HeadOuterChamfer", "UnderHeadCornerRadius"])
def test_option2_native_limit_writers_author_and_read_the_printed_bounds(monkeypatch, name):
    adapter, display, dimension, lookups = _under_head_limit_boundary(monkeypatch, name=name)
    writer = part._head_outer_chamfer_limits if name == "HeadOuterChamfer" else part._single_limits
    writer(adapter)
    places = 2 if name == "HeadOuterChamfer" else 1
    assert lookups == [("ScrewProfile", name)]
    assert display.calls == [(places, -1, places, -1)]
    assert dimension.Tolerance.Type == (3 if places == 2 else 6)
    assert dimension.Tolerance.GetMinValue() == pytest.approx(-0.00015 if places == 2 else 0.0)
    assert dimension.Tolerance.GetMaxValue() == 0.0
    assert (dimension.SystemValue + dimension.Tolerance.GetMinValue()) * 1000 == pytest.approx(0.11 if places == 2 else 0.1)
    assert (dimension.SystemValue + dimension.Tolerance.GetMaxValue()) * 1000 == pytest.approx(0.26 if places == 2 else 0.1)


@pytest.mark.parametrize("name", ["HeadOuterChamfer", "UnderHeadCornerRadius"])
@pytest.mark.parametrize("refusal", ["nominal", "values", "void", "type", "lower", "upper", "primary", "precision", "status"])
def test_option2_native_limit_writers_refuse_every_independent_boundary_drift(monkeypatch, name, refusal):
    adapter, _, _, _ = _under_head_limit_boundary(monkeypatch, name=name, refusal=refusal)
    writer = part._head_outer_chamfer_limits if name == "HeadOuterChamfer" else part._single_limits
    with pytest.raises(RuntimeError):
        writer(adapter)


def _under_head_native_records():
    """Disjoint synthetic native-shaped inventories, never rendered evidence."""
    records = []
    for index, name in enumerate((*drawing.UNDER_HEAD_DIMENSIONS, *drawing.UNDER_HEAD_FOREIGN_DIMENSIONS)):
        x = 0.10 + index * 0.04
        annotation = _ink_annotation(name, type=4, dim={"hole_callout": False},
            texts=[_actual_text(x, 0.245, width=0.015)],
            lines=[_actual_line((x, 0.230), (x + 0.005, 0.230))])
        annotation["display"]["arrows"] = [[x + 0.005, 0.230, 0, -1, 0, 0, 0.001, 0.0004]]
        records.append(annotation)
    return records


def test_option2_actual_under_head_corridors_are_collected_without_replacing_old_settlement():
    records = _settled_native_records()
    assert drawing._settled_under_head_errors([_ink_sheet(*records)]) == []
    drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "errors.extend(_settled_under_head_errors(dumps))" in source
    assert "errors.extend(_settled_profile_and_tip_errors(dumps))" in source
    assert "style_under_head_dimensions(adapter, side_annotations)" in source
    assert drawing.SIDE_KEEP["UnderHeadCornerRadius"] == (0.215, 0.212)
    assert drawing.SIDE_KEEP["HeadOuterChamfer"] == (0.245, 0.250)


@pytest.mark.parametrize("name", [*drawing.UNDER_HEAD_DIMENSIONS, *drawing.UNDER_HEAD_FOREIGN_DIMENSIONS])
@pytest.mark.parametrize("count", [0, 2])
def test_option2_actual_corridors_require_each_unique_native_annotation(name, count):
    records = _under_head_native_records()
    record = next(record for record in records if record["name"] == name)
    records.remove(record)
    records.extend([record] * count)
    errors = drawing._settled_under_head_errors([_ink_sheet(*records)])
    assert any(f"SIDE/{name}: expected one settled under-head corridor annotation; count={count}" in error for error in errors)


@pytest.mark.parametrize("name", [*drawing.UNDER_HEAD_DIMENSIONS, *drawing.UNDER_HEAD_FOREIGN_DIMENSIONS])
@pytest.mark.parametrize("kind", ["lines", "arrows", "texts"])
@pytest.mark.parametrize("bad", [None, [], 42, [None]])
def test_option2_actual_corridors_refuse_missing_or_malformed_ink(name, kind, bad):
    records = _under_head_native_records()
    record = next(record for record in records if record["name"] == name)
    record["display"][kind] = bad
    errors = drawing._settled_under_head_errors([_ink_sheet(*records)])
    assert any(f"SIDE/{name}" in error and ("missing" in error or "malformed" in error) for error in errors)


@pytest.mark.parametrize("new", drawing.UNDER_HEAD_DIMENSIONS)
@pytest.mark.parametrize("foreign", [*drawing.UNDER_HEAD_FOREIGN_DIMENSIONS, "other-under-head"])
@pytest.mark.parametrize("junction", ["crossing", "tee", "overlap"])
def test_option2_actual_corridors_refuse_all_new_feature_foreign_cross_tee_overlap(new, foreign, junction):
    records = {record["name"]: record for record in _under_head_native_records()}
    if foreign == "other-under-head":
        foreign = next(name for name in drawing.UNDER_HEAD_DIMENSIONS if name != new)
    records[new]["display"]["lines"] = [_actual_line((0.2, 0.20), (0.2, 0.22))]
    line = {"crossing": ((0.19, 0.21), (0.21, 0.21)),
            "tee": ((0.2, 0.21), (0.21, 0.21)),
            "overlap": ((0.2, 0.205), (0.2, 0.215))}[junction]
    records[foreign]["display"]["lines"] = [_actual_line(*line)]
    errors = drawing._settled_under_head_errors([_ink_sheet(*records.values())])
    assert any(new in error and foreign in error and "foreign ink crossing" in error for error in errors)


@pytest.mark.parametrize("air,accepted", [(0.0, False), (0.002999, False), (0.003001, True)])
def test_option2_actual_metric_text_requires_three_mm_from_foreign_native_witness(air, accepted):
    records = {record["name"]: record for record in _under_head_native_records()}
    box = drawing._layout_audit.display_box({"texts": records["UnderHeadCornerRadius"]["display"]["texts"]})
    records["HeadDia"]["display"]["lines"] = [_actual_line((box.xmin, box.ymin - air), (box.xmax, box.ymin - air))]
    errors = drawing._settled_under_head_errors([_ink_sheet(*records.values())])
    matching = [error for error in errors if "UnderHeadCornerRadius text vs HeadDia" in error]
    assert not matching if accepted else matching


def test_option2_actual_corridors_collect_malformed_and_all_simultaneous_old_and_new_failures():
    records = _settled_native_records(r17=True)
    for record in records[4:]:
        record["display"]["lines"] = [_actual_line((0.2, 0.20), (0.2, 0.22))]
    records[4]["display"]["texts"].append({**_actual_text(), "w": math.nan})
    records[5]["display"]["arrows"] = []
    with pytest.raises(RuntimeError) as caught:
        drawing._assert_generated_annotation_ink([_ink_sheet(*records)], _approved_detail_ink(), settled=True)
    message = str(caught.value)
    for expected in ("metric text/profile clearance", "ThreadNote/leaders vs UnderHeadLocation",
                     "UnderHeadCornerRadius vs HeadOuterChamfer", "UnderHeadCornerRadius vs HeadDia",
                     "HeadOuterChamfer vs SlotDepth", "HeadOuterChamfer vs ShoulderDia",
                     "HeadOuterChamfer vs ShoulderLength", "malformed", "arrows inventory"):
        assert expected in message


@pytest.fixture
def under_head_drawing_boundary(monkeypatch):
    """Documented native-shaped carrier; no hidden member or seat assumptions."""
    from types import SimpleNamespace
    state = SimpleNamespace(rebuilds=0, after_rebuild=None, refused_position=None)

    class Tolerance:
        __slots__ = ("Type", "lower", "upper")

        def __init__(self, radius):
            self.Type, self.lower, self.upper = (6, 0.0, 0.0) if radius else (3, -0.00015, 0.0)

        def GetMinValue(self):
            return self.lower

        def GetMaxValue(self):
            return self.upper

    class Dimension:
        __slots__ = ("FullName", "SystemValue", "Tolerance")

        def __init__(self, name):
            radius = name == "UnderHeadCornerRadius"
            self.FullName = f"{name}@ScrewProfile@Part.Part"
            self.SystemValue = 0.0001 if radius else 0.00026
            self.Tolerance = Tolerance(radius)

    class Display:
        __slots__ = ("dimension", "Type2", "primary", "tolerance", "override", "CenterText", "ArrowSide")

        def __init__(self, name):
            radius = name == "UnderHeadCornerRadius"
            self.dimension = Dimension(name)
            self.Type2 = 5 if radius else 11
            self.primary = self.tolerance = 1 if radius else 2
            self.override, self.CenterText, self.ArrowSide = False, True, 0

        def GetDimension2(self, index):
            assert index == 0
            return self.dimension

        def GetPrimaryPrecision2(self):
            return self.primary

        def GetPrimaryTolPrecision2(self):
            return self.tolerance

        def GetOverride(self):
            return self.override

    class Annotation:
        __slots__ = ("name", "display", "positions")

        def __init__(self, name):
            self.name, self.display, self.positions = name, Display(name), []

        def GetSpecificAnnotation(self):
            return self.display

        def SetPosition2(self, x, y, z):
            self.positions.append((x, y, z))
            return self.name != state.refused_position

    def rebuild():
        state.rebuilds += 1
        if state.after_rebuild:
            state.after_rebuild()

    def bind(raw, interface):
        assert isinstance(raw, {"IAnnotation": Annotation, "IDisplayDimension": Display,
                                "IDimension": Dimension, "IDimensionTolerance": Tolerance}[interface])
        return raw

    state.annotations = [Annotation(name) for name in drawing.UNDER_HEAD_DIMENSIONS]
    state.adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=rebuild))
    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, annotation: annotation.name)
    return state


def test_option2_native_under_head_style_keeps_real_bounds_and_exact_side_anchors(under_head_drawing_boundary):
    state = under_head_drawing_boundary
    drawing.style_under_head_dimensions(state.adapter, state.annotations)
    radius, bevel = state.annotations
    assert radius.positions == [(*drawing.SIDE_KEEP[radius.name], 0.0)]
    assert bevel.positions == [(*drawing.SIDE_KEEP[bevel.name], 0.0)]
    assert bevel.display.ArrowSide == drawing.ARROWS_OUTSIDE
    assert bevel.display.CenterText is False
    assert state.rebuilds == 1
    assert bevel.display.dimension.Tolerance.lower == -0.00015
    assert not radius.display.override and not bevel.display.override


@pytest.mark.parametrize("name", drawing.UNDER_HEAD_DIMENSIONS)
@pytest.mark.parametrize("fault", ["missing-dimension", "owner", "name", "type", "value", "nonfinite",
                                    "tol-type", "lower", "upper", "primary", "tolerance", "override"])
def test_option2_native_under_head_carriers_refuse_each_independent_native_drift(under_head_drawing_boundary, name, fault):
    state = under_head_drawing_boundary
    annotation = next(annotation for annotation in state.annotations if annotation.name == name)
    display, dimension = annotation.display, annotation.display.dimension
    if fault == "missing-dimension":
        display.dimension = None
    elif fault == "owner":
        dimension.FullName = f"{name}@ScrewProfileSpoof@Part.Part"
    elif fault == "name":
        dimension.FullName = "Other@ScrewProfile@Part.Part"
    elif fault == "type":
        display.Type2 = 6
    elif fault in ("value", "nonfinite"):
        dimension.SystemValue = math.nan if fault == "nonfinite" else dimension.SystemValue + 0.000002
    elif fault == "tol-type":
        dimension.Tolerance.Type = 2
    elif fault == "lower":
        dimension.Tolerance.lower += 0.000001
    elif fault == "upper":
        dimension.Tolerance.upper += 0.000001
    elif fault == "primary":
        display.primary = 3
    elif fault == "tolerance":
        display.tolerance = 3
    else:
        display.override = True
    with pytest.raises(RuntimeError, match="missing native model dimension|native owner/type/value/bounds/precision drift"):
        drawing._assert_under_head_carrier(annotation, name)


@pytest.mark.parametrize("name", drawing.UNDER_HEAD_DIMENSIONS)
@pytest.mark.parametrize("count", [0, 2])
def test_option2_native_under_head_style_requires_unique_features(under_head_drawing_boundary, name, count):
    state = under_head_drawing_boundary
    annotation = next(annotation for annotation in state.annotations if annotation.name == name)
    records = [item for item in state.annotations if item.name != name] + [annotation] * count
    with pytest.raises(RuntimeError, match=f"{name}: expected one native under-head annotation; count={count}"):
        drawing.style_under_head_dimensions(state.adapter, records)


@pytest.mark.parametrize("name", drawing.UNDER_HEAD_DIMENSIONS)
def test_option2_native_under_head_style_refuses_failed_positions(under_head_drawing_boundary, name):
    state = under_head_drawing_boundary
    state.refused_position = name
    with pytest.raises(RuntimeError, match=f"{name}: cannot position native under-head text"):
        drawing.style_under_head_dimensions(state.adapter, state.annotations)


@pytest.mark.parametrize("fault", ["bounds", "override", "style"])
def test_option2_native_under_head_style_rechecks_after_rebuild(under_head_drawing_boundary, fault):
    state = under_head_drawing_boundary
    bevel = state.annotations[1].display

    def drift():
        if fault == "bounds":
            bevel.dimension.Tolerance.lower = 0.0
        elif fault == "override":
            bevel.override = True
        else:
            bevel.ArrowSide = 0

    state.after_rebuild = drift
    with pytest.raises(RuntimeError, match="native owner/type/value/bounds/precision drift|native arrows/centring did not persist"):
        drawing.style_under_head_dimensions(state.adapter, state.annotations)
    assert state.rebuilds == 1


@pytest.mark.parametrize("primitive", ["arrow", "leader", "triangle", "polygon", "polyline"])
def test_option2_actual_under_head_foreign_ink_checks_every_real_carrier(primitive):
    records = {record["name"]: record for record in _under_head_native_records()}
    records["UnderHeadCornerRadius"]["display"]["lines"] = [_actual_line((0.2, 0.2), (0.2, 0.22))]
    record = records["HeadDia"]
    if primitive == "arrow":
        record["display"]["arrows"] = [[0.2, 0.21, 0, -1, 0, 0, 0.003, 0.001]]
    elif primitive == "leader":
        record["leaders"] = [[0.19, 0.21, 0, 0.21, 0.21, 0]]
    elif primitive == "triangle":
        record["display"]["triangles"] = [[0.19, 0.21, 0, 0.21, 0.21, 0, 0.2, 0.215, 0]]
    elif primitive == "polygon":
        record["display"]["polygons"] = [[0, 0, 0, 0, 3, 0.19, 0.21, 0, 0.21, 0.21, 0, 0.2, 0.215, 0]]
    else:
        record["display"]["polylines"] = [[0, 0, 0, 0, 0, 0, 2, 0.19, 0.21, 0, 0.21, 0.21, 0]]
    errors = drawing._settled_under_head_errors([_ink_sheet(*records.values())])
    assert any("UnderHeadCornerRadius vs HeadDia" in error and "foreign ink crossing" in error for error in errors)


@pytest.mark.parametrize("previous,replacement", [
    ("HEAD_OUTER_CHAMFER = HEAD_OUTER_CHAMFER_MAX", "HEAD_OUTER_CHAMFER = 0.25"),
    ("HEAD_OUTER_CHAMFER_BAND = (0.0, round(HEAD_OUTER_CHAMFER_MIN - HEAD_OUTER_CHAMFER_MAX, 6))",
     "HEAD_OUTER_CHAMFER_BAND = (0.0, -0.16)"),
])
def test_option2_model_nominal_and_native_band_cannot_diverge_from_proved_chamfer_limits(previous, replacement):
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert source.count(previous) == 1
    with pytest.raises(AssertionError, match="invalid outer under-head chamfer range"):
        exec(compile(source.replace(previous, replacement), spec.__file__, "exec"),
             {"__name__": "_option2_actual_chamfer_probe"})
