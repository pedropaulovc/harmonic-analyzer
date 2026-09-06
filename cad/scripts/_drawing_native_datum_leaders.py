"""One measured document-length prepass for explicitly opted-in bent datums.

The saved-rocker ``probe_datum_shoulder.py --mode document_length`` is the native
positive control: preference swDetailingAnnotationBentLeaderLength moves the
left/right datum frame by the signed length delta, leaving the elbow and exact
model attachment fixed. IAnnotation.BentLeaderLength stayed -1 in that control;
it is neither a fallback trigger nor the setter used here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping
from xml.etree import ElementTree

from _common import _early_bound
from _drawing_annotation_bounds import _installed_swconst, _native_snapshot
from _drawing_view_packing import Rect
from _drawing_native_callouts import (
    BentShoulder,
    DatumLeaderPolicy,
    Direction,
    GtolPlacement,
    SymbolPlacement,
    _Symbol,
    _clear,
    _final_symbol,
    _past,
    _read_obstacles,
    _read_symbol,
    _same_obstacles,
    _same_symbol,
    _visible_annotations,
)
import _telemetry


@dataclass(frozen=True)
class _Bank:
    view: Any
    context: tuple
    symbols: dict
    obstacles: dict
    gtol_xml: dict


def _direction_delta(shoulder: BentShoulder, increase: float):
    return (-increase if shoulder.direction is Direction.LEFT else increase), 0.0


def required_increase(
    symbol: _Symbol,
    outline: Rect,
    obstacles,
    gap_m: float,
    *,
    minimum_increase: float = 0.0,
) -> float:
    """A monotone extension along the native shoulder, not a coordinate pick."""
    shoulder = symbol.bent_shoulder
    if shoulder is None or shoulder.direction not in (Direction.LEFT, Direction.RIGHT):
        raise RuntimeError("document length needs a measured horizontal datum shoulder")
    delta = _direction_delta(shoulder, minimum_increase)
    extra = _past(symbol.body.translated(delta), outline, shoulder.direction, gap_m)
    delta = delta[0] + extra[0], 0.0
    for _ in range(len(obstacles) + 1):
        moved = symbol.body.translated(delta)
        collision = next(
            (body for body in obstacles if not _clear(moved, body, gap_m)), None
        )
        if collision is None:
            return abs(delta[0])
        extra = _past(moved, collision, shoulder.direction, gap_m)
        delta = delta[0] + extra[0], 0.0
    raise RuntimeError("bounded native shoulder extension did not clear fixed bodies")


def shared_increase(requirements, gap_m: float) -> float:
    """One scalar for all shoulders; recheck earlier obstacles after each increase."""
    increase = 0.0
    # Each strict advance clears at least one datum/view or datum/obstacle pair
    # forever along its native ray. This is not an iterative COM retry policy.
    limit = 1 + sum(1 + len(obstacles) for _, _, obstacles in requirements)
    for _ in range(limit):
        previous = increase
        for symbol, outline, obstacles in requirements:
            increase = max(
                increase,
                required_increase(
                    symbol, outline, obstacles, gap_m, minimum_increase=increase
                ),
            )
        if increase - previous <= 1e-10:
            return increase
    raise RuntimeError("bounded shared datum length did not converge")


def _context(view):
    source = _early_bound(view.ReferencedDocument, "IModelDoc2")
    if source is None or not source.GetPathName():
        raise RuntimeError("document datum policy needs a resolved saved view source")
    values = (
        tuple(float(v) for v in view.Position),
        float(view.ScaleDecimal),
        tuple(float(v) for v in view.GetOutline()),
        str(view.ReferencedConfiguration),
        str(Path(source.GetPathName()).resolve()),
    )
    if (
        len(values[0]) != 2
        or len(values[2]) != 4
        or values[1] <= 0
        or not values[3]
        or not all(math.isfinite(v) for v in (*values[0], values[1], *values[2]))
    ):
        raise RuntimeError("document datum policy needs finite native view context")
    Rect(*values[2])
    return source, values


def _gtol_xml(annotations):
    result = {}
    for name, annotation in annotations.items():
        if int(annotation.GetType()) != 5:
            continue
        gtol = _early_bound(annotation.GetSpecificAnnotation(), "IGtol")
        count = int(gtol.GetFrameCount())
        if not 1 <= count <= 10000:
            raise RuntimeError("document leader policy GTol frame count is invalid")
        frames = []
        for index in range(1, count + 1):
            raw = gtol.GetFrame(index)
            if raw is None:
                raise RuntimeError(
                    "document leader policy found an unreadable GTol frame"
                )
            frames.append(
                ElementTree.canonicalize(
                    str(_early_bound(raw, "IGtolFrame").GetSymbolXml())
                )
            )
        result[name] = tuple(frames)
    return result


def _read_banks(adapter, views, measure):
    banks = {}
    for label, view in views.items():
        annotations = _visible_annotations(view)
        banks[label] = _Bank(
            view,
            _context(view),
            {
                name: _read_symbol(
                    adapter,
                    view,
                    annotation,
                    measure,
                    datum_leader_policy=DatumLeaderPolicy.BENT_DOCUMENT,
                )
                for name, annotation in annotations.items()
                if int(annotation.GetType()) in {2, 7}
            },
            _read_obstacles(adapter, view, annotations, measure, {}),
            _gtol_xml(annotations),
        )
    return banks


def _sheet_witness(adapter, drawing, measure):
    """Sheet notes get fresh bounds; fixed template ink gets exact native data."""
    notes, templates = {}, {}
    for index, raw_sheet in enumerate(drawing.GetViews() or ()):
        sheet = _early_bound(raw_sheet[0], "IView")
        annotations = _visible_annotations(sheet)
        if any(int(a.GetType()) in {2, 7} for a in annotations.values()):
            raise RuntimeError(
                "document datum policy does not support sheet-owned callouts"
            )
        notes[index] = _read_obstacles(adapter, sheet, annotations, measure, {})
        for raw in sheet.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.OwnerType) != 2:
                continue
            key = index, str(annotation.GetName())
            if key in templates:
                raise RuntimeError(
                    "document policy template annotation names are duplicated"
                )
            templates[key] = (
                annotation,
                int(annotation.Visible),
                _native_snapshot(annotation, adapter.currentModel.Extension),
            )
    return notes, templates


def _template_unchanged(app, before, after):
    if before.keys() != after.keys():
        raise RuntimeError("document length changed template annotation inventory")
    for name, original in before.items():
        actual = after[name]
        if int(app.IsSame(original[0], actual[0])) != 1 or original[1:] != actual[1:]:
            raise RuntimeError(f"{name}: document length changed fixed template ink")


def _document_length(extension):
    constants = _installed_swconst()
    preference = int(constants.swDetailingAnnotationBentLeaderLength)
    option = int(constants.swDetailingNoOptionSpecified)
    value = float(extension.GetUserPreferenceDouble(preference, option))
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError("native document bent leader length is not positive/finite")
    return value, preference, option


def _style_datums(adapter, banks, measure):
    changes = []
    styled = {}
    for label, bank in banks.items():
        symbols = dict(bank.symbols)
        for name, before in bank.symbols.items():
            if before.kind != 2:
                continue
            if before.placement is SymbolPlacement.STATIONARY_DIMENSION:
                raise RuntimeError(
                    "document leader policy for dimension-attached datums remains unverified"
                )
            if before.properties[1]:
                continue
            before.specific.Shoulder = True
            if not bool(before.specific.Shoulder):
                raise RuntimeError(
                    f"{before.name}: native bent datum shoulder rejected"
                )
            after = _read_symbol(
                adapter,
                bank.view,
                before.annotation,
                measure,
                datum_leader_policy=DatumLeaderPolicy.BENT_DOCUMENT,
            )
            expected = replace(
                before,
                properties=(before.properties[0], True, before.properties[2]),
                placement=after.placement,
                bent_shoulder=after.bent_shoulder,
            )
            _same_symbol(adapter.swApp, expected, after)
            if any(
                abs(a - b) > 1e-8
                for a, b in zip(
                    (
                        before.frame.xmax - before.frame.xmin,
                        before.frame.ymax - before.frame.ymin,
                    ),
                    (
                        after.frame.xmax - after.frame.xmin,
                        after.frame.ymax - after.frame.ymin,
                    ),
                )
            ):
                raise RuntimeError(
                    f"{before.name}: native shoulder style changed datum frame size"
                )
            changes.append(
                {
                    "view": label,
                    "datum": before.name,
                    "before": before.body.bounds,
                    "after": after.body.bounds,
                }
            )
            symbols[name] = after
        styled[label] = replace(bank, symbols=symbols)
    return styled, changes


def _body_changes(before, after):
    return {
        name: {
            "before_body": row.body.bounds,
            "after_body": after[name].body.bounds,
            "before_envelope": row.measurement.envelope.bounds,
            "after_envelope": after[name].measurement.envelope.bounds,
        }
        for name, row in before.items()
    }


@_telemetry.traced("drawing.datums.document_length")
def prepare_document_datum_leaders(
    adapter: Any,
    *,
    views: Mapping[str, Any],
    measure: Callable,
    planning_gap_m: float,
    declared_notes: Mapping,
    gtol_placement: GtolPlacement,
):
    model, app = adapter.currentModel, adapter.swApp
    drawing = _early_bound(model, "IDrawingDoc")
    registered = tuple(raw for sheet in drawing.GetViews() or () for raw in sheet[1:])
    if len(registered) != len(views) or any(
        sum(int(app.IsSame(view, raw)) == 1 for view in views.values()) != 1
        for raw in registered
    ):
        raise RuntimeError("document datum policy must witness every drawing view")
    with _telemetry.span("drawing.datums.document_initial_witness"):
        original = _read_banks(adapter, views, measure)
        sheet_before, templates_before = _sheet_witness(adapter, drawing, measure)
        old_length, preference, option = _document_length(model.Extension)
    with _telemetry.span("drawing.datums.bent_style"):
        before, style_changes = _style_datums(adapter, original, measure)
    requirements = []
    for bank in before.values():
        bent = tuple(row for row in bank.symbols.values() if row.kind == 2)
        static = tuple(
            row.body
            for name, row in bank.obstacles.items()
            if name not in declared_notes
            and not (row.kind == 5 and gtol_placement is GtolPlacement.ARRANGED_NEXT)
        )
        for index, symbol in enumerate(bent):
            if (
                symbol.bent_shoulder is None
                or abs(symbol.bent_shoulder.length_m - old_length) > 1e-8
            ):
                raise RuntimeError(
                    f"{symbol.name}: measured datum shoulder is not the current document length"
                )
            requirements.append((symbol, Rect(*bank.context[1][2]), static))
            for other in bent[index + 1 :]:
                if (
                    symbol.bent_shoulder.direction is other.bent_shoulder.direction
                    and not _clear(symbol.body, other.body, planning_gap_m)
                ):
                    raise RuntimeError(
                        f"same-side native datums {symbol.name}/{other.name} overlap; one document length cannot separate them"
                    )
    increase = shared_increase(requirements, planning_gap_m)
    requested = old_length + increase
    with _telemetry.span(
        "drawing.datums.document_length_write",
        old_length_m=old_length,
        requested_m=requested,
    ):
        if increase > 1e-8:
            if not model.Extension.SetUserPreferenceDouble(
                preference, option, requested
            ):
                raise RuntimeError("native document annotation leader length rejected")
            if not model.EditRebuild3():
                raise RuntimeError("native document annotation leader rebuild failed")
        actual_length, _, _ = _document_length(model.Extension)
        if abs(actual_length - requested) > 1e-8:
            raise RuntimeError(
                "native document annotation leader length did not persist"
            )
    side_effects = {}
    with _telemetry.span("drawing.datums.document_final_witness"):
        after = _read_banks(adapter, views, measure)
        sheet_after, templates_after = _sheet_witness(adapter, drawing, measure)
        _template_unchanged(app, templates_before, templates_after)
        if sheet_before.keys() != sheet_after.keys():
            raise RuntimeError("document leader policy changed sheet inventory")
        for index, original in sheet_before.items():
            _same_obstacles(app, original, sheet_after[index])
            side_effects[f"sheet:{index}"] = _body_changes(original, sheet_after[index])
        for label, old in before.items():
            new = after[label]
            if (
                old.context[1] != new.context[1]
                or int(app.IsSame(old.context[0], new.context[0])) != 1
            ):
                raise RuntimeError(
                    f"{label}: document leader policy changed view/model context"
                )
            if old.symbols.keys() != new.symbols.keys() or old.gtol_xml != new.gtol_xml:
                raise RuntimeError(
                    f"{label}: document leader policy changed symbol/GTol content"
                )
            _same_obstacles(app, old.obstacles, new.obstacles)
            for name, symbol in old.symbols.items():
                actual = new.symbols[name]
                if symbol.bent_shoulder is None:
                    _same_symbol(app, symbol, actual)
                    continue
                delta = _direction_delta(symbol.bent_shoulder, increase)
                expected = replace(
                    symbol,
                    body=symbol.body.translated(delta),
                    frame=symbol.frame.translated(delta),
                    bent_shoulder=replace(symbol.bent_shoulder, length_m=requested),
                )
                _final_symbol(app, expected, expected, actual)
            side_effects[label] = _body_changes(
                old.symbols, new.symbols
            ) | _body_changes(old.obstacles, new.obstacles)
    _telemetry.info(
        "native document datum length witnessed",
        old_length_m=old_length,
        requested_m=requested,
        increase_m=increase,
        style_changes=json.dumps(style_changes),
        side_effects=json.dumps(side_effects),
        template_annotation_count=len(templates_after),
    )
    # Nothing is handed off here: the ordinary callout loop now takes fresh
    # post-policy measurements, then records only its actual FINAL obstacles.
