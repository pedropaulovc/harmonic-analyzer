"""Offline contracts for the MHA-PD-VN-57 transgear pivot screw.

Recorded recipe calls are not native geometry proof; the farm build, the
native readback in the drawing script and the sheet's machinist review own
that.
"""

from __future__ import annotations

import asyncio
import copy
import contextlib
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from _column_clamp_interface import BAR_DEPTH
import _config
import _telemetry
import build_pd_vn_transgear_pivot_screw as part
import draw_pd_vn_transgear_pivot_screw as drawing
import pd_support_bar_spec as bar
import transgear_hanger_joints as joints
import pd_vn_transgear_pivot_screw_spec as screw
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _printed_tolerance import angular_band_deg
from _stock_recipe import recipe_declaration
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_90325A174 as entry

IN = 25.4
SCRIPTS = Path(__file__).resolve().parent
UNDERHEAD = screw.SHOULDER_LEN + screw.THREAD_LEN


def test_spec_is_the_catalogue_screw() -> None:
    """90325A174 per mcmaster.com (2026-10-14): shoulder Ø3/16 x 1/2,
    8-32 UNC-2A x 3/8, hex-socket head Ø5/16 x 5/32, 3/32 drive."""
    assert screw.SKU == "90325A174"
    assert screw.CATALOG_URL == "https://www.mcmaster.com/90325A174/"
    assert screw.CATALOG_CHECKED_DATE == "2026-10-14"
    assert screw.SHOULDER_DIA == pytest.approx(3.0 / 16.0 * IN)
    assert screw.SHOULDER_LEN == pytest.approx(0.5 * IN)
    assert screw.THREAD == "#8-32"
    assert screw.THREAD_MAJOR == pytest.approx(0.164 * IN)
    assert screw.PITCH == pytest.approx(IN / 32.0)
    assert screw.THREAD_LEN == pytest.approx(3.0 / 8.0 * IN)
    # ASME B18.3-2012 Table 13 note 12: -0.020 in on the thread length.
    assert screw.THREAD_LEN_LIMITS == pytest.approx((-0.020 * IN, 0.0))
    assert screw.STOCK_THREAD_LEN_MIN == pytest.approx(9.017)
    assert screw.HEAD_DIA == pytest.approx(5.0 / 16.0 * IN)
    assert screw.HEAD_H == pytest.approx(5.0 / 32.0 * IN)
    assert screw.SOCKET_AF == pytest.approx(3.0 / 32.0 * IN)


def test_catalogue_inputs_are_pure_and_isolated_from_diagnostics() -> None:
    paths = tuple(
        map(Path, module_deps_of(SCRIPTS / "pd_vn_transgear_pivot_screw_spec.py"))
    )
    assert "_mcmaster_90325a174" in {path.stem for path in paths}
    assert not any("diagnostics" in path.parts for path in paths)
    assert not any(path.stem.startswith("build_") for path in paths)
    assert not any(path.stem in {"_com", "_session"} for path in paths)
    recipe = tuple(
        map(Path, module_deps_of(SCRIPTS / "diagnostics" / "diag_build_90325A174.py"))
    )
    assert "pd_vn_transgear_pivot_screw_spec" not in {path.stem for path in recipe}


def test_fitted_length_is_a_reference_set_by_the_bar() -> None:
    """Rule 19 fit-up: the tip is faced to stand .008-.020 below the bar's
    front face, so the printed length is the nominal bar less the window's
    middle, as a reference."""
    assert screw.TIP_RECESS == pytest.approx((0.008 * 25.4, 0.020 * 25.4))
    assert screw.FITTED_THREAD_LEN == pytest.approx(
        BAR_DEPTH - sum(screw.TIP_RECESS) / 2.0
    )
    assert screw.SHOULDER_END_Y == -screw.SHOULDER_LEN
    assert screw.TIP_Y == pytest.approx(screw.SHOULDER_END_Y - screw.FITTED_THREAD_LEN)
    assert screw.REFERENCE_DIMENSIONS == (("StockTrimProfile", "CutLength"),)
    assert screw.DIMENSION_TOLERANCE_TYPES["CutLength"] == 0
    callout = screw.DIMENSION_CALLOUTS["CutLength"]
    assert ".008-.020 BELOW MHA-PD-07" in callout
    assert "FRONT FACE AS FITTED" in callout
    # Facing only shortens: the nominal fit is inside the catalogue length,
    # and every stock length reaches the thinnest bar's deepest recess.
    assert screw.FITTED_THREAD_LEN < screw.THREAD_LEN
    thin = BAR_DEPTH - bar.BAR_DEPTH_BAND
    assert screw.STOCK_THREAD_LEN_MIN >= thin - screw.TIP_RECESS[1]
    # The corner the fit-up sets aside: ASME-short stock in the thickest bar
    # stops .004 deeper than the .020 max recess.
    thick = BAR_DEPTH + bar.BAR_DEPTH_BAND
    assert joints.PIVOT_STOCK_SHORTFALL_AT_THICKEST_BAR == pytest.approx(
        thick - screw.TIP_RECESS[1] - screw.STOCK_THREAD_LEN_MIN
    )
    assert joints.PIVOT_STOCK_SHORTFALL_AT_THICKEST_BAR == pytest.approx(
        0.1016, abs=1e-3
    )


def test_engagement_charges_one_pitch_and_the_neck() -> None:
    """Worst case: the thinnest bar, the deepest recess, one incomplete pitch
    at the faced tip and the neck before the full thread starts."""
    thin = BAR_DEPTH - bar.BAR_DEPTH_BAND
    assert joints.PIVOT_FITTED_LEN_MIN == pytest.approx(thin - screw.TIP_RECESS[1])
    worst = joints.PIVOT_FITTED_LEN_MIN - screw.PITCH - screw.FULL_THREAD_START
    assert joints.PIVOT_ENGAGEMENT_WORST == pytest.approx(worst)
    assert joints.PIVOT_ENGAGEMENT_WORST_D >= screw.ENGAGEMENT_MIN_D
    # The printed minimum rounds up to the .001 inch grid.
    assert screw.THREAD_LENGTH_MIN == pytest.approx(
        math.ceil((1.5 * screw.THREAD_MAJOR + screw.PITCH) / 0.0254 - 1e-9) * 0.0254
    )


def test_chamfer_max_keeps_the_tip_inside_the_charged_pitch() -> None:
    # The model stands at the printed maximum (swTolMAX prints the nominal).
    assert screw.CHAMFER_WIDTH == screw.CHAMFER_WIDTH_MAX == pytest.approx(0.024 * 25.4)
    assert screw.CHAMFER_ANGLE_TOLERANCE == angular_band_deg(unit=screw.UNIT) == 1.0
    steepest = math.radians(screw.CHAMFER_ANGLE + screw.CHAMFER_ANGLE_TOLERANCE)
    assert screw.CHAMFER_AXIAL_MAX == pytest.approx(screw.CHAMFER_WIDTH * math.tan(steepest))
    assert screw.CHAMFER_AXIAL_MAX <= screw.INCOMPLETE_TIP_LEN_MAX == screw.PITCH
    # "Past the thread root" fits under the maximum: tip Ø 4.1656 - 1.2192 =
    # 2.9464 clears the deepest estimated 2A root Ø3.038.
    screw.require_chamfer_past_root(screw.CHAMFER_WIDTH)
    assert "THREAD ROOT" in screw.DIMENSION_CALLOUTS["ChamferWidth"]


def test_minor_diameter_is_the_external_2a_root() -> None:
    """#8-32 UNC-2A (Kennametal UN tables): UNR minor max 0.1248 in; the
    deepest root estimate is 0.649519 P under the 0.1399 in PD minimum."""
    # 0.1631 - 1.226869/32 = 0.12476 in, tabled as 0.1248 in.
    assert screw.THREAD_MINOR_UNR_2A_MAX == pytest.approx(3.1689, abs=1e-4)
    assert screw.THREAD_MINOR_2A_MIN_EST == pytest.approx(3.0379, abs=1e-4)
    assert screw.THREAD_MINOR_2A_MIN_EST < screw.THREAD_MINOR_UNR_2A_MAX


@pytest.mark.parametrize(
    "chamfer_width_max",
    [
        0.45,  # tip Ø 3.2656: above even the shallowest root, Ø3.170.
        0.55,  # tip Ø 3.0656: under the shallowest root, above the deepest.
    ],
)
def test_chamfer_that_misses_the_deepest_root_is_refused(
    chamfer_width_max: float,
) -> None:
    with pytest.raises(AssertionError, match="thread root"):
        screw.require_chamfer_past_root(chamfer_width_max)


class _Recorder:
    """A fake SolidWorks that records every call a recipe makes."""

    def __init__(self) -> None:
        self.events: list[tuple] = []
        recorder = self

        class _Obj:
            def __init__(self, name: str) -> None:
                self._name = name

            def __getattr__(self, attr: str):
                if attr.startswith("_"):
                    raise AttributeError(attr)

                def call(*args, **kwargs):
                    recorder.log(f"{self._name}.{attr}", args, kwargs)
                    return _Obj(f"{self._name}.{attr}()")

                return call

        self.currentSketchManager = _Obj("sketch")
        self.currentModel = _Obj("model")

    def log(self, name: str, args=(), kwargs=None) -> None:
        self.events.append((name, tuple(args), dict(kwargs or {})))

    async def _async(self, name: str, *args, **kwargs):
        self.log(name, args, kwargs)
        return "ok"

    async def create_sketch(self, *args):
        return await self._async("create_sketch", *args)

    async def exit_sketch(self, *args):
        return await self._async("exit_sketch", *args)

    async def create_extrusion(self, *args):
        return await self._async("create_extrusion", *args)

    async def create_cut_extrude(self, *args):
        return await self._async("create_cut_extrude", *args)

    async def create_revolve(self, *args):
        return await self._async("create_revolve", *args)

    async def add_chamfer(self, *args):
        return await self._async("add_chamfer", *args)


# Two bodies after the split at the neck's land bottom: the head-and-shoulder
# body ends there, the threaded tail runs from there to the tip.
_SPLIT_BODIES = [
    {"name": "Head", "box_mm": [-4.0, entry.Y_LAND_BOT, -4.0, 4.0, 4.0, 4.0]},
    {
        "name": "Tail",
        "box_mm": [-2.1, -UNDERHEAD, -2.1, 2.1, entry.Y_LAND_BOT, 2.1],
    },
]


def _record(monkeypatch, bodies=_SPLIT_BODIES) -> _Recorder:
    adapter = _Recorder()

    def logger(name, result=None):
        def call(*args, **kwargs):
            adapter.log(name, args, kwargs)
            return result

        return call

    def com_logger(name):
        def call(_adapter, *args, **kwargs):
            adapter.log(name, args, kwargs)

        return call

    def async_logger(name):
        async def call(_adapter, *args, **kwargs):
            adapter.log(name, args, kwargs)

        return call

    async def volume_check(_adapter, label, expected, tol):
        adapter.log("volume_check", (label, expected, tol))
        return expected

    @contextlib.contextmanager
    def no_inference(_adapter):
        yield

    def split(_adapter, plane, name):
        adapter.log("split_at_plane", (plane, name))
        return bodies

    monkeypatch.setattr(entry, "check", logger("check", True))
    monkeypatch.setattr(entry, "name_last_feature", com_logger("name_last_feature"))
    monkeypatch.setattr(entry, "volume_check", volume_check)
    monkeypatch.setattr(entry, "define_circle", async_logger("define_circle"))
    monkeypatch.setattr(entry, "add_line_chain", async_logger("add_line_chain"))
    monkeypatch.setattr(entry, "extrude_at_offset", com_logger("extrude_at_offset"))
    monkeypatch.setattr(entry, "offset_plane", com_logger("offset_plane"))
    monkeypatch.setattr(entry, "insert_helix", com_logger("insert_helix"))
    monkeypatch.setattr(entry, "thread_sweep_cut", com_logger("thread_sweep_cut"))
    monkeypatch.setattr(entry, "combine_union", com_logger("combine_union"))
    monkeypatch.setattr(entry, "split_at_plane", split)
    monkeypatch.setattr(entry, "no_sketch_inference", no_inference)
    monkeypatch.setattr(_telemetry, "info", lambda *a, **k: None)
    asyncio.run(entry.build_90325A174(adapter))
    return adapter


def _calls(events, name):
    return [c for c in events if c[0] == name]


def test_recipe_stacks_head_shoulder_and_thread_on_the_shoulder_face(
    monkeypatch,
) -> None:
    calls = _record(monkeypatch).events
    # Head, shoulder and shank circles on the Top Plane (the shoulder face).
    radii = [c[1][2] for c in _calls(calls, "define_circle")]
    assert radii == pytest.approx(
        [screw.HEAD_DIA / 2.0, screw.SHOULDER_DIA / 2.0, screw.THREAD_MAJOR / 2.0]
    )
    head = _calls(calls, "create_extrusion")[0][1][0]
    assert head.depth == pytest.approx(screw.HEAD_H)
    # The shoulder hangs from y = 0 and the thread from the shoulder's end.
    offsets = [c[1] for c in _calls(calls, "extrude_at_offset")]
    assert offsets == [
        pytest.approx((screw.SHOULDER_LEN, -screw.SHOULDER_LEN)),
        pytest.approx((screw.THREAD_LEN, -UNDERHEAD)),
    ]


def test_hex_socket_is_cut_down_from_the_head_top_and_stops_inside_it(
    monkeypatch,
) -> None:
    calls = _record(monkeypatch).events
    assert ("offset_plane", ("HeadTop", pytest.approx(screw.HEAD_H)), {}) in calls
    socket = _calls(calls, "add_line_chain")[1][1][0]
    assert len(socket) == 6
    flats = sorted({round(abs(x), 9) for x, _y in socket})
    assert flats == pytest.approx([0.0, screw.SOCKET_AF / 2.0])
    corner = max(math.hypot(x, y) for x, y in socket)
    assert corner == pytest.approx(screw.SOCKET_AF / math.sqrt(3.0))
    assert corner < screw.HEAD_DIA / 2.0 - screw.HEAD_CHAMFER
    (cut,) = _calls(calls, "create_cut_extrude")
    assert cut[1][0].depth == pytest.approx(screw.SOCKET_DEPTH)
    assert 0.0 < cut[1][0].depth < screw.HEAD_H


def test_neck_regains_the_major_where_the_joint_counts_full_thread(
    monkeypatch,
) -> None:
    """The revolved neck cut: fillet off the shoulder's end face into the
    land, then a 45 deg flank that reaches the thread major exactly
    FULL_THREAD_START below that face -- where the joint starts counting."""
    calls = _record(monkeypatch).events
    (revolve,) = _calls(calls, "create_revolve")
    assert revolve[1][0].is_cut
    assert revolve[1][0].angle == pytest.approx(360.0)
    end_face = -screw.SHOULDER_LEN
    major_r = screw.THREAD_MAJOR / 2.0
    neck_r = screw.NECK_DIA / 2.0
    (arc,) = _calls(calls, "sketch.CreateArc")
    centre, start, stop = ([v * 1000.0 for v in arc[1][i : i + 2]] for i in (0, 3, 6))
    assert start == pytest.approx([major_r, end_face])
    assert stop == pytest.approx([neck_r, end_face - entry.NECK_FILLET_R])
    assert centre == pytest.approx([major_r, end_face - entry.NECK_FILLET_R])
    neck_chain = _calls(calls, "add_line_chain")[0][1][0]
    land_top, land_bot, flank_end = neck_chain[:3]
    assert land_top[0] == land_bot[0] == pytest.approx(neck_r)
    assert land_bot[1] == pytest.approx(end_face - entry.NECK_FLAT_END)
    rise = flank_end[0] - land_bot[0]
    assert land_bot[1] - flank_end[1] == pytest.approx(rise)
    assert flank_end[0] > major_r
    y_at_major = land_bot[1] - (major_r - land_bot[0])
    assert y_at_major == pytest.approx(end_face - screw.FULL_THREAD_START)


def test_thread_is_cut_on_the_tail_below_the_neck_land(monkeypatch) -> None:
    calls = _record(monkeypatch).events
    (helix,) = _calls(calls, "insert_helix")
    pitch, revs = helix[1][0:2]
    assert pitch == pytest.approx(screw.PITCH)
    assert revs * pitch == pytest.approx(screw.THREAD_LEN)
    assert ("offset_plane", ("TipPlane", pytest.approx(-UNDERHEAD)), {}) in calls
    split_plane = next(
        c for c in _calls(calls, "offset_plane") if c[1][0] == "SplitPlane"
    )
    assert split_plane[1][1] == pytest.approx(-screw.SHOULDER_LEN - entry.NECK_FLAT_END)
    assert ("split_at_plane", ("SplitPlane", "TailSplit"), {}) in calls
    (sweep,) = _calls(calls, "thread_sweep_cut")
    assert sweep[1][2:4] == ("Tail", "ThreadGroove")
    assert _calls(calls, "combine_union")


def test_recipe_refuses_a_split_that_leaves_no_single_tail(monkeypatch) -> None:
    whole = [dict(_SPLIT_BODIES[0], box_mm=[-4.0, -UNDERHEAD, -4.0, 4.0, 4.0, 4.0])]
    with pytest.raises(RuntimeError, match="below the neck land"):
        _record(monkeypatch, bodies=whole)


def test_fleet_diagnostic_driver_gates_the_new_sku() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[screw.SKU] is entry.build_90325A174
    assert "91829A205" not in REGISTRY


def test_stock_build_faces_its_registered_recipe_head_up_on_the_origin(
    monkeypatch,
) -> None:
    metadata = discovered_recipes()[screw.SKU]
    assert metadata.module == entry.__name__
    assert metadata.callable_name == entry.build_90325A174.__name__
    assert metadata.threaded
    assert FASTENERS[part.PART_NAME] is part.SPEC
    assert part.SPEC.skus == (screw.SKU,)
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-VN-57"
    assert row["supplier_skus"] == [screw.SKU]
    assert row["stock_name"] == part.SPEC.stock_name

    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == screw.SKU
    # The facing wraps the complete stock recipe: same declaration, new cut.
    assert component.author is not entry.build_90325A174
    assert recipe_declaration(component.sku, component.author) == recipe_declaration(
        screw.SKU, entry.build_90325A174
    )
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert component.transform.rotation_radians == (0.0, 0.0, 0.0)
    assert seen["material"] == part.SPEC.material
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")


def test_native_controls_are_owned_and_the_length_prints_as_reference() -> None:
    assert set(drawing.EXPECTED_CONTROLS) == {
        "ChamferWidth",
        "ChamferAngle",
        "ThreadLengthMin",
    }
    assert set(screw.DIMENSION_PRECISION) == {"CutLength", *drawing.EXPECTED_CONTROLS}
    assert set(drawing.FRONT_KEEP) == set(screw.DIMENSION_PRECISION)
    assert drawing.EXPECTED_CONTROLS["ChamferWidth"] == pytest.approx(
        (0.024 * 0.0254, 0.0, 0.0)
    )
    assert drawing.EXPECTED_CONTROLS["ChamferAngle"] == pytest.approx(
        (math.radians(45.0), -math.radians(1.0), math.radians(1.0))
    )
    assert screw.DIMENSION_TOLERANCE_TYPES == {
        "CutLength": 0,
        "ChamferWidth": 6,
        "ChamferAngle": 11,
        "ThreadLengthMin": 5,
    }
    assert "ChamferAngle" not in screw.DIMENSION_CALLOUTS
    assert all("\\n" not in text for text in screw.DIMENSION_CALLOUTS.values())
    assert screw.DIMENSION_CALLOUTS["ThreadLengthMin"].startswith("#8-32 UNC ")
    assert "1 PITCH MAX" in screw.DIMENSION_CALLOUTS["ThreadLengthMin"]
    assert all("2A" not in text for text in screw.DIMENSION_CALLOUTS.values())
    reason = screw.DIMENSION_CALLOUTS["ChamferWidth"].replace("MHA-PD-07", "")
    assert not any(character.isdigit() for character in reason)
    assert drawing.ISO_SCALE == drawing.SHEET_SCALE


