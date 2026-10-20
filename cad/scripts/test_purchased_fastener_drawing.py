"""Offline orientation contract for the shared purchased-fastener drawing builder."""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

import _purchased_fastener_drawing as purchased
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout


@pytest.mark.parametrize(
    "names",
    [
        ("dt_vn_fillister_screw", "fr_vn_fillister_screw", "pd_vn_fillister_screw"),
        ("mg_vn_clamp_screw", "pd_vn_clamp_screw"),
        ("ch_vn_arbor_set_screw", "dt_vn_arbor_set_screw"),
        ("mg_vn_thumb_screw", "ms_vn_thumb_screw"),
    ],
)
def test_shared_purchases_keep_distinct_native_identities(
    names: tuple[str, ...],
) -> None:
    specs = [DRAWINGS_BY_NAME[name] for name in names]
    assert len({spec.source for spec in specs}) == len(names)
    assert len({spec.artifact_stem for spec in specs}) == len(names)


class _Model:
    def __init__(self, path: Path) -> None:
        self._path = path

    def GetPathName(self) -> str:
        return str(self._path)


class _Adapter:
    def __init__(self, source: Path) -> None:
        self.currentModel = _Model(source)

    async def open_model(self, _path: str) -> bool:
        return True

    @staticmethod
    def _get_attr_or_call(target, name: str):
        return getattr(target, name)()


class _Drawing:
    @staticmethod
    def EditRebuild3() -> bool:
        return True


class _Sheet:
    def __init__(self, width: float, height: float) -> None:
        self._properties = (0, 0, 1.0, 1.0, True, width, height, True)
        self.CustomPropertyView = ""

    def GetProperties2(self):
        return self._properties

    def SetProperties2(self, *values) -> None:
        self._properties = values


class _View:
    def __init__(
        self, orientation: str, source: Path, center: tuple[float, float]
    ) -> None:
        self._orientation = orientation
        self._source = source
        self._center = center
        self.UseSheetScale = 1
        self.ScaleRatio = (1.0, 1.0)

    def GetOrientationName(self) -> str:
        return self._orientation

    def GetReferencedModelName(self) -> str:
        return str(self._source)

    def GetOutline(self) -> tuple[float, float, float, float]:
        x, y = self._center
        return (x - 0.001, y - 0.001, x + 0.001, y + 0.001)

    def GetFirstCenterMark2(self):
        return None


class _Note:
    def __init__(
        self, linked_text: str, resolved_text: str, x: float, y: float
    ) -> None:
        self.PropertyLinkedText = linked_text
        self._resolved_text = resolved_text
        self._extent = (x, y - 0.0005, 0.0, x + 0.001, y + 0.0005, 0.0)

    def GetText(self) -> str:
        return self._resolved_text

    def GetExtent(self):
        return self._extent

    def GetAnnotation(self):
        return self

    def SetPosition(self, x: float, y: float, _z: float) -> bool:
        width = self._extent[3] - self._extent[0]
        self._extent = (x, y - 0.0005, 0.0, x + width, y + 0.0005, 0.0)
        return True


