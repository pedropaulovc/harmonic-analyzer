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
from _purchased_fastener_drawing import _note_text_style
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


# swVerticalJustification_e.swVerticalJustificationTop, not document Top=0.
_TOP_JUSTIFICATION = 1


@_telemetry.traced("drawing.supplier_screw_top_text", label_param="label")
def _top_justify_reference_text(
    adapter: Any,
    *,
    reacquire: Callable[[], dict[str, Any]],
    axes: Mapping[str, int],
    names: Collection[str],
    label: str,
) -> Callable[[], dict[str, Any]]:
    """Justify native text locally without adopting changed physical stations."""
    def justification(display: Any, name: str) -> int:
        value = display.VerticalJustification
        if type(value) is not int or value not in (0, 1, 2, 3):
            raise RuntimeError(
                f"{label} {name}: unreadable native vertical justification: {value!r}"
            )
        return value

    def text_style(display: Any, name: str) -> tuple[Any, bool]:
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        # Display dimensions share one format; the SDK requires index zero.
        count = annotation.GetTextFormatCount()
        if type(count) is not int or count != 1:
            raise RuntimeError(
                f"{label} {name}: unsupported native dimension format count {count!r}"
            )
        formats = _note_text_style(annotation)
        if len(formats) != 1:
            raise RuntimeError(f"{label} {name}: native dimension format count changed")
        use_doc = annotation.GetUseDocTextFormat(0)
        if type(use_doc) is not bool:
            raise RuntimeError(
                f"{label} {name}: unreadable native font inheritance: {use_doc!r}"
            )
        # Native primitive types matter too; do not equate False with integer 0.
        typed_formats = tuple(
            tuple((field, type(value).__name__, value) for field, value in fields)
            for fields in formats
        )
        return typed_formats, use_doc

    rebuild_drawing(adapter, label=f"{label} original reference text stations")
    found = reacquire()
    stations = {}
    styles = {}
    initial_justifications = {}
    # Validate every opted-in carrier before any justification write.
    for name in names:
        display = _early_bound(found[name], "IDisplayDimension")
        initial_justifications[name] = justification(display, name)
        styles[name] = text_style(display, name)
        stations[name] = measure_reference_text(
            adapter, display, axis=axes[name], label=f"{label} {name}"
        )
    for name in names:
        if initial_justifications[name] != _TOP_JUSTIFICATION:
            display = _early_bound(found[name], "IDisplayDimension")
            # SDK property-put is VOID; only fresh getter readback proves it.
            display.VerticalJustification = _TOP_JUSTIFICATION
    rebuild_drawing(adapter, label=f"{label} local top-justified reference text")
    _early_bound(adapter.currentModel, "IModelDoc2").GraphicsRedraw2()

    @_telemetry.traced("drawing.supplier_screw_top_text_check")
    def checked_reacquire() -> dict[str, Any]:
        found = reacquire()
        for name, original in stations.items():
            display = _early_bound(found[name], "IDisplayDimension")
            actual_justification = justification(display, name)
            if actual_justification != _TOP_JUSTIFICATION:
                raise RuntimeError(
                    f"{label} {name}: top text justification did not persist: "
                    f"actual={actual_justification!r}"
                )
            actual_style = text_style(display, name)
            actual = measure_reference_text(
                adapter, display, axis=axes[name], label=f"{label} {name}"
            )
            try:
                if actual_style != styles[name]:
                    raise RuntimeError(
                        f"{label} {name}: supplier reference native font/binding changed"
                    )
                if tuple(row["t"] for row in actual["record"]["display"]["texts"]) != tuple(
                    row["t"] for row in original["record"]["display"]["texts"]
                ):
                    raise RuntimeError(
                        f"{label} {name}: supplier reference native text changed"
                    )
                assert_reference_text_stations(original, actual, label=f"{label} {name}")
            except RuntimeError as error:
                try:
                    # These are held records, rounded to 0.1 um by the reader,
                    # not raw native doubles or invented entity identities.
                    _telemetry.event(
                        "drawing.supplier_screw_text_justification_station_failure",
                        label=label,
                        reference=name,
                        original_justification=initial_justifications[name],
                        actual_justification=actual_justification,
                        original_font=styles[name],
                        actual_font=actual_style,
                        coordinate_basis="held native audit record, metres, 0.1 um",
                        native_array_order="unchanged IDisplayData index order",
                        before={
                            key: original[key]
                            for key in ("axis", "tips", "witnesses", "physical_lines", "record")
                        },
                        after={
                            key: actual[key]
                            for key in ("axis", "tips", "witnesses", "physical_lines", "record")
                        },
                        error=str(error),
                    )
                except BaseException:
                    pass  # Only secondary reporting is best-effort.
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
    top_justified: Collection[str] = (),
) -> dict[str, Any]:
    """Annotate, shelf short full text, and return fresh authoritative displays.

    Only linear reference carriers opt in. The caller uses the identical side
    plan for pre-fit margins and keeps its complete native/PDF collision guards.
    Original view/source/configuration bindings survive every rebuild and the
    final read-only proof; no stale display mapping becomes readback authority.
    ``top_justified`` opts named carriers into the dimension-local native Top
    text justification, retaining original stations, complete effective font
    and document/local font binding at every fresh read-only proof. The empty
    default adds no justification/font reads, writes, rebuilds or redraws.
    Printed-parenthesis clearance still requires the final exported PDF audit.
    """
    axes = {}
    for name, _value, orientation in dimensions:
        if orientation not in ("horizontal", "vertical"):
            raise ValueError(f"{label} {name}: text shelves require a linear reference")
        axes[name] = 0 if orientation == "horizontal" else 1
    top_justified = frozenset(top_justified)
    if top_justified - axes.keys():
        raise ValueError(f"{label}: top-justified text must name actual references")
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
        settled_checks=None if top_justified else settled_checks,
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
    if top_justified:
        reacquire = _top_justify_reference_text(
            adapter, reacquire=reacquire, axes=axes, names=top_justified, label=label
        )

        def settled_source() -> None:
            reacquire()

        settled_checks.append(settled_source)
    proof = shelve_reference_text(
        adapter, reacquire=reacquire, axes=axes, label=label, force=force
    )
    settled_checks.append(proof)
    return reacquire()
