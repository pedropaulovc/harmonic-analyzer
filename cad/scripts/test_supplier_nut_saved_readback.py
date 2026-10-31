"""Offline persisted-nut proofs: fresh native graph, ownership and file integrity.

No COM or production artifacts are touched. The source/chord/mapped-attachment
proof is production code, shared with the existing supplier-nut native doubles.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import _dimensions
import _purchased_fastener_drawing as purchased
import _supplier_nut_drawing as nuts
import test_supplier_nut_drawing as nut_doubles
from test_purchased_fastener_drawing import _purchased_source_lifecycle
from test_supplier_nut_drawing import (
    CONSUMERS,
    FEATURE,
    _point,
)

native_nut = nut_doubles.native_nut


@pytest.fixture
def saved_nut(native_nut, monkeypatch, tmp_path):
    def create(spec=None):
        case = native_nut() if spec is None else native_nut(spec)
        case.source_path = tmp_path / "nut.SLDPRT"
        case.source_path.write_bytes(b"immutable supplier native source")
        case.drawing_path = tmp_path / "nut.SLDDRW"
        case.drawing_path.write_bytes(b"saved drawing before readback")
        case.configuration = "Supplier authoring configuration"
        case.model.native_identity = object()
        case.model.GetPathName = lambda: str(case.source_path)
        case.model.GetType = lambda: 1
        case.model.IsOpenedReadOnly = lambda: True
        case.model.Parameter = lambda name: (
            case.native if name == f"ThreadNominalMajor@{FEATURE}" else None
        )
        case.source_display.GetDimension2 = lambda _index: case.native
        case.feature.GetFirstDisplayDimension = lambda: case.source_display
        case.feature.GetNextDisplayDimension = lambda _display: None
        case.display.GetAnnotation().Owner = case.front
        case.display.GetAnnotation().OwnerType = 0
        # The source's active configuration can legitimately differ from the
        # saved Front's explicitly captured authoring configuration.
        case.model.ConfigurationManager = NS(
            ActiveConfiguration=NS(Name="Another valid configuration")
        )
        case.front.GetOrientationName = lambda: "*Front"
        case.front.GetReferencedModelName = lambda: str(case.source_path)
        case.front.ReferencedConfiguration = case.configuration
        case.annotations = [case.display.GetAnnotation()]
        case.front.GetAnnotations = lambda: tuple(case.annotations)
        case.right.GetOrientationName = lambda: "*Right"
        case.right.GetAnnotations = lambda: ()
        case.sheet_view = NS(GetOrientationName=lambda: "", GetAnnotations=lambda: ())
        case.views = [case.sheet_view, case.front, case.right]
        case.sheets = [case.views]
        case.drawing = NS(
            native_identity=object(),
            GetPathName=lambda: str(case.drawing_path),
            GetTitle=lambda: case.drawing_path.name,
            GetType=lambda: 3,
            IsOpenedReadOnly=lambda: True,
            GetViews=lambda: tuple(tuple(views) for views in case.sheets),
        )
        case.loaded_source = case.model
        case.loaded_drawing = None
        case.open_result = lambda: (case.drawing, 0, 4)
        case.on_open = lambda: None
        case.on_close = lambda: None
        case.opens = []
        case.closes = []
        case.events = []
        case.infos = []
        case.bindings = []
        case.adapter.currentModel = case.model

        def lookup(path):
            path = Path(path).resolve()
            if path == case.source_path.resolve():
                return case.loaded_source
            assert path == case.drawing_path.resolve(), "unexpected native document lookup"
            return case.loaded_drawing

        def open_document(*args):
            assert args == (str(case.drawing_path.resolve()), 3, 3, "", 0, 0)
            case.opens.append(args)
            case.loaded_drawing = case.drawing
            case.on_open()
            return case.open_result()

        def close_document(name):
            assert name in (case.drawing_path.name, str(case.drawing_path.resolve()))
            case.closes.append(name)
            case.on_close()
            case.loaded_drawing = None

        case.adapter.swApp.GetOpenDocumentByName = lookup
        case.adapter.swApp.OpenDoc6 = open_document
        case.adapter.swApp.CloseDoc = close_document

        def bind(obj, interface):
            case.bindings.append((obj, interface))
            return obj

        monkeypatch.setattr(nuts, "_early_bound", bind)
        monkeypatch.setattr(
            _dimensions, "_com_invoke",
            lambda obj, _interface, method, *args: getattr(obj, method)(*args),
        )
        monkeypatch.setattr(nuts._telemetry, "event", lambda name, **kw: case.events.append((name, kw)))
        monkeypatch.setattr(nuts._telemetry, "info", lambda *args, **kw: case.infos.append((args, kw)))

        def run():
            return nuts.assert_saved_supplier_nut_nominal(
                case.adapter, case.drawing_path,
                nominal_major_mm=case.spec.SUPPLIER_NOMINAL_MAJOR_MM,
                source_path=case.source_path,
                configuration=case.configuration,
            )

        case.run = run
        return case
    return create


@pytest.mark.parametrize("spec", CONSUMERS)
def test_saved_readback_proves_fresh_front_chord_and_both_mapped_ends(saved_nut, spec):
    case = saved_nut(spec)
    original_drawing = case.drawing_path.read_bytes()
    original_source = case.source_path.read_bytes()
    assert case.run() is None
    assert len(case.opens) == len(case.closes) == 1
    assert case.loaded_drawing is None
    assert case.adapter.currentModel is None or case.adapter.currentModel is case.model
    assert case.mapping_reads == list(case.inventory)
    assert (case.adapter.swApp, "ISldWorks") in case.bindings
    assert (case.drawing, "IDrawingDoc") in case.bindings
    assert case.drawing_path.read_bytes() == original_drawing
    assert case.source_path.read_bytes() == original_source
    proofs = [
        json.loads(args[0].removeprefix("supplier_nut_saved_readback_proof "))
        for args, _fields in case.infos
        if args and args[0].startswith("supplier_nut_saved_readback_proof ")
    ]
    assert len(proofs) == 1
    assert proofs[0]["nominal_major_mm"] == pytest.approx(spec.SUPPLIER_NOMINAL_MAJOR_MM)
    assert proofs[0]["attachment_correspondence"]["proven"] is True
    assert not case.events, "saved proof must not emit per-entity events"


def test_saved_readback_can_autoload_previously_closed_hidden_source(saved_nut):
    case = saved_nut()
    case.loaded_source = None
    case.on_open = lambda: setattr(case, "loaded_source", case.model)
    case.run()
    assert case.closes and case.loaded_drawing is None
    assert case.loaded_source is case.model


def test_saved_readback_does_not_reuse_pre_save_display(saved_nut):
    case = saved_nut()
    stale = case.display
    fresh_native = NS(**vars(case.native))
    fresh_native.SystemValue *= 2
    fresh = case.make_display()
    fresh.GetDimension2 = lambda _index: fresh_native
    fresh.GetAnnotation().Owner = case.front
    fresh.GetAnnotation().OwnerType = 0
    case.annotations[:] = [fresh.GetAnnotation()]
    assert stale.GetDimension2(0).SystemValue == case.spec.SUPPLIER_NOMINAL_MAJOR_MM / 1000
    with pytest.raises(RuntimeError):
        case.run()
    assert case.closes and case.loaded_drawing is None


@pytest.mark.parametrize("defect", [
    "configuration", "source-path", "source-identity", "source-unloaded",
    "source-writable", "source-kind", "source-loaded-path",
])
def test_saved_readback_requires_expected_configuration_and_exact_loaded_source(saved_nut, tmp_path, defect):
    case = saved_nut()
    if defect == "configuration":
        case.front.ReferencedConfiguration = "Another valid configuration"
    elif defect == "source-path":
        case.front.GetReferencedModelName = lambda: str(tmp_path / "other.SLDPRT")
    elif defect == "source-identity":
        foreign = NS(**vars(case.model))
        foreign.native_identity = object()
        case.front.ReferencedDocument = foreign
    elif defect == "source-unloaded":
        case.loaded_source = None
    elif defect == "source-writable":
        case.model.IsOpenedReadOnly = lambda: False
    elif defect == "source-kind":
        case.model.GetType = lambda: 2
    else:
        case.model.GetPathName = lambda: str(tmp_path / "other.SLDPRT")
    with pytest.raises(RuntimeError):
        case.run()
    assert case.loaded_source is not None or defect == "source-unloaded"
    assert case.loaded_drawing is None
    assert len(case.closes) == len(case.opens)
    assert case.adapter.currentModel is not case.drawing


@pytest.mark.parametrize("foreign", [False, True])
def test_saved_readback_never_borrows_or_closes_already_open_target(saved_nut, foreign):
    case = saved_nut()
    borrowed = NS(**vars(case.drawing)) if foreign else case.drawing
    if foreign:
        borrowed.native_identity = object()
    case.loaded_drawing = borrowed
    case.adapter.currentModel = borrowed
    with pytest.raises(RuntimeError):
        case.run()
    assert not case.opens and not case.closes
    assert case.loaded_drawing is borrowed
    assert case.adapter.currentModel is borrowed


@pytest.mark.parametrize("defect", [
    "path", "kind", "boolean-kind", "writable", "integer-read-only", "loaded-identity",
])
def test_saved_readback_refuses_foreign_or_untrusted_reopened_drawing(saved_nut, tmp_path, defect):
    case = saved_nut()
    if defect == "path":
        case.drawing.GetPathName = lambda: str(tmp_path / "foreign.SLDDRW")
    elif defect == "kind":
        case.drawing.GetType = lambda: 1
    elif defect == "boolean-kind":
        case.drawing.GetType = lambda: True
    elif defect == "writable":
        case.drawing.IsOpenedReadOnly = lambda: False
    elif defect == "integer-read-only":
        case.drawing.IsOpenedReadOnly = lambda: 1
    else:
        foreign = NS(**vars(case.drawing))
        foreign.native_identity = object()
        case.on_open = lambda: setattr(case, "loaded_drawing", foreign)
    with pytest.raises(RuntimeError):
        case.run()
    assert case.adapter.currentModel is not case.drawing
    # A foreign document replacing the acquired target must not be closed.
    if defect in {"loaded-identity", "path", "kind", "boolean-kind"}:
        assert not case.closes
        assert case.loaded_drawing is (foreign if defect == "loaded-identity" else case.drawing)
    else:
        assert case.loaded_drawing is None


@pytest.mark.parametrize("result", [
    lambda c: None,
    lambda c: c.drawing,
    lambda c: (c.drawing, 0),
    lambda c: (c.drawing, 0, 0, 0),
    lambda c: [c.drawing, 0, 0],
    lambda c: (None, 0, 0),
    lambda c: (c.drawing, 2, 0),
    lambda c: (c.drawing, True, 0),
    lambda c: (c.drawing, "0", 0),
    lambda c: (c.drawing, 0.0, 0),
    lambda c: (c.drawing, 0, False),
    lambda c: (c.drawing, 0, None),
    lambda c: (c.drawing, 0, "0"),
], ids=["none", "model-only", "short", "long", "list", "no-model", "error",
        "bool-error", "string-error", "float-error", "bool-warning", "no-warning", "string-warning"])
def test_saved_readback_strict_makepy_tuple_still_cleans_model_loaded_on_error(saved_nut, result):
    case = saved_nut()
    case.open_result = lambda: result(case)
    with pytest.raises(RuntimeError):
        case.run()
    assert len(case.opens) == len(case.closes) == 1
    assert case.loaded_drawing is None
    assert case.adapter.currentModel is None or case.adapter.currentModel is case.model


@pytest.mark.parametrize("defect", [
    "missing-front", "duplicate-front", "multiple-sheets", "missing-nominal",
    "duplicate-nominal", "wrong-view", "hidden-nominal", "wrong-feature", "value-drift",
])
def test_saved_readback_reacquires_exactly_one_visible_front_nominal(saved_nut, defect):
    case = saved_nut()
    if defect == "missing-front":
        case.front.GetOrientationName = lambda: "*Top"
    elif defect == "duplicate-front":
        case.views.append(NS(**vars(case.front)))
    elif defect == "multiple-sheets":
        case.sheets.append([case.sheet_view])
    elif defect == "missing-nominal":
        case.annotations.clear()
    elif defect == "duplicate-nominal":
        case.annotations.append(case.make_display().GetAnnotation())
    elif defect == "wrong-view":
        case.right.GetAnnotations = lambda: (case.display.GetAnnotation(),)
        case.annotations.clear()
    elif defect == "hidden-nominal":
        case.display.GetAnnotation().Visible = 0
    elif defect == "wrong-feature":
        case.native.FullName = "ThreadNominalMajor@OtherReference@nut.SLDPRT"
    else:
        case.native.SystemValue += 0.0001
    with pytest.raises(RuntimeError):
        case.run()
    assert case.closes and case.loaded_drawing is None
    assert case.adapter.currentModel is None or case.adapter.currentModel is case.model


@pytest.mark.parametrize("defect", ["missing-map", "duplicate-map", "unrelated-end", "negative-control", "chord-drift"])
def test_saved_readback_runs_real_source_and_attachment_correspondence_proof(saved_nut, defect):
    case = saved_nut()
    if defect == "missing-map":
        case.mapping[id(case.source[0])] = None
    elif defect == "duplicate-map":
        case.mapping[id(case.source[0])] = case.mapped[1]
    elif defect == "unrelated-end":
        case.display.GetAnnotation().entities = (case.attachments[0], _point(context="drawing"))
    elif defect == "chord-drift":
        case.source[0].X += 1e-6
    else:
        native_same = case.same

        def same(left, right):
            if left is case.attachments[0] and right is case.mapped[1]:
                return 1
            return native_same(left, right)

        case.adapter.swApp.IsSame = same
    with pytest.raises(RuntimeError) as caught:
        case.run()
    if defect != "chord-drift":
        census = json.loads(str(caught.value).split(": ", 1)[1])
        assert census["proven"] is False
    assert case.closes and case.loaded_drawing is None


@pytest.mark.parametrize("primary_failure", [False, True])
def test_saved_readback_hash_guards_saved_drawing_on_success_and_failure(saved_nut, primary_failure):
    case = saved_nut()
    primary = OSError("fresh native annotation read failed")

    def read_annotations():
        case.drawing_path.write_bytes(b"unexpected saved drawing mutation")
        if primary_failure:
            raise primary
        return tuple(case.annotations)

    case.front.GetAnnotations = read_annotations
    with pytest.raises(OSError if primary_failure else RuntimeError) as caught:
        case.run()
    if primary_failure:
        assert caught.value is primary
        assert "drawing" in "\n".join(primary.__notes__).lower()
    assert case.loaded_drawing is None
    assert case.adapter.currentModel is None or case.adapter.currentModel is case.model


@pytest.mark.parametrize("primary_failure", [False, True])
def test_saved_readback_close_failure_is_not_silent_or_primary_replacing(saved_nut, primary_failure):
    case = saved_nut()
    primary = OSError("primary saved native annotation failure")
    cleanup = RuntimeError("drawing CloseDoc failed")

    def fail_close():
        raise cleanup

    case.on_close = fail_close
    if primary_failure:
        def fail_read():
            raise primary
        case.front.GetAnnotations = fail_read
    with pytest.raises(OSError if primary_failure else RuntimeError) as caught:
        case.run()
    if primary_failure:
        assert caught.value is primary
        assert "CloseDoc failed" in "\n".join(primary.__notes__)
    assert case.loaded_drawing is case.drawing
    assert case.adapter.currentModel is not case.drawing


def test_saved_readback_requires_existing_actual_drawing_before_native_open(saved_nut):
    case = saved_nut()
    case.drawing_path.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        case.run()
    assert not case.opens and not case.closes


@pytest.fixture
def public_saved_case(monkeypatch, tmp_path):
    """Keep the public wrapper's real immutable-source try/finally in scope."""
    # Retention is not under test and must not write real forensic artifacts.
    # The public wrapper's hashing, try/finally and failure re-raise stay real.
    monkeypatch.setattr(
        purchased._seat_forensics, "capture_com_failure", lambda *_args, **_kwargs: None
    )
    state = NS(callback=lambda _adapter, _path: None)
    real_builder = purchased.build_purchased_fastener_drawing

    async def build(adapter, spec, **kwargs):
        return await real_builder(adapter, spec, saved_check=state.callback, **kwargs)

    monkeypatch.setattr(purchased, "build_purchased_fastener_drawing", build)
    case = _purchased_source_lifecycle(monkeypatch, tmp_path, "fastener")
    case.artifacts = {"drawing": str(tmp_path / "supplier.SLDDRW"), "pdf": "reference.pdf"}

    async def complete_sheet(adapter, _spec, **_kwargs):
        Path(case.artifacts["drawing"]).write_bytes(b"saved native drawing")
        adapter.currentModel = case.model
        return case.artifacts

    monkeypatch.setattr(purchased, "_build_reference_sheet", complete_sheet)
    case.saved_state = state
    return case


