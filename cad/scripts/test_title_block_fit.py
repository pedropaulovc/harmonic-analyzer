"""SolidWorks-free contract for the title-block PART-name fit.

The PART cell of the hand-made drawing templates prints the linked model's
document Title, and its authored text box is 37 mm narrower than the cell it
sits in, so a long name wrapped onto a second line that landed on the
``DWG. NO.`` caption (found on ``harmonic-analyzer-assembly``, DWG MHA-A08,
during the v36 release render inspection; 18 of the 96 released sheets did it).

These cases hold the fit rule to the whole fleet's real names without a COM
seat: the width model is checked against the wrap evidence measured off the
released renders, every printed name must land on one legible line inside its
own field, and every name that renders correctly today must come out of the
rule untouched.
"""

from __future__ import annotations

import pytest

from _common import part_properties
from _drawing_registry import DRAWINGS, DRAWING_TEMPLATES, DrawingLayout
from _title_block_text import (
    PartNameDoesNotFit,
    fit_is_contained,
    fit_part_name,
    fitted_text_box_mm,
    text_width_mm,
)


LANDSCAPE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE].part_name_field


def printed_part_name(spec) -> str:
    """The string this drawing's title block prints in its PART cell.

    Both sides of the ``$PRPSHEET`` link are offline: a part sheet prints its
    parts-registry title (falling back to the dashed stem), and an assembly
    sheet prints the ``"<stem> assembly"`` its build script stamps as the
    document Title.
    """
    stem = spec.part.replace("_", "-")
    if spec.source_kind == "assembly":
        return f"{stem} assembly"
    return part_properties(stem)["Title"]


FLEET = tuple(
    (spec.artifact_stem, printed_part_name(spec), spec.layout) for spec in DRAWINGS
)


def test_width_model_reproduces_the_measured_wrap_bracket():
    """The glyph model must agree with what the released sheets actually did.

    These two lines bracket the template note's authored line length: the first
    is the widest line that rendered UNWRAPPED anywhere in the v36 release, the
    second the narrowest line that did NOT fit and pushed its remainder onto a
    second line. Any edit to the glyph table that moves a real name across that
    boundary breaks here.
    """
    widest_that_fit = text_width_mm("Brass Fillister Head Slotted", 16)
    narrowest_that_wrapped = text_width_mm("Steel Narrow Fillister Head", 16)
    assert widest_that_fit == pytest.approx(68.834, abs=0.01)
    assert narrowest_that_wrapped == pytest.approx(69.669, abs=0.01)
    assert widest_that_fit <= LANDSCAPE.proven_line_length_mm
    assert narrowest_that_wrapped > LANDSCAPE.proven_line_length_mm


@pytest.mark.parametrize("stem,name,layout", FLEET, ids=[row[0] for row in FLEET])
def test_every_printed_part_name_fits_one_legible_line(stem, name, layout):
    """No fleet name may need two lines, an illegible size, or extra space."""
    field = DRAWING_TEMPLATES[layout].part_name_field
    fit = fit_part_name(name, field)
    assert fit.point_size >= field.minimum_point_size, stem
    # A fitted line must stop short of the field, so SolidWorks' own wrap
    # arithmetic cannot land on the other side of the decision.
    slack = fit.line_length_mm - fit.width_mm
    assert slack >= (field.fit_margin_mm if fit.adjust else 0.0), (stem, slack)
    assert fit_is_contained(fit, field), (stem, fitted_text_box_mm(fit, field))
    # The defect was the second line crossing the cell's lower rule onto the
    # DWG. NO. caption, so the fitted line's own box must clear that rule.
    _left, bottom, _right, top = fitted_text_box_mm(fit, field)
    assert bottom > field.cell_bottom_mm, stem
    assert top < field.value_ceiling_mm(), stem


def test_the_reported_sheet_fits_at_the_templates_own_size():
    """MHA-A08's name needs the field's real width, not a smaller font.

    ``harmonic-analyzer assembly`` is 77.93 mm at the template's authored
    16 pt: wider than the note's 68.83 mm text box (hence the wrap) and well
    inside the 104.77 mm the cell actually offers. Telling the note its true
    width is the whole fix for this sheet -- the reported defect must not cost
    a font step-down.
    """
    fit = fit_part_name("harmonic-analyzer assembly", LANDSCAPE)
    assert fit.point_size == LANDSCAPE.nominal_point_size
    assert fit.adjust is True
    assert fit.width_mm == pytest.approx(77.93, abs=0.01)
    assert fit.width_mm <= LANDSCAPE.line_length_mm


def test_names_that_already_fit_are_left_untouched():
    """The sheets that render correctly must not be re-inked at all.

    A name inside the note's PROVEN authored width returns ``adjust=False``,
    which is what makes the applier skip ``EditTemplate`` entirely -- so those
    sheets' ink cannot change. This is the regression guard for the release:
    78 of the fleet's 96 sheets take this path.
    """
    touched = []
    for stem, name, layout in FLEET:
        field = DRAWING_TEMPLATES[layout].part_name_field
        fit = fit_part_name(name, field)
        if text_width_mm(name, field.nominal_point_size) <= field.proven_line_length_mm:
            assert fit.adjust is False, stem
            assert fit.point_size == field.nominal_point_size, stem
        else:
            assert fit.adjust is True, stem
            touched.append(stem)
    # Both branches must be live, or the case above proves nothing.
    assert touched
    assert len(touched) < len(FLEET)


def test_widest_fleet_name_steps_down_but_stays_legible():
    """The longest name in the fleet still prints above the ASME minimum."""
    fit = fit_part_name(
        "Stainless Steel Flared-Collar Knurled-Head Thumb Screw", LANDSCAPE
    )
    assert fit.point_size == 11
    assert fit.width_mm <= LANDSCAPE.line_length_mm
    assert fit.point_size * (25.4 / 72.0) >= 3.0


def test_an_unfittable_name_fails_the_build():
    """A name that cannot be printed legibly raises instead of overflowing."""
    with pytest.raises(PartNameDoesNotFit):
        fit_part_name("W" * 120, LANDSCAPE)
