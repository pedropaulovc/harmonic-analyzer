"""Author four approved note layouts into a fresh owned DRWDOT, then instantiate.

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

import _drawing_common as common  # noqa: E402
import _telemetry  # noqa: E402
from diagnostics import _baked_template_layout as layout  # noqa: E402
from diagnostics import benchmark_template_defaults as defaults  # noqa: E402
from diagnostics import probe_prepared_template_cache as printed  # noqa: E402
from diagnostics import probe_datum_policy_recipes as pilot  # noqa: E402
from diagnostics import probe_retained_drawing_export as retained  # noqa: E402
from diagnostics._owned_native_documents import DocumentKind, run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402


def bare_drawing(adapter, template):
    """Deliberately bypass normal metric/style normalization during authoring."""
    return common.new_drawing(
        adapter,
        template=str(template),
        width=common.ASME_B_WIDTH_M,
        height=common.ASME_B_HEIGHT_M,
    )


async def transform(adapter, directory, report, checkpoint):
    derived = directory / f"{directory.name}.DRWDOT"
    report["derived_template"] = str(derived)
    with adapter.ownership.creating_document(DocumentKind.DRAWING, derived):
        bare_drawing(adapter, common.PROJECT_DRWDOT)
    report["before"], handles, lines = layout.blank_snapshot(adapter)
    report["plan"] = layout.layout_plan(report["before"]["notes"], lines)
    report["operations"] = []
    checkpoint()
    adapter.ownership.assert_current_owned()
    layout.apply_layout(
        adapter, handles, report["plan"], report["operations"], checkpoint
    )
    report["after"], after_handles, _ = layout.blank_snapshot(adapter)
    checkpoint()
    layout.require_same_handles(adapter.swApp, handles, after_handles)
    layout.require_transition(report["before"], report["after"], report["plan"])
    report["phase_scope"] = layout.blank_phase_scope(report["after"]["notes"])
    plan = layout.blank_label_plan(report["after"]["notes"], lines, report["plan"])
    report["field_fit"] = layout.require_field_fit(report["after"]["notes"], plan)
    first = directory / "authored"
    first.mkdir()
    adapter.ownership.register_directory(first)
    report["printed_authored"] = printed.printed_witness(adapter, first)
    report["pdf_fit"] = layout.pdf_field_fit(
        Path(report["printed_authored"]["pdf"]), report["after"]["notes"], plan
    )
    report["after_pdf"], pdf_handles, _ = layout.blank_snapshot(adapter)
    checkpoint()
    layout.require_same_handles(adapter.swApp, handles, pdf_handles)
    layout.require_equal(
        report["after"], report["after_pdf"], "authoring PDF observation"
    )
    report["save"] = {}
    with adapter.ownership.saving_as(derived):
        defaults.save_prepared_template(adapter.currentModel, derived, report["save"])
    report["saved"], saved_handles, _ = layout.blank_snapshot(adapter)
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
    report["reinstantiated"], readback_handles, readback_lines = layout.blank_snapshot(
        adapter
    )
    checkpoint()
    layout.require_equal(
        report["saved"], report["reinstantiated"], "bare saved-template inheritance"
    )
    report["inherited_phase_scope"] = layout.blank_phase_scope(
        report["reinstantiated"]["notes"]
    )
    cold_plan = layout.blank_label_plan(
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
    report["reinstantiated_after_pdf"], final_handles, _ = layout.blank_snapshot(
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


async def probe(adapter, output_root):
    expected = {
        str(common.PROJECT_DRWDOT): pilot.attachments.file_digest(common.PROJECT_DRWDOT)
    }
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="baked-template-", dir=output_root))
    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(common.PROJECT_DRWDOT)
    path = directory / "template-layout.json"
    report = {
        "status": "running",
        "scope": "blank-only four-note DRWDOT layout; resolved source-linked fit/full recipes pending",
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
        await transform(adapter, directory, report, checkpoint)
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
            lambda adapter: probe(adapter, args.report_root.resolve())
        )
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--report-root",
            str(args.report_root.resolve()),
            "--worker",
        ],
        "baked project template layout",
        com=True,
        log_stem="baked-template-layout",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
