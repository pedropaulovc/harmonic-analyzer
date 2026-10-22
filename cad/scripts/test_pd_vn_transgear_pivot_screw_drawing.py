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
