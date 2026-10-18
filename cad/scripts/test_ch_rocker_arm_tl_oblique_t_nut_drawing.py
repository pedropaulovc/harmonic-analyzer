"""PM kit 14 mm T-nut, 1/2-13 (MHA-CH-006-TL-39) contracts, SolidWorks-free."""

from __future__ import annotations

import ast
import asyncio
import math
import re
from pathlib import Path

import _config
import build_ch_rocker_arm_tl_oblique_t_nut as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
import ch_rocker_arm_tl_oblique_t_nut_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_t_nut as draw
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import TAP_DRILL_MM

STEM = "ch-rocker-arm-tl-oblique-t-nut"
NAME = STEM.replace("-", "_")
ROW = _config.parts(STEM)


def test_registry_row_is_the_purchased_pm_kit_t_nut() -> None:
    assert ROW["number"] == "MHA-CH-006-TL-39"
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


def test_quantity_is_one_under_each_hold_down_stud() -> None:
    assert int(ROW["quantity"]) == spec.QUANTITY == fasteners.HOLD_DOWN_STUD_COUNT


def test_c4_values_are_imported_not_retyped() -> None:
    assert spec.THREAD == fasteners.HOLD_DOWN_STUD_THREAD
    assert spec.SLOT_WIDTH == trammel.TSLOT_WIDTH
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert re.search(r"^SLOT_WIDTH = trammel\.TSLOT_WIDTH", source, re.M)
    # The spec owns C4's T-slot estimates; the jig assembly reads them here.
    assert (spec.FOOT_HEIGHT, spec.THROAT_DEPTH) == (8.0, 14.0)


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
    for mark in (
        "SOURCED",
        "FROM C4",
        "ESTIMATED",
        "verify on receipt",
        "Part frame",
        "Volume",
    ):
        assert mark in doc, mark


def test_t_nut_fits_the_table_slot() -> None:
    # The neck passes the throat and stays below the table surface; the
    # stud's bottom end sits flush with the foot (C4's STUD_BOTTOM_Z).
    assert spec.NECK_WIDTH < trammel.TSLOT_WIDTH
    assert spec.NECK_HEIGHT < spec.THROAT_DEPTH
    assert spec.HEIGHT <= spec.THROAT_DEPTH + spec.FOOT_HEIGHT
    assert jig.STUD_BOTTOM_Z == -(spec.THROAT_DEPTH + spec.FOOT_HEIGHT)
    assert spec.TAP_DRILL_DIA == TAP_DRILL_MM[spec.THREAD]
    assert spec.TAP_DRILL_DIA < spec.NECK_WIDTH < spec.FOOT_WIDTH


def test_section_is_closed_axis_aligned_and_symmetric() -> None:
    profile = spec.PROFILE
    for (u0, v0), (u1, v1) in zip(profile, profile[1:] + profile[:1]):
        assert u0 == u1 or v0 == v1
    assert sorted(profile) == sorted((-u, v) for u, v in profile)
    assert profile[0] == (-spec.FOOT_WIDTH / 2.0, 0.0)
    assert part.profile_points() == list(profile)


def test_closed_form_volume_matches_the_shoelace_section() -> None:
    pts = spec.PROFILE
    area = 0.5 * abs(
        sum(u0 * v1 - u1 * v0 for (u0, v0), (u1, v1) in zip(pts, pts[1:] + pts[:1]))
    )
    tap = math.pi * (TAP_DRILL_MM[spec.THREAD] / 2.0) ** 2 * spec.HEIGHT
    assert math.isclose(spec.VOLUME_MM3, spec.LENGTH * area - tap, rel_tol=1e-12)


def test_builder_taps_up_from_the_foot_and_publishes_the_axis() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "[[0.0, 0.0, 0.0]],\n        (0.0, -1.0, 0.0)," in source
    assert 'name="ThreadBore"' in source
    assert '"Front Plane", 0.0, "Right Plane", 0.0' in source
    assert 'name_last_feature(adapter, "ScrewAxis")' in source
    assert 'create_sketch("Right")' in source


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
    assert "T-SLOT NUT" in draw.ITEM
