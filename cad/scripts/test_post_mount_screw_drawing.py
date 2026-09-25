"""Offline contracts for the MHA-142 cone pivot post mount screw."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pytest

import _config
import build_post_mount_screw as part
import cone_pivot_post_spec as post
import cone_swing_platform_spec as platform
import draw_post_mount_screw as drawing
from _fit_limits import deviations
import post_mount_screw_spec as spec
from _drawing_contract import drawing_specification_violations
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_40923898 as recipe
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

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


def test_no_fixed_cut_length_fits_both_in_band_corners() -> None:
    """U27, geometry first: across the printed post and plate bands, the
    never-proud corner (lowest counterbore floor, thin plate) caps a fixed
    length below what the 0.90D corner (highest floor, after both edge
    breaks) needs.  So no band can go on the print."""
    one = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
    two = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
    low = (round(post.BLOCK_HEIGHT, 1) - one) - (
        round(post.ATTACHMENT_CBORE_DEPTH, 2) + two
    )
    high = (round(post.BLOCK_HEIGHT, 1) + one) - (
        round(post.ATTACHMENT_CBORE_DEPTH, 2) - two
    )
    assert (spec.FLOOR_LOW_MM, spec.FLOOR_HIGH_MM) == pytest.approx((low, high))
    assert (low, high) == pytest.approx((78.67, 81.29))
    thin = platform.PLATE_THICKNESS - spec.PLATE_STOCK_BAND_MM
    assert spec.FIXED_LENGTH_FLUSH_MAX_MM == pytest.approx(low + thin)
    need = (
        high
        + 0.90 * part.SHANK_DIA
        + spec.POST_MOUNT_TAP_EDGE_BREAK
        + spec.CUT_END_BREAK_MAX_MM
    )
    assert spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM == pytest.approx(need)
    assert spec.FIXED_LENGTH_FLUSH_MAX_MM == pytest.approx(84.89)
    assert spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM == pytest.approx(87.205)
    assert spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM > spec.FIXED_LENGTH_FLUSH_MAX_MM
    assert spec.FIXED_CUT_LENGTH_EXISTS is False


def test_cut_length_prints_as_a_reference_without_a_band() -> None:
    """No fixed length exists, so the model's 86.0 prints as "(86.0)" with
    no tolerance; the callout beneath it carries the fit-to-hole acceptance
    (see test_cut_to_fit_acceptance_prints_on_the_delegating_callout)."""
    assert spec.CUT_LENGTH_MM == part.SHANK_LEN == 86.0
    assert not hasattr(spec, "CUT_LENGTH_BAND")
    assert not hasattr(drawing, "EXPECTED_CONTROLS")
    builder = Path(part.__file__).read_text(encoding="utf-8")
    # The one band in the builder is the cut end's break, never the length.
    calls = builder.split("set_dimension_bilateral_tolerance(")[1:]
    assert len(calls) == 1
    assert calls[0].split(")")[0].split(",")[1].strip() == "CUT_END_BREAK_SKETCH"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_reference_dimension(" in source
    assert "swTolNONE" in source
    callout = drawing.DIMENSION_CALLOUTS["CutLength"]
    # The callout still promises no fixed length: never the modelled cut
    # length, never a band on it.
    assert f"{spec.CUT_LENGTH_MM:.1f}" not in callout
    assert "±" not in callout and "+" not in callout


def test_cut_to_fit_acceptance_prints_on_the_delegating_callout() -> None:
    """Codex P1 on #857: the callout delegated the cut to assembly, but no
    MHA-A03 step stated the acceptance the 0.90D worst case depends on.  The
    acceptance is a spec band -- upper 0 (never proud), lower the most a
    screw may be cut short -- and the callout prints it, generated from that
    band at the cut length's places, not a literal."""
    lower, upper = deviations(spec.POST_SCREW_CUT_TO_FIT_BAND)
    assert upper == 0.0
    assert spec.POST_SCREW_CUT_TO_FIT_SHORT == -lower
    places = spec.DRAWING_PRECISION_BY_NAME["CutLength"]
    callout = drawing.DIMENSION_CALLOUTS["CutLength"]
    assert callout == spec.CUT_TO_FIT_CALLOUT
    flat = " ".join(callout.split())
    assert flat.startswith("CUT TO FIT AT ASSEMBLY")
    assert f"FLUSH TO {-lower:.{places}f} SHORT OF MHA-091 UNDERSIDE" in flat
    assert "NEVER PROUD" in flat
    # The printed allowance is the one the named exception's worst case
    # spends: thinnest plate, full allowance, both breaks at their maximum.
    assert spec.POST_MOUNT_ENGAGEMENT_WORST == pytest.approx(
        platform.PLATE_THICKNESS
        - spec.PLATE_STOCK_BAND_MM
        - (-lower)
        - spec.POST_MOUNT_TAP_EDGE_BREAK
        - spec.CUT_END_BREAK_MAX_MM
    )
    assert spec.POST_MOUNT_ENGAGEMENT_WORST / spec.THREAD_DIA_MM >= spec.MIN_ENGAGEMENT_DIAMETERS
    # No other sheet text restates it: the part notes stay digit-free.
    assert not any(ch.isdigit() for ch in spec.MANUFACTURING_NOTES)


