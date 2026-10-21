"""Issue-1667 remaining-group helper ABBA diagnostic ONLY; NEVER MERGE.

Four fresh drawings on one held seat, current template and native inputs. The
production helpers are called unchanged. No save/export or successful return is
allowed: the fixed sequence ends in an explicit STOP before cache publication.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from sys import exception as _active_exception
import time
from typing import Any, Awaitable, Callable, Mapping, NoReturn, Sequence

from solidworks_mcp.adapters.sw_type_info import constant

from _com import _early_bound
import _drawing_balloons as balloons
from _drawing_common import rebuild_drawing
import _seat_forensics
from _session import (
    _resident_output_documents,
    _visible_document_paths,
    discard_open_documents,
)
import _telemetry


MANUAL_COMMIT = "fb1fe894e595c397d0945af042f7071f16200299"
PRODUCTION_COMMIT = "01ec8054295c68a72a095db84f0ba6940f5f0d96"
SEQUENCE = ("manual", "native", "native", "manual")


class GroupPerfProbeStop(RuntimeError):
    """Diagnostic completion, including failed arms, is NOT a drawing success."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        super().__init__(
            "INTENTIONAL GROUP PERFORMANCE DIAGNOSTIC STOP before save/export/cache "
            f"publication; status={report['status']}; report={report['report_path']}"
        )


def _file_identity(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path.resolve()), "sha256": digest, "bytes": path.stat().st_size}


def native_input_identity(source_model: Any, source: Path) -> dict[str, Any]:
    """Read the actual source and every referenced component file, without saving."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    instances = []
    paths = {source.resolve()}
    for raw in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw, "IComponent2")
        path = str(component.GetPathName() or "")
        if not path:
            raise RuntimeError(
                f"group probe: component {component.Name2!r} has no path"
            )
        resolved = Path(path).resolve()
        paths.add(resolved)
        instances.append({"instance": str(component.Name2), "path": str(resolved)})
    return {
        "files": [_file_identity(path) for path in sorted(paths, key=str)],
        "instances": sorted(instances, key=lambda row: row["instance"]),
    }


def _preference(adapter: Any) -> dict[str, Any]:
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    option = constant("swDetailingNoOptionSpecified")
    return {
        "slot": int(
            extension.GetUserPreferenceInteger(
                constant("swLineFontVisibleEdgesThickness"), option
            )
        ),
        "normal_width_m": float(
            extension.GetUserPreferenceDouble(
                constant("swPageSetupPrinterNormalLineWeight"), option
            )
        ),
        "thick_width_m": float(
            extension.GetUserPreferenceDouble(
                constant("swPageSetupPrinterThickLineWeight"), option
            )
        ),
    }


def _manual_selection_miss(
    error: Exception, label: str, items: Sequence[tuple[str, str]]
) -> bool:
    """Only the old manual helper's explicit no-edge boundaries may continue."""
    if type(error) is not RuntimeError:
        return False
    for stem, _item in items:
        prefix = re.escape(f"{label}: {stem}")
        if re.fullmatch(
            prefix + r" frozen balloon anchor .+ selects no edge at sheet .+ on .+ "
            r"in \d+ picks, \d+ after a forced redraw",
            str(error),
        ) or re.fullmatch(
            prefix + r" has no verifiably visible edge: no hit test found ink of .+ "
            r"at sheet mm \[.*\]: \d+ body extreme points, then \d+ points along "
            r"its \d+ listed visible edges \(sampled when 1-\d+\)",
            str(error),
        ):
            return True
    return False


def _helper_call(
    adapter: Any,
    view: Any,
    *,
    arm: str,
    items: Sequence[tuple[str, str]],
    label: str,
    margin: float,
    anchors: Mapping[str, balloons.BalloonAnchor],
    report: dict[str, Any],
) -> list[balloons.BalloonLanding]:
    if arm == "manual":
        helper = balloons.add_component_bom_balloons
        kwargs = {
            "items": items,
            "anchors": anchors,
            "label": label,
            "margin": margin,
        }
    elif arm == "native":
        helper = balloons.add_auto_balloons
        kwargs = {"items": items, "label": label}
    else:
        raise ValueError(f"unknown group probe arm {arm!r}")
    # The entire unchanged helper, including resolution, manual picking/captures,
    # insertion/spreading, native preference guard, rebuild and validation. Do not
    # subtract its internal diagnostics or compare native-call-only to manual.
    started = time.perf_counter()
    try:
        landings = helper(adapter, view, **kwargs)
    except BaseException:
        report["failed_helper_elapsed_ms"] = (time.perf_counter() - started) * 1000.0
        raise
    else:
        report["helper_elapsed_ms"] = (time.perf_counter() - started) * 1000.0
        return landings


