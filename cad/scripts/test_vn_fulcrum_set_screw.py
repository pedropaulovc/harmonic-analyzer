"""Offline contracts for the MHA-VN-055 fulcrum-shaft set screw (McMaster 91375A942)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_vn_fulcrum_set_screw as part
import ch_fulcrum_keeper_spec as keeper
import draw_vn_fulcrum_set_screw as drawing
import vn_fulcrum_set_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _hole_spec import THREAD_MAJOR_MM
from _stock_fastener import RigidTransform
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91375A942 as recipe

IN = 25.4
STEM = "vn-fulcrum-set-screw"


def test_stock_build_uses_its_registered_recipe() -> None:
    metadata = recipe_declaration(spec.SKU, recipe.build_91375A942)
    assert spec.SKU == "91375A942"
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_91375A942.__name__
    assert metadata.threaded
    assert part.SPEC is FASTENERS[STEM]
    assert part.SPEC.skus == (spec.SKU,)
    assert part.MATERIAL == "Alloy Steel"
    # The replica is centred on its origin; the part lifts the cup end to y 0.
    assert part.LENGTH == recipe.LENGTH == 2.0 * recipe.HALF


def test_part_frame_is_the_arbor_set_screws() -> None:
    """Cup end on the Top plane at y 0, socket face at y +LENGTH, axis +Y
    through the origin: the owner's channel placement depends on it."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "transform=RigidTransform(translation_mm=(0.0, HALF, 0.0))," in source
    lift = RigidTransform(translation_mm=(0.0, recipe.HALF, 0.0))
    assert lift.translation_mm[1] - recipe.HALF == 0.0
    assert lift.translation_mm[1] + recipe.HALF == spec.LENGTH


def test_config_row_is_the_catalog_identity() -> None:
    row = _config.parts(STEM)
    assert row["number"] == "MHA-VN-055"
    assert row["title"] == "Fulcrum Shaft Set Screw"
    assert row["stock_name"] == FASTENERS[STEM].stock_name
    assert row["stock_name"] == "Alloy Steel Cup-Tip Set Screw"
    assert row["supplier_skus"] == [spec.SKU]
    assert spec.SKU in row["material_specification"]
    assert row["finish"] == "black oxide"
    assert int(row["quantity"]) == 2
    assert row["process"] == "purchased"


def test_spec_restates_the_replica_it_is_sized_from() -> None:
    assert spec.THREAD == keeper.SET_SCREW_THREAD == "#1-72"
    assert spec.MAJOR_DIA == THREAD_MAJOR_MM[spec.THREAD]
    assert recipe.MAJOR_DIA == pytest.approx(spec.MAJOR_DIA, abs=5e-4)
    assert spec.PITCH == recipe.PITCH == IN / 72.0
    assert spec.LENGTH == recipe.LENGTH == 5.0 / 32.0 * IN
    assert spec.HEX_AF == recipe.HEX_AF == 0.035 * IN
    # The plain point under the first full thread is the cup-end chamfer.
    assert spec.POINT_LENGTH == recipe.POINT_CHAMFER == recipe.PITCH
    # The cup end lands on the ASME B18.3 #1 cup-point maximum, 0.040 in.
    assert spec.CUP_DIA == recipe.CUP_DIA == recipe.point_end_dia() == 0.040 * IN


def test_catalog_recipe_claims_no_vendor_truth() -> None:
    """Catalogue-only (the 91794A077 precedent): no harvest, no pinned truth."""
    assert not [name for name in vars(recipe) if name.startswith("VENDOR_")]
    assert not hasattr(recipe, "_check_truth")
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "no vendor model has been harvested" in source
    assert "sys.exit(run_build(build_catalog))" in source


def test_family_laws_leave_a_sound_part() -> None:
    # Hex corners clear the socket-end chamfer; the thread root clears them.
    assert recipe.hex_corner_r() < recipe.MAJOR_DIA / 2.0 - recipe.SOCKET_CHAMFER
    assert recipe.ROOT_R > recipe.hex_corner_r()
    # The cup rim annulus is the 91375A106's P/16 law.
    assert recipe.point_end_dia() - recipe.cup_rim_dia() == pytest.approx(
        recipe.PITCH / 8.0
    )
    # Solid on the axis between the drill point and the cup.
    assert recipe.web_between_apexes() > 0.5
    assert recipe.HELIX_REVS * recipe.PITCH == pytest.approx(
        recipe.LENGTH + 1.01 * recipe.PITCH
    )
    # Each small cut removes more than its volume check's tolerance.
    assert recipe.countersink_volume() > recipe.SMALL_CUT_TOL_MM3
    assert recipe.drill_point_volume() > recipe.SMALL_CUT_TOL_MM3


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
    sheet = DRAWINGS_BY_NAME["vn_fulcrum_set_screw"]
    assert drawing.SPEC is sheet
    assert sheet.artifact_stem == part.PART_NAME
    assert sheet.source_kind == "part"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "build_purchased_fastener_drawing" in source
    # Machinist review r8: the 8:1 thread and socket hidden edges cluttered
    # the front and right views; every orthographic view is HLR.
    assert "adapter, SPEC, hidden_lines_removed=True" in source
