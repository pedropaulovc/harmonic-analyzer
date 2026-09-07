"""Author an explicit reviewed note-layout variant into an owned DRWDOT.

Blank-only native control: no source models, production recipe edits, normalized
defaults, or original-template replacement. The second drawing inherits the
saved copy without any layout/default setters. Exact raw witnesses and full-page
PDF glyph/300-DPI pixel equality prove this bounded save/re-instantiation path;
resolved model-linked field fit and full rocker/lever recipes remain separate.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

import _drawing_sheet_setup as sheet_setup  # noqa: E402

import _telemetry  # noqa: E402
from diagnostics import _baked_template_layout as layout  # noqa: E402
from diagnostics import _baked_template_gaps as gaps  # noqa: E402
from diagnostics import _baked_template_material as material  # noqa: E402
from diagnostics import _baked_template_material_finish as material_finish  # noqa: E402
from diagnostics import benchmark_template_defaults as defaults  # noqa: E402
from diagnostics import probe_prepared_template_cache as printed  # noqa: E402
from diagnostics import probe_datum_policy_recipes as pilot  # noqa: E402
from diagnostics import probe_retained_drawing_export as retained  # noqa: E402
from diagnostics._owned_native_documents import DocumentKind, run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402


def bare_drawing(adapter, template):
    """Deliberately bypass normal metric/style normalization during authoring."""
    return sheet_setup.new_drawing(
        adapter,
        template=str(template),
        width=sheet_setup.ASME_B_WIDTH_M,
        height=sheet_setup.ASME_B_HEIGHT_M,
    )


async def transform(adapter, directory, report, checkpoint, population=None):
    if (
        report.get("layout_policy") == gaps.LayoutPolicy.MATERIAL_CENTER.value
        and population is not None
    ):
        raise ValueError("material-center cannot combine historical populated-gap changes")
    snapshot = layout.blank_snapshot
    if report.get("layout_policy") in (
        gaps.LayoutPolicy.MATERIAL_CENTER.value,
        gaps.LayoutPolicy.MATERIAL_FINISH.value,
    ):
        snapshot = material.blank_snapshot
    derived = directory / f"{directory.name}.DRWDOT"
    report["derived_template"] = str(derived)
    with adapter.ownership.creating_document(DocumentKind.DRAWING, derived):
        bare_drawing(adapter, sheet_setup.PROJECT_DRWDOT)
    report["before"], handles, lines = snapshot(adapter)
    label_plan, phase_scope = layout.blank_label_plan, layout.blank_phase_scope
    apply, require_transition = layout.apply_layout, layout.require_transition
    if report.get("layout_policy") == gaps.LayoutPolicy.MATERIAL_FINISH.value:
        if population is None:
            raise ValueError("material-finish requires exact populated evidence")
        report["plan"], report["predicted_population"] = material_finish.measured_plan(
            report["before"]["notes"], lines, population["targets"]
        )
        label_plan, phase_scope = material_finish.static_label_plan, material_finish.phase_scope
        apply = material_finish.apply_layout

        def require_transition(before, after, plan):
            material_finish.require_transition(before, after, plan, lines, population["targets"])

    elif report.get("layout_policy") == gaps.LayoutPolicy.MATERIAL_CENTER.value:
        report["plan"] = material.material_plan(report["before"]["notes"], lines)
        label_plan, phase_scope = material.static_label_plan, material.phase_scope
        apply = material.apply_layout

        def require_transition(before, after, plan):
            material.require_transition(before, after, plan, lines)

    else:
        report["plan"] = layout.layout_plan(report["before"]["notes"], lines)
    if population is not None and report.get("layout_policy") != gaps.LayoutPolicy.MATERIAL_FINISH.value:
        report["plan"], report["predicted_population"] = gaps.measured_plan(
            report["before"]["notes"], lines, report["plan"], population["targets"]
        )
        label_plan, phase_scope = gaps.static_label_plan, gaps.phase_scope
    report["operations"] = []
    checkpoint()
    adapter.ownership.assert_current_owned()
    apply(adapter, handles, report["plan"], report["operations"], checkpoint)
    report["after"], after_handles, _ = snapshot(adapter)
    checkpoint()
    layout.require_same_handles(adapter.swApp, handles, after_handles)
    require_transition(report["before"], report["after"], report["plan"])
    report["phase_scope"] = phase_scope(report["after"]["notes"])
    plan = label_plan(report["after"]["notes"], lines, report["plan"])
    report["field_fit"] = layout.require_field_fit(report["after"]["notes"], plan)
    first = directory / "authored"
    first.mkdir()
    adapter.ownership.register_directory(first)
    report["printed_authored"] = printed.printed_witness(adapter, first)
    report["pdf_fit"] = layout.pdf_field_fit(
        Path(report["printed_authored"]["pdf"]), report["after"]["notes"], plan
    )
    report["after_pdf"], pdf_handles, _ = snapshot(adapter)
    checkpoint()
    layout.require_same_handles(adapter.swApp, handles, pdf_handles)
    layout.require_equal(
        report["after"], report["after_pdf"], "authoring PDF observation"
    )
    report["save"] = {}
    with adapter.ownership.saving_as(derived):
        defaults.save_prepared_template(adapter.currentModel, derived, report["save"])
    report["saved"], saved_handles, _ = snapshot(adapter)
    checkpoint()
    layout.require_same_handles(adapter.swApp, handles, saved_handles)
    layout.require_equal(report["after"], report["saved"], "fresh DRWDOT save")
    await adapter.close_owned_documents()
    adapter.ownership.freeze_owned_input(derived)
    report["derived_sha256"] = pilot.attachments.file_digest(derived)
    checkpoint()

    # A distinct native document loaded from the saved bytes; never reuse closed
    # handles for IsSame, and never save this readback drawing to the DRWDOT.
    with adapter.ownership.creating_document(
        DocumentKind.DRAWING, directory / "unsaved-readback.SLDDRW"
    ):
        bare_drawing(adapter, derived)
    report["reinstantiated"], readback_handles, readback_lines = snapshot(
        adapter
    )
    checkpoint()
    layout.require_equal(
        report["saved"], report["reinstantiated"], "bare saved-template inheritance"
    )
    report["inherited_phase_scope"] = phase_scope(report["reinstantiated"]["notes"])
    cold_plan = label_plan(
        report["reinstantiated"]["notes"], readback_lines, report["plan"]
    )
    report["inherited_field_fit"] = layout.require_field_fit(
        report["reinstantiated"]["notes"], cold_plan
    )
    second = directory / "inherited"
    second.mkdir()
    adapter.ownership.register_directory(second)
    report["printed_inherited"] = printed.printed_witness(adapter, second)
    report["inherited_pdf_fit"] = layout.pdf_field_fit(
        Path(report["printed_inherited"]["pdf"]),
        report["reinstantiated"]["notes"],
        cold_plan,
    )
    report["reinstantiated_after_pdf"], final_handles, _ = snapshot(
        adapter
    )
    checkpoint()
    layout.require_same_handles(adapter.swApp, readback_handles, final_handles)
    layout.require_equal(
        report["reinstantiated"],
        report["reinstantiated_after_pdf"],
        "inherited PDF observation",
    )
    report["printed_comparison"] = printed.compare_printed(
        report["printed_authored"], report["printed_inherited"]
    )
    await adapter.close_owned_documents()
    retained.require_hashes(
        {str(derived): report["derived_sha256"]}, "derived template remains exact"
    )
    report["outcome"] = "blank_template_layout_persisted"


async def probe(
    adapter,
    output_root,
    *,
    policy=gaps.LayoutPolicy.FOUR_NOTES,
    population_path=None,
    population_sha256=None,
):
    expected = {
        str(sheet_setup.PROJECT_DRWDOT): pilot.attachments.file_digest(sheet_setup.PROJECT_DRWDOT)
    }
    population = None
    if policy in (gaps.LayoutPolicy.POPULATED_GAPS, gaps.LayoutPolicy.MATERIAL_FINISH):
        if population_path is None or population_sha256 is None:
            raise ValueError(f"{policy.value} requires an exact receipt path and SHA256")
        read_population = material_finish.read_population if policy is gaps.LayoutPolicy.MATERIAL_FINISH else gaps.read_population
        population = read_population(
            population_path, population_sha256, expected[str(sheet_setup.PROJECT_DRWDOT)]
        )
        expected[str(population_path)] = population_sha256
    elif (
        policy not in (gaps.LayoutPolicy.FOUR_NOTES, gaps.LayoutPolicy.MATERIAL_CENTER)
        or population_path is not None
        or population_sha256 is not None
    ):
        raise ValueError(
            "population evidence is valid only for the explicit populated-gaps variant"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="baked-template-", dir=output_root))
    adapter.ownership.register_directory(directory)
    for source in expected:
        adapter.ownership.register_source(Path(source))
    path = directory / "template-layout.json"
    report = {
        "status": "running",
        "scope": f"blank-only {policy} DRWDOT layout; fresh resolved fit/full recipes pending",
        "layout_policy": policy.value,
        "population_evidence": None
        if population is None
        else {key: value for key, value in population.items() if key != "targets"},
        "inputs_before": expected,
        "revision": pilot.benchmark.revision("HEAD"),
        "helpers": pilot.helper_fingerprints(),
        "adapter": pilot.adapter_fingerprints(),
        "errors": [],
    }

    def checkpoint():
        path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")

    checkpoint()
    _telemetry.info("baked blank-template report", path=str(path))
    start, errors = time.perf_counter(), []
    try:
        await transform(adapter, directory, report, checkpoint, population)
    except Exception as error:
        errors.append(error)
    finally:
        try:
            await adapter.close_owned_documents()
        except Exception as error:
            errors.append(error)
        report["inputs_after"] = retained.final_hashes(expected)
        try:
            retained.require_hashes(expected, "original template after control/cleanup")
            pilot.benchmark.check_fingerprints(
                report["helpers"],
                pilot.helper_fingerprints(),
                "frozen template control",
            )
            if report["adapter"] != pilot.adapter_fingerprints():
                raise RuntimeError("imported adapter changed during control")
        except Exception as error:
            errors.append(error)
        report.update(
            seconds=time.perf_counter() - start,
            status="failed" if errors else "passed",
            errors=[repr(error) for error in errors],
        )
        try:
            checkpoint()
        except Exception as error:
            errors.append(error)
    if errors:
        raise ExceptionGroup("baked template control/cleanup failed", errors)
    return {
        "report": str(path),
        "template": report["derived_template"],
        "outcome": report["outcome"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument(
        "--layout",
        type=gaps.LayoutPolicy,
        choices=list(gaps.LayoutPolicy),
        default=gaps.LayoutPolicy.FOUR_NOTES,
    )
    parser.add_argument("--populated-receipt", type=Path)
    parser.add_argument("--populated-sha256")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if (
        os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off"
        or not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID", "").isdecimal()
    ):
        raise RuntimeError(
            "baked template control requires remote off and expected native PID"
        )
    if args.worker:
        return run_copy_diagnostic(
            lambda adapter: probe(
                adapter,
                args.report_root.resolve(),
                policy=args.layout,
                population_path=args.populated_receipt.resolve(strict=True)
                if args.populated_receipt
                else None,
                population_sha256=args.populated_sha256,
            )
        )
    import dodo

    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--report-root",
        str(args.report_root.resolve()),
        "--worker",
        "--layout",
        args.layout.value,
    ]
    if args.populated_receipt is not None:
        command += [
            "--populated-receipt",
            str(args.populated_receipt.resolve(strict=True)),
        ]
    if args.populated_sha256 is not None:
        command += ["--populated-sha256", args.populated_sha256]
    dodo._run(
        command,
        "baked project template layout",
        com=True,
        log_stem="baked-template-layout",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
