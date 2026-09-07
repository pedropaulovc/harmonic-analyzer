"""COM-free prepared-template identity, ownership and explicit opt-in contracts."""

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_common as common
import _drawing_prepared_template as prepared
import _drawing_template_defaults as defaults
from test_template_defaults_drawing import blank_note  # noqa: F401


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setenv("HARMONIC_COM_SEAT", "unit-test")
    inputs = {"template": "original", "helper": "recipe", "revision": "34.3"}
    calls = []

    def identity(adapter, spec):
        return {**inputs, "scale": list(spec.scale), "decimals": spec.decimals}

    async def native(adapter, spec, directory, receipt, scope):
        calls.append(directory)
        (directory / "prepared.DRWDOT").write_bytes(b"native derived template")
        receipt.update(before={"units": 4}, after={"units": 4})

    monkeypatch.setattr(prepared, "preparation_inputs", identity)
    monkeypatch.setattr(prepared, "_prepare_native", native)
    return SimpleNamespace(root=tmp_path, adapter=object(), inputs=inputs, calls=calls)


def access(cache, **kwargs):
    return asyncio.run(
        prepared.prepare_project_drawing_template(
            cache.adapter,
            cache_root=cache.root,
            **kwargs,
        )
    )


def test_first_access_prepares_once_then_hits_without_native_work(cache):
    first, second = access(cache), access(cache)
    assert first == second
    assert len(cache.calls) == 1
    assert first.path.read_bytes() == b"native derived template"
    receipt = json.loads((first.directory / "receipt.json").read_text())
    assert receipt["inputs_after"] == receipt["inputs"]


@pytest.mark.parametrize("field", ["template", "helper", "revision"])
def test_actual_changed_input_requires_a_different_entry(cache, field):
    before = access(cache)
    cache.inputs[field] += " changed"
    after = access(cache)
    assert before.key != after.key
    assert len(cache.calls) == 2
    assert before.path.is_file()


@pytest.mark.parametrize("spec", [{"scale": (2, 1)}, {"decimals": 3}])
def test_scale_and_precision_are_cache_inputs(cache, spec):
    assert access(cache).key != access(cache, **spec).key


@pytest.mark.parametrize(
    "damage", ["bytes", "missing", "manifest", "receipt", "receipt_inputs"]
)
def test_corruption_is_loud_never_reprepared_or_fallback(cache, damage):
    entry = access(cache)
    if damage == "bytes":
        entry.path.write_bytes(b"different")
    if damage == "missing":
        entry.path.unlink()
    if damage == "manifest":
        (entry.directory / "manifest.json").write_text("{}")
    if damage == "receipt":
        (entry.directory / "receipt.json").write_text("{}")
    if damage == "receipt_inputs":
        path = entry.directory / "receipt.json"
        receipt = json.loads(path.read_text())
        receipt["inputs"] = {"wrong": "inputs"}
        path.write_text(json.dumps(receipt))
        manifest_path = entry.directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["receipt_sha256"] = prepared._sha(path)
        manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="invalid prepared template"):
        access(cache)
    assert len(cache.calls) == 1


def test_failure_retains_evidence_and_never_publishes(cache, monkeypatch):
    async def fail(adapter, spec, directory, receipt, scope):
        (directory / "prepared.DRWDOT").write_bytes(b"partial")
        receipt["native_failure"] = "exact rejection"
        raise RuntimeError("native rejection")

    monkeypatch.setattr(prepared, "_prepare_native", fail)
    with pytest.raises(RuntimeError, match="native rejection"):
        access(cache)
    stages = list(cache.root.iterdir())
    assert len(stages) == 1 and stages[0].name.startswith("pending-")
    receipt = json.loads((stages[0] / "receipt.json").read_text())
    assert receipt["native_failure"] == "exact rejection"
    assert receipt["status"] == "failed"
    assert not (stages[0] / "manifest.json").exists()


def test_changed_inputs_during_preparation_are_not_published(cache, monkeypatch):
    original = prepared._prepare_native

    async def mutate(*args):
        await original(*args)
        cache.inputs["template"] = "changed during native preparation"

    monkeypatch.setattr(prepared, "_prepare_native", mutate)
    with pytest.raises(RuntimeError, match="inputs changed"):
        access(cache)
    assert not list(cache.root.glob("*/manifest.json"))


def test_seat_required_even_for_hit(cache, monkeypatch):
    access(cache)
    monkeypatch.delenv("HARMONIC_COM_SEAT")
    with pytest.raises(RuntimeError, match="machine-global COM seat"):
        access(cache)


