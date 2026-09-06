"""Discard exactly the two documents left by template-abba-bn33bcg_.

One-off, reviewed recovery, NOT a generic ownership-policy exception. The prior
receipt proves Draw16 and the opened arbor source were not user baseline. Read
their current values/attachments before closing them without saving; preserve
the exact original lever and unsaved Draw2. No open, activate, rebuild, save,
configuration switch, selection, preference write or automatic recovery occurs.
Requires a new explicit seat grant and the existing native PID 37136.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound  # noqa: E402
from arbor_pedestal_spec import DRAWING_DIMENSIONS  # noqa: E402
from diagnostics import probe_drawing_attachments as attachments  # noqa: E402
from diagnostics._owned_native_session import (  # noqa: E402
    require_owned_diagnostic_environment,
    run_owned_diagnostic,
)

EXPECTED_PID = 37136
SOURCE = Path("C:/src/harmonic-analyzer/cad/out/sldprt/arbor-pedestal.SLDPRT")
SOURCE_SHA = "dbb991437aea105ca5352b8b76468874077aeed0a74906413a1cc56fb7ca769e"
RECEIPT = (
    ROOT / "cad/out/reports/template-defaults/template-abba-bn33bcg_/ownership.json"
)
DRAWING_TITLE = "Draw16 - Sheet1"
BASELINE = [
    {
        "path": str(Path("C:/src/ha-perf-channel/cad/out/sldprt/channel-lever.SLDPRT")),
        "title": "channel-lever.SLDPRT",
        "kind": 1,
        "dirty": "clean",
        "visible": "visible",
    },
    {
        "path": "",
        "title": "Draw2 - Sheet1",
        "kind": 3,
        "dirty": "dirty",
        "visible": "visible",
    },
]
DISCARDED = [
    {
        "path": str(SOURCE),
        "title": "arbor-pedestal.SLDPRT",
        "kind": 1,
        "dirty": "dirty",
        "visible": "visible",
    },
    {
        "path": "",
        "title": DRAWING_TITLE,
        "kind": 3,
        "dirty": "dirty",
        "visible": "visible",
    },
]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def keyed(rows):
    result = {row["title"]: row for row in rows}
    if len(result) != len(rows):
        raise RuntimeError("duplicate document titles prevent exact recovery")
    return result


def validate_receipt(receipt):
    if keyed(receipt["baseline_initial"]) != keyed(BASELINE):
        raise RuntimeError(
            "receipt does not contain the reviewed two-document baseline"
        )
    if keyed(receipt["final_inventory"]) != keyed(BASELINE + DISCARDED):
        raise RuntimeError("receipt does not contain the reviewed four-document scene")
    source_hash = receipt["source_hashes"][str(SOURCE)]
    if source_hash != {"before": SOURCE_SHA, "after": SOURCE_SHA, "unchanged": True}:
        raise RuntimeError("receipt source identity is not the reviewed exact SHA")
    if {
        "operation": "open",
        "path": str(SOURCE),
        "ownership": "opened_read_only_source",
    } not in receipt["events"]:
        raise RuntimeError("receipt does not prove the diagnostic opened the arbor")


def state(model):
    return {
        "path": str(model.GetPathName()),
        "title": str(model.GetTitle()),
        "kind": int(model.GetType()),
        "dirty": "dirty" if model.GetSaveFlag() else "clean",
        "visible": "visible" if model.Visible else "hidden",
    }


def inventory(app):
    rows, handles = [], {}
    for raw in app.GetDocuments() or ():
        model = _early_bound(raw, "IModelDoc2")
        row = state(model)
        rows.append(row)
        handles[row["title"]] = model
    return keyed(rows), handles


def verify_scene(app, expected, handles=None):
    actual, current = inventory(app)
    if actual != keyed(expected):
        raise RuntimeError(f"exact visible scene changed: {actual!r}")
    if handles is not None:
        # Only wrappers proven present by the fresh inventory go back into COM.
        for title in actual:
            if int(app.IsSame(current[title], handles[title])) != 1:
                raise RuntimeError(f"native document was replaced: {title}")
    return current


def verify_references(app, handles):
    """The discarded drawing must reference only the exact diagnostic arbor."""
    source = handles[DISCARDED[0]["title"]]
    rows = {}
    for title in (DRAWING_TITLE, BASELINE[1]["title"]):
        found = attachments.views(handles[title])
        if title == DRAWING_TITLE and not found:
            raise RuntimeError("Draw16 has no native model views")
        rows[title] = {}
        for key, view in found.items():
            raw = view.ReferencedDocument
            if raw is None:
                raise RuntimeError(
                    f"{title}/{key}: unresolved source; recovery refused"
                )
            model = _early_bound(raw, "IModelDoc2")
            path = str(model.GetPathName())
            same = int(app.IsSame(model, source)) == 1
            rows[title][key] = {
                "path": path,
                "configuration": str(view.ReferencedConfiguration),
            }
            if title == DRAWING_TITLE and (not same or path != str(SOURCE)):
                raise RuntimeError(
                    "Draw16 references a document other than the exact arbor"
                )
            if title != DRAWING_TITLE and same:
                raise RuntimeError(
                    "protected Draw2 references the arbor; recovery refused"
                )
    return rows


def observed(getter):
    """Capture failures explicitly; they never waive document/close guards."""
    try:
        return {"status": "returned", "value": getter()}
    except Exception as error:
        return {"status": "error", "error": repr(error)}


def require_source_hash(report, key):
    report[key] = observed(lambda: digest(SOURCE))
    if report[key] != {"status": "returned", "value": SOURCE_SHA}:
        raise RuntimeError(
            f"source disk identity not proved before discard: {report[key]}"
        )


def dimension_row(raw, configuration, value_kind="source"):
    dimension = _early_bound(raw, "IDimension")
    if dimension is None:
        raise RuntimeError("native dimension is missing")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    return {
        "full_name": str(dimension.FullName),
        "value_kind": value_kind,
        "value_system": observed(
            lambda: (
                dimension.GetSystemValue2("")
                if value_kind == "drawing_reference"
                else dimension.GetSystemValue3(3, configuration)
            )
        ),
        "tolerance_type": int(tolerance.Type),
        "legacy_tolerance_type": int(dimension.GetToleranceType()),
        "basic": "basic" if int(tolerance.Type) == 1 else "other",
        "minimum": observed(lambda: tolerance.GetMinValue2()),
        "maximum": observed(lambda: tolerance.GetMaxValue2()),
    }


def source_capture(model):
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    active = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    configuration = str(active.Name)
    result = {
        "active_configuration": configuration,
        "configurations": list(model.GetConfigurationNames() or ()),
        "dimensions_scope": "the five named arbor drawing/source parameters",
        "dimensions": {},
        "properties": {},
    }
    for feature, names in sorted(DRAWING_DIMENSIONS.items()):
        for name in sorted(names):
            key = f"{name}@{feature}"
            result["dimensions"][key] = observed(
                lambda key=key: dimension_row(model.Parameter(key), configuration)
            )
    extension = _early_bound(model.Extension, "IModelDocExtension")
    for scope in ("", configuration):
        props = _early_bound(
            extension.CustomPropertyManager(scope), "ICustomPropertyManager"
        )
        result["properties"][scope] = {
            str(name): observed(lambda name=name: props.Get6(str(name), True))
            for name in props.GetNames() or ()
        }
    result["property_value_policy"] = "Get6 UseCached=True; no configuration activation"
    if (
        str(_early_bound(manager.ActiveConfiguration, "IConfiguration").Name)
        != configuration
    ):
        raise RuntimeError("read-only source capture changed the active configuration")
    return result


def annotation_row(raw, configuration):
    annotation = _early_bound(raw, "IAnnotation")
    kinds = tuple(annotation.GetAttachedEntityTypes() or ())
    entities = tuple(annotation.GetAttachedEntities3() or ())
    row = {
        "name": str(annotation.GetName()),
        "kind": int(annotation.GetType()),
        "dangling": bool(annotation.IsDangling()),
        "attachment_types": kinds,
        "attachment_count": int(annotation.GetAttachedEntityCount3()),
        "geometry": [],
        "dimension": None,
    }
    if len(kinds) != len(entities) or len(kinds) != row["attachment_count"]:
        raise RuntimeError(f"attachment array/count mismatch: {row}")
    for kind, entity in zip(kinds, entities, strict=True):
        if kind not in (1, 2, 3) or entity is None:
            row["geometry"].append(
                {
                    "status": "excluded",
                    "kind": kind,
                    "reason": "unsupported or null native entity",
                }
            )
            continue
        row["geometry"].append(observed(lambda: attachments.geometry(entity, kind)))
    if row["kind"] == 4:
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        value_kind = "drawing_reference" if display.IsReferenceDim() else "source"
        # No fabricated saved drawing name: preserve FullName exactly for Draw16.
        row["dimension"] = [
            observed(
                lambda index=index: dimension_row(
                    display.GetDimension2(index), configuration, value_kind
                )
            )
            for index in range(2 if int(display.Type2) == 10 else 1)
        ]
    return row


def drawing_capture(model):
    return {
        key: [
            observed(
                lambda raw=raw: annotation_row(raw, str(view.ReferencedConfiguration))
            )
            for raw in view.GetAnnotations() or ()
        ]
        for key, view in attachments.views(model).items()
    }


def discard_reviewed_documents(app, handles, report, checkpoint):
    verify_scene(app, BASELINE + DISCARDED, handles)
    app.CloseDoc(DRAWING_TITLE)  # Documented named dirty close: WITHOUT saving.
    actual, _ = inventory(app)
    report["after_drawing_close"] = list(actual.values())
    checkpoint()
    if actual == keyed(BASELINE):
        verify_scene(app, BASELINE, handles)
        report["source_close"] = "already unloaded by native drawing close"
        return
    # Do not inspect or pass the old source wrapper until fresh native inventory
    # has proved that exact full-path source remains present.
    current = verify_scene(app, BASELINE + [DISCARDED[0]], handles)
    app.CloseDoc(str(current[DISCARDED[0]["title"]].GetTitle()))
    verify_scene(app, BASELINE, handles)
    report["source_close"] = "named CloseDoc without save"


async def recover(adapter, receipt_path, report_root):
    if int(adapter.swApp.GetProcessID()) != EXPECTED_PID:
        raise RuntimeError("recovery requires the exact reviewed native process")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    validate_receipt(receipt)
    report_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="scene-recovery-", dir=report_root))
    path = directory / "recovery.json"
    report = {
        "pid": EXPECTED_PID,
        "receipt": str(receipt_path),
        "receipt_sha256": digest(receipt_path),
        "status": "capturing",
    }

    def checkpoint():
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    checkpoint()
    try:
        app = adapter.swApp
        handles = verify_scene(app, BASELINE + DISCARDED)
        report["before"] = BASELINE + DISCARDED
        report["references"] = verify_references(app, handles)
        require_source_hash(report, "source_sha_before")
        report["source_capture"] = observed(
            lambda: source_capture(handles[DISCARDED[0]["title"]])
        )
        checkpoint()
        report["drawing_capture"] = observed(
            lambda: drawing_capture(handles[DRAWING_TITLE])
        )
        checkpoint()
        verify_references(app, handles)
        require_source_hash(report, "source_sha_before_discard")
        discard_reviewed_documents(app, handles, report, checkpoint)
        report["final_inventory"] = list(inventory(app)[0].values())
        report["source_sha_after"] = digest(SOURCE)
        if report["source_sha_after"] != SOURCE_SHA:
            raise RuntimeError("source disk SHA differs after no-save recovery")
        report["status"] = "recovered_without_save_baseline_preserved"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        checkpoint()
    return {"recovery_report": str(path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument(
        "--report-root", type=Path, default=ROOT / "cad/out/reports/template-defaults"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID") != str(EXPECTED_PID):
        raise RuntimeError("explicit HARMONIC_DIAGNOSTIC_SW_PID=37136 required")
    validate_receipt(json.loads(args.receipt.read_text(encoding="utf-8")))
    if args.worker:
        return run_owned_diagnostic(
            lambda adapter: recover(adapter, args.receipt, args.report_root)
        )
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--receipt",
            str(args.receipt.resolve()),
            "--report-root",
            str(args.report_root.resolve()),
            "--worker",
        ],
        "reviewed template diagnostic scene recovery",
        log_stem="template-scene-recovery",
        com=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