def _prove_result(
    adapter: Any,
    view: Any,
    landings: list[balloons.BalloonLanding],
    *,
    items: Sequence[tuple[str, str]],
    label: str,
    arm: str,
    anchors: Mapping[str, balloons.BalloonAnchor],
    report: dict[str, Any],
    finish_and_assert_bounds: Callable[[Any, list[balloons.BalloonLanding]], None],
) -> None:
    """Common correctness readback AFTER the helper timer, including fresh rebuild."""
    rebuild_drawing(adapter, label="group performance common attachment proof")
    # Captions are authored at their original post-helper boundary, then each
    # recipe reads its actual settled field/BOM/caption bounds. Owner readback
    # follows that final caption rebuild; none of this is primary timing.
    finish_and_assert_bounds(adapter, landings)
    balloons.assert_balloon_landings(adapter, landings)
    leaves = balloons._view_component_leaves(adapter, view, label=label)
    allowed = {
        stem: {
            leaf.path.casefold()
            for leaf in balloons._shown_instances(
                leaves, stem, balloons.BalloonAnchor(), label=label
            )
        }
        for stem, _item in items
    }
    expected = dict(items)
    seen: set[str] = set()
    rows = []
    report["balloons"] = rows
    for landing in landings:
        note = _early_bound(landing.note, "INote")
        item = str(note.GetBomBalloonText(True) or "").strip()
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        entities = tuple(annotation.GetAttachedEntities3() or ())
        kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
        owners = [balloons._entity_owner(adapter, entity) for entity in entities]
        rows.append(
            {
                "stem": landing.stem,
                "item": item,
                "owners": owners,
                "attachment_types": kinds,
            }
        )
        if (
            landing.stem not in expected
            or landing.stem in seen
            or item != expected[landing.stem]
            or len(entities) != 1
            or kinds != (constant("swSelEDGES"),)
            or owners[0].casefold() not in allowed[landing.stem]
            or owners[0].casefold() != landing.instance.casefold()
        ):
            raise RuntimeError(
                f"{label}: incorrect final item/EDGE owner: {rows[-1]!r}"
            )
        if arm == "manual":
            pin = anchors[landing.stem].instance
            if pin is not None and owners[0].casefold() != pin.casefold():
                raise RuntimeError(
                    f"{label}: manual historical pin {pin!r} was not retained"
                )
        seen.add(landing.stem)
    if len(rows) != len(expected) or seen != set(expected):
        raise RuntimeError(
            f"{label}: final coverage {len(rows)} != {len(expected)} unique expected items"
        )
    report["unique_expected_items"] = len(expected)
    report["edge_owners_valid"] = True
    report["group_bounds_valid"] = True


def _summary(arms: list[dict[str, Any]]) -> dict[str, Any]:
    samples = [
        {
            "order": row["order"],
            "arm": row["arm"],
            "status": row["status"],
            "helper_elapsed_ms": row.get("helper_elapsed_ms")
            if row["status"] == "passed"
            else None,
        }
        for row in arms
    ]
    complete = len(arms) == 4 and all(row["status"] == "passed" for row in arms)
    summary: dict[str, Any] = {
        "scope": "requested group whole-helper only; NOT whole-drawing or farm-leaf speedup",
        "samples": samples,
        "complete_matched_abba": complete,
        "manual_mean_ms": None,
        "native_mean_ms": None,
        "native_minus_manual_ms": None,
        "percent_reduction": None,
    }
    if complete:
        manual = (
            sum(row["helper_elapsed_ms"] for row in arms if row["arm"] == "manual")
            / 2.0
        )
        native = (
            sum(row["helper_elapsed_ms"] for row in arms if row["arm"] == "native")
            / 2.0
        )
        summary.update(
            manual_mean_ms=manual,
            native_mean_ms=native,
            native_minus_manual_ms=native - manual,
            percent_reduction=(
                100.0 * (manual - native) / manual if manual > 0.0 else None
            ),
        )
    return summary


