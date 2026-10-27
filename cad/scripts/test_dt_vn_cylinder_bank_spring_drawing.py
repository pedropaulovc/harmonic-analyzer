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
    rim = B344192_PLAN[0 if side < 0 else 2]
    shift = drawing.diameter_text_shift(text, B344192_PLAN, side, arrow_reach=rim)
    moved = _moved(text, shift)
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
    """The pre-mutation b344192 stations are the baseline every stage, and the
    settled check, compare against with the shared supplier-Top checker."""
    import copy

    import draw_dt_vn_cylinder_bank_spring as drawing

    baseline = drawing.height_stations(B344192)
    for placed in (R86053, P4):
        drawing.assert_height_stations(placed, baseline)
    moved = copy.deepcopy(P4)
    for line in moved["SupplierThickness"]["display"]["lines"][2:4]:
        line[4] += 1e-4
        line[7] += 1e-4
    for arrow in moved["SupplierThickness"]["display"]["arrows"]:
        arrow[0] += 1e-4
    with pytest.raises(
        RuntimeError, match="SupplierThickness: supplier Top shelf moved native"
    ):
        drawing.assert_height_stations(moved, baseline)


# Native size records of farm run 20261023T190403512Z-86053b8e (head 1325aeba):
# the placed state. SupplierOD's first line is the stray: from the OD rim's
# 0 deg point (0.1442, 0.227), parallel to its leader, through its own "(".
# Pass 2 (run 20261023T200224785Z-27c25caf, head 2308c23d, cyl-pass2.task.log)
# refused the identical stray, (0.1442, 0.227, 0.1903462, 0.2182933), with
# ArcExtensionLineOrOppositeSide False read back.
_DIAMETER_TEXT_ROWS = ((" (", 0.0030139), ("<MOD-DIAM>", 0.0052784))


def _diameter_texts(x, value, y=0.2242486):
    """The three native runs of a "(Ø... in)" text, laid end to end from ``x``."""
    rows = []
    for text, width in (*_DIAMETER_TEXT_ROWS, (value, 0.0352139)):
        rows.append((text, x, y, width))
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


# Native size records of pass 4, farm run 20261023T203408226Z-6bb26ab5 (head
# 33ec8552), where "as placed" won and the OD printed no stray.
P4 = {
    "SupplierThickness": _native_record(
        "SupplierThickness",
        (0.0862323, 0.1335),
        [
            (0.1305, 0.133373, 0.0998, 0.133373),
            (0.1305, 0.133627, 0.0998, 0.133627),
            (0.1008, 0.133373, 0.1008, 0.127023),
            (0.1008, 0.133627, 0.1008, 0.139977),
            (0.1008, 0.1335, 0.0976, 0.1307219),
            (0.0976, 0.1307219, 0.0748646, 0.1307219),
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
            (0.1622, 0.1335, 0.1654, 0.1307219),
            (0.1654, 0.1307219, 0.1881354, 0.1307219),
        ],
        [(" (0.050 in) ", 0.1654, 0.1307219, 0.0227354)],
        [(0.1622, 0.13223, 0.0, -1.0), (0.1622, 0.13477, 0.0, 1.0)],
    ),
    "SupplierID": _native_record(
        "SupplierID",
        (0.0932934, 0.227),
        [
            (0.1218905, 0.2251869, 0.116634, 0.2241951),
            (0.116634, 0.2241951, 0.0715403, 0.2241951),
        ],
        _diameter_texts(0.0715403, "0.385 \u00b10.010 in) "),
        [(0.1218905, 0.2251869, -0.9826622, -0.1854051)],
    ),
    "SupplierOD": _native_record(
        "SupplierOD",
        (0.1697066, 0.227),
        [
            (0.1439798, 0.2246454, 0.146366, 0.2241951),
            (0.146366, 0.2241951, 0.1914597, 0.2241951),
        ],
        _diameter_texts(0.1479535, "0.500 \u00b10.010 in) "),
        [(0.1439798, 0.2246454, 0.9826622, -0.1854051)],
    ),
}


def _od_with(*extra):
    import copy

    od = copy.deepcopy(P4["SupplierOD"])
    od["display"]["lines"].extend(
        [0.0, 0.0, 0.0, 0.0, x0, y0, 0.0, x1, y1, 0.0] for x0, y0, x1, y1 in extra
    )
    return od


