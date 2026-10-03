"""SolidWorks-free contract for the title block's identity cells
(``_drawing_title_fields``): each sheet's DWG. NO. and PART notes print the
linked model's full Number and Title, on one line inside their ruled cells.

The COM side is faked at the members the module reads; extents are sheet
metres from the v39 cone-gear sheet and the cut-over identities' widths.
"""

from __future__ import annotations

import pytest

import _drawing_title_fields as title_fields
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
from _drawing_title_fields import TitleFieldReading, assert_title_fields, audit_records, read_title_fields

CELLS = dict(DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE].title_cells_m)
NUMBER_EXTENT = (0.31278, 0.02376, 0.36418, 0.02861)
TITLE_EXTENT = (0.31271, 0.03680, 0.38795, 0.04157)
CHAR_HEIGHT = 0.0052


class _Note:
    """An IAnnotation and its INote in one."""

    def __init__(self, link, text, extent, *, owner=2, kind=6, height=CHAR_HEIGHT):
        self.OwnerType = owner
        self.PropertyLinkedText = link
        self._kind, self._text, self._extent, self._height = kind, text, extent, height

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
        return self._height

    def GetTextFormat(self, _index):  # noqa: N802 - COM name
        return None


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


class _Manager:
    def __init__(self, values):
        self._values = values

    def Get6(self, name, _cached):  # noqa: N802 - COM name
        if name not in self._values:
            return (1, "", "", False, False)
        return (2, self._values[name], self._values[name], True, False)


class _Extension:
    def __init__(self, scopes):
        self._scopes = scopes

    def CustomPropertyManager(self, scope):  # noqa: N802 - COM name
        return _Manager(self._scopes.get(scope, {}))


class _Model:
    def __init__(self, scopes, title):
        self.Extension = _Extension(scopes)
        self._title = title

    def SummaryInfo(self, field):  # noqa: N802 - COM name
        return self._title if field == 0 else ""


@pytest.fixture(autouse=True)
def _unbound(monkeypatch):
    monkeypatch.setattr(title_fields, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(title_fields, "_read_member", getattr)


# The cone-gear shape: the view's configuration stamps its own Number over
# the file-level one, and the Title is the summary slug.
CONE_GEAR = _Model({"": {"Number": "MHA-DT-003"}, "T006": {"Number": "MHA-DT-003-T006"}}, "dt-cone-gear")


@pytest.mark.parametrize(
    ("number_link", "title_link"),
    [('$PRPSHEET:"Number"', '$PRPSHEET:"SW-Title"'), ("$PRPSHEET:{Number}", " $PRPSHEET:{SW-Title} ")],
)
def test_each_cell_prints_its_linked_models_full_identity(number_link, title_link):
    """The configuration's Number wins over the file's, the summary Title is
    read for an SW-Title link, and neither the drawing's own notes nor the
    template's other property notes are taken for an identity cell."""
    sheet = _SheetView(
        "Sheet1",
        [
            _Note('$PRPSHEET:"Revision"', "39", (0.3770, 0.0240, 0.3850, 0.0290)),
            _Note(number_link, "MHA-DT-003-T006", NUMBER_EXTENT),
            _Note('$PRPSHEET:"Number"', "MHA-DT-003-T006", (0.05, 0.05, 0.10, 0.055), owner=1),
            _Note(title_link, "dt-cone-gear", TITLE_EXTENT),
        ],
    )
    readings = read_title_fields(_Doc(sheet), {"Sheet1": (CONE_GEAR, "T006")}, {"Sheet1": DrawingLayout.LANDSCAPE})
    assert [(r.source, r.expected, r.printed) for r in readings] == [
        ("Number", "MHA-DT-003-T006", "MHA-DT-003-T006"),
        ("Title", "dt-cone-gear", "dt-cone-gear"),
    ]
    assert_title_fields(readings)
    assert audit_records(readings) == {
        "Sheet1": [
            {"source": "Number", "text": "MHA-DT-003-T006", "cell": list(CELLS["Number"])},
            {"source": "Title", "text": "dt-cone-gear", "cell": list(CELLS["Title"])},
        ]
    }


def _reading(source, expected, printed, extent, *, height=CHAR_HEIGHT):
    return TitleFieldReading(
        sheet="Sheet1",
        source=source,
        link=f'$PRPSHEET:"{source}"',
        expected=expected,
        printed=printed,
        extent=extent,
        cell=CELLS[source],
        char_height=height,
        typeface="Century Gothic",
        line_length=0.0,
    )


_TITLE_OK = _reading("Title", "dt-cone-gear", "dt-cone-gear", TITLE_EXTENT)


@pytest.mark.parametrize(
    ("number", "message"),
    [
        (_reading("Number", "MHA-DT-003-T006", "MHA-DT-003", NUMBER_EXTENT), "prints 'MHA-DT-003' where"),
        (_reading("Number", "MHA-DT-003-T006", "MHA-DT-003-T0", NUMBER_EXTENT), "prints 'MHA-DT-003-T0' where"),
        (_reading("Number", "MHA-013", "MHA-013", NUMBER_EXTENT), "'MHA-013' is not a full identity"),
        (_reading("Number", "", "", NUMBER_EXTENT), "'' is not a full identity"),
        (
            _reading("Number", "MHA-DT-003-T006", "MHA-DT-003-T006", (0.31278, 0.02376, 0.37700, 0.02861)),
            "is -1.29 mm inside its cell",
        ),
        (
            # Two 4 mm lines in a 9.1 mm tall extent, still inside the cell.
            _reading(
                "Number", "MHA-DT-003-T006", "MHA-DT-003-T006", (0.31278, 0.01950, 0.36418, 0.02861), height=0.0040
            ),
            "not one line",
        ),
    ],
    ids=["stale", "cut", "old-number", "blank", "past-rev-rule", "wrapped"],
)
def test_a_breach_fails_the_drawing_naming_sheet_and_cell(number, message):
    with pytest.raises(RuntimeError, match="title block identity contract") as raised:
        assert_title_fields([number, _TITLE_OK])
    assert "sheet 'Sheet1' Number: " in str(raised.value)
    assert message in str(raised.value)


def test_a_number_and_title_of_different_categories_fail():
    number = _reading("Number", "MHA-VN-030", "MHA-VN-030", NUMBER_EXTENT)
    with pytest.raises(RuntimeError, match="'MHA-VN-030' and Title 'dt-cone-gear' name different categories"):
        assert_title_fields([number, _TITLE_OK])


@pytest.mark.parametrize(
    ("notes", "message"),
    [
        ([_Note('$PRPSHEET:"Number"', "MHA-DT-003-T006", NUMBER_EXTENT)], r"no template note links the \['Title'\]"),
        (
            [
                _Note('$PRPSHEET:"Number"', "MHA-DT-003-T006", NUMBER_EXTENT),
                _Note('$PRPSHEET:"Number"', "MHA-DT-003-T006", NUMBER_EXTENT),
                _Note('$PRPSHEET:"Title"', "dt-cone-gear", TITLE_EXTENT),
            ],
            "two template notes link the Number cell",
        ),
    ],
    ids=["missing", "duplicate"],
)
def test_a_template_that_no_longer_links_one_note_per_cell_fails(notes, message):
    with pytest.raises(RuntimeError, match=message):
        read_title_fields(
            _Doc(_SheetView("Sheet1", notes)), {"Sheet1": (CONE_GEAR, "T006")}, {"Sheet1": DrawingLayout.LANDSCAPE}
        )
