"""One package declaration, ``drawing_unit``, selects a sheet's unit (#290):
the TOL_* stamps, the drawing's and the model's document units, the tolerance
precision, and the finished-sheet proof.  SolidWorks-free: every document is a
fake that records what was written and answers what was read."""

from __future__ import annotations

import ast
import asyncio
import contextlib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import _assembly
import _assembly_contract
import _config
import _document_units
import _drawing_package_unit
import _drawing_tolerances
import _part_properties
import _part_save
import _seat_forensics
import _visibility
from _drawing_units import (
    LEGACY_DRAWING_UNIT,
    checked_drawing_unit,
    declared_drawing_unit,
    drawing_unit,
    resolved_drawing_unit,
)

# --- the declaration ----------------------------------------------------------


@pytest.mark.parametrize("value", ["mm", "in"])
def test_a_declared_unit_is_mm_or_in(value):
    assert checked_drawing_unit("parts/x", value) == value
    assert declared_drawing_unit("parts/x", {"drawing_unit": value}) == value
    assert drawing_unit("parts/x", {"drawing_unit": value}) == value


@pytest.mark.parametrize("value", ["cm", "inch", "IN", "", None, True, 25.4])
def test_any_other_declared_value_fails_closed(value):
    with pytest.raises(ValueError, match="parts/x: drawing_unit must be one of"):
        declared_drawing_unit("parts/x", {"drawing_unit": value})


def test_an_undeclared_or_unregistered_package_is_the_legacy_millimetre_sheet():
    assert declared_drawing_unit("parts/x", {"number": "MHA-CH-05"}) is None
    assert drawing_unit("parts/x", {"number": "MHA-CH-05"}) == "mm"
    assert drawing_unit("parts/x", None) == "mm"


def test_the_legacy_fallback_lives_in_one_resolver():
    assert LEGACY_DRAWING_UNIT == "mm"
    assert resolved_drawing_unit(None) == LEGACY_DRAWING_UNIT
    assert resolved_drawing_unit("in") == "in"
    assert resolved_drawing_unit("mm") == "mm"


# --- the part and assembly stamping ---------------------------------------------


def _registry(monkeypatch, rows: dict[str, dict[str, Any]]) -> None:
    real = _config.parts

    def parts(stem=None):
        if stem in rows:
            return {"number": "MHA-XX-01", **rows[stem]}
        return real(stem)

    monkeypatch.setattr(_config, "parts", parts)


def test_part_stamps_follow_their_row(monkeypatch):
    _registry(
        monkeypatch,
        {
            "probe-inch": {"drawing_unit": "in"},
            "probe-metric": {"drawing_unit": "mm"},
            "probe-legacy": {},
            "ch-vn-channel-spring-installed": {"drawing_unit": "in"},
        },
    )
    inch = _part_properties.title_block_properties(unit="in")
    metric = _part_properties.title_block_properties()
    assert _part_properties.part_drawing_unit("probe-inch") == "in"
    assert _part_properties.part_drawing_unit("probe-metric") == "mm"
    assert _part_properties.part_drawing_unit("probe-legacy") == "mm"
    assert _part_properties.part_drawing_unit("unregistered-unit-probe") == "mm"
    for name, sheet in (
        ("probe-inch", inch),
        ("probe-metric", metric),
        ("probe-legacy", metric),
        ("unregistered-unit-probe", metric),
        # A stretched spring inherits its base row's unit with its material.
        ("ch-vn-channel-spring-installed-stretch-3", inch),
    ):
        stamped = _part_properties.part_properties(name)
        assert {key: stamped[key] for key in sheet} == sheet, name


def test_a_bad_part_unit_fails_the_stamping(monkeypatch):
    _registry(monkeypatch, {"probe-bad": {"drawing_unit": "inches"}})
    with pytest.raises(ValueError, match="parts/probe-bad: drawing_unit"):
        _part_properties.part_properties("probe-bad")


def test_assembly_stamps_follow_their_contract(monkeypatch):
    real = _assembly.assembly_contract
    monkeypatch.setattr(
        _assembly,
        "assembly_contract",
        lambda stem: replace(real(stem), drawing_unit="in"),
    )
    assert _assembly.assembly_drawing_unit("pn-pen") == "in"
    stamped = _assembly.assembly_title_properties("pn-pen")
    assert stamped["TOL_LIN_XX"] == "±.01"
    assert stamped["TOL_HOLE_PLUS"] == "+.004"