def test_spec_layout_selects_template_dimensions_and_reaches_all_layout_checks(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "test-fastener.SLDPRT"
    source.touch()
    layout = DrawingLayout.PORTRAIT
    selected_template = SimpleNamespace(width_m=0.500, height_m=0.600)
    other_template = SimpleNamespace(width_m=0.700, height_m=0.800)
    outputs = {
        "slddrw": tmp_path / "test-fastener.SLDDRW",
        "pdf": tmp_path / "test-fastener.pdf",
        "png": tmp_path / "test-fastener.png",
    }
    spec = SimpleNamespace(
        artifact_stem="test-fastener",
        source=source,
        source_kind="part",
        layout=layout,
        outputs=outputs,
    )
    properties = {name: "unused" for name in purchased._PROPERTIES}
    properties.update(
        {
            "Number": "42",
            # The PART cell prints the slug; the registry title only names
            # the drawing document (#877 PART-cell ruling).
            "Title": source.stem,
            "Material": "Steel",
            "Stock Name": "Test stock",
            "Supplier": "Test supplier",
            "Supplier SKUs": "SKU-1",
        }
    )
    stock = SimpleNamespace(
        part_name=source.stem,
        stock_name=properties["Stock Name"],
        supplier=properties["Supplier"],
        skus=("SKU-1",),
    )
    registry = {
        "number": properties["Number"],
        "title": "Test Fastener",
        "material": properties["Material"],
        "finish": "As purchased",
    }
    draw = _Drawing()
    sheet = _Sheet(selected_template.width_m, selected_template.height_m)
    views: list[_View] = []
    calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        purchased,
        "DRAWING_TEMPLATES",
        {
            DrawingLayout.LANDSCAPE: other_template,
            DrawingLayout.PORTRAIT: selected_template,
        },
    )
    monkeypatch.setattr(purchased, "fastener", lambda _stem: stock)
    monkeypatch.setattr(purchased._config, "parts", lambda _name: registry)
    monkeypatch.setattr(purchased, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(purchased, "check", lambda _label, result: result)

    def required_properties(_model, names, *, required):
        assert tuple(names) == tuple(purchased._PROPERTIES)
        assert tuple(required) == tuple(names)
        return properties

    monkeypatch.setattr(purchased, "read_required_properties", required_properties)

    def new_project_drawing(_adapter, *, layout):
        calls.append(("new", layout))
        return draw, sheet

    monkeypatch.setattr(purchased, "new_project_drawing", new_project_drawing)
    monkeypatch.setattr(
        purchased, "_purchased_title_block", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        purchased, "stamp_drawing_summary", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(purchased, "double_array", tuple)

    cells = purchased.fastener_view_cells(purchased.view_band_bottom("", label="t"))
    centers = {name: center for name, center, _cell in cells}

    def place_view(_adapter, path, orientation, _x, _y, *, scale):
        assert Path(path) == source
        assert scale == (1, 1)
        view = _View(orientation, source, centers[orientation])
        views.append(view)
        return view

    monkeypatch.setattr(purchased, "place_view", place_view)
    modes: dict[str, str] = {}
    monkeypatch.setattr(
        purchased,
        "set_hidden_lines_removed",
        lambda _adapter, view: modes.update({view.GetOrientationName(): "HLR"}),
    )
    monkeypatch.setattr(
        purchased,
        "_fit_views",
        lambda _draw, _views, cells: {name: (1, 1) for name, _, _ in cells},
    )
    monkeypatch.setattr(
        purchased,
        "view_name",
        lambda _adapter, view: view.GetOrientationName(),
    )

    def assert_sheet(_adapter, _sheet, *, layout, phase, scale):
        calls.append(("assert", layout, phase, scale))

    monkeypatch.setattr(purchased, "assert_asme_b_sheet", assert_sheet)

    monkeypatch.setattr(purchased, "apply_custom_properties", lambda *_a, **_k: None)

    def literal_note(_adapter, text: str, x: float, y: float):
        calls.append(("note", text, x, y))
        return _Note(text, text, x, y)

    def linked_note(_adapter, name: str, x: float, y: float, *, char_height: float):
        assert char_height == 0.003
        return _Note(purchased.property_link(name), properties[name], x, y)

    monkeypatch.setattr(purchased, "_literal_note", literal_note)
    monkeypatch.setattr(purchased, "add_property_linked_note", linked_note)
    monkeypatch.setattr(purchased, "iter_views", lambda _adapter: views)

    def drawable_region(_adapter, _sheet, *, width: float, height: float):
        calls.append(("region", width, height))
        return SimpleNamespace(xmin=0.0, ymin=0.0, xmax=width, ymax=height)

    monkeypatch.setattr(purchased, "sheet_drawable_region", drawable_region)

    async def finalize(
        _adapter, actual_outputs, *, layout, pdf_title, scale, settled_checks
    ):
        calls.append(("finalize", layout, pdf_title, scale))
        assert actual_outputs.slddrw == outputs["slddrw"]
        assert actual_outputs.pdf == outputs["pdf"]
        assert actual_outputs.png == outputs["png"]
        return {"pdf": str(actual_outputs.pdf)}

    monkeypatch.setattr(purchased, "finalize_drawing", finalize)

    result = asyncio.run(
        purchased.build_purchased_fastener_drawing(
            _Adapter(source), spec, item="#4-40 x 1/4 TEST SCREW"
        )
    )

    # Every view is hidden-lines-removed (rule 9: no dimension names a
    # hidden edge on a purchased reference sheet).
    assert modes == dict.fromkeys(("*Front", "*Top", "*Right", "*Isometric"), "HLR")
    printed = [call[1] for call in calls if call[0] == "note"]
    assert "#4-40 x 1/4 TEST SCREW" in printed
    assert purchased._GENERAL_TEXT[False] in printed
    assert not any("STOCK" in text or "INSTALL PER NOTES" in text for text in printed)

    assert result == {"pdf": str(outputs["pdf"])}
    assert ("new", layout) in calls
    assert ("assert", layout, "purchased layout", (1, 1)) in calls
    assert ("region", selected_template.width_m, selected_template.height_m) in calls
    assert (
        "finalize",
        layout,
        "Test Fastener — Purchased Part Reference Drawing",
        (1, 1),
    ) in calls


def test_scale_fitting_does_not_scale_fixed_native_padding(monkeypatch, tmp_path):
    """A fitting 2:1 view must not be rejected by scaling its fixed sheet padding."""

    class PaddedView(_View):
        @property
        def Position(self):
            return self._center

        def GetOutline(self):
            ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
            width = 0.06498 * ratio + 0.0127
            height = 0.00657 * ratio + 0.0127
            x, y = self._center
            return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)

        def SetViewPosition(self, position, _update):
            self._center = tuple(position)
            return True

    monkeypatch.setattr(purchased, "double_array", tuple)
    center = (0.111, 0.170)
    cell = (0.015, 0.155, 0.207, 0.185)
    view = PaddedView("*Front", tmp_path / "spring.SLDPRT", center)
    assert purchased._fit_views(_Drawing(), [view], (("*Front", center, cell),)) == {
        "*Front": (2, 1)
    }


def test_isometric_scales_independently(monkeypatch, tmp_path):
    """A tall pictorial drops its own scale, never the orthographic views'."""

    class SizedView(_View):
        def __init__(self, orientation, source, center, size):
            super().__init__(orientation, source, center)
            self._size = size

        @property
        def Position(self):
            return self._center

        def GetOutline(self):
            ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
            width = self._size[0] * ratio + 0.0112
            height = self._size[1] * ratio + 0.0112
            x, y = self._center
            return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)

        def SetViewPosition(self, position, _update):
            self._center = tuple(position)
            return True

    monkeypatch.setattr(purchased, "double_array", tuple)
    cells = purchased.fastener_view_cells(0.073)
    sizes = {
        "*Front": (0.010, 0.020),
        "*Top": (0.010, 0.010),
        "*Right": (0.010, 0.020),
        "*Isometric": (0.020, 0.030),
    }
    views = [
        SizedView(name, tmp_path / "s.SLDPRT", center, sizes[name])
        for name, center, _ in cells
    ]
    scales = purchased._fit_views(_Drawing(), views, cells)
    assert scales["*Front"] == scales["*Top"] == scales["*Right"] == (4, 1)
    assert scales["*Isometric"] == (1, 1)


