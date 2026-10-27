"""Offline contracts for the MHA-DT-VN-68 cylinder bank spring (McMaster 9714K392)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_dt_vn_cylinder_bank_spring as part
import dt_vn_cylinder_bank_spring_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
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
    # The model is the installed envelope at the 0.95 set gap.
    assert spec.MODEL_HEIGHT == spec.INSTALLED_HEIGHT == pytest.approx(0.95)
    assert spec.WORKING_HEIGHT <= spec.MODEL_HEIGHT < spec.FREE_HEIGHT


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


def test_stock_build_turns_the_recipe_axis_onto_part_z(monkeypatch) -> None:
    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is getattr(recipe, BUILD)
    assert component.transform.rotation_radians == pytest.approx(
        (math.pi / 2.0, 0.0, 0.0)
    )
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert seen["material"] == part.SPEC.material
    assert seen["screw_axis_planes"] == ("Top Plane", "Right Plane")


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
    import draw_dt_vn_cylinder_bank_spring as drawing

    sheet = DRAWINGS_BY_NAME[SHEET]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES


def test_sheet_prints_only_replacement_sizes_while_the_part_keeps_its_gauges() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing
    from _supplier_disc_spring_drawing import supplier_disc_reference_features

    assert spec.SUPPLIER_APPLICATION_DIMENSIONS == ("WORKING_HEIGHT", "WORKING_DEFLECTION")
    assert drawing.SHEET_SPEC.SUPPLIER_APPLICATION_DIMENSIONS == ()
    assert supplier_disc_reference_features(drawing.SHEET_SPEC) == {
        "free_front": ("DiscSupplierHeight", "DiscSupplierStrip"),
        "free_top": ("DiscSupplierPlan",),
    }
    assert drawing.SHEET_SPEC.ID_BAND == spec.ID_BAND
    assert drawing.SHEET_SPEC.OD_BAND == spec.OD_BAND


# Native diagram bounds and size ink of farm runs fa43a1a5 (ec339f3d) and
# ae121732 (d179e35b), identical on both, at 2:1. Metres.
FRONT_BOUNDS = (0.1188, 0.13223, 0.1442, 0.13477)
PLAN_BOUNDS = (0.1188, 0.2143, 0.1442, 0.2397)
NATIVE_POSITIONS = {
    "SupplierThickness": (0.0862323, 0.1335),
    "SupplierFreeHeight": (0.1767677, 0.1335),
    "SupplierID": (0.0932934, 0.227),
    "SupplierOD": (0.1715474, 0.227),
}
# GetArrowHeadAtIndex2 tips and directions (toward the base); every head is
# 3.556 mm long and 0.762 mm wide.
NATIVE_ARROWS = {
    "SupplierThickness": [(0.1008, 0.133373, 0, -1), (0.1008, 0.133627, 0, 1)],
    "SupplierFreeHeight": [(0.1622, 0.13223, 0, -1), (0.1622, 0.13477, 0, 1)],
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


def test_build_places_the_size_texts_after_the_shared_disc_dimensions(
    monkeypatch,
) -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    seen = {}

    async def fake_build(adapter, sheet, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(drawing, "build_supplier_spring_drawing", fake_build)
    asyncio.run(drawing.build(object()))
    supplier_dimensions = seen["supplier_dimensions"]
    assert supplier_dimensions.func is drawing.supplier_dimensions
    assert supplier_dimensions.keywords["settled_checks"] is seen["settled_checks"]

    calls = []

    def shared(adapter, views, *, spec, reference_bounds, settled_checks):
        assert spec is drawing.SHEET_SPEC
        calls.append("shared")
        settled_checks.append("shared check")

    def place(adapter, views, *, reference_bounds):
        calls.append("place")

    monkeypatch.setattr(drawing, "supplier_disc_spring_dimensions", shared)
    monkeypatch.setattr(drawing, "place_size_texts", place)
    supplier_dimensions(object(), {}, reference_bounds=lambda key: (0, 0, 1, 1))
    assert calls == ["shared", "place"]
    # The shared settled checks are the only ones: no sheet-local guard.
    assert seen["settled_checks"] == ["shared check"]


def test_size_text_positions_come_from_the_spec_sizes_and_view_scale() -> None:
    """Heights: the shared station (18 mm beyond the OD-wide diagram), 1 mm
    of witness and the shelf gap. Diameters: the farther of a text height
    off the OD rim and 2 mm past the arrowhead's outer reach. A position is
    its text's centre, as SolidWorks reports it."""
    import draw_dt_vn_cylinder_bank_spring as drawing

    positions = _positions()
    od_rim, id_rim = spec.OD / 1000.0, spec.ID / 1000.0  # radii at 2:1
    shelf = 0.001 + 0.002 + 0.0002
    assert positions["SupplierThickness"] == pytest.approx(
        (0.1315 - od_rim - 0.018 - shelf - 0.0227354 / 2.0, 0.1335)
    )
    assert positions["SupplierFreeHeight"] == pytest.approx(
        (0.1315 + od_rim + 0.018 + shelf + 0.0227354 / 2.0, 0.1335)
    )
    od_gap = od_rim + 0.003556 + 0.000381 + 0.002 + 0.0002
    id_gap = max(od_rim + 0.0035 + 0.0002, id_rim + 0.003556 + 0.000381 + 0.0022)
    assert od_gap == pytest.approx(0.018837) and id_gap == pytest.approx(0.0164)
    assert positions["SupplierOD"] == pytest.approx(
        (0.1315 + od_gap + 0.0435062 / 2.0, 0.227)
    )
    assert positions["SupplierID"] == pytest.approx(
        (0.1315 - id_gap - 0.0435062 / 2.0, 0.227)
    )
    # The heights land exactly on the native shelves, the ID within 0.06 mm,
    # the OD 0.54 mm farther out than the ec339f3d/d179e35b seat.
    for name in ("SupplierThickness", "SupplierFreeHeight"):
        assert positions[name] == pytest.approx(NATIVE_POSITIONS[name], abs=1e-7)
    assert positions["SupplierID"][0] == pytest.approx(0.0932934, abs=6e-5)
    assert positions["SupplierOD"][0] - 0.1715474 == pytest.approx(0.000543, abs=1e-5)
    # Scale, not constants: at 1:1 the stations close in by half the OD.
    unit = _positions(scale=1.0)
    for name, side in drawing.TEXT_SIDES["free_front"].items():
        assert unit[name][0] == pytest.approx(
            positions[name][0] - side * spec.OD / 2000.0
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


def test_fixed_texts_fit_the_top_cell() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing
    from _supplier_spring_drawing import supplier_state_cells

    cells = {key: cell for key, _, cell in supplier_state_cells(0.0, maximum=False)}
    x0, _y0, x1, _y1 = cells["free_top"]
    for name in drawing.TEXT_SIDES["free_top"]:
        text = _text_box(drawing, name, _positions()[name])
        assert x0 < text.xmin and text.xmax < x1


@pytest.mark.parametrize("refused", [False, True], ids=["placed", "refused"])
def test_each_size_text_is_one_position_write_inside_one_span(
    monkeypatch, refused
) -> None:
    """Heights enter offset mode and diameters take the near-side style
    before any write; each text then gets exactly one SetPosition2, at its
    fixed position, with no rebuild or readback of its own."""
    import _telemetry
    import draw_dt_vn_cylinder_bank_spring as drawing

    spans, calls = [], []

    @contextlib.contextmanager
    def span(name, **_attributes):
        spans.append(name)
        try:
            yield None
        finally:
            spans.append(f"/{name}")

    class Display(SimpleNamespace):
        def __setattr__(self, key, value):
            if key == "OffsetText":
                calls.append(("offset", self.name, value))
            super().__setattr__(key, value)

        def GetAnnotation(self):
            return self

    def write(display):
        def set_position(x, y, _z):
            calls.append(("write", display.name, (x, y), list(spans)))
            return not refused

        return SimpleNamespace(SetPosition2=set_position)

    displays = {name: Display(name=name) for name in NATIVE_POSITIONS}
    monkeypatch.setattr(_telemetry, "span", span)
    monkeypatch.setattr(drawing, "_size_displays", lambda _a, _v: displays)
    monkeypatch.setattr(drawing, "_view_scale", lambda _view: 2.0)
    monkeypatch.setattr(
        drawing,
        "set_near_side_diameter",
        lambda annotation, _label: calls.append(("near side", annotation.name)),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda display, _kind: write(display))
    bounds = {"free_front": FRONT_BOUNDS, "free_top": PLAN_BOUNDS}
    name = "drawing.cylinder_bank_spring.size_texts"

    def place():
        drawing.place_size_texts(
            object(), dict.fromkeys(bounds), reference_bounds=bounds.__getitem__
        )

    if refused:
        with pytest.raises(RuntimeError, match="text placement was rejected"):
            place()
        assert spans == [name, f"/{name}"]
        return
    place()
    assert spans == [name, f"/{name}"]
    styles = [call for call in calls if call[0] != "write"]
    writes = [call for call in calls if call[0] == "write"]
    assert (
        calls[: len(styles)]
        == styles
        == [
            ("offset", "SupplierThickness", True),
            ("offset", "SupplierFreeHeight", True),
            ("near side", "SupplierID"),
            ("near side", "SupplierOD"),
        ]
    )
    assert len(writes) == 4 and all(inside == [name] for *_, inside in writes)
    expected = _positions()
    for _, label, xy, _ in writes:
        assert xy == pytest.approx(expected[label])


def test_installation_note_fits_the_sheet() -> None:
    lines = _config.parts(STEM)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