def test_public_wrapper_returns_identical_artifacts_after_saved_callback(public_saved_case):
    case = public_saved_case
    calls = []

    def check(adapter, path):
        assert adapter is case.adapter
        assert isinstance(path, Path)
        assert path.read_bytes() == b"saved native drawing"
        calls.append(path)

    case.saved_state.callback = check
    assert case.run() is case.artifacts
    assert calls == [Path(case.artifacts["drawing"])]
    assert case.source.read_bytes() == b"unchanged supplier bytes"


@pytest.mark.parametrize("primary_failure", [False, True])
@pytest.mark.parametrize("mutation", ["rewrite", "unreadable"])
def test_public_wrapper_source_hash_covers_saved_callback_success_and_error(public_saved_case, primary_failure, mutation):
    case = public_saved_case
    primary = OSError("saved readback primary failure")

    def check(_adapter, _path):
        if mutation == "rewrite":
            case.source.write_bytes(b"source unexpectedly changed inside saved callback")
        else:
            case.source.unlink()
        if primary_failure:
            raise primary

    case.saved_state.callback = check
    expected = OSError if primary_failure else (RuntimeError if mutation == "rewrite" else FileNotFoundError)
    with pytest.raises(expected) as caught:
        case.run()
    if primary_failure:
        assert caught.value is primary
        notes = "\n".join(primary.__notes__)
        assert "supplier source file preservation also failed" in notes
        assert ("bytes changed" if mutation == "rewrite" else "FileNotFoundError") in notes


