"""Drafted blind extrudes and cuts that start off their sketch plane.

Separate module so edits affect only recipes that use this scope.

A cast wall leans from a station that is seldom its sketch plane: the pattern
parts on one plane and every drafted face is sized where it meets a faced
plane.  ``FeatureExtrusion3`` / ``FeatureCut3`` take the start offset, the
direction and the draft sense as five flags whose meaning the seat decides
(``build_ms_stick``: the inward flag flared a cut), so each feature is asked
for in its likeliest form first and accepted by what it does to the solid:
its volume change must be the closed form of the drafted prism.  A form that
changes the solid by anything else is undone and the next one tried.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import _telemetry
from _com import _bind, _com_invoke, _early_bound, _read_member
from _dimensions import _display_dimensions
from _drawing_precision import _named_dimension
from _drawing_tolerances import _set_tolerance_precision
from _feature_tree import _feature_by_name, name_last_feature

_BLIND = 0  # swEndConditions_e.swEndCondBlind
_START_OFFSET = 3  # swStartConditions_e.swStartOffset
# An undone trial must leave the solid as it found it (mm^3).
_UNDO_VOLUME_TOL = 1e-3


@dataclass(frozen=True)
class DraftedForm:
    """One way to ask for the feature: Dir, StartOffset (signed mm),
    FlipStartOffset and Ddir1 (the draft's inward flag)."""

    reverse: bool
    start: float
    flip_start: bool
    inward: bool

    def __str__(self) -> str:
        return (
            f"Dir={self.reverse} StartOffset={self.start:+g}"
            f" FlipStartOffset={self.flip_start} Ddir1={self.inward}"
        )


def drafted_forms(
    *, cut: bool, start: float, along_normal: bool, narrowing: bool
) -> tuple[DraftedForm, ...]:
    """The forms to try for a feature that starts ``start`` mm along the sketch
    normal, runs along that normal or against it, and whose section narrows or
    widens as it goes; likeliest first.

    Proven on bosses: (Dir False, offset s) starts at s for either sign of s
    and runs along the normal; (Dir True, offset s, flipped) starts at -s and
    runs against it.  A boss runs along the normal by default, a cut against
    it.  The first start below is the one every reading of those three agrees
    on; the others cover the readings that differ.
    """
    reverse = along_normal if cut else not along_normal
    first = (start, False) if along_normal else (-start, True)
    starts = [first]
    for candidate in ((start, False), (-start, True), (-start, False), (start, True)):
        if candidate not in starts:
            starts.append(candidate)
    if start == 0.0:
        starts = [(0.0, False)]
    return tuple(
        DraftedForm(reverse, offset, flipped, inward)
        for offset, flipped in starts
        for inward in (narrowing, not narrowing)
    )


def _arguments(form: DraftedForm, cut: bool, depth: float, angle_deg: float) -> tuple:
    """FeatureExtrusion3's 23 arguments, or FeatureCut3's 26."""
    head = (
        True,  # Sd: single-ended (a double-ended cut takes no draft)
        False,  # Flip side to cut
        form.reverse,  # Dir
        _BLIND,
        _BLIND,  # T1, T2
        depth / 1000.0,
        0.0,  # D1, D2
        True,
        False,  # Dchk1, Dchk2
        form.inward,
        False,  # Ddir1, Ddir2
        math.radians(angle_deg),
        0.0,  # Dang1, Dang2
        False,
        False,  # OffsetReverse1/2
        False,
        False,  # TranslateSurface1/2
    )
    tail = (_START_OFFSET, form.start / 1000.0, form.flip_start)
    if cut:
        # NormalCut, UseFeatScope, UseAutoSelect, then the assembly-feature flags.
        return (*head, False, False, True, False, False, False, *tail)
    return (*head, True, False, True, *tail)  # Merge, UseFeatScope, UseAutoSelect


def _create(adapter: Any, sketch_name: str, cut: bool, arguments: tuple) -> Any:
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        sketch_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"drafted extrude: cannot select sketch {sketch_name!r}")
    manager = model.FeatureManager
    create = manager.FeatureCut3 if cut else manager.FeatureExtrusion3
    feature, error = adapter._attempt_with_error(lambda: create(*arguments))
    model.ClearSelection2(True)
    if not feature:
        return None, str(error)
    return feature, ""


