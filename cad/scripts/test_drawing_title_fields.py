"""SolidWorks-free contract for the title block's identity cells
(``_drawing_title_fields``): each sheet's DWG. NO. and PART notes print the
registry's frozen identity, which the linked model also holds, on one line
inside their ruled cells, and reading the model changes nothing.

The COM side is faked at the members the module reads; extents are sheet
metres from the v39 cone-gear sheet and the cut-over identities' widths.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_title_fields as title_fields
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _drawing_title_fields import (
    TitleFieldContractError,
    TitleFieldReading,
    assert_title_fields,
    audit_records,
    read_title_fields,
    registry_identity,
    registry_source,
)

CELLS = dict(DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE].title_cells_m)
NUMBER_EXTENT = (0.31278, 0.02376, 0.36418, 0.02861)
TITLE_EXTENT = (0.31271, 0.03680, 0.38795, 0.04157)
CHAR_HEIGHT = 0.0052
# swmaker000004 native DetailItem245 from the one-view legacy discovery.
NATIVE_TITLE_LINK = '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"'


class _Note:
    """An IAnnotation and its INote in one."""

    def __init__(self, link, text, extent, *, owner=2, kind=6, items=1, upper=False):
        self.OwnerType = owner
        self.PropertyLinkedText = link
        self.AllUpperCase = upper
        self._kind, self._text, self._extent, self._items = kind, text, extent, items

    def GetType(self):  # noqa: N802 - COM name
        return self._kind

    def GetSpecificAnnotation(self):  # noqa: N802 - COM name
        return self

    def GetText(self):  # noqa: N802 - COM name
        return self._text

    def GetExtent(self):  # noqa: N802 - COM name
        x0, y0, x1, y1 = self._extent
        return (x0, y0, 0.0, x1, y1, 0.0)

    def GetHeight(self):  # noqa: N802 - COM name
        return CHAR_HEIGHT

    def GetTextFormat(self, _index):  # noqa: N802 - COM name
        return None

    def GetTextCount(self):  # noqa: N802 - COM name
        return self._items

    def GetDisplayData(self):  # noqa: N802 - COM name
        return self


class _SheetView:
    def __init__(self, name, notes):
        self._name, self._notes = name, notes

    def GetName2(self):  # noqa: N802 - COM name
        return self._name

    def GetAnnotations(self):  # noqa: N802 - COM name
        return tuple(self._notes)


class _Doc:
    def __init__(self, *sheet_views):
        self._rows = [(view, object()) for view in sheet_views]

    def GetViews(self):  # noqa: N802 - COM name
        return self._rows


class _Model:
    """A linked model: per-configuration stored properties, a summary
    Title, and the state a read must not move."""

    def __init__(self, path, kind, scopes, title, *, moves_on_read=False, dirties_on_read=False):
        self._path, self._kind, self._scopes, self._title = path, kind, scopes, title
        self._moves, self._dirties, self._dirty = moves_on_read, dirties_on_read, False
        self.ConfigurationManager = self
        self.ActiveConfiguration = self
        self.Name = "Default"

    def GetPathName(self):  # noqa: N802 - COM name
        return self._path

    def GetType(self):  # noqa: N802 - COM name
        return self._kind

    def GetSaveFlag(self):  # noqa: N802 - COM name
        return self._dirty

    def SummaryInfo(self, field):  # noqa: N802 - COM name
        return self._title if field == 0 else ""

    def GetCustomInfoValue(self, scope, name):  # noqa: N802 - COM name
        if self._moves and scope:
            self.Name = scope
        self._dirty = self._dirty or self._dirties
        return self._scopes.get(scope, {}).get(name, "")


@pytest.fixture(autouse=True)
def _unbound(monkeypatch):
    monkeypatch.setattr(title_fields, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(title_fields, "_read_member", getattr)


CONE_GEAR = DRAWINGS_BY_NAME["dt_cone_gear"]


def _cone_gear(**kwargs):
    # The cone-gear shape: each configuration stamps its own Number over the
    # file-level one, and the Title is the summary slug.
    return _Model(
        str(CONE_GEAR.source),
        1,
        {"": {"Number": "MHA-DT-003"}, "T006": {"Number": "MHA-DT-003-T006"}},
        "dt-cone-gear",
        **kwargs,
    )


def _sheet(
    number="MHA-DT-003-T006",
    title="dt-cone-gear",
    *,
    number_link='$PRPSHEET:"Number"',
    title_link=NATIVE_TITLE_LINK,
    items=1,
    upper=False,
):
    return _SheetView(
        "Sheet1",
        [
            _Note('$PRPSHEET:"Revision"', "39", (0.3770, 0.0240, 0.3850, 0.0290)),
            _Note(number_link, number, NUMBER_EXTENT, items=items, upper=upper),
            _Note('$PRPSHEET:"Number"', number, (0.05, 0.05, 0.10, 0.055), owner=1),
            _Note(title_link, title, TITLE_EXTENT, upper=upper),
        ],
    )


def _read(sheet, model, configuration="T006", spec=CONE_GEAR):
    """The public gate: the identity is always the drawing's own."""
    return read_title_fields(_Doc(sheet), spec, {"Sheet1": (model, configuration)}, {"Sheet1": DrawingLayout.LANDSCAPE})


