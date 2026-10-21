"""Temporary issue-1667 template A/B probe; NEVER merge into production.

Observers only read COM properties/returned notes. The only image is a desktop
pixel grab after native creation and the unchanged production ownership proof.
No drawing save/export is permitted: both complete and incomplete runs STOP.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import time
from typing import Any, Callable, NoReturn, Sequence

from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
import _drawing_balloons as balloons
import _seat_forensics
import _telemetry


def _read(probe: Callable[[], Any]) -> Any:
    try:
        return probe()
    except Exception as exc:  # noqa: BLE001 - unreadable evidence must be explicit
        return {"error": f"{type(exc).__name__}: {exc}"}


def observe_options(adapter: Any, options: Any, selected_name: str) -> dict[str, Any]:
    """Read actual options, including untouched edit-mode defaults; never set them."""
    started = time.perf_counter()
    fields = (
        "Layout", "ReverseDirection", "IgnoreMultiple", "InsertMagneticLine",
        "LeaderAttachmentToFaces", "Style", "Size", "UpperTextContent",
        "ItemNumberStart", "ItemNumberIncrement", "ItemOrder",
        "EditBalloons", "EditBalloonOption",
    )
    report = {name: _read(lambda name=name: getattr(options, name)) for name in fields}
    report["selected_view_name"] = selected_name
    report["selection_count"] = _read(
        lambda: adapter.currentModel.SelectionManager.GetSelectedObjectCount2(-1)
    )
    report["selected_object_view_name"] = _read(
        lambda: view_name(
            adapter, adapter.currentModel.SelectionManager.GetSelectedObject6(1, -1)
        )
    )
    report["observer_ms"] = (time.perf_counter() - started) * 1000.0
    return report


def observe_notes(adapter: Any, notes: Any) -> dict[str, Any]:
    """Snapshot the SAME native return array before/after the existing rebuild."""
    started = time.perf_counter()
    report: dict[str, Any] = {"raw_type": type(notes).__name__, "notes": []}
    if notes is None:
        returned = []
    elif isinstance(notes, str):
        report.update(
            raw_text=notes, count=None, observer_ms=(time.perf_counter() - started) * 1000.0
        )
        return report
    else:
        returned = _read(lambda: list(notes))
        if isinstance(returned, dict):
            report.update(
                count=returned, observer_ms=(time.perf_counter() - started) * 1000.0
            )
            return report
    report["count"] = len(returned)
    for index, raw_note in enumerate(returned):
        row: dict[str, Any] = {"index": index, "raw_type": type(raw_note).__name__}
        report["notes"].append(row)
        try:
            note = _early_bound(raw_note, "INote")
            row["name"] = _read(lambda: note.GetName())
            row["item"] = _read(lambda: note.GetBomBalloonText(True))
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            row["attachment_types"] = _read(
                lambda: list(annotation.GetAttachedEntityTypes() or ())
            )
            entities = tuple(annotation.GetAttachedEntities3() or ())
            row["attachment_count"] = len(entities)
            row["full_owners"] = [
                _read(lambda entity=entity: balloons._entity_owner(adapter, entity))
                for entity in entities
            ]
        except Exception as exc:  # noqa: BLE001 - preserve every returned note
            row["error"] = f"{type(exc).__name__}: {exc}"
    report["readable_item_count"] = sum(
        isinstance(row.get("item"), str) for row in report["notes"]
    )
    report["observer_ms"] = (time.perf_counter() - started) * 1000.0
    return report


def stop_after_template_probe(
    adapter: Any, view: Any, *, items: Sequence[tuple[str, str]], label: str,
    template: Path,
) -> NoReturn:
    """Run the exact production helper once, retain evidence, then intentionally fail."""
    out_dir = _seat_forensics._capture_dir("1667-template-balloon-probe")
    report: dict[str, Any] = {
        "diagnostic_only": True, "intentional_stop_before_save_export": True,
        "label": label, "expected_items": list(items),
        "template_path": str(template.resolve()),
        "post_rebuild_count_source": "same AutoBalloon5 return array, not a view traversal",
    }
    failure = None
    try:
        report["template_sha256"] = hashlib.sha256(template.read_bytes()).hexdigest()
        started = time.perf_counter()
        try:
            landings = balloons.add_auto_balloons(
                adapter, view, items=items, label=label, _diagnostic=report
            )
            report.update(proof="passed", proven_count=len(landings))
        finally:
            elapsed = (time.perf_counter() - started) * 1000.0
            observers = sum(
                report.get(phase, {}).get("observer_ms", 0.0)
                for phase in ("before_native", "pre_rebuild", "post_rebuild")
            )
            report.update(
                helper_including_observers_ms=elapsed,
                reporting_inside_helper_ms=observers,
                helper_excluding_measured_observers_ms=elapsed - observers,
            )
    except Exception as exc:  # noqa: BLE001 - coverage failure must still write evidence
        failure = exc
        report.update(proof="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        started = time.perf_counter()
        report["artifacts"] = _seat_forensics._write_artefacts(
            (("desktop_png", lambda: _seat_forensics._grab_screen(out_dir / "desktop.png")),)
        )
        report["post_proof_capture_ms"] = (time.perf_counter() - started) * 1000.0
        written = _seat_forensics._write_failure_report(out_dir, report)
        _telemetry.info(f"Intentional template probe STOP before save/export: {written['report']}")
    raise RuntimeError(
        f"INTENTIONAL TEMPLATE PROBE STOP before save/export; proof={report['proof']}; "
        f"report={out_dir / 'capture.json'}"
    ) from failure