_OD_TIP = (0.1439798, 0.2246454)
_OD_SHOULDER_END = (0.1914597, 0.2241951)


def _seated(record, side=1):
    """SYNTHETIC: ``record`` with its text moved by the seat move, its shoulder
    and leg end following; the arrow stays (natively it re-aims radially, a
    0.06 mm change the seating loop's read-back absorbs)."""
    import copy

    import draw_dt_vn_cylinder_bank_spring as drawing

    dx, _ = drawing.diameter_seat_move(record, B344192_PLAN, side, level=False)
    moved = copy.deepcopy(record)
    display = moved["display"]
    (arrow,) = display["arrows"]
    moved["pos"][0] += dx
    for run in display["texts"]:
        run["pos"][0] += dx
    for line in display["lines"]:
        for x, y in ((4, 5), (7, 8)):
            if math.dist((line[x], line[y]), arrow[:2]) > 1e-7:
                line[x] += dx
    return moved


def _p4_seated():
    """Pass 4 with its OD text on the arrowhead-aware target."""
    return {**P4, "SupplierOD": _seated(P4["SupplierOD"])}


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
    heights = ("SupplierThickness", "SupplierFreeHeight")
    assert len(drawing.lines_through_own_text(B344192, heights)) >= 2


def test_pass3_refusal_was_the_heights_alone_calibration_not_the_ink() -> None:
    """Run 054fe692 (head 519ba8a5) refused the shelved thickness with exactly
    this detail. The heights were shelved by the same -14.57 mm as on run
    86053b8e, whose sheet audit passed them: calibrated on the height texts
    alone (no exact width sample, so the 0.62 default) the guard boxes the
    text past its native width onto its own offset leg."""
    import draw_dt_vn_cylinder_bank_spring as drawing

    clean = _without_stray(R86053)
    heights = ("SupplierThickness", "SupplierFreeHeight")
    alone = {name: clean[name] for name in heights}
    assert drawing.lines_through_own_text(alone) == [
        "extension line of \"dim SupplierThickness '(0.005 in)'\" (100.8,133.5)->(97.6,130.7)mm "
        "runs 0.93mm through its own text [77.0,130.7]..[98.7,134.2]mm"
    ]
    assert drawing.lines_through_own_text(clean, heights) == []
    # The native width ends exactly where SolidWorks starts the offset leg.
    thickness = clean["SupplierThickness"]["display"]
    (run,) = thickness["texts"]
    assert run["pos"][0] + run["w"] == pytest.approx(
        thickness["lines"][-1][4], abs=1e-6
    )


def test_pass2_stray_is_the_86053_line_and_still_off_chain() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    (stray,) = drawing.stray_leader_lines(R86053["SupplierOD"])
    assert stray == pytest.approx((0.1442, 0.227, 0.1903462, 0.2182933), abs=1e-6)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "ArcExtensionLineOrOppositeSide =" not in source


# Candidate (a) at 2:1, built from the 86053 OD: shoulder moved up 2.805 mm to
# the centre height, so the arrow lands on the rim's 0 deg point and its leg
# runs level into the shoulder. SYNTHETIC: the stray is the 86053 stray (same
# start, same 46.96 mm length) turned level with the leader, as the run's
# "parallel to its leader" observation predicts; only a native run proves it.
_LEVEL = 0.227
_STRAY_LENGTH = math.hypot(0.190346 - 0.1442, 0.218293 - 0.227)


def _level_od(stray):
    return _native_record(
        "SupplierOD",
        (0.1697066, 0.229805),
        [
            stray,
            (0.1442, _LEVEL, 0.146366, _LEVEL),
            (0.146366, _LEVEL, 0.19146, _LEVEL),
        ],
        _diameter_texts(0.1479535, "0.500 \u00b10.010 in) ", y=0.2270536),
        [(0.1442, _LEVEL, 1.0, 0.0)],
    )


LEVEL_STRAY = (0.1442, _LEVEL, 0.1442 + _STRAY_LENGTH, _LEVEL)


def test_a_level_stray_inside_the_leader_ink_is_on_chain() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    od = _seated(_level_od(LEVEL_STRAY))
    assert drawing.stray_leader_lines(od) == []
    assert drawing.shoulder_y(od) == pytest.approx(_LEVEL)
    records = {**_without_stray(R86053), "SupplierOD": od}
    assert drawing.lines_through_own_text(records) == []
    drawing.assert_diameter_ink(od, B344192_PLAN, 1, label="level OD")


