"""Offline contracts for the MHA-DT-VN-61 cone pivot post mount screw."""

from __future__ import annotations

import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_dt_vn_post_mount_screw as part
import dt_cone_pivot_post_spec as post
import dt_cone_swing_platform_spec as platform
import draw_dt_vn_post_mount_screw as drawing
from _fit_deviations import deviations
import dt_vn_post_mount_screw_spec as spec
from _drawing_contract import drawing_specification_violations
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_40923906 as recipe
from _msc_40923906 import FILLISTER_SIZE

IN = 25.4
# Screw head seated on the counterbore floor: its under-head face is this far
# below the post top, and the shank spans the rest of the post and the plate.
GRIP = post.BLOCK_HEIGHT - post.ATTACHMENT_CBORE_DEPTH


def test_recipe_is_the_u37c_screw() -> None:
    """The registered fillister's head envelope, pitch and fitted cut length."""
    assert spec.THREAD == platform.POST_MOUNT_SPEC.size == "1/4-20"
    assert part.SHANK_DIA == THREAD_MAJOR_MM[spec.THREAD]
    assert part.THREAD_PITCH == IN / 20.0
    assert part.SHANK_LEN == spec.CUT_LENGTH_MM
    assert part.HEAD_DIA == 0.414 * IN
    assert part.HEAD_H == 0.237 * IN


def test_head_fits_the_existing_post_counterbore() -> None:
    assert part.HEAD_DIA < post.ATTACHMENT_CBORE_DIA
    assert part.HEAD_H <= post.ATTACHMENT_CBORE_DEPTH + 1e-9  # never above the top
    assert part.SHANK_DIA < post.ATTACHMENT_THRU_DIA


def test_nominal_end_sits_short_of_the_platform_underside() -> None:
    """The spec-derived cut is inside the functional fit-to-hole acceptance."""
    short = GRIP + platform.PLATE_THICKNESS - part.SHANK_LEN
    assert 0.0 <= short <= spec.POST_SCREW_CUT_TO_FIT_SHORT
    engagement = part.SHANK_LEN - GRIP
    assert engagement / part.SHANK_DIA >= 0.90


def test_supplied_stock_reaches_longest_raised_post_corner() -> None:
    assert spec.LONGEST_FITTED_LENGTH_MM == spec.FLOOR_HIGH_MM + spec.PLATE_THICK_MM
    assert spec.STOCK_REACH_MARGIN_MM == (
        spec.STOCK_LENGTH_MM - spec.FACTORY_TIP_CHAMFER_MM - spec.LONGEST_FITTED_LENGTH_MM
    )
    assert spec.STOCK_REACH_MARGIN_MM > 0.0
    assert spec.CUT_LENGTH_MM < spec.LONGEST_FITTED_LENGTH_MM


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
    thin = platform.PLATE_THICKNESS - spec.PLATE_STOCK_BAND_MM
    assert spec.FIXED_LENGTH_FLUSH_MAX_MM == pytest.approx(low + thin)
    need = (
        high
        + 0.90 * part.SHANK_DIA
        + spec.POST_MOUNT_TAP_EDGE_BREAK
        + spec.CUT_END_BREAK_MAX_MM
    )
    assert spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM == pytest.approx(need)
    assert spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM > spec.FIXED_LENGTH_FLUSH_MAX_MM
    assert spec.FIXED_CUT_LENGTH_EXISTS is False


def test_cut_length_prints_as_a_reference_without_a_band() -> None:
    """No fixed length exists, so the model's spec-derived length prints in
    parentheses without a band; the callout carries fit-to-hole acceptance."""
    assert spec.CUT_LENGTH_MM == part.SHANK_LEN
    places = spec.DRAWING_PRECISION_BY_NAME[spec.CUT_LENGTH_DIMENSION]
    assert spec.CUT_LENGTH_MM == round(
        GRIP + platform.PLATE_THICKNESS - spec.POST_SCREW_CUT_TO_FIT_SHORT / 2.0,
        places,
    )
    callout = drawing.DIMENSION_CALLOUTS["CutLength"]
    # The callout still promises no fixed length: never the modelled cut
    # length, never a band on it.
    assert f"{spec.CUT_LENGTH_MM:.1f}" not in callout
    assert "±" not in callout and "+" not in callout


def test_cut_to_fit_acceptance_prints_on_the_delegating_callout() -> None:
    """Codex P1 on #857: the callout delegated the cut to assembly, but no
    MHA-DT-00 step stated the acceptance the 0.90D worst case depends on.  The
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
    assert f"FLUSH TO {-lower:.{places}f} SHORT OF MHA-DT-20 UNDERSIDE" in flat
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
    """Codex P2 on #857 (PRRT_kwDOPHDy386mOxdw): MHA-DT-VN-61 stated its 0.90D
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
    config = _config.parts("dt-vn-post-mount-screw")
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
    assert not _BANNED_ON_SHEET.search("OF MHA-DT-20 UNDERSIDE, NEVER PROUD")


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
    """The per-hole allowance MHA-DT-00 and the platform stack consume."""
    assert spec.POST_SCREW_CUT_TO_FIT_SHORT == 0.3




