"""NEVER MERGE: SM Wireframe -> native AutoBalloon -> authored-style probe.

One control/Wireframe/Wireframe/control experiment on fresh production drawings.
One EDGE AutoBalloon5 per arm; raw and independent inventories precede restoration.
Terminal diagnostic PDF/precision/render observations are separate from coverage.
No refresh, resolving, relinking, quality variant, retry or production SHIP claim.
All outcomes intentionally fail before cache success; hotfix1795 stays unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import socket
import time
from datetime import UTC, datetime
from pathlib import Path
from sys import exception as active_exception
from typing import Any, Awaitable, Callable, NoReturn

from solidworks_mcp.adapters import sw_type_info
from solidworks_mcp.adapters.com_variant import bstr_array

import _drawing_balloons as balloons
import _seat_forensics as forensics
import _telemetry
from _com import _early_bound
from _drawing_common import assert_precise_isometric_views, render_pdf_png
from _drawing_selection import _activate_and_select_view
from _session import discard_open_documents

SEQUENCE = ("control", "wireframe", "wireframe", "control")
LABEL = "SM Wireframe probe"
VIEW_STATE_ORDER = (
    "IsModelOutOfDate",
    "IsLightweight",
    "IsModelLoaded",
    "GetFacettedHlrDisplay",
)
DISPLAY_ORDER = (
    "GetDisplayMode2",
    "GetUseParentDisplayMode",
    "GetDisplayEdgesInShadedMode",
    "GetFacettedHlrDisplay",
    "GetCThreadQuality",
)
AUTHORED_OPTIONS = {
    "Layout": 1,
    "ReverseDirection": False,
    "IgnoreMultiple": True,
    "InsertMagneticLine": False,
    "LeaderAttachmentToFaces": False,
    "Style": 1,
    "Size": 2,
    "UpperTextContent": 1,
    "ItemNumberStart": 1,
    "ItemNumberIncrement": 1,
    "ItemOrder": 1,
}
OPTION_ORDER = (
    *AUTHORED_OPTIONS,
    "CustomSize",
    "EditBalloonOption",
    "EditBalloons",
    "Layername",
    "LowerText",
    "LowerTextContent",
    "UpperText",
    "FirstItem",
)
OPTION_TYPES = {name: type(value) for name, value in AUTHORED_OPTIONS.items()} | {
    "CustomSize": float,
    "EditBalloonOption": int,
    "EditBalloons": bool,
    "Layername": str,
    "LowerText": str,
    "LowerTextContent": int,
    "UpperText": str,
    "FirstItem": type(None),
}


class SmWireframeProbeStop(RuntimeError):
    """Intentional diagnostic failure, including when all native arms pass."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        super().__init__(
            f"INTENTIONAL SM WIREFRAME DIAGNOSTIC STOP before cache "
            f"success; {report['interpretation']}; report={report['report_path']}"
        )


def _error(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"


def _identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "path": str(path.resolve()),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": digest,
    }


def _configurations(feature: Any, view_configuration: str) -> dict[str, Any]:
    # IBomFeature SDK: retval names, then BYREF VARIANT Visible (flags 3).
    raw = feature.GetConfigurations(False, None)
    if type(raw) is not tuple or len(raw) != 2:
        raise RuntimeError(
            f"GetConfigurations did not return (names, visible): {raw!r}"
        )
    names, visible = raw
    if (
        type(names) not in (tuple, list)
        or type(visible) not in (tuple, list)
        or not names
        or len(names) != len(visible)
        or any(type(name) is not str or not name for name in names)
        or len(set(names)) != len(names)
        or any(type(flag) is not bool for flag in visible)
    ):
        raise RuntimeError(f"invalid BOM configuration arrays: {raw!r}")
    selected = tuple(name for name, flag in zip(names, visible, strict=True) if flag)
    if view_configuration not in selected:
        raise RuntimeError(
            f"view configuration {view_configuration!r} not visible: {raw!r}"
        )
    return {"names": list(names), "visible": list(visible), "selected": list(selected)}


def _link_state(view: Any, table: Any, bom_cells: Callable[..., Any]) -> dict[str, Any]:
    """Same cheap read order before/after treatment in EVERY arm; no row census."""
    feature = _early_bound(
        _early_bound(table, "IBomTableAnnotation").BomFeature, "IBomFeature"
    )
    name = feature.Name
    flag = view.GetKeepLinkedToBOM()
    linked_name = view.GetKeepLinkedToBOMName()
    configuration = view.ReferencedConfiguration
    if (
        type(name) is not str
        or not name
        or type(flag) is not bool
        or type(linked_name) is not str
        or type(configuration) is not str
        or not configuration
    ):
        raise RuntimeError("unreadable BOM name/link/configuration")
    configurations = _configurations(feature, configuration)
    grid = bom_cells(_early_bound(table, "ITableAnnotation"))
    return {
        "feature_name": name,
        "link_flag": flag,
        "link_name": linked_name,
        "link_name_relative_to_own_feature": "own"
        if linked_name == name
        else linked_name,
        "view_configuration": configuration,
        "bom_configurations": configurations,
        "grid": grid,
    }


