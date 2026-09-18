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

from types import SimpleNamespace

import pytest

import _drawing_common as drawing_common
from _common import part_properties
from _drawing_registry import DRAWINGS, DRAWING_TEMPLATES, DrawingLayout
from _title_block_text import (
    DESCENDER_EM,
    LINE_SPACING_EM,
    MM_PER_POINT,
    ONE_LINE_EXTENT_EM,
    ONE_LINE_EXTENT_TOLERANCE,
    TITLE_BLOCK_TYPEFACE,
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
    which is what makes the applier leave the note's ink alone -- no format
    override, byte-identical output. This is the regression guard for the
    release: 78 of the fleet's 96 sheets take this path.
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


# --- the applier, with a faked seat ------------------------------------------
#
# ``fit_title_block_part_name`` is the half of the rule that touches COM. Its
# guards are what stand between a mis-measured width model and a shipped
# title block, so they are exercised here against a fake note rather than
# only on a seat.


# Measured on the farm, and the reason this fake renders instead of returning
# a canned box: SolidWorks' system-units height (``ITextFormat.CharHeight``,
# metres) is the CHARACTER height, not the em. Four names at 12, 15 and 16 pt
# across three workers came back with extents 1.3806-1.3813x the single-line
# bound after the applier wrote the em size into it; 1/1.38095 = 0.7241.
SW_CHARACTER_HEIGHT_EM = 0.7241


def _one_line_extent(point_size: float, *, width_mm: float = 60.0):
    """``INote::GetExtent`` (metres) for one line drawn in ``LANDSCAPE``.

    The box is ``ONE_LINE_EXTENT_EM`` tall, which is what the farm measured
    for a correctly-sized note, and it is anchored on the descender because
    that is the edge the cell-rule check reads; SolidWorks' padding sits
    above it.
    """
    size_mm = point_size * MM_PER_POINT
    bottom_mm = LANDSCAPE.baseline_mm - DESCENDER_EM * size_mm
    return (
        LANDSCAPE.text_left_mm / 1000.0,
        bottom_mm / 1000.0,
        0.0,
        (LANDSCAPE.text_left_mm + width_mm) / 1000.0,
        (bottom_mm + ONE_LINE_EXTENT_EM * size_mm) / 1000.0,
        0.0,
    )


# Exactly the names in the generated ITextFormat wrapper's ``_prop_map_put_``
# (typelib 34.0). Anything else is a method or a read-only member, and
# assigning to it raises AttributeError on a live seat.
_SETTABLE_TEXT_FORMAT_PROPERTIES = frozenset(
    {
        "BackWards",
        "Bold",
        "CharHeight",
        "CharHeightInPts",
        "CharSpacingFactor",
        "Escapement",
        "Italic",
        "LineLength",
        "LineSpacing",
        "ObliqueAngle",
        "Strikeout",
        "TypeFaceName",
        "Underline",
        "UpsideDown",
        "Vertical",
        "WidthFactor",
    }
)


class _FakeTextFormat:
    """The template's authored PART format, as ``ITextFormat`` reports it.

    Every property the width model depends on is separately settable, because
    SolidWorks carries them separately: a note can be bold Century Gothic, or
    Century Gothic at 18 pt, with ``TypeFaceName`` unchanged either way.
    ``height_in_points`` chooses which of the two height properties the
    template authored, since ``CharHeightInPts`` is stale when it did not.

    This fake deliberately reproduces three things about the GENERATED
    wrapper and about SolidWorks itself that a plain attribute bag does not,
    because the applier runs against those and all three hid a real defect:

    * ``IsHeightSpecifiedInPts`` is a METHOD (dispid 11, retval ``VT_BOOL``),
      absent from ``_prop_map_get_``. Read as an attribute it yields a bound
      method -- truthy forever -- so a fake exposing it as a ``bool`` lets a
      reader that never calls it pass every test and invert on the seat.
    * assignment is restricted to the wrapper's ``_prop_map_put_`` names;
      ``DispatchBaseClass.__setattr__`` raises ``AttributeError`` for anything
      else, so writing the read-only flag is an error, not a no-op.
    * the two height properties are NOT interchangeable and writing one
      decides which unit the note renders in. ``CharHeight`` is a CHARACTER
      height in metres, so a note switched to it renders an em of
      ``CharHeight / SW_CHARACTER_HEIGHT_EM``. An applier that wrote "the
      same height through both" therefore wrote two different heights and
      the taller one won -- which is what ``rendered_point_size`` exists to
      make visible offline.
    """

    def __init__(
        self,
        typeface: str = TITLE_BLOCK_TYPEFACE,
        *,
        bold: bool = False,
        italic: bool = False,
        point_size: float = LANDSCAPE.nominal_point_size,
        height_in_points: bool = True,
    ):
        self.__dict__["_height_in_points"] = height_in_points
        self.TypeFaceName = typeface
        self.Bold = bold
        self.Italic = italic
        self.LineLength = 0.0
        # Authored state, not a write: the template is self-consistent, so
        # both properties describe the same rendered size. These go straight
        # into __dict__ so that the authority rule below only ever sees what
        # the APPLIER does.
        self.__dict__["CharHeightInPts"] = point_size if height_in_points else 0
        self.__dict__["CharHeight"] = (
            point_size * MM_PER_POINT * SW_CHARACTER_HEIGHT_EM / 1000.0
        )

    def __setattr__(self, name: str, value: object) -> None:
        if name not in _SETTABLE_TEXT_FORMAT_PROPERTIES:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )
        if name in ("CharHeight", "CharHeightInPts"):
            # Last height write wins the unit, which is how the farm's
            # points-authored notes ended up rendering from CharHeight.
            self.__dict__["_height_in_points"] = name == "CharHeightInPts"
        self.__dict__[name] = value

    def IsHeightSpecifiedInPts(self) -> bool:
        return self.__dict__["_height_in_points"]

    @property
    def rendered_point_size(self) -> float:
        """The em the note actually prints at, in points."""
        if self.__dict__["_height_in_points"]:
            return float(self.__dict__["CharHeightInPts"])
        char_height_pts = self.__dict__["CharHeight"] * 1000.0 / MM_PER_POINT
        return char_height_pts / SW_CHARACTER_HEIGHT_EM


