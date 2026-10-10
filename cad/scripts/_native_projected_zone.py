"""Native projected-frame observations, not physical projection-unit qualification.

The current-frame XSD gives ``Projection`` a decimal type but no physical unit.
Document unit getters therefore remain raw evidence; they cannot qualify the
physical height or rendered circled-P symbol. Ordinary frames do not use this
reader. Saved-file reads perform their own documented reload/open operation,
never infer persistence from a caller-supplied phase or an old COM handle.
"""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import _telemetry
from _common import _early_bound
from _gtol_spec import GeometricControl, gtol_frame_signature


# Official swLengthUnit_e values, not a guessed conversion-factor direction.
_LENGTH_UNIT_NAMES = {
    0: "swMM", 1: "swCM", 2: "swMETER", 3: "swINCHES", 4: "swFEET",
    5: "swFEETINCHES", 6: "swANGSTROM", 7: "swNANOMETER", 8: "swMICRON",
    9: "swMIL", 10: "swUIN",
}


def _native_int(value: Any, *, label: str) -> int:
    if type(value) is not int:
        raise RuntimeError(f"{label}: native integer readback is not an integer")
    return value


def _native_string(value: Any, *, label: str, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value.strip()):
        raise RuntimeError(f"{label}: native string readback is not a nonempty string")
    return value


def _native_array(value: Any, *, label: str) -> tuple[Any, ...] | list[Any]:
    if value is None:
        return ()
    if type(value) not in (tuple, list):
        raise RuntimeError(f"{label}: native array readback is not an array")
    return value


def _document_context(model: Any, *, label: str) -> dict[str, Any]:
    model = _early_bound(model, "IModelDoc2")
    document_type = _native_int(model.GetType(), label=f"{label} document type")
    if document_type not in (1, 3):  # swDocPART / swDocDRAWING
        raise RuntimeError(f"{label}: projected reader requires a part or drawing")
    unit = model.GetUserUnit(0)  # swUserUnitsType_e.swLengthUnit
    if unit is None:
        raise RuntimeError(f"{label}: native document length unit is unavailable")
    unit = _early_bound(unit, "IUserUnit")
    unit_type = _native_int(unit.UnitType, label=f"{label} unit type")
    if unit_type != 0:
        raise RuntimeError(f"{label}: native length-unit request returned a non-length unit")
    specific_unit_type = _native_int(
        unit.SpecificUnitType, label=f"{label} specific length unit"
    )
    if specific_unit_type not in _LENGTH_UNIT_NAMES:
        raise RuntimeError(f"{label}: unknown native length unit {specific_unit_type}")
    factor = unit.GetConversionFactor()
    if type(factor) not in (int, float) or not math.isfinite(factor) or factor <= 0:
        raise RuntimeError(f"{label}: native unit conversion factor is not finite positive")
    return {
        "document_path": _native_string(
            model.GetPathName(), label=f"{label} document path", allow_empty=True
        ),
        "document_title": _native_string(model.GetTitle(), label=f"{label} document title"),
        "document_type": document_type,
        "length_unit_type_raw": unit_type,
        "length_specific_unit_type_raw": specific_unit_type,
        "length_specific_unit_enum": _LENGTH_UNIT_NAMES[specific_unit_type],
        "length_conversion_factor_raw": factor,
        "length_unit_full_name_raw": _native_string(
            unit.GetFullUnitName(False), label=f"{label} length unit name"
        ),
    }


