"""Offline contracts for the MHA-140 cone tip block hold-down screw."""

from __future__ import annotations

import math
import re
from pathlib import Path

import _config
import build_cone_tip_block_screw as part
import cone_tip_block_spec as block
import draw_cone_tip_block_screw as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_91255A148 as recipe

IN = 25.4


def test_recipe_is_the_catalog_screw_the_block_is_sized_for() -> None:
    """Handoff item 4 (read 2026-09-23): #6-32 x 1/2, head 0.262 x 0.073, 5/64 hex."""
    assert part.THREAD == block.FOOT_THREAD == "#6-32"
    assert recipe.MAJOR_DIA == THREAD_MAJOR_MM[block.FOOT_THREAD]
    assert recipe.PITCH == IN / 32.0
    assert recipe.LENGTH == block.FOOT_SCREW_LENGTH == 0.5 * IN
    assert recipe.HEAD_DIA == 0.262 * IN
    assert recipe.HEAD_H == 0.073 * IN
    assert recipe.HEX_AF == 5.0 / 64.0 * IN


def test_socket_stays_inside_the_head() -> None:
    assert recipe.HEAD_BAND < recipe.socket_floor_y() < recipe.HEAD_H
    corner = recipe.HEX_AF / math.sqrt(3.0)
    assert recipe.dome_height_at(corner) - recipe.socket_floor_y() == recipe.SOCKET_KEY_ENGAGEMENT
    hex_area = math.sqrt(3.0) / 2.0 * recipe.HEX_AF**2
    depth = recipe.HEAD_H - recipe.socket_floor_y()
    assert hex_area * (depth - 0.2) < recipe.socket_volume(120) < hex_area * depth


def test_stock_build_uses_its_registered_recipe() -> None:
    metadata = STOCK_RECIPES["91255A148"]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_91255A148.__name__
    assert part.SPEC.skus == ("91255A148",)
    assert part.MATERIAL == "Alloy Steel"


def test_installation_note_states_the_printed_minimum_engagement() -> None:
    """The note's 1.80D is the tip-block spec's worst-case reach over the major."""
    notes = _config.parts(part.PART_NAME)["installation_notes"]
    stated = float(re.search(r"ENGAGEMENT (\d+\.\d\d)D MIN", notes).group(1))
    worst = block.FOOT_SCREW_REACH_MM[0] / THREAD_MAJOR_MM[block.FOOT_THREAD]
    assert stated == math.floor(worst * 100.0) / 100.0 == 1.80
    for number in ("MHA-091", "MHA-141", "MHA-092"):
        assert number in notes


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["cone_tip_block_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert "build_purchased_fastener_drawing" in Path(drawing.__file__).read_text(
        encoding="utf-8"
    )
