"""Title-block text metrics and the PART-name fit rule.

The drawing templates are hand-made binaries (``cad/templates/*.DRWDOT``) whose
title block is sheet-format ink: the PART cell is a template-owned note that
renders the linked model's document summary ``Title`` through ``$PRPSHEET``.
The build cannot choose that note's geometry, but it CAN read the note's format
and fit the name to the field -- which is what this module computes and
:func:`_drawing_common.fit_title_block_part_name` applies.

Why a measured model instead of a rendered measurement
------------------------------------------------------
``cad/docs/solidworks-drawing-layout-tuning.md`` records the one thing the
SolidWorks API will not tell you: **rendered text WIDTH**. There is no API for
it (``IDisplayData::GetTextInBoxWidthAtIndex`` is table cells only). So the
width has to be modelled, and the model has to come from the font the template
actually prints with.

It does. Every released sheet is exported as a native vector PDF that embeds
the title block's own font as a CID subset, and a CID font carries a ``/W``
array: the exact advance width of every glyph, in 1/1000 em, as produced by the
same seat that drew the sheet. :data:`GLYPH_ADVANCE_PER_MILLE` is that array,
merged across all 96 release PDFs of v36 (zero conflicting entries), and
:data:`CAP_HEIGHT_EM` / :data:`DESCENDER_EM` come from the same files'
``/FontDescriptor``. This is the drawing's own data, not a calibration guess and
not a pixel measurement, and it is exact rather than estimated.

Measured on the v36 release renders (``cad/out/pdf``, 96 sheets / 104 title
blocks), all values in sheet millimetres:

* the PART value prints at 16 pt Century Gothic, left-justified, sharing its
  left edge with the ``PART`` label on every one of the 104 title blocks;
* the note's line spacing is exactly 1 em (two-line sheets put their baselines
  5.6444 mm apart at 16 pt);
* the note wraps at a line length in **[68.834, 69.669) mm** -- bracketed from
  below by the widest line that rendered unwrapped ("Brass Fillister Head
  Slotted", 68.834 mm) and from above by the narrowest line-plus-next-word that
  did NOT fit ("Steel Narrow Fillister Head", 69.669 mm), with no contradiction
  across the 18 sheets that wrap. Both are ADVANCE widths -- the quantity a
  wrap decision is made on -- so they run about 0.05 mm past where the last
  glyph's ink stops. That box is only 65% of the 106.62 mm cell it sits in,
  which is the defect: the note wraps with 37 mm of its own field unused, and
  the second line lands below the cell's lower rule, on the ``DWG. NO.`` label.

Character count is NOT the threshold. Century Gothic is proportional, so the
fleet's 15-character names span 35.64 mm ("pinion-lift-rod") to 49.04 mm
("Metal Round Cap"), and a 34-character name ("Brass Fillister Head Slotted
Screw", 86.92 mm) overflows while a 24-character one
("channel-spring-installed", 64.82 mm) does not. The rule is width-based.
"""

from __future__ import annotations

from dataclasses import dataclass


TITLE_BLOCK_TYPEFACE = "Century Gothic"

# The FACE the glyph table was measured from, not just the family. A family
# name does not determine advance widths: ``ITextFormat`` carries Bold and
# Italic independently of ``TypeFaceName``, so a template re-authored in bold
# Century Gothic keeps reporting "Century Gothic" while every advance moves.
#
# Checked against the Windows-shipped Century Gothic faces by decoding their
# ``hmtx``/``cmap`` and scaling to 1/1000 em: GLYPH_ADVANCE_PER_MILLE matches
# GOTHIC.TTF (regular) on all 81 glyphs and differs from GOTHICB.TTF (bold) on
# 79 of them (ratio 0.83..1.28, mean 1.019). Bold is enough to re-wrap the
# fleet: "Brass Fillister Head Slotted" -- the line PROVEN to render unwrapped
# at 68.834 mm -- measures 69.765 mm bold, past the wrap bracket.
TITLE_BLOCK_BOLD = False
# Century Gothic Italic is metrically compatible: its advances are identical
# to regular on all 81 glyphs, so italic cannot move a WRAP decision. It is
# still pinned, because the slant puts ink to the right of the advance box
# that :func:`fitted_text_box_mm` and the cell's right rule are compared in,
# and because the model's provenance is the upright face.
TITLE_BLOCK_ITALIC = False

