"""Issue-1667 FR/CH one-shot native compatibility diagnostic; NEVER MERGE.

Reuse the production EDGE/Square helper and its Normal guard unchanged. Observe
only at the helper boundary, retain passive pixels before post-helper COM reads,
and always fail before the recipe can save/export or publish a successful cache
entry. This is not a layout, caption, precision/export or SHIP acceptance gate.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping, NoReturn, Sequence

from _drawing_balloon_display import rendered_balloon_circle
import _drawing_balloons as balloons
from _drawing_group_perf_probe import _preference
from _drawing_sm_quality_probe import (
    _note_snapshot,
    _quality_state,
    _validate_snapshots,
    _view_inventory,
)
import _seat_forensics as forensics


class NativeCompatibilityProbeStop(RuntimeError):
    """Evidence retained; even compatible native owners cannot publish a drawing."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        super().__init__(
            "INTENTIONAL FR/CH NATIVE DIAGNOSTIC STOP before save/export/cache "
            f"publication; status={report['status']}; report={report['report_path']}"
        )


def _path(value: str) -> str:
    return value.replace("\\", "/").casefold()


def _compatibility_failures(
    items: Sequence[tuple[str, str]],
    required_instances: Mapping[str, str],
    landings: Sequence[balloons.BalloonLanding],
    returned_rows: Sequence[dict[str, Any]],
    inventory_rows: Sequence[dict[str, Any]],
    allowed_owners: Mapping[str, Sequence[str]],
) -> list[str]:
    """Compare full paths, never same-family or last-segment substitutes for pins."""
    expected = dict(items)
    failures = []
    if len(expected) != len(items) or len(set(expected.values())) != len(items):
        failures.append("duplicate expected BOM family/item")
    if set(required_instances) - set(expected):
        failures.append("required instance policy names a family outside the BOM")
    allowed = {
        stem: {_path(owner) for owner in owners}
        for stem, owners in allowed_owners.items()
    }
    for stem, pin in required_instances.items():
        if _path(pin) not in allowed.get(stem, set()):
            failures.append(f"required instance is not shown: {stem}={pin!r}")
        allowed[stem] = {_path(pin)}
    for name, rows in (
        ("returned", returned_rows),
        ("actual_view_inventory", inventory_rows),
    ):
        _valid, invalid = _validate_snapshots(
            rows, items=items, allowed=allowed, attachment="edge"
        )
        failures.extend(f"{name}: {message}" for message in invalid)
        for row in rows:
            stem = next((stem for stem, item in items if item == row["item"]), None)
            if stem in required_instances:
                pin = required_instances[stem]
                if [_path(owner) for owner in row["owners"]] != [_path(pin)]:
                    failures.append(
                        f"{name}: required instance mismatch for {stem}: "
                        f"expected={pin!r}, actual={row['owners']!r}"
                    )
    if len(landings) != len(items) or len(returned_rows) != len(landings):
        failures.append("returned landing count does not cover every native BOM row")
    seen = set()
    for landing, row in zip(landings, returned_rows):
        if (
            landing.stem in seen
            or row["item"] != expected.get(landing.stem)
            or len(row["owners"]) != 1
            or _path(row["owners"][0]) != _path(landing.instance)
            or landing.sheet_xy is not None
        ):
            failures.append(
                f"returned landing identity differs: {landing.stem}: {row!r}"
            )
        seen.add(landing.stem)
    returned_ids = {(row["note_name"], row["annotation_name"]) for row in returned_rows}
    inventory_ids = {
        (row["note_name"], row["annotation_name"]) for row in inventory_rows
    }
    if returned_ids != inventory_ids:
        failures.append("returned and actual view BOM-note identities differ")
    return failures


def _shown_owners(
    adapter: Any, view: Any, items: Sequence[tuple[str, str]], *, label: str
) -> dict[str, list[str]]:
    leaves = balloons._view_component_leaves(adapter, view, label=label)
    return {
        stem: sorted(
            leaf.path
            for leaf in balloons._shown_instances(
                leaves, stem, balloons.BalloonAnchor(), label=label
            )
        )
        for stem, _item in items
    }