def test_registry_row_is_the_faced_stock_without_sheet_instructions() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["title"] == "Transgear Pivot Screw"
    # The title block's break-edge row covers the faced end's deburr.
    assert row["finish"] == "AS SUPPLIED"
    note = row["purchased_note"]
    assert note.startswith(f"PURCHASED SCREW McMASTER {screw.SKU}")
    assert "\n" not in note
    assert not any(character.isdigit() for character in note.replace(screw.SKU, ""))
    # The fit-up, stake and optional threadlocker are assembly-sheet steps.
    assert "installation_notes" not in row
    spec = DRAWINGS_BY_NAME["pd_vn_transgear_pivot_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()


class _HeadSelection:
    """Only in-memory selections; no adapter or host actions."""

    def __init__(self) -> None:
        self.selected = []
        self.calls = []
        self.clear_count = 0
        self.count_offset = 0
        self.types = {}
        self.actual = {}
        self.refuse_index = 0
        self.point_result = True
        self.points = {}

    def ClearSelection2(self, _all):
        self.clear_count += 1
        self.selected.clear()

    def CreateSelectData(self):
        return SimpleNamespace(View=None)

    def select(self, edge, append, data):
        index = len(self.selected) + 1 if append else 1
        self.calls.append(("select", index, edge, append, data.View))
        if index == self.refuse_index:
            return False
        if not append:
            self.selected.clear()
        self.selected.append(edge)
        return True

    def GetSelectedObjectCount2(self, mark):
        assert mark == -1
        return len(self.selected) + self.count_offset

    def GetSelectedObjectType3(self, index, mark):
        assert mark == -1
        return self.types.get(index, 1)

    def GetSelectedObject6(self, index, mark):
        assert mark == -1
        return self.actual.get(index, self.selected[index - 1])

    def SetSelectionPoint2(self, index, mark, x, y, z):
        self.calls.append(("point", index, mark, x, y, z))
        self.points[index] = (x, y, z)
        return self.point_result

    def GetSelectionPoint2(self, index, mark):
        assert mark == -1
        return self.points[index]


class _HeadRim:
    def __init__(self, selection, circle, *, nearest=None):
        self.selection = selection
        self.circle = circle
        self.nearest = nearest
        self.probes = []

    def GetClosestPointOn(self, *point):
        self.probes.append(point)
        if self.nearest is not None:
            return self.nearest
        return (*point, 0.0, 0.0)

    def Select4(self, append, data):
        return self.selection.select(self, append, data)

    def GetCurve(self):
        circle = self.circle
        return SimpleNamespace(CircleParams=(
            *(value / 1000 for value in circle[:3]),
            *circle[3:6], circle[6] / 1000,
        ))


def _physical_head_fixture(monkeypatch):
    """Real recipe/shared measurement logic over explicitly bounded no-COM doubles."""
    import _drawing_edge_dimensions as edge_dimensions
    import _drawing_physical_axial_dimension as physical_height
    from _drawing_edges import ViewEdge, ViewEdges

    selection = _HeadSelection()
    front = SimpleNamespace(
        name="FinishedFront", mode=2, ReferencedConfiguration="Default", dimensions=[],
        ScaleDecimal=4.0,
    )
    front.GetDisplayMode2 = lambda: front.mode
    front.GetDisplayDimensions = lambda: tuple(front.dimensions)
    front.GetNextView = lambda: None
    bearing = _HeadRim(selection, (0.0, 0.0, 0.0, 0.0, 1.0, 0.0, screw.HEAD_DIA / 2))
    top = _HeadRim(selection, (
        0.0, screw.HEAD_H, 0.0, 0.0, -1.0, 0.0,
        screw.HEAD_DIA / 2 - screw.HEAD_CHAMFER,
    ))
    annotation = SimpleNamespace(
        attached=[bearing, top], kinds=(1, 1), dangling=False,
        count=2, Owner=front, OwnerType=0, Visible=1,
    )
    annotation.GetAttachedEntities3 = lambda: tuple(annotation.attached)
    annotation.GetAttachedEntityTypes = lambda: annotation.kinds
    annotation.GetAttachedEntityCount3 = lambda: annotation.count
    annotation.IsDangling = lambda: annotation.dangling
    arrows = [
        (0.224, 0.190 + 4 * point[1], 0.0, 0.0, direction, 0.0,
         0.001, 0.001, 0.0, 0.0, 0.0, 1.0)
        for point, direction in zip(drawing._head_height_points(), (1.0, -1.0), strict=True)
    ]
    display_data = SimpleNamespace(
        GetArrowHeadCount=lambda: len(arrows),
        GetArrowHeadAtIndex2=lambda index: arrows[index],
    )
    annotation.GetDisplayData = lambda: display_data
    tolerance = SimpleNamespace(Type=0)
    native = SimpleNamespace(
        SystemValue=screw.HEAD_H / 1000, FullName="D2@FinishedFront", Tolerance=tolerance,
    )
    presentation = screw.SUPPLIER_REFERENCE_DIMENSIONS["SupplierHeadHeight"]
    texts = {1: "(", 2: " in)", 4: presentation.get("callout", "")}
    display = SimpleNamespace(
        Type2=2, ShowDimensionValue=True, ShowParenthesis=False,
        GetDimension2=lambda _index: native, GetAnnotation=lambda: annotation,
        GetUseDocUnits=lambda: False, GetUnits=lambda: 3,
        GetPrimaryPrecision2=lambda: presentation["precision"],
        GetFractionBase=lambda: 1, GetOverride=lambda: False,
        GetText=lambda index: texts[index],
    )
    annotation.GetSpecificAnnotation = lambda: display
    front.dimensions.append(display)
    model = SimpleNamespace(
        SelectionManager=selection, ClearSelection2=selection.ClearSelection2,
    )
    state = SimpleNamespace(
        adapter=SimpleNamespace(currentModel=model), selection=selection, front=front,
        bearing=bearing, top=top, annotation=annotation, display=display, native=native,
        model=model, texts=texts, tolerance=tolerance, activate_result=True,
        create_result=display, scans=[], projections=[], events=[], additions=[],
        arrows=arrows, display_data=display_data,
    )
    model.ActivateView = lambda name: (
        selection.calls.append(("activate", name)) or state.activate_result
    )

    def add_vertical(*position):
        state.additions.append(position)
        return state.create_result

    model.AddVerticalDimension2 = add_vertical
    state.adapter.swApp = SimpleNamespace(IsSame=lambda first, second: int(first is second))

    def item(edge, circle=None):
        return ViewEdge(edge=edge, line=None, circle=circle or edge.circle, vertices=None)

    state.item = item
    state.edges = [item(bearing), item(top)]

    def scan(view, *, label):
        state.scans.append((state.adapter.currentModel, view, label))
        edges = state.stock.edges if hasattr(state, "stock") and view is state.stock.view else state.edges
        return ViewEdges(label=label, edges=tuple(edges))

    def project(_adapter, view, points, *, label):
        points = tuple(points)
        state.projections.append((view, points, label))
        return tuple((0.140 + 4 * x, 0.190 + 4 * y) for x, y, _z in points)

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(edge_dimensions, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(physical_height, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        edge_dimensions._sw_type_info, "early_bound_or_flag",
        lambda value, _kind, *_members: value,
    )
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(physical_height, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(drawing, "scan_view_edges", scan)
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(physical_height, "model_points_in_view", project)
    monkeypatch.setattr(
        _telemetry, "event", lambda name, **fields: state.events.append((name, fields))
    )
    return state


def test_physical_head_height_names_exact_outer_rims_and_arc_points(monkeypatch) -> None:
    state = _physical_head_fixture(monkeypatch)
    # Same supporting circle, wrong finite arc: CircleParams cannot name this edge.
    other_arc = _HeadRim(
        state.selection, state.top.circle, nearest=(0.0, screw.HEAD_H / 1000, -0.004, 0, 0)
    )
    lower_junction = _HeadRim(state.selection, (
        0.0, screw.HEAD_H - screw.HEAD_CHAMFER, 0.0,
        0.0, 1.0, 0.0, screw.HEAD_DIA / 2,
    ))
    socket = _HeadRim(state.selection, (
        0.0, screw.HEAD_H, 0.0, 0.0, 1.0, 0.0, screw.SOCKET_AF / math.sqrt(3),
    ))
    state.edges[:0] = [state.item(edge) for edge in (other_arc, lower_junction, socket)]
    assert drawing._head_height_entities(state.adapter, state.front) == (
        state.bearing, state.top,
    )
    bearing_point, top_point = drawing._head_height_points()
    assert bearing_point == pytest.approx((
        screw.HEAD_DIA / 2 / math.sqrt(2) / 1000, 0.0,
        screw.HEAD_DIA / 2 / math.sqrt(2) / 1000,
    ))
    assert top_point == pytest.approx((
        (screw.HEAD_DIA / 2 - screw.HEAD_CHAMFER) / math.sqrt(2) / 1000,
        screw.HEAD_H / 1000,
        (screw.HEAD_DIA / 2 - screw.HEAD_CHAMFER) / math.sqrt(2) / 1000,
    ))
    assert state.bearing.probes == [bearing_point]
    assert state.top.probes == other_arc.probes == [top_point]
    assert not lower_junction.probes and not socket.probes
    assert not state.selection.calls  # Discovery is not a hit-test or selection.


@pytest.mark.parametrize("change", (
    "missing_bearing", "missing_top", "duplicate_bearing", "duplicate_top",
    "lower_chamfer", "socket_radius", "wrong_axis", "center_shift", "radius_shift",
    "wrong_arc", "unreadable_arc", "nan_geometry",
))
def test_physical_head_height_refuses_wrong_missing_or_ambiguous_geometry(
    monkeypatch, change,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    if change.startswith("missing"):
        state.edges.pop(0 if change == "missing_bearing" else 1)
    elif change.startswith("duplicate"):
        edge = state.bearing if change == "duplicate_bearing" else state.top
        state.edges.append(state.item(_HeadRim(state.selection, edge.circle)))
    elif change == "wrong_arc":
        state.top.nearest = (0.0, screw.HEAD_H / 1000, -0.004, 0, 0)
    elif change == "unreadable_arc":
        state.top.nearest = ()
    else:
        circle = list(state.top.circle)
        if change == "lower_chamfer":
            circle[1] -= screw.HEAD_CHAMFER
            circle[6] = screw.HEAD_DIA / 2
        elif change == "socket_radius":
            circle[6] = screw.SOCKET_AF / math.sqrt(3)
        elif change == "wrong_axis":
            circle[3:6] = (1.0, 0.0, 0.0)
        elif change == "center_shift":
            circle[0] = 2e-5
        elif change == "radius_shift":
            circle[6] += 2e-5
        elif change == "nan_geometry":
            circle[0] = float("nan")
        state.edges[1] = state.item(state.top, tuple(circle))
    with pytest.raises(RuntimeError, match="physical rim has .* matches"):
        drawing._head_height_entities(state.adapter, state.front)
    assert state.events
    assert all(len(fields["candidates"]) <= 12 for _name, fields in state.events)
    assert not state.additions


def test_physical_head_height_refusal_has_bounded_nearest_circle_evidence(monkeypatch) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.edges = [
        state.item(_HeadRim(state.selection, (
            0.0, float(index + 1), 0.0, 0.0, 1.0, 0.0, screw.HEAD_DIA / 2,
        )))
        for index in range(30)
    ]
    with pytest.raises(RuntimeError, match="bearing physical rim"):
        drawing._head_height_entities(state.adapter, state.front)
    _name, evidence = state.events[-1]
    assert evidence["candidate_count"] == 30
    assert len(evidence["candidates"]) == 12
    assert evidence["candidates"][0]["circle_mm"][1] == 1.0


def test_physical_head_height_refuses_one_entity_at_both_stations(monkeypatch) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.edges[1] = state.item(state.bearing, state.top.circle)
    with pytest.raises(RuntimeError, match="not distinct"):
        drawing._head_height_entities(state.adapter, state.front)


@pytest.mark.parametrize("mode", (0, 1, 3, 7))
def test_physical_head_height_requires_actual_hlr_mode(monkeypatch, mode) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.front.mode = mode
    with pytest.raises(RuntimeError, match="hidden-lines-removed"):
        drawing._head_height_entities(state.adapter, state.front)
    assert not state.scans


def test_physical_head_height_uses_strict_entity_selection_and_native_vertical_dimension(
    monkeypatch,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    result = drawing._add_physical_head_height(state.adapter, state.front, (0.224, 0.201))
    assert result is state.display
    calls = state.selection.calls
    assert calls[0] == ("activate", state.front.name)
    assert [call for call in calls if call[0] == "select"] == [
        ("select", 1, state.bearing, False, state.front),
        ("select", 2, state.top, True, state.front),
    ]
    projected = [
        (0.140 + 4 * x, 0.190 + 4 * y) for x, y, _z in drawing._head_height_points()
    ]
    assert [call for call in calls if call[0] == "point"] == [
        ("point", index, -1, *point, 0.0)
        for index, point in enumerate(projected, 1)
    ]
    assert state.additions == [(0.224, 0.201, 0.0)]
    assert len(state.scans) == 1  # Creation reuses its strictly resolved physical pair.
    assert state.selection.clear_count == 2
    assert not state.selection.selected


@pytest.mark.parametrize("fault, index, message", (
    ("activate", 0, "activate exact front"),
    ("select", 1, "failed to select"),
    ("select", 2, "failed to select"),
    ("count", 1, "selection count"),
    ("type", 1, "not an EDGE"),
    ("type", 2, "not an EDGE"),
    ("missing", 1, "wrong selected object"),
    ("missing", 2, "wrong selected object"),
    ("wrong", 1, "wrong selected object"),
    ("wrong", 2, "wrong selected object"),
    ("same", 2, "wrong selected object"),
    ("point", 1, "selection point"),
    ("null", 0, "returned null"),
))
def test_physical_head_height_refuses_bad_native_selection_and_creation(
    monkeypatch, fault, index, message,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    if fault == "activate":
        state.activate_result = False
    elif fault == "select":
        state.selection.refuse_index = index
    elif fault == "count":
        state.selection.count_offset = 1
    elif fault == "type":
        state.selection.types[index] = 46
    elif fault == "missing":
        state.selection.actual[index] = None
    elif fault == "wrong":
        state.selection.actual[index] = object()
    elif fault == "same":
        state.selection.actual[index] = state.bearing
    elif fault == "point":
        state.selection.point_result = False
    elif fault == "null":
        state.create_result = None
    with pytest.raises(RuntimeError, match=message):
        drawing._add_physical_head_height(state.adapter, state.front, (0.224, 0.201))
    assert not state.selection.selected
    assert state.selection.clear_count >= 1
    assert not state.additions or fault == "null"


@pytest.mark.parametrize("phase", ("creation", "settled"))
@pytest.mark.parametrize("fault, message", (
    ("wrong_value", "measures"),
    ("null_value", "no measured native value"),
    ("wrong_attachment", "named entities"),
    ("same_attachment", "named entities"),
    ("null_attachment", "two nonnull actual edge attachments"),
    ("extra_attachment", "two nonnull actual edge attachments"),
    ("attachment_count", "two nonnull actual edge attachments"),
    ("attachment_type", "two nonnull actual edge attachments"),
    ("dangling", "two nonnull actual edge attachments"),
    ("missing_native", "no native model dimension"),
    ("dimension_type", "expected linear dimension Type2=2"),
    ("legacy_vertical_dimension_type", "expected linear dimension Type2=2"),
    ("unknown_owner", "exact front-view owner"),
    ("malformed_kinds", "int"),
    ("owner_type", "exact front-view owner"),
    ("missing_owner", "exact front-view owner"),
    ("wrong_owner", "exact front-view owner"),
))
def test_physical_head_height_proves_creation_and_settled_native_state(
    monkeypatch, phase, fault, message,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    if phase == "settled":
        drawing._add_physical_head_height(state.adapter, state.front, (0.224, 0.201))
    if fault == "wrong_value":
        state.native.SystemValue = (screw.HEAD_H - screw.HEAD_CHAMFER) / 1000
    elif fault == "null_value":
        state.native.SystemValue = None
    elif fault == "wrong_attachment":
        state.annotation.attached[1] = object()
    elif fault == "same_attachment":
        state.annotation.attached[1] = state.bearing
    elif fault == "null_attachment":
        state.annotation.attached[1] = None
    elif fault == "extra_attachment":
        state.annotation.attached.append(object())
    elif fault == "attachment_count":
        state.annotation.count = 3
    elif fault == "attachment_type":
        state.annotation.kinds = (1, 46)
    elif fault == "dangling":
        state.annotation.dangling = True
    elif fault == "missing_native":
        state.display.GetDimension2 = lambda _index: None
    elif fault == "dimension_type":
        state.display.Type2 = 11
    elif fault == "legacy_vertical_dimension_type":
        state.display.Type2 = 12
    elif fault == "unknown_owner":
        state.adapter.swApp.IsSame = lambda first, second: (
            2 if first is state.annotation.Owner and second is state.front
            else int(first is second)
        )
    elif fault == "malformed_kinds":
        state.annotation.kinds = (1, None)
    elif fault == "owner_type":
        state.annotation.OwnerType = 1
    elif fault == "missing_owner":
        state.annotation.Owner = None
    elif fault == "wrong_owner":
        state.annotation.Owner = SimpleNamespace(name=state.front.name)
    with pytest.raises(RuntimeError, match=message) as refusal:
        if phase == "creation":
            drawing._add_physical_head_height(state.adapter, state.front, (0.224, 0.201))
        else:
            drawing._assert_physical_head_height(state.adapter, state.front, state.display)
    assert not state.selection.selected
    evidence = state.events[-1]
    assert evidence[0] == "drawing.physical_axial_dimension_native_refusal"
    if fault == "malformed_kinds":
        assert evidence[1]["kinds"] == (1, None)
        assert evidence[1]["kinds_length"] == 2
        assert isinstance(refusal.value.__cause__, TypeError)


def test_physical_head_height_valid_linear_type_requires_native_spatial_proof(
    monkeypatch,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    assert drawing._assert_physical_head_height(
        state.adapter, state.front, state.display, entities=(state.bearing, state.top),
    ) == screw.HEAD_H
    assert state.events[-1][0] == "drawing.physical_axial_dimension_native_proof"
    assert state.projections[-1][1] == drawing._head_height_points()
    assert not state.scans  # Explicit creation pair does not trigger a second scan.


def test_physical_head_height_accepts_exact_edge_bijection_in_reverse_order(monkeypatch) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.annotation.attached.reverse()
    assert drawing._assert_physical_head_height(
        state.adapter, state.front, state.display,
    ) == screw.HEAD_H
    assert len(state.scans) == 1
    assert state.events[-1][0] == "drawing.physical_axial_dimension_native_proof"


@pytest.mark.parametrize("missing", ("display", "annotation", "attached", "kinds"))
def test_physical_head_height_missing_metadata_has_precise_snapshot(monkeypatch, missing) -> None:
    state = _physical_head_fixture(monkeypatch)
    display = state.display
    if missing == "display":
        display = None
    elif missing == "annotation":
        state.display.GetAnnotation = lambda: None
    elif missing == "attached":
        state.annotation.GetAttachedEntities3 = lambda: None
    else:
        state.annotation.GetAttachedEntityTypes = lambda: None
    with pytest.raises(RuntimeError) as refusal:
        drawing._assert_physical_head_height(
            state.adapter, state.front, display, entities=(state.bearing, state.top),
        )
    evidence = state.events[-1][1]
    if missing == "display":
        assert "native display dimension is null" in str(refusal.value)
        assert evidence["display_null"] is True
    elif missing == "annotation":
        assert "native dimension has no annotation" in str(refusal.value)
        assert evidence["annotation_null"] is True
    else:
        assert "expected two nonnull actual edge attachments" in str(refusal.value)
        assert evidence["attached_length" if missing == "attached" else "kinds_length"] == 0


def test_physical_head_height_refusal_bounds_native_metadata(monkeypatch) -> None:
    state = _physical_head_fixture(monkeypatch)
    reads = []

    class BoundedNativeArray:
        def __init__(self, name, length, value):
            self.name, self.length, self.value = name, length, value

        def __len__(self):
            return self.length

        def __getitem__(self, index):
            assert 0 <= index < 4
            reads.append((self.name, index))
            return self.value

        def __iter__(self):
            raise AssertionError("Must not traverse an unbounded native collection")

    state.annotation.GetAttachedEntities3 = lambda: BoundedNativeArray("attached", 200, state.top)
    state.annotation.GetAttachedEntityTypes = lambda: BoundedNativeArray("kinds", 300, 46)
    state.display.Type2 = 2
    with pytest.raises(RuntimeError, match="expected two nonnull actual edge attachments"):
        drawing._assert_physical_head_height(
            state.adapter, state.front, state.display, entities=(state.bearing, state.top),
        )
    evidence = state.events[-1][1]
    assert evidence["attached_length"] == 200
    assert evidence["kinds_length"] == 300
    assert evidence["kinds"] == (46,) * 4
    assert evidence["attached_nulls"] == (False,) * 4
    assert reads == [(name, index) for name in ("attached", "kinds") for index in range(4)]


def test_physical_head_height_refusal_diagnostic_error_remains_visible(monkeypatch) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.display.Type2 = 2

    def broken_display_data():
        raise RuntimeError("native display data failed")

    state.annotation.GetDisplayData = broken_display_data
    with pytest.raises(RuntimeError, match="native display data failed") as refusal:
        drawing._assert_physical_head_height(
            state.adapter, state.front, state.display, entities=(state.bearing, state.top),
        )
    assert str(refusal.value.__cause__) == "native display data failed"
    assert state.events[-1][1]["failure_error"] == "native display data failed"


@pytest.mark.parametrize("phase", ("metadata", "display_data"))
@pytest.mark.parametrize("error_type", (Exception, OSError))
def test_physical_head_height_native_errors_preserve_partial_evidence_and_cause(
    monkeypatch, phase, error_type,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    error = error_type("native transport failed")

    def broken_native_read():
        raise error

    if phase == "metadata":
        state.annotation.IsDangling = broken_native_read
    else:
        state.display.Type2 = 2
        state.annotation.GetDisplayData = broken_native_read
    with pytest.raises(RuntimeError, match="native transport failed") as refusal:
        drawing._assert_physical_head_height(
            state.adapter, state.front, state.display, entities=(state.bearing, state.top),
        )
    assert refusal.value.__cause__ is error
    evidence = state.events[-1][1]
    assert evidence["attached_count"] == 2
    assert evidence["attached_length"] == 2
    assert evidence["kinds"] == (1, 1)
    assert evidence["failure_error_type"] == error_type.__name__
    assert evidence["failure_error"] == "native transport failed"


def test_physical_head_height_refusal_reads_each_native_metadata_getter_once(monkeypatch) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.display.Type2 = 12
    calls = []
    for name in (
        "GetAttachedEntities3", "GetAttachedEntityTypes", "GetAttachedEntityCount3", "IsDangling",
    ):
        original = getattr(state.annotation, name)

        def read_once(original=original, name=name):
            calls.append(name)
            return original()

        monkeypatch.setattr(state.annotation, name, read_once)
    with pytest.raises(RuntimeError, match="expected linear dimension Type2=2"):
        drawing._assert_physical_head_height(
            state.adapter, state.front, state.display, entities=(state.bearing, state.top),
        )
    assert len(calls) == 4
    assert len(set(calls)) == 4
    evidence = state.events[-1][1]
    assert evidence["type2"] == 12
    assert evidence["owner_same"] == 1
    assert evidence["attached_count"] == 2


def test_physical_head_height_malformed_attachment_array_is_not_silently_accepted(
    monkeypatch,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.annotation.GetAttachedEntities3 = lambda: 7
    with pytest.raises(RuntimeError, match="has no len") as refusal:
        drawing._assert_physical_head_height(
            state.adapter, state.front, state.display, entities=(state.bearing, state.top),
        )
    assert isinstance(refusal.value.__cause__, TypeError)
    evidence = state.events[-1][1]
    assert evidence["attached_count"] == 2
    assert evidence["type2"] == 2
    assert evidence["failure_error_type"] == "TypeError"


def test_supplier_references_route_only_head_height_through_physical_api(monkeypatch) -> None:
    state = _physical_head_fixture(monkeypatch)
    calls = []
    top = SimpleNamespace(name="FinishedTop")
    monkeypatch.setattr(
        drawing, "add_edge_dimension",
        lambda _adapter, view, **options: (
            calls.append(("other", view, options)) or SimpleNamespace()
        ),
    )
    monkeypatch.setattr(
        drawing, "_add_physical_head_height",
        lambda adapter, front, text_xy: (
            calls.append(("physical", adapter, front, text_xy)) or state.display
        ),
    )
    monkeypatch.setattr(
        drawing, "_format_supplier_reference",
        lambda _adapter, display, name: (name, display),
    )
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_args, **_kwargs: ())
    authored = drawing._add_supplier_references(state.adapter, state.front, top)
    assert list(authored) == [
        "SupplierHeadDiameter", "SupplierHeadHeight", "SupplierSocketAF",
    ]
    assert [call[0] for call in calls] == ["other", "physical", "other"]
    assert calls[0][2]["label"] == "SupplierHeadDiameter"
    assert calls[0][2]["entity_type"] == "SILHOUETTE"
    assert calls[1][1:] == (state.adapter, state.front, (0.224, 0.201))
    assert calls[2][1] is top
    assert calls[2][2]["label"] == "SupplierSocketAF"
    assert calls[2][2]["entity_type"] == "EDGE"


def _attach_stock_fixture(state):
    """Two independent native dimensions on real distinct finished/stock views."""
    source = SimpleNamespace(path=str(drawing.SOURCE.resolve()))
    view = SimpleNamespace(
        name="StockFront", mode=2, ReferencedConfiguration=screw.SUPPLIER_STOCK_CONFIGURATION,
        ScaleDecimal=4.0, dimensions=[],
        ReferencedDocument=SimpleNamespace(GetPathName=lambda: source.path),
    )
    view.GetDisplayMode2 = lambda: view.mode
    view.GetDisplayDimensions = lambda: tuple(view.dimensions)
    view.GetNextView = lambda: None
    shoulder = _HeadRim(state.selection, (
        0.0, screw.SHOULDER_END_Y, 0.0, 0.0, 1.0, 0.0, screw.SHOULDER_DIA / 2,
    ))
    tip_radius = screw.THREAD_MAJOR / 2 - drawing.TIP_CHAMFER
    tip_y = screw.SHOULDER_END_Y - screw.THREAD_LEN
    # The surviving trimmed arc need not contain its circle's +Z extremum.
    tip_point = (tip_radius / math.sqrt(2) / 1000, tip_y / 1000,
                 tip_radius / math.sqrt(2) / 1000)
    tip = _HeadRim(state.selection, (
        0.0, tip_y, 0.0, 0.0, -1.0, 0.0, tip_radius,
    ), nearest=(*tip_point, 0.25, float("nan")))  # SDK's fifth NotUsed is ignored.
    points = ((0.0, screw.SHOULDER_END_Y / 1000, screw.SHOULDER_DIA / 2 / 1000), tip_point)
    annotation = SimpleNamespace(
        attached=[shoulder, tip], kinds=(1, 1), dangling=False,
        count=2, Owner=view, OwnerType=0, Visible=1,
    )
    annotation.GetAttachedEntities3 = lambda: tuple(annotation.attached)
    annotation.GetAttachedEntityTypes = lambda: annotation.kinds
    annotation.GetAttachedEntityCount3 = lambda: annotation.count
    annotation.IsDangling = lambda: annotation.dangling
    arrows = [
        (0.130, 0.190 + 4 * point[1], 0.0, 0.0, direction, 0.0,
         0.001, 0.001, 0.0, 0.0, 0.0, 1.0)
        for point, direction in zip(points, (-1.0, 1.0), strict=True)
    ]
    annotation.GetDisplayData = lambda: SimpleNamespace(
        GetArrowHeadCount=lambda: len(arrows),
        GetArrowHeadAtIndex2=lambda index: arrows[index],
    )
    tolerance = SimpleNamespace(Type=0)
    native = SimpleNamespace(
        SystemValue=screw.THREAD_LEN / 1000, FullName="D1@StockFront", Tolerance=tolerance,
    )
    presentation = screw.SUPPLIER_REFERENCE_DIMENSIONS["SupplierStockThreadLength"]
    texts = {1: "(", 2: " in)", 4: presentation["callout"]}
    display = SimpleNamespace(
        Type2=2, ShowDimensionValue=True, ShowParenthesis=False,
        GetDimension2=lambda _index: native, GetAnnotation=lambda: annotation,
        GetUseDocUnits=lambda: False, GetUnits=lambda: 3,
        GetPrimaryPrecision2=lambda: presentation["precision"],
        GetFractionBase=lambda: 1, GetOverride=lambda: False,
        GetText=lambda index: texts[index],
    )
    annotation.GetSpecificAnnotation = lambda: display
    view.dimensions.append(display)

    def select_entity(edge, append):
        state.selection.calls.append(("view_select", view, edge, append))
        return state.selection.select(edge, append, SimpleNamespace(View=view))

    def refuse_model_selection(*_args):
        raise AssertionError("Stock must select model edges via IView.SelectEntity, never Select4")

    view.SelectEntity = select_entity
    shoulder.Select4 = tip.Select4 = refuse_model_selection
    state.stock = SimpleNamespace(
        view=view, shoulder=shoulder, tip=tip, points=points, annotation=annotation,
        native=native, display=display, tolerance=tolerance, texts=texts, arrows=arrows,
        source=source,
        edges=[state.item(shoulder), state.item(tip)],
    )
    return state.stock


def _physical_stock_fixture(monkeypatch):
    state = _physical_head_fixture(monkeypatch)
    monkeypatch.setattr(drawing, "SOURCE", SCRIPTS / "_offline_pivot_stock_source.SLDPRT")
    stock = _attach_stock_fixture(state)
    state.create_result = stock.display
    return state


def _saved_physical_fixture(monkeypatch, tmp_path):
    import _supplier_dimensions as supplier

    state = _physical_head_fixture(monkeypatch)
    monkeypatch.setattr(drawing, "SOURCE", tmp_path / "pivot.SLDPRT")
    _attach_stock_fixture(state)
    monkeypatch.setattr(supplier, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(supplier, "sheet_units", lambda _adapter: "mm")  # an mm sheet
    path = tmp_path / "pivot.SLDDRW"
    path.touch()
    state.path = path.resolve()
    monkeypatch.setattr(drawing, "OUTPUTS", SimpleNamespace(slddrw=path))
    _saved_shelf_boundary(monkeypatch, state)
    state.previous = state.adapter.currentModel
    state.front.ReferencedDocument = SimpleNamespace(GetPathName=lambda: str(drawing.SOURCE.resolve()))
    state.annotation.GetName = lambda: "Head annotation native name"
    state.display.GetNameForSelection = lambda: "Head display native selection name"
    state.stock.annotation.GetName = lambda: "Stock annotation native name"
    state.stock.display.GetNameForSelection = lambda: "Stock display native selection name"
    finished_sheet = SimpleNamespace(
        name=drawing.SHEET_NAMES[0], ReferencedConfiguration="", ReferencedDocument=None,
        GetDisplayDimensions=lambda: (), GetNextView=lambda: state.front,
    )
    stock_sheet = SimpleNamespace(
        name=drawing.SHEET_NAMES[1], ReferencedConfiguration="", ReferencedDocument=None,
        GetDisplayDimensions=lambda: (), GetNextView=lambda: state.stock.view,
    )
    state.sheets = dict(zip(drawing.SHEET_NAMES, (finished_sheet, stock_sheet), strict=True))
    state.active_sheet = drawing.SHEET_NAMES[0]
    state.activations = []
    state.saved = SimpleNamespace(
        GetPathName=lambda: str(state.path), GetType=lambda: 3,
        GetTitle=lambda: state.path.name,
        GetFirstView=lambda: state.sheets[state.active_sheet],
        GetSheetNames=lambda: tuple(state.sheets),
        GetCurrentSheet=lambda: state.paper_sheet,
    )

    def activate_sheet(name):
        state.activations.append(name)
        state.active_sheet = name
        return name in state.sheets

    state.saved.ActivateSheet = activate_sheet
    state.opened_model = state.saved
    state.open_result = None
    state.open_errors = 0
    state.open_warnings = 0
    state.loaded = None
    state.close_sticks = False
    state.opens = []
    state.closes = []
    app = state.adapter.swApp
    app.ActiveDoc = None
    app.GetOpenDocumentByName = lambda _path: state.loaded

    def open_doc(*arguments):
        state.opens.append(arguments)
        state.loaded = state.saved
        app.ActiveDoc = state.saved
        if state.open_result is not None:
            return state.open_result
        return state.opened_model, state.open_errors, state.open_warnings

    def close_doc(title):
        state.closes.append(title)
        if not state.close_sticks:
            state.loaded = None
            app.ActiveDoc = None

    app.OpenDoc6 = open_doc
    app.CloseDoc = close_doc
    state.identities = {
        "SupplierHeadHeight": (
            state.native.FullName, state.front.name,
            (object(), object()), (1, 1),  # Stale live handles MUST NOT be reused.
        ),
        "SupplierStockThreadLength": (
            state.stock.native.FullName, state.stock.view.name,
            (object(), object()), (1, 1),  # Also stale across document close/reopen.
        ),
        "SupplierSocketAF": (
            state.socket_native.FullName, state.paper_top.name,
            tuple(state.socket_annotation.attached), (1, 1),
        ),
    }
    # A native save may change these IDs; only the observed post-save names
    # belong to the saved lookup. The pre-save records stay untouched.
    state.native.FullName = "D2@FinishedFront@pivot.SLDDRW"
    state.stock.native.FullName = "D1@StockFront@pivot.SLDDRW"
    state.serialized_full_names = {
        "SupplierHeadHeight": state.native.FullName,
        "SupplierStockThreadLength": state.stock.native.FullName,
    }
    state.serialized_shelf_names = {
        "SupplierHeadHeight": state.native.FullName,
        "SupplierSocketAF": state.socket_native.FullName,
    }
    state.configurations = {
        state.front.name: (drawing.SHEET_NAMES[0], state.front.ReferencedConfiguration),
        state.stock.view.name: (
            drawing.SHEET_NAMES[1], state.stock.view.ReferencedConfiguration,
        ),
        state.paper_top.name: (drawing.SHEET_NAMES[0], "Default"),
        state.paper_iso.name: (drawing.SHEET_NAMES[0], "Default"),
    }
    _finished_paper_fixture(monkeypatch, tmp_path, _state=state)
    state.adapter.currentModel = state.previous
    state.scans.clear()
    state.projections.clear()
    state.events.clear()
    return state


def test_saved_physical_references_reopen_read_only_rescan_both_and_close(
    monkeypatch, tmp_path,
) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.open_warnings = 2  # Warning telemetry is not a false load error.
    drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=state.serialized_full_names,
    serialized_shelf_names=state.serialized_shelf_names,)
    assert state.opens == [(str(state.path), 3, 3, "", 0, 0)]
    assert state.closes == [state.path.name]
    assert state.loaded is None
    assert state.adapter.currentModel is state.previous
    assert all(scan[0] is state.saved for scan in state.scans)
    assert {scan[1].name for scan in state.scans} >= {state.front.name, state.stock.view.name}
    proof = next(fields for name, fields in state.events if name == "drawing.pivot_head_height_proof")
    assert proof["full_name"] == state.native.FullName
    assert proof["original_full_name"] == state.identities["SupplierHeadHeight"][0]
    assert proof["original_full_name"] != proof["full_name"]
    assert proof["measured_head_height_mm"] == pytest.approx(screw.HEAD_H)
    assert proof["attached_circle_params_m"] == (
        state.bearing.GetCurve().CircleParams, state.top.GetCurve().CircleParams,
    )
    stock_proof = next(
        fields for name, fields in state.events if name == "drawing.pivot_stock_length_proof"
    )
    assert stock_proof["full_name"] == state.stock.native.FullName
    assert stock_proof["original_full_name"] == state.identities["SupplierStockThreadLength"][0]
    assert stock_proof["original_full_name"] != stock_proof["full_name"]
    assert stock_proof["measured_stock_thread_length_mm"] == pytest.approx(screw.THREAD_LEN)
    assert stock_proof["configuration"] == screw.SUPPLIER_STOCK_CONFIGURATION
    native_proofs = [
        fields for name, fields in state.events
        if name == "drawing.physical_axial_dimension_native_proof"
    ]
    assert {(proof["label"], proof["phase"]) for proof in native_proofs} == {
        ("SupplierHeadHeight", "saved"), ("SupplierStockThreadLength", "saved"),
    }
    assert not state.additions and not state.selection.calls


@pytest.mark.parametrize("fault", (
    "missing_both", "missing_head", "missing_stock", "extra", "empty", "null",
    "non_string", "duplicate",
))
def test_saved_physical_reader_requires_complete_distinct_serialized_names_before_open(
    monkeypatch, tmp_path, fault,
) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    names = dict(state.serialized_full_names)
    if fault == "missing_both":
        names.clear()
    elif fault.startswith("missing_"):
        names.pop("SupplierHeadHeight" if fault == "missing_head" else "SupplierStockThreadLength")
    elif fault == "extra":
        names["SupplierHeadDiameter"] = "Other@Native"
    else:
        names["SupplierHeadHeight"] = {
            "empty": "", "null": None, "non_string": 17,
            "duplicate": state.serialized_full_names["SupplierStockThreadLength"],
        }[fault]
    with pytest.raises(RuntimeError, match="serialized FullNames"):
        drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=names,
        serialized_shelf_names=state.serialized_shelf_names,)
    assert not state.opens and not state.closes and not state.scans
    assert state.adapter.currentModel is state.previous


def test_saved_physical_reader_has_no_implicit_presave_name_fallback(monkeypatch, tmp_path) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    with pytest.raises(TypeError, match="serialized_full_names"):
        drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, )
    assert not state.opens and not state.closes


@pytest.mark.parametrize("fault", ("original", "suffix", "whitespace", "selection", "annotation"))
def test_saved_lookup_refuses_every_nonexact_serialized_identity_with_full_inventory(
    monkeypatch, tmp_path, fault,
) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    original_identities = dict(state.identities)
    actual_names = dict(state.serialized_full_names)
    names = dict(actual_names)
    if fault == "original":
        names = {name: state.identities[name][0] for name in state.serialized_full_names}
    elif fault == "suffix":
        names["SupplierHeadHeight"] = actual_names["SupplierHeadHeight"].split("@", 1)[1]
    elif fault == "whitespace":
        names["SupplierHeadHeight"] = f" {actual_names['SupplierHeadHeight']} "
    elif fault == "selection":
        names["SupplierHeadHeight"] = state.display.GetNameForSelection()
    else:
        names["SupplierHeadHeight"] = state.annotation.GetName()
    state.sheets[drawing.SHEET_NAMES[0]].GetDisplayDimensions = lambda: None
    with pytest.raises(RuntimeError, match="saved FullName census is 0") as refusal:
        drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=names,
        serialized_shelf_names=state.serialized_shelf_names,)
    ((event, evidence),) = state.events
    assert event == "drawing.physical_axial_identity_inventory"
    assert evidence["expected_original_full_names"] == {
        name: original_identities[name][0] for name in state.serialized_full_names
    }
    assert evidence["expected_serialized_full_names"] == names
    assert evidence["label_match_counts"] == {
        "SupplierHeadHeight": 0, "SupplierStockThreadLength": 0 if fault == "original" else 1,
    }
    assert evidence["document_path"] == str(state.path)
    assert evidence["document_title"] == state.path.name and evidence["document_type"] == 3
    observed = {
        item["full_name"] for row in evidence["inventory"] for item in row["dimensions"]
    }
    assert set(actual_names.values()) <= observed
    for name in state.serialized_full_names:
        assert actual_names[name] in str(refusal.value)
        assert original_identities[name][0] in str(refusal.value)
    assert "label_match_counts" in str(refusal.value)
    assert state.identities == original_identities
    assert not state.scans and not state.additions and not state.selection.calls
    assert state.closes == [state.path.name] and state.adapter.currentModel is state.previous


def test_saved_lookup_preserves_actual_fullnames_without_stripping(monkeypatch, tmp_path) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.native.FullName = f" {state.native.FullName} "
    state.serialized_full_names["SupplierHeadHeight"] = state.native.FullName
    state.serialized_shelf_names["SupplierHeadHeight"] = state.native.FullName
    drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=state.serialized_full_names,
    serialized_shelf_names=state.serialized_shelf_names,)
    evidence = next(
        fields for name, fields in state.events if name == "drawing.physical_axial_identity_inventory"
    )
    assert evidence["inventory"][1]["dimensions"][0]["full_name"] == state.native.FullName
    assert evidence["expected_serialized_full_names"]["SupplierHeadHeight"] == state.native.FullName


@pytest.mark.parametrize("getter", ("annotation_name", "selection_name", "native_full_name"))
def test_saved_inventory_keeps_original_getter_cause_and_visits_the_other_label(
    monkeypatch, tmp_path, getter,
) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    error = OSError(f"native {getter} getter failed")

    def fail():
        raise error

    if getter == "annotation_name":
        state.annotation.GetName = fail
    elif getter == "selection_name":
        state.display.GetNameForSelection = fail
    else:
        class StaleDimension:
            @property
            def FullName(self):
                raise error

        state.display.GetDimension2 = lambda _index: StaleDimension()
    with pytest.raises(RuntimeError, match="saved inventory getter/metadata refusal") as refusal:
        drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=state.serialized_full_names,
        serialized_shelf_names=state.serialized_shelf_names,)
    assert refusal.value.__cause__ is error
    ((event, evidence),) = state.events
    assert event == "drawing.physical_axial_identity_inventory"
    assert evidence["label_match_counts"] == {
        "SupplierHeadHeight": 0 if getter == "native_full_name" else 1,
        "SupplierStockThreadLength": 1,
    }
    head = evidence["inventory"][1]["dimensions"][0]
    assert getter.replace("native_", "") not in head
    assert any(str(error) in message for message in head["errors"])
    assert any(
        item.get("full_name") == state.stock.native.FullName
        for row in evidence["inventory"] for item in row["dimensions"]
    )
    assert state.stock.native.FullName in str(refusal.value)
    assert not state.scans and not state.additions and not state.selection.calls
    assert state.closes == [state.path.name] and state.adapter.currentModel is state.previous


@pytest.mark.parametrize("fault, message", (
    ("open_error", "open failed"),
    ("null_model", "open failed"),
    ("bad_result", "model/errors/warnings"),
    ("wrong_path", "path/type mismatch"),
    ("wrong_type", "path/type mismatch"),
    ("wrong_current", "current drawing"),
    ("wrong_registered", "current drawing"),
    ("missing_dimension", "FullName census is 0"),
    ("duplicate_dimension", "FullName census is 2"),
    ("sheet_duplicate", "FullName census is 2"),
    ("wrong_full_name", "FullName census is 0"),
    ("wrong_owner", "owner/configuration"),
    ("wrong_annotation_owner", "owner/configuration"),
    ("wrong_configuration", "owner/configuration"),
    ("wrong_sheet", "owner/configuration"),
    ("missing_sheet", "sheet census"),
    ("extra_sheet", "sheet census"),
    ("duplicate_sheet_names", "sheet census"),
    ("reordered_sheet_names", "sheet census"),
    ("empty_sheet_names", "sheet census"),
    ("sheet_activation", "activate saved sheet"),
    ("missing_native", "saved display has no native dimension"),
    ("orphan_display", "saved display has no native dimension"),
    ("dimension_type", "expected linear dimension Type2=2"),
    ("owner_type", "exact front-view owner"),
    ("same_named_wrong_owner", "exact front-view owner"),
    ("wrong_value", "measures"),
    ("wrong_attachment", "named entities"),
    ("wrong_type_attachment", "two nonnull actual edge attachments"),
    ("changed_geometry", "top physical rim"),
    ("lost_hlr", "hidden-lines-removed"),
    ("format", "presentation"),
    ("source_band", "tolerance type"),
    ("close", "did not close"),
))
def test_saved_head_height_refuses_corruption_and_always_restores_current_model(
    monkeypatch, tmp_path, fault, message,
) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    if fault == "open_error":
        state.open_errors = 1
    elif fault == "null_model":
        state.opened_model = None
    elif fault == "bad_result":
        state.open_result = state.saved
    elif fault in ("wrong_path", "wrong_type"):
        state.opened_model = SimpleNamespace(
            GetPathName=lambda: str(state.path if fault == "wrong_type" else tmp_path / "other.SLDDRW"),
            GetType=lambda: 1 if fault == "wrong_type" else 3,
        )
    elif fault in ("wrong_current", "wrong_registered"):
        original = state.adapter.swApp.OpenDoc6

        def open_wrong(*args):
            result = original(*args)
            if fault == "wrong_current":
                state.adapter.swApp.ActiveDoc = object()
            else:
                state.adapter.swApp.IsSame = lambda _first, _second: 0
            return result

        state.adapter.swApp.OpenDoc6 = open_wrong
    elif fault == "missing_dimension":
        state.front.dimensions.clear()
    elif fault == "duplicate_dimension":
        state.front.dimensions.append(state.display)
    elif fault == "sheet_duplicate":
        state.sheets[drawing.SHEET_NAMES[1]].GetDisplayDimensions = lambda: (state.display,)
    elif fault == "wrong_full_name":
        state.native.FullName = "D99@AnotherView"
    elif fault == "wrong_owner":
        state.front.name = "AnotherView"
    elif fault == "wrong_annotation_owner":
        state.annotation.Owner = SimpleNamespace(name="AnotherView")
    elif fault == "wrong_configuration":
        state.front.ReferencedConfiguration = screw.SUPPLIER_STOCK_CONFIGURATION
    elif fault == "wrong_sheet":
        state.sheets[drawing.SHEET_NAMES[0]].GetNextView = lambda: state.stock.view
        state.sheets[drawing.SHEET_NAMES[1]].GetNextView = lambda: state.front
    elif fault == "missing_sheet":
        del state.sheets[drawing.SHEET_NAMES[1]]
    elif fault == "extra_sheet":
        state.sheets["EXTRA"] = SimpleNamespace()
    elif fault == "duplicate_sheet_names":
        state.saved.GetSheetNames = lambda: (*drawing.SHEET_NAMES, drawing.SHEET_NAMES[0])
    elif fault == "reordered_sheet_names":
        state.saved.GetSheetNames = lambda: tuple(reversed(drawing.SHEET_NAMES))
    elif fault == "empty_sheet_names":
        state.saved.GetSheetNames = lambda: None
    elif fault == "sheet_activation":
        state.saved.ActivateSheet = lambda name: name != drawing.SHEET_NAMES[1]
    elif fault == "missing_native":
        state.display.GetDimension2 = lambda _index: None
    elif fault == "orphan_display":
        state.front.dimensions.append(SimpleNamespace(GetDimension2=lambda _index: None))
    elif fault == "dimension_type":
        state.display.Type2 = 11
    elif fault == "owner_type":
        state.annotation.OwnerType = 1
    elif fault == "same_named_wrong_owner":
        state.annotation.Owner = SimpleNamespace(name=state.front.name)
    elif fault == "wrong_value":
        state.native.SystemValue -= screw.HEAD_CHAMFER / 1000
    elif fault == "wrong_attachment":
        state.annotation.attached[1] = object()
    elif fault == "wrong_type_attachment":
        state.annotation.kinds = (46, 1)
    elif fault == "changed_geometry":
        state.edges.pop()
    elif fault == "lost_hlr":
        state.front.mode = 1
    elif fault == "format":
        state.texts[2] = ")"
    elif fault == "source_band":
        state.tolerance.Type = 2
    elif fault == "close":
        state.close_sticks = True
    with pytest.raises(RuntimeError, match=message):
        drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=state.serialized_full_names,
        serialized_shelf_names=state.serialized_shelf_names,)
    assert state.closes == [state.path.name]
    assert state.adapter.currentModel is state.previous
    assert (state.loaded is not None) == (fault == "close")
    assert not state.additions


def test_saved_head_height_refuses_an_already_open_drawing_without_closing_it(
    monkeypatch, tmp_path,
) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.loaded = state.saved
    with pytest.raises(RuntimeError, match="finalize and close"):
        drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=state.serialized_full_names,
        serialized_shelf_names=state.serialized_shelf_names,)
    assert not state.opens and not state.closes
    assert state.loaded is state.saved
    assert state.adapter.currentModel is state.previous


def test_saved_head_height_requires_the_output_file(monkeypatch, tmp_path) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(
        drawing, "OUTPUTS", SimpleNamespace(slddrw=tmp_path / "missing.SLDDRW")
    )
    with pytest.raises(RuntimeError, match="saved drawing is missing"):
        drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=state.serialized_full_names,
        serialized_shelf_names=state.serialized_shelf_names,)
    assert not state.opens and not state.closes


@pytest.mark.parametrize("fault, message", (
    ("none", ""),
    ("geometry", "top physical rim"),
    ("attachment", "named entities"),
    ("value", "native value"),
    ("duplicate", "census"),
))
def test_settled_supplier_census_invokes_fresh_physical_head_proof(
    monkeypatch, tmp_path, fault, message,
) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.adapter.currentModel = state.saved
    # This physical-census consumer owns three references, not the cold-paper extras.
    state.front.dimensions[:] = [state.display]
    state.identities["SupplierHeadHeight"] = (
        state.native.FullName, state.front.name, (state.bearing, state.top), (1, 1),
    )
    state.identities["SupplierStockThreadLength"] = (
        state.stock.native.FullName, state.stock.view.name,
        (state.stock.shoulder, state.stock.tip), (1, 1),
    )
    monkeypatch.setattr(
        drawing, "SUPPLIER_REFERENCE_DIMENSIONS",
        {name: screw.SUPPLIER_REFERENCE_DIMENSIONS[name] for name in state.identities},
    )
    caption = SimpleNamespace(
        GetText=lambda: screw.SUPPLIER_STOCK_TITLE,
        PropertyLinkedText=drawing.property_link("Supplier Reference Title"),
    )
    note_annotation = SimpleNamespace(
        GetType=lambda: 6, OwnerType=1, GetSpecificAnnotation=lambda: caption,
    )
    state.sheets[drawing.SHEET_NAMES[1]].GetAnnotations = lambda: (note_annotation,)
    if fault == "geometry":
        state.edges.pop()
    elif fault == "attachment":
        state.annotation.attached[1] = object()
    elif fault == "value":
        state.native.SystemValue -= screw.HEAD_CHAMFER / 1000
    elif fault == "duplicate":
        state.front.dimensions.append(state.display)
    if fault == "none":
        fresh = drawing._assert_supplier_references(
            state.adapter, state.identities, state.configurations,
        )
        assert fresh["SupplierHeadHeight"] is state.display
        assert fresh["SupplierStockThreadLength"] is state.stock.display
        assert state.active_sheet == drawing.SHEET_NAMES[0]
    else:
        with pytest.raises(RuntimeError, match=message):
            drawing._assert_supplier_references(
                state.adapter, state.identities, state.configurations,
            )


def _record_drawing_build(
    monkeypatch, tmp_path, *, checkpoint_calls=1, capture_fault=None,
):
    """Exercise the real build producer over the existing no-COM doubles."""
    source = tmp_path / "pivot.SLDPRT"
    source.touch()
    events = []
    projections, callouts = [], []
    head_edge = (0.140 - 4 * drawing._HEAD_TOP_R / 1000, 0.186285 + 4 * screw.HEAD_H / 1000)
    head_entity = SimpleNamespace(GetClosestPointOn=lambda *point: (*point, 0.0))
    model = SimpleNamespace(path="", ActivateSheet=lambda _name: True)
    model.GetPathName = lambda: model.path
    adapter = SimpleNamespace(currentModel=model)

    async def open_model(_path):
        return True

    adapter.open_model = open_model
    properties = {
        "Purchased Screw Note": _config.parts(part.PART_NAME)["purchased_note"],
        "Supplier Reference Title": screw.SUPPLIER_STOCK_TITLE,
    }
    front, iso, top = (
        SimpleNamespace(name=name, ReferencedConfiguration="Default")
        for name in ("FinishedFront", "FinishedIso", "FinishedTop")
    )
    stock, stock_iso = (
        SimpleNamespace(name=name, ReferencedConfiguration=screw.SUPPLIER_STOCK_CONFIGURATION)
        for name in ("StockFront", "StockIso")
    )
    controls = []
    for name in ("CutLength", *drawing.EXPECTED_CONTROLS):
        display = SimpleNamespace(
            GetText=lambda _index, name=name: screw.DIMENSION_CALLOUTS.get(name, "")
        )
        controls.append(SimpleNamespace(
            name=name, GetSpecificAnnotation=lambda display=display: display,
        ))
    references = {
        name: object() for name in screw.SUPPLIER_REFERENCE_DIMENSIONS
        if name != "SupplierStockThreadLength"
    }
    physical_labels = ("SupplierHeadHeight", "SupplierStockThreadLength")
    native_dimensions = {
        "SupplierHeadHeight": SimpleNamespace(FullName="D2@FinishedFront@UnsavedDrawing"),
        "SupplierStockThreadLength": SimpleNamespace(FullName="D1@StockFront@UnsavedDrawing"),
        "SupplierSocketAF": SimpleNamespace(FullName="D1@FinishedTop@UnsavedDrawing"),
        "SupplierHeadDiameter": SimpleNamespace(FullName="RD1@FinishedFront@UnsavedDrawing"),
        "SupplierThreadMajor": SimpleNamespace(FullName="SupplierThreadMajor@SupplierReference@pivot.SLDPRT"),
    }
    for name in native_dimensions:
        native = native_dimensions[name]
        display = SimpleNamespace(GetDimension2=lambda _index, native=native: native)
        references[name] = SimpleNamespace(
            GetSpecificAnnotation=lambda display=display: display,
        )
    stock_annotation = references.pop("SupplierStockThreadLength")
    tail_control = next(item for item in controls if item.name == "ThreadLengthMin")
    native_dimensions["ThreadLengthMin"] = SimpleNamespace(
        FullName="ThreadLengthMin@ThreadTailAcceptance@pivot.SLDPRT",
    )
    identities = {
        name: (native_dimensions[name].FullName, owner, (object(), object()), (1, 1))
        for name, owner in zip(physical_labels, (front.name, stock.name), strict=True)
    }
    identities["SupplierSocketAF"] = (
        native_dimensions["SupplierSocketAF"].FullName, top.name, (object(), object()), (1, 1),
    )
    original_identities = dict(identities)
    serialized_names = {
        name: native.FullName.replace("@UnsavedDrawing", "@pivot.SLDDRW")
        for name, native in native_dimensions.items()
    }
    captures = []
    output = SimpleNamespace(slddrw=tmp_path / "pivot.SLDDRW")
    monkeypatch.setattr(drawing, "OUTPUTS", output)
    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "check", lambda _label, value: value)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *_args, **_kwargs: properties)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_args, **_kwargs: (model, object()))
    monkeypatch.setattr(drawing, "create_blank_drawing_sheets", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        drawing, "place_view",
        lambda _adapter, _source, orientation, *_args, **_kwargs: {
            "*Front": front, "*Isometric": iso, "*Top": top,
        }[orientation],
    )
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_args, **_kwargs: controls)
    monkeypatch.setattr(drawing, "verify_machining_controls", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "_verify_reference_length", lambda *_args: None)
    monkeypatch.setattr(drawing, "set_dimension_callouts", lambda *_args: None)
    monkeypatch.setattr(drawing, "offset_dimension_text", lambda *_args: None)
    monkeypatch.setattr(drawing, "_add_supplier_references", lambda *_args: references)
    monkeypatch.setattr(drawing, "_blacken_shoulder_witnesses", lambda *_args: None)
    monkeypatch.setattr(drawing, "_align_top_origin", lambda *_args: lambda: None)
    monkeypatch.setattr(drawing, "_trim_top_mark", lambda *_args: lambda: None)
    monkeypatch.setattr(drawing, "_move_tail_column", lambda *_args: (lambda: None, {}))
    monkeypatch.setattr(drawing, "_assert_paper_layout", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "_place_purchased_note", lambda *_args: (lambda: None, {}))
    monkeypatch.setattr(drawing, "_clear_socket_text", lambda *_args: None)
    monkeypatch.setattr(drawing, "_head_height_entities", lambda *_args: (object(), head_entity))

    def project_head(_adapter, view, point, *, label):
        projections.append((view, point, label))
        return head_edge

    def linked_callout(_adapter, view, **options):
        callouts.append((view, options))
        return SimpleNamespace(
            GetText=lambda: properties["Purchased Screw Note"],
            GetAnnotation=lambda: object(),
            PropertyLinkedText=drawing.property_link("Purchased Screw Note"),
        )

    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda _adapter, _view, points, *, label: tuple(
            (0.140 + 4 * x, 0.186285 + 4 * y) for x, y, _z in points
        ),
    )
    monkeypatch.setattr(drawing, "model_point_in_view", project_head)
    monkeypatch.setattr(drawing, "add_attached_note", linked_callout)
    monkeypatch.setattr(
        drawing, "_add_stock_reference", lambda *_args: (stock, stock_iso, stock_annotation)
    )

    def capture(_adapter, supplied):
        if "ThreadLengthMin" in supplied:
            return {name: (native_dimensions[name].FullName, front.name, (), ()) for name in supplied}
        assert supplied == {**references, "SupplierStockThreadLength": stock_annotation}
        events.append("identities")
        return identities

    monkeypatch.setattr(drawing, "_supplier_reference_identities", capture)

    def capture_serialized(
        actual_adapter, actual_references, actual_identities, configurations, *,
        labels, drawing_path, sheet_names,
    ):
        assert actual_adapter is adapter and adapter.currentModel is model
        assert model.GetPathName() == str(output.slddrw.resolve())
        assert set(actual_references) == set(labels)
        all_references = {
            **references, "SupplierStockThreadLength": stock_annotation, "ThreadLengthMin": tail_control,
        }
        assert all(actual_references[name] is all_references[name] for name in labels)
        assert identities == original_identities
        assert labels in (
            physical_labels, ("SupplierHeadHeight", "SupplierSocketAF"),
            ("SupplierHeadDiameter", "SupplierThreadMajor"), ("SupplierHeadHeight", "ThreadLengthMin"),
        )
        assert sheet_names == drawing.SHEET_NAMES
        assert drawing_path is output.slddrw and len(configurations) == 5
        actual_names = {name: native_dimensions[name].FullName for name in labels}
        assert actual_names == {name: serialized_names[name] for name in labels}
        captures.append(actual_names)
        if capture_fault == "missing":
            actual_names.pop("SupplierStockThreadLength")
        elif capture_fault == "empty":
            actual_names["SupplierHeadHeight"] = ""
        elif capture_fault == "duplicate":
            actual_names["SupplierStockThreadLength"] = actual_names["SupplierHeadHeight"]
        elif capture_fault == "extra":
            actual_names["UnrelatedLabel"] = "Other@Native"
        elif capture_fault == "shelf_head_drift" and labels == ("SupplierHeadHeight", "SupplierSocketAF"):
            actual_names["SupplierHeadHeight"] += " changed-between-captures"
        return actual_names

    monkeypatch.setattr(drawing, "capture_serialized_physical_axial_names", capture_serialized)
    monkeypatch.setattr(drawing, "capture_serialized_note_name", lambda *_args, **_kwargs: "Saved purchased note")

    def settled(_adapter, actual_identities, configurations):
        assert actual_identities is identities
        assert identities == original_identities and model.GetPathName() == ""
        assert all(native_dimensions[name].FullName == identities[name][0] for name in physical_labels)
        assert configurations[front.name] == (drawing.SHEET_NAMES[0], "Default")
        assert configurations[stock.name] == (
            drawing.SHEET_NAMES[1], screw.SUPPLIER_STOCK_CONFIGURATION,
        )
        events.append("settled")
        return {name: object() for name in screw.SUPPLIER_REFERENCE_DIMENSIONS}

    monkeypatch.setattr(drawing, "_assert_supplier_references", settled)

    def shelf(_adapter, *, reacquire, axes, force, label):
        assert axes == {"SupplierHeadHeight": 1, "SupplierSocketAF": 0}
        assert set(force) == set(axes)
        assert set(reacquire()) == set(axes)
        return lambda: reacquire()

    monkeypatch.setattr(drawing, "shelve_reference_text", shelf)
    expected = {"slddrw": "saved-pivot"}

    async def finalize(_adapter, outputs, **options):
        assert outputs is drawing.OUTPUTS
        events.append("finalize")
        for check in options["settled_checks"]:
            check()
        # Simulate the existing successful native SaveAs, PDF export and audit,
        # then invoke the real local checkpoint while the original refs are live.
        model.path = str(outputs.slddrw.resolve())
        for name, native in native_dimensions.items():
            native.FullName = serialized_names[name]
        for _ in range(checkpoint_calls):
            options["checkpoint"]("before_drawing_close")
        adapter.currentModel = None
        events.append("closed")
        return expected

    def saved(_adapter, actual_identities, configurations, *, serialized_full_names, serialized_shelf_names, paper):
        assert adapter.currentModel is None
        assert actual_identities is identities
        assert len(configurations) == 5
        assert actual_identities == original_identities
        assert serialized_full_names == {name: serialized_names[name] for name in physical_labels}
        assert serialized_shelf_names == {name: serialized_names[name] for name in drawing._REFERENCE_SHELF_AXES}
        assert serialized_shelf_names["SupplierHeadHeight"] == serialized_full_names["SupplierHeadHeight"]
        assert paper["note"] == "Saved purchased note"
        assert paper["names"] == {
            name: serialized_names[name] for name in ("SupplierHeadDiameter", "SupplierThreadMajor", "ThreadLengthMin")
        }
        events.append("saved-reopen-proof")

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    monkeypatch.setattr(drawing, "_assert_saved_physical_references", saved)
    return SimpleNamespace(
        result=asyncio.run(drawing.build(adapter)), expected=expected, events=events,
        projections=projections, callouts=callouts, head_edge=head_edge, front=front,
        captures=captures, identities=identities, original_identities=original_identities,
        serialized_names=serialized_names,
    )