class _FakeAnnotation:
    def __init__(self, text_format: _FakeTextFormat):
        # swAnnotationOwner_e.swAnnotationOwner_DrawingTemplate
        self.OwnerType = 2
        self.text_format = text_format
        self.writes = 0

    def GetTextFormat(self, _index):
        return self.text_format

    def SetTextFormat(self, _index, _all_notes, text_format):
        self.writes += 1
        self.text_format = text_format
        return True


class _FakeNote:
    """A note whose extent is RENDERED from its format, not canned.

    An extent fixed at construction cannot catch a write that changes the
    rendered size, which is exactly the class of defect that reached the
    farm. Wrapping is not modelled -- the note always draws one line -- so a
    test that wants a wrapped extent assigns a tuple over ``GetExtent``, the
    way ``_get_attr_or_call`` accepts either.
    """

    def __init__(self, text: str, annotation: _FakeAnnotation, *, width_mm=60.0):
        self.text = text
        self.annotation = annotation
        self.width_mm = width_mm

    def GetExtent(self):
        return _one_line_extent(
            self.annotation.text_format.rendered_point_size, width_mm=self.width_mm
        )

    def GetText(self):
        return self.text

    def GetAnnotation(self):
        return self.annotation

    def GetNext(self):
        return None


class _FakeDrawingDoc:
    """Just enough ``IDrawingDoc`` to walk one sheet-format note.

    ``GetEditSheet`` is a METHOD on the generated wrapper -- dispid retval
    ``(11,0)`` ``VT_BOOL``, in neither prop map -- and it is the read-back
    that verifies ``EditTemplate``/``EditSheet``, both of which declare
    ``(24,0)`` ``VT_VOID`` and so report nothing themselves. Exposing it here
    as a plain attribute would let a bare read pass the suite while returning
    a permanently-truthy bound method on a seat, which is precisely how the
    ``IsHeightSpecifiedInPts`` defect survived review.
    """

    def __init__(self, note: _FakeNote):
        self.note = note
        self._edit_sheet = True
        self.edit_template_calls = 0

    def GetEditSheet(self) -> bool:
        return self._edit_sheet

    def EditTemplate(self) -> None:
        self.edit_template_calls += 1
        self._edit_sheet = False

    def EditSheet(self) -> None:
        self._edit_sheet = True

    def GetFirstView(self):
        # Template notes are only reachable in edit-sheet-format mode.
        note = None if self._edit_sheet else self.note
        return SimpleNamespace(GetFirstNote2=lambda: note)


class _FakeAdapter:
    def __init__(self):
        self.currentModel = SimpleNamespace(GraphicsRedraw2=lambda: None)

    @staticmethod
    def _attempt(call, default=None):
        try:
            return call()
        except Exception:
            return default

    @staticmethod
    def _get_attr_or_call(obj, name):
        value = getattr(obj, name)
        return value() if callable(value) else value


@pytest.fixture
def seat(monkeypatch):
    """A fake seat holding one PART note, plus the early-bind casts removed."""
    monkeypatch.setattr(drawing_common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        drawing_common._sw_type_info,
        "early_bound_or_flag",
        lambda value, *_args, **_kwargs: value,
    )

    def build(name: str, **format_kwargs):
        annotation = _FakeAnnotation(_FakeTextFormat(**format_kwargs))
        return _FakeDrawingDoc(_FakeNote(name, annotation)), annotation

    return build


