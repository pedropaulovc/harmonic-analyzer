"""Read-only slotted-sheet closure; no source enrollment or geometry setters.

The source/native role manifest is supplied by the owned pilot after separately
reviewed producer evidence. These sheet roles come from the unchanged recipe;
they do not invent source hashes, display kinds or attached entity identities.
"""

from enum import StrEnum
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import time
from unittest.mock import patch

from _common import _early_bound
from _drawing_common import ASME_B_DPI, property_link, read_required_properties
from _drawing_view_packing import Rect
from diagnostics._model_dimension_coverage import SemanticCoverage
from diagnostics import probe_drawing_attachments as attachments
import slotted_screw_spec as spec


class LayoutObservation(StrEnum):
    CAPTURE_ONLY = "capture_only"
    BASELINE = "baseline"
    CANDIDATE = "candidate"


class CapturePhase(StrEnum):
    BUILT = "built"
    REOPENED = "reopened"


VIEWS = ("*Front", "*Top", "*Isometric")
DIMENSION_VIEWS = {
    "HeadDia@HeadProfile": "*Top",
    "HeadHt@Head": "*Front",
    "ShankLg@Shank": "*Front",
}
SOURCE_SHA256 = "2033c1fe198e38eebd1c32aaecf38646ae3487569fb7848d718d083bb1736396"
PRODUCER_REVISION = "3c0c4a97e69ead5f04fa760b8aa507c16143172d"
SOURCE_READBACK_SHA256 = (
    "f6835f1d58bcabc55055adf5c904eaa3e12d9a889a88cae77dd59c4204a7a61e"
)


def require_capture_factors():
    from diagnostics._bsurface_attachment_witness import (
        GridControl,
        grid_control_from_environment,
    )
    from diagnostics._tooth_selector_observation import (
        observation_from_environment,
        require_targets,
    )

    if grid_control_from_environment() is not GridControl.OFF:
        raise ValueError("slotted capture-only requires the default grid control")
    require_targets(observation_from_environment(), ("slotted_screw",))


def require_selection(mode, targets, manifests):
    if mode is None:
        return
    if not isinstance(mode, LayoutObservation) or tuple(targets) != ("slotted_screw",):
        raise ValueError("slotted layout observation requires its one explicit target")
    if mode is LayoutObservation.CAPTURE_ONLY:
        return  # No acceptance manifest is fabricated from this observation.
    if "slotted_screw" not in manifests:
        raise ValueError("slotted source enrollment requires reviewed native evidence")
    manifest = manifests["slotted_screw"]
    if (
        manifest.coverage is not SemanticCoverage.MODEL_DIMENSIONS_ONLY
        or manifest.dimensions != spec.DRAWING_DIMENSIONS
        or manifest.basic
        or manifest.entity_labels
        or manifest.view_roles
        or {row.key: row.orientation for row in manifest.model_dimensions}
        != DIMENSION_VIEWS
        or len(manifest.model_dimensions) != len(DIMENSION_VIEWS)
        or sorted(manifest.model_views) != sorted(VIEWS)
    ):
        raise ValueError(
            "slotted source enrollment has an incomplete dimension contract"
        )


def _values(raw, count, label):
    if (
        type(raw) not in (list, tuple)
        or len(raw) != count
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in raw)
    ):
        raise RuntimeError(f"{label}: expected {count} finite native coordinates")
    return tuple(raw)


def _rect(raw):
    if type(raw) is not dict or set(raw) != {"xmin", "ymin", "xmax", "ymax"}:
        raise RuntimeError("annotation measurement rectangle is incomplete")
    return Rect(
        *_values([raw[k] for k in ("xmin", "ymin", "xmax", "ymax")], 4, "measurement")
    )


def _clearance(box, drawable):
    return {
        "left": box.xmin - drawable.xmin,
        "bottom": box.ymin - drawable.ymin,
        "right": drawable.xmax - box.xmax,
        "top": drawable.ymax - box.ymax,
    }


