"""Offline contracts for the MHA-142 cone pivot post mount screw."""

from __future__ import annotations

import ast
import difflib
import hashlib
import subprocess
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
    # The one tolerance in the builder is the cut end's break (a single MAX
    # limit), never the length.
    assert "set_dimension_bilateral_tolerance(" not in builder
    helper = builder.split("def _single_limit_break", 1)[1].split("\ndef ", 1)[0]
    assert "CUT_END_BREAK_SKETCH, CUT_END_BREAK_DIMENSION" in helper
    assert builder.count("tolerance.Type = ") == 1
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
    cut length from its hidden reference sketch and the break from the deburr
    cutter's profile, and re-reads both."""
    assert spec.DRAWING_DIMENSIONS == {
        "CutLengthReference": {"CutLength"},
        "CutEndDeburrProfile": {"CutEndBreak"},
    }
    assert spec.REFERENCE_SKETCHES == ("CutLengthReference",)
    assert spec.DRAWING_PRECISION_BY_NAME == {"CutLength": 1, "CutEndBreak": 1}
    assert set(drawing.FRONT_KEEP) == {"CutLength"}
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in builder
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "hidden_sketches.curate_view_dimensions" in source
    assert "assert_imported_precision" in source


def test_cut_end_break_is_a_model_owned_deburr_of_at_most_0_1() -> None:
    """Main's engagement ruling: the cut end's break is 0.1 max (a deburr,
    not the title block's 0.25).  The model's CutEndBreak carries the band's
    deviations natively as a MAX-limit dimension; the note stays digit-free."""
    lower, upper = deviations(spec.CUT_END_BREAK_BAND)
    assert spec.CUT_END_BREAK_MM + upper <= 0.1 + 1e-12
    assert spec.CUT_END_BREAK_MM + lower >= 0.0
    assert spec.CUT_END_BREAK_MAX_MM == spec.CUT_END_BREAK_MM + upper
    assert spec.POST_MOUNT_TAP_EDGE_BREAK <= 0.1
    builder = Path(part.__file__).read_text(encoding="utf-8")
    helper = builder.split("def _single_limit_break", 1)[1].split("\ndef ", 1)[0]
    assert "lower, upper = deviations(CUT_END_BREAK_BAND)" in helper
    assert "tolerance.Type = CUT_END_BREAK_TOL_TYPE" in helper
    assert "_single_limit_break(adapter)" in builder
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


# MHA-142's own stock recipe (added by #857, touched by nobody else), pinned
# as its git blob (LF-normalised).  The cut end is MHA-142's modification:
# it must never leak into it.
_OWN_RECIPE_BLOBS = {
    "diagnostics/diag_build_40923898.py": "fed1a2b1c89e1cdf7ddc01baa01980b2aed39470",
}
# The SHARED fillister family recipe moves with the base (#839 added
# 91794A112 and dropped 90280A110 under it), so it is checked against the
# base, not pinned: #857's only change to it is this one size row.
_SHARED_RECIPE = "cad/scripts/diagnostics/diag_mcmaster_fillister.py"
_ROW_MARKER = '"40923898": '


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _git(*args: str) -> str:
    root = Path(part.__file__).resolve().parents[2]
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def _row_introducing_commit() -> str:
    """The one commit on HEAD's history that added the 40923898 size row to
    the shared recipe.  Its parent's copy of the file is #857's base (the
    merge base with #839) for this file: no later #857 commit touches it."""
    commits = _git(
        "log", "--format=%H", f"-S{_ROW_MARKER}", "HEAD", "--", _SHARED_RECIPE
    ).split()
    assert len(commits) == 1, f"expected one commit adding the row, got {commits}"
    return commits[0]


