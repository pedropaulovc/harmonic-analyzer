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
# Re-derived from the release PDFs' text matrices (the recipe is under
# EXTENT_BOTTOM_RESERVE_EM): 38.3648, 32.7204 and 27.0759 mm, differences of
# 5.6444 mm = 16 pt to four decimals.
LINE_SPACING_EM = 1.0

# What INote::GetExtent reports for a note that occupies ONE line, in ems of
# the size the note reports back.
#
# The extent is NOT the glyph box, and it is NOT centred on it. SolidWorks
# reports a box that is anchored at its TOP -- the note's own anchor, which
# does not move when the size changes -- with the line's ink just under that
# top edge and about a full line pitch of empty reserve BELOW the descender,
# room for the next line the note does not have. So one line measures the
# glyph box (1.025 em = CAP_HEIGHT_EM + DESCENDER_EM) plus roughly one
# LINE_SPACING_EM, close to 2 em, and a second line consumes the reserve and
# adds another pitch under it. Measured split, at 16 pt, where the applied
# size equals the template's authored size and the ink is therefore exactly
# where the v36 renders measured it (baseline 38.3648 mm):
#
#   0.068 em  above the cap height   (box top 42.80 mm, cap top 42.42 mm)
#   1.025 em  the ink itself         (cap top down to descender 36.63 mm)
#   0.849 em  reserve below the ink  (descender down to box bottom 31.84 mm)
#
# An earlier version of this comment put the reserve ABOVE the ink. That was
# an inference, and it was wrong; see EXTENT_BOTTOM_RESERVE_EM, which is the
# measurement, and which the cell-rule check needs because the box bottom
# and the ink bottom are 4.79 mm apart at 16 pt.
#
# MEASURED, on the 18 landscape sheets whose fitted notes reported an extent
# in the farm build of 4c5a4322 -- every sheet the fit step touched, and the
# em is the log's own figure, computed from the full-precision extent rather
# than the 2-decimal millimetres beside it:
#
#   2.0626 em  10.91 mm @ 15 pt  clamp_screw, frame_side_screw,
#                                gooseneck_set_screw, slotted_screw,
#                                swing_stop_screw
#   2.0411 em  11.52 mm @ 16 pt  lag_screw
#   2.0053 em   8.49 mm @ 12 pt  hex_bolt
#   1.9885 em  10.52 mm @ 15 pt  bracket_screw, cone_lock_knob,
#                                cone_tip_pinch_screw, foot_screw,
#                                thumb_screw
#   1.9678 em   8.33 mm @ 12 pt  hanger_screw
#   1.9419 em  10.96 mm @ 16 pt  fillister_screw, harmonic_analyzer_assembly
#   1.9207 em   7.45 mm @ 11 pt  cone_pivot_screw, pen_set_screw
#   1.9120 em   8.77 mm @ 13 pt  cone_tip_adjuster
#
# This constant is a MODEL of one line, good to about +-0.001 em, and NOT
# the sample maximum: five sheets measure 2.0626 em, which is 0.0006 em
# ABOVE it. They pass because what the check enforces is the PRODUCT
# ONE_LINE_EXTENT_EM * (1 + ONE_LINE_EXTENT_TOLERANCE) = 2.1651 em, which
# clears the tallest measured line by 5.0%. Chasing the observed maximum
# with every build's readings is how 1.8 got here in the first place, so the
# rule is: the constant tracks the model, the tolerance owns the margin, and
# a reading above the constant is only news if it is above the product.
#
# The extent is NOT a function of the name. 'harmonic-analyzer assembly' and
# 'Brass Fillister Head Slotted Screw' are different strings of different
# lengths on different parts, and both measured 10.96 mm at 16 pt; while
# seven sheets carrying the SAME name ('Steel Narrow Fillister Head Slotted
# Screw') split three ways at the same 15 pt -- 10.52 mm on bracket_screw,
# cone_tip_pinch_screw and foot_screw, 10.91 mm on clamp_screw,
# frame_side_screw, slotted_screw and swing_stop_screw. What varies is the
# SHEET; what the extent depends on is the size and the template. That is
# also why shrinking the font can never
# rescue a refused sheet: the ratio this bound is compared against is
# scale-invariant, so the fit step's step-down loop moves the width and
# leaves the height ratio exactly where it was.
#
# Eight discrete values over 18 sheets, each shared to the last digit by
# every sheet that reports it and spanning 7.9% -- a quantised distribution,
# not a continuous spread. The quantising variable is not identified, and two
# candidates are eliminated: the repo ships exactly two sheet formats
# (cad/templates/harmonic-analyzer-{landscape,portrait}.DRWDOT) and all 18
# sheets use the landscape one, so it is not a template revision; and
# GetExtent is proven to report unscaled sheet millimetres
# (_purchased_fastener_drawing checks its own notes' extents against
# absolute cell geometry on these very sheets), so it is not sheet scale.
#
# What the same build DID pin down is the box's top edge, and it splits the
# 18 sheets into two families: extent top = bottom + height is invariant at
# 42.80 mm on 11 sheets and at 43.28..43.29 mm on 7, across every size from
# 11 to 16 pt. So the note is top-anchored and the box grows downward as the
# size rises, and the two families differ by a flat 0.49 mm of sheet space
# (not a fixed number of ems), which is also the whole of their extent-em
# difference. Whatever moves it, it moves the BOX, and the reserve below the
# ink is derived from the family that leaves the ink lowest.
#
# The sample is COMPLETE for the sheets that reached the check, not a
# survivors' sample. The bound it replaces refused anything above
# 1.8 x 1.05 = 1.89 em, and the smallest value here is 1.9120 em, so no
# sheet could have reached the height check and passed: every one was
# refused and printed its measurement. There is no taller sheet hiding
# behind a silent pass.
#
# What the logging buys is the NEXT build, not this sample: EVERY sheet now
# reports its extent, its ratio and its ink bottom with its layout (see
# _drawing_common.fit_title_block_part_name), fitted or not, pass or
# refusal. The first version of that logging fired only on the fitted path,
# which meant the only 18 sheets that could report were the 18 that failed
# -- an instrument that cannot answer "is this value normal?", which is the
# only question it exists to answer. The 77 untouched sheets are the control
# population and they now report too.
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
# sheet (2.0626) to the extrapolated floor of the defect band (2.3049),
# 11.7% wide. At this tolerance the refusal starts at 2.1651 em: 5.0% above
# the tallest legitimate sheet, 6.5% below the floor.
#
# The bounds on editing it, since all three were once stated wrongly here:
#
# * 0.1178 is where a defective sheet gets through (2.3049/2.062 - 1). Not
#   0.057: that is sqrt(2.3049/2.0626) - 1, the geometric midpoint of the
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
# which has to land in (2.0626, 2.3049]. They do not pin either factor: all
# eight readings pass at a constant of 2.0 as well (2.0626/2.0 = 1.031 <
# 1.05). Simplifying the constant and staying green is therefore possible --
# and the reason not to is that the constant is a MODEL with a provenance
# and the tolerance is a decision about how much of the corridor to spend.
ONE_LINE_EXTENT_TOLERANCE = 0.05