def layout_geometry(bank, views, drawable):
    """Use the existing complete native ink bank, including dimension tails.

    Coordinates are unrounded sheet metres. This observes border containment;
    it is not a replacement for production packing's view/obstacle gap gate.
    """
    drawable = Rect(*_values(drawable, 4, "drawable"))
    dimensions = bank["model_dimensions"]["dimensions"]
    if dimensions.keys() != DIMENSION_VIEWS.keys():
        raise RuntimeError("slotted dimension contract requires exactly three roles")
    if sorted(row["orientation"] for row in views.values()) != sorted(VIEWS):
        raise RuntimeError("slotted view contract requires exactly three orientations")
    boxes = {}
    for name, view in views.items():
        if _values(view["scale"], 2, "scale") != (6.0, 1.0):
            raise RuntimeError("slotted view scale must remain exactly 6:1")
        boxes[f"view:{name}"] = Rect(*_values(view["outline"], 4, "view outline"))
    annotations = bank["annotations"]
    for key, row in annotations.items():
        semantic = row["semantic"]
        if semantic["owner_type"] == 2:
            continue  # Sheet-format ink belongs to the existing template bank.
        if (
            semantic["kind"] not in (4, 6)
            or semantic["visible"] != 1
            or semantic["dangling"] is not False
            or row.get("measurement_exclusion")
            or "measurement" not in row
        ):
            raise RuntimeError(f"{key}: unsupported or hidden slotted measurement")
        boxes[key] = _rect(row["measurement"]["envelope"])
    for key, orientation in DIMENSION_VIEWS.items():
        row = dimensions[key]
        annotation_key = row["annotation_key"]
        if (
            row["orientation"] != orientation
            or annotation_key not in boxes
            or row["presentation"]["show_dimension_value"] is not True
            or annotations[annotation_key]["semantic"]["kind"] != 4
        ):
            raise RuntimeError(f"{key}: dimension visibility/view contract changed")
        strokes = annotations[annotation_key]["measurement"]["native_strokes"]
        if not strokes:
            raise RuntimeError(f"{key}: displayed dimension stroke bank is empty")
        envelope = boxes[annotation_key]
        for stroke in strokes:
            points = [_values(stroke[k], 2, "stroke") for k in ("start", "end")]
            (width,) = _values([stroke["width_m"]], 1, "stroke width")
            if width < 0 or any(
                not (
                    envelope.xmin <= x - width / 2 <= x + width / 2 <= envelope.xmax
                    and envelope.ymin <= y - width / 2 <= y + width / 2 <= envelope.ymax
                )
                for x, y in points
            ):
                raise RuntimeError(f"{key}: dimension envelope omits native stroke ink")
    clearances = {key: _clearance(box, drawable) for key, box in boxes.items()}
    return {
        "drawable_m": list(drawable.bounds),
        "envelopes_m": {key: list(box.bounds) for key, box in boxes.items()},
        "clearances_m": clearances,
        "head_height_top_clearance_m": clearances[
            dimensions["HeadHt@Head"]["annotation_key"]
        ]["top"],
        "border_status": "inside"
        if all(value >= 0 for row in clearances.values() for value in row.values())
        else "outside",
    }


def require_border(mode, result):
    if mode not in (
        LayoutObservation.BASELINE,
        LayoutObservation.CANDIDATE,
    ) or not isinstance(mode, LayoutObservation):
        raise ValueError("explicit slotted observation arm required")
    if mode is LayoutObservation.CANDIDATE and result["border_status"] != "inside":
        raise RuntimeError(
            "slotted candidate decorated ink crosses the native zone border"
        )


def _same(app, left, right, label):
    result = app.IsSame(left, right) if left is not None and right is not None else None
    if type(result) is not int or result != 1:
        raise RuntimeError(f"slotted {label}: exact native identity changed")


def _owned_context(adapter, source, native):
    record = adapter.ownership.assert_current_owned()
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    native = Path(native).resolve()
    if (
        model.GetType() != 3
        or model.Visible is not True
        or native not in record.paths
        or native.parent not in adapter.ownership.directories
        or Path(model.GetPathName()).resolve() != native
    ):
        raise RuntimeError(
            "slotted capture requires the exact visible saved owned drawing"
        )
    _same(adapter.swApp, model, adapter.swApp.ActiveDoc, "active drawing")
    part = _early_bound(adapter.swApp.GetOpenDocumentByName(str(source)), "IModelDoc2")
    if (
        part is None
        or part.GetType() != 1
        or Path(part.GetPathName()).resolve() != source
    ):
        raise RuntimeError("slotted capture requires the exact open copied PART")
    return model, part