@pytest.mark.parametrize("callback", [False, 1, "not callable", object()])
def test_public_wrapper_rejects_noncallable_saved_check_before_source_or_native_work(public_saved_case, callback):
    case = public_saved_case
    case.saved_state.callback = callback
    # A bad option must win even over an unavailable source; the real source
    # opener and real source hash guard remain installed.
    case.source.unlink()
    with pytest.raises((TypeError, ValueError), match="saved_check|saved.check|callable"):
        case.run()
    assert not case.app.opens
    assert not case.phases


@pytest.mark.parametrize("kind", ["async", "non-none"])
def test_public_wrapper_rejects_unexecuted_async_or_non_none_saved_check(public_saved_case, kind):
    case = public_saved_case

    async def asynchronous(_adapter, _path):
        case.source.write_bytes(b"an asynchronous check must never be silently skipped")

    def non_none(_adapter, _path):
        return True

    case.saved_state.callback = asynchronous if kind == "async" else non_none
    with pytest.raises(TypeError, match="synchronous.*None"):
        case.run()
    assert case.source.read_bytes() == b"unchanged supplier bytes"


def test_saved_readback_binds_adapter_to_newly_reopened_drawing(saved_nut):
    case = saved_nut()
    case.adapter.currentModel = NS(closed_drawing=True)

    def opening():
        assert case.adapter.currentModel is None

    case.on_open = opening

    def annotations():
        assert case.adapter.currentModel is case.drawing
        assert case.loaded_drawing is case.drawing
        return tuple(case.annotations)

    case.front.GetAnnotations = annotations
    case.run()
    assert case.adapter.currentModel is None or case.adapter.currentModel is case.model


def test_saved_readback_detects_close_that_leaves_target_loaded(saved_nut):
    case = saved_nut()

    def leave_open(name):
        case.closes.append(name)

    case.adapter.swApp.CloseDoc = leave_open
    with pytest.raises(RuntimeError):
        case.run()
    assert len(case.closes) == 1
    assert case.loaded_drawing is case.drawing
    assert case.adapter.currentModel is not case.drawing


def test_public_wrapper_preserves_saved_callback_error_without_source_mutation(public_saved_case):
    case = public_saved_case
    primary = OSError("saved readback rejected native attachment")

    def check(_adapter, _path):
        raise primary

    case.saved_state.callback = check
    with pytest.raises(OSError) as caught:
        case.run()
    assert caught.value is primary
    assert case.source.read_bytes() == b"unchanged supplier bytes"