def test_cut_end_break_is_a_model_owned_deburr_of_at_most_0_1() -> None:
    """Main's engagement ruling: the cut end's break is 0.1 max (a deburr,
    not the title block's 0.25).  The model's CutEndBreak carries the band's
    deviations natively as a MAX-limit dimension; the note stays digit-free."""
    lower, upper = deviations(spec.CUT_END_BREAK_BAND)
    assert spec.CUT_END_BREAK_MM + upper <= 0.1 + 1e-12
    assert spec.CUT_END_BREAK_MM + lower >= 0.0
    assert spec.CUT_END_BREAK_MAX_MM == spec.CUT_END_BREAK_MM + upper
    assert spec.POST_MOUNT_TAP_EDGE_BREAK <= 0.1


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


def test_catalog_row_is_the_supplied_stock_and_only_the_part_is_cut() -> None:
    """The registered catalogue row remains supplied 4 in stock; only the
    MHA-DT-VN-61 builder trims it. No shared stock row is overwritten."""
    row = _config.parts(part.PART_NAME)
    assert row["supplier_skus"] == [spec.SKU]
    assert spec.SKU == recipe.PART_NO
    assert FILLISTER_SIZE[1] == pytest.approx(4.0 * IN)
    assert spec.STOCK_LENGTH_MM == FILLISTER_SIZE[1]
    assert part.SHANK_LEN == spec.CUT_LENGTH_MM < spec.STOCK_LENGTH_MM
    # A half-inch-shorter predecessor cannot reach the longest fitted seat.
    assert spec.STOCK_LENGTH_MM - 0.5 * IN < spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM


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
    # The trimmed tip cannot reach into what the stock carries: the cut
    # clears the factory tip, and the volume gate outruns the sweep's slack.
    assert spec.STOCK_LENGTH_MM - spec.FACTORY_TIP_CHAMFER_MM > spec.CUT_LENGTH_MM
    assert part.TRIM_VOLUME_TOL_MM3 < 0.01 * spec.TRIM_REMOVED_MM3






def _printed_cut_short_allowance() -> float:
    """The acceptance the sheet prints: "END FLUSH TO <x> SHORT"."""
    match = re.search(r"END FLUSH TO (\d+(?:\.\d+)?) SHORT", spec.CUT_TO_FIT_CALLOUT)
    assert match, spec.CUT_TO_FIT_CALLOUT
    return float(match.group(1))


def _short_of_underside(length_mm: float) -> float:
    """How far a screw of this length ends short of the MHA-DT-20 underside on
    the nominal post and plate (negative: proud)."""
    return GRIP + platform.PLATE_THICKNESS - length_mm


def test_the_modelled_length_is_a_cut_the_sheet_accepts() -> None:
    """Codex P2 on #857 (PRRT_kwDOPHDy386mRhqY): the source CAD must satisfy
    its own sheet. The modelled length is the current post/plate flush
    length less the allowance's midpoint, at its printed places."""
    allowance = _printed_cut_short_allowance()
    assert allowance == platform.POST_SCREW_CUT_TO_FIT_SHORT

    def accepted(length_mm: float) -> bool:
        return 0.0 <= _short_of_underside(length_mm) <= allowance

    assert not accepted(spec.FLUSH_LENGTH_MM - allowance - 0.01)
    assert accepted(spec.CUT_LENGTH_MM)
    places = spec.DRAWING_PRECISION_BY_NAME[spec.CUT_LENGTH_DIMENSION]
    assert spec.CUT_LENGTH_MM == round(
        _short_of_underside(0.0) - allowance / 2.0, places
    )
    assert part.SHANK_LEN == spec.CUT_LENGTH_MM


