"""Offline orientation contract for the shared purchased-fastener drawing builder."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

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
    def __init__(self, orientation: str, source: Path, center: tuple[float, float]) -> None:
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
            "Title": "Test Fastener",
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
        "title": properties["Title"],
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
    monkeypatch.setattr(
        purchased,
        "read_required_properties",
        lambda _model, _names, *, required: properties,
    )

    def new_project_drawing(_adapter, *, layout):
        calls.append(("new", layout))
        return draw, sheet

    monkeypatch.setattr(purchased, "new_project_drawing", new_project_drawing)
    monkeypatch.setattr(purchased, "_purchased_title_block", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(purchased, "stamp_drawing_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(purchased, "double_array", tuple)

    centers = {name: center for name, center, _cell in purchased._VIEW_CELLS}

    def place_view(_adapter, path, orientation, _x, _y, *, scale):
        assert Path(path) == source
        assert scale == (1, 1)
        view = _View(orientation, source, centers[orientation])
        views.append(view)
        return view

    monkeypatch.setattr(purchased, "place_view", place_view)
    monkeypatch.setattr(purchased, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(purchased, "_fit_views", lambda _draw, _views: (1, 1))
    monkeypatch.setattr(
        purchased,
        "view_name",
        lambda _adapter, view: view.GetOrientationName(),
    )

    def assert_sheet(_adapter, _sheet, *, layout, phase, scale):
        calls.append(("assert", layout, phase, scale))

    monkeypatch.setattr(purchased, "assert_asme_b_sheet", assert_sheet)

    def literal_note(_adapter, text: str, x: float, y: float):
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

    async def finalize(_adapter, actual_outputs, *, layout, pdf_title, scale):
        calls.append(("finalize", layout, pdf_title, scale))
        assert actual_outputs.slddrw == outputs["slddrw"]
        assert actual_outputs.pdf == outputs["pdf"]
        assert actual_outputs.png == outputs["png"]
        return {"pdf": str(actual_outputs.pdf)}

    monkeypatch.setattr(purchased, "finalize_drawing", finalize)

    result = asyncio.run(purchased.build_purchased_fastener_drawing(_Adapter(source), spec))

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
