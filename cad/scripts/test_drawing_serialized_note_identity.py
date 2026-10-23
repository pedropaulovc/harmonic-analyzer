"""Native-boundary serialized-note identity contracts for the SM and PD consumers.

These fakes model native identity separately from Python wrappers. No physical
attachment, note geometry or text is claimed here; each recipe retains those
proofs and the coordinator owns real saved-drawing/native qualification.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _drawing_serialized_note_identity as identity


def _unexpected(*_args, **_kwargs):
    raise AssertionError("serialized identity must not select, rebuild, save or read dimension/text geometry")


def _view(name, source=None, configuration="Default"):
    view = SimpleNamespace(
        name=name, native_identity=object(), ReferencedDocument=source,
        ReferencedConfiguration=configuration, annotations=[],
        GetDisplayDimensions=_unexpected, GetNextView=_unexpected,
    )
    view.GetAnnotations = lambda: tuple(view.annotations)
    return view


def _annotation(name, owner, *, kind=6, owner_type=0):
    annotation = SimpleNamespace(
        name=name, native_identity=object(), Owner=owner, OwnerType=owner_type,
        kind=kind, GetSpecificAnnotation=_unexpected, GetDisplayData=_unexpected,
        SetPosition2=_unexpected,
    )
    annotation.GetName = lambda: annotation.name
    annotation.GetType = lambda: annotation.kind
    return annotation


def _same(left, right):
    if left is None or right is None:
        return 0
    return int(getattr(left, "native_identity", left) is getattr(right, "native_identity", right))


@pytest.fixture(params=("sm-vn-knife-hanger-stud", "pd-vn-transgear-pivot-screw"), ids=("SM", "PD"))
def case(request, monkeypatch, tmp_path):
    stem = request.param
    case = SimpleNamespace(
        drawing_path=tmp_path / f"{stem}.SLDDRW",
        source_path=tmp_path / f"{stem}.SLDPRT",
        sheet_names=("FINISHED", "ORIGINAL-STOCK"), sheet_name="FINISHED",
        configuration="Default", label=f"{stem}: Purchased Screw Note", events=[],
    )
    case.drawing_path.touch()
    case.source_path.touch()
    case.actual_source_path = str(case.source_path.resolve())
    source = SimpleNamespace(GetPathName=lambda: case.actual_source_path)
    case.finished_sheet = _view(case.sheet_name)
    case.stock_sheet = _view(case.sheet_names[1])
    case.front = _view(f"{stem}:Front", source)
    case.iso = _view(f"{stem}:Iso", source)
    case.stock = _view(f"{stem}:Stock", source, "AS SUPPLIED STOCK")
    case.stock_iso = _view(f"{stem}:StockIso", source, "AS SUPPLIED STOCK")
    case.original = _annotation("DetailItem347", case.front)
    case.creation_name = case.original.name
    # This is the same original native annotation AFTER serialization, not a
    # guessed basename/suffix alias and not a newly found equal-text note.
    case.original.name = f"ACTUAL-SERIALIZED-{stem}-NOTE"
    case.front.annotations.append(case.original)
    case.decoy = _annotation("Other actual annotation", case.front, kind=4)
    case.front.annotations.append(case.decoy)
    # Sheet/template annotations do not have drawing-view Owner references.
    case.finished_sheet.annotations.append(SimpleNamespace(
        native_identity=object(), OwnerType=2, GetName=lambda: "Template item",
        GetType=lambda: 6,
    ))
    case.stock_sheet.annotations.append(SimpleNamespace(
        native_identity=object(), OwnerType=1, GetName=lambda: "Original stock title",
        GetType=lambda: 6,
    ))
    case.actual_sheet_names = case.sheet_names
    case.rows = (
        (case.finished_sheet, case.front, case.iso),
        (case.stock_sheet, case.stock, case.stock_iso),
    )
    case.actual_drawing_path = str(case.drawing_path.resolve())
    model = SimpleNamespace(
        native_identity=object(), GetType=lambda: 3,
        GetPathName=lambda: case.actual_drawing_path,
        GetSheetNames=lambda: case.actual_sheet_names,
        GetViews=lambda: case.rows, EditRebuild3=_unexpected,
        ClearSelection2=_unexpected, Save3=_unexpected, ActivateSheet=_unexpected,
    )
    case.model = model
    case.registered = model
    case.app = SimpleNamespace(
        IsSame=_same, ActiveDoc=model,
        GetOpenDocumentByName=lambda path: case.registered if path == str(case.drawing_path.resolve()) else None,
        OpenDoc6=_unexpected, CloseDoc=_unexpected,
    )
    case.adapter = SimpleNamespace(currentModel=model, swApp=case.app)
    monkeypatch.setattr(identity, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(identity, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(
        identity._telemetry, "event", lambda name, **fields: case.events.append((name, fields)),
    )
    return case


def _capture(case, original=None, view=None):
    return identity.capture_serialized_note_name(
        case.adapter, case.original if original is None else original,
        case.front if view is None else view,
        drawing_path=case.drawing_path, source_path=case.source_path,
        sheet_names=case.sheet_names, sheet_name=case.sheet_name,
        configuration=case.configuration, label=case.label,
    )


def _receipt(case):
    events = [fields for name, fields in case.events if name == "drawing.serialized_note_identity"]
    assert events
    return events[-1]


def test_returns_actual_saved_name_from_original_native_identity_with_unordered_sheet_rows(case):
    case.rows = tuple(reversed(case.rows))
    actual = _capture(case)
    assert actual == case.original.name != case.creation_name
    assert case.original.Owner is case.front
    assert case.adapter.currentModel is case.model
    assert _receipt(case)["status"] == "captured"


def test_accepts_distinct_python_wrappers_only_when_native_note_view_and_document_identities_agree(case):
    original_wrapper = SimpleNamespace(**vars(case.original))
    view_wrapper = SimpleNamespace(**vars(case.front))
    document_wrapper = SimpleNamespace(**vars(case.model))
    case.registered = document_wrapper
    case.app.ActiveDoc = document_wrapper
    assert original_wrapper is not case.original
    assert view_wrapper is not case.front
    assert _capture(case, original_wrapper, view_wrapper) == case.original.name


@pytest.mark.parametrize(
    "fault",
    (
        "same_named_impostor", "duplicate_original", "duplicate_name", "duplicate_name_other_sheet",
        "owner", "null_owner", "owner_type", "not_note", "view", "source", "relative_source",
        "null_source", "configuration",
        "output_path", "relative_output", "drawing_type", "registered", "null_registered", "active",
        "null_active", "empty_name", "null_name", "null_annotation", "null_view", "sheet_names",
        "sheet_rows", "extra_sheet_row", "null_rows", "sheet_owned_original", "unknown_same", "boolean_same",
    ),
)
def test_refuses_native_identity_owner_configuration_source_and_saved_output_drift(case, fault):
    if fault == "same_named_impostor":
        impostor = SimpleNamespace(**vars(case.original), replacement=True)
        impostor.native_identity = object()
        case.front.annotations[0] = impostor
    elif fault == "duplicate_original":
        case.front.annotations.append(case.original)
    elif fault == "duplicate_name":
        case.front.annotations.append(_annotation(case.original.name, case.front))
    elif fault == "duplicate_name_other_sheet":
        case.stock.annotations.append(_annotation(case.original.name, case.stock))
    elif fault == "owner":
        case.original.Owner = SimpleNamespace(name=case.front.name, native_identity=object())
    elif fault == "null_owner":
        case.original.Owner = None
    elif fault == "owner_type":
        case.original.OwnerType = 1
    elif fault == "not_note":
        case.original.kind = 4
    elif fault == "view":
        foreign_view = SimpleNamespace(**vars(case.front))
        foreign_view.native_identity = object()
        case.rows = ((case.finished_sheet, foreign_view, case.iso), case.rows[1])
    elif fault == "source":
        case.actual_source_path = str(case.source_path.with_name("foreign.SLDPRT"))
    elif fault == "relative_source":
        case.actual_source_path = case.source_path.name
    elif fault == "null_source":
        case.front.ReferencedDocument = None
    elif fault == "configuration":
        case.front.ReferencedConfiguration = "FOREIGN"
    elif fault == "output_path":
        case.actual_drawing_path = str(case.drawing_path.with_name("foreign.SLDDRW"))
    elif fault == "relative_output":
        case.actual_drawing_path = case.drawing_path.name
    elif fault == "drawing_type":
        case.model.GetType = lambda: 1
    elif fault == "registered":
        case.registered = object()
    elif fault == "null_registered":
        case.registered = None
    elif fault == "active":
        case.app.ActiveDoc = object()
    elif fault == "null_active":
        case.app.ActiveDoc = None
    elif fault == "empty_name":
        case.original.name = ""
    elif fault == "null_name":
        case.original.name = None
    elif fault == "null_annotation":
        case.front.annotations.append(None)
    elif fault == "null_view":
        case.rows = ((case.finished_sheet, case.front, None), case.rows[1])
    elif fault == "sheet_names":
        case.actual_sheet_names = (case.sheet_name,)
    elif fault == "sheet_rows":
        case.rows = (case.rows[0],)
    elif fault == "extra_sheet_row":
        case.rows = (*case.rows, (_view("UNEXPECTED SHEET"),))
    elif fault == "null_rows":
        case.rows = None
    elif fault == "sheet_owned_original":
        case.front.annotations.remove(case.original)
        case.finished_sheet.annotations.append(case.original)
    elif fault in ("unknown_same", "boolean_same"):
        case.app.IsSame = lambda left, right: (
            (2 if fault == "unknown_same" else True)
            if left is case.original and right is case.original else _same(left, right)
        )
    else:
        raise AssertionError(f"unknown native identity fault {fault}")
    with pytest.raises(RuntimeError, match="serialized note identity capture"):
        _capture(case)
    assert _receipt(case)["status"] == "refused"


@pytest.mark.parametrize("missing", ("annotation", "view", "current_model", "application"))
def test_null_original_or_current_native_references_refuse_without_fallback(case, missing):
    original, view = case.original, case.front
    if missing == "annotation":
        original = None
    elif missing == "view":
        view = None
    elif missing == "current_model":
        case.adapter.currentModel = None
    else:
        case.adapter.swApp = None
    with pytest.raises(RuntimeError, match="serialized note identity capture"):
        identity.capture_serialized_note_name(
            case.adapter, original, view,
            drawing_path=case.drawing_path, source_path=case.source_path,
            sheet_names=case.sheet_names, sheet_name=case.sheet_name,
            configuration=case.configuration, label=case.label,
        )
    assert _receipt(case)["status"] == "refused"


@pytest.mark.parametrize("getter", ("name", "type", "annotations", "source_path"))
def test_original_native_getter_failure_is_chained_and_reachable_actual_inventory_survives(case, getter):
    cause = OSError(f"original native {getter} getter failed")

    def fail(*_args):
        raise cause

    if getter == "name":
        case.original.GetName = fail
    elif getter == "type":
        case.original.GetType = fail
    elif getter == "annotations":
        case.front.GetAnnotations = fail
    else:
        case.front.ReferencedDocument = SimpleNamespace(GetPathName=fail)
    with pytest.raises(RuntimeError, match="serialized note identity capture") as error:
        _capture(case)
    assert error.value.__cause__ is cause
    receipt = _receipt(case)
    assert receipt["status"] == "refused"
    assert any(record.get("view_name") == case.stock.name for record in receipt["inventory"])
    assert any(record.get("view_name") == case.stock_iso.name for record in receipt["inventory"])
    assert any(
        item.get("errors")
        for record in receipt["inventory"]
        for item in (record, *record.get("annotations", ()))
    )


def test_missing_original_is_not_recovered_from_equal_name_or_equal_note_text(case):
    impostor = _annotation(case.original.name, case.front)
    impostor.PropertyLinkedText = "$PRPSHEET:\"Purchased Screw Note\""
    case.front.annotations[0] = impostor
    with pytest.raises(RuntimeError, match="exactly one actual IsSame=1"):
        _capture(case)
    assert _receipt(case)["match_count"] == 0