@pytest.mark.parametrize(
    "scale,decimals",
    [((0, 1), 2), ((1, float("nan")), 2), ((True, 1), 2), ((1, 1), True), ((1, 1), 4)],
)
def test_invalid_spec_rejected(scale, decimals):
    with pytest.raises(ValueError):
        prepared.TemplateSpec(scale, decimals)


def test_current_setup_does_not_import_prepared_or_native_bounds():
    from _buildgraph import module_deps_of

    closure = {Path(path).name for path in module_deps_of(Path(common.__file__))}
    assert "_drawing_prepared_template.py" not in closure
    assert "_drawing_template_defaults.py" not in closure
    assert "_drawing_annotation_bounds.py" not in closure


def test_raw_comparison_does_not_round_font_or_coordinates():
    before = {"sheet_notes": [{"font": "Century Gothic", "anchor": [0.1, 0.2]}]}
    after = deepcopy(before)
    after["sheet_notes"][0]["anchor"][0] += 1e-12
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(before, after)
    after = deepcopy(before)
    after["sheet_notes"][0]["font"] = "Arial"
    with pytest.raises(RuntimeError):
        defaults.compare_defaults(before, after)


def test_only_proven_zero_ink_extent_observations_are_excluded():
    before = {
        "sheet_notes": [{"zero_ink": {"native_counts": {"Text": 0}}}],
        "blank_linked_extent_observations": [1],
    }
    after = deepcopy(before)
    after["blank_linked_extent_observations"] = [2]
    defaults.compare_defaults(before, after)
    after["sheet_notes"][0]["zero_ink"]["native_counts"]["Text"] = 1
    with pytest.raises(RuntimeError):
        defaults.compare_defaults(before, after)


class Model:
    def __init__(self, title, path="", kind=3):
        self.title, self.path, self.kind = title, str(path), kind
        self.Visible = True
        self.dirty = False
        self.calls = []

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return self.path

    def GetType(self):
        return self.kind

    def GetSaveFlag(self):
        return self.dirty

    def ClearSelection2(self, value):
        self.calls.append(("clear", value))

    def SaveAs3(self, path, version, options):
        self.calls.append(("save", path, version, options))
        Path(path).write_bytes(b"native prepared")
        self.path = path
        return 0

    def EditSheet(self):
        self.calls.append("edit_sheet")

    def ViewZoomtofit2(self):
        self.calls.append("fit")


@pytest.fixture
def native(monkeypatch, tmp_path):
    source_path = tmp_path / "source.SLDPRT"
    source_path.write_bytes(b"source unchanged")
    source = Model("source.SLDPRT", source_path, 1)
    documents, closed, created, scopes = [source], [], [], []
    app = SimpleNamespace(
        ActiveDoc=source,
        GetDocuments=lambda: tuple(documents),
        IsSame=lambda a, b: 1 if a is b else 0,
    )
    adapter = SimpleNamespace(swApp=app, currentModel=source)

    def activate(title, user, option, error):
        assert (user, option, error) == (False, 1, 0)
        target = next(doc for doc in documents if doc.title == title)
        app.ActiveDoc = target
        return target, 2

    app.ActivateDoc3 = activate

    def create(adapter, **kwargs):
        model = Model(f"Draw{len(created)}")
        documents.append(model)
        created.append(model)
        adapter.currentModel = app.ActiveDoc = model
        return model

    async def close(save):
        assert save is False
        model = adapter.currentModel
        documents.remove(model)
        closed.append(model)
        adapter.currentModel = None
        app.ActiveDoc = None
        return SimpleNamespace(status="success")

    adapter.close_model = close

    @contextmanager
    def context(kind, path):
        scopes.append((kind, path))
        yield

    monkeypatch.setattr(
        common, "new_project_drawing", lambda a, **k: (create(a, **k), object())
    )
    monkeypatch.setattr(common, "new_drawing", create)
    monkeypatch.setattr(prepared, "check", lambda label, result: result)
    monkeypatch.setattr(prepared, "snapshot_defaults", lambda a, s: {"units": 4})
    directory = tmp_path / "stage"
    directory.mkdir()
    return SimpleNamespace(
        adapter=adapter,
        source=source,
        documents=documents,
        created=created,
        closed=closed,
        scopes=scopes,
        context=context,
        directory=directory,
    )


