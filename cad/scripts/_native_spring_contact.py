"""Certify static native spring contact at the current component poses."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import _telemetry
from _common import _early_bound, _read_member
from solidworks_mcp.adapters.com_variant import dispatch_array


@dataclass(frozen=True, slots=True)
class NativeInterferenceEvidence:
    state: Literal["interfering", "clear"]
    volume_mm3: float | None
    witness: Literal["solid_intersection", "modeler_predicate"]
    boolean_failure_status: int | None


class _NativeBooleanFailure(RuntimeError):
    def __init__(self, label: str, status: int) -> None:
        self.status = status
        super().__init__(f"{label}: native body intersection failed (status={status})")


def _component_solids(assembly: Any, name: str, label: str) -> tuple[list[Any], Any]:
    component = _early_bound(assembly.GetComponentByName(name), "IComponent2")
    if component is None:
        raise RuntimeError(f"{label}: component unavailable: {name}")
    result = component.GetBodies3(0)  # swSolidBody; assembly-instance geometry.
    if not isinstance(result, tuple) or len(result) != 2 or not result[0]:
        raise RuntimeError(f"{label}: no actual solid bodies for {name}")
    transform = _early_bound(_read_member(component, "Transform2"), "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{label}: component transform unavailable: {name}")
    solids = []
    for raw in result[0]:
        body = _early_bound(raw, "IBody2")
        if body is None or body.GetType() != 0:
            raise RuntimeError(f"{label}: non-solid body returned for {name}")
        faults = body.Check3
        if faults is not None and int(_early_bound(faults, "IFaultEntity").Count) != 0:
            raise RuntimeError(f"{label}: invalid native solid in {name}")
        solids.append(body)
    return solids, transform


def _transformed_body_copy(body: Any, transform: Any, label: str) -> Any:
    copied = _early_bound(body.Copy(), "IBody2")
    if copied is None:
        raise RuntimeError(f"{label}: native body copy failed")
    if not copied.ApplyTransform(transform):
        raise RuntimeError(f"{label}: native body transform failed")
    return copied


@_telemetry.traced("spring.contact.body_intersection", label_param="label")
def native_component_overlap_mm3(
    adapter: Any,
    moving_component: str,
    fixed_component: str,
    *,
    label: str,
) -> float:
    """Sum native solid intersections at the CURRENT actual component poses.

    GetBodies3 preserves configured assembly-instance geometry. Only temporary
    copies are transformed or consumed by Operations2; supplier solids and
    component placements are untouched. All body pairs participate, without a
    volume allowance.
    """
    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    moving, moving_transform = _component_solids(assembly, moving_component, label)
    fixed, fixed_transform = _component_solids(assembly, fixed_component, label)
    volume_mm3 = 0.0
    for moving_body in moving:
        for fixed_body in fixed:
            target = _transformed_body_copy(moving_body, moving_transform, label)
            tool = _transformed_body_copy(fixed_body, fixed_transform, label)
            try:
                result = target.Operations2(15901, tool, 0)  # SWBODYINTERSECT
            finally:
                # Operations2 consumes BOTH temporary operands, even on failure.
                target = tool = None
            if not isinstance(result, tuple) or len(result) != 2:
                raise RuntimeError(f"{label}: malformed native intersection result")
            intersections, status = result
            if (
                status in (5, 1067) and not intersections
            ):  # DisjointBodies / NoIntersect
                continue
            if status != 0:
                raise _NativeBooleanFailure(label, status)
            for raw in intersections or ():
                body = _early_bound(raw, "IBody2")
                if body is None or body.GetType() != 0:
                    raise RuntimeError(
                        f"{label}: native intersection returned a non-solid"
                    )
                properties = body.GetMassProperties(1.0)
                if not isinstance(properties, (tuple, list)) or len(properties) != 12:
                    raise RuntimeError(
                        f"{label}: native intersection mass properties unavailable"
                    )
                volume = float(properties[3]) * 1e9
                if not math.isfinite(volume) or volume < 0.0:
                    raise RuntimeError(
                        f"{label}: invalid native intersection volume: {volume!r}"
                    )
                volume_mm3 += volume
    if not math.isfinite(volume_mm3):
        raise RuntimeError(f"{label}: native intersection volume overflow")
    _telemetry.event(
        "spring.contact.body_volume",
        moving_component=moving_component,
        fixed_component=fixed_component,
        volume_mm3=volume_mm3,
    )
    return volume_mm3


@_telemetry.traced("spring.contact.modeler_predicate", label_param="label")
def _modeler_interference(
    adapter: Any,
    moving_component: str,
    fixed_component: str,
    *,
    label: str,
) -> Literal["interfering", "clear"]:
    """Query fresh copies; failed Operations2 operands have already been consumed.

    Option 1 excludes coincident-only contact. Option 4 returns participating
    bodies, NOT overlap solids, so their volumes must never be used here.
    """
    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    moving, moving_transform = _component_solids(assembly, moving_component, label)
    fixed, fixed_transform = _component_solids(assembly, fixed_component, label)
    modeler = _early_bound(_read_member(adapter.swApp, "GetModeler"), "IModeler")
    if modeler is None:
        raise RuntimeError(f"{label}: native modeler unavailable")
    for moving_body in moving:
        for fixed_body in fixed:
            target = _transformed_body_copy(moving_body, moving_transform, label)
            tool = _transformed_body_copy(fixed_body, fixed_transform, label)
            # The three VARIANT outputs are [in,out]; initialize them explicitly.
            result = modeler.CheckInterference3(
                dispatch_array([target]),
                dispatch_array([tool]),
                1,
                None,
                None,
                None,
            )
            target = tool = None
            if not isinstance(result, tuple) or len(result) != 4 or result[0] is None:
                raise RuntimeError(f"{label}: malformed native interference predicate")
            if result[0]:
                _telemetry.event(
                    "spring.contact.modeler_interference",
                    moving_component=moving_component,
                    fixed_component=fixed_component,
                )
                return "interfering"
    return "clear"


@_telemetry.traced("spring.contact.native_predicate", label_param="label")
def native_component_interference(
    adapter: Any,
    moving_component: str,
    fixed_component: str,
    *,
    label: str,
) -> NativeInterferenceEvidence:
    """Keep measured volumes authoritative; only upgrade BooleanFail to collision.

    A successful volume sums every body pair. If construction fails, no total
    exists: a positive independent modeler predicate may prove interference, but
    its volume remains None. A negative predicate leaves the original failure
    fatal. Successful zero-volume seats never consult the second kernel.
    """
    try:
        volume_mm3 = native_component_overlap_mm3(
            adapter,
            moving_component,
            fixed_component,
            label=label,
        )
    except _NativeBooleanFailure as failure:
        if (
            failure.status != 1058
        ):  # swBodyOperationBooleanFail; other errors stay fatal.
            raise
        state = _modeler_interference(
            adapter,
            moving_component,
            fixed_component,
            label=label,
        )
        if state != "interfering":
            raise
        _telemetry.event(
            "spring.contact.boolean_failure_interference",
            moving_component=moving_component,
            fixed_component=fixed_component,
            boolean_failure_status=failure.status,
        )
        _telemetry.warn(
            f"{label}: native modeler proves interference after BooleanFail",
            boolean_failure_status=failure.status,
        )
        return NativeInterferenceEvidence(
            "interfering",
            None,
            "modeler_predicate",
            failure.status,
        )
    return NativeInterferenceEvidence(
        "interfering" if volume_mm3 > 0.0 else "clear",
        volume_mm3,
        "solid_intersection",
        None,
    )


def assert_native_contact(
    adapter: Any,
    first_component: str,
    second_component: str,
    *,
    maximum_distance_mm: float,
    label: str,
) -> float:
    """Certify zero native overlap and bounded separation at the current pose."""
    if (
        not first_component
        or not second_component
        or first_component == second_component
    ):
        raise ValueError("native contact requires two distinct component names")
    if not math.isfinite(maximum_distance_mm) or maximum_distance_mm < 0.0:
        raise ValueError(
            "native contact maximum distance must be finite and nonnegative"
        )

    with _telemetry.span("spring.native_contact", label=label) as span:
        span.set_attribute("first_component", first_component)
        span.set_attribute("second_component", second_component)
        span.set_attribute("maximum_distance_mm", maximum_distance_mm)

        evidence = native_component_interference(
            adapter,
            first_component,
            second_component,
            label=label,
        )
        span.set_attribute("overlap_state", evidence.state)
        span.set_attribute("overlap_witness", evidence.witness)
        if evidence.volume_mm3 is not None:
            span.set_attribute("overlap_volume_mm3", evidence.volume_mm3)
        if evidence.boolean_failure_status is not None:
            span.set_attribute(
                "boolean_failure_status", evidence.boolean_failure_status
            )
        if evidence.state != "clear":
            if evidence.volume_mm3 is None:
                magnitude = "unmeasured native overlap"
            else:
                magnitude = f"{evidence.volume_mm3:.17g} mm^3 native overlap"
            raise RuntimeError(f"{label}: components intersect ({magnitude})")
        if evidence.volume_mm3 != 0.0:
            raise RuntimeError(
                f"{label}: native clear witness has no measured zero-volume result"
            )

        model = _early_bound(adapter.currentModel, "IModelDoc2")
        assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
        first = _early_bound(
            assembly.GetComponentByName(first_component), "IComponent2"
        )
        second = _early_bound(
            assembly.GetComponentByName(second_component), "IComponent2"
        )
        if first is None:
            raise RuntimeError(f"{label}: component unavailable: {first_component}")
        if second is None:
            raise RuntimeError(f"{label}: component unavailable: {second_component}")
        result = model.ClosestDistance(first, second)
        if not isinstance(result, tuple) or len(result) != 3:
            raise RuntimeError(
                f"{label}: unexpected ClosestDistance result: {result!r}"
            )
        distance_mm = float(result[0]) * 1000.0
        if not math.isfinite(distance_mm) or distance_mm < 0.0:
            raise RuntimeError(
                f"{label}: native ClosestDistance has no finite nonnegative solution"
            )

        span.set_attribute("distance_mm", distance_mm)
        _telemetry.event(
            "spring.contact.static_measurement",
            label=label,
            first_component=first_component,
            second_component=second_component,
            volume_mm3=evidence.volume_mm3,
            distance_mm=distance_mm,
            maximum_distance_mm=maximum_distance_mm,
        )
        if distance_mm > maximum_distance_mm:
            raise RuntimeError(
                f"{label}: native distance {distance_mm:.17g} mm exceeds "
                f"calibrated maximum {maximum_distance_mm:.17g} mm"
            )
        span.set_attribute("certificate", "zero_overlap_bounded_distance")
        return distance_mm


@dataclass(frozen=True, slots=True)
class _AssemblySpringInstance:
    name: str
    station_z_mm: float


_CHANNEL_SPRING_FAMILY = "channel-spring-installed"
_CHANNEL_CONTACT_FAMILIES = (
    _CHANNEL_SPRING_FAMILY,
    "spring-hook",
    "channel-lever",
)
_SUMMING_CONTACT_FAMILIES = ("counter-spring", "boss-hook", "gooseneck")
_STATION_LOOKUP_TOLERANCE_MM = 1e-3


def _spring_contact_family(source_stem: str) -> str | None:
    if source_stem == _CHANNEL_SPRING_FAMILY or source_stem.startswith(
        f"{_CHANNEL_SPRING_FAMILY}-stretch"
    ):
        return _CHANNEL_SPRING_FAMILY
    families = (*_CHANNEL_CONTACT_FAMILIES[1:], *_SUMMING_CONTACT_FAMILIES)
    return source_stem if source_stem in families else None


def _assembly_spring_instances(
    adapter: Any, families: tuple[str, ...]
) -> dict[str, list[_AssemblySpringInstance]]:
    """Enumerate each relevant top-level occurrence from its actual source part."""
    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    components = adapter._attempt(lambda: assembly.GetComponents(True), default=None)
    if components is None:
        raise RuntimeError("native spring contact: top-level components unavailable")
    found = {family: [] for family in families}
    for raw in components:
        component = _early_bound(raw, "IComponent2")
        if component is None:
            raise RuntimeError("native spring contact: invalid top-level component")
        name = str(_read_member(component, "Name2") or "")
        source = _read_member(component, "GetPathName")
        if not name or not isinstance(source, str) or not source:
            raise RuntimeError(
                "native spring contact: component identity unavailable "
                f"(name={name!r}, source={source!r})"
            )
        source_stem = Path(source).stem.casefold()
        family = _spring_contact_family(source_stem)
        if family not in found:
            continue
        transform = _early_bound(
            _read_member(component, "Transform2"), "IMathTransform"
        )
        values = _read_member(transform, "ArrayData") if transform is not None else None
        if not isinstance(values, (list, tuple)) or len(values) < 12:
            raise RuntimeError(
                f"native spring contact: transform unavailable for {name}"
            )
        station_z_mm = float(values[11]) * 1000.0
        if not math.isfinite(station_z_mm):
            raise RuntimeError(
                f"native spring contact: non-finite station Z for {name}"
            )
        found[family].append(_AssemblySpringInstance(name, station_z_mm))
    return found


def _ordered_family(
    family: str,
    instances: list[_AssemblySpringInstance],
    expected_count: int,
) -> list[_AssemblySpringInstance]:
    if len(instances) != expected_count:
        raise RuntimeError(
            f"{family}: expected exactly {expected_count} top-level "
            f"instance(s), found {len(instances)}: "
            f"{sorted(instance.name for instance in instances)}"
        )
    ordered = sorted(instances, key=lambda instance: instance.station_z_mm)
    for first, second in zip(ordered, ordered[1:]):
        if second.station_z_mm == first.station_z_mm:
            raise RuntimeError(
                f"{family}: ambiguous duplicate station at "
                f"Z={first.station_z_mm:.9g} mm: {first.name}, {second.name}"
            )
    return ordered


def _match_station_family(
    springs: list[_AssemblySpringInstance],
    family: str,
    instances: list[_AssemblySpringInstance],
) -> list[_AssemblySpringInstance]:
    """Assign one occurrence to each spring station using only its origin Z.

    The 1e-3 mm window identifies corresponding occurrences only. It is never
    used as contact clearance: ``assert_native_contact`` applies each measured
    seat's calibrated distance bound and its independent zero-overlap proof.
    """
    unmatched = list(instances)
    matched = []
    for spring in springs:
        candidates = [
            instance
            for instance in unmatched
            if abs(instance.station_z_mm - spring.station_z_mm)
            <= _STATION_LOOKUP_TOLERANCE_MM
        ]
        if len(candidates) != 1:
            kind = "missing" if not candidates else "ambiguous"
            raise RuntimeError(
                f"{family}: {kind} station pairing for {spring.name} at "
                f"Z={spring.station_z_mm:.9g} mm; found "
                f"{[candidate.name for candidate in candidates]} within "
                f"{_STATION_LOOKUP_TOLERANCE_MM:g} mm"
            )
        match = candidates[0]
        unmatched.remove(match)
        matched.append(match)
    if unmatched:
        raise RuntimeError(
            f"{family}: unmatched top-level instances after station pairing: "
            f"{sorted(instance.name for instance in unmatched)}"
        )
    return matched


def assert_assembly_spring_contacts(
    adapter: Any,
    asm_name: str,
    *,
    channel_count: int | None = None,
) -> None:
    """Certify every configured spring seat from persisted top-level instances.

    Normal channel refresh and soundness checks use the configured active rows.
    A standalone channel build may explicitly select a nonempty prefix of the
    full configured channel vector, including rows beyond ``active_count``.
    The component walk is independent of builder locals. Channel occurrences are
    grouped by source part, ordered by their shared station Z, and required to
    form one spring/hook/lever triplet per selected amplitude. Summing has one
    counter chain. No component is moved and no rebuild is requested.
    """
    if channel_count is not None and asm_name != "channel":
        raise ValueError("channel_count applies only to the channel assembly")
    if asm_name == "channel":
        import _config
        import settled_spring_seats

        if channel_count is None:
            selected_channels = _config.active_channels()
            count = _config.active_count()
            if count < 1:
                raise ValueError("channel native contact requires at least one channel")
            if len(selected_channels) != count:
                raise RuntimeError(
                    f"channel calibration selected {len(selected_channels)} active "
                    f"row(s), expected {count}"
                )
        else:
            if isinstance(channel_count, bool) or not isinstance(channel_count, int):
                raise TypeError("channel_count must be an integer or None")
            all_channels = _config.channels()
            if not 1 <= channel_count <= len(all_channels):
                raise ValueError(
                    f"channel_count must be between 1 and {len(all_channels)}, "
                    f"got {channel_count}"
                )
            selected_channels = all_channels[:channel_count]
            count = channel_count
        seats = [
            settled_spring_seats.channel_seat(float(channel["amplitude_mm"]))
            for channel in selected_channels
        ]
        pitch = float(_config.machine("channels", "station_pitch_mm"))
        if not math.isfinite(pitch) or pitch <= 0.0:
            raise RuntimeError(
                "channel native contact requires positive configured station pitch"
            )
        found = _assembly_spring_instances(adapter, _CHANNEL_CONTACT_FAMILIES)
        springs = _ordered_family(
            _CHANNEL_SPRING_FAMILY,
            found[_CHANNEL_SPRING_FAMILY],
            count,
        )
        hooks = _match_station_family(
            springs,
            "spring-hook",
            _ordered_family("spring-hook", found["spring-hook"], count),
        )
        levers = _match_station_family(
            springs,
            "channel-lever",
            _ordered_family("channel-lever", found["channel-lever"], count),
        )
        # selected_channels is config-row/index order. Because the configured
        # pitch is positive, ascending actual station Z has that same order;
        # therefore each measured seat/bound stays attached to its amplitude.
        for station, (spring, hook, lever, seat) in enumerate(
            zip(springs, hooks, levers, seats, strict=True)
        ):
            lower = assert_native_contact(
                adapter,
                spring.name,
                hook.name,
                maximum_distance_mm=seat.lower_maximum_distance_mm,
                label=f"channel {station:02d} lower native seat",
            )
            upper = assert_native_contact(
                adapter,
                spring.name,
                lever.name,
                maximum_distance_mm=seat.upper_maximum_distance_mm,
                label=f"channel {station:02d} upper native seat",
            )
            _telemetry.success(
                f"channel {station:02d} native contacts: lower {lower:.9g} mm, "
                f"upper {upper:.9g} mm"
            )
        return

    if asm_name == "summing":
        import settled_spring_seats

        seat, _gooseneck_y = settled_spring_seats.counter_seat()
        found = _assembly_spring_instances(adapter, _SUMMING_CONTACT_FAMILIES)
        counter = _ordered_family("counter-spring", found["counter-spring"], 1)
        boss = _match_station_family(
            counter,
            "boss-hook",
            _ordered_family("boss-hook", found["boss-hook"], 1),
        )
        gooseneck = _match_station_family(
            counter,
            "gooseneck",
            _ordered_family("gooseneck", found["gooseneck"], 1),
        )
        counter_instance = counter[0]
        boss_instance = boss[0]
        gooseneck_instance = gooseneck[0]
        lower = assert_native_contact(
            adapter,
            counter_instance.name,
            boss_instance.name,
            maximum_distance_mm=seat.lower_maximum_distance_mm,
            label="counter lower native seat",
        )
        upper = assert_native_contact(
            adapter,
            gooseneck_instance.name,
            counter_instance.name,
            maximum_distance_mm=seat.upper_maximum_distance_mm,
            label="counter upper native seat",
        )
        _telemetry.success(
            f"counter native contacts: lower {lower:.9g} mm, upper {upper:.9g} mm"
        )
        return

    raise ValueError(f"assembly {asm_name!r} has no native spring-contact contract")
