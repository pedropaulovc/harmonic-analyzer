"""Offline contracts for the MHA-DT-VN-68 cylinder bank spring (McMaster 9714K392)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path

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


# Native size records of the b344192 sheet (layout audit of farm run
# 20261023T181332674Z), the state machinist review returned FIX on. Metres.
def _native_record(name, pos, lines, texts, arrows):
    return {
        "type": 4,
        "name": name,
        "pos": [*pos, 0.0],
        "display": {
            "lines": [
                [0.0, 0.0, 0.0, 0.0, x0, y0, 0.0, x1, y1, 0.0]
                for x0, y0, x1, y1 in lines
            ],
            "texts": [
                {
                    "t": t,
                    "pos": [x, y, 0.0],
                    "h": 0.0035,
                    "ref": 1,
                    "ang": 0.0,
                    "font": "Century Gothic",
                    "ls": 0.001,
                    "w": w,
                }
                for t, x, y, w in texts
            ],
            "arrows": [
                [x, y, 0.0, dx, dy, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0]
                for x, y, dx, dy in arrows
            ],
        },
    }


B344192 = {
    "SupplierThickness": _native_record(
        "SupplierThickness",
        (0.1008, 0.1335),
        [
            (0.1305, 0.133373, 0.0998, 0.133373),
            (0.1305, 0.133627, 0.0998, 0.133627),
            (0.1008, 0.133373, 0.1008, 0.127023),
            (0.1008, 0.133627, 0.1008, 0.139977),
        ],
        [(" (0.005 in) ", 0.0894323, 0.1307219, 0.0227354)],
        [(0.1008, 0.133373, 0.0, -1.0), (0.1008, 0.133627, 0.0, 1.0)],
    ),
    "SupplierFreeHeight": _native_record(
        "SupplierFreeHeight",
        (0.1622, 0.1335),
        [
            (0.1198, 0.13223, 0.1632, 0.13223),
            (0.1198, 0.13477, 0.1632, 0.13477),
            (0.1622, 0.13223, 0.1622, 0.12588),
            (0.1622, 0.13477, 0.1622, 0.14112),
        ],
        [(" (0.050 in) ", 0.1508323, 0.1307219, 0.0227354)],
        [(0.1622, 0.13223, 0.0, -1.0), (0.1622, 0.13477, 0.0, 1.0)],
    ),
    "SupplierID": _native_record(
        "SupplierID",
        (0.1008, 0.227),
        [
            (0.122362, 0.223517, 0.124141, 0.224195),
            (0.140638, 0.230483, 0.122362, 0.223517),
        ],
        [
            (" (", 0.0790469, 0.2242486, 0.0030139),
            ("<MOD-DIAM>", 0.0820608, 0.2241951, 0.0052784),
            ("0.385 \u00b10.010 in) ", 0.0873392, 0.2242486, 0.0352139),
        ],
        [(0.1223622, 0.2235173, -0.9344335, -0.3561377)],
    ),
    "SupplierOD": _native_record(
        "SupplierOD",
        (0.1622, 0.227),
        [
            (0.143367, 0.222477, 0.138859, 0.224195),
            (0.119633, 0.231523, 0.143367, 0.222477),
        ],
        [
            (" (", 0.1404469, 0.2242486, 0.0030139),
            ("<MOD-DIAM>", 0.1434608, 0.2241951, 0.0052784),
            ("0.500 \u00b10.010 in) ", 0.1487392, 0.2242486, 0.0352139),
        ],
        [(0.1433673, 0.2224771, 0.9344335, -0.3561377)],
    ),
}
# The full OD line ran rim to rim through the plan centre at (0.1315, 0.227).
B344192_PLAN = (0.1315 - 0.0127, 0.227 - 0.0127, 0.1315 + 0.0127, 0.227 + 0.0127)


def _segments(name):
    return [
        ((line[4], line[5]), (line[7], line[8]))
        for line in B344192[name]["display"]["lines"]
    ]


def _cell_x(key):
    from _supplier_spring_drawing import supplier_state_cells

    cell = next(
        cell
        for name, _, cell in supplier_state_cells(0.05, maximum=False)
        if name == key
    )
    return cell[0], cell[2]


def _moved(box, dx):
    from _layout_geometry import Box

    return Box(box.xmin + dx, box.ymin, box.xmax + dx, box.ymax)


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
        return "placement check"

    monkeypatch.setattr(drawing, "supplier_disc_spring_dimensions", shared)
    monkeypatch.setattr(drawing, "place_size_texts", place)
    supplier_dimensions(object(), {}, reference_bounds=lambda key: (0, 0, 1, 1))
    assert calls == ["shared", "place"]
    assert seen["settled_checks"] == ["shared check", "placement check"]


@pytest.mark.parametrize("name", ["SupplierThickness", "SupplierFreeHeight"])
def test_b344192_struck_height_text_shelves_clear_of_its_own_lines(name) -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing
    from _supplier_screw_layout import supplier_top_text_geometry

    side = drawing.TEXT_SIDES["free_front"][name]
    geometry = supplier_top_text_geometry(B344192[name], horizontal=False)
    with pytest.raises(RuntimeError, match="from its own native lines"):
        drawing.assert_height_text_clear(geometry, side, label=name)
    shifted = {
        **geometry,
        "text": _moved(geometry["text"], drawing.height_text_shift(geometry, side)),
    }
    drawing.assert_height_text_clear(shifted, side, label=name)
    left, right = _cell_x("free_front")
    assert left < shifted["text"].xmin and shifted["text"].xmax < right
    # Shelved away from the 2:1 OD x free-height envelope, never back across it.
    diagram = (0.1315 - 0.0127, 0.1315 + 0.0127)
    if side < 0:
        assert shifted["text"].xmax < diagram[0]
    else:
        assert shifted["text"].xmin > diagram[1]


@pytest.mark.parametrize("name", ["SupplierID", "SupplierOD"])
def test_b344192_rim_diameter_text_moves_a_text_height_clear(name) -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing
    from _layout_audit import display_box

    side = drawing.TEXT_SIDES["free_top"][name]
    text = display_box({"texts": B344192[name]["display"]["texts"]})
    with pytest.raises(RuntimeError, match="under a text height"):
        drawing.assert_diameter_text_clear(text, B344192_PLAN, side, label=name)
    moved = _moved(text, drawing.diameter_text_shift(text, B344192_PLAN, side))
    drawing.assert_diameter_text_clear(moved, B344192_PLAN, side, label=name)
    assert drawing.diameter_air(text) == pytest.approx(0.0035, abs=5e-4)
    left, right = _cell_x("free_top")
    assert left < moved.xmin and moved.xmax < right


def test_plan_leaders_refuse_lines_through_the_centre() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    crossing = {name: _segments(name) for name in ("SupplierID", "SupplierOD")}
    with pytest.raises(RuntimeError, match="leaders not clear"):
        drawing.assert_plan_leaders(crossing, B344192_PLAN, label="b344192")
    centre_y = 0.227
    near_side = {
        # Text shelf, then one leader to the rim nearest the text.
        "SupplierID": [
            ((0.0716, centre_y), (0.1151, centre_y)),
            ((0.1151, centre_y), (0.1315 - 0.0127 * spec.ID / spec.OD, centre_y)),
        ],
        "SupplierOD": [
            ((0.1914, centre_y), (0.1479, centre_y)),
            ((0.1479, centre_y), (0.1315 + 0.0127, centre_y)),
        ],
    }
    drawing.assert_plan_leaders(near_side, B344192_PLAN, label="near side")


def test_settled_heights_refuse_a_moved_native_station() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing
    from _supplier_screw_layout import supplier_top_text_geometry

    geometry = supplier_top_text_geometry(
        B344192["SupplierThickness"], horizontal=False
    )
    assert drawing.stations_match(geometry, geometry)
    tips = tuple((x + 1e-4, y) for x, y in geometry["tips"])
    assert not drawing.stations_match(geometry, {**geometry, "tips": tips})


# Native size records of farm run 20261023T190403512Z-86053b8e (head 1325aeba):
# the placed state. SupplierOD's first line is the stray: OD rim at the text's
# height, parallel to its leader, through its own "(".
_DIAMETER_TEXT_ROWS = ((" (", 0.0030139), ("<MOD-DIAM>", 0.0052784))


def _diameter_texts(x, value):
    """The three native runs of a "(Ø... in)" text, laid end to end from ``x``."""
    rows = []
    for text, width in (*_DIAMETER_TEXT_ROWS, (value, 0.0352139)):
        rows.append((text, x, 0.2242486, width))
        x += width
    return rows


R86053 = {
    "SupplierThickness": _native_record(
        "SupplierThickness",
        (0.0862323, 0.1335),
        [
            (0.1305, 0.133373, 0.0998, 0.133373),
            (0.1305, 0.133627, 0.0998, 0.133627),
            (0.1008, 0.133373, 0.1008, 0.127023),
            (0.1008, 0.133627, 0.1008, 0.139977),
            (0.1008, 0.1335, 0.0976, 0.130722),
            (0.0976, 0.130722, 0.074865, 0.130722),
        ],
        [(" (0.005 in) ", 0.0748646, 0.1307219, 0.0227354)],
        [(0.1008, 0.133373, 0.0, -1.0), (0.1008, 0.133627, 0.0, 1.0)],
    ),
    "SupplierFreeHeight": _native_record(
        "SupplierFreeHeight",
        (0.1767677, 0.1335),
        [
            (0.1198, 0.13223, 0.1632, 0.13223),
            (0.1198, 0.13477, 0.1632, 0.13477),
            (0.1622, 0.13223, 0.1622, 0.12588),
            (0.1622, 0.13477, 0.1622, 0.14112),
            (0.1622, 0.1335, 0.1654, 0.130722),
            (0.1654, 0.130722, 0.188135, 0.130722),
        ],
        [(" (0.050 in) ", 0.1654, 0.1307219, 0.0227354)],
        [(0.1622, 0.13223, 0.0, -1.0), (0.1622, 0.13477, 0.0, 1.0)],
    ),
    "SupplierID": _native_record(
        "SupplierID",
        (0.0932934, 0.227),
        [
            (0.1218905, 0.2251869, 0.116634, 0.224195),
            (0.116634, 0.224195, 0.07154, 0.224195),
        ],
        _diameter_texts(0.0715403, "0.385 \u00b10.010 in) "),
        [(0.1218905, 0.2251869, -0.9826622, -0.1854051)],
    ),
    "SupplierOD": _native_record(
        "SupplierOD",
        (0.1697066, 0.227),
        [
            (0.1442, 0.227, 0.190346, 0.218293),
            (0.1439798, 0.2246454, 0.146366, 0.224195),
            (0.146366, 0.224195, 0.19146, 0.224195),
        ],
        _diameter_texts(0.1479535, "0.500 \u00b10.010 in) "),
        [(0.1439798, 0.2246454, 0.9826622, -0.1854051)],
    ),
}


def _without_stray(records):
    import copy

    clean = copy.deepcopy(records)
    del clean["SupplierOD"]["display"]["lines"][0]
    return clean


def test_86053_stray_od_line_is_refused_by_both_settled_guards() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    struck = drawing.lines_through_own_text(R86053)
    assert len(struck) == 1 and "SupplierOD" in struck[0]
    assert drawing.stray_leader_lines(R86053["SupplierOD"]) == [
        (0.1442, 0.227, 0.190346, 0.218293)
    ]
    assert drawing.stray_leader_lines(R86053["SupplierID"]) == []


def test_86053_placement_without_the_stray_passes_the_own_text_guard() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    clean = _without_stray(R86053)
    assert drawing.lines_through_own_text(clean) == []
    assert drawing.stray_leader_lines(clean["SupplierOD"]) == []


def test_own_text_guard_catches_the_b344192_struck_heights() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    struck = drawing.lines_through_own_text(B344192)
    assert any("SupplierThickness" in detail for detail in struck)
    assert any("SupplierFreeHeight" in detail for detail in struck)


def test_diameters_turn_the_arc_extension_off_before_the_text_move() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("def place_size_texts(") :]
    off = body.index("ArcExtensionLineOrOppositeSide = False")
    assert body.index("set_near_side_diameter(") < off < body.index("rebuild_drawing(")


def test_installation_note_fits_the_sheet() -> None:
    lines = _config.parts(STEM)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