def test_engagement_exception_is_held_by_the_model() -> None:
    """The rule-18 shortfall pending #1019 (0.90D) is a model assert on the chain;
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
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == recipe.build_40923906.__name__
    assert part.SPEC.skus == (spec.SKU,)
    assert part.SPEC.supplier == "MSC Industrial Supply"
    assert part.MATERIAL == "Plain Carbon Steel"
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-DT-VN-61"
    assert int(row["quantity"]) == 2
    assert spec.SKU in row["material_specification"]
    assert "SAE J82" in row["material_specification"]
    assert spec.SKU in drawing.DRAWING_SUMMARY[3]


def test_drawing_is_the_modified_stock_sheet() -> None:
    """A cut purchased part takes a manufacturing sheet with its cut length,
    not the dimensionless purchased reference sheet (boss hook's pattern)."""
    registry = DRAWINGS_BY_NAME["dt_vn_post_mount_screw"]
    assert drawing.SPEC is registry
    assert registry.artifact_stem == part.PART_NAME
    assert registry.script == Path(drawing.__file__).resolve()


def test_sheet_passes_the_drawing_owned_precision_rule() -> None:
    violations = drawing_specification_violations(
        Path(drawing.__file__).read_text(encoding="utf-8"),
        filename=Path(drawing.__file__).name,
    )
    assert violations == ()




def test_break_is_smaller_than_the_allowed_trim_volume_residual() -> None:
    """The tiny deburr is below the trim gate's current volume allowance.
    Its presence must be proved by the end-face rim, not a smaller mass
    reading: the original #857 leaf's broken screw read slightly larger."""
    assert 0.0 < spec.CUT_END_DEBURR_REMOVED_MM3 < part.TRIM_VOLUME_TOL_MM3


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


# --- Main's MHA-DT-VN-61 eye pass on #857: the cut-end break callout -----------
# A 0.1 dimension at 1:1 printed "0.0" stacked over "0.1 -0.1": illegible,
# and +0/-0.1 read as permitting no break.  The note says DEBURR, the Front
# view drops the break, and a 10:1 tip detail prints the single limit.






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
    import _drawing_dimension_import

    break_annotation = object()
    calls: list[str] = []

    def targeted(adapter, view, features):
        calls.append(f"features:{list(features)}")
        return [("CutEndBreak", break_annotation)]

    def entire(adapter, view):
        raise AssertionError("the tip view must not import the entire model")

    monkeypatch.setattr(_drawing_dimension_import, "insert_feature_dimensions", targeted)
    monkeypatch.setattr(_drawing_dimension_import, "insert_marked_dimensions", entire)
    monkeypatch.setattr(
        _drawing_dimension_import,
        "dimension_name",
        lambda adapter, item: "CutEndBreak" if item is break_annotation else "",
    )
    monkeypatch.setattr(
        _drawing_dimension_import,
        "curate_dimensions",
        lambda adapter, items, delete=(), reposition=None: list(items),
    )
    # The stub places nothing, so there is no position to read back.
    monkeypatch.setattr(_drawing_dimension_import, "_reposition_rerun_reason", lambda *a, **k: "none")
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


# The supplier diagram lives in a rotated, translated MODEL sketch.  The
# drawing view's own sketch below remains a separate sheet-to-crop frame.
class _SupplierSourceTransform:
    def __init__(self, seat) -> None:
        self.seat = seat

    def __call__(self, xyz):
        x, y, z = xyz
        return (y + 0.043, 0.031 - x, z - 0.057)

    def Inverse(self):
        self.seat.log.append(("inverse-source-frame",))

        def sketch_to_model(xyz):
            self.seat.log.append(("sketch-to-model", tuple(xyz)))
            x, y, z = xyz
            return (0.031 - y, -0.043 + x, 0.057 + z)

        return sketch_to_model


class _SupplierView:
    INITIAL_ANGLE = 0.37
    TRANSFORMS = {"ReferencedConfiguration", "UseSheetScale", "ScaleRatio", "Angle", "Position"}

    def __init__(self, seat, center, scale, source_angle) -> None:
        self.name = "MSC source"
        self.ReferencedConfiguration = "Default"
        self.UseSheetScale = 1
        self.ScaleRatio = (0.5, 1.0)
        self.Angle = self.INITIAL_ANGLE
        self.Position = (center[0] + 0.007, center[1] - 0.009)
        self.expected_scale = scale
        self.source_angle = source_angle
        self.sheet_signs = (1.0, 1.0)
        self.projection_factor = 1.0
        self.cropped = False
        self.source_sketch = SimpleNamespace(
            ModelToSketchTransform=_SupplierSourceTransform(seat),
        )
        feature = SimpleNamespace(GetSpecificFeature2=self._source_sketch)
        self.ReferencedDocument = SimpleNamespace(
            FeatureByName=lambda name: self._source_feature(name, feature),
        )
        self.seat = seat

    def __setattr__(self, name, value) -> None:
        if name in self.TRANSFORMS and "seat" in self.__dict__:
            assert not self.seat.annotated, f"{name} changed after dimension import"
            if name == "ScaleRatio":
                _require_double_array(value, "ScaleRatio")
            self.seat.log.append((name, value))
            self.seat.dirty = True
            self.seat.display_dirty = True
        object.__setattr__(self, name, value)

    def _source_feature(self, name, feature):
        assert name == drawing.SUPPLIER_STOCK_FEATURE
        self.seat.log.append(("source-feature", name))
        return feature

    def _source_sketch(self):
        self.seat.log.append(("source-sketch",))
        return self.source_sketch

    def sheet_point(self, xyz):
        x, y, _z = xyz
        angle = self.Angle - self.INITIAL_ANGLE + self.source_angle - math.pi / 2.0
        c, s = math.cos(angle), math.sin(angle)
        ratio = self.ScaleRatio[0] / self.ScaleRatio[1] * self.projection_factor
        return (
            self.Position[0] + ratio * self.sheet_signs[0] * (c * x - s * y),
            self.Position[1] + ratio * self.sheet_signs[1] * (s * x + c * y),
            0.0,
        )

    @property
    def ModelToViewTransform(self):
        assert self.seat.revealed
        assert self.ReferencedConfiguration == drawing.SUPPLIER_STOCK_CONFIGURATION
        assert self.UseSheetScale == 0
        assert tuple(self.ScaleRatio) == self.expected_scale
        assert not self.seat.dirty, "projection used an unrebuilt view transform"
        assert not self.seat.display_dirty, "projection used unrefreshed view display geometry"
        self.seat.log.append(("project-frame", self.Angle, self.Position))
        return self.sheet_point

    def SetViewPosition(self, position, move_children):
        _require_double_array(position, "SetViewPosition")
        self.seat.log.append(("move", tuple(position), move_children))
        self.Position = tuple(position)
        return True

    def UpdateViewDisplayGeometry(self):
        assert not self.seat.dirty
        self.seat.display_dirty = False
        self.seat.log.append(("update",))

    def GetOutline(self):
        return (0.123, -0.087, 0.155, 0.128)

    def GetSketch(self):
        self.seat.log.append(("crop-sketch",))
        return _Sketch()

    def Crop2(self, jagged, no_outline, intensity):
        self.seat.log.append(("crop2", jagged, no_outline, intensity))
        self.cropped = True
        return 1

    def IsCropped(self):
        return self.cropped


class _SupplierSeat(_Seat):
    def __init__(self) -> None:
        super().__init__()
        self.revealed = False
        self.annotated = False
        self.dirty = False
        self.display_dirty = False

    def EditRebuild3(self):
        self.log.append(("rebuild",))
        # A rebuild settles edits, but repaint-dependent geometry can still lag.
        self.dirty = False
        return True


_SUPPLIER_FRAME_CASES = (
    (False, drawing.STOCK_CENTER, drawing.STOCK_SCALE, drawing.STOCK_KEEP, 0.0477901),
    (True, drawing.STOCK_HEAD_CENTER, drawing.STOCK_HEAD_SCALE, drawing.STOCK_HEAD_KEEP, -0.0030099),
)


def _supplier_seat(monkeypatch, center, scale, *, source_angle=math.pi / 2.0):
    import _drawing_projection as projection

    seat = _SupplierSeat()
    stock = _SupplierView(seat, center, scale, source_angle)

    def place(adapter, source, orientation, x, y):
        assert adapter is seat and source == str(drawing.SOURCE)
        assert orientation == "*Front" and (x, y) == center
        seat.log.append(("place",))
        return stock

    def reveal(adapter, view, features, *, view_label):
        assert adapter is seat and view is stock
        assert stock.ReferencedConfiguration == drawing.SUPPLIER_STOCK_CONFIGURATION
        assert features == (drawing.SUPPLIER_STOCK_FEATURE,)
        seat.revealed = True
        seat.log.append(("reveal",))
        return features

    def invoke(obj, _interface, member, *args):
        value = getattr(obj, member)
        return value if member in ("ModelToViewTransform", "ArrayData") else value(*args)

    strict_frame = drawing._assert_supplier_profile_frame

    def verify(*args, **kwargs):
        strict_frame(*args, **kwargs)
        seat.log.append(("verified-frame",))

    def import_dimensions(adapter, view, *, keep, view_label, dimensions_by_feature):
        assert adapter is seat and view is stock
        assert dimensions_by_feature == drawing.SUPPLIER_STOCK_DIMENSIONS
        assert any(entry[0] == "verified-frame" for entry in seat.log)
        seat.log.append(("import", tuple(keep)))
        seat.annotated = True
        return [
            SimpleNamespace(
                name=name, GetSpecificAnnotation=lambda name=name: SimpleNamespace(name=name),
            )
            for name in keep
        ]

    def reposition(adapter, annotations, *, reposition):
        assert adapter is seat
        assert {annotation.name for annotation in annotations} == set(reposition)
        seat.log.append(("reposition", tuple(reposition.items())))
        return annotations

    def reference(adapter, display, **contract):
        assert adapter is seat and display.name == contract["label"]
        seat.log.append(("reference", display.name))

    # Existing frame-contract tests count projection calls independently of
    # observational diagnostics; the diagnostic readbacks have their own test.
    monkeypatch.setattr(drawing, "_log_supplier_view_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: _DoubleArray(values))
    monkeypatch.setattr(projection, "double_array", lambda values: _DoubleArray(values))
    monkeypatch.setattr(projection, "_com_invoke", invoke)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing.hidden_sketches, "_show_hidden_owners", reveal)
    monkeypatch.setattr(drawing.hidden_sketches, "curate_view_dimensions", import_dimensions)
    monkeypatch.setattr(drawing, "curate_dimensions", reposition)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "supplier_reference_dimension", reference)
    monkeypatch.setattr(drawing, "_assert_supplier_profile_frame", verify)
    return seat, stock


