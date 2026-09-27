"""Offline contracts for the title-block MATERIAL cell.

The template's MATERIAL cell links the generic SolidWorks material; swing's
877-final audit found 58 of 111 drawings printing it instead of the part's
Material Specification (cone_gear T006-T024 Brass for C67500, knife_mount
Plain Carbon Steel for AISI O1).  finalize_drawing now retargets the cell on
every sheet and reads the resolved text back.

The fakes model the one behaviour the binding rests on: a ``$PRPSHEET`` link
resolves, on rebuild, through the sheet's property view -- its
CustomPropertyView, or for a sheet pasted in "same as Document Properties"
mode, the FIRST sheet's view -- and a configuration property wins over the
file property.  finalize_drawing and the cone-gear recipe run for real on
them; only their COM-heavy tails are stubbed.
"""

from __future__ import annotations

import ast
import asyncio
import re
from pathlib import Path

import pytest

import _common
import _config
import _drawing_common
import cone_gear_spec
import draw_cone_gear
from _drawing_registry import DRAWINGS

SCRIPTS = Path(__file__).resolve().parent
TEMPLATE_TEXT = 'MATERIAL\n$PRPSHEET:"Material"'
_LINK = re.compile(r'\$PRPSHEET:"([^"]+)"')


class FakeModel:
    """A source model: file properties plus per-configuration overrides."""

    def __init__(self, file: dict[str, str], configurations: dict[str, dict[str, str]]) -> None:
        self.file = file
        self.configurations = configurations

    def GetCustomInfoValue(self, configuration: str, name: str) -> str:
        if configuration:
            return self.configurations.get(configuration, {}).get(name, "")
        return self.file.get(name, "")

    def resolve(self, configuration: str, name: str) -> str:
        return self.GetCustomInfoValue(configuration, name) or self.GetCustomInfoValue("", name)


class FakeView:
    def __init__(self, name: str, model: FakeModel, configuration: str) -> None:
        self.name = name
        self.ReferencedDocument = model
        self.ReferencedConfiguration = configuration

    def GetName2(self) -> str:
        return self.name

    def GetOrientationName(self) -> str:
        return "*Front"

    def UpdateViewDisplayGeometry(self) -> None:
        pass


class FakeNote:
    def __init__(self, linked: str) -> None:
        self.PropertyLinkedText = linked
        self.text = ""

    def GetText(self) -> str:
        return self.text


class FakeAnnotation:
    def __init__(self, note: FakeNote) -> None:
        self.note = note

    def GetType(self) -> int:
        return 6  # swNote

    def GetSpecificAnnotation(self) -> FakeNote:
        return self.note


class FakeSheetView:
    def __init__(self, notes: list[FakeNote]) -> None:
        self.notes = notes

    def GetAnnotations(self) -> list[FakeAnnotation]:
        return [FakeAnnotation(note) for note in self.notes]


class FakeSheet:
    def __init__(self, name: str, *, same_as_document: bool, text: str) -> None:
        self.name = name
        self.same_as_document = same_as_document
        self.notes = [FakeNote(text)]
        self.views: list[FakeView] = []
        self.CustomPropertyView = ""

    def GetName(self) -> str:
        return self.name

    def GetProperties2(self) -> list[object]:
        return [0, 0, 1.0, 1.0, False, 0.4318, 0.2794, self.same_as_document]

    def SetProperties2(self, *properties: object) -> bool:
        self.same_as_document = bool(properties[7])
        return True

    def SetScale(self, *args: object) -> bool:
        return True

    def GetViews(self) -> list[FakeView]:
        return self.views


