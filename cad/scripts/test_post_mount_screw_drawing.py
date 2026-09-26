"""Offline contracts for the MHA-142 cone pivot post mount screw."""

from __future__ import annotations

import ast
import difflib
import hashlib
import subprocess
import math
import re
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
    """1/4-20, ASME B18.6.3 1/4 fillister head maximum, 86.2 cut length."""
    assert part.THREAD == platform.POST_MOUNT_SPEC.size == "1/4-20"
    assert part.SHANK_DIA == THREAD_MAJOR_MM[part.THREAD]
    assert part.THREAD_PITCH == IN / 20.0
    assert part.SHANK_LEN == 86.2
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
    """No fixed length exists, so the model's 86.2 prints as "(86.2)" with
    no tolerance; the callout beneath it carries the fit-to-hole acceptance
    (see test_cut_to_fit_acceptance_prints_on_the_delegating_callout)."""
    assert spec.CUT_LENGTH_MM == part.SHANK_LEN == 86.2
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


def test_engagement_minimum_prints_on_the_cut_length_callout() -> None:
    """Codex P2 on #857 (PRRT_kwDOPHDy386mOxdw): MHA-142 stated its 0.90D
    engagement shortfall nowhere, yet the policy's named-exceptions section
    wants every affected sheet to state it.  The callout that delegates the
    cut carries the worst-case minimum as a plain fact, floored from the
    spec's worst case -- never a literal."""
    callout = drawing.DIMENSION_CALLOUTS["CutLength"]
    printed = spec.POST_MOUNT_ENGAGEMENT_PRINTED
    assert printed == math.floor(
        spec.POST_MOUNT_ENGAGEMENT_WORST / spec.THREAD_DIA_MM * 100.0
    ) / 100.0
    assert printed >= spec.MIN_ENGAGEMENT_DIAMETERS
    fact = f"ENGAGEMENT {printed:.2f}D MIN"
    assert fact in callout.splitlines()
    # It closes the acceptance the cut delegates to assembly.
    assert callout.splitlines()[-1] == fact


# Words that cite the exception's LABEL rather than state its fact (Main's
# fleet ruling on the Codex P2): no rule, ruling, policy or exception words,
# and no user-ruling ids such as "U37c".
_BANNED_ON_SHEET = re.compile(
    r"\b(EXCEPTIONS?|ACCEPTED|RULES?|RULINGS?|POLICY|U\d+[A-Z]?)\b", re.IGNORECASE
)


def _mha142_printed_strings() -> dict[str, str]:
    config = _config.parts("post-mount-screw")
    printed = {
        "CutLength callout": drawing.DIMENSION_CALLOUTS["CutLength"],
        "manufacturing notes": spec.MANUFACTURING_NOTES,
        "tip view label": drawing.TIP_VIEW_LABEL,
        "tip letter": drawing.TIP_LETTER,
    }
    for index, text in drawing.DRAWING_SUMMARY.items():
        printed[f"summary {index}"] = text
    for field in (
        "title",
        "number",
        "stock_name",
        "supplier",
        "material",
        "material_specification",
        "finish",
        "installation_notes",
    ):
        if field in config:
            printed[f"yaml {field}"] = str(config[field])
    return printed


def test_banned_word_scan_catches_a_cited_exception() -> None:
    """Positive control: the scan flags the label forms it exists to keep off."""
    for text in (
        "ENGAGEMENT 0.90D MIN (ACCEPTED EXCEPTION)",
        "PER RULE 12",
        "SEE RULING U37c",
        "POLICY: CUT TO FIT",
    ):
        assert _BANNED_ON_SHEET.search(text), text
    assert not _BANNED_ON_SHEET.search("ENGAGEMENT 0.90D MIN")
    assert not _BANNED_ON_SHEET.search("OF MHA-091 UNDERSIDE, NEVER PROUD")