def capture_projected_gtol(
    model: Any,
    gtol: Any,
    *,
    expected_xml: str,
    key: str,
    phase: str,
    migrated: bool | None = None,
) -> dict[str, Any]:
    """Read a fresh current frame and raw native document-unit context.

    ``phase`` describes an observation, not proof of save/reopen. The saved-file
    API below owns those operations. Successful semantic comparison is explicitly
    UNQUALIFIED for production physical-unit/render acceptance. Native failures
    raise; no fabricated XML, conversion factor, or legacy PTZ fallback exists.
    ``migrated=None`` means migration history was not observed (saved-file reads).
    """
    expected = gtol_frame_signature(expected_xml)
    if expected.projected_zone_height_mm is None:
        raise ValueError(f"{key}: projected capture requires a projected source control")
    gtol = _early_bound(gtol, "IGtol")
    evidence = {
        "key": key,
        "phase": phase,
        "migrated": migrated,
        "expected_xml": expected_xml,
        "requested_projected_zone_height_mm": expected.projected_zone_height_mm,
        "physical_projection_unit_qualification": "UNQUALIFIED",
        "physical_projection_unit_verified": False,
        **_document_context(model, label=key),
    }
    if _native_int(gtol.GetFormat(), label=f"{key} frame format") != 2:
        raise RuntimeError(f"{key}: projected frame is not current format")
    if _native_int(gtol.GetFrameCount(), label=f"{key} frame count") != 1:
        raise RuntimeError(f"{key}: projected control requires exactly one frame")
    frame = gtol.GetFrame(1)
    if frame is None:
        raise RuntimeError(f"{key}: projected current frame is unavailable")
    frame = _early_bound(frame, "IGtolFrame")
    applied = frame.GetSymbolXml()
    if type(applied) is not str:
        raise RuntimeError(f"{key}: projected frame XML readback is not a string")
    evidence["applied_xml"] = applied
    try:
        actual = gtol_frame_signature(applied)
    except ValueError as exc:
        _telemetry.event(
            "native.projected_zone_readback", **evidence,
            xml_semantics_match=False, readback_error=str(exc),
        )
        raise RuntimeError(f"{key}: invalid projected frame XML readback: {exc}") from exc
    evidence["readback_projected_zone_height_xml_numeric"] = actual.projected_zone_height_mm
    evidence["xml_semantics_match"] = actual == expected
    _telemetry.event("native.projected_zone_readback", **evidence)
    if actual != expected:
        raise RuntimeError(f"{key}: projected frame did not persist source semantics")
    return evidence


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _require_saved_identity(model: Any, path: str, document_type: int, label: str) -> None:
    model = _early_bound(model, "IModelDoc2")
    actual_path = _native_string(model.GetPathName(), label=f"{label} saved document path")
    actual_type = _native_int(model.GetType(), label=f"{label} saved document type")
    if not _same_path(actual_path, path) or actual_type != document_type:
        raise RuntimeError(f"{label}: native saved reader acquired the wrong document")


def _read_controls(
    model: Any, controls: Sequence[GeometricControl], *, phase: str, label: str
) -> tuple[dict[str, Any], ...]:
    model = _early_bound(model, "IModelDoc2")
    document_type = _native_int(model.GetType(), label=f"{label} document type")
    annotations: list[tuple[Any, str]] = []
    if document_type == 1:
        extension = _early_bound(model.Extension, "IModelDocExtension")
        annotations.extend(
            (raw, "") for raw in _native_array(
                extension.GetAnnotations(), label=f"{label} model annotations"
            )
        )
    elif document_type == 3:
        drawing = _early_bound(model, "IDrawingDoc")
        for row in _native_array(drawing.GetViews(), label=f"{label} drawing views"):
            for raw_view in _native_array(row, label=f"{label} sheet views"):
                view = _early_bound(raw_view, "IView")
                view_name = _native_string(view.GetName2(), label=f"{label} view name")
                annotations.extend(
                    (raw, view_name) for raw in _native_array(
                        view.GetAnnotations(), label=f"{label} view annotations"
                    )
                )
    else:
        raise RuntimeError(f"{label}: saved projected reader requires a part or drawing")
    wanted = {control.annotation_name: control for control in controls}
    found: dict[str, tuple[Any, str]] = {}
    for raw, view_name in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = _native_string(annotation.GetName(), label=f"{label} annotation name")
        if name not in wanted:
            continue
        if name in found:
            raise RuntimeError(f"{label}: duplicate saved projected annotation {name!r}")
        if _native_int(annotation.GetType(), label=f"{label} annotation type") != 5:
            raise RuntimeError(f"{label}: saved projected annotation {name!r} is not a GTol")
        gtol = annotation.GetSpecificAnnotation()
        if gtol is None:
            raise RuntimeError(f"{label}: saved projected annotation {name!r} has no GTol")
        found[name] = gtol, view_name
    missing = set(wanted) - set(found)
    if missing:
        raise RuntimeError(f"{label}: missing saved projected annotations {sorted(missing)!r}")
    result: list[dict[str, Any]] = []
    for control in controls:
        gtol, view_name = found[control.annotation_name]
        evidence = capture_projected_gtol(
            model, gtol, expected_xml=control.frame_xml, key=control.key, phase=phase
        )
        evidence["annotation_name"] = control.annotation_name
        evidence["view_name"] = view_name
        result.append(evidence)
    return tuple(result)