class FakeDrawing:
    """Both IModelDoc2 and IDrawingDoc; $PRPSHEET text resolves on rebuild."""

    def __init__(self) -> None:
        self.sheets: dict[str, FakeSheet] = {}
        self.active = ""
        self.activations: list[str] = []

    def add_sheet(self, name: str, *, same_as_document: bool = False, text: str = TEMPLATE_TEXT) -> FakeSheet:
        sheet = FakeSheet(name, same_as_document=same_as_document, text=text)
        self.sheets[name] = sheet
        self.active = self.active or name
        return sheet

    def GetSheetNames(self) -> tuple[str, ...]:
        return tuple(self.sheets)

    def GetFirstView(self) -> FakeSheetView:
        return FakeSheetView(self.sheets[self.active].notes)

    def GetCurrentSheet(self) -> FakeSheet:
        return self.sheets[self.active]

    def ActivateSheet(self, name: str) -> bool:
        if name not in self.sheets:
            return False
        self.active = name
        self.activations.append(name)
        return True

    def Sheet(self, name: str) -> FakeSheet:
        return self.sheets[name]

    def ClearSelection2(self, _all: bool) -> None:
        pass

    def GetTitle(self) -> str:
        return "fake.SLDDRW"

    def _property_view(self, sheet: FakeSheet) -> FakeView:
        if sheet.same_as_document:
            sheet = next(iter(self.sheets.values()))
        named = [view for view in sheet.views if view.name == sheet.CustomPropertyView]
        return (named or sheet.views)[0]

    def EditRebuild3(self) -> bool:
        for sheet in self.sheets.values():
            if not sheet.views:
                continue
            view = self._property_view(sheet)
            for note in sheet.notes:
                resolved = _LINK.sub(
                    lambda m: view.ReferencedDocument.resolve(view.ReferencedConfiguration, m.group(1)),
                    note.PropertyLinkedText,
                )
                note.text = resolved.replace("\n", "\r\n")  # INote reads back CRLF
        return True


class FakeAdapter:
    def __init__(self, drawing: FakeDrawing) -> None:
        self.currentModel = drawing
        self.swApp = type("App", (), {"CloseDoc": lambda _self, _title: True})()

    def _get_attr_or_call(self, obj: object, name: str) -> object:
        value = getattr(obj, name)
        return value() if callable(value) else value

    async def open_model(self, path: str) -> bool:
        return True


@pytest.fixture
def finalize_tail(monkeypatch, tmp_path):
    """Stub finalize_drawing's export tail and the view walk; keep its sheet loop."""
    monkeypatch.setattr(
        _drawing_common,
        "iter_views",
        lambda adapter: iter(adapter.currentModel.GetCurrentSheet().views),
    )
    for name, value in {
        "apply_custom_properties": lambda *args, **kwargs: None,
        "assert_asme_b_sheet": lambda *args, **kwargs: None,
        "set_high_quality_shaded_with_edges": lambda *args, **kwargs: None,
        "read_required_properties": lambda *args, **kwargs: {},
        "save_drawing": lambda *args, **kwargs: {"drawing": "d", "pdf": "p"},
        "assert_precise_isometric_views": lambda *args: None,
        "sanitize_pdf_metadata": lambda *args, **kwargs: None,
        "render_pdf_png": lambda *args, **kwargs: None,
        "run_layout_audit": lambda *args, **kwargs: None,
        "layout_report_path": lambda stem: tmp_path / f"{stem}.json",
        "_visible_document_paths": lambda adapter: [],
        "_build_id": lambda: "test",
    }.items():
        monkeypatch.setattr(_drawing_common, name, value)
    return _drawing_common.DrawingOutputs(
        slddrw=tmp_path / "t.SLDDRW", pdf=tmp_path / "t.pdf", png=tmp_path / "t.png"
    )


def _finalize(adapter: FakeAdapter, outputs, **kwargs) -> None:
    asyncio.run(
        _drawing_common.finalize_drawing(
            adapter,
            outputs,
            layout=next(iter(_drawing_common.DRAWING_TEMPLATES)),
            pdf_title="t",
            **kwargs,
        )
    )


PART = FakeModel(
    {"Material": "Plain Carbon Steel", "Material Specification": "AISI O1 tool steel"}, {}
)


def test_finalize_prints_the_specification_not_the_generic_material(finalize_tail) -> None:
    drawing = FakeDrawing()
    drawing.add_sheet("Sheet1").views.append(FakeView("Drawing View1", PART, "Default"))
    _finalize(FakeAdapter(drawing), finalize_tail)
    note = drawing.sheets["Sheet1"].notes[0]
    assert note.PropertyLinkedText == 'MATERIAL\n$PRPSHEET:"Material Specification"'
    assert note.GetText() == "MATERIAL\r\nAISI O1 tool steel"