def test_mha142_prints_no_exception_label() -> None:
    printed = _mha142_printed_strings()
    assert "CutLength callout" in printed and "yaml finish" in printed
    hits = {
        name: match.group(0)
        for name, text in printed.items()
        if (match := _BANNED_ON_SHEET.search(text))
    }
    assert hits == {}


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
    # Re-pinned for the Codex P2 fix: its docstring now names the supplied
    # 3-1/2 in length, not the cut length.
    "diagnostics/diag_build_40923898.py": "0bd238baecda45dbac899bca6326245deb070113",
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
    assert FILLISTER_SIZES["40923898"][1] == spec.STOCK_LENGTH_MM


def test_catalog_row_is_the_supplied_stock_and_only_the_part_is_cut() -> None:
    """Codex P2 on #857 (PRRT_kwDOPHDy386mP6Dj): the MSC 40923898 row held
    the cut length, so the catalog build (40923898-catalog.SLDPRT) and
    any direct stock consumer got the modified length labelled as supplier
    stock; only MHA-142's builder swapped in 3-1/2 in.  The row is the
    supplied screw; the cut-to-fit length is MHA-142's own spec, applied by
    its trim, and the builder never mutates the shared row."""
    assert FILLISTER_SIZES["40923898"][1] == pytest.approx(3.5 * 25.4)
    assert spec.STOCK_LENGTH_MM == FILLISTER_SIZES["40923898"][1]
    assert part.SHANK_LEN == spec.CUT_LENGTH_MM == 86.2
    assert not hasattr(part, "_supplied_stock_length")
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "FILLISTER_SIZES[SKU] =" not in source


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
    assert spec.TRIM_REMOVED_MM3 == pytest.approx(62.733, abs=1e-3)
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
    assert wrapper.index("build_40923898(") < wrapper.index("_modify_stock")
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
    The cut length is now a reference dimension, the engagement minimum a
    line of its callout (never a note) and the sequence an MHA-A03 step, so
    no part note carries a number."""
    row = _config.parts(part.PART_NAME)
    assert "installation_notes" not in row
    notes = spec.MANUFACTURING_NOTES
    assert not any(ch.isdigit() for ch in notes)
    assert "DEBURR CUT END" in notes
    for word in ("RULE", "EXCEPTION", "ENGAGEMENT", "NOMINAL", "INSTALL", "MHA-"):
        assert word not in notes
    assert len(notes.splitlines()) <= 4


def _printed_cut_short_allowance() -> float:
    """The acceptance the sheet prints: "END FLUSH TO <x> SHORT"."""
    match = re.search(r"END FLUSH TO (\d+(?:\.\d+)?) SHORT", spec.CUT_TO_FIT_CALLOUT)
    assert match, spec.CUT_TO_FIT_CALLOUT
    return float(match.group(1))


def _short_of_underside(length_mm: float) -> float:
    """How far a screw of this length ends short of the MHA-091 underside on
    the nominal post and plate (negative: proud)."""
    return GRIP + platform.PLATE_THICKNESS - length_mm


def test_the_modelled_length_is_a_cut_the_sheet_accepts() -> None:
    """Codex P2 on #857 (PRRT_kwDOPHDy386mRhqY): the source CAD must satisfy
    its own sheet.  On the nominal post and plate the flush length is
    86.0 - 6.0198 + 6.35 = 86.3302, so the old 86.0 ended 0.33 short --
    outside the callout's "END FLUSH TO 0.3 SHORT".  The modelled length is
    the flush length less the allowance's midpoint, at its printed places."""
    allowance = _printed_cut_short_allowance()
    assert allowance == 0.3

    def accepted(length_mm: float) -> bool:
        return 0.0 <= _short_of_underside(length_mm) <= allowance

    assert not accepted(86.0)
    assert accepted(spec.CUT_LENGTH_MM)
    assert spec.CUT_LENGTH_MM == 86.2
    places = spec.DRAWING_PRECISION_BY_NAME[spec.CUT_LENGTH_DIMENSION]
    assert spec.CUT_LENGTH_MM == round(
        _short_of_underside(0.0) - allowance / 2.0, places
    )
    assert part.SHANK_LEN == spec.CUT_LENGTH_MM