def test_build_proves_both_physical_references_after_finalizer_closes_saved_drawing(
    monkeypatch, tmp_path,
) -> None:
    recorded = _record_drawing_build(monkeypatch, tmp_path)
    assert recorded.result is recorded.expected
    assert recorded.events.index("closed") < recorded.events.index("saved-reopen-proof")
    assert recorded.identities == recorded.original_identities


@pytest.mark.parametrize("checkpoint_calls, capture_fault, message", (
    (0, None, "checkpoint was never called"),
    (2, None, "capture called more than once"),
    (1, "missing", "capture is incomplete"),
    (1, "empty", "capture is incomplete"),
    (1, "duplicate", "capture is incomplete"),
    (1, "extra", "capture is incomplete"),
))
def test_build_requires_one_complete_postsave_identity_capture_before_saved_proof(
    monkeypatch, tmp_path, checkpoint_calls, capture_fault, message,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _record_drawing_build(
            monkeypatch, tmp_path, checkpoint_calls=checkpoint_calls,
            capture_fault=capture_fault,
        )


def test_purchased_note_producer_selects_the_trimmed_head_top_entity_before_insertion(
    monkeypatch, tmp_path,
) -> None:
    recorded = _record_drawing_build(monkeypatch, tmp_path)
    ((view, point, _label),) = recorded.projections
    assert view is recorded.front
    radius = screw.HEAD_DIA / 2 - screw.HEAD_CHAMFER
    assert point == pytest.approx((
        -radius / 1000, screw.HEAD_H / 1000, 0.0,
    ))
    ((view, callout),) = recorded.callouts
    assert view is recorded.front
    assert callout["entity"] is callout["attached_to"]
    assert callout["text"] == drawing.property_link("Purchased Screw Note")
    assert callout["leader_attach_xy"] is recorded.head_edge
    assert callout["note_xy"] == drawing.PURCHASED_NOTE_XY


def test_physical_head_height_bounds_arc_evidence_without_hiding_the_nearest_match(
    monkeypatch,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.edges[1:1] = [
        state.item(_HeadRim(
            state.selection, state.top.circle,
            nearest=(0.0, screw.HEAD_H / 1000, -0.004, 0.0, 0.0),
        ))
        for _ in range(20)
    ]
    assert drawing._head_height_entities(state.adapter, state.front) == (
        state.bearing, state.top,
    )
    _name, top_evidence = state.events[-1]
    assert top_evidence["station"] == "top"
    assert top_evidence["candidate_count"] == 22
    assert len(top_evidence["candidates"]) == 12
    assert top_evidence["candidates"][0]["point_error_m"] == 0.0
    assert top_evidence["candidates"][0]["nearest_m"] == drawing._head_height_points()[1]


@pytest.mark.parametrize("dimension_type", (0, 6, 11, 12))
def test_physical_head_height_refuses_every_nonlinear_native_type(
    monkeypatch, dimension_type,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.display.Type2 = dimension_type
    with pytest.raises(RuntimeError, match="expected linear dimension Type2=2"):
        drawing._assert_physical_head_height(state.adapter, state.front, state.display)


@pytest.mark.parametrize("phase", ("creation", "settled", "saved"))
@pytest.mark.parametrize("fault", (
    "horizontal", "diagonal", "zero_direction", "same_sign", "wrong_span",
    "translated_tips", "different_x", "nonzero_z", "null_display_data",
    "missing_display_data", "null_arrow", "short_arrow", "long_arrow",
    "nonfinite_arrow", "wrong_arrow_count", "wrong_scale", "zero_scale",
    "nonfinite_scale", "wrong_projection", "null_projection",
    "wrong_attachment", "wrong_value", "legacy_type",
))
def test_physical_head_height_spatial_proof_is_fresh_at_every_boundary(
    monkeypatch, tmp_path, phase, fault,
) -> None:
    import _drawing_physical_axial_dimension as physical_height

    state = _saved_physical_fixture(monkeypatch, tmp_path)
    if phase != "creation":
        drawing._add_physical_head_height(state.adapter, state.front, (0.224, 0.201))
    if fault in ("horizontal", "diagonal", "zero_direction", "same_sign"):
        direction = {
            "horizontal": (1.0, 0.0, 0.0),
            "diagonal": (0.1, 1.0, 0.0),
            "zero_direction": (0.0, 0.0, 0.0),
            "same_sign": (0.0, -1.0, 0.0),
        }[fault]
        state.arrows[0] = (*state.arrows[0][:3], *direction, *state.arrows[0][6:])
    elif fault in ("wrong_span", "translated_tips", "different_x", "nonzero_z"):
        for index in range(2 if fault == "translated_tips" else 1):
            arrow = list(state.arrows[index])
            coordinate = {"different_x": 0, "nonzero_z": 2}.get(fault, 1)
            arrow[coordinate] += 0.001
            state.arrows[index] = tuple(arrow)
    elif fault == "null_display_data":
        state.annotation.GetDisplayData = lambda: None
    elif fault == "missing_display_data":
        del state.annotation.GetDisplayData
    elif fault == "null_arrow":
        state.arrows[0] = None
    elif fault == "short_arrow":
        state.arrows[0] = state.arrows[0][:-1]
    elif fault == "long_arrow":
        state.arrows[0] = (*state.arrows[0], 0.0)
    elif fault == "nonfinite_arrow":
        state.arrows[0] = (float("nan"), *state.arrows[0][1:])
    elif fault == "wrong_arrow_count":
        state.arrows.append(state.arrows[0])
    elif fault in ("wrong_scale", "zero_scale", "nonfinite_scale"):
        state.front.ScaleDecimal = {
            "wrong_scale": 2.0, "zero_scale": 0.0, "nonfinite_scale": float("nan"),
        }[fault]
    elif fault in ("wrong_projection", "null_projection"):
        monkeypatch.setattr(
            physical_height, "model_points_in_view",
            lambda *_args, **_kwargs: (
                None if fault == "null_projection" else ((0.1, 0.1), (0.1, 0.2))
            ),
        )
    elif fault == "wrong_attachment":
        state.annotation.attached[1] = object()
    elif fault == "wrong_value":
        state.native.SystemValue -= screw.HEAD_CHAMFER / 1000
    elif fault == "legacy_type":
        state.display.Type2 = 12

    with pytest.raises(RuntimeError):
        if phase == "creation":
            drawing._add_physical_head_height(state.adapter, state.front, (0.224, 0.201))
        elif phase == "settled":
            drawing._assert_physical_head_height(state.adapter, state.front, state.display)
        else:
            drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=state.serialized_full_names,
            serialized_shelf_names=state.serialized_shelf_names,)
    assert state.events[-1][0] == "drawing.physical_axial_dimension_native_refusal"
    assert not state.selection.selected
    if phase == "saved":
        assert state.closes == [state.path.name]
        assert state.adapter.currentModel is state.previous


def test_stock_length_resolves_exact_supplier_stations_and_actual_trimmed_points(monkeypatch) -> None:
    state = _physical_stock_fixture(monkeypatch)
    stock = state.stock
    # Same plane, wrong boundary: inner shoulder neck and factory major/chamfer junction.
    distractors = [
        (0.0, screw.SHOULDER_END_Y, 0.0, 0.0, 1.0, 0.0, screw.THREAD_MAJOR / 2),
        (0.0, screw.SHOULDER_END_Y - screw.THREAD_LEN + drawing.TIP_CHAMFER,
         0.0, 0.0, 1.0, 0.0, screw.THREAD_MAJOR / 2),
        (0.0, screw.TIP_Y, 0.0, 0.0, 1.0, 0.0,
         screw.THREAD_MAJOR / 2 - screw.CHAMFER_WIDTH),
    ]
    stock.edges[:0] = [state.item(_HeadRim(state.selection, circle)) for circle in distractors]
    entities, points = drawing._stock_length_entities(state.adapter, stock.view)
    assert entities == (stock.shoulder, stock.tip)
    assert points == stock.points
    assert stock.shoulder.circle[1:] == pytest.approx((-12.7, 0, 0, 1, 0, 2.38125))
    assert stock.tip.circle[1:] == pytest.approx((-22.225, 0, 0, -1, 0, 1.707896))
    assert (points[0][1] - points[1][1]) * 1000 == pytest.approx(9.525)
    assert len(stock.tip.probes) == 2
    assert stock.tip.probes[0] == pytest.approx((0.0, -22.225 / 1000, 1.707896 / 1000))
    assert stock.tip.probes[1] == stock.points[1]
    assert points[1][2] < stock.tip.circle[6] / 1000  # Actual surviving arc, not a full-circle guess.
    assert not state.selection.calls


@pytest.mark.parametrize("fault", (
    "missing_shoulder", "missing_tip", "wrong_shoulder_radius", "wrong_tip_radius",
    "finished_chamfer_radius", "finished_station", "major_chamfer_station",
    "wrong_axis", "zero_axis", "nonfinite_circle", "wrong_trim_plane", "wrong_trim_radius",
    "nonfinite_native_xyz", "nonfinite_native_parameter", "null_native_point",
    "text_native_coordinate", "boolean_native_parameter",
    "short_native_point", "long_native_point", "changed_membership",
    "ambiguous_distinct_edge", "same_entity",
))
def test_stock_length_refuses_wrong_geometry_or_unproved_trim(monkeypatch, fault) -> None:
    state = _physical_stock_fixture(monkeypatch)
    stock = state.stock
    if fault.startswith("missing"):
        stock.edges.pop(0 if fault == "missing_shoulder" else 1)
    elif fault in (
        "wrong_shoulder_radius", "wrong_tip_radius", "finished_chamfer_radius",
        "finished_station", "major_chamfer_station", "wrong_axis", "zero_axis",
        "nonfinite_circle",
    ):
        index = 0 if fault == "wrong_shoulder_radius" else 1
        edge = stock.shoulder if index == 0 else stock.tip
        circle = list(edge.circle)
        if fault == "wrong_shoulder_radius":
            circle[6] = screw.THREAD_MAJOR / 2
        elif fault == "wrong_tip_radius":
            circle[6] = screw.THREAD_MAJOR / 2
        elif fault == "finished_chamfer_radius":
            circle[6] = screw.THREAD_MAJOR / 2 - screw.CHAMFER_WIDTH
        elif fault == "finished_station":
            circle[1] = screw.TIP_Y
        elif fault == "major_chamfer_station":
            circle[1] += drawing.TIP_CHAMFER
        elif fault == "wrong_axis":
            circle[3:6] = (1.0, 0.0, 0.0)
        elif fault == "zero_axis":
            circle[3:6] = (0.0, 0.0, 0.0)
        else:
            circle[0] = float("nan")
        stock.edges[index] = state.item(edge, tuple(circle))
    elif fault == "null_native_point":
        stock.tip.GetClosestPointOn = lambda *_point: None
    elif fault == "changed_membership":
        calls = []

        def changed(*point):
            calls.append(point)
            x, y, z = stock.points[1]
            return (x if len(calls) == 1 else -x, y, z, 0.0, 0.0)

        stock.tip.GetClosestPointOn = changed
    elif fault == "ambiguous_distinct_edge":
        stock.edges.append(state.item(_HeadRim(
            state.selection, stock.tip.circle, nearest=stock.tip.nearest,
        )))
    elif fault == "same_entity":
        stock.edges[1] = state.item(stock.shoulder, stock.tip.circle)
    else:
        point = list(stock.tip.nearest)
        if fault == "wrong_trim_plane":
            point[1] += 0.0001
        elif fault == "wrong_trim_radius":
            point[2] += 0.0001
        elif fault == "nonfinite_native_xyz":
            point[0] = float("nan")
        elif fault == "nonfinite_native_parameter":
            point[3] = float("inf")
        elif fault == "text_native_coordinate":
            point[0] = str(point[0])
        elif fault == "boolean_native_parameter":
            point[3] = True
        elif fault == "short_native_point":
            point.pop()
        elif fault == "long_native_point":
            point.append(0.0)
        stock.tip.nearest = tuple(point)
    with pytest.raises(RuntimeError, match="SupplierStockThreadLength"):
        drawing._stock_length_entities(state.adapter, stock.view)
    assert not state.additions and not state.selection.calls
    assert all(
        len(fields["candidates"]) <= 12 for name, fields in state.events
        if name == "drawing.pivot_stock_length_edges"
    )


def test_stock_length_chooses_unique_frontmost_actual_edge_not_first_circle(monkeypatch) -> None:
    state = _physical_stock_fixture(monkeypatch)
    stock = state.stock
    x, y, z = stock.points[1]
    rear = _HeadRim(state.selection, stock.tip.circle, nearest=(x, y, -z, 0.0, 0.0))
    stock.edges.insert(0, state.item(rear))
    # Duplicate wrappers for the SAME native edge do not create a distinct-edge ambiguity.
    stock.edges.append(state.item(stock.tip))
    entities, points = drawing._stock_length_entities(state.adapter, stock.view)
    assert entities == (stock.shoulder, stock.tip)
    assert points == stock.points
    evidence = state.events[-1][1]
    assert evidence["matches"] == 3 and evidence["frontmost_matches"] == 2


def test_stock_length_bounds_native_candidate_diagnostics(monkeypatch) -> None:
    state = _physical_stock_fixture(monkeypatch)
    stock = state.stock
    stock.edges[:0] = [
        state.item(_HeadRim(state.selection, (
            0.0, -100.0 - index, 0.0, 0.0, 1.0, 0.0, 5.0 + index,
        )))
        for index in range(30)
    ]
    drawing._stock_length_entities(state.adapter, stock.view)
    evidence = state.events[-1][1]
    assert evidence["configured_source_path"] == str(drawing.SOURCE.resolve())
    assert evidence["native_source_path"] == stock.source.path
    assert evidence["configuration"] == screw.SUPPLIER_STOCK_CONFIGURATION
    assert evidence["candidate_count"] == 32 and len(evidence["candidates"]) == 12
    actual = evidence["candidates"][0]
    assert actual["forward_xyz_u"][:3] == stock.points[1]
    assert actual["membership_xyz_u"][:3] == stock.points[1]
    assert actual["membership_error_m"] == 0.0


@pytest.mark.parametrize("configuration, mode", (
    ("Default", 2), ("AS SUPPLIED", 2), ("", 2),
    (screw.SUPPLIER_STOCK_CONFIGURATION, 0),
    (screw.SUPPLIER_STOCK_CONFIGURATION, 1),
    (screw.SUPPLIER_STOCK_CONFIGURATION, 3),
))
def test_stock_length_requires_actual_stock_configuration_and_hlr_before_scan(
    monkeypatch, configuration, mode,
) -> None:
    state = _physical_stock_fixture(monkeypatch)
    state.stock.view.ReferencedConfiguration = configuration
    state.stock.view.mode = mode
    with pytest.raises(RuntimeError, match="configuration|hidden-lines-removed"):
        drawing._stock_length_entities(state.adapter, state.stock.view)
    assert not state.scans and not state.selection.calls
    assert state.events[-1][1]["configuration"] == configuration


def _stock_creation_recipe_fixture(monkeypatch):
    state = _physical_stock_fixture(monkeypatch)
    state.stock.view.mode = 0
    state.stock.view.ReferencedConfiguration = "Default"
    state.stock_iso = SimpleNamespace(ReferencedConfiguration="Default", mode=0)
    state.recipe_calls = []
    state.model.ActivateSheet = lambda name: (
        state.recipe_calls.append(("sheet", name)) or name == drawing.SHEET_NAMES[1]
    )
    state.model.EditRebuild3 = lambda: state.recipe_calls.append(("rebuild",)) or True
    state.model.GetEditSheet = lambda: True
    monkeypatch.setattr(
        drawing, "place_view",
        lambda _adapter, _source, orientation, *_args, **_kwargs: (
            state.stock.view if orientation == "*Front" else state.stock_iso
        ),
    )
    monkeypatch.setattr(
        drawing, "set_view_position",
        lambda _adapter, view, *centre: state.recipe_calls.append(("position", view, centre)) or True,
    )
    monkeypatch.setattr(
        drawing, "set_hidden_lines_removed",
        lambda _adapter, view: setattr(view, "mode", 2),
    )
    monkeypatch.setattr(
        drawing, "_format_supplier_reference",
        lambda _adapter, display, label: (
            state.recipe_calls.append(("format", display, label)) or state.stock.annotation
        ),
    )
    monkeypatch.setattr(
        drawing, "add_property_linked_note",
        lambda *_args: SimpleNamespace(GetAnnotation=lambda: SimpleNamespace(OwnerType=1)),
    )
    return state


def test_stock_recipe_uses_view_entity_selection_and_creation_axial_proof(monkeypatch) -> None:
    state = _stock_creation_recipe_fixture(monkeypatch)
    stock = state.stock
    assert drawing._add_stock_reference(state.adapter) == (
        stock.view, state.stock_iso, stock.annotation,
    )
    assert [call for call in state.selection.calls if call[0] == "view_select"] == [
        ("view_select", stock.view, stock.shoulder, False),
        ("view_select", stock.view, stock.tip, True),
    ]
    assert state.recipe_calls[0:2] == [("sheet", drawing.SHEET_NAMES[1]), ("rebuild",)]
    assert len(state.scans) == 1
    assert state.scans[0][1] is stock.view
    assert state.additions == [(0.130, 0.118, 0.0)]
    proof = next(
        fields for name, fields in state.events
        if name == "drawing.physical_axial_dimension_native_proof"
    )
    assert proof["phase"] == "creation" and proof["label"] == "SupplierStockThreadLength"
    assert proof["points_m"] == stock.points
    assert proof["measured_mm"] == pytest.approx(9.525)
    assert not state.selection.selected


def test_stock_recipe_refuses_failed_configuration_readback_before_selection(monkeypatch) -> None:
    state = _stock_creation_recipe_fixture(monkeypatch)

    def rebuild():
        state.stock.view.ReferencedConfiguration = "Default"
        return True

    state.model.EditRebuild3 = rebuild
    with pytest.raises(RuntimeError, match="references the faced screw"):
        drawing._add_stock_reference(state.adapter)
    assert not state.scans and not state.selection.calls and not state.additions


@pytest.mark.parametrize("fault", (
    "select_first", "select_second", "count", "selection_type", "missing_selected",
    "wrong_selected", "same_selected", "point_set", "point_read", "point_null",
    "null_creation", "angular_type", "legacy_vertical_type", "horizontal_type",
    "wrong_value", "wrong_attachment", "dangling", "horizontal_arrows", "diagonal_arrows",
))
def test_stock_recipe_refuses_selection_null_or_invalid_native_creation(monkeypatch, fault) -> None:
    state = _stock_creation_recipe_fixture(monkeypatch)
    stock = state.stock
    if fault.startswith("select_"):
        state.selection.refuse_index = 1 if fault == "select_first" else 2
    elif fault == "count":
        state.selection.count_offset = 1
    elif fault == "selection_type":
        state.selection.types[2] = 46
    elif fault == "missing_selected":
        state.selection.actual[2] = None
    elif fault == "wrong_selected":
        state.selection.actual[2] = object()
    elif fault == "same_selected":
        state.selection.actual[2] = stock.shoulder
    elif fault == "point_set":
        state.selection.point_result = False
    elif fault == "point_read":
        state.selection.GetSelectionPoint2 = lambda *_args: (0.0, 0.0, 0.0)
    elif fault == "point_null":
        state.selection.GetSelectionPoint2 = lambda *_args: None
    elif fault == "null_creation":
        state.create_result = None
    elif fault in ("angular_type", "legacy_vertical_type", "horizontal_type"):
        stock.display.Type2 = {
            "angular_type": 3, "legacy_vertical_type": 12, "horizontal_type": 11,
        }[fault]
    elif fault == "wrong_value":
        stock.native.SystemValue = screw.FITTED_THREAD_LEN / 1000
    elif fault == "wrong_attachment":
        stock.annotation.attached[1] = object()
    elif fault == "dangling":
        stock.annotation.dangling = True
    elif fault in ("horizontal_arrows", "diagonal_arrows"):
        direction = (1.0, 0.0, 0.0) if fault == "horizontal_arrows" else (0.1, 1.0, 0.0)
        stock.arrows[0] = (*stock.arrows[0][:3], *direction, *stock.arrows[0][6:])
    with pytest.raises(RuntimeError, match="SupplierStockThreadLength"):
        drawing._add_stock_reference(state.adapter)
    assert not state.selection.selected
    assert not any(call[0] == "format" for call in state.recipe_calls)


@pytest.mark.parametrize("phase", ("settled", "saved"))
@pytest.mark.parametrize("fault", (
    "none", "geometry", "trim", "configuration", "attachment", "null_attachment",
    "wrong_source", "null_source", "empty_source_path", "relative_source_path",
    "angular_type", "legacy_type", "value", "horizontal", "diagonal", "wrong_scale",
    "owner", "missing_native", "missing_dimension", "duplicate_dimension", "presentation",
))
def test_stock_physical_proof_is_fresh_in_settled_and_readonly_saved_census(
    monkeypatch, tmp_path, phase, fault,
) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    stock = state.stock
    if phase == "settled":
        state.adapter.currentModel = state.saved
        state.front.dimensions[:] = [state.display]
        state.identities["SupplierHeadHeight"] = (
            state.native.FullName, state.front.name, (state.bearing, state.top), (1, 1),
        )
        state.identities["SupplierStockThreadLength"] = (
            stock.native.FullName, stock.view.name, (stock.shoulder, stock.tip), (1, 1),
        )
        monkeypatch.setattr(
            drawing, "SUPPLIER_REFERENCE_DIMENSIONS",
            {name: screw.SUPPLIER_REFERENCE_DIMENSIONS[name] for name in state.identities},
        )
        caption = SimpleNamespace(
            GetText=lambda: screw.SUPPLIER_STOCK_TITLE,
            PropertyLinkedText=drawing.property_link("Supplier Reference Title"),
        )
        state.sheets[drawing.SHEET_NAMES[1]].GetAnnotations = lambda: (
            SimpleNamespace(GetType=lambda: 6, OwnerType=1, GetSpecificAnnotation=lambda: caption),
        )
    if fault == "geometry":
        stock.edges.pop()
    elif fault == "trim":
        stock.tip.nearest = (0.0, screw.TIP_Y / 1000, 0.0, 0.0, 0.0)
    elif fault == "configuration":
        stock.view.ReferencedConfiguration = "Default"
    elif fault == "wrong_source":
        stock.source.path = str(tmp_path / "another.SLDPRT")
    elif fault == "null_source":
        stock.view.ReferencedDocument = None
    elif fault == "empty_source_path":
        stock.source.path = ""
    elif fault == "relative_source_path":
        stock.source.path = "pivot.SLDPRT"
    elif fault == "attachment":
        stock.annotation.attached[1] = object()
    elif fault == "null_attachment":
        stock.annotation.attached[1] = None
    elif fault in ("angular_type", "legacy_type"):
        stock.display.Type2 = 3 if fault == "angular_type" else 12
    elif fault == "value":
        stock.native.SystemValue = screw.FITTED_THREAD_LEN / 1000
    elif fault in ("horizontal", "diagonal"):
        direction = (1.0, 0.0, 0.0) if fault == "horizontal" else (0.1, 1.0, 0.0)
        stock.arrows[0] = (*stock.arrows[0][:3], *direction, *stock.arrows[0][6:])
    elif fault == "wrong_scale":
        stock.view.ScaleDecimal = 2.0
    elif fault == "owner":
        stock.annotation.Owner = SimpleNamespace(name=stock.view.name)
    elif fault == "missing_native":
        stock.display.GetDimension2 = lambda _index: None
    elif fault == "missing_dimension":
        stock.view.dimensions.clear()
    elif fault == "duplicate_dimension":
        stock.view.dimensions.append(stock.display)
    elif fault == "presentation":
        stock.texts[2] = ")"
    def run():
        if phase == "settled":
            drawing._assert_supplier_references(
                state.adapter, state.identities, state.configurations,
            )
        else:
            drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=state.serialized_full_names,
            serialized_shelf_names=state.serialized_shelf_names,)
    if fault == "none":
        run()
        assert {scan[1].name for scan in state.scans} == {state.front.name, stock.view.name}
    else:
        with pytest.raises(RuntimeError):
            run()
    assert not state.additions and not state.selection.calls
    if phase == "saved":
        assert state.closes == [state.path.name]
        assert state.adapter.currentModel is state.previous


@pytest.mark.parametrize("fault", (
    "wrong_full_name", "sheet_duplicate", "wrong_sheet", "wrong_owner",
    "wrong_annotation_owner", "captured_wrong_sheet", "captured_wrong_configuration",
    "duplicate_captured_name", "missing_captured_name", "lost_hlr", "source_band",
))
def test_saved_stock_exact_inventory_owner_configuration_and_source_guards(
    monkeypatch, tmp_path, fault,
) -> None:
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    stock = state.stock
    if fault == "wrong_full_name":
        stock.native.FullName = "D99@OtherStock"
    elif fault == "sheet_duplicate":
        state.sheets[drawing.SHEET_NAMES[0]].GetDisplayDimensions = lambda: (stock.display,)
    elif fault == "wrong_sheet":
        state.sheets[drawing.SHEET_NAMES[1]].GetNextView = lambda: None
        state.front.dimensions.append(stock.display)
    elif fault == "wrong_owner":
        stock.view.name = "OtherStock"
    elif fault == "wrong_annotation_owner":
        stock.annotation.Owner = SimpleNamespace(name="OtherStock")
    elif fault == "captured_wrong_sheet":
        state.configurations[stock.view.name] = (
            drawing.SHEET_NAMES[0], screw.SUPPLIER_STOCK_CONFIGURATION,
        )
    elif fault == "captured_wrong_configuration":
        state.configurations[stock.view.name] = (drawing.SHEET_NAMES[1], "Default")
    elif fault in ("duplicate_captured_name", "missing_captured_name"):
        state.serialized_full_names["SupplierStockThreadLength"] = (
            state.native.FullName if fault == "duplicate_captured_name" else ""
        )
    elif fault == "lost_hlr":
        stock.view.mode = 1
    elif fault == "source_band":
        stock.tolerance.Type = 2
    with pytest.raises(RuntimeError):
        drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=state.serialized_full_names,
        serialized_shelf_names=state.serialized_shelf_names,)
    if fault in ("duplicate_captured_name", "missing_captured_name"):
        assert not state.opens and not state.closes
    else:
        assert state.closes == [state.path.name]
    assert state.adapter.currentModel is state.previous
    assert not state.additions and not state.selection.calls


