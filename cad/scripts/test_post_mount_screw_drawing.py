"""Offline contracts for the MHA-142 cone pivot post mount screw."""

from __future__ import annotations

from pathlib import Path

import _config
import build_post_mount_screw as part
import cone_pivot_post_spec as post
import cone_swing_platform_spec as platform
import draw_post_mount_screw as drawing
import post_mount_screw_spec as spec
from _drawing_contract import drawing_specification_violations
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


def test_cut_length_band_is_derived_from_the_post_and_plate_chain() -> None:
    """Modified purchased part: the cut is a real dimension whose band keeps
    the end between the nominal cut and flush, never proud of MHA-091."""
    assert spec.GRIP_MM == GRIP
    assert spec.FLUSH_LENGTH_MM == GRIP + platform.PLATE_THICKNESS
    assert spec.CUT_LENGTH_MM == part.SHANK_LEN == 86.0
    upper, lower = spec.CUT_LENGTH_BAND
    assert (upper, lower) == (0.3, 0.0)
    assert spec.CUT_LENGTH_MIN_MM == spec.CUT_LENGTH_MM
    assert spec.CUT_LENGTH_MAX_MM <= spec.FLUSH_LENGTH_MM  # never proud
    # The band is stated at the dimension's own places, floored toward flush.
    places = spec.DRAWING_PRECISION_BY_NAME["CutLength"]
    assert places == 1
    assert round(upper, places) == upper
    assert spec.FLUSH_LENGTH_MM - spec.CUT_LENGTH_MAX_MM < 10.0**-places


def test_cut_length_is_a_model_owned_drawing_dimension() -> None:
    """Rule 2: the value, places and band are the part's; the sheet imports
    the one marked dimension from its hidden reference sketch and re-reads it."""
    assert spec.DRAWING_DIMENSIONS == {"CutLengthReference": {"CutLength"}}
    assert spec.REFERENCE_SKETCHES == ("CutLengthReference",)
    assert set(drawing.FRONT_KEEP) == {"CutLength"}
    nominal, low, high = drawing.EXPECTED_CONTROLS["CutLength"]
    assert nominal == spec.CUT_LENGTH_MM / 1000
    assert (low, high) == (0.0, spec.CUT_LENGTH_BAND[0] / 1000)
    assert drawing.TOLERANCE_TYPES == {"CutLength": 2}  # swTolBILAT
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert "set_dimension_bilateral_tolerance(" in builder
    assert "*deviations(CUT_LENGTH_BAND)" in builder
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in builder
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "hidden_sketches.curate_view_dimensions" in source
    assert "verify_machining_controls" in source


def test_sheet_notes_carry_no_dimension_rule_or_sequence() -> None:
    """Main's eye pass of warm-c486 (rule 6): the old INSTALLATION block
    printed "(NOMINAL 86.0)", "0.90D MIN" and "NAMED EXCEPTION TO RULE 12".
    The cut length is now the dimension, engagement a model assert and the
    sequence an MHA-A03 step, so no part note carries a number."""
    row = _config.parts(part.PART_NAME)
    assert "installation_notes" not in row
    notes = spec.MANUFACTURING_NOTES
    assert not any(ch.isdigit() for ch in notes)
    assert "CHAMFER CUT END" in notes
    for word in ("RULE", "EXCEPTION", "ENGAGEMENT", "NOMINAL", "INSTALL", "MHA-"):
        assert word not in notes
    assert len(notes.splitlines()) <= 4


def test_engagement_exception_is_held_by_the_model() -> None:
    """The named rule-12 exception (0.90D) is asserted at the short limit."""
    assert spec.MIN_ENGAGEMENT_DIAMETERS == 0.90
    assert spec.ENGAGEMENT_MIN_MM == spec.CUT_LENGTH_MIN_MM - GRIP
    assert spec.ENGAGEMENT_MIN_MM / part.SHANK_DIA >= 0.90


def test_sheet_layout_keeps_notes_clear_of_the_view() -> None:
    """1:1 Front view spans ~92 mm around its centre; the note block sits
    between it and the stock rows, the cut length left of the shank."""
    half_h = (spec.CUT_LENGTH_MM + part.HEAD_H) / 2000.0
    view_bottom = drawing.FRONT_CENTER[1] - half_h
    notes_y = drawing.NOTES_XY[1]
    assert notes_y + 0.004 < view_bottom
    lines = len(spec.MANUFACTURING_NOTES.splitlines())
    assert notes_y - lines * 0.0045 > max(y for _, _, y in drawing.STOCK_ROWS) + 0.003
    x, _ = drawing.FRONT_KEEP["CutLength"]
    assert x < drawing.FRONT_CENTER[0] - part.HEAD_DIA / 2000.0 - 0.010


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


def test_drawing_is_the_modified_stock_sheet() -> None:
    """A cut purchased part takes a manufacturing sheet with its cut length,
    not the dimensionless purchased reference sheet (boss hook's pattern)."""
    registry = DRAWINGS_BY_NAME["post_mount_screw"]
    assert drawing.SPEC is registry
    assert registry.artifact_stem == part.PART_NAME
    assert registry.script == Path(drawing.__file__).resolve()
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "build_purchased_fastener_drawing" not in source
    assert "Installation Notes" not in source


def test_sheet_passes_the_drawing_owned_precision_rule() -> None:
    violations = drawing_specification_violations(
        Path(drawing.__file__).read_text(encoding="utf-8"),
        filename=Path(drawing.__file__).name,
    )
    assert violations == ()


def test_standalone_recipe_run_is_catalog_only() -> None:
    # Codex #857 P2: MSC publishes no CAD, so the standalone command must not
    # enter the McMaster replica path (vendor SLDPRT + harvest).  It builds the
    # recipe and saves it; the documented command is that entry point.
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "replica_main(" not in source and "import replica_main" not in source
    assert "run_build(build_catalog)" in source
    assert "diag_build_40923898.py" in (recipe.__doc__ or "")
    assert "catalog-only" in (recipe.__doc__ or "")