def test_finalize_is_traced_as_drawing_finalize(finalize_tail, monkeypatch) -> None:
    # The pin_sheet_property_view extraction once stole this decorator.
    import contextlib

    import _telemetry

    opened: list[str] = []
    real_aspan, real_span = _telemetry.aspan, _telemetry.span

    @contextlib.asynccontextmanager
    async def aspan(name, **attrs):
        opened.append(name)
        async with real_aspan(name, **attrs) as current:
            yield current

    @contextlib.contextmanager
    def span(name, **attrs):
        opened.append(name)
        with real_span(name, **attrs) as current:
            yield current

    monkeypatch.setattr(_telemetry, "aspan", aspan)
    monkeypatch.setattr(_telemetry, "span", span)
    drawing = FakeDrawing()
    drawing.add_sheet("Sheet1").views.append(FakeView("Drawing View1", PART, "Default"))
    _finalize(FakeAdapter(drawing), finalize_tail)
    assert opened[0] == "drawing.finalize"
    assert opened.count("drawing.finalize") == 1
    assert "drawing.pin_sheet_property_view" in opened


def test_finalize_fails_a_blank_specification_rather_than_print_material(finalize_tail) -> None:
    drawing = FakeDrawing()
    blank = FakeModel({"Material": "Brass", "Material Specification": " "}, {})
    drawing.add_sheet("Sheet1").views.append(FakeView("Drawing View1", blank, "Default"))
    with pytest.raises(RuntimeError, match="no 'Material Specification'"):
        _finalize(FakeAdapter(drawing), finalize_tail)


def test_finalize_fails_a_link_that_does_not_resolve(finalize_tail, monkeypatch) -> None:
    drawing = FakeDrawing()
    drawing.add_sheet("Sheet1").views.append(FakeView("Drawing View1", PART, "Default"))
    monkeypatch.setattr(drawing, "EditRebuild3", lambda: True)  # text never resolves
    with pytest.raises(RuntimeError) as failure:
        _finalize(FakeAdapter(drawing), finalize_tail)
    message = str(failure.value)
    assert "sheet 'Sheet1' MATERIAL did not resolve" in message
    assert "expected 'MATERIAL\\nAISI O1 tool steel', got ''" in message
    assert "property view 'Drawing View1'" in message


@pytest.mark.parametrize(
    ("text", "count"),
    [("MATERIAL: (none)", 0), ('$PRPSHEET:"Material" $PRPSHEET:"Material Specification"', 2)],
)
def test_bind_needs_exactly_one_material_cell(text: str, count: int) -> None:
    drawing = FakeDrawing()
    drawing.add_sheet("Sheet1", text=text)
    with pytest.raises(RuntimeError, match=f"exactly one MATERIAL property link, found {count}"):
        _drawing_common.bind_title_material(drawing, sheet_name="Sheet1", material="x")


def test_bind_accepts_a_sheet_that_arrives_bound() -> None:
    drawing = FakeDrawing()
    drawing.add_sheet("Sheet1", text='MATERIAL\n$PRPSHEET:"Material Specification"')
    binding = _drawing_common.bind_title_material(drawing, sheet_name="Sheet1", material="x")
    assert binding.linked_text == 'MATERIAL\n$PRPSHEET:"Material Specification"'


def test_configuration_property_wins_over_the_file_property() -> None:
    model = FakeModel(
        {"Material Specification": "C36000 free-machining brass"},
        {"T006": {"Material Specification": "C67500 manganese bronze"}},
    )
    read = _drawing_common.linked_title_material
    assert read(model, "T006", label="t") == "C67500 manganese bronze"
    assert read(model, "T030", label="t") == "C36000 free-machining brass"


def _cone_gear_model() -> FakeModel:
    return FakeModel(
        {"Material": "Brass", "Material Specification": cone_gear_spec.BODY_MATERIAL_SPEC},
        {
            f"T{teeth:03d}": {"Material Specification": cone_gear_spec.material_specification(teeth)}
            for teeth in cone_gear_spec.CONFIGURATION_TEETH
        },
    )


