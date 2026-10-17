"""PM kit 1/2-13 flange nut (MHA-CH-006-TL-40) contracts, SolidWorks-free."""

from __future__ import annotations

import ast
import asyncio
import math
from pathlib import Path

import _config
import build_ch_rocker_arm_tl_oblique_flange_nut as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_flange_nut_spec as spec
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_flange_nut as draw
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import TAP_DRILL_MM

STEM = "ch-rocker-arm-tl-oblique-flange-nut"
NAME = STEM.replace("-", "_")
ROW = _config.parts(STEM)


def test_registry_row_is_the_purchased_pm_kit_flange_nut() -> None:
    assert ROW["number"] == "MHA-CH-006-TL-40"
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER == "Precision Matthews"
    assert ROW["supplier_skus"] == [spec.SKU] == ["52PCCK-9/16-14mm"]
    assert ROW["material"] == spec.MATERIAL
    assert ROW["tolerance_class"] == "visual_noncritical"
    assert len(ROW["material_specification"]) <= 36  # one MATERIAL-cell line
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }


def test_quantity_is_one_on_each_hold_down_stud() -> None:
    assert int(ROW["quantity"]) == spec.QUANTITY == fasteners.HOLD_DOWN_STUD_COUNT


def test_c4_envelope_is_owned_here() -> None:
    assert spec.THREAD == fasteners.HOLD_DOWN_STUD_THREAD
    # The spec owns C4's flange-nut estimates; the jig assembly reads them here.
    assert (spec.FLANGE_DIA, spec.HEIGHT) == (28.0, 13.0)
    # The jig seats the flange on the bar top.
    assert math.isclose(jig.FLANGE_NUT_SEAT_Z, trammel.BASE_BAR_THICK)


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
    assert imported <= {
        "__future__",
        "math",
        "_hole_spec",
        "ch_rocker_arm_tl_oblique_fasteners_spec",
        "ch_rocker_arm_tl_oblique_trammel_spec",
    }


def test_docstring_marks_every_source() -> None:
    doc = spec.__doc__ or ""
    assert "datasheet-built: no vendor CAD obtained (" in doc
    assert spec.SOURCE_URL in doc
    assert spec.COMPARISON_URL in doc
    for mark in (
        "SOURCED",
        "FROM C4",
        "UNVERIFIED",
        "ESTIMATED",
        "Part frame",
        "Volume",
    ):
        assert mark in doc, mark


def test_estimated_hex_and_flange_are_te_co_41605_proportions() -> None:
    # TE-CO 41605: 0.875 in across flats, a 0.188 (3/16) in flange.
    assert math.isclose(spec.ACROSS_FLATS, 0.875 * 25.4)
    assert math.isclose(spec.FLANGE_THICK, 3.0 / 16.0 * 25.4)
    assert spec.HEX_CORNER_RADIUS < spec.FLANGE_DIA / 2.0
    assert spec.TAP_DRILL_DIA == TAP_DRILL_MM[spec.THREAD]


def test_hex_outline_is_regular_with_corners_on_z() -> None:
    corners = spec.HEX_OUTLINE
    assert len(corners) == 6
    assert corners[0] == (0.0, spec.HEX_CORNER_RADIUS)
    for (x0, z0), (x1, z1) in zip(corners, corners[1:] + corners[:1]):
        assert math.isclose(math.hypot(x1 - x0, z1 - z0), spec.HEX_CORNER_RADIUS)
    xs = [x for x, _ in corners]
    assert math.isclose(max(xs) - min(xs), spec.ACROSS_FLATS)
    # Top Plane sketch (u, v) = model (X, -Z).
    assert part.hex_points() == [(x, -z) for x, z in corners]


def test_closed_form_volume_matches_the_shoelace_hex() -> None:
    pts = spec.HEX_OUTLINE
    hex_area = 0.5 * abs(
        sum(x0 * z1 - x1 * z0 for (x0, z0), (x1, z1) in zip(pts, pts[1:] + pts[:1]))
    )
    flange = math.pi * (spec.FLANGE_DIA / 2.0) ** 2 * spec.FLANGE_THICK
    tap = math.pi * (TAP_DRILL_MM[spec.THREAD] / 2.0) ** 2 * spec.HEIGHT
    numeric = flange + hex_area * (spec.HEIGHT - spec.FLANGE_THICK) - tap
    assert math.isclose(spec.VOLUME_MM3, numeric, rel_tol=1e-9)


def test_builder_taps_up_from_the_bearing_face_and_publishes_the_axis() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "[[0.0, 0.0, 0.0]],\n        (0.0, -1.0, 0.0)," in source
    assert 'name="ThreadBore"' in source
    assert '"Front Plane", 0.0, "Right Plane", 0.0' in source
    assert 'name_last_feature(adapter, "ScrewAxis")' in source


def test_note_is_one_short_line_without_numbers() -> None:
    note = spec.DRAWING_NOTES
    assert "\n" not in note and len(note) <= 80
    assert note == note.upper()
    assert not any(ch.isdigit() for ch in note)


def test_sheet_is_the_registered_purchased_part_reference(monkeypatch) -> None:
    drawn = DRAWINGS_BY_NAME[NAME]
    assert (drawn.part, drawn.artifact_stem, drawn.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert drawn.layout is DrawingLayout.LANDSCAPE
    calls = []

    async def fake(adapter, sheet, *, item, cut_to_suit=False):
        calls.append((adapter, sheet, item, cut_to_suit))
        return {"pdf": "x"}

    monkeypatch.setattr(draw, "build_purchased_part_drawing", fake)
    adapter = object()
    assert asyncio.run(draw.build(adapter)) == {"pdf": "x"}
    assert calls == [(adapter, drawn, draw.ITEM, False)]
    assert "FLANGE NUT" in draw.ITEM
