"""Opt-in measured text shelves for source-bound linear screw references.

The part-authoring lane planner stays pure. Existing screw annotation and
readback retain source/value/format/attachment authority; the generic shelf
core owns only measured text movement and unchanged native stations.
"""
from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from functools import partial
from typing import Any

from _supplier_reference_text import shelve_reference_text
from _supplier_screw_dimensions import (
    _binding,
    annotate_supplier_screw,
    assert_supplier_screw,
)


def annotate_supplier_screw_with_shelves(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    dimensions: Sequence[tuple[str, float, str]],
    formats: Mapping[str, tuple[int, str, int | None, str | None]],
    settled_checks: list[Callable[[], None]],
    label: str,
    starts: Mapping[str, tuple[float, float]] | None = None,
    planes: Mapping[str, str] | None = None,
    sides: Mapping[str, str] | None = None,
    units: Mapping[str, str] | None = None,
    force: Collection[str] = (),
) -> dict[str, Any]:
    """Annotate, shelf short full text, and return fresh authoritative displays.

    Only linear reference carriers opt in. The caller uses the identical side
    plan for pre-fit margins and keeps its complete native/PDF collision guards.
    Original view/source/configuration bindings survive every rebuild and the
    final read-only proof; no stale display mapping becomes readback authority.
    """
    axes = {}
    for name, _value, orientation in dimensions:
        if orientation not in ("horizontal", "vertical"):
            raise ValueError(f"{label} {name}: text shelves require a linear reference")
        axes[name] = 0 if orientation == "horizontal" else 1
    bindings = {key: _binding(adapter, view) for key, view in views.items()}
    annotate_supplier_screw(
        adapter,
        views,
        dimensions=dimensions,
        formats=formats,
        starts=starts,
        planes=planes,
        sides=sides,
        units=units,
        settled_checks=settled_checks,
    )
    reacquire = partial(
        assert_supplier_screw,
        adapter,
        views,
        dimensions=dimensions,
        formats=formats,
        planes=planes,
        units=units,
        _bindings=bindings,
    )
    proof = shelve_reference_text(
        adapter, reacquire=reacquire, axes=axes, label=label, force=force
    )
    settled_checks.append(proof)
    return reacquire()
