"""Declared process-global preference baselines and overrides.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import _telemetry

# STL export user-preferences (swUserPreferenceIntegerValue / Toggle ids,
# swconst R2026x) -- shared with export_models.py so a build-time part STL and
# the render-cache STL are byte-identical: a fine BINARY mesh in MILLIMETRES,
# left at the model origin. stl_bbox_mm parses exactly this.
PREF_STL_QUALITY = 78  # swSTLQuality -> 2 = fine


PREF_STL_UNITS = 211  # swExportStlUnits -> 0 = swMM


TOGGLE_STL_BINARY = 69  # swSTLBinaryFormat


TOGGLE_STL_ONE_FILE = 72  # swSTLComponentsIntoOneFile


TOGGLE_STL_NO_TRANSLATE = 71  # swSTLDontTranslateToPositive: keep model origin


TOGGLE_STL_SHOW_INFO = 70  # swSTLShowInfoOnSave: the per-file "Save <name>.STL?" modal


# ---------------------------------------------------------------------------
# Process-global SolidWorks preferences: DECLARED baselines, not observed ones
#
# The defect class this replaces: mutate a process-global preference, capture
# the value that happened to be there, restore it in a ``finally``. A leaf that
# dies inside the block strands the seat with the mutated value -- and our OWN
# watchdog exits (86/87/88) are ``os._exit``, which skips ``finally`` BY
# CONSTRUCTION, so this is not a hypothetical. The next run on that seat then
# captures the stranded value as "the original" and faithfully restores it
# forever: self-perpetuating, deterministic per seat, random-looking across a
# fleet -- exactly the signature of the 2026-09-17 "transient" leaf.
#
# Two shapes, one implementation each, and NO observed-value restore anywhere:
#
# * :func:`enforce_preferences` -- the family whose required state IS the
#   baseline (STL/STEP export). Nothing restores anything, so nothing can be
#   stranded; drift found at entry is reported, not inherited.
# * :func:`preference_override` -- a family that must be temporarily different
#   (e.g. suppressing sketch inference). Restores the DECLARED baseline, and is
#   DEPTH-COUNTED so a nested block cannot restore mid-flight for the outer one.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PreferenceSpec:
    """A named family of SolidWorks user preferences and its declared baseline.

    Keys are swconst MEMBER NAMES (resolved at runtime -- ids move between
    releases, names do not) or raw ids for the export families that predate this
    rule and already carry the member name in a comment. ``baseline_*`` is the
    state a seat is left in; when it equals the applied state the family is
    simply enforced and there is nothing to restore.

    The mappings are wrapped read-only at construction: ``frozen=True`` alone
    stops ``spec.toggles = {}`` but not ``spec.toggles[9] = False``, and the
    entire argument for this class is that the baseline is a DECLARED constant
    -- one a recipe cannot quietly accumulate into.
    """

    label: str
    integers: Mapping[str | int, int] = field(default_factory=dict)
    toggles: Mapping[str | int, bool] = field(default_factory=dict)
    baseline_integers: Mapping[str | int, int] = field(default_factory=dict)
    baseline_toggles: Mapping[str | int, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("integers", "toggles", "baseline_integers", "baseline_toggles"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))


# SHOW_INFO -> False: every part build now exports an STL, so leaving the modal on
# would block an unattended `doit` run on the first export (cut_release.py disables
# it for the same reason; codex review #12).
#
# Declared baseline == applied state: every STL this repo writes is a fine binary
# mesh in millimetres at the model origin (``stl_bbox_mm`` parses exactly that),
# and no build step wants any other value, so the seat is deliberately LEFT in
# this state instead of being handed back a value an earlier crash invented.
STL_EXPORT_PREFERENCES = PreferenceSpec(
    label="stl-export",
    integers={PREF_STL_QUALITY: 2, PREF_STL_UNITS: 0},
    toggles={
        TOGGLE_STL_BINARY: True,
        TOGGLE_STL_ONE_FILE: True,
        TOGGLE_STL_NO_TRANSLATE: True,
        TOGGLE_STL_SHOW_INFO: False,
    },
)


def _preference_key(adapter: Any, key: str | int) -> int | None:
    """A raw id passes through; a member name is resolved through swconst."""
    if isinstance(key, int) and not isinstance(key, bool):
        return key
    return _preference_id(adapter, str(key))


def _read_preferences(adapter: Any, spec: PreferenceSpec) -> dict[str | int, Any]:
    """Current seat values for every key in ``spec`` (missing ones omitted)."""
    sw = adapter.swApp
    current: dict[str | int, Any] = {}
    for keys, accessor, cast in (
        (spec.integers or spec.baseline_integers, "GetUserPreferenceIntegerValue", int),
        (spec.toggles or spec.baseline_toggles, "GetUserPreferenceToggle", bool),
    ):
        read = getattr(sw, accessor, None)
        for key in keys:
            pref = _preference_key(adapter, key)
            if pref is None or read is None:
                continue
            value = adapter._attempt(lambda p=pref, r=read: r(p), default=None)
            if value is not None:
                current[key] = cast(value)
    return current


def _write_preferences(
    adapter: Any,
    spec: PreferenceSpec,
    integers: Mapping[str | int, int],
    toggles: Mapping[str | int, bool],
) -> dict[str, Any]:
    """Write ``integers``/``toggles``, then VERIFY by read-back.

    A refused write is the whole failure mode being closed here, so it is
    reported rather than assumed: ``SetUserPreference*`` returns nothing useful
    on a preference the seat declines (an unknown id, or one a policy locks).

    Reported, never RAISED: some preferences are write-ignored by design
    (``swSketchAddConstToRectEntity`` reads fine and silently drops the write
    because it is per-document), and a family whose recipe no longer depends on
    the write succeeding is degraded-but-correct when it does. Raising here would
    turn a cosmetic seat-hygiene problem into a build outage.
    """
    sw = adapter.swApp
    refused: dict[str, Any] = {}
    for values, writer, reader, cast in (
        (
            integers,
            "SetUserPreferenceIntegerValue",
            "GetUserPreferenceIntegerValue",
            int,
        ),
        (toggles, "SetUserPreferenceToggle", "GetUserPreferenceToggle", bool),
    ):
        write = getattr(sw, writer, None)
        read = getattr(sw, reader, None)
        for key, wanted in values.items():
            pref = _preference_key(adapter, key)
            if pref is None or write is None:
                refused[str(key)] = "unresolved"
                continue
            adapter._attempt(lambda p=pref, v=wanted, w=write: w(p, v), default=None)
            if read is None:
                continue
            got = adapter._attempt(lambda p=pref, r=read: r(p), default=None)
            if got is None or cast(got) != wanted:
                refused[str(key)] = f"wanted {wanted}, seat reports {got!r}"
    return refused


def _report_preference_state(
    spec: PreferenceSpec,
    stage: str,
    drift: Mapping[str | int, tuple[Any, Any]],
    refused: dict[str, Any],
) -> None:
    """One span event per stage (never one per preference), and a WARN only when
    the seat actually disagreed -- drift is the evidence a seat was stranded."""
    _telemetry.event(
        f"seat.preferences.{stage}",
        family=spec.label,
        drift=json.dumps({str(k): list(v) for k, v in drift.items()}, sort_keys=True),
        refused=json.dumps(refused, sort_keys=True),
    )
    if drift:
        _telemetry.warn(
            f"[seat] {spec.label}: {len(drift)} preference(s) differed from the "
            f"declared baseline at {stage} "
            + ", ".join(
                f"{key}={actual!r} (want {wanted!r})"
                for key, (actual, wanted) in sorted(drift.items(), key=repr)
            )
            + " -- a seat left mutated by an earlier run, now corrected",
            family=spec.label,
            stage=stage,
        )
    if refused:
        _telemetry.warn(
            f"[seat] {spec.label}: the seat refused {len(refused)} preference "
            f"write(s) at {stage}: {refused}",
            family=spec.label,
            stage=stage,
        )


def _drift_against(
    current: Mapping[str | int, Any],
    integers: Mapping[str | int, int],
    toggles: Mapping[str | int, bool],
) -> dict[str | int, tuple[Any, Any]]:
    """Keys whose read value differs from what this family declares."""
    wanted: dict[str | int, Any] = {**integers, **toggles}
    return {
        key: (current[key], value)
        for key, value in wanted.items()
        if key in current and current[key] != value
    }


def enforce_preferences(adapter: Any, spec: PreferenceSpec) -> dict[str | int, Any]:
    """Assert ``spec``'s required state on the seat; return the drift corrected.

    For families whose required state IS the declared baseline: there is no
    save and no restore, so no leaf -- however it dies -- can strand a value,
    and the next leaf cannot mistake a stranded value for "the original".
    Ambient state is never inherited: whatever the seat carried in is compared
    against the declaration, reported, and overwritten.
    """
    current = _read_preferences(adapter, spec)
    drift = _drift_against(current, spec.integers, spec.toggles)
    refused = _write_preferences(adapter, spec, spec.integers, spec.toggles)
    _report_preference_state(spec, "enforce", drift, refused)
    return {key: actual for key, (actual, _wanted) in drift.items()}


# Nesting depth per preference family (see preference_override). Module-global
# because the seat is: two nested overrides of the same family share one seat,
# whatever objects hold them.
_override_depth: dict[str, int] = {}


@contextlib.contextmanager
def preference_override(adapter: Any, spec: PreferenceSpec) -> Iterator[None]:
    """Apply ``spec``'s state for the duration of the block, then restore its
    DECLARED baseline -- once, on the outermost exit.

    Depth counting is load-bearing, not defensive: restoring a declared baseline
    from a NESTED block is worse than the old observed-value latch, because the
    inner exit would restore the baseline mid-flight while the outer block is
    still relying on the override. The innermost blocks therefore do nothing on
    entry or exit, and only the outermost restores.

    This still cannot survive ``os._exit`` (nothing can), but the damage is now
    bounded: the stranded value is a DECLARED one, the next entry reports the
    drift it finds, and the restore target never depends on what an earlier
    crash left behind.
    """
    depth = _override_depth.get(spec.label, 0)
    _override_depth[spec.label] = depth + 1
    try:
        if depth == 0:
            current = _read_preferences(adapter, spec)
            drift = _drift_against(
                current, spec.baseline_integers, spec.baseline_toggles
            )
            refused = _write_preferences(adapter, spec, spec.integers, spec.toggles)
            _report_preference_state(spec, "override", drift, refused)
        yield
    finally:
        # Decrement FIRST and unconditionally: if the restore write throws while
        # unwinding, a depth left above zero would pin this family for the rest
        # of the session -- every later block silently applying nothing and
        # restoring nothing. That is the latch again, just a subtler one.
        _override_depth[spec.label] = depth
        if depth == 0:
            refused = _write_preferences(
                adapter, spec, spec.baseline_integers, spec.baseline_toggles
            )
            _report_preference_state(spec, "restore", {}, refused)


def _preference_id(adapter: Any, name: str) -> int | None:
    """Resolve a ``swUserPreference*_e`` MEMBER NAME to its id at runtime.

    Through the swconst type library the early-bound adapter loads
    (``win32com.client.constants``) first, then the adapter's own small
    constants table. Never a hard-coded integer.
    """
    constants: Any = None
    with contextlib.suppress(Exception):  # not on a seat: offline gate / no pywin32
        from win32com.client import constants as sw_constants

        constants = sw_constants
    value = getattr(constants, name, None) if constants is not None else None
    if value is None:
        value = getattr(adapter, "constants", {}).get(name)
    return (
        int(value) if isinstance(value, int) and not isinstance(value, bool) else None
    )
