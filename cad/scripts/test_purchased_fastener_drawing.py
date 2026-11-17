"""Offline contracts for canonical purchased screws and configured reference sheets."""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

import _purchased_fastener_drawing as purchased
import _purchased_variant_drawing as configured
from _drawing_types import DrawingLayout


@pytest.fixture(autouse=True)
def offline_source_failure_capture(monkeypatch, tmp_path):
    import _seat_forensics

    monkeypatch.setattr(_seat_forensics, "OUT_FAILURES", tmp_path / "failures")
    monkeypatch.setattr(_seat_forensics, "_grab_screen", lambda target: str(target))
    monkeypatch.setattr(
        purchased, "layout_report_path", lambda stem: tmp_path / f"{stem}.layout.json"
    )


class _Model:
    def __init__(self, path: Path) -> None:
        self._path = path

    def GetPathName(self) -> str:
        return str(self._path)

    def GetType(self) -> int:
        return 1

    def IsOpenedReadOnly(self) -> bool:
        return True

    def GetSaveFlag(self) -> bool:
        return False


class _Adapter:
    def __init__(self, source: Path) -> None:
        self.currentModel = None
        model = _Model(source)
        documents = {}

        def open_doc(path, kind, options, configuration, errors, warnings):
            assert (kind, options, configuration, errors, warnings) == (1, 3, "", 0, 0)
            documents[str(Path(path).resolve())] = model
            return model, 0, 0

        self.swApp = SimpleNamespace(
            OpenDoc6=open_doc,
            GetOpenDocumentByName=lambda path: documents.get(str(Path(path).resolve())),
            IsSame=lambda left, right: int(left is right),
        )

    @staticmethod
    def _get_attr_or_call(target, name: str):
        return getattr(target, name)()


class _Drawing:
    @staticmethod
    def EditRebuild3() -> bool:
        return True

    def GetPathName(self) -> str:
        return ""

    def GetType(self) -> int:
        return 3

    def IsOpenedReadOnly(self) -> bool:
        return False

    def GetSaveFlag(self) -> bool:
        return True


class _Sheet:
    def __init__(self, width: float = 0.4318, height: float = 0.2794) -> None:
        self._properties = (0, 0, 1.0, 1.0, True, width, height, True)
        self.CustomPropertyView = ""

    def GetProperties2(self):
        return self._properties

    def SetProperties2(self, *values):
        self._properties = tuple(values)


class _View:
    def __init__(
        self, orientation: str, source: Path, center: tuple[float, float]
    ) -> None:
        self._orientation = orientation
        self._source = source
        self._center = center
        self.UseSheetScale = 1
        self.ScaleRatio = (1.0, 1.0)
        self.ReferencedConfiguration = "Default"
        self.ReferencedDocument = None

    def GetName2(self) -> str:
        return self._orientation

    def GetOrientationName(self) -> str:
        return self._orientation

    def GetReferencedModelName(self) -> str:
        return str(self._source)

    def GetOutline(self) -> tuple[float, float, float, float]:
        x, y = self._center
        return (x - 0.001, y - 0.001, x + 0.001, y + 0.001)

    def UpdateViewDisplayGeometry(self) -> None:
        return None

    def GetFirstCenterMark2(self):
        return None


class _Note:
    def __init__(
        self, linked_text: str, resolved_text: str, x: float, y: float
    ) -> None:
        self.PropertyLinkedText = linked_text
        self._resolved_text = resolved_text
        self._position = (x, y, 0.0)
        self._extent = (x, y - 0.0005, 0.0, x + 0.001, y + 0.0005, 0.0)

    def GetText(self) -> str:
        return self._resolved_text

    def GetExtent(self):
        return self._extent

    def GetAnnotation(self):
        return self

    def GetPosition(self):
        return self._position

    def SetPosition(self, x, y, z):
        dx, dy = x - self._position[0], y - self._position[1]
        x0, y0, z0, x1, y1, z1 = self._extent
        self._extent = (x0 + dx, y0 + dy, z0, x1 + dx, y1 + dy, z1)
        self._position = (x, y, z)
        return True


_CUSTOM_GENERAL = "PURCHASED PART; TEST OVERRIDE LINE."


@pytest.mark.parametrize("general_text", (None, _CUSTOM_GENERAL))
@pytest.mark.parametrize("number_fit", (None, purchased.NumberFit.SHRINK_TO_CELL))
def test_spec_layout_selects_template_dimensions_and_reaches_all_layout_checks(
    monkeypatch, tmp_path: Path, number_fit, general_text
) -> None:
    source = tmp_path / "test-fastener.SLDPRT"
    source.touch()
    layout = DrawingLayout.PORTRAIT if number_fit is None else DrawingLayout.LANDSCAPE
    other_layout = (
        DrawingLayout.LANDSCAPE if number_fit is None else DrawingLayout.PORTRAIT
    )
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
        {layout: selected_template, other_layout: other_template},
    )
    monkeypatch.setattr(purchased, "fastener", lambda _stem: stock)
    monkeypatch.setattr(purchased._config, "parts", lambda _name: registry)
    monkeypatch.setattr(purchased, "_early_bound", lambda value, _kind: value)

    def required_properties(_model, names, *, required):
        assert tuple(names) == tuple(purchased._PROPERTIES)
        assert tuple(required) == tuple(names)
        return properties

    monkeypatch.setattr(purchased, "read_required_properties", required_properties)

    def new_project_drawing(_adapter, *, layout, checkpoint, unit):
        assert unit == "mm"
        calls.append(("new", layout))
        _adapter.currentModel = draw
        checkpoint("after_new_document")
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
        view.ReferencedDocument = _adapter.swApp.GetOpenDocumentByName(str(source))
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

    def fit_number(_adapter, actual_draw, *, layout, number):
        assert actual_draw is draw
        calls.append(("number-fit", layout, number))
        return lambda: calls.append(("number-fit-settled",))

    monkeypatch.setattr(purchased, "_fit_number", fit_number)

    async def finalize(
        _adapter,
        actual_outputs,
        *,
        layout,
        pdf_title,
        scale,
        settled_checks,
        checkpoint,
    ):
        calls.append(("finalize", layout, pdf_title, scale))
        assert actual_outputs.slddrw == outputs["slddrw"]
        assert actual_outputs.pdf == outputs["pdf"]
        assert actual_outputs.png == outputs["png"]
        for settled_check in settled_checks:
            settled_check()
        return {"pdf": str(actual_outputs.pdf)}

    monkeypatch.setattr(purchased, "finalize_drawing", finalize)
    options = {} if number_fit is None else {"number_fit": number_fit}
    if general_text is not None:
        options["general_text"] = general_text
    result = asyncio.run(
        purchased.build_purchased_fastener_drawing(
            _Adapter(source), spec, item="#4-40 x 1/4 TEST SCREW", **options
        )
    )

    # Every view is hidden-lines-removed (rule 9: no dimension names a
    # hidden edge on a purchased reference sheet).
    assert modes == dict.fromkeys(("*Front", "*Top", "*Right", "*Isometric"), "HLR")
    printed = [call[1] for call in calls if call[0] == "note"]
    assert "#4-40 x 1/4 TEST SCREW" in printed
    # The override replaces only the general line; omitted keeps the default.
    # Both pass the build's native footer readback, which raises on a mismatch.
    general = [text for text in printed if text in (_CUSTOM_GENERAL, *purchased._GENERAL_TEXT.values())]
    assert general == [general_text or purchased._GENERAL_TEXT[False]]
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
    if number_fit is None:
        assert not any(call[0].startswith("number-fit") for call in calls)
    else:
        assert ("number-fit", layout, properties["Number"]) in calls
        assert calls[-1] == ("number-fit-settled",)


@pytest.mark.parametrize("configuration", ("OuterLink", "PenWire", "TNut", "FlangeNut"))
def test_reference_views_select_exact_member_then_rebuild_before_readback(
    configuration: str,
) -> None:
    rebuilt = False

    class View:
        def __init__(self):
            self.selected = "Default"
            self.pending = None

        @property
        def ReferencedConfiguration(self):
            assert rebuilt, "configuration must be read back after rebuilding"
            return self.selected

        @ReferencedConfiguration.setter
        def ReferencedConfiguration(self, value):
            self.pending = value

    def rebuild():
        nonlocal rebuilt
        for view in views:
            view.selected = view.pending
        rebuilt = True
        return True

    views = [View() for _ in range(4)]
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=rebuild))
    configured.configure_reference_views(adapter, configuration, views)
    assert all(view.selected == configuration for view in views)
    assert rebuilt


@pytest.mark.parametrize(
    ("failure", "readback"),
    [
        ("setter", "Default"),
        ("rebuild", "PenWire"),
        ("readback", "Default"),
        ("readback", "LeverWire"),
        ("readback", "penwire"),
    ],
)
def test_reference_configuration_failure_never_retries_default(
    failure: str, readback: str
) -> None:
    requested = []

    class View:
        @property
        def ReferencedConfiguration(self):
            return readback

        @ReferencedConfiguration.setter
        def ReferencedConfiguration(self, value):
            requested.append(value)
            if failure == "setter":
                raise RuntimeError("native setter refused")

    def rebuild():
        if failure == "rebuild":
            raise RuntimeError("native rebuild refused")
        return True

    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=rebuild))
    with pytest.raises(RuntimeError):
        configured.configure_reference_views(adapter, "PenWire", [View()])
    assert requested == ["PenWire"]


@pytest.mark.parametrize("count", (2, 3))
def test_configuration_cells_preserve_third_angle_panels_and_note_clearance(
    count,
) -> None:
    panels = [
        configured.configuration_view_cells(index, count) for index in range(count)
    ]
    panel_bounds = []
    for cells in panels:
        assert [name for name, _, _ in cells] == [
            "*Front",
            "*Top",
            "*Right",
            "*Isometric",
        ]
        boxes = {name: cell for name, _, cell in cells}
        for _, center, (x0, y0, x1, y1) in cells:
            assert 0.018 - 1e-12 <= x0 < x1 <= 0.414 + 1e-12
            assert 0.127 <= y0 < y1 <= 0.244
            assert center == pytest.approx(((x0 + x1) / 2, (y0 + y1) / 2))
        front, top, right, iso = (
            boxes[name] for name in ("*Front", "*Top", "*Right", "*Isometric")
        )
        assert front[0::2] == top[0::2]
        assert right[0::2] == iso[0::2]
        assert front[2] < right[0]
        assert front[3] < top[1]
        assert right[3] < iso[1]
        assert front[1] - 0.004 > 0.106  # Lower captions clear member-note rows.
        assert top[3] < 0.255  # Header QTY labels have their own reserved band.
        panel_bounds.append((front[0], right[2]))
    for previous, following in zip(panel_bounds, panel_bounds[1:]):
        assert following[0] - previous[1] == pytest.approx(0.008)


@pytest.mark.parametrize(
    ("index", "count"), [(-1, 2), (2, 2), (3, 3), (0, 0), (0, 1), (0, 4)]
)
def test_configuration_cells_refuse_invalid_panel_count_or_index(index, count) -> None:
    with pytest.raises(ValueError):
        configured.configuration_view_cells(index, count)


@pytest.mark.parametrize("count", (2, 3))
def test_isometric_only_cell_fills_its_member_panel(count) -> None:
    for index in range(count):
        (iso,) = configured.isometric_view_cells(index, count)
        cells = [cell for _, _, cell in configured.configuration_view_cells(index, count)]
        panel = (
            min(cell[0] for cell in cells),
            min(cell[1] for cell in cells),
            max(cell[2] for cell in cells),
            max(cell[3] for cell in cells),
        )
        assert iso[0] == "*Isometric"
        assert iso[2] == panel
        assert iso[1] == pytest.approx(((panel[0] + panel[2]) / 2, (panel[1] + panel[3]) / 2))


def _isometric_only_sheet(monkeypatch, tmp_path):
    variants = (("Rail", "[1] RAIL"), ("Carriage", "[2] CARRIAGE"))
    state = _variant_sheet(
        monkeypatch, tmp_path, variants, {"Rail": 2, "Carriage": 2}, 4
    )
    new_drawing = configured.new_project_drawing

    def create(adapter, *, layout, unit):
        draw, sheet = new_drawing(adapter, layout=layout, unit=unit)
        sheet.GetName = lambda: "REFERENCE"
        draw.ActivateSheet = lambda _name: True
        return draw, sheet

    monkeypatch.setattr(configured, "new_project_drawing", create)
    monkeypatch.setattr(
        configured, "create_blank_drawing_sheets", lambda *_args, **_kwargs: None
    )
    # The isometric fits at 1:2, the orthographic views at 1:1.
    def fit(_draw, views, cells):
        scales = {}
        for view, (name, _, _) in zip(views, cells, strict=True):
            scales[name] = (1, 2) if name == "*Isometric" else (1, 1)
            view.ScaleRatio = tuple(float(value) for value in scales[name])
        return scales

    monkeypatch.setattr(configured, "_fit_views", fit)
    texts = []
    literal_note = configured._literal_note

    def note(adapter, text, x, y):
        texts.append(text)
        return literal_note(adapter, text, x, y)

    monkeypatch.setattr(configured, "_literal_note", note)
    finalizations = []

    async def finalize(_adapter, outputs, *, settled_checks, **kwargs):
        finalizations.append(kwargs)
        state.before_settle()
        for settled in settled_checks:
            settled()
        state.finalized = True
        return {"pdf": str(outputs.pdf)}

    monkeypatch.setattr(configured, "finalize_drawing", finalize)
    return state, variants, texts, finalizations


def test_isometric_only_member_shows_its_isometric_and_cites_its_sheet(
    monkeypatch, tmp_path
):
    state, variants, texts, finalizations = _isometric_only_sheet(monkeypatch, tmp_path)
    asyncio.run(
        configured.build_purchased_variant_drawing(
            state.adapter,
            state.spec,
            variants=variants,
            item="RAIL KIT",
            purchase_unit="ONE KIT",
            additional_sheet_scales={"RAIL RECEIPT": (1, 2)},
            append_sheets=lambda _adapter: (),
            isometric_only={"Rail": 2},
        )
    )
    assert state.finalized
    assert [(view.ReferencedConfiguration, view.GetOrientationName()) for view in state.views] == [
        ("Rail", "*Isometric"),
        ("Carriage", "*Front"),
        ("Carriage", "*Top"),
        ("Carriage", "*Right"),
        ("Carriage", "*Isometric"),
    ]
    (iso,) = configured.isometric_view_cells(0, 2)
    assert state.views[0]._center == iso[1]
    assert "[1] RAIL  QTY 2 INSTALLED, SEE SHEET 2" in texts
    assert "[2] CARRIAGE  QTY 2 INSTALLED" in texts
    assert "ISOMETRIC  1:2" in texts
    # ASME Y14.3: a view at the sheet's scale states none; a different one does.
    assert "FRONT" in texts
    assert not any(text.startswith("FRONT  ") for text in texts)
    # The sheet's scale is the first orthographic member's, not the isometric's.
    assert finalizations[0]["sheet_scales"]["REFERENCE"] == (1, 1)


def test_isometric_only_member_refuses_a_restored_orthographic_view(
    monkeypatch, tmp_path
):
    state, variants, _texts, _finalizations = _isometric_only_sheet(monkeypatch, tmp_path)
    state.before_settle = lambda: state.views.append(
        SimpleNamespace(
            ReferencedConfiguration="Rail", GetOrientationName=lambda: "*Front"
        )
    )
    with pytest.raises(RuntimeError, match="missing or extra member views"):
        asyncio.run(
            configured.build_purchased_variant_drawing(
                state.adapter,
                state.spec,
                variants=variants,
                item="RAIL KIT",
                purchase_unit="ONE KIT",
                additional_sheet_scales={"RAIL RECEIPT": (1, 2)},
                append_sheets=lambda _adapter: (),
                isometric_only={"Rail": 2},
            )
        )
    assert not state.finalized


@pytest.mark.parametrize(
    "isometric_only, scales",
    [
        ({"Nope": 2}, {"RECEIPT": (1, 2)}),
        ({"Rail": 1}, {"RECEIPT": (1, 2)}),
        ({"Rail": 3}, {"RECEIPT": (1, 2)}),
        ({"Rail": True}, {"RECEIPT": (1, 2)}),
        ({"Rail": 2}, None),
    ],
)
def test_isometric_only_must_cite_an_appended_sheet_before_native_calls(
    isometric_only, scales
):
    with pytest.raises(ValueError):
        asyncio.run(configured.build_purchased_variant_drawing(
            object(), object(), variants=(("Rail", "RAIL"), ("Carriage", "CARRIAGE")),
            item="KIT", purchase_unit="KIT",
            additional_sheet_scales=scales,
            append_sheets=None if scales is None else (lambda _adapter: ()),
            isometric_only=isometric_only,
        ))


