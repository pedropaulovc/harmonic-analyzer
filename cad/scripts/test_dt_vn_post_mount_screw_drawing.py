"""Offline contracts for the MHA-DT-VN-61 cone pivot post mount screw."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_deviations
import build_dt_vn_post_mount_screw as part
import dt_cone_pivot_post_spec as post
import dt_cone_swing_platform_spec as platform
import draw_dt_vn_post_mount_screw as drawing
from _fit_deviations import deviations
import dt_vn_post_mount_screw_spec as spec
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
    assert engagement / part.SHANK_DIA >= 0.87


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
    length below what the 0.87D corner (highest floor, after both edge
    breaks) needs.  So no band can go on the print."""
    unit = drawing_unit("parts/dt-cone-pivot-post", _config.parts("dt-cone-pivot-post"))
    places = post.DRAWING_PRECISION_BY_NAME["MainBodyHt"]
    height_lo, height_hi = printed_deviations(post.BLOCK_HEIGHT, places, unit=unit)
    depth_lo, depth_hi = printed_deviations(post.ATTACHMENT_CBORE_DEPTH, 2, unit=unit)
    low = (post.BLOCK_HEIGHT + height_lo) - (post.ATTACHMENT_CBORE_DEPTH + depth_hi)
    high = (post.BLOCK_HEIGHT + height_hi) - (post.ATTACHMENT_CBORE_DEPTH + depth_lo)
    assert (spec.FLOOR_LOW_MM, spec.FLOOR_HIGH_MM) == pytest.approx((low, high))
    thin = platform.PLATE_THICKNESS - spec.PLATE_STOCK_BAND_MM
    assert spec.FIXED_LENGTH_FLUSH_MAX_MM == pytest.approx(low + thin)
    need = (
        high
        + 0.87 * part.SHANK_DIA
        + spec.POST_MOUNT_TAP_EDGE_BREAK
        + spec.CUT_END_BREAK_MAX_MM
    )
    assert spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM == pytest.approx(need)
    assert spec.FIXED_LENGTH_ENGAGEMENT_MIN_MM > spec.FIXED_LENGTH_FLUSH_MAX_MM
    assert spec.FIXED_CUT_LENGTH_EXISTS is False


def test_only_the_factory_thread_reaches_the_tapped_plate() -> None:
    """MSC threads 1.500 in up from the supplied tip; the shank above is plain.
    Even on the lowest floor the plate's tapped hole lies below the thread
    start, so the engagement chain counts full thread only."""
    assert spec.FACTORY_THREAD_START_MM == pytest.approx((4.000 - 1.500) * IN)
    assert spec.FACTORY_THREAD_START_MM < spec.FLOOR_LOW_MM
    assert spec.FACTORY_THREAD_START_MM < spec.CUT_LENGTH_MM


def test_cut_length_prints_as_a_reference_without_a_band() -> None:
    """No fixed length exists, so the model's spec-derived length prints in
    parentheses without a band; the callout carries fit-to-hole acceptance."""
    assert spec.CUT_LENGTH_MM == part.SHANK_LEN
    places = spec.DRAWING_PRECISION_BY_NAME[spec.CUT_LENGTH_DIMENSION]
    # The model's length sits on the inch grid it prints at (#290).
    assert spec.CUT_LENGTH_MM / IN * 10**places == pytest.approx(
        round(spec.CUT_LENGTH_MM / IN * 10**places), abs=1e-6
    )
    assert 0.0 <= GRIP + platform.PLATE_THICKNESS - spec.CUT_LENGTH_MM
    assert GRIP + platform.PLATE_THICKNESS - spec.CUT_LENGTH_MM <= (
        spec.POST_SCREW_CUT_TO_FIT_SHORT
    )
    callout = drawing.DIMENSION_CALLOUTS["CutLength"]
    # The callout still promises no fixed length: never the modelled cut
    # length, never a band on it.
    assert spec.inch_text(spec.CUT_LENGTH_MM, places) not in callout
    assert "±" not in callout and "+" not in callout


