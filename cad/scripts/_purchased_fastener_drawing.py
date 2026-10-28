"""Four-view purchased-part reference sheets, linked to the native source part.

Every view is hidden-lines-removed. Optional native supplier references use
explicit annotation margins reserved before fitting. Front/Top/Right share
the largest fitting standard scale; Isometric has its own fitting scale and
stays unannotated. All supplier dimensions are reference-only, not fabrication
controls or claims that nominal envelopes survive every physical feature.

Supplier sources are opened read-only and observed through view creation,
formatting, export and close, with a final SHA-256 guard on error paths too.
These checks detect mutation; read-only-at-open does not guarantee native source
preservation. Native outline fitting uses refreshed display geometry and records
each real candidate without replay; custom readers retain their own contract.

The footer, bottom-left above the border and left of the title block, reads
top to bottom: the part's own notes (installation, or a spring's acceptance
data), one general line, then ITEM (the catalogue designation in plain text,
passed by each drawing script), SUPPLIER and SKU (linked to the source part).
The title block alone gives material and finish (rule 2), so the supplier's
stock name, which restates the material, is read and checked but not printed.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from enum import StrEnum
from numbers import Real
from pathlib import Path
from typing import Any, Callable, Literal

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    iter_views,
    place_view,
    view_name,
)

from _com import _early_bound
import _config
from _custom_properties import apply_custom_properties
from _drawing_common import (
    TITLE_BLOCK_TOLERANCE_PROPERTIES,
    DrawingOutputs,
    _drawing_checkpoint,
    assert_asme_b_sheet,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_layout_audit import annotation_display
from _drawing_notes import add_property_linked_note, property_link
from _drawing_projection import model_point_in_view
from _drawing_registry import (
    DRAWING_TEMPLATES,
    DrawingLayout,
    DrawingSpec,
    layout_report_path,
)
from _drawing_scan import _zoomed_on
from _drawing_sheet_region import sheet_drawable_region
from _drawing_view_display import set_hidden_lines_removed
from _fastener_catalog import fastener
import _seat_forensics
import _telemetry

# Project-used scales, largest first, tried against actual native outlines;
# no catalogue dimension/axis heuristics.
_SCALES = ((8, 1), (5, 1), (4, 1), (2, 1), (1, 1), (1, 2), (1, 4), (1, 8))
_ISOMETRIC = "*Isometric"
_PROPERTIES = (
    "Number",
    "Revision",
    "Title",
    "Material",
    "Stock Name",
    "Supplier",
    "Supplier SKUs",
    *TITLE_BLOCK_TOLERANCE_PROPERTIES,
)

# Footer geometry, ASME B landscape (431.8 x 279.4), sheet metres.  The border
# is 12.7 mm in; the title block fills x >= 215.9 mm below y = 65.1 mm, so every
# footer row stops at _FOOTER_RIGHT.  Note y is the text's top edge; 3 mm text
# advances at most _LINE_PITCH a line.
_NOTE_X = 0.018
_VALUE_X = 0.052
_FOOTER_RIGHT = 0.2155
_LINE_PITCH = 0.0045
_FOOTER_ROWS = (("ITEM:", 0.044), ("SUPPLIER:", 0.034), ("SKU:", 0.024))
_GENERAL_Y = 0.054
# The general line's box bottom; the notes above it end at or over this.
_GENERAL_BOTTOM = _GENERAL_Y - 0.007
_NOTES_BOTTOM = _GENERAL_Y + 0.0015
# Footer notes stay within rule 7's four lines with the general line.
MAX_NOTE_LINES = 3
# One plain-text designation line: _VALUE_X.._FOOTER_RIGHT holds about 68
# characters of 3 mm text at the repo's widest 2.36 mm a character.
MAX_ITEM_CHARS = 64
_GENERAL_TEXT = {
    False: "PURCHASED PART, USED AS SUPPLIED. VIEWS ARE REFERENCE ONLY.",
    True: "PURCHASED PART, CUT AT ASSEMBLY PER NOTE ABOVE. VIEWS ARE REFERENCE ONLY.",
}
# The lowest caption of the bottom view row: clear of the title block's top
# (65.1 mm) and of the footer notes by _CAPTION_CLEARANCE.
_LOWEST_CAPTION_Y = 0.073
_CAPTION_CLEARANCE = 0.011
# A caption's top edge sits this far under its cell; its text hangs below.
_CAPTION_TO_CELL = 0.004
_CAPTION_BELOW = 0.006

# Synchronous annotation hook, after fitting; keys include the leading "*".
SupplierDimensions = Callable[[Any, dict[str, Any]], None]
# Per orthographic view: left, bottom, right, top in sheet metres.
SupplierMargins = Mapping[str, tuple[float, float, float, float]]


class NumberFit(StrEnum):
    """How a sheet prints its template's DWG. NO. note."""

    # The template's authored format, unmeasured.
    TEMPLATE = "template"
    # Measured once the link resolves; shrunk only when it runs into REV.
    SHRINK_TO_CELL = "shrink-to-cell"


# The landscape DWG. NO. cell: its exported rules (x = 308.351 / 372.310 mm,
# the REV divider; y = 19.969 / 35.906 mm) rounded inward, less the 1.2 mm the
# REV value keeps on its side of the divider.
_NUMBER_LIMIT = (0.3084, 0.0200, 0.3723 - 0.0012, 0.0359)
# Never smaller than the sheet's 3 mm notes.
_NUMBER_MIN_HEIGHT = 0.003
_NUMBER_HEIGHT_TOL = 1e-7
# INote.GetExtent is the note as displayed, floored to the window's pixels:
# the fitted landscape sheet reads in 0.4766 mm steps on the farm seats (the
# 8d9c8dbba box was 121 x 33 of them, as draw_dt_cone_swing_platform found).
# Every DWG. NO. readback is zoomed onto this square about the cell, a pixel
# there being about a tenth of a millimetre, and the fit aims this far inside
# the limit so that readback quantization cannot chase the hard guard.
_NUMBER_ZOOM_HALF = 0.040
_NUMBER_FIT_AIM = 0.0003
_NUMBER_CENTRE = (
    (_NUMBER_LIMIT[0] + _NUMBER_LIMIT[2]) / 2.0,
    (_NUMBER_LIMIT[1] + _NUMBER_LIMIT[3]) / 2.0,
)


@_telemetry.traced("drawing.purchased_source_hash")
def _source_file_sha256(source: Path) -> str:
    """Read source bytes without loading the native part or buffering the file."""
    with Path(source).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@_telemetry.traced("drawing.purchased_source_open", label_param="label")
def _open_supplier_source_read_only(adapter: Any, source: Path, *, label: str) -> Any:
    """Acquire the exact native part read-only; session teardown owns its close.

    OpenDoc6(FileName, Type, Options, Configuration, out Errors, out Warnings)
    returns (IModelDoc2, errors, warnings) through makepy. IsOpenedReadOnly(),
    GetType() and GetPathName() are methods, not dispatch properties.
    """
    source = Path(source).resolve()
    if source.suffix.lower() != ".sldprt" or not source.is_file():
        raise ValueError(
            f"{label}: supplier source must be an existing SLDPRT: {source}"
        )
    app = _early_bound(adapter.swApp, "ISldWorks")
    model = app.GetOpenDocumentByName(str(source))
    if model is None:
        # swDocPART=1; swOpenDocOptions_Silent=1 | ReadOnly=2. As in
        # _native_projected_zone, the two native [out] integers follow retval.
        opened = app.OpenDoc6(str(source), 1, 1 | 2, "", 0, 0)
        if not isinstance(opened, tuple) or len(opened) != 3:
            raise RuntimeError(
                f"{label}: unreadable supplier native open result: {opened!r}"
            )
        model, errors, warnings = opened
        if type(errors) is not int or type(warnings) is not int:
            raise RuntimeError(
                f"{label}: unreadable supplier open status: {errors!r}, {warnings!r}"
            )
        _telemetry.event(
            "drawing.purchased_source_open",
            document_path=str(source),
            open_error_raw=errors,
            open_warning_raw=warnings,
        )
        if model is None or errors != 0:
            raise RuntimeError(
                f"{label}: supplier read-only open failed ({errors=}, {warnings=})"
            )
    model = _early_bound(model, "IModelDoc2")
    loaded = app.GetOpenDocumentByName(str(source))
    if loaded is None:
        raise RuntimeError(
            f"{label}: supplier source was not found in the loaded documents"
        )
    loaded = _early_bound(loaded, "IModelDoc2")
    for document in (model, loaded):
        kind = document.GetType()
        path = document.GetPathName()
        if type(kind) is not int or kind != 1:
            raise RuntimeError(
                f"{label}: supplier source is not a native part: {kind!r}"
            )
        if type(path) is not str or not path.strip() or Path(path).resolve() != source:
            raise RuntimeError(
                f"{label}: supplier source path identity mismatch: {path!r}"
            )
        if document.IsOpenedReadOnly() is not True:
            raise RuntimeError(f"{label}: supplier source must be opened read-only")
    identity = app.IsSame(model, loaded)
    if type(identity) is not int or identity != 1:  # swObjectSame=1, not VT_BOOL.
        raise RuntimeError(
            f"{label}: supplier loaded document identity mismatch: {identity!r}"
        )
    # io.open_model binds IModelDoc2 then assigns currentModel; it has no other
    # model-state assignment. Do not guess private adapter fields or ActiveDoc.
    adapter.currentModel = model
    current = adapter.currentModel
    if current is None:
        raise RuntimeError(f"{label}: adapter lost the supplier source document")
    for document in (model, loaded):
        identity = app.IsSame(current, document)
        if type(identity) is not int or identity != 1:
            raise RuntimeError(
                f"{label}: adapter supplier source identity mismatch: {identity!r}"
            )
    return model


