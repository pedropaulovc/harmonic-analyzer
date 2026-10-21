"""TEMPORARY issue1667 AutoBalloon5 experiment; DIAGNOSTIC ONLY, NEVER MERGE.

One existing auto-balloon helper call, native association reads, then existing
spread/rebuild and repeat reads. No manual picks, frozen landings, save or retry.
Only the two PNGs and compact checkpoint report are produced before deliberate STOP.
"""

from __future__ import annotations

from collections import Counter
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Mapping, Sequence
from uuid import uuid4

from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _com_invoke, _early_bound
from _drawing_balloon_display import rendered_balloon_circle
import _drawing_balloons as balloons
from _drawing_common import rebuild_drawing
import _drawing_leaders as leaders
from _drawing_sm_pose_diagnostic import _VisibilityDeadline

STOP = "ISSUE1667_AUTO_BALLOON_STOP"
FAILURES = Path(__file__).resolve().parents[1] / "out" / "reports" / "failures"
# v3.12.1 swSelectType_e; GetAttachedEntities3 documents these as IEntity geometry.
_KINDS = {1: "EDGE", 2: "FACE", 3: "VERTEX"}


def _error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _capture_png(path: Path) -> None:
    from PIL import ImageGrab

    ImageGrab.grab(all_screens=True).save(path)