def _semantic(state: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in state.items()
        if key not in ("feature_name", "link_name")
    }


def _pose(view: Any) -> dict[str, Any]:
    position = tuple(view.Position)
    scale, angle, exploded = view.ScaleDecimal, view.Angle, view.IsExploded()
    if (
        len(position) != 2
        or any(type(x) not in (int, float) or not math.isfinite(x) for x in position)
        or type(scale) not in (int, float)
        or not math.isfinite(scale)
        or type(angle) not in (int, float)
        or not math.isfinite(angle)
        or type(exploded) is not bool
    ):
        raise RuntimeError("unreadable SM view pose/explode")
    return {"position": position, "scale": scale, "angle": angle, "exploded": exploded}


def _note(adapter: Any, raw: Any) -> dict[str, Any]:
    note = _early_bound(raw, "INote")
    text, is_bom, name = (
        note.GetBomBalloonText(True),
        note.IsBomBalloon(),
        note.GetName(),
    )
    if type(text) is not str or type(is_bom) is not bool or type(name) is not str:
        raise RuntimeError("unreadable balloon text/type/name")
    row = {
        "raw_text": text,
        "item": text.strip(),
        "is_bom": is_bom,
        "name": name,
        "attachment_types": [],
        "owners": [],
        "entity_count": 0,
        "is_attached": note.IsAttached(),
        "is_dangling": None,
    }
    annotation = note.GetAnnotation()
    if annotation is not None:
        annotation = _early_bound(annotation, "IAnnotation")
        row["annotation_name"] = annotation.GetName()
        row["is_dangling"] = annotation.IsDangling()
        entities = tuple(annotation.GetAttachedEntities3() or ())
        kinds = tuple(annotation.GetAttachedEntityTypes() or ())
        supported = (
            sw_type_info.constant("swSelEDGES"),
            sw_type_info.constant("swSelFACES"),
        )
        row.update(
            entity_count=len(entities),
            attachment_types=list(kinds),
            owners=[
                balloons._entity_owner(adapter, entity)
                if index < len(kinds) and kinds[index] in supported
                else ""
                for index, entity in enumerate(entities)
            ],
        )
    if type(row["is_attached"]) is not bool or type(row["is_dangling"]) is not bool:
        raise RuntimeError("unreadable note attachment/dangling status")
    return row


def _inventory(adapter: Any, view: Any) -> list[dict[str, Any]]:
    inventory = []
    for raw in tuple(view.GetNotes() or ()):
        note = _early_bound(raw, "INote")
        is_bom = note.IsBomBalloon()
        if type(is_bom) is not bool:
            raise RuntimeError("unreadable inventory IsBomBalloon")
        if is_bom:
            inventory.append(_note(adapter, note))
    return inventory


def _coverage(
    notes: list[dict[str, Any]], allowed: dict[str, list[str]]
) -> dict[str, Any]:
    present = {note["item"] for note in notes if note["is_bom"]}
    incorrect = [
        note
        for note in notes
        if not note["is_bom"]
        or note["item"] not in allowed
        or note["is_attached"] is not True
        or note["is_dangling"] is not False
        or note["entity_count"] != 1
        or len(note["attachment_types"]) != 1
        or len(note["owners"]) != 1
        or note["owners"][0].casefold()
        not in {owner.casefold() for owner in allowed.get(note["item"], ())}
    ]
    return {
        "missing": sorted(set(allowed) - present),
        "incorrect": incorrect,
        "correct_ten": len(notes) == 10 and present == set(allowed) and not incorrect,
    }


def _options(
    options: Any, row: dict[str, Any], baseline: dict[str, Any] | None
) -> None:
    """Post-call/post-pixels/pre-restore observations, NOT proof of pre-call defaults."""
    values, failures = {}, row["option_comparison_failures"]
    for name in OPTION_ORDER:
        try:
            value = getattr(options, name)
            # FirstItem is a dispatch, not a JSON scalar. Never traverse it here.
            if type(value) is not OPTION_TYPES[name] or (
                type(value) is float and not math.isfinite(value)
            ):
                raise ValueError(
                    f"invalid/opaque {type(value).__name__}; not comparable"
                )
            values[name] = value
            if name in AUTHORED_OPTIONS and (
                type(value) is not type(AUTHORED_OPTIONS[name])
                or value != AUTHORED_OPTIONS[name]
            ):
                failures.append(f"{name}: post-call authored value mismatch")
        except Exception as error:
            values[name] = {"unreadable": _error(error)}
            failures.append(f"{name}: unreadable")
    row["options"] = values
    if baseline is not None:
        if baseline["option_comparison_failures"]:
            failures.append("arm 1 options not comparable")
        elif any(
            type(values[name]) is not type(baseline["options"][name])
            or values[name] != baseline["options"][name]
            for name in OPTION_ORDER
        ):
            failures.append("post-call options differ from arm 1")
    row["comparison_ineligible"] = bool(failures)