@pytest.mark.parametrize("crop_head,center,scale,keep,semantic_x", _SUPPLIER_FRAME_CASES)
def test_supplier_profile_points_use_the_source_sketch_inverse(
    monkeypatch, crop_head, center, scale, keep, semantic_x,
) -> None:
    seat, stock = _supplier_seat(monkeypatch, center, scale)
    points = drawing._supplier_profile_model_points(
        seat, stock, crop_head=crop_head, label="source mapping",
    )
    expected = (
        (0.031, -0.043, 0.057),
        (0.031, -0.042, 0.057),
        (0.030, -0.043, 0.057),
        (0.031, -0.043 + semantic_x, 0.057),
    )
    assert len(points) == 4
    for actual, target in zip(points, expected, strict=True):
        assert actual == pytest.approx(target, rel=0.0, abs=1e-12)
    assert [entry[1] for entry in seat.log if entry[0] == "sketch-to-model"] == [
        (0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.001, 0.0),
        pytest.approx((semantic_x, 0.0, 0.0), rel=0.0, abs=1e-12),
    ]
    kinds = [entry[0] for entry in seat.log]
    assert kinds[:3] == ["source-feature", "source-sketch", "inverse-source-frame"]
    assert "crop-sketch" not in kinds


@pytest.mark.parametrize("crop_head,center,scale,keep,semantic_x", _SUPPLIER_FRAME_CASES)
@pytest.mark.parametrize("source_angle", [math.pi / 2.0, 0.61], ids=["vertical", "oblique"])
def test_supplier_stock_view_settles_the_measured_frame_before_annotations(
    monkeypatch, crop_head, center, scale, keep, semantic_x, source_angle,
) -> None:
    seat, stock = _supplier_seat(monkeypatch, center, scale, source_angle=source_angle)
    result = drawing._supplier_stock_view(
        seat, center=center, scale=scale, keep=keep, label="MSC source", crop_head=crop_head,
    )
    assert result is stock
    assert stock.Angle == pytest.approx(stock.INITIAL_ANGLE - source_angle, abs=1e-12)
    assert stock.sheet_point((0.031, -0.043 + semantic_x, 0.057))[:2] == pytest.approx(
        center, rel=0.0, abs=1e-12,
    )
    assert tuple(stock.ScaleRatio) == scale and stock.UseSheetScale == 0
    assert stock.IsCropped() is crop_head
    kinds = [entry[0] for entry in seat.log]
    first_measure = kinds.index("source-feature")
    assert kinds[:first_measure] == [
        "place", "ReferencedConfiguration", "reveal", "rebuild",
        "UseSheetScale", "ScaleRatio", "rebuild", "update",
    ]
    angle = kinds.index("Angle")
    move = kinds.index("move")
    verified = kinds.index("verified-frame")
    imported = kinds.index("import")
    assert first_measure < kinds.index("project-frame") < angle < move < verified < imported
    assert "rebuild" in kinds[angle + 1:move]
    assert "update" in kinds[angle + 1:move]
    assert "rebuild" in kinds[move + 1:verified]
    assert "update" in kinds[move + 1:verified]
    assert kinds.count("source-feature") == kinds.count("inverse-source-frame") == 2
    assert not (stock.TRANSFORMS | {"move"}).intersection(kinds[imported + 1:])
    assert kinds[imported + 1:] == ["reposition"] + ["reference"] * len(keep)
    if crop_head:
        assert verified < kinds.index("crop-sketch") < kinds.index("circle") < kinds.index("crop2") < imported
        circle = next(entry for entry in seat.log if entry[0] == "circle")
        cx, cy, _cz, px, py, _pz = (value / 1000.0 for value in circle[2])
        assert (cx, cy) == pytest.approx(center, rel=0.0, abs=1e-12)
        assert math.dist((cx, cy), (px, py)) == pytest.approx(
            drawing.STOCK_HEAD_RADIUS_MM * scale[0] / scale[1] / 1000.0,
        )
        assert next(entry for entry in seat.log if entry[0] == "crop2") == (
            "crop2", False, True, 5,
        )
    else:
        assert not {"crop-sketch", "circle", "crop2"}.intersection(kinds)