def test_footer_notes_hold_rule_seven_budget():
    assert purchased.note_lines("A\nB\nC", label="t") == ("A", "B", "C")
    with pytest.raises(ValueError, match="rule 7"):
        purchased.note_lines("A\nB\nC\nD", label="t")
    with pytest.raises(ValueError, match="ITEM"):
        purchased.check_item("X" * (purchased.MAX_ITEM_CHARS + 1), label="t")
    # More note lines lift the views' bottom row, never below the title block.
    assert purchased.view_band_bottom("", label="t") == purchased._LOWEST_CAPTION_Y
    assert purchased.view_band_bottom("A\nB\nC", label="t") > purchased.footer_top(
        "A\nB\nC", label="t"
    )


def test_center_marks_lose_their_extension_lines(monkeypatch):
    class Mark:
        def __init__(self, following=None):
            self.UseDocDisplaySettings = True
            self.ShowLines = True
            self._following = following

        def GetNext(self):
            return self._following

    class MarkedView:
        def __init__(self, first):
            self._first = first

        def GetFirstCenterMark2(self):
            return self._first

    monkeypatch.setattr(purchased, "_early_bound", lambda value, _kind: value)
    second = Mark()
    first = Mark(second)
    cells = purchased.fastener_view_cells(0.073)
    views = [MarkedView(first), MarkedView(None), MarkedView(None), MarkedView(None)]
    assert purchased._center_marks_without_lines(views, cells) == {
        "*Front": 2,
        "*Top": 0,
        "*Right": 0,
        "*Isometric": 0,
    }
    assert not any(m.ShowLines or m.UseDocDisplaySettings for m in (first, second))

    class StuckMark(Mark):
        @property
        def ShowLines(self):
            return True

        @ShowLines.setter
        def ShowLines(self, _value):
            pass

    views[0] = MarkedView(StuckMark())
    with pytest.raises(RuntimeError, match="extension lines"):
        purchased._center_marks_without_lines(views, cells)