def _supplier_source_checkpoint(
    adapter: Any,
    source: Path,
    source_model: Any,
    expected_sha256: str,
    *,
    label: str,
    evidence: list[dict[str, Any]],
    configuration: str | None = None,
) -> Callable[[str], None]:
    """Observe the original native part, not just a same-named loaded document.

    Read-only-at-open is not a persistence guarantee. Dirty presentation is
    diagnostic only, as is comparison between the different source/drawing
    documents; positive native identities and actual document types stay strict.
    During view creation/selection, record actual configurations but enforce the
    requested configuration only after the existing selection rebuild. After an
    attempted close, never dereference old drawing/view handles; a missing
    loaded source is allowed only there, and its on-disk hash is still required.
    """
    source = Path(source).resolve()
    drawing_model = None

    def checkpoint(phase: str) -> None:
        nonlocal drawing_model
        faults: list[str] = []
        row: dict[str, Any] = {
            "phase": phase,
            "source_path": str(source),
            "expected_sha256": expected_sha256,
            "requested_configuration": configuration,
            "errors": [],
            "views": [],
        }

        def probe(
            state: dict[str, Any],
            key: str,
            getter: Callable[[], Any],
            *,
            diagnostic: bool = False,
        ) -> Any:
            try:
                value = getter()
                if value is not None and type(value) not in (str, int, bool):
                    raise TypeError(f"non-scalar native result: {type(value).__name__}")
                state[key] = value
                return value
            except BaseException as error:
                state[key] = None
                row["errors"].append(
                    {
                        "field": key,
                        "type": type(error).__name__,
                        "message": str(error),
                    }
                )
                if not diagnostic:
                    faults.append(f"unreadable {key}")
                return None

        def native(getter: Callable[[], Any], interface: str, field: str) -> Any:
            try:
                value = getter()
                if value is None:
                    return None
                return _early_bound(value, interface)
            except BaseException as error:
                row["errors"].append(
                    {
                        "field": field,
                        "type": type(error).__name__,
                        "message": str(error),
                    }
                )
                faults.append(f"unreadable {field}")
                return None

        def identity(state: dict[str, Any], key: str, left: Any, right: Any) -> None:
            value = probe(state, key, lambda: app.IsSame(left, right))
            if type(value) is not int or value != 1:
                faults.append(f"{key} native identity mismatch")

        def document(model: Any, *, source_part: bool) -> dict[str, Any]:
            state: dict[str, Any] = {"present": model is not None}
            if model is None:
                faults.append("missing native document")
                return state
            path = probe(state, "path", lambda: model.GetPathName())
            kind = probe(state, "type", lambda: model.GetType())
            ro = probe(state, "read_only", lambda: model.IsOpenedReadOnly())
            probe(state, "save_flag", lambda: model.GetSaveFlag(), diagnostic=True)
            if type(kind) is not int or kind != (1 if source_part else 3):
                faults.append("native document type mismatch")
            if type(path) is not str:
                faults.append("unreadable native document path")
            else:
                resolved = probe(
                    state,
                    "resolved_path",
                    lambda: str(Path(path).resolve()) if path.strip() else "",
                )
                if source_part and resolved != str(source):
                    faults.append("supplier source path mismatch")
                elif not source_part and resolved == str(source):
                    faults.append("drawing receiver has supplier source path")
            if source_part and ro is not True:
                faults.append("supplier source is not read-only")
            return state

        current_sha256 = probe(
            row, "current_sha256", lambda: _source_file_sha256(source)
        )
        if current_sha256 != expected_sha256:
            faults.append("supplier source part bytes changed or unreadable")
        app = native(lambda: adapter.swApp, "ISldWorks", "application")
        loaded = native(
            lambda: app.GetOpenDocumentByName(str(source)),
            "IModelDoc2",
            "loaded_source",
        )
        after_close = phase == "after_drawing_close"
        row["loaded_source_present"] = loaded is not None
        if loaded is not None or not after_close:
            original = native(lambda: source_model, "IModelDoc2", "original_source")
            row["original_source"] = document(original, source_part=True)
            row["loaded_source"] = document(loaded, source_part=True)
            if original is not None and loaded is not None:
                identity(row, "original_loaded_identity", original, loaded)
        if after_close:
            row["drawing_observation"] = "not_dereferenced_after_close_attempt"
        else:
            current = native(
                lambda: adapter.currentModel, "IModelDoc2", "drawing_receiver"
            )
            row["drawing_receiver"] = document(current, source_part=False)
            if current is not None:
                if drawing_model is None and phase == "after_new_document":
                    drawing_model = current
                if drawing_model is None:
                    faults.append("missing original drawing receiver")
                else:
                    identity(
                        row["drawing_receiver"],
                        "original_drawing_identity",
                        current,
                        drawing_model,
                    )
                probe(
                    row["drawing_receiver"],
                    "original_source_identity",
                    lambda: app.IsSame(current, source_model),
                    diagnostic=True,
                )
                try:
                    # The purchased sheet is single-sheet. Read actual live views,
                    # not the creation list (which can hide a replacement).
                    views = list(iter_views(adapter))
                except BaseException as error:
                    views = []
                    faults.append("unreadable live drawing views")
                    row["errors"].append(
                        {
                            "field": "views",
                            "type": type(error).__name__,
                            "message": str(error),
                        }
                    )
                for raw_view in views:
                    view = native(lambda: raw_view, "IView", "view")
                    state: dict[str, Any] = {}
                    row["views"].append(state)
                    if view is None:
                        faults.append("missing native view")
                        continue
                    for key, getter in (
                        ("orientation", lambda: view.GetOrientationName()),
                        ("name", lambda: view.GetName2()),
                        ("source_path", lambda: view.GetReferencedModelName()),
                        ("configuration", lambda: view.ReferencedConfiguration),
                    ):
                        value = probe(state, key, getter)
                        if type(value) is not str or not value.strip():
                            faults.append(f"unreadable view {key}")
                    path = state["source_path"]
                    if type(path) is str:
                        resolved = probe(
                            state,
                            "resolved_source_path",
                            lambda: str(Path(path).resolve()),
                        )
                        if resolved != str(source):
                            faults.append("view source path mismatch")
                    pending = phase.startswith(
                        (
                            "before_create_view:",
                            "after_create_view:",
                            "after_select_configuration:",
                        )
                    )
                    state["configuration_selection_pending"] = pending
                    if (
                        configuration is not None
                        and not pending
                        and state["configuration"] != configuration
                    ):
                        faults.append("view source configuration mismatch")
                    referenced = native(
                        lambda: view.ReferencedDocument,
                        "IModelDoc2",
                        "referenced_document",
                    )
                    state["referenced_document"] = document(
                        referenced, source_part=True
                    )
                    if referenced is not None:
                        identity(
                            state, "original_source_identity", referenced, source_model
                        )
                        if loaded is not None:
                            identity(
                                state, "loaded_source_identity", referenced, loaded
                            )
        row["failures"] = faults
        evidence.append(row)
        # Record before refusing; a diagnostic emission must not erase the row.
        try:
            _telemetry.event(
                "drawing.purchased_source_checkpoint",
                phase=phase,
                source_state=json.dumps(row, sort_keys=True),
            )
        except BaseException as error:
            if not faults:
                raise
            row["errors"].append(
                {
                    "field": "telemetry",
                    "type": type(error).__name__,
                    "message": str(error),
                }
            )
        if faults:
            raise RuntimeError(
                f"{label}: source checkpoint {phase}: {'; '.join(faults)}"
            )

    return checkpoint


def _retain_supplier_source_failure(
    spec: DrawingSpec, error: BaseException, evidence: list[dict[str, Any]]
) -> None:
    """Retain already-exported outputs only; never SaveAs a failing source graph."""
    try:
        paths = spec.outputs
        _seat_forensics.capture_com_failure(
            None,
            f"{spec.artifact_stem}-source-lifecycle",
            str(error),
            exception=error,
            retained_artifacts={
                "slddrw": paths["slddrw"],
                "pdf": paths["pdf"],
                "png": paths["png"],
                "layout_json": layout_report_path(spec.artifact_stem),
            },
            source_path=str(spec.source),
            source_lifecycle=evidence,
        )
    except BaseException as capture_error:
        if capture_error is not error:
            error.add_note(
                "source lifecycle capture also failed: "
                f"{type(capture_error).__name__}: {capture_error}"
            )
    raise error