def _empty_documents(adapter: Any) -> dict[str, Any]:
    state = {
        "visible_document_paths": _visible_document_paths(adapter),
        "resident_output_documents": _resident_output_documents(adapter),
    }
    if state["visible_document_paths"] or state["resident_output_documents"]:
        raise RuntimeError(f"group probe requires a fresh document context: {state!r}")
    return state


async def run_matched_group_probe(
    adapter: Any,
    *,
    template: Path,
    case: str,
    manual_recipe_blob: str,
    anchors: Mapping[str, balloons.BalloonAnchor],
    label: str,
    margin: float,
    prepare_arm: Callable[
        [Any, dict[str, Any]],
        Awaitable[
            tuple[
                Any,
                Sequence[tuple[str, str]],
                Callable[[Any, list[balloons.BalloonLanding]], None],
            ]
        ],
    ],
) -> NoReturn:
    """Fixed ABBA, no retries: unexpected native/identity/cleanup errors abort."""
    out_dir = _seat_forensics._capture_dir(f"1667-matched-{case}-performance")
    report: dict[str, Any] = {
        "diagnostic_only": True,
        "never_merge": True,
        "intentional_stop_before_save_export_cache_publication": True,
        "status": "aborted",
        "case": case,
        "helper_label": label,
        "manual_margin_m": margin,
        "proof_scope": (
            "post-helper diagnostic field/BOM/caption and attachment readback; "
            "NOT final-sheet or export proof"
        ),
        # The unchanged helper records actual original/Normal/restored readbacks;
        # do not present an expected slot-1 value here as a measured readback.
        "native_weight_guard_trace": {
            "span": "drawing.auto_balloon_edge_weight",
            "label": label,
            "readbacks": (
                "original_slot",
                "normal_readback_slot",
                "restore_readback_slot",
            ),
        },
        "sequence": SEQUENCE,
        "production_source": PRODUCTION_COMMIT,
        "manual_anchor_base": MANUAL_COMMIT,
        "manual_anchor_recipe_blob": manual_recipe_blob,
        "manual_anchors": {
            stem: {"point_mm": anchor.point_mm, "instance": anchor.instance}
            for stem, anchor in sorted(anchors.items())
        },
        "report_path": str(out_dir / "capture.json"),
        "arms": [
            {"order": order, "arm": arm, "status": "not_reached"}
            for order, arm in enumerate(SEQUENCE, start=1)
        ],
    }
    baseline: dict[str, Any] | None = None
    started = time.perf_counter()
    try:
        seat_pid = int(adapter.swApp.GetProcessID())
        if seat_pid <= 0:
            raise RuntimeError(f"group probe has invalid SolidWorks PID {seat_pid}")
        report["seat_pid"] = seat_pid
        report["native_helper"] = _file_identity(Path(balloons.__file__))
        report["seat_provenance"] = _seat_forensics.seat_provenance(adapter)
        for row in report["arms"]:
            phase = "matched_context"
            try:
                row["documents_before"] = _empty_documents(adapter)
                row["seat_pid_before"] = int(adapter.swApp.GetProcessID())
                if row["seat_pid_before"] != seat_pid:
                    raise RuntimeError(
                        "group probe: SolidWorks seat changed before setup"
                    )
                row["template"] = _file_identity(template)
                phase = "setup"
                view, items, finish_and_assert_bounds = await prepare_arm(adapter, row)
                phase = "matched_context"
                row["drawing_title"] = str(adapter.currentModel.GetTitle() or "")
                row["drawing_path"] = str(adapter.currentModel.GetPathName() or "")
                if (
                    not row["drawing_title"]
                    or row["drawing_path"]
                    or int(adapter.currentModel.GetType()) != 3
                ):
                    raise RuntimeError(
                        "group probe did not create a fresh unsaved drawing"
                    )
                if int(adapter.swApp.GetProcessID()) != seat_pid:
                    raise RuntimeError(
                        "group probe: SolidWorks seat changed during setup"
                    )
                row["items"] = list(items)
                if (
                    len(items) != len(anchors)
                    or len({item for _stem, item in items}) != len(anchors)
                    or {stem for stem, _item in items} != set(anchors)
                ):
                    raise RuntimeError(
                        f"group probe requires exactly {len(anchors)} unique {case} BOM items"
                    )
                row["preference_before"] = _preference(adapter)
                # Equal inputs and fit are prerequisites, not a certificate system.
                if baseline is None:
                    baseline = row
                else:
                    for key in (
                        "template",
                        "native_inputs",
                        "setup",
                        "items",
                        "preference_before",
                    ):
                        if row[key] != baseline[key]:
                            raise RuntimeError(
                                f"group probe matched context differs: {key}"
                            )
                phase = "helper"
                try:
                    landings = _helper_call(
                        adapter,
                        view,
                        arm=row["arm"],
                        items=items,
                        label=label,
                        margin=margin,
                        anchors=anchors,
                        report=row,
                    )
                except Exception as exc:
                    if row["arm"] != "manual" or not _manual_selection_miss(
                        exc, label, items
                    ):
                        raise
                    row.update(
                        status="failed",
                        failure_classification="manual_selection_miss",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                else:
                    phase = "correctness"
                    _prove_result(
                        adapter,
                        view,
                        landings,
                        items=items,
                        label=label,
                        arm=row["arm"],
                        anchors=anchors,
                        report=row,
                        finish_and_assert_bounds=finish_and_assert_bounds,
                    )
                    row["status"] = "passed"
                finally:
                    primary_error = _active_exception()
                    try:
                        row["preference_after"] = _preference(adapter)
                        if row["preference_after"] != row["preference_before"]:
                            raise RuntimeError(
                                "group probe: document visible-edge preference changed"
                            )
                    except BaseException as exc:
                        row["preference_error"] = f"{type(exc).__name__}: {exc}"
                        # Keep an exceptional helper/proof failure and its phase
                        # primary. A handled manual miss is no longer propagating:
                        # retain it separately, but a preference failure must abort.
                        if primary_error is None:
                            if (
                                row.get("failure_classification")
                                == "manual_selection_miss"
                            ):
                                row.update(
                                    prior_failure_classification="manual_selection_miss",
                                    prior_error=row["error"],
                                )
                            phase = "preference_restoration"
                            raise
            except BaseException as exc:
                row.update(
                    status="failed",
                    failure_classification=(
                        f"{row['arm']}_helper_error"
                        if phase == "helper"
                        else f"{phase}_error"
                    ),
                    error=f"{type(exc).__name__}: {exc}",
                )
                raise
            finally:
                try:
                    discard_open_documents(adapter)
                    adapter.currentModel = None
                    row["cleanup"] = _empty_documents(adapter)
                    row["seat_pid_after"] = int(adapter.swApp.GetProcessID())
                    if row["seat_pid_after"] != seat_pid:
                        raise RuntimeError(
                            "group probe: SolidWorks seat changed during cleanup"
                        )
                    if _file_identity(template) != row.get("template"):
                        raise RuntimeError(
                            "group probe: template bytes changed during arm"
                        )
                    for identity in row.get("native_inputs", {}).get("files", ()):
                        if _file_identity(Path(identity["path"])) != identity:
                            raise RuntimeError(
                                f"group probe: native input changed: {identity['path']}"
                            )
                except BaseException as exc:
                    # Keep an earlier native/identity failure as the primary
                    # cause; cleanup must still abort and retain its own error.
                    if row.get("failure_classification") == "manual_selection_miss":
                        row["prior_failure_classification"] = "manual_selection_miss"
                        row["failure_classification"] = "cleanup_or_identity_error"
                    row.setdefault(
                        "failure_classification", "cleanup_or_identity_error"
                    )
                    row.update(
                        status="failed",
                        cleanup_error=f"{type(exc).__name__}: {exc}",
                    )
                    raise
                finally:
                    _seat_forensics._write_failure_report(
                        out_dir / f"{row['order']:02d}-{row['arm']}", row
                    )
        report["status"] = (
            "completed"
            if all(row["status"] == "passed" for row in report["arms"])
            else "completed_with_failed_arms"
        )
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["summary"] = _summary(report["arms"])
        report["elapsed_ms"] = (time.perf_counter() - started) * 1000.0
        _seat_forensics._write_failure_report(out_dir, report)
        _telemetry.info(
            f"Matched group diagnostic retained: {report['report_path']}",
            status=report["status"],
            summary=report["summary"],
        )
    raise GroupPerfProbeStop(report)
