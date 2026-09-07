"""Fresh selected recipe builds with the combined native datum policy.

Default order is rocker then lever. Repeat --target to select an explicit order,
for example --target channel_lever for the independent lever-only control.
Both original rocker/lever pairs and each explicitly selected target remain
hash-protected. --source-root and --guard-root may name the same directory:
ownership and the initial/final SHA witness protect that one original directly.
Optional --factory normal|prepared selects only the isolated recipe's initial
project drawing factory. Use separate invocations for a functional pair: a
failed normal cold-title witness never authorizes continuing to prepared.
The opt-in --drawing-save control requires alignment_pinion and its source
boundary observations. It changes only the native save call, not hash acceptance.
--callout-storage lower_text changes only that recipe's below-text field and
requires an explicit save arm plus the same source and cold drawing witnesses.

Run only under an explicitly granted COM seat, attaching to the expected existing
SolidWorks process with automatic launch/recovery disabled. Production recipes
and final gates run unchanged; the reviewed benchmark loader redirects SOURCE
and OUTPUTS before defaults/aliases are evaluated. This is a functional pilot,
not an ABBA speed benchmark or a full doit merge gate.

Original source files are disk-read only, never opened. Each recipe uses a
unique-basename exact bytecopy in its registered diagnostic directory. Native
imported callout formatting can mutate the copied source display in memory (the
arbor source-dirty-9cbdz77u control proved this); existing COPY ownership permits
discarding that copy but does not relax protected original/baseline documents.
Copy disk hashes must remain exact: no source save is authorized by default.
Only --source-callout-authoring alignment_fit deliberately authors the copied
PART, saves/reopens it and pins H1 before drawing work; original H0 protection
never changes. Its drawing callout request verifies import without a setter.
Shared ownership preserves the user's visible lever and unsaved Draw2 throughout.
Every successful recipe gets a fresh saved/reopened geometry, dimension/BASIC,
annotation-content/layout and source-parameter witness. Stop at the first failure.
The named parameter witnesses do not prove full in-memory source immutability.
Failed trials retain fresh native observations and PDF/PNG evidence when the
exact active drawing is owned. Evidence errors never replace the original
failure; no native drawing/source save or additional successful-trial reads.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from enum import StrEnum
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
from diagnostics import benchmark_drawing_recipes as benchmark  # noqa: E402
from diagnostics import probe_datum_shoulder as shoulder  # noqa: E402
from diagnostics import probe_drawing_attachments as attachments  # noqa: E402
from diagnostics.probe_source_basic_dimensions import part_dimensions  # noqa: E402
from diagnostics._owned_native_documents import DocumentKind, run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_documents import save_drawing as owned_save_drawing  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from diagnostics._reopen_annotation_comparison import compare_reopened_annotations  # noqa: E402
from diagnostics._recipe_acceptance_targets import TARGETS  # noqa: E402
from diagnostics._recipe_entity_acceptance import EntityAcceptance  # noqa: E402
from diagnostics._recipe_view_entity_acceptance import ViewEntityAcceptance  # noqa: E402
from diagnostics._bsurface_attachment_witness import grid_control_from_environment  # noqa: E402
from diagnostics._tooth_selector_observation import (  # noqa: E402
    observation_from_environment, observe_selector,
    require_targets as require_tooth_targets,
)
import _telemetry  # noqa: E402

ORDER = ("rocker_arm", "channel_lever")
EXPECTED_PART_HASHES = {target: row.source_sha256 for target, row in TARGETS.items()}


def target_order(targets=None):
    """Choose only recipes with the pilot's exact source and semantic manifests."""
    if targets is None:
        return ORDER
    if isinstance(targets, str):
        raise ValueError("targets must be a sequence of recipe names")
    order = tuple(targets)
    if not order or any(target not in EXPECTED_PART_HASHES for target in order):
        raise ValueError("select a nonempty order from the registered pilot recipes")
    if len(set(order)) != len(order):
        raise ValueError("each selected recipe may run only once per invocation")
    return order


def selected_callout_contract(
    candidate, source_observation, callout_storage, source_authoring
):
    """Reject unsupported recipe/experiment ABIs before attach or owned writes."""
    if source_observation is None:
        return None
    from diagnostics._callout_recipe_contract import recipe_contract, require_experiment

    contract = recipe_contract(benchmark.recipe_source(candidate, "alignment_pinion"))
    require_experiment(
        contract, lower_text=callout_storage, source_authoring=source_authoring
    )
    return contract


def adapter_fingerprints():
    """Fingerprint the imported editable package, not an empty worktree submodule."""
    import solidworks_mcp

    package = Path(solidworks_mcp.__file__).resolve(strict=True).parent
    required = (package / "__init__.py", package / "adapters/pywin32_adapter.py")
    if not all(path.is_file() for path in required):
        raise RuntimeError("actual imported adapter package is incomplete")
    return {
        "package_path": str(package),
        "files": {
            str(path.relative_to(package)): attachments.file_digest(path)
            for path in sorted(package.rglob("*.py"))
        },
    }


def helper_fingerprints():
    result = benchmark.helper_fingerprints()
    result.update(
        {
            str(path.relative_to(ROOT)): attachments.file_digest(path)
            for path in sorted((ROOT / "cad/scripts/diagnostics").glob("*.py"))
        }
    )
    return result


def require_sources(sources, guards):
    if sources.keys() != guards.keys():
        raise ValueError("source and guard manifests must have the same targets")
    hashes = {}
    for target in sources:
        for path in (sources[target], guards[target]):
            actual = attachments.file_digest(path)
            hashes[str(path)] = actual
            if actual != EXPECTED_PART_HASHES[target]:
                raise RuntimeError(
                    f"{target}: exact immutable source hash mismatch: {path}: {actual}"
                )
    return hashes


