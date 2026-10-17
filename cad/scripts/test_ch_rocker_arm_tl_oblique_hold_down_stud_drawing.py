"""PM kit 1/2-13 x 3 in hold-down stud (MHA-CH-006-TL-38) contracts, SolidWorks-free."""

from __future__ import annotations

import ast
import asyncio
import math
import re
from pathlib import Path

import _config
import build_ch_rocker_arm_tl_oblique_hold_down_stud as part
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_hold_down_stud_spec as spec
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
import draw_ch_rocker_arm_tl_oblique_hold_down_stud as draw
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import THREAD_MAJOR_MM

STEM = "ch-rocker-arm-tl-oblique-hold-down-stud"
NAME = STEM.replace("-", "_")
ROW = _config.parts(STEM)


def test_registry_row_is_the_purchased_pm_kit_stud() -> None:
    assert ROW["number"] == "MHA-CH-006-TL-38"
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


def test_quantity_is_c4s_hold_down_count() -> None:
    assert int(ROW["quantity"]) == spec.QUANTITY == fasteners.HOLD_DOWN_STUD_COUNT


def test_size_is_imported_from_c4_not_retyped() -> None:
    assert spec.THREAD == fasteners.HOLD_DOWN_STUD_THREAD == "1/2-13"
    assert spec.LENGTH == fasteners.HOLD_DOWN_STUD_LENGTH_MM == jig.STUD_LENGTH
    assert spec.MAJOR_DIA == base_bar.HOLD_DOWN_STUD_DIA == jig.STUD_DIA
    assert math.isclose(spec.MAJOR_DIA, THREAD_MAJOR_MM[spec.THREAD])
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert re.search(r"^THREAD = fasteners\.HOLD_DOWN_STUD_THREAD", source, re.M)
    assert re.search(r"^LENGTH = fasteners\.HOLD_DOWN_STUD_LENGTH_MM", source, re.M)
    assert re.search(r"^MAJOR_DIA = base_bar\.HOLD_DOWN_STUD_DIA", source, re.M)


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
        "ch_rocker_arm_tl_oblique_base_bar_spec",
        "ch_rocker_arm_tl_oblique_fasteners_spec",
    }


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


def test_profile_closes_on_the_axis_from_the_origin() -> None:
    assert spec.PROFILE[0] == (0.0, 0.0)
    assert spec.PROFILE[-1] == (spec.LENGTH, 0.0)
    assert max(r for _, r in spec.PROFILE) == spec.MAJOR_DIA / 2.0
    assert part.profile_points() == [(r, y) for y, r in spec.PROFILE]


def test_closed_form_volume_matches_a_numeric_revolve() -> None:
    def radius(y: float) -> float:
        for (y0, r0), (y1, r1) in zip(spec.PROFILE, spec.PROFILE[1:]):
            if y0 <= y <= y1 and y1 > y0:
                return r0 + (r1 - r0) * (y - y0) / (y1 - y0)
        raise AssertionError(y)

    n = 20000
    dy = spec.LENGTH / n
    numeric = sum(math.pi * radius((i + 0.5) * dy) ** 2 * dy for i in range(n))
    assert math.isclose(spec.VOLUME_MM3, numeric, rel_tol=1e-6)


def test_builder_publishes_the_screw_axis() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
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
    assert "1/2-13" in draw.ITEM
