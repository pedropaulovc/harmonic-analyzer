"""Fresh linked-title baseline, then ONE chosen update only after reproduction.

Create a project-template drawing with one Front view of an exact, uniquely
named owned rocker-part bytecopy. Call the production finalizer unchanged.
Diagnostic wrappers observe the late property and native/PDF save boundaries;
the explicit candidate adds a redraw, one checked EditRebuild3, or reapplication
of the title's existing horizontal justification plus its documented redraw,
immediately before native SaveAs3. No position writes, geometry picks, other
added rebuilds, default changes, or full recipe.

Each trial closes all and ONLY owned documents, cold-opens its saved drawing,
and exports a second PDF without native save or redraw. A candidate is authorized
only by a material rigid first-PDF/cold-PDF title displacement with changed PNG
pixels in this fresh baseline. A non-reproduction is inconclusive, not success.
Originals, template and owned source-copy bytes remain exact; full native title
and annotation deltas are evidence, never normalized into an equality pass.

API references: ISheet.CustomPropertyView, IModelDoc2.GraphicsRedraw2/EditRebuild3,
official Redraw_Graphics_Example_VB/Rebuild_Example_VB; INote.GetText/PropertyLinkedText/GetExtent/
GetTextJustification/GetTextVerticalJustification/LockPosition. GraphicsRedraw2
is obsolete but documented and already used by this project. This tests its
known no-argument form, not an inferred missing-rebuild cause.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
from enum import StrEnum
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

import _common as common  # noqa: E402
import _drawing_common as drawing  # noqa: E402
import _telemetry  # noqa: E402
from _common import _early_bound, check  # noqa: E402
from diagnostics import probe_retained_drawing_export as retained  # noqa: E402
from diagnostics import probe_datum_policy_recipes as pilot  # noqa: E402
from diagnostics.audit_drawing_snapshot_delta import audit_pair, changed_leaves  # noqa: E402
from diagnostics._owned_native_documents import DocumentKind, run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from solidworks_mcp.adapters.solidworks.drawing import place_view  # noqa: E402

TITLE = "rocker-arm"
TITLE_LINK = '$PRPSHEET:"SW-Title(Title)"'
EXPECTED_SOURCE_SHA256 = pilot.EXPECTED_PART_HASHES["rocker_arm"]
# Layout-only constants copied from the current rocker Front view; no feature pick.
FRONT_CENTER, SCALE = (0.180, 0.175), (1.0, 2.0)


class Variant(StrEnum):
    BASELINE = "baseline"
    REDRAW = "pre_save_redraw"
    EDIT_REBUILD = "pre_save_edit_rebuild"
    REJUSTIFY = "pre_save_rejustify"


def require_title_style(before, after):
    fields = (
        "key",
        "linked_text",
        "horizontal_justification",
        "vertical_justification",
        "locked",
    )
    if changed_leaves(
        {field: before[field] for field in fields},
        {field: after[field] for field in fields},
    ):
        raise RuntimeError("title link/justification/lock style changed")


def _finite(values, length, label):
    values = tuple(float(value) for value in values or ())
    if len(values) != length or not all(math.isfinite(value) for value in values):
        raise RuntimeError(
            f"{label}: incomplete/non-finite native geometry: {values!r}"
        )
    return values


def find_title(adapter):
    matches = []
    for sheet in _early_bound(adapter.currentModel, "IDrawingDoc").GetViews() or ():
        for raw_view in sheet:
            view = _early_bound(raw_view, "IView")
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                if int(annotation.GetType()) != 6 or int(annotation.OwnerType) != 2:
                    continue
                note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
                if str(note.PropertyLinkedText) == TITLE_LINK:
                    matches.append(
                        (f"{view.GetName2()}/{annotation.GetName()}", annotation)
                    )
    if len(matches) != 1:
        raise RuntimeError(
            "fresh template requires one exact sheet-format part-title link"
        )
    return matches[0]


class TitleObserver:
    """Cached exact title handle; no repeated full-document measurements."""

    def __init__(self, adapter, trial, checkpoint):
        self.adapter, self.trial, self.checkpoint = adapter, trial, checkpoint
        self.model = adapter.currentModel
        self.key, self.annotation = find_title(adapter)
        self.owner = self.annotation.Owner
        self.trial["title_key"] = self.key
        self.trial["title_stages"] = []
        self.initial = None

    def record(self, stage):
        # During native SaveAs the shared saving_as scope has not yet updated
        # its recorded path/title. Verify handles here; that scope subsequently
        # performs its full path/inventory/source verification unchanged.
        app, model, annotation = (
            self.adapter.swApp,
            self.adapter.currentModel,
            self.annotation,
        )
        if (
            int(app.IsSame(model, self.model)) != 1
            or int(app.IsSame(app.ActiveDoc, model)) != 1
            or int(model.GetType()) != 3
            or not bool(model.Visible)
            or int(annotation.GetType()) != 6
            or int(annotation.OwnerType) != 2
            or str(annotation.GetName()) != self.key.split("/", 1)[1]
        ):
            raise RuntimeError(
                "title observation lost its exact visible owned drawing/note"
            )
        owner = annotation.Owner
        if (owner is None) != (self.owner is None) or (
            owner is not None and int(app.IsSame(owner, self.owner)) != 1
        ):
            raise RuntimeError("title native owner was replaced")
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        ddoc = _early_bound(model, "IDrawingDoc")
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        generic = pilot.shoulder.raw_display_data(annotation)
        row = {
            "stage": stage,
            "path": str(model.GetPathName()),
            "property_view": str(sheet.CustomPropertyView),
            "unit_display": str(model.GetCustomInfoValue("", "UNIT_DISPLAY")),
            "key": self.key,
            "text": str(note.GetText()),
            "linked_text": str(note.PropertyLinkedText),
            "horizontal_justification": int(note.GetTextJustification()),
            "vertical_justification": int(note.GetTextVerticalJustification()),
            "locked": bool(note.LockPosition),
            "position": _finite(annotation.GetPosition(), 3, "title position"),
            "extent": _finite(note.GetExtent(), 6, "title extent"),
            "generic": generic,
        }
        if (
            row["linked_text"] != TITLE_LINK
            or row["horizontal_justification"] not in (0, 1, 2, 3)
            or row["vertical_justification"] not in (0, 1, 2)
        ):
            raise RuntimeError("title link or standard-note alignment changed")
        if (
            stage
            in {
                "before_native_save",
                "after_pre_save_edit_rebuild",
                "after_pre_save_rejustify",
                "after_pre_save_rejustify_redraw",
                "after_native_save",
                "before_pdf_export",
                "after_pdf_export",
                "cold_open",
                "after_cold_pdf",
            }
            and row["text"] != TITLE
        ):
            raise RuntimeError(
                f"{stage}: title did not resolve to exact owned-part summary"
            )
        self.trial["title_stages"].append(row)
        self.checkpoint()
        if self.initial is not None:
            require_title_style(self.initial, row)
        if self.initial is None:
            self.initial = row
        return row


@contextmanager
def finalizer_observations(adapter, observer, variant):
    """Keep finalizer bytes/calls, compose observers, and restore on every exit."""
    if not isinstance(variant, Variant):
        raise TypeError("title update variant must be explicit")
    original_properties, original_save = (
        common.apply_custom_properties,
        drawing.save_drawing,
    )
    counts = {
        "properties": 0, "drawing": 0, "pdf": 0,
        "redraw": 0, "edit_rebuild": 0, "justification": 0,
    }

    def properties(current, values):
        if (
            current is not adapter
            or values != {"UNIT_DISPLAY": "MM"}
            or counts["properties"]
        ):
            raise RuntimeError("unexpected finalizer property call")
        observer.record("after_property_link_before_unit")
        result = original_properties(current, values)
        counts["properties"] += 1
        observer.record("after_unit_property")
        return result

    def save(current, path, *, artifact_context=None, **kwargs):
        if current is not adapter or counts["properties"] != 1:
            raise RuntimeError(
                "finalizer save lacks the expected adapter/property boundary"
            )

        @contextmanager
        def observe(kind, target):
            if kind not in ("drawing", "pdf") or counts[kind]:
                raise RuntimeError("unexpected/repeated finalizer artifact")
            if kind == "pdf" and counts["drawing"] != 1:
                raise RuntimeError("PDF must follow the one native drawing save")
            counts[kind] += 1
            phase = "native_save" if kind == "drawing" else "pdf_export"
            observer.record(f"before_{phase}")
            if kind == "drawing" and variant is Variant.REDRAW:
                with _telemetry.span("diagnostic.fresh_title.redraw"):
                    current.currentModel.GraphicsRedraw2()  # Official void/no-arg form.
                counts["redraw"] += 1
                observer.record("after_pre_save_redraw")
            if kind == "drawing" and variant is Variant.EDIT_REBUILD:
                counts["edit_rebuild"] += 1
                with _telemetry.span("diagnostic.fresh_title.edit_rebuild") as span:
                    returned = current.currentModel.EditRebuild3()
                    span.set_attribute("native_return", repr(returned))
                    if returned is not True:
                        raise RuntimeError(
                            f"pre-save EditRebuild3 did not return True: {returned!r}"
                        )
                observer.record("after_pre_save_edit_rebuild")
            if kind == "drawing" and variant is Variant.REJUSTIFY:
                note = _early_bound(observer.annotation.GetSpecificAnnotation(), "INote")
                justification = int(note.GetTextJustification())
                with _telemetry.span("diagnostic.fresh_title.rejustify"):
                    # INote.SetTextJustification is void. Preserve the existing
                    # native alignment and verify it through the exact observer.
                    counts["justification"] += 1
                    note.SetTextJustification(justification)
                    observer.record("after_pre_save_rejustify")
                    # The setter's official documentation requires a redraw.
                    counts["redraw"] += 1
                    current.currentModel.GraphicsRedraw2()
                    observer.record("after_pre_save_rejustify_redraw")
            with artifact_context(kind, target) if artifact_context else nullcontext():
                yield
            observer.record(f"after_{phase}")

        with adapter.ownership.saving_as(path):
            return original_save(current, path, artifact_context=observe, **kwargs)

    common.apply_custom_properties, drawing.save_drawing = properties, save
    try:
        yield counts
        expected = {
            "properties": 1,
            "drawing": 1,
            "pdf": 1,
            "redraw": int(variant in (Variant.REDRAW, Variant.REJUSTIFY)),
            "edit_rebuild": int(variant is Variant.EDIT_REBUILD),
            "justification": int(variant is Variant.REJUSTIFY),
        }
        if counts != expected:
            raise RuntimeError(
                f"finalizer call inventory differs: {counts} != {expected}"
            )
    finally:
        common.apply_custom_properties, drawing.save_drawing = (
            original_properties,
            original_save,
        )


def printed_displacement(before, after):
    """Classify an experiment; never round/accept a native or PDF comparator."""
    if (
        before["text"] != TITLE
        or after["text"] != TITLE
        or before["page_size_pt"] != after["page_size_pt"]
    ):
        raise RuntimeError("PDF title text/page changed")
    rows_before, rows_after = before["characters"], after["characters"]
    if len(rows_before) != len(TITLE) or len(rows_after) != len(TITLE):
        raise RuntimeError("PDF title glyph multiplicity changed")
    deltas = []
    for letter, left, right in zip(TITLE, rows_before, rows_after, strict=True):
        if left["text"] != letter or right["text"] != letter:
            raise RuntimeError("PDF title character changed")
        a, b = (
            _finite(left["box_pt"], 4, "PDF glyph"),
            _finite(right["box_pt"], 4, "PDF glyph"),
        )
        if any(box[0] > box[2] or box[1] > box[3] for box in (a, b)):
            raise RuntimeError("PDF glyph has inverted bounds")
        deltas.append(tuple(y - x for x, y in zip(a, b)))
    dx, dy = deltas[0][:2]
    residual = max(
        abs(value - (dx, dy, dx, dy)[i])
        for row in deltas
        for i, value in enumerate(row)
    )
    classification = "nonrigid_delta"
    if not any(value for row in deltas for value in row):
        classification = "unchanged"
    elif residual <= 0.001:
        # These are diagnostic reproduction thresholds only: one rendered
        # 300-DPI pixel and a 0.001-point PDF coordinate representation spread.
        classification = (
            "reproduced"
            if math.hypot(dx, dy) >= 72 / drawing.ASME_B_DPI
            else "subpixel_delta"
        )
    return {
        "classification": classification,
        "displacement_pt": (dx, dy),
        "displacement_mm": (dx * 25.4 / 72, dy * 25.4 / 72),
        "maximum_rigid_residual_pt": residual,
        "glyph_deltas_pt": deltas,
    }


async def run_pair(trial, selected):
    if not isinstance(selected, Variant) or selected is Variant.BASELINE:
        raise ValueError("an explicit non-baseline title update candidate is required")
    baseline = await trial(Variant.BASELINE)
    if baseline["printed"]["classification"] != "reproduced":
        return "inconclusive_baseline_not_reproduced"
    if baseline["png_delta"]["changed_pixel_count"] <= 0:
        raise RuntimeError("PDF displacement lacks changed rendered pixels")
    candidate = await trial(selected)
    if (
        candidate["printed"]["classification"] == "unchanged"
        and candidate["png_delta"]["changed_pixel_count"] == 0
    ):
        return "candidate_printed_stable"
    return "candidate_not_stable"


def require_cold_semantics(before, after):
    pilot.attachments.compare(
        before["semantics"], after["semantics"], "fresh title cold reopen"
    )
    pilot.attachments.check_layout(
        before["layout"], after["layout"], "fresh title cold reopen"
    )
    if before["annotations"].keys() != after["annotations"].keys():
        raise RuntimeError("fresh title cold reopen changed annotation inventory")
    for key, row in before["annotations"].items():
        if changed_leaves(
            retained.serialized(row["semantic"]),
            retained.serialized(after["annotations"][key]["semantic"]),
        ):
            raise RuntimeError(
                f"{key}: fresh title cold reopen changed annotation semantics"
            )


def require_inputs(source, guard):
    expected = {str(path): EXPECTED_SOURCE_SHA256 for path in (source, guard)}
    retained.require_hashes(expected, "fresh title original source")
    expected[str(drawing.PROJECT_DRWDOT)] = pilot.attachments.file_digest(
        drawing.PROJECT_DRWDOT
    )
    return expected


async def one_trial(adapter, variant, source, directory, report, checkpoint, expected):
    trial_dir = directory / variant.value
    trial_dir.mkdir()
    adapter.ownership.register_directory(trial_dir)
    copy_source = trial_dir / f"rocker-source-{directory.name}-{variant.value}.SLDPRT"
    shutil.copy2(source, copy_source)
    copy_expected = {str(copy_source): EXPECTED_SOURCE_SHA256}
    retained.require_hashes(copy_expected, "exact fresh title part copy")
    stem = f"title-{directory.name}-{variant.value}"
    outputs = drawing.DrawingOutputs(
        trial_dir / f"{stem}.SLDDRW",
        trial_dir / f"{stem}.pdf",
        trial_dir / f"{stem}.png",
    )
    trial = {
        "variant": variant.value,
        "status": "running",
        "source_copy": str(copy_source),
        "copy_hashes": {"initial": EXPECTED_SOURCE_SHA256},
    }
    report["trials"].append(trial)
    checkpoint()
    started = time.perf_counter()
    try:
        check(
            "open unique fresh title source", await adapter.open_model(str(copy_source))
        )
        source_model = adapter.currentModel
        trial["source_before"], source_handles = pilot.source_dimensions(
            source_model, "rocker_arm", copy_source
        )
        if str(source_model.SummaryInfo(0)) != TITLE:
            raise RuntimeError(
                "owned source does not contain the exact saved summary Title"
            )
        with adapter.ownership.creating_document(DocumentKind.DRAWING, outputs.slddrw):
            drawing.new_project_drawing(adapter, scale=SCALE)
            observer = TitleObserver(adapter, trial, checkpoint)
            observer.record("after_blank_setup")
            view = place_view(
                adapter, str(copy_source), "*Front", *FRONT_CENTER, scale=SCALE
            )
            if (
                view is None
                or int(adapter.swApp.IsSame(view.ReferencedDocument, source_model)) != 1
            ):
                raise RuntimeError("fresh Front view has the wrong exact source owner")
            observer.record("after_front_view")
            observer.record("before_finalizer_properties")
            with finalizer_observations(adapter, observer, variant) as counts:
                artifacts = await drawing.finalize_drawing(
                    adapter,
                    outputs,
                    pdf_title="Fresh linked title control",
                    scale=SCALE,
                )
            trial["call_counts"] = dict(counts)
        trial["artifacts"] = pilot.benchmark.validate_artifacts(artifacts, outputs)
        retained.require_hashes(copy_expected, "after first native/PDF export")
        trial["built"], built_handles = retained.capture_drawing(
            adapter, copy_source, trial["source_before"]["configuration"]
        )
        if (
            int(
                adapter.swApp.IsSame(
                    observer.annotation, built_handles[observer.key][0]
                )
            )
            != 1
        ):
            raise RuntimeError(
                "title annotation was replaced during fresh construction"
            )
        trial["source_after"], after_handles = pilot.source_dimensions(
            source_model, "rocker_arm", copy_source
        )
        pilot.require_same_source(
            trial["source_before"],
            trial["source_after"],
            "fresh title build",
            app=adapter.swApp,
            handles_before=source_handles,
            handles_after=after_handles,
        )
        trial["first_pdf_title"] = retained.pdf_title(outputs.pdf)
        native_expected = {
            str(outputs.slddrw): pilot.attachments.file_digest(outputs.slddrw)
        }
        await adapter.close_owned_documents()
        retained.require_hashes(copy_expected, "after owned source no-save close")
        check(
            "cold open fresh title drawing",
            await adapter.open_model(str(outputs.slddrw)),
        )
        # New handle after cold reopen: never redraw this already-resolved copy.
        cold_trial = {"title_stages": []}
        trial["cold_title"] = cold_trial
        cold = TitleObserver(adapter, cold_trial, checkpoint)
        cold_open = cold.record("cold_open")
        require_title_style(trial["title_stages"][-1], cold_open)
        trial["reopened"], cold_handles = retained.capture_drawing(
            adapter, copy_source, trial["source_before"]["configuration"]
        )
        reopened_source = adapter.swApp.GetOpenDocumentByName(str(copy_source))
        trial["source_reopened"], cold_source_handles = pilot.source_dimensions(
            reopened_source, "rocker_arm", copy_source
        )
        pilot.require_same_source(
            trial["source_before"],
            trial["source_reopened"],
            "fresh title source cold reopen",
        )
        trial["cold_delta"] = audit_pair(
            retained.serialized(trial["built"]), retained.serialized(trial["reopened"])
        )
        require_cold_semantics(trial["built"], trial["reopened"])
        cold_pdf, cold_png = trial_dir / "cold.pdf", trial_dir / "cold.png"
        retained.export_pdf_only(adapter, cold_pdf)
        cold.record("after_cold_pdf")
        trial["after_cold_pdf"], after_cold_handles = retained.capture_drawing(
            adapter, copy_source, trial["source_before"]["configuration"]
        )
        trial["source_after_cold_pdf"], after_cold_source_handles = (
            pilot.source_dimensions(reopened_source, "rocker_arm", copy_source)
        )
        pilot.require_same_source(
            trial["source_reopened"],
            trial["source_after_cold_pdf"],
            "cold PDF source",
            app=adapter.swApp,
            handles_before=cold_source_handles,
            handles_after=after_cold_source_handles,
        )
        trial["cold_export_delta"] = audit_pair(
            retained.serialized(trial["reopened"]),
            retained.serialized(trial["after_cold_pdf"]),
        )
        changes = pilot.shoulder.compare_all_annotation_layout(
            adapter.swApp,
            trial["reopened"]["annotations"],
            trial["after_cold_pdf"]["annotations"],
            cold_handles,
            after_cold_handles,
        )
        if changes:
            raise RuntimeError(
                f"no-setter cold PDF export changed live annotation layout: {changes}"
            )
        require_cold_semantics(trial["reopened"], trial["after_cold_pdf"])
        drawing.render_pdf_png(cold_pdf, cold_png)
        trial["cold_artifacts"] = {"pdf": str(cold_pdf), "png": str(cold_png)}
        trial["cold_pdf_title"] = retained.pdf_title(cold_pdf)
        trial["printed"] = printed_displacement(
            trial["first_pdf_title"], trial["cold_pdf_title"]
        )
        trial["png_delta"] = retained.compare_png(outputs.png, cold_png)
        retained.require_hashes(native_expected, "cold PDF did not save native drawing")
        retained.require_hashes(copy_expected, "cold PDF did not save source copy")
        retained.require_hashes(expected, "fresh title protected originals/template")
        await adapter.close_owned_documents()
        retained.require_hashes(native_expected, "after cold no-save close")
        retained.require_hashes(copy_expected, "after cold source no-save close")
        trial["status"] = "observed"
    except Exception as error:
        trial.update(status="failed", error=repr(error))
        raise
    finally:
        trial["seconds"] = time.perf_counter() - started
        trial["copy_hashes"]["final"] = retained.final_hashes(copy_expected)[
            str(copy_source)
        ]
        checkpoint()
    return trial


async def probe(adapter, source, guard, output_root, candidate):
    expected = require_inputs(source, guard)
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="fresh-title-", dir=output_root))
    adapter.ownership.register_directory(directory)
    for path in expected:
        adapter.ownership.register_source(Path(path))
    report_path = directory / "title-update.json"
    report = {
        "status": "running",
        "candidate": candidate.value,
        "inputs_before": expected,
        "trials": [],
        "revision": pilot.benchmark.revision("HEAD"),
        "helpers": pilot.helper_fingerprints(),
        "imported_adapter": pilot.adapter_fingerprints(),
        "scope": "fresh linked-title experiment, not a full recipe or whole-sheet acceptance; all raw deltas retained",
    }

    def checkpoint():
        report_path.write_text(
            json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
        )

    checkpoint()
    _telemetry.info("fresh title control report", path=str(report_path))
    try:

        async def run(variant):
            with _telemetry.span("diagnostic.fresh_title.trial", variant=variant.value):
                result = await one_trial(
                    adapter, variant, source, directory, report, checkpoint, expected
                )
            pilot.benchmark.check_fingerprints(
                report["helpers"],
                pilot.helper_fingerprints(),
                "frozen title control helpers/config/template",
            )
            if report["imported_adapter"] != pilot.adapter_fingerprints():
                raise RuntimeError(
                    "actual imported adapter changed during title control"
                )
            return result

        report["outcome"] = await run_pair(run, candidate)
        report["status"] = "observed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        report["inputs_after"] = retained.final_hashes(expected)
        checkpoint()
    return {"report": str(report_path), "outcome": report["outcome"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--guard-source", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument(
        "--candidate",
        type=Variant,
        choices=(Variant.REDRAW, Variant.EDIT_REBUILD, Variant.REJUSTIFY),
        required=True,
    )
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if (
        os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off"
        or not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID", "").isdecimal()
    ):
        raise RuntimeError(
            "fresh title control requires remote cache off and expected existing PID"
        )
    source, guard = (
        args.source.resolve(strict=True),
        args.guard_source.resolve(strict=True),
    )
    require_inputs(source, guard)
    if not args.worker:
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--source",
                str(source),
                "--guard-source",
                str(guard),
                "--report-root",
                str(args.report_root.resolve()),
                "--candidate",
                args.candidate.value,
                "--worker",
            ],
            "fresh linked-title update control",
            com=True,
            log_stem="fresh-title-update",
        )
        return 0
    return run_copy_diagnostic(
        lambda adapter: probe(
            adapter, source, guard, args.report_root.resolve(), args.candidate
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
