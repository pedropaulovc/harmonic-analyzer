"""Issue-1667 SM EDGE/FACE/FACE/EDGE diagnostic ONLY; NEVER MERGE.

Four fresh production-prepared SM drawings, one held PID, one AutoBalloon5 call
per drawing. Both attachment modes borrow the same Normal mapping. Observations
are post-call (never proof of in-call display/eligibility), and no sheet is saved
or exported. Even a fully qualified contrast ends in diagnostic STOP.
"""

from __future__ import annotations

import math
from pathlib import Path
from sys import exception as _active_exception
import time
from typing import Any, Awaitable, Callable, NoReturn, Sequence

from solidworks_mcp.adapters import sw_type_info
from solidworks_mcp.adapters.solidworks import drawing as sw_drawing

from _com import _early_bound
import _drawing_balloons as balloons
from _drawing_group_perf_probe import (
    _empty_documents,
    _file_identity,
    _preference,
    assert_matched_setup,
)
import _seat_forensics as forensics
from _session import discard_open_documents


SEQUENCE = ("edge", "face", "face", "edge")
LABEL = "summing exploded-view BOM coverage"
SPRING = "sm-vn-counter-spring"
# The actual SM preparer already resolves ten families. These bounds only limit
# observational work; exceeding one aborts rather than silently truncating proof.
MAX_VIEW_NOTES = 64
MAX_TREE_NODES = 128
MAX_SPRING_INSTANCES = 8
MAX_SPRING_EDGES = 64


class SmAttachmentCandidateInvalid(RuntimeError):
    """An observed coverage/attachment/layout failure, not a native exception."""