def test_cut_to_fit_acceptance_prints_on_the_delegating_callout() -> None:
    """Codex P1 on #857: the callout delegated the cut to assembly, but no
    MHA-DT-00 step stated the acceptance the 0.90D worst case depends on.  The
    acceptance is a spec band -- upper 0 (flush), lower the most a screw may
    be cut short -- and the sheet prints it, generated from that band at its
    own places, not a literal.  Rule 7 (novice rubric): a callout carries at
    most two lines of words, and round 1 showed the acceptance cannot sit
    between the extension lines (rule 14), so the callout links to numbered
    note 1 and the note carries it; NEVER PROUD only restated the flush limit."""
    lower, upper = deviations(spec.POST_SCREW_CUT_TO_FIT_BAND)
    assert upper == 0.0
    assert spec.POST_SCREW_CUT_TO_FIT_SHORT == -lower
    places = spec.CUT_TO_FIT_SHORT_PLACES
    callout = drawing.DIMENSION_CALLOUTS["CutLength"]
    assert callout == drawing.CUT_LENGTH_CALLOUT == "SEE NOTE 1"
    lines = drawing.CUT_LENGTH_NOTE.splitlines()
    assert len(lines) == 2
    assert lines[0] == (
        f"1. CUT END FLUSH TO {spec.inch_text(-lower, places)} SHORT OF MHA-DT-20 UNDERSIDE."
    )
    assert "NEVER PROUD" not in drawing.CUT_LENGTH_NOTE
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


def test_engagement_minimum_prints_on_the_cut_length_note() -> None:
    """Codex P2 on #857 (PRRT_kwDOPHDy386mOxdw): MHA-DT-VN-61 stated its 0.90D
    engagement shortfall nowhere, yet the policy's named-exceptions section
    wants every affected sheet to state it.  Note 1, which the cut length's
    callout links to, carries the worst-case minimum as a plain fact,
    floored from the spec's worst case -- never a literal."""
    printed = spec.POST_MOUNT_ENGAGEMENT_PRINTED
    assert printed == math.floor(
        spec.POST_MOUNT_ENGAGEMENT_WORST / spec.THREAD_DIA_MM * 100.0
    ) / 100.0
    assert printed >= spec.MIN_ENGAGEMENT_DIAMETERS
    fact = f"ENGAGEMENT {printed:.2f}D MIN."
    # It closes the acceptance the cut delegates to assembly.
    assert drawing.CUT_LENGTH_NOTE.splitlines()[-1].strip() == fact


def test_engagement_shortfall_is_declared_for_the_blind_reviewer() -> None:
    """A stated shortfall with no package-local declaration gates like a
    blocker; RV-01 names the fact the sheet prints, as a minor."""
    from machinist_exceptions import load_exceptions

    (entry,) = load_exceptions(_config.CONFIG_DIR, "dt_vn_post_mount_screw", "part")
    assert (entry.id, entry.kind) == ("RV-01", "minor")
    assert f"ENGAGEMENT {spec.POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN" in entry.where
    assert "rule 18" in entry.finding


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
        "cut-length note": drawing.CUT_LENGTH_NOTE,
        "manufacturing notes": spec.MANUFACTURING_NOTES,
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
    assert spec.POST_SCREW_CUT_TO_FIT_SHORT == 0.127  # .005 in


def test_cut_end_break_is_the_title_block_edge_break() -> None:
    """Main's run-7 and 2026-11-01 rulings: no part-local break limit at either
    end; the engagement stack spends the title block's general chamfer at the
    screw's cut end and at the platform's tap."""
    assert spec.CUT_END_BREAK_MAX_MM == edge_break_chamfer_mm(unit="in")
    assert spec.POST_MOUNT_TAP_EDGE_BREAK == edge_break_chamfer_mm(unit="in")


def test_worst_case_engagement_holds_the_named_minimum() -> None:
    """Cut to fit, the plate limits engagement: thinnest stock, the full
    fit-to-hole allowance, the tap's entry deburr and the cut end's general
    edge break, both at their maximum, recomputed here from the chain."""
    worst = (
        platform.PLATE_THICKNESS
        - spec.PLATE_STOCK_BAND_MM
        - spec.POST_SCREW_CUT_TO_FIT_SHORT
        - spec.POST_MOUNT_TAP_EDGE_BREAK
        - edge_break_chamfer_mm(unit="in")
    )
    assert spec.POST_MOUNT_ENGAGEMENT_WORST == pytest.approx(worst)
    assert worst / part.SHANK_DIA >= 0.87
    assert spec.POST_MOUNT_ENGAGEMENT_PRINTED >= 0.87


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