@_telemetry.traced("diagnostic.datum_policy.source_dimensions")
def source_dimensions(model, target, path):
    model = _early_bound(model, "IModelDoc2")
    if (
        model is None
        or int(model.GetType()) != 1
        or Path(model.GetPathName()).resolve() != path
    ):
        raise RuntimeError("source parameter witness has the wrong exact native owner")
    configuration = str(
        _early_bound(
            _early_bound(
                model.ConfigurationManager, "IConfigurationManager"
            ).ActiveConfiguration,
            "IConfiguration",
        ).Name
    )
    if not configuration:
        raise RuntimeError("source parameter witness has no active configuration")
    manifest = TARGETS[target]
    targets = manifest.dimensions
    rows, handles = part_dimensions(
        SimpleNamespace(currentModel=model), path, configuration, targets=targets
    )
    for feature, names in manifest.basic.items():
        for name in names:
            if rows[f"{name}@{feature}"]["tolerance_type"] != 1:
                raise RuntimeError(
                    f"{name}@{feature}: saved source BASIC designation missing"
                )
    return {"configuration": configuration, "dimensions": rows}, handles


def require_same_source(
    before, after, stage, *, app=None, handles_before=None, handles_after=None
):
    if before != after:
        raise RuntimeError(f"{stage}: source parameters/tolerances changed")
    if app is not None:
        if handles_before.keys() != handles_after.keys() or any(
            int(app.IsSame(handle, handles_after[name])) != 1
            for name, handle in handles_before.items()
        ):
            raise RuntimeError(f"{stage}: exact source dimension identity changed")


def require_copy_hash(trial, phase):
    """Record the owned part's disk identity; formatting may dirty memory only."""
    actual = attachments.file_digest(Path(trial["copy_source"]))
    trial.setdefault("copy_hashes", {})[phase] = actual
    from diagnostics._source_callout_authoring import expected_copy_hash

    if actual != expected_copy_hash(trial, EXPECTED_PART_HASHES[trial["target"]]):
        raise RuntimeError(
            f"{phase}: owned source copy changed on disk; no source save is authorized"
        )


def drawing_witness(adapter, *, source, configuration, model_dimensions=None):
    return _drawing_witness(
        adapter,
        source=source,
        configuration=configuration,
        model_dimensions=model_dimensions,
    )[0]


def _drawing_witness(adapter, *, source, configuration, model_dimensions=None):
    coverage = {}
    if model_dimensions is None:
        semantics = _drawing_semantics(
            adapter, source=source, configuration=configuration
        )
    else:
        semantics, bank = model_dimensions.capture(
            adapter, source=source, configuration=configuration
        )
        coverage["model_dimensions"] = bank
    annotations, handles = shoulder.all_annotation_layout(adapter)
    if model_dimensions is not None:
        model_dimensions.require_printed(annotations, bank)
    return {
        "semantics": semantics,
        "annotations": annotations,
        "layout": attachments.layout(adapter.currentModel),
        **coverage,
    }, handles


class DrawingSemanticCoverageError(RuntimeError):
    """Keep a rejected, fully read snapshot separate from accepted semantics."""

    def __init__(self, snapshot):
        from collections import Counter

        self.snapshot = snapshot
        self.validation = {
            "failed_conditions": [
                name
                for name, failed in (
                    ("checked_empty", not snapshot["checked"]),
                    ("dimensions_empty", not snapshot["dimensions"]),
                    (
                        "dimensions_excluded_nonempty",
                        bool(snapshot["dimensions_excluded"]),
                    ),
                )
                if failed
            ],
            "counts": {
                name: len(snapshot[name])
                for name in (
                    "models",
                    "checked",
                    "excluded",
                    "dimensions",
                    "dimensions_excluded",
                    "semantic_attachments",
                )
            },
            "exclusion_reasons": {
                name: dict(Counter(row["reason"] for row in snapshot[name].values()))
                for name in ("excluded", "dimensions_excluded")
            },
        }
        super().__init__(
            "functional pilot semantic coverage rejected: "
            + json.dumps(self.validation, sort_keys=True)
        )


def _drawing_semantics(adapter, *, source, configuration):
    semantics = attachments.snapshot(adapter.currentModel, app=adapter.swApp)
    if not semantics["models"]:
        raise RuntimeError("functional pilot has no captured drawing view models")
    for view, model in semantics["models"].items():
        if (
            Path(model["path"]).resolve() != source
            or model["configuration"] != configuration
        ):
            raise RuntimeError(
                f"{view}: drawing does not reference the expected owned source/configuration: "
                f"{model} != {source} / {configuration}"
            )
    if (
        not semantics["checked"]
        or not semantics["dimensions"]
        or semantics["dimensions_excluded"]
    ):
        raise DrawingSemanticCoverageError(semantics)
    return semantics


def compare_drawing(app, before, after):
    from diagnostics._model_dimension_coverage import compare

    compare(before, after)
    attachments.compare(
        before["semantics"], after["semantics"], "saved production reopen"
    )
    attachments.check_layout(
        before["layout"], after["layout"], "saved production reopen"
    )
    changes = shoulder.compare_all_annotation_layout(
        app, before["annotations"], after["annotations"]
    )
    if changes:
        raise RuntimeError(
            f"saved production reopen changed native annotation layout: {changes}"
        )


def compare_drawing_reopen(before, after):
    """Keep all attachment/source semantics exact; report coordinate noise only."""
    from diagnostics._model_dimension_coverage import compare

    compare(before, after)
    attachments.compare(
        before["semantics"], after["semantics"], "saved production reopen"
    )
    attachments.check_layout(
        before["layout"], after["layout"], "saved production reopen"
    )
    return compare_reopened_annotations(before["annotations"], after["annotations"])