@pytest.mark.parametrize("fault", (
    "null_document", "wrong_path", "null_path", "empty_path", "relative_path", "filename_only",
))
def test_stock_source_identity_refuses_before_scanning_or_selection(monkeypatch, fault) -> None:
    state = _physical_stock_fixture(monkeypatch)
    stock = state.stock
    if fault == "null_document":
        stock.view.ReferencedDocument = None
    else:
        stock.source.path = {
            "wrong_path": str(drawing.SOURCE.with_name("other.SLDPRT").resolve()),
            "null_path": None,
            "empty_path": "",
            "relative_path": f"../{drawing.SOURCE.name}",
            "filename_only": drawing.SOURCE.name,
        }[fault]
    with pytest.raises(RuntimeError, match="native source"):
        drawing._stock_length_entities(state.adapter, stock.view)
    assert not state.scans and not state.selection.calls and not state.additions
    evidence = state.events[-1][1]
    assert evidence["configured_source_path"] == str(drawing.SOURCE.resolve())
    if fault == "null_document":
        assert evidence["referenced_document_null"] is True
        assert "native_source_path" not in evidence  # Getter was never reached.
    else:
        assert evidence["native_source_path"] == stock.source.path
    assert "configuration" not in evidence  # Path identity is proved first.


@pytest.mark.parametrize("query", ("forward", "membership"))
def test_stock_trim_getter_errors_preserve_cause_and_bounded_actual_evidence(
    monkeypatch, query,
) -> None:
    state = _physical_stock_fixture(monkeypatch)
    stock = state.stock
    error = OSError("native trim read failed")
    calls = []

    def closest(*point):
        calls.append(point)
        if query == "forward" or len(calls) == 2:
            raise error
        return stock.tip.nearest

    stock.tip.GetClosestPointOn = closest
    with pytest.raises(RuntimeError, match="native trim query failed") as refusal:
        drawing._stock_length_entities(state.adapter, stock.view)
    assert refusal.value.__cause__ is error
    evidence = state.events[-1][1]
    assert evidence["query"] == query
    assert evidence["native_error"] == str(error)
    assert evidence["native_source_path"] == stock.source.path
    assert len(evidence["candidates"]) <= 12
    assert len(state.scans) == 1
    assert not state.selection.calls and not state.additions


