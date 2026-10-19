"""Offline orientation contract for the shared purchased-fastener drawing builder."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import _supplier_dimensions as supplier
import _purchased_fastener_drawing as purchased
from _drawing_registry import DrawingLayout


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
        _adapter, actual_outputs, *, layout, pdf_title, scale, settled_checks=()
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

    # Reference dimensions attach to visible geometry; no hidden-edge
    # identification is needed on these four purchased views.
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


@pytest.mark.parametrize(
    "kind, expected_mm, expected_degrees",
    [(3, 11.1125, None), (6, 11.1125, None), (2, None, 82.0)],
)
def test_supplier_native_type_is_checked_before_reading_si_value(
    kind, expected_mm, expected_degrees
):
    class UnreadableValue:
        Type2 = kind

        def GetDimension2(self, _index):
            raise AssertionError(
                "an incompatible dimension must not be read as a length"
            )

    with pytest.raises(RuntimeError, match="native dimension type"):
        supplier._measured_supplier_value(
            UnreadableValue(),
            label="supplier size",
            presentation="angle" if expected_degrees is not None else "length",
            expected_mm=expected_mm,
            expected_degrees=expected_degrees,
        )


def test_supplier_display_rounding_cannot_replace_exact_model_geometry(monkeypatch):
    monkeypatch.setattr(supplier, "_early_bound", lambda value, _kind: value)

    def display(mm):
        return SimpleNamespace(
            Type2=11,
            GetDimension2=lambda _index: SimpleNamespace(SystemValue=mm / 1000.0),
        )

    assert supplier._measured_supplier_value(
        display(11.1125),
        label="7/16 inch thread length",
        presentation="length",
        expected_mm=11.1125,
        expected_degrees=None,
    ) == pytest.approx(11.1125)
    # .438 is the supplier's displayed rounding, not its exact 7/16 inch size.
    with pytest.raises(RuntimeError, match="exact expected"):
        supplier._measured_supplier_value(
            display(0.438 * 25.4),
            label="7/16 inch thread length",
            presentation="length",
            expected_mm=11.1125,
            expected_degrees=None,
        )