MM_PER_POINT = 25.4 / 72.0

# /FontDescriptor of the embedded Century Gothic subset, per em.
CAP_HEIGHT_EM = 0.718
DESCENDER_EM = 0.307

# Measured: two-line sheets place consecutive baselines exactly one em apart.
LINE_SPACING_EM = 1.0

# What INote::GetExtent reports for a note that occupies ONE line, in ems of
# the size the note reports back.
#
# The extent is NOT the glyph box. SolidWorks anchors a note's extent on the
# descender and reserves a full line pitch of leading above the line it
# draws, so one line measures the glyph box (1.025 em = CAP_HEIGHT_EM +
# DESCENDER_EM) plus about one LINE_SPACING_EM -- close to 2 em -- and a
# second line adds another LINE_SPACING_EM on top of that.
#
# MEASURED, on the 15 landscape sheets whose fitted notes reported an extent
# in the farm build of integration head c99e0026 -- every sheet the fit step
# touched, all 15 refused by the 1.8 bound this value replaces -- after
# 6d3704a6 removed the system-units height write
# (em = extent_mm / (pt * MM_PER_POINT)):
#
#   10.91 mm @ 15 pt  2.0617 em  slotted_screw, frame_side_screw
#   10.52 mm @ 15 pt  1.9880 em  foot_screw, gooseneck_set_screw,
#                                clamp_screw, swing_stop_screw,
#                                bracket_screw, cone_lock_knob
#    8.33 mm @ 12 pt  1.9677 em  hex_bolt, hanger_screw
#   10.96 mm @ 16 pt  1.9417 em  fillister_screw, lag_screw,
#                                harmonic_analyzer_assembly
#    7.45 mm @ 11 pt  1.9198 em  cone_pivot_screw
#    8.77 mm @ 13 pt  1.9123 em  cone_tip_adjuster
#
# This constant is the MAXIMUM of that distribution, not its mean: the check
# is one-sided, so the bound has to clear the tallest legitimate sheet.
#
# The extent is NOT a function of the name. 'harmonic-analyzer assembly' and
# 'Brass Fillister Head Slotted Screw' are different strings of different
# lengths on different parts, and both measured 10.96 mm at 16 pt; while two
# sheets carrying the SAME name ('Steel Narrow Fillister Head Slotted Screw'
# on slotted_screw and swing_stop_screw) measured 10.91 and 10.52 mm at the
# same 15 pt. What varies is the SHEET; what the extent depends on is the
# size and the template. That is also why shrinking the font can never
# rescue a refused sheet: the ratio this bound is compared against is
# scale-invariant, so the fit step's step-down loop moves the width and
# leaves the height ratio exactly where it was.
#
# Six discrete values over 15 sheets, each shared to the last digit by every
# sheet that reports it and spanning 7.8% -- a quantised distribution, not a
# continuous spread. The quantising variable is not identified: the repo
# ships exactly two sheet formats (cad/templates/harmonic-analyzer-
# {landscape,portrait}.DRWDOT) and all 15 sheets use the landscape one, so it
# is not a template revision; and GetExtent is proven to report unscaled
# sheet millimetres (_purchased_fastener_drawing checks its own notes'
# extents against absolute cell geometry on these very sheets), so it is not
# sheet scale.
#
# The sample is COMPLETE for the sheets that reached the check, not a
# survivors' sample. The bound it replaces refused anything above
# 1.8 x 1.05 = 1.89 em, and the smallest value here is 1.9123 em, so no
# sheet could have reached this check and passed: every one of the 15 was
# refused and printed its measurement. There is no taller sheet hiding
# behind a silent pass.
#
# What the new logging buys is the NEXT build, not this sample: every sheet
# that reaches the check now reports its extent with its layout (see
# _drawing_common.fit_title_block_part_name), pass or refusal, so the
# distribution is re-measured instead of re-argued.
#
# The portrait template is not in the sample, and no portrait sheet reaches
# this check: of the 96 fleet names 18 need fitting and all 18 are
# landscape, while the three portrait sheets (cylinder-gear 36.51 mm,
# tube-frame 31.03 mm, and frame-assembly 43.06 mm, which is portrait only
# through additional_layouts) all print at the authored 16 pt inside a
# 68.834 mm proven line. That is pinned by
# test_no_portrait_sheet_needs_its_name_fitted rather than assumed, because
# nothing in the code restricts this check to one layout. If a portrait name
# ever does grow long enough, its extent arrives in that log line and this
# constant is where the reading gets recorded.
#
# The earlier value was 1.8, which was never a measurement of anything. It
# was the threshold 37e961c4 placed between the glyph box (1.025 em) and what
# it ASSUMED a second line would measure (2.025 em), on the reasoning that
# "one line -- glyph box 1.025 em, plus whatever padding SolidWorks adds --
# cannot reach 1.8 em". One line reaches 1.91..2.06 em, so the bound sat
# BELOW the quantity it bounds and refused every sheet the fit touched.
# 6d3704a6 then re-labelled it as measured -- "a 16 pt note extents 10.16 mm
# = 1.800 em" -- from 14.03/1.381, where 1.381 was itself 14.03/(1.8 em):
# the same error used to confirm itself.
ONE_LINE_EXTENT_EM = 2.062