@pytest.mark.parametrize("crop_head,center,scale,keep,semantic_x", _SUPPLIER_FRAME_CASES)
@pytest.mark.parametrize(
    "fault", ["none", "rotated", "axial-mirror", "radial-mirror", "scale", "center-x", "center-y"],
)
def test_supplier_final_frame_reader_reprojects_and_rejects_native_drift(
    monkeypatch, crop_head, center, scale, keep, semantic_x, fault,
) -> None:
    seat, stock = _supplier_seat(monkeypatch, center, scale)
    drawing._supplier_stock_view(
        seat, center=center, scale=scale, keep=keep, label="MSC source", crop_head=crop_head,
    )
    # Simulate a settled native transform changing behind the recorded view
    # properties. Keep the semantic center exact for the axis-only faults.
    if fault == "rotated":
        object.__setattr__(stock, "Angle", stock.Angle + 0.013)
    elif fault == "axial-mirror":
        stock.sheet_signs = (-1.0, 1.0)
    elif fault == "radial-mirror":
        stock.sheet_signs = (1.0, -1.0)
    elif fault == "scale":
        stock.projection_factor = 1.02
    if fault in {"rotated", "axial-mirror", "radial-mirror", "scale"}:
        actual = stock.sheet_point((0.031, -0.043 + semantic_x, 0.057))
        object.__setattr__(stock, "Position", tuple(
            stock.Position[index] + center[index] - actual[index] for index in range(2)
        ))
    elif fault in {"center-x", "center-y"}:
        index = 0 if fault == "center-x" else 1
        shifted = list(stock.Position)
        shifted[index] += 2e-8  # Strict reader tolerance is 1e-8 metres.
        object.__setattr__(stock, "Position", tuple(shifted))
    assert tuple(stock.ScaleRatio) == scale and stock.UseSheetScale == 0
    seat.log.clear()
    seat.display_dirty = True
    if fault == "none":
        drawing._assert_supplier_profile_frame(
            seat, stock, center, scale, crop_head=crop_head, label="settled source",
        )
    else:
        reason = "center moved" if fault.startswith("center-") else "axes lost"
        with pytest.raises(RuntimeError, match=reason):
            drawing._assert_supplier_profile_frame(
                seat, stock, center, scale, crop_head=crop_head, label="settled source",
            )
    kinds = [entry[0] for entry in seat.log]
    assert kinds.count("source-feature") == kinds.count("inverse-source-frame") == 1
    assert kinds.count("sketch-to-model") == 4
    assert kinds.count("project-frame") == 1
    assert kinds.count("update") == 1
    assert kinds.index("update") < kinds.index("project-frame")
    assert not (stock.TRANSFORMS | {"move", "crop-sketch", "import"}).intersection(kinds)