def run_native(native, receipt=None):
    receipt = {} if receipt is None else receipt
    asyncio.run(
        prepared._prepare_native(
            native.adapter,
            prepared.TemplateSpec(),
            native.directory,
            receipt,
            native.context,
        )
    )
    return receipt


def test_native_preparation_preserves_source_and_uses_exact_owned_scopes(native):
    receipt = run_native(native)
    assert native.documents == [native.source]
    assert native.adapter.currentModel is native.source
    assert native.adapter.swApp.ActiveDoc is native.source
    assert native.closed == native.created and len(native.closed) == 2
    assert [kind for kind, _ in native.scopes] == [
        prepared.TemplateOperation.CREATE,
        prepared.TemplateOperation.SAVE_AS,
        prepared.TemplateOperation.CREATE,
    ]
    assert native.created[0].calls[:2] == [
        ("clear", True),
        ("save", str(native.directory / "prepared.DRWDOT"), 0, 0),
    ]
    assert receipt["baseline_preserved"] == "exact_native_handles_and_state"


def test_hidden_source_is_rejected_before_creating_or_closing(native):
    native.source.Visible = False
    with pytest.raises(RuntimeError, match="hidden documents"):
        run_native(native)
    assert native.created == native.closed == []


def test_failed_defaults_closes_only_its_owned_drawing_and_restores_source(
    native, monkeypatch
):
    def fail(*args):
        raise RuntimeError("defaults mismatch")

    monkeypatch.setattr(prepared, "snapshot_defaults", fail)
    with pytest.raises(ExceptionGroup, match="native operation"):
        run_native(native)
    assert native.closed == native.created and len(native.closed) == 1
    assert native.adapter.currentModel is native.source


def test_setup_failure_after_newdocument_still_claims_exact_created_handle(
    native, monkeypatch
):
    original = common.new_project_drawing

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("style setter failed")

    monkeypatch.setattr(common, "new_project_drawing", fail)
    with pytest.raises(ExceptionGroup):
        run_native(native)
    assert len(native.closed) == 1
    assert native.adapter.currentModel is native.source


def test_source_mutation_prevents_close_and_retains_cleanup_failure(
    native, monkeypatch
):
    def mutate(*args):
        native.source.dirty = True
        return {"units": 4}

    monkeypatch.setattr(prepared, "snapshot_defaults", mutate)
    receipt = {}
    with pytest.raises(ExceptionGroup):
        run_native(native, receipt)
    assert not native.closed
    assert "pre-existing document" in receipt["cleanup_error"]


def test_actual_fingerprint_contains_preparation_and_adapter_closure(monkeypatch):
    app = SimpleNamespace(RevisionNumber=lambda: "34.3.0")
    first = prepared.preparation_inputs(
        SimpleNamespace(swApp=app), prepared.TemplateSpec()
    )
    sources = first["source_sha256"]
    for required in (
        "cad/scripts/_drawing_common.py",
        "cad/scripts/_drawing_prepared_template.py",
        "cad/scripts/_drawing_template_defaults.py",
        "cad/scripts/_drawing_annotation_bounds.py",
        "cad/scripts/_drawing_view_packing.py",
        "uv.lock",
        "SolidworksMCP-python/src/solidworks_mcp/adapters/solidworks/drawing.py",
    ):
        assert required in sources
    assert first["solidworks_revision"] == "34.3.0"


@pytest.mark.parametrize(
    "helper",
    [
        "_drawing_prepared_template.py",
        "_drawing_template_defaults.py",
        "_drawing_annotation_bounds.py",
        "_drawing_view_packing.py",
    ],
)
def test_each_preparation_helper_byte_change_changes_actual_key(
    monkeypatch, tmp_path, helper
):
    """Actual closure/key code; mutate an owned byte-copy, never checkout inputs."""
    original = Path(prepared.__file__).parent / helper
    copied = tmp_path / helper
    copied.write_bytes(original.read_bytes())
    real_sha = prepared._sha
    monkeypatch.setattr(
        prepared,
        "_sha",
        lambda path: real_sha(
            copied if Path(path).resolve() == original.resolve() else path
        ),
    )
    adapter = SimpleNamespace(swApp=SimpleNamespace(RevisionNumber=lambda: "34.3.0"))
    spec = prepared.TemplateSpec()
    before = prepared.preparation_inputs(adapter, spec)
    copied.write_bytes(copied.read_bytes() + b"\n# owned test input mutation\n")
    after = prepared.preparation_inputs(adapter, spec)
    changed = {
        name
        for name, digest in before["source_sha256"].items()
        if digest != after["source_sha256"][name]
    }
    assert changed == {f"cad/scripts/{helper}"}
    assert prepared._key(before) != prepared._key(after)
    assert real_sha(original) == before["source_sha256"][f"cad/scripts/{helper}"]


