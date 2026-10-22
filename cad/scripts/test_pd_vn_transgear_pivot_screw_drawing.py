"""Offline contracts for the MHA-PD-VN-57 transgear pivot screw.

Recorded recipe calls are not native geometry proof; the farm build, the
native readback in the drawing script and the sheet's machinist review own
that.
"""

from __future__ import annotations

import asyncio
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
    """Rule 19 fit-up: the tip is faced to stand 0.20-0.50 below the bar's
    front face, so the printed length is the nominal bar less the window's
    middle, as a reference."""
    assert screw.TIP_RECESS == (0.20, 0.50)
    assert screw.FITTED_THREAD_LEN == pytest.approx(
        BAR_DEPTH - sum(screw.TIP_RECESS) / 2.0
    )
    assert screw.SHOULDER_END_Y == -screw.SHOULDER_LEN
    assert screw.TIP_Y == pytest.approx(screw.SHOULDER_END_Y - screw.FITTED_THREAD_LEN)
    assert screw.REFERENCE_DIMENSIONS == (("StockTrimProfile", "CutLength"),)
    assert screw.DIMENSION_TOLERANCE_TYPES["CutLength"] == 0
    callout = screw.DIMENSION_CALLOUTS["CutLength"]
    assert "0.20-0.50 BELOW MHA-PD-07" in callout
    assert "FRONT FACE AS FITTED" in callout
    # Facing only shortens: the nominal fit is inside the catalogue length,
    # and every stock length reaches the thinnest bar's deepest recess.
    assert screw.FITTED_THREAD_LEN < screw.THREAD_LEN
    thin = BAR_DEPTH - bar.BAR_DEPTH_BAND
    assert screw.STOCK_THREAD_LEN_MIN >= thin - screw.TIP_RECESS[1]
    # The corner the fit-up sets aside: ASME-short stock (9.017) in the
    # thickest bar (9.63) stops 0.113 deeper than the 0.50 max recess.
    thick = BAR_DEPTH + bar.BAR_DEPTH_BAND
    assert joints.PIVOT_STOCK_SHORTFALL_AT_THICKEST_BAR == pytest.approx(
        thick - screw.TIP_RECESS[1] - screw.STOCK_THREAD_LEN_MIN
    )
    assert joints.PIVOT_STOCK_SHORTFALL_AT_THICKEST_BAR == pytest.approx(
        0.113, abs=1e-3
    )


def test_engagement_charges_one_pitch_and_the_neck() -> None:
    """Worst case: the thinnest bar, the deepest recess, one incomplete pitch
    at the faced tip and the neck before the full thread starts."""
    thin = BAR_DEPTH - bar.BAR_DEPTH_BAND
    assert joints.PIVOT_FITTED_LEN_MIN == pytest.approx(thin - screw.TIP_RECESS[1])
    worst = joints.PIVOT_FITTED_LEN_MIN - screw.PITCH - screw.FULL_THREAD_START
    assert joints.PIVOT_ENGAGEMENT_WORST == pytest.approx(worst)
    assert joints.PIVOT_ENGAGEMENT_WORST_D >= screw.ENGAGEMENT_MIN_D
    assert screw.THREAD_LENGTH_MIN == pytest.approx(
        math.ceil((1.5 * screw.THREAD_MAJOR + screw.PITCH) * 20.0) / 20.0
    )


def test_chamfer_max_keeps_the_tip_inside_the_charged_pitch() -> None:
    # The model stands at the printed maximum (swTolMAX prints the nominal).
    assert screw.CHAMFER_WIDTH == screw.CHAMFER_WIDTH_MAX == pytest.approx(0.60)
    assert screw.CHAMFER_ANGLE_TOLERANCE == angular_band_deg() == 1.0
    steepest = math.radians(screw.CHAMFER_ANGLE + screw.CHAMFER_ANGLE_TOLERANCE)
    assert screw.CHAMFER_AXIAL_MAX == pytest.approx(0.60 * math.tan(steepest))
    assert screw.CHAMFER_AXIAL_MAX <= screw.INCOMPLETE_TIP_LEN_MAX == screw.PITCH
    # "Past the thread root" fits under the maximum: tip Ø 4.1656 - 1.20 =
    # 2.9656 clears the deepest estimated 2A root Ø3.038.
    screw.require_chamfer_past_root(0.60)
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
        (0.00060, 0.0, 0.0)
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
    source = (SCRIPTS / "draw_pd_vn_transgear_pivot_screw.py").read_text(encoding="utf-8")
    assert "build_purchased_fastener_drawing" not in source
    assert "_stock_trim_drawing" in source
    assert "SetPrecision3" not in source and "set_dimension_precision" not in source
    assert drawing.ISO_SCALE == drawing.SHEET_SCALE
    build_source = (SCRIPTS / "build_pd_vn_transgear_pivot_screw.py").read_text(
        encoding="utf-8"
    )
    assert 'display.SetText(1, "(")' in build_source
    assert 'display.SetText(2, ")")' in build_source


