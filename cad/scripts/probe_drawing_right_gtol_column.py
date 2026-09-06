"""Copy-only RIGHT native GTol-column control, without a custom leader router.

Run through uv with DRAWING (optionally --view NAME). The largest unique native
GTol bank is used unless explicitly named. Translate its complete measured body
bank to the first clear RIGHT outboard position, keeping native Y/order/leaders.
Compare actual native leader segments AND conservative native decoration boxes
against text cells; these are potential ink-cell overlaps, not exact glyph-ink
intersections. Decorations include all-around circles and native arrow symbols.
If RIGHT still crosses text, try at most two absolute vertical candidates (UP,
then DOWN), derived from the crossed cells and native elbow stations. Reuse text
cells only for candidate screening; remeasure all native bodies/text at the final
witness before exporting the first clear candidate. No leader segment is edited.
Record both PNGs and final saved/reopened geometry, frame and dimension witnesses.
The original drawing and referenced native parts must remain byte-unchanged.

Requires the integrated _drawing_native_gtol and diagnostics attachment helper.
No production recipe/helper is patched and nothing is published by this probe.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Any

from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_annotation_bounds import (
    Segment,
    annotation_box,
    annotation_leader_geometry,
)
from _drawing_common import render_pdf_png
from _drawing_view_packing import Rect
from _drawing_leader_clearance import (
    _clear,
    crossing_records,
    displayed_leader_coverage,
    vertical_candidates,
    _candidate_text_cells,
)
import _telemetry


def right_translation(
    column: Rect, outline: Rect, obstacles: tuple[Rect, ...], gap_m=0.003
):
    if not math.isfinite(gap_m) or gap_m < 0:
        raise ValueError("column clearance must be finite and nonnegative")
    dx = max(0.0, outline.xmax + gap_m - column.xmin)
    for _ in range(len(obstacles) + 1):
        moved = column.translated((dx, 0.0))
        collision = next(
            (item for item in obstacles if not _clear(moved, item, gap_m)), None
        )
        if collision is None:
            return dx, 0.0
        dx = collision.xmax + gap_m - column.xmin
    raise RuntimeError("bounded right-column candidate did not clear obstacles")


def prove_narrow_reader(bank, measurements):
    """Read-only live parity against the freshly completed full measurements."""
    started = time.perf_counter()
    geometry = {
        name: annotation_leader_geometry(row.annotation) for name, row in bank.items()
    }
    elapsed = time.perf_counter() - started
    coverage = {}
    for name, actual in geometry.items():
        expected = measurements[name]
        if (
            actual.segments != expected.native_leader_segments
            or actual.decorations != expected.leader_decorations
        ):
            raise RuntimeError(
                f"{name}: narrow/full RAW native leader geometry differs: actual={actual}, expected_native={expected.native_leader_segments}, expected_decorations={expected.leader_decorations}"
            )
        coverage[name] = displayed_leader_coverage(actual, expected.leader_segments)
    if any(row["uncovered_display_indices"] for row in coverage.values()):
        raise RuntimeError(
            f"native reader does not cover every displayed open leader: {json.dumps(coverage)}"
        )
    return {
        "count": len(bank),
        "elapsed_s": elapsed,
        "native_geometry": "exactly_equal_to_full_snapshot",
        "display_coverage": coverage,
    }


def _candidate_trials(
    right_seed,
    measured,
    leaders,
    decorations,
    crossings,
    outline,
    obstacles,
    *,
    move_bank,
    read_leaders,
    read_decorations,
    attempts,
    gap_m=0.003,
):
    """Screen at most two absolute candidates; caller MUST run fresh final witness."""
    if attempts:
        raise ValueError("candidate attempt log must start empty")
    last = right_seed
    for candidate in vertical_candidates(crossings, leaders, decorations):
        delta = (0.0, candidate.dy_m)
        attempt = {
            "direction": candidate.direction.value,
            "absolute_delta_from_right_m": delta,
            "status": "started",
        }
        attempts.append(attempt)
        # Pass the same immutable right seed every time, never the previous trial.
        last = move_bank(
            right_seed,
            {name: delta for name in right_seed},
            f"diagnostic right column {candidate.direction.value}",
        )
        actual_leaders = read_leaders(last)
        actual_decorations = read_decorations(last)
        actual_crossings = crossing_records(
            actual_leaders,
            _candidate_text_cells(measured, right_seed, last),
            actual_decorations,
        )
        body_clear = all(
            _clear(row.body, obstacle, gap_m)
            for row in last.values()
            for obstacle in (outline, *obstacles)
        )
        attempt.update(
            {
                "direction": candidate.direction.value,
                "absolute_delta_from_right_m": delta,
                "body_clearance": "clear" if body_clear else "blocked",
                "crossings": actual_crossings,
                "native_leaders": {
                    name: [asdict(segment) for segment in rows]
                    for name, rows in actual_leaders.items()
                },
                "native_leader_decorations": {
                    name: [box.bounds for box in boxes]
                    for name, boxes in actual_decorations.items()
                },
                "predicted_positions": {
                    name: row.position for name, row in last.items()
                },
                "predicted_bodies": {
                    name: row.body.bounds for name, row in last.items()
                },
                "body_text_basis": "derived_from_measured_right_seed_and_actual_native_position",
                "status": "screened",
            }
        )
        if body_clear and not actual_crossings:
            return candidate.direction, last, attempts
    return None, last, attempts


def _leaders(annotation):
    segments = []
    for index in range(int(annotation.GetLeaderCount())):
        raw = tuple(
            float(value) for value in annotation.GetLeaderPointsAtIndex(index) or ()
        )
        if len(raw) not in (6, 9) or not all(math.isfinite(value) for value in raw):
            raise RuntimeError(
                "native GTol leader is not a finite two/three-point chain"
            )
        points = tuple((raw[i], raw[i + 1]) for i in range(0, len(raw), 3))
        segments.extend(
            Segment(first, second) for first, second in zip(points, points[1:])
        )
    return tuple(segments)


def _native_entities(adapter, view):
    result = {}
    for raw in view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        kind = int(annotation.GetType())
        if kind not in {2, 4, 5, 7}:
            continue
        entities = tuple(annotation.GetAttachedEntities3() or ())
        kinds = tuple(int(item) for item in annotation.GetAttachedEntityTypes() or ())
        if len(entities) != len(kinds) or len(entities) != int(
            annotation.GetAttachedEntityCount3()
        ):
            raise RuntimeError("native annotation attachment inventory is incomplete")
        if (
            any(item is None for item in entities)
            or 0 in kinds
            or annotation.IsDangling()
        ):
            raise RuntimeError(
                "selected lever view has unsupported/null native attachment slots"
            )
        result[str(annotation.GetName())] = annotation, kind, entities, kinds
    return result


def _same_native(app, before, after):
    if before.keys() != after.keys():
        raise RuntimeError("native manufacturing annotation inventory changed")
    for name, (annotation, kind, entities, types) in before.items():
        actual, actual_kind, actual_entities, actual_types = after[name]
        if (
            kind != actual_kind
            or types != actual_types
            or len(entities) != len(actual_entities)
            or int(app.IsSame(annotation, actual)) != 1
            or any(
                int(app.IsSame(a, b)) != 1 for a, b in zip(entities, actual_entities)
            )
        ):
            raise RuntimeError(f"{name}: native annotation/entity identity changed")


def _records(bank):
    return {
        name: {
            "position": row.position,
            "body": row.body.bounds,
            "frames": row.frames,
            "text": row.text,
            "format": row.text_format,
            "attachment_types": row.entity_types,
        }
        for name, row in bank.items()
    }


def _same_saved_frames(before, after):
    if before.keys() != after.keys():
        raise RuntimeError("saved/reopened GTol inventory changed")
    for name, original in before.items():
        actual = after[name]
        for field in ("frames", "text", "format", "attachment_types"):
            if original[field] != actual[field]:
                raise RuntimeError(f"{name}: saved/reopened GTol {field} changed")
        for field in ("position", "body"):
            if len(original[field]) != len(actual[field]) or any(
                abs(a - b) > 1e-8 for a, b in zip(original[field], actual[field])
            ):
                raise RuntimeError(f"{name}: saved/reopened GTol {field} moved")


def _measure_view(adapter, view):
    measured = {}
    for raw in view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.OwnerType) == 2 or int(annotation.Visible) == 3:
            continue
        bounds = annotation_box(adapter, annotation)
        if bounds.name in measured:
            raise RuntimeError("native view annotation names are not unique")
        measured[bounds.name] = bounds
    return measured


async def probe(adapter: Any, source: Path, requested_view: str | None):
    import _drawing_native_gtol as gtol
    from diagnostics.probe_drawing_attachments import snapshot, compare
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    reports = CAD_ROOT / "out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(
        tempfile.mkdtemp(prefix="gtol-right-column-", dir=reports)
    ).resolve()
    copy = directory / f"{directory.name}-source.SLDDRW"
    shutil.copy2(source, copy)
    owned = {copy}
    hashes = {source: hashlib.sha256(source.read_bytes()).hexdigest()}
    report = {"source": str(source), "copy": str(copy), "phases": {}}

    def export(stage):
        path = directory / f"{directory.name}-{stage}.SLDDRW"
        owned.add(path)
        outputs = save_drawing(
            adapter, str(path), pdf_path=str(path.with_suffix(".pdf"))
        )
        if not path.with_suffix(".pdf").is_file():
            raise RuntimeError(f"right-column diagnostic PDF missing: {outputs}")
        render_pdf_png(path.with_suffix(".pdf"), path.with_suffix(".png"))
        report.setdefault("exports", {})[stage] = {
            "drawing": str(path),
            "pdf": str(path.with_suffix(".pdf")),
            "png": str(path.with_suffix(".png")),
        }
        return path

    try:
        check(
            "open unique right-column drawing copy", await adapter.open_model(str(copy))
        )
        if Path(adapter.currentModel.GetPathName()).resolve() != copy:
            raise RuntimeError("SolidWorks opened the wrong right-column copy")
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        views = [
            _early_bound(raw, "IView")
            for sheet in drawing.GetViews() or ()
            for raw in sheet[1:]
        ]
        for view in views:
            path = Path(view.ReferencedDocument.GetPathName()).resolve(strict=True)
            if path.suffix.upper() != ".SLDPRT":
                raise ValueError(
                    "right-column control supports native part drawings only"
                )
            hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        candidates = [(view, len(view.GetAnnotationsByType(5) or ())) for view in views]
        if requested_view is not None:
            matches = [
                view
                for view, count in candidates
                if str(view.GetName2()) == requested_view and count
            ]
        else:
            largest = max((count for _view, count in candidates), default=0)
            matches = [view for view, count in candidates if count == largest and count]
        if len(matches) != 1:
            raise ValueError(
                "name an exact view or require one uniquely largest nonempty GTol bank"
            )
        view = matches[0]
        report["view"] = str(view.GetName2())
        report["view_inventory"] = {
            str(item.GetName2()): count for item, count in candidates
        }
        if not drawing.ActivateView(str(view.GetName2())):
            raise RuntimeError("right-column owning view activation failed")
        export("before")
        before = gtol._read_gtols(adapter, view, annotation_box)
        if any(int(row.annotation.GetLeaderStyle()) != 2 for row in before.values()):
            raise RuntimeError(
                "right-column control requires existing native bent GTol leaders"
            )
        native_before = _native_entities(adapter, view)
        semantics_before = snapshot(adapter.currentModel, app=adapter.swApp)
        measured_before = _measure_view(adapter, view)
        leaders_before = {
            name: _leaders(row.annotation) for name, row in before.items()
        }
        decorations_before = {
            name: measured_before[name].leader_decorations for name in before
        }
        report["phases"]["before"] = {
            "narrow_reader": prove_narrow_reader(before, measured_before),
            "bank": _records(before),
            "leaders": {
                name: [asdict(segment) for segment in rows]
                for name, rows in leaders_before.items()
            },
            "leader_decorations": {
                name: [box.bounds for box in boxes]
                for name, boxes in decorations_before.items()
            },
            "crossings": crossing_records(
                leaders_before, measured_before, decorations_before
            ),
            "semantics": semantics_before,
        }
        outline = Rect(*view.GetOutline())
        column = gtol._union([row.body for row in before.values()])
        obstacles = tuple(
            bounds.body
            for name, bounds in measured_before.items()
            if name not in before and bounds.kind in {2, 4, 7}
        )
        delta = right_translation(column, outline, obstacles)
        report["placement"] = {
            "column": column.bounds,
            "outline": outline.bounds,
            "obstacles": [item.bounds for item in obstacles],
            "translation_m": delta,
        }
        predicted = gtol._move_bank(
            before,
            {name: delta for name in before},
            "diagnostic alternative right column",
        )
        after = gtol._read_gtols(adapter, view, annotation_box)
        if any(int(row.annotation.GetLeaderStyle()) != 2 for row in after.values()):
            raise RuntimeError(
                "alternative column changed native bent GTol leader style"
            )
        gtol._unchanged(adapter.swApp, before, after, "alternative right column")
        gtol._assert_measured_prediction(predicted, after)
        _same_native(adapter.swApp, native_before, _native_entities(adapter, view))
        semantics_after = snapshot(adapter.currentModel, app=adapter.swApp)
        compare(semantics_before, semantics_after, "alternative right column")
        measured_after = _measure_view(adapter, view)
        leaders_after = {name: _leaders(row.annotation) for name, row in after.items()}
        decorations_after = {
            name: measured_after[name].leader_decorations for name in after
        }
        report["phases"]["after"] = {
            "narrow_reader": prove_narrow_reader(after, measured_after),
            "bank": _records(after),
            "leaders": {
                name: [asdict(segment) for segment in rows]
                for name, rows in leaders_after.items()
            },
            "leader_decorations": {
                name: [box.bounds for box in boxes]
                for name, boxes in decorations_after.items()
            },
            "crossings": crossing_records(
                leaders_after, measured_after, decorations_after
            ),
            "semantics": semantics_after,
        }
        saved = export("right")
        saved_bank = after
        right_crossings = report["phases"]["after"]["crossings"]
        if right_crossings:
            report["vertical_attempts"] = []
            direction, trial, attempts = _candidate_trials(
                after,
                measured_after,
                leaders_after,
                decorations_after,
                right_crossings,
                outline,
                obstacles,
                move_bank=gtol._move_bank,
                read_leaders=lambda bank: {
                    name: _leaders(row.annotation) for name, row in bank.items()
                },
                read_decorations=lambda bank: {
                    name: annotation_box(adapter, row.annotation).leader_decorations
                    for name, row in bank.items()
                },
                attempts=report["vertical_attempts"],
            )
            report["vertical_attempts"] = attempts
            final_bank = gtol._read_gtols(adapter, view, annotation_box)
            if any(
                int(row.annotation.GetLeaderStyle()) != 2 for row in final_bank.values()
            ):
                raise RuntimeError(
                    "vertical candidate changed native bent GTol leader style"
                )
            gtol._unchanged(
                adapter.swApp, before, final_bank, "right-column vertical final witness"
            )
            gtol._assert_measured_prediction(trial, final_bank)
            _same_native(adapter.swApp, native_before, _native_entities(adapter, view))
            final_semantics = snapshot(adapter.currentModel, app=adapter.swApp)
            compare(
                semantics_before, final_semantics, "right-column vertical final witness"
            )
            final_measured = _measure_view(adapter, view)
            final_leaders = {
                name: _leaders(row.annotation) for name, row in final_bank.items()
            }
            final_decorations = {
                name: final_measured[name].leader_decorations for name in final_bank
            }
            final_crossings = crossing_records(
                final_leaders, final_measured, final_decorations
            )
            final_obstacles = tuple(
                bounds.body
                for name, bounds in final_measured.items()
                if name not in final_bank and bounds.kind in {2, 4, 7}
            )
            final_outline = Rect(*view.GetOutline())
            body_clear = all(
                _clear(row.body, obstacle, 0.003)
                for row in final_bank.values()
                for obstacle in (final_outline, *final_obstacles)
            )
            report["phases"]["vertical_final"] = {
                "narrow_reader": prove_narrow_reader(final_bank, final_measured),
                "bank": _records(final_bank),
                "crossings": final_crossings,
                "leader_decorations": {
                    name: [box.bounds for box in boxes]
                    for name, boxes in final_decorations.items()
                },
                "semantics": final_semantics,
                "body_clearance": "clear" if body_clear else "blocked",
                "selected_direction": direction.value
                if direction is not None
                else None,
            }
            if direction is not None:
                if final_crossings or not body_clear:
                    raise RuntimeError(
                        "fresh final native measurement rejected the screened column candidate"
                    )
                saved = export(f"clear-{direction.value}")
                saved_bank = final_bank
                report["vertical_outcome"] = "fresh_native_witness_clear"
            if direction is None:
                report["vertical_outcome"] = "no_clear_candidate_within_two_trial_bound"
        if not right_crossings:
            report["vertical_attempts"] = []
            report["vertical_outcome"] = "right_column_already_clear"
        check(
            "close right-column copy for persistence witness",
            await adapter.close_model(save=False),
        )
        check("reopen right-column saved copy", await adapter.open_model(str(saved)))
        if Path(adapter.currentModel.GetPathName()).resolve() != saved:
            raise RuntimeError("reopened right-column document path differs")
        reopened = snapshot(adapter.currentModel, app=adapter.swApp)
        compare(semantics_before, reopened, "saved/reopened alternative right column")
        report["reopened_semantics"] = reopened
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        reopened_views = [
            _early_bound(raw, "IView")
            for sheet in drawing.GetViews() or ()
            for raw in sheet[1:]
        ]
        matches = [
            item for item in reopened_views if str(item.GetName2()) == report["view"]
        ]
        if len(matches) != 1:
            raise RuntimeError("saved/reopened right-column view identity changed")
        reopened_bank = gtol._read_gtols(adapter, matches[0], annotation_box)
        _same_saved_frames(_records(saved_bank), _records(reopened_bank))
        report["reopened_bank"] = _records(reopened_bank)
        reopened_measured = _measure_view(adapter, matches[0])
        report["reopened_narrow_reader"] = prove_narrow_reader(
            reopened_bank, reopened_measured
        )
        reopened_crossings = crossing_records(
            {name: _leaders(row.annotation) for name, row in reopened_bank.items()},
            reopened_measured,
            {
                name: reopened_measured[name].leader_decorations
                for name in reopened_bank
            },
        )
        report["reopened_crossings"] = reopened_crossings
        if (
            report["vertical_outcome"]
            in {"fresh_native_witness_clear", "right_column_already_clear"}
            and reopened_crossings
        ):
            raise RuntimeError(
                "saved/reopened native leader geometry crosses a text cell"
            )
        report["outcome"] = "captured_alternative_not_production_layout"
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        try:
            if (
                adapter.currentModel is not None
                and Path(adapter.currentModel.GetPathName()).resolve() in owned
            ):
                check(
                    "close owned right-column diagnostic copy",
                    await adapter.close_model(save=False),
                )
            report["source_unchanged"] = {
                str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest
                for path, digest in hashes.items()
            }
            if not all(report["source_unchanged"].values()):
                raise RuntimeError(
                    "right-column diagnostic changed original source bytes"
                )
        finally:
            (directory / "column.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            _telemetry.info(f"right-column diagnostic observations: {directory}")
    return {"report": str(directory / "column.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--view")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if source.suffix.upper() != ".SLDDRW":
        raise ValueError("right-column probe needs a native drawing")
    if not args.worker:
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo

        command = [sys.executable, str(Path(__file__).resolve()), str(source)]
        if args.view:
            command += ["--view", args.view]
        dodo._run(
            [*command, "--worker"],
            "native alternative right GTol column",
            log_stem="gtol-right-column",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")
    _telemetry.set_service("drawing-right-gtol-column-probe")
    return run_build(lambda adapter: probe(adapter, source, args.view))


if __name__ == "__main__":
    raise SystemExit(main())