def test_policy_exception_row_names_the_length_constant_not_a_number() -> None:
    """Codex P2 on #857 (PRRT_kwDOPHDy386mRsWJ): the policy's named-exception
    row still read "nominal 86.0" after the model moved to 86.2.  The row
    names the spec constant and its rule, so it carries no number that can
    drift from the model."""
    policy = Path(part.__file__).resolve().parents[1] / "docs" / "drawing-simplicity-policy.md"
    rows = [
        line
        for line in policy.read_text(encoding="utf-8").splitlines()
        if line.startswith("| MHA-142 ")
    ]
    assert len(rows) == 1, rows
    assert "post_mount_screw_spec.CUT_LENGTH_MM" in rows[0]
    assert not re.search(r"nominal \d", rows[0]), rows[0]
    assert f"{spec.CUT_LENGTH_MM:.1f}" not in rows[0]


def test_engagement_exception_is_held_by_the_model() -> None:
    """The named rule-12 exception (0.90D) is a model assert on the chain;
    the sheet prints it on the cut-length callout
    (test_engagement_minimum_prints_on_the_cut_length_callout)."""
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
    the 10:1 tip view, and both import by feature (never the entire model)."""
    assert "CutEndBreak" not in drawing.FRONT_KEEP
    assert spec.FRONT_VIEW_DIMENSIONS == {"CutLengthReference": {"CutLength"}}
    assert set(drawing.DETAIL_KEEP) == {"CutEndBreak"}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "dimensions_by_feature=FRONT_VIEW_DIMENSIONS" in source
    assert "dimensions_by_feature=DRAWING_DIMENSIONS" in source
    assert "BREAK_CONTROLS" not in source and "offset_dimension_text" not in source


def test_tip_view_prints_the_band_max_as_a_single_limit() -> None:
    """The tip view's dimension reads the spec band's max at its places, as a
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
    assert source.count("_verify_tip_view(adapter, front, tip)") == 2
    block = source.split('_telemetry.span("drawing.tip_view"', 1)[1]
    block = block.split("_verify_tip_view(adapter, front, tip)", 1)[0]
    assert "cropped_tip_view(adapter)" in block
    assert "_curate_tip_view(adapter, tip)" in block
    assert "assert_imported_precision(adapter, tip_annotations, DETAIL_PRECISION)" in block
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


# --- The tip view is a CROPPED 10:1 MODEL VIEW, not a detail ----------------
# b6552f13b (diag/mha142-bisect, farm worker swmaker000008): no detail child
# of the Front offered CutEndBreak to the import, under 10:1 HLR, 10:1 HLV,
# 5:1 and 2:1, imported before or after the Front's own import; a standalone
# 10:1 *Front model view, moved to the tip and cropped, imported it twice.


class _Point:
    def __init__(self, xyz) -> None:
        self.ArrayData = tuple(xyz)

    def MultiplyTransform(self, transform):
        return _Point(transform(self.ArrayData))


class _DoubleArray(tuple):
    """What the fake double_array hands COM: a bare list must never reach
    CreatePoint or SetViewPosition (a real seat reads it as zeros)."""


def _require_double_array(values, what: str) -> None:
    if not isinstance(values, _DoubleArray):
        raise TypeError(f"{what} got {type(values).__name__}, not a double_array")


class _Utility:
    def CreatePoint(self, xyz):
        _require_double_array(xyz, "CreatePoint")
        return _Point(xyz)


class _SketchPoint:
    def __init__(self, xyz) -> None:
        self.X, self.Y, self.Z = xyz


class _Arc:
    """ISketchArc stand-in: what the seat actually made."""

    def __init__(self, center, radius: float) -> None:
        self.center = center
        self.radius = radius

    def GetCenterPoint2(self):
        return _SketchPoint(self.center)

    def GetRadius(self):
        return self.radius


class _Sketch:
    # A sheet point maps to its view-sketch point x1000 (any affine map works).
    ModelToSketchTransform = staticmethod(lambda xyz: tuple(v * 1000.0 for v in xyz))


class _Note:
    def __init__(self, text: str, owner: str) -> None:
        self.text = text
        self.owner = owner

    def GetText(self):
        return self.text


