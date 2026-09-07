"""One selected native dimension-arrangement control on retained lever copies.

Requires an explicitly granted seat and existing expected PID. The only drawing
layout operation is AlignDimensions once on Drawing View1: the original all-
dimension AutoArrange, or explicit SpaceEvenly on the five radial/diameter items.
Closed-document reference replacement targets an owned bytecopy and an identical
native-ID part bytecopy. No native drawing/part save, rebuild, retry, or global
preference write. PDF-only output is diagnostic even when clearance fails.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from enum import StrEnum
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
from _drawing_annotation_bounds import annotation_box  # noqa: E402
from _drawing_common import render_pdf_png  # noqa: E402
from _drawing_leader_clearance import crossing_records, validate_gtol_leader_clearance  # noqa: E402
from diagnostics import probe_datum_policy_recipes as pilot  # noqa: E402
from diagnostics import probe_retained_drawing_export as retained  # noqa: E402
from diagnostics._owned_native_documents import run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import null_callout  # noqa: E402

RECEIPT_SHA = "bd281f36661a6d52001c6104806df241e31df834e3529c65eb59eeedd399e119"
ARTIFACT_SHA = {
    "drawing": "a90c8e4b467071556169f028081cec8042803888d26cf4f5bb507a6b5f1f0d71",
    "pdf": "c917b8840ab016ed5198377da8397ed1c849f0c77ae610a9d76db99d3ee9f1f6",
    "png": "81aa6dc996cdcd33a79a5d2a6e371db4931ed2069ccf63901c857055b2829fad",
}
VIEW = "Sheet1/Drawing View1"
KNOWN_PAIRS = {("FulcrumDia", "NoseRadius"), ("RD5", "DetailItem349")}
RADIAL_TYPES = {
    "NoseRadius": 5,
    "TipRadius": 5,
    "FulcrumDia": 6,
    "RD4": 6,
    "RD5": 6,
}


class Arrangement(StrEnum):
    AUTO_ARRANGE = "auto_arrange"
    RADIAL_SPACE_EVENLY = "radial_space_evenly"


def selected_types(expected, arrangement):
    """Select from the captured semantic bank, never from text or coordinates."""
    if not isinstance(arrangement, Arrangement):
        raise ValueError("native arrangement requires its explicit policy enum")
    if not expected or any(
        not name or type(kind) is not int or kind not in range(1, 17)
        for name, kind in expected.items()
    ):
        raise ValueError("native arrangement needs known nonempty dimension types")
    if arrangement is Arrangement.AUTO_ARRANGE:
        if len(expected) < 2:
            raise ValueError("AutoArrange requires at least two captured dimensions")
        return dict(expected)
    radial = {name: kind for name, kind in expected.items() if kind in (5, 6)}
    if radial != RADIAL_TYPES:
        raise ValueError(
            f"radial spacing requires the five reviewed native dimension types: {radial}"
        )
    return radial


def read_inputs(receipt):
    if pilot.attachments.file_digest(receipt) != RECEIPT_SHA:
        raise RuntimeError("dimension control requires the reviewed exact receipt")
    result = json.loads(receipt.read_text(encoding="utf-8"))
    if len(result["trials"]) != 1 or result["trials"][0]["target"] != "channel_lever":
        raise RuntimeError("dimension control requires only the reviewed lever trial")
    trial = result["trials"][0]
    paths = {
        kind: Path(path).resolve(strict=True)
        for kind, path in trial["artifacts"].items()
    }
    if paths.keys() != ARTIFACT_SHA.keys():
        raise RuntimeError("retained artifact inventory changed")
    part = Path(trial["copy_source"]).resolve(strict=True)
    expected = {
        **result["sources_before"],
        str(receipt): RECEIPT_SHA,
        str(part): trial["copy_hashes"]["copied"],
    }
    expected.update({str(path): ARTIFACT_SHA[kind] for kind, path in paths.items()})
    retained.require_hashes(expected, "reviewed retained inputs")
    return trial, paths, part, expected


def copied_archive(trial, part):
    """Remap ONLY the verified model owner path/basename for an exact bytecopy."""
    result = deepcopy(trial["reopened"])
    previous = Path(trial["copy_source"])
    for row in result["semantics"]["models"].values():
        if Path(row["path"]).resolve() != previous.resolve():
            raise RuntimeError(
                "archived view does not reference the exact retained part"
            )
        row["path"] = str(part)
    old, new = f"@{previous.stem}.Part", f"@{part.stem}.Part"
    for row in result["semantics"]["dimensions"].values():
        if row["kind"] != "model_dimension":
            continue
        for component in row["components"]:
            name = component["qualified_name"]
            if not name.endswith(old):
                raise RuntimeError(
                    "archived model dimension has a different source owner"
                )
            component["qualified_name"] = name[: -len(old)] + new
    return result


def copied_source_witness(trial, part):
    expected = deepcopy(trial["source_before"])
    old = f"@{Path(trial['copy_source']).stem}.Part"
    new = f"@{part.stem}.Part"
    for row in expected["dimensions"].values():
        if not row["full_name"].endswith(old):
            raise RuntimeError("archived source parameter has an unrelated owner")
        row["full_name"] = row["full_name"][: -len(old)] + new
    return expected


def relink_closed_copy(adapter, drawing, previous, part):
    adapter.ownership.inventory()
    if (
        drawing.parent not in adapter.ownership.directories
        or part.parent not in adapter.ownership.directories
    ):
        raise RuntimeError("reference replacement requires registered owned copies")
    if (
        not drawing.is_file()
        or not part.is_file()
        or drawing.suffix.lower() != ".slddrw"
        or part.suffix.lower() != ".sldprt"
    ):
        raise RuntimeError("closed reference replacement files/types are invalid")
    if adapter.swApp.GetOpenDocumentByName(str(drawing)) is not None:
        raise RuntimeError("referencing drawing copy must be closed before relink")
    if pilot.attachments.file_digest(previous) != pilot.attachments.file_digest(part):
        raise RuntimeError("replacement part must be an exact native-ID bytecopy")
    # Official ISldWorks.ReplaceReferencedDocument: closed referencing document,
    # existing same-type renamed source copy. Native open validates every view.
    if not adapter.swApp.ReplaceReferencedDocument(
        str(drawing), str(previous), str(part)
    ):
        raise RuntimeError("closed owned drawing reference replacement rejected")
    adapter.ownership.inventory()


def measure_views(adapter, views):
    result = {}
    for key, view in views.items():
        rows = {}
        for raw in view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            visible = int(annotation.Visible)
            if visible == 3:
                continue  # swAnnotationHidden; complete inventory still witnessed
            name = str(annotation.GetName())
            if (
                visible != 1
                or not name
                or name in rows
                or int(annotation.OwnerType) != 0
                or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
            ):
                raise RuntimeError(
                    "clearance requires exact visible view-owned annotations"
                )
            # This symbol-aware reader must succeed: generic archived exclusions
            # are not a fallback and no nominal bodies are substituted.
            rows[name] = annotation_box(adapter, annotation)
        result[key] = rows
    return result


def dimension_crossings(measurements):
    result = {}
    for key, rows in measurements.items():
        dimensions = {name: row for name, row in rows.items() if row.kind == 4}
        # Center marks are geometry adornments, not text/frame obstacles. Their
        # identity and complete strokes are still captured. Do not exempt any
        # other dimension or datum. Type-14 intentional joins are NOT assumed.
        targets = {
            name: SimpleNamespace(
                kind=row.kind,
                text_boxes=(row.body,),
                text_runs=row.text_runs,
                body=row.body,
            )
            for name, row in rows.items()
            if row.kind in (2, 4, 5, 6, 7)
        }
        result[key] = crossing_records(
            {
                name: (*row.native_strokes, *row.native_leader_segments)
                for name, row in dimensions.items()
            },
            targets,
            {name: row.leader_decorations for name, row in dimensions.items()},
        )
    return result


def require_positive_baseline(crossings):
    pairs = {
        (row["leader_annotation"], row["target_annotation"])
        for row in crossings.get(VIEW, ())
        if row["segments"]
    }
    if not KNOWN_PAIRS <= pairs:
        raise RuntimeError(
            "both exact retained dimension/frame crossings must reproduce before arrangement"
        )


def require_clearance(crossings, arrangement):
    """Selection scope never narrows the original all-view clearance gate."""
    if any(crossings.values()):
        raise RuntimeError(
            f"native {arrangement.value} leaves dimension stroke/other-body crossings; see measured report"
        )


def arrange_once(
    adapter, view, expected, handles, *, arrangement=Arrangement.AUTO_ARRANGE
):
    planned = selected_types(expected, arrangement)
    if expected.keys() != handles.keys():
        raise ValueError("captured dimension types and exact handle inventory differ")
    model = adapter.currentModel
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    drawing = _early_bound(model, "IDrawingDoc")
    bank = {}
    seen = set()
    model.ClearSelection2(True)
    try:
        if not drawing.ActivateView(str(view.GetName2())):
            raise RuntimeError("cannot activate exact dimension view")
        for raw in view.GetAnnotationsByType(4) or ():
            annotation = _early_bound(raw, "IAnnotation")
            name = str(annotation.GetName())
            if (
                name not in expected
                or name in seen
                or int(annotation.Visible) != 1
                or int(annotation.OwnerType) != 0
                or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
            ):
                raise RuntimeError("native dimension bank identity/view mismatch")
            if int(adapter.swApp.IsSame(annotation, handles[name])) != 1:
                raise RuntimeError(
                    "measured dimension annotation was replaced before selection"
                )
            display = _early_bound(
                annotation.GetSpecificAnnotation(), "IDisplayDimension"
            )
            native_type = display.Type2
            if type(native_type) is not int or native_type != expected[name]:
                raise RuntimeError(f"captured native dimension type changed: {name}")
            seen.add(name)
            if name not in planned:
                continue
            selection_name = str(display.GetNameForSelection() or "")
            if not selection_name or not extension.SelectByID2(
                selection_name, "DIMENSION", 0.0, 0.0, 0.0, True, 0, null_callout(), 0
            ):
                raise RuntimeError("native named dimension selection rejected")
            bank[name] = display
            if (
                int(selection.GetSelectedObjectCount2(-1)) != len(bank)
                or int(
                    adapter.swApp.IsSame(
                        selection.GetSelectedObject6(len(bank), -1), display
                    )
                )
                != 1
            ):
                raise RuntimeError("selected object is not the exact IDisplayDimension")
        if seen != expected.keys() or bank.keys() != planned.keys() or len(bank) < 2:
            raise RuntimeError(
                "selected dimension inventory differs from measured bank"
            )
        started = time.perf_counter()
        # Bundled IModelDocExtension.AlignDimensions + swAlignDimensionType_e:
        # AutoArrange=0, SpaceEvenly=1. The native palette supports radial
        # spacing; Stagger is a linear-dimension tool, not a diameter fallback.
        code, alignment = (
            (0, "AutoArrange")
            if arrangement is Arrangement.AUTO_ARRANGE
            else (1, "SpaceEvenly")
        )
        if not extension.AlignDimensions(code, 0.001):
            raise RuntimeError(f"one native per-view {alignment} rejected")
        return {
            "selected": tuple(bank),
            "dimension_types": planned,
            "arrangement": arrangement.value,
            "seconds": time.perf_counter() - started,
            "alignment": alignment,
            "alignment_value": code,
            "spacing_m": 0.001,
        }
    finally:
        model.ClearSelection2(True)


def compare_arranged(adapter, before, after, before_handles, after_handles, selected):
    pilot.attachments.compare(
        before["semantics"], after["semantics"], "one native dimension arrangement"
    )
    pilot.attachments.check_layout(
        before["layout"], after["layout"], "one native dimension arrangement"
    )
    changes = pilot.shoulder.compare_all_annotation_layout(
        adapter.swApp,
        before["annotations"],
        after["annotations"],
        before_handles,
        after_handles,
    )
    if set(changes) - selected:
        raise RuntimeError(
            f"native dimension arrangement moved an unselected annotation: {sorted(set(changes) - selected)}"
        )
    return changes


def compare_measured(before, after, movable=()):
    if before.keys() != after.keys():
        raise RuntimeError("native measured view inventory changed")
    for view, rows in before.items():
        if rows.keys() != after[view].keys():
            raise RuntimeError("native measured annotation inventory changed")
        for name, old in rows.items():
            new = after[view][name]
            if (view, name) not in movable:
                if asdict(old) != asdict(new):
                    raise RuntimeError(
                        f"{view}/{name}: fixed measured annotation changed"
                    )
                continue

            # Position/leader changes are intended only for the selected bank;
            # native text, font, orientation, type and format must stay exact.
            def text_signature(row):
                return [
                    {
                        key: value
                        for key, value in asdict(run).items()
                        if key != "position"
                    }
                    for run in row.text_runs
                ]

            if (old.name, old.kind, old.format_signature, text_signature(old)) != (
                new.name,
                new.kind,
                new.format_signature,
                text_signature(new),
            ):
                raise RuntimeError(f"{view}/{name}: arranged text/format changed")


async def probe(adapter, receipt, output_root, *, arrangement=Arrangement.AUTO_ARRANGE):
    if not isinstance(arrangement, Arrangement):
        raise ValueError("native arrangement requires its explicit policy enum")
    trial, paths, previous, expected = read_inputs(receipt)
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="dimension-arrange-", dir=output_root))
    adapter.ownership.register_directory(directory)
    for path in expected:
        adapter.ownership.register_source(Path(path))
    part = directory / f"{directory.name}-part.SLDPRT"
    drawing = directory / f"{directory.name}.SLDDRW"
    report_path = directory / "dimension-arrange.json"
    report = {
        "status": "running",
        "receipt": str(receipt),
        "inputs_before": expected,
        "helper_revision": pilot.benchmark.revision("HEAD"),
        "helper_fingerprints": pilot.helper_fingerprints(),
        "imported_adapter": pilot.adapter_fingerprints(),
        "view": VIEW,
        "arrangement": arrangement.value,
        "scope": "one selected native per-view arrangement; no native save/rebuild or automatic next candidate",
    }
    copy_expected = {}
    errors = []

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    checkpoint()
    try:
        shutil.copy2(previous, part)
        shutil.copy2(paths["drawing"], drawing)
        copy_expected = {
            str(part): expected[str(previous)],
            str(drawing): expected[str(paths["drawing"])],
        }
        retained.require_hashes(
            {
                str(part): expected[str(previous)],
                str(drawing): expected[str(paths["drawing"])],
            },
            "initial owned bytecopies",
        )
        relink_closed_copy(adapter, drawing, previous, part)
        # Only the closed drawing reference bytes may change. Never establish
        # a new source-copy baseline from an unexpected native metadata save.
        copy_expected[str(drawing)] = pilot.attachments.file_digest(drawing)
        retained.require_hashes(copy_expected, "after closed relink")
        report["copy_hashes_after_closed_relink"] = dict(copy_expected)
        retained.require_hashes(expected, "after owned closed relink")
        check("open owned relinked drawing", await adapter.open_model(str(drawing)))
        configuration = trial["source_before"]["configuration"]
        report["before"], before_handles = retained.capture_drawing(
            adapter, part, configuration
        )
        report["archive_delta"] = retained.compare_archived_drawing(
            copied_archive(trial, part), report["before"]
        )
        if (
            report["before"]["semantics"]["dimensions_excluded"]
            or report["before"]["semantics"]["semantic_attachments"]
        ):
            raise RuntimeError(
                "control requires complete dimensions and no unclassified intentional datum/dimension joins"
            )
        source = adapter.swApp.GetOpenDocumentByName(str(part))
        report["source_before"], source_handles = pilot.source_dimensions(
            source, "channel_lever", part
        )
        pilot.require_same_source(
            copied_source_witness(trial, part),
            report["source_before"],
            "retained source bytecopy versus archived original parameters",
        )
        views = pilot.attachments.views(adapter.currentModel)
        if VIEW not in views:
            raise RuntimeError("reviewed front view is missing")
        before = measure_views(adapter, views)
        report["before_measured"] = {
            key: {name: asdict(row) for name, row in rows.items()}
            for key, rows in before.items()
        }
        report["before_crossings"] = dimension_crossings(before)
        require_positive_baseline(report["before_crossings"])
        report["before_gtol_clearance"] = validate_gtol_leader_clearance(before)
        checkpoint()
        names = {name for name, row in before[VIEW].items() if row.kind == 4}
        types = {
            name: report["before"]["semantics"]["dimensions"][f"{VIEW}/{name}/4"][
                "display_type"
            ]
            for name in names
        }
        report["native_arrange"] = arrange_once(
            adapter,
            views[VIEW],
            types,
            {name: before_handles[f"Drawing View1/{name}"][0] for name in names},
            arrangement=arrangement,
        )
        report["after"], after_handles = retained.capture_drawing(
            adapter, part, configuration
        )
        selected_names = report["native_arrange"]["selected"]
        selected = {f"Drawing View1/{name}" for name in selected_names}
        report["moved_dimensions"] = compare_arranged(
            adapter,
            report["before"],
            report["after"],
            before_handles,
            after_handles,
            selected,
        )
        after = measure_views(adapter, views)
        compare_measured(before, after, {(VIEW, name) for name in selected_names})
        report["after_measured"] = {
            key: {name: asdict(row) for name, row in rows.items()}
            for key, rows in after.items()
        }
        report["after_crossings"] = dimension_crossings(after)
        report["source_after"], source_after_handles = pilot.source_dimensions(
            source, "channel_lever", part
        )
        pilot.require_same_source(
            report["source_before"],
            report["source_after"],
            "native arrangement",
            app=adapter.swApp,
            handles_before=source_handles,
            handles_after=source_after_handles,
        )
        retained.require_hashes(expected, "after native arrangement originals")
        retained.require_hashes(copy_expected, "after native arrangement copies")
        checkpoint()
        # Export a diagnostic image even when geometric clearance remains false;
        # it is not a saved/accepted native drawing and does not bypass any gate.
        pdf, png = directory / "after.pdf", directory / "after.png"
        retained.export_pdf_only(adapter, pdf)
        render_pdf_png(pdf, png)
        report["artifacts"] = {"pdf": str(pdf), "png": str(png)}
        report["after_export"], exported_handles = retained.capture_drawing(
            adapter, part, configuration
        )
        changes = compare_arranged(
            adapter,
            report["after"],
            report["after_export"],
            after_handles,
            exported_handles,
            set(),
        )
        if changes:
            raise RuntimeError("PDF export altered native annotation geometry")
        report["source_after_export"], exported_source_handles = (
            pilot.source_dimensions(source, "channel_lever", part)
        )
        pilot.require_same_source(
            report["source_after"],
            report["source_after_export"],
            "PDF export",
            app=adapter.swApp,
            handles_before=source_after_handles,
            handles_after=exported_source_handles,
        )
        exported_measurements = measure_views(adapter, views)
        compare_measured(after, exported_measurements)
        report["after_export_measured"] = {
            key: {name: asdict(row) for name, row in rows.items()}
            for key, rows in exported_measurements.items()
        }
        report["after_gtol_clearance"] = validate_gtol_leader_clearance(
            exported_measurements
        )
        require_clearance(report["after_crossings"], arrangement)
        report["status"] = "clear_under_measured_gate"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        errors.append(error)
    finally:
        try:
            await adapter.close_owned_documents()
        except Exception as error:
            report["cleanup_error"] = repr(error)
            errors.append(error)
        # Every final guard runs even after a native or cleanup failure. Preserve
        # the primary error first; never replace it with the last cleanup fault.
        for field, readback, initial in (
            ("inputs_after", lambda: retained.final_hashes(expected), expected),
            (
                "copies_after",
                lambda: retained.final_hashes(copy_expected),
                copy_expected,
            ),
            (
                "helper_fingerprints_after",
                pilot.helper_fingerprints,
                report["helper_fingerprints"],
            ),
            (
                "imported_adapter_after",
                pilot.adapter_fingerprints,
                report["imported_adapter"],
            ),
        ):
            try:
                actual = readback()
                report[field] = actual
                if actual != initial:
                    raise RuntimeError(f"final {field} witness changed")
            except Exception as error:
                report.setdefault("final_guard_errors", {})[field] = repr(error)
                errors.append(error)
        if errors:
            report.update(status="failed", errors=[repr(error) for error in errors])
        try:
            checkpoint()
        except Exception as error:
            errors.append(error)
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise ExceptionGroup(
            "dimension control failed with cleanup/final witnesses", errors
        )
    return {"report": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument(
        "--arrangement",
        choices=tuple(item.value for item in Arrangement),
        default=Arrangement.AUTO_ARRANGE.value,
        help="one explicit native operation; never an automatic candidate sequence",
    )
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args(argv)
    arrangement = Arrangement(args.arrangement)
    require_owned_diagnostic_environment()
    if (
        os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off"
        or int(os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID", "0")) <= 0
    ):
        raise RuntimeError("diagnostic requires cache off and an explicit existing PID")
    receipt = args.receipt.resolve(strict=True)
    read_inputs(receipt)
    if not args.worker:
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--receipt",
                str(receipt),
                "--report-root",
                str(args.report_root.resolve()),
                "--arrangement",
                arrangement.value,
                "--worker",
            ],
            "one per-view native dimension arrangement",
            com=True,
            log_stem="dimension-arrangement",
        )
        return 0
    return run_copy_diagnostic(
        lambda adapter: probe(
            adapter, receipt, args.report_root.resolve(), arrangement=arrangement
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