@pytest.mark.parametrize(
    "stray",
    [
        # Collinear but past the shoulder's end.
        (0.1442, _LEVEL, 0.1935, _LEVEL),
        # Parallel, 0.5 mm off the leader: a second stroke.
        (0.1442, _LEVEL + 0.0005, 0.19116, _LEVEL + 0.0005),
        # The 86053 slope from the same 0 deg point, now sharing the arrow tip.
        (0.1442, _LEVEL, 0.190346, 0.218293),
    ],
    ids=["overruns", "offset", "branch"],
)
def test_level_candidate_still_refuses_lines_that_print_apart(stray) -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    with pytest.raises(RuntimeError, match="off its leader chain"):
        drawing.assert_diameter_ink(_level_od(stray), B344192_PLAN, 1, label="level OD")


def test_seat_move_levels_the_shoulder_on_the_plan_centre() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    od = R86053["SupplierOD"]
    dx, dy = drawing.diameter_seat_move(od, B344192_PLAN, 1, level=True)
    assert dy == pytest.approx(0.227 - 0.224195)
    # Pass 2 seated it a text height off the rim; its own arrowhead now rules.
    from _drawing_annotation_extent import PLACE_SETTLE_M
    from _layout_geometry import ARROW_TEXT_CLEARANCE_M

    reach = drawing.arrow_reach(od, 1) + ARROW_TEXT_CLEARANCE_M + PLACE_SETTLE_M
    assert dx == pytest.approx(reach - drawing.size_text_box(od).xmin)
    assert dx > 1e-3
    assert drawing.diameter_seat_move(od, B344192_PLAN, 1, level=False)[1] == 0.0
    dx, _ = drawing.diameter_seat_move(od, B344192_PLAN, -1, level=False)
    text = drawing.display_box({"texts": od["display"]["texts"]})
    drawing.assert_diameter_text_clear(
        _moved(text, dx), B344192_PLAN, -1, label="OD left"
    )


def test_diameter_ink_refuses_a_leader_short_of_its_text_or_leaving_the_cell(
    monkeypatch,
) -> None:
    import copy

    import draw_dt_vn_cylinder_bank_spring as drawing

    clean = _seated(_without_stray(R86053)["SupplierOD"])
    drawing.assert_diameter_ink(clean, B344192_PLAN, 1, label="OD")
    short = copy.deepcopy(clean)
    del short["display"]["lines"][1]
    with pytest.raises(RuntimeError, match="does not reach its text"):
        drawing.assert_diameter_ink(short, B344192_PLAN, 1, label="OD")
    # The shoulder already ends at the text, so narrow the cell under it instead.
    x0, y0, _x1, y1 = drawing.FREE_TOP_CELL
    monkeypatch.setattr(drawing, "FREE_TOP_CELL", (x0, y0, 0.190, y1))
    with pytest.raises(RuntimeError, match="leaves the TOP cell"):
        drawing.assert_diameter_ink(clean, B344192_PLAN, 1, label="OD")


def test_free_top_cell_is_the_finalizers_outer_cell_for_any_caption() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing
    from _supplier_spring_drawing import supplier_state_cells

    for caption_y in (0.03, 0.05, 0.08):
        cells = {
            key: cell for key, _, cell in supplier_state_cells(caption_y, maximum=False)
        }
        assert cells["free_top"] == drawing.FREE_TOP_CELL


def test_plan_placements_are_tried_in_the_agreed_order() -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    od, id_ = drawing.OD_NAME, drawing.ID_NAME
    assert [
        (p.label, dict(p.sides), set(p.level)) for p in drawing.PLAN_PLACEMENTS
    ] == [
        ("as placed", {id_: -1, od: 1}, set()),
        ("OD leader level at 0 deg", {id_: -1, od: 1}, {od}),
        ("sides swapped", {id_: 1, od: -1}, set()),
        ("sides swapped, OD leader level at 180 deg", {id_: 1, od: -1}, {od}),
    ]


def _scripted_placement(monkeypatch, verdicts):
    import draw_dt_vn_cylinder_bank_spring as drawing

    seated, checked = [], []
    monkeypatch.setattr(
        drawing,
        "_seat_diameters",
        lambda _a, _d, _p, placement: seated.append(placement.label) or {},
    )

    def check(_records, _plan, placement):
        checked.append(placement.label)
        if not verdicts[placement.label]:
            raise RuntimeError("lines off its leader chain")

    monkeypatch.setattr(drawing, "_assert_diameters", check)
    return drawing, seated, checked