class _SeatView:
    """IView stand-in whose tip reference sits 0.4 m below its Position."""

    def __init__(self, name: str, seat: "_Seat", *, cropped: bool = True) -> None:
        self.name = name
        self.seat = seat
        self.cropped = cropped
        self.ScaleRatio = (10.0, 1.0)
        self.Position = (0.2, 0.6)

    def SetViewPosition(self, position, move_children):
        _require_double_array(position, "SetViewPosition")
        self.seat.log.append(("move", self.name, tuple(position), move_children))
        self.Position = tuple(position)
        return True

    def GetSketch(self):
        return _Sketch()

    def Crop2(self, jagged, no_outline, intensity):
        self.seat.log.append(("crop2", self.name, jagged, no_outline, intensity))
        return 1  # swCropViewErrors_NoError

    def IsCropped(self):
        return self.cropped

    def GetOutline(self):
        return (0.15, 0.13, 0.23, 0.22)

    def GetNotes(self):
        return tuple(note for note in self.seat.notes if note.owner == self.name)


class _Seat:
    """IModelDoc2 + IDrawingDoc + ISketchManager + adapter, recorded."""

    def __init__(self) -> None:
        self.log: list[tuple] = []
        self.notes: list[_Note] = []
        self.active = ""
        self.currentModel = self
        self.SketchManager = self
        self.swApp = self
        self.AddToDB = False
        # (dx, dy, radius factor), in the fake sketch space (sheet mm), applied
        # when AddToDB is off (or ignored); the 6e65 leaf's Front mark read
        # ~1.5 mm for 3.6, centred on the cut end.
        self.snap: tuple[float, float, float] | None = None
        self.honours_add_to_db = True
        self.add_to_db_seen: list[bool] = []

    def GetMathUtility(self):
        return _Utility()

    def ActivateView(self, name):
        self.log.append(("activate", name))
        self.active = name
        return True

    def ClearSelection2(self, _all):
        return True

    def EditRebuild3(self):
        return True

    def CreateCircle(self, *xyz):
        self.log.append(("circle", self.active, tuple(round(v, 9) for v in xyz)))
        self.add_to_db_seen.append(self.AddToDB)
        cx, cy, cz, px, py, _pz = xyz
        radius = math.dist((cx, cy), (px, py))
        if self.snap is not None and not (self.AddToDB and self.honours_add_to_db):
            # Sketch inference: the points land on nearby geometry instead.
            dx, dy, factor = self.snap
            cx, cy, radius = cx + dx, cy + dy, radius * factor
        return _Arc((cx, cy, cz), radius)

    def CreateDetailViewAt4(self, *args):
        raise AssertionError("the tip must not be a detail view")


def _tip_seat(monkeypatch, *, cropped: bool = True):
    seat = _Seat()
    tip = _SeatView("Drawing View3", seat, cropped=cropped)
    front = _SeatView("Drawing View1", seat)
    placed: list[tuple] = []

    def place(adapter, source, orientation, x, y, *, scale=None):
        placed.append((orientation, x, y, scale))
        return tip

    def point_in_view(adapter, view, xyz, *, label):
        assert xyz == tuple(v / 1000 for v in drawing.TIP_DETAIL.detail_reference_mm)
        return (view.Position[0], view.Position[1] - 0.4)

    def note(adapter, text, x, y, **_kwargs):
        made = _Note(text, seat.active)
        seat.notes.append(made)
        seat.log.append(("note", seat.active, text, round(x, 9), round(y, 9)))
        return made

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: _DoubleArray(values))
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "model_point_in_view", point_in_view)
    monkeypatch.setattr(drawing, "view_name", lambda adapter, view: view.name)
    monkeypatch.setattr(drawing, "add_note", note)
    return seat, tip, front, placed