def test_cut_to_fit_allowance_is_exported_once() -> None:
    """The per-hole allowance MHA-A03 and the platform stack consume."""
    assert spec.POST_SCREW_CUT_TO_FIT_SHORT == 0.3


def test_cut_length_is_a_model_owned_drawing_dimension() -> None:
    """Rule 2: the value and places are the part's; the sheet imports the
    one marked dimension from its hidden reference sketch and re-reads it."""
    assert spec.DRAWING_DIMENSIONS == {
        "CutLengthReference": {"CutLength"},
        "CutEndBreakReference": {"CutEndBreak"},
    }
    assert spec.REFERENCE_SKETCHES == ("CutLengthReference", "CutEndBreakReference")
    assert spec.DRAWING_PRECISION_BY_NAME == {"CutLength": 1, "CutEndBreak": 1}
    assert set(drawing.FRONT_KEEP) == {"CutLength", "CutEndBreak"}
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in builder
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "hidden_sketches.curate_view_dimensions" in source
    assert "assert_imported_precision" in source


def test_cut_end_break_is_a_model_owned_deburr_of_at_most_0_1() -> None:
    """Main's engagement ruling: the cut end's break is 0.1 max (a deburr,
    not the title block's 0.25), banded on the model's CutEndBreak dimension
    and re-read on the sheet; the note stays digit-free."""
    lower, upper = deviations(spec.CUT_END_BREAK_BAND)
    assert spec.CUT_END_BREAK_MM + upper <= 0.1 + 1e-12
    assert spec.CUT_END_BREAK_MM + lower >= 0.0
    assert spec.CUT_END_BREAK_MAX_MM == spec.CUT_END_BREAK_MM + upper
    assert spec.POST_MOUNT_TAP_EDGE_BREAK <= 0.1
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert "lower, upper = deviations(CUT_END_BREAK_BAND)" in builder
    assert "CUT_END_BREAK_DIMENSION" in builder
    nominal, low, high = drawing.BREAK_CONTROLS["CutEndBreak"]
    assert (nominal, low, high) == pytest.approx(
        (spec.CUT_END_BREAK_MM / 1000, lower / 1000, upper / 1000)
    )
    assert drawing.BREAK_TOLERANCE_TYPES == {"CutEndBreak": 2}  # swTolBILAT
    assert not any(ch.isdigit() for ch in spec.MANUFACTURING_NOTES)


def test_worst_case_engagement_holds_the_named_minimum() -> None:
    """Cut to fit, the plate limits engagement: thinnest stock, the full
    fit-to-hole allowance, the tap's entry deburr and the cut end's break,
    both at their maximum.  Recomputed here from the chain: 5.72 = 0.90D."""
    lower, upper = deviations(spec.CUT_END_BREAK_BAND)
    worst = (
        platform.PLATE_THICKNESS
        - spec.PLATE_STOCK_BAND_MM
        - spec.POST_SCREW_CUT_TO_FIT_SHORT
        - spec.POST_MOUNT_TAP_EDGE_BREAK
        - (spec.CUT_END_BREAK_MM + upper)
    )
    assert spec.POST_MOUNT_ENGAGEMENT_WORST == pytest.approx(worst)
    assert worst == pytest.approx(5.72)
    assert worst / part.SHANK_DIA >= 0.90
    assert spec.POST_MOUNT_ENGAGEMENT_PRINTED >= 0.90


