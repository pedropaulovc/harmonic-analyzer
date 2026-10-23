"""Opt-in measured text shelves for source-bound linear screw references.

The part-authoring lane planner stays pure. Existing screw annotation and
readback retain source/value/format/attachment authority; the generic shelf
core owns only measured text movement and unchanged native stations.
"""
from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from functools import partial
from typing import Any

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _supplier_reference_text import (
    assert_reference_text_stations,
    measure_reference_text,
    shelve_reference_text,
)
from _supplier_screw_dimensions import (
    _binding,
    annotate_supplier_screw,
    assert_supplier_screw,
)
import _telemetry


# swDisplayDimensionLeaderText_e.swBrokenLeaderAlignedText.
_BROKEN_LINE_ALIGNED_TEXT = 3


@_telemetry.traced("drawing.supplier_screw_broken_lines", label_param="label")
def _break_reference_lines(
    adapter: Any,
    *,
    reacquire: Callable[[], dict[str, Any]],
    axes: Mapping[str, int],
    names: Collection[str],
    label: str,
) -> Callable[[], dict[str, Any]]:
    """Apply local line breaks without adopting post-style stations as authority."""
    rebuild_drawing(adapter, label=f"{label} original reference line stations")
    found = reacquire()
    stations = {}
    setter_statuses = {}
    for name in names:
        geometry = measure_reference_text(
            adapter, found[name], axis=axes[name], label=f"{label} {name}"
        )
        stations[name] = geometry
    for name in names:
        display = _early_bound(found[name], "IDisplayDimension")
        status = display.SetBrokenLeader2(False, _BROKEN_LINE_ALIGNED_TEXT)
        # SDK: 0 succeeds; -1 fails; 1 silently falls back to the document default.
        # bool is not the SDK integer status, even though False compares equal to 0.
        if type(status) is not int or status != 0:
            raise RuntimeError(
                f"{label} {name}: failed to break supplier reference line: "
                f"status={status!r}"
            )
        setter_statuses[name] = status
    rebuild_drawing(adapter, label=f"{label} local broken reference lines")
    _early_bound(adapter.currentModel, "IModelDoc2").GraphicsRedraw2()

    @_telemetry.traced("drawing.supplier_screw_broken_line_check")
    def checked_reacquire() -> dict[str, Any]:
        found = reacquire()
        for name, original in stations.items():
            display = _early_bound(found[name], "IDisplayDimension")
            mode = display.GetBrokenLeader2()
            use_doc = display.GetUseDocBrokenLeader()
            if (
                type(mode) is not int
                or mode != _BROKEN_LINE_ALIGNED_TEXT
                or use_doc is not False
            ):
                raise RuntimeError(
                    f"{label} {name}: local broken supplier reference line did not persist: "
                    f"mode={mode!r}, use_doc={use_doc!r}"
                )
            actual = measure_reference_text(
                adapter, display, axis=axes[name], label=f"{label} {name}"
            )
            try:
                assert_reference_text_stations(original, actual, label=f"{label} {name}")
            except RuntimeError as error:
                try:
                    # Keep native array order/indices and exact held coordinates.
                    # The reader already rounds to 0.1 um; do not round again
                    # or invent an entity identity from an arrow array index.
                    _telemetry.event(
                        "drawing.supplier_screw_broken_line_station_failure",
                        label=label,
                        reference=name,
                        setter_status=setter_statuses[name],
                        broken_line_mode=mode,
                        use_doc_broken_line=use_doc,
                        coordinate_basis="held native audit record, metres, 0.1 um",
                        native_array_order="unchanged IDisplayData index order",
                        before={
                            key: original[key]
                            for key in ("axis", "tips", "witnesses", "record")
                        },
                        after={
                            key: actual[key]
                            for key in ("axis", "tips", "witnesses", "record")
                        },
                        error=str(error),
                    )
                except Exception:
                    # Only the diagnostic is best-effort, never the failed proof.
                    pass
                raise
        return found

    checked_reacquire()
    return checked_reacquire


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
    broken_lines: Collection[str] = (),
) -> dict[str, Any]:
    """Annotate, shelf short full text, and return fresh authoritative displays.

    Only linear reference carriers opt in. The caller uses the identical side
    plan for pre-fit margins and keeps its complete native/PDF collision guards.
    Original view/source/configuration bindings survive every rebuild and the
    final read-only proof; no stale display mapping becomes readback authority.
    ``broken_lines`` opts named carriers into the local SDK aligned-text line
    break, preserving their complete original native arrow/witness stations
    through styling, shelving and every fresh read-only final proof. The empty
    default adds no style getters, setters, measurements, rebuilds or redraws.
    Printed-parenthesis clearance still requires the final exported PDF audit.
    """
    axes = {}
    for name, _value, orientation in dimensions:
        if orientation not in ("horizontal", "vertical"):
            raise ValueError(f"{label} {name}: text shelves require a linear reference")
        axes[name] = 0 if orientation == "horizontal" else 1
    broken_lines = frozenset(broken_lines)
    if broken_lines - axes.keys():
        raise ValueError(f"{label}: broken lines must name actual references")
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
        settled_checks=None if broken_lines else settled_checks,
    )
    reacquire: Callable[[], dict[str, Any]] = partial(
        assert_supplier_screw,
        adapter,
        views,
        dimensions=dimensions,
        formats=formats,
        planes=planes,
        units=units,
        _bindings=bindings,
    )
    if broken_lines:
        reacquire = _break_reference_lines(
            adapter, reacquire=reacquire, axes=axes, names=broken_lines, label=label
        )

        def settled_source() -> None:
            reacquire()

        settled_checks.append(settled_source)
    proof = shelve_reference_text(
        adapter, reacquire=reacquire, axes=axes, label=label, force=force
    )
    settled_checks.append(proof)
    return reacquire()