@pytest.mark.parametrize("refuse_isometric_mode", (False, True))
def test_finished_views_remove_hidden_lines_before_annotations(
    monkeypatch, tmp_path, refuse_isometric_mode
) -> None:
    import _drawing_view_display as display

    source = tmp_path / "pivot-screw.SLDPRT"
    source.touch()
    views = {}

    def place(_adapter, _source, orientation, *_args, **_kwargs):
        state = SimpleNamespace(mode=0)

        def set_mode(_parent, mode, *_options):
            if not (refuse_isometric_mode and orientation == "*Isometric" and mode == 2):
                state.mode = mode
            return True

        view = SimpleNamespace(
            SetDisplayMode4=set_mode, GetDisplayMode2=lambda: state.mode
        )
        views[orientation] = view
        return view

    class AnnotationPhase(Exception):
        pass

    def reached_annotations(*_args, **_kwargs):
        raise AnnotationPhase

    async def open_source(_path):
        return True

    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(display, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "check", lambda _label, value: value)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        drawing,
        "new_project_drawing",
        lambda *_args, **_kwargs: (
            SimpleNamespace(ActivateSheet=lambda _name: True), object()
        ),
    )
    monkeypatch.setattr(drawing, "create_blank_drawing_sheets", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *_args: None)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "curate_view_dimensions", reached_annotations)
    adapter = SimpleNamespace(currentModel=object(), open_model=open_source)
    if refuse_isometric_mode:
        with pytest.raises(RuntimeError, match="hidden-lines-removed"):
            asyncio.run(drawing.build(adapter))
        assert views["*Isometric"].GetDisplayMode2() != 2
    else:
        with pytest.raises(AnnotationPhase):
            asyncio.run(drawing.build(adapter))
        assert set(views) == {"*Front", "*Isometric", "*Top"}
        assert all(view.GetDisplayMode2() == 2 for view in views.values())


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
        return self.point_result


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
    from _drawing_edges import ViewEdge, ViewEdges

    selection = _HeadSelection()
    front = SimpleNamespace(
        name="FinishedFront", mode=2, ReferencedConfiguration="Default", dimensions=[],
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
    annotation.GetDisplayData = lambda: None
    tolerance = SimpleNamespace(Type=0)
    native = SimpleNamespace(
        SystemValue=screw.HEAD_H / 1000, FullName="D2@FinishedFront", Tolerance=tolerance,
    )
    presentation = screw.SUPPLIER_REFERENCE_DIMENSIONS["SupplierHeadHeight"]
    texts = {1: "(", 2: " in)", 4: presentation.get("callout", "")}
    display = SimpleNamespace(
        Type2=12, ShowDimensionValue=True, ShowParenthesis=False,
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
        return ViewEdges(label=label, edges=tuple(state.edges))

    def project(_adapter, view, points, *, label):
        points = tuple(points)
        state.projections.append((view, points, label))
        return tuple((0.140 + 4 * x, 0.190 + 4 * y) for x, y, _z in points)

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(edge_dimensions, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        edge_dimensions._sw_type_info, "early_bound_or_flag",
        lambda value, _kind, *_members: value,
    )
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(drawing, "scan_view_edges", scan)
    monkeypatch.setattr(drawing, "model_points_in_view", project)
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
    ("null_attachment", "named entities"),
    ("extra_attachment", "two EDGE attachments"),
    ("attachment_count", "two EDGE attachments"),
    ("attachment_type", "two EDGE attachments"),
    ("dangling", "named entities"),
    ("missing_native", "no native model dimension"),
    ("dimension_type", "not vertical"),
    ("linear_dimension_type", "not vertical"),
    ("unknown_owner", "exact front view"),
    ("malformed_kinds", "int"),
    ("owner_type", "exact front view"),
    ("missing_owner", "exact front view"),
    ("wrong_owner", "exact front view"),
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
    elif fault == "linear_dimension_type":
        state.display.Type2 = 2
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
    assert evidence[0] == "drawing.pivot_head_height_refusal"
    for field in (
        "type2", "count_api", "attached_len", "kinds_len", "kinds",
        "attached_nulls", "dangling", "owner_type", "owner_null", "owner_is_same",
        "native_dimension_null", "system_value", "attachment_is_same",
        "display_data_null", "arrow_count", "arrows",
    ):
        assert field in evidence[1]
        assert f"'{field}':" in str(refusal.value)


def test_physical_head_height_valid_snapshot_returns_exact_height_without_failure_probes(
    monkeypatch,
) -> None:
    state = _physical_head_fixture(monkeypatch)

    def forbidden():
        raise AssertionError("Refusal-only display data must not be read on success")

    state.annotation.GetDisplayData = forbidden
    assert drawing._assert_physical_head_height(
        state.adapter, state.front, state.display, entities=(state.bearing, state.top),
    ) == screw.HEAD_H
    assert not state.events


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
    with pytest.raises(RuntimeError, match="native_snapshot=") as refusal:
        drawing._assert_physical_head_height(
            state.adapter, state.front, display, entities=(state.bearing, state.top),
        )
    evidence = state.events[-1][1]
    if missing == "display":
        assert "missing native display dimension" in str(refusal.value)
        assert evidence["display_null"] is True
    elif missing == "annotation":
        assert "missing native annotation" in str(refusal.value)
        assert evidence["annotation_null"] is True
    else:
        assert "expected two EDGE attachments" in str(refusal.value)
        assert evidence["attached_len" if missing == "attached" else "kinds_len"] == 0


def test_physical_head_height_refusal_bounds_metadata_and_rendered_arrow_evidence(
    monkeypatch,
) -> None:
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
    arrows = []
    state.annotation.GetDisplayData = lambda: SimpleNamespace(
        GetArrowHeadCount=lambda: 100,
        GetArrowHeadAtIndex2=lambda index: arrows.append(index) or tuple(range(20)),
    )
    with pytest.raises(RuntimeError, match="expected two EDGE attachments") as refusal:
        drawing._assert_physical_head_height(
            state.adapter, state.front, state.display, entities=(state.bearing, state.top),
        )
    evidence = state.events[-1][1]
    assert evidence["attached_len"] == 200
    assert evidence["kinds_len"] == 300
    assert evidence["kinds"] == (46,) * 4
    assert evidence["attached_nulls"] == (False,) * 4
    assert reads == [(name, index) for name in ("attached", "kinds") for index in range(4)]
    assert evidence["native_dimension_null"] is False
    assert evidence["system_value"] == screw.HEAD_H / 1000
    assert evidence["attachment_is_same"] == ((0, 1), (0, 1))
    assert evidence["display_data_null"] is False
    assert evidence["arrow_count"] == 100
    assert arrows == list(range(4))
    assert evidence["arrows"] == (tuple(range(12)),) * 4
    assert f"native_snapshot={evidence}" in str(refusal.value)


def test_physical_head_height_refusal_diagnostic_error_remains_visible(monkeypatch) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.display.Type2 = 2

    def broken_display_data():
        raise RuntimeError("native display data failed")

    state.annotation.GetDisplayData = broken_display_data
    with pytest.raises(RuntimeError, match="not vertical.*native_snapshot=") as refusal:
        drawing._assert_physical_head_height(
            state.adapter, state.front, state.display, entities=(state.bearing, state.top),
        )
    assert str(refusal.value.__cause__) == "native display data failed"
    assert state.events[-1][1]["failure_probe_error"] == "native display data failed"


def test_physical_head_height_refusal_reads_each_native_metadata_getter_once(monkeypatch) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.display.Type2 = 2
    calls = []
    for name in (
        "GetAttachedEntities3", "GetAttachedEntityTypes", "GetAttachedEntityCount3", "IsDangling",
    ):
        original = getattr(state.annotation, name)

        def read_once(original=original, name=name):
            calls.append(name)
            return original()

        monkeypatch.setattr(state.annotation, name, read_once)
    with pytest.raises(RuntimeError, match="not vertical"):
        drawing._assert_physical_head_height(
            state.adapter, state.front, state.display, entities=(state.bearing, state.top),
        )
    assert len(calls) == 4
    assert len(set(calls)) == 4
    evidence = state.events[-1][1]
    assert evidence["type2"] == 2
    assert evidence["owner_is_same"] == 1
    assert evidence["count_api"] == 2


def test_physical_head_height_malformed_attachment_array_is_not_silently_accepted(
    monkeypatch,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.annotation.GetAttachedEntities3 = lambda: 7
    with pytest.raises(RuntimeError, match="has no len.*native_snapshot=") as refusal:
        drawing._assert_physical_head_height(
            state.adapter, state.front, state.display, entities=(state.bearing, state.top),
        )
    assert isinstance(refusal.value.__cause__, TypeError)
    assert state.events[-1][1]["attached_len"] is None
    assert state.events[-1][1]["count_api"] == 2


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


def _saved_head_fixture(monkeypatch, tmp_path):
    import _supplier_dimensions as supplier

    state = _physical_head_fixture(monkeypatch)
    monkeypatch.setattr(supplier, "_early_bound", lambda value, _kind: value)
    path = tmp_path / "pivot.SLDDRW"
    path.touch()
    state.path = path.resolve()
    monkeypatch.setattr(drawing, "OUTPUTS", SimpleNamespace(slddrw=path))
    state.previous = state.adapter.currentModel
    finished_sheet = SimpleNamespace(
        GetDisplayDimensions=lambda: (), GetNextView=lambda: state.front,
    )
    stock_sheet = SimpleNamespace(GetDisplayDimensions=lambda: (), GetNextView=lambda: None)
    state.sheets = dict(zip(drawing.SHEET_NAMES, (finished_sheet, stock_sheet), strict=True))
    state.active_sheet = drawing.SHEET_NAMES[0]
    state.activations = []
    state.saved = SimpleNamespace(
        GetPathName=lambda: str(state.path), GetType=lambda: 3,
        GetTitle=lambda: state.path.name,
        GetFirstView=lambda: state.sheets[state.active_sheet],
        GetSheetNames=lambda: tuple(state.sheets),
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
    }
    state.configurations = {
        state.front.name: (drawing.SHEET_NAMES[0], state.front.ReferencedConfiguration),
    }
    return state


def test_saved_head_height_reopens_read_only_rescans_proves_and_closes(
    monkeypatch, tmp_path,
) -> None:
    state = _saved_head_fixture(monkeypatch, tmp_path)
    state.open_warnings = 2  # Warning telemetry is not a false load error.
    drawing._assert_saved_physical_head_height(
        state.adapter, state.identities, state.configurations,
    )
    assert state.opens == [(str(state.path), 3, 3, "", 0, 0)]
    assert state.closes == [state.path.name]
    assert state.loaded is None
    assert state.adapter.currentModel is state.previous
    assert len(state.scans) == 1
    assert state.scans[0][0] is state.saved
    assert state.scans[0][1] is state.front
    assert state.activations == [*drawing.SHEET_NAMES, drawing.SHEET_NAMES[0]]
    _name, proof = state.events[-1]
    assert proof["phase"] == "after_saved_reopen"
    assert proof["full_name"] == state.native.FullName
    assert proof["measured_head_height_mm"] == pytest.approx(screw.HEAD_H)
    assert proof["attached_circle_params_m"] == (
        state.bearing.GetCurve().CircleParams, state.top.GetCurve().CircleParams,
    )
    assert not state.additions and not state.selection.calls


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
    ("dimension_type", "not vertical"),
    ("owner_type", "exact front view"),
    ("same_named_wrong_owner", "exact front view"),
    ("wrong_value", "measures"),
    ("wrong_attachment", "named entities"),
    ("wrong_type_attachment", "two EDGE attachments"),
    ("changed_geometry", "top physical rim"),
    ("lost_hlr", "hidden-lines-removed"),
    ("format", "presentation"),
    ("source_band", "tolerance type"),
    ("close", "did not close"),
))
def test_saved_head_height_refuses_corruption_and_always_restores_current_model(
    monkeypatch, tmp_path, fault, message,
) -> None:
    state = _saved_head_fixture(monkeypatch, tmp_path)
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
        state.sheets[drawing.SHEET_NAMES[0]].GetNextView = lambda: None
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
        drawing._assert_saved_physical_head_height(
            state.adapter, state.identities, state.configurations,
        )
    assert state.closes == [state.path.name]
    assert state.adapter.currentModel is state.previous
    assert (state.loaded is not None) == (fault == "close")
    assert not state.additions


def test_saved_head_height_refuses_an_already_open_drawing_without_closing_it(
    monkeypatch, tmp_path,
) -> None:
    state = _saved_head_fixture(monkeypatch, tmp_path)
    state.loaded = state.saved
    with pytest.raises(RuntimeError, match="finalize and close"):
        drawing._assert_saved_physical_head_height(
            state.adapter, state.identities, state.configurations,
        )
    assert not state.opens and not state.closes
    assert state.loaded is state.saved
    assert state.adapter.currentModel is state.previous


def test_saved_head_height_requires_the_output_file(monkeypatch, tmp_path) -> None:
    state = _saved_head_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(
        drawing, "OUTPUTS", SimpleNamespace(slddrw=tmp_path / "missing.SLDDRW")
    )
    with pytest.raises(RuntimeError, match="saved drawing is missing"):
        drawing._assert_saved_physical_head_height(
            state.adapter, state.identities, state.configurations,
        )
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
    state = _saved_head_fixture(monkeypatch, tmp_path)
    state.adapter.currentModel = state.saved
    state.identities["SupplierHeadHeight"] = (
        state.native.FullName, state.front.name, (state.bearing, state.top), (1, 1),
    )
    monkeypatch.setattr(
        drawing, "SUPPLIER_REFERENCE_DIMENSIONS",
        {"SupplierHeadHeight": screw.SUPPLIER_REFERENCE_DIMENSIONS["SupplierHeadHeight"]},
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
        drawing._assert_supplier_references(
            state.adapter, state.identities, state.configurations,
        )
        assert len(state.scans) == 1
    else:
        with pytest.raises(RuntimeError, match=message):
            drawing._assert_supplier_references(
                state.adapter, state.identities, state.configurations,
            )


def test_build_proves_physical_head_after_finalizer_closes_saved_drawing(
    monkeypatch, tmp_path,
) -> None:
    source = tmp_path / "pivot.SLDPRT"
    source.touch()
    events = []
    model = SimpleNamespace(ActivateSheet=lambda _name: True)
    adapter = SimpleNamespace(currentModel=model)

    async def open_model(_path):
        return True

    adapter.open_model = open_model
    properties = {
        "Purchased Screw Note": "PURCHASED HEAD",
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
    stock_annotation = object()
    identities = {"captured": object()}
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
    monkeypatch.setattr(drawing, "model_point_in_view", lambda *_args, **_kwargs: (0.0, 0.0))
    monkeypatch.setattr(
        drawing, "add_property_linked_callout",
        lambda *_args, **_kwargs: SimpleNamespace(
            GetText=lambda: properties["Purchased Screw Note"],
            PropertyLinkedText=drawing.property_link("Purchased Screw Note"),
        ),
    )
    monkeypatch.setattr(
        drawing, "_add_stock_reference", lambda *_args: (stock, stock_iso, stock_annotation)
    )

    def capture(_adapter, supplied):
        assert supplied == {**references, "SupplierStockThreadLength": stock_annotation}
        events.append("identities")
        return identities

    monkeypatch.setattr(drawing, "_supplier_reference_identities", capture)

    def settled(_adapter, actual_identities, configurations):
        assert actual_identities is identities
        assert configurations[front.name] == (drawing.SHEET_NAMES[0], "Default")
        assert configurations[stock.name] == (
            drawing.SHEET_NAMES[1], screw.SUPPLIER_STOCK_CONFIGURATION,
        )
        events.append("settled")

    monkeypatch.setattr(drawing, "_assert_supplier_references", settled)
    expected = {"slddrw": "saved-pivot"}

    async def finalize(_adapter, outputs, **options):
        assert outputs is drawing.OUTPUTS
        events.append("finalize")
        for check in options["settled_checks"]:
            check()
        adapter.currentModel = None
        events.append("closed")
        return expected

    def saved(_adapter, actual_identities, configurations):
        assert adapter.currentModel is None
        assert actual_identities is identities
        assert len(configurations) == 5
        events.append("saved-reopen-proof")

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    monkeypatch.setattr(drawing, "_assert_saved_physical_head_height", saved)
    assert asyncio.run(drawing.build(adapter)) is expected
    assert events == [
        "identities", "finalize", "settled", "closed", "saved-reopen-proof",
    ]


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


@pytest.mark.parametrize("dimension_type", (0, 2, 6, 11))
def test_physical_head_height_refuses_every_nonvertical_native_type(
    monkeypatch, dimension_type,
) -> None:
    state = _physical_head_fixture(monkeypatch)
    state.display.Type2 = dimension_type
    with pytest.raises(RuntimeError, match="not vertical"):
        drawing._assert_physical_head_height(state.adapter, state.front, state.display)
