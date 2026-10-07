"""Receiving-sheet identity must match the native purchased-part properties."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import draw_vn_knife_hanger_washer as drawing


@pytest.mark.parametrize("native_title_is_slug", [True, False])
def test_source_title_uses_saved_part_identity_not_display_title(
    monkeypatch, tmp_path, native_title_is_slug
):
    """Accept the saved PART slug, not the human-readable registry title.

    The latter remains the PDF/document title; accepting it as the source Title
    would reject every correctly saved current-framework purchased washer.
    """
    stock = drawing.fastener(drawing.SPEC.artifact_stem)
    registry = drawing.PART_REGISTRY
    source = tmp_path / f"{stock.part_name}.SLDPRT"
    source.touch()
    monkeypatch.setattr(
        drawing,
        "SPEC",
        SimpleNamespace(
            source=source,
            source_kind="part",
            artifact_stem=stock.part_name,
            layout=drawing.SPEC.layout,
        ),
    )
    properties = {
        "Number": str(registry["number"]),
        "Title": stock.part_name if native_title_is_slug else registry["title"],
        "Material": str(registry["material"]),
        "Stock Name": stock.stock_name,
        "Supplier": stock.supplier,
        "Supplier SKUs": ", ".join(stock.skus),
    }
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "check", lambda _label, result: result)
    monkeypatch.setattr(
        drawing,
        "read_required_properties",
        lambda _model, _names, *, required: properties,
    )

    class SourceAccepted(Exception):
        pass

    def stop_at_sheet_creation(*_args, **_kwargs):
        raise SourceAccepted

    monkeypatch.setattr(drawing, "new_project_drawing", stop_at_sheet_creation)

    class Adapter:
        currentModel = SimpleNamespace(GetPathName=lambda: str(source))

        async def open_model(self, _path):
            return True

    if native_title_is_slug:
        with pytest.raises(SourceAccepted):
            asyncio.run(drawing.build(Adapter()))
    else:
        with pytest.raises(RuntimeError, match="stale source Title"):
            asyncio.run(drawing.build(Adapter()))


@pytest.mark.parametrize(
    "fault", [None, "value", "prefix", "suffix", "precision", "diametric", "linear"]
)
def test_final_settling_refuses_changed_receiving_dimensions_before_save(
    monkeypatch, tmp_path, fault
):
    """Exercise the washer consumer through the real finalizer's last rebuild.

    Annotation placement initially succeeds. Only the final settling step
    damages a displayed reference; the damaged print must never reach SaveAs
    or PDF export. The unchanged positive control reaches the save boundary.
    """
    import _drawing_common as common

    stock = drawing.fastener(drawing.SPEC.artifact_stem)
    registry = drawing.PART_REGISTRY
    source = tmp_path / f"{stock.part_name}.SLDPRT"
    source.touch()
    monkeypatch.setattr(
        drawing, "SPEC",
        SimpleNamespace(
            source=source, source_kind="part",
            artifact_stem=stock.part_name, layout=drawing.SPEC.layout,
        ),
    )
    properties = {
        "Number": str(registry["number"]), "Title": stock.part_name,
        "Material": str(registry["material"]), "Stock Name": stock.stock_name,
        "Supplier": stock.supplier, "Supplier SKUs": ", ".join(stock.skus),
    }

    class Display:
        def __init__(self, value):
            self.model = SimpleNamespace(SystemValue=value)
            self.text = {}
            self.precision = 2
            self.Diametric = True
            self.DisplayAsLinear = False
            self.second_arrow = False

        def GetDimension2(self, _index):
            return self.model

        def SetText(self, index, text):
            self.text[index] = text

        def GetText(self, index):
            return self.text.get(index, "")

        def GetPrimaryPrecision2(self):
            return self.precision

        def SetSecondArrow(self, _use_doc, second):
            self.second_arrow = second

        def GetUseDocSecondArrow(self):
            return False

        def GetSecondArrow(self):
            return self.second_arrow

        def SetBrokenLeader2(self, _use_doc, _style):
            return 0

    annotations = [
        SimpleNamespace(name=name, GetSpecificAnnotation=lambda d=Display(value): d)
        for name, value in (
            (drawing.OUTER_DIAMETER_DIM, 0.0269748),
            (drawing.INNER_DIAMETER_DIM, 0.0134874),
            (drawing.THICKNESS_DIM, 0.0024765),
        )
    ]

    class Note:
        def __init__(self, text, linked=""):
            self.text = text
            self.PropertyLinkedText = linked

        def GetText(self):
            return self.text

        def GetExtent(self):
            return (0.02, 0.03, 0.0, 0.03, 0.04, 0.0)

    views = []
    for orientation, center, _cell in drawing._VIEW_CELLS:
        x, y = center
        views.append(SimpleNamespace(
            GetOrientationName=lambda n=orientation: n,
            GetReferencedModelName=lambda: str(source),
            ReferencedDocument=SimpleNamespace(GetPathName=lambda: str(source)),
            GetOutline=lambda x=x, y=y: (x - 0.005, y - 0.005, x + 0.005, y + 0.005),
            UpdateViewDisplayGeometry=lambda: None,
        ))
    sheet = SimpleNamespace(
        GetProperties2=lambda: (0, 0, 1, 1, False, 0.4318, 0.2794, False),
        SetProperties2=lambda *_args: None,
        SetScale=lambda *_args: True,
        GetViews=lambda: views,
    )
    draw = SimpleNamespace(
        ClearSelection2=lambda *_args: None,
        GetSheetNames=lambda: ("Sheet1",),
        ActivateSheet=lambda _name: True,
        GetCurrentSheet=lambda: sheet,
        Sheet=lambda _name: sheet,
        EditRebuild3=lambda: True,
    )

    class Adapter:
        currentModel = views[0].ReferencedDocument

        async def open_model(self, _path):
            return True

        def _attempt(self, operation, **_kwargs):
            return operation()

        def _get_attr_or_call(self, obj, name):
            value = getattr(obj, name)
            return value() if callable(value) else value

    adapter = Adapter()

    def new_sheet(*_args, **_kwargs):
        adapter.currentModel = draw
        return draw, sheet

    monkeypatch.setattr(drawing, "new_project_drawing", new_sheet)
    monkeypatch.setattr(drawing, "check", lambda _label, result: result)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "place_view", lambda _adapter, _source, name, *_args, **_kw:
                        next(v for v in views if v.GetOrientationName() == name))
    monkeypatch.setattr(drawing, "_fit_views", lambda *_args: (1, 1))
    monkeypatch.setattr(drawing, "_purchased_title_block", lambda *_args, **_kw: [])
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *_args: None)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "_literal_note", lambda _adapter, text, *_args: Note(text))
    monkeypatch.setattr(drawing, "_caption_below_view", lambda _adapter, text, *_args: Note(text))
    monkeypatch.setattr(drawing, "add_property_linked_note",
                        lambda _adapter, name, *_args, **_kw:
                        Note(properties[name], drawing.property_link(name)))
    monkeypatch.setattr(drawing, "sheet_drawable_region", lambda *_args, **_kw:
                        SimpleNamespace(xmin=0, ymin=0, xmax=0.4318, ymax=0.2794))
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda _adapter, view, **_kw:
                        annotations[:2] if view is views[0] else annotations[2:])
    for module in (drawing, common):
        monkeypatch.setattr(module, "_early_bound", lambda value, _kind: value)
        monkeypatch.setattr(module, "dimension_name", lambda _adapter, annotation: annotation.name)
        monkeypatch.setattr(module, "read_required_properties", lambda *_args, **_kw: properties)
        monkeypatch.setattr(module, "assert_asme_b_sheet", lambda *_args, **_kw: None)
        monkeypatch.setattr(module, "iter_views", lambda _adapter: iter(views))
        monkeypatch.setattr(module, "view_name", lambda _adapter, view: view.GetOrientationName())
    monkeypatch.setattr(drawing._sw_type_info, "early_bound_or_flag",
                        lambda value, *_args: value)
    monkeypatch.setattr(common, "apply_custom_properties", lambda *_args, **_kw: None)
    monkeypatch.setattr(common, "set_high_quality_shaded_with_edges", lambda *_args, **_kw: None)

    def settle(_adapter, *, label):
        if label != "finalize_drawing" or fault is None:
            return
        display = annotations[0].GetSpecificAnnotation()
        if fault == "value":
            display.model.SystemValue += 0.001
        elif fault == "prefix":
            display.text[1] = "<MOD-DIAM>"
        elif fault == "suffix":
            display.text[2] = ""
        elif fault == "precision":
            display.precision = 3
        elif fault == "diametric":
            display.Diametric = False
        elif fault == "linear":
            display.DisplayAsLinear = True

    monkeypatch.setattr(common, "rebuild_drawing", settle)
    persisted = []

    class SaveReached(Exception):
        pass

    def save(*_args, **_kwargs):
        persisted.append("save")
        raise SaveReached

    monkeypatch.setattr(common, "save_drawing", save)
    monkeypatch.setattr(common, "render_pdf_png",
                        lambda *_args, **_kwargs: persisted.append("export"))
    if fault is None:
        with pytest.raises(SaveReached):
            asyncio.run(drawing.build(adapter))
        assert persisted == ["save"]
    else:
        with pytest.raises(RuntimeError, match="settled washer reference"):
            asyncio.run(drawing.build(adapter))
        assert persisted == []
