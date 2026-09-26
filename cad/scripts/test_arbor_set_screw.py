"""Offline contracts for the MHA-147 arbor apex set screw (McMaster 91375A106)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import arbor_set_screw_spec as spec
import build_arbor_set_screw as part
import draw_arbor_set_screw as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_91375A106 as recipe

IN = 25.4


def test_stock_build_uses_its_registered_recipe() -> None:
    metadata = STOCK_RECIPES["91375A106"]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_91375A106.__name__
    assert part.SPEC.skus == ("91375A106",)
    assert part.MATERIAL == "Alloy Steel"
    # The replica is centred on its origin; the part lifts the cup end to y 0.
    assert part.LENGTH == recipe.LENGTH == 2.0 * recipe.HALF


def test_spec_restates_the_replica_it_is_sized_from() -> None:
    assert spec.THREAD == "#4-40"
    assert recipe.MAJOR_DIA == pytest.approx(THREAD_MAJOR_MM[spec.THREAD], abs=5e-4)
    assert spec.LENGTH == recipe.LENGTH == 0.25 * IN
    assert spec.HEX_AF == recipe.HEX_AF == 0.050 * IN
    # The plain point under the first full thread is the cup-end chamfer.
    assert spec.POINT_LENGTH == recipe.POINT_CHAMFER == recipe.PITCH


def test_laws_reproduce_the_vendor_measurements() -> None:
    """Read off the 2026-09-26 dump of 91375A106.SLDPRT (SHA-256 7f4cfb6c...)."""
    assert recipe.PITCH == IN / 40.0
    assert recipe.MAJOR_DIA / 2.0 == pytest.approx(1.4224, abs=1e-6)
    assert recipe.ROOT_R == pytest.approx(1.009955, abs=1e-6)
    assert recipe.SOCKET_CHAMFER == pytest.approx(0.47625, abs=1e-6)
    assert recipe.MAJOR_DIA / 2.0 - recipe.SOCKET_CHAMFER == pytest.approx(
        0.94615, abs=1e-6
    )
    assert recipe.point_end_dia() / 2.0 == pytest.approx(0.7874, abs=1e-6)
    assert recipe.cup_depth() == pytest.approx(3.175 - 2.725729, abs=1e-5)
    assert recipe.SOCKET_DEPTH == pytest.approx(1.778, abs=1e-6)
    assert recipe.drill_point_depth() == pytest.approx(0.5328, abs=1e-4)
    assert recipe.HELIX_REVS * recipe.PITCH == pytest.approx(6.99135, abs=1e-5)


def test_analytic_faces_match_the_vendor_face_areas() -> None:
    """The faces the thread never touches, computed from the laws."""
    socket_face = math.pi * (
        (recipe.MAJOR_DIA / 2.0 - recipe.SOCKET_CHAMFER) ** 2
        - recipe.hex_corner_r() ** 2
    )
    cup_rim = math.pi * (
        (recipe.point_end_dia() / 2.0) ** 2 - (recipe.CUP_RIM_DIA / 2.0) ** 2
    )
    cup_cone = (
        math.pi
        * recipe.CUP_RIM_DIA
        / 2.0
        * math.hypot(recipe.CUP_RIM_DIA / 2.0, recipe.cup_depth())
    )
    drill_cone = (
        math.pi
        * recipe.HEX_AF
        / 2.0
        * math.hypot(recipe.HEX_AF / 2.0, recipe.drill_point_depth())
    )
    hex_area = math.sqrt(3.0) / 2.0 * recipe.HEX_AF**2
    floor_corner = (hex_area - math.pi * (recipe.HEX_AF / 2.0) ** 2) / 6.0
    assert socket_face == pytest.approx(1.1233, abs=1e-4)
    assert cup_rim == pytest.approx(0.1914, abs=1e-4)
    assert cup_cone == pytest.approx(2.0491, abs=1e-4)
    assert drill_cone == pytest.approx(1.6536, abs=1e-4)
    assert floor_corner == pytest.approx(0.0217, abs=1e-4)


def test_vendor_truth_is_pinned() -> None:
    assert recipe.VENDOR_VOLUME_MM3 == 25.8601
    assert recipe.VENDOR_SURFACE_MM2 == 95.038
    assert recipe.VENDOR_FACE_COUNT == 28
    truth = {
        "mass": {"volume_mm3": 25.8601, "surface_area_mm2": 95.038},
        "bodies": [{"faces": [{}] * 28}],
    }
    recipe._check_truth(truth)
    truth["bodies"] = [{"faces": [{}] * 12}]
    with pytest.raises(RuntimeError, match="pinned vendor truth"):
        recipe._check_truth(truth)


def test_pre_thread_volume_leaves_the_groove_its_share() -> None:
    pre_thread = (
        recipe.revolved_volume()
        - recipe.socket_volume()
        - recipe.drill_point_volume()
        - recipe.countersink_volume()
    )
    groove = pre_thread - recipe.VENDOR_VOLUME_MM3
    # Less than the whole crest-to-root annulus, more than half of it.
    annulus = (
        math.pi
        * ((recipe.MAJOR_DIA / 2.0) ** 2 - recipe.ROOT_R**2)
        * (recipe.LENGTH - recipe.SOCKET_CHAMFER - recipe.POINT_CHAMFER)
    )
    assert 0.5 * annulus < groove < annulus


def test_com_map_is_a_proper_rotation() -> None:
    # replica (x, y, z) = vendor (x, z, -y): det +1, so the thread's hand holds.
    rows = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]
    det = (
        rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
        - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
        + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
    )
    assert det == 1
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "adapter._mcm_com_map = lambda c: [c[0], c[2], -c[1]]" in source


def test_drawing_is_the_purchased_reference_sheet() -> None:
    sheet = DRAWINGS_BY_NAME["arbor_set_screw"]
    assert drawing.SPEC is sheet
    assert sheet.artifact_stem == part.PART_NAME
    assert "build_purchased_fastener_drawing" in Path(drawing.__file__).read_text(
        encoding="utf-8"
    )