def _kinds(raised):
    return {(breach.source, breach.kind) for breach in raised.value.breaches}


def test_the_identity_is_the_drawings_own_frozen_one():
    identity = registry_identity(CONE_GEAR)
    assert identity == ("MHA-DT-003", "dt-cone-gear")
    # Only dt-cone-gear takes its view configuration's variant.
    assert registry_source(CONE_GEAR, identity, None, "T006").number == "MHA-DT-003-T006"
    with pytest.raises(RuntimeError):
        registry_source(CONE_GEAR, identity, None, "Default")
    screw = DRAWINGS_BY_NAME["vn_pedestal_hold_down_screw"]
    assert registry_source(screw, registry_identity(screw), None, "T006").number == "MHA-VN-032"
    # An assembly's is its contract's frozen Number and its stem.
    assert registry_identity(DRAWINGS_BY_NAME["ha_harmonic_analyzer_assembly"]) == ("MHA-HA-000", "ha-harmonic-analyzer")
    # part_properties' stretched-spring variants keep their own slug and the base row's Number.
    stretched = SimpleNamespace(source=Path("C:/x/vn-channel-spring-installed-stretch03.SLDPRT"), source_kind="part")
    assert registry_identity(stretched) == ("MHA-VN-004", "vn-channel-spring-installed-stretch03")
    with pytest.raises(KeyError):
        registry_identity(SimpleNamespace(source=Path("C:/x/vn-not-a-part.SLDPRT"), source_kind="part"))
    with pytest.raises(FileNotFoundError):
        registry_identity(SimpleNamespace(source=Path("C:/x/xx-not-an-assembly.SLDASM"), source_kind="assembly"))


def test_a_sheet_linked_to_another_model_fails_before_any_identity_is_read():
    screw = _Model(str(DRAWINGS_BY_NAME["vn_pedestal_hold_down_screw"].source), 1, {}, "")
    with pytest.raises(TitleFieldContractError) as raised:
        _read(_sheet(), screw)
    assert _kinds(raised) == {("model", "foreign-source")}


@pytest.mark.parametrize("number_link", ['$PRPSHEET:"Number"', "$PRPSHEET:{Number}", " $PRPSHEET:Number "])
def test_each_cell_prints_the_registry_identity_its_model_holds(number_link):
    """The configuration's stored Number wins over the file's, the summary
    Title is read for an SW-Title link, and neither the drawing's own notes
    nor the template's other property notes are taken for an identity cell."""
    readings = _read(_sheet(number_link=number_link), _cone_gear())
    assert [(r.source, r.expected, r.model_value, r.printed) for r in readings] == [
        ("Number", "MHA-DT-003-T006", "MHA-DT-003-T006", "MHA-DT-003-T006"),
        ("Title", "dt-cone-gear", "dt-cone-gear", "dt-cone-gear"),
    ]
    assert_title_fields(readings)
    assert audit_records(readings) == {
        "Sheet1": [
            {"source": "Number", "text": "MHA-DT-003-T006", "cell": list(CELLS["Number"])},
            {"source": "Title", "text": "dt-cone-gear", "cell": list(CELLS["Title"])},
        ]
    }



@pytest.mark.parametrize(
    "title_link",
    [NATIVE_TITLE_LINK, '$PRPSHEET:"SW-Title(Title)"', '$PRPSHEET:"SW-Title"'],
)
def test_native_summary_title_descriptor_reads_summary_not_a_same_named_custom_property(title_link):
    model = _Model(
        str(CONE_GEAR.source),
        1,
        {
            "": {
                "Number": "MHA-DT-003",
                "Title": "vn-wrong-custom-title",
                "SW-Title(Title)": "vn-wrong-custom-summary-descriptor",
                "SW-Title": "vn-wrong-custom-summary-name",
            },
            "T006": {"Number": "MHA-DT-003-T006"},
        },
        "dt-cone-gear",
    )
    readings = _read(_sheet(title_link=title_link), model)
    assert [(reading.source, reading.model_value, reading.printed) for reading in readings] == [
        ("Number", "MHA-DT-003-T006", "MHA-DT-003-T006"),
        ("Title", "dt-cone-gear", "dt-cone-gear"),
    ]
    assert_title_fields(readings)
    assert model.Name == "Default" and model.GetSaveFlag() is False