def _functions(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    return {
        node.name: ast.dump(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_shared_fillister_recipe_is_untouched() -> None:
    """Main's ruling on the cut end: the modification lives in MHA-142's
    builder, never in the family recipe (which would re-key every
    fillister screw for one part's fact).  Against the base (Main's option
    (b) after the restack onto #839): #857's only change to the shared
    recipe is its one FILLISTER_SIZES row, and every function in the
    recipe is identical to the base's."""
    scripts = Path(part.__file__).resolve().parent
    for relative, blob in _OWN_RECIPE_BLOBS.items():
        assert _git_blob_sha(scripts / relative) == blob, relative
    base = _git("show", f"{_row_introducing_commit()}^:{_SHARED_RECIPE}")
    head = (Path(part.__file__).resolve().parents[2] / _SHARED_RECIPE).read_text(
        encoding="utf-8"
    ).replace("\r\n", "\n")
    diff = [
        line
        for line in difflib.unified_diff(
            base.splitlines(), head.splitlines(), lineterm="", n=0
        )
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]
    removed = [line for line in diff if line.startswith("-")]
    added = [line[1:] for line in diff if line.startswith("+")]
    assert removed == [], removed
    rows = [line for line in added if _ROW_MARKER in line]
    assert len(rows) == 1, added
    assert all(line.strip().startswith("#") for line in added if line not in rows), added
    assert _functions(base) == _functions(head)
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
    assert part.DEBURR_DRIVES["CutterMargin"] == '"CutEndDeburrMargin"'
    assert part.DEBURR_DRIVES["CutterRise"] == (
        '"CutEndBreak@CutEndDeburrProfile" + "CutEndDeburrMargin"'
    )
    # CutEndBreak itself is the cutter's driving dimension: no equation.
    assert "CutEndBreak" not in part.DEBURR_DRIVES
    assert (part.TRIM_FEATURE, part.DEBURR_FEATURE) == ("CutToLength", "CutEndDeburr")
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source.split("async def _modify_stock", 1)[1].split("\ndef ", 1)[0]
    for step in (
        "_trim_to_cut_length(adapter)",
        "_check_removed(\"trim to cut length\"",
        "_break_cut_end(adapter)",
        "CUT_END_BREAK_SKETCH, CUT_END_BREAK_DIMENSION",
        "assert_break_removed_metal(rim_before, rim_after, brk)",
    ):
        assert step in body, step
    # The rim is read on the trimmed end BEFORE the break, then after it.
    assert body.index('phase="trimmed"') < body.index("_break_cut_end(adapter)")
    assert body.index("_break_cut_end(adapter)") < body.index('phase="broken"')
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
    assert "DEBURR CUT END" in notes
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
    assert not hasattr(drawing, "BREAK_TEXT")


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


# The first seat leaf of part:post_mount_screw on 198071f23 (farm log
# pms857-leaf.log, lines 310-373): stock-less-trimmed and stock-less-finished
# as SolidWorks' mass properties read them.
_LEAF_TRIM_REMOVED_MM3 = 67.4463
_LEAF_TRIM_AND_BREAK_REMOVED_MM3 = 67.4189


def test_the_break_is_below_the_volume_reads_resolution() -> None:
    """The analytic break (~0.015 mm^3) is smaller than the leaf's own
    mass-property residual on the trim alone, so no volume comparison can
    prove it: that leaf read the broken screw 0.027 mm^3 LARGER."""
    residual = abs(_LEAF_TRIM_REMOVED_MM3 - spec.TRIM_REMOVED_MM3)
    assert spec.CUT_END_DEBURR_REMOVED_MM3 < residual / 5.0
    assert _LEAF_TRIM_AND_BREAK_REMOVED_MM3 < _LEAF_TRIM_REMOVED_MM3
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source.split("async def _modify_stock", 1)[1].split("\ndef ", 1)[0]
    assert "finished < trimmed" not in body


def test_break_gate_decides_on_the_rim_before_and_after() -> None:
    """The leaf's break was right (profile r 3.075..3.675 at y -86); the gate
    must accept it from the exact rim reads, and still reject a break that
    cut nothing or cut the wrong depth."""
    major, brk = spec.MAJOR_RADIUS_MM, spec.CUT_END_BREAK_MM
    assert part.assert_break_removed_metal(major, major - brk, brk) == pytest.approx(brk)
    with pytest.raises(RuntimeError, match="removed no metal"):
        part.assert_break_removed_metal(major, major, brk)
    with pytest.raises(RuntimeError, match="less the"):
        part.assert_break_removed_metal(major, major - brk / 2.0, brk)
    with pytest.raises(RuntimeError, match="is not the major"):
        part.assert_break_removed_metal(major - brk, major - brk, brk)
    assert part.RIM_TOL_MM == 1e-4


# --- Main's MHA-142 eye pass on #857: the cut-end break callout -----------
# A 0.1 dimension at 1:1 printed "0.0" stacked over "0.1 -0.1": illegible,
# and +0/-0.1 read as permitting no break.  The note says DEBURR, the Front
# view drops the break, and a 10:1 tip detail prints the single limit.


def test_note_says_deburr_not_chamfer() -> None:
    notes = spec.MANUFACTURING_NOTES
    assert notes.splitlines()[0] == "DEBURR CUT END."
    assert "CHAMFER" not in notes
    assert not any(ch.isdigit() for ch in notes)


def test_front_view_carries_no_break_dimension() -> None:
    """The 1:1 Front claims only the cut length; the break is claimed only by
    the tip detail."""
    assert "CutEndBreak" not in drawing.FRONT_KEEP
    assert spec.FRONT_VIEW_DIMENSIONS == {"CutLengthReference": {"CutLength"}}
    assert spec.DETAIL_VIEW_DIMENSIONS == {"CutEndDeburrProfile": {"CutEndBreak"}}
    assert set(drawing.DETAIL_KEEP) == {"CutEndBreak"}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "dimensions_by_feature=FRONT_VIEW_DIMENSIONS" in source
    # The detail's import is the entire-model form, never the targeted one.
    assert "dimensions_by_feature=DETAIL_VIEW_DIMENSIONS" not in source
    assert "BREAK_CONTROLS" not in source and "offset_dimension_text" not in source


def test_tip_detail_prints_the_band_max_as_a_single_limit() -> None:
    """The detail's dimension reads the spec band's max at its places, as a
    swTolMAX single limit; the seat read-back composes the same text."""
    lower, upper = deviations(spec.CUT_END_BREAK_BAND)
    places = spec.DRAWING_PRECISION_BY_NAME["CutEndBreak"]
    expected = f"{spec.CUT_END_BREAK_MM + upper:.{places}f} MAX"
    assert spec.CUT_END_BREAK_TEXT == expected == "0.1 MAX"
    assert spec.CUT_END_BREAK_TOL_TYPE == 6  # swTolType_e.swTolMAX
    # swTolMAX prints the nominal, so the nominal must be the band's max.
    assert spec.CUT_END_BREAK_MM == spec.CUT_END_BREAK_MAX_MM
    # Tighter than the title block's general chamfer, or it would not print.
    general = float(_config.title_block("edge_break")["chamfer_max_mm"])
    assert spec.TITLE_BLOCK_CHAMFER_MAX_MM == general
    assert spec.CUT_END_BREAK_MAX_MM < general
    # The seat composes the rendered text from the read-back parts.
    assert drawing.break_text(spec.CUT_END_BREAK_MAX_MM, places, 6, "", "") == expected
    assert drawing.break_text(spec.CUT_END_BREAK_MAX_MM, places, 2, "", "") != expected
    assert drawing.break_text(spec.CUT_END_BREAK_MAX_MM, places, 6, "(", ")") != expected
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("_verify_tip_detail(adapter, front, detail)") == 2
    block = source.split('_telemetry.span("drawing.tip_detail"', 1)[1]
    block = block.split("assert_imported_precision(adapter, detail_annotations", 1)[0]
    assert "trim_drawing.end_detail(adapter, front, TIP_DETAIL)" in block
    assert "_curate_tip_detail(adapter, detail)" in block
    assert "hidden_sketches.curate_view_dimensions(" not in block


def test_tip_detail_geometry_keeps_the_break_inside_its_crop() -> None:
    """A detail drops any dimension whose reference lies outside its crop:
    both ends of the break's radial leg must sit inside the fence."""
    assert drawing.DETAIL_SCALE == (10.0, 1.0)
    reference_y = -spec.CUT_LENGTH_MM + drawing.DETAIL_OFFSET_MM
    assert drawing.TIP_DETAIL.detail_reference_mm == (0.0, reference_y, 0.0)
    for radius in (spec.MAJOR_RADIUS_MM, spec.MAJOR_RADIUS_MM - spec.CUT_END_BREAK_MM):
        reach = math.hypot(radius, -spec.CUT_LENGTH_MM - reference_y)
        assert reach < drawing.DETAIL_FENCE_MM - 0.25


# Named margins for the sheet-local layout of the tip detail.
DETAIL_BORDER_MARGIN = 0.013  # sheet edge to the inner frame, plus clearance
DETAIL_VIEW_GAP = 0.010  # detail circle to any other view's ink
DETAIL_NOTE_GAP = 0.008  # detail circle or label to the note block


def test_tip_detail_layout_is_clear() -> None:
    from _drawing_registry import DRAWING_TEMPLATES

    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    cx, cy = drawing.DETAIL_CENTER
    r = drawing.DETAIL_RADIUS
    assert r == pytest.approx(drawing.DETAIL_FENCE_MM * 10.0 / 1000.0)
    # Inside the frame.
    assert cy + r < template.height_m - DETAIL_BORDER_MARGIN
    # Right of the Front view's head, left of the isometric's head.
    assert cx - r > drawing.FRONT_CENTER[0] + part.HEAD_DIA / 2000.0 + DETAIL_VIEW_GAP
    assert cx + r < drawing.ISO_CENTER[0] - part.HEAD_DIA / 2000.0 - DETAIL_VIEW_GAP
    # Above the title block and the note block.
    assert cy - r > template.title_block_top_m + DETAIL_VIEW_GAP
    notes_top = drawing.NOTES_XY[1] + 0.004
    assert cy - r > notes_top + DETAIL_NOTE_GAP
    label_x, label_y = drawing.TIP_DETAIL.detail_label_xy
    assert label_y > notes_top + DETAIL_NOTE_GAP
    assert label_y > template.title_block_top_m + DETAIL_NOTE_GAP
    assert label_x < template.title_block_left_m or label_y > template.title_block_top_m
    # The break's text sits inside the detail's column, below the end face.
    text_x, text_y = drawing.DETAIL_KEEP["CutEndBreak"]
    rim_x, rim_y = drawing.BREAK_RIM_XY
    assert text_y < rim_y
    assert cx - r < text_x < drawing.ISO_CENTER[0] - part.HEAD_DIA / 2000.0 - DETAIL_VIEW_GAP
    assert text_y > label_y + DETAIL_NOTE_GAP / 2.0


def test_break_is_owned_by_the_deburr_cutter_not_a_hidden_reference_sketch() -> None:
    """pms857-f543 (f54309af5): the 10:1 detail imported nothing from the
    part-hidden CutEndBreakReference, even shown in memory around the detail
    ("tip detail break view is missing model dimensions: ['CutEndBreak']").
    The agreed fallback is the boss hook's pattern: the break is a driving
    dimension of the deburr cutter's own (consumed) profile."""
    assert spec.CUT_END_BREAK_SKETCH == part.DEBURR_PROFILE == "CutEndDeburrProfile"
    assert spec.REFERENCE_SKETCHES == ("CutLengthReference",)
    assert not hasattr(spec, "DETAIL_SKETCHES")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "part_sketches_shown(" not in source
    builder = Path(part.__file__).read_text(encoding="utf-8")
    controls = builder.split("async def _author_cut_controls", 1)[1].split("\nasync def ", 1)[0]
    assert "CUT_END_BREAK_SKETCH" not in controls
    cutter = builder.split("async def _break_cut_end", 1)[1].split("\nasync def ", 1)[0]
    assert "dims.record(CUT_END_BREAK_DIMENSION)" in cutter
    # The break leg is the inner of two collinear legs split at the major
    # radius, and that split point is the one anchored to the origin.
    assert "(radius - CUT_END_BREAK_MM, end),\n                (radius, end)," in cutter
    assert 'f"{lines[1]}.start", radius, end, DEBURR_PROFILE' in cutter


class _FakeDetailView:
    """A derived view as the two MHA-142 leaves saw it: it has a base view."""

    def GetBaseView(self):
        return object()


def _fake_detail_seat(monkeypatch):
    """Model pms857-f543/56f7: into the detail, the targeted selected-feature
    import (source 1) returns nothing; the entire-model import (source 0)
    returns the marked CutEndBreak."""
    import _drawing_common as dc
    import _drawing_hidden_sketches as hs

    break_annotation = object()
    calls: list[str] = []

    def targeted(adapter, view, features):
        calls.append(f"source1:{list(features)}")
        return []

    def entire(adapter, view):
        calls.append("source0")
        return [break_annotation]

    monkeypatch.setattr(dc, "insert_feature_dimensions", targeted)
    monkeypatch.setattr(dc, "insert_marked_dimensions", entire)
    monkeypatch.setattr(dc, "delete_unnamed_imports", lambda adapter, items: list(items))
    monkeypatch.setattr(
        dc,
        "dimension_name",
        lambda adapter, item: "CutEndBreak" if item is break_annotation else "",
    )
    monkeypatch.setattr(
        dc,
        "curate_dimensions",
        lambda adapter, items, delete=(), reposition=None: list(items),
    )
    monkeypatch.setattr(hs, "_show_hidden_owners", lambda *a, **k: [])
    monkeypatch.setattr(hs, "_warn_undetected_owners", lambda *a, **k: [])
    return break_annotation, calls


def test_targeted_import_into_the_tip_detail_raises_as_on_the_seat(monkeypatch) -> None:
    """The observed failure shape, pinned: the targeted form the two leaves
    ran returns nothing into the detail and raises "missing model
    dimensions"."""
    import _drawing_hidden_sketches as hs

    _, calls = _fake_detail_seat(monkeypatch)
    with pytest.raises(RuntimeError, match="missing model dimensions: \\['CutEndBreak'\\]"):
        hs.curate_view_dimensions(
            object(),
            _FakeDetailView(),
            keep=drawing.DETAIL_KEEP,
            view_label="tip detail break",
            dimensions_by_feature=spec.DETAIL_VIEW_DIMENSIONS,
        )
    assert calls == ["source1:['CutEndDeburrProfile']"]


def test_tip_detail_takes_the_break_through_the_entire_model_import(monkeypatch) -> None:
    """Option A (Main): only the import source changes -- the tip detail uses
    the boss hook's entire-model form, and so receives the break."""
    break_annotation, calls = _fake_detail_seat(monkeypatch)
    monkeypatch.setattr(
        drawing,
        "read_detail_visible_entities",
        lambda adapter, detail: calls.append("visible") or {},
    )
    curated = drawing._curate_tip_detail(object(), _FakeDetailView())
    assert curated == [break_annotation]
    # The visible-entity read runs BEFORE the import (pms857-diag-9eca).
    assert calls == ["visible", "source0"]


class _FakeVisibleView:
    """IView stand-in: 2 edges and 3 vertices on one component."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    def GetVisibleComponents(self):
        return ("screw",)

    def GetVisibleEntities2(self, component, entity_type):
        self.calls.append(entity_type)
        return {1: ("e1", "e2"), 2: ("v1", "v2", "v3")}[entity_type]


def test_visible_entity_read_counts_edges_and_vertices(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    view = _FakeVisibleView()
    counts = drawing.read_detail_visible_entities(object(), view)
    assert counts == {"components": 1, "edges": 2, "vertices": 3}
    assert view.calls == [1, 2]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source.split("def read_detail_visible_entities", 1)[1].split("\ndef ", 1)[0]
    body = " ".join(body.split())
    assert "may be seat variance" in body
    assert "pms857-f543, -56f7, -6099" in body and "pms857-diag-9eca" in body


def test_front_is_active_before_the_notes() -> None:
    """pms857-diag-9eca: the four property-linked notes landed in the active
    tip detail ("expected one native detail label, found 5").  The Front is
    activated after the detail's curate and before the first note."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source.split("async def build", 1)[1]
    detail = body.index("_curate_tip_detail(adapter, detail)")
    activate = body.index("activate_front_for_notes(adapter, front)")
    first_note = body.index("add_property_linked_note(")
    label = body.index("trim_drawing.position_detail_label(")
    assert detail < activate < first_note < label


def test_activate_front_for_notes_activates_the_front_by_name(monkeypatch) -> None:
    activated: list[str] = []

    class _Doc:
        def ActivateView(self, name):
            activated.append(name)
            return name == "Drawing View1"

    class _Adapter:
        currentModel = _Doc()

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "view_name", lambda adapter, view: view)
    drawing.activate_front_for_notes(_Adapter(), "Drawing View1")
    assert activated == ["Drawing View1"]
    with pytest.raises(RuntimeError, match="Front view"):
        drawing.activate_front_for_notes(_Adapter(), "Detail View A (10 : 1)")