def test_an_undeclared_assembly_keeps_the_millimetre_sheet():
    assert _assembly_contract.assembly_contract("pn-pen").drawing_unit is None
    assert _assembly.assembly_drawing_unit("pn-pen") == "mm"
    assert _assembly.assembly_title_properties("pn-pen")["TOL_LIN_XX"] == "±0.51"


# --- the drawing's package -------------------------------------------------------


def test_a_drawing_package_resolves_its_contract_before_any_part_row(monkeypatch):
    real = _drawing_package_unit.assembly_contract
    monkeypatch.setattr(
        _drawing_package_unit,
        "assembly_contract",
        lambda stem: replace(real(stem), drawing_unit="in"),
    )
    assert _drawing_package_unit.declared_package_drawing_unit("pn-pen") == "in"
    assert _drawing_package_unit.package_drawing_unit("pn-pen") == "in"


def test_a_drawing_package_resolves_its_part_row(monkeypatch):
    _registry(monkeypatch, {"probe-inch": {"drawing_unit": "in"}, "probe-legacy": {}})
    assert _drawing_package_unit.declared_package_drawing_unit("probe-inch") == "in"
    assert _drawing_package_unit.declared_package_drawing_unit("probe-legacy") is None
    assert _drawing_package_unit.package_drawing_unit("probe-legacy") == "mm"


def test_a_drawing_naming_no_package_is_the_legacy_sheet():
    assert _drawing_package_unit.declared_package_drawing_unit(None) is None
    assert _drawing_package_unit.package_drawing_unit(None) == "mm"


def test_an_unknown_drawing_package_is_refused():
    with pytest.raises(KeyError, match="neither a registered part nor an assembly"):
        _drawing_package_unit.package_drawing_unit("no-such-package")


# --- document units ----------------------------------------------------------------


class _Extension:
    """IModelDocExtension's integer preferences, with optional rejections and
    a forced readback (SolidWorks drifting the unit system to Custom)."""

    def __init__(self, values=None, *, reject=(), forced=None):
        self.values = dict(values or {})
        self.reject = set(reject)
        self.forced = dict(forced or {})
        self.writes: list[tuple[int, int, int]] = []

    def SetUserPreferenceInteger(self, pref, option, value):
        self.writes.append((pref, option, value))
        if pref in self.reject:
            return False
        self.values[pref] = value
        return True

    def GetUserPreferenceInteger(self, pref, option):
        assert option == 0
        return self.forced.get(pref, self.values.get(pref))