def _box(
    values: Any, *, label: str, kind: Literal["view", "note"] = "view"
) -> tuple[float, float, float, float]:
    """Decode documented IView.GetOutline / INote.GetExtent sheet coordinates."""
    coordinates = tuple(float(value) for value in (values or ()))
    expected = 6 if kind == "note" else 4
    if len(coordinates) != expected or not all(map(math.isfinite, coordinates)):
        raise RuntimeError(f"{label}: invalid native extent {coordinates!r}")
    if kind == "note":
        coordinates = (coordinates[0], coordinates[1], coordinates[3], coordinates[4])
    if coordinates[0] >= coordinates[2] or coordinates[1] >= coordinates[3]:
        raise RuntimeError(f"{label}: empty or inverted native extent {coordinates!r}")
    return coordinates


def _inside(box: tuple[float, ...], container: tuple[float, ...]) -> bool:
    return (
        box[0] >= container[0]
        and box[1] >= container[1]
        and box[2] <= container[2]
        and box[3] <= container[3]
    )


def _rebuild(draw: Any, *, phase: str) -> None:
    if not draw.EditRebuild3():
        raise RuntimeError(f"purchased drawing rebuild failed: {phase}")


def note_lines(notes: str, *, label: str) -> tuple[str, ...]:
    """The footer note's lines, held to rule 7's budget beside the general line."""
    lines = tuple(line for line in notes.strip().splitlines() if line.strip())
    if len(lines) > MAX_NOTE_LINES:
        raise ValueError(
            f"{label}: purchased-sheet notes run {len(lines)} lines; "
            f"at most {MAX_NOTE_LINES} fit beside the general line (rule 7)"
        )
    return lines


def check_item(item: str, *, label: str) -> str:
    """One plain-text catalogue designation line that fits the ITEM row."""
    text = item.strip()
    if not text or "\n" in text or len(text) > MAX_ITEM_CHARS:
        raise ValueError(
            f"{label}: ITEM must be one line of 1-{MAX_ITEM_CHARS} characters: {item!r}"
        )
    return text


def _supplier_data_lines(data: Sequence[str], *, label: str) -> tuple[str, ...]:
    """Source operating/suitability data, not free-text fabrication dimensions."""
    if isinstance(data, str):
        raise ValueError(f"{label}: supplier_data must contain separate lines")
    lines = tuple(data)
    if any(
        not isinstance(line, str)
        or not line.strip()
        or "\n" in line
        or "\r" in line
        or len(line) > MAX_ITEM_CHARS
        for line in lines
    ):
        raise ValueError(
            f"{label}: supplier operating data must fit single footer lines"
        )
    return ("SUPPLIER OPERATING DATA (REFERENCE):", *lines) if lines else ()


def footer_top(notes: str, *, label: str, supplier_data: Sequence[str] = ()) -> float:
    """The top edge of installation notes and separate supplier operating data."""
    lines = note_lines(notes, label=label)
    data = _supplier_data_lines(supplier_data, label=label)
    if not lines and not data:
        return _GENERAL_Y
    gap = _LINE_PITCH if lines and data else 0.0
    return _NOTES_BOTTOM + (len(lines) + len(data)) * _LINE_PITCH + gap + 0.001


def view_band_bottom(
    notes: str, *, label: str, supplier_data: Sequence[str] = ()
) -> float:
    """Bottom-row captions clear the complete footer and title block."""
    return max(
        footer_top(notes, label=label, supplier_data=supplier_data)
        + _CAPTION_CLEARANCE,
        _LOWEST_CAPTION_Y,
    )


def _cell(
    name: str, x0: float, y0: float, x1: float, y1: float
) -> tuple[str, tuple[float, float], tuple[float, float, float, float]]:
    return (name, ((x0 + x1) / 2, (y0 + y1) / 2), (x0, y0, x1, y1))


def fastener_view_cells(
    caption_y: float, *, layout: Literal["standard", "supplier_top", "tall_top"] = "standard"
) -> tuple:
    """Third-angle Front/Top/Right with the Isometric upper right.

    Front and Right fill the band from their captions (``caption_y``) up to the
    Top/Isometric captions; Top and Isometric fill the band under the border.
    The Isometric's cell reaches 6 mm lower, its caption ending on the Right
    cell's top, so a 1:1 pictorial of a long part (the 67 mm keeper chain)
    is not shrunk to 1:2, where small round features show their facets.
    ``supplier_top`` has 70 mm: two 26 mm annotation lanes leave 18 mm for
    its native outline. ``tall_top`` gives 96 mm. Both lower the bottom-row
    cells and Isometric together without changing the standard layout.
    """
    if layout not in ("standard", "supplier_top", "tall_top"):
        raise ValueError(f"unknown purchased fastener view layout: {layout!r}")
    bottom = caption_y + _CAPTION_TO_CELL
    if layout == "tall_top":
        row_top, top_bottom, isometric_bottom = 0.150, 0.166, 0.160
    elif layout == "supplier_top":
        row_top, top_bottom, isometric_bottom = 0.176, 0.192, 0.186
    else:
        row_top, top_bottom, isometric_bottom = 0.182, 0.198, 0.192
    return (
        _cell("*Front", 0.025, bottom, 0.205, row_top),
        _cell("*Top", 0.025, top_bottom, 0.205, 0.262),
        _cell("*Right", 0.225, bottom, 0.405, row_top),
        _cell(_ISOMETRIC, 0.225, isometric_bottom, 0.415, 0.262),
    )


def spring_view_cells(caption_y: float) -> tuple:
    """Long coils: wide Front/Top, a narrow end view and a tall Isometric column."""
    bottom = caption_y + _CAPTION_TO_CELL
    return (
        _cell("*Front", 0.015, bottom, 0.207, 0.150),
        _cell("*Top", 0.015, 0.168, 0.207, 0.262),
        _cell("*Right", 0.212, bottom, 0.262, 0.150),
        _cell(_ISOMETRIC, 0.270, bottom, 0.418, 0.262),
    )


def supplier_fit_cells(cells: tuple, margins: SupplierMargins, *, label: str) -> tuple:
    """Reserve annotation lanes before measuring native candidate scales."""
    orientations = {name for name, _, _ in cells}
    if not margins or set(margins) - orientations or _ISOMETRIC in margins:
        raise ValueError(
            f"{label}: supplier margins must name actual annotated orthographic cells"
        )
    fitted = []
    for name, center, cell in cells:
        if name not in margins:
            fitted.append((name, center, cell))
            continue
        padding = tuple(float(value) for value in margins[name])
        if (
            len(padding) != 4
            or not all(math.isfinite(value) and value >= 0.0 for value in padding)
            or not any(padding)
        ):
            raise ValueError(
                f"{label} {name}: supplier margins must be four nonnegative metre values"
            )
        left, bottom, right, top = padding
        inset = (cell[0] + left, cell[1] + bottom, cell[2] - right, cell[3] - top)
        if inset[0] >= inset[2] or inset[1] >= inset[3]:
            raise ValueError(
                f"{label} {name}: supplier margins leave no geometry space"
            )
        fitted.append(_cell(name, *inset))
    return tuple(fitted)


@_telemetry.traced("drawing.supplier_view_cell", label_param="label")
def assert_supplier_view_fits(
    adapter: Any, view: Any, cell: tuple[float, float, float, float], *, label: str
) -> None:
    """Read settled native view/dimension/note ink inside its outer cell."""
    view = _early_bound(view, "IView")
    outline = _box(view.GetOutline(), label=label)
    if not _inside(outline, cell):
        raise RuntimeError(
            f"{label}: settled supplier view leaves its cell: {outline!r}"
        )
    assert_supplier_annotations_fit(adapter, view, cell, label=label)


@_telemetry.traced("drawing.supplier_annotations_cell", label_param="label")
def assert_supplier_annotations_fit(
    adapter: Any, view: Any, cell: tuple[float, float, float, float], *, label: str
) -> None:
    """Read settled native dimension/note ink independently of the view outline."""
    from _layout_audit import display_box

    view = _early_bound(view, "IView")
    display = view.GetFirstDisplayDimension6()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        raw_dimension = display.GetDimension2(0)
        if raw_dimension is None:
            raise RuntimeError(
                f"{label}: supplier annotation lost its native dimension"
            )
        native = _early_bound(raw_dimension, "IDimension")
        identity = str(native.FullName)
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        if (
            int(annotation.OwnerType) != 0
            or annotation.Owner is None
            or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
            or int(annotation.Visible) != 1
            or annotation.IsDangling()
            or display.GetOverride()
            or not display.ShowDimensionValue
        ):
            raise RuntimeError(
                f"{label} {identity}: unsound supplier annotation owner/value"
            )
        geometry, refused = annotation_display(adapter, annotation)
        if refused or not geometry.get("texts"):
            raise RuntimeError(
                f"{label} {identity}: unreadable settled native dimension ink: {refused!r}"
            )
        ink = display_box(geometry)
        if ink is None:
            raise RuntimeError(f"{label} {identity}: supplier dimension draws no ink")
        bounds = (ink.xmin, ink.ymin, ink.xmax, ink.ymax)
        if not _inside(bounds, cell):
            raise RuntimeError(
                f"{label} {identity}: supplier dimension leaves its cell/caption space: "
                f"ink={bounds!r}, cell={cell!r}"
            )
        display = display.GetNext5()
    for raw_annotation in view.GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 6:  # swNote
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        bounds = _box(note.GetExtent(), label=f"{label} note", kind="note")
        if not _inside(bounds, cell):
            raise RuntimeError(f"{label}: supplier note leaves its cell: {bounds!r}")


