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


@pytest.mark.parametrize("number_fit", (None, purchased.NumberFit.SHRINK_TO_CELL))
def test_spec_layout_selects_template_dimensions_and_reaches_all_layout_checks(
    monkeypatch, tmp_path: Path, number_fit
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

    def fit_number(_adapter, actual_draw, *, layout, number):
        assert actual_draw is draw
        calls.append(("number-fit", layout, number))
        return lambda: calls.append(("number-fit-settled",))

    monkeypatch.setattr(purchased, "_fit_number", fit_number)

    async def finalize(
        _adapter, actual_outputs, *, layout, pdf_title, scale, settled_checks
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

    def new_drawing(adapter, *, layout):
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
    source_bore = SimpleNamespace(
        Name=bore_feature,
        GetTypeName2=lambda: "HoleWzd",
        GetDefinition=lambda: bore_definition,
    )
    feature_readback = source_bore
    native_features = {
        bore_feature: source_bore,
        other_feature: SimpleNamespace(Name=other_feature),
        "Body": SimpleNamespace(Name="Body"),
    }

    def face(feature=bore_feature):
        native = native_features[feature] if isinstance(feature, str) else feature
        return SimpleNamespace(GetFeature=lambda: native)

    def edge(feature=bore_feature):
        return SimpleNamespace(
            GetTwoAdjacentFaces2=lambda: (face("Body"), face(feature))
        )

    class BoreRim:
        def __init__(self):
            self.feature = bore_feature
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
    views = [
        SimpleNamespace(
            GetOutline=lambda box=box: (
                box[0] + offset,
                box[1],
                box[2] + offset,
                box[3],
            )
        )
        for box in outlines
    ]
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
            if drawing_state.active is None:
                return None
            return SimpleNamespace(GetName2=lambda: drawing_state.active)

        def GetCurrentSheet(self):
            return SimpleNamespace(GetName=lambda: drawing_state.sheet)

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
            if drift == "bore-fresh-wrapper":
                return AnnotationReadback(feature_readback, feature_readback)
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

    def read_annotations():
        assert events[0] == "final-display-mode"
        assert events[-1] == "refresh"
        events.append("inventory")
        return native_threads

    # GetNotes exposes only an unrelated literal decoy, not ThreadCallout.
    decoy = _Note("literal", "1/2-13 Tapped Hole", offset + 0.32, 0.23)
    views[3].GetNotes = lambda: [decoy]
    views[3].GetAnnotations = read_annotations
    views[3].UpdateViewDisplayGeometry = lambda: events.append("refresh")
    views[3].GetName2 = lambda: iso_name
    views[3].ReferencedDocument = SimpleNamespace(FeatureByName=source_feature)

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
    monkeypatch.setattr(
        kit, "visible_view_entities", lambda *_args, **_kwargs: visible_rims
    )
    monkeypatch.setattr(kit, "model_points_in_view", project_points)
    monkeypatch.setattr(
        kit,
        "set_high_quality_shaded_with_edges",
        lambda *_args, **_kwargs: events.append("final-display-mode"),
    )
    monkeypatch.setattr(kit, "_early_bound", lambda value, _kind: value)
    adapter = SimpleNamespace(
        currentModel=Drawing(),
        swApp=SimpleNamespace(
            IsSame=lambda a, b: int(
                getattr(a, "native_identity", a) is getattr(b, "native_identity", b)
            )
        ),
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
        rim.feature = other_feature
    elif drift in {"rim-wrong-height", "rim-wrong-radius"}:
        circle = list(rim.CircleParams)
        circle[1 if drift == "rim-wrong-height" else 6] += 0.001
        rim.CircleParams = tuple(circle)
    elif drift == "rim-duplicate":
        visible_rims.append(BoreRim())
    elif drift == "rim-missing":
        visible_rims.remove(rim)
    elif drift == "rim-feature-identity":
        rim.feature = SimpleNamespace(Name=bore_feature)
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
    initial_refusals = {
        "setter-refused": "placement refused",
        "setter-ignored": "leader attachment moved",
        "setter-parent-detached": "expected one automatic",
        "setter-geometry-detached": "expected one automatic",
        "setter-note-identity": "lost identity, attachment or clearance",
        "setter-owner-detached": "lost identity, attachment or clearance",
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
        with pytest.raises(RuntimeError, match=initial_refusals[drift]):
            kit.annotate_member(adapter, configuration, cells, views)
        assert "insert" not in events and "delete-note" not in events
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
        feature_readback = SimpleNamespace(
            Name=bore_feature,
            GetTypeName2=lambda: "HoleWzd",
            GetDefinition=lambda: bore_definition,
        )
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

    radius = (kit.stud.RADIUS - kit.stud.END_CHAMFER) / 1000
    rims = [Rim(kit.stud.LENGTH / 1000, radius), Rim(0.0, radius)]
    land = Rim(kit.stud.END_CHAMFER / 1000, kit.stud.RADIUS / 1000)
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