def _failure_document(adapter, output):
    """Never infer ownership from currentModel or from an output directory."""
    record = adapter.ownership.assert_current_owned()
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    output = Path(output).resolve()
    if (
        output not in record.paths
        or output.parent not in adapter.ownership.directories
        or int(model.GetType()) != int(DocumentKind.DRAWING)
    ):
        raise RuntimeError("failure evidence requires the trial's exact owned DRAWING")
    path = str(model.GetPathName())
    if path and Path(path).resolve() != output:
        raise RuntimeError("failure drawing has an unexpected native path")
    return {
        "path": path,
        "title": str(model.GetTitle()),
        "kind": int(model.GetType()),
        "dirty": bool(model.GetSaveFlag()),
        "visible": bool(model.Visible),
    }


class FailureEvidenceCompleteness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


def _failure_sheet(adapter):
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(float(value) for value in sheet.GetProperties2())
    if len(properties) != 8 or not all(math.isfinite(value) for value in properties):
        raise RuntimeError("failure sheet properties are not eight finite values")
    return {
        "name": str(sheet.GetName()),
        "properties": properties,
        "scale": properties[2:4],
    }


def retain_failed_drawing(adapter, trial, output, checkpoint):
    """Failure-only observations; the caller must re-raise its original error.

    Reuses the existing PDF-only native helper (empty native target), not recipe
    finalization. No rebuild, native/source save, layout or cleanup occurs here.
    Complete measured rows and native handles are checked across export; known
    measurement exclusions remain explicit. The outer pilot retains its source
    and factory guards, and the owned runner still owns cleanup.
    """
    from diagnostics import probe_retained_drawing_export as printed

    evidence = {
        "primary_error": trial["error"],
        "scope": "failed native scene, measured annotation ink and geometry/dimension witnesses; PDF-only export; no cold/native-save acceptance",
        "completeness": FailureEvidenceCompleteness.PARTIAL,
        "errors": [],
    }
    trial["failure_evidence"] = evidence
    output = Path(output).resolve()
    receipt = output.parent / "failure-evidence.json"
    handles = {}

    def persist():
        for phase, action in (
            (
                "evidence_checkpoint",
                lambda: receipt.write_text(
                    json.dumps(evidence, indent=2), encoding="utf-8"
                ),
            ),
            ("pilot_checkpoint", checkpoint),
        ):
            try:
                action()
            except Exception as error:
                evidence["completeness"] = FailureEvidenceCompleteness.PARTIAL
                evidence["errors"].append({"phase": phase, "error": repr(error)})

    def observe(phase, action, *, destination=None, key=None):
        destination = evidence if destination is None else destination
        key = phase if key is None else key
        try:
            with _telemetry.span(
                "diagnostic.datum_policy.failure_evidence", phase=phase
            ):
                destination[key] = action()
        except Exception as error:
            rejected = {"phase": phase, "error": repr(error)}
            if isinstance(error, DrawingSemanticCoverageError):
                rejected.update(snapshot=error.snapshot, validation=error.validation)
            evidence["errors"].append(rejected)

    # Refuse existing evidence before any write; never overwrite an earlier
    # observation, and do not inspect/export a borrowed or replaced document.
    observe("ownership", lambda: _failure_document(adapter, output))
    if "ownership" not in evidence:
        return
    if any(
        (output.parent / name).exists()
        for name in ("failure-evidence.json", "failure.pdf", "failure.png")
    ):
        evidence["errors"].append(
            {"phase": "targets", "error": "failure evidence targets already exist"}
        )
        return
    evidence["receipt"] = str(receipt)
    evidence["document_before"] = evidence.pop("ownership")
    persist()

    def hashes():
        paths = {"source_copy": Path(trial["copy_source"]), "native_drawing": output}
        if "original_source" in trial:
            paths["original_source"] = Path(trial["original_source"])
        return {
            name: {
                "path": str(path),
                "sha256": attachments.file_digest(path) if path.is_file() else None,
            }
            for name, path in paths.items()
        }

    def scene(phase):
        _failure_document(adapter, output)
        row = {"drawing": {}}
        native = {"drawing": adapter.currentModel}
        handles[phase] = native
        source = Path(trial["copy_source"]).resolve()

        def raw_annotations():
            records, annotation_handles = shoulder.all_annotation_layout(adapter)
            native["annotations"] = annotation_handles
            return records

        def source_parameters():
            source_model = _early_bound(
                adapter.swApp.GetOpenDocumentByName(str(source)), "IModelDoc2"
            )
            values, source_handles = source_dimensions(
                source_model, trial["target"], source
            )
            native.update(source=source_model, source_dimensions=source_handles)
            row["source_document"] = {
                "path": str(source_model.GetPathName()),
                "title": str(source_model.GetTitle()),
                "kind": int(source_model.GetType()),
                "dirty": bool(source_model.GetSaveFlag()),
                "visible": bool(source_model.Visible),
            }
            return values

        # Each independently captured field survives another field's rejection.
        # In particular a saved-owner semantic check can reject an UNSAVED
        # RD1@...@Draw52.Drawing without discarding all already measurable ink.
        # Raw annotations are scanned once per phase, never via _drawing_witness.
        for name, reader in (
            ("annotations", raw_annotations),
            ("layout", lambda: attachments.layout(adapter.currentModel)),
            ("sheet", lambda: _failure_sheet(adapter)),
            (
                "semantics",
                lambda: _drawing_semantics(
                    adapter,
                    source=source,
                    configuration=trial["source_before"]["configuration"],
                ),
            ),
        ):
            observe(f"{phase}.{name}", reader, destination=row["drawing"], key=name)
        observe(f"{phase}.source", source_parameters, destination=row, key="source")
        return row

    observe("hashes_before", hashes)
    observe("before", lambda: scene("before"))
    persist()
    pdf, png = output.parent / "failure.pdf", output.parent / "failure.png"

    def pdf_export():
        _failure_document(adapter, output)
        printed.export_pdf_only(adapter, pdf)
        return {"path": str(pdf), "sha256": attachments.file_digest(pdf)}

    def render():
        printed.render_pdf_png(pdf, png)
        return {"path": str(png), "sha256": attachments.file_digest(png)}

    observe("pdf", pdf_export)
    persist()
    if "pdf" in evidence:
        observe("png", render)
        persist()
    # Always observe post-export state/hashes, even if export or rasterization
    # failed. Independent phases retain these when a full snapshot is rejected.
    observe("document_after", lambda: _failure_document(adapter, output))
    observe("hashes_after", hashes)
    observe("after", lambda: scene("after"))
    persist()

    def equal_field(first, last, label):
        if first != last:
            raise RuntimeError(f"failure PDF export changed {label}")
        return "unchanged"

    def source_unchanged():
        before, after = evidence["before"], evidence["after"]
        equal_field(
            before["source_document"], after["source_document"], "source document state"
        )
        first, last = handles["before"], handles["after"]
        if int(adapter.swApp.IsSame(first["source"], last["source"])) != 1:
            raise RuntimeError("failure export replaced source native identity")
        require_same_source(
            before["source"],
            after["source"],
            "failure PDF export",
            app=adapter.swApp,
            handles_before=first["source_dimensions"],
            handles_after=last["source_dimensions"],
        )
        return "unchanged"

    def raw_unchanged():
        before, after = evidence["before"]["drawing"], evidence["after"]["drawing"]
        first, last = handles["before"], handles["after"]
        if int(adapter.swApp.IsSame(first["drawing"], last["drawing"])) != 1:
            raise RuntimeError("failure export replaced drawing native identity")
        shoulder.compare_all_annotation_layout(
            adapter.swApp,
            before["annotations"],
            after["annotations"],
            first["annotations"],
            last["annotations"],
        )
        return equal_field(
            before["annotations"],
            after["annotations"],
            "raw native annotation measurements",
        )

    for field, label in (("document", "document"), ("hashes", "hash")):
        if all(f"{field}_{phase}" in evidence for phase in ("before", "after")):
            observe(
                f"{label}_preservation",
                lambda field=field: equal_field(
                    evidence[f"{field}_before"], evidence[f"{field}_after"], field
                ),
            )
    before, after = evidence.get("before", {}), evidence.get("after", {})
    if "source" in before and "source" in after:
        observe("source_preservation", source_unchanged)
    for field, label, compare in (
        ("annotations", "raw", raw_unchanged),
        (
            "semantics",
            "semantic",
            lambda: attachments.compare(
                before["drawing"]["semantics"],
                after["drawing"]["semantics"],
                "failure PDF export",
            ),
        ),
        (
            "layout",
            "layout",
            lambda: attachments.check_layout(
                before["drawing"]["layout"],
                after["drawing"]["layout"],
                "failure PDF export",
            ),
        ),
        (
            "sheet",
            "sheet",
            lambda: equal_field(
                before["drawing"]["sheet"],
                after["drawing"]["sheet"],
                "sheet properties",
            ),
        ),
    ):
        if all(field in row.get("drawing", {}) for row in (before, after)):
            observe(f"{label}_preservation", compare)
    if "source" in before:
        observe(
            "recipe_source_preservation",
            lambda: require_same_source(
                trial["source_before"],
                evidence["before"]["source"],
                "failed recipe before evidence export",
            ),
        )
    if not evidence["errors"]:
        evidence["completeness"] = FailureEvidenceCompleteness.COMPLETE
    persist()