# The fake's CharHeightInPts <-> CharHeight step, fitted to what the
# templates-1636 census read off the landscape template: 18 pt as
# 0.0047625 m and 15 pt as 0.00396875 m.  A fake calibration, not a claim
# about other templates, fonts or seats.
_NATIVE_POINT = 0.0254 / 96.0
# The fake's printed em per CharHeight, chosen so the template's 18 pt note
# keeps the r3 kp08 width below; likewise only a calibration.
_EM_PER_CHAR_HEIGHT = 4.0 / 3.0
_NUMBER_LINK = '$PRPSHEET:"Number"'
_LONG_NUMBER = "MHA-CH-06-TL-VN-65"
# The r3 kp08 sheet's REV divider, x mm from the PDF.
_REV_DIVIDER = 0.37231
# The census's DWG. NO. box top, which the 8d9c8dbba readback kept.
_NUMBER_TOP = 0.029136093645


class _FitFormat:
    """ITextFormat whose getters answer for either authority.

    Heights convert on :data:`_NATIVE_POINT`; writing ``CharHeight`` makes
    metres the authoritative unit.
    """

    def __init__(self, *, points: int | None = None, metres: float = 0.0) -> None:
        self._points, self._metres = points, metres
        self.TypeFaceName = "Century Gothic"

    def IsHeightSpecifiedInPts(self) -> bool:
        return self._points is not None

    @property
    def CharHeightInPts(self) -> int:
        if self._points is not None:
            return self._points
        return round(self._metres / _NATIVE_POINT)

    @property
    def CharHeight(self) -> float:
        if self._points is not None:
            return self._points * _NATIVE_POINT
        return self._metres

    @CharHeight.setter
    def CharHeight(self, value: float) -> None:
        self._points, self._metres = None, value


class _TitleNote:
    """A template INote/IAnnotation whose printed box follows its font.

    Calibrated to the r3 kp08 sheet (18 characters at 18 pt end at
    372.87 mm) and to the census box: top-anchored, 0.976 em a row.
    """

    def __init__(
        self, text: str, *, link: str = _NUMBER_LINK, accepts: bool = True
    ) -> None:
        self.PropertyLinkedText = link
        self._text = text
        self._format = _FitFormat(points=18)
        self._use_doc = True
        self._accepts = accepts

    def GetType(self) -> int:
        return 6

    def GetSpecificAnnotation(self):
        return self

    def GetTextFormat(self, _index: int) -> _FitFormat:
        return copy.copy(self._format)

    def SetTextFormat(self, _index: int, use_doc: bool, text_format) -> bool:
        if self._accepts:
            self._format, self._use_doc = copy.copy(text_format), use_doc
        return self._accepts

    def GetUseDocTextFormat(self, _index: int) -> bool:
        return self._use_doc

    def GetText(self) -> str:
        return self._text

    def GetExtent(self):
        em = self._format.CharHeight * _EM_PER_CHAR_HEIGHT
        width = 0.5464 * len(self._text) * em
        bottom = _NUMBER_TOP - 0.976 * em
        return (0.31042, bottom, 0.0, 0.31042 + width, _NUMBER_TOP, 0.0)


class _TitleSheet:
    """IDrawingDoc whose sheet view carries the template notes."""

    def __init__(self, *notes: _TitleNote) -> None:
        self._notes = notes

    def GetFirstView(self):
        return self

    def GetAnnotations(self):
        return self._notes

    def EditRebuild3(self) -> bool:
        return True

    def ViewZoomTo2(self, *_box: float) -> None:
        pass

    def ViewZoomtofit2(self) -> None:
        pass


def _fit(sheet: _TitleSheet, *, number: str, layout=DrawingLayout.LANDSCAPE):
    return purchased._fit_number(
        SimpleNamespace(currentModel=sheet), sheet, layout=layout, number=number
    )