def _state(model, part):
    values = [model.GetSaveFlag(), part.GetSaveFlag()]
    if any(type(value) is not bool for value in values):
        raise RuntimeError("slotted native dirty flags must be Boolean")
    return {"drawing_dirty": values[0], "source_dirty": values[1]}


def sheet_witness(adapter, model, part, bank, handles):
    """Documented sheet metres; no coordinate, scale or text setters."""
    drawing = _early_bound(model, "IDrawingDoc")
    if len(tuple(drawing.GetViews() or ())) != 1:
        raise RuntimeError("slotted capture requires exactly one sheet")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = _values(sheet.GetProperties2(), 8, "sheet properties")
    if properties[2:4] != (6.0, 1.0):
        raise RuntimeError("slotted sheet scale must remain exactly 6:1")
    margins = _values([sheet.GetZoneMargin(i) for i in range(4)], 4, "zone margins")
    if any(value < 0 for value in margins):
        raise RuntimeError("slotted zone margins cannot be negative")
    top, bottom, right, left = margins
    views = {}
    for view in attachments.views(model).values():
        name = str(view.GetName2())
        if name in views:
            raise RuntimeError("slotted native view name is ambiguous")
        _same(adapter.swApp, part, view.ReferencedDocument, "view source")
        views[name] = {
            "orientation": str(view.GetOrientationName()),
            "scale": list(_values(view.ScaleRatio, 2, "view scale")),
            "outline": list(_values(view.GetOutline(), 4, "view outline")),
        }
    geometry = layout_geometry(
        bank, views, [left, bottom, properties[5] - right, properties[6] - top]
    )
    expected = {
        "Manufacturing Notes": spec.DRAWING_NOTES,
        "End View Note": spec.END_VIEW_NOTE,
    }
    source_text = read_required_properties(
        part, tuple(expected), required=tuple(expected)
    )
    if source_text != expected:
        raise RuntimeError("slotted exact source manufacturing notes changed")
    notes = {}
    for key, row in bank["annotations"].items():
        semantic = row["semantic"]
        if semantic["owner_type"] == 2 or semantic["kind"] != 6:
            continue
        annotation = handles[key][0]
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        linked, text = note.PropertyLinkedText, note.GetText()
        matches = [name for name in expected if linked == property_link(name)]
        if len(matches) != 1 or matches[0] in notes or text != expected[matches[0]]:
            raise RuntimeError(f"{key}: exact linked manufacturing note changed")
        notes[matches[0]] = {"annotation_key": key, "link": linked, "text": text}
    if notes.keys() != expected.keys():
        raise RuntimeError("slotted linked note inventory is incomplete")
    return {
        "sheet_properties": list(properties),
        "zone_margins_m": list(margins),
        "views": views,
        "geometry": geometry,
        "source_notes": source_text,
        "notes": notes,
    }