class SmAttachmentProbeStop(RuntimeError):
    """Reports were retained; this deliberate failure cannot publish a drawing."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        super().__init__(
            "INTENTIONAL SM ATTACHMENT DIAGNOSTIC STOP before save/export/cache "
            f"publication; status={report['status']}; report={report['report_path']}"
        )


def _owner(entity: Any) -> str:
    """Existing IEntity ownership route, without swallowing unexpected COM errors."""
    if entity is None:
        return ""
    entity = _early_bound(balloons._bind(entity, "IEntity"), "IEntity")
    component = entity.GetComponent()
    if component is None:
        return ""
    path = _early_bound(component, "IComponent2").Name2
    if type(path) is not str:
        raise RuntimeError("SM contrast: component Name2 is not a string")
    return path.replace("\\", "/")


def _allowed_shown_owners(
    view: Any, items: Sequence[tuple[str, str]]
) -> dict[str, set[str]]:
    """Production leaf-family/ancestor-visibility rules, but native errors abort."""
    root = _early_bound(view, "IView").RootDrawingComponent2(False)
    if root is None:
        raise RuntimeError("SM contrast: drawing view has no root component")
    stems = frozenset(stem for stem, _item in items)
    allowed: dict[str, set[str]] = {stem: set() for stem in stems}
    pending = [(child, True) for child in balloons._drawing_component_children(root)]
    visited = 0
    while pending:
        drawing_component, ancestor_shown = pending.pop()
        visited += 1
        if visited > MAX_TREE_NODES:
            raise RuntimeError("SM contrast: shown-owner tree exceeded fixed bound")
        visible = drawing_component.Visible
        if type(visible) is not bool:
            raise RuntimeError("SM contrast: unreadable drawing-component visibility")
        shown = ancestor_shown and visible
        children = balloons._drawing_component_children(drawing_component)
        pending.extend((child, shown) for child in children)
        if children:
            continue
        name = drawing_component.Name
        if type(name) is not str:
            raise RuntimeError("SM contrast: unreadable drawing-component name")
        component = drawing_component.Component
        if component is None:
            raise RuntimeError("SM contrast: leaf drawing component has no component")
        component = _early_bound(component, "IComponent2")
        native_path = component.GetPathName()
        path = component.Name2
        if type(native_path) is not str or type(path) is not str or not path:
            raise RuntimeError("SM contrast: unreadable component file/full instance")
        identities = frozenset(
            {
                Path(native_path).stem.casefold(),
                balloons._instance_name(name).casefold(),
            }
        )
        for stem in balloons._stems_matching(identities, stems):
            if shown:
                allowed[stem].add(path.replace("\\", "/").casefold())
    if any(not paths for paths in allowed.values()):
        raise RuntimeError(f"SM contrast: missing shown BOM family owners: {allowed!r}")
    return allowed


def _note_snapshot(raw_note: Any) -> dict[str, Any]:
    note = _early_bound(raw_note, "INote")
    name = note.GetName()
    item = note.GetBomBalloonText(True)
    is_bom = note.IsBomBalloon()
    if type(is_bom) is not bool:
        raise RuntimeError("SM contrast: IsBomBalloon did not return a bool")
    if type(name) is not str or not name or type(item) is not str:
        raise RuntimeError("SM contrast: unreadable native note identity/BOM text")
    row: dict[str, Any] = {
        "note_name": name,
        "bom_text_raw": item,
        "item": item.strip(),
        "is_bom_balloon": is_bom,
    }
    annotation = note.GetAnnotation()
    if annotation is None:
        row.update(annotation_name=None, entity_count=0, attachment_types=[], owners=[])
        return row
    annotation = _early_bound(annotation, "IAnnotation")
    annotation_name = annotation.GetName()
    if type(annotation_name) is not str or not annotation_name:
        raise RuntimeError("SM contrast: unreadable native annotation identity")
    entities = tuple(annotation.GetAttachedEntities3() or ())
    kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
    # Only actual EDGE/FACE objects support this owner route. Unsupported/null
    # attachments are retained as invalid candidates, not queried as IEntity.
    supported = {
        sw_type_info.constant("swSelEDGES"),
        sw_type_info.constant("swSelFACES"),
    }
    owners = [
        _owner(entity) if index < len(kinds) and kinds[index] in supported else ""
        for index, entity in enumerate(entities)
    ]
    row.update(
        annotation_name=annotation_name,
        entity_count=len(entities),
        attachment_types=list(kinds),
        owners=owners,
    )
    return row


def _view_inventory(view: Any) -> tuple[tuple[Any, ...], list[dict[str, Any]]]:
    """Actual BOM objects and identities, independent of the returned array."""
    notes = tuple(_early_bound(view, "IView").GetNotes() or ())
    if len(notes) > MAX_VIEW_NOTES:
        raise RuntimeError("SM contrast: view-note census exceeded fixed bound")
    inventory = []
    bom_notes = []
    for raw_note in notes:
        note = _early_bound(raw_note, "INote")
        is_bom = note.IsBomBalloon()
        if type(is_bom) is not bool:
            raise RuntimeError("SM contrast: IsBomBalloon did not return a bool")
        if is_bom:
            bom_notes.append(note)
            inventory.append(_note_snapshot(note))
    return tuple(bom_notes), inventory


def _spring_census(adapter: Any, view: Any) -> list[dict[str, Any]]:
    """Spring-only tree/visible-edge evidence; no picking, sampling or redraw."""
    view = _early_bound(view, "IView")
    root = view.RootDrawingComponent2(False)
    if root is None:
        raise RuntimeError("SM contrast: drawing view lost its root component")
    pending = [(root, [])]
    visited = 0
    rows = []
    edge_kind = sw_type_info.constant("swViewEntityType_Edge")
    while pending:
        component, ancestors = pending.pop()
        visited += 1
        if visited > MAX_TREE_NODES:
            raise RuntimeError("SM contrast: spring tree census exceeded fixed bound")
        name = component.Name
        visible = component.Visible
        if type(name) is not str or type(visible) is not bool:
            raise RuntimeError("SM contrast: unreadable drawing-component tree state")
        chain = [*ancestors, {"drawing_component": name, "visible": visible}]
        children = balloons._drawing_component_children(component)
        pending.extend((child, chain) for child in children)
        if children or not balloons._stems_matching(
            frozenset({balloons._instance_name(name).casefold()}), frozenset({SPRING})
        ):
            continue
        if len(rows) >= MAX_SPRING_INSTANCES:
            raise RuntimeError(
                "SM contrast: spring instance census exceeded fixed bound"
            )
        model_component = component.Component
        if model_component is None:
            raise RuntimeError("SM contrast: spring drawing component has no component")
        model_component = _early_bound(model_component, "IComponent2")
        path = model_component.Name2
        if type(path) is not str or not path:
            raise RuntimeError("SM contrast: spring has no full instance identity")
        count = int(view.GetVisibleEntityCount2(model_component, edge_kind))
        row = {
            "instance": path.replace("\\", "/"),
            "ancestor_visibility": chain,
            # Match _view_component_leaves: its shown rule starts at the root's
            # children. Retain the root flag, but do not treat it as leaf ink.
            "root_flag_included_in_shown_rule": False,
            "tree_visible": all(entry["visible"] for entry in chain[1:]),
            "visible_edge_count": count,
        }
        rows.append(row)
        if count < 0:
            raise RuntimeError("SM contrast: negative visible-edge count")
        if count > MAX_SPRING_EDGES:
            row["visible_entities_status"] = "not_fetched_count_exceeds_fixed_bound"
            continue
        # Existing raw bridge is GetVisibleEntities2 without eager per-edge
        # Dispatch wrapping. Bind only the bounded spring array, for owner reads.
        raw = sw_drawing.raw_visible_entities(view, model_component, edge_kind)
        row["visible_entities_raw_count"] = len(raw)
        if len(raw) > MAX_SPRING_EDGES:
            raise RuntimeError("SM contrast: spring edge array exceeded fixed bound")
        row["visible_edge_owners"] = [
            _owner(sw_drawing.bind_view_entity(edge, edge_kind)) for edge in raw
        ]
        row["count_matches_array"] = count == len(raw)
    if not rows:
        raise RuntimeError("SM contrast: spring missing from drawing-component tree")
    return rows


def _collect_stage(
    adapter: Any,
    view: Any,
    returned: tuple[Any, ...],
    *,
    stage: str,
    out_dir: Path,
    cached_hwnd: int | None,
    row: dict[str, Any],
) -> tuple[Any, ...]:
    """Passive pixels FIRST; every subsequent COM read is labelled post-passive."""
    started = time.perf_counter()
    snapshot: dict[str, Any] = {
        "stage": stage,
        "identity_boundary": "post-passive-pixels; not instantaneous or in-call proof",
        "status": "unread",
    }
    row.setdefault("observations", []).append(snapshot)
    try:
        snapshot["passive_pixels"] = forensics._write_artefacts(
            (
                (
                    "desktop_png",
                    lambda: forensics._grab_screen(out_dir / f"{stage}-desktop.png"),
                ),
                (
                    "window_png",
                    lambda: forensics._grab_screen(
                        out_dir / f"{stage}-window.png", window=cached_hwnd or 0
                    ),
                ),
            )
        )
        if len(returned) > MAX_VIEW_NOTES:
            raise RuntimeError("SM contrast: returned-note census exceeded fixed bound")
        snapshot["returned_notes"] = []
        for note in returned:
            snapshot["returned_notes"].append(_note_snapshot(note))
        inventory_notes, snapshot["view_bom_inventory"] = _view_inventory(view)
        snapshot["spring"] = _spring_census(adapter, view)
        snapshot["drawing_pick_state"] = forensics.drawing_pick_state(adapter, view)
        # Reuse the existing read-only display bag; it records unreadable window
        # state explicitly. Neither this nor the spring census proves call state.
        snapshot["display_geometry"], _seat = forensics._display_bags(adapter)
        returned_keys = {
            (note["note_name"], note["annotation_name"])
            for note in snapshot["returned_notes"]
        }
        inventory_keys = {
            (note["note_name"], note["annotation_name"])
            for note in snapshot["view_bom_inventory"]
        }
        snapshot["view_only_annotation_identities"] = sorted(
            inventory_keys - returned_keys, key=str
        )
        snapshot["returned_only_annotation_identities"] = sorted(
            returned_keys - inventory_keys, key=str
        )
        snapshot["status"] = "captured"
        return inventory_notes
    except BaseException as error:
        snapshot["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        snapshot["observer_ms"] = (time.perf_counter() - started) * 1000.0


def _call_once(
    adapter: Any,
    view: Any,
    *,
    row: dict[str, Any],
    baseline: dict[str, Any] | None,
    out_dir: Path,
) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    balloons._activate_and_select_view(adapter, view, label=LABEL)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    options = ddoc.CreateAutoBalloonOptions()
    if options is None:
        raise RuntimeError("SM contrast: CreateAutoBalloonOptions returned null")
    options = sw_type_info.early_bound_or_flag(options, "IAutoBalloonOptions")
    authored = {
        "Layout": 1,
        "ReverseDirection": False,
        "IgnoreMultiple": True,
        "InsertMagneticLine": False,
        "LeaderAttachmentToFaces": row["attachment"] == "face",
        "Style": 1,
        "Size": 2,
        "UpperTextContent": 1,
        "ItemNumberStart": 1,
        "ItemNumberIncrement": 1,
        "ItemOrder": 1,
    }
    for name, value in authored.items():
        setattr(options, name, value)
    # Preserve the production setter-only option path before AutoBalloon5.
    # Readbacks/default observations happen only after passive post-call pixels.
    row["authored_native_options"] = authored
    # Resolve this before the call: no HWND/COM lookup precedes passive pixels.
    cached_hwnd = forensics._frame_hwnd(adapter)
    row["cached_pre_call_hwnd"] = cached_hwnd
    extension = _early_bound(draw.Extension, "IModelDocExtension")
    preference = sw_type_info.constant("swLineFontVisibleEdgesThickness")
    option = sw_type_info.constant("swDetailingNoOptionSpecified")
    normal = sw_type_info.constant("swLW_NORMAL")
    original = row["preference_before"]["slot"]
    guard = row["normal_mapping_guard"] = {
        "original_slot": original,
        "normal_slot": normal,
    }
    # The same guard encloses BOTH EDGE and FACE. Restoration precedes the same
    # existing ClearSelection2/EditRebuild3 boundary, without extra native calls.
    try:
        started = time.perf_counter()
        result = extension.SetUserPreferenceInteger(preference, option, normal)
        guard["normal_set_return"] = result
        guard["normal_readback_slot"] = int(
            extension.GetUserPreferenceInteger(preference, option)
        )
        guard["enter_ms"] = (time.perf_counter() - started) * 1000.0
        if result is not True or guard["normal_readback_slot"] != normal:
            raise RuntimeError(
                "SM contrast: Normal visible-edge mapping was not applied"
            )
        started = time.perf_counter()
        try:
            raw = ddoc.AutoBalloon5(options)
        finally:
            # End before even Python array metadata or passive observers.
            row["native_call_ms"] = (time.perf_counter() - started) * 1000.0
        row["raw_return"] = {
            "python_type": f"{type(raw).__module__}.{type(raw).__qualname__}",
            "count": len(raw) if type(raw) in (tuple, list) else None,
            "boundary": "post-call Python metadata before passive pixels",
        }
        if raw is not None and type(raw) not in (tuple, list):
            raise RuntimeError("SM contrast: AutoBalloon5 returned a non-array shape")
        returned = tuple(raw) if raw is not None else ()
        _collect_stage(
            adapter,
            view,
            returned,
            stage="post_call_pre_restore_pre_rebuild",
            out_dir=out_dir,
            cached_hwnd=cached_hwnd,
            row=row,
        )
        observed_started = time.perf_counter()
        row["native_options"] = {}
        row["unmodified_native_options"] = {}
        row["option_candidate_failures"] = []
        row["option_comparison_failures"] = []
        row["option_observation_stage"] = (
            "post-call/post-passive/pre-restoration/pre-rebuild; NOT in-call proof"
        )
        for name in (
            *authored,
            "CustomSize",
            "EditBalloonOption",
            "EditBalloons",
            "Layername",
            "LowerText",
            "LowerTextContent",
            "UpperText",
            "FirstItem",
        ):
            target = (
                row["native_options"]
                if name in authored
                else row["unmodified_native_options"]
            )
            try:
                value = getattr(options, name)
            except Exception as error:
                # Optional metadata cannot replace the already-retained native
                # outcome or prevent the remaining predeclared calls.
                target[name] = {
                    "status": "unreadable",
                    "error": f"{type(error).__name__}: {error}",
                }
                row["option_comparison_failures"].append(f"{name}: unreadable")
                continue
            if (value is None or type(value) in (str, int, bool, float)) and not (
                type(value) is float and not math.isfinite(value)
            ):
                target[name] = value
                if name in authored and (
                    type(value) is not type(authored[name]) or value != authored[name]
                ):
                    row["option_candidate_failures"].append(
                        f"post-call authored option mismatch: {name}={value!r}"
                    )
            else:
                target[name] = {
                    "status": "unresolved_not_comparable",
                    "python_type": f"{type(value).__module__}.{type(value).__qualname__}",
                }
                row["option_comparison_failures"].append(
                    f"{name}: opaque/nonfinite post-call value; not compared"
                )
        if baseline is not None:
            if baseline["option_comparison_failures"]:
                row["option_comparison_failures"].append(
                    "baseline post-call options were not comparable"
                )
            elif not row["option_comparison_failures"]:
                for name in authored:
                    if name != "LeaderAttachmentToFaces" and (
                        row["native_options"][name] != baseline["native_options"][name]
                    ):
                        row["option_comparison_failures"].append(
                            f"post-call options differ beyond attachment: {name}"
                        )
                if (
                    row["unmodified_native_options"]
                    != baseline["unmodified_native_options"]
                ):
                    row["option_comparison_failures"].append(
                        "post-call unmodified native-option observations differ"
                    )
        row["option_observer_ms"] = (time.perf_counter() - observed_started) * 1000.0
    finally:
        primary = _active_exception()
        started = time.perf_counter()
        try:
            result = extension.SetUserPreferenceInteger(preference, option, original)
            guard["restore_set_return"] = result
            guard["restore_readback_slot"] = int(
                extension.GetUserPreferenceInteger(preference, option)
            )
            if result is not True or guard["restore_readback_slot"] != original:
                raise RuntimeError(
                    "SM contrast: visible-edge mapping restoration failed"
                )
        except BaseException as error:
            guard["restore_error"] = f"{type(error).__name__}: {error}"
            if primary is None:
                raise
            primary.add_note(f"SM contrast additional restoration failure: {error}")
        finally:
            guard["restore_ms"] = (time.perf_counter() - started) * 1000.0
    _collect_stage(
        adapter,
        view,
        returned,
        stage="post_restore_pre_existing_rebuild",
        out_dir=out_dir,
        cached_hwnd=cached_hwnd,
        row=row,
    )
    started = time.perf_counter()
    draw.ClearSelection2(True)
    if draw.EditRebuild3() is not True:
        raise RuntimeError("SM contrast: existing post-call drawing rebuild failed")
    row["existing_rebuild_ms"] = (time.perf_counter() - started) * 1000.0
    inventory_notes = _collect_stage(
        adapter,
        view,
        returned,
        stage="post_restore_post_existing_rebuild",
        out_dir=out_dir,
        cached_hwnd=cached_hwnd,
        row=row,
    )
    row["returned_snapshot_changed_across_existing_rebuild"] = (
        row["observations"][0]["returned_notes"]
        != row["observations"][-1]["returned_notes"]
    )
    return returned, inventory_notes


def _validate_snapshots(
    snapshots: Sequence[dict[str, Any]],
    *,
    items: Sequence[tuple[str, str]],
    allowed: dict[str, set[str]],
    attachment: str,
) -> tuple[list[int], list[str]]:
    expected = {item: stem for stem, item in items}
    kind = sw_type_info.constant("swSelFACES" if attachment == "face" else "swSelEDGES")
    seen: set[str] = set()
    names: set[str] = set()
    valid_indices = []
    failures = []
    for index, snapshot in enumerate(snapshots):
        item = snapshot["item"]
        name = snapshot["note_name"]
        stem = expected.get(item)
        owners = snapshot["owners"]
        if stem is None or item in seen or name in names:
            failures.append(f"unexpected/duplicate item or note: {snapshot!r}")
        elif (
            not snapshot["is_bom_balloon"]
            or snapshot["entity_count"] != 1
            or snapshot["attachment_types"] != [kind]
            or len(owners) != 1
            or owners[0].casefold() not in allowed[stem]
        ):
            failures.append(
                f"invalid {attachment.upper()} attachment/full shown owner: {snapshot!r}"
            )
        else:
            valid_indices.append(index)
        seen.add(item)
        names.add(name)
    missing = sorted(expected.keys() - seen)
    if missing:
        failures.append(f"missing native BOM items {missing!r}")
    return valid_indices, failures


async def run_sm_attachment_probe(
    adapter: Any,
    *,
    template: Path,
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
    """Fixed SM-only coverage contrast; known invalid arms continue, errors abort."""
    out_dir = forensics._capture_dir("1667-sm-edge-face-fixed-contrast")
    report: dict[str, Any] = {
        "diagnostic_only": True,
        "never_merge": True,
        "status": "aborted",
        "sequence": SEQUENCE,
        "report_path": str(out_dir / "capture.json"),
        "proof_scope": "post-helper diagnostic owner/circle/field/BOM/caption only; NOT full-sheet/PDF/machinist proof",
        "observer_limit": "all scene/identity evidence is post-call; no observation proves native in-call state",
        "no_save_export_or_publication": True,
        "arms": [
            {"order": order, "attachment": arm, "status": "not_reached"}
            for order, arm in enumerate(SEQUENCE, start=1)
        ],
    }
    baseline = None
    started = time.perf_counter()
    try:
        seat_pid = int(adapter.swApp.GetProcessID())
        if seat_pid <= 0:
            raise RuntimeError("SM contrast: invalid SolidWorks PID")
        report["seat_pid"] = seat_pid
        report["source"] = _file_identity(Path(__file__))
        report["native_helper_source"] = _file_identity(Path(balloons.__file__))
        report["preparer_source"] = _file_identity(
            Path(prepare_arm.__code__.co_filename)
        )
        report["seat_provenance"] = forensics.seat_provenance(adapter)
        for row in report["arms"]:
            phase = "setup"
            post_helper_started: float | None = None
            try:
                row["documents_before"] = _empty_documents(adapter)
                if int(adapter.swApp.GetProcessID()) != seat_pid:
                    raise RuntimeError("SM contrast: seat changed before setup")
                row["template"] = _file_identity(template)
                view, items, finish_bounds = await prepare_arm(adapter, row)
                row["drawing_title"] = str(adapter.currentModel.GetTitle() or "")
                if (
                    not row["drawing_title"]
                    or adapter.currentModel.GetPathName()
                    or int(adapter.currentModel.GetType()) != 3
                ):
                    raise RuntimeError(
                        "SM contrast: preparer did not create a fresh unsaved drawing"
                    )
                if int(adapter.swApp.GetProcessID()) != seat_pid:
                    raise RuntimeError("SM contrast: seat changed during setup")
                row["items"] = list(items)
                if (
                    len(items) != 10
                    or len(dict(items)) != 10
                    or len({item for _stem, item in items}) != 10
                    or SPRING not in dict(items)
                ):
                    raise RuntimeError(
                        "SM contrast: expected exactly ten unique SM BOM families/items"
                    )
                row["preference_before"] = _preference(adapter)
                assert_matched_setup(row["setup"], row["setup"])
                if baseline is not None:
                    for key in (
                        "template",
                        "native_inputs",
                        "items",
                        "preference_before",
                    ):
                        if row[key] != baseline[key]:
                            raise RuntimeError(
                                f"SM contrast: matched context differs: {key}"
                            )
                    assert_matched_setup(row["setup"], baseline["setup"])
                allowed = _allowed_shown_owners(view, items)
                row["allowed_full_shown_owners"] = {
                    stem: sorted(paths) for stem, paths in allowed.items()
                }
                if (
                    baseline is not None
                    and row["allowed_full_shown_owners"]
                    != baseline["allowed_full_shown_owners"]
                ):
                    raise RuntimeError("SM contrast: shown component owners differ")
                phase = "native_and_observers"
                returned, inventory_notes = _call_once(
                    adapter,
                    view,
                    row=row,
                    baseline=baseline,
                    out_dir=out_dir / f"{row['order']:02d}-{row['attachment']}",
                )
                if baseline is None:
                    baseline = row
                phase = "post_helper_diagnostic_proof"
                post_helper_started = time.perf_counter()
                settled = row["observations"][-1]
                current_allowed = _allowed_shown_owners(view, items)
                row["post_helper_full_shown_owners"] = {
                    stem: sorted(paths) for stem, paths in current_allowed.items()
                }
                if current_allowed != allowed:
                    raise RuntimeError(
                        "SM contrast: component visibility/identity changed"
                    )
                _indices, failures = _validate_snapshots(
                    settled["returned_notes"],
                    items=items,
                    allowed=allowed,
                    attachment=row["attachment"],
                )
                failures.extend(row["option_candidate_failures"])
                expected = dict((item, stem) for stem, item in items)
                indices, inventory_failures = _validate_snapshots(
                    settled["view_bom_inventory"],
                    items=items,
                    allowed=allowed,
                    attachment=row["attachment"],
                )
                landings = [
                    balloons.BalloonLanding(
                        stem=expected[settled["view_bom_inventory"][index]["item"]],
                        instance=settled["view_bom_inventory"][index]["owners"][0],
                        note=inventory_notes[index],
                        sheet_xy=None,
                        label=LABEL,
                    )
                    for index in indices
                ]
                failures.extend(
                    f"actual view inventory: {error}" for error in inventory_failures
                )
                if (
                    settled["view_only_annotation_identities"]
                    or settled["returned_only_annotation_identities"]
                ):
                    failures.append(
                        "native return and actual view annotation identities differ"
                    )
                row["bounds_actual_inventory_candidates"] = len(landings)
                row["bounds_actual_inventory_total"] = len(inventory_notes)
                proof_started = time.perf_counter()
                try:
                    finish_bounds(adapter, landings)
                except SmAttachmentCandidateInvalid as error:
                    failures.append(f"layout: {error}")
                finally:
                    row["bounds_observer_ms"] = (
                        time.perf_counter() - proof_started
                    ) * 1000.0
                final_rows = [_note_snapshot(note) for note in returned]
                _indices, final_failures = _validate_snapshots(
                    final_rows,
                    items=items,
                    allowed=allowed,
                    attachment=row["attachment"],
                )
                row["post_caption_rebuild_returned_notes"] = final_rows
                failures.extend(
                    f"post-caption rebuild: {error}" for error in final_failures
                )
                _final_notes, final_inventory = _view_inventory(view)
                row["post_caption_rebuild_view_bom_inventory"] = final_inventory
                _indices, final_inventory_failures = _validate_snapshots(
                    final_inventory,
                    items=items,
                    allowed=allowed,
                    attachment=row["attachment"],
                )
                failures.extend(
                    f"post-caption actual view inventory: {error}"
                    for error in final_inventory_failures
                )
                row["post_helper_proof_ms"] = (
                    time.perf_counter() - post_helper_started
                ) * 1000.0
                row["candidate_failures"] = failures
                row["options_comparison_eligible"] = not row[
                    "option_comparison_failures"
                ]
                row["status"] = (
                    "invalid_candidate"
                    if failures
                    else "qualified"
                    if row["options_comparison_eligible"]
                    else "comparison_ineligible"
                )
                phase = "post_arm_identity"
                if _preference(adapter) != row["preference_before"]:
                    raise RuntimeError("SM contrast: visible-edge preferences changed")
                if (
                    str(adapter.currentModel.GetTitle() or "") != row["drawing_title"]
                    or adapter.currentModel.GetPathName()
                    or int(adapter.currentModel.GetType()) != 3
                ):
                    raise RuntimeError("SM contrast: drawing identity changed")
            except BaseException as error:
                row.update(
                    status="aborted",
                    failure_phase=phase,
                    error=f"{type(error).__name__}: {error}",
                )
                raise
            finally:
                if (
                    post_helper_started is not None
                    and "post_helper_proof_ms" not in row
                ):
                    row["post_helper_proof_ms"] = (
                        time.perf_counter() - post_helper_started
                    ) * 1000.0
                primary = _active_exception()
                try:
                    discard_open_documents(adapter)
                    adapter.currentModel = None
                    row["cleanup"] = _empty_documents(adapter)
                    if int(adapter.swApp.GetProcessID()) != seat_pid:
                        raise RuntimeError("SM contrast: seat changed during cleanup")
                    if _file_identity(template) != row.get("template"):
                        raise RuntimeError("SM contrast: template bytes changed")
                    for identity in row.get("native_inputs", {}).get("files", ()):
                        if _file_identity(Path(identity["path"])) != identity:
                            raise RuntimeError(
                                f"SM contrast: native source changed: {identity['path']}"
                            )
                    for key in ("source", "native_helper_source", "preparer_source"):
                        identity = report[key]
                        if _file_identity(Path(identity["path"])) != identity:
                            raise RuntimeError(
                                f"SM contrast: diagnostic source changed: {key}"
                            )
                except BaseException as error:
                    row.update(
                        status="aborted",
                        cleanup_error=f"{type(error).__name__}: {error}",
                    )
                    if primary is None:
                        raise
                    primary.add_note(
                        f"SM contrast additional cleanup/identity failure: {error}"
                    )
                finally:
                    write_primary = _active_exception()
                    try:
                        forensics._write_failure_report(
                            out_dir / f"{row['order']:02d}-{row['attachment']}", row
                        )
                    except BaseException as error:
                        if write_primary is None:
                            raise
                        write_primary.add_note(
                            f"SM contrast arm-report write failed: {error}"
                        )
        report["status"] = (
            "completed"
            if all(row["status"] == "qualified" for row in report["arms"])
            else "completed_with_unqualified_arms"
        )
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        qualified = all(row["status"] == "qualified" for row in report["arms"])
        report["summary"] = {
            "scope": "coverage contrast, NOT a production performance/speedup claim",
            "complete_qualified_contrast": qualified,
            "samples": [
                {
                    "order": row["order"],
                    "attachment": row["attachment"],
                    "status": row["status"],
                    "native_call_ms": row.get("native_call_ms"),
                    "post_call_observer_ms": (
                        sum(
                            stage["observer_ms"]
                            for stage in row.get("observations", ())
                        )
                        + row.get("option_observer_ms", 0.0)
                        + row.get("post_helper_proof_ms", 0.0)
                    ),
                    "normal_mapping_enter_ms": row.get("normal_mapping_guard", {}).get(
                        "enter_ms"
                    ),
                    "normal_mapping_restore_ms": row.get(
                        "normal_mapping_guard", {}
                    ).get("restore_ms"),
                    "existing_rebuild_ms": row.get("existing_rebuild_ms"),
                }
                for row in report["arms"]
            ],
            "edge_native_call_mean_ms": sum(
                row["native_call_ms"]
                for row in report["arms"]
                if row["attachment"] == "edge"
            )
            / 2.0
            if qualified
            else None,
            "face_native_call_mean_ms": sum(
                row["native_call_ms"]
                for row in report["arms"]
                if row["attachment"] == "face"
            )
            / 2.0
            if qualified
            else None,
        }
        report["elapsed_ms"] = (time.perf_counter() - started) * 1000.0
        primary = _active_exception()
        try:
            forensics._write_failure_report(out_dir, report)
        except BaseException as error:
            if primary is None:
                raise
            primary.add_note(f"SM contrast final-report write failed: {error}")
    raise SmAttachmentProbeStop(report)