@pytest.mark.parametrize(
    "failure,reason",
    [
        ("missing", "cannot create supplier source point"),
        ("zeros", "point marshaling changed"),
        ("short", "point marshaling changed"),
        ("unmapped", "cannot map supplier source point"),
        ("nonfinite", "source model point is invalid"),
    ],
)
def test_supplier_profile_mapping_rejects_bad_native_math_points(
    monkeypatch, failure, reason,
) -> None:
    seat, stock = _supplier_seat(monkeypatch, drawing.STOCK_CENTER, drawing.STOCK_SCALE)

    def create(values):
        point = _Utility().CreatePoint(values)
        if failure == "missing":
            return None
        if failure == "zeros":
            return _Point((0.0, 0.0, 0.0))
        if failure == "short":
            return _Point(point.ArrayData[:2])
        return SimpleNamespace(
            ArrayData=point.ArrayData,
            MultiplyTransform=lambda _transform: (
                None if failure == "unmapped" else _Point((math.nan, 0.0, 0.0))
            ),
        )

    monkeypatch.setattr(seat, "GetMathUtility", lambda: SimpleNamespace(CreatePoint=create))
    with pytest.raises(RuntimeError, match=reason):
        drawing._supplier_profile_model_points(
            seat, stock, crop_head=False, label="bad source math",
        )
    assert not {"project-frame", "crop-sketch", "import"}.intersection(
        entry[0] for entry in seat.log
    )