def _view_state(view: Any) -> dict[str, Any]:
    """Fixed-order Boolean observations, not readiness or causal certificates."""
    state = {}
    for name in VIEW_STATE_ORDER:
        try:
            value = getattr(view, name)()
            if type(value) is not bool:
                raise ValueError(f"non-boolean {name}: {value!r}")
            state[name] = value
        except Exception as error:
            state[name + "_error"] = _error(error)
    return state


def _display_state(view: Any) -> dict[str, Any]:
    state = {}
    for name in DISPLAY_ORDER:
        try:
            value = getattr(view, name)()
            expected = int if name == "GetDisplayMode2" else bool
            if type(value) is not expected:
                raise ValueError(f"invalid {name}: {value!r}")
            state[name] = value
        except Exception as error:
            state[name + "_error"] = _error(error)
    return state


def _authored_display(state: dict[str, Any]) -> bool:
    # Mode3 and composite7 are equivalent only with shaded edges enabled.
    return (
        state.get("GetDisplayMode2") in (3, 7)
        and state.get("GetUseParentDisplayMode") is False
        and state.get("GetDisplayEdgesInShadedMode") is True
        and state.get("GetCThreadQuality") is True
        and not any(name.endswith("_error") for name in state)
    )


def _same_notes(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
    # Already-recorded facts only; preserve multiplicity, ignore enumeration order.
    return sorted(json.dumps(note, sort_keys=True) for note in left) == sorted(
        json.dumps(note, sort_keys=True) for note in right
    )


@_telemetry.traced("drawing.sm_wireframe.call_and_observe")
def _call_once(
    adapter: Any,
    view: Any,
    row: dict[str, Any],
    baseline: dict[str, Any] | None,
    out_dir: Path,
    hwnd: int,
) -> None:
    _telemetry.annotate(arm=row["arm"], arm_index=row["index"])
    _activate_and_select_view(adapter, view, label=LABEL)
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    ddoc = _early_bound(draw, "IDrawingDoc")
    options = ddoc.CreateAutoBalloonOptions()
    if options is None:
        raise RuntimeError("CreateAutoBalloonOptions returned null")
    options = _early_bound(options, "IAutoBalloonOptions")
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    preference = sw_type_info.constant("swLineFontVisibleEdgesThickness")
    option = sw_type_info.constant("swDetailingNoOptionSpecified")
    normal = sw_type_info.constant("swLW_NORMAL")
    original = extension.GetUserPreferenceInteger(preference, option)
    row["normal_guard"] = {"original_slot": original, "normal_slot": normal}
    row.update(treatment_ms=0.0, display_restore_calls=0, display_restore_ms=0.0)
    restore_display = False
    try:
        started = time.perf_counter()
        result = extension.SetUserPreferenceInteger(preference, option, normal)
        applied = extension.GetUserPreferenceInteger(preference, option)
        row["normal_guard"].update(
            set_return=result,
            applied_slot=applied,
            enter_ms=(time.perf_counter() - started) * 1000,
        )
        if result is not True or applied != normal:
            raise RuntimeError("Normal visible-edge slot did not apply")
        for name, value in AUTHORED_OPTIONS.items():
            setattr(options, name, value)
        observer_started = time.perf_counter()
        row["pre_treatment_view_state"] = _view_state(view)
        row["pre_treatment_display"] = _display_state(view)
        row["pre_treatment_observer_ms"] = (
            time.perf_counter() - observer_started
        ) * 1000
        row["observer_ms"] += row["pre_treatment_observer_ms"]
        if not _authored_display(row["pre_treatment_display"]):
            raise RuntimeError("initial view is not authored Shaded-with-Edges")
        # This finally encloses native capture AND sealing the pre-restore inventory.
        try:
            try:
                if row["arm"] == "wireframe":
                    restore_display = True  # The mutating call could partially fail.
                    row["treatment_calls"] += 1
                    with _telemetry.span("drawing.sm_wireframe.set_wireframe"):
                        started = time.perf_counter()
                        try:
                            row["treatment_return"] = view.SetDisplayMode4(
                                False, 0, False, True, True
                            )
                        finally:
                            row["treatment_ms"] = (
                                time.perf_counter() - started
                            ) * 1000
                elif row["arm"] != "control":
                    raise RuntimeError(f"unknown Wireframe arm: {row['arm']!r}")
            except BaseException as error:
                row["treatment_error"] = _error(error)
                raise
            observer_started = time.perf_counter()
            row["post_treatment_view_state"] = _view_state(view)
            row["post_treatment_display"] = _display_state(view)
            row["post_treatment_observer_ms"] = (
                time.perf_counter() - observer_started
            ) * 1000
            row["observer_ms"] += row["post_treatment_observer_ms"]
            state = row["post_treatment_display"]
            if row["arm"] == "wireframe" and (
                state.get("GetDisplayMode2") != 0
                or state.get("GetUseParentDisplayMode") is not False
                or any(name.endswith("_error") for name in state)
            ):
                raise RuntimeError("Wireframe/local display treatment did not read back")
            selection_started = time.perf_counter()
            try:
                _activate_and_select_view(adapter, view, label=LABEL)
            except BaseException as error:
                row["final_selection_error"] = _error(error)
                raise
            finally:
                row["final_selection_ms"] = (
                    time.perf_counter() - selection_started
                ) * 1000
            raw = None
            try:
                with _telemetry.span("drawing.sm_wireframe.autoballoon_native"):
                    started = time.perf_counter()
                    try:
                        row["native_calls"] += 1
                        raw = ddoc.AutoBalloon5(options)
                    finally:
                        row["native_ms"] = (time.perf_counter() - started) * 1000
            finally:
                # Python-only metadata immediately, before even passive pixels.
                row["raw_return"] = {
                    "python_type": type(raw).__name__,
                    "count": len(raw) if type(raw) in (tuple, list) else None,
                }
                started = time.perf_counter()
                try:
                    row["passive_post_call_png"] = forensics._grab_screen(
                        out_dir / f"{row['index']}-{row['arm']}-post-call.png",
                        window=hwnd,
                    )
                except BaseException as error:
                    row["passive_capture_error"] = _error(error)
                    row["secondary_errors"].append("passive pixels: " + _error(error))
                finally:
                    row["observer_ms"] += (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            try:
                if raw is not None and type(raw) not in (tuple, list):
                    raise RuntimeError("AutoBalloon5 returned non-array shape")
                returned = tuple(raw) if raw is not None else ()
                row["raw_notes"] = [_note(adapter, note) for note in returned]
                row["inventory"] = _inventory(adapter, view)
                row["pre_restore_sealed"] = True
            finally:
                _options(options, row, baseline)
                row["observer_ms"] += (time.perf_counter() - started) * 1000
        finally:
            primary = active_exception()
            try:
                if restore_display:
                    row["display_restore_calls"] += 1
                    with _telemetry.span("drawing.sm_wireframe.restore_authored"):
                        started = time.perf_counter()
                        try:
                            row["display_restore_return"] = view.SetDisplayMode4(
                                False, 3, False, True, True
                            )
                        finally:
                            row["display_restore_ms"] = (
                                time.perf_counter() - started
                            ) * 1000
            except BaseException as error:
                row["display_restore_error"] = _error(error)
                row["secondary_errors"].append("display restore: " + _error(error))
                if primary is not None:
                    primary.add_note("additional display restoration: " + _error(error))
            # Symmetric observation stage even in controls (zero display setters).
            started = time.perf_counter()
            try:
                row["restored_display"] = _display_state(view)
                try:
                    row["passive_restored_png"] = forensics._grab_screen(
                        out_dir / f"{row['index']}-{row['arm']}-restored.png",
                        window=hwnd,
                    )
                except BaseException as error:
                    row["restored_capture_error"] = _error(error)
                    row["secondary_errors"].append(
                        "restored pixels: " + _error(error)
                    )
                    if primary is not None:
                        primary.add_note("additional restored pixels: " + _error(error))
                row["restored_inventory"] = _inventory(adapter, view)
                row["restored_inventory_unchanged"] = (
                    row.get("pre_restore_sealed", False)
                    and _same_notes(row["inventory"], row["restored_inventory"])
                )
            except BaseException as error:
                row["post_restore_observation_error"] = _error(error)
                row["secondary_errors"].append("restored observation: " + _error(error))
                if primary is not None:
                    primary.add_note("additional restored observation: " + _error(error))
            finally:
                row["restoration_observer_ms"] = (
                    time.perf_counter() - started
                ) * 1000
                row["observer_ms"] += row["restoration_observer_ms"]
    finally:
        primary = active_exception()
        started = time.perf_counter()
        try:
            result = extension.SetUserPreferenceInteger(preference, option, original)
            restored = extension.GetUserPreferenceInteger(preference, option)
            row["normal_guard"].update(restore_return=result, restored_slot=restored)
            if result is not True or restored != original:
                raise RuntimeError("Normal visible-edge slot restoration failed")
        except BaseException as error:
            row["secondary_errors"].append("Normal restore: " + _error(error))
            if primary is None:
                raise
            primary.add_note("additional Normal restoration: " + _error(error))
        finally:
            row["restore_ms"] = (time.perf_counter() - started) * 1000
    if "passive_capture_error" in row:
        raise RuntimeError("SM native passive capture failed; see retained errors")


@_telemetry.traced("drawing.sm_wireframe.row_association")
def _row_components(
    table: Any, state: dict[str, Any], bom_column: Callable[..., int]
) -> list[dict[str, Any]]:
    grid = state["grid"]
    column = bom_column(grid[0], lambda cell: cell.startswith("ITEM NO"), "ITEM NO.")
    item_rows = {cells[column]: index for index, cells in enumerate(grid[1:], start=1)}
    if len(item_rows) != len(grid) - 1:
        raise RuntimeError("duplicate actual BOM item-to-native-row mapping")
    configuration = state["view_configuration"]
    if state["bom_configurations"]["selected"] != [configuration]:
        raise RuntimeError(
            "SM row association requires one actual selected BOM configuration"
        )
    bom = _early_bound(table, "IBomTableAnnotation")
    rows = []
    for item in ("4", "8", "1"):
        row = {
            "item": item,
            "native_row": item_rows[item],
            "bom_configuration": configuration,
            "parent_assembly_configuration": configuration,
            "components": [],
        }
        rows.append(row)
        try:
            components = tuple(bom.GetComponents2(item_rows[item], configuration) or ())
            for raw in components:
                component = _early_bound(raw, "IComponent2")
                observed = {}
                row["components"].append(observed)
                # First native read after pointer: post-state only, raw enum retained.
                for name, read in (
                    ("suppression_raw", lambda: component.GetSuppression2()),
                    ("name", lambda: component.Name2),
                    (
                        "referenced_configuration",
                        lambda: component.ReferencedConfiguration,
                    ),
                    (
                        "excluded_from_parent_bom",
                        lambda: component.GetExcludeFromBOM2(
                            sw_type_info.constant("swSpecifyConfiguration"),
                            bstr_array([configuration]),
                        ),
                    ),
                ):
                    try:
                        value = read()
                        if name == "suppression_raw" and type(value) is not int:
                            raise ValueError(
                                f"non-integer suppression state: {value!r}"
                            )
                        if name in ("name", "referenced_configuration") and (
                            type(value) is not str or not value
                        ):
                            raise ValueError(f"empty/non-string {name}: {value!r}")
                        if name == "excluded_from_parent_bom":
                            if (
                                type(value) not in (tuple, list)
                                or len(value) != 1
                                or type(value[0]) is not bool
                            ):
                                raise ValueError(f"invalid exclusion array: {value!r}")
                            value = list(value)
                        observed[name] = value
                    except Exception as error:
                        observed[name + "_error"] = _error(error)
        except Exception as error:
            row["error"] = _error(error)
    return rows


@_telemetry.traced("drawing.sm_wireframe.terminal_output")
def _terminal_output(
    adapter: Any,
    view: Any,
    row: dict[str, Any],
    out_dir: Path,
    *,
    layout: Any,
    sheet_layouts: dict[str, Any],
) -> None:
    """Terminal computation, never a pre-call intervention or coverage repair."""
    quality: dict[str, Any] = {"errors": [], "precision_verified": False}
    row["terminal_quality"] = quality
    started = time.perf_counter()
    try:
        draw = _early_bound(adapter.currentModel, "IModelDoc2")
        names = _early_bound(draw, "IDrawingDoc").GetSheetNames()
        if (
            type(names) not in (tuple, list)
            or not names
            or any(type(name) is not str or not name for name in names)
            or len(set(names)) != len(names)
        ):
            raise RuntimeError(f"invalid diagnostic sheet names: {names!r}")
        quality["sheet_names"] = list(names)
        quality["expected_pages"] = len(names)
        layouts = tuple(sheet_layouts[name] for name in names)
        export_started = time.perf_counter()
        try:
            with _telemetry.span("drawing.sm_wireframe.diagnostic_pdf"):
                quality["export"] = forensics._save_failure_document(
                    adapter,
                    out_dir,
                    f"{row['index']}-{row['arm']}-restored",
                    sheet_pdf=True,
                )
        finally:
            quality["export_ms"] = (time.perf_counter() - export_started) * 1000
        pdf = Path(quality["export"]["sheet_pdf"])
        if not pdf.is_file() or pdf.stat().st_size <= 0:
            raise RuntimeError("diagnostic PDF is absent/empty")
        quality_started = time.perf_counter()
        try:
            # Prior project observations motivate this computed-output boundary;
            # the official getter does not promise universal PDF-only readiness.
            quality["checked_isometrics"] = assert_precise_isometric_views(
                adapter, names
            )
            if (
                type(quality["checked_isometrics"]) is not int
                or quality["checked_isometrics"] < 1
            ):
                raise RuntimeError("no diagnostic isometric received a precision check")
            quality["precision_verified"] = True
        except Exception as error:
            quality["errors"].append("precision assertion: " + _error(error))
        finally:
            quality["quality_ms"] = (time.perf_counter() - quality_started) * 1000
        quality["display"] = _display_state(view)
        quality["precision_verified"] = (
            quality["precision_verified"]
            and _authored_display(quality["display"])
            and quality["display"].get("GetFacettedHlrDisplay") is False
        )
        quality["live_path"] = draw.GetPathName()
        if quality["live_path"] != "":
            quality["errors"].append("silent-copy export changed the live drawing path")
        quality["inventory"] = _inventory(adapter, view)
        quality["inventory_unchanged"] = _same_notes(
            row.get("restored_inventory", []), quality["inventory"]
        )
        render_started = time.perf_counter()
        try:
            png = out_dir / f"{row['index']}-{row['arm']}-restored-pdf.png"
            render_pdf_png(
                pdf, png, layout=layout, expected_pages=len(names), page_layouts=layouts
            )
            quality["render_png"] = str(png)
        finally:
            quality["render_ms"] = (time.perf_counter() - render_started) * 1000
    except Exception as error:
        quality["errors"].append("terminal output: " + _error(error))
    finally:
        quality["total_ms"] = (time.perf_counter() - started) * 1000
        row["secondary_errors"].extend(quality["errors"])
        row["restoration_quality_verified"] = (
            "display_restore_error" not in row
            and "post_restore_observation_error" not in row
            and "restored_capture_error" not in row
            and _authored_display(row.get("restored_display", {}))
            and row.get("restored_inventory_unchanged", False)
            and quality["precision_verified"]
            and quality.get("inventory_unchanged", False)
            and not quality["errors"]
            and bool(quality.get("render_png"))
        )


def _quality_interpret(rows: list[dict[str, Any]]) -> str:
    if len(rows) != 4 or any("terminal_quality" not in row for row in rows):
        return "unproven: incomplete terminal restoration observations"
    controls = [row for row in rows if row["arm"] == "control"]
    treated = [row for row in rows if row["arm"] == "wireframe"]
    if all(row.get("restoration_quality_verified", False) for row in rows):
        return (
            "restored precision/text/owners/attachment verified in these arms; "
            "visible landing and layout require human inspection"
        )
    if all(row.get("restoration_quality_verified", False) for row in controls) and any(
        not row.get("restoration_quality_verified", False) for row in treated
    ):
        return "rejected: treated-only restoration quality failure"
    if all(
        row["terminal_quality"].get("export", {}).get("sheet_pdf")
        and not row["terminal_quality"]["precision_verified"]
        for row in rows
    ):
        return (
            "diagnostic export limitation: precision unproven in all arms; "
            "native coverage verdict unchanged"
        )
    return "unproven: restoration/export/render observations failed or split"


def _interpret(rows: list[dict[str, Any]]) -> str:
    if len(rows) != 4 or any("error" in row for row in rows):
        return "inconclusive: setup/native/treatment/selection/cleanup failure"
    if any(row["comparison_ineligible"] for row in rows):
        return "inconclusive: post-call options or observation comparability failed"
    if not all(row.get("association_verified", False) for row in rows):
        return "inconclusive: targeted post-call row association not verified"
    if any(
        sorted(
            json.dumps((note["name"], note.get("annotation_name")))
            for note in row["raw_notes"]
        )
        != sorted(
            json.dumps((note["name"], note.get("annotation_name")))
            for note in row["inventory"]
        )
        for row in rows
    ):
        return "inconclusive: raw/inventory note identities disagree"
    if any(
        set(row["raw_coverage"]["missing"])
        != set(row["inventory_coverage"]["missing"])
        or row["raw_coverage"]["correct_ten"]
        != row["inventory_coverage"]["correct_ten"]
        or sorted(
            json.dumps(note, sort_keys=True)
            for note in row["raw_coverage"]["incorrect"]
        )
        != sorted(
            json.dumps(note, sort_keys=True)
            for note in row["inventory_coverage"]["incorrect"]
        )
        for row in rows
    ):
        return "inconclusive: raw/inventory coverage disagreement"
    controls = [row for row in rows if row["arm"] == "control"]
    treated = [row for row in rows if row["arm"] == "wireframe"]
    kinds = ("raw_coverage", "inventory_coverage")
    position_two_correct = all(rows[1][kind]["correct_ten"] for kind in kinds)
    if all(rows[-1][kind]["correct_ten"] for kind in kinds):
        suffix = (
            ""
            if position_two_correct
            else "; Wireframe insufficient at position 2"
        )
        return "inconclusive: final control passes; position trend" + suffix
    if not position_two_correct:
        return "Wireframe insufficient at position 2; no production claim"
    if all(
        all(
            "8" in row[kind]["missing"] and not row[kind]["incorrect"]
            for kind in kinds
        )
        for row in controls
    ) and all(all(row[kind]["correct_ten"] for kind in kinds) for row in treated):
        return (
            "supports candidate Wireframe coverage effect in these arms only; "
            "not proof of restored quality, visible landing or layout; "
            "no production SHIP/performance claim"
        )
    return "inconclusive: split outcome or controls also pass; no production claim"


@_telemetry.traced("drawing.sm_wireframe.probe")
async def run_probe(
    adapter: Any,
    prepare: Callable[[], Awaitable[tuple[Any, Any, Any]]],
    *,
    source: Path,
    bom_cells: Callable[..., Any],
    bom_column: Callable[..., int],
    anchors: dict[str, Any],
    layout: Any,
    sheet_layouts: dict[str, Any],
) -> NoReturn:
    """Called only in this diagnostic leaf's exclusively held run_build session."""
    out_dir = forensics._capture_dir("sm-wireframe-discriminator")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "diagnostic_only_never_merge": True,
        "started_utc": datetime.now(UTC).isoformat(),
        "report_path": str(out_dir / "report.json"),
        "worker": socket.gethostname(),
        "python_pid": os.getpid(),
        "seat": forensics.seat_provenance(adapter),
        "sequence": SEQUENCE,
        "arms": [],
        "errors": [],
        "suppression_enum": {
            0: "suppressed",
            1: "lightweight",
            2: "fully resolved",
            3: "resolved",
            4: "fully lightweight",
            5: "internal-ID mismatch",
        },
        "view_state_observation_limit": (
            "identical pre/post-treatment Boolean observations are mediators, not readiness "
            "certificates; post-call resolution never establishes pre-call component state"
        ),
        "interpretation_limit": (
            "Wireframe may attach to shaded-hidden edges: correct owner, attached "
            "and non-dangling do not prove a visible leader landing or good layout. "
            "Faceting transience is a prior project observation, not an official "
            "universal PDF-only readiness guarantee."
        ),
        "fallback_bounds": {
            "fresh_attempts_per_artifact": 4,
            "max_candidate_artifacts": 6,
            "max_native_calls": 24,
            "max_leaf_executions": 2,
            "requires_parent_clearance": True,
            "seed_zero_omissions": "stop: standalone seed did not reproduce",
            "accept_reduction": "at least one actual spring omission in four attempts",
            "stop_on_one_component_reproduction": True,
        },
    }
    started = time.perf_counter()
    baseline_setup = None
    pid = hwnd = None
    try:
        report["source_code"] = [
            _identity(Path(__file__)),
            _identity(Path(__file__).with_name("draw_sm_summing_assembly.py")),
        ]
        pid = adapter.swApp.GetProcessID()
        hwnd = forensics._frame_hwnd(adapter)
        report["held_seat_pid"] = pid
        report["cached_window_handle"] = hwnd
        if type(pid) is not int or pid <= 0 or type(hwnd) is not int or hwnd <= 0:
            raise RuntimeError("unreadable held-seat PID/window")
        for index, arm in enumerate(SEQUENCE, start=1):
            row = {
                "index": index,
                "arm": arm,
                "started_utc": datetime.now(UTC).isoformat(),
                "native_calls": 0,
                "treatment_calls": 0,
                "observer_ms": 0.0,
                "secondary_errors": [],
                "option_comparison_failures": [],
                "comparison_ineligible": False,
            }
            report["arms"].append(row)
            arm_started = time.perf_counter()
            try:
                discard_open_documents(adapter)
                view, table, items = await prepare()
                view = _early_bound(view, "IView")
                if _early_bound(adapter.currentModel, "IModelDoc2").GetPathName() != "":
                    raise RuntimeError("diagnostic drawing is not fresh/unsaved")
                if adapter.swApp.GetProcessID() != pid:
                    raise RuntimeError("held SolidWorks process changed")
                observer_started = time.perf_counter()
                leaves = balloons._view_component_leaves(adapter, view, label=LABEL)
                allowed = {
                    item: [
                        leaf.path
                        for leaf in balloons._shown_instances(
                            leaves, stem, anchors[stem], label=LABEL
                        )
                    ]
                    for stem, item in items
                }
                setup = {
                    "source": _identity(source),
                    "pose": _pose(view),
                    "allowed_owners": allowed,
                    "items": items,
                }
                row["setup"] = setup
                row["before"] = _link_state(view, table, bom_cells)
                matched = {
                    **setup,
                    "semantic_link_config_grid": _semantic(row["before"]),
                }
                if baseline_setup is None:
                    baseline_setup = matched
                elif matched != baseline_setup:
                    raise RuntimeError(
                        "pre-treatment source/pose/owners/link/config/BOM grid drift"
                    )
                row["observer_ms"] += (time.perf_counter() - observer_started) * 1000
                helper_started = time.perf_counter()
                try:
                    _call_once(
                        adapter,
                        view,
                        row,
                        report["arms"][0] if index > 1 else None,
                        out_dir,
                        hwnd,
                    )
                finally:
                    row["full_helper_ms"] = (
                        time.perf_counter() - helper_started
                    ) * 1000
                observer_started = time.perf_counter()
                row["raw_coverage"] = _coverage(row["raw_notes"], allowed)
                row["inventory_coverage"] = _coverage(row["inventory"], allowed)
                row["restored_coverage"] = _coverage(
                    row.get("restored_inventory", []), allowed
                )
                row["post_call_state"] = _link_state(view, table, bom_cells)
                row["post_call_pose"] = _pose(view)
                row["post_call_source"] = _identity(source)
                if (
                    row["post_call_state"] != row["before"]
                    or row["post_call_pose"] != setup["pose"]
                    or row["post_call_source"] != setup["source"]
                ):
                    raise RuntimeError(
                        "post-call link/config/BOM grid/pose/source drift"
                    )
                row["resolution_post_call"] = {}
                for name in ("IsLightweight", "IsModelLoaded"):
                    try:
                        value = getattr(view, name)()
                        if type(value) is not bool:
                            raise ValueError(f"non-boolean {name}: {value!r}")
                        row["resolution_post_call"][name] = value
                    except Exception as error:
                        row["resolution_post_call"][name + "_error"] = _error(error)
                row["row_components"] = _row_components(
                    table, row["post_call_state"], bom_column
                )
                row["association_verified"] = all(
                    "error" not in association
                    and association["components"]
                    and all(
                        not any(key.endswith("_error") for key in component)
                        and component["name"].replace("\\", "/").casefold()
                        in {owner.casefold() for owner in allowed[association["item"]]}
                        and component["excluded_from_parent_bom"] == [False]
                        for component in association["components"]
                    )
                    for association in row["row_components"]
                )
                row["observer_ms"] += (time.perf_counter() - observer_started) * 1000
                _terminal_output(
                    adapter, view, row, out_dir,
                    layout=layout, sheet_layouts=sheet_layouts,
                )
                row["terminal_source"] = _identity(source)
                row["terminal_source_changed"] = (
                    row["terminal_source"] != row["post_call_source"]
                )
                if "inventory" in row["terminal_quality"]:
                    row["terminal_coverage"] = _coverage(
                        row["terminal_quality"]["inventory"], allowed
                    )
            except BaseException as error:
                row["error"] = _error(error)
                raise
            finally:
                row["full_arm_ms"] = (time.perf_counter() - arm_started) * 1000
                row["finished_utc"] = datetime.now(UTC).isoformat()
    except BaseException as error:
        report["errors"].append(_error(error))
    finally:
        try:
            discard_open_documents(adapter)
        except BaseException as error:
            report["errors"].append("final discard: " + _error(error))
        report["coverage_interpretation"] = _interpret(report["arms"])
        if report["errors"]:
            report["coverage_interpretation"] = (
                "inconclusive: setup/native/cleanup failure"
            )
        report["quality_interpretation"] = _quality_interpret(report["arms"])
        report["interpretation"] = (
            report["coverage_interpretation"] + "; " + report["quality_interpretation"]
        )
        report["fallback_required"] = (
            not report["coverage_interpretation"].startswith("supports candidate")
            or not all(
                row.get("restoration_quality_verified", False)
                for row in report["arms"]
            )
        )
        report["visible_landing_verified"] = False
        report["next_action"] = (
            "separately cleared minimum-part native repro; no further variants"
            if report["fallback_required"]
            else "parent inspect passive images/PDF render; no fix claim before review"
        )
        report["native_calls"] = sum(row["native_calls"] for row in report["arms"])
        report["full_probe_ms"] = (time.perf_counter() - started) * 1000
        report["finished_utc"] = datetime.now(UTC).isoformat()
        try:
            Path(report["report_path"]).write_text(
                json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
            )
        except BaseException as error:
            report["errors"].append("report write: " + _error(error))
            raise SmWireframeProbeStop(report) from error
    raise SmWireframeProbeStop(report)