def require_drawing_save(variant, source_observation, order):
    from diagnostics._native_drawing_save_control import DrawingSave
    from diagnostics._source_save_boundaries import SourceObservation

    if variant is None:
        return
    if (
        not isinstance(variant, DrawingSave)
        or source_observation is not SourceObservation.ALIGNMENT_SAVE
        or tuple(order) != ("alignment_pinion",)
    ):
        raise ValueError(
            "drawing-save control requires only alignment_pinion with alignment_save observations"
        )


def require_callout_storage(variant, source_observation, drawing_save, order):
    if variant is None:
        return
    from diagnostics._drawing_lower_text_control import CalloutStorage
    from diagnostics._native_drawing_save_control import DrawingSave
    from diagnostics._source_save_boundaries import SourceObservation

    if (
        not isinstance(variant, CalloutStorage)
        or not isinstance(drawing_save, DrawingSave)
        or source_observation is not SourceObservation.ALIGNMENT_SAVE
        or tuple(order) != ("alignment_pinion",)
    ):
        raise ValueError(
            "callout-storage control requires alignment_pinion, alignment_save observations and an explicit drawing-save arm"
        )


async def pilot(
    adapter,
    candidate,
    source_root,
    guard_root,
    output_root,
    *,
    targets=None,
    setup_controller=None,
    linear_control=None,
    source_observation=None,
    drawing_save=None,
    callout_storage=None,
    source_callout_authoring=None,
):
    grid_control = grid_control_from_environment()
    tooth_observation = observation_from_environment()
    order = target_order(targets)
    require_tooth_targets(tooth_observation, order)
    from diagnostics._source_save_boundaries import (
        require_targets as require_source_targets,
    )

    require_source_targets(source_observation, order)
    require_drawing_save(drawing_save, source_observation, order)
    require_callout_storage(callout_storage, source_observation, drawing_save, order)
    from diagnostics._source_callout_authoring import require_selection

    require_selection(
        source_callout_authoring,
        callout_storage,
        source_observation,
        drawing_save,
        order,
    )
    callout_contract = selected_callout_contract(
        candidate, source_observation, callout_storage, source_callout_authoring
    )
    protected_targets = tuple(dict.fromkeys((*ORDER, *order)))
    if linear_control is not None:
        from diagnostics._linear_dimension_arrangement import require_targets

        require_targets(linear_control.variant, order)
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="datum-policy-", dir=output_root))
    adapter.ownership.register_directory(directory)
    sources = {
        target: (source_root / f"{target.replace('_', '-')}.SLDPRT").resolve(
            strict=True
        )
        for target in protected_targets
    }
    guards = {
        target: (guard_root / sources[target].name).resolve(strict=True)
        for target in protected_targets
    }
    report = {
        "status": "running",
        "candidate": candidate,
        "helper_revision": benchmark.revision("HEAD"),
        "order": order,
        "protected_targets": protected_targets,
        "factory": setup_controller.variant.value if setup_controller else "normal",
        "bsurf_grid_control": grid_control.value,
        "tooth_selector_observation": tooth_observation.value,
        "trials": [],
        "scope": "one functional build per recipe; no speedup/full-pipeline claim",
        "source_witness_scope": "exact original/copy disk hashes and named recipe dimension identities/values/tolerances/BASIC; not full in-memory source immutability",
    }
    report_path = directory / "pilot.json"
    failure_output = None
    pilot_started = time.perf_counter()
    report["elapsed_scope"] = (
        "pilot source guards, preparation, recipe and cold witnesses; excludes parent lock/attach and outer owned-session cleanup"
    )

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    checkpoint()
    _telemetry.info("combined datum-policy pilot report", path=str(report_path))
    try:
        report["sources_before"] = require_sources(sources, guards)
        for path in dict.fromkeys((*sources.values(), *guards.values())):
            adapter.ownership.register_source(path)
        report["helpers"] = helper_fingerprints()
        report["imported_adapter"] = adapter_fingerprints()
        for target in order:
            failure_output = None
            trial = {"target": target, "status": "running"}
            report["trials"].append(trial)
            trial_dir = directory / target
            trial_dir.mkdir()
            adapter.ownership.register_directory(trial_dir)
            copy_source = (
                trial_dir / f"{sources[target].stem}-source-{directory.name}.SLDPRT"
            )
            shutil.copy2(sources[target], copy_source)
            trial.update(
                original_source=str(sources[target]), copy_source=str(copy_source)
            )
            # Do not register/freeze this as a protected source: it is an owned
            # COPY, and imported drawing formatting can legitimately dirty it.
            require_copy_hash(trial, "copied")
            checkpoint()
            module = benchmark.load_recipe(
                candidate, target, trial_dir, source=copy_source
            )
            if callout_contract is not None:
                from diagnostics._callout_recipe_contract import recipe_contract

                if (
                    recipe_contract(
                        (trial_dir / "recipe-source.py").read_text(encoding="utf-8")
                    )
                    is not callout_contract
                ):
                    raise RuntimeError(
                        "loaded recipe callout contract changed after preflight"
                    )
                trial["callout_contract"] = callout_contract.value
            entity_acceptance = None
            manifest = TARGETS[target]
            entity_handles = after_entities = reopened_entities = None
            if manifest.view_roles:
                entity_acceptance = ViewEntityAcceptance(module, manifest)
            if manifest.entity_labels:
                entity_acceptance = EntityAcceptance(module, manifest)
            if entity_acceptance is not None:
                trial["acceptance_manifest"] = {
                    "source_sha256": EXPECTED_PART_HASHES[target],
                    "dimensions": {
                        key: sorted(names) for key, names in manifest.dimensions.items()
                    },
                    "explicit_labels": manifest.entity_labels,
                    "view_roles": {
                        label: {
                            "orientation": role.orientation,
                            "annotation_kind": role.annotation_kind,
                            "entity_type": role.entity_type,
                            "resolver": role.resolver.value,
                        }
                        for label, role in manifest.view_roles.items()
                    },
                    "entity_context": "view" if manifest.view_roles else "model",
                    "input_scope": "exact disk identity; builder content recorded, not inferred native build provenance",
                    "code": {
                        f"cad/scripts/{name}.py": attachments.file_digest(
                            ROOT / f"cad/scripts/{name}.py"
                        )
                        for name in (f"build_{target}", manifest.spec_module)
                    },
                }
            failure_output = module.OUTPUTS.slddrw
            await adapter.close_owned_documents()
            from _drawing_build import normal_drawing_factory

            drawing_factory = normal_drawing_factory(adapter, module.TEMPLATE_SPEC)
            if setup_controller is not None:
                drawing_factory = await setup_controller.configure(
                    adapter, module, trial, trial_dir
                )
            check(
                "open exact owned source copy",
                await adapter.open_model(str(copy_source)),
            )
            adapter.ownership.assert_current_owned()
            source_model = adapter.currentModel
            trial["source_before"], source_handles = source_dimensions(
                source_model, target, copy_source
            )
            from diagnostics._model_dimension_coverage import (
                ModelDimensionCoverage,
                SemanticCoverage,
            )

            witness_kwargs = {}
            if manifest.coverage is SemanticCoverage.MODEL_DIMENSIONS_ONLY:
                witness_kwargs["model_dimensions"] = ModelDimensionCoverage(
                    adapter, manifest, source_model, copy_source, trial
                )
            source_callout_control = None
            if source_callout_authoring is not None:
                from diagnostics._source_callout_authoring import SourceCalloutControl

                source_callout_control = SourceCalloutControl(
                    adapter, module, trial, checkpoint
                )
                source_model, trial["source_before"], source_handles = (
                    await source_callout_control.author(
                        source_model, trial["source_before"], source_handles,
                        lambda model: source_dimensions(model, target, copy_source),
                    )
                )
                require_copy_hash(trial, "authored_cold_baseline")
            if manifest.entity_labels:
                trial["source_entities_before"], entity_handles = (
                    entity_acceptance.source_snapshot(source_model)
                )
            trial["recipe_sha256"] = attachments.file_digest(
                trial_dir / "recipe-source.py"
            )
            build_kwargs = {"drawing_factory": drawing_factory}
            callout_control = source_callout_control
            if callout_storage is not None:
                from diagnostics._drawing_lower_text_control import LowerTextControl

                callout_control = LowerTextControl(
                    adapter, module, trial, source_handles, storage=callout_storage
                )
            save_control = nullcontext()
            if drawing_save is not None:
                from diagnostics._native_drawing_save_control import (
                    native_drawing_save_control,
                )

                trial["drawing_save"] = drawing_save.value
                trial["native_save_calls"] = []
                save_control = native_drawing_save_control(
                    adapter, drawing_save, records=trial["native_save_calls"]
                )
            source_boundaries = None
            if source_observation is not None:
                from diagnostics._source_save_boundaries import SourceSaveBoundaries

                source_boundaries = SourceSaveBoundaries(
                    adapter,
                    module,
                    trial,
                    checkpoint,
                    source_model,
                    trial["source_before"],
                    source_handles,
                    lambda: source_dimensions(source_model, target, copy_source),
                    callout_contract=callout_contract,
                    **(
                        {"drawing_reader": callout_control.boundary_snapshot}
                        if callout_control is not None
                        else {}
                    ),
                )
            if linear_control is not None:
                build_kwargs.update(
                    linear_control.bind(
                        adapter,
                        module,
                        trial,
                        checkpoint,
                        lambda: source_dimensions(source_model, target, copy_source),
                        source_model,
                    )
                )
            started = time.perf_counter()
            try:
                with _telemetry.span("diagnostic.datum_policy.recipe", target=target):
                    with adapter.ownership.creating_document(
                        DocumentKind.DRAWING, module.OUTPUTS.slddrw
                    ):
                        with (
                            # Complete native rename ownership before source
                            # after-banks; the creation scope exits too late.
                            # LEGACY leaves this base intact, modern overrides it.
                            patch("_drawing_common.save_drawing", owned_save_drawing),
                            save_control,
                            (
                                callout_control.observe()
                                if callout_control is not None
                                else nullcontext()
                            ),
                            (
                                # Install common/recipe identity-checked entity
                                # hooks before the selected source observer
                                # wraps those recipe aliases for read-only banks.
                                entity_acceptance.observe(adapter, entity_handles)
                                if entity_acceptance is not None
                                else nullcontext()
                            ),
                            (
                                source_boundaries.observe()
                                if source_boundaries is not None
                                else nullcontext()
                            ),
                            observe_selector(
                                adapter, module, source_model, trial, tooth_observation
                            ),
                        ):
                            artifacts = await module.build(adapter, **build_kwargs)
                if source_boundaries is not None:
                    source_boundaries.require_used()
                if callout_control is not None:
                    callout_control.require_used()
                if setup_controller is not None:
                    setup_controller.require_used()
                if setup_controller is None:
                    drawing_factory.require_used()
                if linear_control is not None:
                    linear_control.require_used()
            finally:
                trial["recipe_seconds"] = time.perf_counter() - started
                if entity_acceptance is not None:
                    trial["entity_context_observations"] = (
                        entity_acceptance.context_report
                    )
                checkpoint()
            trial["artifacts"] = benchmark.validate_artifacts(artifacts, module.OUTPUTS)
            require_copy_hash(trial, "after_recipe")
            adapter.ownership.assert_current_owned()
            with _telemetry.span(
                "diagnostic.datum_policy.drawing_witness", target=target, phase="built"
            ):
                trial["built"] = drawing_witness(
                    adapter,
                    source=copy_source,
                    configuration=trial["source_before"]["configuration"],
                    **witness_kwargs,
                )
            trial["source_after"], after_handles = source_dimensions(
                source_model, target, copy_source
            )
            require_same_source(
                trial["source_before"],
                trial["source_after"],
                "recipe",
                app=adapter.swApp,
                handles_before=source_handles,
                handles_after=after_handles,
            )
            if callout_control is not None:
                trial["callout_storage_built"] = callout_control.snapshot(
                    adapter,
                    after_handles,
                    phase="built",
                    annotations=trial["built"]["annotations"],
                )
            if manifest.entity_labels:
                trial["source_entities_after"], after_entities = (
                    entity_acceptance.source_snapshot(source_model)
                )
                require_same_source(
                    trial["source_entities_before"],
                    trial["source_entities_after"],
                    "recipe controlled faces/boundaries",
                    app=adapter.swApp,
                    handles_before=entity_handles,
                    handles_after=after_entities,
                )
            if entity_acceptance is not None:
                trial["explicit_entities_built"] = entity_acceptance.drawing_snapshot(
                    adapter, after_entities, phase="built"
                )
            await adapter.close_owned_documents()
            require_copy_hash(trial, "after_close")
            check(
                "reopen owned production drawing",
                await adapter.open_model(str(module.OUTPUTS.slddrw)),
            )
            adapter.ownership.assert_current_owned()
            with _telemetry.span(
                "diagnostic.datum_policy.drawing_witness",
                target=target,
                phase="reopened",
            ):
                trial["reopened"] = drawing_witness(
                    adapter,
                    source=copy_source,
                    configuration=trial["source_before"]["configuration"],
                    **witness_kwargs,
                )
            if callout_control is not None:
                cold_source = adapter.swApp.GetOpenDocumentByName(str(copy_source))
                cold_values, cold_handles = source_dimensions(
                    cold_source, target, copy_source
                )
                require_same_source(
                    trial["source_before"], cold_values, "lower-text cold source"
                )
                trial["callout_storage_reopened"] = callout_control.snapshot(
                    adapter,
                    cold_handles,
                    phase="reopened",
                    annotations=trial["reopened"]["annotations"],
                )
                # These rows contain raw parameter values and exact names/text,
                # not geometry coordinates or native handles from closed docs.
                # Retain both observations before rejecting any cold drift.
                if trial["callout_storage_built"] != trial["callout_storage_reopened"]:
                    raise RuntimeError("cold reopen lower-text mapping changed")
            trial["reopen_annotation_comparison"] = compare_drawing_reopen(
                trial["built"], trial["reopened"]
            )
            if trial["reopen_annotation_comparison"]["status"] != "passed":
                raise RuntimeError(
                    "saved production reopen changed native annotation layout: "
                    f"{trial['reopen_annotation_comparison']['rejected']}"
                )
            reopened_source = adapter.swApp.GetOpenDocumentByName(str(copy_source))
            trial["source_reopened"], _ = source_dimensions(
                reopened_source, target, copy_source
            )
            require_same_source(
                trial["source_before"], trial["source_reopened"], "saved reopen"
            )
            if manifest.entity_labels:
                trial["source_entities_reopened"], reopened_entities = (
                    entity_acceptance.source_snapshot(reopened_source)
                )
                require_same_source(
                    trial["source_entities_before"],
                    trial["source_entities_reopened"],
                    "cold controlled faces/boundaries",
                )
            if entity_acceptance is not None:
                trial["explicit_entities_reopened"] = (
                    entity_acceptance.drawing_snapshot(
                        adapter, reopened_entities, phase="reopened"
                    )
                )
                if manifest.view_roles:
                    trial["explicit_entity_comparison"] = entity_acceptance.compare_cold(
                        trial["explicit_entities_built"],
                        trial["explicit_entities_reopened"],
                    )
                    explicit_changed = (
                        trial["explicit_entity_comparison"]["status"] != "passed"
                    )
                else:
                    explicit_changed = (
                        trial["explicit_entities_built"]
                        != trial["explicit_entities_reopened"]
                    )
                if explicit_changed:
                    raise RuntimeError(
                        "cold reopen changed explicit annotation role/geometry/view"
                    )
            benchmark.check_fingerprints(
                report["helpers"],
                helper_fingerprints(),
                "frozen helpers/config/template",
            )
            if report["imported_adapter"] != adapter_fingerprints():
                raise RuntimeError(
                    "actual imported adapter changed during functional pilot"
                )
            require_sources(sources, guards)
            await adapter.close_owned_documents()
            require_copy_hash(trial, "after_reopened_close")
            trial["status"] = "passed"
            checkpoint()
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        if report["trials"]:
            report["trials"][-1].update(status="failed", error=repr(error))
            if isinstance(error, DrawingSemanticCoverageError):
                report["trials"][-1]["semantic_failure"] = {
                    "snapshot": error.snapshot,
                    "validation": error.validation,
                }
        if failure_output is not None:
            try:
                checkpoint()
                retain_failed_drawing(
                    adapter, report["trials"][-1], failure_output, checkpoint
                )
            except Exception as evidence_error:
                report["trials"][-1]["failure_evidence_error"] = repr(evidence_error)
        raise
    finally:
        primary_error = sys.exception()
        runtime_guard_errors = []
        for trial in report["trials"]:
            if "copy_source" not in trial:
                continue
            try:
                trial["copy_final"] = attachments.file_digest(
                    Path(trial["copy_source"])
                )
                from diagnostics._source_callout_authoring import expected_copy_hash

                try:
                    expected_hash = expected_copy_hash(
                        trial, EXPECTED_PART_HASHES[trial["target"]]
                    )
                except Exception as error:
                    trial["copy_final_expected_error"] = repr(error)
                    runtime_guard_errors.append(error)
                    continue
                if trial["copy_final"] != expected_hash:
                    runtime_guard_errors.append(
                        RuntimeError("final owned source copy changed on disk")
                    )
            except OSError as error:
                trial["copy_final"] = {"error": repr(error)}
                runtime_guard_errors.append(error)
        report["sources_after"] = {}
        for path in (*sources.values(), *guards.values()):
            try:
                report["sources_after"][str(path)] = attachments.file_digest(path)
            except OSError as error:
                report["sources_after"][str(path)] = {"error": repr(error)}
        for label, action in (
            ("original source hashes", lambda: require_sources(sources, guards)),
            (
                "frozen helper files",
                lambda: benchmark.check_fingerprints(
                    report["helpers"],
                    helper_fingerprints(),
                    "frozen helpers/config/template",
                ),
            ),
            (
                "actual adapter",
                lambda: benchmark.check_fingerprints(
                    report["imported_adapter"],
                    adapter_fingerprints(),
                    "actual imported adapter",
                ),
            ),
        ):
            if label == "frozen helper files" and "helpers" not in report:
                continue
            if label == "actual adapter" and "imported_adapter" not in report:
                continue
            try:
                action()
            except Exception as error:
                runtime_guard_errors.append(error)
        report["runtime_final_guard_errors"] = [
            repr(error) for error in runtime_guard_errors
        ]
        if runtime_guard_errors:
            report["status"] = "failed"
        guard_errors = []
        if setup_controller is not None:
            guard_errors = setup_controller.final_guards()
            report["factory_final_guards"] = setup_controller.guards
            if guard_errors:
                report.update(
                    status="failed",
                    factory_guard_errors=[repr(error) for error in guard_errors],
                )
        report["elapsed_seconds"] = time.perf_counter() - pilot_started
        checkpoint()
        if guard_errors:
            raise BaseExceptionGroup(
                "functional recipe/factory final guards failed",
                ([primary_error] if primary_error is not None else [])
                + guard_errors
                + runtime_guard_errors,
            )
        if runtime_guard_errors and primary_error is None:
            raise BaseExceptionGroup(
                "functional recipe final guards failed", runtime_guard_errors
            )
        if runtime_guard_errors and primary_error is not None:
            primary_error.add_note(
                f"additional final guard failures: {report['runtime_final_guard_errors']}"
            )
    return {"report": str(report_path)}