@_telemetry.traced("drawing.purchased_supplier_layout", label_param="label")
def _assert_supplier_layout(
    adapter: Any,
    cells: tuple,
    *,
    label: str,
    margins: SupplierMargins,
    scales: dict[str, tuple[int, int]],
    origins: dict[str, tuple[float, float]],
    sources: dict[str, tuple[str, str]],
    sheet_notes: Sequence[tuple],
) -> None:
    """Reacquire after the final rebuild; no refitting or repair in this guard."""
    actual = list(iter_views(adapter))
    views = {
        str(view.GetOrientationName()): _early_bound(view, "IView") for view in actual
    }
    if len(actual) != len(cells) or set(views) != {name for name, _, _ in cells}:
        raise RuntimeError(f"{label}: supplier layout lost its four native view cells")
    for name, _, cell in cells:
        view = views[name]
        source = (
            str(Path(view.GetReferencedModelName()).resolve()),
            str(view.ReferencedConfiguration),
        )
        if source != sources[name]:
            raise RuntimeError(
                f"{label} {name}: supplier view changed source/configuration"
            )
        if tuple(view.ScaleRatio) != scales[name] or view.UseSheetScale != 0:
            raise RuntimeError(
                f"{label} {name}: supplier callback changed fitted scale"
            )
        view.UpdateViewDisplayGeometry()
        origin = model_point_in_view(
            adapter, view, (0.0, 0.0, 0.0), label=f"{label} {name} settled origin"
        )
        if not all(map(math.isfinite, origin + origins[name])) or any(
            abs(actual - expected) > 1e-6
            for actual, expected in zip(origin, origins[name], strict=True)
        ):
            raise RuntimeError(
                f"{label} {name}: supplier callback moved the fitted view"
            )
        if (view.GetFirstDisplayDimension6() is not None) != (name in margins):
            raise RuntimeError(
                f"{label} {name}: actual supplier dimensions do not match reserved views"
            )
        assert_supplier_view_fits(adapter, view, cell, label=f"{label} {name}")
    for note, text, resolved, cell in sheet_notes:
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        bounds = _box(note.GetExtent(), label=f"{label} {text}", kind="note")
        if (
            int(annotation.OwnerType) != 1
            or note.PropertyLinkedText != text
            or note.GetText().replace("\r\n", "\n") != resolved
            or not _inside(bounds, cell)
        ):
            raise RuntimeError(
                f"{label}: settled caption/footer changed owner/text/space: {text!r}"
            )


def _custom_fit_bounds(raw: Any, *, label: str) -> tuple[float, ...]:
    """Fail closed on custom geometry while allowing a one-dimensional extent."""
    try:
        values = tuple(raw)
    except TypeError as exc:
        raise RuntimeError(f"{label}: invalid custom geometry bounds: {raw!r}") from exc
    if len(values) != 4 or any(
        not isinstance(value, Real) or isinstance(value, bool) for value in values
    ):
        raise RuntimeError(f"{label}: invalid custom geometry bounds: {raw!r}")
    bounds = tuple(float(value) for value in values)
    if (
        not all(map(math.isfinite, bounds))
        or bounds[0] > bounds[2]
        or bounds[1] > bounds[3]
        or (bounds[0] == bounds[2] and bounds[1] == bounds[3])
    ):
        raise RuntimeError(f"{label}: invalid custom geometry bounds: {raw!r}")
    return bounds


def _refreshed_native_fit_bounds(
    view: Any, *, label: str
) -> tuple[tuple[float, ...], dict[str, Any]]:
    outlines: dict[str, Any] = {}
    try:
        outlines["outline_before_refresh_m"] = _box(view.GetOutline(), label=label)
    except Exception as error:
        outlines["outline_before_refresh_error"] = repr(error)
    # VT_VOID: refresh has no Boolean result. Only its validated outline fits.
    view.UpdateViewDisplayGeometry()
    box = _box(view.GetOutline(), label=label)
    outlines["outline_after_refresh_m"] = box
    return box, outlines


def _fit_group(
    draw: Any,
    members: list[tuple[Any, tuple]],
    *,
    read_bounds: Callable[[Any, str], tuple[float, float, float, float]] | None = None,
) -> tuple[int, int]:
    """The largest standard scale at which every member's bounds fit its cell.

    Native outlines include fixed sheet-space padding, so scaling a 1:1 outline
    can reject a larger view that actually fits; measure each standard scale.
    Only the native-outline path refreshes display geometry before measuring;
    its post-refresh outline selects the scale. Custom readers retain ownership
    of their geometry refresh and return four finite numeric coordinates,
    ordered with at least one positive extent (one-dimensional is allowed).
    """

    def record(
        view: Any,
        name: str,
        center: tuple,
        cell: tuple,
        box: tuple,
        *,
        scale: tuple[int, int],
        phase: str,
        reason: str,
        outlines: dict[str, Any],
    ) -> None:
        width, height = box[2] - box[0], box[3] - box[1]
        state: dict[str, Any] = {
            "view_key": name,
            "requested_scale": scale,
            "phase": phase,
            "reason": reason,
            "bounds_kind": "native_outline" if read_bounds is None else "custom",
            "fit_bounds_m": box,
            "cell_m": cell,
            "cell_center_m": center,
            "width_m": width,
            "height_m": height,
            "width_excess_m": width - (cell[2] - cell[0]),
            "height_excess_m": height - (cell[3] - cell[1]),
            **outlines,
        }
        errors = {}
        for key, getter in (
            ("actual_scale_ratio", lambda: tuple(view.ScaleRatio)),
            ("use_sheet_scale", lambda: view.UseSheetScale),
            ("view_name", lambda: view.GetName2()),
            ("orientation", lambda: view.GetOrientationName()),
            ("source_path", lambda: view.GetReferencedModelName()),
            ("configuration", lambda: view.ReferencedConfiguration),
            ("position_m", lambda: tuple(view.Position)),
        ):
            try:
                state[key] = getter()
            except Exception as error:
                errors[key] = repr(error)
        if errors:
            state["metadata_errors"] = errors
        if phase == "postcenter":
            state.update(
                center_error_m=(
                    (box[0] + box[2]) / 2 - center[0],
                    (box[1] + box[3]) / 2 - center[1],
                ),
                containment_excess_m={
                    "left": cell[0] - box[0],
                    "bottom": cell[1] - box[1],
                    "right": box[2] - cell[2],
                    "top": box[3] - cell[3],
                },
            )
        _telemetry.event("drawing.purchased_fit_candidate", **state)

    for scale in _SCALES:
        with _telemetry.span(
            "drawing.purchased_scale_candidate", scale=f"{scale[0]}:{scale[1]}"
        ):
            for view, _ in members:
                view.UseSheetScale = 0
                view.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
            _rebuild(draw, phase="apply view scale")
            bounds = []
            oversized = False
            for view, (name, center, cell) in members:
                if read_bounds is None:
                    box, outlines = _refreshed_native_fit_bounds(view, label=name)
                else:
                    box = _custom_fit_bounds(read_bounds(view, name), label=name)
                    outlines = {}
                bounds.append(box)
                too_large = (
                    box[2] - box[0] > cell[2] - cell[0]
                    or box[3] - box[1] > cell[3] - cell[1]
                )
                record(
                    view,
                    name,
                    center,
                    cell,
                    box,
                    scale=scale,
                    phase="precenter",
                    reason="precenter_size" if too_large else "accepted",
                    outlines=outlines,
                )
                oversized = oversized or too_large
            if oversized:
                continue
            for (view, (name, center, _)), box in zip(members, bounds, strict=True):
                position = tuple(float(value) for value in view.Position)
                if len(position) != 2 or not all(map(math.isfinite, position)):
                    raise RuntimeError(
                        f"{name}: invalid native view position {position!r}"
                    )
                # Center the actual bounds, not a presumed model-origin/axis.
                target = [
                    position[0] + center[0] - (box[0] + box[2]) / 2,
                    position[1] + center[1] - (box[1] + box[3]) / 2,
                ]
                if not view.SetViewPosition(double_array(target), False):
                    raise RuntimeError(f"{name}: failed to position purchased view")
            _rebuild(draw, phase="center purchased views")
            fits = True
            for view, (name, center, cell) in members:
                ratio = tuple(float(value) for value in view.ScaleRatio)
                if (
                    ratio != tuple(float(value) for value in scale)
                    or view.UseSheetScale != 0
                ):
                    raise RuntimeError(
                        f"{name}: independent view scale did not persist: {ratio!r}"
                    )
                if read_bounds is None:
                    box, outlines = _refreshed_native_fit_bounds(view, label=name)
                else:
                    box = _custom_fit_bounds(read_bounds(view, name), label=name)
                    outlines = {}
                centered = (
                    abs((box[0] + box[2]) / 2 - center[0]) <= 1e-6
                    and abs((box[1] + box[3]) / 2 - center[1]) <= 1e-6
                )
                contained = _inside(box, cell)
                record(
                    view,
                    name,
                    center,
                    cell,
                    box,
                    scale=scale,
                    phase="postcenter",
                    reason="accepted"
                    if centered and contained
                    else "postcenter_containment",
                    outlines=outlines,
                )
                if not centered:
                    raise RuntimeError(f"{name}: native view failed to center: {box!r}")
                fits = fits and contained
            if fits:
                return scale
    names = ", ".join(name for _, (name, _, _) in members)
    raise RuntimeError(f"purchased part has no project-standard scale fitting {names}")