def test_pasted_sheets_read_their_own_configuration(finalize_tail) -> None:
    """Unpinned, a pasted sheet resolves through the FIRST sheet's view: the
    T030 page would print T006's tip bronze."""
    model = _cone_gear_model()
    drawing = FakeDrawing()
    for name, pasted in (("T006", False), ("T030", True)):
        drawing.add_sheet(name, same_as_document=pasted).views.append(
            FakeView(f"{name} front", model, name)
        )
    drawing.sheets["T030"].notes[0].PropertyLinkedText = 'MATERIAL\n$PRPSHEET:"Material Specification"'
    drawing.EditRebuild3()
    assert drawing.sheets["T030"].notes[0].GetText().endswith("C67500 manganese bronze")

    _finalize(
        FakeAdapter(drawing),
        finalize_tail,
        expected_sheet_names=("T006", "T030"),
        expected_materials={"T006": "C67500 manganese bronze", "T030": "C36000 free-machining brass"},
    )
    assert drawing.sheets["T030"].notes[0].GetText().endswith("C36000 free-machining brass")
    assert drawing.active == "T006"  # export starts from the first sheet


def test_expected_materials_hold_the_source_to_the_recipe(finalize_tail) -> None:
    drawing = FakeDrawing()
    drawing.add_sheet("T006").views.append(FakeView("T006 front", _cone_gear_model(), "T006"))
    with pytest.raises(RuntimeError, match="source Material Specification 'C67500 manganese bronze' != 'Brass'"):
        _finalize(FakeAdapter(drawing), finalize_tail, expected_materials={"T006": "Brass"})


async def _async_none(*args, **kwargs) -> dict[str, str]:
    return {}


def test_cone_gear_recipe_prints_each_sheets_configured_alloy(
    monkeypatch, tmp_path, finalize_tail
) -> None:
    """The 20-sheet package through draw_cone_gear.build and the REAL
    finalize_drawing: each sheet's MATERIAL resolves, through that sheet's own
    view, to its configuration's alloy (v37 printed "Brass" on all twenty)."""
    model = _cone_gear_model()
    drawing = FakeDrawing()
    adapter = FakeAdapter(drawing)
    source = tmp_path / "cone-gear.SLDPRT"
    source.write_bytes(b"")

    def blank_sheets(adapter, names, *, label):
        for index, name in enumerate(names):
            drawing.add_sheet(name, same_as_document=index > 0)

    def place(adapter, path, orientation, x, y, *, scale):
        view = FakeView(f"{drawing.active} {orientation}", model, "Default")
        drawing.GetCurrentSheet().views.append(view)
        return view

    def configure(adapter, configuration, views):
        for view in views:
            view.ReferencedConfiguration = configuration

    stubs = {
        "SOURCE": source,
        "check": lambda *args, **kwargs: None,
        "assert_saved_configuration_topology": _async_none,
        "read_required_properties": lambda *args, **kwargs: {},
        "new_project_drawing": lambda *args, **kwargs: (drawing, None),
        "_assert_dimension_arrow_length": lambda *args: None,
        "create_blank_drawing_sheets": blank_sheets,
        "stamp_drawing_summary": lambda *args: None,
        "place_view": place,
        "_configure_views": configure,
        "set_hidden_lines_removed": lambda *args: None,
        "_assert_tooth_geometry": lambda *args: None,
        "_assert_sheet_floor_limits": lambda *args: None,
        "_curate_repeated_dimensions": lambda *args, **kwargs: [],
        "set_dimension_callouts": lambda *args: None,
        "assert_imported_precision": lambda *args: None,
        "auto_center_marks": lambda *args, **kwargs: True,
        "add_surface_finish": lambda *args, **kwargs: None,
        "add_property_linked_note": lambda *args, **kwargs: None,
        "add_note": lambda *args, **kwargs: object(),
        "rebuild_drawing": lambda *args, **kwargs: None,
        "check_drawing_layout": lambda *args, **kwargs: None,
    }
    for name, value in stubs.items():
        monkeypatch.setattr(draw_cone_gear, name, value)
    monkeypatch.setattr(
        draw_cone_gear.hidden_sketches, "curate_view_dimensions", lambda *args, **kwargs: []
    )
    outputs = finalize_tail
    monkeypatch.setattr(draw_cone_gear, "OUTPUTS", outputs)

    asyncio.run(draw_cone_gear.build(adapter))

    printed = {
        name: sheet.notes[0].GetText().replace("\r\n", "\n") for name, sheet in drawing.sheets.items()
    }
    assert printed == {
        f"T{teeth:03d}": f"MATERIAL\n{cone_gear_spec.material_specification(teeth)}"
        for teeth in cone_gear_spec.CONFIGURATION_TEETH
    }
    assert printed["T006"].endswith("C67500 manganese bronze")
    assert printed["T030"].endswith("C36000 free-machining brass")