@pytest.mark.parametrize(
    ("model_number", "printed", "kinds"),
    [
        # Same category, wrong number: the model and its print agree, the registry does not.
        ("MHA-DT-004-T006", "MHA-DT-004-T006", {("Number", "model-mismatch"), ("Number", "readback")}),
        # The file-level Number printed where the configuration's is due.
        ("MHA-DT-003-T006", "MHA-DT-003", {("Number", "readback")}),
        ("MHA-DT-003-T006", "MHA-DT-003-T0", {("Number", "readback")}),
        ("MHA-DT-003-T012", "MHA-DT-003-T012", {("Number", "model-mismatch"), ("Number", "readback")}),
    ],
    ids=["same-category-number", "file-level-printed", "cut", "other-variant"],
)
def test_the_registry_identity_is_authoritative(model_number, printed, kinds):
    model = _Model(
        str(CONE_GEAR.source), 1, {"": {"Number": "MHA-DT-003"}, "T006": {"Number": model_number}}, "dt-cone-gear"
    )
    with pytest.raises(TitleFieldContractError) as raised:
        assert_title_fields(_read(_sheet(number=printed), model))
    assert _kinds(raised) == kinds


def test_a_note_printing_in_capitals_breaches_only_the_lowercase_title():
    """``AllUpperCase`` prints the slug in capitals; the Number already is."""
    with pytest.raises(TitleFieldContractError) as raised:
        assert_title_fields(_read(_sheet(upper=True), _cone_gear()))
    assert _kinds(raised) == {("Title", "readback")}


def _reading(
    extent=None,
    *,
    source="Number",
    identity=("MHA-DT-003-T006", "dt-cone-gear"),
    line_length=0.0,
    text_count=1,
    display_count=1,
    printed=None,
):
    expected = identity[0] if source == "Number" else identity[1]
    return TitleFieldReading(
        sheet="Sheet1",
        source=source,
        link='$PRPSHEET:"Number"' if source == "Number" else '$PRPSHEET:"SW-Title"',
        identity=identity,
        model_value=expected,
        printed=expected if printed is None else printed,
        all_upper_case=False,
        extent=extent or (NUMBER_EXTENT if source == "Number" else TITLE_EXTENT),
        cell=CELLS[source],
        char_height=CHAR_HEIGHT,
        typeface="Century Gothic",
        line_length=line_length,
        text_count=text_count,
        display_count=display_count,
    )


@pytest.mark.parametrize(
    ("identity", "source"),
    [
        # -T### extends dt-cone-gear's Number alone, and always does.
        (("MHA-VN-037-T006", "vn-transgear-collar-cross-pin"), "Number"),
        (("MHA-DT-003", "dt-cone-gear"), "Number"),
        (("MHA-DT-003-6", "dt-cone-gear"), "Number"),
        # Number and Title of different categories.
        (("MHA-PD-015", "vn-transgear-collar-cross-pin"), "Number"),
        # A slug of no registry category, or not a slug.
        (("MHA-XX-015", "xx-transgear-knob-thrust-ring"), "Title"),
        (("MHA-PD-015", "pd-Transgear-knob"), "Title"),
        # v39's shapes.
        (("MHA-013", "cone-gear"), "Number"),
        (("MHA-013", "cone-gear"), "Title"),
    ],
    ids=[
        "suffix-off-cone-gear",
        "cone-gear-bare",
        "cone-gear-bad-suffix",
        "cross-category",
        "unknown-category",
        "not-a-slug",
        "v39-number",
        "v39-title",
    ],
)
def test_a_registry_value_that_is_not_one_frozen_identity_fails(identity, source):
    with pytest.raises(TitleFieldContractError) as raised:
        assert_title_fields([_reading(source=source, identity=identity)])
    assert _kinds(raised) == {(source, "not-identity")}


@pytest.mark.parametrize("source", ["Number", "Title"])
@pytest.mark.parametrize(
    "identity",
    [
        ("MHA-DT-003-T006", "dt-cone-gear"),
        ("MHA-PD-015", "pd-transgear-knob-thrust-ring"),
        ("MHA-HA-000", "ha-harmonic-analyzer"),
    ],
)
def test_a_whole_identity_passes(identity, source):
    assert_title_fields([_reading(source=source, identity=identity)])