@_telemetry.traced("drawing.purchased_fit_views")
def _fit_views(draw: Any, views: list[Any], cells: tuple) -> dict[str, tuple[int, int]]:
    """Per-view scales: one shared by the orthographic views, one for the Isometric."""
    _rebuild(draw, phase="initial view extents")
    for view, (name, _, _) in zip(views, cells, strict=True):
        ratio = tuple(float(value) for value in view.ScaleRatio)
        if len(ratio) != 2 or ratio != (1.0, 1.0):
            raise RuntimeError(
                f"{name}: initial 1:1 view scale did not persist: {ratio!r}"
            )
    members = list(zip(views, cells, strict=True))
    scales: dict[str, tuple[int, int]] = {}
    for group in (
        [member for member in members if member[1][0] != _ISOMETRIC],
        [member for member in members if member[1][0] == _ISOMETRIC],
    ):
        if not group:
            continue
        scale = _fit_group(draw, group)
        scales.update({cell[0]: scale for _, cell in group})
    return scales


@_telemetry.traced("drawing.purchased_center_marks")
def _center_marks_without_lines(views: list[Any], cells: tuple) -> dict[str, int]:
    """Drop the extension lines of every template-inserted centre mark.

    The template auto-inserts a centre mark on each view of a circle, its arms
    scaled with the view (8:1 washers: arms ~11 mm past the rim, outside the
    view outline the cells fit). Captions sit on the view's vertical axis, so
    those arms struck the FRONT caption and the TOP caption above it (r3
    review, rule 14). The centre cross stays; the reference views need no
    more. Even the cross is scaled (8:1 pins: ~20 mm arms), so the count of
    marks per view tells the caption pass which views to leave at the cell
    floor.
    """
    counts: dict[str, int] = {}
    for view, (name, _, _) in zip(views, cells, strict=True):
        counts[name] = 0
        mark = view.GetFirstCenterMark2()
        while mark is not None:
            mark = _early_bound(mark, "ICenterMark")
            mark.UseDocDisplaySettings = False
            mark.ShowLines = False
            if mark.UseDocDisplaySettings or mark.ShowLines:
                raise RuntimeError(
                    f"{name}: centre mark still shows its extension lines"
                )
            counts[name] += 1
            mark = mark.GetNext()
    return counts


@_telemetry.traced("drawing.purchased_note")
def _literal_note(adapter: Any, text: str, x: float, y: float) -> Any:
    note = add_note(adapter, text, x, y)
    if note is None:
        raise RuntimeError(f"failed to insert purchased drawing note {text!r}")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"purchased drawing note has no text format: {text!r}")
    text_format.CharHeight = 0.003
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size purchased drawing note {text!r}")
    if not annotation.SetPosition(x, y, 0.0):
        raise RuntimeError(f"failed to position purchased drawing note {text!r}")
    return note


@_telemetry.traced("drawing.purchased_title_block")
def _purchased_title_block(
    adapter: Any,
    draw: Any,
    *,
    material: str,
    finish: str,
    material_property: str = "Material",
) -> list[tuple[Any, str, str]]:
    """Retarget this drawing's material/finish cells, never the saved template."""
    apply_custom_properties(adapter, {"Finish": finish}, model=draw)
    ddoc = _early_bound(draw, "IDrawingDoc")
    sheet_view = ddoc.GetFirstView()
    if sheet_view is None:
        raise RuntimeError("purchased drawing template has no sheet view")
    sheet_view = _early_bound(sheet_view, "IView")
    replacements = {
        property_link("Material"): (property_link(material_property), material),
        property_link("Finish"): ('$PRP:"Finish"', finish),
    }
    matched = {token: 0 for token in replacements}
    notes = []
    for annotation in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(annotation, "IAnnotation")
        if annotation.GetType() != 6:  # swAnnotationType_e.swNote
            continue
        specific = annotation.GetSpecificAnnotation()
        if specific is None:
            raise RuntimeError("purchased title-block note has no INote")
        note = _early_bound(specific, "INote")
        raw = str(note.PropertyLinkedText)
        linked_text = raw
        resolved_text = raw
        for token, (replacement, value) in replacements.items():
            occurrences = raw.count(token)
            if occurrences:
                matched[token] += occurrences
                linked_text = linked_text.replace(token, replacement)
                resolved_text = resolved_text.replace(token, value)
        if resolved_text == raw:
            continue
        # Preserve the existing note, annotation formatting and all surrounding
        # label text; only these exact property-link tokens change ownership.
        if linked_text != raw:
            note.PropertyLinkedText = linked_text
        if note.PropertyLinkedText != linked_text:
            raise RuntimeError(f"purchased title-block link did not persist: {raw!r}")
        notes.append((note, linked_text, resolved_text))
    if any(count != 1 for count in matched.values()):
        raise RuntimeError(
            "purchased template must contain exactly one Material "
            f"and one Finish property link: {matched!r}"
        )
    return notes


def _number_note(draw: Any) -> tuple[Any, Any]:
    """The template's one note that links Number and nothing else."""
    link = property_link("Number")
    sheet_view = _early_bound(draw, "IDrawingDoc").GetFirstView()
    if sheet_view is None:
        raise RuntimeError("DWG. NO.: drawing has no sheet view")
    found = []
    for annotation in _early_bound(sheet_view, "IView").GetAnnotations() or ():
        annotation = _early_bound(annotation, "IAnnotation")
        if annotation.GetType() != 6:  # swAnnotationType_e.swNote
            continue
        specific = annotation.GetSpecificAnnotation()
        if specific is None:
            raise RuntimeError("DWG. NO.: sheet note has no INote")
        note = _early_bound(specific, "INote")
        raw = note.PropertyLinkedText
        if type(raw) is not str:
            raise RuntimeError(f"DWG. NO.: unreadable note link {raw!r}")
        if link in raw:
            found.append((note, annotation, raw))
    if [raw for _note, _annotation, raw in found] != [link]:
        raise RuntimeError(
            f"DWG. NO.: the sheet must carry one note linking only {link}: "
            f"{[raw for _note, _annotation, raw in found]!r}"
        )
    return found[0][:2]


def _number_format(annotation: Any) -> tuple[Any, float, str]:
    """The note's format, its native ``CharHeight`` in metres, and its face.

    ``CharHeight`` is read whatever the height's authority, because it is the
    scale the metre setter writes.  The templates-1636 census read the
    landscape template's 18 pt DWG. NO. as 0.0047625 m and its 15 pt title as
    0.00396875 m.  8d9c8dbba instead took 18 pt as 18 x 0.0254/72 = 6.35 mm
    and wrote 0.00618 m, 1.30x the note's native 0.0047625 m, and its
    readback ran down to y = 13.41 mm, below the cell.
    """
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError("DWG. NO.: note has no text format")
    text_format = _early_bound(text_format, "ITextFormat")
    height = text_format.CharHeight
    face = text_format.TypeFaceName
    if (
        type(height) not in (int, float)
        or not math.isfinite(height)
        or height <= 0
        or type(face) is not str
        or not face.strip()
    ):
        raise RuntimeError(f"DWG. NO.: unreadable font {height!r}, {face!r}")
    return text_format, float(height), face


def _number_state(adapter: Any, note: Any, annotation: Any) -> str:
    """The note's readback that explains a fit, as JSON; never raises.

    Diagnostic only: a failure building or serializing it is recorded in its
    place, so it cannot mask the authoritative extent and guard around it.
    """
    try:
        return _read_number_state(adapter, note, annotation)
    except Exception as exc:
        return f"<state refused {type(exc).__name__}: {exc}>"


def _read_number_state(adapter: Any, note: Any, annotation: Any) -> str:
    """Extent and position are sheet metres (``GetPosition`` is the text
    box's upper-left); the format is both height authorities and the
    line/spacing members ``ITextFormat`` exposes; rows are
    ``IDisplayData``'s text runs.  A refused read is recorded as such.
    """

    def read(call: Callable[[], Any]) -> Any:
        try:
            value = call()
        except Exception as exc:
            return f"<refused {type(exc).__name__}>"
        if isinstance(value, (tuple, list)):
            try:
                return [round(float(item), 9) for item in value]
            except (TypeError, ValueError):
                return repr(value)
        if isinstance(value, float):
            return round(value, 9)
        if value is None or isinstance(value, (bool, int, str)):
            return value
        return repr(value)

    state: dict[str, Any] = {
        "extent": read(lambda: note.GetExtent()),
        "position": read(lambda: annotation.GetPosition()),
        "use_doc": read(lambda: annotation.GetUseDocTextFormat(0)),
        "justification": read(lambda: note.GetTextJustification()),
        "vertical": read(lambda: note.GetTextVerticalJustification()),
    }
    try:
        text_format = _early_bound(annotation.GetTextFormat(0), "ITextFormat")
    except Exception as exc:
        state["format"] = f"<refused {type(exc).__name__}>"
    else:
        state["format"] = {
            name: read(lambda name=name: getattr(text_format, name))
            for name in (
                "TypeFaceName",
                "CharHeight",
                "CharHeightInPts",
                "WidthFactor",
                "CharSpacingFactor",
                "LineSpacing",
                "LineLength",
            )
        }
        state["format"]["IsHeightSpecifiedInPts"] = read(
            lambda: text_format.IsHeightSpecifiedInPts()
        )
    try:
        display, refused = annotation_display(adapter, annotation)
    except Exception as exc:
        state["rows"] = f"<refused {type(exc).__name__}>"
    else:
        state["rows"] = [
            {key: text[key] for key in ("t", "pos", "h", "ls", "w") if key in text}
            for text in display.get("texts", ())
        ]
        if refused:
            state["display_refused"] = refused
    return json.dumps(state, sort_keys=True)


