"""Temporary issue-1667 visible-edge weight ABBA probe; NEVER merge into production.

Only the document visible-edge line-font slot is changed. Observers read COM
properties/returned notes. The only image is a desktop pixel grab after native
creation and the unchanged production ownership proof. No save/export is permitted.
"""

from __future__ import annotations

from pathlib import Path
import math
import sys
import time
from typing import Any, Callable, NoReturn, Sequence

from solidworks_mcp.adapters.solidworks.drawing import view_name
from solidworks_mcp.adapters.sw_type_info import constant

from _com import _early_bound
import _drawing_balloons as balloons
import _seat_forensics
import _telemetry


class TemplateProbeStop(RuntimeError):
    """Only the expected diagnostic outcome; native/recipe errors stay fatal."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        super().__init__(
            "INTENTIONAL VISIBLE-EDGE WEIGHT PROBE STOP before save/export; "
            f"proof={report['proof']}; report={report['report_path']}"
        )


def apply_visible_edge_weight(
    model: Any, *, slot: str, report: dict[str, Any]
) -> None:
    """Set only visible-edge slot selection; read, never write, its widths."""
    started = time.perf_counter()
    weight: dict[str, Any] = {
        "preference": "swLineFontVisibleEdgesThickness",
        "option": "swDetailingNoOptionSpecified",
        "requested_slot_name": slot,
    }
    report["visible_edge_weight"] = weight
    try:
        extension = _early_bound(model.Extension, "IModelDocExtension")
        preference = constant("swLineFontVisibleEdgesThickness")
        option = constant("swDetailingNoOptionSpecified")
        slots = {name: constant(f"swLW_{name}") for name in ("NORMAL", "THICK")}
        thickness_preferences = {
            "NORMAL": constant("swPageSetupPrinterNormalLineWeight"),
            "THICK": constant("swPageSetupPrinterThickLineWeight"),
        }
        expected_m = {"NORMAL": 0.00018, "THICK": 0.00035}[slot]
        weight.update(requested_slot=slots[slot], expected_thickness_m=expected_m)

        def readback() -> dict[str, Any]:
            read_started = time.perf_counter()
            actual_slot = int(extension.GetUserPreferenceInteger(preference, option))
            thickness_m = {
                name: float(extension.GetUserPreferenceDouble(pref, option))
                for name, pref in thickness_preferences.items()
            }
            slot_name = next(
                (name for name, value in slots.items() if value == actual_slot), None
            )
            return {
                "slot": actual_slot,
                "slot_name": slot_name,
                "thickness_m": thickness_m,
                "slot_thickness_m": thickness_m.get(slot_name),
                "readback_ms": (time.perf_counter() - read_started) * 1000.0,
            }

        weight["before"] = readback()
        setter_started = time.perf_counter()
        try:
            result = extension.SetUserPreferenceInteger(preference, option, slots[slot])
            weight["setter_return"] = result
        finally:
            weight["setter_ms"] = (time.perf_counter() - setter_started) * 1000.0
        weight["after"] = readback()
        if result is not True:
            raise RuntimeError("failed to set document visible-edge weight slot")
        after = weight["after"]
        if after["slot"] != slots[slot]:
            raise RuntimeError("document visible-edge weight slot readback differs")
        if after["thickness_m"] != weight["before"]["thickness_m"]:
            raise RuntimeError("document Normal/Thick slot widths changed")
        if not math.isclose(after["slot_thickness_m"], expected_m, abs_tol=1e-10):
            raise RuntimeError("document visible-edge slot thickness readback differs")
    finally:
        weight["elapsed_ms"] = (time.perf_counter() - started) * 1000.0


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
    template: Path, out_dir: Path, report: dict[str, Any],
) -> NoReturn:
    """Retain the exact production proof, then STOP on complete/incomplete coverage."""
    report.update(
        diagnostic_only=True, intentional_stop_before_save_export=True,
        label=label, expected_items=list(items), proof="unexpected_error",
        template_path=str(template.resolve()),
        report_path=str(out_dir / "capture.json"),
        post_rebuild_count_source="same AutoBalloon5 return array, not a view traversal",
    )
    try:
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
    except TemplateProbeStop:
        # Only the helper's explicit missing-items boundary may continue ABBA.
        pass
    finally:
        failure = sys.exception()
        if failure is not None:
            report.update(
                proof="unexpected_error", error=f"{type(failure).__name__}: {failure}"
            )
        started = time.perf_counter()
        report["artifacts"] = _seat_forensics._write_artefacts(
            (("desktop_png", lambda: _seat_forensics._grab_screen(out_dir / "desktop.png")),)
        )
        report["post_proof_capture_ms"] = (time.perf_counter() - started) * 1000.0
        written = _seat_forensics._write_failure_report(out_dir, report)
        _telemetry.info(f"Visible-edge weight probe retained before save/export: {written['report']}")
    raise TemplateProbeStop(report)