# How far above ONE_LINE_EXTENT_EM a measured extent may sit before the sheet
# is refused. This is NOT slack for rounding, and the margin it leaves is NOT
# an order of magnitude -- an earlier version of this comment claimed that,
# and the claim was part of the defect.
#
# What is actually being separated, in em (all measured, see above):
#
#   legitimate one line     1.9123 .. 2.0617
#   with the units write    2.4850 .. 2.6362   (four sheets; the inflation is
#                                              per-sheet, 1.2053 .. 1.3261,
#                                              NOT one factor)
#   floor of that band      2.3049             (the shortest legitimate sheet
#                                              times the smallest measured
#                                              inflation: 1.9123 x 1.2053)
#   a second line           2.9 .. 3.2         (one line + LINE_SPACING_EM;
#                                              cone_tip_adjuster, the sheet
#                                              that did wrap, measured 3.173
#                                              em de-inflated)
#
# So the corridor to place the refusal in runs from the tallest legitimate
# sheet (2.0617) to the extrapolated floor of the defect band (2.3049),
# 11.8% wide. At this tolerance the refusal starts at 2.1651 em: 5.0% above
# the tallest legitimate sheet, 6.1% below the floor.
#
# The bounds on editing it, since all three were once stated wrongly here:
#
# * 0.1178 is where a defective sheet gets through (2.3049/2.062 - 1). Not
#   0.058: that is sqrt(2.3049/2.0617) - 1, the geometric midpoint of the
#   corridor -- where the split stops being even, which is not the same
#   thing as where the guard stops working. 0.205 is where the lowest
#   OBSERVED defect (2.4850) gets through.
# * 0.034 is where it may no longer be TIGHTENED (0.0337 = 15/14.51 - 1, at
#   the 15 pt end; 0.0576 at the 9 pt floor). Below that, which of two sizes
#   the extent is divided by starts to decide verdicts: the applier accepts
#   a note whose reported size rounds to the requested one, so the two may
#   differ by up to 0.49 pt. That is a bound from round(), a code contract
#   in _drawing_common -- not COM noise; a VARIANT round trip drifts 1e-12,
#   not half a point.
#
# Note that the tests defend the PRODUCT, ONE_LINE_EXTENT_EM * (1 + this),
# which has to land in (2.0617, 2.3049]. They do not pin either factor: all
# six readings pass at a constant of 2.0 as well (2.0617/2.0 = 1.031 < 1.05).
# Simplifying the constant and staying green is therefore possible -- and
# the reason not to is that the constant is a MEASUREMENT with a provenance
# and the tolerance is a decision about how much of the corridor to spend.
ONE_LINE_EXTENT_TOLERANCE = 0.05