@_telemetry.traced("drawing.purchased_number_fit")
def _fit_number(
    adapter: Any, draw: Any, *, layout: DrawingLayout, number: str
) -> Callable[[], None]:
    """Shrink this drawing's DWG. NO. note, never the template, clear of REV.

    One proportional write of the note's native ``CharHeight`` from its
    measured extent, in its own face, aimed :data:`_NUMBER_FIT_AIM` inside
    the limit.  Returns the settled check that re-proves the link, number,
    face, height and fit after the final rebuild.  The note's state before
    the write and at every check is a span event, and in any failure.
    """
    if layout is not DrawingLayout.LANDSCAPE:
        raise ValueError(f"DWG. NO.: the {layout} template's cell is unmeasured")
    link = property_link("Number")
    note, annotation = _number_note(draw)

    def measure(phase: str) -> tuple[tuple[float, float, float, float], str]:
        """The zoomed extent, and the state it was read in."""
        if note.PropertyLinkedText != link or note.GetText() != number:
            raise RuntimeError(
                f"DWG. NO.: readback {note.PropertyLinkedText!r} = "
                f"{note.GetText()!r}, expected {link!r} = {number!r}"
            )
        with _zoomed_on(adapter, _NUMBER_CENTRE, _NUMBER_ZOOM_HALF):
            state = _number_state(adapter, note, annotation)
            _telemetry.event(
                "drawing.purchased_number_fit.state", phase=phase, state=state
            )
            return _box(note.GetExtent(), label="DWG. NO.", kind="note"), state

    text_format, height, face = _number_format(annotation)
    box, before = measure("template")
    # Only an overrun across the REV divider is this fit's to repair.
    if not _inside(box, (*_NUMBER_LIMIT[:2], math.inf, _NUMBER_LIMIT[3])):
        raise RuntimeError(f"DWG. NO.: note leaves its cell: {box!r}; state {before}")
    if box[2] > _NUMBER_LIMIT[2]:
        ratio = (_NUMBER_LIMIT[2] - _NUMBER_FIT_AIM - box[0]) / (box[2] - box[0])
        target = math.floor(height * ratio * 1e5) / 1e5  # 0.01 mm, downward
        if target < _NUMBER_MIN_HEIGHT:
            raise RuntimeError(
                f"DWG. NO.: {number!r} needs {target!r} m, under the note height"
            )
        # This note's local format: the metre setter, as add_property_linked_note.
        text_format.CharHeight = target
        if annotation.SetTextFormat(0, False, text_format) is not True:
            raise RuntimeError(f"DWG. NO.: font setter refused {target!r} m")
        _rebuild(draw, phase="DWG. NO. fit")
        if annotation.GetUseDocTextFormat(0) is not False:
            raise RuntimeError("DWG. NO.: local font did not persist")
        height = target

    def settled() -> None:
        _format, actual, actual_face = _number_format(annotation)
        box, state = measure("settled")
        if (
            abs(actual - height) > _NUMBER_HEIGHT_TOL
            or actual_face != face
            or not _inside(box, _NUMBER_LIMIT)
        ):
            raise RuntimeError(
                f"DWG. NO.: note left its fit: {actual!r} m {actual_face!r} at "
                f"{box!r}, fitted {height!r} m {face!r} within {_NUMBER_LIMIT!r}; "
                f"template state {before}; settled state {state}"
            )

    settled()
    _telemetry.info(f"DWG. NO. fit: {number!r} at {height!r} m, from {before}")
    return settled


@_telemetry.traced("drawing.purchased_footer")
def add_purchased_footer(
    adapter: Any,
    draw: Any,
    properties: dict[str, str],
    *,
    item: str,
    notes: str = "",
    cut_to_suit: bool = False,
    general_text: str | None = None,
    label: str,
    supplier_data: Sequence[str] = (),
) -> list[tuple[Any, str, str, tuple[float, float, float, float]]]:
    """Notes, general line, ITEM, SUPPLIER and SKU rows, bottom-left of the sheet.

    Returns (note, linked text, resolved text, reserved box) for the native
    readback.  When ``general_text`` is None, ``cut_to_suit`` says the part is
    cut at assembly (its note says where); otherwise the default general line
    says it is used as supplied. A literal override uses the same reserved
    single-line space and native text/extent checks.
    """
    item = check_item(item, label=label)
    lines = note_lines(notes, label=label)
    data = _supplier_data_lines(supplier_data, label=label)
    placed = []
    if lines:
        # The part's own requirements are drawing-local, like purchased
        # Finish: never forced into title-block cells.
        text = "\n".join(lines)
        apply_custom_properties(adapter, {"Installation Notes": text}, model=draw)
        # $PRP (this drawing), not $PRPSHEET (the model in view).
        link = '$PRP:"Installation Notes"'
        top = footer_top(text, label=label)
        note = _literal_note(adapter, link, _NOTE_X, top)
        placed.append(
            (
                note,
                link,
                text,
                (0.015, _NOTES_BOTTOM - 0.001, _FOOTER_RIGHT, top + 0.001),
            )
        )
    if data:
        text = "\n".join(data)
        top = footer_top(notes, label=label, supplier_data=supplier_data)
        bottom = (
            footer_top(notes, label=label) + _LINE_PITCH if lines else _NOTES_BOTTOM
        )
        note = _literal_note(adapter, text, _NOTE_X, top)
        placed.append(
            (note, text, text, (0.015, bottom - 0.001, _FOOTER_RIGHT, top + 0.001))
        )
    general = _GENERAL_TEXT[cut_to_suit] if general_text is None else general_text
    note = _literal_note(adapter, general, _NOTE_X, _GENERAL_Y)
    placed.append(
        (
            note,
            general,
            general,
            (0.015, _GENERAL_BOTTOM, _FOOTER_RIGHT, _GENERAL_Y + 0.001),
        )
    )
    for row, y in _FOOTER_ROWS:
        row_note = _literal_note(adapter, row, _NOTE_X, y)
        placed.append(
            (row_note, row, row, (0.015, y - 0.007, _VALUE_X - 0.002, y + 0.001))
        )
        box = (_VALUE_X - 0.002, y - 0.007, _FOOTER_RIGHT, y + 0.001)
        if row == "ITEM:":
            value = _literal_note(adapter, item, _VALUE_X, y)
            placed.append((value, item, item, box))
            continue
        name = "Supplier" if row == "SUPPLIER:" else "Supplier SKUs"
        value = add_property_linked_note(adapter, name, _VALUE_X, y, char_height=0.003)
        placed.append(
            (_early_bound(value, "INote"), property_link(name), properties[name], box)
        )
    return placed