def _variant_sheet(monkeypatch, tmp_path, variants, quantities, total):
    """Only model paths, native view fields and note extents; never real COM."""
    source = tmp_path / "configured-stock.SLDPRT"
    source.touch()
    outputs = {
        extension: tmp_path / f"configured-stock.{suffix}"
        for extension, suffix in (("slddrw", "SLDDRW"), ("pdf", "pdf"), ("png", "png"))
    }
    spec = SimpleNamespace(
        artifact_stem=source.stem,
        source=source,
        source_kind="part",
        layout=DrawingLayout.LANDSCAPE,
        outputs=outputs,
    )
    row = {
        "number": "MHA-SH-VN-50",
        "title": "Configured Stock",
        "stock_name": "One purchased product",
        "supplier": "Test supplier",
        "supplier_skus": ["SKU-1"],
        "material_specification": "Purchased alloy",
        "finish": "As purchased",
        "quantity": total,
        "configuration_quantities": quantities,
        "default_configuration": variants[0][0],
    }
    properties = dict.fromkeys(configured._PROPERTIES, "test value")
    properties.update(
        {
            "Number": row["number"],
            "Title": source.stem,
            "Stock Name": row["stock_name"],
            "Supplier": row["supplier"],
            "Supplier SKUs": "SKU-1",
            "Material Specification": row["material_specification"],
            "Finish": row["finish"],
            **{
                f"{name} Manufacturing Notes": f"{label} ONLY"
                for name, label in variants
            },
        }
    )
    state = SimpleNamespace(
        spec=spec,
        adapter=SimpleNamespace(
            currentModel=_Model(source),
            _get_attr_or_call=lambda target, name: getattr(target, name)(),
        ),
        sheet=_Sheet(),
        opens=[],
        views=[],
        finalized=False,
        before_settle=lambda: None,
        active=[variants[0][0]],
        transitions=[],
    )
    draw = _Drawing()

    def open_read_only(adapter, path, *, label):
        state.opens.append(path)
        return adapter.currentModel

    monkeypatch.setattr(configured, "_open_supplier_source_read_only", open_read_only)
    monkeypatch.setattr(
        configured, "active_configuration_name", lambda _adapter, _model: state.active[0]
    )

    def show(_adapter, _model, name, *, label):
        state.transitions.append(name)
        state.active[0] = name

    monkeypatch.setattr(configured, "_show_reference_configuration", show)
    monkeypatch.setattr(configured._config, "parts", lambda _stem: row)
    monkeypatch.setattr(configured, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(configured, "double_array", tuple)

    def required_properties(_model, names, *, required):
        return properties

    monkeypatch.setattr(configured, "read_required_properties", required_properties)

    def new_drawing(adapter, *, layout, unit):
        adapter.currentModel = draw
        return draw, state.sheet

    monkeypatch.setattr(configured, "new_project_drawing", new_drawing)
    monkeypatch.setattr(
        configured, "stamp_drawing_summary", lambda *_args, **_kwargs: None
    )

    monkeypatch.setattr(
        configured, "_purchased_title_block", lambda *_args, **_kwargs: []
    )

    def place_view(_adapter, path, orientation, x, y, *, scale):
        view = _View(orientation, source, (x, y))
        view.ReferencedConfiguration = "Default"
        state.views.append(view)
        return view

    monkeypatch.setattr(configured, "place_view", place_view)
    monkeypatch.setattr(configured, "iter_views", lambda _adapter: iter(state.views))
    monkeypatch.setattr(
        configured,
        "view_name",
        lambda _adapter, view: f"view-{state.views.index(view)}",
    )
    monkeypatch.setattr(
        configured, "set_hidden_lines_removed", lambda _adapter, _view: None
    )
    monkeypatch.setattr(
        configured,
        "_fit_views",
        lambda _draw, _views, cells: {name: (1, 1) for name, _, _ in cells},
    )

    def literal_note(_adapter, linked, x, y):
        resolved = linked
        for name, value in properties.items():
            resolved = resolved.replace(purchased.property_link(name), value)
        note = _Note(linked, resolved, x, y)
        return note

    monkeypatch.setattr(configured, "_literal_note", literal_note)

    monkeypatch.setattr(
        configured, "add_purchased_footer", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        configured,
        "sheet_drawable_region",
        lambda *_args, **_kwargs: SimpleNamespace(
            xmin=0.0127, ymin=0.0127, xmax=0.4191, ymax=0.2667
        ),
    )

    async def finalize(_adapter, actual_outputs, *, settled_checks, **kwargs):
        state.before_settle()
        for settled_check in settled_checks:
            settled_check()
        state.finalized = True
        return {"pdf": str(actual_outputs.pdf)}

    monkeypatch.setattr(configured, "finalize_drawing", finalize)
    return state


@pytest.mark.parametrize("cut_to_suit", (False, True))
@pytest.mark.parametrize("footer", ("omitted", None, "kit"))
@pytest.mark.parametrize("drift", (None, "linked-text", "resolved-text", "extent"))
def test_configured_footer_override_reaches_native_placement_and_settled_checks(
    monkeypatch, tmp_path, cut_to_suit, footer, drift
):
    variants = (("InnerLink", "INNER"), ("OuterLink", "OUTER"))
    state = _variant_sheet(
        monkeypatch, tmp_path, variants, {"InnerLink": 34, "OuterLink": 33}, 67
    )
    custom = "REFERENCE VIEWS; [2]/[3] AS SUPPLIED; [1] REWORK PER SHEET 2."
    expected = custom if footer == "kit" else purchased._GENERAL_TEXT[cut_to_suit]
    notes = []

    def literal_note(_adapter, text, x, y):
        note = _Note(text, text, x, y)
        notes.append(note)
        return note

    def linked_note(_adapter, name, x, y, *, char_height):
        assert char_height == 0.003
        value = {"Supplier": "Test supplier", "Supplier SKUs": "SKU-1"}[name]
        return _Note(purchased.property_link(name), value, x, y)

    # Run the actual footer author, not an argument-recording substitute.
    monkeypatch.setattr(configured, "add_purchased_footer", purchased.add_purchased_footer)
    monkeypatch.setattr(purchased, "_literal_note", literal_note)
    monkeypatch.setattr(purchased, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(purchased, "add_property_linked_note", linked_note)

    def before_settle():
        general = [note for note in notes if note.GetText() == expected]
        assert len(general) == 1
        note = general[0]
        assert note.PropertyLinkedText == expected
        assert note.GetPosition() == (purchased._NOTE_X, purchased._GENERAL_Y, 0.0)
        if footer == "kit":
            assert not any(
                note.GetText() in purchased._GENERAL_TEXT.values() for note in notes
            )
        if drift == "linked-text":
            note.PropertyLinkedText = "STALE GENERAL LINE"
        elif drift == "resolved-text":
            note._resolved_text = "STALE GENERAL LINE"
        elif drift == "extent":
            # Still inside the sheet border, but beyond the unchanged footer box.
            note._extent = (
                purchased._NOTE_X, purchased._GENERAL_BOTTOM, 0.0,
                purchased._FOOTER_RIGHT + 0.001, purchased._GENERAL_Y, 0.0,
            )

    state.before_settle = before_settle
    options = {"cut_to_suit": cut_to_suit}
    if footer != "omitted":
        options["general_text"] = custom if footer == "kit" else None

    def build():
        return asyncio.run(configured.build_purchased_variant_drawing(
            state.adapter, state.spec, variants=variants, item="TEST KIT",
            purchase_unit="KIT", **options,
        ))

    if drift is None:
        assert build() == {"pdf": str(state.spec.outputs["pdf"])}
        assert state.finalized
    else:
        message = "reserved space" if drift == "extent" else "did not resolve"
        with pytest.raises(RuntimeError, match=message):
            build()
        assert not state.finalized


@pytest.mark.parametrize(
    ("variants", "quantities", "total"),
    [
        (
            (("InnerLink", "INNER"), ("InnerLink", "DUPLICATE")),
            {"InnerLink": 67},
            67,
        ),
        (
            (("InnerLink", "INNER"), ("OuterLink", "OUTER")),
            {"InnerLink": 67},
            67,
        ),
        (
            (("InnerLink", "INNER"), ("OuterLink", "OUTER")),
            {"InnerLink": 34, "OuterLink": 33, "Default": 0},
            67,
        ),
        (
            (("InnerLink", "INNER"), ("OuterLink", "OUTER")),
            {"InnerLink": 34, "OuterLink": 33},
            1,
        ),
    ],
)
def test_configured_sheet_refuses_member_or_quantity_mismatch_before_opening(
    monkeypatch, tmp_path, variants, quantities, total
) -> None:
    state = _variant_sheet(monkeypatch, tmp_path, variants, quantities, total)
    with pytest.raises(ValueError):
        asyncio.run(
            configured.build_purchased_variant_drawing(
                state.adapter,
                state.spec,
                variants=variants,
                item="ANSI 25 CHAIN",
                purchase_unit="ONE CHAIN",
                cut_to_suit=True,
            )
        )
    assert state.opens == []
    assert state.views == []
    assert not state.finalized


@pytest.mark.parametrize(
    ("variants", "quantities", "total"),
    [
        (
            (("InnerLink", "INNER"), ("OuterLink", "OUTER")),
            {"InnerLink": 34, "OuterLink": 33},
            67,
        ),
        (
            (("HoldDownStud", "STUD"), ("TNut", "T-NUT"), ("FlangeNut", "FLANGE NUT")),
            {"HoldDownStud": 4, "TNut": 4, "FlangeNut": 4},
            12,
        ),
    ],
)
def test_configured_sheet_accepts_complete_consistent_native_members(
    monkeypatch, tmp_path, variants, quantities, total
):
    state = _variant_sheet(monkeypatch, tmp_path, variants, quantities, total)
    asyncio.run(
        configured.build_purchased_variant_drawing(
            state.adapter,
            state.spec,
            variants=variants,
            item="PURCHASED PRODUCT",
            purchase_unit="ONE PRODUCT",
        )
    )
    assert state.finalized


_MEMBERS = (("InnerLink", "INNER"), ("OuterLink", "OUTER"))
_MEMBER_QUANTITIES = {"InnerLink": 34, "OuterLink": 33}
_FINALIZE_STAGES = (
    "before_drawing_save",
    "after_drawing_save",
    "before_pdf_save",
    "after_pdf_save",
    "before_drawing_close",
    "after_drawing_close",
)


def _guarded_finalize(monkeypatch, state, mutate=None):
    """finalize_drawing's settled checks, then its save/close checkpoints."""
    stages = []

    async def finalize(_adapter, outputs, *, settled_checks, checkpoint, **_kwargs):
        state.before_settle()
        for settled in settled_checks:
            settled()
        for stage in _FINALIZE_STAGES:
            if mutate is not None:
                mutate(stage)
            checkpoint(stage)
            stages.append(stage)
        state.finalized = True
        return {"pdf": str(outputs.pdf)}

    monkeypatch.setattr(configured, "finalize_drawing", finalize)
    return stages


@pytest.mark.parametrize(
    "drift",
    (None, "dirty", "settled-bytes", "writable", "configuration", "saved-bytes"),
)
def test_configured_sheet_keeps_its_source_read_only_clean_and_unchanged(
    monkeypatch, tmp_path, drift
):
    state = _variant_sheet(monkeypatch, tmp_path, _MEMBERS, _MEMBER_QUANTITIES, 67)
    model = state.adapter.currentModel
    source = state.spec.source

    def mutate(stage):
        if drift == "saved-bytes" and stage == "after_drawing_save":
            source.write_bytes(b"drawing saved the referenced part")

    stages = _guarded_finalize(monkeypatch, state, mutate)
    if drift == "dirty":
        model.GetSaveFlag = lambda: True
    elif drift == "settled-bytes":
        state.before_settle = lambda: source.write_bytes(b"dimension text wrote through")
    elif drift == "writable":
        state.before_settle = lambda: setattr(model, "IsOpenedReadOnly", lambda: False)
    elif drift == "configuration":
        state.before_settle = lambda: state.active.__setitem__(0, "OuterLink")

    def build():
        return asyncio.run(
            configured.build_purchased_variant_drawing(
                state.adapter,
                state.spec,
                variants=_MEMBERS,
                item="PURCHASED PRODUCT",
                purchase_unit="ONE PRODUCT",
            )
        )

    if drift is None:
        build()
        assert state.finalized
        assert stages == list(_FINALIZE_STAGES)
        assert state.opens == [source]
        assert state.transitions == []
        return
    message = "clean before the drawing exists" if drift == "dirty" else "source state changed"
    with pytest.raises(RuntimeError, match=message):
        build()
    assert not state.finalized
    if drift == "dirty":
        assert state.views == []
    if drift == "saved-bytes":
        assert stages == ["before_drawing_save"]


@pytest.mark.parametrize("drift", (None, "reverted", "other"))
def test_configured_sheet_holds_exactly_the_declared_source_member(
    monkeypatch, tmp_path, drift
):
    state = _variant_sheet(monkeypatch, tmp_path, _MEMBERS, _MEMBER_QUANTITIES, 67)
    stages = _guarded_finalize(monkeypatch, state)
    model = state.adapter.currentModel
    seen = []
    placed = []
    events = []
    place_view = configured.place_view

    def place(*args, **kwargs):
        placed.append(state.active[0])
        return place_view(*args, **kwargs)

    monkeypatch.setattr(configured, "place_view", place)
    monkeypatch.setattr(
        configured._telemetry,
        "event",
        lambda name, **attributes: events.append((name, attributes)),
    )

    def annotate(_adapter, configuration, _cells, _views):
        seen.append((configuration, state.active[0]))
        return ()

    def settle():
        # Drawing work dirties the source in memory (#2775: shown and
        # re-blanked part sketches, imported dimension text).
        model.GetSaveFlag = lambda: True
        if drift is not None:
            state.active[0] = "InnerLink" if drift == "reverted" else "Default"

    state.before_settle = settle

    def build():
        return asyncio.run(
            configured.build_purchased_variant_drawing(
                state.adapter,
                state.spec,
                variants=_MEMBERS,
                item="PURCHASED PRODUCT",
                purchase_unit="ONE PRODUCT",
                annotate_member=annotate,
                source_configuration="OuterLink",
            )
        )

    if drift is None:
        build()
        assert stages == list(_FINALIZE_STAGES)
    else:
        with pytest.raises(RuntimeError, match="expected='OuterLink'") as refused:
            build()
        assert not state.finalized
        # The exit check holds the declared member too, without switching back.
        assert "drawing lifecycle exit" in "\n".join(refused.value.__notes__)
    # Active before the first view, for every view and annotation, and left
    # active at exit: the dirty source is never switched back.
    assert placed == ["OuterLink"] * 8
    assert seen == [("InnerLink", "OuterLink"), ("OuterLink", "OuterLink")]
    assert state.transitions == ["OuterLink"]
    left = {None: "OuterLink", "reverted": "InnerLink", "other": "Default"}[drift]
    assert state.active == [left]
    names = [name for name, _ in events]
    assert names == [
        "drawing.reference_source_transition.before",
        "drawing.reference_source_transition.after",
        "drawing.reference_source_exit",
    ]
    before, after, exit_ = (attributes for _, attributes in events)
    assert before == {"configuration": "InnerLink", "requested": "OuterLink", "dirty": False}
    assert after["configuration"] == "OuterLink" and after["dirty"] is False
    assert after["elapsed_s"] >= 0.0
    assert exit_["configuration"] == left
    assert exit_["expected"] == "OuterLink"
    assert exit_["saved_configuration"] == "InnerLink"
    assert exit_["dirty"] is True
    assert exit_["held_s"] >= after["elapsed_s"]


def test_configured_sheet_refuses_an_undepicted_source_member_before_opening(
    monkeypatch, tmp_path
):
    state = _variant_sheet(monkeypatch, tmp_path, _MEMBERS, _MEMBER_QUANTITIES, 67)
    with pytest.raises(ValueError, match="depicted member"):
        asyncio.run(
            configured.build_purchased_variant_drawing(
                state.adapter,
                state.spec,
                variants=_MEMBERS,
                item="PURCHASED PRODUCT",
                purchase_unit="ONE PRODUCT",
                source_configuration="Default",
            )
        )
    assert state.opens == []


@pytest.mark.parametrize("drift", [None, "reference-view", "reference-activation"])
def test_configured_sheet_appends_rework_sheets_before_single_guarded_finalization(
    monkeypatch, tmp_path, drift
):
    variants = (("HoldDownStud", "STUD"), ("TNut", "T-NUT"), ("FlangeNut", "FLANGE NUT"))
    state = _variant_sheet(
        monkeypatch, tmp_path, variants, dict.fromkeys((name for name, _ in variants), 4), 12
    )
    events = []
    active = ["HARDWARE"]
    new_drawing = configured.new_project_drawing

    def create(adapter, *, layout, unit):
        draw, sheet = new_drawing(adapter, layout=layout, unit=unit)
        sheet.GetName = lambda: "HARDWARE"

        def activate(name):
            if drift == "reference-activation" and name == "HARDWARE" and state.views:
                return False
            active[0] = name
            events.append(("activate", name))
            return True

        draw.ActivateSheet = activate
        return draw, sheet

    def blank(_adapter, names, *, label):
        assert not state.views, "extra sheets must copy the blank template, not reference views"
        events.append(("blank", tuple(names)))

    def annotate(_adapter, configuration, cells, views):
        def settled():
            assert active[0] == "HARDWARE"
            events.append(("member", configuration))
        return (settled,)

    def append(adapter):
        assert len(state.views) == 12
        assert adapter.currentModel.ActivateSheet("REWORK")
        events.append(("append",))

        def settled():
            assert adapter.currentModel.ActivateSheet("MEASURE-AND-FIT")
            events.append(("rework-settled",))
        return (settled,)

    finalizations = []

    async def finalize(_adapter, outputs, *, settled_checks, **kwargs):
        finalizations.append(kwargs)
        if drift == "reference-view":
            state.views.pop()
        for settled in settled_checks:
            settled()
        state.finalized = True
        return {"pdf": str(outputs.pdf)}

    monkeypatch.setattr(configured, "new_project_drawing", create)
    monkeypatch.setattr(configured, "create_blank_drawing_sheets", blank)
    monkeypatch.setattr(
        configured, "iter_views",
        lambda _adapter: iter(state.views if active[0] == "HARDWARE" else ()),
    )
    monkeypatch.setattr(configured, "finalize_drawing", finalize)
    scales = {"REWORK": (2.0, 1.0), "MEASURE-AND-FIT": (2.0, 1.0)}

    def build():
        return asyncio.run(configured.build_purchased_variant_drawing(
            state.adapter, state.spec, variants=variants, item="PM KIT",
            purchase_unit="52-PIECE KIT", annotate_member=annotate,
            additional_sheet_scales=scales, append_sheets=append,
        ))

    if drift:
        with pytest.raises(RuntimeError):
            build()
        assert not state.finalized
    else:
        build()
        assert state.finalized
        assert len(finalizations) == 1
        assert finalizations[0]["expected_sheet_names"] == ("HARDWARE", *scales)
        assert finalizations[0]["sheet_scales"] == {"HARDWARE": (1, 1), **scales}
        assert events[0] == ("blank", ("HARDWARE", *scales))
        assert events[-4:] == [
            ("member", "TNut"), ("member", "FlangeNut"),
            ("activate", "MEASURE-AND-FIT"), ("rework-settled",),
        ]


@pytest.mark.parametrize("scales, author", [
    ({"REWORK": (2.0, 1.0)}, None),
    (None, lambda _adapter: ()),
    ({}, lambda _adapter: ()),
])
def test_configured_sheet_refuses_incomplete_append_contract_before_native_calls(scales, author):
    with pytest.raises(ValueError):
        asyncio.run(configured.build_purchased_variant_drawing(
            object(), object(), variants=(), item="KIT", purchase_unit="KIT",
            additional_sheet_scales=scales, append_sheets=author,
        ))


@pytest.mark.parametrize(
    ("count", "offset", "size", "moves", "fits"),
    (
        (2, (-0.003, -0.006), (0.070, 0.004), True, True),
        (3, (-0.003, -0.006), (0.070, 0.004), True, True),
        (2, (0.005, 0.002), (0.070, 0.004), True, True),
        (3, (0.005, 0.002), (0.070, 0.004), True, True),
        (3, (-0.003, -0.006), (0.200, 0.004), True, False),
        (2, (-0.003, -0.006), (0.070, 0.020), True, False),
        (2, (-0.200, -0.006), (0.070, 0.004), False, False),
    ),
    ids=(
        "two-panels-left-overhang",
        "three-panels-left-overhang",
        "two-panels-upper-offset",
        "three-panels-upper-offset",
        "too-wide",
        "too-tall",
        "native-move-ignored",
    ),
)
def test_member_caption_native_extents_are_centered_or_refused(
    monkeypatch, tmp_path, count, offset, size, moves, fits
):
    """Synthetic extent/anchor offsets are not native after-fix evidence."""
    variants = tuple((f"Member{index}", f"MEMBER {index}") for index in range(count))
    quantities = {configuration: 1 for configuration, _ in variants}
    state = _variant_sheet(monkeypatch, tmp_path, variants, quantities, count)
    literal_note = configured._literal_note
    headers = []

    def native_note(adapter, text, x, y):
        note = literal_note(adapter, text, x, y)
        if y > 0.250:
            x0, y0 = x + offset[0], y + offset[1]
            note._extent = (x0, y0, 0.0, x0 + size[0], y0 + size[1], 0.0)
            if not moves:
                note.SetPosition = lambda *_args: True
            headers.append(note)
        return note

    monkeypatch.setattr(configured, "_literal_note", native_note)

    def build():
        return asyncio.run(
            configured.build_purchased_variant_drawing(
                state.adapter,
                state.spec,
                variants=variants,
                item="PURCHASED PRODUCT",
                purchase_unit="ONE PRODUCT",
            )
        )

    if not fits:
        with pytest.raises(RuntimeError):
            build()
        assert not state.finalized
        return

    build()
    assert state.finalized
    for index, note in zip(range(count), headers, strict=True):
        cells = configured.configuration_view_cells(index, count)
        left, right = cells[0][2][0], cells[2][2][2]
        x0, y0, _, x1, y1, _ = note.GetExtent()
        assert (x0 + x1) / 2 == pytest.approx((left + right) / 2)
        assert (y0 + y1) / 2 == pytest.approx((0.255 + 0.264) / 2)
        assert left <= x0 < x1 <= right
        assert 0.255 <= y0 < y1 <= 0.264


def test_configured_sheet_refuses_default_fallback_during_final_readback(
    monkeypatch, tmp_path
):
    variants = (("InnerLink", "INNER"), ("OuterLink", "OUTER"))
    state = _variant_sheet(
        monkeypatch, tmp_path, variants, {"InnerLink": 34, "OuterLink": 33}, 67
    )
    state.before_settle = lambda: setattr(
        state.views[-1], "ReferencedConfiguration", "Default"
    )
    with pytest.raises(RuntimeError):
        asyncio.run(
            configured.build_purchased_variant_drawing(
                state.adapter,
                state.spec,
                variants=variants,
                item="ANSI 25 CHAIN",
                purchase_unit="ONE CHAIN",
                cut_to_suit=True,
            )
        )
    assert not state.finalized


@pytest.mark.parametrize(
    "drift",
    ("first-angle", "property-source", "missing-view", "extra-view", "duplicate-view"),
)
def test_configured_sheet_refuses_projection_or_native_view_inventory_drift(
    monkeypatch, tmp_path, drift
):
    variants = (("InnerLink", "INNER"), ("OuterLink", "OUTER"))
    state = _variant_sheet(
        monkeypatch, tmp_path, variants, {"InnerLink": 34, "OuterLink": 33}, 67
    )

    def change_native_state():
        if drift in ("first-angle", "property-source"):
            values = list(state.sheet.GetProperties2())
            values[4 if drift == "first-angle" else 7] = True
            state.sheet.SetProperties2(*values)
        elif drift == "missing-view":
            state.views.pop()
        elif drift == "extra-view":
            state.views.append(state.views[0])
        else:
            state.views[-1] = state.views[0]

    state.before_settle = change_native_state
    with pytest.raises(RuntimeError):
        asyncio.run(
            configured.build_purchased_variant_drawing(
                state.adapter,
                state.spec,
                variants=variants,
                item="PURCHASED PRODUCT",
                purchase_unit="ONE PRODUCT",
            )
        )
    assert not state.finalized


class _BoundsView:
    def __init__(self):
        self.Position = (0.2, 0.3)
        self.moves = []

    def GetOutline(self):
        raise AssertionError("custom bounds must not read GetOutline")

    def SetViewPosition(self, position, _update):
        self.Position = tuple(position)
        self.moves.append(self.Position)
        return True


@pytest.mark.parametrize(
    "bounds",
    [
        pytest.param((0.0, 0.0, 1.0), id="short"),
        pytest.param((0.0, 0.0, 1.0, 1.0, 2.0), id="long"),
        pytest.param((0.0, 0.0, float("nan"), 1.0), id="nan"),
        pytest.param((0.0, 0.0, 1.0, float("inf")), id="infinity"),
        pytest.param((1.0, 0.0, 0.0, 1.0), id="inverted-x"),
        pytest.param((0.0, 1.0, 1.0, 0.0), id="inverted-y"),
        pytest.param((0.5, 0.5, 0.5, 0.5), id="point-only"),
        pytest.param((0.0, 0.0, "1.0", 1.0), id="nonnumeric"),
    ],
)
@pytest.mark.parametrize("after_center", [False, True], ids=["candidate", "settled"])
def test_fit_group_rejects_malformed_custom_bounds_without_outline_fallback(
    monkeypatch, bounds, after_center
):
    monkeypatch.setattr(purchased, "double_array", tuple)
    view = _BoundsView()
    reads = []

    def read_bounds(actual_view, name):
        assert actual_view is view
        assert name == "*Front"
        reads.append(view.Position)
        if after_center and not view.moves:
            x, y = view.Position
            return (x, y, x + 0.1, y)
        return bounds

    members = [(view, ("*Front", (0.5, 0.5), (0.0, 0.0, 1.0, 1.0)))]
    with pytest.raises(RuntimeError, match=r"\*Front: invalid custom geometry bounds"):
        purchased._fit_group(_Drawing(), members, read_bounds=read_bounds)
    # The candidate must be validated before any positioning. Invalid settled
    # geometry must stop immediately, without another move or scale attempt.
    assert len(view.moves) == int(after_center)
    assert len(reads) == 1 + int(after_center)


@pytest.mark.parametrize("height", [0.0, 0.1])
def test_fit_group_custom_bounds_measures_candidates_and_centered_view(
    monkeypatch, height
):
    monkeypatch.setattr(purchased, "double_array", tuple)
    view = _BoundsView()
    reads = []
    rebuilds = []
    draw = SimpleNamespace(EditRebuild3=lambda: rebuilds.append(True) or True)

    def read_bounds(actual_view, name):
        assert actual_view is view
        assert name == "*Front"
        reads.append((view.ScaleRatio, view.Position, len(rebuilds)))
        ratio = view.ScaleRatio[0] / view.ScaleRatio[1]
        x, y = view.Position
        # Bounds are offset from the view origin, including for a 1D extent.
        return (x + 0.1, y + 0.05, x + 0.1 + 0.2 * ratio, y + 0.05 + height * ratio)

    # Give the 5:1 width (1.0) real clearance; its translated left edge can
    # round just below zero. The 8:1 width (1.6) must still exceed this cell.
    members = [(view, ("*Front", (0.5, 0.5), (-0.05, 0.0, 1.05, 1.0)))]
    assert purchased._fit_group(draw, members, read_bounds=read_bounds) == (5, 1)
    assert [ratio for ratio, _, _ in reads] == [(8.0, 1.0), (5.0, 1.0), (5.0, 1.0)]
    assert [rebuild for _, _, rebuild in reads] == [1, 2, 3]
    assert reads[0][1] == reads[1][1] == (0.2, 0.3)
    assert len(view.moves) == 1
    assert reads[2][1] == view.moves[0]
    assert view.Position == pytest.approx((-0.1, 0.45 - 2.5 * height))


def test_fit_group_custom_bounds_post_center_error_propagates(monkeypatch):
    monkeypatch.setattr(purchased, "double_array", tuple)
    view = _BoundsView()
    error = RuntimeError("settled construction bounds unavailable")
    reads = []

    def read_bounds(actual_view, name):
        assert actual_view is view
        assert name == "*Front"
        reads.append(view.Position)
        if view.moves:
            raise error
        x, y = view.Position
        return (x, y, x + 0.1, y)

    members = [(view, ("*Front", (0.5, 0.5), (0.0, 0.0, 1.0, 1.0)))]
    with pytest.raises(
        RuntimeError, match="settled construction bounds unavailable"
    ) as caught:
        purchased._fit_group(_Drawing(), members, read_bounds=read_bounds)
    assert caught.value is error
    assert len(reads) == 2
    assert len(view.moves) == 1


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


class _PaddedView(_View):
    """A view whose native outline is its geometry at scale plus fixed padding."""

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


def test_short_top_band_lowers_the_row_instead_of_shrinking_every_view(
    monkeypatch, tmp_path
):
    """A #6-32 x 5/8 SHCS's lane-starved Top band no longer forces 1:8."""
    monkeypatch.setattr(purchased, "double_array", tuple)
    margins = {
        "*Front": (0.026, 0.026, 0.026, 0.020),
        "*Top": (0.020, 0.026, 0.020, 0.026),
    }
    sizes = {
        "*Front": (0.0057, 0.0197),
        "*Top": (0.0057, 0.0057),
        "*Right": (0.0057, 0.0197),
        "*Isometric": (0.008, 0.021),
    }

    def fit_cells(lower):
        outer = purchased.fastener_view_cells(0.073, lower=lower)
        inner = purchased.supplier_fit_cells(outer, margins, label="t")
        return purchased._project_from_front(inner)

    def fresh_views(cells):
        return [
            _PaddedView(name, tmp_path / "s.SLDPRT", center, sizes[name])
            for name, center, _ in cells
        ]

    standard = fit_cells(0.0)
    assert purchased._fit_views(_Drawing(), fresh_views(standard), standard)[
        "*Front"
    ] == (1, 8)

    views = fresh_views(standard)
    lowering = purchased._top_lowering(_Drawing(), views, standard)
    assert lowering == pytest.approx(0.0165)
    assert all(view.ScaleRatio == (1.0, 1.0) for view in views)
    lowered = fit_cells(lowering)
    scales = purchased._fit_views(_Drawing(), views, lowered)
    assert scales["*Front"] == scales["*Top"] == scales["*Right"] == (1, 1)
    front, _top, right, _isometric = views
    assert front.Position[1] == pytest.approx(right.Position[1])

    roomy = purchased.fastener_view_cells(0.073)
    assert purchased._top_lowering(_Drawing(), fresh_views(roomy), roomy) == 0.0


def test_top_and_right_project_from_front():
    # The dowel lanes: Front's diameter text left, Top's application lane right.
    outer = purchased.fastener_view_cells(0.073)
    inset = purchased.supplier_fit_cells(
        outer,
        {"*Front": (0.035, 0.024, 0.004, 0.006), "*Top": (0.003, 0.018, 0.075, 0.012)},
        label="t",
    )
    cells = {name: (center, cell) for name, center, cell in inset}
    assert cells["*Front"][0][0] - cells["*Top"][0][0] == pytest.approx(0.0515)
    assert cells["*Front"][0][1] != cells["*Right"][0][1]

    shared = {
        name: (center, cell)
        for name, center, cell in purchased._project_from_front(inset)
    }
    front, top, right = shared["*Front"], shared["*Top"], shared["*Right"]
    assert front[0][0] == top[0][0] == pytest.approx(0.095)
    assert front[0][1] == right[0][1]
    assert front[1] == pytest.approx((0.060, 0.101, 0.130, 0.176))
    assert top[1] == pytest.approx((0.060, 0.216, 0.130, 0.250))
    assert right[1] == pytest.approx((0.225, 0.101, 0.405, 0.176))
    assert shared["*Isometric"] == cells["*Isometric"]
    with pytest.raises(ValueError):
        purchased._project_from_front(
            (
                ("*Front", (0, 0), (0, 0.0, 1, 0.1)),
                ("*Top", (0, 0), (0, 0.2, 1, 0.3)),
                ("*Right", (0, 0), (2, 0.2, 3, 0.3)),
            )
        )


def test_struck_centred_spans_alternate_shelves_outward(monkeypatch):
    import _supplier_text_shelf as shelf

    # Front outline centred at x=0.110, y=0.130; tips at each dimension line.
    lines = {
        "inner@F": ((0.108, 0.100), (0.112, 0.100)),
        "outer@F": ((0.106, 0.092), (0.114, 0.092)),
        "flats@F": ((0.104, 0.170), (0.116, 0.170)),
        "offset@F": ((0.120, 0.090), (0.124, 0.090)),
        "length@F": ((0.140, 0.110), (0.140, 0.150)),
    }

    class Display:
        Type2 = 2

        def __init__(self, name):
            self.name = name

        def GetDimension2(self, _index):
            return SimpleNamespace(FullName=self.name)

    class Annotation:
        def __init__(self, name):
            self.display = Display(name)

        def GetType(self):
            return 4

        def GetSpecificAnnotation(self):
            return self.display

    view = SimpleNamespace(
        GetOutline=lambda: (0.090, 0.110, 0.130, 0.150),
        GetAnnotations=lambda: [Annotation(name) for name in lines],
    )

    def record(_adapter, display):
        tips = lines[display.name]
        return {"display": {"arrows": [(*tip, 0, 0, 0, 0, 0, 0) for tip in tips]}}

    monkeypatch.setattr(shelf, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(shelf, "_supplier_top_record", record)
    monkeypatch.setattr(
        shelf,
        "supplier_top_text_geometry",
        lambda data, horizontal: {
            "tips": tuple(sorted(row[:2] for row in data["display"]["arrows"]))
        },
    )
    monkeypatch.setattr(shelf, "_struck", lambda _actual, _horizontal: True)
    displays, shelves = shelf.struck_supplier_text(None, {"*Front": view})
    assert set(displays) == set(lines)
    assert shelves == {
        "inner@F": (True, "right"),
        "outer@F": (True, "left"),
        "flats@F": (True, "right"),
        "offset@F": (True, "right"),
        "length@F": (False, "right"),
    }


def test_lowered_cells_move_the_row_boundary_only():
    standard = {name: cell for name, _, cell in purchased.fastener_view_cells(0.073)}
    lowered = {
        name: cell
        for name, _, cell in purchased.fastener_view_cells(0.073, lower=0.010)
    }
    for name in ("*Front", "*Right"):
        assert lowered[name][3] == pytest.approx(standard[name][3] - 0.010)
        assert lowered[name][:3] == standard[name][:3]
    for name in ("*Top", purchased._ISOMETRIC):
        assert lowered[name][1] == pytest.approx(standard[name][1] - 0.010)
        assert lowered[name][3] == standard[name][3]
    with pytest.raises(ValueError):
        purchased.fastener_view_cells(0.073, lower=-0.001)


def test_own_witness_through_text_is_struck_and_clear_text_is_not():
    import _supplier_text_shelf as shelf
    from _layout_geometry import Box

    # A 4 mm horizontal span; witnesses rise 20 mm from the part to the line.
    horizontal = ((0.100, 0.050, 0.070), (0.104, 0.050, 0.070))
    across = {"witnesses": horizontal, "text": Box(0.095, 0.060, 0.110, 0.063)}
    assert shelf._struck(across, True)
    shelved = {"witnesses": horizontal, "text": Box(0.1065, 0.060, 0.120, 0.063)}
    assert not shelf._struck(shelved, True)
    beyond_ends = {"witnesses": horizontal, "text": Box(0.095, 0.071, 0.110, 0.074)}
    assert not shelf._struck(beyond_ends, True)
    # A vertical span: witnesses run along x, so text height is what strikes.
    vertical = ((0.100, 0.050, 0.070), (0.103, 0.050, 0.070))
    tall = {"witnesses": vertical, "text": Box(0.060, 0.099, 0.068, 0.104)}
    assert shelf._struck(tall, False)
    beside = {"witnesses": vertical, "text": Box(0.072, 0.099, 0.080, 0.104)}
    assert not shelf._struck(beside, False)


def test_footer_notes_hold_rule_seven_budget():
    assert purchased.note_lines("A\nB\nC", label="t") == ("A", "B", "C")
    with pytest.raises(ValueError):
        purchased.note_lines("A\nB\nC\nD", label="t")
    with pytest.raises(ValueError):
        purchased.check_item("X" * (purchased.MAX_ITEM_CHARS + 1), label="t")
    # More note lines lift the views' bottom row, never below the title block.
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
    with pytest.raises(RuntimeError):
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


def _supplier_native(monkeypatch, *, value=0.0111125, kind=11):
    import _supplier_dimensions as supplier

    monkeypatch.setattr(supplier, "_early_bound", lambda obj, _interface: obj)
    # An mm sheet unless a test sets state.sheet; the rule has its own test.
    monkeypatch.setattr(supplier, "sheet_units", lambda _adapter: state.sheet)
    view = SimpleNamespace()
    native = SimpleNamespace(
        SystemValue=value,
        FullName="Length@SupplierReference@stock.SLDPRT",
        GetSystemValue3=lambda _which, _configuration: (value,),
    )
    annotation = SimpleNamespace(
        Visible=1,
        OwnerType=0,
        Owner=view,
        entities=(object(), object()),
        IsDangling=lambda: False,
        GetType=lambda: 4,
    )
    annotation.GetAttachedEntities3 = lambda: annotation.entities
    annotation.GetAttachedEntityCount3 = lambda: len(annotation.entities)
    annotation.GetAttachedEntityTypes = lambda: (11,) * len(annotation.entities)
    text = {}
    state = SimpleNamespace(
        unit=0, fraction=1, denominator=0, precision=2, rounding=False, sheet="mm"
    )
    display = SimpleNamespace(
        Type2=kind,
        ShowDimensionValue=True,
        ShowParenthesis=False,
        GetDimension2=lambda _index: native,
        GetAnnotation=lambda: annotation,
        GetOverride=lambda: False,
        GetUseDocUnits=lambda: False,
        GetUnits=lambda: state.unit,
        GetPrimaryPrecision2=lambda: state.precision,
        GetFractionBase=lambda: state.fraction,
        GetFractionValue=lambda: state.denominator,
        GetRoundToFraction=lambda: state.rounding,
        GetText=lambda index: text.get(index, ""),
        SetText=lambda index, value: text.__setitem__(index, value),
    )

    def units(_use_document, unit, fraction, denominator, rounding, _decimal_rounding):
        state.unit, state.fraction = unit, fraction
        state.denominator, state.rounding = denominator, rounding
        return 0

    def precision(primary, _dual, _tolerance, _dual_tolerance):
        state.precision = primary
        return 0

    display.SetUnits2 = units
    display.SetPrecision3 = precision
    annotation.GetSpecificAnnotation = lambda: display
    return SimpleNamespace(
        helper=supplier,
        display=display,
        native=native,
        annotation=annotation,
        view=view,
        state=state,
        text=text,
    )


def test_supplier_native_size_preserves_exact_fraction_not_rounded_catalogue_ink(
    monkeypatch,
):
    case = _supplier_native(monkeypatch)
    settings = dict(
        label="7/16 supplier length", units="in", precision=3, expected_mm=11.1125
    )
    case.helper.supplier_reference_dimension(None, case.display, **settings)
    assert case.native.SystemValue == 0.0111125
    assert case.text == {1: "(", 2: " in)", 4: ""}
    with pytest.raises(RuntimeError, match="!= exact expected"):
        case.helper.assert_supplier_reference_dimension(
            None,
            case.display,
            **{**settings, "expected_mm": 0.438 * 25.4},
        )


@pytest.mark.parametrize(
    ("sheet", "units", "denominator", "suffix"),
    (
        ("in", "in", None, ")"),
        ("mm", "in", None, " in)"),
        ("in", "mm", None, " mm)"),
        ("mm", "mm", None, " mm)"),
        ("in", "in", 16, ")"),
        ("mm", "in", 16, ")"),
        ("in", "deg", None, ")"),
    ),
)
def test_supplier_suffix_names_its_unit_only_where_the_sheet_does_not(
    sheet, units, denominator, suffix,
):
    import _supplier_dimensions as supplier

    drawing = SimpleNamespace(Extension=SimpleNamespace(
        GetUserPreferenceInteger=lambda preference, _option: (
            {"in": 3, "mm": 0}[sheet] if preference == 47 else None
        ),
    ))
    *_, actual = supplier._presentation(
        SimpleNamespace(currentModel=drawing), label="supplier size", units=units,
        precision=3, presentation="angle" if units == "deg" else "length",
        fraction_denominator=denominator, callout=None,
        expected_mm=25.4 / 16 if denominator else None,
    )
    assert actual == suffix


def test_supplier_inch_reference_on_an_inch_sheet_sets_and_reads_back_no_suffix(
    monkeypatch,
):
    case = _supplier_native(monkeypatch)
    case.state.sheet = "in"
    settings = dict(label="supplier length", units="in", precision=3, expected_mm=11.1125)
    case.helper.supplier_reference_dimension(None, case.display, **settings)
    assert case.text == {1: "(", 2: ")", 4: ""}
    case.state.sheet = "mm"
    with pytest.raises(RuntimeError, match=r"suffix: actual='\)', expected=' in\)'"):
        case.helper.assert_supplier_reference_dimension(None, case.display, **settings)


def test_supplier_value_uses_referenced_configuration_not_active_model_configuration(
    monkeypatch,
):
    case = _supplier_native(monkeypatch, value=0.008)
    case.native.GetSystemValue3 = lambda _which, configuration: (
        0.0111125 if configuration == "Supplier" else 0.008,
    )
    case.helper.supplier_reference_dimension(
        None,
        case.display,
        label="supplier length",
        units="in",
        precision=3,
        expected_mm=11.1125,
        configuration="Supplier",
    )
    assert case.native.SystemValue == 0.008
    with pytest.raises(RuntimeError, match="!= exact expected"):
        case.helper.assert_supplier_reference_dimension(
            None,
            case.display,
            label="supplier length",
            units="in",
            precision=3,
            expected_mm=11.1125,
            configuration="Installed",
        )


@pytest.mark.parametrize("kind", (1, 3, 4, 5, 7, 8, 13, 16))
def test_supplier_linear_size_rejects_other_native_dimension_types(monkeypatch, kind):
    case = _supplier_native(monkeypatch, kind=kind)
    with pytest.raises(RuntimeError, match="dimension type"):
        case.helper.supplier_reference_dimension(
            None,
            case.display,
            label="supplier length",
            units="in",
            precision=3,
            expected_mm=11.1125,
        )


@pytest.mark.parametrize("value", (float("nan"), float("inf")))
def test_supplier_native_size_rejects_nonfinite_values(monkeypatch, value):
    case = _supplier_native(monkeypatch, value=value)
    with pytest.raises(RuntimeError, match="native value"):
        case.helper.supplier_reference_dimension(
            None,
            case.display,
            label="supplier length",
            units="in",
            precision=3,
            expected_mm=11.1125,
        )


@pytest.mark.parametrize(
    "drift",
    (
        "override",
        "hidden-value",
        "hidden-annotation",
        "dangling",
        "half-detached",
        "sheet-owner",
        "missing-owner",
    ),
)
def test_supplier_settled_reference_rejects_unsound_native_ink(monkeypatch, drift):
    case = _supplier_native(monkeypatch)
    settings = dict(
        label="supplier length", units="in", precision=3, expected_mm=11.1125
    )
    case.helper.supplier_reference_dimension(None, case.display, **settings)
    if drift == "override":
        case.display.GetOverride = lambda: True
    elif drift == "hidden-value":
        case.display.ShowDimensionValue = False
    elif drift == "hidden-annotation":
        case.annotation.Visible = 3
    elif drift == "dangling":
        case.annotation.IsDangling = lambda: True
    elif drift == "half-detached":
        case.annotation.entities = (case.annotation.entities[0], None)
    elif drift == "sheet-owner":
        case.annotation.OwnerType = 1
    else:
        case.annotation.Owner = None
    with pytest.raises(RuntimeError, match="supplier"):
        case.helper.assert_supplier_reference_dimension(None, case.display, **settings)


def test_supplier_thread_identification_keeps_native_nominal_major_value(monkeypatch):
    case = _supplier_native(monkeypatch, value=0.0028448)
    settings = dict(
        label="nominal thread major",
        units="in",
        precision=3,
        expected_mm=2.8448,
        presentation="diameter",
        callout="4-40 THREAD\nNOMINAL MAJOR",
    )
    case.helper.supplier_reference_dimension(None, case.display, **settings)
    assert case.native.SystemValue == 0.0028448
    assert case.display.ShowDimensionValue
    assert case.text[1] == "(<MOD-DIAM>"
    assert case.text[4] == "4-40 THREAD\nNOMINAL MAJOR"
    case.text[4] = "8-32 THREAD"
    with pytest.raises(RuntimeError, match="presentation differs"):
        case.helper.assert_supplier_reference_dimension(None, case.display, **settings)


@pytest.mark.parametrize(
    "field",
    (
        "use_document_units", "units", "primary_precision", "fraction_base",
        "show_parentheses", "override", "show_native_value", "prefix", "suffix",
        "below_callout",
    ),
)
def test_supplier_presentation_rejects_each_actual_drift_without_repair(monkeypatch, field):
    case = _supplier_native(monkeypatch)
    settings = dict(label="supplier thickness", units="in", precision=3, expected_mm=11.1125)
    case.helper.supplier_reference_dimension(None, case.display, **settings)
    mutations = {
        "use_document_units": lambda: setattr(case.display, "GetUseDocUnits", lambda: True),
        "units": lambda: setattr(case.state, "unit", 0),
        "primary_precision": lambda: setattr(case.state, "precision", 2),
        "fraction_base": lambda: setattr(case.state, "fraction", 2),
        "show_parentheses": lambda: setattr(case.display, "ShowParenthesis", True),
        "override": lambda: setattr(case.display, "GetOverride", lambda: True),
        "show_native_value": lambda: setattr(case.display, "ShowDimensionValue", False),
        "prefix": lambda: case.text.__setitem__(1, "CHANGED PREFIX"),
        "suffix": lambda: case.text.__setitem__(2, "CHANGED SUFFIX"),
        "below_callout": lambda: case.text.__setitem__(4, "FOREIGN CALLOUT"),
    }
    mutations[field]()
    source_value = case.native.SystemValue
    source_text = dict(case.text)
    source_state = vars(case.state).copy()
    with pytest.raises(RuntimeError, match="native supplier presentation differs from its source") as error:
        case.helper.assert_supplier_reference_dimension(None, case.display, **settings)
    assert f"({field}: actual=" in str(error.value)
    assert ", expected=" in str(error.value)
    assert case.native.SystemValue == source_value
    assert case.text == source_text
    assert vars(case.state) == source_state


def test_supplier_presentation_first_mismatch_does_not_read_a_later_failing_field(monkeypatch):
    case = _supplier_native(monkeypatch)
    settings = dict(label="supplier thickness", units="in", precision=3, expected_mm=11.1125)
    case.helper.supplier_reference_dimension(None, case.display, **settings)
    case.display.GetUseDocUnits = lambda: True

    def later_reader():
        raise AssertionError("a later reader must not hide the first mismatch")

    case.display.GetUnits = later_reader
    with pytest.raises(RuntimeError, match="use_document_units: actual=True, expected=False"):
        case.helper.assert_supplier_reference_dimension(None, case.display, **settings)


def test_supplier_presentation_retains_first_native_reader_exception(monkeypatch):
    case = _supplier_native(monkeypatch)
    settings = dict(label="supplier thickness", units="in", precision=3, expected_mm=11.1125)
    case.helper.supplier_reference_dimension(None, case.display, **settings)
    original = RuntimeError("native units getter refused")

    def first_reader():
        raise original

    def later_reader():
        raise AssertionError("a later reader must not mask the native exception")

    case.display.GetUnits = first_reader
    case.display.GetPrimaryPrecision2 = later_reader
    with pytest.raises(RuntimeError) as error:
        case.helper.assert_supplier_reference_dimension(None, case.display, **settings)
    assert error.value is original


def test_supplier_presentation_retains_native_empty_callout_normalization(monkeypatch):
    case = _supplier_native(monkeypatch)
    settings = dict(label="supplier thickness", units="in", precision=3, expected_mm=11.1125)
    case.helper.supplier_reference_dimension(None, case.display, **settings)
    case.text[4] = None
    case.helper.assert_supplier_reference_dimension(None, case.display, **settings)
    assert case.text[4] is None
    assert case.native.SystemValue == 0.0111125


def _linear_supplier_pin_reference(monkeypatch, *, axis=1):
    import _drawing_edge_dimensions as edge_dimensions
    import _supplier_pin_drawing as pins

    length_mm = 4.7625 if axis == 1 else 15.875
    case = _supplier_native(monkeypatch, value=length_mm / 1000.0, kind=2)
    monkeypatch.setattr(pins, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(edge_dimensions, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(edge_dimensions._sw_type_info, "early_bound_or_flag",
                        lambda value, _interface, *_members: value)
    monkeypatch.setattr(pins, "model_points_in_view",
                        lambda _adapter, _view, points, **_kw: [(0.1+x, 0.1+y) for x, y, _z in points])
    monkeypatch.setattr(pins, "add_edge_dimension", lambda *_args, **_kw: case.display)
    case.arc_conditions = {1: 0, 2: 0}
    case.native.GetArcEndCondition = lambda index: case.arc_conditions[index]
    case.native.GetSystemValue3 = lambda *_args: (case.native.SystemValue,)
    case.native.Tolerance = SimpleNamespace(Type=0)

    def forbidden_arc_setter(*_args):
        raise AssertionError("linear end-plane picks are not arc-ended dimensions")

    case.native.SetArcEndCondition = forbidden_arc_setter
    case.annotation.GetAttachedEntityTypes = lambda: (1,) * len(case.annotation.entities)
    case.view.GetOutline = lambda: (0.09, 0.09, 0.11, 0.12)
    case.adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda left, right: int(left is right)))
    stations = (0.0, length_mm) if axis == 1 else (-length_mm / 2.0, length_mm / 2.0)
    circles = [
        SimpleNamespace(
            circle=((0.0, station, 0.0, 0.0, 1.0, 0.0, 1.190625) if axis == 1 else
                    (station, 0.0, 0.0, 1.0, 0.0, 0.0, 1.190625)), edge=entity,
        ) for station, entity in zip(stations, case.annotation.entities)
    ]
    source = SimpleNamespace(sku="supplier-pin", length_mm=length_mm, units="in", length_precision=3)
    case.length_mm = length_mm
    case.display, case.assert_length = pins._supplier_length(
        case.adapter, case.view, circles, source, axis=axis, stations=stations,
    )
    return case


@pytest.mark.parametrize("axis", (0, 1), ids=("spring", "dowel"))
def test_supplier_linear_pin_retains_observed_full_length_and_none_end_conditions(monkeypatch, axis):
    case = _linear_supplier_pin_reference(monkeypatch, axis=axis)
    case.assert_length(case.display)
    assert case.native.SystemValue == case.length_mm / 1000.0
    assert case.arc_conditions == {1: 0, 2: 0}
    assert case.native.Tolerance.Type == 0


@pytest.mark.parametrize("drift,error", [
    ("condition", None),
    ("value", "native value"),
    ("attachment", "named entities"),
    ("tolerance", "unsourced tolerance"),
    ("type", None),
])
@pytest.mark.parametrize("axis", (0, 1), ids=("spring", "dowel"))
def test_supplier_linear_pin_retains_real_value_attachment_and_condition_guards(
    monkeypatch, drift, error, axis,
):
    case = _linear_supplier_pin_reference(monkeypatch, axis=axis)
    if drift == "condition":
        case.arc_conditions[2] = 1
    elif drift == "value":
        case.native.SystemValue += 0.0001
    elif drift == "attachment":
        case.annotation.entities = (case.annotation.entities[0], object())
    elif drift == "tolerance":
        case.native.Tolerance.Type = 2
    else:
        case.display.Type2 = 6
    native_value = case.native.SystemValue
    with pytest.raises(RuntimeError, match=error):
        case.assert_length(case.display)
    assert case.native.SystemValue == native_value


def _supplier_pin_layout_placement(monkeypatch, *, family, outline):
    import _supplier_pin_drawing as pins

    # Isolate native authoring, not the production station calculation. The
    # returned station drives the real audit consumer against recorded R43 ink.
    monkeypatch.setattr(pins, "scan_view_edges", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pins, "_axis_circles", lambda *_args, **_kwargs: ())
    length = SimpleNamespace(GetDimension2=lambda _index: SimpleNamespace(FullName="Length@View"))
    monkeypatch.setattr(pins, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(pins, "_supplier_length", lambda *_args, **_kwargs: (length, None))
    monkeypatch.setattr(pins, "_supplier_diameter", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(pins, "_settled_pin_check", lambda *_args, **_kwargs: lambda: None)
    if family == "spring":
        monkeypatch.setattr(pins, "shelve_supplier_text", lambda *_args: {})
    placements = {}

    def import_references(_adapter, _view, _source, keep):
        placements.update(keep)
        return {name: (None, None) for name in keep}

    monkeypatch.setattr(pins, "_import_model_references", import_references)
    view = SimpleNamespace(GetOutline=lambda: outline, Position=(0.2875, 0.143))
    source = SimpleNamespace(
        sku="R43 layout", length_mm=12.7, wall_mm=0.3048,
        wall_precision=3, application_hole_limits=(1.5748, 1.651),
        application_hole_precision=3,
    )
    if family == "dowel":
        pins.add_supplier_dowel_dimensions(None, {"*Front": view, "*Top": view}, source)
        return placements[pins.DIAMETER_DIMENSION]
    pins.add_supplier_spring_pin_dimensions(None, {"*Front": view, "*Right": view}, source)
    return placements[pins.MATING_HOLE_DIMENSION]


def _supplier_spring_pin_imports(monkeypatch, *, limits, precision, shelf_error=None):
    import _supplier_pin_drawing as pins

    length = SimpleNamespace(
        GetDimension2=lambda _index: SimpleNamespace(FullName="SupplierLength@Drawing View1"),
    )
    monkeypatch.setattr(pins, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(pins, "scan_view_edges", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pins, "_axis_circles", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(pins, "_supplier_length", lambda *_args, **_kwargs: (length, "length check"))
    monkeypatch.setattr(pins, "_supplier_diameter", lambda *_args, **_kwargs: ("diameter", "diameter check"))
    imports, settled, events = [], {}, []

    def import_references(_adapter, _view, _source, keep):
        imports.append(tuple(keep))
        events.append("import")
        return {name: (name, f"{name} check") for name in keep}

    def settle(_adapter, _views, references, *, expected_count, label):
        settled.update(references=references, expected_count=expected_count, label=label)
        return lambda: events.append("settled census")

    def shelve(_adapter, displays, shelves):
        events.append(("shelve", dict(displays), dict(shelves)))
        return {"stations": "measured"}

    def assert_shelves(_adapter, displays, shelves, stations):
        events.append(("assert shelves", dict(displays), dict(shelves), stations))
        if shelf_error is not None:
            raise RuntimeError(shelf_error)

    monkeypatch.setattr(pins, "_import_model_references", import_references)
    monkeypatch.setattr(pins, "_settled_pin_check", settle)
    monkeypatch.setattr(pins, "shelve_supplier_text", shelve)
    monkeypatch.setattr(pins, "assert_supplier_shelves", assert_shelves)
    view = SimpleNamespace(GetOutline=lambda: (0.27, 0.13, 0.30, 0.15), Position=(0.2875, 0.143))
    source = SimpleNamespace(
        sku="spring-pin", length_mm=12.7, wall_mm=0.3048, wall_precision=3,
        application_hole_limits=limits, application_hole_precision=precision,
    )
    check = pins.add_supplier_spring_pin_dimensions(None, {"*Front": view, "*Right": view}, source)
    return SimpleNamespace(
        imports=imports, settled=settled, events=events, length=length, check=check,
    )


def test_supplier_spring_pin_without_application_hole_imports_only_the_wall(monkeypatch):
    import _supplier_pin_drawing as pins

    case = _supplier_spring_pin_imports(monkeypatch, limits=None, precision=None)
    assert case.imports == [(pins.WALL_DIMENSION,)]
    assert case.settled == {
        "references": [
            ("*Right", "diameter", "diameter check"), ("*Front", case.length, "length check"),
            ("*Right", pins.WALL_DIMENSION, f"{pins.WALL_DIMENSION} check"),
        ],
        "expected_count": 3, "label": "spring-pin",
    }


def test_supplier_spring_pin_with_application_hole_still_imports_the_mating_hole(monkeypatch):
    import _supplier_pin_drawing as pins

    case = _supplier_spring_pin_imports(
        monkeypatch, limits=(0.062, 0.065), precision=3,
    )
    assert case.imports == [(pins.WALL_DIMENSION, pins.MATING_HOLE_DIMENSION)]
    assert case.settled["expected_count"] == 4
    assert case.settled["references"][2:] == [
        ("*Right", pins.WALL_DIMENSION, f"{pins.WALL_DIMENSION} check"),
        ("*Right", pins.MATING_HOLE_DIMENSION, f"{pins.MATING_HOLE_DIMENSION} check"),
    ]


@pytest.mark.parametrize("limits,precision", [(None, None), ((0.062, 0.065), 3)],
                         ids=("strap-pin", "cup-pin"))
def test_supplier_spring_pin_length_text_shelves_right_and_settles_measured(
    monkeypatch, limits, precision,
):
    """Machinist review: the FRONT length's own line ran through its "(.500)"."""
    case = _supplier_spring_pin_imports(monkeypatch, limits=limits, precision=precision)
    name = "SupplierLength@Drawing View1"
    shelf = ({name: case.length}, {name: (True, "right")})
    # The shared measured shelf, once, after every reference is in place.
    assert case.events == ["import", ("shelve", *shelf)]
    case.check()
    assert case.events[2:] == [
        "settled census", ("assert shelves", *shelf, {"stations": "measured"}),
    ]


def test_supplier_spring_pin_settled_check_refuses_a_lost_length_shelf(monkeypatch):
    case = _supplier_spring_pin_imports(
        monkeypatch, limits=None, precision=None,
        shelf_error="SupplierLength@Drawing View1: supplier text shelf is not clear",
    )
    with pytest.raises(RuntimeError, match="supplier text shelf is not clear"):
        case.check()


def test_supplier_dowel_length_text_is_not_shelved(monkeypatch):
    # The dowel's vertical length prints its level text beside the line, clear.
    import _supplier_pin_drawing as pins

    def forbidden(*_args):
        raise AssertionError("dowel length text sits beside its vertical line")

    monkeypatch.setattr(pins, "shelve_supplier_text", forbidden)
    _supplier_pin_layout_placement(
        monkeypatch, family="dowel", outline=(0.065412, 0.219412, 0.092588, 0.246588),
    )


def test_spring_pin_front_reserves_its_length_shelf_lane():
    import _supplier_pin_drawing as pins
    from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M

    # The knob-cup pin's "(0.625 in)" printed about 19.5 mm wide at 5:1.
    assert pins.SPRING_PIN_SUPPLIER_MARGINS["*Front"][2] >= 0.0195 + CLEAR_GAP_M + PLACE_SETTLE_M


@pytest.mark.parametrize("limits,precision", [((0.062, 0.065), None), (None, 3)])
def test_supplier_spring_pin_refuses_a_half_declared_application_hole(monkeypatch, limits, precision):
    import _supplier_pin_drawing as pins

    scans = []
    monkeypatch.setattr(pins, "scan_view_edges", lambda *_args, **_kwargs: scans.append(1))
    source = SimpleNamespace(
        sku="spring-pin", length_mm=12.7, wall_mm=0.3048, wall_precision=3,
        application_hole_limits=limits, application_hole_precision=precision,
    )
    with pytest.raises(ValueError, match="incomplete supplier mating-hole reference"):
        pins.add_supplier_spring_pin_dimensions(None, {"*Front": None, "*Right": None}, source)
    assert scans == []


@pytest.mark.parametrize(
    "family,outline,old_position,text_box,line",
    [
        pytest.param(
            "dowel", (0.065412, 0.219412, 0.092588, 0.246588),
            (0.110588, 0.233), (0.0881, 0.2286, 0.1331, 0.2331),
            (0.079, 0.233, 0.099, 0.233), id="locating-pin",
        ),
        pytest.param(
            "dowel", (0.070237, 0.224237, 0.087763, 0.241763),
            (0.105763, 0.233), (0.0832, 0.2286, 0.1283, 0.2331),
            (0.079, 0.233, 0.084, 0.233), id="latch-pin-container",
        ),
        pytest.param(
            "dowel", (0.070237, 0.224237, 0.087763, 0.241763),
            (0.105763, 0.233), (0.0832, 0.2286, 0.1283, 0.2331),
            (0.079, 0.233, 0.084, 0.233), id="knife-dowel-container",
        ),
        pytest.param(
            "spring", (0.2779432, 0.1334433, 0.2970568, 0.1525568),
            (0.3165, 0.112), (0.2842854, 0.1029181, 0.3487146, 0.1064181),
            (0.3090623, 0.1397694, 0.2826979, 0.1019181), id="strap-spring-pin",
        ),
        pytest.param(
            "spring", (0.2779432, 0.1334433, 0.2970568, 0.1525568),
            (0.3165, 0.112), (0.2842854, 0.1029181, 0.3487146, 0.1064181),
            (0.3090623, 0.1397694, 0.2826979, 0.1019181), id="cup-spring-pin",
        ),
    ],
)
def test_supplier_pin_replays_r43_collision_clearance_without_moving_witnesses(
    monkeypatch, family, outline, old_position, text_box, line,
):
    """5049b24 R43 native audit records, in sheet metres.

    Locating-pin ink and both spring qualifiers are genuinely struck. Latch
    and knife records are conservative container findings, not glyph strikes.
    This replay retains those containers rather than weakening the audit.
    """
    from _layout_audit import find_lines_through_own_text
    from _layout_geometry import (
        AnnotationGeometry, Box, Segment, SheetGeometry, find_text_on_line,
    )
    import _supplier_pin_drawing as pins

    position = _supplier_pin_layout_placement(monkeypatch, family=family, outline=outline)

    def replay(station):
        dx, dy = station[0] - old_position[0], station[1] - old_position[1]
        box = Box(text_box[0] + dx, text_box[1] + dy, text_box[2] + dx, text_box[3] + dy)
        if family == "dowel":
            annotations = (
                AnnotationGeometry("R43 diameter", "dim", "Top", (box,)),
                AnnotationGeometry("R43 center mark", "center-mark", "Top", (),
                                   (Segment(*line),)),
            )
            finder = find_text_on_line
        else:
            # Keep the actual circle-end witness fixed. Only the text end of
            # its leader follows the moved block; translating both ends would
            # falsely move the model witness and hide this failure.
            leader = Segment(line[0], line[1], line[2] + dx, line[3] + dy, "dim-line")
            annotations = (AnnotationGeometry(
                "R43 application qualifier", "dim", "Right", (box,), (leader,),
            ),)
            finder = find_lines_through_own_text
        sheet = SheetGeometry("R43", 0.4318, 0.2794, None, annotations=annotations)
        return finder(sheet), box

    old_findings, _ = replay(old_position)
    assert len(old_findings) == 1  # The actual old placement is a negative control.
    findings, box = replay(position)
    assert not findings
    if family == "dowel":
        assert box.xmax < outline[2] + pins.DOWEL_SUPPLIER_MARGINS["*Top"][2]
    else:
        right_cell = next(cell for name, _center, cell in purchased.fastener_view_cells(0.018)
                          if name == "*Right")
        assert right_cell[0] < box.xmin < box.xmax < right_cell[2]
        assert right_cell[1] < box.ymin < box.ymax < right_cell[3]


@pytest.mark.parametrize("denominator", (True, 1.5, 0, 3))
def test_supplier_fraction_requires_an_exact_integer_power_of_two(
    monkeypatch, denominator
):
    case = _supplier_native(monkeypatch, value=0.00238125)
    with pytest.raises(ValueError, match="power of two"):
        case.helper.supplier_reference_dimension(
            None,
            case.display,
            label="supplier head height",
            units="in",
            precision=3,
            expected_mm=2.38125,
            fraction_denominator=denominator,
        )


def test_supplier_fraction_cannot_round_a_nonrepresentable_native_size(monkeypatch):
    case = _supplier_native(monkeypatch, value=0.003)
    with pytest.raises(ValueError, match="cannot display that inch fraction"):
        case.helper.supplier_reference_dimension(
            None,
            case.display,
            label="supplier head height",
            units="in",
            precision=3,
            expected_mm=3.0,
            fraction_denominator=32,
        )


@pytest.mark.parametrize(
    "drift",
    (
        "model-import",
        "missing",
        "duplicate",
        "unknown",
        "view-owner",
        "feature-membership",
        "model-dimension",
        "qualified-model-name",
        "source-dimension-unsupported",
        "attachment-owner",
        "null-attachment",
        "source-sketch-error",
        "attachment-read-error",
        "attachment-type-count",
        "source-inventory-error",
        "source-null-member",
        "mapping-error",
        "mapping-null",
        "mapping-foreign",
        "duplicate-member",
        "duplicate-mapping",
        "source-self",
        "mapped-self",
        "target-self",
        "ambiguous-member",
        "unsupported-comparison",
        "mapping-other-unsupported",
        "census-error",
        "capture-error",
        "configuration",
        "orientation",
    ),
)
def test_supplier_final_inventory_reacquires_and_rejects_source_or_inventory_drift(
    monkeypatch, drift
):
    import _supplier_screw_dimensions as screws

    case = _supplier_native(monkeypatch)
    monkeypatch.setattr(screws, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(screws, "_binding", lambda _adapter, view: view.binding)
    monkeypatch.setattr(screws, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(screws, "iter_views", lambda adapter: adapter.views)
    captures = []

    def capture(_adapter, _label, _message, **context):
        captures.append(context)
        if drift == "capture-error":
            raise OSError("forensic destination unavailable")
        raise context["exception"]

    monkeypatch.setattr(screws._seat_forensics, "capture_com_failure", capture)
    source_points = tuple(SimpleNamespace(native_identity=object()) for _ in range(2))
    drawing_points = tuple(SimpleNamespace(native_identity=object()) for _ in range(2))
    # Separate COM wrappers identify the same native drawing-context points.
    attachment_points = tuple(
        SimpleNamespace(native_identity=point.native_identity)
        for point in drawing_points
    )
    case.annotation.entities = attachment_points
    source_sketch = SimpleNamespace(
        GetSketchPoints2=lambda: source_points,
        GetSketchSegments=lambda: (),
    )
    raw_source_display = object()
    source_dimension = SimpleNamespace(**vars(case.native))
    source_display = SimpleNamespace(
        GetDimension2=lambda _index: source_dimension,
        GetAnnotation=lambda: pytest.fail("source annotation mapping is not required"),
    )
    source_feature = SimpleNamespace(
        Name="SupplierReference",
        GetTypeName2=lambda: "ProfileFeature",
        GetSpecificFeature2=lambda: source_sketch,
        GetFirstDisplayDimension=lambda: raw_source_display,
        GetNextDisplayDimension=lambda _display: None,
    )
    bind = screws._bind

    def bind_source_display(raw, interface):
        if raw is raw_source_display:
            assert interface == "IDisplayDimension"
            return source_display
        return bind(raw, interface)

    monkeypatch.setattr(screws, "_bind", bind_source_display)
    model = SimpleNamespace(
        Parameter=lambda _name: source_dimension,
        FeatureByName=lambda _name: source_feature,
    )
    # A distinct IFeature wrapper is not the native source-dimension proof.
    case.native.GetFeatureOwner = lambda: SimpleNamespace(
        Name="SupplierReference", GetTypeName2=lambda: "ProfileFeature"
    )
    case.view.name = "Drawing View1"
    case.view.binding = (case.view.name, "stock.SLDPRT", "Default")
    case.view.ReferencedDocument = model
    case.view.GetOrientationName = lambda: "*Front"
    forward_map = {
        id(source): mapped
        for source, mapped in zip(source_points, drawing_points, strict=True)
    }
    case.view.GetCorresponding = lambda obj: forward_map.get(id(obj))
    annotations = [case.annotation]
    case.view.GetAnnotations = lambda: annotations

    def same(left, right):
        # MSC returns swObjectUnsupported across source/drawing dimensions.
        if (left is case.native and right is source_dimension) or (
            left is source_dimension and right is case.native
        ):
            return 2
        return int(
            getattr(left, "native_identity", left)
            is getattr(right, "native_identity", right)
        )

    adapter = SimpleNamespace(views=[case.view], swApp=SimpleNamespace(IsSame=same))
    settings = dict(
        dimensions=(("Length", 11.1125, "horizontal"),),
        formats={"Length": (3, "length", None, None)},
        _bindings={"*Front": case.view.binding},
    )
    case.helper.supplier_reference_dimension(
        adapter,
        case.display,
        label="Length@SupplierReference",
        units="in",
        precision=3,
        expected_mm=11.1125,
        configuration="Default",
    )
    if drift == "model-import":
        def unsupported_drawing_attachment(*_args):
            pytest.fail("imported model association must not inspect drawing point wrappers")

        case.annotation.GetAttachedEntities3 = unsupported_drawing_attachment
        case.annotation.GetAttachedEntityTypes = unsupported_drawing_attachment
        case.view.GetCorresponding = unsupported_drawing_attachment
        source_feature.GetSpecificFeature2 = unsupported_drawing_attachment
        assert screws._assert_dimension_source(
            adapter, case.view, case.display, name="Length", feature="SupplierReference"
        ) is source_feature
        return

    assert set(
        screws.assert_supplier_screw(adapter, {"*Front": case.view}, **settings)
    ) == {"Length"}
    original_attachment_error = None
    if drift == "missing":
        annotations.clear()
    elif drift == "duplicate":
        annotations.append(case.annotation)
    elif drift == "unknown":
        case.native.FullName = "Unrequested@SupplierReference@stock.SLDPRT"
    elif drift == "view-owner":
        case.annotation.Owner = object()
    elif drift == "feature-membership":
        # Identical names and values are insufficient without native identity.
        different_dimension = SimpleNamespace(**vars(case.native))
        source_display.GetDimension2 = lambda _index: different_dimension
    elif drift == "model-dimension":
        model.Parameter = lambda _name: object()
    elif drift == "qualified-model-name":
        case.native.FullName = "Length@SupplierReference@unrelated.SLDPRT"
    elif drift == "source-dimension-unsupported":
        adapter.swApp.IsSame = lambda left, right: (
            2 if left is right is source_dimension else same(left, right)
        )
    elif drift in {"attachment-owner", "capture-error"}:
        case.annotation.entities = (
            SimpleNamespace(native_identity=object()),
            attachment_points[1],
        )
    elif drift == "null-attachment":
        case.annotation.entities = (None, attachment_points[1])
    elif drift in {"source-sketch-error", "attachment-read-error"}:
        original_attachment_error = RuntimeError(
            "supplier attachment acquisition failed"
        )

        def unreadable_attachment():
            raise original_attachment_error

        if drift == "source-sketch-error":
            source_feature.GetSpecificFeature2 = unreadable_attachment
        else:
            case.annotation.GetAttachedEntities3 = unreadable_attachment
    elif drift == "attachment-type-count":
        case.annotation.GetAttachedEntityTypes = lambda: (11,)
    elif drift == "source-inventory-error":

        def unreadable_inventory():
            raise RuntimeError("source sketch inventory unreadable")

        source_sketch.GetSketchPoints2 = unreadable_inventory
    elif drift == "source-null-member":
        source_sketch.GetSketchPoints2 = lambda: (None, source_points[1])
    elif drift == "mapping-error":

        def unreadable_mapping(obj):
            if obj is source_points[0]:
                raise RuntimeError("source point mapping unreadable")
            return forward_map.get(id(obj))

        case.view.GetCorresponding = unreadable_mapping
    elif drift == "mapping-null":
        forward_map[id(source_points[0])] = None
    elif drift == "mapping-foreign":
        forward_map[id(source_points[0])] = SimpleNamespace(native_identity=object())
    elif drift == "duplicate-member":
        case.annotation.entities = (attachment_points[0],) * 2
    elif drift == "duplicate-mapping":
        forward_map[id(source_points[1])] = drawing_points[0]
    elif drift in {
        "source-self",
        "mapped-self",
        "target-self",
        "ambiguous-member",
        "unsupported-comparison",
        "mapping-other-unsupported",
    }:
        original_comparison = adapter.swApp.IsSame

        def comparison(left, right):
            if drift == "source-self" and left is right is source_points[0]:
                return 2
            if drift == "mapped-self" and left is right is drawing_points[0]:
                return 2
            if drift == "target-self" and left is right is attachment_points[0]:
                return 2
            if (
                drift == "mapping-other-unsupported"
                and left is drawing_points[0]
                and right is drawing_points[1]
            ):
                return 2
            if left is attachment_points[0] and right is drawing_points[1]:
                if drift == "unsupported-comparison":
                    return 2  # swObjectUnsupported is not a known negative.
                if drift == "ambiguous-member":
                    return 1
            return original_comparison(left, right)

        adapter.swApp.IsSame = comparison
    elif drift == "census-error":
        original_attachment_error = RuntimeError(
            "supplier correspondence census failed"
        )

        def refuse(*_args, **_kwargs):
            raise original_attachment_error

        monkeypatch.setattr(screws, "_attachment_correspondence", refuse)
    elif drift == "configuration":
        case.view.binding = (case.view.name, "stock.SLDPRT", "Other")
    else:
        case.view.GetOrientationName = lambda: "*Top"
    with pytest.raises(RuntimeError, match="supplier") as caught:
        screws.assert_supplier_screw(adapter, {"*Front": case.view}, **settings)
    capture_expected = drift not in {
        "missing",
        "duplicate",
        "unknown",
        "view-owner",
        "feature-membership",
        "model-dimension",
        "qualified-model-name",
        "source-dimension-unsupported",
        "configuration",
        "orientation",
    }
    assert len(captures) == int(capture_expected)
    if captures:
        assert captures[0]["sheet_png"] is True
        assert captures[0]["sketch"] is (
            None if drift == "source-sketch-error" else source_sketch
        )
        assert captures[0]["exception"] is caught.value
        context = captures[0]["attachment_context"]
        census = context["attachment_correspondence"]
        if original_attachment_error is not None:
            assert caught.value is original_attachment_error
            assert census == {}
            assert context["attachment_error"] == {
                "member": "attachment proof",
                "error_type": "RuntimeError",
                "message": str(original_attachment_error),
            }
        elif drift == "attachment-type-count":
            assert census == {}
            assert "lost its source sketch attachments" in str(caught.value)
        else:
            assert len(census["attachments"]) == 2
            first, second = census["attachments"]
            assert first["proven"] is False
            mapping_invalid = drift in {
                "source-inventory-error",
                "source-null-member",
                "mapping-error",
                "mapping-null",
                "duplicate-mapping",
                "source-self",
                "mapped-self",
                "mapping-other-unsupported",
            }
            assert second["proven"] is not (
                mapping_invalid or drift == "duplicate-member"
            )
            assert first["member_proof"] == "direct_view_corresponding"
            if drift == "mapping-foreign":
                assert census["sources"][0]["source_member_count"] == 2
                assert census["sources"][0]["mapped_member_count"] == 2
                assert census["sources"][0]["mapping_complete"] is True
                assert first["view_source_entity_is_same"] == [0, 0]
            if drift == "unsupported-comparison":
                assert first["view_source_entity_is_same"] == [1, 2]
                assert first["negative_controls_proven"] is False


@pytest.mark.parametrize("outline_fits", [False, True])
def test_supplier_view_guard_checks_native_outline_before_annotations(
    monkeypatch, outline_fits
):
    monkeypatch.setattr(purchased, "_early_bound", lambda obj, _interface: obj)
    cell = (0.0, 0.0, 1.0, 1.0)
    view = SimpleNamespace(
        GetOutline=lambda: (0.1, 0.1, 0.9 if outline_fits else 1.1, 0.9)
    )
    calls = []
    adapter = object()
    monkeypatch.setattr(
        purchased,
        "assert_supplier_annotations_fit",
        lambda adapter, view, cell, *, label: calls.append(
            (adapter, view, cell, label)
        ),
    )
    if outline_fits:
        purchased.assert_supplier_view_fits(adapter, view, cell, label="supplier")
        assert calls == [(adapter, view, cell, "supplier")]
    else:
        with pytest.raises(RuntimeError, match="settled supplier view leaves its cell"):
            purchased.assert_supplier_view_fits(adapter, view, cell, label="supplier")
        assert calls == []


@pytest.mark.parametrize(
    ("drift", "message"),
    [
        (None, None),
        ("missing-dimension", "lost its native dimension"),
        ("owner", "unsound supplier annotation owner/value"),
        ("hidden-value", "unsound supplier annotation owner/value"),
        ("unreadable", "unreadable settled native dimension ink"),
        ("dimension-outside", "supplier dimension leaves its cell/caption space"),
        ("note-outside", "supplier note leaves its cell"),
    ],
)
def test_supplier_annotations_guard_validates_native_ink_without_outline(
    monkeypatch, drift, message
):
    case = _supplier_native(monkeypatch)
    monkeypatch.setattr(purchased, "_early_bound", lambda obj, _interface: obj)
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    case.display.GetNext5 = lambda: None
    case.view.GetFirstDisplayDimension6 = lambda: case.display
    note = SimpleNamespace(
        GetExtent=lambda: (
            0.1,
            0.1,
            0.0,
            1.1 if drift == "note-outside" else 0.9,
            0.9,
            0.0,
        )
    )
    note_annotation = SimpleNamespace(
        GetType=lambda: 6, GetSpecificAnnotation=lambda: note
    )
    case.view.GetAnnotations = lambda: (case.annotation, note_annotation)
    # No GetOutline: sketch-only views can have unusable outlines while their
    # native dimensions and notes must still pass the original containment guard.
    if drift == "missing-dimension":
        case.display.GetDimension2 = lambda _index: None
    elif drift == "owner":
        case.annotation.Owner = object()
    elif drift == "hidden-value":
        case.display.ShowDimensionValue = False
    geometry = {
        "texts": [
            {
                "t": "(7/16)",
                "pos": (0.5, 0.5, 0.0),
                "h": 0.01,
                "w": 2.0 if drift == "dimension-outside" else 0.1,
                "ang": 0.0,
                "ref": 2,
            }
        ]
    }
    monkeypatch.setattr(
        purchased,
        "annotation_display",
        lambda *_args: (geometry, {"refused": True} if drift == "unreadable" else {}),
    )
    if message is None:
        purchased.assert_supplier_annotations_fit(
            adapter, case.view, (0.0, 0.0, 1.0, 1.0), label="supplier"
        )
    else:
        with pytest.raises(RuntimeError, match=message):
            purchased.assert_supplier_annotations_fit(
                adapter, case.view, (0.0, 0.0, 1.0, 1.0), label="supplier"
            )


def test_supplier_margins_reserve_authored_lanes_without_refitting_geometry():
    from _supplier_screw_layout import supplier_screw_lane_plan, supplier_screw_margins

    rows = (("Head", 9.525, "horizontal"), ("Thread", 2.8448, "horizontal"))
    sides = {"Head": "top", "Thread": "top"}
    plan = supplier_screw_lane_plan(rows, sides=sides)
    margins = supplier_screw_margins(rows, sides=sides)
    assert plan["Thread"][1] < plan["Head"][1]
    cells = purchased.fastener_view_cells(purchased.view_band_bottom("", label="test"))
    fitted = purchased.supplier_fit_cells(cells, margins, label="test")
    original = {name: cell for name, _center, cell in cells}
    actual = {name: cell for name, _center, cell in fitted}
    assert original["*Top"] == actual["*Top"]
    assert original["*Isometric"] == actual["*Isometric"]
    assert actual["*Front"][3] == pytest.approx(
        original["*Front"][3] - margins["*Front"][3]
    )
    with pytest.raises(ValueError, match="orthographic"):
        purchased.supplier_fit_cells(cells, {"*Isometric": (0.01,) * 4}, label="test")


@pytest.mark.parametrize(
    "layout,orthographic", [
        ("standard", (1, 8)), ("supplier_top", (1, 4)), ("tall_top", (1, 1)),
    ]
)
def test_clamp_native_outline_fits_readable_scale_with_unchanged_annotation_room(
    monkeypatch, tmp_path, layout, orthographic
):
    import sh_vn_clamp_screw_spec as supplier
    from _supplier_screw_layout import supplier_screw_margins

    # 4dcfee native fit events, 20261021T225443Z-1-a1e7290f. These are
    # decompositions of native outlines, NOT assumed physical-body bounds.
    sizes = {
        "*Front": (0.006858, 0.006858),
        "*Top": (0.006858, 0.036145592231561),
        "*Right": (0.036145592231561, 0.006858),
        "*Isometric": (0.030408131682318, 0.023154077655594),
    }

    class ClampView(_View):
        @property
        def Position(self):
            return self._center

        def GetOutline(self):
            ratio = self.ScaleRatio[0] / self.ScaleRatio[1]
            width, height = (
                size * ratio + 0.011176 for size in sizes[self._orientation]
            )
            x, y = self._center
            return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)

        def SetViewPosition(self, position, _update):
            self._center = tuple(position)
            return True

    monkeypatch.setattr(purchased, "double_array", tuple)
    margins = supplier_screw_margins(
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
        sides=supplier.SUPPLIER_REFERENCE_SIDES,
    )
    assert margins["*Top"] == pytest.approx((0.026, 0.026, 0.026, 0.020))
    outer = purchased.fastener_view_cells(0.073, layout=layout)
    fitted = purchased.supplier_fit_cells(outer, margins, label="clamp")
    views = [
        ClampView(name, tmp_path / "clamp.SLDPRT", center) for name, center, _ in outer
    ]
    scales = purchased._fit_views(_Drawing(), views, fitted)
    assert {scales[name] for name in ("*Front", "*Top", "*Right")} == {orthographic}
    assert scales["*Isometric"] == (2, 1)
    for view, (_name, _center, bounds) in zip(views, fitted, strict=True):
        assert purchased._inside(view.GetOutline(), bounds)


@pytest.mark.parametrize("layout", ("standard", "supplier_top", "tall_top"))
def test_fastener_cells_and_captions_clear_border_title_block_and_each_other(layout):
    from itertools import combinations

    from _layout_geometry import Box

    cells = purchased.fastener_view_cells(0.073, layout=layout)
    rectangles = {name: Box(*bounds) for name, _center, bounds in cells}
    front, top, right, iso = (
        rectangles[name] for name in ("*Front", "*Top", "*Right", "*Isometric")
    )
    assert next(center[0] for name, center, _ in cells if name == "*Front") == next(
        center[0] for name, center, _ in cells if name == "*Top"
    )
    assert next(center[1] for name, center, _ in cells if name == "*Front") == next(
        center[1] for name, center, _ in cells if name == "*Right"
    )
    # Complete caption cells, including their six-mm lower extent. The
    # isometric caption can touch the Right cell's top, as on standard sheets.
    captions = {
        name: Box(box.xmin, box.ymin - 0.010, box.xmax, box.ymin - 0.003)
        for name, box in rectangles.items()
    }
    border = (0.0127, 0.0127, 0.4191, 0.2667)
    title = Box(0.2159, 0.0127, 0.4191, 0.0651)
    for box in (*rectangles.values(), *captions.values()):
        assert purchased._inside((box.xmin, box.ymin, box.xmax, box.ymax), border)
        assert box.overlaps(title, tol=0.0) is None
    for first, second in combinations((*rectangles.values(), *captions.values()), 2):
        assert first.overlaps(second, tol=0.0) is None
    assert captions["*Top"].ymin - front.ymax >= 0.006 - 1e-12
    assert captions["*Front"].ymin - title.ymax >= 0.0019 - 1e-12
    assert captions["*Right"].ymin - title.ymax >= 0.0019 - 1e-12


@pytest.mark.parametrize("axis", (0, 1), ids=("horizontal", "vertical"))
@pytest.mark.parametrize("tail_extension", (0.0, 0.004))
def test_clamp_shelf_follows_measured_text_and_arrow_reach(axis, tail_extension):
    import draw_sh_vn_clamp_screw as clamp
    from _layout_geometry import Box, Segment, segment_box_distance

    # Representative settled-mode geometry, not native after-fix evidence.
    # Horizontal text includes the whole nominal-diameter/thread-ID block.
    text = Box(0.1029, 0.2192, 0.1271, 0.2288)
    reach = 0.135 if axis == 0 else 0.245
    reach += tail_extension
    position = (0.115, 0.222, 0.0)
    geometry = dict(axis=axis, text=text, reach=reach)
    target = clamp._shelf_target(geometry, position, position[1 - axis])
    dx, dy = (target[index] - position[index] for index in (0, 1))
    moved = Box(text.xmin + dx, text.ymin + dy, text.xmax + dx, text.ymax + dy)
    assert target[1 - axis] == position[1 - axis]
    assert (moved.xmin if axis == 0 else moved.ymin) - reach == pytest.approx(
        clamp.CLEAR_GAP_M + clamp.PLACE_SETTLE_M
    )
    line = (
        Segment(0.108, 0.222, reach, 0.222)
        if axis == 0
        else Segment(0.115, 0.215, 0.115, reach)
    )
    assert segment_box_distance(line, moved) >= clamp.CLEAR_GAP_M
    cell = Box(0.025, 0.166, 0.205, 0.262)
    assert purchased._inside(
        (moved.xmin, moved.ymin, moved.xmax, moved.ymax),
        (cell.xmin, cell.ymin, cell.xmax, cell.ymax),
    )


@pytest.mark.parametrize("key", ("tips", "witnesses"))
def test_clamp_shelving_rejects_native_line_station_drift(key):
    import draw_sh_vn_clamp_screw as clamp

    original = dict(
        tips=((0.1, 0.2), (0.1, 0.204)),
        witnesses=((0.2, 0.099, 0.11), (0.204, 0.099, 0.11)),
    )
    clamp._assert_stations("head", original, copy.deepcopy(original))
    moved = copy.deepcopy(original)
    moved[key] = (
        tuple(value + 0.0001 for value in original[key][0]),
        *original[key][1:],
    )
    with pytest.raises(RuntimeError, match=f"native {key} moved"):
        clamp._assert_stations("head", original, moved)


@pytest.fixture
def clamp_native_supplier_inventory(monkeypatch):
    import draw_sh_vn_clamp_screw as clamp

    class Display:
        def __init__(self, full_name):
            # Only the proven typed IDimension.FullName is available: no
            # assumed short Name or annotation-name convenience interface.
            self.native = SimpleNamespace(FullName=full_name)
            self.next = None

        def GetDimension2(self, index):
            assert index == 0
            return self.native

        def GetAnnotation(self):
            raise AssertionError("annotation-name convenience path is unavailable")

        def GetNext5(self):
            return self.next

    class View:
        def __init__(self, orientation, displays):
            self.orientation = orientation
            self.displays = displays

        def GetOrientationName(self):
            return self.orientation

        def GetFirstDisplayDimension6(self):
            for index, display in enumerate(self.displays):
                display.next = (
                    self.displays[index + 1] if index + 1 < len(self.displays) else None
                )
            return self.displays[0] if self.displays else None

    # Spec-derived identities, not a retained 4e200 native inventory.
    identities = (
        ("SupplierHeadDiameter", "SupplierReference", "*Front"),
        ("SupplierLength", "SupplierTopReference", "*Top"),
        ("SupplierHeadHeight", "SupplierTopReference", "*Top"),
        ("SupplierThreadDiameter", "SupplierTopReference", "*Top"),
    )
    displays = {
        name: Display(f"{name}@{feature}@sh-vn-clamp-screw.Part")
        for name, feature, _owner in identities
    }
    views = {
        owner: View(
            owner,
            [
                displays[name]
                for name, _feature, expected_owner in identities
                if expected_owner == owner
            ],
        )
        for owner in ("*Front", "*Top", "*Right", "*Isometric")
    }
    adapter = object()
    monkeypatch.setattr(clamp, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(clamp, "iter_views", lambda _adapter: iter(views.values()))
    return SimpleNamespace(
        clamp=clamp,
        adapter=adapter,
        displays=displays,
        views=views,
        identities=identities,
        make_display=Display,
    )


def test_clamp_supplier_displays_accepts_exact_typed_native_inventory(
    clamp_native_supplier_inventory,
):
    case = clamp_native_supplier_inventory
    actual = case.clamp._supplier_displays(case.adapter)
    assert set(actual) == set(case.displays)
    assert all(actual[name] is display for name, display in case.displays.items())
    assert len(actual) == 4


@pytest.mark.parametrize(
    "defect",
    (
        "missing",
        "duplicate",
        "unexpected-name",
        "wrong-feature",
        "wrong-view-front",
        "wrong-view-right",
        "wrong-view-isometric",
        "missing-native-dimension",
    ),
)
def test_clamp_supplier_displays_rejects_changed_native_inventory(
    clamp_native_supplier_inventory, defect
):
    case = clamp_native_supplier_inventory
    name = "SupplierHeadHeight"
    display = case.displays[name]
    top = case.views["*Top"].displays
    missing = []
    if defect == "missing":
        top.remove(display)
        missing = [name]
    elif defect == "duplicate":
        top.append(case.make_display(display.native.FullName))
    elif defect == "unexpected-name":
        top.append(
            case.make_display(
                "UnexpectedDimension@SupplierTopReference@sh-vn-clamp-screw.Part"
            )
        )
    elif defect == "wrong-feature":
        display.native.FullName = f"{name}@SupplierReference@sh-vn-clamp-screw.Part"
        missing = [name]
    elif defect.startswith("wrong-view-"):
        owner = {
            "wrong-view-front": "*Front",
            "wrong-view-right": "*Right",
            "wrong-view-isometric": "*Isometric",
        }[defect]
        top.remove(display)
        case.views[owner].displays.append(display)
        missing = [name]
    elif defect == "missing-native-dimension":
        display.native = None
        missing = [name]

    expected_inventory = sorted(
        (f"{name}@{feature}", owner) for name, feature, owner in case.identities
    )
    actual_inventory = [
        (
            display.native.FullName if display.native is not None else "",
            owner,
        )
        for owner, view in case.views.items()
        for display in view.displays
    ]
    with pytest.raises(
        RuntimeError, match="clamp supplier dimension inventory changed"
    ) as exc:
        case.clamp._supplier_displays(case.adapter)
    diagnostic = str(exc.value)
    assert f"expected={expected_inventory}" in diagnostic
    assert f"actual={actual_inventory}" in diagnostic
    assert f"missing={missing}" in diagnostic


def test_supplier_angle_converts_native_radians_to_degrees(monkeypatch):
    import math

    case = _supplier_native(monkeypatch, value=math.radians(82.0), kind=3)
    case.helper.supplier_reference_dimension(
        None,
        case.display,
        label="included angle",
        units="deg",
        precision=0,
        expected_degrees=82.0,
        presentation="angle",
    )
    assert case.native.SystemValue == math.radians(82.0)
    assert case.text[2] == ")"


@pytest.mark.parametrize(
    "start,end",
    (((0.0, 0.0), (-6.35, 0.0)), ((1.0, 0.0), (7.35, 0.0))),
)
def test_supplier_chord_rejects_same_length_in_wrong_final_frame(
    monkeypatch, start, end
):
    import _supplier_screw_reference as reference

    monkeypatch.setattr(reference, "_early_bound", lambda obj, _interface: obj)

    def point(coordinates):
        return SimpleNamespace(
            X=coordinates[0] / 1000.0, Y=coordinates[1] / 1000.0, Z=0.0
        )

    line = SimpleNamespace(
        GetStartPoint2=lambda: point(start),
        GetEndPoint2=lambda: point(end),
    )
    adapter = SimpleNamespace(_sketch_entities={"chord": line})
    reference._assert_line_frame(adapter, "chord", start, end)
    with pytest.raises(RuntimeError, match="final-frame coordinates"):
        reference._assert_line_frame(adapter, "chord", (0.0, 0.0), (6.35, 0.0))


def _supplier_reference_solver(monkeypatch):
    """Small witness solver: shared point identity carries native constraints."""
    import _supplier_screw_reference as reference
    import _sketch

    monkeypatch.setattr(reference, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        reference, "set_sketch_direct_db", lambda adapter, enabled: None
    )
    case = SimpleNamespace(
        lines={}, points={}, emitted=[], overdefined=False, unreadable=None,
        selected=[], native_angles=[],
    )

    def success(data=None):
        return SimpleNamespace(is_success=True, data=data, error=None)

    class Point:
        def __init__(self, x, y):
            self.X, self.Y, self.Z = x / 1000.0, y / 1000.0, 0.0
            self.axes = set()

        @property
        def Status(self):
            solve()
            if case.unreadable is not None:
                if isinstance(case.unreadable, Exception):
                    raise case.unreadable
                return case.unreadable
            if case.overdefined:
                return 4  # swOverConstrained, never equivalent to fully constrained.
            return 3 if len(self.axes) == 2 else 2

    def point(x, y):
        return case.points.setdefault((x, y), Point(x, y))

    class Line:
        ConstructionGeometry = False

        def __init__(self, start, end):
            self.start, self.end = start, end
            self.orientation = None
            self.sized = False

        def GetStartPoint2(self):
            return self.start

        def GetEndPoint2(self):
            return self.end

        def GetSketch(self):
            return case.sketch

    def solve():
        # A sized oriented line transfers its anchored end's position to the
        # other end; a sized oblique ray still has one free rotational DOF.
        for _ in range(len(case.lines) + 1):
            for line in case.lines.values():
                if line.sized and line.orientation:
                    if len(line.start.axes) == 2 or len(line.end.axes) == 2:
                        line.start.axes.update(("x", "y"))
                        line.end.axes.update(("x", "y"))

    def resolve(ref):
        entity, endpoint = ref.rsplit(".", 1)
        return getattr(case.lines[entity], endpoint)

    async def add_line(x1, y1, x2, y2):
        name = f"line{len(case.lines)}"
        case.lines[name] = Line(point(x1, y1), point(x2, y2))
        return success(name)

    async def constraint(left, right, kind):
        if kind in ("horizontal", "vertical"):
            case.lines[left].orientation = kind
        elif kind == "coincident":
            if right == "origin":
                resolve(left).axes.update(("x", "y"))
            else:
                entity, endpoint = right.rsplit(".", 1)
                setattr(case.lines[entity], endpoint, resolve(left))
        elif kind in ("horizontal_points", "vertical_points"):
            resolve(left).axes.add("y" if kind == "horizontal_points" else "x")
        else:
            raise AssertionError(f"unexpected witness relation {kind}")
        solve()
        return success()

    async def dimension(left, right, kind, value):
        case.emitted.append((left, right, kind, value))
        if right == "origin":
            target = resolve(left)
            if len(target.axes) == 2:
                case.overdefined = True
            target.axes.add("x" if kind == "horizontal_distance" else "y")
        else:
            entity = left.rsplit(".", 1)[0]
            case.lines[entity].sized = True
        solve()
        return success(f"D{len(case.emitted)}")

    async def definition():
        solve()
        state = (
            "over_defined" if case.overdefined else
            "fully_defined" if all(
                len(p.axes) == 2
                for line in case.lines.values() for p in (line.start, line.end)
            ) else "under_defined"
        )
        return success({"definition_state": state})

    async def over_relations():
        return success(["redundant origin anchor"])

    case.adapter = SimpleNamespace(
        _sketch_entities=case.lines, add_line=add_line,
        add_sketch_constraint=constraint, add_sketch_dimension=dimension,
        check_sketch_fully_defined=definition,
        get_over_defining_relations=over_relations,
    )
    case.reference = reference
    case.dimensions = _sketch.SketchDims()
    case.point = point
    case.solve = solve
    case.ensure = lambda: asyncio.run(
        reference.ensure_fully_defined(case.adapter, "SupplierReference")
    )
    case.linear = lambda name, value, orientation, start: asyncio.run(
        reference._linear(
            case.adapter, case.dimensions, name, value, orientation, start
        )
    )
    return case


def test_supplier_reference_linear_independent_witness_needs_origin_anchor(monkeypatch):
    case = _supplier_reference_solver(monkeypatch)
    case.linear("Diameter", 6.0, "horizontal", (2.0, 3.0))
    case.ensure()
    assert case.emitted == [
        ("line0.start", "line0.end", "horizontal_distance", 6.0),
        ("line0.start", "origin", "horizontal_distance", 2.0),
        ("line0.start", "origin", "vertical_distance", 3.0),
    ]
    assert case.dimensions._rows == [
        ("Diameter", None), ("DiameterStartX", None), ("DiameterStartY", None),
    ]
    assert case.lines["line0"].ConstructionGeometry is True


def test_supplier_reference_linear_shared_end_inherits_spigot_anchor(monkeypatch):
    case = _supplier_reference_solver(monkeypatch)
    case.linear("Spigot", 5.0, "vertical", (8.0, -2.0))
    case.linear("Diameter", 6.0, "horizontal", (2.0, 3.0))
    case.ensure()
    spigot, witness = case.lines.values()
    assert witness.end is spigot.end
    assert (witness.start.Status, witness.end.Status) == (3, 3)
    assert case.emitted == [
        ("line0.start", "line0.end", "vertical_distance", 5.0),
        ("line0.start", "origin", "horizontal_distance", 8.0),
        ("line0.start", "origin", "vertical_distance", 2.0),
        ("line1.start", "line1.end", "horizontal_distance", 6.0),
    ]
    assert case.dimensions._rows == [
        ("Spigot", None), ("SpigotStartX", None), ("SpigotStartY", None),
        ("Diameter", None),
    ]
    assert not case.overdefined


@pytest.mark.parametrize("status", [None, "3", RuntimeError("native Status unavailable")])
def test_supplier_reference_linear_unreadable_status_fails_without_anchors(
    monkeypatch, status
):
    case = _supplier_reference_solver(monkeypatch)
    # None is an unreadable native property too; use a separate property for it.
    if status is None:
        case.point(2.0, 3.0).__class__.Status = property(lambda self: None)
    else:
        case.unreadable = status
    with pytest.raises(RuntimeError, match="status is unreadable|Status unavailable"):
        case.linear("Diameter", 6.0, "horizontal", (2.0, 3.0))
    assert case.emitted == [
        ("line0.start", "line0.end", "horizontal_distance", 6.0),
    ]
    assert case.dimensions._rows == [("Diameter", None)]


def test_supplier_reference_linear_overdefined_status_cannot_skip_anchor_or_guard(
    monkeypatch,
):
    case = _supplier_reference_solver(monkeypatch)
    case.overdefined = True
    case.linear("Diameter", 6.0, "horizontal", (2.0, 3.0))
    assert [row[1] for row in case.emitted] == ["line0.end", "origin", "origin"]
    assert case.dimensions._rows[-2:] == [
        ("DiameterStartX", None), ("DiameterStartY", None),
    ]
    with pytest.raises(RuntimeError, match="OVER-defined"):
        case.ensure()


@pytest.mark.parametrize("fault", ["reflected", "translated"])
def test_supplier_reference_linear_constrained_wrong_frame_is_rejected(
    monkeypatch, fault
):
    case = _supplier_reference_solver(monkeypatch)
    original = case.adapter.add_sketch_dimension

    async def displaced(*args):
        result = await original(*args)
        if args[1] != "origin":
            line = case.lines["line0"]
            line.start.axes.update(("x", "y"))
            line.end.axes.update(("x", "y"))
            if fault == "reflected":
                line.end.X = line.start.X - (line.end.X - line.start.X)
            else:
                line.start.X += 0.001
                line.end.X += 0.001
        return result

    case.adapter.add_sketch_dimension = displaced
    with pytest.raises(RuntimeError, match="final-frame coordinates"):
        case.linear("Diameter", 6.0, "horizontal", (2.0, 3.0))
    assert case.dimensions._rows == [("Diameter", None)]
    assert len(case.emitted) == 1  # No anchor should hide the bad solved frame.


def _supplier_reference_angle_solver(monkeypatch, defect=None):
    import math
    import solidworks_mcp.adapters.com_variant as variants
    import solidworks_mcp.adapters.solidworks.sketch as sdk_sketch

    case = _supplier_reference_solver(monkeypatch)
    case.angle_text = None

    class MathPoint:
        def __init__(self, coordinates):
            self.ArrayData = tuple(coordinates)

        def MultiplyTransform(self, transform):
            return MathPoint(transform(self.ArrayData))

    # Rotated/translated owning plane: sketch +Y is model +Z, not model +Y.
    # Native AddSpecificDimension takes MODEL metres even in an active sketch.
    def sketch_to_model(xyz):
        x, y, z = xyz
        return (0.020 + x, 0.030 - z, 0.040 + y)

    case.sketch = SimpleNamespace(
        ModelToSketchTransform=SimpleNamespace(Inverse=lambda: sketch_to_model)
    )
    case.adapter.swApp = SimpleNamespace(
        GetMathUtility=lambda: SimpleNamespace(CreatePoint=MathPoint)
    )
    monkeypatch.setattr(variants, "double_array", lambda values: values)

    def select(adapter, entities, mark):
        case.selected = [adapter._sketch_entities[name] for name in entities]

    monkeypatch.setattr(sdk_sketch, "_select_sketch_entities", select)

    class Angle:
        def __init__(self, attachments, value):
            self.attachments = attachments
            self.SystemValue = value
            self._driven = 1

        @property
        def DrivenState(self):
            return self._driven

        @DrivenState.setter
        def DrivenState(self, state):
            if defect == "not-driving":
                return
            self._driven = state
            if state == 2 and len(self.attachments) == 2:
                baseline, ray = self.attachments
                if baseline.start is ray.start and baseline.orientation:
                    ray.orientation = "included-angle"
                    case.solve()

    def add_specific(x, y, z, kind, options):
        attachments = tuple(case.selected)
        assert len(attachments) == 2
        assert all(hasattr(line, "GetEndPoint2") for line in attachments)
        baseline, ray = attachments
        a = (
            baseline.end.X - baseline.start.X,
            baseline.end.Y - baseline.start.Y,
        )
        b = (ray.end.X - ray.start.X, ray.end.Y - ray.start.Y)
        value = math.acos(
            (a[0] * b[0] + a[1] * b[1]) / (math.hypot(*a) * math.hypot(*b))
        )
        # Invert the actual non-Front placement. A sketch-space text point
        # cannot pass either the plane test or the interior-wedge test.
        local = (x - 0.020, z - 0.040, 0.030 - y)
        dx, dy = local[0] - baseline.start.X, local[1] - baseline.start.Y
        assert local[2] == pytest.approx(0.0, abs=1e-12)
        assert math.atan2(dy, dx) == pytest.approx(value / 2.0)
        assert math.hypot(dx, dy) == pytest.approx(0.0005)
        assert (kind, options) == (3, 0)
        case.angle_text = (x, y, z)
        if defect == "supplement":
            value = math.pi - value
        native = Angle(
            attachments,
            value + math.radians(0.01) if defect == "wrong-value" else value,
        )
        case.native_angles.append(native)
        case.emitted.append((baseline, ray, "native-angular", native))
        return SimpleNamespace(
            Type2=2 if defect == "wrong-type" else 3,
            GetDimension2=lambda index: native,
        ), 0

    case.adapter.currentModel = SimpleNamespace(
        ClearSelection2=lambda all_marks: case.selected.clear(),
        Extension=SimpleNamespace(AddSpecificDimension=add_specific),
    )
    case.angle = lambda: asyncio.run(
        case.reference._angle(
            case.adapter, case.dimensions, "Included", 82.0, (2.0, 3.0)
        )
    )
    return case


def test_supplier_reference_angle_drives_both_rays_in_native_owning_plane(monkeypatch):
    import math

    case = _supplier_reference_angle_solver(monkeypatch)
    case.angle()
    case.ensure()
    baseline, ray = case.lines.values()
    assert baseline.start is ray.start
    assert baseline.sized and ray.sized
    assert baseline.ConstructionGeometry and ray.ConstructionGeometry
    assert len(case.lines) == 2
    assert case.native_angles[0].attachments == (baseline, ray)
    assert case.native_angles[0].DrivenState == 2
    assert case.native_angles[0].SystemValue == pytest.approx(math.radians(82.0))
    assert case.angle_text is not None
    assert case.selected == []
    assert [row[2] for row in case.emitted] == [
        "horizontal_distance", "horizontal_distance", "vertical_distance",
        "distance", "native-angular",
    ]
    assert case.dimensions._rows == [
        ("IncludedBaselineLength", None),
        ("IncludedStartX", None), ("IncludedStartY", None),
        ("IncludedRayLength", None), ("Included", None),
    ]


@pytest.mark.parametrize(
    "defect,message",
    [
        ("wrong-type", "not a native angular dimension"),
        ("wrong-value", "not the specified 82 degrees"),
        ("supplement", "not the specified 82 degrees"),
        ("not-driving", "not an exact driving control"),
    ],
)
def test_supplier_reference_angle_rejects_invalid_native_control(
    monkeypatch, defect, message
):
    case = _supplier_reference_angle_solver(monkeypatch, defect)
    with pytest.raises(RuntimeError, match=message):
        case.angle()
    assert ("Included", None) not in case.dimensions._rows
    assert case.native_angles[0].DrivenState != 2
    assert case.selected == []
    with pytest.raises(RuntimeError, match="not fully defined"):
        case.ensure()


def test_supplier_exact_fraction_keeps_native_value_and_refuses_fraction_rounding(
    monkeypatch,
):
    case = _supplier_native(monkeypatch, value=0.00238125)
    settings = dict(
        label="supplier head height",
        units="in",
        precision=3,
        expected_mm=2.38125,
        fraction_denominator=32,
    )
    case.helper.supplier_reference_dimension(None, case.display, **settings)
    assert case.native.SystemValue == 0.00238125
    assert case.state.denominator == 32
    case.state.rounding = True
    with pytest.raises(RuntimeError, match="exact supplier fraction"):
        case.helper.assert_supplier_reference_dimension(None, case.display, **settings)


@pytest.mark.parametrize("units,unit_code", [("in", 3), ("mm", 0)])
def test_supplier_row_units_survive_annotation_and_final_reacquisition(
    monkeypatch,
    units,
    unit_code,
):
    import _supplier_screw_dimensions as screws

    case = _supplier_native(monkeypatch, value=0.006)
    case.native.FullName = "Length@SupplierReference@stock.SLDPRT"
    case.view.GetOrientationName = lambda: "*Front"
    case.view.GetOutline = lambda: (0.05, 0.10, 0.10, 0.15)
    case.view.UpdateViewDisplayGeometry = lambda: None
    case.view.GetAnnotations = lambda: [case.annotation]
    monkeypatch.setattr(screws, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        screws, "_binding", lambda *_args: ("Front", "stock.SLDPRT", "Default")
    )
    monkeypatch.setattr(screws, "_assert_source", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(screws, "iter_views", lambda _adapter: [case.view])
    monkeypatch.setattr(screws, "view_name", lambda *_args: "Front")
    monkeypatch.setattr(screws, "dimension_name", lambda *_args: "Length")
    monkeypatch.setattr(
        screws,
        "model_points_in_view",
        lambda *_args, **_kwargs: [(0.075, 0.125)],
    )
    monkeypatch.setattr(
        screws,
        "curate_view_dimensions",
        lambda *_args, **_kwargs: [case.annotation],
    )
    checks = []
    found = screws.annotate_supplier_screw(
        None,
        {"*Front": case.view},
        dimensions=(("Length", 6.0, "vertical"),),
        formats={"Length": (3, "length", None, None)},
        units={"Length": units},
        settled_checks=checks,
    )
    assert found == {"Length": case.display}
    assert case.native.SystemValue == 0.006
    assert case.state.unit == unit_code
    assert case.text[2] == f" {units})"
    assert len(checks) == 1
    checks[0]()
    case.state.unit = 3 if units == "mm" else 0
    with pytest.raises(RuntimeError, match="presentation differs"):
        checks[0]()


@pytest.mark.parametrize("units", [{"Alien": "mm"}, {"Length": "cm"}])
def test_supplier_unknown_or_unsupported_row_units_fail_before_native_access(units):
    from _supplier_screw_dimensions import (
        annotate_supplier_screw,
        assert_supplier_screw,
    )

    options = dict(
        dimensions=(("Length", 6.0, "vertical"),),
        formats={"Length": (3, "length", None, None)},
        units=units,
    )
    for operation in (annotate_supplier_screw, assert_supplier_screw):
        with pytest.raises(ValueError, match="supplier reference units"):
            operation(None, {}, **options)


class _SupplierReadOnlyDocument(_Model):
    """Method-shaped IModelDoc2 getters; no source save/flag-clear operations."""

    def __init__(self, path):
        super().__init__(path)
        self.native_id = object()
        self.kind = 1
        self.read_only = True
        self.read_only_error = None
        self.presentation_dirty = False

    def GetType(self):
        return self.kind

    def IsOpenedReadOnly(self):
        if self.read_only_error is not None:
            raise self.read_only_error
        return self.read_only

    def GetSaveFlag(self):
        raise AssertionError(
            "source cleanliness is stage-specific, not an opener policy"
        )


def _supplier_read_only_case(monkeypatch, tmp_path, *, already_open=False):
    source = tmp_path / "supplier.SLDPRT"
    source.write_bytes(b"unchanged supplier bytes")
    model = _SupplierReadOnlyDocument(source)
    readback = _SupplierReadOnlyDocument(source)
    readback.native_id = model.native_id

    class App:
        def __init__(self):
            self.loaded = model if already_open else None
            self.readback = readback
            self.errors = 0
            self.warnings = 4
            self.identity_result = None
            self.opens = []
            self.on_open = lambda: None

        def GetOpenDocumentByName(self, path):
            assert Path(path).resolve() == source.resolve()
            return self.loaded

        def OpenDoc6(self, path, kind, options, configuration, errors, warnings):
            self.opens.append((path, kind, options, configuration, errors, warnings))
            self.on_open()
            self.loaded = self.readback
            return model, self.errors, self.warnings

        def IsSame(self, left, right):
            if self.identity_result is not None:
                return self.identity_result
            return int(left.native_id is right.native_id)

    app = App()
    adapter = SimpleNamespace(swApp=app, currentModel=None)
    events = []
    monkeypatch.setattr(purchased, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        purchased._telemetry,
        "event",
        lambda name, **fields: events.append((name, fields)),
    )
    return SimpleNamespace(
        source=source,
        model=model,
        readback=readback,
        app=app,
        adapter=adapter,
        events=events,
    )


@pytest.mark.parametrize("already_open", (False, True), ids=("new", "loaded"))
@pytest.mark.parametrize("path_type", (Path, str), ids=("path", "string"))
def test_supplier_read_only_open_acquires_or_reuses_exact_native_part(
    monkeypatch,
    tmp_path,
    already_open,
    path_type,
):
    case = _supplier_read_only_case(monkeypatch, tmp_path, already_open=already_open)
    # Expected native annotation presentation dirtiness is not a blanket veto.
    case.model.presentation_dirty = True
    model = purchased._open_supplier_source_read_only(
        case.adapter,
        path_type(case.source),
        label="supplier",
    )
    assert model is case.model
    assert case.adapter.currentModel is model
    assert model.presentation_dirty is True
    if already_open:
        assert case.app.opens == []
    else:
        assert case.app.opens == [(str(case.source.resolve()), 1, 3, "", 0, 0)]
        assert case.events[-1][1]["open_error_raw"] == 0
        assert case.events[-1][1]["open_warning_raw"] == 4


@pytest.mark.parametrize(
    "defect",
    (
        "writable",
        "integer-read-only",
        "unreadable-read-only",
        "missing-read-only",
        "wrong-type",
        "boolean-type",
        "wrong-path",
        "empty-path",
        "unloaded",
        "loaded-writable",
        "loaded-wrong-path",
        "loaded-wrong-type",
        "loaded-native-identity",
        "boolean-native-identity",
        "adapter-native-identity",
    ),
)
@pytest.mark.parametrize("already_open", (False, True), ids=("new", "loaded"))
def test_supplier_read_only_open_refuses_untrusted_native_source(
    monkeypatch,
    tmp_path,
    defect,
    already_open,
):
    case = _supplier_read_only_case(monkeypatch, tmp_path, already_open=already_open)
    if defect == "writable":
        case.model.read_only = False
    elif defect == "integer-read-only":
        case.model.read_only = 1
    elif defect == "unreadable-read-only":
        case.model.read_only_error = RuntimeError("read-only getter unavailable")
    elif defect == "missing-read-only":
        case.model.read_only = None
    elif defect == "wrong-type":
        case.model.kind = 3
    elif defect == "boolean-type":
        case.model.kind = True
    elif defect == "wrong-path":
        case.model._path = tmp_path / "other.SLDPRT"
    elif defect == "empty-path":
        case.model._path = ""
    elif defect.startswith("loaded-") or defect == "unloaded":
        # The second lookup is an independent native readback, including reuse.
        readback = None if defect == "unloaded" else case.readback
        lookups = iter((case.model if already_open else None, readback))
        case.app.GetOpenDocumentByName = lambda _path: next(lookups)
        if defect == "loaded-writable":
            case.readback.read_only = False
        elif defect == "loaded-wrong-path":
            case.readback._path = tmp_path / "other.SLDPRT"
        elif defect == "loaded-wrong-type":
            case.readback.kind = 2
        elif defect == "loaded-native-identity":
            case.readback.native_id = object()
    elif defect == "boolean-native-identity":
        case.app.identity_result = True
    else:
        foreign = _SupplierReadOnlyDocument(case.source)

        class RedirectedAdapter:
            swApp = case.app

            @property
            def currentModel(self):
                return foreign

            @currentModel.setter
            def currentModel(self, _value):
                return None

        case.adapter = RedirectedAdapter()
    with pytest.raises(RuntimeError):
        purchased._open_supplier_source_read_only(
            case.adapter, case.source, label="supplier"
        )
    if already_open:
        assert case.app.opens == []


@pytest.mark.parametrize(
    ("errors", "warnings", "has_model"),
    (
        (2, 0, True),
        (True, 0, True),
        ("0", 0, True),
        (0, False, True),
        (0, None, True),
        (0, 0, False),
    ),
    ids=(
        "native-error",
        "boolean-error",
        "string-error",
        "boolean-warning",
        "missing-warning",
        "missing-document",
    ),
)
def test_supplier_read_only_open_refuses_native_error_or_noninteger_status(
    monkeypatch,
    tmp_path,
    errors,
    warnings,
    has_model,
):
    case = _supplier_read_only_case(monkeypatch, tmp_path)
    case.app.errors, case.app.warnings = errors, warnings
    if not has_model:
        case.app.OpenDoc6 = lambda *_args: (None, errors, warnings)
    with pytest.raises(RuntimeError):
        purchased._open_supplier_source_read_only(
            case.adapter, case.source, label="supplier"
        )
    assert case.adapter.currentModel is None


def _purchased_source_lifecycle(monkeypatch, tmp_path, lane):
    """Run the real public lifecycle; fake all native/source-property/drawing work."""
    case = _supplier_read_only_case(monkeypatch, tmp_path)
    case.phases = []
    case.on_phase = lambda _phase: None
    spec = SimpleNamespace(
        artifact_stem=case.source.stem,
        source=case.source,
        source_kind="part",
        outputs={
            "slddrw": tmp_path / "supplier.SLDDRW",
            "pdf": tmp_path / "supplier.pdf",
            "png": tmp_path / "supplier.png",
        },
    )
    properties = dict.fromkeys(purchased._PROPERTIES, "test")
    properties.update(
        Number="42",
        Title=case.source.stem,
        Material="Steel",
        **{
            "Stock Name": "Supplier stock",
            "Supplier": "Supplier",
            "Supplier SKUs": "SKU-1",
            "Material Specification": "Steel",
            "Finish": "As purchased",
            "Manufacturing Notes": "",
        },
    )
    if lane == "part":
        import _purchased_part_drawing as module

        builder = module.build_purchased_part_drawing
    else:
        module = purchased
        builder = (
            purchased.build_purchased_fastener_drawing
            if lane == "fastener"
            else purchased.build_purchased_spring_drawing
        )
    monkeypatch.setattr(
        purchased,
        "fastener",
        lambda _stem: SimpleNamespace(
            part_name=case.source.stem,
            stock_name="Supplier stock",
            supplier="Supplier",
            skus=("SKU-1",),
        ),
    )
    monkeypatch.setattr(
        purchased._config,
        "parts",
        lambda _stem: {
            "number": "42",
            "material": "Steel",
            "finish": "As purchased",
            "title": "Supplier",
        },
    )

    def phase(name):
        case.phases.append(name)
        case.on_phase(name)

    case.app.on_open = lambda: phase("open")

    def read_properties(_model, _names, *, required):
        phase("properties")
        return properties

    async def complete_sheet(_adapter, _spec, **_kwargs):
        case.model.presentation_dirty = True
        for name in ("layout", "slddrw-save", "pdf-save", "drawing-close"):
            phase(name)
        return {"pdf": "reference.pdf"}

    monkeypatch.setattr(module, "read_required_properties", read_properties)
    monkeypatch.setattr(module, "_build_reference_sheet", complete_sheet)
    case.run = lambda: asyncio.run(builder(case.adapter, spec, item="SUPPLIER STOCK"))
    return case


@pytest.mark.parametrize("lane", ("fastener", "spring", "part"))
@pytest.mark.parametrize("mutation", ("unchanged", "rewrite", "unreadable"))
def test_purchased_source_integrity_covers_completed_sheet(
    monkeypatch,
    tmp_path,
    lane,
    mutation,
):
    case = _purchased_source_lifecycle(monkeypatch, tmp_path, lane)

    def completed(phase):
        if phase == "drawing-close":
            if mutation == "rewrite":
                case.source.write_bytes(b"changed supplier bytes")
            elif mutation == "unreadable":
                case.source.unlink()

    case.on_phase = completed
    if mutation == "unchanged":
        assert case.run() == {"pdf": "reference.pdf"}
        assert case.source.read_bytes() == b"unchanged supplier bytes"
        assert case.model.presentation_dirty is True
    elif mutation == "rewrite":
        with pytest.raises(RuntimeError, match="source part bytes changed"):
            case.run()
    else:
        with pytest.raises(FileNotFoundError):
            case.run()
    assert case.phases[-3:] == ["slddrw-save", "pdf-save", "drawing-close"]


@pytest.mark.parametrize("lane", ("fastener", "spring", "part"))
@pytest.mark.parametrize(
    "phase", ("open", "properties", "layout", "pdf-save", "drawing-close")
)
@pytest.mark.parametrize("mutation", ("rewrite", "unreadable"))
@pytest.mark.parametrize("error_type", (RuntimeError, asyncio.CancelledError))
def test_purchased_source_integrity_preserves_primary_failure(
    monkeypatch,
    tmp_path,
    lane,
    phase,
    mutation,
    error_type,
):
    case = _purchased_source_lifecycle(monkeypatch, tmp_path, lane)
    primary = error_type("primary native/drawing failure")

    def fail(current):
        if current == phase:
            if mutation == "rewrite":
                case.source.write_bytes(b"changed supplier bytes")
            else:
                case.source.unlink()
            raise primary

    case.on_phase = fail
    with pytest.raises(error_type) as caught:
        case.run()
    assert caught.value is primary
    assert "supplier source file preservation also failed" in "\n".join(
        primary.__notes__
    )
    assert (
        "bytes changed" if mutation == "rewrite" else "FileNotFoundError"
    ) in "\n".join(primary.__notes__)
    assert case.phases[-1] == phase


class _RefreshedOutlineView:
    """Native display bounds lag both scale and position until the void refresh."""

    def __init__(self, source, *, display_ratio=8.0):
        self.source = source
        self.Position = (0.25, 0.25)
        self.UseSheetScale = 1
        self.ReferencedConfiguration = "Supplier"
        self._scale = (1.0, 1.0)
        self._display_ratio = display_ratio
        self._display_position = self.Position
        self.scales = []
        self.moves = []
        self.refreshes = []

    @property
    def ScaleRatio(self):
        return self._scale

    @ScaleRatio.setter
    def ScaleRatio(self, value):
        self._scale = tuple(value)
        self.scales.append(self._scale)

    def GetName2(self):
        return "Drawing View1"

    def GetOrientationName(self):
        return "*Front"

    def GetReferencedModelName(self):
        return str(self.source)

    def GetOutline(self):
        x, y = self._display_position
        x, y = x + 0.125, y - 0.0625
        width, height = 0.2 * self._display_ratio, 0.04 * self._display_ratio
        return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)

    def UpdateViewDisplayGeometry(self):
        self._display_ratio = self._scale[0] / self._scale[1]
        self._display_position = self.Position
        self.refreshes.append((self._scale, self.Position))
        return None  # Real IView method is VT_VOID, not a success Boolean.

    def SetViewPosition(self, position, move_children):
        assert move_children is False
        self.Position = tuple(position)
        self.moves.append(self.Position)
        return True


def _native_fit_records(monkeypatch):
    records = []
    monkeypatch.setattr(purchased, "double_array", tuple)
    monkeypatch.setattr(
        purchased._telemetry,
        "event",
        lambda name, **fields: records.append((name, fields)),
    )
    return records


@pytest.mark.parametrize(
    "display_ratio", (8.0, 1.0), ids=("stale-too-large", "stale-too-small")
)
def test_fit_group_selects_post_refresh_native_outline(
    monkeypatch, tmp_path, display_ratio
):
    records = _native_fit_records(monkeypatch)
    view = _RefreshedOutlineView(
        tmp_path / "supplier.SLDPRT", display_ratio=display_ratio
    )
    members = [(view, ("*Front", (0.5, 0.5), (0.0, 0.0, 1.0, 1.0)))]
    assert purchased._fit_group(_Drawing(), members) == (5, 1)
    assert view.scales == [(8.0, 1.0), (5.0, 1.0)]  # No diagnostic replay.
    assert len(view.refreshes) == 3 and len(view.moves) == 1
    assert view.Position == pytest.approx((0.375, 0.5625))
    states = [
        state for name, state in records if name == "drawing.purchased_fit_candidate"
    ]
    assert [(state["phase"], state["reason"]) for state in states] == [
        ("precenter", "precenter_size"),
        ("precenter", "accepted"),
        ("postcenter", "accepted"),
    ]
    candidate = states[1]
    assert candidate["requested_scale"] == (5, 1)
    assert candidate["actual_scale_ratio"] == (5.0, 1.0)
    assert candidate["use_sheet_scale"] == 0
    assert candidate["view_name"] == "Drawing View1"
    assert candidate["orientation"] == "*Front"
    assert candidate["source_path"] == str(view.source)
    assert candidate["configuration"] == "Supplier"
    before = candidate["outline_before_refresh_m"]
    after = candidate["outline_after_refresh_m"]
    assert before[2] - before[0] == pytest.approx(1.6)
    assert after[2] - after[0] == pytest.approx(1.0)
    assert candidate["fit_bounds_m"] == after
    assert candidate["width_excess_m"] == pytest.approx(0.0)
    assert candidate["height_excess_m"] < 0.0
    settled = states[-1]
    assert settled["outline_before_refresh_m"] != settled["outline_after_refresh_m"]
    assert settled["center_error_m"] == pytest.approx((0.0, 0.0))
    assert set(settled["containment_excess_m"]) == {"left", "bottom", "right", "top"}
    assert all(value <= 1e-12 for value in settled["containment_excess_m"].values())


@pytest.mark.parametrize(
    "failure", ("degenerate", "short", "nonfinite", "getter-error")
)
def test_fit_views_ignores_unusable_pre_refresh_diagnostics(
    monkeypatch, tmp_path, failure
):
    records = _native_fit_records(monkeypatch)

    class InvalidStaleOutline(_RefreshedOutlineView):
        def GetOutline(self):
            if (
                self._display_ratio != self._scale[0] / self._scale[1]
                or self._display_position != self.Position
            ):
                if failure == "getter-error":
                    raise RuntimeError("stale native outline unavailable")
                return {
                    "degenerate": (0.0, 0.0, 0.0, 0.0),
                    "short": (0.0, 0.0, 1.0),
                    "nonfinite": (0.0, 0.0, float("nan"), 1.0),
                }[failure]
            return super().GetOutline()

    view = InvalidStaleOutline(tmp_path / "supplier.SLDPRT", display_ratio=0.0)
    cells = (("*Front", (0.5, 0.5), (0.0, 0.0, 1.0, 1.0)),)
    assert purchased._fit_views(_Drawing(), [view], cells) == {"*Front": (5, 1)}
    assert view.Position == pytest.approx((0.375, 0.5625))
    states = [
        state for name, state in records if name == "drawing.purchased_fit_candidate"
    ]
    assert [state["phase"] for state in states] == [
        "precenter",
        "precenter",
        "postcenter",
    ]
    for state in states:
        assert "outline_before_refresh_m" not in state
        assert "outline_before_refresh_error" in state
        assert state["fit_bounds_m"] == state["outline_after_refresh_m"]


@pytest.mark.parametrize("phase", ("candidate", "postcenter"))
@pytest.mark.parametrize(
    "outline",
    (
        (0.0, 0.0, 1.0),
        (0.0, 0.0, float("nan"), 1.0),
        (1.0, 0.0, 0.0, 1.0),
        (0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
    ),
    ids=("short", "nonfinite", "inverted", "degenerate", "zero-height"),
)
def test_fit_group_refresh_retains_native_extent_guard(
    monkeypatch, tmp_path, outline, phase
):
    _native_fit_records(monkeypatch)

    class BrokenRefresh(_RefreshedOutlineView):
        def GetOutline(self):
            if self.refreshes and (phase == "candidate" or self.moves):
                return outline
            return super().GetOutline()

    view = BrokenRefresh(tmp_path / "supplier.SLDPRT")
    members = [(view, ("*Front", (0.5, 0.5), (0.0, 0.0, 1.0, 1.0)))]
    with pytest.raises(RuntimeError, match="native extent"):
        purchased._fit_group(_Drawing(), members)
    assert len(view.refreshes) == (1 if phase == "candidate" else 3)
    assert len(view.moves) == (0 if phase == "candidate" else 1)


@pytest.mark.parametrize(
    ("key", "method"),
    (("view_name", "GetName2"), ("source_path", "GetReferencedModelName")),
)
def test_fit_group_metadata_failure_is_diagnostic(monkeypatch, tmp_path, key, method):
    records = _native_fit_records(monkeypatch)
    view = _RefreshedOutlineView(tmp_path / "supplier.SLDPRT")

    def unavailable():
        raise RuntimeError("native metadata getter unavailable")

    setattr(view, method, unavailable)
    members = [(view, ("*Front", (0.5, 0.5), (0.0, 0.0, 1.0, 1.0)))]
    assert purchased._fit_group(_Drawing(), members) == (5, 1)
    for _name, state in records:
        assert key not in state
        assert "native metadata getter unavailable" in state["metadata_errors"][key]
        assert state["actual_scale_ratio"] == tuple(
            float(value) for value in state["requested_scale"]
        )


def test_fit_group_records_postcenter_containment_rejection(monkeypatch, tmp_path):
    records = _native_fit_records(monkeypatch)

    class ExpandedAfterCenter(_RefreshedOutlineView):
        def GetOutline(self):
            left, bottom, right, top = super().GetOutline()
            if self.moves and self.ScaleRatio == (5.0, 1.0):
                left, right = left - 0.1, right + 0.1
            return left, bottom, right, top

    view = ExpandedAfterCenter(tmp_path / "supplier.SLDPRT")
    members = [(view, ("*Front", (0.5, 0.5), (0.0, 0.0, 1.0, 1.0)))]
    assert purchased._fit_group(_Drawing(), members) == (4, 1)
    rejected = [
        state for _name, state in records if state["reason"] == "postcenter_containment"
    ]
    assert len(rejected) == 1
    state = rejected[0]
    assert state["phase"] == "postcenter" and state["requested_scale"] == (5, 1)
    assert state["center_error_m"] == pytest.approx((0.0, 0.0))
    assert state["width_excess_m"] == pytest.approx(0.2)
    assert state["containment_excess_m"]["left"] == pytest.approx(0.1)
    assert state["containment_excess_m"]["right"] == pytest.approx(0.1)
    assert state["containment_excess_m"]["bottom"] < 0.0
    assert state["containment_excess_m"]["top"] < 0.0


def test_fit_group_records_center_failure_without_refitting(monkeypatch, tmp_path):
    records = _native_fit_records(monkeypatch)

    class Unmoved(_RefreshedOutlineView):
        def SetViewPosition(self, position, move_children):
            self.moves.append(tuple(position))
            return True  # A lying success must still fail authoritative bounds.

    view = Unmoved(tmp_path / "supplier.SLDPRT")
    members = [(view, ("*Front", (0.5, 0.5), (0.0, 0.0, 1.0, 1.0)))]
    with pytest.raises(RuntimeError, match="native view failed to center"):
        purchased._fit_group(_Drawing(), members)
    assert view.scales == [(8.0, 1.0), (5.0, 1.0)]
    state = records[-1][1]
    assert state["phase"] == "postcenter"
    assert state["reason"] == "postcenter_containment"
    assert state["center_error_m"] == pytest.approx((-0.125, -0.3125))


def test_fit_group_custom_reader_keeps_refresh_ownership(monkeypatch, tmp_path):
    records = _native_fit_records(monkeypatch)

    class CustomView(_RefreshedOutlineView):
        def GetOutline(self):
            raise AssertionError("custom geometry must not read native outlines")

        def UpdateViewDisplayGeometry(self):
            raise AssertionError("custom reader owns its refresh")

    view = CustomView(tmp_path / "supplier.SLDPRT")
    reads = []

    def custom_bounds(actual_view, _name):
        reads.append((actual_view.ScaleRatio, actual_view.Position))
        ratio = actual_view.ScaleRatio[0] / actual_view.ScaleRatio[1]
        x, y = actual_view.Position
        x, y = x + 0.125, y - 0.0625
        return x - 0.1 * ratio, y - 0.02 * ratio, x + 0.1 * ratio, y + 0.02 * ratio

    members = [(view, ("*Front", (0.5, 0.5), (0.0, 0.0, 1.0, 1.0)))]
    assert purchased._fit_group(_Drawing(), members, read_bounds=custom_bounds) == (
        5,
        1,
    )
    assert [ratio for ratio, _position in reads] == [(8.0, 1.0), (5.0, 1.0), (5.0, 1.0)]
    assert len(view.moves) == 1 and view.refreshes == []
    for _name, state in records:
        assert state["bounds_kind"] == "custom"
        assert "outline_before_refresh_m" not in state
        assert "outline_after_refresh_m" not in state


@pytest.mark.parametrize("result_kind", ("scalar", "short-tuple", "long-tuple"))
def test_supplier_read_only_open_refuses_unmeasured_native_status(
    monkeypatch,
    tmp_path,
    result_kind,
):
    case = _supplier_read_only_case(monkeypatch, tmp_path)
    result = {
        "scalar": case.model,
        "short-tuple": (case.model, 0),
        "long-tuple": (case.model, 0, 0, 0),
    }[result_kind]
    case.app.OpenDoc6 = lambda *_args: result
    with pytest.raises(RuntimeError, match="unreadable supplier native open result"):
        purchased._open_supplier_source_read_only(
            case.adapter, case.source, label="supplier"
        )
    assert case.adapter.currentModel is None


def _source_checkpoint_case(monkeypatch, tmp_path):
    """Method/property-shaped SDK doubles; all evidence reads are production code."""
    source = tmp_path / "observed.SLDPRT"
    source.write_bytes(b"original supplier source")

    class Document:
        def __init__(self, path, kind=1):
            self.path = str(path)
            self.kind = kind
            self.read_only = kind == 1
            self.dirty = True
            self.native_id = object()
            self.closed = False

        def GetPathName(self):
            assert not self.closed
            return self.path

        def GetType(self):
            assert not self.closed
            return self.kind

        def IsOpenedReadOnly(self):
            assert not self.closed
            return self.read_only

        def GetSaveFlag(self):
            assert not self.closed
            return self.dirty

    original = Document(source)
    loaded = Document(source)
    loaded.native_id = original.native_id
    drawing = Document("", 3)
    app = SimpleNamespace(
        loaded=loaded,
        IsSame=lambda left, right: int(left.native_id is right.native_id),
    )
    app.GetOpenDocumentByName = lambda path: app.loaded
    adapter = SimpleNamespace(swApp=app, currentModel=drawing)
    views = []
    evidence = []
    events = []
    monkeypatch.setattr(purchased, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(purchased, "iter_views", lambda _adapter: iter(views))
    monkeypatch.setattr(
        purchased._telemetry,
        "event",
        lambda name, **fields: events.append((name, fields)),
    )
    checkpoint = purchased._supplier_source_checkpoint(
        adapter,
        source,
        original,
        purchased._source_file_sha256(source),
        label="observed",
        evidence=evidence,
        configuration="Supplier",
    )
    checkpoint("after_new_document")

    def add_view():
        view = _View("*Front", source, (0.1, 0.1))
        view.ReferencedDocument = loaded
        view.ReferencedConfiguration = "Supplier"
        views.append(view)
        return view

    return SimpleNamespace(
        source=source,
        original=original,
        loaded=loaded,
        drawing=drawing,
        app=app,
        adapter=adapter,
        views=views,
        evidence=evidence,
        events=events,
        checkpoint=checkpoint,
        add_view=add_view,
        Document=Document,
    )


@pytest.mark.parametrize(
    "defect",
    (
        "lost-ro",
        "loaded-identity",
        "reference-identity",
        "reference-ro",
        "reference-path",
        "boolean-identity",
        "boolean-type",
        "wrong-receiver",
    ),
)
def test_source_checkpoint_rejects_native_transition_during_view_creation(
    monkeypatch, tmp_path, defect
):
    import json
    import _drawing_common as common

    case = _source_checkpoint_case(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match="source checkpoint after_create_view"):
        with common._drawing_checkpoint(case.checkpoint, "create_view:*Front"):
            view = case.add_view()
            if defect == "lost-ro":
                case.original.read_only = False
            elif defect == "loaded-identity":
                case.app.loaded = case.Document(case.source)
            elif defect == "reference-identity":
                view.ReferencedDocument = case.Document(case.source)
            elif defect == "reference-ro":
                case.loaded.read_only = False
            elif defect == "reference-path":
                case.loaded.path = str(tmp_path / "foreign.SLDPRT")
            elif defect == "boolean-identity":
                case.app.IsSame = lambda left, right: left.native_id is right.native_id
            elif defect == "boolean-type":
                case.original.kind = True
            else:
                case.adapter.currentModel = case.original
    row = case.evidence[-1]
    assert row["phase"] == "after_create_view:*Front"
    assert row["failures"]
    assert row["views"][0]["name"] == "*Front"
    assert row["views"][0]["referenced_document"]["present"] is True
    assert json.loads(case.events[-1][1]["source_state"]) == row
    assert case.source.read_bytes() == b"original supplier source"


def test_source_checkpoint_observes_configuration_selection_and_dirty_presentation(
    monkeypatch, tmp_path
):
    case = _source_checkpoint_case(monkeypatch, tmp_path)
    view = case.add_view()
    view.ReferencedConfiguration = "Default"
    for phase in (
        "after_create_view:*Front",
        "after_select_configuration:*Front",
        "before_create_view:*Top",
        "after_create_view:*Top",
        "after_select_configuration:*Top",
    ):
        case.checkpoint(phase)
        assert case.evidence[-1]["views"][0]["configuration"] == "Default"
        assert case.evidence[-1]["views"][0]["configuration_selection_pending"] is True
        assert not case.evidence[-1]["failures"]
    # The existing selection rebuild reconciles the native readback.
    view.ReferencedConfiguration = "Supplier"
    case.checkpoint("after_configuration_rebuild")
    assert case.evidence[-1]["views"][0]["configuration_selection_pending"] is False
    case.checkpoint("after_supplier_formatting")
    case.checkpoint("last_settled")
    assert case.evidence[-1]["original_source"]["save_flag"] is True
    assert not case.evidence[-1]["failures"]
    view.ReferencedConfiguration = "Other"
    with pytest.raises(RuntimeError, match="configuration mismatch"):
        case.checkpoint("last_settled")


def test_source_checkpoint_rejects_wrong_configuration_after_selection_rebuild(
    monkeypatch, tmp_path
):
    case = _source_checkpoint_case(monkeypatch, tmp_path)
    view = case.add_view()
    view.ReferencedConfiguration = "Default"
    case.checkpoint("after_select_configuration:*Front")
    with pytest.raises(RuntimeError, match="configuration mismatch"):
        case.checkpoint("after_configuration_rebuild")
    assert case.evidence[-1]["phase"] == "after_configuration_rebuild"
    assert case.evidence[-1]["views"][0]["configuration"] == "Default"
    assert case.evidence[-1]["views"][0]["configuration_selection_pending"] is False


@pytest.mark.parametrize("cross_result", (2, "error"))
@pytest.mark.parametrize("positive_result", (1, 0, 2, True, "error"))
def test_source_checkpoint_cross_document_comparison_is_diagnostic_only(
    monkeypatch, tmp_path, cross_result, positive_result
):
    case = _source_checkpoint_case(monkeypatch, tmp_path)
    case.add_view()

    def same(left, right):
        if left is case.drawing and right is case.original:
            if cross_result == "error":
                raise OSError("cross-document comparison unsupported")
            return cross_result
        if positive_result == "error":
            raise OSError("positive identity unreadable")
        return positive_result

    case.app.IsSame = same
    if type(positive_result) is int and positive_result == 1:
        case.checkpoint("last_settled")
        assert not case.evidence[-1]["failures"]
    else:
        with pytest.raises(RuntimeError, match="native identity mismatch"):
            case.checkpoint("last_settled")
    row = case.evidence[-1]
    assert row["drawing_receiver"]["type"] == 3
    assert row["original_source"]["type"] == 1
    assert row["drawing_receiver"]["original_source_identity"] == (
        None if cross_result == "error" else 2
    )
    if cross_result == "error":
        assert any(
            error["message"] == "cross-document comparison unsupported"
            for error in row["errors"]
        )


@pytest.mark.parametrize("kind", ("drawing", "pdf"))
def test_source_checkpoint_identifies_first_mutating_artifact_boundary(
    monkeypatch, tmp_path, kind
):
    import contextlib
    import _drawing_common as common
    from solidworks_mcp.adapters.solidworks import drawing as native_drawing

    case = _source_checkpoint_case(monkeypatch, tmp_path)
    case.add_view()
    outputs = {
        name: tmp_path / f"observed.{suffix}"
        for name, suffix in (
            ("drawing", "SLDDRW"),
            ("pdf", "pdf"),
        )
    }
    saved = []

    def save(path, version, options, export_data, advanced_options, errors, warnings):
        assert (version, options, export_data, advanced_options, errors, warnings) == (
            0,
            1,
            None,
            None,
            0,
            0,
        )
        saved.append(Path(path).suffix)
        Path(path).write_bytes(b"completed native output")
        if Path(path) == outputs[kind]:
            case.source.write_bytes(b"persisted despite read-only")
        return True, 0, 0

    extension = SimpleNamespace(SaveAs3=save)
    case.drawing.Extension = extension

    def bind_extension(value, interface):
        assert value is extension and interface == "IModelDocExtension"
        return extension

    monkeypatch.setattr(native_drawing._sw_type_info, "early_bound", bind_extension)
    monkeypatch.setattr(native_drawing, "_draw", lambda adapter: adapter.currentModel)
    monkeypatch.setattr(
        common, "pdf_shaded_raster_dpi", lambda *_args: contextlib.nullcontext()
    )
    with pytest.raises(RuntimeError, match=f"source checkpoint after_{kind}_save"):
        native_drawing.save_drawing(
            case.adapter,
            str(outputs["drawing"]),
            pdf_path=str(outputs["pdf"]),
            artifact_context=lambda name, path: common._drawing_artifact_save(
                case.adapter, name, path, case.checkpoint
            ),
        )
    phases = [row["phase"] for row in case.evidence]
    assert phases[-2:] == [f"before_{kind}_save", f"after_{kind}_save"]
    assert all(not row["failures"] for row in case.evidence[:-1])
    assert case.evidence[-1]["original_source"]["read_only"] is True
    assert case.evidence[-1]["current_sha256"] != case.evidence[-1]["expected_sha256"]
    assert saved == ([".SLDDRW"] if kind == "drawing" else [".SLDDRW", ".pdf"])
    assert outputs[kind].read_bytes() == b"completed native output"


@pytest.mark.parametrize("operation", ("drawing_save", "pdf_save", "drawing_close"))
@pytest.mark.parametrize("error_type", (RuntimeError, asyncio.CancelledError))
def test_source_checkpoint_after_failure_preserves_native_primary(
    monkeypatch, tmp_path, operation, error_type
):
    import _drawing_common as common

    case = _source_checkpoint_case(monkeypatch, tmp_path)
    case.add_view()
    original = error_type("native operation failed")
    with pytest.raises(error_type) as caught:
        with common._drawing_checkpoint(case.checkpoint, operation):
            case.source.write_bytes(b"native failed after source mutation")
            raise original
    assert caught.value is original
    assert case.evidence[-1]["phase"] == f"after_{operation}"
    assert f"after_{operation} checkpoint also failed" in "\n".join(original.__notes__)


def test_source_checkpoint_before_refusal_does_not_attempt_save(monkeypatch, tmp_path):
    import _drawing_common as common

    case = _source_checkpoint_case(monkeypatch, tmp_path)
    case.add_view()
    case.original.read_only = False
    attempted = []
    with pytest.raises(RuntimeError, match="before_drawing_save"):
        with common._drawing_checkpoint(case.checkpoint, "drawing_save"):
            attempted.append("save")
    assert attempted == []
    assert case.evidence[-1]["phase"] == "before_drawing_save"


@pytest.mark.parametrize("source_closed", (False, True))
def test_source_checkpoint_after_close_avoids_closed_handles(
    monkeypatch, tmp_path, source_closed
):
    case = _source_checkpoint_case(monkeypatch, tmp_path)
    case.add_view()
    case.checkpoint("before_drawing_close")
    case.drawing.closed = True

    def forbidden(_adapter):
        raise AssertionError("closed views must not be queried")

    monkeypatch.setattr(purchased, "iter_views", forbidden)
    if source_closed:
        case.app.loaded = None
        case.original.closed = case.loaded.closed = True
    case.checkpoint("after_drawing_close")
    row = case.evidence[-1]
    assert row["loaded_source_present"] is not source_closed
    assert row["views"] == []
    assert row["current_sha256"] == row["expected_sha256"]
    case.source.write_bytes(b"changed after close")
    with pytest.raises(RuntimeError, match="bytes changed"):
        case.checkpoint("after_drawing_close")


@pytest.mark.parametrize("failure", (None, "drawing_save", "pdf_save", "drawing_close"))
@pytest.mark.parametrize("error_type", (RuntimeError, asyncio.CancelledError))
def test_source_checkpoint_real_finalizer_boundaries_preserve_native_failure(
    monkeypatch, tmp_path, failure, error_type
):
    import contextlib
    import _drawing_common as common
    from solidworks_mcp.adapters.solidworks import drawing as native_drawing

    case = _source_checkpoint_case(monkeypatch, tmp_path)
    case.add_view()
    draw = case.drawing
    sheet = _Sheet()
    sheet._properties = (0, 0, 1.0, 1.0, False, 0.4318, 0.2794, False)
    sheet.SetScale = lambda *_args: True
    sheet.GetViews = lambda: case.views
    draw.GetSheetNames = lambda: ("Sheet1",)
    draw.ActivateSheet = lambda _name: True
    draw.GetCurrentSheet = lambda: sheet
    draw.Sheet = lambda _name: sheet
    draw.ClearSelection2 = lambda _append: None
    draw.EditRebuild3 = lambda: True
    draw.GetTitle = lambda: "observed.SLDDRW"
    outputs = common.DrawingOutputs(
        slddrw=tmp_path / "observed.SLDDRW",
        pdf=tmp_path / "observed.pdf",
        png=tmp_path / "observed.png",
    )
    layout = tmp_path / "observed.layout.json"
    original = error_type("actual native boundary failed")
    operations = []

    def attempt(operation):
        operations.append(operation)
        if failure == operation:
            case.source.write_bytes(b"native mutation before failure")
            raise original

    def save(path, version, options, export_data, advanced_options, errors, warnings):
        assert (version, options, export_data, advanced_options, errors, warnings) == (
            0,
            1,
            None,
            None,
            0,
            0,
        )
        Path(path).write_bytes(b"native output")
        if Path(path).suffix == ".SLDDRW":
            draw.path = path
            attempt("drawing_save")
        else:
            attempt("pdf_save")
        return True, 0, 0

    def close(title):
        assert title == "observed.SLDDRW"
        draw.closed = True
        attempt("drawing_close")

    extension = SimpleNamespace(SaveAs3=save)
    draw.Extension = extension

    def bind_extension(value, interface):
        assert value is extension and interface == "IModelDocExtension"
        return extension

    monkeypatch.setattr(native_drawing._sw_type_info, "early_bound", bind_extension)
    case.app.CloseDoc = close

    def member(target, name):
        value = getattr(target, name)
        return value() if callable(value) else value

    case.adapter._get_attr_or_call = member
    monkeypatch.setattr(common, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        common._sw_type_info, "early_bound_or_flag", lambda value, *_args: value
    )
    monkeypatch.setattr(native_drawing, "_draw", lambda adapter: adapter.currentModel)
    monkeypatch.setattr(common, "iter_views", lambda _adapter: iter(case.views))
    monkeypatch.setattr(common, "_build_id", lambda: "inert-source-test")
    for name in (
        "apply_custom_properties",
        "assert_asme_b_sheet",
        "assert_precise_isometric_views",
        "sanitize_pdf_metadata",
    ):
        monkeypatch.setattr(common, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        common,
        "read_required_properties",
        lambda *_args, **_kwargs: {"TOL_LIN_XX": "±0.51"},
    )
    monkeypatch.setattr(
        common, "pdf_shaded_raster_dpi", lambda *_args: contextlib.nullcontext()
    )
    monkeypatch.setattr(
        common,
        "render_pdf_png",
        lambda _pdf, png, **_kwargs: png.write_bytes(b"rendered output"),
    )
    monkeypatch.setattr(common, "layout_report_path", lambda _stem: layout)
    monkeypatch.setattr(
        common,
        "run_layout_audit",
        lambda _adapter, *, report, **_kwargs: report.write_text("{}"),
    )
    monkeypatch.setattr(common, "_visible_document_paths", lambda _adapter: ())

    async def finalize():
        return await common.finalize_drawing(
            case.adapter,
            outputs,
            layout=DrawingLayout.LANDSCAPE,
            pdf_title="Observed source",
            settled_checks=(lambda: case.checkpoint("last_settled"),),
            checkpoint=case.checkpoint,
        )

    if failure is None:
        result = asyncio.run(finalize())
        assert set(result) == {"drawing", "pdf", "png"}
        assert operations == ["drawing_save", "pdf_save", "drawing_close"]
        assert [row["phase"] for row in case.evidence][-7:] == [
            "last_settled",
            "before_drawing_save",
            "after_drawing_save",
            "before_pdf_save",
            "after_pdf_save",
            "before_drawing_close",
            "after_drawing_close",
        ]
        assert not any(row["failures"] for row in case.evidence)
    else:
        with pytest.raises(error_type) as caught:
            asyncio.run(finalize())
        assert caught.value is original
        assert case.evidence[-1]["phase"] == f"after_{failure}"
        assert f"after_{failure} checkpoint also failed" in "\n".join(
            original.__notes__
        )
        assert operations[-1] == failure
        assert (
            len(operations)
            == ("drawing_save", "pdf_save", "drawing_close").index(failure) + 1
        )
    assert outputs.slddrw.read_bytes() == b"native output"
    if failure != "drawing_save":
        assert outputs.pdf.read_bytes() == b"native output"
    if failure in (None, "drawing_close"):
        assert outputs.png.read_bytes() == b"rendered output"
        assert layout.read_text() == "{}"


def test_source_checkpoint_finalizer_rejects_noncallable_before_native_work(tmp_path):
    import _drawing_common as common

    with pytest.raises(TypeError, match="checkpoint must be callable"):
        asyncio.run(
            common.finalize_drawing(
                object(),
                common.DrawingOutputs(
                    slddrw=tmp_path / "unused.SLDDRW",
                    pdf=tmp_path / "unused.pdf",
                    png=tmp_path / "unused.png",
                ),
                layout=DrawingLayout.LANDSCAPE,
                pdf_title="unused",
                checkpoint=object(),
            )
        )


@pytest.mark.parametrize("lane", ("fastener", "spring", "part"))
def test_source_checkpoint_public_wrappers_reject_and_retain_native_transition(
    monkeypatch, tmp_path, lane
):
    import json
    import _purchased_part_drawing as part

    case = _purchased_source_lifecycle(monkeypatch, tmp_path, lane)
    views = []
    monkeypatch.setattr(purchased, "iter_views", lambda _adapter: iter(views))

    async def create_sheet(adapter, _spec, *, source_checkpoint, **_kwargs):
        drawing = _Drawing()
        drawing.native_id = object()
        adapter.currentModel = drawing
        source_checkpoint("after_new_document")
        view = _View("*Front", case.source, (0.1, 0.1))
        view.ReferencedDocument = case.readback
        views.append(view)
        # Same name and native identity, but the view load lost read-only mode.
        case.readback.read_only = False
        source_checkpoint("after_create_view:*Front")
        pytest.fail("source transition was not refused")

    monkeypatch.setattr(
        part if lane == "part" else purchased, "_build_reference_sheet", create_sheet
    )
    with pytest.raises(RuntimeError, match="source checkpoint after_create_view"):
        case.run()
    (report_path,) = tuple((tmp_path / "failures").glob("*/*/capture.json"))
    report = json.loads(report_path.read_text())
    observed = report["context"]["source_lifecycle"]
    if isinstance(observed, str):
        observed = json.loads(observed)
    assert observed[-1]["phase"] == "after_create_view:*Front"
    assert observed[-1]["loaded_source"]["read_only"] is False
    assert observed[-1]["original_loaded_identity"] == 1
    assert report["capture_mode"] == "no_followup_com"
    assert report["retained_pdf"]["status"] == "missing"
    assert case.source.read_bytes() == b"unchanged supplier bytes"


def test_source_checkpoint_records_native_read_errors_before_refusing(
    monkeypatch, tmp_path
):
    import json

    case = _source_checkpoint_case(monkeypatch, tmp_path)
    view = case.add_view()

    def unreadable():
        raise OSError("native source path unavailable")

    view.GetReferencedModelName = unreadable
    with pytest.raises(RuntimeError, match="unreadable source_path"):
        case.checkpoint("after_create_view:*Front")
    row = case.evidence[-1]
    assert row["views"][0]["source_path"] is None
    assert {
        "field": "source_path",
        "type": "OSError",
        "message": "native source path unavailable",
    } in row["errors"]
    assert json.loads(case.events[-1][1]["source_state"]) == row


def test_source_checkpoint_failure_capture_cannot_replace_primary(
    monkeypatch, tmp_path
):
    original = asyncio.CancelledError("native primary")

    def failed_capture(*_args, **_kwargs):
        raise KeyboardInterrupt("secondary capture interruption")

    monkeypatch.setattr(
        purchased._seat_forensics, "capture_com_failure", failed_capture
    )
    spec = SimpleNamespace(
        artifact_stem="supplier",
        source=tmp_path / "supplier.SLDPRT",
        outputs={
            kind: tmp_path / f"supplier.{suffix}"
            for kind, suffix in (
                ("slddrw", "SLDDRW"),
                ("pdf", "pdf"),
                ("png", "png"),
            )
        },
    )
    with pytest.raises(asyncio.CancelledError) as caught:
        purchased._retain_supplier_source_failure(spec, original, [])
    assert caught.value is original
    assert "secondary capture interruption" in "\n".join(original.__notes__)


@pytest.mark.parametrize(
    ("raw", "expression"),
    [
        ('$PRPSHEET:"SW-Title(Title)"', '$PRPSHEET:"SW-Title(Title)"'),
        (
            '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"',
            '$PRPSHEET:"SW-Title(Title)"',
        ),
        ('<FONT size=15.5PTS>$PRPSHEET:"Material"', '$PRPSHEET:"Material"'),
        ('<FONT size=0.5PTS>$PRPSHEET:"Material"', '$PRPSHEET:"Material"'),
    ],
)
def test_source_property_expression_accepts_only_the_optional_font_wrapper(
    raw: str, expression: str
) -> None:
    from _purchased_title_fit import source_property_expression

    assert source_property_expression(raw) == expression


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "ch-rocker-arm-tl-vn-oblique-pivot-screw",
        '$PRP:"SW-Title(Title)"',
        'NAME $PRPSHEET:"SW-Title(Title)"',
        '$PRPSHEET:"SW-Title(Title)" suffix',
        ' $PRPSHEET:"SW-Title(Title)"',
        '$PRPSHEET:"SW-Title(Title)" ',
        '$PRPSHEET:"SW-Title(Title)"$PRPSHEET:"Material"',
        '$PRPSHEET:"SW-Title(Title)"\n$PRPSHEET:"Material"',
        '$PRPSHEET:"SW-Title(Title)"\n',
        '$PRPSHEET:"SW-Title(Title)',
        '$PRPSHEET:SW-Title(Title)',
        '<B>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"</FONT>',
        '<FONT size=15PTS><FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS> $PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS>$PRP:"SW-Title(Title)"',
        '<FONT size=15PTS>literal',
        '<FONT size=0PTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=-15PTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=+15PTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=1e1PTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=NaNPTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=infPTS>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PX>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size="15PTS">$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS color=red>$PRPSHEET:"SW-Title(Title)"',
        '<FONT size=15PTS$PRPSHEET:"SW-Title(Title)"',
        '<font size=15PTS>$PRPSHEET:"SW-Title(Title)"',
    ],
)
def test_source_property_expression_refuses_noncontract_content(raw: str) -> None:
    from _purchased_title_fit import source_property_expression

    assert source_property_expression(raw) is None


def test_linked_value_preserves_captured_name_when_native_format_strips_font() -> None:
    from _purchased_title_fit import assert_linked_value

    # Captured native SetTextFormat readback: only FONT disappears; the full
    # source property and resolved Name remain intact. This is not a COM echo.
    assert_linked_value(
        '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"',
        "ch-rocker-arm-tl-vn-oblique-pivot-screw",
        '$PRPSHEET:"SW-Title(Title)"',
        "ch-rocker-arm-tl-vn-oblique-pivot-screw",
        label="Name",
    )


def test_linked_value_accepts_exact_wrapped_material_without_normalizing_text() -> None:
    from _purchased_title_fit import assert_linked_value

    # Synthetic identity control, not native after-fix evidence.
    assert_linked_value(
        '<FONT size=15PTS>$PRPSHEET:"Material"',
        "ALLOY STEEL",
        '$PRPSHEET:"Material"',
        "ALLOY STEEL",
        label="Material",
    )


@pytest.mark.parametrize(
    ("actual_link", "actual_text"),
    [
        pytest.param(
            '$PRPSHEET:"Title"',
            "ch-rocker-arm-tl-vn-oblique-pivot-screw",
            id="different-property-even-with-identical-resolved-text",
        ),
        pytest.param(
            '$PRP:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot-screw",
            id="different-property-owner",
        ),
        pytest.param(
            "ch-rocker-arm-tl-vn-oblique-pivot-screw",
            "ch-rocker-arm-tl-vn-oblique-pivot-screw",
            id="literal-replacement",
        ),
        pytest.param(
            'NAME $PRPSHEET:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot-screw",
            id="extra-prefix",
        ),
        pytest.param(
            '$PRPSHEET:"SW-Title(Title)" suffix',
            "ch-rocker-arm-tl-vn-oblique-pivot-screw",
            id="extra-suffix",
        ),
        pytest.param(
            '$PRPSHEET:"SW-Title(Title)"$PRPSHEET:"Material"',
            "ch-rocker-arm-tl-vn-oblique-pivot-screw",
            id="second-link",
        ),
        pytest.param(
            '<B>$PRPSHEET:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot-screw",
            id="unsupported-markup",
        ),
        pytest.param(
            '<FONT size=15PTS$PRPSHEET:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot-screw",
            id="malformed-font",
        ),
        pytest.param(
            '$PRPSHEET:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot",
            id="truncated-full-value",
        ),
        pytest.param(
            '$PRPSHEET:"SW-Title(Title)"',
            "ch-rocker-arm-tl-vn-oblique-pivot-screw ",
            id="value-whitespace-is-not-normalized",
        ),
        pytest.param(
            '$PRPSHEET:"SW-Title(Title)"',
            "CH-ROCKER-ARM-TL-VN-OBLIQUE-PIVOT-SCREW",
            id="value-case-is-not-normalized",
        ),
    ],
)
def test_linked_value_refuses_true_identity_or_full_value_changes(
    actual_link: str, actual_text: str
) -> None:
    from _purchased_title_fit import assert_linked_value

    expected_link = '<FONT size=15PTS>$PRPSHEET:"SW-Title(Title)"'
    expected_text = "ch-rocker-arm-tl-vn-oblique-pivot-screw"
    with pytest.raises(RuntimeError) as caught:
        assert_linked_value(
            expected_link, expected_text, actual_link, actual_text, label="Name"
        )
    message = str(caught.value)
    for raw in (expected_link, expected_text, actual_link, actual_text):
        assert repr(raw) in message


@pytest.mark.parametrize(
    "invalid_link",
    [
        'NAME $PRPSHEET:"SW-Title(Title)"',
        '<FONT size=0PTS>$PRPSHEET:"SW-Title(Title)"',
        '$PRP:"SW-Title(Title)"',
        "literal",
    ],
)
def test_linked_value_refuses_invalid_expected_link_even_when_unchanged(
    invalid_link: str,
) -> None:
    from _purchased_title_fit import assert_linked_value

    text = "ch-rocker-arm-tl-vn-oblique-pivot-screw"
    with pytest.raises(RuntimeError) as caught:
        assert_linked_value(invalid_link, text, invalid_link, text, label="Name")
    assert repr(invalid_link) in str(caught.value)
    assert repr(text) in str(caught.value)


def test_note_fits_cell_refuses_captured_native_name_overflow() -> None:
    from _purchased_title_fit import note_fits_cell

    box = (0.310260575, 0.032472074, 0.409863405, 0.042956582)
    ruled_cell = (0.3083506, 0.035906, 0.4191, 0.0475164)
    inset = 0.0006
    limit = (
        ruled_cell[0] + inset,
        ruled_cell[1] + inset,
        ruled_cell[2] - inset,
        ruled_cell[3] - inset,
    )
    assert not note_fits_cell(box, 2, limit)
    # The captured bottom edge also fails independently of its two-row state.
    assert not note_fits_cell(box, 1, limit)


@pytest.mark.parametrize(
    ("box", "fits"),
    [
        pytest.param((2.0, 3.0, 8.0, 7.0), True, id="interior"),
        pytest.param((1.0, 2.0, 9.0, 8.0), True, id="all-four-boundaries"),
        pytest.param((0.999, 3.0, 8.0, 7.0), False, id="left-overflow"),
        pytest.param((2.0, 1.999, 8.0, 7.0), False, id="bottom-overflow"),
        pytest.param((2.0, 3.0, 9.001, 7.0), False, id="right-overflow"),
        pytest.param((2.0, 3.0, 8.0, 8.001), False, id="top-overflow"),
        pytest.param((0.0, 1.0, 10.0, 9.0), False, id="center-inside-edges-outside"),
    ],
)
def test_note_fits_cell_synthetic_four_edge_predicate_controls(
    box: tuple[float, ...], fits: bool
) -> None:
    from _purchased_title_fit import note_fits_cell

    # Mathematical predicate controls only, never native after-fix proof.
    assert note_fits_cell(box, 1, (1.0, 2.0, 9.0, 8.0)) is fits


@pytest.mark.parametrize("rows", [-1, 0, 1, 2, 3])
def test_note_fits_cell_synthetic_row_count_predicate_controls(rows: int) -> None:
    from _purchased_title_fit import note_fits_cell

    # Mathematical predicate controls only, never native after-fix proof.
    assert note_fits_cell((2.0, 3.0, 8.0, 7.0), rows, (1.0, 2.0, 9.0, 8.0)) is (
        rows == 1
    )


def _washer_paint_native(monkeypatch, case):
    """Replay R48 native paint; only native I/O is doubled, not placement/math."""
    washer = case.helper
    thick, outer, bore = washer.THICKNESS, washer.OUTER_DIAMETER, washer.BORE_DIAMETER
    # Retained native paint, metres: R48 thickness/bore and R50 outer diameter.
    # Include complete limits/qualifier blocks, not nominal-value surrogates.
    records = {
        thick: dict(type=4, pos=[.144901, .23, .0000039], display=dict(
            lines=[
                [0, 0, 0, 0, .126313, .232275, 0, .145901, .232275, 0],
                [0, 0, 0, 0, .126313, .227725, 0, .145901, .227725, 0],
                [0, 0, 0, 0, .144901, .232275, 0, .144901, .238625, 0],
                [0, 0, 0, 0, .144901, .227725, 0, .144901, .221375, 0],
            ],
            arrows=[
                [.144901, .232275, 0, 0, 1, 0, .003556, .000762, 0, 0, 0, 1],
                [.144901, .227725, 0, 0, -1, 0, .003556, .000762, 0, 0, 0, 1],
            ],
            texts=[
                dict(t=" (", pos=[.1335333, .2274941, 0], w=.0030139),
                dict(t="0.043", pos=[.1365472, .23, 0], w=.0116375),
                dict(t="0.029", pos=[.1365472, .2254743, 0], w=.0116375),
                dict(t=" in) ", pos=[.1481847, .2274941, 0], w=.008084),
            ],
        )),
        outer: dict(type=4, pos=[.1364005, .1455, -.0019651], display=dict(
            lines=[
                [0, 0, 0, 0, .1162203, .1443043, 0, .1130599, .1426951, 0],
                [0, 0, 0, 0, .0737797, .1226957, 0, .1162203, .1443043, 0],
            ],
            arrows=[[.1162203, .1443043, 0, .8911429, .4537227, 0,
                     .003556, .000762, 0, 0, 0, -1]],
            texts=[
                dict(t=" (", pos=[.1146474, .1427486, 0], w=.0030139),
                dict(t="<MOD-DIAM>", pos=[.1176613, .1426951, 0], w=.0052784),
                dict(t="0.375 ±0.002 in) ", pos=[.1229397, .1427486, 0], w=.0352139),
            ],
        )),
        bore: dict(type=4, pos=[.140401, .12025, -.002275], display=dict(
            lines=[
                [0, 0, 0, 0, .1041185, .1234101, 0, .1131371, .114667, 0],
                [0, 0, 0, 0, .0858815, .1410899, 0, .1041185, .1234101, 0],
                [0, 0, 0, 0, .1131371, .114667, 0, .1660774, .114667, 0],
            ],
            arrows=[[.1041185, .1234101, 0, .7179897, -.6960538, 0,
                     .003556, .000762, 0, 0, 0, -1]],
            texts=[
                dict(t="(", pos=[.1276871, .1202767, 0], w=.0017208),
                dict(t="<MOD-DIAM>", pos=[.129408, .1202233, 0], w=.0052784),
                dict(t="0.200 in)", pos=[.1346864, .1202767, 0], w=.0184285),
                dict(t="FOR No. 10 SCREW SIZE", pos=[.1147246, .114667, 0], w=.0513528),
            ],
        )),
    }
    face = case.views["*Top" if case.kwargs["axis"] == "y" else "*Front"]
    side = case.views["*Front" if case.kwargs["axis"] == "y" else "*Top"]
    for label, record in records.items():
        bounds = (side if label == thick else face).GetOutline()
        xy = (bounds[2] + (.014 if label == thick else .012),
              (bounds[1] + bounds[3]) / 2 + (0 if label == thick else (.012 if label == outer else -.012)))
        dx, dy = xy[0] - record["pos"][0], xy[1] - record["pos"][1]
        for row in record["display"]["lines"]:
            for index in (4, 7):
                row[index] += dx
                row[index + 1] += dy
        for arrow in record["display"]["arrows"]:
            arrow[0] += dx
            arrow[1] += dy
        for text in record["display"]["texts"]:
            text.update(h=.0035, ref=1, ang=0, font="Century Gothic", ls=.001)
            text["pos"][0] += dx
            text["pos"][1] += dy
        record["pos"][:2] = xy
    case.paint = {label: SimpleNamespace(record=record, settled_offset=False,
                                        offset_shift=0.0, clamp=False, reject=False,
                                        refuse_mode=False)
                  for label, record in records.items()}

    def position(label, x, y, _z):
        item = case.imports[label]
        paint = case.paint[label]
        if paint.reject:
            return False
        if paint.clamp:
            return True  # Native can report success but constrain the position.
        record = paint.record
        dx, dy = x - record["pos"][0], y - record["pos"][1]
        if label == thick and not item.display.OffsetText:
            # Linear OffsetText=False moves the physical dimension station.
            for index, row in enumerate(record["display"]["lines"]):
                row[7] += dx
                if index >= 2:
                    row[4] += dx
            for arrow in record["display"]["arrows"]:
                arrow[0] += dx
        for text in record["display"]["texts"]:
            text["pos"][0] += dx
            text["pos"][1] += dy
        record["pos"][:2] = (x, y)
        return True

    for label in records:
        item = case.imports[label]
        item.display.OffsetText = False
        item.annotation.SetPosition2 = lambda x, y, z, label=label: position(label, x, y, z)
        # Document default: smart arrows, solid two-arrow diameter line.
        item.display.ArrowSide, item.display.SolidLeader = 2, True
        item.second = SimpleNamespace(use_doc=True, arrow=True)
        item.display.SetSecondArrow = lambda use_doc, arrow, second=item.second: (
            vars(second).update(use_doc=use_doc, arrow=arrow))
        item.display.GetUseDocSecondArrow = lambda second=item.second: second.use_doc
        item.display.GetSecondArrow = lambda second=item.second: second.arrow

    def rebuild(_adapter, **_kwargs):
        paint = case.paint[thick]
        display = case.imports[thick].display
        if paint.refuse_mode:
            display.OffsetText = False
        if display.OffsetText and not paint.settled_offset:
            for text in paint.record["display"]["texts"]:
                text["pos"][0] += paint.offset_shift
            paint.settled_offset = True

    def record(_reader, annotation):
        label = next(label for label, item in case.imports.items()
                     if item.annotation is annotation)
        return copy.deepcopy(case.paint[label].record)

    monkeypatch.setattr(washer, "rebuild_drawing", rebuild)
    monkeypatch.setattr(washer, "_dump_annotation", record)

    rims = tuple(case.model.GetBodies2(0, False)[0].GetEdges())

    def circle_at(center, radius, *, axis, **_kwargs):
        matches = [edge for edge in rims if
                   all(abs(a * 1000 - b) < 1e-6 for a, b in zip(edge.GetCurve().CircleParams[:3], center))
                   and abs(edge.GetCurve().CircleParams[6] * 1000 - radius) < 1e-6
                   and tuple(edge.GetCurve().CircleParams[3:6]) == axis]
        assert len(matches) == 1
        return SimpleNamespace(edge=matches[0])

    monkeypatch.setattr(washer, "scan_view_edges",
                        lambda *_args, **_kwargs: SimpleNamespace(circle_at=circle_at))

    def native_diameter(_adapter, _view, rim, *, label, **_kwargs):
        item = case.imports[label]
        item.annotation.entities = (rim,)
        item.native.Tolerance.Type = 0
        return item.display

    monkeypatch.setattr(washer, "_native_diameter", native_diameter)
    for view in case.views.values():
        displays = [item.display for item in case.imports.values() if item.annotation.Owner is view]
        view.GetFirstDisplayDimension5 = lambda displays=displays: displays[0]
        for index, display in enumerate(displays):
            display.GetNext5 = lambda index=index, displays=displays: (
                displays[index + 1] if index + 1 < len(displays) else None
            )


def _washer_import_native(monkeypatch, *, defect=None, axis="y", values=None):
    """Native-I/O doubles; run the real body, source, no-band and import guards."""
    import _supplier_washer_drawing as washer
    import _supplier_washer_model as model_helpers

    for module in (washer, model_helpers):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(model_helpers, "_bind", lambda value, _interface: value)
    monkeypatch.setattr(model_helpers, "double_array", lambda value: value)
    values = values or {washer.OUTER_DIAMETER: 12.7, washer.BORE_DIAMETER: 6.35, washer.THICKNESS: 1.5875}
    outer, bore, thickness = (values[key] for key in (washer.OUTER_DIAMETER, washer.BORE_DIAMETER, washer.THICKNESS))
    precision = dict.fromkeys(values, 3)

    class Point:
        def __init__(self, values):
            self.ArrayData = tuple(values)

        def MultiplyTransform(self, transform):
            x, y, z = self.ArrayData
            return Point((x, 0.0, -y) if transform == "Top" else (x, y, z))

    adapter = SimpleNamespace(swApp=SimpleNamespace(
        IsSame=lambda left, right: int(left is right),
        GetMathUtility=lambda: SimpleNamespace(CreatePoint=Point),
    ), currentModel=SimpleNamespace(Extension=SimpleNamespace(
        GetUserPreferenceInteger=lambda _preference, _option: 0,  # an mm sheet
    )))
    source_entities = {}
    features = {}
    for label in values:
        if label == washer.THICKNESS:
            points = tuple(SimpleNamespace(X=outer / 2000.0, Y=y, Z=0.0)
                           for y in (0.0, thickness / 1000.0 * (1 if axis == "y" else -1)))
            segment = SimpleNamespace(
                ConstructionGeometry=True, GetType=lambda: 0,
                GetStartPoint2=lambda: points[0], GetEndPoint2=lambda: points[1],
            )
            segments, source_entities[label] = (segment,), points
            plane = "Front" if axis == "y" else "Top"
        else:
            if washer.OUTER_DIAMETER in source_entities:
                source_entities[label] = (segments[1],)
                continue
            circles = []
            for diameter in (outer, bore):
                circles.append(SimpleNamespace(
                    ConstructionGeometry=True, GetType=lambda: 1, IsCircle=lambda: 1,
                    GetCenterPoint2=lambda: SimpleNamespace(X=0.0, Y=0.0, Z=0.0),
                    GetRadius=lambda diameter=diameter: diameter / 2000.0,
                ))
            segments, source_entities[label] = tuple(circles), (circles[0],)
            plane = "Top" if axis == "y" else "Front"
        sketch = SimpleNamespace(
            GetSketchSegments=lambda segments=segments: segments,
            ModelToSketchTransform=SimpleNamespace(Inverse=lambda plane=plane: plane),
        )
        feature_name = washer.SOURCE_DIMENSIONS[label][0]
        features[feature_name] = SimpleNamespace(GetSpecificFeature2=lambda sketch=sketch: sketch)
    rims = []
    for diameter in (outer, bore):
        for station in (0.0, thickness / 1000.0):
            center = (0.0, station, 0.0) if axis == "y" else (0.0, 0.0, station)
            normal = (0.0, 1.0, 0.0) if axis == "y" else (0.0, 0.0, 1.0)
            curve = SimpleNamespace(
                IsCircle=lambda: True, CircleParams=(*center, *normal, diameter / 2000.0),
            )
            rims.append(SimpleNamespace(GetCurve=lambda curve=curve: curve))
    model = SimpleNamespace(
        FeatureByName=lambda name: features[name],
        GetBodies2=lambda *_args: (SimpleNamespace(GetEdges=lambda: rims),),
    )
    mapped = {id(entity): SimpleNamespace() for entities in source_entities.values() for entity in entities}
    mapped.update({id(feature): SimpleNamespace() for feature in features.values()})
    def view(orientation):
        x, y = (.095, .13225) if orientation == "*Front" else (.0975, .23)
        face = orientation == ("*Top" if axis == "y" else "*Front")
        half_x = outer / 2000.0 * 5 + .005588
        half_y = (outer if face else thickness) / 2000.0 * 5 + .005588
        return SimpleNamespace(
            ReferencedDocument=model, GetOutline=lambda: (x - half_x, y - half_y, x + half_x, y + half_y),
            GetCorresponding=lambda entity: mapped.get(id(entity)),
        )

    views = {name: view(name) for name in ("*Front", "*Top")}
    sources, imports = {}, {}
    for label, value in values.items():
        feature_name, name = washer.SOURCE_DIMENSIONS[label]
        for collection, imported in ((sources, False), (imports, True)):
            case = _supplier_native(monkeypatch, value=value / 1000.0,
                                    kind=2 if label == washer.THICKNESS else 6)
            case.native.FullName = f"{name}@{feature_name}@stock"
            owner = mapped[id(features[feature_name])] if imported else features[feature_name]
            case.native.GetFeatureOwner = lambda owner=owner: owner
            case.native.Tolerance = SimpleNamespace(Type=0)
            case.display.GetNameForSelection = lambda name=name: f"{name}@View"
            case.state.use_doc = imported
            case.display.GetUseDocUnits = lambda state=case.state: state.use_doc
            original_units = case.display.SetUnits2

            def set_units(use_doc, *args, case=case, original_units=original_units):
                case.state.use_doc = use_doc
                return original_units(use_doc, *args)

            case.display.SetUnits2 = set_units
            if not imported:
                case.state.unit, case.state.precision = 3, 3
                case.text.update({1: "(" if label == washer.THICKNESS else "(<MOD-DIAM>",
                                  2: " in)", 4: ""})
            case.annotation.entities = tuple(
                mapped[id(entity)] if imported else entity for entity in source_entities[label]
            )
            face = "*Top" if axis == "y" else "*Front"
            side = "*Front" if axis == "y" else "*Top"
            case.annotation.Owner = views[side if label == washer.THICKNESS else face]
            collection[label] = case
    parameters = {
        f"{name}@{feature}": sources[label].native
        for label, (feature, name) in washer.SOURCE_DIMENSIONS.items()
    }
    # Distinct part/import Python wrappers can denote the same native IDimension.
    # Foreign lookalikes are not registered and retain their own identity.
    canonical_dimensions = {
        id(case.native): sources[label].native
        for collection in (sources, imports) for label, case in collection.items()
    }
    adapter.swApp.IsSame = lambda left, right: int(
        canonical_dimensions.get(id(left), left) is canonical_dimensions.get(id(right), right))
    model.Parameter = parameters.get
    monkeypatch.setattr(model_helpers, "_named_dimensions", lambda _adapter, _feature, names, **_kwargs: {
        name: (sources[label].display, sources[label].native)
        for label, (_feature, name) in washer.SOURCE_DIMENSIONS.items() if name in names
    })
    imported_calls = []

    def import_annotations(_adapter, _view, *, keep, **_kwargs):
        imported_calls.append(tuple(keep))
        if defect == "source_import_mutation":
            sources[washer.THICKNESS].state.use_doc = True
        return [imports[label].annotation for label, (_feature, name)
                in washer.SOURCE_DIMENSIONS.items() if name in keep]

    monkeypatch.setattr(washer, "curate_view_dimensions", import_annotations)
    monkeypatch.setattr(washer, "dimension_name",
                        lambda _adapter, annotation: annotation.GetSpecificAnnotation().GetNameForSelection().split("@")[0])
    if defect == "source_band":
        sources[washer.THICKNESS].native.Tolerance.Type = 2
    elif defect == "import_value":
        imports[washer.THICKNESS].native.SystemValue *= 2.0
    elif defect == "source_geometry":
        points[0].X += 0.001
    elif defect == "import_band":
        imports[washer.THICKNESS].native.Tolerance.Type = 2
    case = SimpleNamespace(
        helper=washer, source_helper=model_helpers, adapter=adapter, model=model, views=views,
        sources=sources, imports=imports, mapped=mapped, entities=source_entities,
        precision=precision, model_references=frozenset(values), imported_calls=imported_calls,
        kwargs=dict(axis=axis, bore_mm=bore, outer_mm=outer, thickness_mm=thickness,
                    units="in", precision=precision, model_references=frozenset(values)),
    )
    _washer_paint_native(monkeypatch, case)
    return case


def test_washer_import_formats_drawing_display_without_changing_source_values_or_bands(monkeypatch):
    case = _washer_import_native(monkeypatch)
    before = {label: (vars(native.state).copy(), native.text.copy(), native.native.SystemValue,
                      native.native.Tolerance.Type) for label, native in case.sources.items()}
    case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    for label, imported in case.imports.items():
        case.helper.assert_supplier_reference_dimension(
            case.adapter, imported.display, label=label, units="in", precision=3,
            expected_mm=case.kwargs["thickness_mm"] if label == case.helper.THICKNESS else (
                case.kwargs["outer_mm"] if label == case.helper.OUTER_DIAMETER else case.kwargs["bore_mm"]
            ), presentation="length" if label == case.helper.THICKNESS else "diameter",
        )
        case.source_helper.assert_supplier_washer_source_attachment(
            case.adapter, case.model, imported.display,
            view=case.views["*Front" if label == case.helper.THICKNESS else "*Top"],
            label=label, axis="y", bore_mm=6.35, outer_mm=12.7, thickness_mm=1.5875,
        )
    after = {label: (vars(native.state).copy(), native.text.copy(), native.native.SystemValue,
                     native.native.Tolerance.Type) for label, native in case.sources.items()}
    assert after == before


@pytest.mark.parametrize("defect", [
    "source_band", "source_geometry", "import_value", "import_band", "source_import_mutation",
])
def test_washer_import_never_repairs_source_or_import_value_band_and_geometry(monkeypatch, defect):
    case = _washer_import_native(monkeypatch, defect=defect)
    with pytest.raises(RuntimeError):
        case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    if defect.startswith("source_") and defect != "source_import_mutation":
        assert case.imported_calls == []


def test_washer_bore_line_still_through_the_centre_fails_the_build(monkeypatch):
    case = _washer_import_native(monkeypatch)
    # The seat keeps the far-side arrow: the bore line still spans the centre.
    case.imports[case.helper.BORE_DIAMETER].display.SetSecondArrow = lambda *_args: None
    with pytest.raises(RuntimeError):
        case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)


def test_washer_source_checks_read_labels_in_sorted_order(monkeypatch):
    # Each label's source checks are COM reads: they run in sorted label
    # order, never the set's (string hashing is salted per process).
    case = _washer_import_native(monkeypatch)
    helpers = case.source_helper
    labels, named = helpers._model_reference_labels, helpers._named_dimensions
    asked = []

    class Reversed(frozenset):
        def __iter__(self):
            return iter(sorted(frozenset.__iter__(self), reverse=True))

    monkeypatch.setattr(
        helpers,
        "_model_reference_labels",
        lambda references: Reversed(labels(references)),
    )
    monkeypatch.setattr(
        helpers,
        "_named_dimensions",
        lambda adapter, owner, names, **kwargs: (
            asked.extend(names) or named(adapter, owner, names, **kwargs)
        ),
    )
    case.helper.supplier_washer_dimensions(case.adapter, case.views, **case.kwargs)
    by_name = {
        name: label for label, (_feature, name) in helpers.SOURCE_DIMENSIONS.items()
    }
    assert list(dict.fromkeys(by_name[name] for name in asked)) == sorted(
        case.model_references
    )


@pytest.mark.parametrize("label", (
    "supplier outer diameter", "supplier bore diameter", "supplier thickness",
))
@pytest.mark.parametrize("axis", ("y", "z"))
@pytest.mark.parametrize("defect", ["missing", "duplicate", "foreign", "raw_source", "extra"])
def test_washer_import_requires_exact_typed_view_entity_correspondence(monkeypatch, defect, label, axis):
    case = _washer_import_native(monkeypatch, axis=axis)
    imported = case.imports[label]
    entities = list(imported.annotation.entities)
    source = case.sources[label]
    feature, dimension = case.source_helper.SOURCE_DIMENSIONS[label]
    assert imported.native.FullName == source.native.FullName
    assert imported.native.SystemValue == source.native.SystemValue
    assert case.adapter.swApp.IsSame(imported.native, source.native) == 1
    assert case.adapter.swApp.IsSame(imported.native, case.model.Parameter(f"{dimension}@{feature}")) == 1
    if defect == "missing":
        case.mapped.pop(id(case.entities[label][0]))
    elif defect == "duplicate":
        if label == case.helper.THICKNESS:
            case.mapped[id(case.entities[label][1])] = entities[0]
        else:
            entities.append(entities[0])
    elif defect == "foreign":
        entities[0] = SimpleNamespace(**vars(entities[0]))
    elif defect == "raw_source":
        entities = list(case.entities[label])
    else:
        entities.append(SimpleNamespace())
    imported.annotation.entities = tuple(entities)
    with pytest.raises(RuntimeError):
        case.source_helper.assert_supplier_washer_source_attachment(
            case.adapter, case.model, imported.display, view=imported.annotation.Owner,
            label=label, axis=axis, bore_mm=6.35, outer_mm=12.7, thickness_mm=1.5875,
        )


@pytest.mark.parametrize(("units", "sheet", "suffix"), (
    ("in", "in", ")"), ("in", "mm", " in)"), ("mm", "in", " mm)"), ("mm", "mm", " mm)"),
))
def test_washer_model_reference_suffix_follows_its_package_sheet(units, sheet, suffix):
    import _supplier_washer_model as model_helpers

    assert model_helpers._suffix(units, sheet) == suffix