@_telemetry.traced("native.saved_projected_gtols", label_param="label")
def require_saved_projected_gtols(
    adapter: Any, path: str | Path, controls: Sequence[GeometricControl], *, label: str
) -> tuple[dict[str, Any], ...]:
    """Audit real saved-file XML, not physical units or rendered symbol acceptance.

    Call after part saving, or after ``finalize_drawing`` has closed the drawing.
    An open part is force-reloaded from its SAME file with DiscardChanges=False;
    open-part dirty state is refused, never discarded or saved. Caller-held part
    handles become stale; reacquire them from the refreshed adapter.currentModel.
    An already-closed part/drawing opens read-only/silent through OpenDoc6 and
    closes even when XML audit fails. CloseDoc can also close non-active hidden
    documents, discarding dirty state there: use an isolated farm audit context.
    An open drawing is refused: finalize it first. Saved drawing lookup covers
    canonically named project_part_pmi frames, not unnamed direct-helper frames.

    The returned receipts stay physical-unit UNQUALIFIED. They permit first-farm
    evidence acquisition, not production publication without the separate native
    physical-height/units/render proof.
    """
    projected = tuple(control for control in controls if control.projected_zone_height_mm is not None)
    if not projected:
        raise ValueError(f"{label}: saved projected audit requires projected controls")
    names = [control.annotation_name for control in projected]
    if len(set(names)) != len(names):
        raise ValueError(f"{label}: duplicate projected control annotation names")
    saved_path = Path(path).resolve()
    document_type = {".sldprt": 1, ".slddrw": 3}.get(saved_path.suffix.lower())
    if document_type is None or not saved_path.is_file():
        raise ValueError(f"{label}: saved audit requires an existing SLDPRT or SLDDRW")
    path_string = str(saved_path)
    app = _early_bound(adapter.swApp, "ISldWorks")
    model = app.GetOpenDocumentByName(path_string)
    if model is not None:
        _require_saved_identity(model, path_string, document_type, label)
        if document_type != 1:
            raise RuntimeError(f"{label}: finalize and close the drawing before saved audit")
        model = _early_bound(model, "IModelDoc2")
        if model.GetSaveFlag() is not False:
            raise RuntimeError(f"{label}: refuse to discard dirty or unreadable native part state")
        before = _read_controls(model, projected, phase="before_saved_reload", label=label)
        extension = _early_bound(model.Extension, "IModelDocExtension")
        # Official Reload Model example uses the same GetPathName as replacement.
        # Unlike that example, DiscardChanges is False: this reader never discards.
        status = extension.ReloadOrReplace(False, path_string, False, True)
        if _native_int(status, label=f"{label} reload status") != 0:
            raise RuntimeError(f"{label}: saved part reload failed with status {status}")
        model = app.GetOpenDocumentByName(path_string)
        if model is None:
            raise RuntimeError(f"{label}: saved part was not reacquired after reload")
        _require_saved_identity(model, path_string, document_type, label)
        model = _early_bound(model, "IModelDoc2")
        adapter.currentModel = model
        after = _read_controls(model, projected, phase="after_saved_reload", label=label)
        for old, new in zip(before, after, strict=True):
            unit_keys = (
                "length_unit_type_raw", "length_specific_unit_type_raw",
                "length_conversion_factor_raw", "length_unit_full_name_raw",
            )
            if any(old[key] != new[key] for key in unit_keys):
                raise RuntimeError(f"{label}: native document units changed across saved reload")
        return after

    try:
        # swOpenDocOptions_Silent | swOpenDocOptions_ReadOnly. Never OpenDoc7: a
        # spec may carry ViewOnly, which IsOpenedViewOnly cannot tell from a load
        # still in progress (test_failure_forensics). Errors and Warnings are
        # [out] parameters that pywin32 appends to the returned document.
        opened = app.OpenDoc6(path_string, document_type, 1 | 2, "", 0, 0)
        model, errors, warnings = opened if isinstance(opened, tuple) else (opened, 0, 0)
        errors = _native_int(errors, label=f"{label} open error")
        warnings = _native_int(warnings, label=f"{label} open warning")
        _telemetry.event(
            "native.projected_zone_saved_open", document_path=path_string,
            open_error_raw=errors, open_warning_raw=warnings,
        )
        if model is None or errors != 0:
            raise RuntimeError(f"{label}: saved native open failed ({errors=}, {warnings=})")
        _require_saved_identity(model, path_string, document_type, label)
        return _read_controls(model, projected, phase="after_saved_reopen", label=label)
    finally:
        # Also covers a failed OpenDoc6 that nevertheless loaded the target.
        opened = app.GetOpenDocumentByName(path_string)
        if opened is not None:
            opened = _early_bound(opened, "IModelDoc2")
            _require_saved_identity(opened, path_string, document_type, label)
            title = _native_string(opened.GetTitle(), label=f"{label} reopened title")
            app.CloseDoc(title)  # VT_VOID: no Boolean return to test.
            if app.GetOpenDocumentByName(path_string) is not None:
                raise RuntimeError(f"{label}: saved audit document did not close")
