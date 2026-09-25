"""Offline contracts for the MHA-140 cone tip block hold-down screw."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

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
    # The vendor's 0.138 in; the shared table rounds it to 3.505.
    assert recipe.MAJOR_DIA == pytest.approx(
        THREAD_MAJOR_MM[block.FOOT_THREAD], abs=5e-4
    )
    assert recipe.PITCH == IN / 32.0
    assert recipe.LENGTH == block.FOOT_SCREW_LENGTH == 0.5 * IN
    assert recipe.HEAD_DIA == 0.262 * IN
    assert recipe.HEAD_H == 0.073 * IN
    assert recipe.HEX_AF == 5.0 / 64.0 * IN


def test_head_laws_reproduce_the_vendor_measurements() -> None:
    """Main ruling (i), 2026-09-24: the head is the vendor's, measured from the
    dump of 91255A148.SLDPRT (SHA-256 4b8dac17...), not the ASME sketch."""
    assert recipe.dome_radius() == pytest.approx(3.941216, abs=1e-5)
    assert recipe.dome_center_y() == pytest.approx(-1.834117, abs=1e-5)
    assert recipe.FLAT_TOP_DIA == pytest.approx(2.778125, abs=1e-6)
    assert recipe.BAND_H == pytest.approx(0.27813, abs=1e-5)
    assert recipe.EDGE_FILLET_R == pytest.approx(0.09271, abs=1e-5)
    assert recipe.SOCKET_DEPTH == pytest.approx(1.01981, abs=1e-5)
    # Their bearing-face annulus runs out to r 3.200565 past the fillet.
    assert recipe.bearing_face_dia() == pytest.approx(6.401130, abs=1e-5)
    assert 2.0 * recipe.bearing_edge_r() == pytest.approx(6.556716, abs=1e-5)
    # Their neck cone meets the shank cylinder 0.0859 under the bearing face.
    assert recipe.NECK_DIA / 2.0 == pytest.approx(1.838526, abs=1e-6)
    assert recipe.neck_reach()[0] == pytest.approx(5.4229 - 5.337, abs=1e-3)
    assert recipe.ROOT_R == pytest.approx(1.237044, abs=1e-6)


def test_socket_and_countersink_stay_inside_the_flat_top() -> None:
    corner = recipe.hex_corner_r()
    assert 2.0 * corner < recipe.FLAT_TOP_DIA
    assert recipe.HEAD_H - recipe.SOCKET_DEPTH > recipe.BAND_H
    slope = math.tan(math.radians(recipe.CSK_DEG))
    runout = (corner - recipe.HEX_AF / 2.0) / slope  # onto the flats
    apex = corner / slope
    assert runout == pytest.approx(0.0886, abs=1e-4)
    assert runout < apex < recipe.SOCKET_DEPTH
    # The flat top the socket and countersink leave: their plane face, 1.9381.
    top = math.pi * ((recipe.FLAT_TOP_DIA / 2.0) ** 2 - corner**2)
    assert top == pytest.approx(1.9381, abs=1e-4)
    assert 0.0 < recipe.countersink_volume() < 0.05
    assert 0.0 < recipe.edge_fillet_volume() < 0.05


def test_neck_cone_stays_under_the_platform_ledge() -> None:
    """The neck fills the last groove turns 0.60 under the bearing face; the
    thinnest ledge plus shim stack is 2.96, so the block's tap only ever meets
    full thread and the tip chamfer, and the printed 1.80D still stands."""
    to_root = recipe.neck_reach()[1]
    assert to_root == pytest.approx(0.6015, abs=1e-4)
    assert to_root < block.FOOT_LEDGE_RANGE_MM[0] + block.FOOT_SHIM_RANGE_MM[0]
    major = THREAD_MAJOR_MM[block.FOOT_THREAD]
    full_form = block.FOOT_SCREW_REACH_MM[0] - recipe.TIP_CHAMFER
    assert full_form / major >= 1.5
    # The neck collar (above the major) passes the shim's horseshoe and the
    # platform's 4.0 tip slot (cone_swing_platform_spec.TIP_SLOT_W on #830,
    # not yet in this stack).
    import cone_tip_shim_spec as shim

    assert recipe.NECK_DIA < shim.SLOT_W
    assert (4.0 - recipe.NECK_DIA) / 2.0 == pytest.approx(0.161, abs=1e-3)


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


def test_replica_driver_names_a_missing_local_vendor_file(
    tmp_path: Path, monkeypatch
) -> None:
    """Codex P2 on #857: the vendor SLDPRT is local-only, so a clean checkout
    must get a download instruction, not a bare FileNotFoundError."""
    from diagnostics import diag_build_mcmaster as driver

    monkeypatch.setattr(driver, "MCMASTER_DIR", tmp_path / "mcmaster")
    monkeypatch.setattr(driver, "REPORTS_DIR", tmp_path / "reports")
    why = driver._missing_inputs("91255A148")
    assert "vendor SLDPRT not present locally" in why
    assert "https://www.mcmaster.com/91255A148/" in why
    (tmp_path / "mcmaster").mkdir()
    (tmp_path / "mcmaster" / "91255A148.SLDPRT").write_bytes(b"")
    assert "no harvest" in driver._missing_inputs("91255A148")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "mcmaster-91255A148-dump.json").write_text("{}")
    assert driver._missing_inputs("91255A148") is None


def test_replica_driver_skips_missing_parts_under_all(monkeypatch) -> None:
    import asyncio

    from diagnostics import diag_build_mcmaster as driver

    ran: list[str] = []

    async def fake_replica(adapter, part_no, builder):
        ran.append(part_no)
        return {}

    monkeypatch.setattr(driver, "run_replica", fake_replica)
    monkeypatch.setattr(
        driver, "_missing_inputs", lambda p: "absent" if p == "91255A148" else None
    )
    monkeypatch.setattr(driver.sys, "argv", ["diag_build_mcmaster.py", "--all"])
    asyncio.run(driver.build(None))
    assert "91255A148" not in ran and len(ran) == len(driver.REGISTRY) - 1
    monkeypatch.setattr(driver.sys, "argv", ["diag_build_mcmaster.py", "91255A148"])
    with pytest.raises(SystemExit, match="91255A148: absent"):
        asyncio.run(driver.build(None))
