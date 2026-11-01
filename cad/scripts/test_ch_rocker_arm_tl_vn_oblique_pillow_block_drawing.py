"""AMPEC KP08 pillow block (MHA-CH-06-TL-VN-56) contracts, SolidWorks-free."""

from __future__ import annotations

import ast
import asyncio
import math
import re
from pathlib import Path

import _config
import build_ch_rocker_arm_tl_vn_oblique_pillow_block as part
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_vn_oblique_pillow_block_spec as spec
import draw_ch_rocker_arm_tl_vn_oblique_pillow_block as draw
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout

STEM = "ch-rocker-arm-tl-vn-oblique-pillow-block"
NAME = STEM.replace("-", "_")
ROW = _config.parts(STEM)


def test_registry_row_is_the_purchased_ampec_kp08() -> None:
    assert ROW["number"] == "MHA-CH-06-TL-VN-56"
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER
    assert ROW["supplier_skus"] == [spec.SKU] == ["KP08"]
    assert ROW["material"] == spec.MATERIAL
    assert ROW["tolerance_class"] == "visual_noncritical"
    assert len(ROW["material_specification"]) <= 36  # one MATERIAL-cell line
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }


def test_quantity_is_the_near_and_far_blocks() -> None:
    assert int(ROW["quantity"]) == spec.QUANTITY == len(leadscrew.KP08_S) == 2


def test_bought_dimensions_are_imported_from_c4_not_retyped() -> None:
    assert (
        spec.AXIS_HEIGHT,
        spec.BOLT_SPACING,
        spec.LENGTH,
        spec.HEIGHT,
        spec.BORE_DIA,
        spec.WIDTH,
        spec.HOLE_DIA,
        spec.FOOT_THICK,
    ) == (
        leadscrew.KP08_AXIS_HEIGHT,
        leadscrew.KP08_BOLT_SPACING,
        leadscrew.KP08_LENGTH,
        leadscrew.KP08_HEIGHT,
        leadscrew.KP08_BORE,
        leadscrew.KP08_WIDTH,
        leadscrew.KP08_HOLE_DIA,
        leadscrew.KP08_FOOT_THICK,
    )
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for name in (
        "AXIS_HEIGHT",
        "BOLT_SPACING",
        "LENGTH",
        "HEIGHT",
        "BORE_DIA",
        "WIDTH",
        "HOLE_DIA",
        "FOOT_THICK",
    ):
        assert re.search(rf"^{name} = leadscrew\.KP08_\w+", source, re.M), name


def test_spec_is_pure_data() -> None:
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported <= {"__future__", "math", "ch_rocker_arm_tl_vn_oblique_leadscrew_spec"}


def test_docstring_marks_every_source() -> None:
    doc = spec.__doc__ or ""
    assert "datasheet-built: no vendor CAD obtained (" in doc
    assert spec.SOURCE_URL in doc
    for mark in (
        "SOURCED",
        "FROM C4",
        "UNVERIFIED",
        "ESTIMATED",
        "Part frame",
        "Volume",
    ):
        assert mark in doc, mark


def test_boss_crowns_the_height_on_the_bore_axis() -> None:
    assert spec.AXIS_HEIGHT + spec.BOSS_RADIUS == spec.HEIGHT
    assert spec.HOLE_X == (-spec.BOLT_SPACING / 2.0, spec.BOLT_SPACING / 2.0)
    # The bolt holes pierce only the foot, inside its ends.
    assert spec.BOLT_SPACING / 2.0 - spec.HOLE_DIA / 2.0 > spec.BOSS_RADIUS
    assert spec.BOLT_SPACING / 2.0 + spec.HOLE_DIA / 2.0 < spec.LENGTH / 2.0


def test_outline_is_a_closed_axis_aligned_foot_and_pedestal() -> None:
    outline = spec.BASE_OUTLINE
    for (x0, z0), (x1, z1) in zip(outline, outline[1:] + outline[:1]):
        assert x0 == x1 or z0 == z1
    xs = [x for x, _ in outline]
    zs = [z for _, z in outline]
    assert (min(xs), max(xs)) == (-spec.LENGTH / 2.0, spec.LENGTH / 2.0)
    assert (min(zs), max(zs)) == (0.0, spec.AXIS_HEIGHT)
    # Top Plane sketch (u, v) = model (X, -Z): the block stands above the plane.
    assert part.base_profile_points() == [(x, -z) for x, z in outline]


def _section_contains(x: float, z: float) -> bool:
    r_bore = spec.BORE_DIA / 2.0
    if math.hypot(x, z - spec.AXIS_HEIGHT) < r_bore:
        return False
    in_foot = abs(x) < spec.LENGTH / 2.0 and 0.0 < z < spec.FOOT_THICK
    in_pedestal = abs(x) < spec.BOSS_RADIUS and 0.0 < z < spec.AXIS_HEIGHT
    in_boss = math.hypot(x, z - spec.AXIS_HEIGHT) < spec.BOSS_RADIUS
    return in_foot or in_pedestal or in_boss