def test_the_first_placement_whose_guards_pass_wins(monkeypatch) -> None:
    import draw_dt_vn_cylinder_bank_spring as module

    labels = [placement.label for placement in module.PLAN_PLACEMENTS]
    drawing, seated, checked = _scripted_placement(
        monkeypatch, dict(zip(labels, (False, False, True, True)))
    )
    won = drawing.choose_plan_placement(object(), {}, B344192_PLAN)
    assert won.label == "sides swapped"
    assert seated == checked == labels[:3]


def test_no_passing_placement_refuses_the_sheet(monkeypatch) -> None:
    import draw_dt_vn_cylinder_bank_spring as module

    labels = [placement.label for placement in module.PLAN_PLACEMENTS]
    drawing, _seated, checked = _scripted_placement(
        monkeypatch, dict.fromkeys(labels, False)
    )
    with pytest.raises(RuntimeError, match="no plan diameter placement") as refused:
        drawing.choose_plan_placement(object(), {}, B344192_PLAN)
    assert checked == labels
    assert all(label in str(refused.value) for label in labels)


def _offset_displays(on=True):
    from types import SimpleNamespace

    return {
        name: SimpleNamespace(OffsetText=on)
        for name in ("SupplierThickness", "SupplierFreeHeight")
    }


def test_pass4_od_arrowhead_crowds_its_text_until_the_text_is_seated() -> None:
    """Review 4364351776: pass 4's OD arrowhead base is 0.41 mm from its text,
    under the fleet's 2 mm arrow-to-text clearance. The arrowhead-aware target
    moves the text 1.79 mm out, still inside the TOP cell. One snapshot serves
    both checks; neither reads COM (no adapter given)."""
    import draw_dt_vn_cylinder_bank_spring as drawing

    baseline = drawing.height_stations(B344192)
    as_placed = drawing.PLAN_PLACEMENTS[0]
    with pytest.raises(
        RuntimeError, match=r"SupplierOD: own arrowhead 0\.41 mm from its text"
    ):
        drawing._assert_diameters(P4, B344192_PLAN, as_placed)
    dx, dy = drawing.diameter_seat_move(P4["SupplierOD"], B344192_PLAN, 1, level=False)
    assert (dx, dy) == (pytest.approx(0.00179, abs=1e-5), 0.0)
    seated = _p4_seated()
    drawing._assert_heights(_offset_displays(), seated, baseline)
    drawing._assert_diameters(seated, B344192_PLAN, as_placed)
    assert drawing.size_text_box(seated["SupplierOD"]).xmax < drawing.FREE_TOP_CELL[2]
    # The ID's own arrowhead points away from its text: already 3.3 mm clear.
    drawing.assert_own_arrows_clear(
        P4["SupplierID"], drawing.size_text_box(P4["SupplierID"]), label="ID"
    )
    with pytest.raises(RuntimeError, match="lines off its leader chain"):
        drawing._assert_diameters(R86053, B344192_PLAN, as_placed)
    with pytest.raises(RuntimeError, match="offset text was lost"):
        drawing._assert_heights(_offset_displays(False), seated, baseline)