@pytest.mark.parametrize(
    ("reading", "kind"),
    [
        (_reading((0.31278, 0.02376, 0.37700, 0.02861)), "outside-cell"),
        (_reading((0.31278, 0.02376, 0.37571 - 0.0001, 0.02861)), "outside-cell"),
        # A 9.11 mm tall two-line wrap of 5.2 mm characters, still inside the cell.
        (_reading((0.31278, 0.01950, 0.36418, 0.02861), text_count=2, display_count=2), "multi-line"),
        (_reading(display_count=2), "multi-line"),
        (_reading(display_count=-1), "multi-line"),
        (_reading(printed="MHA-DT-003-\nT006"), "multi-line"),
        (_reading(line_length=0.030), "wrap-width"),
    ],
    ids=["past-rev-rule", "inside-the-air", "wrapped", "display-wrapped", "no-display-data", "line-break", "narrow-wrap"],
)
def test_a_value_not_whole_on_one_line_inside_its_cell_fails(reading, kind):
    with pytest.raises(TitleFieldContractError) as raised:
        assert_title_fields([reading])
    assert kind in {breach.kind for breach in raised.value.breaches}


def test_a_wrap_width_wider_than_the_cell_and_the_cells_air_pass():
    assert_title_fields([_reading(line_length=0.200)])


@pytest.mark.parametrize("change", ["moves_on_read", "dirties_on_read"])
def test_a_read_that_moves_the_models_configuration_or_dirties_it_fails(change):
    with pytest.raises(TitleFieldContractError) as raised:
        _read(_sheet(), _cone_gear(**{change: True}))
    assert _kinds(raised) == {("model", "model-changed")}


@pytest.mark.parametrize(
    "notes",
    [
        [_Note('$PRPSHEET:"Number"', "MHA-DT-003-T006", NUMBER_EXTENT)],
        [
            _Note('$PRPSHEET:"Number"', "MHA-DT-003-T006", NUMBER_EXTENT),
            _Note('$PRPSHEET:"Number"', "MHA-DT-003-T006", NUMBER_EXTENT),
            _Note('$PRPSHEET:"Title"', "dt-cone-gear", TITLE_EXTENT),
        ],
    ],
    ids=["missing", "duplicate"],
)
def test_a_template_that_no_longer_links_one_note_per_cell_fails(notes):
    with pytest.raises(RuntimeError):
        _read(_SheetView("Sheet1", notes), _cone_gear())


@pytest.mark.parametrize(
    ("link", "owner"),
    [
        (NATIVE_TITLE_LINK, 1),
        (NATIVE_TITLE_LINK, 0),
        ('<FONT size=15PTS>$PRP:"SW-Title(Title)"', 2),
        ('<FONT size=15PTS>$PRPVIEW:"SW-Title(Title)"', 2),
    ],
    ids=["drawing-owned", "view-owned", "drawing-property", "view-property"],
)
def test_only_a_template_owned_sheet_source_link_can_supply_the_title(link, owner):
    """A matching displayed slug cannot prove where a note resolves its value."""
    notes = [
        _Note('$PRPSHEET:"Number"', "MHA-DT-003-T006", NUMBER_EXTENT),
        _Note(link, "dt-cone-gear", TITLE_EXTENT, owner=owner),
    ]
    with pytest.raises(RuntimeError):
        _read(_SheetView("Sheet1", notes), _cone_gear())


@pytest.mark.parametrize(
    "title_link",
    [
        '<FONT size=15PTS>PART: $PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"-suffix',
        '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"$PRPSHEET:"Number"',
        '<FONT size=15PTS>$PRP:"Title"$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS>$PRPSHEET:"SW-Title(Author)"',
        '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)-extra"',
        '<FONT size=15PTS>$PRPSHEET:"SW-<FONT size=15PTS>Title(Title)"',
        '<TEXT>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS title=hidden>$PRPSHEET:"SW-Title(Title)"',
        "dt-cone-gear",
    ],
    ids=[
        "visible-prefix", "visible-suffix", "two-sheet-links", "mixed-scopes",
        "wrong-summary-label", "extended-property-name", "markup-inside-property",
        "unknown-tag", "unknown-font-attribute", "literal-title",
    ],
)
def test_title_link_lookalikes_cannot_supply_a_source_identity(title_link):
    with pytest.raises(RuntimeError):
        _read(_sheet(title_link=title_link), _cone_gear())


def test_two_template_title_links_are_ambiguous_even_when_both_values_match():
    sheet = _SheetView(
        "Sheet1",
        [
            _Note('$PRPSHEET:"Number"', "MHA-DT-003-T006", NUMBER_EXTENT),
            _Note(NATIVE_TITLE_LINK, "dt-cone-gear", TITLE_EXTENT),
            _Note('$PRPSHEET:"SW-Title"', "dt-cone-gear", TITLE_EXTENT),
        ],
    )
    with pytest.raises(RuntimeError):
        _read(sheet, _cone_gear())