def read_pdf(pdf, png):
    """Reuse PDFium's full-page renderer without the preview's bottom-row crop."""
    import pypdfium2 as pdfium

    if not pdf.is_file() or png.exists():
        raise RuntimeError("slotted print requires an existing PDF and a fresh PNG")
    with pdfium.PdfDocument(str(pdf)) as document:
        if len(document) != 1:
            raise RuntimeError("slotted printed output must have exactly one page")
        page = document[0]
        try:
            textpage = page.get_textpage()
            try:
                glyphs = [
                    {
                        "text": textpage.get_text_range(i, 1),
                        "box_pt": list(textpage.get_charbox(i)),
                    }
                    for i in range(textpage.count_chars())
                ]
            finally:
                textpage.close()
            bitmap = page.render(scale=ASME_B_DPI / 72.0)
            try:
                image = bitmap.to_pil()
                raster = {
                    "size": list(image.size),
                    "mode": image.mode,
                    "pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                }
                image.save(png)
            finally:
                bitmap.close()
            page_size = list(page.get_size())
        finally:
            page.close()
    if not glyphs:
        raise RuntimeError("slotted PDF contains no text glyphs")
    return {
        "pdf": str(pdf),
        "png": str(png),
        "hashes": {
            "pdf": attachments.file_digest(pdf),
            "png": attachments.file_digest(png),
        },
        "page_size_pt": page_size,
        "glyphs": glyphs,
        "full_page_raster": raster,
        "scope": "uncropped whole-page pixels and PDF text; not PDF-object/CAD identity or raw vector equivalence",
    }


def require_pdf_content(printed, sheet, bank):
    """Require unique literal runs in their own native body; no symbol guessing."""
    page_width, page_height = _values(printed["page_size_pt"], 2, "PDF page")
    expected = {row["annotation_key"]: [row["text"]] for row in sheet["notes"].values()}
    expected.update(
        {
            row["annotation_key"]: row["native_text_values"]
            for row in bank["model_dimensions"]["dimensions"].values()
        }
    )
    observations = {}
    for key, values in expected.items():
        body = _rect(bank["annotations"][key]["measurement"]["body"])
        body_pt = Rect(*(value * 72.0 / 0.0254 for value in body.bounds))
        characters = []
        for glyph in printed["glyphs"]:
            text = glyph["text"]
            if not isinstance(text, str):
                raise RuntimeError("PDF glyph text has an unsupported type")
            if not text.strip():
                continue
            xmin, ymin, xmax, ymax = _values(glyph["box_pt"], 4, "PDF glyph")
            if (
                0 <= xmin < xmax <= page_width
                and 0 <= ymin < ymax <= page_height
                and body_pt.xmin <= xmin <= xmax <= body_pt.xmax
                and body_pt.ymin <= ymin <= ymax <= body_pt.ymax
            ):
                characters.append(text)
        actual = "".join(characters)
        required = ["".join(value.split()) for value in values if value.strip()]
        if not required or any(
            not value or actual.count(value) != 1 for value in required
        ):
            raise RuntimeError(
                f"{key}: exact printed text is absent, ambiguous or outside native body"
            )
        observations[key] = {
            "required": required,
            "body_text_without_whitespace": actual,
        }
    return observations


def capture(adapter, *, phase, bank, handles, source, outputs, record, checkpoint):
    """Observe one live phase. Only cold capture exports, with an empty native target.

    The pilot independently re-reads the complete native bank after this returns
    and compares exact same-session values and handles before cold acceptance.
    """
    from diagnostics.probe_retained_drawing_export import export_pdf_only

    if not isinstance(phase, CapturePhase):
        raise ValueError("slotted capture requires an explicit phase")
    if phase.value in record:
        raise RuntimeError("slotted phase cannot be captured twice")
    row = {"status": "running", "guard_errors": []}
    record[phase.value] = row
    model = part = None
    paths = (Path(source).resolve(), Path(outputs.slddrw).resolve())
    try:
        model, part = _owned_context(adapter, paths[0], paths[1])
        row["before"] = _state(model, part)
        row["hashes_before"] = {
            str(path): attachments.file_digest(path) for path in paths
        }
        row["sheet"] = sheet_witness(adapter, model, part, bank, handles)
        checkpoint()
        current, current_part = _owned_context(adapter, paths[0], paths[1])
        _same(adapter.swApp, model, current, "pre-export drawing")
        _same(adapter.swApp, part, current_part, "pre-export source")
        pdf = Path(outputs.pdf)
        if phase is CapturePhase.REOPENED:
            pdf = paths[1].parent / "slotted-cold.pdf"
            export_pdf_only(adapter, pdf)
        png = paths[1].parent / f"slotted-{phase.value}-full.png"
        row["printed"] = read_pdf(pdf, png)
        row["printed_content"] = require_pdf_content(row["printed"], row["sheet"], bank)
        row["status"] = "captured"
        return row
    except BaseException as error:
        row.update(status="failed", error=repr(error))
        raise
    finally:
        primary = sys.exception()
        errors = []
        if model is not None and part is not None:
            try:
                row["after"] = _state(model, part)
                current, current_part = _owned_context(adapter, paths[0], paths[1])
                _same(adapter.swApp, model, current, "final drawing")
                _same(adapter.swApp, part, current_part, "final source")
                if row.get("before") != row["after"]:
                    raise RuntimeError("slotted capture changed native dirty state")
            except BaseException as error:
                errors.append(error)
        row["hashes_after"] = {}
        for path in paths:
            try:
                row["hashes_after"][str(path)] = attachments.file_digest(path)
            except BaseException as error:
                errors.append(error)
        if (
            row.get("hashes_before") is not None
            and row["hashes_before"] != row["hashes_after"]
        ):
            errors.append(
                RuntimeError("slotted capture changed source/native file bytes")
            )
        row["guard_errors"] = [repr(error) for error in errors]
        if errors:
            row["status"] = "failed"
        try:
            checkpoint()
        except BaseException as error:
            errors.append(error)
            row["status"] = "failed"
            row["guard_errors"].append(repr(error))
        if primary is not None:
            for error in errors:
                primary.add_note(f"slotted capture guard: {error!r}")
        elif errors:
            raise errors[0]


def compare_cold(mode, record):
    before, after = (record[phase.value] for phase in CapturePhase)
    for snapshot in (before, after):
        for kind, digest in snapshot["printed"]["hashes"].items():
            if attachments.file_digest(Path(snapshot["printed"][kind])) != digest:
                raise RuntimeError("slotted retained print artifact changed")
    for key in ("page_size_pt", "glyphs", "full_page_raster"):
        if before["printed"][key] != after["printed"][key]:
            raise RuntimeError(f"slotted cold printed {key} changed")
    for key in ("source_notes", "notes", "sheet_properties", "zone_margins_m"):
        if before["sheet"][key] != after["sheet"][key]:
            raise RuntimeError(f"slotted cold {key} changed")
    for snapshot in (before, after):
        require_border(mode, snapshot["sheet"]["geometry"])
    record["comparison"] = "exact_print_and_declared_border_passed"


def capture_roles(adapter, annotations, handles, part, source_handles):
    """Read fresh parameter/view identity and the already captured raw slots."""
    roles = {}
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    views = attachments.views(model)
    for key, row in annotations.items():
        semantic = row["semantic"]
        if semantic["owner_type"] == 2 or semantic["kind"] == 6:
            continue
        if semantic["kind"] != 4:
            raise RuntimeError("slotted capture found an unexpected annotation role")
        annotation = handles[key][0]
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        parameter = _early_bound(display.GetDimension2(0), "IDimension")
        full_name = str(parameter.FullName)
        role = full_name.rsplit("@", 1)[0]
        if (
            role not in DIMENSION_VIEWS
            or role in roles
            or full_name not in source_handles
        ):
            raise RuntimeError("slotted capture imported dimension inventory differs")
        _same(
            adapter.swApp,
            parameter,
            source_handles[full_name],
            "imported source parameter",
        )
        _same(adapter.swApp, part.Parameter(role), parameter, "named source parameter")
        _same(adapter.swApp, display.GetAnnotation(), annotation, "display roundtrip")
        owners = [
            view
            for view in views.values()
            if adapter.swApp.IsSame(view, annotation.Owner) == 1
        ]
        if len(owners) != 1 or semantic["owner_type"] != 0:
            raise RuntimeError(
                "slotted capture dimension lacks a unique owned native view"
            )
        view = owners[0]
        _same(adapter.swApp, view.ReferencedDocument, part, "referenced source")
        orientation = str(view.GetOrientationName())
        if orientation != DIMENSION_VIEWS[role]:
            raise RuntimeError("slotted capture dimension is in the wrong native view")
        roles[role] = {
            "annotation_key": key,
            "full_name": full_name,
            "orientation": orientation,
            "display_type": display.Type2,
            "attachment_types": semantic["attachment_types"],
            "null_attachments": semantic["null_attachments"],
            "visible": semantic["visible"],
            "dangling": semantic["dangling"],
            "native_text_values": [row["value"] for row in row["generic"]["texts"]],
            "identity": "exact_live_view_source_parameter_roundtrip",
        }
    if roles.keys() != DIMENSION_VIEWS.keys():
        raise RuntimeError("slotted capture is missing a required imported dimension")
    return roles


async def capture_only(
    adapter, candidate, source_root, guard_root, output_root, *, setup_controller
):
    """One fixed slotted build for raw enrollment data, never an acceptance trial.

    Uses the existing owned session/copy, AST recipe loader, prepared factory and
    raw annotation/source readers. It neither writes a manifest nor runs cold
    acceptance against its own observations.
    """
    from _common import check
    from diagnostics import probe_datum_policy_recipes as pilot
    from diagnostics import _source_dimension_snapshot as source_reads
    from diagnostics._owned_native_documents import DocumentKind, save_drawing
    from diagnostics._recipe_template_factory import DrawingFactory

    require_capture_factors()
    if (
        candidate != PRODUCER_REVISION
        or setup_controller.variant is not DrawingFactory.PREPARED
    ):
        raise ValueError(
            "slotted capture requires the exact producer revision and prepared factory"
        )
    expected = {target: pilot.EXPECTED_PART_HASHES[target] for target in pilot.ORDER}
    expected["slotted_screw"] = SOURCE_SHA256
    paths = {
        Path(root / f"{target.replace('_', '-')}.SLDPRT").resolve(strict=True): sha
        for root in (source_root, guard_root)
        for target, sha in expected.items()
    }
    for path, sha in paths.items():
        if attachments.file_digest(path) != sha:
            raise RuntimeError(f"slotted capture immutable source pin differs: {path}")
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(
        tempfile.mkdtemp(prefix="slotted-attachment-capture-", dir=output_root)
    )
    adapter.ownership.register_directory(directory)
    report = {
        "status": "running",
        "acceptance": "not_accepted",
        "target": "slotted_screw",
        "candidate": candidate,
        "producer_revision": PRODUCER_REVISION,
        "source_readback_sha256": SOURCE_READBACK_SHA256,
        "helper_revision": pilot.benchmark.revision("HEAD"),
        "helpers": pilot.helper_fingerprints(),
        "adapter": pilot.adapter_fingerprints(),
        "sources_before": {str(path): sha for path, sha in paths.items()},
        "final_guard_errors": [],
        "scope": "raw imported attachment enrollment evidence only; no cold/print/manufacturing acceptance or speed claim",
    }
    report_path = directory / "capture.json"

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    copy_source = directory / f"slotted-screw-source-{directory.name}.SLDPRT"
    source_model = captured_model = None
    try:
        checkpoint()
        for path in paths:
            adapter.ownership.register_source(path)
        original = (source_root / "slotted-screw.SLDPRT").resolve(strict=True)
        shutil.copy2(original, copy_source)
        report.update(original_source=str(original), copy_source=str(copy_source))
        if attachments.file_digest(copy_source) != SOURCE_SHA256:
            raise RuntimeError("slotted capture owned copy differs before open")
        module = pilot.benchmark.load_recipe(
            candidate, "slotted_screw", directory, source=copy_source
        )
        report["recipe_sha256"] = attachments.file_digest(
            directory / "recipe-source.py"
        )
        await adapter.close_owned_documents()
        factory = await setup_controller.configure(adapter, module, report, directory)
        check(
            "open exact owned slotted source",
            await adapter.open_model(str(copy_source)),
        )
        adapter.ownership.assert_current_owned()
        source_model = _early_bound(adapter.currentModel, "IModelDoc2")
        if (
            source_model.GetType() != 1
            or Path(source_model.GetPathName()).resolve() != copy_source
        ):
            raise RuntimeError("slotted capture opened the wrong copied source")
        _same(
            adapter.swApp,
            source_model,
            adapter.swApp.ActiveDoc,
            "initial copied source",
        )
        report["source_dirty_before"] = source_model.GetSaveFlag()
        if report["source_dirty_before"] is not False:
            raise RuntimeError(
                "slotted capture requires an initially clean source dirty flag (native False)"
            )
        report["source_before"], source_handles = source_reads.dimension_snapshot(
            adapter.swApp,
            source_model,
            copy_source,
            required=spec.DRAWING_DIMENSIONS,
        )
        if source_model.GetSaveFlag() != report["source_dirty_before"]:
            raise RuntimeError("slotted source read changed dirty state")
        properties = read_required_properties(
            source_model,
            ("Generator", "Manufacturing Notes", "End View Note"),
            required=("Generator", "Manufacturing Notes", "End View Note"),
        )
        report["source_properties"] = properties
        if properties != {
            "Generator": "harmonic-analyzer @ 3c0c4a97",
            "Manufacturing Notes": spec.DRAWING_NOTES,
            "End View Note": spec.END_VIEW_NOTE,
        }:
            raise RuntimeError("slotted capture source producer/notes differ")
        adapter.ownership.assert_current_owned()
        _same(adapter.swApp, source_model, adapter.currentModel, "pre-build source")
        _same(
            adapter.swApp,
            source_model,
            adapter.swApp.ActiveDoc,
            "pre-build active source",
        )
        if source_model.GetSaveFlag() != report["source_dirty_before"]:
            raise RuntimeError("slotted source property reads changed dirty state")
        checkpoint()
        started = time.perf_counter()
        try:
            with adapter.ownership.creating_document(
                DocumentKind.DRAWING, module.OUTPUTS.slddrw
            ):
                with patch("_drawing_common.save_drawing", save_drawing):
                    artifacts = await module.build(adapter, drawing_factory=factory)
            setup_controller.require_used()
        finally:
            report["recipe_seconds"] = time.perf_counter() - started
            checkpoint()
        report["artifacts"] = pilot.benchmark.validate_artifacts(
            artifacts, module.OUTPUTS
        )
        model, part = _owned_context(adapter, copy_source, module.OUTPUTS.slddrw)
        captured_model = model
        _same(adapter.swApp, source_model, part, "post-build source")
        report["capture_before"] = _state(model, part)
        report["annotations"], handles = pilot.shoulder.all_annotation_layout(adapter)
        checkpoint()  # Keep raw slots even if a later role/identity check rejects.
        report["roles"] = capture_roles(
            adapter, report["annotations"], handles, part, source_handles
        )
        report["source_after"], after_handles = source_reads.dimension_snapshot(
            adapter.swApp,
            part,
            copy_source,
            required=spec.DRAWING_DIMENSIONS,
        )
        source_reads.compare_source(
            report["source_before"],
            report["source_after"],
            app=adapter.swApp,
            handles_before=source_handles,
            handles_after=after_handles,
        )
        if report["source_before"] != report["source_after"]:
            raise RuntimeError("slotted capture source presentation changed")
        report["capture_after"] = _state(model, part)
        if report["capture_before"] != report["capture_after"]:
            raise RuntimeError("slotted attachment reads changed native dirty state")
        _owned_context(adapter, copy_source, module.OUTPUTS.slddrw)
        report["status"] = "capture_only"
    except BaseException as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        primary = sys.exception()
        errors = []
        if captured_model is not None:
            try:
                report["capture_final"] = _state(captured_model, source_model)
                if report.get("capture_before") != report["capture_final"]:
                    raise RuntimeError(
                        "slotted attachment reads changed native dirty state"
                    )
            except BaseException as error:
                errors.append(error)
        if source_model is not None:
            try:
                report["source_dirty_final"] = source_model.GetSaveFlag()
                if (
                    report.get("source_dirty_before") is not False
                    or report["source_dirty_final"] is not False
                ):
                    raise RuntimeError(
                        "slotted capture source dirty flag changed or is not native False"
                    )
            except BaseException as error:
                errors.append(error)
        try:
            await adapter.close_owned_documents()
        except BaseException as error:
            errors.append(error)
        report["sources_after"] = {}
        for path, expected_sha in (*paths.items(), (copy_source, SOURCE_SHA256)):
            try:
                actual = attachments.file_digest(path)
                report["sources_after"][str(path)] = actual
                if actual != expected_sha:
                    raise RuntimeError(
                        f"slotted capture final source bytes changed: {path}"
                    )
            except BaseException as error:
                errors.append(error)
        for name, reader in (
            ("helpers", pilot.helper_fingerprints),
            ("adapter", pilot.adapter_fingerprints),
        ):
            try:
                report[f"{name}_after"] = reader()
                if report[name] != report[f"{name}_after"]:
                    raise RuntimeError(f"slotted capture runtime {name} changed")
            except BaseException as error:
                errors.append(error)
        try:
            errors.extend(setup_controller.final_guards())
            report["factory_final_guards"] = setup_controller.guards
        except BaseException as error:
            errors.append(error)
        report["final_guard_errors"] = [repr(error) for error in errors]
        if errors:
            report["status"] = "failed"
        try:
            checkpoint()
        except BaseException as error:
            errors.append(error)
        if primary is not None:
            for error in errors:
                primary.add_note(f"slotted capture final guard: {error!r}")
        elif errors:
            raise errors[0]
    return {"report": str(report_path), "acceptance": "not_accepted"}