def test_tip_view_is_a_cropped_10_to_1_model_view_not_a_detail(monkeypatch) -> None:
    seat, tip, _front, placed = _tip_seat(monkeypatch)
    view = drawing.cropped_tip_view(seat)
    assert view is tip
    assert placed == [("*Front", *drawing.DETAIL_CENTER, drawing.DETAIL_SCALE)]
    # Moved so the tip reference lands where the detail sat.
    moves = [entry for entry in seat.log if entry[0] == "move"]
    assert len(moves) == 1
    assert moves[0][2] == pytest.approx(
        (drawing.DETAIL_CENTER[0], drawing.DETAIL_CENTER[1] + 0.4)
    )
    # The crop circle is sketched in the tip view itself, centred on the tip,
    # at the fence's sheet radius, and Crop2 runs straight after it (the new
    # circle must still be the selection).
    kinds = [entry[0] for entry in seat.log]
    assert kinds[-3:] == ["activate", "circle", "crop2"]
    assert seat.log[-3] == ("activate", "Drawing View3")
    _, owner, xyz = seat.log[-2]
    assert owner == "Drawing View3"
    cx, cy, _, px, py, _ = (v / 1000.0 for v in xyz)
    assert (cx, cy) == pytest.approx(drawing.DETAIL_CENTER)
    assert math.dist((cx, cy), (px, py)) == pytest.approx(drawing.DETAIL_RADIUS)
    assert seat.log[-1] == ("crop2", "Drawing View3", False, False, 5)


def test_tip_view_raises_when_the_crop_did_not_take(monkeypatch) -> None:
    seat, _tip, _front, _placed = _tip_seat(monkeypatch, cropped=False)
    with pytest.raises(RuntimeError, match="not cropped"):
        drawing.cropped_tip_view(seat)


def test_tip_view_imports_the_break_by_feature(monkeypatch) -> None:
    """Targeted import: only the deburr cutter's profile is selected; the
    entire-model import is never called."""
    import _drawing_common as dc

    break_annotation = object()
    calls: list[str] = []

    def targeted(adapter, view, features):
        calls.append(f"features:{list(features)}")
        return [("CutEndBreak", break_annotation)]

    def entire(adapter, view):
        raise AssertionError("the tip view must not import the entire model")

    monkeypatch.setattr(dc, "insert_feature_dimensions", targeted)
    monkeypatch.setattr(dc, "insert_marked_dimensions", entire)
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
    curated = drawing._curate_tip_view(object(), object())
    assert curated == [break_annotation]
    assert calls == ["features:['CutEndDeburrProfile']"]


# The 857-b835 render of detail A: the 1 mm (0.1 at 10:1) break between two
# vertical extension lines, arrows outside pointing in, and "0.1 max." centred
# almost on the lines, so it overprints both and the inner arrowheads.
_B835_EXTENSION_X = (0.2000, 0.2010)
_B835_ARROW_WIDTH = 0.003
_B835_TEXT = "0.1 max."
_B835_TEXT_HEIGHT = 0.0035
_B835_TEXT_XY = (0.1995, 0.155)


class _BreakData:
    """IDisplayData of the break: lines, arrowheads, one centred text run."""

    def __init__(self, annotation: "_BreakAnnotation") -> None:
        self._annotation = annotation
        left, right = _B835_EXTENSION_X
        self._lines = [
            (0, 0, 0, 0, left, 0.150, 0.0, left, 0.160, 0.0),
            (0, 0, 0, 0, right, 0.150, 0.0, right, 0.160, 0.0),
            (0, 0, 0, 0, 0.190, 0.152, 0.0, 0.215, 0.152, 0.0),
        ]
        self._arrows = [
            (left, 0.152, 0.0, 1.0, 0.0, 0.0, _B835_ARROW_WIDTH, 0.001, 1, 0, 0, 1),
            (right, 0.152, 0.0, -1.0, 0.0, 0.0, _B835_ARROW_WIDTH, 0.001, 1, 0, 0, 1),
        ]

    def GetLineCount(self):
        return len(self._lines)

    def GetLineAtIndex2(self, index):
        return self._lines[index]

    def GetArrowHeadCount(self):
        return len(self._arrows)

    def GetArrowHeadAtIndex2(self, index):
        return self._arrows[index]

    def GetTextCount(self):
        return 1

    def GetTextAtIndex(self, index):
        return _B835_TEXT

    def GetTextPositionAtIndex(self, index):
        x, y = self._annotation.text_xy
        return (x, y, 0.0)

    def GetTextHeightAtIndex(self, index):
        return _B835_TEXT_HEIGHT

    def GetTextRefPositionAtIndex(self, index):
        return 2  # swTextPosition_e.swCENTER

    def GetTextAngleAtIndex(self, index):
        return 0.0