def test_unreported_text_widths_fall_back_to_the_calibrated_estimate(
    monkeypatch,
) -> None:
    """Review 4364351784: a run without a native width is estimated, not fatal."""
    import copy
    from types import SimpleNamespace

    import draw_dt_vn_cylinder_bank_spring as drawing

    seated = _p4_seated()
    unmeasured = copy.deepcopy(seated)
    for record in unmeasured.values():
        for run in record["display"]["texts"]:
            del run["w"]
    monkeypatch.setattr(
        drawing, "_Reader", lambda _adapter: SimpleNamespace(take_errors=list)
    )
    for name, record in unmeasured.items():
        monkeypatch.setattr(
            drawing, "_dump_annotation", lambda _reader, _note, record=record: record
        )
        display = SimpleNamespace(GetAnnotation=lambda: None)
        assert drawing._text_record(object(), display, label=name) is record
    od, bare = seated["SupplierOD"], unmeasured["SupplierOD"]
    assert drawing.widths_measured(od) and not drawing.widths_measured(bare)
    # Measured: the native widths end the box; unmeasured: the run positions
    # still fix its start, so the OD's arrow-side edge and seat are unchanged.
    (*_, last) = od["display"]["texts"]
    assert drawing.size_text_box(od).xmax == pytest.approx(last["pos"][0] + last["w"])
    assert drawing.size_text_box(bare).xmin == drawing.size_text_box(od).xmin
    dx, _ = drawing.diameter_seat_move(bare, B344192_PLAN, 1, level=False)
    assert abs(dx) <= drawing._SEATED_M
    assert drawing.leader_chain(bare)[0] == drawing.leader_chain(od)[0]
    drawing._assert_diameters(unmeasured, B344192_PLAN, drawing.PLAN_PLACEMENTS[0])
    drawing.height_stations(unmeasured)
    # The fallback keeps refusing what the measured path refuses.
    stray = copy.deepcopy(R86053)
    for record in stray.values():
        for run in record["display"]["texts"]:
            del run["w"]
    with pytest.raises(RuntimeError, match="lines off its leader chain"):
        drawing.assert_diameter_ink(stray["SupplierOD"], B344192_PLAN, 1, label="OD")


@pytest.mark.parametrize(
    "extra",
    [
        # A stroke joined to the shoulder's far end.
        ((*_OD_SHOULDER_END, 0.1950, 0.2200),),
        # The shoulder run on, collinear, past the text.
        ((*_OD_SHOULDER_END, 0.1935, 0.2241951),),
        # A stray in three pieces chained on from the shoulder end.
        (
            (*_OD_SHOULDER_END, 0.1960, 0.2230),
            (0.1960, 0.2230, 0.2000, 0.2220),
            (0.2000, 0.2220, 0.2040, 0.2210),
        ),
        # A stray from the arrow tip in four pieces, longer than the leader.
        (
            (*_OD_TIP, 0.1587, 0.2219),
            (0.1587, 0.2219, 0.1735, 0.2191),
            (0.1735, 0.2191, 0.1882, 0.2163),
            (0.1882, 0.2163, 0.2029, 0.2135),
        ),
    ],
    ids=[
        "joined-to-shoulder-end",
        "past-shoulder",
        "split-after-shoulder",
        "split-from-tip",
    ],
)
def test_leader_chain_runs_arrow_to_shoulder_and_refuses_every_other_stroke(
    extra,
) -> None:
    import draw_dt_vn_cylinder_bank_spring as drawing

    od = _od_with(*extra)
    chain, _rest = drawing.leader_chain(od)
    assert chain == drawing.leader_chain(P4["SupplierOD"])[0]
    assert drawing.stray_leader_lines(od) == [pytest.approx(stroke) for stroke in extra]
    with pytest.raises(RuntimeError, match="lines off its leader chain"):
        drawing.assert_diameter_ink(od, B344192_PLAN, 1, label="OD")


