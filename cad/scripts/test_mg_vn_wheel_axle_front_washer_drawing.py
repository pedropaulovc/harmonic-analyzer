"""Offline contracts for the MHA-MG-VN-55 wheel-axle front washer (McMaster 92916A250)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path

import pytest

import _config
import build_mg_vn_wheel_axle_front_washer as part
import mg_vn_wheel_axle_front_washer_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_92916A250 as recipe

STEM = "mg-vn-wheel-axle-front-washer"
SHEET = "mg_vn_wheel_axle_front_washer"
NUMBER = "MHA-MG-VN-55"
STOCK_NAME = "Brass Washer for Number 4 Screw Size"
BUILD = "build_92916A250"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_part() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("92916A250",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == STOCK_NAME
    assert stock.material == row["material"] == part.MATERIAL == "Brass"
    assert row["number"] == NUMBER
    assert row["process"] == "purchased"
    assert int(row["quantity"]) == spec.COUNT == 1
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is getattr(recipe, BUILD)
    assert metadata.threaded is False


def test_spec_carries_the_live_catalogue_facts() -> None:
    """mcmaster.com/92916A250, checked live 2026-10-10."""
    assert spec.ID == pytest.approx(0.120 * IN)
    assert spec.OD == pytest.approx(0.281 * IN)
    assert spec.THICKNESS_MIN == pytest.approx(0.018 * IN)
    assert spec.THICKNESS_MAX == pytest.approx(0.032 * IN)
    # The model is the catalogue range's nominal, to 0.01 mm.
    assert spec.MODEL_THICKNESS == pytest.approx(0.025 * IN, abs=0.01)
    assert spec.THICKNESS_MIN < spec.MODEL_THICKNESS < spec.THICKNESS_MAX


class _Recorder:
    """A fake SolidWorks that records every call a recipe makes."""

    def __init__(self) -> None:
        self.events: list[tuple] = []

    def log(self, name: str, args=(), kwargs=None) -> None:
        self.events.append((name, tuple(args), dict(kwargs or {})))

    async def create_sketch(self, *args):
        self.log("create_sketch", args)
        return "ok"

    async def exit_sketch(self, *args):
        self.log("exit_sketch", args)
        return "ok"

    async def create_extrusion(self, *args):
        self.log("create_extrusion", args)
        return "ok"


def _record(monkeypatch) -> list[tuple]:
    adapter = _Recorder()

    async def define_circle(_adapter, x, y, radius, label, **kwargs):
        adapter.log("circle", (x, y, radius, label))
        return label

    async def volume_check(_adapter, label, expected, tol):
        adapter.log("volume_check", (label, expected, tol))
        return expected

    @contextlib.contextmanager
    def no_inference(_adapter):
        adapter.log("no_inference_enter")
        yield
        adapter.log("no_inference_exit")

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(
        recipe, "name_last_feature", lambda _a, name: adapter.log("name", (name,))
    )
    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "define_circle", define_circle)
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    asyncio.run(getattr(recipe, BUILD)(adapter))
    return adapter.events


def test_recipe_is_the_washer_annulus(monkeypatch) -> None:
    calls = _record(monkeypatch)
    names = [c[0] for c in calls]
    assert calls[0] == ("create_sketch", ("Top",), {})
    circles = [c[1] for c in calls if c[0] == "circle"]
    assert sorted(r for _x, _y, r, _ in circles) == pytest.approx(
        [spec.ID / 2.0, spec.OD / 2.0]
    )
    assert all((x, y) == (0.0, 0.0) for x, y, _r, _ in circles)
    enter, leave = names.index("no_inference_enter"), names.index("no_inference_exit")
    assert all(enter < i < leave for i, n in enumerate(names) if n == "circle")
    (extrude,) = [c for c in calls if c[0] == "create_extrusion"]
    assert extrude[1][0].depth == pytest.approx(spec.MODEL_THICKNESS)
    assert not extrude[1][0].both_directions
    assert [c[1][0] for c in calls if c[0] == "name"] == ["WasherProfile", "WasherBody"]
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    assert volume[1][1] == pytest.approx(
        math.pi / 4.0 * (spec.OD**2 - spec.ID**2) * spec.MODEL_THICKNESS
    )




def test_standalone_recipe_run_is_catalog_only(monkeypatch, tmp_path) -> None:
    from diagnostics import diag_mcmaster_lib as lib

    assert not hasattr(recipe, "replica_main")
    saved: list[str] = []
    built: list = []

    class _Adapter:
        async def create_part(self):
            return "ok"

        async def save_file(self, path):
            saved.append(path)
            return "ok"

    async def fake_recipe(adapter, truth=None):
        built.append(adapter)

    async def no_views(_adapter, _stem):
        return {}

    async def no_close(_adapter):
        return None

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(recipe, BUILD, fake_recipe)
    monkeypatch.setattr(lib, "OUT_DIR", tmp_path)
    monkeypatch.setattr(lib, "assert_seat_sketch_baseline", lambda *a: None)
    monkeypatch.setattr(lib, "mass_properties", lambda _a: {"volume_mm3": 13.0})
    monkeypatch.setattr(lib, "export_views", no_views)
    monkeypatch.setattr(lib, "close_all", no_close)
    adapter = _Adapter()
    artefacts = asyncio.run(recipe.build_catalog(adapter))
    assert built == [adapter]
    assert saved == [str((tmp_path / f"{spec.SKU}-catalog.SLDPRT").resolve())]
    assert artefacts["sldprt"] == str(tmp_path / f"{spec.SKU}-catalog.SLDPRT")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{spec.SKU}*.SLDPRT"))


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_mg_vn_wheel_axle_front_washer as drawing

    sheet = DRAWINGS_BY_NAME[SHEET]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert (
        drawing.build.__code__.co_names.count("build_purchased_fastener_drawing") == 1
    )


def test_installation_note_fits_the_sheet() -> None:
    lines = _config.parts(STEM)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines


@pytest.mark.parametrize(
    "name,original_front,original_top",
    [
        (
            "mg_vn_wheel_axle_back_washer",
            (0.0, 0.008, 0.040, 0.006),
            (0.0, 0.008, 0.035, 0.008),
        ),
        (
            "mg_vn_wheel_axle_front_washer",
            (0.0, 0.008, 0.040, 0.006),
            (0.0, 0.008, 0.035, 0.008),
        ),
        (
            "ch_rocker_arm_tl_vn_oblique_lever_washer",
            (0.0, 0.008, 0.035, 0.008),
            (0.0, 0.008, 0.040, 0.006),
        ),
        (
            "ch_rocker_arm_tl_vn_oblique_block_washer",
            (0.0, 0.008, 0.035, 0.008),
            (0.0, 0.008, 0.040, 0.006),
        ),
        (
            "pd_vn_transgear_pivot_shim",
            (0.0, 0.006, 0.035, 0.006),
            (0.0, 0.008, 0.040, 0.008),
        ),
        (
            "ch_vn_rocker_thrust_washer",
            (0.0, 0.008, 0.040, 0.008),
            (0.0, 0.006, 0.035, 0.006),
        ),
        (
            "sm_vn_knife_hanger_washer",
            (0.0, 0.008, 0.035, 0.008),
            (0.0, 0.008, 0.040, 0.006),
        ),
    ],
)
def test_seven_washer_recipes_reserve_projected_axes_before_fit(
    monkeypatch, name, original_front, original_top
) -> None:
    """Exercise actual recipe arguments and shared pure cell geometry, not COM."""
    import importlib

    import _purchased_fastener_drawing as purchased

    drawing = importlib.import_module(f"draw_{name}")
    captured = []

    async def capture(_adapter, sheet, **kwargs):
        assert sheet is drawing.SPEC
        captured.append(kwargs)
        return {}

    monkeypatch.setattr(drawing, "build_purchased_fastener_drawing", capture)
    assert asyncio.run(drawing.build(object())) == {}
    (arguments,) = captured
    margins = arguments["supplier_margins"]
    assert margins is drawing.SUPPLIER_MARGINS
    # Reserved views are the dimension-bearing Front/Top, never the bare Right.
    # This offline recipe census does not establish the native dimension census.
    assert set(margins) == {"*Front", "*Top"}
    assert callable(arguments["supplier_dimensions"])
    assert callable(arguments["saved_check"])
    assert len(arguments["settled_checks"]) == 1

    label = drawing.SPEC.artifact_stem
    # Match the builder: supplier operating data is a separate footer input.
    notes = str(_config.parts(label).get("installation_notes", ""))
    caption_y = purchased.view_band_bottom(
        notes, label=label, supplier_data=arguments.get("supplier_data", ())
    )
    cells = purchased.fastener_view_cells(caption_y)
    outer = {view: bounds for view, _center, bounds in cells}
    fitted = {
        view: (center, bounds)
        for view, center, bounds in purchased.supplier_fit_cells(
            cells, margins, label=label
        )
    }
    original = {
        view: center
        for view, center, _bounds in purchased.supplier_fit_cells(
            cells,
            {"*Front": original_front, "*Top": original_top},
            label=label,
        )
    }
    # The actual former 40/35 mm right reserves displaced X by 2.5 mm.
    assert abs(original["*Top"][0] - original["*Front"][0]) == pytest.approx(
        0.0025
    )
    assert fitted["*Top"][0][0] == pytest.approx(fitted["*Front"][0][0])
    assert fitted["*Right"][0][1] == pytest.approx(fitted["*Front"][0][1])

    for view, previous in (("*Front", original_front), ("*Top", original_top)):
        # Keep at least every authored lane; symmetry only enlarges MG Front top.
        left, bottom, right, top = margins[view]
        assert left == previous[0]
        assert bottom == previous[1]
        assert right == 0.040
        assert top >= previous[3]
        assert top == (bottom if view == "*Front" else previous[3])
        bounds = fitted[view][1]
        assert bounds[1] == pytest.approx(outer[view][1] + bottom)
        assert bounds[3] == pytest.approx(outer[view][3] - top)
    y_difference = original_front[1] - original_front[3]
    assert original["*Front"][1] - original["*Right"][1] == pytest.approx(
        y_difference / 2
    )
    if y_difference:
        # Only the two MG Fronts had +1 mm Y from 8 mm bottom / 6 mm top.
        assert y_difference == pytest.approx(0.002)
        assert margins["*Front"][3] == pytest.approx(original_front[3] + y_difference)
    assert "*Right" not in margins
    assert fitted["*Right"][1] == outer["*Right"]
    assert fitted["*Isometric"][1] == outer["*Isometric"]
    for view, (_center, bounds) in fitted.items():
        assert bounds[0] >= outer[view][0]
        assert bounds[1] >= outer[view][1]
        assert bounds[2] <= outer[view][2]
        assert bounds[3] <= outer[view][3]
        assert bounds[0] < bounds[2]
        assert bounds[1] < bounds[3]