@pytest.mark.parametrize("fault", ("null_document", "wrong_path"))
def test_stock_creation_recipe_requires_exact_native_source_before_selection(
    monkeypatch, fault,
) -> None:
    state = _stock_creation_recipe_fixture(monkeypatch)
    if fault == "null_document":
        state.stock.view.ReferencedDocument = None
    else:
        state.stock.source.path = str(drawing.SOURCE.with_name("other.SLDPRT").resolve())
    with pytest.raises(RuntimeError, match="native source"):
        drawing._add_stock_reference(state.adapter)
    assert not state.scans and not state.selection.calls and not state.additions


def _native_line(first, second):
    return [0.0, 0.0, 0.0, 0.0, *first, 0.0, *second, 0.0]


def _native_text(text, x, y, width):
    return dict(t=text, pos=[x, y, 0.0], h=0.0035, w=width, ref=1, ang=0.0)


def _native_reference_record(name, axis, tips, sources, texts):
    lines, arrows = [], []
    for index, tip in enumerate(tips):
        direction = -1.0 if index == 0 else 1.0
        end = list(tip)
        end[axis] += direction * 0.00635
        lines.append(_native_line(tip, end))
        witness_end = list(tip)
        witness_end[1 - axis] += (-0.001 if axis == 0 else 0.001)
        lines.append(_native_line(sources[index], witness_end))
        vector = (direction, 0.0, 0.0) if axis == 0 else (0.0, direction, 0.0)
        arrows.append([*tip, 0.0, *vector, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0])
    lines.append(_native_line(tips[0], tips[1]))
    return dict(type=4, name=name, visible=1, owner_type=0,
                display=dict(lines=lines, arrows=arrows, texts=texts))