# Glyph advances in 1/1000 em, from the ``/W`` array of the Century Gothic CID
# subset embedded in the v36 release PDFs. ASCII only: the CID-to-character
# decode is proved by 104 title blocks' worth of text decoding to correct
# English over this range, and the handful of higher CIDs (the copyright sign,
# the diameter sign) decode ambiguously, so they are deliberately absent and
# fall back to FALLBACK_ADVANCE_PER_MILLE rather than carrying a guess.
GLYPH_ADVANCE_PER_MILLE = {
    ' ': 277, '"': 309, '#': 720, '%': 775, "'": 198, '(': 369, ')': 369,
    '*': 425, '+': 606, ',': 277, '-': 332, '.': 277, '/': 437, '0': 554,
    '1': 554, '2': 554, '3': 554, '4': 554, '5': 554, '6': 554, '7': 554,
    '8': 554, '9': 554, ':': 277, ';': 277, '=': 606, '>': 606, 'A': 740,
    'B': 574, 'C': 813, 'D': 744, 'E': 536, 'F': 485, 'G': 872, 'H': 683,
    'I': 226, 'J': 482, 'K': 591, 'L': 462, 'M': 919, 'N': 740, 'O': 869,
    'P': 592, 'Q': 871, 'R': 607, 'S': 498, 'T': 426, 'U': 655, 'V': 702,
    'W': 960, 'X': 609, 'Y': 592, 'Z': 480, 'a': 683, 'b': 682, 'c': 647,
    'd': 685, 'e': 650, 'f': 314, 'g': 673, 'h': 610, 'i': 200, 'j': 203,
    'k': 502, 'l': 200, 'm': 938, 'n': 610, 'o': 655, 'p': 682, 'q': 682,
    'r': 301, 's': 388, 't': 339, 'u': 608, 'v': 554, 'w': 831, 'x': 480,
    'y': 536, 'z': 425, '|': 672, '~': 606,
}

# The widest advance in the table ('W'). An unmeasured character is charged the
# widest glyph, so the width model can only ever OVER-estimate -- which makes
# the fit step down further than strictly needed and never overflow the field.
FALLBACK_ADVANCE_PER_MILLE = max(GLYPH_ADVANCE_PER_MILLE.values())


def text_advance_em(text: str) -> float:
    """Advance width of ``text`` in em, from the template font's own metrics."""
    return (
        sum(
            GLYPH_ADVANCE_PER_MILLE.get(char, FALLBACK_ADVANCE_PER_MILLE)
            for char in text
        )
        / 1000.0
    )


def text_width_mm(text: str, point_size: float) -> float:
    """Rendered width of ``text`` at ``point_size``, in sheet millimetres."""
    return text_advance_em(text) * point_size * MM_PER_POINT


@dataclass(frozen=True)
class PartNameField:
    """One drawing template's measured title-block PART field.

    All millimetres, sheet space, origin at the sheet's lower-left -- the same
    frame ``IAnnotation::GetPosition`` and ``INote::GetExtent`` report in
    (metres there; this module reports mm and converts at the COM boundary).

    ``cell_*`` is the ruled cell. ``text_left_mm`` / ``baseline_mm`` are where
    the template anchors the value's first line; ``label_*`` describe the
    ``PART`` caption above it, which is what bounds the value from above.
    """

    cell_left_mm: float
    cell_right_mm: float
    cell_bottom_mm: float
    cell_top_mm: float
    text_left_mm: float
    baseline_mm: float
    label_baseline_mm: float
    label_point_size: float
    # The template's authored size for the value, and the floor a step-down may
    # not go below: ASME Y14.2 sets 3 mm (0.12 in) as the minimum character
    # height for a title-block title, and 9 pt = 3.175 mm is already used by
    # this very title block's FINISH and MATERIAL values.
    nominal_point_size: int = 16
    minimum_point_size: int = 9
    # The line length at which the template's note is PROVEN to wrap nothing:
    # the lower bound of the measured bracket. A name that fits here needs no
    # intervention at all, so this constant is what keeps the fit a no-op on
    # every sheet that renders correctly today.
    proven_line_length_mm: float = 68.834
    # The wrap decision belongs to SolidWorks, and it is made in SolidWorks'
    # own arithmetic on a line length we hand over in metres. This model is
    # exact in the font's units, but it is not the same code, so a fitted line
    # is required to stop short of the field by a third of a space glyph --
    # enough that a rounding difference cannot re-wrap it, small enough to cost
    # at most one point of size.
    fit_margin_mm: float = 0.5

    @property
    def side_inset_mm(self) -> float:
        """The template's left text inset, mirrored on the right."""
        return self.text_left_mm - self.cell_left_mm

    @property
    def line_length_mm(self) -> float:
        """The field's usable single-line width: the cell, inset both sides."""
        return self.cell_right_mm - self.side_inset_mm - self.text_left_mm

    def value_ceiling_mm(self) -> float:
        """Highest y the value's glyphs may reach: the label's descender."""
        return self.label_baseline_mm - DESCENDER_EM * self.label_point_size * MM_PER_POINT