def test_full_supplier_profile_fits_its_fixed_cell_only_when_horizontal() -> None:
    assert drawing.STOCK_SCALE == (2.0, 1.0)
    points = drawing.SUPPLIER_PROFILE_MM
    xmin = min(point[0] for point in points) / 1000.0
    xmax = max(point[0] for point in points) / 1000.0
    ymin = min(point[1] for point in points) / 1000.0
    ymax = max(point[1] for point in points) / 1000.0
    ratio = drawing.STOCK_SCALE[0] / drawing.STOCK_SCALE[1]
    cx, cy = drawing.STOCK_CENTER
    semantic_x = (xmin + xmax) / 2.0
    horizontal = (
        cx + ratio * (xmin - semantic_x), cy + ratio * ymin,
        cx + ratio * (xmax - semantic_x), cy + ratio * ymax,
    )
    left, bottom, right, top = drawing.STOCK_VIEW_CELL
    assert left <= horizontal[0] < horizontal[2] <= right
    assert bottom <= horizontal[1] < horizontal[3] <= top
    assert ratio * (xmax - xmin) > top - bottom


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_final_supplier_labels_accept_native_line_endings_but_not_changed_text(
    monkeypatch, newline,
):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "_log_supplier_view_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "assert_supplier_view_fits", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None)
    frames = []
    monkeypatch.setattr(
        drawing, "_assert_supplier_profile_frame",
        lambda _adapter, view, center, scale, *, crop_head, label: frames.append(
            (view.Name, center, scale, crop_head)
        ),
    )
    template = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout]
    monkeypatch.setattr(
        drawing, "sheet_drawable_region",
        lambda *_args, **_kwargs: SimpleNamespace(
            xmin=0.0, ymin=0.0, xmax=template.width_m, ymax=template.height_m,
        ),
    )
    rows = {row.name: row for row in drawing.SUPPLIER_REFERENCE_DIMENSIONS}
    views = []
    for name, keep, scale, cropped in (
        ("stock", drawing.STOCK_KEEP, drawing.STOCK_SCALE, False),
        ("head", drawing.STOCK_HEAD_KEEP, drawing.STOCK_HEAD_SCALE, True),
    ):
        annotations = []
        for dimension_name in keep:
            row = rows[dimension_name]
            band = row.deviations_mm
            tolerance = SimpleNamespace(
                Type=0 if band is None else 3,
                GetMinValue=lambda band=band: 0.0 if band is None else band[0] / 1000.0,
                GetMaxValue=lambda band=band: 0.0 if band is None else band[1] / 1000.0,
            )
            native = SimpleNamespace(
                FullName=f"{row.name}@{drawing.SUPPLIER_STOCK_FEATURE}@source",
                DrivenState=1, Tolerance=tolerance,
            )
            display = SimpleNamespace(
                Type2=row.native_type,
                GetDimension2=lambda _index, native=native: native,
                GetPrimaryTolPrecision2=lambda: drawing.SUPPLIER_PRECISION,
            )
            points = tuple(
                SimpleNamespace(X=x / 1000.0, Y=y / 1000.0, Z=0.0)
                for x, y in (drawing.SUPPLIER_PROFILE_MM[index] for index in row.vertices)
            )
            annotations.append(SimpleNamespace(
                name=row.name, Visible=1,
                GetSpecificAnnotation=lambda display=display: display,
                GetAttachedEntityTypes=lambda: (11, 11),
                GetAttachedEntities3=lambda points=points: points,
            ))
        views.append(SimpleNamespace(
            Name=name, ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
            UseSheetScale=0, ScaleRatio=scale,
            IsCropped=lambda cropped=cropped: cropped,
            UpdateViewDisplayGeometry=lambda: None,
            GetAnnotations=lambda annotations=annotations: annotations,
        ))
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: views)
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            ActivateSheet=lambda _name: True, GetCurrentSheet=lambda: object(),
        ),
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )
    text = drawing.SUPPLIER_STOCK_TITLE
    assert "\n" in text
    state = SimpleNamespace(text=text.replace("\n", newline))
    annotation = SimpleNamespace(Visible=1, OwnerType=1)
    note = SimpleNamespace(
        GetText=lambda: state.text, GetAnnotation=lambda: annotation,
        GetExtent=lambda: (0.03, 0.22, 0.0, 0.15, 0.24, 0.0),
    )
    notes = [(note, text, (0.02, 0.20, 0.18, 0.25))]
    drawing._check_supplier_stock(adapter, *views, notes)
    assert frames == [
        ("stock", drawing.STOCK_CENTER, drawing.STOCK_SCALE, False),
        ("head", drawing.STOCK_HEAD_CENTER, drawing.STOCK_HEAD_SCALE, True),
    ]
    state.text = state.text.replace("NO SOLID GEOMETRY", "SOLID GEOMETRY")
    with pytest.raises(RuntimeError, match="source label changed"):
        drawing._check_supplier_stock(adapter, *views, notes)


