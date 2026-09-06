"""One measured document-length prepass for explicitly opted-in bent datums.

The saved-rocker ``probe_datum_shoulder.py --mode document_length`` is the native
positive control: preference swDetailingAnnotationBentLeaderLength moves the
left/right datum frame by the signed length delta, leaving the elbow and exact
model attachment fixed. IAnnotation.BentLeaderLength stayed -1 in that control;
it is neither a fallback trigger nor the setter used here.

The independent ``probe_gtol_leader_override.py`` controls positively preserve
GTol and SF leaders through family defaults (4a28d4e0/y228ca9f and
55f14f9/f4ty_f46). Capture their effective defaults before the datum-global
change, then detach inherited families at those captured values. No individual
annotation override is written. Their actual native primitives must stay fixed
in the existing final measurement bank; the combined policy still needs its
own production drawing gates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
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
    length_overrides: dict


class _Family(Enum):
    GTOL = "gtol"
    SURFACE_FINISH = "surface_finish"


class _LengthSource(Enum):
    DOCUMENT = "document"
    FAMILY = "family"


@dataclass(frozen=True)
class _FamilyLength:
    source: _LengthSource
    value_m: float
    effective_m: float
    toggle: int
    preference: int
    option: int


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
        context = _context(view)
        symbols = {
            name: _read_symbol(
                adapter,
                view,
                annotation,
                measure,
                datum_leader_policy=DatumLeaderPolicy.BENT_DOCUMENT,
            )
            for name, annotation in annotations.items()
            if int(annotation.GetType()) in {2, 7}
        }
        obstacles = _read_obstacles(adapter, view, annotations, measure, {})
        banks[label] = _Bank(
            view,
            context,
            symbols,
            obstacles,
            _gtol_xml(annotations),
            _length_overrides(symbols | obstacles),
        )
    return banks


def _length_overrides(rows):
    result = {}
    for name, row in rows.items():
        if row.kind not in {5, 7}:
            continue
        value = float(row.annotation.BentLeaderLength)
        if not math.isfinite(value) or (value < 0 and value != -1):
            raise RuntimeError(
                f"{name}: invalid native family annotation length override"
            )
        # -1 has several documented meanings. Preserve it; do not infer that
        # it proves inheritance or an unsupported native annotation mechanism.
        result[name] = value
    return result


def _same_non_datum_primitives(before, after):
    """Consume already measured native geometry; never add a second COM pass."""
    for name, original in before.items():
        if original.kind == 2:
            continue
        actual = after[name]
        for field in (
            "native_strokes",
            "leader_segments",
            "native_leader_segments",
            "leader_decorations",
        ):
            initial = tuple(getattr(original.measurement, field))
            final = tuple(getattr(actual.measurement, field))
            if initial != final:
                _telemetry.error(
                    "native non-datum primitive preservation failed",
                    annotation=name,
                    primitive_field=field,
                    before_primitives=repr(initial),
                    after_primitives=repr(final),
                )
                raise RuntimeError(
                    f"{name}: document datum policy changed non-datum native {field}"
                )


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


def _family_lengths(extension, global_length):
    constants = _installed_swconst()
    option = int(constants.swDetailingNoOptionSpecified)
    preferences = {
        _Family.GTOL: (
            int(constants.swDetailingGtolUseDocBentLeaderLength),
            int(constants.swDetailingGtolBentLeaderLength),
        ),
        _Family.SURFACE_FINISH: (
            int(constants.swDetailingSFSymbolUseDocBentLeaderLength),
            int(constants.swDetailingSFSymbolBentLeaderLength),
        ),
    }
    result = {}
    for family, (toggle, preference) in preferences.items():
        source = (
            _LengthSource.DOCUMENT
            if extension.GetUserPreferenceToggle(toggle, option)
            else _LengthSource.FAMILY
        )
        value = float(extension.GetUserPreferenceDouble(preference, option))
        if not math.isfinite(value) or value <= 0:
            raise RuntimeError(
                f"{family.value}: native family length is not positive/finite"
            )
        effective = global_length if source is _LengthSource.DOCUMENT else value
        result[family] = _FamilyLength(
            source, value, effective, toggle, preference, option
        )
    return result


def _preserve_family_lengths(extension, original):
    for family, initial in original.items():
        if initial.source is _LengthSource.FAMILY:
            continue
        toggle_result = bool(
            extension.SetUserPreferenceToggle(initial.toggle, initial.option, False)
        )
        # Both positive native controls returned True with an OFF getter,
        # despite the reference describing a resulting-state Boolean. Require
        # actual getter state, retaining the raw return for the native receipt.
        if extension.GetUserPreferenceToggle(initial.toggle, initial.option):
            raise RuntimeError(
                f"{family.value}: native family length still inherits the document"
            )
        if not extension.SetUserPreferenceDouble(
            initial.preference, initial.option, initial.effective_m
        ):
            raise RuntimeError(f"{family.value}: native family length rejected")
        _telemetry.info(
            "native annotation family length detached",
            family=family.value,
            preserved_m=initial.effective_m,
            toggle_returned=toggle_result,
        )


def _require_preserved_families(original, actual, increase):
    for family, initial in original.items():
        current = actual[family]
        expected_source = _LengthSource.FAMILY if increase > 1e-8 else initial.source
        if (
            current.source is not expected_source
            or abs(current.effective_m - initial.effective_m) > 1e-8
            or (
                current.source is _LengthSource.FAMILY
                and abs(current.value_m - initial.effective_m) > 1e-8
            )
        ):
            raise RuntimeError(
                f"{family.value}: native family length did not retain its original effective definition"
            )


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
        family_lengths = _family_lengths(model.Extension, old_length)
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
            _preserve_family_lengths(model.Extension, family_lengths)
            if not model.EditRebuild3():
                raise RuntimeError("native document annotation leader rebuild failed")
        actual_length, _, _ = _document_length(model.Extension)
        if abs(actual_length - requested) > 1e-8:
            raise RuntimeError(
                "native document annotation leader length did not persist"
            )
    side_effects = {}
    with _telemetry.span("drawing.datums.document_final_witness"):
        families_after = _family_lengths(model.Extension, actual_length)
        _require_preserved_families(family_lengths, families_after, increase)
        after = _read_banks(adapter, views, measure)
        sheet_after, templates_after = _sheet_witness(adapter, drawing, measure)
        _template_unchanged(app, templates_before, templates_after)
        if sheet_before.keys() != sheet_after.keys():
            raise RuntimeError("document leader policy changed sheet inventory")
        for index, original in sheet_before.items():
            _same_obstacles(app, original, sheet_after[index])
            _same_non_datum_primitives(original, sheet_after[index])
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
            if old.length_overrides != new.length_overrides:
                raise RuntimeError(
                    f"{label}: native family annotation length override changed"
                )
            _same_obstacles(app, old.obstacles, new.obstacles)
            _same_non_datum_primitives(old.obstacles, new.obstacles)
            _same_non_datum_primitives(old.symbols, new.symbols)
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
        family_lengths=json.dumps(
            {
                family.value: {
                    "source_before": initial.source.value,
                    "effective_before_m": initial.effective_m,
                    "source_after": families_after[family].source.value,
                    "effective_after_m": families_after[family].effective_m,
                }
                for family, initial in family_lengths.items()
            }
        ),
    )
    # Nothing is handed off here: the ordinary callout loop now takes fresh
    # post-policy measurements, then records only its actual FINAL obstacles.
