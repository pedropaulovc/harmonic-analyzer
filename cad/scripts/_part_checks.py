"""Part volume, measurement and bounding-box checks.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _com import _early_bound


@_telemetry.traced("check.volume", label_param="label")
async def volume_check(adapter: Any, label: str, expected: float, tol: float) -> float:
    """Assert the part volume (mm^3) and return it."""
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"{label}: get_mass_properties failed: {mass.error}")
    volume = float(mass.data.volume)
    if abs(volume - expected) > tol:
        raise RuntimeError(
            f"{label}: volume {volume:.1f} mm^3, expected {expected:.1f} "
            f"(+/- {tol:.1f})"
        )
    _telemetry.success(f"{label}: volume {volume:.1f} mm^3 (analytic {expected:.1f})")
    return volume


@_telemetry.traced("check.measure", label_param="label")
async def measure_check(
    adapter: Any,
    label: str,
    entities: list[dict[str, Any]],
    key: str,
    expected: float,
    tol: float = 0.01,
) -> None:
    """Measure entities and assert ``key`` equals ``expected`` (mm/mm²/deg).

    ``entities`` are ``MeasureEntityRef`` kwargs, e.g.
    ``{"entity_type": "EDGE", "point": [x, y, z]}`` or
    ``{"entity_type": "PLANE", "name": "Front Plane"}``. Point-based
    selection is view-dependent (screen projection) — use points visible
    in the default view, same caveat as the live regression suite.
    """
    from solidworks_mcp.adapters.base import MeasureEntityRef, MeasureParameters

    # Point selection projects through the screen, so the whole part must be
    # in the viewport — long parts otherwise miss their far faces.
    adapter._zoom_to_fit(adapter.currentModel)

    refs = [MeasureEntityRef(**entity) for entity in entities]
    res = await adapter.measure(MeasureParameters(entities=refs))
    if not res.is_success:
        raise RuntimeError(f"measure {label} failed: {res.error}")
    value = res.data.get(key)
    if value is None:
        raise RuntimeError(f"measure {label}: no {key!r} in {res.data!r}")
    if abs(value - expected) > tol:
        raise RuntimeError(
            f"measure {label}: {key}={value} outside {expected} +/- {tol}"
        )
    _telemetry.success(f"measure {label}: {key}={value:.4f} (expected {expected:g})")


@_telemetry.traced("check.bbox", label_param="label")
async def bbox_extent_check(
    adapter: Any,
    label: str,
    axis: str,
    expected: float,
    tol: float = 0.05,
) -> None:
    """Assert the part's solid bounding-box extent along ``axis`` (mm).

    The view-independent replacement for a face-to-face ``normal_distance``
    measure of an overall width/height/length. ``measure_check`` selected the
    two opposite faces by a screen-projected point each, but mutually-occluding
    faces collapse to a single pick in every standard view (one face hides the
    other), so the measure came back single-faced -- the same screen-projection
    trap the bar-length measure already dodges with a silhouette edge. Reading
    the bounding box needs no face picking at all.

    Unions the solid bodies' precise extreme points along ``axis`` so an
    unabsorbed, shown sketch can't inflate the extent. Only valid when the measured
    faces ARE the part's bounding faces along ``axis`` (true for these overall-size
    annotations); a feature protruding past them would read larger.

    Uses ``IBody2::GetExtremePoint`` (the exact farthest vertex in a direction),
    NOT ``IBody2::GetBodyBox`` -- the latter is documented as an approximate box
    that varies after rebuilds, so a 0.05 mm gate on it can pass/fail
    nondeterministically (codex review #9).
    """
    index = {"x": 0, "y": 1, "z": 2}[axis]
    pos = [1.0 if i == index else 0.0 for i in range(3)]
    neg = [-v for v in pos]

    def _extreme(body: Any, direction: list[float]) -> float:
        # IBody2::GetExtremePoint(Px,Py,Pz): direction in, the extreme point
        # comes back through three [out] doubles (metres). The early-bound makepy
        # wrapper collects the [out] params into the return tuple
        # (retval_bool, X, Y, Z), so pass only the 3 [in] direction components --
        # NOT the late-binding byref VARIANTs. Returns the axis coord in mm.
        body = _early_bound(body, "IBody2")
        res = adapter._attempt(
            lambda: body.GetExtremePoint(direction[0], direction[1], direction[2]),
            default=None,
        )
        if not res or len(res) < 4:
            raise RuntimeError(f"bbox {label}: GetExtremePoint failed")
        return res[1 + index] * 1000.0

    doc = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = adapter._attempt(lambda: doc.GetBodies2(0, False)) or []  # solid
    if not bodies:
        raise RuntimeError(f"bbox {label}: part has no solid bodies")
    lo, hi = float("inf"), float("-inf")
    for body in bodies:
        lo = min(lo, _extreme(body, neg))
        hi = max(hi, _extreme(body, pos))
    extent = hi - lo
    if abs(extent - expected) > tol:
        raise RuntimeError(
            f"bbox {label}: {axis}-extent={extent:.4f} outside {expected} +/- {tol}"
        )
    _telemetry.success(
        f"bbox {label}: {axis}-extent={extent:.4f} (expected {expected:g})"
    )


async def report_mass_properties(adapter: Any) -> None:
    """Print volume/bounding data for the eyeball-vs-DIMENSIONS.md check."""
    res = await adapter.get_mass_properties()
    if res.is_success:
        _telemetry.debug(f"mass properties: {res.data!r}")
        return
    _telemetry.warn(f"get_mass_properties failed: {res.error}")