@pytest.mark.parametrize(
    "name,adjust",
    [("channel-spring-installed", False), ("harmonic-analyzer assembly", True)],
    ids=["untouched-sheet", "fitted-sheet"],
)
@pytest.mark.parametrize(
    "authored,match",
    [
        ({"typeface": "Arial"}, "prints in 'Arial'"),
        ({"bold": True}, "Bold=True"),
        ({"italic": True}, "Italic=True"),
        ({"point_size": 18}, r"prints at 18\.00 pt"),
    ],
    ids=["family", "weight", "style", "size"],
)
def test_a_reauthored_template_fails_every_sheet(seat, name, adjust, authored, match):
    """A note that is not the FACE and SIZE the model measured fails the sheet.

    The width model is one face's own glyph table read at one size, so
    ``adjust=False`` -- "this name renders unwrapped at 16 pt" -- is a verdict
    of that model, never an observation. Those are precisely the sheets that
    would start wrapping under a re-authored template, with no fit applied and
    no extent check afterwards to catch it.

    Family is not enough, because ``ITextFormat`` carries weight, style and
    size independently of ``TypeFaceName``. Measured against the Windows
    Century Gothic faces: bold differs from regular on 79 of the table's 81
    glyphs and pushes the line PROVEN to render unwrapped (68.834 mm) to
    69.765 mm, past the bracket; 18 pt pushes the widest untouched fleet name
    from 64.82 mm to 72.92 mm, likewise past it. Italic is metrically
    identical to regular so it cannot move a wrap, but it slants ink past the
    advance box the containment arithmetic uses, and the model's provenance is
    the upright face.
    """
    assert fit_part_name(name, LANDSCAPE).adjust is adjust
    ddoc, annotation = seat(name, **authored)

    with pytest.raises(RuntimeError, match=match):
        drawing_common.fit_title_block_part_name(
            _FakeAdapter(),
            ddoc,
            layout=DrawingLayout.LANDSCAPE,
            sheet_name="Sheet1",
            expected_name=name,
        )

    # Nothing is written on the way to the refusal, on either sheet class.
    assert annotation.writes == 0
    assert ddoc.GetEditSheet() is True


@pytest.mark.parametrize(
    "name,adjust",
    [("channel-spring-installed", False), ("harmonic-analyzer assembly", True)],
    ids=["untouched-sheet", "fitted-sheet"],
)
def test_a_millimetre_authored_note_is_refused_not_converted(seat, name, adjust):
    """A note that prints from ``CharHeight`` is refused, on either class.

    ``CharHeight`` is a CHARACTER height in metres, so it is not the em the
    width model is keyed to; the farm measured the difference at a factor of
    1.381. The applier used to convert with the em factor and write both
    properties, which inflated every fitted note by that factor. There is no
    measured font constant to convert with, so the rule now names the gap
    instead of guessing across it -- on the untouched sheets too, because
    ``adjust=False`` is a verdict of the same width model.
    """
    assert fit_part_name(name, LANDSCAPE).adjust is adjust
    ddoc, annotation = seat(name, height_in_points=False)
    assert annotation.text_format.CharHeightInPts == 0

    with pytest.raises(RuntimeError, match="authors its height in system units"):
        drawing_common.fit_title_block_part_name(
            _FakeAdapter(),
            ddoc,
            layout=DrawingLayout.LANDSCAPE,
            sheet_name="Sheet1",
            expected_name=name,
        )

    assert annotation.writes == 0
    assert ddoc.GetEditSheet() is True


def test_an_untouched_sheets_ink_is_never_written(seat):
    """Inspecting the 78 good sheets must not re-ink any of them."""
    name = "channel-spring-installed"
    ddoc, annotation = seat(name)
    before = vars(annotation.text_format).copy()

    fit = drawing_common.fit_title_block_part_name(
        _FakeAdapter(),
        ddoc,
        layout=DrawingLayout.LANDSCAPE,
        sheet_name="Sheet1",
        expected_name=name,
    )

    assert fit.adjust is False
    assert annotation.writes == 0
    assert vars(annotation.text_format) == before
    assert ddoc.GetEditSheet() is True


