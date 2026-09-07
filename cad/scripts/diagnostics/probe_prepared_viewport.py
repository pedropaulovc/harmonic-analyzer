"""Owned, unsaved blank Scale2 A/B/A; no template/content saves or source parts.

The retained failed receipt is input provenance, not permission to publish its
template. Strict A/A defaults and export stability remain gates. A/B extent
differences are observations; PDF glyph/path/pixel verdicts are independent.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from enum import StrEnum
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound  # noqa: E402
from _drawing_template_defaults import compare_defaults, snapshot_defaults  # noqa: E402
import _drawing_template_viewport as viewports  # noqa: E402
from diagnostics import _owned_native_documents as owned  # noqa: E402
from diagnostics import _populated_template_symbols as symbols  # noqa: E402
from diagnostics import probe_prepared_template_cache as base  # noqa: E402


class Arm(StrEnum):
    INITIAL = "a_initial"
    ZOOM = "b_zoom"
    RESTORED = "a_restored"


class Comparison(StrEnum):
    EXACT = "exact"
    OBSERVATION = "observation"


class Translation(StrEnum):
    NATIVE = "native"
    ORIGINAL = "original"


def read_inputs(receipt_path, receipt_sha, template_path, template_sha):
    paths = {
        "receipt": Path(receipt_path).resolve(strict=True),
        "template": Path(template_path).resolve(strict=True),
    }
    for label, sha in (("receipt", receipt_sha), ("template", template_sha)):
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("inputs require explicit lowercase SHA-256 values")
        if base.prepared._sha(paths[label]) != sha:
            raise RuntimeError(f"pinned {label} SHA-256 differs")
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    if (
        paths["template"].suffix.lower() != ".drwdot"
        or Path(receipt["saved_path"]).resolve() != paths["template"]
    ):
        raise RuntimeError("retained receipt does not name this exact DRWDOT")
    spec = receipt["inputs"]["spec"]
    base.prepared.TemplateSpec(tuple(spec["scale"]), spec["decimals"])
    return {
        "receipt": {"path": str(paths["receipt"]), "sha256": receipt_sha},
        "template": {"path": str(paths["template"]), "sha256": template_sha},
        "spec": spec,
        "retained_status": receipt["status"],
    }


def runtime_inputs(adapter, spec):
    from _buildgraph import module_deps_of

    # The production graph follows sibling modules, not this diagnostics package.
    # Pin its complete Python bytes conservatively, including this entrypoint.
    sources = {*Path(__file__).parent.glob("*.py"), *module_deps_of(Path(__file__))}
    return {
        "prepared": base.runtime_inputs(adapter, spec),
        "diagnostic_closure": {
            Path(path).relative_to(ROOT).as_posix(): base.prepared._sha(path)
            for path in sources
        },
    }


viewport = viewports.capture


def identity_bank(adapter):
    adapter.ownership.assert_current_owned()
    base.blank_witness(adapter)
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet_view = _early_bound(drawing.GetViews()[0][0], "IView")
    bank = {}
    for raw in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        key = (str(annotation.GetName()), int(annotation.GetType()))
        if key in bank:
            raise RuntimeError("ambiguous native blank annotation identity")
        bank[key] = annotation
    if not bank:
        raise RuntimeError("blank positive control has no native annotations")
    return sheet_view, bank


def same_bank(adapter, before):
    after = identity_bank(adapter)
    if (
        int(adapter.swApp.IsSame(before[0], after[0])) != 1
        or before[1].keys() != after[1].keys()
        or any(
            int(adapter.swApp.IsSame(value, after[1][key])) != 1
            for key, value in before[1].items()
        )
    ):
        raise RuntimeError("native blank annotation/view identity changed")


def semantic_defaults(snapshot):
    """Experiment-only field alignment; the production comparator stays exact.

    Exclude raw GetExtent and its two derived rectangles only. Retain every
    captured text/style/anchor/display field and require unique matching keys.
    """
    result = deepcopy(snapshot)
    result.pop("blank_linked_extent_observations", None)
    rows = {}
    for row in result["sheet_notes"]:
        row.pop("extent", None)
        ink = row.get("measured", row.get("zero_ink", {}))
        key = (row["text"], row["linked_text"], tuple(ink.get("anchor", ())))
        if key in rows:
            raise RuntimeError("ambiguous note field alignment")
        if "measured" in row:
            ink.pop("body", None)
            ink.pop("envelope", None)
        rows[key] = row
    result["sheet_notes"] = [rows[key] for key in sorted(rows)]
    return result


def printed_snapshot(adapter, directory):
    """Reuse PDF-only export; separately retain exact supported flat path data."""
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    result = base.printed_witness(adapter, directory)
    result["paths"] = []
    result["objects"] = []
    try:
        with pdfium.PdfDocument(result["pdf"]) as document:
            page = document[0]
            try:
                result["full_page_raster"] = full_page_raster(page)
            except Exception as error:
                result["full_page_raster_error"] = repr(error)
            for obj in page.get_objects(max_depth=1):
                geometry = {
                    "type": obj.type,
                    "level": obj.level,
                    "matrix": list(obj.get_matrix().get()),
                    "bounds_pt": list(obj.get_bounds()),
                }
                result["objects"].append(geometry)
                if not all(
                    math.isfinite(x) for x in geometry["matrix"] + geometry["bounds_pt"]
                ):
                    raise RuntimeError("nonfinite PDF object geometry")
                if (
                    obj.type in (raw.FPDF_PAGEOBJ_TEXT, raw.FPDF_PAGEOBJ_IMAGE)
                    and obj.level == 0
                ):
                    continue  # Exact full-sheet pixels cover rendered image appearance.
                if obj.type != raw.FPDF_PAGEOBJ_PATH:
                    raise RuntimeError(
                        f"unsupported PDF object kind/level: {obj.type}/{obj.level}"
                    )
                result["paths"].append(symbols.path_snapshot(obj))
        if not result["paths"]:
            raise RuntimeError("positive PDF path control has no native vector paths")
        result["vector_status"] = "supported_paths_and_object_inventory_captured"
    except Exception as error:
        # The exact glyph/pixel evidence remains useful if vector decoding fails.
        result.update(vector_status="failed", vector_error=repr(error))
    result["vector_scope"] = (
        "exact supported flat paths plus complete object kind/matrix/bounds inventory; image appearance requires the independent full-sheet pixel/glyph verdict; no raw image/paint or whole-vector equivalence claim"
    )
    return result


def full_page_raster(page):
    """The production preview may crop one bottom row; hash uncropped pixels too."""
    bitmap = page.render(scale=base.common.ASME_B_DPI / 72.0)
    try:
        image = bitmap.to_pil()
        return {
            "size": list(image.size),
            "mode": image.mode,
            "pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        }
    finally:
        bitmap.close()


def compare_appearance(before, after):
    delta = base.compare_printed(before, after)
    if (
        "full_page_raster" not in before
        or "full_page_raster" not in after
        or before["full_page_raster"] != after["full_page_raster"]
    ):
        raise RuntimeError("uncropped whole-page PDF raster differs or is unavailable")
    return delta


def compare_vectors(before, after):
    if (
        before["vector_status"] != "supported_paths_and_object_inventory_captured"
        or after["vector_status"] != "supported_paths_and_object_inventory_captured"
        or before["paths"] != after["paths"]
        or before["objects"] != after["objects"]
    ):
        raise RuntimeError("exact PDF vector geometry/inventory differs")


def equal(before, after):
    if before != after:
        raise RuntimeError("exact captured fields differ")


async def probe(
    adapter, pins, report_root, expected_pid, *, translation=Translation.NATIVE
):
    if not isinstance(translation, Translation):
        raise ValueError("viewport translation requires an explicit policy enum")
    base.require_environment(expected_pid)
    if int(adapter.swApp.GetProcessID()) != expected_pid:
        raise RuntimeError("running native PID differs")
    spec = base.prepared.TemplateSpec(
        tuple(pins["spec"]["scale"]), pins["spec"]["decimals"]
    )
    report_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="prepared-viewport-", dir=report_root))
    adapter.ownership.register_directory(directory)
    for label in ("receipt", "template"):
        adapter.ownership.register_source(Path(pins[label]["path"]))
    frozen = runtime_inputs(adapter, spec)
    report = {
        "status": "running",
        "scope": "one owned blank, viewport-only Scale2 A/B/A",
        "translation": translation.value,
        "inputs": pins,
        "runtime_inputs": frozen,
        "expected_pid": expected_pid,
        "arms": [],
        "comparisons": {},
        "guards": [],
        "revision": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
    }
    errors = []
    report_path = directory / "measurements.json"

    def checkpoint():
        report_path.write_text(
            json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
        )

    def guard(phase):
        row = {"phase": phase, "status": "running"}
        report["guards"].append(row)
        try:
            row["sha256"] = {
                label: base.prepared._sha(pins[label]["path"])
                for label in ("receipt", "template")
            }
            row["runtime_inputs"] = runtime_inputs(adapter, spec)
            if (
                any(
                    row["sha256"][label] != pins[label]["sha256"]
                    for label in row["sha256"]
                )
                or row["runtime_inputs"] != frozen
            ):
                raise RuntimeError("pinned input/runtime bytes changed")
            adapter.ownership.inventory()
            row["status"] = "passed"
        except Exception as error:
            row.update(status="failed", error=repr(error))
            raise
        finally:
            checkpoint()

    def compare(label, check, before, after, *, mode=Comparison.EXACT):
        try:
            value = check(before, after)
            report["comparisons"][label] = {"status": "passed", "result": value}
        except Exception as error:
            report["comparisons"][label] = {
                "status": "different" if mode is Comparison.OBSERVATION else "failed",
                "error": repr(error),
            }
            if mode is Comparison.EXACT:
                errors.append(error)
        checkpoint()

    checkpoint()
    try:
        guard("before_create")
        with adapter.ownership.creating_document(
            owned.DocumentKind.DRAWING, directory / "unsaved.SLDDRW"
        ):
            model = base.common.new_drawing(
                adapter,
                template=pins["template"]["path"],
                width=base.common.ASME_B_WIDTH_M,
                height=base.common.ASME_B_HEIGHT_M,
            )
            _early_bound(model, "IDrawingDoc").EditSheet()
            model.ViewZoomtofit2()
        bank = identity_bank(adapter)
        report["native_annotation_inventory"] = [
            {"name": name, "kind": kind} for name, kind in bank[1]
        ]
        initial = viewport(model)
        report["initial_viewport"] = initial
        view = _early_bound(model.ActiveView, "IModelView")
        for arm in Arm:
            same_bank(adapter, bank)
            if int(adapter.swApp.IsSame(view, model.ActiveView)) != 1:
                raise RuntimeError("active native viewport replaced")
            # Absolute targets from the original scale; no accumulated zoom.
            target = initial["scale2"] * (2 if arm is Arm.ZOOM else 1)
            row = {"variant": arm.value, "target_scale2": target}
            report["arms"].append(row)
            view.Scale2 = target
            row["after_scale_viewport"] = viewport(model)
            if row["after_scale_viewport"]["orientation3"] != initial["orientation3"]:
                raise RuntimeError("native Scale2 changed the original orientation")
            if translation is Translation.ORIGINAL:
                row["translation_target"] = initial["translation3"]
                viewports.assign_translation(
                    adapter.swApp, view, initial["translation3"]
                )
            model.GraphicsRedraw2()  # Identical documented redraw in every arm.
            row["viewport"] = viewport(model)
            if row["viewport"]["orientation3"] != initial["orientation3"]:
                raise RuntimeError("native viewport orientation changed")
            if (
                translation is Translation.ORIGINAL
                and row["viewport"]["translation3"] != initial["translation3"]
            ):
                raise RuntimeError("native original Translation3 readback differs")
            if row["viewport"]["scale2"] != target:
                raise RuntimeError("native viewport scale assignment did not persist")
            row["defaults"] = snapshot_defaults(adapter, spec)
            same_bank(adapter, bank)
            checkpoint()
            arm_dir = directory / arm.value
            arm_dir.mkdir()
            adapter.ownership.register_directory(arm_dir)
            try:
                row["printed"] = printed_snapshot(adapter, arm_dir)
            except Exception as error:
                row["printed_error"] = repr(error)
                errors.append(error)
            same_bank(adapter, bank)
            row["native_identity_after_export"] = "exact_annotation_and_sheet_handles"
            row["after_print_defaults"] = snapshot_defaults(adapter, spec)
            row["after_print_viewport"] = viewport(model)
            compare(
                arm.value + "_export_defaults",
                compare_defaults,
                row["defaults"],
                row["after_print_defaults"],
            )
            compare(
                arm.value + "_export_viewport",
                equal,
                row["viewport"],
                row["after_print_viewport"],
            )
            guard(arm.value)
        first, middle, last = report["arms"]
        for label, other in (("a_b", middle), ("a_a", last)):
            compare(
                label + "_strict_defaults",
                compare_defaults,
                first["defaults"],
                other["defaults"],
                mode=Comparison.OBSERVATION if label == "a_b" else Comparison.EXACT,
            )
            compare(
                label + "_semantics",
                lambda a, b: equal(semantic_defaults(a), semantic_defaults(b)),
                first["defaults"],
                other["defaults"],
            )
            if "printed" in first and "printed" in other:
                compare(
                    label + "_printed",
                    compare_appearance,
                    first["printed"],
                    other["printed"],
                )
                compare(
                    label + "_supported_paths_and_inventory",
                    compare_vectors,
                    first["printed"],
                    other["printed"],
                )
        compare("a_a_viewport", equal, first["viewport"], last["viewport"])
    except Exception as error:
        report["error"] = repr(error)
        errors.append(error)
    finally:
        try:
            await adapter.close_owned_documents()
        except Exception as error:
            report["cleanup_error"] = repr(error)
            errors.append(error)
        try:
            guard("finally")
        except Exception as error:
            report["final_guard_error"] = repr(error)
            errors.append(error)
        report.update(
            status="failed" if errors else "passed", errors=[repr(e) for e in errors]
        )
        checkpoint()
    if errors:
        raise ExceptionGroup("prepared viewport control failed", errors)
    return {
        "measurements": str(report_path),
        "ownership": str(directory / "ownership.json"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--template-sha256", required=True)
    parser.add_argument("--expected-pid", type=int, required=True)
    parser.add_argument(
        "--translation",
        type=Translation,
        choices=tuple(Translation),
        default=Translation.NATIVE,
    )
    parser.add_argument(
        "--report-root", type=Path, default=ROOT / "cad/out/reports/prepared-viewport"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    base.require_environment(args.expected_pid)
    pins = read_inputs(
        args.receipt, args.receipt_sha256, args.template, args.template_sha256
    )
    if args.worker:
        return owned.run_copy_diagnostic(
            lambda adapter: probe(
                adapter,
                pins,
                args.report_root.resolve(),
                args.expected_pid,
                translation=args.translation,
            )
        )
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--receipt",
            pins["receipt"]["path"],
            "--receipt-sha256",
            pins["receipt"]["sha256"],
            "--template",
            pins["template"]["path"],
            "--template-sha256",
            pins["template"]["sha256"],
            "--expected-pid",
            str(args.expected_pid),
            "--translation",
            args.translation.value,
            "--report-root",
            str(args.report_root.resolve()),
            "--worker",
        ],
        "prepared viewport control",
        log_stem="prepared-viewport",
        com=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