@pytest.mark.parametrize("teeth", cone_gear_spec.CONFIGURATION_TEETH)
def test_cone_gear_alloy_by_configuration(teeth: int) -> None:
    expected = "C67500 manganese bronze" if teeth <= 24 else "C36000 free-machining brass"
    assert cone_gear_spec.material_specification(teeth) == expected


# --- Fleet audit, offline: swing's material_audit expectation side ----------

_ASSEMBLY_LITERAL = re.compile(r'"Material Specification":\s*"([^"]+)"')


@pytest.fixture
def no_git(monkeypatch) -> None:
    # part_properties shells out to git for Generator / COPYRIGHT_YEAR, which
    # these checks never read (15 s over the fleet).
    monkeypatch.setattr(_common, "_git_sha", lambda: "test")
    monkeypatch.setattr(_common, "_git_commit_year", lambda: "2026")


def _expected_title_materials(drawing) -> list[str]:
    """What each page of ``drawing`` must print (swing's audit, offline)."""
    if drawing.source_kind == "assembly":
        script = SCRIPTS / f"build_{drawing.part}_assembly.py"
        if not script.is_file():
            script = SCRIPTS / f"build_{drawing.part}.py"
        return _ASSEMBLY_LITERAL.findall(script.read_text(encoding="utf-8"))[:1]
    if drawing.part == "cone_gear":
        return [cone_gear_spec.material_specification(t) for t in cone_gear_spec.CONFIGURATION_TEETH]
    stem = drawing.part.replace("_", "-")
    return [str(_common.part_properties(stem).get("Material Specification", ""))]


@pytest.mark.parametrize("drawing", DRAWINGS, ids=lambda drawing: drawing.name)
def test_every_drawing_has_a_title_material_to_print(drawing, no_git) -> None:
    """finalize_drawing fails a blank Material Specification, so every
    drawing's source must stamp one (part_properties for registered parts,
    the assembly build's literal, cone_gear per configuration)."""
    expected = _expected_title_materials(drawing)
    assert expected, f"{drawing.name}: no Material Specification source"
    assert all(value.strip() for value in expected), f"{drawing.name}: blank {expected!r}"


def test_the_audit_covers_the_fleet(no_git) -> None:
    assert len(DRAWINGS) >= 111
    registered = [d for d in DRAWINGS if d.source_kind == "part" and d.part != "cone_gear"]
    for drawing in registered:
        stem = drawing.part.replace("_", "-")
        assert _common.part_properties(stem)["Material Specification"] == str(
            _config.parts(stem)["material_specification"]
        )


def test_no_drawing_recipe_rebinds_the_material_cell_itself() -> None:
    # finalize_drawing owns the MATERIAL retarget; a recipe or sheet builder
    # that looked the generic link up itself would be a second copy to drift.
    offenders = []
    for path in sorted([*SCRIPTS.glob("draw_*.py"), *SCRIPTS.glob("_purchased_*.py"), *SCRIPTS.glob("_assembly_drawing.py")]):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            generic_call = (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", "") == "property_link"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "Material"
            )
            generic_literal = (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and 'PRPSHEET:"Material"' in node.value
            )
            if generic_call or generic_literal:
                offenders.append(path.name)
    assert offenders == []
