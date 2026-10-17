"""Offline contracts for the MHA-VN-061 pen-rod set screw (McMaster 91375A105)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_vn_pen_rod_set_screw as part
import draw_vn_pen_rod_set_screw as drawing
import vn_pen_rod_set_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _hole_spec import THREAD_MAJOR_MM
from _stock_fastener import RigidTransform
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91375A105 as recipe
from diagnostics import diag_build_91375A106 as family

IN = 25.4
STEM = "vn-pen-rod-set-screw"


def test_stock_build_uses_its_registered_recipe() -> None:
    metadata = recipe_declaration(spec.SKU, recipe.build_91375A105)
    assert spec.SKU == "91375A105"
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_91375A105.__name__
    assert metadata.threaded
    assert part.SPEC is FASTENERS[STEM]
    assert part.SPEC.skus == (spec.SKU,)
    assert part.MATERIAL == "Alloy Steel"
    assert part.LENGTH == recipe.LENGTH == 2.0 * recipe.HALF


def test_part_frame_is_the_arbor_set_screws() -> None:
    """Cup end on the Top plane at y 0, socket face at y +LENGTH, axis +Y."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "transform=RigidTransform(translation_mm=(0.0, HALF, 0.0))," in source
    lift = RigidTransform(translation_mm=(0.0, recipe.HALF, 0.0))
    assert lift.translation_mm[1] - recipe.HALF == 0.0
    assert lift.translation_mm[1] + recipe.HALF == spec.LENGTH


def test_config_row_is_the_catalog_identity() -> None:
    row = _config.parts(STEM)
    assert row["number"] == "MHA-VN-061"
    assert row["title"] == "Pen Rod Set Screw"
    assert row["stock_name"] == FASTENERS[STEM].stock_name
    assert row["stock_name"] == "Alloy Steel Cup-Tip Set Screw"
    assert row["supplier_skus"] == [spec.SKU]
    assert spec.SKU in row["material_specification"]
    assert row["finish"] == "black oxide"
    assert int(row["quantity"]) == 1
    assert row["process"] == "purchased"


def test_spec_carries_the_live_catalogue_facts() -> None:
    """mcmaster.com/91375A105, read live 2026-10-13."""
    assert spec.THREAD == "#4-40"
    assert spec.MAJOR_DIA == pytest.approx(THREAD_MAJOR_MM[spec.THREAD], abs=5e-4)
    assert spec.PITCH == recipe.PITCH == IN / 40.0
    assert spec.LENGTH == recipe.LENGTH == 3.0 / 16.0 * IN
    assert spec.HEX_AF == recipe.HEX_AF == 0.050 * IN
    # The plain point under the first full thread is the cup-end chamfer.
    assert spec.POINT_LENGTH == recipe.POINT_CHAMFER == recipe.PITCH
    assert spec.CUP_DIA == pytest.approx(recipe.point_end_dia())
    blank = math.pi / 4.0 * spec.MAJOR_DIA**2 * spec.LENGTH * 7.7e-3
    assert 0.5 * blank < spec.MASS_G < blank


def test_recipe_restates_every_length_independent_law_of_91375A106() -> None:
    """Restated, not imported: a stock build's closure holds its own recipe."""
    for name in (
        "MAJOR_DIA",
        "PITCH",
        "HEX_AF",
        "SOCKET_DEPTH",
        "SOCKET_CHAMFER",
        "POINT_CHAMFER",
        "CUP_HALF_ANGLE_DEG",
        "CUP_RIM_DIA",
        "DRILL_HALF_ANGLE_DEG",
        "CSK_HALF_ANGLE_DEG",
        "ROOT_R",
        "H_SHARP",
    ):
        assert getattr(recipe, name) == pytest.approx(getattr(family, name)), name
    for name in (
        "cup_depth",
        "hex_corner_r",
        "drill_point_depth",
        "socket_volume",
        "drill_point_volume",
        "countersink_volume",
        "point_end_dia",
    ):
        assert getattr(recipe, name)() == pytest.approx(getattr(family, name)()), name
    assert recipe.LENGTH == pytest.approx(family.LENGTH - IN / 16.0)
    assert (
        "diag_build_91375A106"
        not in Path(recipe.__file__).read_text(encoding="utf-8").split('"""')[2]
    )


def test_catalog_recipe_claims_no_vendor_truth() -> None:
    assert not [name for name in vars(recipe) if name.startswith("VENDOR_")]
    assert not hasattr(recipe, "_check_truth")
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "no vendor model has been harvested" in source
    assert "sys.exit(run_build(build_catalog))" in source


def test_family_laws_leave_a_sound_part() -> None:
    assert recipe.hex_corner_r() < recipe.MAJOR_DIA / 2.0 - recipe.SOCKET_CHAMFER
    assert recipe.ROOT_R > recipe.hex_corner_r()
    # Solid on the axis between the drill point and the cup.
    assert recipe.web_between_apexes() > 0.5
    assert recipe.HELIX_REVS * recipe.PITCH == pytest.approx(
        recipe.LENGTH + 1.01 * recipe.PITCH
    )


def test_pre_thread_volume_is_positive_and_below_the_blank() -> None:
    pre_thread = (
        recipe.revolved_volume()
        - recipe.socket_volume()
        - recipe.drill_point_volume()
        - recipe.countersink_volume()
    )
    blank = math.pi * (recipe.MAJOR_DIA / 2.0) ** 2 * recipe.LENGTH
    assert 0.0 < pre_thread < blank


def test_recipe_cuts_the_registered_thread_feature() -> None:
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert 'await adapter.create_sketch("Front")' in source
    assert "start_angle_rad=math.pi / 2.0," in source
    assert '"ThreadGroove"' in source


def test_drawing_is_the_purchased_reference_sheet() -> None:
    sheet = DRAWINGS_BY_NAME["vn_pen_rod_set_screw"]
    assert drawing.SPEC is sheet
    assert sheet.artifact_stem == part.PART_NAME
    assert sheet.source_kind == "part"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "build_purchased_fastener_drawing" in source
    assert "adapter, SPEC, item=ITEM" in source
    assert drawing.ITEM.startswith("#4-40 x 3/16 ")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{spec.SKU}*.SLDPRT"))