class _BreakDisplay:
    def __init__(self, annotation: "_BreakAnnotation") -> None:
        self._annotation = annotation
        self.ArrowSide = 2  # swDimArrowsSmart
        self.CenterText = True

    def GetDisplayData(self):
        return _BreakData(self._annotation)


class _BreakAnnotation:
    def __init__(self, *, text_offset=(0.0, 0.0)) -> None:
        self.position = _B835_TEXT_XY
        self.text_offset = text_offset
        self.display = _BreakDisplay(self)
        self.moves: list[tuple[float, float]] = []

    @property
    def text_xy(self):
        return (
            self.position[0] + self.text_offset[0],
            self.position[1] + self.text_offset[1],
        )

    def GetSpecificAnnotation(self):
        return self.display

    def GetPosition(self):
        return (*self.position, 0.0)

    def SetPosition2(self, x, y, z):
        self.position = (x, y)
        self.moves.append((x, y))
        return True


class _RebuildSeat:
    def __init__(self) -> None:
        self.rebuilds = 0
        self.currentModel = self

    def EditRebuild3(self):
        self.rebuilds += 1
        return True


def _break_seat(monkeypatch, **kwargs):
    annotation = _BreakAnnotation(**kwargs)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(
        drawing,
        "dimension_name",
        lambda adapter, item: "CutEndBreak" if item is annotation else "",
    )
    return _RebuildSeat(), annotation


def test_b835_break_text_overprints_both_extension_lines(monkeypatch) -> None:
    """Planted from the 857-b835 render: the read-back sees the text box
    across both extension lines, and the check refuses it."""
    _seat, annotation = _break_seat(monkeypatch)
    ink = drawing.read_break_ink(annotation)
    assert ink.extension_x == _B835_EXTENSION_X
    assert ink.text == _B835_TEXT
    assert ink.text_box.xmin < _B835_EXTENSION_X[0]
    assert ink.text_box.xmax > _B835_EXTENSION_X[1]
    with pytest.raises(RuntimeError, match="extension line"):
        drawing.assert_break_text_outside(ink)


def test_break_text_moves_left_of_both_extension_lines(monkeypatch) -> None:
    """Arrows outside pointing in, text not centred, and the text's right
    edge a gap clear of the left arrow's tail -- so left of both lines."""
    seat, annotation = _break_seat(monkeypatch)
    ink = drawing.place_break_text_outside(seat, [object(), annotation])
    assert annotation.display.ArrowSide == drawing.ARROWS_OUTSIDE == 1
    assert annotation.display.CenterText is False
    assert len(annotation.moves) == 1
    # The text moves along the dimension line only.
    assert annotation.moves[0][1] == pytest.approx(_B835_TEXT_XY[1])
    arrow_tail = _B835_EXTENSION_X[0] - _B835_ARROW_WIDTH
    assert ink.arrow_left_x == pytest.approx(arrow_tail)
    assert ink.text_box.xmax == pytest.approx(arrow_tail - drawing.BREAK_TEXT_GAP_M)
    assert ink.text_box.xmax < _B835_EXTENSION_X[0]
    # The minimum form: the centred anchor sits left of the left extension
    # line by at least half the text's width.
    half = ink.text_box.width / 2.0
    assert annotation.text_xy[0] <= _B835_EXTENSION_X[0] - half
    drawing.assert_break_text_outside(ink)
    assert seat.rebuilds >= 2


def test_break_ink_refuses_text_off_the_sheet_frame(monkeypatch) -> None:
    """GetTextPositionAtIndex is an offset from the display data's origin; if
    that is not the sheet, no clearance can be read from it."""
    _seat, annotation = _break_seat(monkeypatch, text_offset=(0.2, 0.0))
    with pytest.raises(RuntimeError, match="sheet"):
        drawing.read_break_ink(annotation)