# The shared fillister recipe's git blobs (LF-normalised) at 695af67a0.  The
# cut end is MHA-142's own modification: it must never leak into the family.
_RECIPE_BLOBS = {
    "diagnostics/diag_mcmaster_fillister.py": "01b1860f31fd5ffd179bbe1e1fd73de590425383",
    "diagnostics/diag_build_40923898.py": "fed1a2b1c89e1cdf7ddc01baa01980b2aed39470",
}


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def test_shared_fillister_recipe_is_untouched() -> None:
    """Main's ruling on the cut end: the modification lives in MHA-142's
    builder, never in the family recipe (which would re-key every
    fillister screw for one part's fact)."""
    scripts = Path(part.__file__).resolve().parent
    for relative, blob in _RECIPE_BLOBS.items():
        assert _git_blob_sha(scripts / relative) == blob, relative
    assert FILLISTER_SIZES["40923898"][1] == 86.0


def test_stock_is_built_at_its_supplied_length_then_restored() -> None:
    """The recipe runs at the supplied 3-1/2 in, so the trim has a factory
    tip to remove; the size row comes back even if the recipe raises."""
    assert spec.STOCK_LENGTH_MM == pytest.approx(3.5 * 25.4)
    modelled = FILLISTER_SIZES["40923898"]
    with pytest.raises(RuntimeError):
        with part._supplied_stock_length():
            assert FILLISTER_SIZES["40923898"][1] == spec.STOCK_LENGTH_MM
            assert FILLISTER_SIZES["40923898"][0] == modelled[0]
            raise RuntimeError("recipe failed")
    assert FILLISTER_SIZES["40923898"] == modelled


def _independent_removal() -> tuple[float, float]:
    """Brute-force the two removed volumes (midpoint rule, 20k slices):
    at radius r the groove takes w(r)/P of the circumference, w(r) the
    cutter's axial width, P/8 at the root, widening 2 tan 30 per mm."""
    radius, pitch = part.SHANK_DIA / 2.0, part.THREAD_PITCH
    root = radius - 0.75 * pitch * math.sqrt(3.0) / 2.0
    tip = 0.7 * pitch

    def metal(section: float, steps: int = 400) -> float:
        total = math.pi * section**2
        if section > root:
            width = (section - root) / steps
            for i in range(steps):
                r = root + (i + 0.5) * width
                groove = pitch / 8.0 + 2.0 / math.sqrt(3.0) * (r - root)
                total -= 2.0 * math.pi * r * groove / pitch * width
        return total

    stock, cut = spec.STOCK_LENGTH_MM, spec.CUT_LENGTH_MM
    slices = 2000
    height = tip / slices
    trim = sum(
        metal(radius - tip + (i + 0.5) * height) * height for i in range(slices)
    )
    trim += metal(radius) * (stock - tip - cut)
    brk = spec.CUT_END_BREAK_MM
    height = brk / slices
    deburr = sum(
        (metal(radius) - metal(radius - brk + (i + 0.5) * height)) * height
        for i in range(slices)
    )
    return trim, deburr


def test_analytic_removal_volumes_match_a_brute_force_integral() -> None:
    trim, deburr = _independent_removal()
    assert spec.TRIM_REMOVED_MM3 == pytest.approx(trim, rel=1e-4)
    assert spec.CUT_END_DEBURR_REMOVED_MM3 == pytest.approx(deburr, rel=1e-3)
    assert spec.TRIM_REMOVED_MM3 == pytest.approx(67.581, abs=1e-3)
    assert spec.CUT_END_DEBURR_REMOVED_MM3 == pytest.approx(0.0153, abs=1e-4)


