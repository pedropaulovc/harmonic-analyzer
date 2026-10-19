"""Offline contracts for the MHA-CH-06-TL-VN-67 riser screw (McMaster 91771A110)."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import _mcmaster_91771a110 as dims
import build_ch_rocker_arm_tl_vn_oblique_riser_screw as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_riser_screw_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91771A110 as recipe
from diagnostics.diag_mcmaster_phillips_flat_head import chain_segments
from diagnostics.sketch_profile import closed_loops, endpoint_merges
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

STEM = "ch-rocker-arm-tl-vn-oblique-riser-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91771A110",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-67"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert "installation_notes" not in row
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_91771A110)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91771A110
    assert metadata.threaded is True


def test_quantity_thread_and_length_are_the_fastener_tables() -> None:
    row = fasteners.RISER_TO_CARRIER
    assert spec.ROW is row
    assert int(_config.parts(STEM)["quantity"]) == spec.QUANTITY == row.count
    assert (dims.THREAD, dims.LENGTH_TEXT, fasteners.FLAT_HEAD) == (
        row.thread,
        row.length,
        row.head,
    )
    assert dims.DIMS.length == pytest.approx(row.length_mm)
    assert dims.DIMS.major_dia == pytest.approx(row.major_mm, abs=1e-3)
    assert spec.CALLOUT == fasteners.callout(row) == "#4-40 X 1/2 B18.6.3 FLAT HEAD"


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert REGISTRY[spec.SKU] is recipe.build_91771A110
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source
    assert not hasattr(recipe, "_com_map")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/91771A110*.SLDPRT"))


def test_recipe_is_the_catalogue_screw() -> None:
    d = dims.DIMS
    assert d.part_no == spec.SKU
    assert d.major_dia == pytest.approx(0.112 * IN)
    assert d.pitch == pytest.approx(IN / 40.0)
    assert d.length == pytest.approx(0.5 * IN)
    assert d.head_dia == pytest.approx(0.212 * IN)
    assert d.head_dia <= trammel.RISER_SCREW_HEAD_DIA
    assert d.head_angle_deg == 82.0
    assert d.thread_top_depth == pytest.approx(0.067 * IN)  # catalogue head height
    assert d.junction_depth < d.thread_top_depth < spec.ROW.grip_mm


def test_recess_volume_matches_an_occ_boolean() -> None:
    # FreeCAD 1.1 boolean of the drafted cross-and-notch prism with the entry
    # cylinder and bottom cone: 5.086111 mm^3 (2026-10-17).
    assert dims.DIMS.recess_volume() == pytest.approx(5.086111, abs=1e-3)


def test_profiles_close() -> None:
    d = dims.DIMS
    for points, on_axis in (
        (tuple(seg[0] for seg in d.body_profile()), True),
        (tuple(seg[0] for seg in d.head_profile()), True),
        (tuple(seg[0] for seg in d.shank_profile()), True),
        (tuple(seg[0] for seg in d.refill_profile()), False),
        (d.cone_tip_profile(), True),
    ):
        segments = chain_segments(points)
        endpoint_merges(segments)
        assert len(closed_loops(segments)) == 1
        assert any(s.start[0] == 0.0 and s.end[0] == 0.0 for s in segments) is on_axis


def test_frame_puts_the_flat_top_at_y0() -> None:
    d = dims.DIMS
    ys = [p[1] for seg in d.body_profile() for p in seg]
    assert max(ys) == 0.0
    assert min(ys) == pytest.approx(-spec.ROW.length_mm)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'screw_axis_planes=("Front Plane", "Right Plane")' in source


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_riser_screw as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_riser_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
