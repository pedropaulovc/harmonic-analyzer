"""A drawing package's ``drawing_unit``: resolve it, and prove the finished
sheet prints in it.

The package is the drawing's own source, named by its dashed registry stem: a
part's ``cad/config/parts/<stem>.yaml`` row or an assembly's
``cad/config/assemblies/<stem>.yaml`` contract.  ``new_project_drawing`` reads
it to choose the SDK's ``set_units_inch`` or ``set_units_mm``; the part and
assembly stamping read the same field for the TOL_* rows
(``_part_properties.part_drawing_unit``, ``_assembly.assembly_drawing_unit``).

Build-graph note: a drawing closure that reaches this module reads its OWN
package's row (``"parts/*"``, narrowed by ``dodo._expand_parts_token``) and its
OWN assembly contract (``"assemblies/*"``, narrowed by
``dodo._expand_assembly_contracts_token``); callers pass their own package
literal (``test_dodo_recipe`` pins it), so a sibling's edit never re-keys them.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import _config
import _telemetry
from _assembly_contract import assembly_contract, contract_path
from _com import _early_bound
from _document_units import document_unit_mismatch, read_document_units
from _drawing_units import LEGACY_DRAWING_UNIT, DrawingUnit, declared_drawing_unit
from _part_properties import title_block_properties

# The title block's UNIT cell: SolidWorks' drawing-document unit property,
# which resolves "mm" on an MMGS document and "in" on an IPS one
# (cad/templates/README.md).
UNIT_OF_MEASURE_LINK = '$PRP:"UnitOfMeasure"'

_SW_NOTE = 6  # swAnnotationType_e.swNote


def declared_package_drawing_unit(package_name: str) -> DrawingUnit | None:
    """The unit ``package_name`` declares, or ``None`` when it declares none.

    An assembly's contract wins when one exists; otherwise the part registry
    row.  A package that is neither raises: a drawing that names its package
    must name a real one."""
    if contract_path(package_name).is_file():
        return assembly_contract(package_name).drawing_unit
    try:
        row = _config.parts(package_name)
    except KeyError:
        raise KeyError(
            f"drawing package {package_name!r} is neither a registered part "
            "nor an assembly contract"
        ) from None
    return declared_drawing_unit(f"parts/{package_name}", row)


def package_drawing_unit(package_name: str) -> DrawingUnit:
    """The unit ``package_name``'s sheet prints: its declaration, else the
    legacy millimetre."""
    declared = declared_package_drawing_unit(package_name)
    return LEGACY_DRAWING_UNIT if declared is None else declared


def carries_inch_rows(linked_properties: Mapping[str, str]) -> bool:
    """True when a linked model's TOL_* values are the inch sheet's rows: it
    was stamped as an inch package, whatever the drawing says about itself."""
    expected = title_block_properties(unit="in")
    return all(linked_properties.get(name) == text for name, text in expected.items())


def _unit_notes(draw: Any) -> list[tuple[str, str]]:
    """``(linked text, resolved text)`` of the active sheet's notes that link
    the UNIT cell (the sheet format's notes ride the sheet view)."""
    sheet_view = _early_bound(draw, "IDrawingDoc").GetFirstView()
    if sheet_view is None:
        raise RuntimeError("drawing sheet has no sheet view to read the UNIT cell from")
    found = []
    for annotation in _early_bound(sheet_view, "IView").GetAnnotations() or ():
        annotation = _early_bound(annotation, "IAnnotation")
        if annotation.GetType() != _SW_NOTE:
            continue
        specific = annotation.GetSpecificAnnotation()
        if specific is None:
            raise RuntimeError("sheet note has no INote")
        note = _early_bound(specific, "INote")
        raw = note.PropertyLinkedText
        if type(raw) is not str:
            raise RuntimeError(f"unreadable sheet note link {raw!r}")
        if UNIT_OF_MEASURE_LINK in raw:
            found.append((raw, str(note.GetText() or "")))
    return found


@_telemetry.traced("drawing.unit_proof", label_param="sheet_name")
def assert_sheet_prints_unit(
    draw: Any,
    *,
    package_name: str,
    unit: DrawingUnit,
    sheet_name: str,
    linked_model: Any,
    linked_properties: Mapping[str, str],
) -> dict[str, Any]:
    """Prove the ACTIVE sheet of ``draw`` prints ``package_name``'s ``unit``.

    Readbacks, each against the one selection: the drawing document's unit
    system and length unit (``_document_units``); the UNIT cell's resolved
    text (exactly one note links it; its text reads ``unit`` where the link
    stands); the linked model's TOL_* custom properties
    (``linked_properties``) equal ``title_block_properties(unit=unit)``; and,
    on an inch sheet, the linked model's own document units are IPS decimal
    inches.  The linked model is the referenced document as the drawing
    loaded it -- on a farm leaf, the restored saved artifact -- so that last
    readback is the persisted model's units, read without a reopen.
    Millimetre models keep their template units and are not checked.
    Records every measured value as a span event, then raises on any
    mismatch."""
    document = read_document_units(draw)
    document_mismatch = document_unit_mismatch(document, unit)
    model = read_document_units(linked_model) if unit == "in" else {}
    model_mismatch = document_unit_mismatch(model, unit) if unit == "in" else {}
    notes = _unit_notes(draw)
    unit_cell = [resolved for _raw, resolved in notes]
    unit_cell_expected = [raw.replace(UNIT_OF_MEASURE_LINK, unit) for raw, _ in notes]
    expected = title_block_properties(unit=unit)
    tolerance_mismatch = {
        name: (linked_properties.get(name), text)
        for name, text in expected.items()
        if linked_properties.get(name) != text
    }
    _telemetry.event(
        "drawing.unit_proof.readback",
        package=package_name,
        sheet=sheet_name,
        unit=unit,
        **{f"document_{name}": value for name, value in document.items()},
        **{f"model_{name}": value for name, value in model.items()},
        unit_cell=" | ".join(unit_cell),
        tolerance_rows=" | ".join(
            f"{name}={linked_properties.get(name)}" for name in expected
        ),
    )
    problems = []
    if document_mismatch:
        problems.append(f"drawing document units (got, want) {document_mismatch!r}")
    if model_mismatch:
        problems.append(f"linked model units (got, want) {model_mismatch!r}")
    if len(notes) != 1:
        problems.append(f"{len(notes)} notes link {UNIT_OF_MEASURE_LINK}, expected 1")
    elif unit_cell != unit_cell_expected:
        problems.append(
            f"UNIT cell reads {unit_cell!r}, expected {unit_cell_expected!r}"
        )
    if tolerance_mismatch:
        problems.append(f"linked TOL_* rows (got, want) {tolerance_mismatch!r}")
    if problems:
        raise RuntimeError(
            f"{package_name} sheet {sheet_name!r} does not print {unit!r}: "
            + "; ".join(problems)
        )
    return {
        "document": document,
        "model": model,
        "unit_cell": unit_cell[0],
        "tolerance_rows": {name: linked_properties[name] for name in expected},
    }


def assert_document_units_after_save(
    draw: Any, *, package_name: str, unit: DrawingUnit
) -> dict[str, int]:
    """Re-read the STILL-OPEN drawing document's units right after its
    SLDDRW/PDF save and record them, so a save that drifted the unit system
    does not go unseen.  This is not persisted proof: that is
    :func:`prove_saved_drawing_units`, which reopens the file.  Raises on a
    mismatch."""
    document = read_document_units(draw)
    _telemetry.event(
        "drawing.unit_proof.open_after_save",
        package=package_name,
        unit=unit,
        **{f"document_{name}": value for name, value in document.items()},
    )
    mismatch = document_unit_mismatch(document, unit)
    if mismatch:
        raise RuntimeError(
            f"{package_name}: open drawing document units after save (got, want) "
            f"{mismatch!r}"
        )
    return document


_SW_DOC_DRAWING = 3  # swDocumentTypes_e.swDocDRAWING
_SW_OPEN_SILENT_READ_ONLY = 1 | 2  # swOpenDocOptions_Silent | _ReadOnly


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _linked_view(draw: Any, sheet: Any) -> Any:
    """The view the active sheet's ``$PRPSHEET`` links read
    (``ISheet.CustomPropertyView``, set by ``finalize_drawing``)."""
    name = str(sheet.CustomPropertyView or "")
    view = _early_bound(draw, "IDrawingDoc").GetFirstView()  # the sheet view
    view = None if view is None else _early_bound(view, "IView").GetNextView()
    while view is not None:
        view = _early_bound(view, "IView")
        if str(view.GetName2()) == name:
            return view
        view = view.GetNextView()
    raise RuntimeError(f"saved sheet links property view {name!r}, which it lacks")


@_telemetry.traced("drawing.unit_proof.saved_reopen", label_param="package_name")
def prove_saved_drawing_units(
    adapter: Any, slddrw: Path, *, package_name: str, unit: DrawingUnit
) -> list[dict[str, Any]]:
    """Persisted proof: reopen the CLOSED, saved ``slddrw`` read-only and
    prove every sheet prints ``unit`` (``assert_sheet_prints_unit``: document
    units, UNIT cell, linked TOL_* values and, for inches, the linked model's
    units), then close it without saving.

    Bounded and read-only: ``OpenDoc6`` silent | read-only, one pass over the
    sheets, ``CloseDoc`` with no save, the file's SHA-256 identical before and
    after, and the session's previous current model restored.  Refuses a
    drawing that is still open -- reading the in-memory document would prove
    nothing about the file.  For explicitly declared packages only
    (``finalize_drawing``); the legacy fleet never pays the reopen.
    """
    path = slddrw.resolve()
    if not path.is_file():
        raise RuntimeError(f"{package_name}: saved drawing {path} is missing")
    path_string = str(path)
    before = _sha256(path)
    app = _early_bound(adapter.swApp, "ISldWorks")
    if app.GetOpenDocumentByName(path_string) is not None:
        raise RuntimeError(f"{package_name}: close {path.name} before its saved proof")
    previous_model = adapter.currentModel
    proofs: list[dict[str, Any]] = []
    try:
        opened = app.OpenDoc6(
            path_string, _SW_DOC_DRAWING, _SW_OPEN_SILENT_READ_ONLY, "", 0, 0
        )
        if not isinstance(opened, tuple) or len(opened) != 3:
            raise RuntimeError(f"{package_name}: saved OpenDoc6 returned {opened!r}")
        model, errors, warnings = opened
        _telemetry.event(
            "drawing.unit_proof.saved_open",
            package=package_name,
            open_error_raw=int(errors),
            open_warning_raw=int(warnings),
        )
        if model is None or errors != 0:
            raise RuntimeError(
                f"{package_name}: saved open failed ({errors=}, {warnings=})"
            )
        model = _early_bound(model, "IModelDoc2")
        actual = str(Path(str(model.GetPathName())).resolve())
        if (
            int(model.GetType()) != _SW_DOC_DRAWING
            or actual.casefold() != path_string.casefold()
        ):
            raise RuntimeError(
                f"{package_name}: saved reader acquired {actual!r} "
                f"(type {model.GetType()!r}), not {path_string!r}"
            )
        adapter.currentModel = model
        draw = _early_bound(model, "IDrawingDoc")
        sheet_names = tuple(draw.GetSheetNames() or ())
        if not sheet_names:
            raise RuntimeError(f"{package_name}: saved drawing has no sheets")
        for sheet_name in sheet_names:
            if not draw.ActivateSheet(sheet_name):
                raise RuntimeError(
                    f"{package_name}: cannot activate saved sheet {sheet_name!r}"
                )
            sheet = _early_bound(draw.GetCurrentSheet(), "ISheet")
            linked_model = _linked_view(model, sheet).ReferencedDocument
            if linked_model is None:
                raise RuntimeError(
                    f"{package_name}: saved sheet {sheet_name!r} links no loaded model"
                )
            linked_model = _early_bound(linked_model, "IModelDoc2")
            linked_properties = {
                name: str(linked_model.GetCustomInfoValue("", name) or "")
                for name in title_block_properties(unit=unit)
            }
            proofs.append(
                assert_sheet_prints_unit(
                    model,
                    package_name=package_name,
                    unit=unit,
                    sheet_name=f"saved {sheet_name}",
                    linked_model=linked_model,
                    linked_properties=linked_properties,
                )
            )
    finally:
        # Also covers a failed OpenDoc6 that nevertheless loaded the file.
        reopened = app.GetOpenDocumentByName(path_string)
        if reopened is not None:
            app.CloseDoc(str(_early_bound(reopened, "IModelDoc2").GetTitle()))
        adapter.currentModel = previous_model
    if app.GetOpenDocumentByName(path_string) is not None:
        raise RuntimeError(f"{package_name}: saved proof left {path.name} open")
    after = _sha256(path)
    _telemetry.event(
        "drawing.unit_proof.saved_bytes",
        package=package_name,
        sha256_before=before,
        sha256_after=after,
        sheets=len(proofs),
    )
    if after != before:
        raise RuntimeError(
            f"{package_name}: the saved proof changed {path.name}'s bytes"
        )
    return proofs