def _independent_removal() -> float:
    """Brute-force the trim's removed volume (midpoint rule, 2k slices):
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
    return trim


def test_analytic_removal_volume_matches_a_brute_force_integral() -> None:
    assert spec.TRIM_REMOVED_MM3 == pytest.approx(_independent_removal(), rel=1e-4)


def test_cut_end_features_are_driven_by_the_model_dimensions() -> None:
    """The trim follows CutLength by equation."""
    assert part.TRIM_DRIVES == {"TrimAt": '"CutLength@CutLengthReference"'}
    assert part.TRIM_FEATURE == "CutToLength"
    # The trimmed tip cannot reach into what the stock carries: the cut
    # clears the factory tip, and the volume gate outruns the sweep's slack.
    assert spec.STOCK_LENGTH_MM - spec.FACTORY_TIP_CHAMFER_MM > spec.CUT_LENGTH_MM
    assert part.TRIM_VOLUME_TOL_MM3 < 0.01 * spec.TRIM_REMOVED_MM3


def _printed_cut_short_allowance() -> float:
    """The acceptance the sheet prints: "END FLUSH TO <x> SHORT"."""
    match = re.search(r"END FLUSH TO (\d*\.\d+) SHORT", drawing.CUT_LENGTH_NOTE)
    assert match, drawing.CUT_LENGTH_NOTE
    return round(float(match.group(1)) * IN, 9)


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
    middle = (_short_of_underside(0.0) - allowance / 2.0) / IN
    assert spec.CUT_LENGTH_MM / IN == pytest.approx(
        math.floor(middle * 10**places + 0.5) / 10**places
    )
    assert part.SHANK_LEN == spec.CUT_LENGTH_MM


def test_engagement_exception_is_held_by_the_model() -> None:
    """The rule-18 shortfall pending #1019 (floor 0.87D) is a model assert on the
    chain; the sheet prints it on the cut-length callout
    (test_engagement_minimum_prints_on_the_cut_length_callout)."""
    assert spec.MIN_ENGAGEMENT_DIAMETERS == 0.87
    assert spec.ENGAGEMENT_NOMINAL_MM == spec.CUT_LENGTH_MM - GRIP
    assert spec.ENGAGEMENT_NOMINAL_MM / part.SHANK_DIA >= 0.87


def test_sheet_layout_keeps_notes_clear_of_the_view() -> None:
    """The 1:1 Front lies head left on a horizontal axis (as sheet 2 draws
    the supplied stock); the cut length and its one word line read below the
    shank between its own extension lines (round 1: a wider callout was
    struck by them, rule 14), above note 1 and the reference note."""
    head_r = part.HEAD_DIA / 2000.0
    assert drawing.FRONT_AXIS_MID[1] == drawing.FRONT_CENTER[1]
    x, y = drawing.FRONT_KEEP["CutLength"]
    assert x == drawing.FRONT_AXIS_MID[0]
    assert y + 0.004 < drawing.FRONT_AXIS_MID[1] - head_r
    lines = drawing.DIMENSION_CALLOUTS["CutLength"].splitlines()
    # The widest callout line (~2.85 mm per capital, warm-c486) fits well
    # inside the extension lines, which stand CUT_LENGTH_MM apart.
    widest = max(len(line) for line in lines)
    assert widest * 0.00285 < spec.CUT_LENGTH_MM / 1000.0 - 0.020
    # Value line plus the callout's lines, ~4.5 mm each, then note 1 (two
    # lines), then the reference note, then the stock rows.
    callout_bottom = y - (1 + len(lines)) * 0.0045
    note_x, note_y = drawing.CUT_LENGTH_NOTE_XY
    assert note_x == drawing.NOTES_XY[0]
    assert note_y + 0.004 < callout_bottom
    note_lines = len(drawing.CUT_LENGTH_NOTE.splitlines())
    notes_y = drawing.NOTES_XY[1]
    assert notes_y + 0.003 < note_y - note_lines * 0.0045
    notes = len(spec.MANUFACTURING_NOTES.splitlines())
    assert notes_y - notes * 0.0045 > max(y for _, _, y in drawing.STOCK_ROWS) + 0.003
    # Note 1's long line (~2.2 mm per capital at 3 mm) stays left of the
    # title block.
    longest = max(len(line) for line in drawing.CUT_LENGTH_NOTE.splitlines())
    assert note_x + longest * 0.0025 < drawing.ISO_CENTER[0]
    # The head, ~6 mm left of the under-head face, stays inside the border.
    left = drawing.FRONT_AXIS_MID[0] - spec.CUT_LENGTH_MM / 2000.0 - part.HEAD_H / 1000.0
    assert left > 0.015
    assert not hasattr(drawing, "BREAK_TEXT")


def test_detail_a_boundary_circles_the_head_on_the_full_view() -> None:
    """Rule 9: the 6:1 head view is DETAIL A of the full 2:1 view, with its
    boundary on that parent; the full view, the sheet's principal view,
    carries no caption and no scale (it is the sheet's)."""
    head = next(
        row.expected_mm for row in spec.SUPPLIER_PROFILE_DIMENSIONS
        if row.name == "SupplierHeadHeight"
    )
    length = next(
        row.expected_mm for row in spec.SUPPLIER_PROFILE_DIMENSIONS
        if row.name == "SupplierStockLength"
    )
    ratio = drawing.STOCK_SCALE[0] / drawing.STOCK_SCALE[1]
    # The full view centres (L - H) / 2; the head's centre is -H / 2.
    expected_x = drawing.STOCK_CENTER[0] + ratio * (-head / 2.0 - (length - head) / 2.0) / 1000.0
    assert drawing.DETAIL_BOUNDARY_CENTER == pytest.approx((expected_x, drawing.STOCK_CENTER[1]))
    assert drawing.DETAIL_BOUNDARY_RADIUS_M == pytest.approx(
        drawing.STOCK_HEAD_RADIUS_MM * ratio / 1000.0
    )
    cx, cy = drawing.DETAIL_BOUNDARY_CENTER
    r = drawing.DETAIL_BOUNDARY_RADIUS_M
    left, bottom, right, top = drawing.STOCK_VIEW_CELL
    assert left < cx - r and cx + r < right and bottom < cy - r and cy + r < top
    texts = [text for text, *_ in drawing.STOCK_NOTES]
    assert texts == [
        spec.SUPPLIER_STOCK_TITLE, "DETAIL A  SCALE 6:1", drawing.DETAIL_LETTER,
    ]
    assert not any("2:1" in text or "ENVELOPE  SCALE" in text for text in texts)
    # The letter stands outside the boundary, clear of the head view's cell.
    _, x, y, (lx, ly, ux, uy) = drawing.STOCK_NOTES[2]
    assert lx <= x <= ux and ly <= y <= uy
    corners = [(px, py) for px in (lx, ux) for py in (ly, uy)]
    assert min(math.dist(corner, (cx, cy)) for corner in corners) > r
    assert uy < drawing.STOCK_HEAD_CELL[1]


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


@pytest.mark.parametrize("fault", ["one-ulp", "duplicate"])
def test_supplier_profile_state_matches_vertices_without_float_ordering(fault):
    row = next(
        row
        for row in drawing.SUPPLIER_REFERENCE_DIMENSIONS
        if drawing.SUPPLIER_PROFILE_MM[row.vertices[0]][0]
        == drawing.SUPPLIER_PROFILE_MM[row.vertices[1]][0]
        and drawing.SUPPLIER_PROFILE_MM[row.vertices[0]][1]
        != drawing.SUPPLIER_PROFILE_MM[row.vertices[1]][1]
    )
    points = sorted(
        [(*drawing.SUPPLIER_PROFILE_MM[index], 0.0) for index in row.vertices],
        key=lambda point: point[1],
    )
    points = [
        (math.nextafter(points[0][0], math.inf), *points[0][1:]),
        (math.nextafter(points[1][0], -math.inf), *points[1][1:]),
    ]
    if fault == "duplicate":
        points[1] = points[0]
    if fault == "duplicate":
        with pytest.raises(RuntimeError, match="source-diagram vertices"):
            drawing._assert_supplier_profile_vertices(row, points)
    else:
        drawing._assert_supplier_profile_vertices(row, points)


@pytest.mark.parametrize(
    "actual,expected",
    [
        ([(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]),
        ([(0.0, 0.0, 0.0), (1e-9, 0.0, 0.0)], [(0.0, 0.0, 0.0), (1e-9, 0.0, 0.0)]),
    ],
)
def test_supplier_points_match_refuses_duplicate_or_ambiguous_points(actual, expected):
    assert not drawing._supplier_points_match(actual, expected, tolerance=1e-8)
