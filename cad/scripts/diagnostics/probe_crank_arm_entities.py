"""Crank-arm-only native evidence, using the shared attach-only owned runner."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
from crank_arm_spec import DRAWING_DIMENSIONS  # noqa: E402
from diagnostics._owned_native_documents import run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from diagnostics._source_dimension_snapshot import dimension_snapshot  # noqa: E402
from diagnostics.probe_source_basic_dimensions import part_dimensions  # noqa: E402
import _telemetry  # noqa: E402

SOURCE = ROOT / "cad/out/sldprt/crank-arm.SLDPRT"
TOKEN = SOURCE.with_name(".crank-arm.execution")
EXPECTED_SOURCE_SHA = "6b086d5dbcb6e904fb794822728b705f69cd3903a0e8b2c5cf7abb8d9621f102"
BASELINE = "bc593d784fba08fc6552224767a460338f51b664"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_default(value):
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported evidence type: {type(value)}")


def persist_report(path, report):
    primary = sys.exception()
    try:
        path.write_text(
            json.dumps(report, indent=2, default=json_default), encoding="utf-8"
        )
    except Exception as error:
        if primary is not None and primary is not error:
            raise ExceptionGroup(
                "native operation and report failures", [primary, error]
            ) from None
        raise


def revision(directory):
    return subprocess.check_output(
        ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True
    ).strip()


def provenance():
    import solidworks_mcp.adapters.pywin32_adapter as native
    import draw_crank_arm as recipe

    source_hash = sha(SOURCE)
    token = TOKEN.read_text(encoding="utf-8").strip()
    if source_hash != token or source_hash != EXPECTED_SOURCE_SHA:
        raise RuntimeError("source SHA differs from its original execution token")
    return {
        "root_commit": revision(ROOT),
        "adapter_commit": revision(ROOT / "SolidworksMCP-python"),
        "python": sys.executable,
        "recipe_import": recipe.__file__,
        "adapter_import": native.__file__,
        "host": platform.node(),
        "platform": platform.platform(),
        "source": str(SOURCE),
        "source_sha256": source_hash,
        "execution_token": token,
        "source_size": SOURCE.stat().st_size,
    }


@_telemetry.traced("diagnostic.crank_arm.source_snapshot")
def source_snapshot(adapter, path):
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if (
        int(model.GetType()) != 1
        or Path(model.GetPathName()).resolve() != path.resolve()
        or int(
            adapter.swApp.IsSame(adapter.swApp.GetOpenDocumentByName(str(path)), model)
        )
        != 1
    ):
        raise RuntimeError("crank-arm snapshot has the wrong exact source owner")
    before = bool(model.GetSaveFlag())
    raw, _ = dimension_snapshot(adapter.swApp, model, path, required=DRAWING_DIMENSIONS)
    required, _ = part_dimensions(
        adapter, path, raw["configuration"], targets=DRAWING_DIMENSIONS
    )
    return {
        "dirty_before": before,
        "dirty_after": bool(model.GetSaveFlag()),
        "required_dimensions": required,
        "observed_dimensions": raw,
    }


async def capture_source(adapter, directory):
    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(SOURCE)
    report = {"status": "running", "provenance": provenance()}
    report_path = directory / "measurements.json"
    try:
        report["session"] = {
            "pid": int(adapter.swApp.GetProcessID()),
            "revision": str(adapter.swApp.RevisionNumber()),
            "inventory": adapter.ownership.evidence(),
        }
        check("open crank-arm for readback", await adapter.open_model(str(SOURCE)))
        report["source_snapshot"] = source_snapshot(adapter, SOURCE)
        report["status"] = "captured"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        report["source_sha256_after"] = sha(SOURCE)
        report["execution_token_after"] = TOKEN.read_text(encoding="utf-8").strip()
        persist_report(report_path, report)
        _telemetry.info(f"crank-arm evidence: {report_path}")
        if (
            report["source_sha256_after"] != report["provenance"]["source_sha256"]
            or report["execution_token_after"]
            != report["provenance"]["execution_token"]
        ):
            raise RuntimeError("crank-arm source or original token changed")
    return {"report": str(report_path)}


async def capture_drawing(adapter, directory):
    from diagnostics import probe_drawing_attachments as attachments
    from diagnostics.probe_datum_shoulder import all_annotation_layout
    import draw_crank_arm as recipe

    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(SOURCE)
    adapter.ownership.register_source(recipe.OUTPUTS.slddrw)
    copy = directory / f"{directory.name}.SLDDRW"
    shutil.copy2(recipe.OUTPUTS.slddrw, copy)
    report = {"status": "running", "provenance": provenance()}
    try:
        async with attachments.open_drawing(adapter, copy) as model:
            report["attachments"] = attachments.snapshot(model, app=adapter.swApp)
            report["annotations"], _ = all_annotation_layout(adapter)
            report["layout"] = attachments.layout(model)
            source_model = _early_bound(
                adapter.swApp.GetOpenDocumentByName(str(SOURCE)), "IModelDoc2"
            )
            report["source_snapshot"] = source_snapshot(
                SimpleNamespace(currentModel=source_model, swApp=adapter.swApp), SOURCE
            )
        report["status"] = "captured"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        persist_report(directory / "measurements.json", report)
    return {"report": str(directory / "measurements.json")}


def positive_roles():
    from _drawing_entities import CircleEdge, FaceBoundary, FeatureFace, LineEdge
    from _gtol_spec import CylinderFace, PlanarFace
    from crank_arm_spec import (
        ARM_C2C,
        ARM_END_X,
        ARM_THICKNESS,
        HALF_WIDTH,
        PIN_HOLE_DIA,
        SHAFT_BORE_DIA,
    )

    end = FeatureFace("Arm", PlanarFace((1, 0, 0), ARM_END_X))
    return {
        "shaft": FaceBoundary(
            FeatureFace("ShaftBore", CylinderFace(SHAFT_BORE_DIA)),
            CircleEdge(SHAFT_BORE_DIA / 2, (0, 0, ARM_THICKNESS), (0, 0, 1)),
        ),
        "pivot": FaceBoundary(
            FeatureFace("PivotBore", CylinderFace(15 / 64 * 25.4)),
            CircleEdge(15 / 64 * 25.4 / 2, (ARM_C2C, 0, ARM_THICKNESS), (0, 0, 1)),
        ),
        "pin": FaceBoundary(
            FeatureFace("Arm", PlanarFace((0, 1, 0), HALF_WIDTH)),
            CircleEdge(PIN_HOLE_DIA / 2, (0, HALF_WIDTH, ARM_THICKNESS / 2), (0, 1, 0)),
        ),
        "width_lo": FaceBoundary(
            end, LineEdge((ARM_END_X, -HALF_WIDTH, ARM_THICKNESS / 2), (0, 0, 1))
        ),
        "width_hi": FaceBoundary(
            end, LineEdge((ARM_END_X, HALF_WIDTH, ARM_THICKNESS / 2), (0, 0, 1))
        ),
    }


def require_attachment(adapter, annotation, view, entities, label):
    """Read exact source identities for all attached edges, including dimensions."""
    from _drawing_common import _drawing_entity_in_source

    annotation = _early_bound(annotation, "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    kinds = tuple(annotation.GetAttachedEntityTypes() or ())
    if (
        int(annotation.GetAttachedEntityCount3()) != len(entities)
        or len(attached) != len(entities)
        or kinds != (1,) * len(entities)
        or int(annotation.OwnerType) != 0
        or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
        or annotation.IsDangling()
    ):
        raise RuntimeError(f"{label}: attachment count/type/view/dangling mismatch")
    for actual, expected in zip(attached, entities, strict=True):
        source = _drawing_entity_in_source(
            view, actual, entity_type="EDGE", label=label
        )
        if int(adapter.swApp.IsSame(source, expected)) != 1:
            raise RuntimeError(f"{label}: attached source entity changed")
    return {
        "name": str(annotation.GetName()),
        "view": str(view.GetName2()),
        "attachment_types": kinds,
    }


async def positive_control(adapter, directory):
    from diagnostics import benchmark_drawing_recipes as benchmark
    from diagnostics import probe_drawing_attachments as attachments
    from diagnostics._owned_native_documents import DocumentKind, save_drawing
    from diagnostics._recipe_template_factory import (
        DrawingFactory,
        RecipeTemplateFactory,
    )
    from diagnostics.probe_datum_shoulder import all_annotation_layout
    from _drawing_entities import ModelEntities
    import _drawing_common as drawing

    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(SOURCE)
    report = {"status": "running", "provenance": provenance(), "observations": []}
    report_path = directory / "measurements.json"

    def checkpoint():
        persist_report(report_path, report)

    source = directory / f"{directory.name}-part.SLDPRT"
    shutil.copy2(SOURCE, source)
    module = benchmark.load_recipe(BASELINE, "crank_arm", directory, source=source)
    controller = RecipeTemplateFactory(DrawingFactory.PREPARED)
    checkpoint()
    try:
        factory = await controller.configure(adapter, module, report, directory)
        check(
            "open positive-control source copy", await adapter.open_model(str(source))
        )
        adapter.ownership.assert_current_owned()
        source_model = adapter.currentModel
        report["source_before"] = source_snapshot(adapter, source)
        roles = positive_roles()
        report["requests"] = {name: repr(value) for name, value in roles.items()}
        started = time.perf_counter()
        bank = ModelEntities(source_model).resolve(roles)
        report["resolver_seconds"] = time.perf_counter() - started
        report["resolved"] = {
            name: attachments.geometry(entity, 1) for name, entity in bank.items()
        }
        checkpoint()
        originals = {
            name: getattr(module, name)
            for name in (
                "add_edge_dimension",
                "add_datum_feature",
                "add_native_hole_callout",
            )
        }

        def insert(name, actual_adapter, view, **kwargs):
            label = kwargs["label"]
            selected = {
                "arm-width overall": ("width_lo", "width_hi"),
                "crank shaft axis": ("shaft",),
                "crank-arm cross-hole": ("pin",),
                "handle pivot hole": ("pivot",),
            }.get(label)
            if selected is None:
                return originals[name](actual_adapter, view, **kwargs)
            adapter.ownership.assert_current_owned()
            if (
                actual_adapter is not adapter
                or int(adapter.swApp.IsSame(view.ReferencedDocument, source_model)) != 1
            ):
                raise RuntimeError("positive control has the wrong adapter/source view")
            entities = tuple(bank[role] for role in selected)
            row = {"label": label, "roles": selected, "status": "inserting"}
            report["observations"].append(row)
            checkpoint()
            if name == "add_edge_dimension":
                for key in ("p0", "p1"):
                    kwargs.pop(key)
                result = drawing.add_entity_dimension(
                    adapter, view, entities=entities, **kwargs
                )
            else:
                kwargs.pop("edge_xy")
                kwargs["edge" if name == "add_native_hole_callout" else "entity"] = (
                    entities[0]
                )
                result = originals[name](adapter, view, **kwargs)
            row["attachment"] = require_attachment(
                adapter, result.GetAnnotation(), view, entities, label
            )
            row["status"] = "passed"
            checkpoint()
            return result

        started = time.perf_counter()
        with ExitStack() as stack:
            stack.enter_context(
                adapter.ownership.creating_document(
                    DocumentKind.DRAWING, module.OUTPUTS.slddrw
                )
            )
            stack.enter_context(patch("_drawing_common.save_drawing", save_drawing))
            for name in originals:
                stack.enter_context(
                    patch.object(
                        module,
                        name,
                        lambda a, v, _name=name, **kw: insert(_name, a, v, **kw),
                    )
                )
            report["artifacts"] = await module.build(adapter, drawing_factory=factory)
        report["recipe_seconds"] = time.perf_counter() - started
        controller.require_used()
        if len(report["observations"]) != 4:
            raise RuntimeError(
                "positive control did not exercise all four required call sites"
            )
        report["attachments"] = attachments.snapshot(
            adapter.currentModel, app=adapter.swApp
        )
        report["annotations"], _ = all_annotation_layout(adapter)
        report["source_after"] = source_snapshot(
            SimpleNamespace(currentModel=source_model, swApp=adapter.swApp), source
        )
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        report["template_guard_errors"] = [
            repr(error) for error in controller.final_guards()
        ]
        report["source_copy_sha256_after"] = sha(source)
        checkpoint()
        if report["source_copy_sha256_after"] != EXPECTED_SOURCE_SHA:
            raise RuntimeError("positive control changed its source copy on disk")
        if report["template_guard_errors"]:
            raise RuntimeError("positive control template/helper guards failed")
    return {"report": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("source", "drawing", "positive"))
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if not args.worker:
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), args.mode, "--worker"],
            "crank-arm entity diagnostic",
            com=True,
            log_stem="crank-arm-entities-probe",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("crank-arm worker requires the locked parent")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="crank-arm-entities-", dir=reports))
    callback = {
        "source": capture_source,
        "drawing": capture_drawing,
        "positive": positive_control,
    }[args.mode]
    return run_copy_diagnostic(lambda adapter: callback(adapter, directory))


if __name__ == "__main__":
    raise SystemExit(main())