@pytest.mark.parametrize(
    "authored",
    [_FitFormat(points=18), _FitFormat(metres=18 * _NATIVE_POINT)],
    ids=["points", "metres"],
)
def test_number_fit_clears_the_rev_divider(authored):
    note = _TitleNote(_LONG_NUMBER)
    note._format = authored
    other = _TitleNote("ALLOY STEEL", link='$PRPSHEET:"Material"')
    before = authored.CharHeight
    settled = _fit(_TitleSheet(other, note), number=_LONG_NUMBER)
    extent = note.GetExtent()
    assert extent[3] < _REV_DIVIDER - 0.001  # a visible gap before REV
    assert extent[1] >= 0.0200  # one row, inside the cell
    assert 0.003 <= note._format.CharHeight < before
    assert (note.PropertyLinkedText, note.GetText()) == (_NUMBER_LINK, _LONG_NUMBER)
    assert note._format.TypeFaceName == "Century Gothic"
    assert other._format.CharHeightInPts == 18 and other._use_doc is True
    settled()
    # A later rebuild back at the template size never reaches the export.
    note._format = _FitFormat(points=18)
    with pytest.raises(RuntimeError):
        settled()


def test_number_fit_writes_the_native_height_it_measured():
    # The landscape template's DWG. NO. as the templates-1636 census read it
    # (DetailItem248).  8d9c8dbba scaled its 18 pt at 0.0254/72 m and wrote
    # 0.00618 m, 1.30x the note's native height; the clamp/nut readback ran
    # down to y = 13.41 mm, below the cell.
    note = _TitleNote(_LONG_NUMBER)
    assert note._format.CharHeight == pytest.approx(0.0047625, abs=1e-12)
    _fit(_TitleSheet(note), number=_LONG_NUMBER)
    assert note._format.IsHeightSpecifiedInPts() is False
    assert note._format.CharHeight == pytest.approx(0.0046, abs=1e-12)


def test_number_fit_state_refusal_cannot_mask_the_guard(monkeypatch):
    class Escaped(_TitleNote):
        def GetExtent(self):
            if self._use_doc:
                return super().GetExtent()
            return (0.3102605752508361, 0.013409331103678923, 0.0, 0.36, 0.0291, 0.0)

    def refuse(*_args, **_kwargs):
        raise TypeError("diagnostic serialization failed")

    monkeypatch.setattr(purchased, "json", SimpleNamespace(dumps=refuse))
    with pytest.raises(RuntimeError):
        _fit(_TitleSheet(Escaped(_LONG_NUMBER)), number=_LONG_NUMBER)


def test_number_fit_leaves_a_fitting_number_at_the_template_size():
    number = "MHA-CH-06-TL-21"
    note = _TitleNote(number)
    settled = _fit(_TitleSheet(note), number=number)
    assert note._use_doc is True
    assert note._format.CharHeightInPts == 18
    settled()


@pytest.mark.parametrize(
    ("notes", "number", "layout", "error"),
    [
        pytest.param(
            (_TitleNote(_LONG_NUMBER, accepts=False),),
            _LONG_NUMBER,
            DrawingLayout.LANDSCAPE,
            RuntimeError,
            id="setter-refused",
        ),
        pytest.param(
            (_TitleNote(_LONG_NUMBER), _TitleNote(_LONG_NUMBER)),
            _LONG_NUMBER,
            DrawingLayout.LANDSCAPE,
            RuntimeError,
            id="two-number-notes",
        ),
        pytest.param(
            (_TitleNote(_LONG_NUMBER, link=f"DWG. NO. {_NUMBER_LINK}"),),
            _LONG_NUMBER,
            DrawingLayout.LANDSCAPE,
            RuntimeError,
            id="label-in-number-note",
        ),
        pytest.param(
            (_TitleNote("MHA-CH-06-TL-VN-64"),),
            _LONG_NUMBER,
            DrawingLayout.LANDSCAPE,
            RuntimeError,
            id="stale-number",
        ),
        pytest.param(
            (_TitleNote("M" * 40),),
            "M" * 40,
            DrawingLayout.LANDSCAPE,
            RuntimeError,
            id="below-note-height",
        ),
        pytest.param(
            (_TitleNote(_LONG_NUMBER),),
            _LONG_NUMBER,
            DrawingLayout.PORTRAIT,
            ValueError,
            id="unmeasured-portrait",
        ),
    ],
)
def test_number_fit_refuses_rather_than_hide_a_collision(notes, number, layout, error):
    with pytest.raises(error):
        _fit(_TitleSheet(*notes), layout=layout, number=number)
    for note in notes:
        assert note._format.CharHeightInPts == 18