def _saved_shelf_boundary(monkeypatch, state):
    """Actual native dump boundary; real shelf/axis/source predicates stay active."""
    import _supplier_reference_text as shelves

    def dump(_reader, annotation):
        record = annotation.paper_record
        return copy.deepcopy(record() if callable(record) else record)

    monkeypatch.setattr(drawing, "_dump_annotation", dump)
    monkeypatch.setattr(shelves, "_dump_annotation", dump)
    monkeypatch.setattr(shelves, "_early_bound", lambda value, _kind: value)
    state.front.Position = drawing.FRONT_CENTER
    state.front.origin_offset = (0.0, 0.040)
    state.front.Angle = 0.0
    state.front.GetOutline = lambda: (0.118537, 0.092252, 0.161463, 0.207748)
    state.paper_top = SimpleNamespace(
        name="FinishedTop", Position=(0.140, 0.245), origin_offset=(0.0, 0.0),
        Angle=0.0, ScaleDecimal=4.0, ReferencedConfiguration="Default",
        ReferencedDocument=SimpleNamespace(GetPathName=lambda: str(drawing.SOURCE.resolve())),
    )
    state.paper_top.GetDisplayMode2 = lambda: 2
    state.paper_top.GetOutline = lambda: (
        state.paper_top.Position[0] - 0.021463, 0.223537,
        state.paper_top.Position[0] + 0.021463, 0.266463,
    )
    state.paper_iso = SimpleNamespace(
        name="FinishedIso", Position=drawing.ISO_CENTER, Angle=0.0, ScaleDecimal=4.0,
        ReferencedConfiguration="Default", ReferencedDocument=state.paper_top.ReferencedDocument,
        GetOutline=lambda: (0.3319614, 0.1038607, 0.3880386, 0.2261393),
        GetDisplayDimensions=lambda: (), GetNextView=lambda: None,
    )
    state.front.GetNextView = lambda: state.paper_top
    state.paper_top.GetNextView = lambda: state.paper_iso
    state.paper_sheet = SimpleNamespace(margins=[0.0127] * 4, height=0.2794)
    state.paper_sheet.GetProperties2 = lambda: (
        1.0, 0.0, 4.0, 1.0, 0.0, 0.4318, state.paper_sheet.height, 0.0,
    )
    state.paper_sheet.GetZoneMargin = lambda index: state.paper_sheet.margins[index]

    def project(_adapter, view, points, *, label):
        origin = tuple(a + b for a, b in zip(view.Position, view.origin_offset, strict=True))
        projected = []
        for index in range(len(points)):
            x, y, z = points[index]
            projected.append((
                origin[0] + 4 * x, origin[1] + (-4 * z if view is state.paper_top else 4 * y),
            ))
        return tuple(projected)

    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(
        drawing, "model_point_in_view",
        lambda adapter, view, point, *, label: project(adapter, view, (point,), label=label)[0],
    )
    head_tips = tuple(tuple(arrow[:2]) for arrow in state.arrows)
    reach = max(point[1] for point in head_tips) + 0.00635
    state.head_record = _native_reference_record(
        "Head height", 1, head_tips, ((0.156875, head_tips[0][1]), (0.1556558, head_tips[1][1])),
        [_native_text("(0.156 in)", 0.2139253, reach + 0.0077563, 0.0201493),
         _native_text("HEAD HEIGHT", 0.2090497, reach + 0.0022, 0.0299007)],
    )
    state.annotation.paper_record = state.head_record
    state.display.OffsetText = True
    state.socket_record = _native_reference_record(
        "Socket", 0, ((0.1352375, 0.2276449), (0.1447625, 0.2276449)),
        ((0.1352375, 0.2412504), (0.1447625, 0.2412504)),
        [_native_text("(", 0.1718486, 0.2352722, 0.0017208),
         _native_text("3", 0.1758882, 0.2378294, 0.0025861),
         _native_text("32", 0.1745951, 0.2332011, 0.0051722),
         _native_text('" in)', 0.1807931, 0.2352722, 0.0082347),
         _native_text("HEX SOCKET AF", 0.1633125, 0.2276449, 0.0342514)],
    )
    state.socket_record["display"]["lines"].append(
        _native_line((0.1740823, 0.2381371), (0.1802802, 0.2381371)),
    )
    socket_edges = [
        SimpleNamespace(GetClosestPointOn=lambda *_point, x=x: (x, screw.HEAD_H / 1000, 0.0, 0.0))
        for x in (-screw.SOCKET_AF / 2 / 1000, screw.SOCKET_AF / 2 / 1000)
    ]
    state.socket_annotation = SimpleNamespace(
        Owner=state.paper_top, OwnerType=0, Visible=1, attached=list(socket_edges),
        paper_record=state.socket_record, IsDangling=lambda: False,
        GetName=lambda: "Native socket annotation",
        GetAttachedEntityCount3=lambda: 2, GetAttachedEntityTypes=lambda: (1, 1),
    )
    state.socket_annotation.GetAttachedEntities3 = lambda: tuple(state.socket_annotation.attached)
    state.socket_native = SimpleNamespace(
        FullName="D1@FinishedTop@pivot.SLDDRW", SystemValue=screw.SOCKET_AF / 1000,
        Tolerance=SimpleNamespace(Type=0),
    )
    presentation = screw.SUPPLIER_REFERENCE_DIMENSIONS["SupplierSocketAF"]
    texts = {1: "(", 2: ")", 4: presentation["callout"]}
    state.socket_display = SimpleNamespace(
        Type2=2, OffsetText=True, ShowDimensionValue=True, ShowParenthesis=False,
        GetDimension2=lambda _index: state.socket_native,
        GetAnnotation=lambda: state.socket_annotation, GetUseDocUnits=lambda: False,
        GetUnits=lambda: 3, GetPrimaryPrecision2=lambda: presentation["precision"],
        GetFractionBase=lambda: 2, GetOverride=lambda: False, GetText=lambda index: texts[index],
        GetFractionValue=lambda: 32, GetRoundToFraction=lambda: False,
        GetNameForSelection=lambda: "Native socket selection",
    )
    state.socket_annotation.GetSpecificAnnotation = lambda: state.socket_display
    state.paper_top.GetDisplayDimensions = lambda: (state.socket_display,)
    original_scan = drawing.scan_view_edges

    def scan(view, *, label):
        if view is state.paper_top:
            return SimpleNamespace(edges=tuple(SimpleNamespace(edge=edge) for edge in socket_edges))
        return original_scan(view, label=label)

    monkeypatch.setattr(drawing, "scan_view_edges", scan)
    state.mark = SimpleNamespace(UseDocDisplaySettings=False, ShowLines=False, Size=0.00075)
    state.mark_override = None

    def mark_lines():
        if state.mark_override is not None:
            return state.mark_override
        x, y = project(state.adapter, state.paper_top, ((0, 0, 0),), label="mark")[0]
        arm = state.mark.Size * state.paper_top.ScaleDecimal
        return [_native_line((x, y), end) for end in (
            (x - arm, y), (x + arm, y), (x, y - arm), (x, y + arm),
        )]

    state.mark_lines = mark_lines
    data = SimpleNamespace(
        GetLineCount=lambda: len(mark_lines()), GetLineAtIndex2=lambda index: mark_lines()[index],
    )
    state.mark_annotation = SimpleNamespace(
        Owner=state.paper_top, OwnerType=0, Visible=1,
        GetSpecificAnnotation=lambda: state.mark, GetDisplayData=lambda: data,
        paper_record=lambda: dict(type=13, name="Mark", visible=1, owner_type=0,
                                 display=dict(lines=mark_lines())),
    )
    state.paper_top.GetAnnotationsByType = lambda _kind: (state.mark_annotation,)
    state.front.GetAnnotations = lambda: (state.annotation,)
    state.paper_top.GetAnnotations = lambda: (state.socket_annotation, state.mark_annotation)


@pytest.mark.parametrize("fault", ("none", "head_offset", "head_reach", "socket_offset",
                                  "fraction", "socket_name", "socket_span", "socket_attachment",
                                  "alignment", "axis", "mark_escape", "mark_nan", "mark_axis"))
def test_cold_saved_presentation_is_fresh_and_fail_closed(monkeypatch, tmp_path, fault):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    if fault == "head_offset":
        state.display.OffsetText = False
    elif fault == "head_reach":
        state.head_record["display"]["texts"][1]["pos"][1] -= 0.003
    elif fault == "socket_offset":
        state.socket_display.OffsetText = False
    elif fault == "fraction":
        state.socket_record["display"]["texts"][2]["pos"][0] = 0.145
    elif fault == "socket_name":
        state.serialized_shelf_names["SupplierSocketAF"] += " stale"
    elif fault == "socket_span":
        state.socket_record["display"]["arrows"][0][0] -= 0.001
    elif fault == "socket_attachment":
        state.socket_annotation.attached[0] = state.bearing
    elif fault == "alignment":
        state.paper_top.Position = (0.295, 0.245)
    elif fault == "axis":
        state.paper_top.Angle = 0.1
    elif fault.startswith("mark_"):
        state.mark_override = copy.deepcopy(state.mark_lines())
        state.mark_override[0][{"mark_escape": 8, "mark_nan": 4, "mark_axis": 5}[fault]] = {
            "mark_escape": 0.270875, "mark_nan": float("nan"), "mark_axis": 0.244,
        }[fault]
    def prove():
        drawing._assert_saved_physical_references(state.adapter, state.identities, state.configurations, paper=state.paper, serialized_full_names=state.serialized_full_names,
        serialized_shelf_names=state.serialized_shelf_names,)
    if fault == "none":
        prove()
    else:
        with pytest.raises(RuntimeError):
            prove()
    assert state.closes == [state.path.name]
    assert state.adapter.currentModel is state.previous
    assert not state.additions and not state.selection.calls


def test_top_translation_uses_projected_origins_not_geometric_centres(monkeypatch, tmp_path):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.adapter.currentModel = state.saved
    state.paper_top.Position = (0.295, 0.245)
    state.paper_top.origin_offset = (0.002, 0.0)
    original_front, original_iso = state.front.Position, state.paper_iso.Position
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        drawing, "set_view_position",
        lambda _adapter, view, x, y, *, move_children: (
            setattr(view, "Position", (x, y)) or not move_children
        ),
    )
    settled = drawing._align_top_origin(state.adapter, state.front, state.paper_top, state.paper_iso)
    assert state.paper_top.Position == pytest.approx((0.138, 0.245))
    assert state.front.Position == original_front and state.paper_iso.Position == original_iso
    state.paper_top.Position = (0.140, 0.245)
    with pytest.raises(RuntimeError, match="drift"):
        settled()


@pytest.mark.parametrize("fault", ("none", "oversized_ink", "missing_axis", "off_axis"))
def test_native_finite_mark_reads_actual_endpoints_not_just_show_lines(monkeypatch, tmp_path, fault):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.adapter.currentModel = state.saved
    state.mark.UseDocDisplaySettings = True
    state.mark.ShowLines = True
    state.mark.Size = 0.0025
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    settled = drawing._trim_top_mark(state.adapter, state.paper_top)
    assert state.mark.Size * state.paper_top.ScaleDecimal == pytest.approx(0.003)
    if fault != "none":
        state.mark_override = copy.deepcopy(state.mark_lines())
        if fault == "oversized_ink":
            state.mark_override[2][8] = 0.270875
        elif fault == "missing_axis":
            state.mark_override = state.mark_override[:2]
        else:
            state.mark_override[0][5] += 0.0001
        with pytest.raises(RuntimeError):
            settled()
    else:
        settled()


@pytest.mark.parametrize("x_axis,z_axis", ((4.0, 0.0), (-4.0, 0.0), (0.0, 4.0), (2.4, 3.2)))
def test_head_note_target_requires_actual_sheet_left_trim_membership(
    monkeypatch, x_axis, z_axis,
):
    state = _physical_head_fixture(monkeypatch)
    def project(_adapter, _view, points, *, label):
        return tuple(
            (0.140 + x_axis * x + z_axis * z, 0.190 + 4 * y) for x, y, z in points
        )
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(
        drawing, "model_point_in_view",
        lambda adapter, view, point, *, label: project(adapter, view, (point,), label=label)[0],
    )
    edge, point = drawing._purchased_head_target(state.adapter, state.front)
    radius = drawing._HEAD_TOP_R / 1000
    scale = math.hypot(x_axis, z_axis)
    assert edge is state.top
    assert point == pytest.approx((0.140 - radius * scale, 0.190 + 4 * screw.HEAD_H / 1000))
    assert state.top.probes[-1] == pytest.approx((
        -radius * x_axis / scale, screw.HEAD_H / 1000, -radius * z_axis / scale,
    ))
    state.top.nearest = (*drawing._head_height_points()[1], 0.0)
    with pytest.raises(RuntimeError, match="actual trimmed rim"):
        drawing._purchased_head_target(state.adapter, state.front)


@pytest.mark.parametrize("fault", ("nonfinite", "collapsed", "tilted", "center", "landing"))
def test_head_note_refuses_unproven_native_projection_axes(monkeypatch, fault):
    state = _physical_head_fixture(monkeypatch)
    def project(_adapter, _view, points, *, label):
        result = [[0.140 + 4 * x, 0.190 + 4 * y] for x, y, _z in points]
        if fault == "nonfinite":
            result[0][0] = math.nan
        elif fault == "collapsed":
            for point in result:
                point[0] = 0.140
        elif fault == "tilted":
            result[0][1] += 0.001
        elif fault == "center":
            result[2][0] += 0.001
        return result
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(
        drawing, "model_point_in_view",
        lambda _adapter, _view, point, *, label: (
            0.140 + 4 * point[0] + (0.001 if fault == "landing" else 0.0),
            0.190 + 4 * point[1],
        ),
    )
    with pytest.raises(RuntimeError, match="Purchased Screw Note"):
        drawing._purchased_head_target(state.adapter, state.front)