def _scripted_seating(monkeypatch, settles_after):
    import draw_dt_vn_cylinder_bank_spring as drawing

    reads, moves = [], []
    monkeypatch.setattr(drawing, "_size_records", lambda _a, _d: reads.append(1) or P4)
    monkeypatch.setattr(
        drawing,
        "diameter_seat_move",
        lambda *_args, **_kwargs: (
            (0.0, 0.0) if len(reads) > settles_after else (1e-3, 0.0)
        ),
    )
    monkeypatch.setattr(
        drawing, "_move_text", lambda _d, _r, dx, dy, *, label: moves.append(label)
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    return drawing, reads, moves


def test_a_placement_settling_on_its_last_permitted_move_is_read_back(
    monkeypatch,
) -> None:
    import draw_dt_vn_cylinder_bank_spring as module

    # Settles only on the read after the last permitted move.
    drawing, reads, moves = _scripted_seating(monkeypatch, module._SEAT_PASSES)
    displays = dict.fromkeys(("SupplierID", "SupplierOD"))
    snapshot = drawing._seat_diameters(
        object(), displays, B344192_PLAN, drawing.PLAN_PLACEMENTS[0]
    )
    assert snapshot is P4
    assert len(reads) == drawing._SEAT_PASSES + 1
    assert len(moves) == 2 * drawing._SEAT_PASSES


def test_a_placement_still_moving_after_its_last_move_is_refused(monkeypatch) -> None:
    drawing, reads, moves = _scripted_seating(monkeypatch, 99)
    displays = dict.fromkeys(("SupplierID", "SupplierOD"))
    with pytest.raises(RuntimeError, match="did not settle"):
        drawing._seat_diameters(
            object(), displays, B344192_PLAN, drawing.PLAN_PLACEMENTS[0]
        )
    assert len(reads) == drawing._SEAT_PASSES + 1
    assert len(moves) == 2 * drawing._SEAT_PASSES


def _ladder(corner, size=2e-4, squares=24):
    """A row of joined squares off ``corner``: exponentially many simple paths."""
    x, y = corner
    strokes = [(x, y, x, y - size)]
    for index in range(squares):
        x0, x1 = x - index * size, x - (index + 1) * size
        strokes += [
            (x0, y, x1, y),
            (x0, y - size, x1, y - size),
            (x1, y, x1, y - size),
        ]
    return strokes


@pytest.mark.parametrize("shoulder", [True, False], ids=["found", "refused"])
def test_leader_chain_search_is_bounded_on_duplicate_and_cyclic_strokes(
    shoulder,
) -> None:
    """Review 4364351792: each endpoint is reached once, shortest first."""
    import time

    import draw_dt_vn_cylinder_bank_spring as drawing

    leg, _shoulder = P4["SupplierOD"]["display"]["lines"]
    ladder = _ladder(_OD_TIP)
    od = _od_with(*[tuple(leg[i] for i in (4, 5, 7, 8))] * 8, *ladder)
    if not shoulder:
        del od["display"]["lines"][1]
    started = time.perf_counter()
    if shoulder:
        chain, _rest = drawing.leader_chain(od)
        assert chain == drawing.leader_chain(P4["SupplierOD"])[0]
        # Duplicates print as the leg; every ladder stroke is stray.
        strays = drawing.stray_leader_lines(od)
        assert strays == [pytest.approx(stroke) for stroke in ladder]
    else:
        with pytest.raises(RuntimeError, match="does not reach its text shoulder"):
            drawing.leader_chain(od)
    assert time.perf_counter() - started < 1.0


@pytest.mark.parametrize("refused", [False, True], ids=["placed", "refused"])
def test_size_text_placement_is_one_operation_span(monkeypatch, refused) -> None:
    """Review 4364351801: every native write and rebuild runs inside the span,
    which closes on success and on refusal alike."""
    from types import SimpleNamespace

    import _telemetry
    import draw_dt_vn_cylinder_bank_spring as drawing

    spans = []

    @contextlib.contextmanager
    def span(name, **_attributes):
        spans.append(name)
        try:
            yield None
        finally:
            spans.append(f"/{name}")

    monkeypatch.setattr(_telemetry, "span", span)
    seated = _p4_seated()
    displays = {
        name: SimpleNamespace(OffsetText=False, GetAnnotation=lambda: None)
        for name in seated
    }
    inside = []
    position = SimpleNamespace(
        SetPosition2=lambda *_p: inside.append(list(spans)) or True
    )
    monkeypatch.setattr(drawing, "_size_displays", lambda _a, _v: displays)
    monkeypatch.setattr(drawing, "_size_records", lambda _a, _d: seated)
    monkeypatch.setattr(drawing, "set_near_side_diameter", lambda *_a: None)
    monkeypatch.setattr(drawing, "_early_bound", lambda *_a: position)
    monkeypatch.setattr(
        drawing, "_move_text", lambda *_a, **_k: inside.append(list(spans))
    )
    monkeypatch.setattr(
        drawing, "rebuild_drawing", lambda _a, *, label: inside.append(list(spans))
    )

    def choose(_adapter, _displays, _plan):
        if refused:
            raise RuntimeError("no plan diameter placement passes its guards")
        return drawing.PLAN_PLACEMENTS[0]

    monkeypatch.setattr(drawing, "choose_plan_placement", choose)
    name = "drawing.cylinder_bank_spring.size_texts"
    place = lambda: drawing.place_size_texts(  # noqa: E731
        object(), {}, reference_bounds=lambda _key: B344192_PLAN
    )
    if refused:
        with pytest.raises(RuntimeError, match="no plan diameter placement"):
            place()
    else:
        place()()
    assert inside and all(seen == [name] for seen in inside)
    assert spans == [name, f"/{name}"]


def test_installation_note_fits_the_sheet() -> None:
    lines = _config.parts(STEM)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