@dataclass(frozen=True)
class PartNameFit:
    """The single-line plan for one PART name."""

    name: str
    point_size: int
    width_mm: float
    line_length_mm: float
    # True when the template's own note has to be touched to realise the plan.
    adjust: bool

    @property
    def line_height_mm(self) -> float:
        """Cap-to-descender height of one rendered line."""
        return (CAP_HEIGHT_EM + DESCENDER_EM) * self.point_size * MM_PER_POINT


class PartNameDoesNotFit(RuntimeError):
    """A PART name cannot be printed on one legible line in its field."""


def fit_part_name(name: str, field: PartNameField) -> PartNameFit:
    """Plan the PART name as ONE line inside ``field``.

    The rule, in full:

    1. A name whose width at the template's nominal size already fits the
       field's PROVEN line length is left alone -- no plan to apply, no
       template ink touched, byte-identical output.
    2. Otherwise the name is fitted to the field's full usable width
       (``line_length_mm``, the ruled cell inset by the template's own text
       inset) at the largest integer point size <= nominal whose rendered width
       clears that width by ``fit_margin_mm``. Integer because
       ``ITextFormat::CharHeightInPts`` is an int.
    3. A name that will not fit one line at ``minimum_point_size`` raises.
       Nothing in the fleet comes close (the widest needs 11 pt), and failing
       the build beats shipping a title block that collides with its own rules.

    Two lines are deliberately not an option. The cell is 11.60 mm tall and the
    ``PART`` caption takes the top of it: the value band between the lower rule
    and the caption's descender is 7.11 mm, so two lines plus interline spacing
    at the 3 mm ASME minimum leaves under half a millimetre of total slack.
    That is not a clearance anyone can defend across seats, so the field is
    treated as what it is -- a single-line field.
    """
    if not name:
        raise ValueError("PART name is empty")
    nominal = field.nominal_point_size
    if text_width_mm(name, nominal) <= field.proven_line_length_mm:
        return PartNameFit(
            name=name,
            point_size=nominal,
            width_mm=text_width_mm(name, nominal),
            line_length_mm=field.proven_line_length_mm,
            adjust=False,
        )
    budget = field.line_length_mm
    for point_size in range(nominal, field.minimum_point_size - 1, -1):
        width = text_width_mm(name, point_size)
        if width <= budget - field.fit_margin_mm:
            return PartNameFit(
                name=name,
                point_size=point_size,
                width_mm=width,
                line_length_mm=budget,
                adjust=True,
            )
    raise PartNameDoesNotFit(
        f"PART name {name!r} needs "
        f"{text_width_mm(name, field.minimum_point_size):.2f} mm at the "
        f"{field.minimum_point_size} pt minimum but the field offers only "
        f"{budget - field.fit_margin_mm:.2f} mm; shorten the name or widen the "
        "title-block cell"
    )


def fitted_text_box_mm(fit: PartNameFit, field: PartNameField) -> tuple[float, float, float, float]:
    """``(left, bottom, right, top)`` the fitted single line will occupy."""
    size_mm = fit.point_size * MM_PER_POINT
    return (
        field.text_left_mm,
        field.baseline_mm - DESCENDER_EM * size_mm,
        field.text_left_mm + fit.width_mm,
        field.baseline_mm + CAP_HEIGHT_EM * size_mm,
    )


def fit_is_contained(fit: PartNameFit, field: PartNameField) -> bool:
    """True when the fitted line sits wholly inside its own field."""
    left, bottom, right, top = fitted_text_box_mm(fit, field)
    return (
        left >= field.cell_left_mm
        and right <= field.cell_right_mm
        and bottom >= field.cell_bottom_mm
        and top <= field.value_ceiling_mm()
    )