def _finished_paper_fixture(monkeypatch, tmp_path, *, _state=None):
    if _state is None:
        state = _saved_physical_fixture(monkeypatch, tmp_path)
        state.adapter.currentModel = state.saved
        return state
    state = _state
    state.adapter.currentModel = state.saved
    state.front.origin_offset = (0.0, 0.036285)
    import _drawing_physical_axial_dimension as physical
    original_project = physical.model_points_in_view
    def physical_project(adapter, view, points, *, label):
        if view is state.front:
            return drawing.model_points_in_view(adapter, view, points, label=label)
        return original_project(adapter, view, points, label=label)
    monkeypatch.setattr(physical, "model_points_in_view", physical_project)
    for index, arrow in enumerate(state.arrows):
        state.arrows[index] = (arrow[0], arrow[1] - 0.003715, *arrow[2:])
    for row in state.head_record["display"]["texts"]:
        row["pos"][1] -= 0.003715
    for row in state.head_record["display"]["arrows"]:
        row[1] -= 0.003715
    for row in state.head_record["display"]["lines"]:
        row[5] -= 0.003715
        row[8] -= 0.003715
    diameter_record = _native_reference_record(
        "Head diameter", 0, ((0.124125, 0.206577), (0.155875, 0.206577)),
        ((0.124125, 0.2019408), (0.155875, 0.2019408)),
        [_native_text("(", 0.1272861, 0.2121868, 0.0017208),
         _native_text("<MOD-DIAM>", 0.129007, 0.2121333, 0.0052784),
         _native_text("0.313 in)", 0.1342854, 0.2121868, 0.0184285),
         _native_text("HEAD", 0.1336927, 0.206577, 0.0126146)],
    )
    # These are the actual recorded outside witnesses, not the generic fixture convention.
    diameter_record["display"]["lines"][1] = _native_line((0.124125, 0.2019408), (0.124125, 0.207577))
    diameter_record["display"]["lines"][3] = _native_line((0.155875, 0.2019408), (0.155875, 0.207577))
    state.diameter_annotation = SimpleNamespace(paper_record=diameter_record)
    shoulder_record = dict(type=4, display=dict(texts=[
        _native_text("AS-SUPPLIED SHOULDER", 0.1758545, 0.1646962, 0.052291),
        _native_text("0.000", 0.203526, 0.1747781, 0.0116375),
    ]))
    state.shoulder_annotation = SimpleNamespace(paper_record=shoulder_record, GetType=lambda: 4)
    length_record = dict(type=4, name="SupplierShoulderLength", display=dict(
        lines=[
            _native_line((0.148525, 0.135485), (0.064, 0.135485)),
            _native_line((0.148525, 0.186285), (0.064, 0.186285)),
            _native_line((0.065, 0.135485), (0.065, 0.1626962)),
            _native_line((0.065, 0.186285), (0.065, 0.1773038)),
        ],
        arrows=[
            [0.065, y, 0.0004, 0.0, direction, 0.0,
             0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0]
            for y, direction in ((0.135485, 1.0), (0.186285, -1.0))
        ],
        texts=[
            _native_text("(0.500 ", 0.0470455, 0.1683059, 0.0146514),
            _native_text("+", 0.0616969, 0.1727781, 0.0028292),
            _native_text(" ", 0.0624649, 0.1682524, 0.0012931),
            _native_text("0.002", 0.064526, 0.1727781, 0.0116375),
            _native_text("0.000", 0.064526, 0.1682524, 0.0116375),
            _native_text(" in)", 0.0761635, 0.1683059, 0.006791),
            _native_text("AS-SUPPLIED SHOULDER", 0.0388545, 0.1626962, 0.052291),
        ],
    ))
    state.shoulder_length_annotation = SimpleNamespace(paper_record=length_record, GetType=lambda: 4)
    state.paper_displays = dict(
        SupplierHeadDiameter=SimpleNamespace(GetAnnotation=lambda: state.diameter_annotation),
        SupplierShoulderDiameter=SimpleNamespace(GetAnnotation=lambda: state.shoulder_annotation),
        SupplierShoulderLength=SimpleNamespace(GetAnnotation=lambda: state.shoulder_length_annotation),
        SupplierHeadHeight=state.display, SupplierSocketAF=state.socket_display,
    )
    state.note_text = _config.parts(part.PART_NAME)["purchased_note"]
    _edge, state.landing = drawing._purchased_head_target(state.adapter, state.front)
    state.note_position = [*drawing.PURCHASED_NOTE_XY, 0.0]
    state.note_start_override = None
    state.note_ink_missing = False
    state.note_arrow_count = 1
    state.wrap_fault = ""
    state.note_uses_doc_font = True
    state.note_format = SimpleNamespace(
        LineLength=0.0, TypeFaceName="Century Gothic", CharHeight=0.0035,
        WidthFactor=1.0, CharSpacingFactor=1.0, LineSpacing=0.001,
        Bold=False, Italic=False, Underline=False, Strikeout=False,
        BackWards=False, UpsideDown=False, Vertical=False,
    )
    def note_rows():
        # Native boundary double: automatic rows leave the underlying string
        # untouched. No wrapping algorithm is added to the production recipe.
        chunks = [state.note_text]
        if state.note_format.LineLength > 0 and state.wrap_fault != "unwrapped":
            chunks = [""]
            for word in state.note_text.split():
                candidate = f"{chunks[-1]} {word}".strip()
                measured = 0.1777368 * len(candidate) / len(state.note_text)
                if chunks[-1] and measured > state.note_format.LineLength:
                    chunks.append(word)
                else:
                    chunks[-1] = candidate
        x, y, _z = state.note_position
        return [
            {**_native_text(chunk, x, y - 0.0045257 - index * (0.0035 + state.note_format.LineSpacing),
                           0.1777368 * len(chunk) / len(state.note_text)), "font": "Century Gothic"}
            for index, chunk in enumerate(chunks)
        ]
    def leader_start():
        box = drawing.display_box({"texts": note_rows()})
        return state.note_start_override or (
            box.xmax + 0.0005182, state.note_position[1] - 0.0018311,
        )
    state.note_annotation = SimpleNamespace(
        Owner=state.front, OwnerType=0, Visible=1, IsDangling=lambda: False,
        GetLeaderCount=lambda: 1, GetLeaderStyle=lambda: 1 | 0x800,  # Native swSTRAIGHT + nearest attachment.
        GetAttachedEntityCount3=lambda: 1, GetAttachedEntityTypes=lambda: (1,),
        GetAttachedEntities3=lambda: (state.top,),
        GetLeaderPointsAtIndex=lambda _index: (*leader_start(), 0.0, *state.landing, 0.0),
        GetPosition=lambda: tuple(state.note_position), GetTextFormatCount=lambda: 1,
        GetTextFormat=lambda _index: copy.deepcopy(state.note_format),
        GetUseDocTextFormat=lambda _index: state.note_uses_doc_font,
    )
    def set_format(_index, _use_doc, native):
        if state.wrap_fault == "refused":
            return False
        if state.wrap_fault != "ignored":
            state.note_format = copy.deepcopy(native)
            state.note_uses_doc_font = False
        if state.wrap_fault == "font_shrink":
            state.note_format.CharHeight /= 2
        return True
    state.note_annotation.SetTextFormat = set_format
    def position_note(x, y, z):
        if state.wrap_fault != "ignored_position":
            state.note_position[:] = (x, y, z)
        return True
    state.note_annotation.SetPosition2 = position_note
    def note_record():
        rows = note_rows()
        box = drawing.display_box({"texts": rows})
        start = state.note_start_override or (box.xmax + 0.0008113, state.note_position[1] - 0.0017283)
        dx, dy = start[0] - state.landing[0], start[1] - state.landing[1]
        length = math.hypot(dx, dy)
        arrow = [*state.landing, 0.0, dx / length, dy / length, 0.0,
                 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0]
        # The real collector rounds registered leaders independently of the
        # display primitives. The native point getter above remains unrounded.
        return dict(
            type=6, name="Purchased note", visible=1, owner_type=0,
            leaders=[[round(float(value), 7) for value in state.note_annotation.GetLeaderPointsAtIndex(0)]],
            display=dict(
                texts=rows, lines=[] if state.note_ink_missing else [_native_line(start, state.landing)],
                arrows=[] if state.note_ink_missing else [list(arrow) for _ in range(state.note_arrow_count)],
            ),
        )
    state.note_annotation.paper_record = note_record
    def note_display_data():
        # Native doubles are independent of the audit dump's serialization.
        display = state.note_annotation.paper_record()["display"]
        return SimpleNamespace(
            GetArrowHeadCount=lambda: len(display.get("arrows") or ()),
            GetArrowHeadAtIndex2=lambda index: display["arrows"][index],
            GetLineCount=lambda: len(display.get("lines") or ()),
            GetLineAtIndex2=lambda index: display["lines"][index],
        )
    state.note_annotation.GetDisplayData = note_display_data
    state.note = SimpleNamespace(
        GetAnnotation=lambda: state.note_annotation, GetText=lambda: state.note_text,
        PropertyLinkedText=drawing.property_link("Purchased Screw Note"),
    )
    state.foreign_annotations = [
        state.diameter_annotation, state.shoulder_annotation, state.shoulder_length_annotation,
    ]
    state.front.GetAnnotations = lambda: (state.annotation, state.note_annotation, *state.foreign_annotations)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    state.note_check, state.note_frame = drawing._place_purchased_note(
        state.adapter, state.front, state.note, state.paper_displays,
    )
    tail, major, tail_record, major_record, _original_text = _tail_paper_boundary(monkeypatch, state)
    _tail_check, tail_frame = drawing._move_tail_column(state.adapter, tail, major)
    state.tail_annotation, state.tail_record = tail, tail_record
    state.major_annotation, state.major_record = major, major_record
    native_members = dict(
        SupplierHeadDiameter=(state.diameter_annotation, screw.HEAD_DIA, "RD1@FinishedFront@pivot.SLDDRW"),
        SupplierThreadMajor=(major, screw.THREAD_MAJOR, "SupplierThreadMajor@SupplierReference@pivot.SLDPRT"),
    )
    def decorate(annotation, name, native, display):
        annotation.Owner, annotation.OwnerType, annotation.Visible = state.front, 0, 1
        annotation.GetSpecificAnnotation = lambda: display
        annotation.IsDangling = lambda: False
        annotation.GetName = lambda: name
        annotation.GetType = lambda: 4
        annotation.GetAttachedEntityCount3 = lambda: 2
        annotation.GetAttachedEntities3 = lambda: (state.bearing, state.top)
        annotation.GetAttachedEntityTypes = lambda: (1, 1)
        display.GetAnnotation = lambda: annotation
        display.GetDimension2 = lambda _index: native
        display.GetNameForSelection = lambda: name
        state.front.dimensions.append(display)
    for name, (annotation, value, full_name) in native_members.items():
        presentation = screw.SUPPLIER_REFERENCE_DIMENSIONS[name]
        native = SimpleNamespace(
            FullName=full_name, SystemValue=value / 1000, Tolerance=SimpleNamespace(Type=0),
        )
        texts = {1: "(<MOD-DIAM>", 2: " in)", 4: presentation.get("callout", "")}
        display = SimpleNamespace(
            Type2=2, ShowDimensionValue=True, ShowParenthesis=False,
            GetUseDocUnits=lambda: False, GetUnits=lambda: 3,
            GetPrimaryPrecision2=lambda p=presentation: p["precision"],
            GetFractionBase=lambda: 1, GetOverride=lambda: False,
            GetText=lambda index, texts=texts: texts[index],
        )
        decorate(annotation, name, native, display)
    tail_display = tail.GetSpecificAnnotation()
    native = tail_display.GetDimension2(0)
    tail_display.GetPrimaryPrecision2 = lambda: drawing.DIMENSION_PRECISION["ThreadLengthMin"]
    tail_display.GetText = lambda _index: ""
    decorate(tail, "ThreadLengthMin", native, tail_display)
    import _stock_trim_drawing as controls
    monkeypatch.setattr(controls, "_early_bound", lambda value, _kind: value)
    state.note_annotation.GetType = lambda: 6
    state.note_annotation.GetName = lambda: "Saved purchased note"
    state.note_annotation.GetSpecificAnnotation = lambda: state.note
    state.annotation.GetType = lambda: 4
    state.socket_annotation.GetType = lambda: 4
    state.mark_annotation.GetType = lambda: 13
    state.front.GetAnnotations = lambda: (
        state.annotation, state.note_annotation, tail, major, *state.foreign_annotations,
    )
    for view in (state.paper_iso, state.stock.view, *state.sheets.values()):
        view.GetAnnotations = lambda: ()
    state.paper = dict(
        names={name: row[2] for name, row in native_members.items()},
        note=state.note_annotation.GetName(), tail=tail_frame, wrap=state.note_frame, text=state.note_text,
    )
    state.paper["names"]["ThreadLengthMin"] = native.FullName
    return state


@pytest.mark.parametrize("phase", ("settled", "saved"))
def test_paper_and_saved_source_geometry_use_real_sized_projection_contract(
    monkeypatch, tmp_path, phase,
):
    import _drawing_projection as projection

    state = _saved_physical_fixture(monkeypatch, tmp_path)
    utility = object()
    def invoke(obj, interface, member, *args):
        # Fake only the raw COM math boundary. The real projection helpers
        # retain their len/index/iteration contract and source-point math.
        if (interface, member) == ("ISldWorks", "GetMathUtility"):
            return utility
        if (interface, member) == ("IView", "ModelToViewTransform"):
            return obj
        if (interface, member) == ("IMathUtility", "CreatePoint"):
            return args[0]
        if (interface, member) == ("IMathPoint", "MultiplyTransform"):
            view = args[0]
            origin = tuple(a + b for a, b in zip(view.Position, view.origin_offset, strict=True))
            return (
                origin[0] + 4 * obj[0],
                origin[1] + (-4 * obj[2] if view is state.paper_top else 4 * obj[1]),
                0.0,
            )
        if (interface, member) == ("IMathPoint", "ArrayData"):
            return obj
        raise AssertionError(f"unexpected projection math boundary: {interface}.{member}")
    monkeypatch.setattr(projection, "_com_invoke", invoke)
    monkeypatch.setattr(projection, "double_array", lambda values: tuple(values))
    monkeypatch.setattr(drawing, "model_points_in_view", projection.model_points_in_view)
    monkeypatch.setattr(drawing, "model_point_in_view", projection.model_point_in_view)
    if phase == "saved":
        drawing._assert_saved_physical_references(
            state.adapter, state.identities, state.configurations,
            serialized_full_names=state.serialized_full_names,
            serialized_shelf_names=state.serialized_shelf_names, paper=state.paper,
        )
    else:
        state.adapter.currentModel = state.saved
        state.note_check()
        drawing._assert_paper_layout(
            state.adapter, state.front, state.paper_top, state.paper_iso, state.note,
            state.paper_displays, purchased_text=state.note_text,
        )


@pytest.mark.parametrize("fault", (
    "none", "foreign_line", "fraction_foreign_line", "qualifier_foreign_line",
    "note_width", "note_property", "note_attachment", "note_landing", "head_trim",
    "head_shelf_late", "socket_shelf_late", "socket_line", "leader_into_head",
    "leader_into_top", "missing_published_leader", "arrow_landing",
))
def test_actual_complete_native_paper_boundaries_refuse_late_drift(monkeypatch, tmp_path, fault):
    state = _finished_paper_fixture(monkeypatch, tmp_path)
    expected = state.note_text
    if fault in ("foreign_line", "fraction_foreign_line", "qualifier_foreign_line"):
        note_box = drawing.display_box({"texts": state.note_annotation.paper_record()["display"]["texts"]})
        middle_y = (note_box.ymin + note_box.ymax) / 2
        location = {
            "foreign_line": ((note_box.xmin, middle_y), (note_box.xmax, middle_y)),
            "fraction_foreign_line": ((0.176, 0.237), (0.180, 0.237)),
            "qualifier_foreign_line": ((0.162, 0.229), (0.195, 0.229)),
        }[fault]
        state.foreign_annotations.append(SimpleNamespace(paper_record=dict(
            type=13, display=dict(lines=[_native_line(*location)]),
        )))
    elif fault == "note_width":
        old_record = state.note_annotation.paper_record
        def too_wide():
            record = old_record()
            record["display"]["texts"][0]["w"] += 0.100
            return record
        state.note_annotation.paper_record = too_wide
    elif fault == "note_property":
        state.note.PropertyLinkedText = "free text"
    elif fault == "note_attachment":
        state.note_annotation.GetAttachedEntities3 = lambda: (state.bearing,)
    elif fault == "note_landing":
        state.landing = (state.landing[0] + 0.0001, state.landing[1])
    elif fault == "head_trim":
        state.top.nearest = (*drawing._head_height_points()[1], 0.0)
    elif fault == "head_shelf_late":
        state.head_record["display"]["texts"][1]["pos"][1] -= 0.003
    elif fault == "socket_shelf_late":
        state.socket_record["display"]["texts"][2]["pos"][0] = 0.150
    elif fault == "socket_line":
        for row in state.socket_record["display"]["arrows"]:
            row[1] = 0.212
    elif fault == "leader_into_head":
        state.note_start_override = (0.135, 0.195)
    elif fault == "leader_into_top":
        state.note_start_override = (0.140, 0.250)
    elif fault == "missing_published_leader":
        state.note_ink_missing = True
    elif fault == "arrow_landing":
        state.landing = (0.147, 0.20216)

    def prove():
        state.note_check()
        drawing._assert_paper_layout(
            state.adapter, state.front, state.paper_top, state.paper_iso,
            state.note, state.paper_displays, purchased_text=expected,
        )
    if fault == "none":
        prove()
        assert state.landing == pytest.approx((
            0.140 - drawing._HEAD_TOP_R * 4 / 1000,
            0.186285 + screw.HEAD_H * 4 / 1000,
        ))
    else:
        with pytest.raises(RuntimeError):
            prove()


@pytest.mark.parametrize("fault", (
    "none", "refused", "ignored", "unwrapped", "font_shrink", "ignored_position",
))
def test_native_note_wrapping_measures_full_ink_and_preserves_linked_text(monkeypatch, tmp_path, fault):
    state = _finished_paper_fixture(monkeypatch, tmp_path)
    original = state.note.GetText()
    original_link = state.note.PropertyLinkedText
    state.note_position[:] = (*drawing.PURCHASED_NOTE_XY, 0.0)
    state.note_format.LineLength = 0.0
    state.note_uses_doc_font = True
    state.wrap_fault = fault
    def place():
        check, frame = drawing._place_purchased_note(
            state.adapter, state.front, state.note, state.paper_displays,
        )
        check()
        drawing._assert_paper_layout(
            state.adapter, state.front, state.paper_top, state.paper_iso, state.note,
            state.paper_displays, purchased_text=original,
        )
        return frame
    if fault == "none":
        frame = place()
        assert state.note_format.LineLength == pytest.approx(frame["line_length"])
        actual = state.note_annotation.paper_record()["display"]["texts"]
        box = drawing.display_box({"texts": actual})
        assert box.xmin >= drawing._finished_border(state.adapter).xmin + 0.002
        assert box.xmax < state.front.GetOutline()[0] - 0.002
        length = state.shoulder_length_annotation.paper_record
        full_length = drawing.annotation_geometry(
            length, owner="SupplierShoulderLength", advance=drawing.calibrate_sheet_advance((length,)),
        ).box()
        assert box.ymin > full_length.ymax + 0.002
        assert " ".join(row["t"] for row in actual) == original
    else:
        with pytest.raises(RuntimeError, match="Purchased Screw Note"):
            place()
    assert state.note.GetText() == original
    assert state.note.PropertyLinkedText == original_link


def test_native_left_wrap_refuses_actual_shoulder_outside_stub_without_trying_another_route(
    monkeypatch, tmp_path,
):
    state = _finished_paper_fixture(monkeypatch, tmp_path)
    # c356 has no upward stub. A real late native style change must be read,
    # not ignored to retain the earlier clear-field placement.
    state.shoulder_length_annotation.paper_record["display"]["lines"].append(
        _native_line((0.065, 0.186285), (0.065, 0.192635)),
    )
    with pytest.raises(RuntimeError, match="cannot fit/place complete native left wrapped text"):
        drawing._place_purchased_note(
            state.adapter, state.front, state.note, state.paper_displays,
        )


@pytest.mark.parametrize("phase", ("settled", "saved"))
@pytest.mark.parametrize("fault", (
    "width", "font", "doc_format", "missing_fragment", "line_missing", "foreign_height_line",
    "shoulder_witness", "shoulder_words",
))
def test_wrapped_note_refuses_actual_width_font_fragment_and_foreign_line_drift(
    monkeypatch, tmp_path, phase, fault,
):
    state = _finished_paper_fixture(monkeypatch, tmp_path)
    if fault == "width":
        state.note_format.LineLength += 0.001
    elif fault == "font":
        state.note_format.WidthFactor = 0.8
    elif fault == "doc_format":
        state.note_uses_doc_font = True
    elif fault in ("missing_fragment", "line_missing"):
        original_record = state.note_annotation.paper_record
        def incomplete():
            record = original_record()
            if fault == "missing_fragment":
                record["display"]["texts"].pop()
            else:
                record["display"]["lines"].clear()
            return record
        state.note_annotation.paper_record = incomplete
    elif fault in ("shoulder_witness", "shoulder_words"):
        text = drawing.display_box({"texts": state.note_annotation.paper_record()["display"]["texts"]})
        length = state.shoulder_length_annotation.paper_record["display"]
        if fault == "shoulder_witness":
            length["lines"][1] = _native_line(
                (0.148525, text.ymin + 0.001), (0.064, text.ymin + 0.001),
            )
        else:
            length["texts"][-1]["pos"][1] = text.ymin + 0.001
    else:
        box = drawing.display_box(state.note_annotation.paper_record()["display"])
        x = (box.xmin + box.xmax) / 2
        state.foreign_annotations.append(SimpleNamespace(
            GetType=lambda: 13, paper_record=dict(
                type=13, display=dict(lines=[_native_line((x, box.ymin), (x, box.ymax))]),
            ),
        ))
    with pytest.raises(RuntimeError):
        if phase == "saved":
            drawing._assert_saved_physical_references(
                state.adapter, state.identities, state.configurations,
                serialized_full_names=state.serialized_full_names,
                serialized_shelf_names=state.serialized_shelf_names, paper=state.paper,
            )
        else:
            state.note_check()
            drawing._assert_paper_layout(
                state.adapter, state.front, state.paper_top, state.paper_iso, state.note,
                state.paper_displays, purchased_text=state.note_text,
            )
    if phase == "saved":
        assert state.closes == [state.path.name]


def test_socket_whole_fraction_moves_only_text_beyond_source_body(monkeypatch, tmp_path):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.adapter.currentModel = state.saved
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    for row in state.socket_record["display"]["texts"]:
        row["pos"][0] -= 0.010
    position = [0.140, 0.235, 0.0]
    state.socket_annotation.GetPosition = lambda: tuple(position)
    def set_position(x, y, z):
        delta = x - position[0]
        position[:] = (x, y, z)
        for row in state.socket_record["display"]["texts"]:
            row["pos"][0] += delta
        for row in state.socket_record["display"]["lines"][-1:]:
            row[4] += delta
            row[7] += delta
        return True
    state.socket_annotation.SetPosition2 = set_position
    before = drawing.measure_reference_text(state.adapter, state.socket_display, axis=0, label="Socket")
    drawing._clear_socket_text(state.adapter, state.paper_top, state.socket_display)
    after = drawing.measure_reference_text(state.adapter, state.socket_display, axis=0, label="Socket")
    assert after["text"].xmin == pytest.approx(0.158075)
    assert after["tips"] == before["tips"] and after["witnesses"] == before["witnesses"]
    assert position[1:] == [0.235, 0.0]
    # An ignored native text setter is a refusal, not a nominal placement.
    state.socket_record["display"]["texts"][2]["pos"][0] = 0.154
    state.socket_annotation.SetPosition2 = lambda *_args: True
    with pytest.raises(RuntimeError, match="clearance"):
        drawing._clear_socket_text(state.adapter, state.paper_top, state.socket_display)


def test_serialized_shelf_capture_refuses_head_identity_time_drift(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError, match="identity"):
        _record_drawing_build(monkeypatch, tmp_path, capture_fault="shelf_head_drift")


@pytest.mark.parametrize("fault", ("none", "ignored_column", "late_station", "late_text",
                                  "late_major_extent", "late_crossing"))
def test_tail_column_move_uses_complete_major_ink_and_preserves_acceptance_text(
    monkeypatch, tmp_path, fault,
):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.adapter.currentModel = state.saved
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    tail, major, tail_record, major_record, original_text = _tail_paper_boundary(monkeypatch, state, fault=fault)
    if fault == "ignored_column":
        with pytest.raises(RuntimeError, match="stations/column"):
            drawing._move_tail_column(state.adapter, tail, major)
        return
    settled, _frame = drawing._move_tail_column(state.adapter, tail, major)
    assert [row[0] for row in tail_record["display"]["arrows"]] == pytest.approx([0.2766024] * 2)
    assert tail.GetSpecificAnnotation().ArrowSide == drawing._DIM_ARROWS_INSIDE
    for actual, original in zip(tail_record["display"]["texts"], original_text, strict=True):
        assert actual["t"] == original["t"]
        assert actual["pos"] == pytest.approx(original["pos"], abs=1e-12)
    if fault == "late_station":
        tail_record["display"]["arrows"][0][1] += 0.0001
    elif fault == "late_text":
        tail_record["display"]["texts"][0]["pos"][0] += 0.0003
    elif fault == "late_major_extent":
        major_record["display"]["texts"][0]["w"] += 0.001
    elif fault == "late_crossing":
        tail_record["display"]["lines"].append(
            _native_line((0.200, 0.100), (0.200, 0.120)),
        )
    if fault == "none":
        settled()
    else:
        with pytest.raises(RuntimeError):
            settled()


@pytest.mark.parametrize("fault", (
    "none", "nonuniform_offset", "offset_size", "offset_angle", "offset_wording",
    "ignored_restore", "refused_restore",
))
def test_tail_offset_restores_measured_native_ink_not_the_dimension_line_anchor(
    monkeypatch, tmp_path, fault,
):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.adapter.currentModel = state.saved
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    tail, major, record, _major_record, original_text = _tail_paper_boundary(
        monkeypatch, state, fault=fault,
    )
    display = tail.GetSpecificAnnotation()
    line_anchor = tail.GetPosition()
    assert line_anchor != tuple(original_text[0]["pos"])
    original_stations = tuple(tuple(row[:3]) for row in record["display"]["arrows"])
    if fault == "none":
        settled, _frame = drawing._move_tail_column(state.adapter, tail, major)
        assert display.OffsetText is True
        assert tail.GetPosition() == pytest.approx(original_text[0]["pos"], abs=1e-12)
        for old, actual in zip(original_stations, record["display"]["arrows"], strict=True):
            assert actual[0] == pytest.approx(0.2766024, abs=1e-12)
            assert tuple(actual[1:3]) == old[1:3]
        for old, actual in zip(original_text, record["display"]["texts"], strict=True):
            assert actual["t"] == old["t"]
            assert actual["pos"] == pytest.approx(old["pos"], abs=1e-12)
            assert (actual["w"], actual["h"], actual["ang"]) == (old["w"], old["h"], old["ang"])
        settled()
        return
    reason = (
        "cannot restore measured acceptance ink" if fault == "refused_restore"
        else "complete acceptance text moved" if fault == "ignored_restore"
        else "not one congruent native text translation"
    )
    with pytest.raises(RuntimeError, match=reason) as refusal:
        drawing._move_tail_column(state.adapter, tail, major)
    assert isinstance(refusal.value.__cause__, RuntimeError)
    if fault not in ("ignored_restore", "refused_restore"):
        # Do not "repair" a changed fraction, size, angle or independent row.
        assert tail.GetPosition() == pytest.approx(line_anchor, abs=1e-12)
    evidence = next(
        fields for name, fields in state.events
        if name == "drawing.pivot_tail_layout_refusal"
    )
    assert evidence["original"]["full_name"] == evidence["current"]["full_name"]
    assert evidence["current"]["full_name"] == display.GetDimension2(0).FullName
    assert evidence["original"]["offset_text"] is False
    assert evidence["current"]["offset_text"] is True
    assert evidence["original"]["arrow_stations"] == tuple(row[:2] for row in original_stations)
    assert all(abs(tip[0] - 0.2766024) < 1e-12 for tip in evidence["current"]["arrow_stations"])
    assert tuple(
        row["text"] for row in evidence["original"]["text_fragments"]
    ) == tuple(row["t"] for row in original_text)
    assert evidence["current"]["text_fragments"]
    assert "native_snapshot=" in str(refusal.value)