def test_break_ink_needs_exactly_two_extension_lines(monkeypatch) -> None:
    _seat, annotation = _break_seat(monkeypatch)
    data = _BreakData(annotation)
    data._lines = data._lines[1:]
    annotation.display.GetDisplayData = lambda: data
    with pytest.raises(RuntimeError, match="two extension lines"):
        drawing.read_break_ink(annotation)


def test_break_ink_refuses_an_arrowhead_wider_than_one(monkeypatch) -> None:
    """GetArrowHeadAtIndex2 is unread on the seat: a width in another unit
    must fail loud, not park the text far left."""
    _seat, annotation = _break_seat(monkeypatch)
    data = _BreakData(annotation)
    tip = list(data._arrows[0])
    tip[6] = 3.0  # millimetres, not metres
    data._arrows[0] = tuple(tip)
    annotation.display.GetDisplayData = lambda: data
    with pytest.raises(RuntimeError, match="arrowhead"):
        drawing.read_break_ink(annotation)


def test_break_text_move_is_bounded(monkeypatch) -> None:
    seat, annotation = _break_seat(monkeypatch)
    annotation.position = (_B835_TEXT_XY[0] + 0.05, _B835_TEXT_XY[1])
    monkeypatch.setattr(drawing, "_TEXT_FRAME_TOLERANCE_M", 1.0)
    with pytest.raises(RuntimeError, match="would move"):
        drawing.place_break_text_outside(seat, [annotation])
    assert annotation.moves == []


def test_break_text_is_placed_and_checked_on_the_seat() -> None:
    """The build places the text right after the tip view's import, and both
    tip-view read-backs re-prove it."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    block = source.split('_telemetry.span("drawing.tip_view"', 1)[1]
    block = block.split("_verify_tip_view(adapter, front, tip)", 1)[0]
    curate = block.index("_curate_tip_view(adapter, tip)")
    place = block.index("place_break_text_outside(adapter, tip_annotations)")
    assert curate < place
    verify = source.split("def _verify_tip_view", 1)[1].split("\ndef ", 1)[0]
    assert "assert_break_text_outside(" in verify
    assert "read_break_ink(" in verify


def test_tip_view_label_is_owned_by_the_tip_view(monkeypatch) -> None:
    seat, tip, _front, _placed = _tip_seat(monkeypatch)
    assert drawing.TIP_VIEW_LABEL == "DETAIL A  SCALE 10:1"
    drawing.label_tip_view(seat, tip)
    assert [(n.owner, n.text) for n in seat.notes] == [
        ("Drawing View3", "DETAIL A  SCALE 10:1")
    ]
    x, y = drawing.TIP_DETAIL.detail_label_xy
    assert (
        "note", "Drawing View3", "DETAIL A  SCALE 10:1", round(x, 9), round(y, 9)
    ) in seat.log


def test_tip_view_label_tolerates_another_note_on_the_view(monkeypatch) -> None:
    """Whether the template gives a model view a native label of its own is
    unread on the seat, so only OUR label is counted, never the total."""
    seat, tip, _front, _placed = _tip_seat(monkeypatch)
    seat.notes.append(_Note("DRAWING VIEW3", "Drawing View3"))
    drawing.label_tip_view(seat, tip)
    texts = [n.text for n in seat.notes if n.owner == "Drawing View3"]
    assert texts.count("DETAIL A  SCALE 10:1") == 1


def test_tip_view_reposition_tolerance_matches_the_notch_detail() -> None:
    """The move is checked to 0.1 mm on the sheet (draw_cylinder_gear's notch
    detail tolerance), not a micron the diag never proved."""
    assert drawing.TIP_VIEW_POSITION_TOLERANCE_M == 1e-4


def test_tip_view_label_raises_when_it_lands_elsewhere(monkeypatch) -> None:
    seat, tip, _front, _placed = _tip_seat(monkeypatch)
    monkeypatch.setattr(seat, "ActivateView", lambda name: True)  # stays inactive
    with pytest.raises(RuntimeError, match="label"):
        drawing.label_tip_view(seat, tip)


def test_front_marks_the_tip_with_a_circle_and_letter(monkeypatch) -> None:
    seat, _tip, front, _placed = _tip_seat(monkeypatch)
    drawing.mark_tip_on_front(seat, front)
    circles = [entry for entry in seat.log if entry[0] == "circle"]
    assert len(circles) == 1 and circles[0][1] == "Drawing View1"
    cx, cy, _, px, py, _ = (v / 1000.0 for v in circles[0][2])
    tip = (front.Position[0], front.Position[1] - 0.4)
    assert (cx, cy) == pytest.approx(tip)
    # The fence's 1:1 radius: the circle bounds exactly what the tip view shows.
    assert math.dist((cx, cy), (px, py)) == pytest.approx(drawing.DETAIL_FENCE_MM / 1000.0)
    assert [(n.owner, n.text) for n in seat.notes] == [("Drawing View1", "A")]
    note = next(entry for entry in seat.log if entry[0] == "note")
    offset = drawing.TIP_DETAIL.parent_letter_offset
    assert note[3:] == (round(tip[0] + offset[0], 9), round(tip[1] + offset[1], 9))


def test_tip_label_and_letter_agree() -> None:
    assert drawing.TIP_LETTER == "A"
    assert drawing.TIP_VIEW_LABEL.startswith(f"DETAIL {drawing.TIP_LETTER} ")
    num, den = drawing.DETAIL_SCALE
    assert drawing.TIP_VIEW_LABEL.endswith(f"SCALE {num:g}:{den:g}")


def test_bisect_scaffolding_is_gone() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for token in (
        "read_detail_visible_entities",
        "GetVisibleEntities2",
        "_detail_facts",
        "mha142-bisect view=",
        "run_bisect",
        "end_detail(",
        "CreateDetailViewAt4",
        "position_detail_label",
        "position_parent_detail_letter",
    ):
        assert token not in source, token


def test_measured_behaviour_is_recorded_on_the_tip_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source.split("def cropped_tip_view", 1)[1].split("\ndef ", 1)[0]
    body = " ".join(body.split())
    for evidence in ("b6552f13b", "10:1 HLR", "10:1 HLV", "5:1", "2:1", "before or after"):
        assert evidence in body, evidence


def test_front_is_active_before_the_notes() -> None:
    """pms857-diag-9eca: property-linked notes land in the ACTIVE view.  The
    tip view is labelled while active, the Front is marked, then the Front
    is re-activated before the first sheet note."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source.split("async def build", 1)[1]
    curate = body.index("_curate_tip_view(adapter, tip)")
    label = body.index("label_tip_view(adapter, tip)")
    mark = body.index("mark_tip_on_front(adapter, front)")
    activate = body.index("activate_front_for_notes(adapter, front)")
    first_note = body.index("add_property_linked_note(")
    assert curate < label < mark < activate < first_note



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


