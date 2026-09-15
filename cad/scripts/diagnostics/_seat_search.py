"""Native seat SEARCH for recalibrating ``cad/config/machine/springs.yaml``.

The production builds insert fixed measured placements and only certify them
(``_native_spring_contact.assert_native_contact``). This module is the search
that produced those placements: it moves one grounded component along a unit
direction, witnesses interference with the same native predicates the gate
uses, and closes a collision/clear bracket to 1e-6 mm. Each clear trial also
reads the native minimum distance ``d``: a rigid shift shorter than ``d``
cannot create overlap, so the next probe goes to ``hi - d`` (a few trials to
converge) and only falls back to the midpoint when that bound makes no
progress. Trial placements affect only that one component and are always
restored. No overlap volume is allowed and no clearance margin is ever added.

Driven by ``calibrate_spring_seats.py``; never imported by a build script.
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
from _native_spring_contact import native_component_interference

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
        self, offset_mm: float
    ) -> tuple[Literal["interfering", "clear"], float | None]:
        """Native state at ``offset_mm`` and, for a clear pose, its minimum distance."""
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
            state = self._interference_state(expected)
            self._assert_poses(expected)
            distance = self._distance_mm() if state == "clear" else None
            self._assert_poses(expected)
            return state, distance
        except BaseException as exc:
            primary = exc
            exc.add_note(
                f"{self.label}: native trial {self.trials}, offset={offset_mm:.17g} mm"
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
    steers where the next probe lands and is recorded at the clear endpoint
    (disagreement warns); it never decides a state and cannot overrule the
    native bracket. No distance margin is added. Recheck after applying the
    offset.
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
            seed_state, seed_distance = pair.evaluate(0.0)
            if seed_state == "clear":
                assert seed_distance is not None
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
                    inward_state, _ = pair.evaluate(-_POSITION_CONVERGENCE_MM)
                    if inward_state == "interfering":
                        span.set_attribute("certificate", "already_seated")
                        span.set_attribute("witness", "native_collision_bracket")
                        span.set_attribute(
                            "interfering_offset_mm", -_POSITION_CONVERGENCE_MM
                        )
                        span.set_attribute("clear_offset_mm", 0.0)
                        span.set_attribute("bracket_width_mm", _POSITION_CONVERGENCE_MM)
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
            hi_state, hi_distance = pair.evaluate(hi)
            if hi_state != "clear":
                raise RuntimeError(
                    f"{label}: positive native bracket is not clear ({hi:.17g} mm)"
                )
            assert hi_distance is not None
            jumps = 0
            steer = True
            previous_clear: tuple[float, float] | None = None
            use_secant = True
            while hi - lo > _POSITION_CONVERGENCE_MM:
                if iterations >= _MAX_ITERATIONS:
                    raise RuntimeError(
                        f"{label}: native contact bisection exhausted {_MAX_ITERATIONS} iterations"
                    )
                # Distance-guided step. A rigid shift shorter than the minimum
                # separation cannot create overlap, so from the clear endpoint
                # every offset in (hi - d, hi] is clear and the contact lies at
                # or below hi - d. Two clear readings also give a secant
                # estimate of where d reaches zero; the probe goes to the lower
                # of the two (the secant may only extend the proven bound). Once
                # d is below the convergence width the clear endpoint IS the
                # contact and one probe a width below it closes the bracket.
                # Only the native evaluations decide: a landing outside the
                # bracket falls back to the midpoint, and a closing probe that
                # comes back clear hands the rest to plain bisection.
                candidate = None
                closing = False
                by_secant = False
                if steer and hi_distance < _POSITION_CONVERGENCE_MM:
                    candidate = hi - _POSITION_CONVERGENCE_MM
                    closing = True
                elif steer:
                    candidate = hi - hi_distance
                    if (
                        use_secant
                        and previous_clear is not None
                        and previous_clear[1] > hi_distance
                    ):
                        offset, distance = previous_clear
                        secant = hi - hi_distance * (offset - hi) / (
                            distance - hi_distance
                        )
                        by_secant = secant < candidate
                        candidate = min(candidate, secant)
                if candidate is not None and not lo < candidate < hi:
                    candidate = None
                if candidate is None:
                    closing = False
                    candidate = lo + (hi - lo) / 2.0
                else:
                    jumps += 1
                if not math.isfinite(candidate) or not lo < candidate < hi:
                    raise RuntimeError(
                        f"{label}: native contact bracket cannot converge"
                    )
                state, distance = pair.evaluate(candidate)
                if state == "interfering":
                    lo = candidate
                    if by_secant:
                        use_secant = False  # d is concave in the offset; the bound alone converges
                else:
                    assert distance is not None
                    previous_clear = (hi, hi_distance)
                    hi, hi_distance = candidate, distance
                    if closing:
                        steer = False  # the distance under-reported the gap
                iterations += 1
                span.set_attribute("iterations", iterations)
            span.set_attribute("distance_jumps", jumps)
            span.set_attribute("final_distance_mm", hi_distance)
            _warn_distance_disagreement(label, hi_distance)
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
                hi_distance,
            )
        finally:
            span.set_attribute("iterations", iterations)
            span.set_attribute("trials", pair.trials if pair is not None else 0)
            span.set_attribute("elapsed_s", time.monotonic() - started)