def test_a_fitted_sheet_gets_the_planned_size_and_line_length(seat):
    """The fitted sheets get the plan's size through ONE height property.

    The note must come out of the fit still declaring points, and with its
    system-units height untouched: two properties nominally describing the
    same height in different units is what shipped a 1.381x inflation, and
    the one the applier does not own is the one whose unit it got wrong.
    """
    name = "harmonic-analyzer assembly"
    ddoc, annotation = seat(name)
    authored_char_height = annotation.text_format.CharHeight

    fit = drawing_common.fit_title_block_part_name(
        _FakeAdapter(),
        ddoc,
        layout=DrawingLayout.LANDSCAPE,
        sheet_name="Sheet1",
        expected_name=name,
    )

    assert fit.adjust is True
    assert annotation.writes == 1
    assert annotation.text_format.CharHeightInPts == fit.point_size
    assert annotation.text_format.IsHeightSpecifiedInPts() is True
    assert annotation.text_format.CharHeight == authored_char_height
    assert annotation.text_format.LineLength * 1000.0 == pytest.approx(
        fit.line_length_mm
    )
    assert ddoc.GetEditSheet() is True


def test_a_fitted_note_renders_no_taller_than_one_line(seat):
    """The RATIO, which is what the farm actually measured going wrong.

    Pinning "this name fits" passes again the day a unit factor comes back
    on a shorter name. What failed on the farm was a constant multiplicative
    inflation -- extent 1.3806-1.3813x the single-line bound across four
    names, three sizes and three workers -- so the assertion is on
    extent/bound, at the size the note reports back rather than the one that
    was requested.
    """
    name = "harmonic-analyzer assembly"
    ddoc, annotation = seat(name)

    fit = drawing_common.fit_title_block_part_name(
        _FakeAdapter(),
        ddoc,
        layout=DrawingLayout.LANDSCAPE,
        sheet_name="Sheet1",
        expected_name=name,
    )

    assert fit.adjust is True
    applied_pts = annotation.text_format.rendered_point_size
    assert applied_pts == pytest.approx(fit.point_size)
    _x0, y0, _z0, _x1, y1, _z1 = ddoc.note.GetExtent()
    height_mm = abs(y1 - y0) * 1000.0
    one_line_mm = ONE_LINE_EXTENT_EM * applied_pts * MM_PER_POINT
    assert height_mm / one_line_mm <= 1.0 + ONE_LINE_EXTENT_TOLERANCE


def test_writing_the_system_units_height_inflates_the_note(seat):
    """The fake can SEE the defect the applier used to ship.

    Without this, the ratio assertion above is unfalsifiable: a fake whose
    extent ignores the format would pass it whatever the applier wrote. This
    reproduces the removed write -- ``CharHeight = em_mm / 1000`` after the
    points write -- and pins the inflation at the farm's measured 1.381, so
    reinstating that line in ``fit_title_block_part_name`` makes the sheet
    fail here instead of on a worker.
    """
    name = "harmonic-analyzer assembly"
    ddoc, annotation = seat(name)
    fit = fit_part_name(name, LANDSCAPE)
    text_format = annotation.text_format

    text_format.CharHeightInPts = int(fit.point_size)
    text_format.CharHeight = fit.point_size * MM_PER_POINT / 1000.0

    assert text_format.IsHeightSpecifiedInPts() is False
    assert text_format.rendered_point_size == pytest.approx(
        fit.point_size / SW_CHARACTER_HEIGHT_EM
    )
    _x0, y0, _z0, _x1, y1, _z1 = ddoc.note.GetExtent()
    height_mm = abs(y1 - y0) * 1000.0
    one_line_mm = ONE_LINE_EXTENT_EM * fit.point_size * MM_PER_POINT
    assert height_mm / one_line_mm == pytest.approx(1.381, abs=0.001)


def test_a_wrapped_note_fails_the_sheet_it_was_meant_to_fix(seat):
    """If ``LineLength`` is ignored, the two-line extent must fail the build.

    The refusal has to say what was MEASURED, not what it infers. An earlier
    version reported "renders on more than one line" for every over-tall
    extent, and that wording sent three agents after font ladders when the
    real cause was a unit factor on notes that never wrapped. A wrap here
    adds one em to a 1.8 em line, so the ratio it must report is 1.556, and
    the size it must report is the one read BACK off the note.
    """
    name = "harmonic-analyzer assembly"
    ddoc, _annotation = seat(name)
    point_size = fit_part_name(name, LANDSCAPE).point_size
    x0, y0, z0, x1, y1, z1 = _one_line_extent(point_size)
    # A second line drops one em BELOW the first, through the cell's rule.
    ddoc.note.GetExtent = (
        x0,
        y0 - LINE_SPACING_EM * point_size * MM_PER_POINT / 1000.0,
        z0,
        x1,
        y1,
        z1,
    )

    with pytest.raises(RuntimeError) as raised:
        drawing_common.fit_title_block_part_name(
            _FakeAdapter(),
            ddoc,
            layout=DrawingLayout.LANDSCAPE,
            sheet_name="Sheet1",
            expected_name=name,
        )

    message = str(raised.value)
    assert "renders 1.556x taller than one line" in message
    assert f"at the {point_size:g} pt the note reports back" in message
