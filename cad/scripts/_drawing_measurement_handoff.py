"""One-consumer handoff of actual annotation bounds between layout phases.

Only view-owned annotations freshly measured by the preceding phase are recorded.
The handoff never measures on record, never serves a GTol witness, and expires
after the initial packing snapshot. Final packing must use the independent
fresh measurement callback, even when the initial plan requires no movement.
Position/context checks do not prove unchanged text or shape: the fresh final
packing inventory and measurements remain the semantic and final-fit witness.
Consumers must bracket read-only inventory collection with read_scope. Drawing,
sheet and recorded view context are checked at both boundaries, not for every
entry. A read may return after mid-bank context drift, but completion fails before
the consumer may run a native command, move a view or accept an unchanged plan.

The opt-in POST_DATUM_CALLOUTS purpose additionally pins the complete visible
inventory and exact referenced-model identities, and permits one read scope for
ALL views before any callout mutation. Only kind2/4/7 bounds are reused; initial
native semantic/attachment/value reads, restyled SF bounds and final checks stay
fresh. Native anchorless cosmetic threads/centerlines/centermarks are not cached.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Callable, Mapping

from _common import _early_bound
import _telemetry


class _Phase(Enum):
    RECORDING = "recording"
    SEALED = "sealed"
    CONSUMING = "consuming"
    FAILED = "failed"
    CLOSED = "closed"
    EXHAUSTED = "exhausted"


class HandoffPurpose(Enum):
    GTOL_OBSTACLES = "gtol_obstacles_only"
    INITIAL_PACKING = "initial_packing_only"
    POST_DATUM_CALLOUTS = "post_datum_callout_initial_only"


@dataclass(frozen=True)
class _Entry:
    annotation: Any
    owner: Any
    position: tuple[float, ...]
    measured: Any


@dataclass(frozen=True)
class _InventoryEntry:
    annotation: Any
    owner: Any
    owner_type: int
    kind: int
    position: tuple[float, ...]


def _inventory_position(annotation, kind):
    values = annotation.GetPosition()
    # These native kinds can have no annotation anchor. They are NEVER reused;
    # the consumer measures their actual strokes afresh, as does its final pass.
    if not values and kind in {1, 13, 15}:
        return ()
    return _values(values, 3, "inventory position")


def _values(raw, size, label):
    values = tuple(float(value) for value in raw or ())
    if len(values) != size or not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"measurement handoff requires finite {label}")
    return values


def _view_context(view):
    return (
        str(view.GetName2()),
        _values(view.Position, 2, "view position"),
        _values(view.ScaleRatio, 2, "view scale"),
        str(view.GetReferencedModelName()),
        str(view.ReferencedConfiguration),
    )


class AnnotationMeasurementHandoff:
    """Record actual output, seal, consume each entry once in read banks, close.

    Names index candidates only; native IsSame checks prove annotation, owner,
    drawing and sheet identity. Native view position/scale/model/configuration
    must match at both read-bank boundaries. Every reused entry independently
    retains exact native annotation/owner identity and recorded XYZ checks.
    An absent entry is a normal fresh measurement, but a changed recorded
    context is a failed transaction, never a silent new baseline.
    """

    def __init__(
        self,
        adapter: Any,
        *,
        views: Mapping[str, Any],
        measure_annotation: Callable,
        purpose: HandoffPurpose,
        inventory_of: Callable | None = None,
    ):
        if not isinstance(purpose, HandoffPurpose):
            raise ValueError("measurement handoff requires an explicit purpose enum")
        self._purpose = purpose
        if (purpose is HandoffPurpose.POST_DATUM_CALLOUTS) != callable(inventory_of):
            raise ValueError(
                "post-datum handoff requires its exact visible inventory reader"
            )
        self._inventory_of = inventory_of
        self._adapter = adapter
        self._model = adapter.currentModel
        self._drawing = _early_bound(self._model, "IDrawingDoc")
        self._sheet = self._drawing.GetCurrentSheet()
        self._measure = measure_annotation
        self._views = {}
        for view in views.values():
            name = str(view.GetName2())
            if not name or name in self._views:
                raise ValueError("measurement handoff requires unique native views")
            self._views[name] = view
        self._contexts = {}
        self._entries = {}
        self._inventories = {}
        self._sources = {}
        self._outlines = {}
        self._consumed = set()
        self._phase = _Phase.RECORDING
        self._reading_names = ()
        self._context_names = ()
        self._recorded = self._reused = self._fresh = 0

    def _same(self, first, second):
        return int(self._adapter.swApp.IsSame(first, second)) == 1

    def _view(self, view):
        name = str(view.GetName2())
        expected = self._views.get(name)
        if expected is None or not self._same(view, expected):
            raise RuntimeError("measurement handoff native view identity changed")
        return name

    def _assert_context(self, names=None):
        if not self._same(self._model, self._adapter.currentModel):
            raise RuntimeError("measurement handoff active drawing identity changed")
        if not self._same(self._sheet, self._drawing.GetCurrentSheet()):
            raise RuntimeError("measurement handoff active sheet identity changed")
        if self._purpose is HandoffPurpose.POST_DATUM_CALLOUTS and not self._same(
            self._model, self._adapter.swApp.ActiveDoc
        ):
            raise RuntimeError("measurement handoff native active document changed")
        names = self._contexts if names is None else names
        for name in names:
            context = self._contexts[name]
            if context != _view_context(self._views[name]):
                raise RuntimeError(f"measurement handoff view context changed: {name}")
            if name in self._sources and (
                not self._same(
                    self._sources[name], self._views[name].ReferencedDocument
                )
                or self._outlines[name]
                != _values(self._views[name].GetOutline(), 4, "view outline")
            ):
                raise RuntimeError(
                    f"measurement handoff source/outline context changed: {name}"
                )

    def record_bank(self, view, rows, *, source):
        """Record one already validated post-datum bank, not new semantic facts.

        Only kind2/4/7 footprints are reused. Every other visible annotation
        still participates in the exact inventory guard and is freshly measured
        if consumed. The whole drawing's initial inventory is consumed before
        any subsequent native geometry/style operation; this bank cannot reopen.
        """
        if (
            self._purpose is not HandoffPurpose.POST_DATUM_CALLOUTS
            or self._phase is not _Phase.RECORDING
        ):
            raise RuntimeError("measurement handoff is not recording post-datum banks")
        name = self._view(view)
        if name in self._inventories or source is None:
            raise RuntimeError(
                "measurement handoff duplicate or unresolved post-datum bank"
            )
        inventory = {}
        for key, row in rows.items():
            annotation = row.annotation
            kind = row.kind
            if (
                key != str(annotation.GetName())
                or kind != int(annotation.GetType())
                or int(annotation.Visible) != 1
                or not self._same(row.owner, annotation.Owner)
            ):
                raise RuntimeError("measurement handoff post-datum inventory changed")
            inventory[key] = _InventoryEntry(
                annotation,
                row.owner,
                int(annotation.OwnerType),
                kind,
                _inventory_position(annotation, kind),
            )
            if kind in {2, 4, 7} and inventory[key].owner_type == 0:
                self.record(view, annotation, row.measurement)
        self._inventories[name] = inventory
        self._contexts[name] = _view_context(view)
        self._sources[name] = source
        self._outlines[name] = _values(view.GetOutline(), 4, "view outline")

    def _assert_inventory(self):
        for name, expected in self._inventories.items():
            actual = self._inventory_of(self._views[name])
            if expected.keys() != actual.keys():
                raise RuntimeError(
                    f"measurement handoff visible inventory changed: {name}"
                )
            for key, old in expected.items():
                annotation = actual[key]
                if (
                    not self._same(old.annotation, annotation)
                    or not self._same(old.owner, annotation.Owner)
                    or old.owner_type != int(annotation.OwnerType)
                    or old.kind != int(annotation.GetType())
                    or key != str(annotation.GetName())
                    or int(annotation.Visible) != 1
                    or old.position != _inventory_position(annotation, old.kind)
                ):
                    raise RuntimeError(
                        f"measurement handoff inventory identity/position changed: {name}/{key}"
                    )

    def record(self, view, annotation, measured):
        if self._phase is not _Phase.RECORDING:
            raise RuntimeError("measurement handoff is no longer recording")
        name = self._view(view)
        owner = annotation.Owner
        if int(annotation.OwnerType) != 0 or not self._same(owner, view):
            raise RuntimeError("measurement handoff requires exact drawing-view owner")
        key = (name, str(annotation.GetName()), int(annotation.GetType()))
        permitted = (
            {2, 4, 7}
            if self._purpose
            in {HandoffPurpose.GTOL_OBSTACLES, HandoffPurpose.POST_DATUM_CALLOUTS}
            else {2, 4, 5, 7}
        )
        if key[2] not in permitted or key[1:] != (measured.name, measured.kind):
            raise RuntimeError("measurement handoff annotation measurement mismatch")
        position = _values(annotation.GetPosition(), 3, "annotation position")
        if position[:2] != tuple(measured.anchor):
            raise RuntimeError("measurement handoff measured anchor changed")
        if key in self._entries:
            raise RuntimeError(f"measurement handoff duplicate actual witness: {key}")
        if name not in self._contexts:
            self._contexts[name] = _view_context(view)
        self._entries[key] = _Entry(annotation, owner, position, measured)
        self._recorded += 1

    def seal(self):
        if self._phase is not _Phase.RECORDING:
            raise RuntimeError("measurement handoff cannot be sealed twice")
        if self._purpose is HandoffPurpose.POST_DATUM_CALLOUTS:
            if self._inventories.keys() != self._views.keys():
                raise RuntimeError(
                    "measurement handoff requires every post-datum view bank"
                )
            self._assert_inventory()
        self._assert_context()
        self._phase = _Phase.SEALED

    def begin_read(self, view=None):
        """Start a read-only bank; completion must precede any native mutation."""
        if self._phase is not _Phase.SEALED:
            raise RuntimeError("measurement handoff cannot begin a read bank")
        if self._purpose is HandoffPurpose.POST_DATUM_CALLOUTS:
            if view is not None:
                raise RuntimeError(
                    "post-datum handoff must consume all views before mutation"
                )
            self._assert_inventory()
        names = tuple(self._views) if view is None else (self._view(view),)
        contexts = tuple(name for name in names if name in self._contexts)
        self._assert_context(contexts)
        self._reading_names, self._context_names = names, contexts
        self._phase = _Phase.CONSUMING

    def end_read(self):
        """Reject mid-inventory drift before a subsequent command can run."""
        if self._phase is not _Phase.CONSUMING:
            raise RuntimeError("measurement handoff has no active read bank")
        self._phase = _Phase.FAILED
        if self._purpose is HandoffPurpose.POST_DATUM_CALLOUTS:
            self._assert_inventory()
        self._assert_context(self._context_names)
        self._reading_names = self._context_names = ()
        self._phase = (
            _Phase.EXHAUSTED
            if self._purpose is HandoffPurpose.POST_DATUM_CALLOUTS
            else _Phase.SEALED
        )

    @contextmanager
    def read_scope(self, view=None):
        self.begin_read(view)
        try:
            yield
        finally:
            self.end_read()

    def initial_measure(self, adapter, annotation):
        if self._phase is not _Phase.CONSUMING:
            raise RuntimeError("measurement handoff is not ready: no active read bank")
        if adapter is not self._adapter:
            raise RuntimeError("measurement handoff adapter changed")
        if int(annotation.OwnerType) != 0:
            self._fresh += 1
            return self._measure(adapter, annotation)
        owner = annotation.Owner
        name = self._view(_early_bound(owner, "IView"))
        if name not in self._reading_names:
            raise RuntimeError("measurement handoff owner is outside its read bank")
        key = (name, str(annotation.GetName()), int(annotation.GetType()))
        if self._purpose is HandoffPurpose.POST_DATUM_CALLOUTS:
            if key in self._consumed:
                raise RuntimeError(f"measurement handoff entry consumed twice: {key}")
            self._consumed.add(key)
        entry = self._entries.get(key)
        if entry is None:
            self._fresh += 1
            return self._measure(adapter, annotation)
        if not self._same(entry.annotation, annotation) or not self._same(
            entry.owner, owner
        ):
            raise RuntimeError(
                f"measurement handoff annotation identity changed: {key}"
            )
        if entry.position != _values(
            annotation.GetPosition(), 3, "annotation position"
        ):
            raise RuntimeError(
                f"measurement handoff annotation position changed: {key}"
            )
        del self._entries[key]
        self._reused += 1
        return entry.measured

    def close(self):
        if self._phase is _Phase.CONSUMING:
            raise RuntimeError("measurement handoff requires read bank completion")
        outcome = self._phase.value
        self._entries.clear()
        self._inventories.clear()
        self._consumed.clear()
        self._phase = _Phase.CLOSED
        _telemetry.info(
            "native annotation measurement handoff",
            recorded_count=self._recorded,
            reused_count=self._reused,
            fresh_initial_count=self._fresh,
            scope=self._purpose.value,
            lifecycle_outcome=outcome,
            final_witness="fresh_native_measurement",
        )