def test_native_note_primitive_read_errors_cannot_be_masked_by_complete_text(monkeypatch, tmp_path):
    state = _finished_paper_fixture(monkeypatch, tmp_path)
    original_dump = drawing._dump_annotation
    def refused_display(reader, annotation):
        reader._count("GetPolyLineAtIndex")
        return original_dump(reader, annotation)
    monkeypatch.setattr(drawing, "_dump_annotation", refused_display)
    with pytest.raises(RuntimeError, match="GetPolyLineAtIndex"):
        state.note_check()


def _tail_paper_boundary(monkeypatch, state, *, fault="none"):
    major_record = _native_reference_record(
        "Thread major", 0, ((0.1316688, 0.1106389), (0.1483312, 0.1106389)),
        ((0.1316688, 0.096), (0.1483312, 0.096)),
        [_native_text("(0.164 in)", 0.2095976, 0.1218049, 0.0588048),
         _native_text("THREAD MAJOR", 0.2095976, 0.1106389, 0.0588048)],
    )
    major_record["display"]["lines"].append(
        _native_line((0.1483312, 0.1106389), (0.2684024, 0.1106389)),
    )
    major = SimpleNamespace(paper_record=major_record)
    tail_record = _native_reference_record(
        "ThreadLengthMin", 1, ((0.180, 0.098885), (0.180, 0.127085)),
        ((0.1493312, 0.098885), (0.1493312, 0.127085)),
        [_native_text("0.278 in MIN", 0.180, 0.1465, 0.069),
         _native_text("MIN FINISHED THREAD LENGTH", 0.180, 0.13145, 0.0982187)],
    )
    original_text = copy.deepcopy(tail_record["display"]["texts"])
    tail = SimpleNamespace(paper_record=tail_record, Owner=state.front, OwnerType=0)
    nominal, lower, upper = drawing.EXPECTED_CONTROLS["ThreadLengthMin"]
    native = SimpleNamespace(
        Name="ThreadLengthMin",
        FullName="ThreadLengthMin@ThreadTailAcceptance@pivot.SLDPRT", SystemValue=nominal, DrivenState=2,
        Tolerance=SimpleNamespace(
            Type=drawing.DIMENSION_TOLERANCE_TYPES["ThreadLengthMin"],
            GetMinValue=lambda: lower, GetMaxValue=lambda: upper,
        ),
    )
    display = SimpleNamespace(
        GetAnnotation=lambda: tail, OffsetText=False, Type2=2, GetDimension2=lambda _index: native,
    )
    tail.GetSpecificAnnotation = lambda: display
    line_position = [0.180, 0.1425625, 0.0]
    # Actual ink insertion is not the OffsetText=False dimension-line anchor.
    text_position = [*original_text[0]["pos"]]
    tail.GetPosition = lambda: tuple(text_position if display.OffsetText else line_position)
    text_writes = 0

    def move(x, y, z):
        nonlocal text_writes
        if display.OffsetText:
            text_writes += 1
            if text_writes > 1 and fault in ("ignored_restore", "refused_restore"):
                return fault == "ignored_restore"
            dx, dy = x - text_position[0], y - text_position[1]
        else:
            if fault == "ignored_column":
                return True
            old_column = tail_record["display"]["arrows"][0][0]
            for row in tail_record["display"]["arrows"]:
                row[0] = x
            for row in tail_record["display"]["lines"]:
                if abs(row[4] - old_column) < 1e-8 and abs(row[7] - old_column) < 1e-8:
                    row[4] = row[7] = x
                elif abs(row[7] - old_column - 0.001) < 1e-8:
                    row[7] = x + 0.001
            dx, dy = x - line_position[0], y - line_position[1]
            line_position[:] = (x, y, z)
        for row in tail_record["display"]["texts"]:
            row["pos"][0] += dx
            row["pos"][1] += dy
        text_position[:] = (text_position[0] + dx, text_position[1] + dy, z)
        return True

    tail.SetPosition2 = move

    def offset(_adapter, annotations, targets):
        assert tuple(annotations) == (tail,)
        assert targets["ThreadLengthMin"] == (0.180, 0.1425625)
        display.OffsetText = True
        target = targets["ThreadLengthMin"]
        assert tail.SetPosition2(target[0], target[1], 0.0)
        row = tail_record["display"]["texts"][0]
        if fault == "nonuniform_offset":
            row["pos"][0] += 0.0004
        elif fault == "offset_size":
            row["w"] += 0.0004
        elif fault == "offset_angle":
            row["ang"] += 0.0001
        elif fault == "offset_wording":
            row["t"] = "0.278 in"

    monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    return tail, major, tail_record, major_record, original_text


@pytest.mark.parametrize("fault", (
    "none", "note_name", "note_property", "note_landing", "note_leader_lost",
    "note_ink_unpublished", "note_owner", "note_duplicate", "tail_identity",
    "tail_column", "tail_text", "tail_nominal", "tail_band", "major_identity", "major_extent",
))
def test_cold_saved_note_and_tail_replay_exact_identity_and_actual_paper(monkeypatch, tmp_path, fault):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    if fault == "note_name":
        state.paper["note"] += " stale"
    elif fault == "note_property":
        state.note.PropertyLinkedText = "free text"
    elif fault == "note_landing":
        state.landing = (state.landing[0] + 0.0001, state.landing[1])
    elif fault == "note_leader_lost":
        state.note_annotation.GetLeaderCount = lambda: 0
    elif fault == "note_ink_unpublished":
        state.note_ink_missing = True
    elif fault == "note_owner":
        state.note_annotation.Owner = state.paper_top
    elif fault == "note_duplicate":
        state.paper_iso.GetAnnotations = lambda: (state.note_annotation,)
    elif fault == "tail_identity":
        state.paper["names"]["ThreadLengthMin"] += " stale"
    elif fault == "tail_column":
        state.tail_record["display"]["arrows"][0][0] += 0.001
    elif fault == "tail_text":
        state.tail_record["display"]["texts"][0]["pos"][0] += 0.001
    elif fault == "tail_nominal":
        state.tail_annotation.GetSpecificAnnotation().GetDimension2(0).SystemValue += 0.001
    elif fault == "tail_band":
        state.tail_annotation.GetSpecificAnnotation().GetDimension2(0).Tolerance.Type = 0
    elif fault == "major_identity":
        state.paper["names"]["SupplierThreadMajor"] += " stale"
    elif fault == "major_extent":
        state.major_record["display"]["texts"][0]["w"] += 0.001
    def prove():
        drawing._assert_saved_physical_references(
            state.adapter, state.identities, state.configurations,
            serialized_full_names=state.serialized_full_names,
            serialized_shelf_names=state.serialized_shelf_names, paper=state.paper,
        )
    if fault == "none":
        prove()
    else:
        with pytest.raises(RuntimeError):
            prove()
    assert state.closes == [state.path.name]
    assert state.adapter.currentModel is state.previous
    assert not state.selection.calls and not state.additions


def test_finite_top_mark_accepts_actual_native_depth_but_not_inconsistent_endpoints(monkeypatch, tmp_path):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.adapter.currentModel = state.saved
    state.mark_override = copy.deepcopy(state.mark_lines())
    for row in state.mark_override:
        row[6] = row[9] = 0.036285
    drawing._assert_top_mark(state.adapter, state.paper_top)
    state.mark_override[0][9] += 0.0001
    with pytest.raises(RuntimeError, match="depth"):
        drawing._assert_top_mark(state.adapter, state.paper_top)


def test_cold_tail_cannot_keep_box_but_drop_native_minimum_acceptance_wording(monkeypatch, tmp_path):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.tail_record["display"]["texts"][0]["t"] = "0.278 in"
    with pytest.raises(RuntimeError, match="wording"):
        drawing._assert_saved_physical_references(
            state.adapter, state.identities, state.configurations,
            serialized_full_names=state.serialized_full_names,
            serialized_shelf_names=state.serialized_shelf_names, paper=state.paper,
        )
    assert state.closes == [state.path.name]
    assert state.adapter.currentModel is state.previous


@pytest.mark.parametrize("phase", ("settled", "saved"))
def test_complete_native_note_ink_still_refuses_actual_head_body_intrusion(
    monkeypatch, tmp_path, phase,
):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    inside = drawing.model_points_in_view(
        state.adapter, state.front,
        [(-0.000125, screw.HEAD_H / 2000, 0.0), (0.000125, screw.HEAD_H / 2000, 0.0)],
        label="actual source head interior negative",
    )
    original_record = state.note_annotation.paper_record
    def inside_stroke():
        record = original_record()
        record["display"]["lines"].append(_native_line(*inside))
        return record
    state.note_annotation.paper_record = inside_stroke
    with pytest.raises(RuntimeError, match="actual leader enters projected head/Top body"):
        if phase == "saved":
            drawing._assert_saved_physical_references(
                state.adapter, state.identities, state.configurations,
                serialized_full_names=state.serialized_full_names,
                serialized_shelf_names=state.serialized_shelf_names, paper=state.paper,
            )
        else:
            state.adapter.currentModel = state.saved
            state.note_check()
            drawing._assert_paper_layout(
                state.adapter, state.front, state.paper_top, state.paper_iso, state.note,
                state.paper_displays, purchased_text=state.note_text,
            )


@pytest.mark.parametrize("phase", ("settled", "saved"))
@pytest.mark.parametrize("fault", ("none", "native_arrow_tip", "native_line_tip", "native_registered_tip"))
def test_native_note_precision_cannot_be_replaced_by_rounded_paper(
    monkeypatch, tmp_path, phase, fault,
):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    if fault == "none":
        # Actual 59cfa710b native origin, not its seven-decimal audit value.
        delta = 0.186285034189251 - 0.186285
        state.front.origin_offset = (
            state.front.origin_offset[0], state.front.origin_offset[1] + delta,
        )
        for index, arrow in enumerate(state.arrows):
            state.arrows[index] = (arrow[0], arrow[1] + delta, *arrow[2:])
        for row in state.head_record["display"]["arrows"]:
            row[1] += delta
        for row in state.head_record["display"]["lines"]:
            row[5] += delta
            row[8] += delta
        for row in state.head_record["display"]["texts"]:
            row["pos"][1] += delta
        state.landing = drawing._purchased_head_target(state.adapter, state.front)[1]
        state.adapter.currentModel = state.saved
        state.note_check, state.note_frame = drawing._place_purchased_note(
            state.adapter, state.front, state.note, state.paper_displays,
        )
        state.paper["wrap"] = state.note_frame
        state.adapter.currentModel = state.previous
    elif fault == "native_registered_tip":
        original_points = state.note_annotation.GetLeaderPointsAtIndex
        def wrong_native_registered_tip(index):
            points = list(original_points(index))
            points[4] += 2e-8
            return points
        state.note_annotation.GetLeaderPointsAtIndex = wrong_native_registered_tip
    else:
        original_record = state.note_annotation.paper_record
        def wrong_native_tip():
            record = original_record()
            if fault == "native_arrow_tip":
                record["display"]["arrows"][0][1] += 2e-8
            else:
                record["display"]["lines"][0][8] += 2e-8
            return record
        state.note_annotation.paper_record = wrong_native_tip
    original_dump = drawing._dump_annotation
    def rounded_dump(reader, annotation):
        record = original_dump(reader, annotation)
        if annotation is state.note_annotation:
            for kind in ("arrows", "lines"):
                record["display"][kind] = [
                    [round(float(value), 7) for value in row]
                    for row in record["display"].get(kind) or ()
                ]
        return record
    monkeypatch.setattr(drawing, "_dump_annotation", rounded_dump)
    # Independent source dimensions and the actual native origin, not the
    # recipe's target helper or the rounded leader's own coordinates.
    expected = (
        0.140 - (screw.HEAD_DIA / 2 - screw.HEAD_CHAMFER) * 4 / 1000,
        (0.186285034189251 if fault == "none" else 0.186285) + screw.HEAD_H * 4 / 1000,
    )
    reported = drawing._paper_annotation(
        state.adapter, state.note_annotation, label="Purchased Screw Note",
    )
    reported_errors = (
        math.dist(reported["display"]["arrows"][0][:2], expected),
        math.dist(reported["display"]["lines"][0][7:9], expected),
        math.dist(reported["leaders"][0][3:5], expected),
    )
    if fault == "none":
        assert all(error > 1e-8 for error in reported_errors)
    else:
        assert all(error <= 1e-8 for error in reported_errors)
    def verify():
        if phase == "saved":
            drawing._assert_saved_physical_references(
                state.adapter, state.identities, state.configurations,
                serialized_full_names=state.serialized_full_names,
                serialized_shelf_names=state.serialized_shelf_names, paper=state.paper,
            )
        else:
            state.adapter.currentModel = state.saved
            state.note_check()
            drawing._assert_paper_layout(
                state.adapter, state.front, state.paper_top, state.paper_iso, state.note,
                state.paper_displays, purchased_text=state.note_text,
            )
    if fault == "none":
        verify()
    else:
        with pytest.raises(RuntimeError):
            verify()


@pytest.mark.parametrize("phase", ("settled", "saved"))
@pytest.mark.parametrize("fault", (
    "display_null", "arrow_count_null", "arrow_count_fractional", "arrow_count_boolean",
    "arrow_count_mismatch", "line_count_zero", "line_count_mismatch",
    "arrow_null", "line_null", "line_short", "line_long", "line_nonfinite",
    "arrow_read_error", "line_read_error",
))
def test_note_native_primitive_read_failures_cannot_hide_behind_complete_report(
    monkeypatch, tmp_path, phase, fault,
):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    original_data = state.note_annotation.GetDisplayData
    def bad_data():
        data = original_data()
        if fault == "display_null":
            return None
        if fault.startswith("arrow_count"):
            value = {
                "arrow_count_null": None, "arrow_count_fractional": 1.5,
                "arrow_count_boolean": True, "arrow_count_mismatch": 2,
            }[fault]
            data.GetArrowHeadCount = lambda: value
        elif fault in ("line_count_zero", "line_count_mismatch"):
            data.GetLineCount = lambda: 0 if fault == "line_count_zero" else 2
        elif fault == "arrow_null":
            data.GetArrowHeadAtIndex2 = lambda _index: None
        elif fault == "line_null":
            data.GetLineAtIndex2 = lambda _index: None
        elif fault in ("line_short", "line_long", "line_nonfinite"):
            original_line = data.GetLineAtIndex2
            def bad_line(index):
                line = list(original_line(index))
                if fault == "line_short":
                    line.pop()
                elif fault == "line_long":
                    line.append(0.0)
                else:
                    line[5] = math.nan
                return line
            data.GetLineAtIndex2 = bad_line
        else:
            def refuse(_index):
                raise RuntimeError("native primitive read refused")
            if fault == "arrow_read_error":
                data.GetArrowHeadAtIndex2 = refuse
            else:
                data.GetLineAtIndex2 = refuse
        return data
    state.note_annotation.GetDisplayData = bad_data
    with pytest.raises(RuntimeError):
        if phase == "saved":
            drawing._assert_saved_physical_references(
                state.adapter, state.identities, state.configurations,
                serialized_full_names=state.serialized_full_names,
                serialized_shelf_names=state.serialized_shelf_names, paper=state.paper,
            )
        else:
            state.note_check()


@pytest.mark.parametrize("phase", ("settled", "saved"))
@pytest.mark.parametrize("style,accepted", (
    (1, True),
    (1 | 0x100, True),
    (1 | 0x200, True),
    (1 | 0x400, True),
    (1 | 0x800, True),
    (0, False),
    (2, False),
    (3, False),
    (4, False),
    (5, False),
    (8, False),
    (9, False),
    (0x800, False),
    (0x800 | 2, False),
    (0x800 | 3, False),
    (0x800 | 4, False),
    (0x800 | 8, False),
    (1 | 0x100 | 0x200, False),
    (1 | 0x100 | 0x800, False),
    (1 | 0x10, False),
    (1 | 0x1000, False),
    (-1, False),
))
def test_straight_note_decodes_only_documented_single_attachment_mode(
    monkeypatch, tmp_path, phase, style, accepted,
):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    state.note_annotation.GetLeaderStyle = lambda: style
    def verify():
        if phase == "saved":
            drawing._assert_saved_physical_references(
                state.adapter, state.identities, state.configurations,
                serialized_full_names=state.serialized_full_names,
                serialized_shelf_names=state.serialized_shelf_names, paper=state.paper,
            )
        else:
            state.adapter.currentModel = state.saved
            state.note_check()
            drawing._assert_paper_layout(
                state.adapter, state.front, state.paper_top, state.paper_iso, state.note,
                state.paper_displays, purchased_text=state.note_text,
            )
    if accepted:
        verify()
    else:
        with pytest.raises(RuntimeError, match="actual straight leader/arrow/landing changed"):
            verify()


@pytest.mark.parametrize("fault", (
    "attachment_count", "attachment_type", "dangling", "bent_leader", "arrow_count",
    "leader_hidden", "leader_multiple", "leader_points_short", "leader_points_long",
    "leader_nonfinite", "leader_landing_drift", "leader_zero_length",
    "short_arrow", "long_arrow", "nonfinite_arrow", "arrow_landing_drift",
    "zero_arrow_direction", "zero_arrow_length", "zero_arrow_width",
))
def test_straight_note_keeps_exact_one_actual_attached_native_arrow(monkeypatch, tmp_path, fault):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    if fault == "attachment_count":
        state.note_annotation.GetAttachedEntityCount3 = lambda: 2
    elif fault == "attachment_type":
        state.note_annotation.GetAttachedEntityTypes = lambda: (46,)
    elif fault == "dangling":
        state.note_annotation.IsDangling = lambda: True
    elif fault == "bent_leader":
        state.note_annotation.GetLeaderStyle = lambda: 2
    elif fault == "leader_hidden":
        state.note_annotation.GetLeaderCount = lambda: 0
    elif fault == "leader_multiple":
        state.note_annotation.GetLeaderCount = lambda: 2
    elif fault in (
        "leader_points_short", "leader_points_long", "leader_nonfinite",
        "leader_landing_drift", "leader_zero_length",
    ):
        original_points = state.note_annotation.GetLeaderPointsAtIndex
        def broken_points(index):
            points = list(original_points(index))
            if fault == "leader_points_short":
                points.pop()
            elif fault == "leader_points_long":
                points.append(0.0)
            elif fault == "leader_nonfinite":
                points[0] = math.nan
            elif fault == "leader_landing_drift":
                points[4] += 2e-8
            else:
                points[:3] = points[3:6]
            return points
        state.note_annotation.GetLeaderPointsAtIndex = broken_points
    elif fault in (
        "short_arrow", "long_arrow", "nonfinite_arrow", "arrow_landing_drift",
        "zero_arrow_direction", "zero_arrow_length", "zero_arrow_width",
    ):
        original_record = state.note_annotation.paper_record
        def broken_arrow():
            record = original_record()
            arrow = record["display"]["arrows"][0]
            if fault == "short_arrow":
                arrow.pop()
            elif fault == "long_arrow":
                arrow.append(0.0)
            elif fault == "nonfinite_arrow":
                arrow[3] = math.nan
            elif fault == "arrow_landing_drift":
                arrow[1] += 2e-8
            elif fault == "zero_arrow_direction":
                arrow[3:5] = (0.0, 0.0)
            elif fault == "zero_arrow_length":
                arrow[6] = 0.0
            else:
                arrow[7] = 0.0
            return record
        state.note_annotation.paper_record = broken_arrow
    else:
        state.note_arrow_count = 2
    with pytest.raises(RuntimeError):
        drawing._assert_saved_physical_references(
            state.adapter, state.identities, state.configurations,
            serialized_full_names=state.serialized_full_names,
            serialized_shelf_names=state.serialized_shelf_names, paper=state.paper,
        )
    assert state.closes == [state.path.name]
    assert state.adapter.currentModel is state.previous


@pytest.mark.parametrize("phase", ("settled", "saved"))
@pytest.mark.parametrize("field", ("position", "width", "angle"))
def test_tail_fragment_drift_cannot_hide_inside_complete_box_settle_tolerance(
    monkeypatch, tmp_path, phase, field,
):
    state = _saved_physical_fixture(monkeypatch, tmp_path)
    display = state.tail_annotation.GetSpecificAnnotation()
    before = drawing.measure_reference_text(state.adapter, display, axis=1, label="ThreadLengthMin")
    row = state.tail_record["display"]["texts"][0]
    if field == "position":
        row["pos"][0] += 0.0003
    elif field == "width":
        row["w"] += 0.0003
    else:
        row["ang"] += 0.0001
    after = drawing.measure_reference_text(state.adapter, display, axis=1, label="ThreadLengthMin")
    assert max(
        abs(getattr(before["text"], key) - getattr(after["text"], key))
        for key in ("xmin", "ymin", "xmax", "ymax")
    ) <= 0.0002
    with pytest.raises(RuntimeError, match="fragment placement/format"):
        if phase == "settled":
            state.adapter.currentModel = state.saved
            drawing._assert_tail_layout(
                state.adapter, state.tail_annotation, state.major_annotation, frame=state.paper["tail"],
            )
        else:
            drawing._assert_saved_physical_references(
                state.adapter, state.identities, state.configurations,
                serialized_full_names=state.serialized_full_names,
                serialized_shelf_names=state.serialized_shelf_names, paper=state.paper,
            )
    if phase == "saved":
        assert state.closes == [state.path.name]
        assert state.adapter.currentModel is state.previous
