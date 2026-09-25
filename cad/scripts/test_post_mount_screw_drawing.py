"""Offline contracts for the MHA-142 cone pivot post mount screw."""

from __future__ import annotations

import re
from pathlib import Path

import _config
import build_post_mount_screw as part
import cone_pivot_post_spec as post
import cone_swing_platform_spec as platform
import draw_post_mount_screw as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_40923898 as recipe

IN = 25.4
# Screw head seated on the counterbore floor: its under-head face is this far
# below the post top, and the shank spans the rest of the post and the plate.
GRIP = post.BLOCK_HEIGHT - post.ATTACHMENT_CBORE_DEPTH


def test_recipe_is_the_u37c_screw() -> None:
    """1/4-20, ASME B18.6.3 1/4 fillister head maximum, 86.0 cut length."""
    assert part.THREAD == platform.POST_MOUNT_SPEC.size == "1/4-20"
    assert part.SHANK_DIA == THREAD_MAJOR_MM[part.THREAD]
    assert part.THREAD_PITCH == IN / 20.0
    assert part.SHANK_LEN == 86.0
    assert part.HEAD_DIA == 0.414 * IN
    assert part.HEAD_H == 0.237 * IN


def test_head_fits_the_existing_post_counterbore() -> None:
    assert part.HEAD_DIA < post.ATTACHMENT_CBORE_DIA
    assert part.HEAD_H <= post.ATTACHMENT_CBORE_DEPTH + 1e-9  # never above the top
    assert part.SHANK_DIA < post.ATTACHMENT_THRU_DIA


def test_nominal_end_sits_short_of_the_platform_underside() -> None:
    """Never proud; the nominal cut leaves the end 0.33 short (U37c)."""
    short = GRIP + platform.PLATE_THICKNESS - part.SHANK_LEN
    assert 0.0 <= short < 0.35
    engagement = part.SHANK_LEN - GRIP
    assert engagement / part.SHANK_DIA >= 0.90


def test_installation_note_carries_the_ruled_cut_to_fit_line() -> None:
    notes = " ".join(_config.parts(part.PART_NAME)["installation_notes"].split())
    assert (
        "CUT EACH TO FIT, SHORT OF MHA-091 UNDERSIDE, NEVER PROUD (NOMINAL 86.0)"
        in notes
    )
    stated = float(re.search(r"ENGAGEMENT (\d+\.\d\d)D MIN", notes).group(1))
    assert stated == 0.90
    assert "NAMED EXCEPTION TO RULE 12" in notes
    for number in ("MHA-016", "MHA-091"):
        assert number in notes
    assert f"NOMINAL {part.SHANK_LEN:.1f}" in notes


def test_installation_note_fits_the_purchased_note_box() -> None:
    """The contract's reserved box (_purchased_fastener_drawing) is
    (0.015, 0.169)-(0.225, 0.190), with the note anchored at (0.018, 0.189).

    It is a literal inside the builder, so this pins it from the one
    measurement we have: 857-parts-r1 (bb0c8b18) rendered the six-line
    note at 17.6..128.6 x 165.2..189.4 mm: 4.04 mm per line.  One of its
    lines of 45 to 50 characters set the width, so a character is at most
    110.96 / 45 = 2.47 mm.  Four lines leave about 4 mm spare, as MHA-140's
    four did.
    """
    lines = _config.parts(part.PART_NAME)["installation_notes"].splitlines()
    top, bottom, left, right = 189.42, 169.0, 17.62, 225.0
    line_pitch, char_width = 24.25 / 6, 110.96 / 45
    assert top - len(lines) * line_pitch >= bottom + 2.0
    widest = max(len(line) for line in lines)
    assert left + widest * char_width <= right - 10.0


def test_stock_build_uses_its_registered_recipe() -> None:
    metadata = STOCK_RECIPES["40923898"]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_40923898.__name__
    assert part.SPEC.skus == ("40923898",)
    assert part.SPEC.supplier == "MSC Industrial Supply"
    assert part.MATERIAL == "Plain Carbon Steel"
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-142"
    assert int(row["quantity"]) == 2
    assert "1456MSL" in row["material_specification"]


def test_drawing_is_the_purchased_reference_sheet() -> None:
    spec = DRAWINGS_BY_NAME["post_mount_screw"]
    assert drawing.SPEC is spec
    assert spec.artifact_stem == part.PART_NAME
    assert spec.script == Path(drawing.__file__).resolve()
    assert "build_purchased_fastener_drawing" in Path(drawing.__file__).read_text(
        encoding="utf-8"
    )


def test_standalone_recipe_run_is_catalog_only() -> None:
    # Codex #857 P2: MSC publishes no CAD, so the standalone command must not
    # enter the McMaster replica path (vendor SLDPRT + harvest).  It builds the
    # recipe and saves it; the documented command is that entry point.
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "replica_main(" not in source and "import replica_main" not in source
    assert "run_build(build_catalog)" in source
    assert "diag_build_40923898.py" in (recipe.__doc__ or "")
    assert "catalog-only" in (recipe.__doc__ or "")