def test_supplier_diagnostics_read_native_vertices_not_expected_profile(monkeypatch):
    import ast

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: _DoubleArray(values))
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(drawing, "visible_reference_geometry", lambda *_args: [("OtherSketch", "sketch")])
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", messages.append)
    native_points = [_SketchPoint((0.004, 0.008, 0.0)), _SketchPoint((0.007, 0.012, 0.0))]
    source_transform = SimpleNamespace(
        ArrayData=tuple(range(16)),
        Inverse=lambda: lambda xyz: (xyz[0] + 0.020, xyz[1] - 0.030, xyz[2]),
    )
    segment = SimpleNamespace(
        GetType=lambda: 0, ConstructionGeometry=True,
        GetStartPoint2=lambda: native_points[0], GetEndPoint2=lambda: native_points[1],
    )
    sketch = SimpleNamespace(
        ModelToSketchTransform=source_transform,
        GetSketchPoints2=lambda: native_points, GetSketchSegments=lambda: [segment],
    )
    feature = SimpleNamespace(Visible=1, GetSpecificFeature2=lambda: sketch)
    source = SimpleNamespace(
        FeatureByName=lambda _name: feature, GetPathName=lambda: "source.SLDPRT",
        ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default")),
    )
    bad_outline = (0.1233162, -0.08746936549327414, 0.1555234, 0.1275858660249454)
    view = SimpleNamespace(
        Name="Drawing View4", ReferencedDocument=source,
        ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
        UseSheetScale=0, ScaleRatio=drawing.STOCK_SCALE, Angle=0.41,
        Position=(0.2, 0.1), GetOutline=lambda: bad_outline, IsCropped=lambda: False,
        ModelToViewTransform=SimpleNamespace(ArrayData=tuple(range(16, 32))),
        GetSketch=lambda: SimpleNamespace(
            ModelToSketchTransform=SimpleNamespace(ArrayData=tuple(range(32, 48))),
        ),
    )
    adapter = SimpleNamespace(swApp=SimpleNamespace(GetMathUtility=lambda: _Utility()))
    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda _adapter, _view, points, *, label: [(2 * x + 0.2, 2 * y + 0.1) for x, y, _z in points],
    )
    drawing._log_supplier_view_state(adapter, view, stage="control", geometry=True)
    fields = {
        line.split(" ", 3)[3].split("=", 1)[0]: ast.literal_eval(line.split("=", 1)[1])
        for line in messages
    }
    assert fields["pose"]["outline_m"] == bad_outline
    assert fields["pose"]["angle_rad"] == 0.41
    assert fields["source_geometry"]["source_active_configuration"] == "Default"
    assert fields["source_geometry"]["source_points_m"] == [(0.004, 0.008, 0.0), (0.007, 0.012, 0.0)]
    assert fields["source_geometry"]["sheet_vertex_bounds_m"] == pytest.approx((0.248, 0.056, 0.254, 0.064))
    assert fields["source_geometry"]["segments"] == [{
        "type": 0, "construction": True,
        "endpoints_m": [(0.004, 0.008, 0.0), (0.007, 0.012, 0.0)],
    }]
    assert fields["model_to_view"] == tuple(range(16, 32))
    assert fields["sheet_to_view_sketch"] == tuple(range(32, 48))
    assert fields["source_shown_references"] == [("OtherSketch", "sketch")]
    # Missing diagnostic data must be reported, not fabricated or fatal.
    view.ModelToViewTransform = None
    messages.clear()
    drawing._log_supplier_view_state(adapter, view, stage="missing transform")
    assert "read_error" in messages[-1] and "AttributeError" in messages[-1]


@pytest.mark.parametrize("identity", [0, 1])
def test_supplier_failure_captures_sheet_and_checks_final_frame_before_outline(monkeypatch, identity):
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    views = [
        SimpleNamespace(
            Name=name, ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
            UseSheetScale=0, ScaleRatio=scale, IsCropped=lambda cropped=cropped: cropped,
            UpdateViewDisplayGeometry=lambda: None,
        )
        for name, scale, cropped in (
            ("Drawing View4", drawing.STOCK_SCALE, False),
            ("Drawing View5", drawing.STOCK_HEAD_SCALE, True),
        )
    ]
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(ActivateSheet=lambda _name: True, GetCurrentSheet=lambda: object()),
        swApp=SimpleNamespace(IsSame=lambda _first, _second: identity),
    )
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: views)
    monkeypatch.setattr(drawing, "sheet_drawable_region", lambda *_args, **_kwargs: SimpleNamespace(
        xmin=0.0, ymin=0.0, xmax=0.5, ymax=0.5,
    ))
    calls = []
    monkeypatch.setattr(drawing, "_log_supplier_view_state", lambda _adapter, view, **kwargs: calls.append(
        ("snapshot", view.Name, kwargs["stage"]),
    ))
    monkeypatch.setattr(drawing, "_assert_supplier_profile_frame", lambda _adapter, view, *_args, **_kwargs: calls.append(
        ("frame", view.Name),
    ))
    refusal = RuntimeError("native outline is still vertical")

    def cell(*_args, **_kwargs):
        calls.append(("cell",))
        raise refusal

    def capture(actual_adapter, label, message, **kwargs):
        assert actual_adapter is adapter
        assert label == f"{drawing.PART_STEM}-supplier-envelope"
        assert kwargs["sheet_png"] is True
        calls.append(("capture", kwargs["exception"]))
        raise kwargs["exception"]

    monkeypatch.setattr(drawing, "assert_supplier_view_fits", cell)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    with pytest.raises(RuntimeError) as caught:
        drawing._verify_supplier_stock(adapter, *views, [])
    assert calls[-1] == ("capture", caught.value)
    if identity:
        assert caught.value is refusal
        assert calls[:4] == [
            ("snapshot", view.Name, f"{view.Name}: settled {phase} refresh")
            for view in views for phase in ("before", "after")
        ]
        assert calls[4:6] == [("frame", "Drawing View4"), ("cell",)]
    else:
        assert "identity changed" in str(caught.value)
        assert len(calls) == 1