def _adapter(model):
    def attempt(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    return SimpleNamespace(currentModel=model, _attempt=attempt)


_IPS = {263: 3, 47: 3, 48: 1, 49: 3}
_MMGS = {263: 5, 47: 0, 48: 1, 49: 2}
# A model's calculation units: IPS decimal inches at the template's 8 places.
_IPS_MODEL = {263: 3, 47: 3, 48: 1, 49: 8}


def test_inch_models_are_built_ips_at_eight_places_and_read_back():
    ext = _Extension(_MMGS)
    model = SimpleNamespace(Extension=ext)
    readback = _document_units.apply_package_model_units(
        _adapter(model), "in", label="probe"
    )
    # The unit system first, then length, display, places -- all at option 0.
    assert ext.writes == [(263, 0, 3), (47, 0, 3), (48, 0, 1), (49, 0, 8)]
    assert readback == {
        "unit_system": 3,
        "linear": 3,
        "linear_display": 1,
        "linear_places": 8,
    }


def test_eight_places_keep_length_globals_inside_the_readback_budget():
    """The equation manager re-evaluates a global at the document's places
    (memory sw-globals-rounded-to-doc-decimals).  Eight inch places hold any
    value to half of 1e-8 in, inside the builders' 1e-9 m SystemValue budget;
    three moved the review's globals (CamOd 14.6, Ecc 2.0, ThinWallMin
    2.02438, DivisionSpacing 14.2 mm) off their spec."""
    places = _document_units.MODEL_INCH_DECIMALS
    assert places == 8
    half_step_mm = 0.5 * 10.0**-places * 25.4
    assert half_step_mm * 1e-3 < 1e-9
    for value_mm in (14.6, 2.0, 2.02438, 14.2):
        inches = value_mm / 25.4
        assert abs(round(inches, places) * 25.4 - value_mm) <= half_step_mm + 1e-12
        assert abs(round(inches, 3) * 25.4 - value_mm) > 1e-3


def test_a_model_that_keeps_fewer_places_is_refused():
    model = SimpleNamespace(Extension=_Extension(_MMGS, forced={49: 3}))
    with pytest.raises(RuntimeError, match="model units did not persist"):
        _document_units.apply_package_model_units(_adapter(model), "in", label="probe")


def test_millimetre_and_legacy_models_are_left_untouched():
    ext = _Extension(_MMGS)
    model = SimpleNamespace(Extension=ext)
    assert (
        _document_units.apply_package_model_units(_adapter(model), "mm", label="p")
        is None
    )
    assert ext.writes == []


def test_a_rejected_model_unit_write_raises():
    model = SimpleNamespace(Extension=_Extension(_MMGS, reject={47}))
    with pytest.raises(RuntimeError, match="model unit linear .pref 47. = 3 rejected"):
        _document_units.apply_package_model_units(_adapter(model), "in", label="probe")


def test_a_unit_system_that_drifts_to_custom_raises():
    model = SimpleNamespace(Extension=_Extension(_MMGS, forced={263: 4}))
    with pytest.raises(RuntimeError, match="model units did not persist"):
        _document_units.apply_package_model_units(_adapter(model), "in", label="probe")


def test_an_unreadable_unit_is_no_proof():
    model = SimpleNamespace(Extension=_Extension({263: 3, 47: 3, 48: 1}))
    with pytest.raises(RuntimeError, match="linear_places .pref 49. read None"):
        _document_units.read_document_units(model)


def test_a_save_proves_already_selected_units_without_writing():
    ext = _Extension(_IPS_MODEL)
    readback = _document_units.require_package_model_units(
        _adapter(SimpleNamespace(Extension=ext)), "in", label="probe"
    )
    assert readback["linear_places"] == 8
    assert ext.writes == []


@pytest.mark.parametrize(
    "values",
    [_MMGS, {**_IPS_MODEL, 49: 3}, {**_IPS_MODEL, 263: 4}],
    ids=["never-selected", "three-places", "custom-system"],
)
def test_a_save_refuses_units_its_build_did_not_select_first(values):
    ext = _Extension(values)
    with pytest.raises(RuntimeError, match="right after create_part/create_assembly"):
        _document_units.require_package_model_units(
            _adapter(SimpleNamespace(Extension=ext)), "in", label="probe"
        )
    assert ext.writes == []


def test_a_millimetre_save_reads_no_model_units():
    # A model with no extension at all: an mm package keeps its template units.
    assert (
        _document_units.require_package_model_units(
            _adapter(SimpleNamespace()), "mm", label="p"
        )
        is None
    )


def _part_save_seat(monkeypatch, tmp_path, model):
    """Run ``save_part_and_images`` with every non-unit step stubbed; returns
    the adapter and the paths it saved."""
    saves: list[str] = []

    async def save_file(path):
        saves.append(path)
        return SimpleNamespace(is_success=True, data=None, error=None)

    async def no_stl(*_args):
        return None

    adapter = _adapter(model)
    adapter.save_file = save_file
    monkeypatch.setattr(_seat_forensics, "record_authoring_context", lambda *_a: None)
    monkeypatch.setattr(
        _visibility, "assert_reference_geometry_hidden", lambda *_a: None
    )
    for name in ("OUT_SLDPRT", "OUT_PNG", "OUT_STL"):
        monkeypatch.setattr(_part_save, name, tmp_path / name)
    for name in (
        "set_isometric_view",
        "apply_block_tolerances",
        "apply_custom_properties",
        "apply_summary_info",
        "rebuild_stale_configurations",
    ):
        monkeypatch.setattr(_part_save, name, lambda *_a, **_kw: None)
    monkeypatch.setattr(_part_save, "part_properties", lambda _name: {"Title": "probe"})
    monkeypatch.setattr(_part_save, "export_part_stl", no_stl)
    return adapter, saves


def test_an_inch_part_save_proves_units_and_never_switches_them(monkeypatch, tmp_path):
    ext = _Extension(_IPS_MODEL)
    adapter, saves = _part_save_seat(
        monkeypatch, tmp_path, SimpleNamespace(Extension=ext)
    )
    asyncio.run(_part_save.save_part_and_images(adapter, "dt-pinion-cam", ()))
    assert len(saves) == 2  # the first save and the re-save with properties
    assert ext.writes == []


def test_an_inch_part_built_without_early_units_is_refused_before_its_first_save(
    monkeypatch, tmp_path
):
    ext = _Extension({**_IPS_MODEL, 49: 3})
    adapter, saves = _part_save_seat(
        monkeypatch, tmp_path, SimpleNamespace(Extension=ext)
    )
    with pytest.raises(RuntimeError, match="never at save"):
        asyncio.run(_part_save.save_part_and_images(adapter, "dt-pinion-cam", ()))
    assert saves == []
    assert ext.writes == []


def test_a_millimetre_part_save_reads_no_model_units(monkeypatch, tmp_path):
    adapter, saves = _part_save_seat(monkeypatch, tmp_path, SimpleNamespace())
    asyncio.run(_part_save.save_part_and_images(adapter, "dt-crank-arm", ()))
    assert len(saves) == 2


_SCRIPTS = Path(__file__).resolve().parent


def _statements_around_create(path: Path, function: str, create: str):
    """``function``'s statements before its ``adapter.<create>()`` call, and
    the one right after it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    body = next(
        node.body
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == function
    )
    texts = [ast.unparse(statement) for statement in body]
    created = next(
        i for i, text in enumerate(texts) if f"await adapter.{create}()" in text
    )
    return texts[:created], texts[created + 1]


def _module_constant(path: Path, name: str) -> object:
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
            and isinstance(node.value, ast.Constant)
        ):
            return node.value.value
    return None


def _inch_packages() -> tuple[list[str], list[str]]:
    parts = sorted(
        stem
        for stem in _config.parts()
        if _part_properties.part_drawing_unit(stem) == "in"
    )
    assemblies = sorted(
        path.stem
        for path in _assembly_contract.contract_files()
        if _assembly.assembly_drawing_unit(path.stem) == "in"
    )
    return parts, assemblies


def test_every_inch_package_selects_its_units_before_any_geometry():
    """The model's calculation units are selected once, by the statement right
    after the document is created -- before any global, sketch, feature or
    check -- from the package's own declaration.  The save chokepoints only
    prove them, so a converted package that skipped this fails at save."""
    parts, assemblies = _inch_packages()
    assert parts and assemblies  # the pilot's declarations are visible
    stock = 0
    for stem in parts:
        path = _SCRIPTS / f"build_{stem.replace('-', '_')}.py"
        source = path.read_text(encoding="utf-8")
        if "build_stock_fastener(" in source:
            # The shared stock builder owns create_part (checked below).
            stock += 1
            continue
        assert _module_constant(path, "PART_NAME") == stem, path.name
        before, after = _statements_around_create(path, "build", "create_part")
        assert after == (
            "apply_package_model_units(adapter, part_drawing_unit(PART_NAME), "
            "label=PART_NAME)"
        ), path.name
        assert not any(
            "set_global" in text or "create_sketch" in text for text in before
        )
    for stem in assemblies:
        path = _SCRIPTS / f"build_{stem.replace('-', '_')}_assembly.py"
        assert _module_constant(path, "ASM_NAME") == stem, path.name
        before, after = _statements_around_create(path, "build", "create_assembly")
        assert after == (
            "apply_package_model_units(adapter, assembly_drawing_unit(ASM_NAME), "
            "label=ASM_NAME)"
        ), path.name
        assert not any("place" in text or "set_global" in text for text in before)
    assert stock  # the purchased inch screw goes through the stock builder
    _before, after = _statements_around_create(
        _SCRIPTS / "_stock_fastener.py", "build_stock_fastener", "create_part"
    )
    assert after == (
        "apply_package_model_units(adapter, part_drawing_unit(part_name), label=part_name)"
    )


@pytest.mark.parametrize(
    "path",
    [_SCRIPTS / "_part_save.py", _SCRIPTS / "_assembly.py"],
    ids=lambda p: p.name,
)
def test_no_save_chokepoint_selects_model_units(path):
    """A unit switch after the checks would re-evaluate checked globals and
    publish geometry no check saw; the chokepoints only prove the readback."""
    source = path.read_text(encoding="utf-8")
    assert "apply_package_model_units" not in source
    assert "require_package_model_units(adapter" in source


# --- the finished-sheet proof --------------------------------------------------------


class _Note:
    def __init__(self, linked, resolved):
        self.PropertyLinkedText = linked
        self._resolved = resolved

    def GetText(self):
        return self._resolved


class _Annotation:
    def __init__(self, note, kind=6):
        self._note, self._kind = note, kind

    def GetType(self):
        return self._kind

    def GetSpecificAnnotation(self):
        return self._note


def _drawing(document_units, notes):
    sheet_view = SimpleNamespace(
        GetAnnotations=lambda: [_Annotation(note) for note in notes]
    )
    return SimpleNamespace(
        Extension=_Extension(document_units), GetFirstView=lambda: sheet_view
    )


_UNIT_LINK = '$PRP:"UnitOfMeasure"'


@pytest.fixture
def unbound(monkeypatch):
    monkeypatch.setattr(
        _drawing_package_unit, "_early_bound", lambda value, _type: value
    )


def _prove(draw, model, unit, linked):
    return _drawing_package_unit.assert_sheet_prints_unit(
        draw,
        package_name="probe",
        unit=unit,
        sheet_name="Sheet1",
        linked_model=model,
        linked_properties=linked,
    )


def test_an_inch_sheet_proves_document_unit_cell_rows_and_model(unbound):
    draw = _drawing(_IPS, [_Note(_UNIT_LINK, "in"), _Note("SCALE", "SCALE")])
    model = SimpleNamespace(Extension=_Extension(_IPS_MODEL))
    rows = _part_properties.title_block_properties(unit="in")
    proof = _prove(draw, model, "in", rows)
    assert proof["unit_cell"] == "in"
    assert proof["document"]["unit_system"] == proof["model"]["unit_system"] == 3
    # The sheet prints .XXX; the model it links keeps its 8 calculation places.
    assert (proof["document"]["linear_places"], proof["model"]["linear_places"]) == (
        3,
        8,
    )
    assert proof["tolerance_rows"]["TOL_LIN_XX"] == "±.01"


def test_a_millimetre_sheet_proof_reads_no_model_units(unbound):
    draw = _drawing(_MMGS, [_Note(f"UNIT {_UNIT_LINK}", "UNIT mm")])
    model = SimpleNamespace()  # an mm model keeps its template units
    proof = _prove(draw, model, "mm", _part_properties.title_block_properties())
    assert proof["model"] == {} and proof["unit_cell"] == "UNIT mm"


@pytest.mark.parametrize(
    ("document", "cell", "model", "rows", "match"),
    [
        (_MMGS, "in", _IPS_MODEL, "in", "drawing document units"),
        (_IPS, "mm", _IPS_MODEL, "in", "UNIT cell reads"),
        (_IPS, "in", _MMGS, "in", "linked model units"),
        # A model rounded to the sheet's 3 print places lost its calculation places.
        (_IPS, "in", _IPS, "in", "linked model units"),
        (_IPS, "in", _IPS_MODEL, "mm", "linked TOL_. rows"),
    ],
)
def test_an_inch_sheet_that_prints_anything_millimetre_fails(
    unbound, document, cell, model, rows, match
):
    draw = _drawing(document, [_Note(_UNIT_LINK, cell)])
    linked_model = SimpleNamespace(Extension=_Extension(model))
    linked = _part_properties.title_block_properties(unit=rows)
    with pytest.raises(RuntimeError, match=match):
        _prove(draw, linked_model, "in", linked)


def test_the_unit_cell_must_be_linked_exactly_once(unbound):
    rows = _part_properties.title_block_properties(unit="in")
    model = SimpleNamespace(Extension=_Extension(_IPS_MODEL))
    with pytest.raises(RuntimeError, match="0 notes link"):
        _prove(_drawing(_IPS, []), model, "in", rows)
    twice = [_Note(_UNIT_LINK, "in"), _Note(_UNIT_LINK, "in")]
    with pytest.raises(RuntimeError, match="2 notes link"):
        _prove(_drawing(_IPS, twice), model, "in", rows)


@pytest.mark.parametrize(
    ("linked", "resolved"),
    [
        (f"UNIT\n{_UNIT_LINK}", "UNIT\r\nin"),  # INote.GetText returns CRLF
        (f"UNIT\r\n{_UNIT_LINK}", "UNIT\nin"),
        (f"UNIT\r\n{_UNIT_LINK}", "UNIT\r\nin"),
    ],
)
def test_a_multi_line_unit_cell_compares_across_line_endings(unbound, linked, resolved):
    rows = _part_properties.title_block_properties(unit="in")
    model = SimpleNamespace(Extension=_Extension(_IPS_MODEL))
    proof = _prove(_drawing(_IPS, [_Note(linked, resolved)]), model, "in", rows)
    assert proof["unit_cell"] == "UNIT\nin"


@pytest.mark.parametrize(
    "resolved",
    ["UNIT\r\nmm", "UNIT in", "UNITin", "UNIT\r\n\r\nin", "UNIT\r\nin ", "unit\r\nin"],
)
def test_a_multi_line_unit_cell_still_compares_every_other_character(unbound, resolved):
    # Only the break encoding is normalized: a wrong unit, a lost or extra
    # break, whitespace or case still fails.
    rows = _part_properties.title_block_properties(unit="in")
    model = SimpleNamespace(Extension=_Extension(_IPS_MODEL))
    draw = _drawing(_IPS, [_Note(f"UNIT\n{_UNIT_LINK}", resolved)])
    with pytest.raises(RuntimeError, match="UNIT cell reads"):
        _prove(draw, model, "in", rows)


def test_an_inch_stamped_model_is_recognised_whatever_the_drawing_declares():
    assert _drawing_package_unit.carries_inch_rows(
        _part_properties.title_block_properties(unit="in")
    )
    assert not _drawing_package_unit.carries_inch_rows(
        _part_properties.title_block_properties()
    )


def test_each_sheet_is_proved_in_its_package_unit_or_its_inch_model():
    inch = _part_properties.title_block_properties(unit="in")
    metric = _part_properties.title_block_properties()
    proof = _drawing_package_unit.sheet_proof_unit
    # A declared package proves every sheet in its unit, whatever it links: an
    # inch package linking a mm-stamped model then fails the TOL_* readback.
    assert proof("in", metric) == "in"
    assert proof("mm", inch) == "mm"
    # An undeclared sheet linking an inch-stamped model is never skipped.
    assert proof(None, inch) == "in"
    assert proof(None, metric) is None


def test_one_document_unit_requires_every_sheet_to_agree():
    agree = _drawing_package_unit.document_proof_unit
    assert agree({}) is None
    assert agree({"A": None, "B": None}) is None
    assert agree({"A": "in", "B": "in"}) == "in"
    assert agree({"A": "mm"}) == "mm"
    # An inch sheet beside a legacy one, or two proved units, is one document
    # printing two units: refused rather than proved by the last sheet alone.
    mixed = ({"A": "in", "B": None}, {"A": None, "B": "in"}, {"A": "in", "B": "mm"})
    for sheets in mixed:
        with pytest.raises(RuntimeError, match="sheets disagree on the unit"):
            agree(sheets)


def test_the_open_document_is_reread_after_save():
    draw = SimpleNamespace(Extension=_Extension(_IPS))
    assert (
        _drawing_package_unit.assert_document_units_after_save(
            draw, package_name="probe", unit="in"
        )["unit_system"]
        == 3
    )
    drifted = SimpleNamespace(Extension=_Extension(_IPS, forced={263: 4}))
    with pytest.raises(RuntimeError, match="after save"):
        _drawing_package_unit.assert_document_units_after_save(
            drifted, package_name="probe", unit="in"
        )


class _SavedApp:
    """ISldWorks over one saved SLDDRW: OpenDoc6 loads it, CloseDoc unloads
    it; ``on_close`` may tamper with the file to prove the hash gate."""

    def __init__(self, path, *, unit="in", opened_path=None, on_close=None):
        rows = _part_properties.title_block_properties(unit=unit)
        units = _IPS if unit == "in" else _MMGS
        linked = SimpleNamespace(
            Extension=_Extension(_IPS_MODEL if unit == "in" else _MMGS),
            GetCustomInfoValue=lambda _config_name, name: rows[name],
        )
        view = SimpleNamespace(
            GetName2=lambda: "Drawing View1",
            ReferencedDocument=linked,
            GetNextView=lambda: None,
        )
        sheet_view = SimpleNamespace(
            GetAnnotations=lambda: [_Annotation(_Note(_UNIT_LINK, unit))],
            GetNextView=lambda: view,
        )
        sheet = SimpleNamespace(CustomPropertyView="Drawing View1")
        self.model = SimpleNamespace(
            Extension=_Extension(units),
            GetPathName=lambda: str(opened_path or path),
            GetType=lambda: 3,
            GetTitle=lambda: path.name,
            GetSheetNames=lambda: ("Sheet1",),
            ActivateSheet=lambda _name: True,
            GetCurrentSheet=lambda: sheet,
            GetFirstView=lambda: sheet_view,
        )
        self.path, self.loaded, self.on_close = path, False, on_close
        self.opens: list[tuple] = []
        # The session's open documents other than this one (GetDocuments).
        self.documents: list[Any] = []

    def GetDocuments(self):
        return tuple(self.documents)

    def IsSame(self, left, right):
        return 1 if left is right else 0  # swObjectSame / swObjectNotSame

    def GetOpenDocumentByName(self, name):
        return self.model if self.loaded and name == str(self.path) else None

    def OpenDoc6(self, name, kind, options, configuration, errors, warnings):
        self.opens.append((name, kind, options, configuration))
        self.loaded = True
        return self.model, 0, 0

    def CloseDoc(self, title):
        assert title == self.path.name
        self.loaded = False
        if self.on_close is not None:
            self.on_close()


def _saved(tmp_path, **kwargs):
    path = (tmp_path / "probe.SLDDRW").resolve()
    path.write_bytes(b"saved drawing bytes")
    app = _SavedApp(path, **kwargs)
    previous = object()
    app.documents.append(previous)  # a live document the session still holds
    return path, app, SimpleNamespace(swApp=app, currentModel=previous), previous


@pytest.mark.parametrize("unit", ["in", "mm"])
def test_the_saved_drawing_is_reopened_read_only_and_proved(tmp_path, unbound, unit):
    path, app, adapter, previous = _saved(tmp_path, unit=unit)
    proofs = _drawing_package_unit.prove_saved_drawing_units(
        adapter, path, package_name="probe", unit=unit
    )
    # Drawing, silent | read-only; closed unsaved; the session's model restored.
    assert app.opens == [(str(path), 3, 3, "")]
    assert not app.loaded and adapter.currentModel is previous
    assert [proof["unit_cell"] for proof in proofs] == [unit]
    assert path.read_bytes() == b"saved drawing bytes"


def test_the_saved_proof_refuses_a_still_open_drawing(tmp_path, unbound):
    path, app, adapter, _previous = _saved(tmp_path)
    app.loaded = True
    with pytest.raises(RuntimeError, match="before its saved proof"):
        _drawing_package_unit.prove_saved_drawing_units(
            adapter, path, package_name="probe", unit="in"
        )
    assert app.opens == []


def test_the_saved_proof_fails_a_millimetre_file_and_still_closes_it(tmp_path, unbound):
    path, app, adapter, previous = _saved(tmp_path, unit="mm")
    with pytest.raises(RuntimeError, match="does not print 'in'"):
        _drawing_package_unit.prove_saved_drawing_units(
            adapter, path, package_name="probe", unit="in"
        )
    assert not app.loaded and adapter.currentModel is previous


def test_the_saved_proof_refuses_another_document(tmp_path, unbound):
    other = tmp_path / "other.SLDDRW"
    path, app, adapter, _previous = _saved(tmp_path, opened_path=other)
    with pytest.raises(RuntimeError, match="saved reader acquired"):
        _drawing_package_unit.prove_saved_drawing_units(
            adapter, path, package_name="probe", unit="in"
        )
    assert not app.loaded


def test_the_saved_proof_fails_if_the_file_bytes_change(tmp_path, unbound):
    path = (tmp_path / "probe.SLDDRW").resolve()
    path.write_bytes(b"saved drawing bytes")
    app = _SavedApp(path, on_close=lambda: path.write_bytes(b"rewritten"))
    adapter = SimpleNamespace(swApp=app, currentModel=None)
    with pytest.raises(RuntimeError, match="changed probe.SLDDRW's bytes"):
        _drawing_package_unit.prove_saved_drawing_units(
            adapter, path, package_name="probe", unit="in"
        )


@pytest.mark.parametrize("saved_unit", ["in", "mm"])
def test_a_closed_current_model_is_cleared_not_restored(tmp_path, unbound, saved_unit):
    # finalize_drawing closes its drawing before the proof; a handle the
    # session no longer has open must not come back as the current model,
    # whether the proof passes or fails.
    path, app, adapter, closed = _saved(tmp_path, unit=saved_unit)
    app.documents.remove(closed)
    failure = (
        pytest.raises(RuntimeError, match="does not print 'in'")
        if saved_unit == "mm"
        else contextlib.nullcontext()
    )
    with failure:
        _drawing_package_unit.prove_saved_drawing_units(
            adapter, path, package_name="probe", unit="in"
        )
    assert not app.loaded and adapter.currentModel is None


def test_the_live_model_is_restored_even_when_the_close_raises(tmp_path, unbound):
    path, app, adapter, previous = _saved(tmp_path)

    def fail():
        raise RuntimeError("close failed")

    app.on_close = fail
    with pytest.raises(RuntimeError, match="close failed"):
        _drawing_package_unit.prove_saved_drawing_units(
            adapter, path, package_name="probe", unit="in"
        )
    assert adapter.currentModel is previous


# --- tolerance precision in the sheet's unit -------------------------------------------


class _Tolerance:
    Type = 0

    def SetValues(self, minimum, maximum):
        self.minimum, self.maximum = minimum, maximum
        return True

    def GetMinValue(self):
        return self.minimum

    def GetMaxValue(self):
        return self.maximum


class _Display:
    tolerance_precision = 2

    def SetPrecision3(self, _primary, _dual, primary_tol, _dual_tol):
        self.tolerance_precision = primary_tol
        return 0

    def GetPrimaryTolPrecision2(self):
        return self.tolerance_precision


@pytest.fixture
def dimension(monkeypatch):
    display = _Display()
    dim = SimpleNamespace(Tolerance=_Tolerance())
    monkeypatch.setattr(
        _drawing_tolerances, "_named_dimension", lambda *_a: (display, dim)
    )
    monkeypatch.setattr(_drawing_tolerances, "_early_bound", lambda value, _type: value)
    return display, dim


def test_symmetric_inch_tolerance_counts_inch_places(dimension):
    display, dim = dimension
    # ±.01 in (0.254 mm) prints at 2 inch places but needs 3 mm places.
    _drawing_tolerances.set_dimension_symmetric_tolerance(
        object(), "F", "D", 0.254, display_unit="in"
    )
    assert display.tolerance_precision == 2
    assert dim.Tolerance.minimum == pytest.approx(-0.000254)
    assert dim.Tolerance.maximum == pytest.approx(0.000254)
    _drawing_tolerances.set_dimension_symmetric_tolerance(object(), "F", "D", 0.254)
    assert display.tolerance_precision == 3


def test_symmetric_tolerance_prints_at_the_nominals_places(dimension):
    display, _dim = dimension
    # .0787 ±.0020: the band needs 3 inch places, the nominal shows 4.
    _drawing_tolerances.set_dimension_symmetric_tolerance(
        object(), "F", "D", 0.0508, places=4, display_unit="in"
    )
    assert display.tolerance_precision == 4
    with pytest.raises(ValueError, match="2 tolerance places would round"):
        _drawing_tolerances.set_dimension_symmetric_tolerance(
            object(), "F", "D", 0.0508, places=2, display_unit="in"
        )


def test_bilateral_inch_tolerance_counts_inch_places(dimension):
    display, _dim = dimension
    # The drilled-hole row, +.004/0 in.
    _drawing_tolerances.set_dimension_bilateral_tolerance(
        object(), "F", "D", 0.0, 0.1016, display_unit="in"
    )
    assert display.tolerance_precision == 3


def test_a_band_with_no_exact_inch_print_is_refused(dimension):
    # 0.02 mm is 0.000787... in: no 0-8 place inch print shows it.
    with pytest.raises(ValueError, match="more than 8 decimal places"):
        _drawing_tolerances.set_dimension_symmetric_tolerance(
            object(), "F", "D", 0.02, display_unit="in"
        )


@pytest.mark.parametrize("unit", ["deg", "cm"])
def test_a_length_tolerance_prints_only_in_mm_or_inches(dimension, unit):
    with pytest.raises(ValueError, match="drawing_unit must be one of"):
        _drawing_tolerances.set_dimension_bilateral_tolerance(
            object(), "F", "D", -0.1, 0.1, display_unit=unit
        )