def test_closed_form_volume_matches_a_numeric_section() -> None:
    step = 0.1
    nx = round(spec.LENGTH / step)
    nz = round(spec.HEIGHT / step)
    area = (
        step
        * step
        * sum(
            _section_contains(-spec.LENGTH / 2.0 + (i + 0.5) * step, (j + 0.5) * step)
            for i in range(nx)
            for j in range(nz)
        )
    )
    holes = 2.0 * math.pi * (spec.HOLE_DIA / 2.0) ** 2 * spec.FOOT_THICK
    numeric = spec.WIDTH * area - holes
    assert math.isclose(spec.VOLUME_MM3, numeric, rel_tol=2e-3)


def test_builder_publishes_the_bore_axis_in_the_part_frame() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        'name_bore_axis(\n        adapter, "Front Plane", AXIS_HEIGHT, "Right Plane", 0.0,'
        in source
    )
    assert 'name_last_feature(adapter, "ScrewAxis")' in source
    assert source.count("both_directions=True") == 4
    assert 'volume_check(adapter, "pillow block", VOLUME_MM3' in source


def test_note_is_one_short_line_naming_the_end_bracket() -> None:
    note = spec.DRAWING_NOTES
    assert "\n" not in note and len(note) <= 80
    assert note == note.upper()
    assert "MHA-CH-06-TL-28" in note


def test_sheet_is_the_registered_purchased_part_reference(monkeypatch) -> None:
    drawn = DRAWINGS_BY_NAME[NAME]
    assert (drawn.part, drawn.artifact_stem, drawn.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert drawn.layout is DrawingLayout.LANDSCAPE
    calls = []

    async def fake(
        adapter,
        sheet,
        *,
        item,
        cut_to_suit=False,
        number_fit=None,
        supplier_dimensions=None,
        supplier_margins=None,
        settled_checks=(),
    ):
        calls.append((adapter, sheet, item, cut_to_suit, number_fit, supplier_margins))
        assert callable(supplier_dimensions) and len(settled_checks) == 1
        return {"pdf": "x"}

    monkeypatch.setattr(draw, "build_purchased_part_drawing", fake)
    adapter = object()
    assert asyncio.run(draw.build(adapter)) == {"pdf": "x"}
    # The 18-character number is fitted to its DWG. NO. cell, clear of REV.
    assert calls == [
        (
            adapter,
            drawn,
            draw.ITEM,
            False,
            draw.NumberFit.SHRINK_TO_CELL,
            draw.SUPPLIER_MARGINS,
        )
    ]
    assert "KP08" in draw.ITEM


def test_plan_view_carries_the_receipt_check_reference_sizes() -> None:
    """Machinist review: the envelope sheet gave no bolt-hole size or spacing."""
    from _supplier_screw_layout import supplier_screw_lane_plan

    rows = {name: (value, orientation) for name, value, orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    assert rows == {
        "SupplierBoltSpacing": (leadscrew.KP08_BOLT_SPACING, "horizontal"),
        "SupplierLength": (leadscrew.KP08_LENGTH, "horizontal"),
        "SupplierBoltHoleDiameter": (leadscrew.KP08_HOLE_DIA, "vertical"),
    }
    # All on the plan (Front) view, in millimetres.
    assert spec.SUPPLIER_REFERENCE_PLANES == {}
    assert set(spec.SUPPLIER_REFERENCE_UNITS.values()) == {"mm"}
    assert spec.SUPPLIER_REFERENCE_FORMATS["SupplierBoltHoleDiameter"] == (
        1, "diameter", None, "2X",
    )

    def chord(name):
        (x, y), (value, orientation) = spec.SUPPLIER_REFERENCE_STARTS[name], rows[name]
        return (x, y), (x + value, y) if orientation == "horizontal" else (x, y + value)

    # The spacing runs hole centre to hole centre along the foot's +Y edge,
    # the length along the -Y edge, the hole across the -X hole's centre.
    assert chord("SupplierBoltSpacing") == ((spec.HOLE_X[0], spec.WIDTH / 2.0), (spec.HOLE_X[1], spec.WIDTH / 2.0))
    assert chord("SupplierLength") == ((-spec.LENGTH / 2.0, -spec.WIDTH / 2.0), (spec.LENGTH / 2.0, -spec.WIDTH / 2.0))
    assert chord("SupplierBoltHoleDiameter") == ((spec.HOLE_X[0], -spec.HOLE_DIA / 2.0), (spec.HOLE_X[0], spec.HOLE_DIA / 2.0))
    lanes = supplier_screw_lane_plan(
        spec.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=spec.SUPPLIER_REFERENCE_PLANES,
        sides=spec.SUPPLIER_REFERENCE_SIDES,
    )
    assert {name: side for name, (side, _offset) in lanes.items()} == {
        "SupplierBoltSpacing": "top",
        "SupplierLength": "bottom",
        "SupplierBoltHoleDiameter": "left",
    }
    assert draw.SHELVES == {"SupplierBoltHoleDiameter": (False, "left")}
    left, bottom, right, top = draw.SUPPLIER_MARGINS["*Front"]
    # The hole text's left reserve; the plan view (55 x 13 at 2:1 plus 11.176
    # mm of native padding) still fits the 180 mm cell beside it.
    assert (left, right) == (0.034, 0.020) and bottom == top
    assert 0.180 - left - right >= 2 * spec.LENGTH / 1000.0 + 0.011176
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "supplier.SUPPLIER_REFERENCE_DIMENSIONS" in source