def test_inherited_path_verifies_bytes_before_native_and_omits_setters(
    cache, monkeypatch
):
    entry = access(cache)
    calls = []
    sheet = object()
    draw = SimpleNamespace(
        EditSheet=lambda: calls.append("edit_sheet"),
        GetCurrentSheet=lambda: sheet,
        ViewZoomtofit2=lambda: calls.append("fit"),
    )

    def create(adapter, **kwargs):
        calls.append(kwargs)
        return draw

    monkeypatch.setattr(common, "new_drawing", create)
    monkeypatch.setattr(common, "assert_asme_b_sheet", lambda *a, **k: calls.append(k))
    assert prepared.inherited_drawing(cache.adapter, entry) == (draw, sheet)
    assert calls[0]["template"] == str(entry.path)
    assert calls[1:] == [
        "edit_sheet",
        {"phase": "prepared setup", "scale": (1.0, 1.0)},
        "fit",
    ]
    entry.path.write_bytes(b"corrupted")
    calls.clear()
    with pytest.raises(RuntimeError, match="hash differs"):
        prepared.inherited_drawing(cache.adapter, entry)
    assert calls == []


@pytest.mark.parametrize(
    "kind",
    [
        "Text",
        "Line",
        "Arc",
        "PolyLine",
        "Triangle",
        "ArrowHead",
        "Polygon",
        "Ellipse",
        "Parabola",
        "Point",
    ],
)
def test_blank_link_exclusion_checks_every_native_primitive(blank_note, kind):  # noqa: F811
    blank_note.counts[kind] = 1
    with pytest.raises(
        (RuntimeError, ValueError), match="ink or leaders|primitive inventory"
    ):
        defaults._empty_link(blank_note.annotation, blank_note.note)


@pytest.mark.parametrize("field", ["GetLeaderCount", "GetMultiJogLeaderCount"])
def test_blank_link_exclusion_checks_both_native_leader_inventories(blank_note, field):  # noqa: F811
    setattr(blank_note.annotation, field, lambda: 1)
    with pytest.raises(RuntimeError, match="ink or leaders"):
        defaults._empty_link(blank_note.annotation, blank_note.note)


@pytest.fixture
def blank_sheet(
    monkeypatch,
    blank_note,  # noqa: F811
):
    @dataclass
    class Bounds:
        name: str
        kind: int = 6

    edge = SimpleNamespace(
        GetText=lambda: common._METRIC_EDGE_BREAK_NOTE,
        PropertyLinkedText="",
        GetExtent=lambda: (0.2, 0.3, 0, 0.25, 0.31, 0),
        GetTextJustification=lambda: 2,
        GetTextVerticalJustification=lambda: 0,
        LockPosition=False,
    )
    blank_note.note.GetTextJustification = lambda: 2
    blank_note.note.GetTextVerticalJustification = lambda: 0
    blank_note.note.LockPosition = False
    edge_annotation = SimpleNamespace(
        GetType=lambda: 6, GetSpecificAnnotation=lambda: edge, Visible=1
    )
    notes = [edge_annotation, blank_note.annotation, blank_note.annotation]
    view = SimpleNamespace(GetAnnotations=lambda: notes)
    sheet = SimpleNamespace(
        GetProperties2=lambda: (2, 12, 2, 1, 0, 0.4318, 0.2794, 1),
        SheetFormatVisible=True,
    )
    units = {263: 4, 47: 0, 49: 2}
    model = SimpleNamespace(
        GetCurrentSheet=lambda: sheet,
        GetFirstView=lambda: view,
        GetViews=lambda: ((view,),),
        GetEditSheet=lambda: True,
        GetUserPreferenceIntegerValue=lambda key: units[key],
        Extension=SimpleNamespace(GetUserPreferenceInteger=lambda *a: 2),
    )
    monkeypatch.setattr(defaults, "annotation_box", lambda *a: Bounds("generated"))
    adapter = SimpleNamespace(
        currentModel=model, _get_attr_or_call=lambda obj, name: getattr(obj, name)()
    )
    spec = prepared.TemplateSpec((2, 1), 2)
    return SimpleNamespace(
        adapter=adapter,
        spec=spec,
        blank_note=blank_note,
        edge=edge,
        units=units,
        sheet=sheet,
    )


