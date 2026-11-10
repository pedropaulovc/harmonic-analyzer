"""A blind reamed hole's native callout on a plain (non-Hole-Wizard) cut.

``IDrawingDoc.AddHoleCallout2`` on a cut-extruded hole's rim writes the
format definitions ``{5: '<MOD-DIAM>', 6: '<HOLE-DEPTH>.20', 7: '', 8: ''}``
(swDimensionTextParts_e 5..8: prefix, suffix, callout above, callout below;
PR 2 r7 of the cone gear shaft socket).  The size prints from the cut's own
diameter dimension with its model band.  The depth is the literal
SolidWorks resolved from the cut at insertion, so every regenerated sheet
prints the model's value, never a typed one.  This module joins the process
before the depth (drawing-guidelines.md rule 26: size, process, depth) and
an optional flag below, then reads back the size, band and depth it prints,
failing loud with the definitions dumped.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_hole_callout import add_native_hole_callout
import _telemetry

DEPTH_TOKEN = "<HOLE-DEPTH>"
# Format definitions (swDimensionTextParts_e 5..8) and the part 1..4 each is
# written through (draw_dt_crankshaft._DEFINITION_TO_WRITABLE).
DEFINITION_TO_WRITABLE = {5: 1, 6: 2, 7: 3, 8: 4}
CALLOUT_BELOW_DEFINITION = 8
# swTolType_e
_TOL_NONE = 0
_TOL_BILAT = 2


def ream_definitions(
    definitions: Mapping[int, str], *, process: str, below: str, label: str
) -> dict[int, str]:
    """``definitions`` with ``process`` joined before the one native depth and
    ``below`` (if any) in the below compartment.

    Exactly one definition may carry ``<HOLE-DEPTH>``, once, followed by the
    depth alone (draw_dt_crankshaft._depth_banded_definition's contract); the
    below compartment must be empty unless it is that one.  Anything else
    (no depth, two, text after it, the process or ``below`` already there)
    fails loud, naming the definitions.
    """
    current = dict(definitions)
    if set(current) != set(DEFINITION_TO_WRITABLE):
        raise RuntimeError(f"{label} callout: unexpected format parts {current!r}")
    holders = [part for part, text in current.items() if DEPTH_TOKEN in text]
    joined = "\n".join(current.values())
    if (
        len(holders) != 1
        or re.search(rf"\b{re.escape(process)}\b", joined)
        or (below and below in joined)
    ):
        raise RuntimeError(f"{label} callout has no single native depth: {current!r}")
    part = holders[0]
    head, _marker, tail = current[part].rpartition(DEPTH_TOKEN)
    if DEPTH_TOKEN in head or len(tail.split()) != 1:
        raise RuntimeError(f"{label} callout has no single native depth: {current!r}")
    updated = dict(current)
    updated[part] = f"{head.rstrip()} {process} {DEPTH_TOKEN}{tail.rstrip()}"
    if not below:
        return updated
    slot = CALLOUT_BELOW_DEFINITION
    if part == slot:
        updated[slot] = f"{updated[slot]}\n{below}"
    elif current[slot].strip():
        raise RuntimeError(f"{label} callout's below compartment is taken: {current!r}")
    else:
        updated[slot] = below
    return updated


def printed_depth(definitions: Mapping[int, str], *, label: str) -> str:
    """The depth text that follows the one ``<HOLE-DEPTH>``."""
    texts = [text for text in definitions.values() if DEPTH_TOKEN in text]
    if len(texts) != 1 or texts[0].count(DEPTH_TOKEN) != 1:
        raise RuntimeError(
            f"{label} callout has no single native depth: {dict(definitions)!r}"
        )
    return texts[0].rpartition(DEPTH_TOKEN)[2].split("\n")[0].strip()


def require_printed_size(
    display: Any,
    *,
    dia_mm: float,
    deviations_mm: tuple[float, float] | None,
    definitions: Mapping[int, str],
    label: str,
) -> None:
    """The callout's own dimension (``GetDimension2(0)``) is the hole's
    diameter, ``dia_mm``, with its model band ``deviations_mm`` (lower, upper
    mm, swTolBILAT) or none (swTolNONE).

    The callout's dimension is its own: its name reads empty (PR 2 r7), so
    the hole is known by its value.  Fails loud with the definitions.
    """
    raw = display.GetDimension2(0)
    if raw is None:
        raise RuntimeError(
            f"{label} callout carries no dimension: {dict(definitions)!r}"
        )
    dimension = _early_bound(raw, "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    value = float(dimension.SystemValue)
    kind = int(tolerance.Type)
    minimum = float(tolerance.GetMinValue())
    maximum = float(tolerance.GetMaxValue())
    if deviations_mm is None:
        wanted_kind, lower, upper = _TOL_NONE, 0.0, 0.0
        band_ok = kind == wanted_kind
    else:
        wanted_kind = _TOL_BILAT
        lower, upper = (deviation / 1000.0 for deviation in deviations_mm)
        band_ok = (
            kind == wanted_kind
            and abs(minimum - lower) <= 1e-9
            and abs(maximum - upper) <= 1e-9
        )
    if abs(value - dia_mm / 1000.0) > 1e-9 or not band_ok:
        raise RuntimeError(
            f"{label} callout does not print its size: dimension {value:g} m, "
            f"tolerance type {kind} {minimum:g}/{maximum:g} m (wanted "
            f"{dia_mm / 1000.0:g} m, type {wanted_kind} {lower:g}/{upper:g} m); "
            f"definitions {dict(definitions)!r}"
        )


@_telemetry.traced("drawing.blind_ream_callout", label_param="label")
def add_blind_ream_callout(
    adapter: Any,
    view: Any,
    *,
    edge: Any,
    callout_xy: tuple[float, float],
    label: str,
    dia_mm: float,
    deviations_mm: tuple[float, float] | None,
    depth_text: str,
    process: str = "REAM",
    below: str = "",
) -> Any:
    """Call out a blind reamed cut natively on its rim ``edge`` in ``view``.

    SolidWorks prints the cut's diameter, band and depth; ``process`` joins
    before the depth and ``below`` goes under it, each written into the format
    definitions and read back.  The printed size must be ``dia_mm`` with
    ``deviations_mm`` and the printed depth ``depth_text`` (the model's depth
    at its drawing places), else it fails loud.  Returns the callout's
    annotation.
    """
    display = add_native_hole_callout(
        adapter, view, callout_xy=callout_xy, label=label, edge=edge
    )
    display = _early_bound(display, "IDisplayDimension")
    definitions = {
        part: str(display.GetText(part) or "") for part in DEFINITION_TO_WRITABLE
    }
    _telemetry.info(f"{label} callout definitions: {definitions!r}")
    updated = ream_definitions(definitions, process=process, below=below, label=label)
    for part, text in updated.items():
        if text == definitions[part]:
            continue
        display.SetText(DEFINITION_TO_WRITABLE[part], text)
        applied = str(display.GetText(part) or "")
        if applied.replace("\r", "") != text.replace("\r", ""):
            raise RuntimeError(
                f"{label} callout part {part} did not persist: {applied!r}, "
                f"wanted {text!r}; definitions {definitions!r}"
            )
    depth = printed_depth(updated, label=label)
    if depth != depth_text:
        raise RuntimeError(
            f"{label} callout prints depth {depth!r}, wanted {depth_text!r}; "
            f"definitions {updated!r}"
        )
    require_printed_size(
        display,
        dia_mm=dia_mm,
        deviations_mm=deviations_mm,
        definitions=updated,
        label=label,
    )
    rebuild_drawing(adapter, label=f"{label} callout")
    return display.GetAnnotation()
