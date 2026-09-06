"""One native GTol length override on a coherent saved rocker drawing COPY.

The documented Insert_GTol C# example sets IAnnotation.BentLeaderLength after
SetLeader3(swBENT). This control starts with an existing swBENT GTol and changes
ONLY its length to 6.35 mm; it never calls SetLeader3 or UseDocDispLeader.
The source drawing's document length must remain 73.30296548073768 mm.
Immediate/full/reopened native geometry, XML, attachments, dimension values and
tolerance types are captured, with before/after/reopened PDF/PNG exports.

Existing visible documents may remain open, including an unsaved failed build.
Their exact native handles, paths, titles, kind, dirty flag and visibility are
witnessed before opening, before mutations/close, and after owned-copy close.
Hidden pre-existing documents are refused: documented CloseDoc can close hidden
documents too. No pre-existing document, original drawing or source reference
is ever a close target. Unknown/replaced documents cause a fail-loud refusal.

Control 9eef747b (gtol-leader-override-h_wiopl4, 2026-09-06) positively retained
6.35 mm through save/reopen, unchanged document default, XML/geometry/values and
source hashes. Its first immediate GetLeaderPoints read remained stale; the
subsequent display-data measurement already had the correct 6.35 mm geometry.
The strict pre-export length assertion deliberately failed. --update-boundary
edit_rebuild tests one explicit EditRebuild3 before that exact read, preserving
the original immediate control and every final assertion.
That variant passed at 108fe65a (gtol-leader-override-fd4f_eux): exact before-export
and reopened 6.35 mm geometry, unchanged body/attachments and identical PNGs.
--length-scope gtol_default independently tests the document's GTol-family
defaults on a fresh source copy; it never writes an individual annotation length.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from enum import StrEnum
import math
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
from _drawing_annotation_bounds import annotation_box  # noqa: E402
from diagnostics._owned_native_session import (  # noqa: E402
    require_owned_diagnostic_environment,
    run_owned_diagnostic,
)
from diagnostics import probe_datum_shoulder as shoulder  # noqa: E402
from diagnostics import probe_drawing_attachments as attachments  # noqa: E402
from diagnostics.probe_native_model_pmi import file_digest, render_pdf_png  # noqa: E402
import _telemetry  # noqa: E402

DOCUMENT_LENGTH_M = 0.07330296548073768
OVERRIDE_LENGTH_M = 0.00635
EPSILON = 1e-8


class UpdateBoundary(StrEnum):
    IMMEDIATE = "immediate"
    EDIT_REBUILD = "edit_rebuild"


class LengthScope(StrEnum):
    ANNOTATION = "annotation"
    GTOL_DEFAULT = "gtol_default"


def gtol_defaults(extension):
    constants = shoulder._installed_swconst()
    option = int(constants.swDetailingNoOptionSpecified)
    toggle = int(constants.swDetailingGtolUseDocBentLeaderLength)
    length = int(constants.swDetailingGtolBentLeaderLength)
    value = float(extension.GetUserPreferenceDouble(length, option))
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError(
            "GTol-family native default length must be positive and finite"
        )
    return {
        "use_global_document_length": bool(
            extension.GetUserPreferenceToggle(toggle, option)
        ),
        "length_m": value,
        "toggle_enum": toggle,
        "length_enum": length,
        "option_enum": option,
    }


def verify_gtol_defaults(state):
    if (
        state["use_global_document_length"]
        or not math.isfinite(state["length_m"])
        or abs(state["length_m"] - OVERRIDE_LENGTH_M) > EPSILON
    ):
        raise RuntimeError(
            "native GTol-family default did not retain its independent 6.35mm policy"
        )


def apply_length_scope(annotation, extension, scope):
    if scope is LengthScope.ANNOTATION:
        annotation.BentLeaderLength = OVERRIDE_LENGTH_M
        return {"operation": scope.value}
    if scope is not LengthScope.GTOL_DEFAULT:
        raise ValueError("unknown native length scope")
    before = gtol_defaults(extension)
    toggle_returned = bool(
        extension.SetUserPreferenceToggle(
            before["toggle_enum"], before["option_enum"], False
        )
    )
    # SetUserPreferenceToggle documents its Boolean as the resulting state;
    # False is legitimate for the requested OFF value. Preserve that return and
    # require the explicit getter, rather than treating False as failed success.
    toggle_actual = bool(
        extension.GetUserPreferenceToggle(before["toggle_enum"], before["option_enum"])
    )
    if toggle_actual:
        raise RuntimeError(
            "GTol-family default still inherits the global document length"
        )
    length_returned = bool(
        extension.SetUserPreferenceDouble(
            before["length_enum"], before["option_enum"], OVERRIDE_LENGTH_M
        )
    )
    if not length_returned:
        raise RuntimeError(
            "native GTol-family default length setter rejected its value"
        )
    after = gtol_defaults(extension)
    verify_gtol_defaults(after)
    return {
        "operation": scope.value,
        "before": before,
        "after": after,
        "toggle_returned": toggle_returned,
        "toggle_actual": toggle_actual,
        "length_returned": length_returned,
    }


def update_boundary(model, boundary):
    if boundary is UpdateBoundary.IMMEDIATE:
        return {"operation": boundary.value}
    if boundary is not UpdateBoundary.EDIT_REBUILD:
        raise ValueError("unknown native update boundary")
    returned = bool(model.EditRebuild3())
    if not returned:
        raise RuntimeError("explicit native EditRebuild3 rejected the update")
    return {"operation": boundary.value, "returned": returned}


def verify_layout_changes(changes, target):
    if set(changes) - {target["inventory_key"]}:
        raise RuntimeError("one GTol setter changed other annotation native layout")


def document_state(document):
    return {
        "path": str(document.GetPathName()),
        "title": str(document.GetTitle()),
        "kind": int(document.GetType()),
        "dirty": bool(document.GetSaveFlag()),
        "visible": bool(document.Visible),
    }


class ExistingSessionCopy(shoulder.OwnedDrawingCopy):
    """A unique copy alongside an immutable, explicitly witnessed native bank."""

    def __init__(self, adapter, directory, source_part, source_drawing):
        self.adapter = adapter
        self.app = _early_bound(adapter.swApp, "ISldWorks")
        self.directory = directory.resolve()
        self.source_part = source_part.resolve()
        self.handle = self.reference = self.expected = None
        self.paths, self.titles = set(), {}
        self.baseline = tuple(
            (
                _early_bound(raw, "IModelDoc2"),
                document_state(_early_bound(raw, "IModelDoc2")),
            )
            for raw in self.app.GetDocuments() or ()
        )
        protected_names = {source_part.name.casefold(), source_drawing.name.casefold()}
        for _document, state in self.baseline:
            if not state["visible"]:
                raise RuntimeError(
                    f"hidden pre-existing document prevents safe scoped CloseDoc: {state}"
                )
            if state["path"] and Path(state["path"]).name.casefold() in protected_names:
                raise RuntimeError(
                    "source drawing/part is already open; coherent isolation not proven"
                )
        self._inventory()

    def _inventory(self, owned=None):
        found, baseline_found, paths = [], set(), set()
        for raw in self.app.GetDocuments() or ():
            document = _early_bound(raw, "IModelDoc2")
            baseline = [
                index
                for index, (original, _) in enumerate(self.baseline)
                if int(self.app.IsSame(original, document)) == 1
            ]
            if baseline:
                if len(baseline) != 1 or baseline[0] in baseline_found:
                    raise RuntimeError(
                        "pre-existing document native identity is duplicated"
                    )
                index = baseline[0]
                if document_state(document) != self.baseline[index][1]:
                    raise RuntimeError("pre-existing document state changed")
                baseline_found.add(index)
                continue
            path_value = str(document.GetPathName())
            if not path_value:
                raise RuntimeError("unknown unsaved native document prevents cleanup")
            path = Path(path_value).resolve()
            if path in paths:
                raise RuntimeError("duplicate new native document path")
            paths.add(path)
            if owned is not None and int(self.app.IsSame(document, owned)) == 1:
                found.append(document)
                continue
            if path == self.source_part and int(document.GetType()) == 1:
                if self.reference is None and owned is not None:
                    self.reference = document
                if (
                    self.reference is not None
                    and int(self.app.IsSame(document, self.reference)) == 1
                ):
                    continue  # implicitly loaded reference; never a close target
            raise RuntimeError("unknown native document prevents cleanup")
        if baseline_found != set(range(len(self.baseline))):
            raise RuntimeError("pre-existing document disappeared or was replaced")
        if owned is not None and len(found) != 1:
            raise RuntimeError("owned drawing is not unique in native inventory")
        if self.source_part not in paths:
            self.reference = None

    def expect_open(self, path):
        if self.handle is not None:
            raise RuntimeError("previous owned drawing must close first")
        self._inventory()
        for current in (self.app.ActiveDoc, self.adapter.currentModel):
            if current is not None and not any(
                int(self.app.IsSame(current, document)) == 1
                for document, _state in self.baseline
            ):
                raise RuntimeError("unexpected active document before opening copy")
        self.expected = self._path(path)
        self.paths, self.titles = {self.expected}, {}


def capture_target(adapter, part):
    app = adapter.swApp
    candidates, contexts, handles = {}, {}, {}
    for view_key, view in attachments.views(adapter.currentModel).items():
        source = _early_bound(view.ReferencedDocument, "IModelDoc2")
        if source is None or Path(source.GetPathName()).resolve() != part:
            raise RuntimeError("GTol control view has an unguarded source reference")
        contexts[view_key] = {
            "position": tuple(view.Position),
            "scale": float(view.ScaleDecimal),
            "outline": tuple(view.GetOutline()),
            "configuration": str(view.ReferencedConfiguration),
            "source": str(part),
        }
        handles[view_key] = (view, source)
        for raw in view.GetAnnotationsByType(5) or ():
            annotation = _early_bound(raw, "IAnnotation")
            gtol = _early_bound(annotation.GetSpecificAnnotation(), "IGtol")
            if (
                int(annotation.GetType()) != 5
                or int(annotation.Visible) != 1
                or int(annotation.OwnerType) != 0
                or int(app.IsSame(annotation.Owner, view)) != 1
                or int(app.IsSame(gtol.GetAnnotation(), annotation)) != 1
            ):
                raise RuntimeError("GTol exact annotation/owner roundtrip failed")
            key = f"{view_key}/{annotation.GetName()}"
            if key in candidates:
                raise RuntimeError("GTol native name is duplicated")
            candidates[key] = (annotation, f"{view.GetName2()}/{annotation.GetName()}")
    if len(candidates) != 1:
        raise RuntimeError("bounded rocker control requires exactly one visible GTol")
    key, (annotation, inventory_key) = next(iter(candidates.items()))
    record = leader_record(annotation)
    record.update(
        {
            "key": key,
            "inventory_key": inventory_key,
            "views": contexts,
            "measurement": asdict(annotation_box(adapter, annotation)),
        }
    )
    return record, annotation, handles


def leader_record(annotation):
    if (
        int(annotation.GetLeaderStyle()) != 2
        or annotation.GetLeaderCount() != 1
        or annotation.GetMultiJogLeaderCount() != 0
    ):
        raise RuntimeError("control requires one existing non-multijog swBENT leader")
    points = tuple(float(v) for v in annotation.GetLeaderPointsAtIndex(0) or ())
    position = tuple(float(v) for v in annotation.GetPosition() or ())
    if (
        len(points) != 9
        or len(position) != 3
        or not all(math.isfinite(v) for v in (*points, *position))
    ):
        raise RuntimeError("native bent leader geometry is not three finite XYZ points")
    if abs(points[1] - points[4]) > EPSILON or abs(points[2] - points[5]) > EPSILON:
        raise RuntimeError("native first leader segment is not horizontal")
    return {
        "position": position,
        "leader_points": points,
        "horizontal_length_m": abs(points[0] - points[3]),
        "length_readback_m": float(annotation.BentLeaderLength),
        "style": int(annotation.GetLeaderStyle()),
        "side": int(annotation.GetLeaderSide()),
        "perpendicular": bool(annotation.GetLeaderPerpendicular()),
        "all_around": bool(annotation.GetLeaderAllAround()),
        "dashed": bool(annotation.GetDashedLeader()),
    }


def verify_override(before, after, document_after, *, scope=LengthScope.ANNOTATION):
    if (
        not math.isfinite(document_after)
        or abs(document_after - DOCUMENT_LENGTH_M) > EPSILON
    ):
        raise RuntimeError("per-GTol override changed the document leader preference")
    for field in (
        "key",
        "inventory_key",
        "views",
        "style",
        "side",
        "perpendicular",
        "all_around",
        "dashed",
    ):
        if before[field] != after[field]:
            raise RuntimeError(f"per-GTol override changed {field}")
    if (
        not math.isfinite(after["horizontal_length_m"])
        or abs(after["horizontal_length_m"] - OVERRIDE_LENGTH_M) > EPSILON
    ):
        raise RuntimeError(
            "per-GTol override did not retain requested horizontal_length_m"
        )
    expected_getter = OVERRIDE_LENGTH_M
    if scope is LengthScope.GTOL_DEFAULT:
        # This is still a document-driven length, only at the GTol-family level.
        # IAnnotation.BentLeaderLength documents -1 for a document-driven default.
        expected_getter = -1.0
    if (
        not math.isfinite(after["length_readback_m"])
        or abs(after["length_readback_m"] - expected_getter) > EPSILON
    ):
        raise RuntimeError(
            "native length getter did not match its explicit property scope"
        )
    for initial, actual in (
        (before["position"], after["position"]),
        (before["leader_points"][:3], after["leader_points"][:3]),
        (before["leader_points"][-3:], after["leader_points"][-3:]),
        (
            tuple(before["measurement"]["body"].values()),
            tuple(after["measurement"]["body"].values()),
        ),
    ):
        if math.dist(initial, actual) > EPSILON:
            raise RuntimeError(
                "override moved annotation body/frame join/model endpoint"
            )


async def probe(
    adapter,
    source,
    part,
    directory,
    guard_paths=(),
    *,
    boundary=UpdateBoundary.IMMEDIATE,
    scope=LengthScope.ANNOTATION,
):
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    started = time.perf_counter()
    report_path = directory / "gtol-leader-override.json"
    report = {
        "source_hashes": {str(p): file_digest(p) for p in (source, part, *guard_paths)},
        "operation": scope.value,
        "requested_m": OVERRIDE_LENGTH_M,
        "update_boundary": boundary.value,
    }
    owned = None
    app = _early_bound(adapter.swApp, "ISldWorks")

    def export(stem):
        target = directory / f"{directory.name}-{stem}.SLDDRW"
        pdf, png = target.with_suffix(".pdf"), target.with_suffix(".png")
        owned.authorize_save(target)
        save_drawing(adapter, str(target), pdf_path=str(pdf))
        owned._validate_active()
        render_pdf_png(pdf, png)
        return {"drawing": str(target), "pdf": str(pdf), "png": str(png)}

    try:
        owned = ExistingSessionCopy(adapter, directory, part, source)
        report["pre_existing_documents"] = [state for _, state in owned.baseline]
        copy = directory / f"{directory.name}-source.SLDDRW"
        owned.expect_open(copy)
        shutil.copy2(source, copy)
        check("open unique rocker GTol copy", await adapter.open_model(str(copy)))
        owned.claim()
        report["opened_native_title"] = str(adapter.currentModel.GetTitle())
        report["before_export"] = export("before")
        report["document_before_m"], _, _ = shoulder.document_length(
            adapter.currentModel.Extension
        )
        if abs(report["document_before_m"] - DOCUMENT_LENGTH_M) > EPSILON:
            raise RuntimeError("source is not the freshly passed global-length rocker")
        report["before"], annotation, view_handles = capture_target(adapter, part)
        report["gtol_defaults_before"] = gtol_defaults(adapter.currentModel.Extension)
        if scope is LengthScope.GTOL_DEFAULT and (
            not report["gtol_defaults_before"]["use_global_document_length"]
            or report["before"]["length_readback_m"] != -1.0
        ):
            raise RuntimeError(
                "fresh source GTol does not inherit the global document default"
            )
        if abs(report["before"]["horizontal_length_m"] - DOCUMENT_LENGTH_M) > EPSILON:
            raise RuntimeError("source GTol does not use the witnessed document length")
        report["annotations_before"], all_handles = shoulder.all_annotation_layout(
            adapter
        )
        native_key = report["before"]["inventory_key"]
        if (
            native_key not in all_handles
            or int(app.IsSame(all_handles[native_key][0], annotation)) != 1
        ):
            raise RuntimeError("GTol target is not the exact full-inventory annotation")
        report["manufacturing_before"] = attachments.snapshot(
            adapter.currentModel, app=app
        )
        owned._validate_active()
        with _telemetry.span("diagnostic.gtol_length_override", scope=scope.value):
            report["length_scope"] = apply_length_scope(
                annotation, adapter.currentModel.Extension, scope
            )
        report["immediate"] = leader_record(annotation)
        owned._validate_active()
        with _telemetry.span(
            "diagnostic.gtol_update_boundary", boundary=boundary.value
        ):
            report["update"] = update_boundary(adapter.currentModel, boundary)
        report["after"], after_annotation, after_view_handles = capture_target(
            adapter, part
        )
        if int(app.IsSame(annotation, after_annotation)) != 1:
            raise RuntimeError("target annotation identity changed")
        for key, initial in view_handles.items():
            shoulder.same_handles(app, initial, after_view_handles[key])
        report["annotations_after"], after_handles = shoulder.all_annotation_layout(
            adapter
        )
        report["layout_changes"] = shoulder.compare_all_annotation_layout(
            app,
            report["annotations_before"],
            report["annotations_after"],
            all_handles,
            after_handles,
        )
        report["manufacturing_after"] = attachments.snapshot(
            adapter.currentModel, app=app
        )
        attachments.compare(
            report["manufacturing_before"],
            report["manufacturing_after"],
            "GTol length setter",
        )
        report["document_after_m"], _, _ = shoulder.document_length(
            adapter.currentModel.Extension
        )
        report["gtol_defaults_after"] = gtol_defaults(adapter.currentModel.Extension)
        report["after_export"] = export("after")
        await owned.close()
        owned.expect_open(Path(report["after_export"]["drawing"]))
        check(
            "reopen owned GTol copy",
            await adapter.open_model(report["after_export"]["drawing"]),
        )
        owned.claim()
        report["reopened"], _, _ = capture_target(adapter, part)
        report["annotations_reopened"], _ = shoulder.all_annotation_layout(adapter)
        report["reopen_layout_changes"] = shoulder.compare_all_annotation_layout(
            app, report["annotations_after"], report["annotations_reopened"]
        )
        report["manufacturing_reopened"] = attachments.snapshot(
            adapter.currentModel, app=app
        )
        attachments.compare(
            report["manufacturing_before"],
            report["manufacturing_reopened"],
            "GTol saved reopen",
        )
        report["document_reopened_m"], _, _ = shoulder.document_length(
            adapter.currentModel.Extension
        )
        report["gtol_defaults_reopened"] = gtol_defaults(adapter.currentModel.Extension)
        report["reopened_export"] = export("reopened")
        verify_override(
            report["before"], report["after"], report["document_after_m"], scope=scope
        )
        verify_override(
            report["before"],
            report["reopened"],
            report["document_reopened_m"],
            scope=scope,
        )
        for phase in ("after", "reopened"):
            if scope is LengthScope.GTOL_DEFAULT:
                verify_gtol_defaults(report[f"gtol_defaults_{phase}"])
            elif report[f"gtol_defaults_{phase}"] != report["gtol_defaults_before"]:
                raise RuntimeError(
                    "individual GTol override changed its family defaults"
                )
        verify_layout_changes(report["layout_changes"], report["before"])
        if report["reopen_layout_changes"]:
            raise RuntimeError("saved GTol copy changed native layout on reopen")
        report["result"] = "passed"
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        report["elapsed_s"] = time.perf_counter() - started
        await shoulder.finalize_probe(owned, report, report_path)
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--part", required=True, type=Path)
    parser.add_argument("--guard-source", action="append", type=Path, default=[])
    parser.add_argument(
        "--update-boundary",
        type=UpdateBoundary,
        choices=tuple(UpdateBoundary),
        default=UpdateBoundary.IMMEDIATE,
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument(
        "--length-scope",
        type=LengthScope,
        choices=tuple(LengthScope),
        default=LengthScope.ANNOTATION,
    )
    args = parser.parse_args()
    source, part = args.drawing.resolve(strict=True), args.part.resolve(strict=True)
    guards = tuple(path.resolve(strict=True) for path in args.guard_source)
    if (
        source.name.casefold() != "rocker-arm.slddrw"
        or part.name.casefold() != "rocker-arm.sldprt"
    ):
        raise ValueError("this control is bounded to the coherent rocker drawing/part")
    require_owned_diagnostic_environment()
    if (
        args.length_scope is LengthScope.GTOL_DEFAULT
        and args.update_boundary is not UpdateBoundary.EDIT_REBUILD
    ):
        raise ValueError(
            "GTol-family default control requires one explicit edit_rebuild boundary"
        )
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                str(source),
                "--part",
                str(part),
                "--worker",
                "--update-boundary",
                args.update_boundary.value,
                "--length-scope",
                args.length_scope.value,
                *(value for path in guards for value in ("--guard-source", str(path))),
            ],
            "one GTol leader override",
            com=True,
            log_stem="gtol-leader-override",
        )
        return 0
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="gtol-leader-override-", dir=reports))
    return run_owned_diagnostic(
        lambda adapter: probe(
            adapter,
            source,
            part,
            directory,
            guards,
            boundary=args.update_boundary,
            scope=args.length_scope,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