def _layout(notes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Focused balloon-only check from measured native leaders and circle boxes."""
    groups = {}
    boxes = {}
    for row in notes:
        name = str(row["index"])
        if "body_box_m" in row:
            boxes[name] = row["body_box_m"]
        groups[name] = []
        for flat in row.get("leader_points_m", ()):
            points = [(flat[i], flat[i + 1]) for i in range(0, len(flat), 3)]
            groups[name].extend(zip(points, points[1:]))
    crossings = leaders.leader_crossings(groups)
    hits = [
        [name, other]
        for name, segments in groups.items()
        for other, box in boxes.items()
        if name != other
        and any(leaders.distance_to_box(segment, box) == 0.0 for segment in segments)
    ]
    overlaps = [
        [first, second]
        for first, a in boxes.items()
        for second, b in boxes.items()
        if int(first) < int(second)
        and min(a[2], b[2]) > max(a[0], b[0])
        and min(a[3], b[3]) > max(a[1], b[1])
    ]
    return {
        "scope": "returned balloon leaders and circle-body boxes only; not whole-sheet approval",
        "leader_crossings": crossings,
        "leader_body_hits": hits,
        "body_overlaps": overlaps,
        "clear": not (crossings or hits or overlaps),
    }


def _snapshot(
    adapter: Any,
    notes: Sequence[Any],
    expected: Mapping[str, set[str]],
    *,
    label: str,
) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    rows: list[dict[str, Any]] = []
    handles: list[tuple[Any, ...]] = []
    counts: Counter[str] = Counter()
    items: Counter[str] = Counter()
    for index, raw_note in enumerate(notes, 1):
        row: dict[str, Any] = {"index": index, "qualified": False, "attachments": []}
        rows.append(row)
        handles.append(())
        try:
            note = _early_bound(raw_note, "INote")
            row["item"] = balloons._balloon_item_number(adapter, note, label=label)
            items[row["item"]] += 1
            counts["INote.GetAnnotation"] += 1
            annotation = note.GetAnnotation()
            if annotation is None:
                raise RuntimeError("returned balloon has no annotation")
            annotation = _early_bound(annotation, "IAnnotation")

            def read(member: str, *args: Any) -> Any:
                counts[f"IAnnotation.{member}"] += 1
                return getattr(annotation, member)(*args)

            entities = tuple(read("GetAttachedEntities3") or ())
            kinds = tuple(int(v) for v in (read("GetAttachedEntityTypes") or ()))
            row["attached_types"] = kinds
            handles[-1] = entities
            problems = []
            if not entities or len(entities) != len(kinds):
                problems.append("empty or mismatched native attachment arrays")
            allowed = expected.get(row["item"], set())
            if not allowed:
                problems.append("unexpected native BOM item")
            for position, kind in enumerate(kinds):
                attached = {
                    "type": kind,
                    "kind": _KINDS.get(kind, "UNKNOWN"),
                    "owner_status": "unknown",
                }
                row["attachments"].append(attached)
                entity = entities[position] if position < len(entities) else None
                try:
                    if kind not in _KINDS or entity is None:
                        raise RuntimeError(
                            "unsupported or dangling attachment; real native probe required"
                        )
                    owner = balloons._entity_owner(adapter, entity)
                    if not owner:
                        raise RuntimeError(
                            "IEntity.GetComponent/Name2 ownership unreadable; real native probe required"
                        )
                    attached.update(owner_full_path=owner, owner_status="read")
                    if owner.casefold() not in allowed:
                        raise RuntimeError(
                            "attached full component path is not a shown instance of this BOM row"
                        )
                except Exception as exc:
                    attached["error"] = _error(exc)
                    problems.append(attached["error"])
            leader_count = int(read("GetLeaderCount"))
            row["leader_points_m"] = []
            if not 0 < leader_count <= 8:
                raise RuntimeError(
                    f"unreadable or excessive leader count {leader_count}"
                )
            for leader in range(leader_count):
                flat = tuple(
                    float(v) for v in (read("GetLeaderPointsAtIndex", leader) or ())
                )
                if (
                    len(flat) < 6
                    or len(flat) % 3
                    or not all(math.isfinite(v) for v in flat)
                ):
                    raise RuntimeError("invalid native leader points")
                row["leader_points_m"].append(flat)
            x, y, radius = rendered_balloon_circle(note, label=label)
            row["body_box_m"] = (x - radius, y - radius, x + radius, y + radius)
            row["qualified"] = not problems
            if problems:
                row["error"] = "; ".join(problems)
        except Exception as exc:
            row["error"] = _error(exc)
    coverage = {
        "missing": sorted(set(expected) - items.keys()),
        "unexpected": sorted(items.keys() - set(expected)),
        "duplicates": {item: count for item, count in items.items() if count > 1},
    }
    return {
        "notes": rows,
        "coverage": coverage,
        "qualified": bool(rows)
        and all(row["qualified"] for row in rows)
        and not coverage["missing"]
        and not coverage["unexpected"],
        "getter_calls": dict(counts),
        "getter_count_scope": "explicit collector getters only; helper, ownership and rendered-circle internals excluded",
        "layout": _layout(rows),
    }, handles


def collect_and_stop(
    adapter: Any,
    view: Any,
    *,
    items: Sequence[tuple[str, str]],
    anchors: Mapping[str, balloons.BalloonAnchor],
    label: str,
    margin: float = 0.014,
) -> None:
    """Collect one view once and always refuse drawing publication."""
    out_dir = FAILURES / f"ab1667-{uuid4().hex[:8]}"
    path = out_dir / "p.json"
    started = time.perf_counter()
    report: dict[str, Any] = {
        "experiment": "existing native auto balloons, then existing spread",
        "stop": STOP,
        "status": "begun",
        "label": label,
        "requested_rows": list(items),
        "expected_rows": [],
        "guard_seconds": 120,
        "timings_ms": {},
        "display_operations": [],
        "captures": {},
        "execution": {
            key: os.environ[key]
            for key in (
                "HARMONIC_FARM_BUILD_ID",
                "HARMONIC_FARM_RUN",
                "HARMONIC_FARM_COMMIT",
                "HARMONIC_WORKER_ID",
                "FARM_LEAF_WORKFLOW_ID",
                "TRACEPARENT",
            )
            if os.environ.get(key)
        },
        "interpretation": "Creation times the WHOLE existing helper: view selection, options, AutoBalloon5, rebuild and item reads; NOT raw API latency. Duplicates recorded, not rejected. No manual XY baseline, frozen landing, save, cache healing or retry. Native success unproven until this runs on the farm.",
    }

    def checkpoint(stage: str) -> None:
        report["checkpoint"] = stage
        temporary = out_dir / "p.tmp"
        temporary.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)

    def capture(stage: str) -> None:
        before = time.perf_counter()
        operation = {
            "stage": stage,
            "api": "IModelDoc2.ViewZoomtofit2 + GraphicsRedraw2",
            "status": "attempted",
        }
        report["display_operations"].append(operation)
        draw = adapter.currentModel
        try:
            draw.ClearSelection2(True)
            draw.ViewZoomtofit2()  # Same sheet fit used by existing _drawing_scan.
            draw.GraphicsRedraw2()
            operation["status"] = "completed"
        finally:
            report["timings_ms"][f"display_{stage}"] = (
                time.perf_counter() - before
            ) * 1000
        before = time.perf_counter()
        try:
            target = out_dir / f"{stage}.png"
            _capture_png(target)
            report["captures"][stage] = str(target)
        finally:
            report["timings_ms"][f"capture_{stage}"] = (
                time.perf_counter() - before
            ) * 1000

    error: Exception | None = None
    try:
        out_dir.mkdir(parents=True, exist_ok=False)
        if len(str(path.absolute()).encode("utf-16-le")) // 2 > 230:
            raise RuntimeError("short diagnostic report exceeds Windows path budget")
        checkpoint("begin")  # Persist before guard and the first added native call.
        with _VisibilityDeadline(120.0):
            try:
                report["view_name"] = view_name(adapter, view)
                if (
                    not items
                    or len({stem for stem, _ in items}) != len(items)
                    or len({item for _, item in items}) != len(items)
                ):
                    raise RuntimeError("expected BOM rows must be nonempty and unique")
                leaves = balloons._view_component_leaves(adapter, view, label=label)
                expected = {}
                for stem, item in items:
                    if stem not in anchors:
                        raise RuntimeError(
                            f"no existing balloon family mapping for {stem}"
                        )
                    # Only family membership matters: no frozen point or pinned instance.
                    shown = balloons._shown_instances(
                        leaves, stem, balloons.BalloonAnchor(), label=label
                    )
                    paths = [leaf.path for leaf in shown]
                    report["expected_rows"].append(
                        {"stem": stem, "item": item, "shown_instances": paths}
                    )
                    expected[item] = {name.casefold() for name in paths}
                checkpoint("prepared")
                before = time.perf_counter()
                try:
                    notes = balloons._create_auto_balloons(adapter, view, label=label)
                finally:
                    report["timings_ms"]["create_helper"] = (
                        time.perf_counter() - before
                    ) * 1000
                before = time.perf_counter()
                report["as_generated"], original = _snapshot(
                    adapter, notes, expected, label=label
                )
                report["timings_ms"]["proof_as_generated"] = (
                    time.perf_counter() - before
                ) * 1000
                checkpoint(
                    "as_generated"
                )  # Association evidence survives even a capture failure.
                capture("as-generated")
                checkpoint("as_generated")  # PNG + report both durable BEFORE spread.
                if not report["as_generated"]["qualified"]:
                    raise RuntimeError(
                        "as-generated native BOM coverage/ownership/leader proof refused"
                    )
                before = time.perf_counter()
                try:
                    balloons._spread_balloons(adapter, view, notes, margin=margin)
                    rebuild_drawing(adapter, label="issue1667 auto-balloon spread")
                finally:
                    report["timings_ms"]["spread_rebuild"] = (
                        time.perf_counter() - before
                    ) * 1000
                before = time.perf_counter()
                report["after_spread"], current = _snapshot(
                    adapter, notes, expected, label=label
                )
                checks = []
                report["attachment_identity_after_spread"] = checks
                for index, (old, new) in enumerate(zip(original, current), 1):
                    check = {"index": index, "IsSame": [], "unchanged": False}
                    checks.append(check)
                    a = report["as_generated"]["notes"][index - 1]
                    b = report["after_spread"]["notes"][index - 1]
                    if b["qualified"] and all(
                        a[key] == b[key]
                        for key in ("item", "attached_types", "attachments")
                    ):
                        check["IsSame"] = [
                            int(
                                _com_invoke(
                                    adapter.swApp, "ISldWorks", "IsSame", first, second
                                )
                            )
                            for first, second in zip(old, new)
                        ]
                        check["unchanged"] = (
                            bool(old)
                            and len(old) == len(new)
                            and all(value == 1 for value in check["IsSame"])
                        )
                report["timings_ms"]["proof_after_spread"] = (
                    time.perf_counter() - before
                ) * 1000
                checkpoint("spread")
                capture("spread")
                if not report["after_spread"]["qualified"] or not all(
                    check["unchanged"] for check in checks
                ):
                    raise RuntimeError(
                        "post-spread native coverage/ownership/attachment proof refused"
                    )
                if not report["after_spread"]["layout"]["clear"]:
                    raise RuntimeError(
                        "post-spread focused balloon-only layout check found collisions"
                    )
                report["status"] = "completed"
            except Exception as exc:
                error = exc
                report.update(status="refused", error=_error(exc))
            finally:
                report["elapsed_ms"] = (time.perf_counter() - started) * 1000
                checkpoint("final")
    except Exception as exc:
        error = exc
        report.update(status="refused", error=_error(exc))
    raise RuntimeError(
        f"{STOP} status={report['status']} report={path}; document remains unsaved"
    ) from error
