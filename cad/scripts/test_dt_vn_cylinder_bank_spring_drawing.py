"""Offline contracts for the MHA-DT-VN-68 cylinder bank spring (McMaster 9714K392)."""

from __future__ import annotations

import contextlib
import math
from pathlib import Path

import pytest

import _config
import build_dt_vn_cylinder_bank_spring as part
import dt_vn_cylinder_bank_spring_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_9714K392 as recipe

STEM = "dt-vn-cylinder-bank-spring"
SHEET = "dt_vn_cylinder_bank_spring"
NUMBER = "MHA-DT-VN-68"
STOCK_NAME = "Wave Disc Spring"
BUILD = "build_9714K392"
IN = 25.4
LBF = 4.4482216


def test_catalogue_row_is_the_registered_mcmaster_wave_spring() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("9714K392",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == STOCK_NAME
    assert stock.material == row["material"] == part.MATERIAL
    assert row["number"] == NUMBER
    assert int(row["quantity"]) == spec.COUNT == 1
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is getattr(recipe, BUILD)
    assert metadata.threaded is False


def test_spec_carries_the_live_catalogue_facts() -> None:
    """mcmaster.com/9714K392, read live 2026-10-09."""
    assert spec.ID == pytest.approx(0.385 * IN)
    assert spec.OD == pytest.approx(0.5 * IN)
    assert spec.THICKNESS == pytest.approx(0.005 * IN)
    assert spec.FREE_HEIGHT == pytest.approx(0.05 * IN)
    assert spec.WORKING_HEIGHT == pytest.approx(0.024 * IN)
    assert spec.WORKING_LOAD_N == pytest.approx(1.5 * LBF)
    # The model is the installed envelope at the .035 set gap (one inch
    # feeler leaf, #3042; fit audit part 2, B11).
    assert spec.MODEL_HEIGHT == spec.INSTALLED_HEIGHT == pytest.approx(0.035 * IN)
    assert spec.WORKING_HEIGHT <= spec.MODEL_HEIGHT < spec.FREE_HEIGHT


class _Recorder:
    """A fake SolidWorks that records every call a recipe makes."""

    def __init__(self) -> None:
        self.events: list[tuple] = []

    def log(self, name: str, args=(), kwargs=None) -> None:
        self.events.append((name, tuple(args), dict(kwargs or {})))

    def create_sketch(self, *args):
        self.log("create_sketch", args)
        return "ok"

    def exit_sketch(self, *args):
        self.log("exit_sketch", args)
        return "ok"

    def create_extrusion(self, *args):
        self.log("create_extrusion", args)
        return "ok"


def _record(monkeypatch) -> list[tuple]:
    adapter = _Recorder()

    def define_circle(_adapter, x, y, radius, label, **kwargs):
        adapter.log("circle", (x, y, radius, label))
        return label

    def volume_check(_adapter, label, expected, tol):
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
    getattr(recipe, BUILD)(adapter)
    return adapter.events


def test_recipe_is_the_installed_envelope_annulus(monkeypatch) -> None:
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
    assert extrude[1][0].depth == pytest.approx(spec.MODEL_HEIGHT)
    assert not extrude[1][0].both_directions
    assert [c[1][0] for c in calls if c[0] == "name"] == ["SpringProfile", "SpringBody"]
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    assert volume[1][1] == pytest.approx(
        math.pi / 4.0 * (spec.OD**2 - spec.ID**2) * spec.MODEL_HEIGHT
    )


def test_standalone_recipe_run_is_catalog_only(monkeypatch, tmp_path) -> None:
    from diagnostics import diag_mcmaster_lib as lib

    assert not hasattr(recipe, "replica_main")
    saved: list[str] = []
    built: list = []

    class _Adapter:
        def create_part(self):
            return "ok"

        def save_file(self, path):
            saved.append(path)
            return "ok"

    def fake_recipe(adapter, truth=None):
        built.append(adapter)

    def no_views(_adapter, _stem):
        return {}

    def no_close(_adapter):
        return None

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(recipe, BUILD, fake_recipe)
    monkeypatch.setattr(lib, "OUT_DIR", tmp_path)
    monkeypatch.setattr(lib, "assert_seat_sketch_baseline", lambda *a: None)
    monkeypatch.setattr(lib, "mass_properties", lambda _a: {"volume_mm3": 13.0})
    monkeypatch.setattr(lib, "export_views", no_views)
    monkeypatch.setattr(lib, "close_all", no_close)
    adapter = _Adapter()
    artefacts = recipe.build_catalog(adapter)
    assert built == [adapter]
    assert saved == [str((tmp_path / f"{spec.SKU}-catalog.SLDPRT").resolve())]
    assert artefacts["sldprt"] == str(tmp_path / f"{spec.SKU}-catalog.SLDPRT")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{spec.SKU}*.SLDPRT"))


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    sheet = DRAWINGS_BY_NAME[SHEET]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES


def test_sheet_prints_only_replacement_sizes_while_the_part_keeps_its_gauges() -> None:
    """ID, OD and free height; not the strip thickness the SKU defines
    (machinist 4e46b502), nor the load-point gauges the part keeps."""
    import draw_dt_vn_cylinder_bank_spring as drawing
    from vn_disc_spring_supplier_stock import SUPPLIER_DIMENSIONS_BY_FEATURE

    assert spec.SUPPLIER_APPLICATION_DIMENSIONS == ("WORKING_HEIGHT", "WORKING_DEFLECTION")
    assert drawing.SHEET_SPEC.SUPPLIER_APPLICATION_DIMENSIONS == ()
    assert drawing.SHEET_FEATURES == {
        "free_front": ("DiscSupplierHeight",),
        "free_top": ("DiscSupplierPlan",),
    }
    assert {field for sizes in drawing.PRINTED.values() for field in sizes} == {
        "ID",
        "OD",
        "FREE_HEIGHT",
    }
    # The part keeps its strip; the sheet neither shows nor dimensions it.
    assert SUPPLIER_DIMENSIONS_BY_FEATURE["DiscSupplierStrip"] == ("SupplierThickness",)
    assert spec.THICKNESS == pytest.approx(0.005 * IN)
    assert drawing.SHEET_SPEC.ID_BAND == spec.ID_BAND
    assert drawing.SHEET_SPEC.OD_BAND == spec.OD_BAND


# Native diagram bounds and size ink of farm runs fa43a1a5 (ec339f3d) and
# ae121732 (d179e35b), identical on both, at 2:1. Metres.
FRONT_BOUNDS = (0.1188, 0.13223, 0.1442, 0.13477)
PLAN_BOUNDS = (0.1188, 0.2143, 0.1442, 0.2397)
# Those runs' free-height station, 18 mm off the envelope; it is now 10 mm.
_OLD_STATION_X, _STATION_X = 0.1622, 0.1442 + 0.010
# GetArrowHeadAtIndex2 tips and directions (toward the base); every head is
# 3.556 mm long and 0.762 mm wide. The free height's ride its station.
NATIVE_ARROWS = {
    "SupplierFreeHeight": [
        (0.1622 - _OLD_STATION_X + _STATION_X, 0.13223, 0, -1),
        (0.1622 - _OLD_STATION_X + _STATION_X, 0.13477, 0, 1),
    ],
    "SupplierID": [(0.1218905, 0.2251869, -0.9826622, -0.1854051)],
    "SupplierOD": [(0.1440247, 0.2248973, 0.9861979, -0.1655707)],
}


def _positions(scale=2.0):
    import draw_dt_vn_cylinder_bank_spring as drawing

    return drawing.size_text_positions(
        {"free_front": FRONT_BOUNDS, "free_top": PLAN_BOUNDS},
        {"free_front": scale, "free_top": scale},
    )


def _text_box(drawing, name, position):
    from _layout_geometry import Box

    x, y = position
    width = (
        drawing.HEIGHT_TEXT_WIDTH_M
        if name in drawing.TEXT_SIDES["free_front"]
        else drawing.DIAMETER_TEXT_WIDTH_M
    )
    half_height = drawing.TEXT_HEIGHT_M / 2.0
    return Box(x - width / 2.0, y - half_height, x + width / 2.0, y + half_height)


def test_size_text_positions_come_from_the_spec_sizes_and_view_scale() -> None:
    """Free height: its station 10 mm off the OD-wide envelope, 1 mm of
    witness and the shelf gap. Diameters: the farther of a text height off
    the OD rim and 2 mm past the arrowhead's outer reach. A position is its
    text's centre, as SolidWorks reports it."""

    positions = _positions()
    assert set(positions) == {"SupplierFreeHeight", "SupplierID", "SupplierOD"}
    od_rim, id_rim = spec.OD / 1000.0, spec.ID / 1000.0  # radii at 2:1
    shelf = 0.001 + 0.002 + 0.0002
    assert positions["SupplierFreeHeight"] == pytest.approx(
        (0.1315 + od_rim + 0.010 + shelf + 0.0201493 / 2.0, 0.1335)
    )
    assert positions["SupplierFreeHeight"][0] == pytest.approx(0.16747465)
    od_gap = od_rim + 0.003556 + 0.000381 + 0.002 + 0.0002
    id_gap = max(od_rim + 0.0035 + 0.0002, id_rim + 0.003556 + 0.000381 + 0.0022)
    assert od_gap == pytest.approx(0.018837) and id_gap == pytest.approx(0.0164)
    assert positions["SupplierOD"] == pytest.approx(
        (0.1315 + od_gap + 0.038334 / 2.0, 0.227)
    )
    assert positions["SupplierID"] == pytest.approx(
        (0.1315 - id_gap - 0.038334 / 2.0, 0.227)
    )
    # Scale, not constants: at 1:1 the station closes in by half the OD.
    unit = _positions(scale=1.0)
    assert unit["SupplierFreeHeight"][0] == pytest.approx(
        positions["SupplierFreeHeight"][0] - spec.OD / 2000.0
    )


@pytest.mark.parametrize("name", list(NATIVE_ARROWS))
def test_each_text_clears_its_own_native_arrowheads_by_two_mm(name) -> None:
    """The fixed text clears the native arrowheads by at least
    ``ARROW_TEXT_CLEARANCE_M``, and the arithmetic reach bounds them."""
    import draw_dt_vn_cylinder_bank_spring as drawing
    from _layout_audit import arrowhead_segments
    from _layout_geometry import ARROW_TEXT_CLEARANCE_M, segment_box_distance

    heads = [
        segment
        for x, y, dx, dy in NATIVE_ARROWS[name]
        for segment in arrowhead_segments([x, y, 0.0, dx, dy, 0.0, 0.003556, 0.000762])
    ]
    text = _text_box(drawing, name, _positions()[name])
    clearance = min(segment_box_distance(head, text) for head in heads)
    assert clearance >= ARROW_TEXT_CLEARANCE_M + 1e-4, clearance
    side = {**drawing.TEXT_SIDES["free_front"], **drawing.TEXT_SIDES["free_top"]}[name]
    if name in drawing.TEXT_SIDES["free_top"]:
        rim = {"SupplierID": spec.ID, "SupplierOD": spec.OD}[name] / 1000.0
        reach = max(abs(x - 0.1315) for head in heads for x in (head.x0, head.x1))
        assert reach <= drawing.arrow_reach(rim)
        near = text.xmin if side > 0 else text.xmax
        assert abs(near - 0.1315) - drawing.arrow_reach(rim) >= ARROW_TEXT_CLEARANCE_M
    else:
        assert drawing.height_text_gap() - 0.000762 / 2.0 >= ARROW_TEXT_CLEARANCE_M


def test_fixed_texts_fit_their_cells() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing
    from _supplier_spring_drawing import supplier_state_cells

    cells = {key: cell for key, _, cell in supplier_state_cells(0.0)}
    for key, sides in drawing.TEXT_SIDES.items():
        x0, _y0, x1, _y1 = cells[key]
        for name in sides:
            text = _text_box(drawing, name, _positions()[name])
            assert x0 < text.xmin and text.xmax < x1


def test_witness_gap_spans_the_envelope_from_its_far_end() -> None:
    """Natively each witness starts at the envelope's far end (round 3 PNG),
    so its gap ends WITNESS_GAP_M past the near end on the 2:1 view."""
    import draw_dt_vn_cylinder_bank_spring as drawing

    x0, _y0, x1, _y1 = FRONT_BOUNDS
    assert x1 - x0 == pytest.approx(spec.OD / 1000.0 * 2.0)
    assert x0 + drawing.witness_gap(2.0) == pytest.approx(x1 + drawing.WITNESS_GAP_M)
    # The witness keeps a visible run to 1 mm past its station.
    assert x0 + drawing.witness_gap(2.0) < _STATION_X - 0.005