def run_native_compatibility_probe(
    adapter: Any,
    view: Any,
    *,
    items: Sequence[tuple[str, str]],
    required_instances: Mapping[str, str],
    label: str,
    artifact_stem: str,
    place: Callable[[], Sequence[balloons.BalloonLanding]],
) -> NoReturn:
    """One unchanged helper call; evidence failure never masks a required failure."""
    out_dir = forensics._capture_dir(f"issue1667-native-{artifact_stem}")
    report: dict[str, Any] = {
        "label": label,
        "artifact_stem": artifact_stem,
        "report_path": str(out_dir / "capture.json"),
        "status": "setup",
        "scope": (
            "coverage and existing instance policies only; NOT layout/SHIP/export proof"
        ),
        "quality_observation_boundary": (
            "pre-helper/post-helper actual five fields; NOT immediate pre-AutoBalloon "
            "or in-call proof; production helper includes selection/rebuild/validation"
        ),
        "placement": (
            "one production add_auto_balloons call; EDGE/Square; existing Normal guard"
        ),
        "expected_items": list(items),
        "required_instances": dict(required_instances),
        "manual_short_leader_layout_preserved": False,
        "helper_attempted": False,
        "observer_errors": [],
    }
    primary: BaseException | None = None
    primary_traceback = None
    landings: tuple[balloons.BalloonLanding, ...] = ()
    cached_hwnd = None
    phase = "pre_helper"
    try:
        cached_hwnd = forensics._frame_hwnd(adapter)
        report["cached_pre_helper_hwnd"] = cached_hwnd
        report["pre_helper_quality"] = _quality_state(view)
        report["preference_before"] = _preference(adapter)
        phase = "helper"
        report["helper_attempted"] = True
        started = time.perf_counter()
        try:
            # No retry, alternate attachment, option changes or quality treatment.
            result = place()
        finally:
            report["helper_wall_ms"] = (time.perf_counter() - started) * 1000.0
        landings = tuple(result)
        report["helper_result"] = "returned"
    except BaseException as error:
        primary = error
        primary_traceback = error.__traceback__
        report[f"{phase}_error"] = f"{type(error).__name__}: {error}"
        report["helper_result"] = "raised" if phase == "helper" else "not_called"

    # FIRST after the helper outcome: only Python bookkeeping above, no COM.
    try:
        report["passive_pixels"] = forensics._write_artefacts(
            (
                (
                    "desktop_png",
                    lambda: forensics._grab_screen(out_dir / "post-helper-desktop.png"),
                ),
                (
                    "window_png",
                    lambda: forensics._grab_screen(
                        out_dir / "post-helper-window.png", window=cached_hwnd or 0
                    ),
                ),
            )
        )
        for kind in ("desktop_png", "window_png"):
            if kind not in report["passive_pixels"]:
                error = report["passive_pixels"].get(f"{kind}_error", "no file written")
                report["observer_errors"].append(f"{kind}: {error}")
    except BaseException as error:
        report["observer_errors"].append(
            f"passive_pixels: {type(error).__name__}: {error}"
        )

    # Independent read-only observations: a failed quality read must not prevent
    # actual inventory retention, including balloons left behind by helper errors.
    inventory_notes: tuple[Any, ...] = ()
    for name, observe in (
        ("post_helper_quality", lambda: _quality_state(view)),
        ("preference_after", lambda: _preference(adapter)),
        (
            "returned_notes",
            lambda: [_note_snapshot(landing.note) for landing in landings],
        ),
        ("actual_view_inventory", lambda: _view_inventory(view)),
        (
            "allowed_shown_owners",
            lambda: _shown_owners(adapter, view, items, label=label),
        ),
    ):
        try:
            value = observe()
            if name == "actual_view_inventory":
                inventory_notes, value = value
            report[name] = value
        except BaseException as error:
            report["observer_errors"].append(f"{name}: {type(error).__name__}: {error}")
    report["returned_landings"] = [
        {
            "stem": landing.stem,
            "instance": landing.instance,
            "sheet_xy": landing.sheet_xy,
        }
        for landing in landings
    ]
    report["actual_circle_boxes_m"] = []
    for index, note in enumerate(inventory_notes):
        row: dict[str, Any] = {"inventory_index": index}
        report["actual_circle_boxes_m"].append(row)
        try:
            x, y, radius = rendered_balloon_circle(note, label=label)
            row.update(
                center_m=(x, y),
                radius_m=radius,
                box_m=(x - radius, y - radius, x + radius, y + radius),
            )
        except BaseException as error:
            row["error"] = f"{type(error).__name__}: {error}"
            report["observer_errors"].append(f"circle[{index}]: {row['error']}")

    failures = []
    if report["helper_result"] == "returned":
        # Python landing identities remain available even if a later native
        # observer fails. Do not demote an already-known policy violation.
        if len(landings) != len(items) or {landing.stem for landing in landings} != {
            stem for stem, _ in items
        }:
            failures.append("returned landings do not cover every expected BOM family")
        for landing in landings:
            pin = required_instances.get(landing.stem)
            if pin is not None and _path(landing.instance) != _path(pin):
                failures.append(
                    f"returned required instance mismatch for {landing.stem}: "
                    f"expected={pin!r}, actual={landing.instance!r}"
                )
    if all(
        key in report
        for key in ("returned_notes", "actual_view_inventory", "allowed_shown_owners")
    ):
        try:
            failures.extend(
                _compatibility_failures(
                    items,
                    required_instances,
                    landings,
                    report["returned_notes"],
                    report["actual_view_inventory"],
                    report["allowed_shown_owners"],
                )
            )
        except BaseException as error:
            report["observer_errors"].append(
                f"compatibility: {type(error).__name__}: {error}"
            )
    if "preference_after" in report and "preference_before" in report:
        if report["preference_after"] != report["preference_before"]:
            failures.append(
                "document visible-edge preference/Normal widths changed across helper"
            )
    report["compatibility_failures"] = failures
    report["reported_owner_rows"] = [
        {
            "stem": stem,
            "item": item,
            "required_instance": required_instances.get(stem),
            "actual_owners": [
                row["owners"]
                for row in report.get("actual_view_inventory", ())
                if row["item"] == item
            ],
        }
        for stem, item in items
    ]
    if primary is not None:
        report["status"] = (
            "helper_failed" if report["helper_attempted"] else "setup_failed"
        )
    elif failures:
        report["status"] = "incompatible"
        primary = RuntimeError(
            f"{label}: native instance/coverage compatibility failed: {failures!r}"
        )
    elif report["observer_errors"]:
        report["status"] = "evidence_failed"
        primary = RuntimeError(
            f"{label}: diagnostic evidence incomplete: {report['observer_errors']!r}"
        )
    else:
        report["status"] = "compatible_coverage_and_instances_only"
    if primary is not None:
        primary.add_note(f"FR/CH diagnostic report: {report['report_path']}")
        for error in report["observer_errors"]:
            primary.add_note(f"Additional diagnostic observer failure: {error}")
    try:
        forensics._write_failure_report(out_dir, report)
    except BaseException as error:
        if primary is None:
            raise
        primary.add_note(
            "Additional diagnostic report-write failure: "
            f"{type(error).__name__}: {error}"
        )
    if primary is not None:
        raise primary.with_traceback(primary_traceback)
    raise NativeCompatibilityProbeStop(report)