async def _solid_volume(adapter: Any, label: str) -> float:
    """The part's volume (mm^3); zero before the first solid exists."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    if not tuple(part.GetBodies2(0, False) or ()):  # swBodyType_e.swSolidBody
        return 0.0
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"{label}: get_mass_properties failed: {mass.error}")
    return float(mass.data.volume)


def assert_drafted(
    adapter: Any, feature_name: str, depth: float, angle_deg: float
) -> bool:
    """Read one drafted feature's depth and draft back; returns its
    draft-outward flag (the seat's sense of it is proved by volume)."""
    feature = _early_bound(_feature_by_name(adapter, feature_name), "IFeature")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError(f"{feature_name}: missing native extrusion definition")
    definition = _early_bound(definition, "IExtrudeFeatureData2")
    read_depth = float(definition.GetDepth(True)) * 1000.0
    drafted = bool(definition.GetDraftWhileExtruding(True))
    read_angle = math.degrees(float(definition.GetDraftAngle(True)))
    if (
        not drafted
        or not math.isfinite(read_angle)
        or abs(read_angle - angle_deg) > 1e-6
        or not math.isfinite(read_depth)
        or abs(read_depth - depth) > 1e-6
    ):
        raise RuntimeError(
            f"{feature_name}: expected {depth:g} mm at {angle_deg:g} deg draft; got"
            f" depth {read_depth:.6g}, drafted={drafted}, angle {read_angle:.6g}"
        )
    return bool(definition.GetDraftOutward(True))


@_telemetry.traced("feature.drafted_extrude", label_param="label")
async def drafted_extrude(
    adapter: Any,
    sketch_name: str,
    feature_name: str,
    label: str,
    *,
    cut: bool,
    depth: float,
    angle_deg: float,
    forms: tuple[DraftedForm, ...],
    volume: float,
    change: float,
    tol: float,
) -> float:
    """Extrude (or cut) ``sketch_name`` blind ``depth`` mm with ``angle_deg``
    draft, named ``feature_name``; returns the solid's new volume.

    ``volume`` is the solid before the feature and ``change`` what the drafted
    prism must add to it (negative for a cut), to within ``tol`` mm^3.  Each
    form in ``forms`` is created in turn; the first that changes the solid by
    ``change`` stays, any other is undone and the solid proved restored.
    """
    tried: list[str] = []
    for form in forms:
        feature, error = _create(
            adapter, sketch_name, cut, _arguments(form, cut, depth, angle_deg)
        )
        if feature is None:
            tried.append(f"[{form}] refused ({error})")
            continue
        after = await _solid_volume(adapter, label)
        if abs(after - volume - change) <= tol:
            name_last_feature(adapter, feature_name)
            outward = assert_drafted(adapter, feature_name, depth, angle_deg)
            _telemetry.success(
                f"{label}: {feature_name} [{form}] changed the solid by"
                f" {after - volume:+.1f} mm^3 (drafted prism {change:+.1f});"
                f" draft-outward reads {outward}"
            )
            return after
        tried.append(f"[{form}] changed the solid by {after - volume:+.1f} mm^3")
        adapter.currentModel.EditUndo2(1)
        restored = await _solid_volume(adapter, label)
        if abs(restored - volume) > _UNDO_VOLUME_TOL:
            raise RuntimeError(
                f"{label}: undoing [{form}] left {restored - volume:+.4f} mm^3;"
                f" tried {tried}"
            )
    raise RuntimeError(
        f"{label}: no form changed the solid by the drafted prism's"
        f" {change:+.1f} mm^3 (+/-{tol:g}): " + "; ".join(tried)
    )


def name_feature_dimensions(
    adapter: Any,
    feature_name: str,
    *,
    lengths: dict[str, float],
    angles: dict[str, float],
) -> None:
    """Name a drafted feature's own dimensions by what each reads.

    A drafted offset extrude carries its depth, its start offset and its draft
    angle in an order nothing promises; ``lengths`` (mm) and ``angles``
    (degrees) give each wanted name's value, and each must match exactly one
    of the feature's dimensions.
    """
    wanted = {name: abs(value) / 1000.0 for name, value in lengths.items()}
    wanted.update({name: math.radians(abs(value)) for name, value in angles.items()})
    feature = _feature_by_name(adapter, feature_name)
    readings = [
        (dimension, abs(float(_com_invoke(dimension, "IDimension", "SystemValue"))))
        for dimension in _display_dimensions(feature, feature_name)
    ]
    for name, value in wanted.items():
        matches = [
            dimension for dimension, reading in readings if abs(reading - value) < 1e-9
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"{feature_name}: {len(matches)} dimensions read {name}'s {value:g};"
                f" the feature reads {[reading for _d, reading in readings]}"
            )
        _bind(matches[0], "IDimension").Name = name
        _telemetry.success(f"dim {name}@{feature_name} = {value:g} (by value)")


@_telemetry.traced("dim.draft_tolerance", label_param="dimension_name")
def set_draft_angle_tolerance(
    adapter: Any,
    feature_name: str,
    dimension_name: str,
    minus_degrees: float,
    plus_degrees: float,
) -> None:
    """Band one draft-angle dimension ``-minus_degrees`` / ``+plus_degrees``
    on the model (SolidWorks stores radians): symmetric when the two are
    equal, bilateral otherwise."""
    if minus_degrees < 0.0 or plus_degrees < 0.0 or minus_degrees + plus_degrees <= 0.0:
        raise ValueError("a draft-angle band needs non-negative deviations and a range")
    display, dimension = _named_dimension(adapter, feature_name, dimension_name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    symmetric = minus_degrees == plus_degrees
    kind = 4 if symmetric else 2  # swTolType_e.swTolSYMMETRIC / swTolBILAT
    tolerance.Type = kind
    lower, upper = -math.radians(minus_degrees), math.radians(plus_degrees)
    if not tolerance.SetValues(lower, upper):
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: SetValues rejected"
            f" -{minus_degrees:g}/+{plus_degrees:g} deg"
        )
    minimum = float(tolerance.GetMinValue())
    maximum = float(tolerance.GetMaxValue())
    if (
        int(_read_member(tolerance, "Type")) != kind
        or abs(minimum - lower) > 1e-12
        or abs(maximum - upper) > 1e-12
    ):
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: draft band readback"
            f" {minimum:g}/{maximum:g} rad != {lower:g}/{upper:g} rad"
        )
    _set_tolerance_precision(
        display,
        (-minus_degrees, plus_degrees),
        display_unit="deg",
        label=f"{dimension_name}@{feature_name}",
    )
    _telemetry.success(
        f"toleranced {dimension_name}@{feature_name}:"
        f" -{minus_degrees:g}/+{plus_degrees:g} deg"
    )