async def build_purchased_fastener_drawing(
    adapter: Any,
    spec: DrawingSpec,
    *,
    item: str | None = None,
    cut_to_suit: bool = False,
    general_text: str | None = None,
    number_fit: NumberFit = NumberFit.TEMPLATE,
    view_layout: Literal["standard", "supplier_top", "tall_top"] = "standard",
    supplier_dimensions: SupplierDimensions | None = None,
    supplier_margins: SupplierMargins | None = None,
    configuration: str | None = None,
    settled_checks: Sequence[Callable[[], None]] = (),
    supplier_data: Sequence[str] = (),
    title_block_setup: Callable[[Any], Callable[[], None]] | None = None,
) -> dict[str, str]:
    """Export Front/Top/Right plus Isometric without fabrication dimensions or PMI.

    ``item`` is the catalogue designation printed on the ITEM row, e.g.
    ``#4-40 x 1/4 SOCKET SET SCREW, CUP POINT``; without one the row prints
    the registry stock name (pd_vn_transgear_pivot_screw, reworked in PR #1477).
    ``cut_to_suit`` marks a fastener its registry installation note cuts at
    assembly.  ``number_fit`` opts a sheet whose registry number overruns the
    DWG. NO. cell into the measured fit (:func:`_fit_number`).
    ``general_text`` overrides only the footer's general line (the same
    reserved line and native text/extent readbacks); None keeps the
    ``cut_to_suit``-selected default.
    ``title_block_setup`` formats existing linked title notes and returns their
    mandatory final-rebuild check, as for purchased-part reference sheets.
    ``view_layout="supplier_top"`` reserves the supplier screw family's Top
    annotation lanes; ``"tall_top"`` gives a longer axial Top view. Neither
    changes annotation margins or the standard-scale fitting contract.
    Supplier hooks import native reference sizes after fitting; explicit margins
    reserve their annotation space before scale selection. Pass the same mutable
    settled-check list the hook populates, or a predeclared read-only assertion.
    Final checks run after the finalizer's last rebuild, without refitting.
    """
    stock = fastener(spec.artifact_stem)
    source = spec.source

    if spec.source_kind != "part" or source.stem != stock.part_name:
        raise ValueError(f"purchased drawing source identity mismatch: {spec!r}")
    if not source.is_file():
        raise FileNotFoundError(f"source purchased part is missing: {source}")

    source_sha256 = _source_file_sha256(source)
    primary: BaseException | None = None
    source_evidence: list[dict[str, Any]] = []
    try:
        with _telemetry.span("drawing.purchased_source", part=stock.part_name):
            model = _open_supplier_source_read_only(
                adapter, source, label=stock.part_name
            )
            properties = read_required_properties(
                model, _PROPERTIES, required=_PROPERTIES
            )
            registry = _config.parts(stock.part_name)
            finish = registry["finish"]
            if not isinstance(finish, str) or not finish.strip():
                raise RuntimeError(
                    f"{stock.part_name}: registered purchased finish is empty"
                )
            expected = {
                "Number": str(registry["number"]),
                # The PART cell prints the slug (_part_properties.part_properties).
                "Title": stock.part_name,
                "Material": str(registry["material"]),
                "Stock Name": stock.stock_name,
                "Supplier": stock.supplier,
                "Supplier SKUs": ", ".join(stock.skus),
            }
            for name, value in expected.items():
                if properties[name] != value:
                    raise RuntimeError(
                        f"{stock.part_name}: stale source {name} {properties[name]!r} != {value!r}"
                    )

        return await _build_reference_sheet(
            adapter,
            spec,
            properties=properties,
            finish=finish,
            item=item if item is not None else stock.stock_name.upper(),
            notes=str(registry.get("installation_notes", "")),
            cut_to_suit=cut_to_suit,
            general_text=general_text,
            document_title=str(registry["title"]),
            number_fit=number_fit,
            view_layout=view_layout,
            supplier_dimensions=supplier_dimensions,
            supplier_margins=supplier_margins,
            configuration=configuration,
            settled_checks=settled_checks,
            supplier_data=supplier_data,
            title_block_setup=title_block_setup,
            source_checkpoint=_supplier_source_checkpoint(
                adapter,
                source,
                model,
                source_sha256,
                label=stock.part_name,
                evidence=source_evidence,
                configuration=configuration,
            ),
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        # Includes finalize_drawing's SLDDRW/PDF saves and drawing CloseDoc.
        # SetText can dirty source presentation without changing native values.
        # Never save or clear that flag; the source must remain byte-identical.
        try:
            if _source_file_sha256(source) != source_sha256:
                raise RuntimeError(
                    f"{stock.part_name}: supplier source part bytes changed during drawing"
                )
        except BaseException as preservation_error:
            if primary is not None:
                primary.add_note(
                    f"{stock.part_name}: supplier source file preservation also failed: {preservation_error!r}"
                )
            else:
                _retain_supplier_source_failure(
                    spec, preservation_error, source_evidence
                )
        if primary is not None:
            _retain_supplier_source_failure(spec, primary, source_evidence)


async def build_purchased_spring_drawing(
    adapter: Any,
    spec: DrawingSpec,
    *,
    item: str,
    supplier_dimensions: SupplierDimensions | None = None,
    supplier_margins: SupplierMargins | None = None,
    configuration: str | None = None,
    settled_checks: Sequence[Callable[[], None]] = (),
    supplier_data: Sequence[str] = (),
) -> dict[str, str]:
    """Use spring metadata without treating the part as a catalogued fastener.

    The part's Manufacturing Notes print as the footer notes; the Front view
    shows the coil at its installed length.
    """
    source = spec.source
    if spec.source_kind != "part" or not source.is_file():
        raise FileNotFoundError(f"source purchased spring is missing: {source}")
    source_sha256 = _source_file_sha256(source)
    primary: BaseException | None = None
    source_evidence: list[dict[str, Any]] = []
    try:
        model = _open_supplier_source_read_only(
            adapter, source, label=spec.artifact_stem
        )
        names = (
            *_PROPERTIES,
            "Material Specification",
            "Finish",
            "Manufacturing Notes",
        )
        properties = read_required_properties(model, names, required=names)
        return await _build_reference_sheet(
            adapter,
            spec,
            properties=properties,
            finish=properties["Finish"],
            item=item,
            material_property="Material Specification",
            notes=properties["Manufacturing Notes"],
            spring=True,
            supplier_dimensions=supplier_dimensions,
            supplier_margins=supplier_margins,
            configuration=configuration,
            settled_checks=settled_checks,
            supplier_data=supplier_data,
            source_checkpoint=_supplier_source_checkpoint(
                adapter,
                source,
                model,
                source_sha256,
                label=spec.artifact_stem,
                evidence=source_evidence,
                configuration=configuration,
            ),
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if _source_file_sha256(source) != source_sha256:
                raise RuntimeError(
                    f"{spec.artifact_stem}: supplier source part bytes changed during drawing"
                )
        except BaseException as preservation_error:
            if primary is not None:
                primary.add_note(
                    f"{spec.artifact_stem}: supplier source file preservation also failed: {preservation_error!r}"
                )
            else:
                _retain_supplier_source_failure(
                    spec, preservation_error, source_evidence
                )
        if primary is not None:
            _retain_supplier_source_failure(spec, primary, source_evidence)


async def _build_reference_sheet(
    adapter: Any,
    spec: DrawingSpec,
    *,
    properties: dict[str, str],
    finish: str,
    item: str,
    material_property: str = "Material",
    notes: str = "",
    cut_to_suit: bool = False,
    general_text: str | None = None,
    document_title: str | None = None,
    spring: bool = False,
    view_layout: Literal["standard", "supplier_top", "tall_top"] = "standard",
    number_fit: NumberFit = NumberFit.TEMPLATE,
    supplier_dimensions: SupplierDimensions | None = None,
    supplier_margins: SupplierMargins | None = None,
    configuration: str | None = None,
    settled_checks: Sequence[Callable[[], None]] = (),
    supplier_data: Sequence[str] = (),
    source_checkpoint: Callable[[str], None] | None = None,
    title_block_setup: Callable[[Any], Callable[[], None]] | None = None,
) -> dict[str, str]:
    source = spec.source
    template = DRAWING_TEMPLATES[spec.layout]
    label = spec.artifact_stem
    # Validate the footer text and Number fit choice before any native work.
    check_item(item, label=label)
    if not isinstance(number_fit, NumberFit):
        raise TypeError(f"{label}: number_fit must be a NumberFit: {number_fit!r}")
    if configuration is not None and (
        not isinstance(configuration, str) or not configuration.strip()
    ):
        raise ValueError(f"{label}: source configuration must be a nonempty name")
    caption_y = view_band_bottom(notes, label=label, supplier_data=supplier_data)
    cells = (
        spring_view_cells(caption_y)
        if spring
        else fastener_view_cells(caption_y, layout=view_layout)
    )
    if supplier_dimensions is None:
        if supplier_margins is not None:
            raise ValueError(f"{label}: supplier margins require an annotation hook")
        fit_cells = cells
    else:
        if not callable(supplier_dimensions):
            raise TypeError(f"{label}: supplier annotation hook must be callable")
        if supplier_margins is None:
            raise ValueError(
                f"{label}: supplier annotations require explicit pre-fit margins"
            )
        fit_cells = supplier_fit_cells(cells, supplier_margins, label=label)
    draw, sheet = new_project_drawing(
        adapter,
        layout=spec.layout,
        **({"checkpoint": source_checkpoint} if source_checkpoint is not None else {}),
    )
    title_block_notes = _purchased_title_block(
        adapter,
        draw,
        material=properties[material_property],
        finish=finish,
        material_property=material_property,
    )
    # The registry title still names the drawing document and PDF; only the
    # sheet's PART cell moved to the slug.
    title = (
        f"{document_title or properties['Title']} — Purchased Part Reference Drawing"
    )
    with _telemetry.span("drawing.purchased_summary"):
        stamp_drawing_summary(
            adapter,
            draw,
            {
                0: title,
                1: "Harmonic Analyzer purchased-part identification; reference only",
                2: "Harmonic Analyzer Project",
                3: f"{spec.artifact_stem}; {properties['Supplier']}; {properties['Supplier SKUs']}",
                4: (
                    "Front, Top, Right and Isometric; supplier sizes are reference only"
                    if supplier_dimensions is not None
                    else "Front, Top, Right and Isometric; no fabrication dimensions or PMI"
                ),
            },
        )

    views = []
    with _telemetry.span("drawing.purchased_create_views"):
        for name, center, _ in cells:
            with _drawing_checkpoint(source_checkpoint, f"create_view:{name}"):
                view = _early_bound(
                    place_view(adapter, str(source), name, *center, scale=(1, 1)),
                    "IView",
                )
            if configuration is not None:
                view.ReferencedConfiguration = configuration
                if source_checkpoint is not None:
                    source_checkpoint(f"after_select_configuration:{name}")
            set_hidden_lines_removed(adapter, view)
            views.append(view)
        if configuration is not None:
            _rebuild(draw, phase="select supplier source configuration")
            if source_checkpoint is not None:
                source_checkpoint("after_configuration_rebuild")
            for view in views:
                if str(view.ReferencedConfiguration) != configuration:
                    raise RuntimeError(
                        f"{view.GetOrientationName()}: supplier configuration did not persist"
                    )
        # Later insertions may auto-adjust the sheet scale. Pin all views only
        # after insertion so the measurement pass is genuinely at native 1:1.
        for view in views:
            view.UseSheetScale = 0
            view.ScaleRatio = double_array([1.0, 1.0])
    scales = _fit_views(draw, views, fit_cells)
    fitted_origins: dict[str, tuple[float, float]] = {}
    fitted_sources: dict[str, tuple[str, str]] = {}
    if supplier_dimensions is not None:
        for view, (name, _, _) in zip(views, cells, strict=True):
            view.UpdateViewDisplayGeometry()
            fitted_origins[name] = model_point_in_view(
                adapter, view, (0.0, 0.0, 0.0), label=f"{label} {name} fitted origin"
            )
            fitted_sources[name] = (
                str(Path(view.GetReferencedModelName()).resolve()),
                str(view.ReferencedConfiguration),
            )
    center_marks = _center_marks_without_lines(views, cells)
    scale = scales["*Front"]

    with _telemetry.span("drawing.purchased_property_link"):
        values = tuple(adapter._get_attr_or_call(sheet, "GetProperties2"))
        if len(values) != 8:
            raise RuntimeError(
                f"purchased drawing has incomplete sheet properties: {values!r}"
            )
        # Preserve template dimensions/format while explicitly selecting third
        # angle and the first view's source for every title-block property link.
        sheet.SetProperties2(
            int(values[0]),
            int(values[1]),
            float(scale[0]),
            float(scale[1]),
            False,
            float(values[5]),
            float(values[6]),
            False,
        )
        first_name = view_name(adapter, views[0])
        if not first_name:
            raise RuntimeError("purchased front view has no native name")
        sheet.CustomPropertyView = first_name
        values = tuple(adapter._get_attr_or_call(sheet, "GetProperties2"))
        if (
            len(values) != 8
            or bool(values[4])
            or bool(values[7])
            or sheet.CustomPropertyView != first_name
        ):
            raise RuntimeError(
                "purchased drawing third-angle/property-source settings did not persist"
            )
        assert_asme_b_sheet(
            adapter,
            sheet,
            layout=spec.layout,
            phase="purchased layout",
            scale=scale,
        )

    placed = []
    with _telemetry.span("drawing.purchased_annotations"):
        if supplier_dimensions is not None:
            with _drawing_checkpoint(source_checkpoint, "supplier_formatting"):
                supplier_dimensions(
                    adapter,
                    {
                        name: view
                        for view, (name, _, _) in zip(views, cells, strict=True)
                    },
                )
            # Import leaves a model view active. Footer/captions are sheet-owned.
            drawing = _early_bound(draw, "IDrawingDoc")
            drawing.ActivateView("")
            if not drawing.GetEditSheet() or drawing.ActiveDrawingView is not None:
                raise RuntimeError(f"{label}: cannot restore sheet context for footer")
        for view, (name, center, cell) in zip(views, cells, strict=True):
            view_scale = scales[name]
            caption = f"{name[1:].upper()}  {view_scale[0]}:{view_scale[1]}"
            if spring and name == "*Front":
                caption += "  (SHOWN AT INSTALLED LENGTH)"
            # Under the view itself, not the cell's floor: a short view in a
            # tall cell (the counter spring's TOP) left its caption stranded
            # mid-field (r4 review, rule 15). The fit keeps outlines in cells,
            # so this only ever lifts a caption toward its own view. A view
            # with a centre mark keeps the cell floor: the mark's scaled cross
            # reaches past the outline and struck lifted captions (r5, 8:1
            # pins, rule 14).
            floor = cell[1]
            annotated = (
                supplier_dimensions is not None
                and view.GetFirstDisplayDimension6() is not None
            )
            if not center_marks[name] and not annotated:
                floor = max(_box(view.GetOutline(), label=name)[1], floor)
            caption_at = floor - _CAPTION_TO_CELL
            note = _literal_note(adapter, caption, center[0], caption_at)
            bounds = _box(note.GetExtent(), label=caption, kind="note")
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            x = 2 * center[0] - (bounds[0] + bounds[2]) / 2
            if not annotation.SetPosition(x, caption_at, 0.0):
                raise RuntimeError(f"{caption}: failed to center view caption")
            placed.append(
                (
                    note,
                    caption,
                    caption,
                    (cell[0], caption_at - _CAPTION_BELOW, cell[2], caption_at + 0.001),
                )
            )
        placed.extend(
            add_purchased_footer(
                adapter,
                draw,
                properties,
                item=item,
                notes=notes,
                cut_to_suit=cut_to_suit,
                general_text=general_text,
                label=label,
                supplier_data=supplier_data,
            )
        )
    with _telemetry.span("drawing.purchased_native_contract"):
        _rebuild(draw, phase="linked notes and final layout")
        for note, linked_text, resolved_text in title_block_notes:
            if (
                note.PropertyLinkedText != linked_text
                or note.GetText() != resolved_text
            ):
                raise RuntimeError(
                    "purchased title-block property did not resolve from its "
                    f"expected source: {linked_text!r}"
                )
        # The links resolve at the rebuild above; an opted-in DWG. NO. is
        # measured and fitted here, then re-proved after the final rebuild.
        supplier_checks = tuple(settled_checks)
        if any(not callable(verify) for verify in supplier_checks):
            raise TypeError(f"{label}: settled checks must be callable")
        if supplier_dimensions is not None and not supplier_checks:
            raise RuntimeError(
                f"{label}: supplier annotations require final settled native checks"
            )
        final_checks = supplier_checks
        if number_fit is NumberFit.SHRINK_TO_CELL:
            final_checks = (
                *final_checks,
                _fit_number(
                    adapter, draw, layout=spec.layout, number=properties["Number"]
                ),
            )
        if title_block_setup is not None:
            final_checks = (*final_checks, title_block_setup(adapter))
        actual = list(iter_views(adapter))
        orientations = tuple(view.GetOrientationName() for view in actual)
        if len(actual) != 4 or set(orientations) != {name for name, _, _ in cells}:
            raise RuntimeError(
                f"purchased drawing must have exactly four native views: {orientations!r}"
            )
        views_by_orientation = dict(zip(orientations, actual, strict=True))
        region = sheet_drawable_region(
            adapter,
            sheet,
            width=template.width_m,
            height=template.height_m,
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        for name, _, cell in cells:
            view = views_by_orientation[name]
            if Path(view.GetReferencedModelName()).resolve() != source.resolve():
                raise RuntimeError(f"{name}: purchased view references the wrong model")
            if (
                configuration is not None
                and str(view.ReferencedConfiguration) != configuration
            ):
                raise RuntimeError(f"{name}: final purchased configuration changed")
            if tuple(view.ScaleRatio) != scales[name]:
                raise RuntimeError(f"{name}: final purchased view scale changed")
            box = _box(view.GetOutline(), label=name)
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"{name}: purchased view leaves its cell/border: {box!r}"
                )
        for note, linked_text, resolved_text, cell in placed:
            actual_link = note.PropertyLinkedText
            actual_text = note.GetText()
            # INote.GetText uses CRLF; PropertyLinkedText preserves authored LF.
            if (
                actual_link != linked_text
                or actual_text.replace("\r\n", "\n") != resolved_text
            ):
                raise RuntimeError(
                    f"purchased note readback mismatch: expected link={linked_text!r}, "
                    f"actual link={actual_link!r}, expected text={resolved_text!r}, "
                    f"actual text={actual_text!r}"
                )
            box = _box(note.GetExtent(), label=linked_text, kind="note")
            if not _inside(box, cell) or not _inside(box, border):
                raise RuntimeError(
                    f"purchased note leaves its reserved space/border: {linked_text!r}: {box!r}"
                )

    if supplier_dimensions is not None:
        final_checks = (
            *final_checks,
            lambda: _assert_supplier_layout(
                adapter,
                cells,
                label=label,
                margins=supplier_margins,
                scales=scales,
                origins=fitted_origins,
                sources=fitted_sources,
                sheet_notes=placed,
            ),
        )
    if source_checkpoint is not None:
        final_checks = (*final_checks, lambda: source_checkpoint("last_settled"))
    paths = spec.outputs
    return await finalize_drawing(
        adapter,
        DrawingOutputs(slddrw=paths["slddrw"], pdf=paths["pdf"], png=paths["png"]),
        layout=spec.layout,
        pdf_title=title,
        scale=scale,
        settled_checks=final_checks,
        **({"checkpoint": source_checkpoint} if source_checkpoint is not None else {}),
    )