def test_default_snapshot_preserves_links_multiplicity_raw_font_and_anchor(blank_sheet):
    adapter, spec = blank_sheet.adapter, blank_sheet.spec
    linked_note = blank_sheet.blank_note
    before = defaults.snapshot_defaults(adapter, spec)
    linked_note.note.GetExtent = lambda: (0.1, 0.2, 0, 0.1, 0.21, 0)
    after = defaults.snapshot_defaults(adapter, spec)
    defaults.compare_defaults(before, after)
    assert len(before["sheet_notes"]) == 3
    assert (
        before["blank_linked_extent_observations"]
        != after["blank_linked_extent_observations"]
    )
    linked_note.fmt.CharHeight += 1e-12
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(after, defaults.snapshot_defaults(adapter, spec))
    blank_sheet.units[263] = 5
    with pytest.raises(RuntimeError, match="units differ"):
        defaults.snapshot_defaults(adapter, spec)


@pytest.mark.parametrize("target", ["blank_link", "visible_note"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("GetTextJustification", lambda: 1),
        ("GetTextVerticalJustification", lambda: 2),
        ("LockPosition", True),
    ],
)
def test_raw_defaults_reject_note_alignment_and_lock_changes(
    blank_sheet, target, field, value
):
    adapter, spec = blank_sheet.adapter, blank_sheet.spec
    note = blank_sheet.blank_note.note if target == "blank_link" else blank_sheet.edge
    before = defaults.snapshot_defaults(adapter, spec)
    setattr(note, field, value)
    after = defaults.snapshot_defaults(adapter, spec)
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(before, after)


def test_raw_defaults_reject_hidden_sheet_format(blank_sheet):
    adapter, spec = blank_sheet.adapter, blank_sheet.spec
    before = defaults.snapshot_defaults(adapter, spec)
    blank_sheet.sheet.SheetFormatVisible = False
    after = defaults.snapshot_defaults(adapter, spec)
    with pytest.raises(RuntimeError, match="raw defaults"):
        defaults.compare_defaults(before, after)


def test_native_save_requires_owned_document_still_active(native, monkeypatch):
    def switch_active(*args):
        native.adapter.swApp.ActiveDoc = native.source
        return {"units": 4}

    monkeypatch.setattr(prepared, "snapshot_defaults", switch_active)
    with pytest.raises(ExceptionGroup):
        run_native(native)
    assert not native.closed
    assert all(not doc.calls for doc in native.created)
    assert not (native.directory / "prepared.DRWDOT").exists()


def test_duplicate_document_title_refuses_save_and_title_based_close(
    native, monkeypatch
):
    original = common.new_project_drawing

    def duplicate_title(*args, **kwargs):
        draw, sheet = original(*args, **kwargs)
        draw.title = native.source.title.swapcase()
        return draw, sheet

    monkeypatch.setattr(common, "new_project_drawing", duplicate_title)
    with pytest.raises(ExceptionGroup):
        run_native(native)
    assert not native.closed
    assert native.source in native.documents
    assert all(not doc.calls for doc in native.created)
    assert not (native.directory / "prepared.DRWDOT").exists()


@pytest.mark.parametrize(
    "case", ["bool_return", "missing_file", "wrong_path", "readback"]
)
def test_native_save_failures_never_pass_and_close_only_owned(
    native, monkeypatch, case
):
    original = Model.SaveAs3

    def save(model, path, version, options):
        result = original(model, path, version, options)
        if case == "missing_file":
            Path(path).unlink()
        if case == "wrong_path":
            model.path = str(Path(path).with_name("unexpected.DRWDOT"))
        return True if case == "bool_return" else result

    monkeypatch.setattr(Model, "SaveAs3", save)
    if case == "readback":
        readings = iter(({"units": 4}, {"units": 5}))
        monkeypatch.setattr(prepared, "snapshot_defaults", lambda *a: next(readings))
    with pytest.raises(ExceptionGroup):
        run_native(native)
    assert native.documents == [native.source]
    assert native.source not in native.closed


def test_setup_failure_with_changed_active_user_document_never_closes_it(
    native, monkeypatch
):
    original = common.new_project_drawing

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        native.adapter.swApp.ActiveDoc = native.source
        raise RuntimeError("user activated original during failed setup")

    monkeypatch.setattr(common, "new_project_drawing", fail)
    receipt = {}
    with pytest.raises(ExceptionGroup):
        run_native(native, receipt)
    assert not native.closed
    assert native.source in native.documents
    assert "inventory" in receipt["cleanup_error"]