def test_cut_end_features_are_driven_by_the_model_dimensions() -> None:
    """The trim follows CutLength and the 45 deg break's legs follow
    CutEndBreak, by equation; the build proves the end face's rim sits at
    the major radius less CutEndBreak."""
    assert part.TRIM_DRIVES == {"TrimAt": '"CutLength@CutLengthReference"'}
    assert part.DEBURR_DRIVES["CutEnd"] == '"CutLength@CutLengthReference"'
    for leg in ("CutterRun", "CutterRise"):
        assert part.DEBURR_DRIVES[leg] == (
            '"CutEndBreak@CutEndBreakReference" + "CutEndDeburrMargin"'
        )
    assert (part.TRIM_FEATURE, part.DEBURR_FEATURE) == ("CutToLength", "CutEndDeburr")
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source.split("async def _modify_stock", 1)[1].split("\ndef ", 1)[0]
    for step in (
        "_trim_to_cut_length(adapter)",
        "_check_removed(\"trim to cut length\"",
        "_break_cut_end(adapter)",
        "CUT_END_BREAK_SKETCH, CUT_END_BREAK_DIMENSION",
        "MAJOR_RADIUS_MM - brk",
    ):
        assert step in body, step
    wrapper = source.split("async def _cut_to_length", 1)[1]
    assert wrapper.index("_supplied_stock_length()") < wrapper.index("_modify_stock")
    # The trimmed tip cannot reach into what the stock carries: the cut
    # clears the factory tip, and the volume gate outruns the sweep's slack.
    assert spec.STOCK_LENGTH_MM - spec.FACTORY_TIP_CHAMFER_MM > spec.CUT_LENGTH_MM
    assert part.TRIM_VOLUME_TOL_MM3 < 0.01 * spec.TRIM_REMOVED_MM3


def test_finish_oils_the_bare_cut_end() -> None:
    """Rule 1: bare-surface protection is the Finish field's, worded like the
    boss hook's (MHA-005), never a note."""
    finish = _config.parts(part.PART_NAME)["finish"]
    boss = _config.parts("boss-hook")["finish"]
    assert finish == boss == "SUPPLIED ZINC PLATING; OIL BARE CUT END"
    assert "OIL" not in spec.MANUFACTURING_NOTES


def test_sheet_notes_carry_no_dimension_rule_or_sequence() -> None:
    """Main's eye pass of warm-c486 (rule 6): the old INSTALLATION block
    printed "(NOMINAL 86.0)", "0.90D MIN" and "NAMED EXCEPTION TO RULE 12".
    The cut length is now a reference dimension, engagement a model assert
    and the sequence an MHA-A03 step, so no part note carries a number."""
    row = _config.parts(part.PART_NAME)
    assert "installation_notes" not in row
    notes = spec.MANUFACTURING_NOTES
    assert not any(ch.isdigit() for ch in notes)
    assert "CHAMFER CUT END" in notes
    for word in ("RULE", "EXCEPTION", "ENGAGEMENT", "NOMINAL", "INSTALL", "MHA-"):
        assert word not in notes
    assert len(notes.splitlines()) <= 4


def test_engagement_exception_is_held_by_the_model() -> None:
    """The named rule-12 exception (0.90D) is a model assert on the chain."""
    assert spec.MIN_ENGAGEMENT_DIAMETERS == 0.90
    assert spec.ENGAGEMENT_NOMINAL_MM == spec.CUT_LENGTH_MM - GRIP
    assert spec.ENGAGEMENT_NOMINAL_MM / part.SHANK_DIA >= 0.90


def test_sheet_layout_keeps_notes_clear_of_the_view() -> None:
    """1:1 Front view spans ~92 mm around its centre; the note block sits
    between it and the stock rows, the cut length left of the shank."""
    half_h = (spec.CUT_LENGTH_MM + part.HEAD_H) / 2000.0
    view_bottom = drawing.FRONT_CENTER[1] - half_h
    notes_y = drawing.NOTES_XY[1]
    assert notes_y + 0.004 < view_bottom
    lines = len(spec.MANUFACTURING_NOTES.splitlines())
    assert notes_y - lines * 0.0045 > max(y for _, _, y in drawing.STOCK_ROWS) + 0.003
    # The widest callout line (~2.85 mm per capital, warm-c486) clears the
    # head's silhouette, the widest part of the view.
    x, _ = drawing.FRONT_KEEP["CutLength"]
    widest = max(len(line) for line in drawing.DIMENSION_CALLOUTS["CutLength"].splitlines())
    assert x + widest * 0.00285 / 2.0 < drawing.FRONT_CENTER[0] - part.HEAD_DIA / 2000.0 - 0.003
    assert x - widest * 0.00285 / 2.0 > 0.015  # inside the border
    # The break's leadered text: right of the shank, above the note block.
    text_x, text_y = drawing.BREAK_TEXT
    assert text_x - 0.004 > drawing.FRONT_CENTER[0] + part.SHANK_DIA / 2000.0 + 0.010
    assert text_y - 0.004 > notes_y + 0.004
    assert text_y < drawing.TIP_Y


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