def main(argv=None):
    grid_control_from_environment()  # invalid opt-in refuses before parent/worker COM routing
    tooth_observation = observation_from_environment()
    from diagnostics._source_callout_authoring import (
        SourceCalloutAuthoring, require_selection,
    )
    from diagnostics._drawing_lower_text_control import CalloutStorage
    from diagnostics._native_drawing_save_control import DrawingSave
    from diagnostics._source_save_boundaries import (
        SourceObservation,
        require_targets as require_source_targets,
    )
    from diagnostics._linear_dimension_arrangement import (
        LinearArrangement,
        ParallelLinearControl,
        require_targets,
    )
    from diagnostics._recipe_template_factory import (
        DrawingFactory,
        RecipeTemplateFactory,
        require_factory_environment,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--guard-root", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument("--candidate", default="HEAD")
    parser.add_argument(
        "--factory",
        type=DrawingFactory,
        choices=tuple(DrawingFactory),
        help="explicit full-recipe factory control; prepared materialization is timed separately",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=tuple(EXPECTED_PART_HASHES),
        help="repeat to choose recipe order; default: rocker_arm then channel_lever",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument(
        "--source-callout-authoring", type=SourceCalloutAuthoring,
        choices=tuple(SourceCalloutAuthoring),
        help="explicit owned alignment PART fit-text authoring; no drawing callout setter",
    )
    parser.add_argument(
        "--callout-storage",
        type=CalloutStorage,
        choices=tuple(CalloutStorage),
        help="diagnostic alignment drawing lower text; explicit save and source banks required",
    )
    parser.add_argument(
        "--drawing-save",
        type=DrawingSave,
        choices=tuple(DrawingSave),
        help="diagnostic native save only; requires alignment source observations",
    )
    parser.add_argument(
        "--source-observation",
        type=SourceObservation,
        choices=tuple(SourceObservation),
        help="read-only alignment source banks around callout/precision/native-save/PDF",
    )
    parser.add_argument(
        "--linear-dimensions",
        type=LinearArrangement,
        choices=tuple(LinearArrangement),
        help="diagnostic only: exact channel_lever linear pairs before original layout",
    )
    args = parser.parse_args(argv)
    order = target_order(args.target)
    require_tooth_targets(tooth_observation, order)
    require_source_targets(args.source_observation, order)
    require_drawing_save(args.drawing_save, args.source_observation, order)
    require_callout_storage(
        args.callout_storage, args.source_observation, args.drawing_save, order
    )
    require_selection(
        args.source_callout_authoring, args.callout_storage,
        args.source_observation, args.drawing_save, order,
    )
    require_targets(args.linear_dimensions, order)
    require_owned_diagnostic_environment()  # before dodo._run in the parent
    if args.factory is not None:
        require_factory_environment()
    candidate = benchmark.revision(args.candidate)
    selected_callout_contract(
        candidate,
        args.source_observation,
        args.callout_storage,
        args.source_callout_authoring,
    )
    source_root, guard_root = (
        args.source_root.resolve(strict=True),
        args.guard_root.resolve(strict=True),
    )
    if not args.worker:
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--source-root",
                str(source_root),
                "--guard-root",
                str(guard_root),
                "--report-root",
                str(args.report_root.resolve()),
                "--candidate",
                candidate,
                *(
                    ["--factory", args.factory.value]
                    if args.factory is not None
                    else []
                ),
                *(argument for target in order for argument in ("--target", target)),
                *(
                    ["--source-callout-authoring", args.source_callout_authoring.value]
                    if args.source_callout_authoring is not None else []
                ),
                *(
                    ["--callout-storage", args.callout_storage.value]
                    if args.callout_storage is not None
                    else []
                ),
                *(
                    ["--drawing-save", args.drawing_save.value]
                    if args.drawing_save is not None
                    else []
                ),
                *(
                    ["--source-observation", args.source_observation.value]
                    if args.source_observation is not None
                    else []
                ),
                *(
                    ["--linear-dimensions", args.linear_dimensions.value]
                    if args.linear_dimensions is not None
                    else []
                ),
                "--worker",
            ],
            "combined datum-policy functional pilot",
            com=True,
            log_stem="datum-policy-functional",
        )
        return 0
    return run_copy_diagnostic(
        lambda adapter: pilot(
            adapter,
            candidate,
            source_root,
            guard_root,
            args.report_root.resolve(),
            targets=order,
            **(
                {"source_callout_authoring": args.source_callout_authoring}
                if args.source_callout_authoring is not None else {}
            ),
            **(
                {"callout_storage": args.callout_storage}
                if args.callout_storage is not None
                else {}
            ),
            **(
                {"drawing_save": args.drawing_save}
                if args.drawing_save is not None
                else {}
            ),
            **(
                {"source_observation": args.source_observation}
                if args.source_observation is not None
                else {}
            ),
            **(
                {"setup_controller": RecipeTemplateFactory(args.factory)}
                if args.factory is not None
                else {}
            ),
            **(
                {"linear_control": ParallelLinearControl(args.linear_dimensions)}
                if args.linear_dimensions is not None
                else {}
            ),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