# How much of the extent box sits BELOW the ink, in ems of the size the note
# reports back. The cell-rule check needs this because GetExtent's bottom
# edge is not where the text is: it is one line pitch of empty reserve
# lower, so comparing the box bottom against the cell's lower rule compares
# padding against ruled geometry.
#
# MEASURED, at the one size where the ink's position is known independently.
# fillister_screw and harmonic_analyzer_assembly fit at 16 pt, which is the
# template's own authored size: the applier widens their LineLength and
# writes the same 16 pt back, so their ink is in exactly the place the v36
# renders measured (baseline 38.3648 mm) and in exactly the place the 77
# untouched sheets print it. Their extent bottom came back at 31.84 mm, so
#
#   reserve = (38.3648 - 31.84) / (16 * MM_PER_POINT) - DESCENDER_EM
#           = 1.1560 - 0.307 = 0.8490 em
#
# The second top family (lag_screw, extent bottom 31.77 mm at 16 pt) gives
# 0.8614 em by the same arithmetic. This constant takes the SMALLER of the
# two, which is the conservative direction: it predicts the ink lower than
# it is, so the check refuses sooner rather than later.
#
# Corroborated independently of both: the total padding the box carries is
# then 1.025 em of ink inside a 1.9419 em box, i.e. 0.917 em of empty space,
# which is one LINE_SPACING_EM to within 8% -- and LINE_SPACING_EM was
# measured from two-line baselines on the v36 renders, with no reference to
# any extent. The reserve is one line's worth of room for the line that is
# not there. cone_tip_adjuster's wrapped extent agrees: 17.54 mm for two
# lines at 13 pt requested implies a rendered size 1.296x the request, which
# lands inside the 1.2053..1.3261 system-units inflation measured on other
# sheets in that same build.
#
# Where 38.3648 mm comes from, since this whole check now rests on it: the
# release PDFs themselves, and it is RE-DERIVABLE in a dozen lines of
# Python with no seat and no SolidWorks. Each sheet in cad/out/pdf is a
# native vector PDF; inflate its content stream, tokenise the text objects,
# and the PART value is the 16 pt run whose text matrix starts at
# x = 312.442 mm. Its Tm f component IS the baseline. Re-derived here over
# all 96: 53 sheets carry that run and every one of them reports
# 38.3648 mm, identical to four decimals -- the template authors it, so it
# does not vary by sheet or by name.
#
# The same extraction re-derives LINE_SPACING_EM and finds the defect this
# module exists for: 18 of the 96 print a SECOND 16 pt run at 32.7204 mm
# (exactly one em lower, which is the 1.0 above) and three of those print a
# third at 27.0759 mm. Eighteen wrapped sheets in the renders, eighteen
# sheets the fit step touches -- the two populations are the same one.
#
# NOT derived from the sheets it exonerates. The 18 refusals were at 11..16
# pt and the arithmetic above uses only the two 16 pt sheets, whose applied
# size equals the authored size -- the single case where the ink's position
# is a v36 measurement rather than an inference from this box.
#
# PROPORTIONAL TO THE EM, which is a model and not a second measurement:
# there is no sheet at a second size where the ink is independently known,
# because 16 pt IS the template's authored size and every other fitted size
# is one the applier chose. What backs it:
#
# * The box as a whole scales with the em. Regressing the 18 measured
#   heights on em within a top family gives extent = 2.023*em - 0.36 mm
#   (family A, residual sigma 0.16 mm), and the fixed term's standard error
#   is 0.53 mm -- so any size-independent component of the box is zero to
#   within about half a millimetre. A reserve fixed at its 16 pt value
#   instead would be 1.5 mm out at 11 pt, three times that bound.
# * Cap height and descender are font metrics, proportional by definition,
#   and this reserve is one LINE_SPACING_EM of the same kind of space.
# * Below 16 pt the proportional reserve is the SMALLER of the two
#   candidate models in millimetres (3.29 mm at 11 pt against a fixed
#   4.79 mm), so it is also the conservative one -- and the fit step never
#   goes ABOVE 16 pt, since it only ever steps DOWN from the authored size.
#   The proportional model is therefore the lower bound at every size the
#   applier can produce, and exact at the size it was measured at.
# * It cannot change a verdict on the measured population either way: at
#   11..15 pt the tightest margin against the enforced threshold is 1.39 mm,
#   which no 0.53 mm uncertainty crosses, and at 16 pt the two models are
#   the same number.
#
# So: measured at 16 pt, assumed proportional, unverified below it. If a
# future build ever wants that verified, the discriminating sheet is one
# whose ink position is known independently at a second size -- which today
# means a template authored at something other than 16 pt.
EXTENT_BOTTOM_RESERVE_EM = 0.848

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