def test_front_tip_mark_is_sketched_with_inference_off(monkeypatch) -> None:
    """r857-6e65 (docstring-only change) drew the Front's tip mark at ~1.5 mm
    radius on the cut end; eae5 drew it at the 3.6 mm fence, 1 mm above.
    Nothing read it back.  The circle goes straight to the sketch database
    (AddToDB), the prior setting comes back, and the made circle is read."""
    seat, _tip, front, _placed = _tip_seat(monkeypatch)
    seat.snap = (0.0, -1.0, 0.43)
    seat.AddToDB = False
    drawing.mark_tip_on_front(seat, front)
    assert seat.add_to_db_seen == [True]
    assert seat.AddToDB is False


def test_a_circle_the_seat_moved_raises(monkeypatch) -> None:
    seat, _tip, front, _placed = _tip_seat(monkeypatch)
    seat.snap = (0.0, -1.0, 0.43)
    seat.honours_add_to_db = False
    with pytest.raises(RuntimeError, match="Front tip mark circle"):
        drawing.mark_tip_on_front(seat, front)
    assert seat.AddToDB is False
    seat, _tip, _front, _placed = _tip_seat(monkeypatch)
    seat.snap = (0.5, 0.0, 1.0)
    seat.honours_add_to_db = False
    with pytest.raises(RuntimeError, match="tip view crop circle"):
        drawing.cropped_tip_view(seat)
