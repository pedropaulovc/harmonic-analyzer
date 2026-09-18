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
    EXTENT_BOTTOM_RESERVE_EM,
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


# Every SHEET the fleet prints, not every drawing: a spec may also be rendered
# on a second template through ``additional_layouts``, and that sheet gets its
# own title block with its own field. Deriving the rows from ``spec.layout``
# alone is how the portrait template came to be described as carrying two
# names when it carries three -- ``frame-assembly`` reaches it only through
# ``additional_layouts``.
FLEET_SHEETS = tuple(
    (spec.artifact_stem, printed_part_name(spec), layout, source)
    for spec in DRAWINGS
    for layout, source in (
        (spec.layout, "layout"),
        *((extra, "additional_layouts") for extra in spec.additional_layouts),
    )
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


def test_no_portrait_sheet_needs_its_name_fitted():
    """The portrait template's names must all print at the authored size.

    ONE_LINE_EXTENT_EM is measured on landscape sheets only, and it can be,
    because no portrait name reaches the height check: the check runs behind
    ``fit.adjust``. That is an OBSERVATION about today's names, not something
    the code enforces -- ``fit_title_block_part_name`` accepts either layout
    and the portrait template has a PART field of its own -- so it is pinned
    here. This is contract hardening, not a bug fix: a portrait name that
    grew past its field would be refused loudly, with its extent logged,
    rather than shipping a wrapped sheet. What it buys is that the refusal
    would be a NEW measurement nobody has, so the constant's provenance has
    to be revisited rather than the tolerance widened.

    The rows come from FLEET_SHEETS, so ``additional_layouts`` counts: three
    portrait sheets exist, and the third is reachable no other way.
    """
    field = DRAWING_TEMPLATES[DrawingLayout.PORTRAIT].part_name_field
    portrait = [row for row in FLEET_SHEETS if row[2] is DrawingLayout.PORTRAIT]
    # A scan that matched nothing would pass forever; both derivations of a
    # portrait sheet have to be represented.
    assert {source for _stem, _name, _layout, source in portrait} == {
        "layout",
        "additional_layouts",
    }

    for stem, name, _layout, _source in portrait:
        fit = fit_part_name(name, field)
        assert fit.adjust is False, (stem, name, fit.point_size)
        assert fit.point_size == field.nominal_point_size, stem
        assert text_width_mm(name, field.nominal_point_size) <= field.proven_line_length_mm, (
            stem,
            text_width_mm(name, field.nominal_point_size),
        )


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
# metres) is the CHARACTER height, not the em. The same sheet measured twice
# -- slotted_screw's 15 pt note measured 13.15 mm with the em written into
# CharHeight, 10.91 mm without it -- puts the inflation at 1.2053, so the
# fraction the renderer treats as a character height is 1/1.2053 = 0.8297.
#
# That factor is per-SHEET, not global: the four inflated readings divide by
# their own clean readings to 1.2053, 1.2629, 1.2801 and 1.3261. The fake
# models the SMALLEST, which is the least favourable choice for a test that
# wants to see the inflation -- a fake built on 1.3261 would pass a guard
# that 1.2053 slips past.
#
# The 0.7241 this fake used to carry was 1/1.381, and 1.381 was the inflated
# extent divided by the OLD one-line constant of 1.8 -- which was itself
# derived from 1.381. Both numbers came out of the same circle.
SW_CHARACTER_HEIGHT_EM = 0.8297

# Every one-line extent the 4c5a4322 farm build measured, as
# ``(point_size, extent_mm, extent_bottom_mm, name, sheets)``. These are the
# raw readings from the 18 sheets whose fitted notes reached the checks,
# every one of them refused; ``em = extent_mm / (pt * MM_PER_POINT)`` runs
# 1.9123..2.0617 over this table, and 1.9120..2.0626 in the log's own
# figures, which divide the unrounded extent rather than these two-decimal
# millimetres. The readings are a property of the size and the TEMPLATE, not
# of the name -- 'harmonic-analyzer assembly' and 'Brass Fillister Head
# Slotted Screw' both measured 10.96 mm at 16 pt, while the same name on
# seven sheets split into 10.52 and 10.91 mm at 15 pt.
#
# ``name`` is one real sheet's PART name for that reading, and it is load
# bearing: the fit model has to choose that reading's point size for it, so
# the fake reproduces the farm's box at the farm's size instead of replaying
# a reading at some other size where the cell rule would mean something else.
#
# ``extent_bottom_mm`` is the reading that matters for the cell rule, and
# every one of the 18 is BELOW the cell's 35.88 mm lower rule: that is the
# refusal being fixed, and the table is the evidence it was not one sheet.
# Adding the height gives a box TOP that is invariant per family -- 42.80 mm
# on 11 sheets and 43.28..43.29 on 7, at every size from 11 to 16 pt -- which
# is how the anchor is known to be at the top and the reserve underneath.
#
# The heights are written here as MILLIMETRES, deliberately. The fake below
# renders from these, not from ``ONE_LINE_EXTENT_EM``, so a change to the
# constant cannot move both sides of an assertion at once: reverting the
# model to 1.8 reds these tests instead of quietly re-agreeing with itself.
FARM_ONE_LINE_EXTENTS_MM = (
    (
        15,
        10.91,
        32.37,
        "Steel Narrow Fillister Head Slotted Screw",
        "clamp_screw, frame_side_screw, gooseneck_set_screw, slotted_screw, swing_stop_screw",
    ),
    (16, 11.52, 31.77, "Rocker-Support Hold-Down Screw", "lag_screw"),
    (12, 8.49, 34.80, "Medium-Strength Grade 5 Steel Hex Head Screw", "hex_bolt"),
    (
        15,
        10.52,
        32.28,
        "Steel Raised Knurled-Head Thumb Screw",
        "bracket_screw, cone_lock_knob, cone_tip_pinch_screw, foot_screw, thumb_screw",
    ),
    (12, 8.33, 34.47, "Low-Strength Zinc-Plated Steel Hex Head Screw", "hanger_screw"),
    (
        16,
        10.96,
        31.84,
        "harmonic-analyzer assembly",
        "fillister_screw, harmonic_analyzer_assembly",
    ),
    (
        11,
        7.45,
        35.35,
        "Slotted 18-8 Stainless Steel Precision Shoulder Screw",
        "cone_pivot_screw, pen_set_screw",
    ),
    (13, 8.77, 34.04, "18-8 Stainless Steel Slotted Cup-Tip Set Screw", "cone_tip_adjuster"),
)

# The tallest of them, in em: the envelope ``ONE_LINE_EXTENT_EM`` has to
# clear, and therefore the worst legitimate case to render a fake note at.
FARM_TALLEST_ONE_LINE_EM = max(
    mm / (pt * MM_PER_POINT) for pt, mm, _bottom, _name, _sheets in FARM_ONE_LINE_EXTENTS_MM
)

# The lowest box TOP the build measured. The top is the anchor, so this is
# the reading that puts a note's ink closest to the cell's lower rule.
FARM_LOWEST_EXTENT_TOP_MM = min(
    bottom + mm for _pt, mm, bottom, _name, _sheets in FARM_ONE_LINE_EXTENTS_MM
)


def _one_line_extent(
    point_size: float,
    *,
    width_mm: float = 60.0,
    extent_em: float = FARM_TALLEST_ONE_LINE_EM,
    top_mm: float = FARM_LOWEST_EXTENT_TOP_MM,
):
    """``INote::GetExtent`` (metres) for one line drawn in ``LANDSCAPE``.

    Anchored at the TOP, because that is what the farm measured: the box top
    is invariant per family across 11..16 pt while the bottom descends with
    the size, so the box grows DOWNWARD and its lower edge is padding --
    ``EXTENT_BOTTOM_RESERVE_EM`` of empty reserve below the descender, room
    for a line that is not there. A fake that anchored the box on the
    descender instead (as this one once did) puts the ink and the reserve in
    the wrong order, and then every sheet the farm refused looks fine
    offline, which is exactly how the refusal shipped.

    The defaults are the worst legitimate case rather than a comfortable
    one: the TALLEST one line measured, hung from the LOWEST box top
    measured. Both are real readings, from different sheets -- no sheet is
    both -- so the default is a sheet slightly worse than any that exists.
    """
    size_mm = point_size * MM_PER_POINT
    top = top_mm / 1000.0
    return (
        LANDSCAPE.text_left_mm / 1000.0,
        (top_mm - extent_em * size_mm) / 1000.0,
        0.0,
        (LANDSCAPE.text_left_mm + width_mm) / 1000.0,
        top,
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

    This fake deliberately reproduces four things about the GENERATED
    wrapper and about SolidWorks itself that a plain attribute bag does not,
    because the applier runs against those and the first three hid a real
    defect:

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
    * the size the format REPORTS BACK and the size the note renders at are
      separate numbers (``readback_pts``). They are equal in every honest
      case, and the applier's readback tolerates them differing by up to
      0.49 pt, so which of the two the extent is judged against is a real
      choice that only shows up in a test that can drive them apart.
    """

    def __init__(
        self,
        typeface: str = TITLE_BLOCK_TYPEFACE,
        *,
        bold: bool = False,
        italic: bool = False,
        point_size: float = LANDSCAPE.nominal_point_size,
        height_in_points: bool = True,
        readback_pts: float | None = None,
    ):
        self.__dict__["_height_in_points"] = height_in_points
        # What a re-read of the format REPORTS, when that is not the size the
        # note renders at. ``None`` is the honest format: it reports back what
        # was written. The applier's readback accepts up to 0.49 pt of
        # divergence (it compares ``round(applied_pts)``), so this is the
        # slack the code itself permits, not a COM artefact.
        self.__dict__["_readback_pts"] = readback_pts
        self.TypeFaceName = typeface
        self.Bold = bold
        self.Italic = italic
        self.LineLength = 0.0
        # Authored state, not a write: the template is self-consistent, so
        # both properties describe the same rendered size. These go straight
        # into __dict__ so that the authority rule below only ever sees what
        # the APPLIER does.
        self.__dict__["_rendered_pts"] = float(point_size)
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
        if name == "CharHeightInPts":
            # The ink follows the write; the PROPERTY may report something
            # else. Keeping the two apart is what makes the applier's choice
            # of denominator observable offline.
            self.__dict__["_rendered_pts"] = float(value)
            if self.__dict__["_readback_pts"] is not None:
                value = self.__dict__["_readback_pts"]
        self.__dict__[name] = value

    def IsHeightSpecifiedInPts(self) -> bool:
        return self.__dict__["_height_in_points"]

    @property
    def rendered_point_size(self) -> float:
        """The em the note actually prints at, in points."""
        if self.__dict__["_height_in_points"]:
            return float(self.__dict__["_rendered_pts"])
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

    def __init__(
        self,
        text: str,
        annotation: _FakeAnnotation,
        *,
        width_mm=60.0,
        extent_em: float = FARM_TALLEST_ONE_LINE_EM,
        top_mm: float = FARM_LOWEST_EXTENT_TOP_MM,
    ):
        self.text = text
        self.annotation = annotation
        self.width_mm = width_mm
        # Which sheet of the measured family this note renders like. Defaults
        # to the tallest one line the farm reported hung from the lowest box
        # top it reported, so every test that does not care runs against a
        # case slightly worse than the worst real sheet.
        self.extent_em = extent_em
        self.top_mm = top_mm

    def GetExtent(self):
        return _one_line_extent(
            self.annotation.text_format.rendered_point_size,
            width_mm=self.width_mm,
            extent_em=self.extent_em,
            top_mm=self.top_mm,
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

    def build(
        name: str,
        *,
        extent_em: float = FARM_TALLEST_ONE_LINE_EM,
        top_mm: float = FARM_LOWEST_EXTENT_TOP_MM,
        **format_kwargs,
    ):
        annotation = _FakeAnnotation(_FakeTextFormat(**format_kwargs))
        note = _FakeNote(name, annotation, extent_em=extent_em, top_mm=top_mm)
        return _FakeDrawingDoc(note), annotation

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
    width model is keyed to; the same sheet measured 13.15 mm with the em
    written into it and 10.91 mm without, a factor of 1.2053. The applier
    used to convert with the em factor and write both properties, which
    inflated every fitted note by that factor. There is no
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
    same height in different units is what shipped a 1.2053x inflation, and
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
    on a shorter name. What failed on the farm was a multiplicative
    inflation -- extents of 2.4850-2.6362 em across four names, three sizes
    and three workers, 1.21x to 1.33x the same sheets without the write --
    so the assertion is on extent/bound, at the size the note reports back
    rather than the one that was requested.

    The note renders at the TALLEST one line the farm measured (2.0617 em as
    this file's rounded millimetres divide out, 2.0626 in the log's own
    figure), so this passes only while the model clears every real sheet:
    against the 1.8 em the constant used to carry, this reads 1.145x and
    reds.
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


@pytest.mark.parametrize(
    "point_size,extent_mm,bottom_mm,name,sheets",
    FARM_ONE_LINE_EXTENTS_MM,
    ids=[f"{mm:g}mm@{pt}pt" for pt, mm, _b, _n, _s in FARM_ONE_LINE_EXTENTS_MM],
)
def test_the_sheets_the_farm_refused_are_all_accepted(
    seat, point_size, extent_mm, bottom_mm, name, sheets
):
    """Every real sheet must PASS -- this is the defect being fixed.

    All 18 sheets whose fitted notes reached these checks in 4c5a4322 were
    refused, by both of them in turn:

    * the height bound (1.8 em) sat below the quantity it bounds, because a
      correct one line measures 1.9120..2.0626 em -- the box carries a full
      line pitch of empty reserve BELOW the ink;
    * and then the cell rule compared that box's bottom edge, which is the
      bottom of the reserve, against ruled geometry the INK has to clear.
      Every bottom in this table is below the 35.88 mm rule, and every one
      of those sheets is correct.

    Each row is replayed as the farm measured it: the row's own name, so the
    fit model picks the row's own point size, and the row's own box, so the
    reserve is doing real work rather than arithmetic on a synthetic note.
    """
    assert sheets
    fit_plan = fit_part_name(name, LANDSCAPE)
    assert fit_plan.point_size == point_size, "the fit model must pick the farm's size"
    measured_em = extent_mm / (point_size * MM_PER_POINT)
    assert bottom_mm < LANDSCAPE.cell_bottom_mm, "the box bottom IS below the rule"
    ddoc, annotation = seat(name, extent_em=measured_em, top_mm=bottom_mm + extent_mm)

    fit = drawing_common.fit_title_block_part_name(
        _FakeAdapter(),
        ddoc,
        layout=DrawingLayout.LANDSCAPE,
        sheet_name="Sheet1",
        expected_name=name,
    )

    assert fit.adjust is True
    assert annotation.text_format.rendered_point_size == pytest.approx(point_size)
    _x0, y0, _z0, _x1, y1, _z1 = ddoc.note.GetExtent()
    assert y0 * 1000.0 == pytest.approx(bottom_mm, abs=0.005)
    assert (y1 - y0) * 1000.0 == pytest.approx(extent_mm, abs=0.005)
    assert measured_em <= ONE_LINE_EXTENT_EM * (1.0 + ONE_LINE_EXTENT_TOLERANCE)


@pytest.mark.parametrize(
    "extent_em,provenance",
    (
        (2.4850, "slotted_screw 13.15 mm @ 15 pt, with the system-units write"),
        (2.6362, "swing_stop_screw 13.95 mm @ 15 pt, with the system-units write"),
        (3.8246, "cone_tip_adjuster 17.54 mm @ 13 pt, wrapped at the inflated size"),
        (2.3049, "the shortest sheet a unit-bugged write could produce: 1.9123 x 1.2053"),
    ),
    ids=("slotted_inflated", "swing_inflated", "cone_tip_wrapped", "band_floor"),
)
def test_the_extents_the_farm_measured_when_broken_are_still_refused(
    seat, extent_em, provenance
):
    """The other side of the band, from the same build's measurements.

    Raising the bound to clear a real one line must not raise it past a real
    defect, and the two populations are 11.7% apart, not an order of
    magnitude: the legitimate 1.9120..2.0626 em maps to 2.4850..2.6362 em
    under per-sheet inflations of 1.2053..1.3261, whose extrapolated floor
    (1.9123 x 1.2053) is 2.3049. The last case is that floor -- the hardest
    defect to catch -- and it is the one that fails first if anyone widens
    ONE_LINE_EXTENT_TOLERANCE for comfort: green at 0.10, red at 0.118.

    What these cases pin is the PRODUCT ONE_LINE_EXTENT_EM * (1 + tolerance),
    which has to land in (2.0626, 2.3049]. Neither factor is pinned alone --
    a constant of 2.0 passes every case here too.
    """
    assert provenance
    name = "harmonic-analyzer assembly"
    ddoc, _annotation = seat(name, extent_em=extent_em)

    with pytest.raises(RuntimeError) as raised:
        drawing_common.fit_title_block_part_name(
            _FakeAdapter(),
            ddoc,
            layout=DrawingLayout.LANDSCAPE,
            sheet_name="Sheet1",
            expected_name=name,
        )

    assert "taller than one line" in str(raised.value)


def test_every_sheet_records_what_it_measured(seat):
    """The measurement must reach the log on sheets that PASS, and on sheets
    that are never fitted at all.

    The 18-sheet sample behind ONE_LINE_EXTENT_EM is complete for the sheets
    that reached the check: the old bound refused everything above 1.89 em
    and the shortest reading is 1.9120, so nothing could have passed
    quietly. It was still the wrong sample, in two ways that this pins:

    * with the bound corrected every sheet passes, so a refusal-only record
      would print nothing ever again and the distribution would stop being
      re-measurable;
    * and it could only ever contain sheets the fit TOUCHED, which is 18 of
      95. The other 77 print the same note through the same template and
      are the control population for "is this reading normal?" -- the
      question the sample exists to answer and could not.

    The event carries the raw box edges as well as the derived ink bottom,
    so a reader can re-derive EXTENT_BOTTOM_RESERVE_EM from a log instead of
    taking the constant on trust.
    """
    recorded: list[tuple[str, dict]] = []

    def measure(name):
        recorded.clear()
        ddoc, _annotation = seat(name)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                drawing_common._telemetry,
                "event",
                lambda event_name, **fields: recorded.append((event_name, fields)),
            )
            drawing_common.fit_title_block_part_name(
                _FakeAdapter(),
                ddoc,
                layout=DrawingLayout.LANDSCAPE,
                sheet_name="Sheet1",
                expected_name=name,
            )
        events = [f for event_name, f in recorded if event_name == "title_block.extent"]
        assert len(events) == 1
        return events[0]

    fitted = measure("harmonic-analyzer assembly")
    assert fitted["sheet"] == "Sheet1"
    assert fitted["fitted"] is True
    assert fitted["extent_em"] == pytest.approx(FARM_TALLEST_ONE_LINE_EM, abs=0.001)
    assert fitted["extent_mm"] == pytest.approx(
        FARM_TALLEST_ONE_LINE_EM * fitted["applied_pts"] * MM_PER_POINT
    )
    assert fitted["extent_top_mm"] == pytest.approx(FARM_LOWEST_EXTENT_TOP_MM)
    assert fitted["ink_bottom_mm"] == pytest.approx(
        fitted["extent_bottom_mm"]
        + EXTENT_BOTTOM_RESERVE_EM * fitted["applied_pts"] * MM_PER_POINT
    )
    assert fitted["cell_bottom_mm"] == pytest.approx(LANDSCAPE.cell_bottom_mm)

    # A name that needs no fit: nothing is written, and it reports anyway.
    untouched = measure("channel-spring-installed")
    assert untouched["fitted"] is False
    assert untouched["applied_pts"] == pytest.approx(LANDSCAPE.nominal_point_size)
    assert untouched["extent_mm"] > 0.0


# The longest name in the fleet fits at 11 pt; this one is a plausible
# McMaster description one qualifier longer, and it fits only at the fit
# step's 9 pt floor. The floor is where the requested and the reported size
# are furthest apart in RELATIVE terms, which is the only place the choice of
# denominator is observable at today's tolerance.
NAME_THAT_FITS_AT_THE_FLOOR = (
    "Black-Oxide Stainless Steel Flared-Collar Knurled-Head Thumb Screw"
)


@pytest.mark.parametrize(
    "readback_pts,refused",
    [(None, False), (8.51, True)],
    ids=["reports-the-size-it-was-written", "reports-0.49-pt-lower"],
)
def test_the_extent_is_judged_at_the_size_the_note_reports(seat, readback_pts, refused):
    """One line of ink is measured against the size the NOTE claims.

    The applier does not trust the size it wrote: it reads the format back
    and accepts the note only if ``round(applied_pts)`` equals the requested
    size. That comparison admits up to 0.49 pt of divergence -- a
    code-contract bound from ``round()``, not a measured COM behaviour, and
    nothing to do with VARIANT drift, which is ~1e-12 -- so a note may be
    accepted as "kept the format" while reporting 8.51 pt after a 9 pt write.

    Which of the two sizes the extent is divided by then decides the verdict
    once 0.49 pt exceeds the tolerance, and at the 9 pt floor it does:
    9/8.51 = 1.0576, against a 1.05 refusal point. A note printing a full
    line of ink at 9 pt while reporting 8.51 pt is 1.057x the one-line model
    at the size it claims -- refused, correctly, because ink that does not
    match the reported size IS the failure this check exists to catch -- and
    exactly one line at the size it was asked for, which is what the
    requested size would say.

    Above 10 pt the two agree inside the tolerance (0.49 pt is at most 4.7%
    there), which is why every other case in this file is blind to the
    difference: computing ``em_mm`` from ``fit.point_size`` instead of
    ``applied_pts`` survives all of them. This pair is what kills it.
    """
    fit = fit_part_name(NAME_THAT_FITS_AT_THE_FLOOR, LANDSCAPE)
    assert fit.adjust is True
    assert fit.point_size == 9
    ddoc, annotation = seat(NAME_THAT_FITS_AT_THE_FLOOR, readback_pts=readback_pts)

    def apply():
        drawing_common.fit_title_block_part_name(
            _FakeAdapter(),
            ddoc,
            layout=DrawingLayout.LANDSCAPE,
            sheet_name="Sheet1",
            expected_name=NAME_THAT_FITS_AT_THE_FLOOR,
        )

    if not refused:
        apply()
        assert annotation.text_format.rendered_point_size == pytest.approx(9.0)
        return

    with pytest.raises(RuntimeError) as refusal:
        apply()
    message = str(refusal.value)
    # The ratio, and the two sizes it was computed from, all have to be in
    # the message: a reader has to be able to see WHICH size was used.
    assert "renders 1.057x taller than one line" in message
    assert "at the 8.51 pt the note reports back (requested 9 pt)" in message


def test_writing_the_system_units_height_inflates_the_note(seat):
    """The fake can SEE the defect the applier used to ship.

    Without this, the ratio assertion above is unfalsifiable: a fake whose
    extent ignores the format would pass it whatever the applier wrote. This
    reproduces the removed write -- ``CharHeight = em_mm / 1000`` after the
    points write -- and pins the inflation at the farm's measured 1.2053, so
    reinstating that line in ``fit_title_block_part_name`` makes the sheet
    fail here instead of on a worker.

    The expectation used to read 1.381. That was never the inflation: it was
    the inflated extent (2.4850 em) over the OLD one-line constant of 1.8,
    which was itself back-derived from 1.381. Against the measured one-line
    extent the same physical reading is 1.205 -- and the same sheet measured
    13.15 mm with the write and 10.91 mm without it, independently of any
    constant, which is where 1.2053 comes from. It is the SMALLEST of the
    four inflations the build measured (up to 1.3261), so this pins the
    least visible version of the defect.
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
    assert height_mm / one_line_mm == pytest.approx(1.205, abs=0.001)
    # The farm's own reading at this size: an inflated 16 pt note, 14.03 mm.
    assert height_mm == pytest.approx(14.03, abs=0.01)


def test_a_wrapped_note_fails_the_sheet_it_was_meant_to_fix(seat):
    """If ``LineLength`` is ignored, the two-line extent must fail the build.

    The refusal has to say what was MEASURED, not what it infers. An earlier
    version reported "renders on more than one line" for every over-tall
    extent, and that wording sent three agents after font ladders when the
    real cause was a unit factor on notes that never wrapped. A wrap adds one
    LINE_SPACING_EM to a line that already measures 2.0617 em, so the ratio
    it must report is 1.485 -- NOT 2x, because the extent already carries a
    line of empty reserve below the ink, which the second line spends; on
    cone_tip_adjuster, the one sheet that really wrapped, the same
    arithmetic reads 1.539. And the size it must report is the one
    read BACK off the note.
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
    assert "renders 1.485x taller than one line" in message
    assert f"at the {point_size:g} pt the note reports back" in message


def test_a_note_whose_ink_hangs_below_its_cell_still_fails(seat):
    """Right height, wrong place: the cell rule is a SEPARATE refusal.

    A note can be exactly one line tall and still be in the wrong place, so
    the check that catches a name sitting on DWG. NO. has to be exercised by
    an extent the HEIGHT guard passes. Without this test, deleting the cell
    rule leaves the suite green -- the wrapped-note case above never reaches
    it, because the height guard refuses that sheet first.

    The defect shape is a note whose whole box sits one line pitch below any
    the farm measured: one line of ink, dropped through the rule. That is
    not the same as dropping the box a millimetre, which is what an earlier
    version of this test did and what the ink model makes harmless -- the
    box's lower edge is EXTENT_BOTTOM_RESERVE_EM of empty space, 4.79 mm of
    it at 16 pt, so a box bottom a millimetre under the rule still has all
    of its ink above it. All 18 sheets the farm refused were that case.
    """
    name = "harmonic-analyzer assembly"
    point_size = fit_part_name(name, LANDSCAPE).point_size
    em_mm = point_size * MM_PER_POINT
    dropped_top_mm = FARM_LOWEST_EXTENT_TOP_MM - LINE_SPACING_EM * em_mm
    ddoc, _annotation = seat(name, top_mm=dropped_top_mm)

    with pytest.raises(RuntimeError) as raised:
        drawing_common.fit_title_block_part_name(
            _FakeAdapter(),
            ddoc,
            layout=DrawingLayout.LANDSCAPE,
            sheet_name="Sheet1",
            expected_name=name,
        )

    message = str(raised.value)
    assert "hangs below its cell" in message
    assert "taller than one line" not in message
    # Both quantities have to be in the message: the derived one the verdict
    # was made on, and the raw edge it came from.
    box_bottom_mm = dropped_top_mm - FARM_TALLEST_ONE_LINE_EM * em_mm
    ink_bottom_mm = box_bottom_mm + EXTENT_BOTTOM_RESERVE_EM * em_mm
    assert f"lowest ink {ink_bottom_mm:.2f} mm" in message
    assert f"extent box bottom {box_bottom_mm:.2f} mm" in message


def test_the_cell_rule_refuses_where_the_ink_crosses_not_where_the_box_does(seat):
    """WHERE the cell rule fires, to 0.01 mm, and it is a claim about INK.

    Every one of the 18 sheets the farm refused had its extent box below the
    rule -- by 0.53 mm at 11 pt, 4.11 mm at 16 -- and every one of them was
    correct, because that lower edge is reserve and the ink is a whole
    EXTENT_BOTTOM_RESERVE_EM above it. So this pins the boundary itself: the
    lowest box a sheet may have is the rule, less the 0.5 mm the check keeps
    in hand, less the reserve. At 16 pt that is 30.59 mm, 4.79 mm BELOW
    where the box-bottom comparison it replaces fired.

    Sweeping 0.01 mm either side is what makes the constant load bearing:
    dropping the reserve term, halving it, or comparing the raw box bottom
    all move this boundary by millimetres.
    """
    name = "harmonic-analyzer assembly"
    point_size = fit_part_name(name, LANDSCAPE).point_size
    em_mm = point_size * MM_PER_POINT
    extent_mm = FARM_TALLEST_ONE_LINE_EM * em_mm
    boundary_mm = LANDSCAPE.cell_bottom_mm - 0.5 - EXTENT_BOTTOM_RESERVE_EM * em_mm

    def refusal_for(box_bottom_mm):
        ddoc, _annotation = seat(name, top_mm=box_bottom_mm + extent_mm)
        try:
            drawing_common.fit_title_block_part_name(
                _FakeAdapter(),
                ddoc,
                layout=DrawingLayout.LANDSCAPE,
                sheet_name="Sheet1",
                expected_name=name,
            )
        except RuntimeError as error:
            return str(error)
        return None

    assert refusal_for(boundary_mm + 0.01) is None
    assert "hangs below its cell" in (refusal_for(boundary_mm - 0.01) or "")
    assert boundary_mm == pytest.approx(30.59, abs=0.01)
    assert LANDSCAPE.cell_bottom_mm - 0.5 - boundary_mm == pytest.approx(4.79, abs=0.01)


def test_an_untouched_sheet_is_measured_but_never_refused(seat):
    """Instrumentation may not invent a way to fail a green build.

    Measuring every sheet is what makes the one-line model re-measurable,
    and the 77 sheets the fit never touches are its control population. But
    their notes are what v36 shipped, nothing is written to them, and no
    extent of theirs was ever measured before this commit -- so a refusal
    there would be a brand-new failure mode introduced by a measurement, on
    sheets whose geometry nobody changed. An extent that refuses a fitted
    sheet twice over is therefore only logged here.
    """
    geometry = {
        # Two lines' worth of box, hung a line pitch below the lowest top
        # the farm measured: over the height bound AND through the rule.
        "extent_em": FARM_TALLEST_ONE_LINE_EM + LINE_SPACING_EM,
        "top_mm": FARM_LOWEST_EXTENT_TOP_MM - LINE_SPACING_EM * 16 * MM_PER_POINT,
    }
    short_name = "channel-spring-installed"
    assert fit_part_name(short_name, LANDSCAPE).adjust is False
    ddoc, annotation = seat(short_name, **geometry)

    fit = drawing_common.fit_title_block_part_name(
        _FakeAdapter(),
        ddoc,
        layout=DrawingLayout.LANDSCAPE,
        sheet_name="Sheet1",
        expected_name=short_name,
    )

    assert fit.adjust is False
    assert annotation.writes == 0
    # The same geometry on a FITTED sheet is refused, which is what makes
    # this a statement about the path rather than about the numbers.
    long_name = "harmonic-analyzer assembly"
    ddoc, _annotation = seat(long_name, **geometry)
    with pytest.raises(RuntimeError):
        drawing_common.fit_title_block_part_name(
            _FakeAdapter(),
            ddoc,
            layout=DrawingLayout.LANDSCAPE,
            sheet_name="Sheet1",
            expected_name=long_name,
        )
