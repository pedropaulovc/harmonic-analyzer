"""Offline contracts for canonical purchased screws and configured reference sheets."""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

import _purchased_fastener_drawing as purchased
import _purchased_variant_drawing as configured
from _drawing_registry import DrawingLayout


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
    )
    draw = _Drawing()

    async def open_model(path):
        state.opens.append(path)
        return True

    state.adapter.open_model = open_model
    monkeypatch.setattr(configured._config, "parts", lambda _stem: row)
    monkeypatch.setattr(configured, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(configured, "check", lambda _label, result: result)
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


@pytest.mark.parametrize("configuration", ("TNut", "FlangeNut"))
@pytest.mark.parametrize(
    "drift",
    (
        "create",
        "create-from-sheet",
        "create-without-source-definition",
        "create-fresh-wrapper",
        "create-replaced-thread",
        "none",
        "cross-context-feature",
        "source-already-target",
        "baseline-mapping-throws",
        "baseline-bore-throws",
        "baseline-equality-zero",
        "baseline-equality-throws",
        "mapping-failure-restore-throws-logger",
        "logger-failure-restore",
        "source-activation-false",
        "source-activation-false-mutates",
        "source-activation-true-wrong",
        "source-restore-false",
        "source-restore-lying",
        "source-restore-throws",
        "mapping-failure-restore-false",
        "mapping-failure-restore-lying",
        "mapping-failure-restore-throws",
        "scope-cleanup-independent",
        "scope-dirty-drift",
        "scope-hash-drift",
        "scope-view-config-drift",
        "scope-other-view-config-drift",
        "scope-drawing-view-drift",
        "scope-drawing-sheet-drift",
        "postrestore-rim-missing",
        "postrestore-rim-replaced",
        "postrestore-rim-duplicates",
        "postrestore-rim-fresh-wrapper",
        "rim-source-mapping-missing",
        "rim-roundtrip-missing",
        "rim-roundtrip-wrong",
        "rim-source-edge-wrong",
        "rim-source-fresh-wrapper",
        "rim-roundtrip-fresh-wrapper",
        "rim-source-feature-fresh-wrapper",
        "face",
        "create-face",
        "edge",
        "create-edge",
        "retire-right",
        "retire-selection-refused",
        "retire-selection-ignored",
        "retire-selection-neighbour",
        "retire-selection-wrong-type",
        "retire-selection-extra",
        "retire-ignored-delete",
        "retire-thread-lost",
        "retire-thread-identity",
        "retire-geometry",
        "retire-callout-survives",
        "retire-note-survives",
        "retire-wrong-feature",
        "retire-owner-type",
        "retire-owner-missing",
        "retire-owner-neighbour",
        "noniso-reappears",
        "noniso-shared-iso-note",
        "setter-refused",
        "setter-ignored",
        "setter-parent-detached",
        "setter-geometry-detached",
        "setter-note-identity",
        "setter-owner-detached",
        "rim-wrong-feature",
        "rim-feature-identity",
        "rim-wrong-height",
        "rim-wrong-radius",
        "rim-duplicate",
        "rim-missing",
        "rim-identity",
        "rim-split",
        "rim-off-arc",
        "rim-params-missing",
        "rim-params-nan",
        "rim-params-empty",
        "rim-closest-missing",
        "rim-closest-nan",
        "rim-closest-short",
        "rim-closest-u-nan",
        "rim-unused-nan",
        "bore-feature-missing",
        "bore-feature-type",
        "bore-definition-missing",
        "bore-diameter-nan",
        "bore-diameter-zero",
        "bore-feature-drift",
        "bore-diameter-drift",
        "bore-fresh-wrapper",
        "leader-drift",
        "leader-within-tolerance",
        "leader-nan",
        "leader-inf",
        "leader-truncated",
        "leader-multiple",
        "text-nan",
        "projection-nan",
        "ignored-move",
        "text",
        "link",
        "lost",
        "identity",
        "lost-callout",
        "thread-identity",
        "dangling",
        "callout-neighbour",
        "attachment",
        "attachment-type",
        "collision",
        "no-thread",
        "no-callout",
        "activation-refused",
        "selection-refused",
        "selection-ignored",
        "selection-neighbour",
        "selection-wrong-type",
        "selection-extra",
        "restore-view-ignored",
        "restore-sheet-ignored",
        "restore-sheet-mismatch",
        "insert-error-restore-error",
        "wrong-thread",
        "duplicate",
        "duplicate-uncreated",
        "wrong-feature",
        "null-attachment",
        "bad-count",
        "unsupported-type",
    ),
)
def test_kit_native_member_note_relocation_and_settled_refusals(
    monkeypatch, configuration, drift
):
    import math
    import hashlib
    import draw_sh_vn_clamping_kit_hardware as kit

    spec = kit.tnut if configuration == "TNut" else kit.flange_nut
    bore_feature = f"{configuration}ThreadBore"
    other_feature = (
        "FlangeNutThreadBore" if configuration == "TNut" else "TNutThreadBore"
    )
    # Use each member's real panel, with the same native83 local geometry.
    offset = 0.0 if configuration == "TNut" else 0.396 / 3 + 0.008 / 3
    iso_name = f"{configuration}-Isometric"
    # Native83's vendor STEP bore is 0.21095 in, not nominal TAP_DRILL_DIA / 2.
    native_bore_radius = 0.00535813
    bore_definition = SimpleNamespace(ThruTapDrillDiameter=0.01071626)
    source_feature_ids = iter(range(1001, 1101))
    drawing_feature_ids = iter(range(5001, 5101))
    scope_events = []

    class SourceFeature:
        feature_context = "source"

        def __init__(self, name, kind="HoleWzd", definition=None):
            self.Name = name
            self.kind = kind
            self.definition = definition
            self.native_identity = object()
            self.native_feature_id = next(source_feature_ids)

        def GetID(self):
            return self.native_feature_id

        def GetTypeName2(self):
            return self.kind

        def GetDefinition(self):
            return self.definition

    class DrawingFeature:
        feature_context = "drawing"

        def __init__(self, name, kind="HoleWzd"):
            self.Name = name
            self.kind = kind
            self.native_identity = object()
            self.native_feature_id = next(drawing_feature_ids)

        def GetTypeName2(self):
            return self.kind

    class EntityWrapper:
        def __init__(self, entity):
            self.entity = entity

        def __getattr__(self, name):
            return getattr(self.entity, name)

    def native_equal(first, second):
        return int(
            getattr(first, "native_identity", first)
            is getattr(second, "native_identity", second)
        )

    source_bore = SourceFeature(bore_feature, definition=bore_definition)
    feature_readback = source_bore
    source_features = {
        bore_feature: source_bore,
        other_feature: SourceFeature(other_feature),
        "Body": SourceFeature("Body", kind="Boss"),
    }
    drawing_features = {
        bore_feature: DrawingFeature(bore_feature),
        other_feature: DrawingFeature(other_feature),
        "Body": DrawingFeature("Body", kind="Boss"),
    }
    # Reproduce the old filter's false refusal without teaching IsSame that
    # equal spellings imply equal native objects across document contexts.
    assert drawing_features[bore_feature].Name == source_bore.Name
    assert (
        drawing_features[bore_feature].native_identity
        is not source_bore.native_identity
    )
    assert native_equal(drawing_features[bore_feature], source_bore) == 0
    assert drawing_features[bore_feature].native_feature_id != source_bore.GetID()
    source_mapping_calls, roundtrip_calls = [], []
    source_face_features, identity_comparisons, early_binding_calls = [], [], []

    def face(feature=bore_feature):
        native = drawing_features[feature] if isinstance(feature, str) else feature
        return SimpleNamespace(GetFeature=lambda: native)

    def edge(feature=bore_feature):
        return SimpleNamespace(
            GetTwoAdjacentFaces2=lambda: (face("Body"), face(feature))
        )

    class SourceFace:
        def __init__(self, feature):
            self.feature = feature

        def GetFeature(self):
            source_face_features.append(self.feature)
            return self.feature

    class SourceEdge:
        def __init__(self, drawing_edge, feature=bore_feature):
            self.drawing_edge = drawing_edge
            self.feature = feature
            self.native_identity = object()

        def GetTwoAdjacentFaces2(self):
            feature = (
                source_features[self.feature]
                if isinstance(self.feature, str)
                else self.feature
            )
            if drift == "rim-source-feature-fresh-wrapper":
                feature = EntityWrapper(feature)
            return (SourceFace(source_features["Body"]), SourceFace(feature))

    class BoreRim:
        def __init__(self):
            self.feature = bore_feature
            self.native_identity = object()
            self.source_edge = SourceEdge(self)
            self.parameter_range = (0.0, 2 * math.pi)
            self.curve_read = False
            self.closest_queries = []
            self.CircleParams = (
                0.0,
                spec.HEIGHT / 1000,
                0.0,
                0.0,
                1.0,
                0.0,
                native_bore_radius,
            )

        def GetCurve(self):
            self.curve_read = True
            return self

        def IsCircle(self):
            return True

        def GetCurveParams3(self):
            assert self.curve_read
            if self is rim and drift == "rim-params-missing":
                return None
            low, high = self.parameter_range
            return SimpleNamespace(UMinValue=low, UMaxValue=high)

        def GetClosestPointOn(self, x, y, z):
            self.closest_queries.append((x, y, z))
            if self is rim and drift == "rim-closest-missing":
                return None
            cx, cy, cz, _ax, _ay, _az, radius = self.CircleParams
            angle = math.atan2(z - cz, x - cx) % (2 * math.pi)
            low, high = self.parameter_range
            if not low <= angle <= high:
                # Choose the physically closest trimmed arc endpoint, not a
                # requested point on its untrimmed supporting circle.
                angle = min(
                    (low, high),
                    key=lambda endpoint: (
                        (cx + radius * math.cos(endpoint) - x) ** 2
                        + (cz + radius * math.sin(endpoint) - z) ** 2
                    ),
                )
            closest = (cx + radius * math.cos(angle), cy, cz + radius * math.sin(angle))
            if self is rim and drift == "rim-closest-nan":
                closest = (float("nan"), cy, closest[2])
            elif self is rim and drift == "rim-closest-short":
                return closest
            elif self is rim and drift == "rim-closest-u-nan":
                angle = float("nan")
            unused = float("nan") if drift == "rim-unused-nan" else 0.0
            return (*closest, angle, unused)

        def GetTwoAdjacentFaces2(self):
            return (face("Body"), face(self.feature))

    rim = BoreRim()
    if drift == "cross-context-feature":
        old_context_features = tuple(
            attached.GetFeature() for attached in rim.GetTwoAdjacentFaces2()
        )
        assert tuple(feature.Name for feature in old_context_features) == (
            "Body",
            bore_feature,
        )
        assert not any(
            native_equal(feature, source_bore) == 1 for feature in old_context_features
        )
    outer_rim, bottom_rim = BoreRim(), BoreRim()
    outer_rim.feature = "Body"
    outer_rim.CircleParams = (*rim.CircleParams[:6], 0.02)
    bottom_rim.CircleParams = (0.0, 0.0, 0.0, 0.0, 1.0, 0.0, native_bore_radius)
    # Exterior and opposite-end circles are real native geometry, not eligible
    # substitute landings when the actual visible top opening is wrong/missing.
    visible_rims = [outer_rim, bottom_rim, rim]
    projection_calls = []

    def project_point(point):
        x, y, z = point
        # An oblique, scaled affine model-to-sheet projection. Nonzero Y
        # and unequal X/Z bases expose height, radius and silhouette guesses.
        return (
            offset + 0.249 + 0.4 * x + 0.12 * y - 0.3 * z,
            0.213 + 0.18 * x + 0.25 * y + 0.28 * z,
        )

    def project_points(_adapter, view, points, **_kwargs):
        assert view is views[3]
        projection_calls.append(tuple(points))
        projected = [project_point(point) for point in points]
        if drift == "projection-nan":
            projected[0] = (float("nan"), projected[0][1])
        return projected

    class ThreadNote(_Note):
        def __init__(self):
            # A semantic callout need not have the old contiguous literal text.
            super().__init__(
                "automatic", "1/2-13\nTapped Hole", offset + 0.2631371, 0.2304204
            )
            self.Visible = 1
            self.dangling = False
            self.annotation_readback = self
            self.OwnerType = 0
            self.Owner = None
            self.leader_tip = (offset + 0.2492598, 0.21695, 0.0)
            self.leader_count = 1
            self.setter_calls = []

        def GetAnnotation(self):
            return self.annotation_readback

        def GetType(self):
            return 6

        def SetPosition2(self, *xyz):
            if drift != "ignored-move":
                self.SetPosition(*xyz)
            return True

        def Select2(self, append, mark):
            assert append is False and mark == 0
            events.append("select-note")
            if drift == "retire-selection-refused":
                return False
            if drift != "retire-selection-ignored":
                drawing_state.selected = (
                    ThreadNote() if drift == "retire-selection-neighbour" else self
                )
            return True

        def SetLeaderAttachmentPointAtIndex(self, index, x, y, z):
            assert index == 0
            # No canonical-source wrapper may escape the configuration scope
            # into a drawing mutation, even when activation initially failed.
            assert source_state.active == source_original_name
            assert source_state.postrestore_inventories
            assert source_state.postrestore_inventories[-1][0] == source_original_name
            assert all(
                not isinstance(item, SourceEdge)
                for item in source_state.postrestore_inventories[-1][1]
            )
            if source_original_name != configuration:
                assert source_state.activations
                assert source_state.restorations == [source_original_name] * len(
                    source_state.activations
                )
            events.append("set-leader")
            scope_events.append(("leader-set", source_state.active))
            self.setter_calls.append((x, y, z))
            if drift == "setter-refused":
                return False
            if drift != "setter-ignored":
                self.leader_tip = (x, y, z)
            if drift == "setter-parent-detached":
                native_threads[0].callout = None
            elif drift == "setter-geometry-detached":
                native_threads[0].entity = None
            elif drift == "setter-note-identity":
                self.annotation_readback = AnnotationReadback(self, object())
            elif drift == "setter-owner-detached":
                self.Owner = views[2]
            return True

        def GetLeaderPointsAtIndex(self, index):
            assert index == 0
            return (*self._position, *self.leader_tip)

        def GetLeaderCount(self):
            return self.leader_count

        def GetAttachedEntities3(self):
            # The native inserted INote has no direct geometry attachments.
            return ()

        def GetAttachedEntityTypes(self):
            return ()

        def GetAttachedEntityCount3(self):
            return 0

        def IsDangling(self):
            return self.dangling

        def GetDisplayData(self):
            return SimpleNamespace(
                GetTextCount=lambda: 1,
                GetTextAtIndex=lambda _i: self._resolved_text,
                GetTextInBoxWidthAtIndex=lambda _i: 0.0445132,
                GetTextHeightAtIndex=lambda _i: 0.0048299,
                GetTextPositionAtIndex=lambda _i: (
                    self._position[0],
                    self._position[1] - 0.0045257,
                    0.0,
                ),
                GetTextRefPositionAtIndex=lambda _i: 1,
                GetTextAngleAtIndex=lambda _i: 0.0,
            )

        def GetExtent(self):
            # The leader is native geometry, not translated with its text.
            data = self.GetDisplayData()
            x, y, _z = data.GetTextPositionAtIndex(0)
            right = x + data.GetTextInBoxWidthAtIndex(0)
            top = y + data.GetTextHeightAtIndex(0)
            return (
                min(self.leader_tip[0], x),
                min(self.leader_tip[1], y),
                0.0,
                max(self.leader_tip[0], right),
                max(self.leader_tip[1], top),
                0.0,
            )

    class ThreadAnnotation:
        def __init__(self, callout):
            self.callout = callout
            self.entity = face()
            self.attachment_type = 2
            self.attachment_count = 1
            self.native_identity = object()

        def GetName(self):
            return "CosmeticThread1"

        def GetAttachedEntities3(self):
            return (self.entity,)

        def GetAttachedEntityTypes(self):
            return (self.attachment_type,)

        def GetAttachedEntityCount3(self):
            return self.attachment_count

        def Select2(self, append, mark):
            assert append is False and mark == 0
            events.append("select-thread")
            if drift == "selection-refused":
                return False
            if drift == "selection-ignored":
                return True
            drawing_state.selected = (
                ThreadAnnotation(self.callout)
                if drift == "selection-neighbour"
                else self
            )
            return True

        def GetAnnotation(self):
            return self

        def GetType(self):
            return 1

        def GetSpecificAnnotation(self):
            return self

        @property
        def ThreadCallout(self):
            return self.callout

    class AnnotationReadback:
        def __init__(self, note, identity):
            self.note = note
            self.native_identity = identity

        def __getattr__(self, name):
            return getattr(self.note, name)

    note = ThreadNote()
    outlines = (
        (0.16, 0.13, 0.19, 0.17),
        (0.1647453, 0.201412, 0.1999213, 0.236588),
        (0.23, 0.13, 0.26, 0.17),
        (0.2271081, 0.1978993, 0.2722252, 0.2401007),
    )

    class MemberView(SimpleNamespace):
        @property
        def ReferencedConfiguration(self):
            scope_events.append(("view-configuration", self))
            return self._referenced_configuration

        @ReferencedConfiguration.setter
        def ReferencedConfiguration(self, _value):
            pytest.fail("drawing view configurations are immutable")

        def GetReferencedModelName(self):
            return source_model_path

    views = [
        MemberView(
            _referenced_configuration=configuration,
            GetOutline=lambda box=box: (
                box[0] + offset,
                box[1],
                box[2] + offset,
                box[3],
            ),
        )
        for box in outlines
    ]
    unrelated_view = MemberView(
        _referenced_configuration="Unrelated",
        GetName2=lambda: "unrelated-view",
    )
    note.Owner = views[3]
    native_threads = [ThreadAnnotation(note)]
    original_thread = native_threads[0]
    events = []
    right_threads, right_notes = [], []
    old_note = ThreadNote()
    old_note.Owner = views[2]
    old_note.SetPosition(offset + 0.29, 0.16, 0.0)
    old_thread = ThreadAnnotation(old_note)
    original_right_geometry = old_thread.entity
    retiring = drift.startswith("retire-")
    if retiring:
        right_threads.append(old_thread)
        right_notes.append(old_note)
        native_threads[0].callout = None
    elif drift == "noniso-shared-iso-note":
        # An undocumented owner alias must not authorize deleting the ISO note.
        right_threads.append(ThreadAnnotation(note))
    drawing_state = SimpleNamespace(
        selected=None,
        active=None
        if drift
        in {
            "create-from-sheet",
            "restore-sheet-ignored",
            "restore-sheet-mismatch",
        }
        else "previous-view",
        sheet="Sheet1",
    )
    previous_active = drawing_state.active

    class NativeInsertError(RuntimeError):
        pass

    native_error = NativeInsertError("native insertion failed")

    class SelectionReadback:
        def GetSelectedObjectCount2(self, mark):
            assert mark == -1
            if drawing_state.selected is None:
                return 0
            return 2 if drift in {"selection-extra", "retire-selection-extra"} else 1

        def GetSelectedObjectType3(self, index, mark):
            assert index == 1 and mark == -1
            if isinstance(drawing_state.selected, ThreadNote):
                return 39 if drift == "retire-selection-wrong-type" else 15
            return 2 if drift == "selection-wrong-type" else 39

        def GetSelectedObject6(self, index, mark):
            assert index == 1 and mark == -1
            return drawing_state.selected

    class Drawing:
        SelectionManager = SelectionReadback()

        @property
        def ActiveDrawingView(self):
            scope_events.append(("drawing-view", drawing_state.active))
            if drawing_state.active is None:
                return None
            return SimpleNamespace(GetName2=lambda: drawing_state.active)

        def GetCurrentSheet(self):
            scope_events.append(("drawing-sheet", drawing_state.sheet))
            return SimpleNamespace(GetName=lambda: drawing_state.sheet)

        def GetViews(self):
            scope_events.append(("drawing-views",))
            # SDK arrays include each sheet as their first entry; the active
            # sheet need not be first and other-sheet views must be protected.
            return (
                (SimpleNamespace(GetName2=lambda: "OtherSheet"), unrelated_view),
                (SimpleNamespace(GetName2=lambda: "Sheet1"), *views),
            )

        def ActivateView(self, name):
            events.append(f"activate:{name}")
            if name == iso_name and drift == "activation-refused":
                return False
            if name == "previous-view":
                if drift == "restore-view-ignored":
                    return True
                if drift == "insert-error-restore-error":
                    raise RuntimeError("native restore failed")
            drawing_state.active = name
            return True

        def ActivateSheet(self, name):
            assert name == "Sheet1"
            if drift != "restore-sheet-ignored":
                drawing_state.active = None
            if drift == "restore-sheet-mismatch":
                drawing_state.sheet = "OtherSheet"
            events.append("restore-sheet")
            return True

        def ClearSelection2(self, all_selected):
            assert all_selected is True
            drawing_state.selected = None
            events.append("clear")

        def EditDelete(self):
            assert drawing_state.selected is old_note
            events.append("delete-note")
            if drift == "retire-ignored-delete":
                return
            if drift != "retire-note-survives":
                right_notes.clear()
            if drift == "retire-thread-lost":
                right_threads.clear()
                return
            # Native inventory refresh may return a different dispatch wrapper.
            fresh = ThreadAnnotation(None)
            fresh.native_identity = old_thread.native_identity
            fresh.entity = old_thread.entity
            fresh.attachment_type = old_thread.attachment_type
            if drift == "retire-thread-identity":
                fresh.native_identity = object()
            elif drift == "retire-geometry":
                fresh.entity = face()
            elif drift == "retire-callout-survives":
                fresh.callout = old_note
            right_threads[:] = [fresh]
            # Like the real API, success is VT_VOID and must be read back.

        def InsertThreadCallout(self):
            events.append("insert")
            assert drawing_state.active == iso_name
            assert drawing_state.selected is native_threads[0]
            if retiring:
                # Immediate deletion/readback must precede any new authoring.
                assert events.index("delete-note") < events.index("right-notes")
                assert not right_notes and right_threads[0].callout is None
                assert right_threads[0].entity is original_right_geometry
            if drift == "insert-error-restore-error":
                raise native_error
            if drift in {"create-fresh-wrapper", "create-replaced-thread"}:
                replacement = ThreadAnnotation(note)
                if drift == "create-fresh-wrapper":
                    replacement.native_identity = drawing_state.selected.native_identity
                    replacement.entity = drawing_state.selected.entity
                native_threads[0] = replacement
            elif drift != "no-callout":
                drawing_state.selected.callout = note
            # Native insertion is VT_VOID; a None return is not failure.

    def source_feature(name):
        if name == bore_feature:
            events.append("bore-definition")
            if drift == "baseline-bore-throws" and source_state.active != configuration:
                source_state.baseline_definition_failures += 1
                raise baseline_error
            if drift == "bore-fresh-wrapper":
                return EntityWrapper(feature_readback)
            return feature_readback
        assert name == "CosmeticThread1"
        events.append("source-definition")
        if drift == "create-without-source-definition":
            return None
        return SimpleNamespace(
            GetTypeName2=lambda: "CosmeticThread",
            GetDefinition=lambda: SimpleNamespace(
                Standard=0,
                StandardType="",
                ThreadCallout="1/2-13 Tapped Hole",
            ),
        )

    source_model_path = r"C:\fixture\clamping_kit.SLDPRT"
    source_original_name = (
        configuration if drift == "source-already-target" else "HoldDownStud"
    )
    source_state = SimpleNamespace(
        active=source_original_name,
        dirty=False,
        payload=b"unchanged canonical kit part",
        phase="baseline",
        activation_generation=0,
        readback_generation=0,
        refresh_count=0,
        activations=[],
        restorations=[],
        hash_calls=[],
        inventories=[],
        postrestore_inventories=[],
        baseline_definition_failures=0,
        baseline_observations=[],
    )

    class NativeMappingError(RuntimeError):
        pass

    mapping_error = NativeMappingError("native reverse mapping failed")
    baseline_error = NativeMappingError("baseline reverse mapping failed")
    restore_error = RuntimeError("source configuration restore threw")
    logger_error = RuntimeError("diagnostic logger failed")
    baseline_equality_error = RuntimeError("stale baseline view wrapper")
    control_logs = []
    logger_failures = []
    if drift in {
        "baseline-bore-throws",
        "baseline-mapping-throws",
        "mapping-failure-restore-throws-logger",
        "logger-failure-restore",
    }:
        original_info = kit._telemetry.info

        def control_log(message, *args, **kwargs):
            if "native bore configuration control" in message:
                control_logs.append(message)
                if "logger" in drift:
                    logger_failures.append(logger_error)
                    raise logger_error
            return original_info(message, *args, **kwargs)

        monkeypatch.setattr(kit._telemetry, "info", control_log)

    def change_protected_state():
        all_drift = drift in {
            "scope-cleanup-independent",
            "mapping-failure-restore-throws-logger",
        }
        if all_drift or drift == "scope-dirty-drift":
            source_state.dirty = True
        if all_drift or drift == "scope-hash-drift":
            source_state.payload += b" changed"
        if all_drift or drift == "scope-view-config-drift":
            views[0]._referenced_configuration = "Unexpected"
        if drift == "scope-other-view-config-drift":
            unrelated_view._referenced_configuration = "Unexpected"
        if all_drift or drift == "scope-drawing-view-drift":
            drawing_state.active = "unexpected-view"
        if all_drift or drift == "scope-drawing-sheet-drift":
            drawing_state.sheet = "UnexpectedSheet"

    def source_hash(path):
        assert isinstance(path, Path) and path == Path(source_model_path)
        digest = hashlib.sha256(source_state.payload).hexdigest()
        source_state.hash_calls.append((path, digest, source_state.active))
        scope_events.append(("hash", source_state.active))
        return digest

    monkeypatch.setattr(kit, "_sha256", source_hash)
    wrong_source_edge = SourceEdge(
        rim, SourceFeature(bore_feature, definition=bore_definition)
    )
    wrong_roundtrip_rim = BoreRim()

    class SourceExtension:
        def GetCorrespondingEntity2(self, drawing_edge):
            unwrapped = (
                drawing_edge.entity
                if isinstance(drawing_edge, EntityWrapper)
                else drawing_edge
            )
            assert isinstance(unwrapped, BoreRim)
            assert unwrapped.curve_read
            inventory = source_state.inventories[-1]
            assert inventory["refresh"] == source_state.refresh_count
            assert any(item is drawing_edge for item in inventory["edges"])
            assert inventory["active"] == source_state.active
            if (
                drift == "baseline-mapping-throws"
                and source_state.active != configuration
            ):
                inventory["maps"].append((drawing_edge, baseline_error))
                raise baseline_error
            canonical = None
            if source_state.active == configuration:
                # Active configuration alone is not activation acceptance:
                # the production caller must first perform strict readback.
                assert (
                    source_state.readback_generation
                    == source_state.activation_generation
                )
                change_protected_state()
                if (
                    drift.startswith("mapping-failure-")
                    or drift == "scope-cleanup-independent"
                ):
                    inventory["maps"].append((drawing_edge, mapping_error))
                    raise mapping_error
                canonical = unwrapped.source_edge
                if unwrapped is rim:
                    if drift == "rim-source-mapping-missing":
                        canonical = None
                    elif drift == "rim-source-edge-wrong":
                        canonical = wrong_source_edge
                    elif drift == "rim-source-fresh-wrapper":
                        canonical = EntityWrapper(canonical)
            source_mapping_calls.append((drawing_edge, canonical))
            inventory["maps"].append((drawing_edge, canonical))
            scope_events.append(("reverse-map", source_state.active, drawing_edge))
            return canonical

    class SourceConfiguration:
        __slots__ = ()

        @property
        def Name(self):
            scope_events.append(("source-configuration", source_state.active))
            source_state.readback_generation = source_state.activation_generation
            return source_state.active

    class SourceConfigurationManager:
        __slots__ = ()

        @property
        def ActiveConfiguration(self):
            return source_configuration

    class SourceModel:
        __slots__ = ()

        def FeatureByName(self, name):
            return source_feature(name)

        @property
        def Extension(self):
            # ReferencedDocument is an IModelDoc2, not an IPartDoc shortcut.
            assert (self, "IModelDoc2") in early_binding_calls
            return source_extension

        @property
        def ConfigurationManager(self):
            return source_configuration_manager

        def GetPathName(self):
            return source_model_path

        def GetType(self):
            return 1

        def GetSaveFlag(self):
            scope_events.append(("save-flag", source_state.dirty))
            return source_state.dirty

        def ShowConfiguration2(self, name):
            assert (self, "IModelDoc2") in early_binding_calls
            assert name in {configuration, source_original_name}
            scope_events.append(("show-configuration", name))
            source_state.activation_generation += 1
            if name == configuration:
                source_state.activations.append(name)
                source_state.phase = "matched"
                if drift == "source-activation-false":
                    return False
                if drift == "source-activation-false-mutates":
                    source_state.active = name
                    return False
                if drift == "source-activation-true-wrong":
                    source_state.active = "WrongConfiguration"
                    return True
                source_state.active = name
                return True
            source_state.restorations.append(name)
            source_state.phase = "restored"
            if drift in {
                "source-restore-throws",
                "mapping-failure-restore-throws",
                "mapping-failure-restore-throws-logger",
                "logger-failure-restore",
                "scope-cleanup-independent",
            }:
                raise restore_error
            if drift in {"source-restore-false", "mapping-failure-restore-false"}:
                return False
            if drift in {"source-restore-lying", "mapping-failure-restore-lying"}:
                return True
            source_state.active = name
            return True

    source_extension = SourceExtension()
    source_configuration = SourceConfiguration()
    source_configuration_manager = SourceConfigurationManager()
    source_model = SourceModel()

    def view_corresponding_entity(canonical):
        unwrapped = (
            canonical.entity if isinstance(canonical, EntityWrapper) else canonical
        )
        assert isinstance(unwrapped, SourceEdge)
        assert source_state.active == configuration
        assert source_state.readback_generation == source_state.activation_generation
        roundtrip = unwrapped.drawing_edge
        if roundtrip is rim:
            if drift == "rim-roundtrip-missing":
                roundtrip = None
            elif drift == "rim-roundtrip-wrong":
                roundtrip = wrong_roundtrip_rim
            elif drift == "rim-roundtrip-fresh-wrapper":
                roundtrip = EntityWrapper(roundtrip)
        roundtrip_calls.append((canonical, roundtrip))
        return roundtrip

    def read_annotations():
        assert events[0] == "final-display-mode"
        assert events[-1] == "refresh"
        events.append("inventory")
        return native_threads

    # GetNotes exposes only an unrelated literal decoy, not ThreadCallout.
    decoy = _Note("literal", "1/2-13 Tapped Hole", offset + 0.32, 0.23)
    views[3].GetNotes = lambda: [decoy]
    views[3].GetAnnotations = read_annotations

    def refresh_iso():
        if source_state.phase == "matched":
            assert source_state.active == configuration
            assert (
                source_state.readback_generation == source_state.activation_generation
            )
        source_state.refresh_count += 1
        scope_events.append(("refresh", source_state.active))
        events.append("refresh")

    views[3].UpdateViewDisplayGeometry = refresh_iso
    views[3].GetName2 = lambda: iso_name
    views[3].ReferencedDocument = source_model
    views[3].GetCorrespondingEntity = view_corresponding_entity

    def right_annotations():
        assert events[-1] == "refresh-right"
        events.append("right-inventory")
        return [*right_threads, *(item.GetAnnotation() for item in right_notes)]

    def read_right_notes():
        events.append("right-notes")
        return right_notes

    for index, view in enumerate(views[:3]):
        view.GetName2 = lambda index=index: f"{configuration}-{index}"
        view.UpdateViewDisplayGeometry = lambda index=index: events.append(
            "refresh-right" if index == 2 else f"refresh-{index}"
        )
        view.GetAnnotations = right_annotations if index == 2 else lambda: ()
        view.GetNotes = read_right_notes if index == 2 else lambda: ()
    postrestore_wrapper = EntityWrapper(rim)

    def visible_entities(view, kind, **_kwargs):
        assert view is views[3] and kind == 1
        assert source_state.refresh_count
        visible = list(visible_rims)
        restored = source_state.phase == "restored" or (
            drift == "source-already-target" and len(source_state.hash_calls) == 2
        )
        if restored:
            if drift == "postrestore-rim-missing":
                visible = [item for item in visible if item is not rim]
            elif drift == "postrestore-rim-replaced":
                visible = [BoreRim() if item is rim else item for item in visible]
            elif drift == "postrestore-rim-duplicates":
                visible.append(EntityWrapper(rim))
            elif drift == "postrestore-rim-fresh-wrapper":
                visible = [
                    postrestore_wrapper if item is rim else item for item in visible
                ]
            source_state.postrestore_inventories.append(
                (source_state.active, tuple(visible))
            )
        source_state.inventories.append(
            {
                "active": source_state.active,
                "phase": source_state.phase,
                "refresh": source_state.refresh_count,
                "edges": tuple(visible),
                "maps": [],
            }
        )
        scope_events.append(("visible-edges", source_state.active))
        return visible

    monkeypatch.setattr(kit, "visible_view_entities", visible_entities)
    monkeypatch.setattr(kit, "model_points_in_view", project_points)
    monkeypatch.setattr(
        kit,
        "set_high_quality_shaded_with_edges",
        lambda *_args, **_kwargs: events.append("final-display-mode"),
    )

    def early_bound(value, kind):
        early_binding_calls.append((value, kind))
        return value

    def is_same(first, second):
        assert not any(
            isinstance(
                item.entity if isinstance(item, EntityWrapper) else item,
                SourceEdge,
            )
            for item in (first, second)
        ), "canonical source edges must not escape into visible-edge identity"
        first_context = getattr(first, "feature_context", None)
        second_context = getattr(second, "feature_context", None)
        if first_context is not None or second_context is not None:
            assert first_context == second_context == "source", (
                "drawing-context feature identity must not prove source ownership"
            )
        identity_comparisons.append((first, second))
        if (
            drift in {"baseline-equality-zero", "baseline-equality-throws"}
            and first is rim
            and second is rim
            and source_state.phase == "matched"
            and not source_state.inventories[-1]["maps"]
            and not source_state.baseline_observations
        ):
            if drift == "baseline-equality-throws":
                source_state.baseline_observations.append(baseline_equality_error)
                raise baseline_equality_error
            source_state.baseline_observations.append(0)
            return 0
        return native_equal(first, second)

    monkeypatch.setattr(kit, "_early_bound", early_bound)
    adapter = SimpleNamespace(
        currentModel=Drawing(),
        swApp=SimpleNamespace(IsSame=is_same),
    )
    cells = configured.configuration_view_cells(1 if configuration == "TNut" else 2, 3)
    if drift in {"face", "create-face"}:
        native_threads[0].entity, native_threads[0].attachment_type = face(), 2
        if drift == "create-face":
            native_threads[0].callout = None
    elif drift in {"edge", "create-edge"}:
        native_threads[0].entity, native_threads[0].attachment_type = edge(), 1
        if drift == "create-edge":
            native_threads[0].callout = None
    elif drift == "no-thread":
        native_threads.clear()
    elif drift in {
        "create",
        "create-from-sheet",
        "create-without-source-definition",
        "create-fresh-wrapper",
        "create-replaced-thread",
        "no-callout",
        "activation-refused",
        "selection-refused",
        "selection-ignored",
        "selection-neighbour",
        "selection-wrong-type",
        "selection-extra",
        "restore-view-ignored",
        "restore-sheet-ignored",
        "restore-sheet-mismatch",
        "insert-error-restore-error",
    }:
        native_threads[0].callout = None
    elif drift == "wrong-thread":
        native_threads[0].callout = None
        native_threads[0].entity = face(other_feature)
    elif drift == "duplicate":
        native_threads.append(ThreadAnnotation(ThreadNote()))
    elif drift == "duplicate-uncreated":
        native_threads[0].callout = None
        native_threads.append(ThreadAnnotation(None))
    elif drift == "wrong-feature":
        native_threads[0].entity = face(other_feature)
    elif drift == "null-attachment":
        native_threads[0].entity = None
    elif drift == "bad-count":
        native_threads[0].attachment_count = 2
    elif drift == "unsupported-type":
        native_threads[0].attachment_type = 3
    if drift == "retire-wrong-feature":
        old_thread.entity = face(other_feature)
    elif drift == "retire-owner-type":
        old_note.OwnerType = 1
    elif drift == "retire-owner-missing":
        old_note.Owner = None
    elif drift == "retire-owner-neighbour":
        old_note.Owner = views[0]
    elif drift == "rim-wrong-feature":
        rim.source_edge.feature = other_feature
    elif drift in {"rim-wrong-height", "rim-wrong-radius"}:
        circle = list(rim.CircleParams)
        circle[1 if drift == "rim-wrong-height" else 6] += 0.001
        rim.CircleParams = tuple(circle)
    elif drift == "rim-duplicate":
        visible_rims.append(BoreRim())
    elif drift == "rim-missing":
        visible_rims.remove(rim)
    elif drift == "rim-feature-identity":
        rim.source_edge.feature = SourceFeature(
            bore_feature, definition=bore_definition
        )
    elif drift == "rim-split":
        rim.parameter_range = (0.0, math.pi)
        other_arc = BoreRim()
        other_arc.parameter_range = (math.pi, 2 * math.pi)
        visible_rims.append(other_arc)
    elif drift == "rim-off-arc":
        rim.parameter_range = (math.pi, 2 * math.pi)
    elif drift == "rim-params-nan":
        rim.parameter_range = (0.0, float("nan"))
    elif drift == "rim-params-empty":
        rim.parameter_range = (0.0, 0.0)
    elif drift == "bore-feature-missing":
        feature_readback = None
    elif drift == "bore-feature-type":
        source_bore.GetTypeName2 = lambda: "Cut"
    elif drift == "bore-definition-missing":
        source_bore.GetDefinition = lambda: None
    elif drift == "bore-diameter-nan":
        bore_definition.ThruTapDrillDiameter = float("nan")
    elif drift == "bore-diameter-zero":
        bore_definition.ThruTapDrillDiameter = 0.0
    if drift in {
        "retire-selection-refused",
        "retire-selection-ignored",
        "retire-selection-neighbour",
        "retire-selection-wrong-type",
        "retire-selection-extra",
        "retire-wrong-feature",
        "retire-owner-type",
        "retire-owner-missing",
        "retire-owner-neighbour",
        "noniso-shared-iso-note",
    }:
        with pytest.raises(
            RuntimeError,
            match="cannot select the non-isometric|association|owner",
        ):
            kit.annotate_member(adapter, configuration, cells, views)
        assert "delete-note" not in events and "insert" not in events
        assert drawing_state.selected is None
        assert drawing_state.active == previous_active
        return
    if drift in {
        "retire-ignored-delete",
        "retire-thread-lost",
        "retire-thread-identity",
        "retire-geometry",
        "retire-callout-survives",
        "retire-note-survives",
    }:
        with pytest.raises(RuntimeError, match="retirement failed or changed"):
            kit.annotate_member(adapter, configuration, cells, views)
        assert events.count("delete-note") == 1 and "insert" not in events
        assert "right-notes" in events
        assert drawing_state.selected is None
        assert drawing_state.active == previous_active
        return

    def assert_scope_cleanup():
        assert source_state.active == source_original_name
        assert source_state.dirty is False
        assert [view._referenced_configuration for view in views] == [configuration] * 4
        assert unrelated_view._referenced_configuration == "Unrelated"
        assert drawing_state.active == previous_active
        assert drawing_state.sheet == "Sheet1"
        assert len(source_state.hash_calls) == 2
        assert source_state.hash_calls[0] == source_state.hash_calls[1]
        if drift == "source-already-target":
            assert not source_state.activations and not source_state.restorations
        else:
            assert source_state.activations
            assert source_state.activations == [configuration] * len(
                source_state.activations
            )
            assert source_state.restorations == [source_original_name] * len(
                source_state.activations
            )

    def assert_source_correspondence():
        assert_scope_cleanup()
        mapped_inventories = [
            inventory for inventory in source_state.inventories if inventory["maps"]
        ]
        if drift == "baseline-bore-throws":
            assert source_state.baseline_definition_failures == 1
            assert mapped_inventories
            matched = mapped_inventories[0]
        else:
            assert len(mapped_inventories) >= 2
            baseline, matched = mapped_inventories[:2]
            assert [item[0] for item in baseline["maps"]] == [
                item[0] for item in matched["maps"]
            ]
            assert baseline["refresh"] < matched["refresh"]
            assert baseline["active"] == source_original_name
            if drift == "baseline-mapping-throws":
                assert baseline["maps"] == [(rim, baseline_error)]
            elif drift != "source-already-target":
                assert all(canonical is None for _edge, canonical in baseline["maps"])
        assert matched["active"] == configuration
        if drift in {"baseline-bore-throws", "baseline-mapping-throws"}:
            assert sum(str(baseline_error) in message for message in control_logs) == 1
        if drift in {"baseline-equality-zero", "baseline-equality-throws"}:
            assert source_state.baseline_observations == [
                baseline_equality_error if drift == "baseline-equality-throws" else 0
            ]
        if drift != "source-already-target":
            assert len(source_state.activations) == sum(
                inventory["active"] == configuration
                for inventory in source_state.inventories
            )
        assert all(canonical is not None for _edge, canonical in matched["maps"])
        assert source_state.postrestore_inventories
        for canonical, roundtrip in roundtrip_calls:
            assert canonical is not roundtrip
            assert native_equal(roundtrip, canonical.drawing_edge) == 1
            assert any(
                mapped is canonical and native_equal(drawing_edge, roundtrip) == 1
                for drawing_edge, mapped in source_mapping_calls
            )
        assert roundtrip_calls
        for drawing_edge, canonical in matched["maps"]:
            assert canonical is not drawing_edge
            assert native_equal(canonical, drawing_edge.source_edge) == 1
            assert any(mapped is canonical for mapped, _edge in roundtrip_calls)
        assert any(
            first is feature and native_equal(second, source_bore) == 1
            for feature in source_face_features
            if native_equal(feature, source_bore) == 1
            for first, second in identity_comparisons
        )
        assert (source_model, "IModelDoc2") in early_binding_calls
        assert (source_extension, "IModelDocExtension") in early_binding_calls
        assert source_configuration.Name == source_original_name
        assert views[3].ReferencedConfiguration == configuration
        if drift == "rim-source-fresh-wrapper":
            assert all(
                isinstance(canonical, EntityWrapper)
                and canonical is not drawing_edge.source_edge
                for drawing_edge, canonical in matched["maps"]
            )
        elif drift == "rim-roundtrip-fresh-wrapper":
            assert all(
                isinstance(roundtrip, EntityWrapper) and roundtrip is not rim
                for _canonical, roundtrip in roundtrip_calls
            )
        elif drift == "rim-source-feature-fresh-wrapper":
            assert any(
                isinstance(feature, EntityWrapper)
                and feature is not source_bore
                and native_equal(feature, source_bore) == 1
                for feature in source_face_features
            )
        if drift == "bore-fresh-wrapper":
            assert EntityWrapper(source_bore).GetID() == source_bore.GetID()
        if drift == "postrestore-rim-fresh-wrapper":
            assert any(
                first is postrestore_wrapper or second is postrestore_wrapper
                for first, second in identity_comparisons
            )

    configuration_refusals = {
        "source-activation-false",
        "source-activation-false-mutates",
        "source-activation-true-wrong",
        "source-restore-false",
        "source-restore-lying",
        "source-restore-throws",
        "mapping-failure-restore-false",
        "mapping-failure-restore-lying",
        "mapping-failure-restore-throws",
        "mapping-failure-restore-throws-logger",
        "logger-failure-restore",
        "scope-cleanup-independent",
        "scope-dirty-drift",
        "scope-hash-drift",
        "scope-view-config-drift",
        "scope-other-view-config-drift",
        "scope-drawing-view-drift",
        "scope-drawing-sheet-drift",
        "postrestore-rim-missing",
        "postrestore-rim-replaced",
        "postrestore-rim-duplicates",
    }
    if drift in configuration_refusals:
        with pytest.raises(RuntimeError) as refused:
            kit.annotate_member(adapter, configuration, cells, views)
        assert not note.setter_calls
        assert "set-leader" not in events and "insert" not in events
        assert "delete-note" not in events
        assert source_state.activations == [configuration]
        assert source_state.restorations == [source_original_name]
        assert len(source_state.hash_calls) == 2
        assert source_state.hash_calls[0][2] == source_original_name
        restore_failed = drift in {
            "source-restore-false",
            "source-restore-lying",
            "source-restore-throws",
            "mapping-failure-restore-false",
            "mapping-failure-restore-lying",
            "mapping-failure-restore-throws",
            "mapping-failure-restore-throws-logger",
            "logger-failure-restore",
            "scope-cleanup-independent",
        }
        assert source_state.active == (
            configuration if restore_failed else source_original_name
        )
        assert source_state.hash_calls[1][2] == source_state.active
        changed_bytes = drift in {
            "scope-hash-drift",
            "scope-cleanup-independent",
            "mapping-failure-restore-throws-logger",
        }
        assert (
            source_state.hash_calls[0][1] != source_state.hash_calls[1][1]
        ) is changed_bytes
        restore_index = scope_events.index(("show-configuration", source_original_name))
        cleanup = scope_events[restore_index + 1 :]
        cleanup_kinds = {item[0] for item in cleanup}
        assert {
            "save-flag",
            "drawing-views",
            "drawing-view",
            "drawing-sheet",
            "hash",
        } <= cleanup_kinds
        assert all(("view-configuration", view) in cleanup for view in views)
        if "logger" in drift:
            assert logger_failures == [logger_error]
            assert refused.value is not logger_error
            assert repr(logger_error) in "\n".join(refused.value.__notes__)
        assert ("view-configuration", unrelated_view) in cleanup
        if drift.startswith("source-activation-"):
            assert len(source_state.inventories) == 1
            assert "source configuration activation failed" in str(refused.value)
            assert all(
                inventory["active"] == source_original_name
                for inventory in source_state.inventories
            )
            assert not roundtrip_calls
        elif (
            drift.startswith("mapping-failure-") or drift == "scope-cleanup-independent"
        ):
            assert refused.value is mapping_error
            assert refused.value.__notes__
            notes = "\n".join(refused.value.__notes__)
            assert "configuration restoration" in notes
            if drift in {
                "scope-cleanup-independent",
                "mapping-failure-restore-throws-logger",
            }:
                assert source_state.dirty
                assert views[0]._referenced_configuration == "Unexpected"
                assert drawing_state.active == "unexpected-view"
                assert drawing_state.sheet == "UnexpectedSheet"
                assert len(refused.value.__notes__) >= 5
                assert all(
                    stage in notes
                    for stage in (
                        "source unsaved state",
                        "drawing activation",
                        "drawing configurations",
                        "native source SHA",
                    )
                )
        elif drift == "logger-failure-restore":
            assert refused.value.__cause__ is restore_error
            assert "native bore configuration restoration failed" in str(refused.value)
            assert repr(restore_error) in "\n".join(refused.value.__notes__)
        elif drift.startswith("postrestore-"):
            assert source_state.postrestore_inventories
            visible = source_state.postrestore_inventories[-1][1]
            matches = [item for item in visible if native_equal(item, rim) == 1]
            assert len(matches) == (2 if drift == "postrestore-rim-duplicates" else 0)
        return

    initial_refusals = {
        "setter-refused": "placement refused",
        "setter-ignored": "leader attachment moved",
        "setter-parent-detached": "expected one automatic",
        "setter-geometry-detached": "expected one automatic",
        "setter-note-identity": "lost identity, attachment or clearance",
        "setter-owner-detached": "lost identity, attachment or clearance",
        "rim-source-mapping-missing": (
            "native bore-rim source/view correspondence failed"
        ),
        "rim-roundtrip-missing": "native bore-rim source/view correspondence failed",
        "rim-roundtrip-wrong": "native bore-rim source/view correspondence failed",
        "rim-source-edge-wrong": "visible top bore rim",
        "rim-wrong-feature": "visible top bore rim",
        "rim-feature-identity": "visible top bore rim",
        "rim-wrong-height": "visible top bore rim",
        "rim-wrong-radius": "visible top bore rim",
        "rim-duplicate": "visible physical bore-rim edge",
        "rim-missing": "visible top bore rim",
        "rim-off-arc": "visible physical bore-rim edge",
        "rim-params-missing": "curve parameters are missing",
        "rim-params-nan": "trim/closest point is unreadable",
        "rim-params-empty": "trim/closest point is unreadable",
        "rim-closest-missing": "trim/closest point is unreadable",
        "rim-closest-nan": "trim/closest point is unreadable",
        "rim-closest-short": "trim/closest point is unreadable",
        "rim-closest-u-nan": "trim/closest point is unreadable",
        "bore-feature-missing": "native bore feature .* is missing",
        "bore-feature-type": "no Hole Wizard definition",
        "bore-definition-missing": "no Hole Wizard definition",
        "bore-diameter-nan": "drill diameter is unreadable",
        "bore-diameter-zero": "drill diameter is unreadable",
        "projection-nan": "no readable projection",
    }
    if drift in initial_refusals:
        with pytest.raises(RuntimeError, match=initial_refusals[drift]) as refused:
            kit.annotate_member(adapter, configuration, cells, views)
        assert "insert" not in events and "delete-note" not in events
        assert_scope_cleanup()
        if drift in {
            "rim-source-mapping-missing",
            "rim-roundtrip-missing",
            "rim-roundtrip-wrong",
            "rim-source-edge-wrong",
            "rim-wrong-feature",
            "rim-feature-identity",
        }:
            assert not note.setter_calls
            matched_maps = [
                mapping
                for inventory in source_state.inventories
                if inventory["active"] == configuration
                for mapping in inventory["maps"]
            ]
            assert len(matched_maps) == 1
            drawing_edge, canonical = matched_maps[0]
            assert drawing_edge is rim
            assert rim.feature == bore_feature
            if drift == "rim-source-mapping-missing":
                assert canonical is None and not roundtrip_calls
                assert any(
                    first is rim and second is rim
                    for first, second in identity_comparisons
                ), "baseline view equality cannot qualify missing source ownership"
            else:
                assert len(roundtrip_calls) == 1
                assert roundtrip_calls[0][0] is canonical
                roundtrip = roundtrip_calls[0][1]
                if drift == "rim-roundtrip-missing":
                    assert roundtrip is None
                elif drift == "rim-roundtrip-wrong":
                    assert roundtrip is wrong_roundtrip_rim
                    assert native_equal(roundtrip, rim) == 0
                else:
                    assert roundtrip is rim
                    if drift == "rim-source-edge-wrong":
                        assert canonical is wrong_source_edge
                        assert native_equal(canonical, rim.source_edge) == 0
                    owner = (
                        source_features[canonical.feature]
                        if isinstance(canonical.feature, str)
                        else canonical.feature
                    )
                    if drift != "rim-wrong-feature":
                        assert owner.Name == source_bore.Name
                    assert native_equal(owner, source_bore) == 0
                    assert any(
                        first is owner and native_equal(second, source_bore) == 1
                        for first, second in identity_comparisons
                    )
            message = str(refused.value)
            assert iso_name in message and source_model_path in message.replace(
                "\\\\", "\\"
            )
            assert "'source_active_configuration':" in message
            assert "'view_configuration':" in message
        return
    original_geometry = native_threads[0].entity if native_threads else None
    if drift in {
        "activation-refused",
        "selection-refused",
        "selection-ignored",
        "selection-neighbour",
        "selection-wrong-type",
        "selection-extra",
    }:
        with pytest.raises(
            RuntimeError, match="cannot activate|cannot select"
        ) as refused:
            kit.annotate_member(adapter, configuration, cells, views)
        message = str(refused.value)
        if drift == "selection-ignored":
            assert "'selection_count': 0" in message
        elif drift == "selection-neighbour":
            assert "'selection_name': 'CosmeticThread1'" in message
            assert "'same_thread': False" in message
        elif drift == "selection-wrong-type":
            assert "'selection_type': 2" in message
        elif drift == "selection-extra":
            assert "'selection_count': 2" in message
        assert "insert" not in events
        assert (
            drawing_state.selected is None and drawing_state.active == previous_active
        )
        return
    if drift in {
        "restore-view-ignored",
        "restore-sheet-ignored",
        "restore-sheet-mismatch",
    }:
        with pytest.raises(
            RuntimeError, match="cannot restore drawing activation"
        ) as refused:
            kit.annotate_member(adapter, configuration, cells, views)
        message = str(refused.value)
        assert "actual view=" in message and "expected view=" in message
        assert "CosmeticThread1" in message
        assert events.count("insert") == 1 and drawing_state.selected is None
        if drift == "restore-sheet-mismatch":
            assert drawing_state.active is None and drawing_state.sheet == "OtherSheet"
            assert "OtherSheet" in message
        else:
            assert drawing_state.active == iso_name
        return
    if drift == "insert-error-restore-error":
        with pytest.raises(NativeInsertError) as refused:
            kit.annotate_member(adapter, configuration, cells, views)
        assert refused.value is native_error
        restore_notes = "\n".join(refused.value.__notes__)
        assert "native restore failed" in restore_notes
        assert (
            "CosmeticThread1" in restore_notes and "'requested': True" in restore_notes
        )
        assert events.count("insert") == 1 and drawing_state.selected is None
        return
    if drift == "create-replaced-thread":
        with pytest.raises(RuntimeError, match="lost identity after insertion"):
            kit.annotate_member(adapter, configuration, cells, views)
        assert events.count("insert") == 1
        assert (
            drawing_state.selected is None and drawing_state.active == previous_active
        )
        return
    if drift in {
        "no-thread",
        "no-callout",
        "wrong-thread",
        "duplicate",
        "duplicate-uncreated",
        "wrong-feature",
        "null-attachment",
        "bad-count",
        "unsupported-type",
    }:
        with pytest.raises(RuntimeError, match="expected one automatic") as refused:
            kit.annotate_member(adapter, configuration, cells, views)
        message = str(refused.value)
        assert f"found={2 if drift == 'duplicate' else 0}" in message
        assert "cosmetic_threads=" in message and "callouts=" in message
        assert "candidates=" in message
        assert events.count("insert") == int(drift == "no-callout")
        assert (
            drawing_state.selected is None and drawing_state.active == previous_active
        )
        if drift == "no-callout":
            assert "'thread_name': 'CosmeticThread1'" in message
            assert "'source_definition':" in message
            assert "'requested': True" in message
        if drift not in {
            "no-thread",
            "no-callout",
            "wrong-thread",
            "duplicate-uncreated",
        }:
            assert "'types':" in message and "'features':" in message
        return
    if drift == "ignored-move":
        with pytest.raises(RuntimeError, match="clearance"):
            kit.annotate_member(adapter, configuration, cells, views)
        return
    checks = kit.annotate_member(adapter, configuration, cells, views)
    assert_source_correspondence()
    created = drift in {
        "create",
        "create-face",
        "create-edge",
        "create-from-sheet",
        "create-without-source-definition",
        "create-fresh-wrapper",
        "retire-right",
    }
    assert events.count("insert") == int(created)
    assert drawing_state.selected is None and drawing_state.active == previous_active
    if created:
        assert events.index("source-definition") < events.index("insert")
    if drift == "create-fresh-wrapper":
        assert (
            original_thread.callout is None and native_threads[0] is not original_thread
        )
    if drift == "retire-right":
        assert events.count("delete-note") == 1
        assert events.index("delete-note") < events.index("insert")
        assert not right_notes and right_threads[0].callout is None
        assert right_threads[0] is not old_thread
        assert right_threads[0].native_identity is old_thread.native_identity
        assert right_threads[0].entity is original_right_geometry
        assert old_note.Owner is views[2]
    else:
        assert "delete-note" not in events
    assert len(native_threads) == 1 and native_threads[0].callout is note
    assert native_threads[0].entity is original_geometry
    assert note.GetAttachedEntities3() == ()
    assert note.GetAttachedEntityTypes() == ()
    assert note.GetAttachedEntityCount3() == 0
    assert note.OwnerType == 0 and note.Owner is views[3]
    assert rim.closest_queries
    if drift == "rim-split":
        assert other_arc.closest_queries
    # Independently derive the circle's support point through the affine
    # projection. A setter that just echoes a requested arbitrary point is not
    # sufficient: the requested point itself must face the actual text.
    radius = native_bore_radius
    height = spec.HEIGHT / 1000
    center = (offset + 0.249 + 0.12 * height, 0.213 + 0.25 * height)
    dx = note._position[0] + 0.0445132 / 2 - center[0]
    dy = note._position[1] - 0.0045257 + 0.0048299 / 2 - center[1]
    angle = math.atan2(-0.3 * dx + 0.28 * dy, 0.4 * dx + 0.18 * dy)
    expected_model_tip = (radius * math.cos(angle), height, radius * math.sin(angle))
    expected_tip = project_point(expected_model_tip)
    assert all(
        point == pytest.approx(expected_model_tip) for point in rim.closest_queries
    )
    if drift == "rim-split":
        assert all(
            point == pytest.approx(expected_model_tip)
            for point in other_arc.closest_queries
        )
    assert note.setter_calls == [pytest.approx((*expected_tip, 0.0))]
    assert projection_calls[0] == (
        (0.0, height, 0.0),
        (radius, height, 0.0),
        (0.0, height, radius),
    )
    box = kit._note_text_box(note)
    assert box[0] >= cells[0][2][0]
    assert box[2] <= cells[2][2][2] < offset + 0.297412
    assert box[1] > views[3].GetOutline()[3]
    assert note.GetExtent()[1] == pytest.approx(expected_tip[1])
    assert decoy._position == (offset + 0.32, 0.23, 0.0)
    # A fresh Python dispatch wrapper is still the same native annotation.
    note.annotation_readback = AnnotationReadback(note, note)
    if drift == "text":
        note._resolved_text = "1/2-20 Tapped Hole"
    elif drift == "link":
        note.PropertyLinkedText = "replaced"
    elif drift == "lost":
        native_threads.clear()
    elif drift == "lost-callout":
        native_threads[0].callout = None
    elif drift == "identity":
        note.annotation_readback = AnnotationReadback(note, object())
    elif drift == "thread-identity":
        native_threads[0] = ThreadAnnotation(note)
    elif drift == "dangling":
        note.dangling = True
    elif drift == "callout-neighbour":
        native_threads[0].callout = ThreadNote()
    elif drift == "attachment":
        native_threads[0].entity = face()
    elif drift == "attachment-type":
        native_threads[0].entity, native_threads[0].attachment_type = edge(), 1
    elif drift == "collision":
        note.SetPosition(offset + 0.32, 0.23, 0.0)
    elif drift == "noniso-reappears":
        right_threads.append(old_thread)
        right_notes.append(old_note)
    elif drift == "rim-identity":
        visible_rims[:] = [BoreRim()]
    elif drift == "bore-feature-drift":
        feature_readback = SourceFeature(bore_feature, definition=bore_definition)
    elif drift == "bore-diameter-drift":
        bore_definition.ThruTapDrillDiameter += 0.000001
    elif drift in {"leader-drift", "leader-within-tolerance"}:
        x, y, z = note.leader_tip
        distance = 0.0001001 if drift == "leader-drift" else 0.0000999
        note.leader_tip = (x + distance, y, z)
    elif drift in {"leader-nan", "leader-inf"}:
        x, y, z = note.leader_tip
        note.leader_tip = (
            x,
            y,
            float("nan") if drift == "leader-nan" else float("inf"),
        )
    elif drift == "leader-truncated":
        note.GetLeaderPointsAtIndex = lambda _index: (*note._position, 0.0)
    elif drift == "leader-multiple":
        note.leader_count = 2
    elif drift == "text-nan":
        note._position = (float("nan"), note._position[1], 0.0)
    if (
        drift
        in {
            "none",
            "cross-context-feature",
            "source-already-target",
            "baseline-mapping-throws",
            "baseline-bore-throws",
            "baseline-equality-zero",
            "baseline-equality-throws",
            "postrestore-rim-fresh-wrapper",
            "rim-source-fresh-wrapper",
            "rim-roundtrip-fresh-wrapper",
            "rim-source-feature-fresh-wrapper",
            "face",
            "edge",
            "leader-within-tolerance",
            "rim-split",
            "rim-unused-nan",
            "bore-fresh-wrapper",
        }
        or created
    ):
        checks[0]()
        assert_source_correspondence()
        if drift == "postrestore-rim-fresh-wrapper":
            # Only the settled comparison sees two returned view wrappers;
            # the post-restore inventory itself compares wrapper to old rim.
            assert any(
                first is postrestore_wrapper and second is postrestore_wrapper
                for first, second in identity_comparisons
            )
    else:
        expected_error = {
            "noniso-reappears": "survived/returned",
            "rim-identity": "visible bore rim lost native identity",
            "bore-feature-drift": "native bore feature/diameter changed",
            "bore-diameter-drift": "native bore feature/diameter changed",
            "leader-drift": "leader attachment moved",
            "leader-nan": "leader is unreadable",
            "leader-inf": "leader is unreadable",
            "leader-truncated": "leader is unreadable",
            "leader-multiple": "leader did not survive",
            "text-nan": "unreadable",
        }.get(drift)
        with pytest.raises(RuntimeError, match=expected_error):
            checks[0]()
        assert_scope_cleanup()
    # Missing callouts during settled readback are failures, not repair requests.
    assert events.count("insert") == int(created)
    assert events.count("delete-note") == int(drift == "retire-right")
    assert len(note.setter_calls) == 1


@pytest.mark.parametrize(
    "drift",
    (
        "none",
        "wide-text",
        "ignored-move",
        "move-refused",
        "text-model",
        "model-moves-left",
        "clearance-below-2mm",
        "clearance-above-2mm",
        "length",
        "attachment",
        "identity",
        "dangling",
        "hidden",
        "reference",
        "lost",
        "text-border",
        "stroke-border",
        "unmeasured-width",
    ),
)
def test_kit_stud_reference_measures_real_end_rims_and_rejects_drift(
    monkeypatch, drift
):
    import draw_sh_vn_clamping_kit_hardware as kit
    import _drawing_edge_dimensions as edge_dimensions
    from solidworks_mcp.adapters import sw_type_info
    import _drawing_dimensions as dimension_text

    class Rim:
        def __init__(self, station, radius):
            self.station = station
            self.CircleParams = (0.0, station, 0.0, 0.0, 1.0, 0.0, radius)

        def GetCurve(self):
            return self

        def IsCircle(self):
            return True

    lower_radius = (kit.stud.RADIUS - kit.stud.LOWER_FACTORY_CHAMFER) / 1000
    cut_radius = (kit.stud.RADIUS - kit.stud.CUT_END_CHAMFER_MAX) / 1000
    rims = [Rim(kit.stud.LENGTH / 1000, cut_radius), Rim(0.0, lower_radius)]
    land = Rim(kit.stud.LOWER_FACTORY_CHAMFER / 1000, kit.stud.RADIUS / 1000)
    state = SimpleNamespace(display=None)
    projection_events = []

    class Front:
        def __init__(self):
            self.position_y = 0.10895
            self.projection_y = self.position_y
            self.outline_left = 0.044492

        def SetViewPosition(self, _x, y):
            self.position_y = y
            projection_events.append("move")
            return True

        def UpdateViewDisplayGeometry(self):
            self.projection_y = self.position_y
            projection_events.append("update")
            # Native VT_VOID returns None, not a success flag.

        def GetAnnotations(self):
            return (
                [SimpleNamespace(native_identity=inventory_identity or state.display)]
                if present
                else []
            )

        def GetOutline(self):
            return (
                self.outline_left,
                self.position_y,
                self.outline_left + 0.00635,
                self.position_y + 0.0381,
            )

    front = Front()
    assert front.SetViewPosition(0.047667, 0.13395) is True
    assert front.projection_y != front.position_y

    def project_points(_adapter, view, points, **_kwargs):
        projection_events.append("project")
        # Moving/rebuilding alone leaves native projection geometry stale.
        return [(0.047667, view.projection_y + y / 2) for _x, y, _z in points]

    class Dimension:
        Visible = 1
        DrivenState = 1

        def __init__(self, entities):
            self.entities = entities
            self.SystemValue = entities[1].station - entities[0].station
            self.text = {1: "", 2: ""}
            self.dangling = False
            self.moves = []

        def GetPosition(self):
            return (*self.text_xy, 0.0)

        def SetPosition2(self, x, y, z):
            self.moves.append((x, y, z))
            if drift == "move-refused":
                return False
            if drift != "ignored-move":
                dx = x - self.text_xy[0]
                self.text_xy = (x, y)
                self.stroke_x += dx
            return True

        def GetAnnotation(self):
            return self

        def GetSpecificAnnotation(self):
            return self

        def GetDimension2(self, _index):
            return self

        def GetAttachedEntities3(self):
            return self.entities

        def GetAttachedEntityTypes(self):
            return (1, 1)

        def IsDangling(self):
            return self.dangling

        def GetText(self, index):
            return self.text[index]

        def SetText(self, index, text):
            self.text[index] = text

    def add_dimension(adapter, view, **kwargs):
        state.display = Dimension(kwargs["entities"])
        state.display.text_xy = kwargs["text_xy"]
        state.display.stroke_x = kwargs["text_xy"][0]
        # Native83 centred 17.67 mm of text on the requested dimension line.
        state.display.width = 0.022 if drift == "wide-text" else 0.01767
        state.display.initial_position = (*kwargs["text_xy"], 0.0)
        return state.display

    monkeypatch.setattr(kit, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(edge_dimensions, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        sw_type_info, "early_bound_or_flag", lambda value, *_args: value
    )
    monkeypatch.setattr(
        kit, "visible_view_entities", lambda *_args, **_kwargs: [rims[0], land, rims[1]]
    )
    monkeypatch.setattr(kit, "model_points_in_view", project_points)
    monkeypatch.setattr(kit, "add_edge_dimension", add_dimension)
    monkeypatch.setattr(
        dimension_text, "rebuild_drawing", lambda *_args, **_kwargs: None
    )

    def native_display(_adapter, annotation):
        x, y = annotation.text_xy
        return (
            {
                "texts": [
                    {
                        "t": "(76.20)",
                        "pos": (x, y, 0.0),
                        "h": 0.003,
                        "w": annotation.width,
                        "ang": 0.0,
                        "ref": 2,
                    }
                ],
                "lines": [
                    [
                        0,
                        0,
                        0,
                        0,
                        annotation.stroke_x,
                        0.13395,
                        0.0,
                        annotation.stroke_x,
                        0.17205,
                        0.0,
                    ]
                ],
            },
            {},
        )

    monkeypatch.setattr(kit, "annotation_display", native_display)
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(
            IsSame=lambda a, b: int(
                getattr(a, "native_identity", a) is getattr(b, "native_identity", b)
            )
        ),
        _attempt=lambda operation: operation(),
    )
    present = True
    inventory_identity = None
    cells = configured.configuration_view_cells(0, 3)
    if drift in {"ignored-move", "move-refused"}:
        with pytest.raises(
            RuntimeError,
            match="clearance" if drift == "ignored-move" else "relocation refused",
        ):
            kit.annotate_member(adapter, "HoldDownStud", cells, [front] * 4)
        assert len(state.display.moves) == 1
        assert state.display.GetPosition() == state.display.initial_position
        assert (
            state.display.text_xy[0] + state.display.width / 2 > front.GetOutline()[0]
        )
        return
    checks = kit.annotate_member(adapter, "HoldDownStud", cells, [front] * 4)
    dimension = state.display
    assert dimension.SystemValue * 1000 == pytest.approx(kit.stud.LENGTH)
    assert dimension.entities == (rims[1], rims[0])
    assert projection_events == ["move", "update", "project"]
    assert dimension.text_xy[1] == pytest.approx(0.13395 + kit.stud.LENGTH / 4000)
    assert dimension.initial_position[0] == pytest.approx(cells[0][2][0] + 0.022)
    assert dimension.initial_position[0] + dimension.width / 2 > front.GetOutline()[0]
    expected_x = front.GetOutline()[0] - 0.0025 - dimension.width / 2
    assert dimension.moves == [
        pytest.approx((expected_x, dimension.initial_position[1], 0.0))
    ]
    assert dimension.GetPosition()[0] < dimension.initial_position[0]
    assert dimension.text_xy[0] + dimension.width / 2 == pytest.approx(
        front.GetOutline()[0] - 0.0025
    )
    if drift == "length":
        dimension.SystemValue -= 0.002
    elif drift == "attachment":
        dimension.entities = (rims[1], land)
    elif drift == "identity":
        inventory_identity = object()
    elif drift == "dangling":
        dimension.dangling = True
    elif drift == "hidden":
        dimension.Visible = 3
    elif drift == "reference":
        dimension.text[1] = ""
    elif drift == "lost":
        present = False
    elif drift == "text-border":
        dimension.text_xy = (0.024, dimension.text_xy[1])
    elif drift == "stroke-border":
        dimension.stroke_x = 0.010
    elif drift == "unmeasured-width":
        dimension.width = 0.0
    elif drift == "text-model":
        # Return the native centred text to the requested dimension line.
        dimension.SetPosition2(*dimension.initial_position)
    elif drift == "model-moves-left":
        front.outline_left -= 0.001
    elif drift in {"clearance-below-2mm", "clearance-above-2mm"}:
        right = front.GetOutline()[0] - (
            0.0019999 if drift == "clearance-below-2mm" else 0.0020001
        )
        dimension.text_xy = (right - dimension.width / 2, dimension.text_xy[1])
    if drift in {"none", "wide-text", "clearance-above-2mm"}:
        checks[0]()
    else:
        with pytest.raises(RuntimeError):
            checks[0]()


@pytest.mark.parametrize(
    ("reference", "anchor"),
    [
        (0, (0.1, 0.204)),
        (1, (0.1, 0.2)),
        (2, (0.11, 0.202)),
        (3, (0.12, 0.204)),
        (4, (0.12, 0.2)),
        (5, (0.11, 0.204)),
    ],
)
def test_kit_native_text_reference_anchors_preserve_same_measured_ink(
    reference, anchor
):
    import draw_sh_vn_clamping_kit_hardware as kit

    box = kit._measured_display_box(
        {
            "texts": [
                {
                    "t": "1/2-13",
                    "pos": (*anchor, 0.0),
                    "w": 0.02,
                    "h": 0.004,
                    "ref": reference,
                    "ang": 0.0,
                }
            ]
        }
    )
    assert (box.xmin, box.ymin, box.xmax, box.ymax) == pytest.approx(
        (0.1, 0.2, 0.12, 0.204)
    )


def test_kit_rotated_native_text_anchor_rotates_the_reference_offset():
    import math
    import draw_sh_vn_clamping_kit_hardware as kit

    box = kit._measured_display_box(
        {
            "texts": [
                {
                    "t": "(76.20)",
                    "pos": (0.04, 0.17, 0.0),
                    "w": 0.02,
                    "h": 0.004,
                    "ref": 4,
                    "ang": math.pi / 2,
                }
            ]
        }
    )
    assert (box.xmin, box.ymin, box.xmax, box.ymax) == pytest.approx(
        (0.036, 0.15, 0.04, 0.17)
    )


class _KitFlagNativeWrapper:
    """A fresh dispatch wrapper, not a new native annotation or edge."""

    def __init__(self, native):
        self.native = native

    def __getattr__(self, name):
        return getattr(self.native, name)


class _KitFlagNativeEdge:
    """Physical edge oracle independent of the recipe's candidate selection."""

    def __init__(self, *, circle=None, endpoints=None, trimmed=False):
        self.native_identity = object()
        self.CircleParams = circle
        self.endpoints = endpoints
        self.trimmed = trimmed
        self.closest_queries = []
        self.closest_defect = None

    def GetCurve(self):
        return self

    def IsCircle(self):
        return self.CircleParams is not None

    def IsLine(self):
        return self.endpoints is not None

    def GetStartVertex(self):
        return self._vertex(0)

    def GetEndVertex(self):
        return self._vertex(1)

    def _vertex(self, index):
        if self.endpoints is None:
            return None
        return SimpleNamespace(GetPoint=lambda: self.endpoints[index])

    def GetCurveParams3(self):
        return SimpleNamespace(
            StartPoint=None if self.endpoints is None else self.endpoints[0],
            EndPoint=None if self.endpoints is None else self.endpoints[1],
            UMinValue=0.0,
            UMaxValue=1.0,
        )

    def GetClosestPointOn(self, x, y, z):
        import math

        self.closest_queries.append((x, y, z))
        if self.endpoints is not None:
            start, end = self.endpoints
            delta = tuple(b - a for a, b in zip(start, end))
            length_squared = sum(value * value for value in delta)
            fraction = (
                sum(
                    (value - origin) * direction
                    for value, origin, direction in zip((x, y, z), start, delta)
                )
                / length_squared
            )
            fraction = min(1.0, max(0.0, fraction))
            point = tuple(
                origin + fraction * direction for origin, direction in zip(start, delta)
            )
        else:
            cx, cy, cz, ax, ay, az, radius = self.CircleParams
            axis_length = math.sqrt(ax * ax + ay * ay + az * az)
            axis = (ax / axis_length, ay / axis_length, az / axis_length)
            delta = (x - cx, y - cy, z - cz)
            normal = sum(a * b for a, b in zip(delta, axis))
            radial = tuple(a - normal * b for a, b in zip(delta, axis))
            radial_length = math.sqrt(sum(value * value for value in radial))
            if radial_length == 0.0:
                radial, radial_length = (0.0, 0.0, 1.0), 1.0
            point = tuple(
                center + radius * direction / radial_length
                for center, direction in zip((cx, cy, cz), radial)
            )
            if self.trimmed:
                # Same untrimmed circle, but its physical arc omits +Z.
                point = (cx, cy, cz - radius)
            fraction = 0.5
        # IEdge.GetClosestPointOn's fifth field is explicitly unused by the
        # SDK. Spatial proof must not reject an otherwise valid native edge.
        result = (*point, fraction, float("nan"))
        if self.closest_defect == "nan":
            return (float("nan"), *result[1:])
        if self.closest_defect == "short":
            return result[:2]
        return result


class _KitFlagNativeAnnotation:
    """Separate IAnnotation readback for a real-looking native INote graph."""

    def __init__(self, note, view, edge, landing):
        self.native_identity = object()
        self.note = note
        self.Owner = view
        self.OwnerType = 0
        self.Visible = 1
        self.entities = (edge,)
        self.entity_types = (1,)
        self.entity_count = 1
        self.dangling = False
        self.leader_count = 1
        self.landing = (*landing, 0.0)
        self.leader_override = None
        self.leader_start_offset = (0.0, 0.0, 0.0)
        self.position = (0.0, 0.0, 0.0)
        self.moves = []
        self.ignore_movement = False
        self.refuse_movement = False
        self.leader_set_calls = []

    def GetType(self):
        return 6

    def GetSpecificAnnotation(self):
        return self.note

    def GetPosition(self):
        return self.position

    def SetPosition(self, x, y, z):
        return self.SetPosition2(x, y, z)

    def SetPosition2(self, x, y, z):
        self.moves.append((x, y, z))
        if self.refuse_movement:
            return False
        if not self.ignore_movement:
            self.position = (x, y, z)
        return True

    def GetAttachedEntities3(self):
        return self.entities

    def GetAttachedEntityTypes(self):
        return self.entity_types

    def GetAttachedEntityCount3(self):
        return self.entity_count

    def GetLeaderCount(self):
        return self.leader_count

    def SetLeaderAttachmentPointAtIndex(self, index, x, y, z):
        self.leader_set_calls.append((index, x, y, z))
        pytest.fail(
            "post-insert leader endpoint movement loses the native edge attachment"
        )

    def GetLeaderPointsAtIndex(self, index):
        assert index == 0
        if self.leader_override is not None:
            return self.leader_override
        start = tuple(
            value + offset
            for value, offset in zip(
                self.position, self.leader_start_offset, strict=True
            )
        )
        return (*start, *self.landing)

    def IsDangling(self):
        return self.dangling

    def GetDisplayData(self):
        return self.note.GetDisplayData()


class _KitFlagNativeNote:
    def __init__(self, text, view, edge, landing):
        self.native_identity = object()
        self.PropertyLinkedText = text
        self.resolved_text = text
        self.width = 0.0042
        self.height = 0.003
        # Deliberately not equal to the annotation insertion point: placement
        # must measure native ink rather than trusting requested coordinates.
        self.ink_offset = (-0.0013, -0.0008)
        self.extent_override = None
        self.extent_includes_leader = False
        self.annotation = _KitFlagNativeAnnotation(self, view, edge, landing)

    def GetAnnotation(self):
        return _KitFlagNativeWrapper(self.annotation)

    def GetText(self):
        return self.resolved_text

    def _text_bounds(self):
        x, y, _z = self.annotation.position
        left = x + self.ink_offset[0]
        bottom = y + self.ink_offset[1]
        return (left, bottom, left + self.width, bottom + self.height)

    def GetExtent(self):
        if self.extent_override is not None:
            return self.extent_override
        left, bottom, right, top = self._text_bounds()
        if self.extent_includes_leader:
            points = self.annotation.GetLeaderPointsAtIndex(0)
            xs = (left, right, *points[0::3])
            ys = (bottom, top, *points[1::3])
            left, bottom, right, top = min(xs), min(ys), max(xs), max(ys)
        return (left, bottom, 0.0, right, top, 0.0)

    def GetDisplayData(self):
        x0, y0, _x1, _y1 = self._text_bounds()
        return SimpleNamespace(
            GetTextCount=lambda: 1,
            GetTextAtIndex=lambda _index: self.resolved_text,
            GetTextInBoxWidthAtIndex=lambda _index: self.width,
            GetTextHeightAtIndex=lambda _index: self.height,
            GetTextPositionAtIndex=lambda _index: (x0, y0, 0.0),
            GetTextRefPositionAtIndex=lambda _index: 1,
            GetTextAngleAtIndex=lambda _index: 0.0,
        )


@pytest.fixture
def kit_installation_native(monkeypatch):
    """Keep recipe validation real; replace only the native COM boundary."""
    import build_sh_vn_clamping_kit_hardware as producer
    import draw_sh_vn_clamping_kit_hardware as kit
    import _drawing_attachment as attachment
    from solidworks_mcp.adapters import sw_type_info

    monkeypatch.setattr(kit, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(attachment, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        sw_type_info, "early_bound_or_flag", lambda value, *_args: value
    )

    def make(configuration, *, prior_view="previous-view"):
        index, key, title, spec = {
            "HoldDownStud": (0, "[1]", "HOLD-DOWN STUD", kit.stud),
            "TNut": (1, "[2]", "T-NUT", kit.tnut),
            "FlangeNut": (2, "[3]", "FLANGE NUT", kit.flange_nut),
        }[configuration]
        cells = configured.configuration_view_cells(index, 3)
        state = SimpleNamespace(
            kit=kit,
            configuration=configuration,
            key=key,
            title=title,
            spec=spec,
            source_properties=dict(producer.MEMBER_NOTE_PROPERTIES),
            cells=cells,
            active=prior_view,
            sheet="KitSheet",
            prior_view=prior_view,
            selected=object(),
            events=[],
            calls=[],
            comparisons=[],
            projections=[],
            author_defect=None,
            restore_defect=None,
            clear_error=None,
            projection_defect=None,
            repeat_note_wrappers=False,
            on_author=lambda _note: None,
            note=None,
            legend=None,
            error=RuntimeError("native flag authoring failed"),
        )
        state.bore_radius = 0.00535813
        state.bore_definition = SimpleNamespace(
            ThruTapDrillDiameter=2 * state.bore_radius
        )
        state.bore_kind = "HoleWzd"
        state.bore_feature_missing = False
        state.bore_definition_missing = False

        def source_feature(name):
            assert name == f"{configuration}ThreadBore"
            state.events.append(("native-bore", name))
            if state.bore_feature_missing:
                return None
            return SimpleNamespace(
                GetTypeName2=lambda: state.bore_kind,
                GetDefinition=lambda: (
                    None if state.bore_definition_missing else state.bore_definition
                ),
            )

        state.source = SimpleNamespace(
            FeatureByName=source_feature,
            ShowConfiguration2=lambda *_args: pytest.fail(
                "flag presentation must not mutate source configuration"
            ),
        )

        class NativeView:
            def __init__(self, name, center, box):
                self.name = name
                self.center = center
                self.cell = box
                self.native_identity = object()
                self.notes = []
                self.refreshes = 0
                self.scans = 0
                self.ScaleRatio = (1.0, 2.0)
                self.ReferencedDocument = state.source

            def GetName2(self):
                return self.name

            def GetOutline(self):
                x, y = self.center
                return (x - 0.008, y - 0.006, x + 0.008, y + 0.006)

            def UpdateViewDisplayGeometry(self):
                self.refreshes += 1
                state.events.append(("refresh", self.name))

            def GetNotes(self):
                state.events.append(("notes", self.name))
                wrappers = [_KitFlagNativeWrapper(note) for note in self.notes]
                return wrappers * (2 if state.repeat_note_wrappers else 1)

        views = [
            NativeView(f"{configuration}-{name}", center, box)
            for name, center, box in cells
        ]
        state.views = views
        state.view_index = 2 if configuration == "TNut" else 0
        state.view = views[state.view_index]
        state.sheet_view = NativeView("KitSheet", (0.0, 0.0), (0, 0, 1, 1))
        state.other_sheet = NativeView("OtherSheet", (0.0, 0.0), (0, 0, 1, 1))
        state.other_view = NativeView("OtherView", (0.0, 0.0), (0, 0, 1, 1))

        if configuration == "TNut":
            half_length = spec.LENGTH / 2000
            half_width = spec.FOOT_WIDTH / 2000
            endpoints = (
                (half_length, 0.0, half_width),
                (half_length, 0.0, -half_width),
            )
            target = _KitFlagNativeEdge(endpoints=endpoints)
            inboard = (half_width + state.bore_radius) / 2
            # This fixture's oblique projection puts -Z on screen-right.
            state.model_point = (half_length, 0.0, -inboard)
            state.decoys = [
                _KitFlagNativeEdge(
                    endpoints=tuple((-x, y, z) for x, y, z in endpoints)
                ),
                _KitFlagNativeEdge(
                    endpoints=tuple((x, y + 0.001, z) for x, y, z in endpoints)
                ),
                _KitFlagNativeEdge(
                    endpoints=tuple((x, y, z * 0.8) for x, y, z in endpoints)
                ),
                _KitFlagNativeEdge(
                    endpoints=(endpoints[0], (half_length, 0.0, -half_width / 2))
                ),
            ]
        else:
            radius = (
                (spec.RADIUS - spec.LOWER_FACTORY_CHAMFER) / 1000
                if configuration == "HoldDownStud"
                else spec.FLANGE_DIA / 2000
            )
            circle = (0.0, 0.0, 0.0, 0.0, 1.0, 0.0, radius)
            target = _KitFlagNativeEdge(circle=circle)
            if configuration == "HoldDownStud":
                state.model_point = (0.0, 0.0, radius)
            else:
                import math

                inboard = (radius + state.bore_radius) / 2
                state.model_point = (
                    inboard,
                    0.0,
                    math.sqrt(radius * radius - inboard * inboard),
                )
            upper_y = (
                spec.LENGTH / 1000
                if configuration == "HoldDownStud"
                else spec.HEIGHT / 1000
            )
            chamfer_y = (
                spec.LOWER_FACTORY_CHAMFER / 1000 if configuration == "HoldDownStud" else 0.0005
            )
            chamfer_radius = (
                spec.RADIUS / 1000
                if configuration == "HoldDownStud"
                else radius + 0.0005
            )
            inner_radius = (
                state.bore_radius if configuration == "FlangeNut" else radius * 0.6
            )
            state.decoys = [
                _KitFlagNativeEdge(circle=(0.0, upper_y, 0.0, 0.0, 1.0, 0.0, radius)),
                _KitFlagNativeEdge(circle=(0.0, 0.0, 0.0, 0.0, 1.0, 0.0, inner_radius)),
                _KitFlagNativeEdge(
                    circle=(0.0, chamfer_y, 0.0, 0.0, 1.0, 0.0, chamfer_radius)
                ),
                _KitFlagNativeEdge(circle=(0.0005, 0.0, 0.0, 0.0, 1.0, 0.0, radius)),
                _KitFlagNativeEdge(circle=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0, radius)),
            ]
        state.target = target
        state.edges = [*state.decoys, target]

        def same(first, second):
            state.comparisons.append((first, second))
            first_identity = getattr(first, "native_identity", first)
            second_identity = getattr(second, "native_identity", second)
            if state.author_defect == "owner-identity-unknown" and (
                first_identity is state.view.native_identity
                and second_identity is state.view.native_identity
            ):
                return -1
            return int(first_identity is second_identity)

        class NativeDrawing:
            @property
            def ActiveDrawingView(self):
                if state.active is None:
                    return None
                return SimpleNamespace(GetName2=lambda: state.active)

            def GetCurrentSheet(self):
                return SimpleNamespace(GetName=lambda: state.sheet)

            def ActivateView(self, name):
                state.events.append(("activate-view", name))
                if name == state.prior_view and state.restore_defect == "throws":
                    raise RuntimeError("native flag view restore failed")
                if name == state.prior_view and state.restore_defect == "ignored":
                    return True
                state.active = name
                return True

            def ActivateSheet(self, name):
                state.events.append(("activate-sheet", name))
                if state.restore_defect == "throws":
                    raise RuntimeError("native flag sheet restore failed")
                if state.restore_defect != "ignored":
                    state.active = None
                    state.sheet = name
                return True

            def ClearSelection2(self, all_selected):
                assert all_selected is True
                state.selected = None
                state.events.append(("clear-selection",))
                if state.clear_error is not None:
                    raise state.clear_error

            def GetViews(self):
                state.events.append(("all-views",))
                return (
                    (state.other_sheet, state.other_view),
                    (state.sheet_view, *views),
                )

        def project_point(point):
            x, y, z = point
            cx, cy = state.view.center
            return (
                cx + 0.31 * x + 0.11 * y - 0.23 * z,
                cy + 0.13 * x + 0.37 * y + 0.29 * z,
            )

        state.adapter = SimpleNamespace(
            currentModel=NativeDrawing(),
            swApp=SimpleNamespace(IsSame=same),
            _attempt=lambda operation: operation(),
        )
        state.same = same
        state.project_point = project_point
        return state

    return make


@pytest.fixture
def kit_installation_real_note_native(kit_installation_native, monkeypatch):
    """Real note author/selector; selected point and inserted note are native fakes."""
    import _drawing_leader_notes as native_notes
    import _drawing_selection as native_selection

    def make(configuration, *, defect=None):
        state = kit_installation_native(configuration)
        draw = state.adapter.currentModel
        cx, cy = state.view.center
        state.default_tip = (cx - 0.006, cy + 0.003, 0.0)
        state.native_point = state.default_tip
        state.point = state.project_point(state.model_point)
        state.real_events = []
        state.selection_data = []
        state.select_calls = []
        state.object_reads = []
        state.point_calls = []
        state.point_reads = []
        state.inserted = []
        state.rebuilds = []
        state.repair_calls = []
        state.extra_selection = False
        state.point_api_forbidden = False
        state.legacy_repair_allowed = False
        replacement = _KitFlagNativeEdge(
            circle=state.target.CircleParams, endpoints=state.target.endpoints
        )

        def create_select_data():
            data = SimpleNamespace(View=None)
            state.selection_data.append(data)
            return data

        def select_entity(append, data):
            assert append is False
            assert data.View is state.view
            assert state.active == state.view.GetName2()
            assert state.selected is None
            state.real_events.append("select-entity")
            state.select_calls.append((append, data))
            if defect == "selection-refused":
                return False
            state.selected = state.target
            return True

        def selected_count(mark):
            assert mark == -1
            if (
                defect == "count-before-point"
                and state.object_reads
                and not state.point_calls
            ):
                return 2
            if state.extra_selection:
                return 2
            return int(state.selected is not None)

        def selected_entity(index, mark):
            assert index == 1 and mark == -1
            if (
                defect == "identity-before-point"
                and state.object_reads
                and not state.point_calls
            ):
                state.selected = replacement
            state.object_reads.append(state.selected)
            if state.selected is None:
                return None
            # A different wrapper still identifies the same native IEdge.
            return _KitFlagNativeWrapper(state.selected)

        def set_selection_point(index, mark, x, y, z):
            assert not state.point_api_forbidden
            assert index == 1 and mark == -1
            assert state.selected is state.target
            assert not state.inserted
            state.real_events.append("set-point")
            state.point_calls.append((index, mark, x, y, z))
            # Even perfect geometry cannot authorize a non-True native receipt.
            # This keeps return-value regressions independent of readback guards.
            if defect in {
                "point-refused",
                "point-return-none",
                "point-truthy-not-bool",
            }:
                state.native_point = (x, y, z)
            if defect == "point-refused":
                return False
            if defect == "point-return-none":
                return None
            if defect == "point-truthy-not-bool":
                return 1
            if defect != "point-ignored":
                state.native_point = (x, y, z)
            if defect == "point-wrong":
                state.native_point = (x + 2e-8, y, z)
            elif defect == "point-wrong-z":
                state.native_point = (x, y, z + 2e-8)
            elif defect == "point-nan":
                state.native_point = (float("nan"), y, z)
            elif defect == "point-inf":
                state.native_point = (x, y, float("inf"))
            elif defect == "point-short":
                state.native_point = (x, y)
            elif defect == "point-long":
                state.native_point = (x, y, z, 0.0)
            elif defect == "point-within-tolerance":
                state.native_point = (x + 6e-9, y - 6e-9, z)
            elif defect == "count-after-point":
                state.extra_selection = True
            elif defect == "identity-after-point":
                state.selected = replacement
            elif defect == "selection-lost-after-point":
                state.selected = None
            return True

        def get_selection_point(index, mark):
            assert not state.point_api_forbidden
            assert index == 1 and mark == -1
            assert state.point_calls
            assert not state.inserted
            state.real_events.append("read-point")
            state.point_reads.append(state.native_point)
            return state.native_point

        def forbid_coordinate_pick(*_args, **_kwargs):
            pytest.fail(
                "installation entity selection must never use coordinate picking"
            )

        def insert_note(text):
            assert state.selected is not None
            assert state.active == state.view.GetName2()
            state.real_events.append("insert-note")
            tip = (
                state.default_tip
                if defect == "native-ignored-point"
                else state.native_point
            )
            note = _KitFlagNativeNote(
                text, state.view, _KitFlagNativeWrapper(state.selected), tip[:2]
            )
            if defect in {"insert-detached", "legacy-detached"}:
                note.annotation.entities = ()
                note.annotation.entity_count = 0
                note.annotation.entity_types = ()
            elif defect == "insert-rebound":
                note.annotation.entities = (_KitFlagNativeWrapper(replacement),)
            elif defect == "native-nan-leader":
                note.annotation.leader_override = (
                    0.0,
                    0.0,
                    0.0,
                    float("nan"),
                    tip[1],
                    0.0,
                )
            elif defect == "native-short-leader":
                note.annotation.leader_override = (0.0, 0.0, 0.0)

            def set_leader(*_arguments):
                note.annotation.leader_count = 1
                return 0

            def set_attached_entities(entities):
                state.repair_calls.append(note)
                if not state.legacy_repair_allowed:
                    pytest.fail(
                        "a native selection-point note must never repair attachment"
                    )
                note.annotation.entities = tuple(entities)
                note.annotation.entity_count = len(note.annotation.entities)
                note.annotation.entity_types = (1,)
                return True

            note.annotation.SetLeader3 = set_leader
            note.annotation.SetAttachedEntities = set_attached_entities
            state.note = note
            state.view.notes.append(note)
            state.inserted.append(note)
            return note

        def rebuild():
            state.real_events.append("rebuild")
            state.rebuilds.append(state.note)
            if defect == "rebuild-detached":
                state.note.annotation.entities = ()
                state.note.annotation.entity_count = 0
                state.note.annotation.entity_types = ()
            return True

        draw.SelectionManager = SimpleNamespace(
            CreateSelectData=create_select_data,
            GetSelectedObjectCount2=selected_count,
            GetSelectedObject6=selected_entity,
            SetSelectionPoint2=set_selection_point,
            GetSelectionPoint2=get_selection_point,
        )
        draw.Extension = SimpleNamespace(SelectByID2=forbid_coordinate_pick)
        draw.InsertNote = insert_note
        draw.EditRebuild3 = rebuild
        state.target.Select4 = select_entity
        state.adapter._get_attr_or_call = lambda target, name: getattr(target, name)()
        monkeypatch.setattr(native_notes, "_early_bound", lambda value, _kind: value)
        monkeypatch.setattr(
            native_selection, "_early_bound", lambda value, _kind: value
        )
        monkeypatch.setattr(
            native_notes, "dispatch_array", lambda entities: tuple(entities)
        )
        monkeypatch.setattr(
            native_selection._seat_forensics,
            "capture_pick_miss",
            forbid_coordinate_pick,
        )
        state.native_author = native_notes.add_attached_note
        return state

    return make


@pytest.mark.parametrize("configuration", ("HoldDownStud", "TNut", "FlangeNut"))
@pytest.mark.parametrize(
    "defect",
    (
        "selection-refused",
        "count-before-point",
        "identity-before-point",
        "point-refused",
        "point-return-none",
        "point-truthy-not-bool",
        "point-ignored",
        "point-wrong",
        "point-wrong-z",
        "point-nan",
        "point-inf",
        "point-short",
        "point-long",
        "count-after-point",
        "identity-after-point",
        "selection-lost-after-point",
    ),
)
def test_kit_installation_real_author_refuses_invalid_point_selection_before_insert(
    kit_installation_real_note_native, configuration, defect
):
    state = kit_installation_real_note_native(configuration, defect=defect)
    with pytest.raises(RuntimeError):
        state.native_author(
            state.adapter,
            state.view,
            text=state.key,
            entity=state.target,
            attached_to=state.target,
            leader_attach_xy=state.point,
            note_xy=state.view.center,
            label=f"kit {configuration} native selection-point refusal",
        )
    assert not state.inserted
    assert not state.rebuilds
    assert not state.repair_calls
    assert "insert-note" not in state.real_events
    if defect in {"selection-refused", "count-before-point", "identity-before-point"}:
        assert not state.point_calls
    else:
        assert len(state.point_calls) == 1
    if defect in {"point-refused", "point-return-none", "point-truthy-not-bool"}:
        assert not state.point_reads


@pytest.mark.parametrize("configuration", ("HoldDownStud", "TNut", "FlangeNut"))
@pytest.mark.parametrize(
    "defect",
    (
        "insert-detached",
        "insert-rebound",
        "rebuild-detached",
        "native-ignored-point",
        "native-nan-leader",
        "native-short-leader",
    ),
)
def test_kit_installation_real_author_refuses_lost_association_without_repair(
    kit_installation_real_note_native, configuration, defect
):
    state = kit_installation_real_note_native(configuration, defect=defect)
    with pytest.raises(RuntimeError):
        state.native_author(
            state.adapter,
            state.view,
            text=state.key,
            entity=state.target,
            attached_to=state.target,
            leader_attach_xy=state.point,
            note_xy=state.view.center,
            label=f"kit {configuration} native inserted-note refusal",
        )
    assert state.inserted == [state.note]
    assert len(state.point_calls) == 1
    assert not state.note.annotation.leader_set_calls
    assert not state.repair_calls


@pytest.mark.parametrize("explicit_none", (False, True))
@pytest.mark.parametrize("initially_attached", (True, False))
def test_kit_real_note_author_default_does_not_require_selection_point_apis(
    kit_installation_real_note_native, explicit_none, initially_attached
):
    state = kit_installation_real_note_native(
        "HoldDownStud", defect=None if initially_attached else "legacy-detached"
    )
    state.legacy_repair_allowed = not initially_attached
    state.point_api_forbidden = True
    options = {"leader_attach_xy": None} if explicit_none else {}
    note = state.native_author(
        state.adapter,
        state.view,
        text=state.key,
        entity=state.target,
        attached_to=state.target,
        note_xy=state.view.center,
        label="kit native note unchanged default branch",
        **options,
    )
    assert note is state.note
    assert state.inserted == [note]
    assert note.annotation.landing == state.default_tip
    assert not state.point_calls
    assert not state.point_reads
    assert not note.annotation.leader_set_calls
    assert state.repair_calls == ([] if initially_attached else [note])
    assert note.annotation.entity_count == 1
    assert note.annotation.entities[0].native_identity is state.target.native_identity


def test_kit_real_note_author_accepts_finite_selection_point_within_native_tolerance(
    kit_installation_real_note_native,
):
    state = kit_installation_real_note_native(
        "HoldDownStud", defect="point-within-tolerance"
    )
    note = state.native_author(
        state.adapter,
        state.view,
        text=state.key,
        entity=state.target,
        attached_to=state.target,
        leader_attach_xy=state.point,
        note_xy=state.view.center,
        label="kit native selection-point readback tolerance",
    )
    assert note is state.note
    assert note.annotation.landing == state.native_point
    assert state.inserted == [note]
    assert not note.annotation.leader_set_calls


@pytest.mark.parametrize(
    "invalid",
    ("missing-entity", "nan-x", "inf-y", "short-xy", "long-xy"),
)
def test_kit_real_note_point_requires_direct_entity_and_finite_xy_before_selection(
    kit_installation_real_note_native, invalid
):
    state = kit_installation_real_note_native("HoldDownStud")
    x, y = state.point
    point = {
        "missing-entity": state.point,
        "nan-x": (float("nan"), y),
        "inf-y": (x, float("inf")),
        "short-xy": (x,),
        "long-xy": (x, y, 0.0),
    }[invalid]
    with pytest.raises(ValueError):
        state.native_author(
            state.adapter,
            state.view,
            text=state.key,
            entity=None if invalid == "missing-entity" else state.target,
            entity_xy=state.point if invalid == "missing-entity" else None,
            attached_to=state.target,
            leader_attach_xy=point,
            note_xy=state.view.center,
            label="kit invalid native selection-point request",
        )
    assert not state.select_calls
    assert not state.point_calls
    assert not state.inserted


@pytest.mark.parametrize("attached_to", ("omitted", "same-native", "wrong-native"))
def test_kit_real_note_point_checks_the_named_native_entity_before_insertion(
    kit_installation_real_note_native, attached_to
):
    state = kit_installation_real_note_native("HoldDownStud")
    options = {}
    if attached_to == "same-native":
        options["attached_to"] = _KitFlagNativeWrapper(state.target)
    elif attached_to == "wrong-native":
        options["attached_to"] = _KitFlagNativeEdge(circle=state.target.CircleParams)

    def author():
        return state.native_author(
            state.adapter,
            state.view,
            text=state.key,
            entity=state.target,
            leader_attach_xy=state.point,
            note_xy=state.view.center,
            label="kit named native installation edge",
            **options,
        )

    if attached_to == "wrong-native":
        with pytest.raises(RuntimeError):
            author()
        assert not state.point_calls
        assert not state.inserted
    else:
        note = author()
        assert state.inserted == [note]
        assert note.annotation.landing == pytest.approx((*state.point, 0.0))
        assert not note.annotation.leader_set_calls


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


def _clamp_recovered_head_height():
    # 4dcfee recovered SupplierHeadHeight display data, metres, 2026-10-21.
    # Inline only the native primitives needed here; no external log dependency.
    z = 0.0000125
    return {
        "type": 4,
        "name": "SupplierHeadHeight",
        "visible": 1,
        "pos": (0.1029834, 0.2350132, z),
        "display": {
            "lines": [
                [0, 0, 0, 0, 0.1135714, 0.2347655, z, 0.1019834, 0.2347655, z],
                [0, 0, 0, 0, 0.1135714, 0.2352608, z, 0.1019834, 0.2352608, z],
                [0, 0, 0, 0, 0.1029834, 0.2347655, z, 0.1029834, 0.2284155, z],
                [0, 0, 0, 0, 0.1029834, 0.2352608, z, 0.1029834, 0.2416108, z],
            ],
            "arrows": [
                [0.1029834, 0.2347655, z, 0, -1, 0, 0.003556, 0.000762, 0, 0, 0, 1],
                [0.1029834, 0.2352608, z, 0, 1, 0, 0.003556, 0.000762, 0, 0, 0, 1],
            ],
            "texts": [
                {
                    "t": " (0.156 in) ",
                    "pos": (0.0916157, 0.232235, z),
                    "h": 0.0035,
                    "w": 0.0227354,
                    "ref": 1,
                    "ang": 0.0,
                }
            ],
        },
    }


def test_clamp_native_geometry_distinguishes_offset_ink_from_real_witnesses(
    monkeypatch,
):
    import draw_sh_vn_clamp_screw as clamp

    record = _clamp_recovered_head_height()
    monkeypatch.setattr(
        clamp, "_Reader", lambda _adapter: SimpleNamespace(take_errors=lambda: {})
    )
    monkeypatch.setattr(clamp, "_dump_annotation", lambda *_args: record)
    display = SimpleNamespace(GetAnnotation=lambda: object())
    original_record = copy.deepcopy(record)
    before = clamp._native_geometry(None, display, "SupplierHeadHeight")
    assert before["axis"] == 1
    assert before["tips"] == (
        (0.1029834, 0.2347655),
        (0.1029834, 0.2352608),
    )
    assert before["witnesses"] == (
        (0.2347655, 0.1019834, 0.1135714),
        (0.2352608, 0.1019834, 0.1135714),
    )
    assert before["reach"] == pytest.approx(0.2416108)
    assert before["text"].width > 0.015
    assert record == original_record

    z = record["pos"][2]
    # Native OffsetText uses display-data paths, not registered leaders. The
    # perpendicular underline is NOT at either arrow-tip station; the diagonal
    # connector is NOT a witness even when its start touches an arrow tip.
    offset_rows = [
        [0, 0, 0, 0, 0.0916157, 0.250, z, 0.1143511, 0.250, z],
        [0, 0, 0, 0, 0.1029834, 0.2352608, z, 0.0916157, 0.250, z],
    ]
    record["display"]["lines"].extend(offset_rows)
    for row in record["display"]["lines"][:2]:
        row[4:7], row[7:10] = row[7:10], row[4:7]
    with_offset = copy.deepcopy(record)
    after = clamp._native_geometry(None, display, "SupplierHeadHeight")
    for key in ("tips", "witnesses", "reach"):
        assert after[key] == before[key]
    assert after["record"] == with_offset
    assert after["record"]["display"]["lines"][-2:] == offset_rows
    assert record == with_offset  # No pruning of ink before the full audit.

    del record["display"]["lines"][0]
    with pytest.raises(RuntimeError, match="witness"):
        clamp._native_geometry(None, display, "SupplierHeadHeight")
    record = copy.deepcopy(with_offset)
    record["display"]["lines"][0][5] += 0.0001
    record["display"]["lines"][0][8] += 0.0001
    with pytest.raises(RuntimeError, match="witness"):
        clamp._native_geometry(None, display, "SupplierHeadHeight")
    record = copy.deepcopy(with_offset)
    record["display"]["lines"][0][4] -= 0.0001
    changed = clamp._native_geometry(None, display, "SupplierHeadHeight")
    with pytest.raises(RuntimeError, match="native witnesses moved"):
        clamp._assert_stations("SupplierHeadHeight", before, changed)


@pytest.mark.parametrize(
    "defect", (None, "ignored-seed", "ignored-shelf", "station-drift")
)
def test_clamp_annotation_hook_shelves_native_text_and_rechecks_late_drift(
    monkeypatch, defect
):
    import draw_sh_vn_clamp_screw as clamp
    from _layout_geometry import Box, segment_box_distance

    # Bounded native-shaped model, following the thumb measured-offset fixture:
    # text moves independently; enabling OffsetText snaps the native line to
    # its seeded transverse anchor, then later text moves leave it fixed.
    # The vertical short row uses recovered HeadHeight primitives verbatim.
    class Display:
        def __init__(self, name, axis, span):
            self.name, self.axis = name, axis
            self.record = _clamp_recovered_head_height()
            self.record["name"] = name
            data = self.record["display"]
            if axis == 0:
                for row in data["lines"]:
                    row[4], row[5] = row[5], row[4]
                    row[7], row[8] = row[8], row[7]
                for row in data["arrows"]:
                    row[0], row[1] = row[1], row[0]
                    row[3], row[4] = row[4], row[3]
                self.record["pos"] = (0.2350132, 0.1057615, 0.0)
                data["texts"] = [
                    {
                        "t": "(<MOD-DIAM>0.164 in)",
                        "pos": (0.222, 0.1058, 0),
                        "h": 0.0035,
                        "w": 0.0254278,
                        "ref": 1,
                        "ang": 0.0,
                    },
                    {
                        "t": "8-32",
                        "pos": (0.230, 0.1002, 0),
                        "h": 0.0035,
                        "w": 0.009309,
                        "ref": 1,
                        "ang": 0.0,
                    },
                ]
            if span is not None:
                # Long vertical reference: enough native span for its text,
                # not an outside-arrow short row that should enter offset mode.
                data["arrows"][0][1] = 0.210
                data["arrows"][1][1] = 0.260
                data["lines"][0][5] = data["lines"][0][8] = 0.210
                data["lines"][1][5] = data["lines"][1][8] = 0.260
                data["lines"][2:] = [
                    [0, 0, 0, 0, 0.1029834, 0.210, 0, 0.1029834, 0.229, 0],
                    [0, 0, 0, 0, 0.1029834, 0.242, 0, 0.1029834, 0.260, 0],
                ]
                data["texts"][0]["t"] = "(1.25 in)"
            self.position = tuple(self.record["pos"])
            self.original_position = self.position
            self._offset = False
            dimensions = clamp.supplier.SUPPLIER_REFERENCE_DIMENSIONS
            values = {name: value for name, value, _orientation in dimensions}
            value = values[name]
            self.native = SimpleNamespace(
                Name=name,
                FullName=f"{name}@SupplierReference@clamp.SLDPRT",
                SystemValue=value / 1000,
            )

        def GetAnnotation(self):
            return self

        def GetDimension2(self, _index):
            return self.native

        def GetPosition(self):
            return self.position

        @property
        def OffsetText(self):
            return self._offset

        @OffsetText.setter
        def OffsetText(self, enabled):
            if enabled and not self._offset:
                transverse = 1 - self.axis
                delta = (
                    self.position[transverse]
                    - self.record["display"]["arrows"][0][transverse]
                )
                self.shift_stations(transverse, delta)
            self._offset = enabled

        def shift_stations(self, axis, delta):
            for row in self.record["display"]["lines"]:
                row[4 + axis] += delta
                row[7 + axis] += delta
            for row in self.record["display"]["arrows"]:
                row[axis] += delta

        def SetPosition2(self, x, y, z):
            if self.name == "SupplierThreadDiameter" and (
                (defect == "ignored-seed" and not self.OffsetText)
                or (defect == "ignored-shelf" and self.OffsetText)
            ):
                return True  # Native success is not proof of a settled move.
            delta = (x - self.position[0], y - self.position[1])
            for row in self.record["display"]["texts"]:
                px, py, pz = row["pos"]
                row["pos"] = (px + delta[0], py + delta[1], pz)
            self.position = (x, y, z)
            self.record["pos"] = self.position
            if (
                defect == "station-drift"
                and self.OffsetText
                and abs(delta[self.axis]) > 0.001
            ):
                self.shift_stations(self.axis, 0.0001)
            return True

    displays = {
        name: Display(name, axis, span)
        for name, axis, span in (
            ("SupplierHeadHeight", 1, None),
            ("SupplierThreadDiameter", 0, None),
            ("SupplierLength", 1, 0.050),
        )
    }
    adapter = object()
    views = {
        "*Top": SimpleNamespace(
            GetOrientationName=lambda: "*Top",
            GetName2=lambda: "Top",
            GetOutline=lambda: (0.01, 0.01, 0.40, 0.27),
        )
    }
    checks, audited = [], []

    def source_callback():
        pass

    def shared_annotate(actual_adapter, actual_views, **settings):
        assert actual_adapter is adapter and actual_views is views
        assert settings["dimensions"] is clamp.supplier.SUPPLIER_REFERENCE_DIMENSIONS
        assert settings["formats"] is clamp.supplier.SUPPLIER_REFERENCE_FORMATS
        assert settings["settled_checks"] is checks
        settings["settled_checks"].append(source_callback)

    monkeypatch.setattr(clamp, "annotate_supplier_screw", shared_annotate)
    monkeypatch.setattr(clamp, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(clamp, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(clamp, "_supplier_displays", lambda _adapter: dict(displays))
    monkeypatch.setattr(clamp, "iter_views", lambda _adapter: iter(views.values()))
    monkeypatch.setattr(
        clamp, "sheet_region", lambda _adapter: Box(0.01, 0.01, 0.42, 0.27)
    )
    monkeypatch.setattr(
        clamp, "_Reader", lambda _adapter: SimpleNamespace(take_errors=lambda: {})
    )
    monkeypatch.setattr(
        clamp,
        "_dump_annotation",
        lambda _reader, annotation: copy.deepcopy(annotation.record),
    )
    # Isolate the native shelf contract from the separate full-sheet collision
    # rules; the real final layout guard still reacquires and measures each row.
    monkeypatch.setattr(clamp, "audit_dump", lambda dump: audited.append(dump) or [])
    transverse_before = {
        name: tuple(
            row["pos"][1 - display.axis] for row in display.record["display"]["texts"]
        )
        for name, display in displays.items()
    }
    before = {
        name: clamp._native_geometry(adapter, display, name)
        for name, display in displays.items()
    }
    native_before = {
        name: (display.native.FullName, display.native.SystemValue)
        for name, display in displays.items()
    }
    thread_text = tuple(
        row["t"]
        for row in displays["SupplierThreadDiameter"].record["display"]["texts"]
    )
    if defect:
        message = {
            "ignored-seed": "anchor did not settle",
            "ignored-shelf": "text crowds its native line",
            "station-drift": "native (tips|witnesses) moved",
        }[defect]
        with pytest.raises(RuntimeError, match=message):
            clamp._annotate_supplier_dimensions(adapter, views, settled_checks=checks)
        return

    clamp._annotate_supplier_dimensions(adapter, views, settled_checks=checks)
    assert checks[0] is source_callback
    assert checks[-1].func is clamp._assert_supplier_layout
    assert audited
    for name, display in displays.items():
        after = clamp._native_geometry(adapter, display, name)
        assert (display.native.FullName, display.native.SystemValue) == native_before[
            name
        ]
        for key in ("tips", "witnesses"):
            assert after[key] == before[name][key]
        # Geometric ink clearance, not a tautological assertion about the target
        # helper: the entire text block must clear every physical native run,
        # including witnesses and arrowheads, on both short and long rows.
        ink = clamp.annotation_geometry(
            after["record"],
            owner=name,
            advance=clamp.calibrate_sheet_advance((after["record"],)),
        )
        assert ink is not None and ink.segments
        assert all(
            segment_box_distance(segment, after["text"]) >= clamp.CLEAR_GAP_M
            for segment in ink.segments
        )
        assert tuple(
            row["pos"][1 - display.axis] for row in display.record["display"]["texts"]
        ) == pytest.approx(transverse_before[name])
        if name == "SupplierLength":
            assert display.OffsetText is False
            assert display.position == display.original_position
        else:
            axis = display.axis
            low = after["text"].xmin if axis == 0 else after["text"].ymin
            assert display.OffsetText is True
            assert low - after["reach"] >= clamp.CLEAR_GAP_M
            assert display.position[1 - axis] == display.original_position[1 - axis]
            assert display.position[axis] != display.original_position[axis]
    assert (
        tuple(
            row["t"]
            for row in displays["SupplierThreadDiameter"].record["display"]["texts"]
        )
        == thread_text
    )
    assert "8-32" in thread_text
    checks[-1]()  # Execute, not merely inspect, the registered late guard.
    old = displays["SupplierHeadHeight"]
    replacement = copy.copy(old)
    replacement.record = copy.deepcopy(old.record)
    replacement.record["display"]["texts"][0]["pos"] = (0.0916157, 0.232235, 0)
    displays[old.name] = replacement
    with pytest.raises(RuntimeError, match="text crowds its native line"):
        checks[-1]()  # Must reacquire; a captured old display would still pass.
    replacement.record = copy.deepcopy(old.record)
    replacement.shift_stations(replacement.axis, 0.0001)
    with pytest.raises(RuntimeError, match="native (tips|witnesses) moved"):
        checks[-1]()


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


def test_metric_flange_nut_supplier_lanes_leave_a_fittable_end_view():
    import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as supplier
    from _supplier_screw_layout import supplier_screw_margins

    margins = supplier_screw_margins(
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
        sides=supplier.SUPPLIER_REFERENCE_SIDES,
    )
    cells = purchased.fastener_view_cells(
        purchased.view_band_bottom(
            supplier.DRAWING_NOTES,
            label="metric flange nut",
            supplier_data=("SOURCE NOMINALS; INTERNAL THREAD NOT MODELLED.",),
        )
    )
    fitted = purchased.supplier_fit_cells(cells, margins, label="metric flange nut")
    end_cell = next(bounds for name, _center, bounds in fitted if name == "*Top")
    # A positive cell alone is insufficient: even the smallest permitted scale
    # must retain the real flange envelope plus native-view padding.
    smallest_ratio = min(
        numerator / denominator for numerator, denominator in purchased._SCALES
    )
    required_span = supplier.FLANGE_DIA / 1000.0 * smallest_ratio + 0.002
    assert min(end_cell[2] - end_cell[0], end_cell[3] - end_cell[1]) >= required_span


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
    """Native-I/O doubles; run the real body, source, band and import guards."""
    import _supplier_washer_drawing as washer
    import _supplier_washer_model as model_helpers

    for module in (washer, model_helpers):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(model_helpers, "_bind", lambda value, _interface: value)
    monkeypatch.setattr(model_helpers, "double_array", lambda value: value)
    values = values or {washer.OUTER_DIAMETER: 12.7, washer.BORE_DIAMETER: 6.35, washer.THICKNESS: 1.5875}
    outer, bore, thickness = (values[key] for key in (washer.OUTER_DIAMETER, washer.BORE_DIAMETER, washer.THICKNESS))
    precision = dict.fromkeys(values, 3)
    bands = {label: (value - 0.05, value + 0.05, "bilateral") for label, value in values.items()}

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
            case.native.Tolerance = SimpleNamespace(Type=2, GetMinValue=lambda: -0.00005,
                                                    GetMaxValue=lambda: 0.00005)
            case.display.GetPrimaryTolPrecision2 = lambda: 3
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
        sources[washer.THICKNESS].native.Tolerance.Type = 0
    elif defect == "import_value":
        imports[washer.THICKNESS].native.SystemValue *= 2.0
    elif defect == "source_geometry":
        points[0].X += 0.001
    elif defect == "import_band":
        imports[washer.THICKNESS].native.Tolerance.Type = 0
    case = SimpleNamespace(
        helper=washer, source_helper=model_helpers, adapter=adapter, model=model, views=views,
        sources=sources, imports=imports, mapped=mapped, entities=source_entities,
        precision=precision, bands=bands, imported_calls=imported_calls,
        kwargs=dict(axis=axis, bore_mm=bore, outer_mm=outer, thickness_mm=thickness,
                    units="in", precision=precision, bands=bands),
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
