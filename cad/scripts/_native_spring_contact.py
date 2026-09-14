"""Seat unchanged supplier solids using actual native component intersections.

Trial placements affect only one grounded component and are always restored.
No overlap volume is allowed. Contact is witnessed by native minimum distance
or a converged native collision bracket, never an added clearance margin.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Literal

import _telemetry
from _assembly import configured_interference_manager
from _common import _early_bound, _read_member
from _cwm import put_component_pose
from solidworks_mcp.adapters.com_variant import dispatch_array

NATIVE_CONTACT_DISTANCE_TOLERANCE_MM = 1e-5
_POSITION_CONVERGENCE_MM = 1e-6
_TRANSFORM_READBACK_TOLERANCE = 1e-12
_MAX_ITERATIONS = 64


@dataclass(frozen=True, slots=True)
class ContactSolution:
    offset_mm: float
    interfering_offset_mm: float | None
    clear_offset_mm: float
    iterations: int
    certificate: Literal["already_seated", "bracketed_native_contact"]
    witness: Literal["native_distance", "native_collision_bracket"]
    final_distance_mm: float


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


def _warn_distance_disagreement(label: str, distance_mm: float) -> None:
    if distance_mm > NATIVE_CONTACT_DISTANCE_TOLERANCE_MM:
        _telemetry.warn(
            f"{label}: native collision bracket and ClosestDistance disagree",
            final_distance_mm=distance_mm,
            native_distance_guard_mm=NATIVE_CONTACT_DISTANCE_TOLERANCE_MM,
        )


def _cleanup_failure(
    primary: BaseException | None, cleanup: BaseException, context: str
) -> None:
    """Never replace the original failure with a cleanup failure."""
    message = f"{context}: {type(cleanup).__name__}: {cleanup}"
    if primary is None:
        raise cleanup
    primary.add_note(message)
    try:
        _telemetry.error(message, exc_info=True)
    except Exception:
        # Reporting must not replace the primary failure either; its note stays.
        pass


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
    volume allowance. This independently catches pairs the assembly manager can
    omit after placement updates (probe_stock_spring_seating's saved mode).
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


class _ActualContact:
    """Restore every actual placement; independently check its native solid bodies."""

    def __init__(
        self,
        adapter: Any,
        moving: str,
        fixed: str,
        direction: tuple[float, float, float],
        maximum: float,
        label: str,
    ) -> None:
        if not moving or not fixed or moving == fixed:
            raise ValueError("native contact requires two distinct component names")
        self.adapter = adapter
        self.model = _early_bound(adapter.currentModel, "IModelDoc2")
        self.asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
        self.moving, self.fixed = moving, fixed
        self.direction = direction
        self.label = label
        self.trials = 0
        self.components = list(self.asm.GetComponents(True) or [])
        self.names = [
            str(_read_member(component, "Name2")) for component in self.components
        ]
        if moving not in self.names or fixed not in self.names:
            raise RuntimeError(
                f"{label}: native contact requires existing top-level components"
            )
        component = _early_bound(self.asm.GetComponentByName(moving), "IComponent2")
        if not component.IsFixed():
            raise RuntimeError(
                f"{label}: native contact may only move a grounded component ({moving})"
            )
        self.originals = {name: self._transform(name) for name in self.names}
        self.endpoints = (self._shifted(-maximum), self._shifted(maximum))

    def _transform(self, name: str) -> list[float]:
        component = self.asm.GetComponentByName(name)
        if component is None:
            raise RuntimeError(f"{self.label}: component disappeared: {name}")
        transform = _read_member(component, "Transform2")
        if transform is None:
            raise RuntimeError(f"{self.label}: transform unavailable: {name}")
        data = [float(value) for value in _read_member(transform, "ArrayData")]
        if (
            len(data) != 16
            or not all(math.isfinite(value) for value in data)
            or data[12] <= 0.0
        ):
            raise RuntimeError(f"{self.label}: invalid component transform: {name}")
        return data

    def _assert_pose(self, name: str, expected: list[float]) -> None:
        actual = self._transform(name)
        deviation = max(abs(a - b) for a, b in zip(actual, expected, strict=True))
        if deviation > _TRANSFORM_READBACK_TOLERANCE:
            raise RuntimeError(
                f"{self.label}: {name} transform readback differs by {deviation:.17g}"
            )

    def _assert_poses(self, expected: dict[str, list[float]]) -> None:
        for name, transform in expected.items():
            self._assert_pose(name, transform)

    def _shifted(self, offset_mm: float) -> list[float]:
        data = list(self.originals[self.moving])
        for axis, value in enumerate(self.direction):
            data[9 + axis] += value * offset_mm / 1000.0
        if not all(math.isfinite(value) for value in data):
            raise ValueError("native contact trial transform must be finite")
        return data

    def _put(self, target: list[float]) -> None:
        # Transform2 can ignore a sub-nanometre change. Visit the farthest of the
        # EXISTING bracket endpoints before every trial and restoration, then
        # land on the exact target. This is not an added clearance or margin.
        waypoint = max(
            self.endpoints,
            key=lambda values: sum(
                (values[9 + i] - target[9 + i]) ** 2 for i in range(3)
            ),
        )
        for transform in (waypoint, target):
            put_component_pose(self.adapter, self.moving, transform)
            self._assert_pose(self.moving, transform)

    def _distance_mm(self) -> float:
        moving = _early_bound(self.asm.GetComponentByName(self.moving), "IComponent2")
        fixed = _early_bound(self.asm.GetComponentByName(self.fixed), "IComponent2")
        result = self.model.ClosestDistance(moving, fixed)
        if not isinstance(result, tuple) or len(result) != 3:
            raise RuntimeError(
                f"{self.label}: unexpected ClosestDistance result: {result!r}"
            )
        distance_mm = float(result[0]) * 1000.0
        if not math.isfinite(distance_mm) or distance_mm < 0.0:
            raise RuntimeError(
                f"{self.label}: native ClosestDistance has no finite solution"
            )
        return distance_mm

    def _interference_state(
        self, expected: dict[str, list[float]]
    ) -> Literal["interfering", "clear"]:
        self.model.ClearSelection2(True)
        self.adapter._attempt(lambda: self.asm.ToolsCheckInterference(), default=None)
        manager = configured_interference_manager(self.adapter)
        primary: BaseException | None = None
        try:
            state: Literal["interfering", "clear"] = "clear"
            pair = {self.moving, self.fixed}
            for raw in manager.GetInterferences() or []:
                hit = _early_bound(raw, "IInterference")
                names = [
                    str(_read_member(component, "Name2"))
                    for component in _read_member(hit, "Components") or []
                ]
                if len(names) == 2 and set(names) == pair:
                    state = "interfering"
            # Verify immediately after querying as well as after Done. The native
            # detector must not silently reset a trial to its original position.
            self._assert_poses(expected)
        except BaseException as exc:
            primary = exc
            raise
        finally:
            try:
                manager.Done()
            except BaseException as cleanup:
                _cleanup_failure(
                    primary, cleanup, f"{self.label}: interference Done failed"
                )
        self._assert_poses(expected)
        if state == "interfering":
            return state
        native_result = native_component_interference(
            self.adapter,
            self.moving,
            self.fixed,
            label=self.label,
        )
        self._assert_poses(expected)
        if native_result.state == "interfering":
            details: dict[str, Any] = {
                "witness": native_result.witness,
                "overlap_measurement": "unmeasured",
            }
            magnitude = "unmeasured volume"
            if native_result.volume_mm3 is not None:
                details["overlap_measurement"] = "measured"
                details["overlap_volume_mm3"] = native_result.volume_mm3
                magnitude = f"{native_result.volume_mm3:.17g} mm^3"
            _telemetry.event(
                "spring.contact.manager_omission",
                label=self.label,
                moving_component=self.moving,
                fixed_component=self.fixed,
                trial=self.trials,
                **details,
            )
            if self.trials == 1:
                _telemetry.warn(
                    f"{self.label}: assembly manager omitted native body overlap ({magnitude})",
                    **details,
                )
            return "interfering"
        return "clear"

    def _update_mates(self) -> None:
        # swRebuildOptions_e.swUpdateMates is documented specifically for
        # Transform2 and refreshes placement without rebuilding supplier solids.
        extension = _early_bound(
            _read_member(self.model, "Extension"), "IModelDocExtension"
        )
        if not extension.Rebuild(4):
            raise RuntimeError(f"{self.label}: native contact mate update failed")

    def evaluate(
        self,
        offset_mm: float,
        *,
        measurement: Literal["interference", "contact"] = "interference",
    ) -> tuple[Literal["interfering", "clear"], float | None]:
        if measurement not in ("interference", "contact"):
            raise ValueError(
                "native contact measurement must be interference or contact"
            )
        if not math.isfinite(offset_mm):
            raise ValueError("native contact offset must be finite")
        self._assert_poses(self.originals)
        target = self._shifted(offset_mm)
        expected = dict(self.originals)
        expected[self.moving] = target
        primary: BaseException | None = None
        self.trials += 1
        try:
            self._put(target)
            # Matrix readback alone does not certify refreshed assembly geometry.
            # Use the documented mate-only update proven against full rebuilds.
            self._update_mates()
            self._assert_poses(expected)
            distance = self._distance_mm() if measurement == "contact" else None
            state = self._interference_state(expected)
            self._assert_poses(expected)
            return state, distance
        except BaseException as exc:
            primary = exc
            exc.add_note(
                f"{self.label}: native trial {self.trials}, "
                f"offset={offset_mm:.17g} mm, measurement={measurement}"
            )
            raise
        finally:
            try:
                self._put(self.originals[self.moving])
                self._update_mates()
                self._assert_poses(self.originals)
            except BaseException as cleanup:
                _cleanup_failure(
                    primary,
                    cleanup,
                    f"{self.label}: original placement restoration failed",
                )
            else:
                if primary is None:
                    _telemetry.debug(
                        f"{self.label}: native trial {self.trials} restored",
                        trial=self.trials,
                        offset_mm=offset_mm,
                    )


def solve_component_contact(
    adapter: Any,
    moving_component: str,
    fixed_component: str,
    direction_xyz: tuple[float, float, float],
    max_translation_mm: float,
    *,
    label: str,
) -> ContactSolution:
    """Certify an existing seat or return a proposed clear native contact pose.

    Only a grounded top-level moving component is accepted. Positive direction
    must separate the local contact monotonically within the symmetric bracket.
    Actual component placement, rebuild, assembly interference, native solid
    intersection, and minimum distance are used; every trial restores the pose.

    ``already_seated`` certifies the CURRENT clear pose, either by native
    distance or an actual inward collision within 1e-6 mm. Its offset and
    iterations are zero; the distance witness has no interfering endpoint.
    ``bracketed_native_contact`` proposes a move: its clear endpoint has a
    confirmed collision/clear bracket converged to 1e-6 mm. ClosestDistance
    remains recorded and disagreement warns; it cannot overrule that native
    bracket. No distance margin is added. Recheck after applying the offset.
    """
    if len(direction_xyz) != 3 or not all(
        math.isfinite(value) for value in direction_xyz
    ):
        raise ValueError("native contact direction must contain three finite values")
    if not math.isclose(math.hypot(*direction_xyz), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("native contact direction must be a unit vector")
    if (
        not math.isfinite(max_translation_mm)
        or max_translation_mm <= 0.0
        or not math.isfinite(2.0 * max_translation_mm)
    ):
        raise ValueError("native contact bracket must have finite positive width")
    with _telemetry.span("spring.native_contact", label=label) as span:
        started = time.monotonic()
        iterations = 0
        pair: _ActualContact | None = None
        span.set_attribute("moving_component", moving_component)
        span.set_attribute("fixed_component", fixed_component)
        span.set_attribute("direction_xyz", list(direction_xyz))
        span.set_attribute("max_translation_mm", max_translation_mm)
        span.set_attribute(
            "native_distance_guard_mm", NATIVE_CONTACT_DISTANCE_TOLERANCE_MM
        )
        try:
            pair = _ActualContact(
                adapter,
                moving_component,
                fixed_component,
                direction_xyz,
                max_translation_mm,
                label,
            )
            seed_state, seed_distance = pair.evaluate(0.0, measurement="contact")
            assert seed_distance is not None
            if seed_state == "clear":
                if seed_distance <= NATIVE_CONTACT_DISTANCE_TOLERANCE_MM:
                    span.set_attribute("certificate", "already_seated")
                    span.set_attribute("witness", "native_distance")
                    span.set_attribute("final_distance_mm", seed_distance)
                    span.set_attribute("clear_offset_mm", 0.0)
                    return ContactSolution(
                        0.0,
                        None,
                        0.0,
                        0,
                        "already_seated",
                        "native_distance",
                        seed_distance,
                    )
                if max_translation_mm >= _POSITION_CONVERGENCE_MM:
                    inward_state, inward_distance = pair.evaluate(
                        -_POSITION_CONVERGENCE_MM, measurement="contact"
                    )
                    if inward_state == "interfering":
                        assert inward_distance is not None
                        span.set_attribute("certificate", "already_seated")
                        span.set_attribute("witness", "native_collision_bracket")
                        span.set_attribute(
                            "interfering_offset_mm", -_POSITION_CONVERGENCE_MM
                        )
                        span.set_attribute("clear_offset_mm", 0.0)
                        span.set_attribute("bracket_width_mm", _POSITION_CONVERGENCE_MM)
                        span.set_attribute(
                            "interfering_endpoint_distance_mm", inward_distance
                        )
                        span.set_attribute("final_distance_mm", seed_distance)
                        _warn_distance_disagreement(label, seed_distance)
                        return ContactSolution(
                            0.0,
                            -_POSITION_CONVERGENCE_MM,
                            0.0,
                            0,
                            "already_seated",
                            "native_collision_bracket",
                            seed_distance,
                        )
            lo, hi = -max_translation_mm, max_translation_mm
            if pair.evaluate(lo)[0] != "interfering":
                raise RuntimeError(
                    f"{label}: negative native bracket is not interfering ({lo:.17g} mm)"
                )
            if pair.evaluate(hi)[0] != "clear":
                raise RuntimeError(
                    f"{label}: positive native bracket is not clear ({hi:.17g} mm)"
                )
            while hi - lo > _POSITION_CONVERGENCE_MM:
                if iterations >= _MAX_ITERATIONS:
                    raise RuntimeError(
                        f"{label}: native contact bisection exhausted {_MAX_ITERATIONS} iterations"
                    )
                mid = lo + (hi - lo) / 2.0
                if not math.isfinite(mid) or not lo < mid < hi:
                    raise RuntimeError(
                        f"{label}: native contact bracket cannot converge"
                    )
                if pair.evaluate(mid)[0] == "interfering":
                    lo = mid
                else:
                    hi = mid
                iterations += 1
                span.set_attribute("iterations", iterations)
            low_state, low_distance = pair.evaluate(lo, measurement="contact")
            clear_state, clear_distance = pair.evaluate(hi, measurement="contact")
            assert low_distance is not None and clear_distance is not None
            span.set_attribute("interfering_endpoint_distance_mm", low_distance)
            span.set_attribute("final_distance_mm", clear_distance)
            if low_state != "interfering" or clear_state != "clear":
                raise RuntimeError(f"{label}: native contact final bracket is unstable")
            _warn_distance_disagreement(label, clear_distance)
            span.set_attribute("certificate", "bracketed_native_contact")
            span.set_attribute("witness", "native_collision_bracket")
            span.set_attribute("interfering_offset_mm", lo)
            span.set_attribute("clear_offset_mm", hi)
            span.set_attribute("bracket_width_mm", hi - lo)
            return ContactSolution(
                hi,
                lo,
                hi,
                iterations,
                "bracketed_native_contact",
                "native_collision_bracket",
                clear_distance,
            )
        finally:
            span.set_attribute("iterations", iterations)
            span.set_attribute("trials", pair.trials if pair is not None else 0)
            span.set_attribute("elapsed_s", time.monotonic() - started)
