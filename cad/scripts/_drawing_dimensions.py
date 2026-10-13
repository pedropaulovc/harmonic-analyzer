"""Drawing dimension text, references, precision and arc endpoints.

Dimensioned drawings apply text, references, precision and arc endpoints here
without coupling those edits to model-item import.
"""

from __future__ import annotations

from typing import Any, Iterable, Literal

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    TOL_BASIC,
    dimension_name,
    view_name,
)

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_scan import _span_scan_attrs
import _telemetry


def move_model_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a native model dimension and verify its new drawing-view owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    drawing.DragModelDimension(
        view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0
    )
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    matches = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(item, "IAnnotation")) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


_DIMENSION_TEXT_CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow


def set_dimension_callouts(
    adapter: Any,
    annotations: Iterable[Any],
    callout_text: dict[str, str],
    *,
    location: Literal["above", "below"] = "below",
) -> None:
    """Append native callout text above or below named dimensions.

    A bare Ø does not tell the machinist whether a hole is through or blind;
    ASME hole callouts carry that below the value.  Keyed on the parametric
    dimension name, so a value collision can never stamp the wrong hole.

    ``above`` is required when a datum feature symbol is attached to the same
    size dimension: SOLIDWORKS places that symbol between the primary value and
    the below-callout lane, while the above-callout lane remains unobstructed.
    """
    text_part = {
        "above": 3,  # swDimensionTextCalloutAbove
        "below": _DIMENSION_TEXT_CALLOUT_BELOW,
    }[location]
    remaining = dict(callout_text)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        text = remaining.pop(name, None)
        if text is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText"
        )
        adapter._attempt(lambda d=display, s=text: d.SetText(text_part, s))
    if remaining:
        raise RuntimeError(f"dimension callouts not applied: {sorted(remaining)}")

    # ``SetText`` takes effect immediately (``GetText`` reads it back without
    # a rebuild); the text EXTENT it changes is only read by the finalizer's
    # layout pass, which rebuilds first. 30 rebuilds on top-frame, ~14 s.


def set_dimension_text(
    adapter: Any, annotations: Iterable[Any], replacement: dict[str, str]
) -> None:
    """Replace the entire displayed text of named model dimensions.

    This is for associative size callouts whose model parameter is only the
    view carrier.  In particular, a schematic thread-minor cylinder must read
    as its thread designation rather than masquerading as a manufactured
    plain-diameter feature.
    """
    remaining = dict(replacement)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        text = remaining.pop(name, None)
        if text is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText", "GetText"
        )
        # SetText is void.  With swDimensionTextAll it stores the replacement
        # in the prefix compartment and suppresses the numeric value; GetText
        # explicitly rejects swDimensionTextAll, so read back the prefix.
        display.SetText(0, text)  # swDimensionTextAll
        if str(display.GetText(1) or "") != text:  # swDimensionTextPrefix
            raise RuntimeError(f"dimension text did not persist for {name!r}")
    if remaining:
        raise RuntimeError(f"dimension text not applied: {sorted(remaining)}")
    rebuild_drawing(adapter, label="set_dimension_text")


@_telemetry.traced("drawing.reference_dimension", label_param="label")
def set_reference_dimension(
    adapter: Any,
    annotation: Any,
    *,
    label: str,
    diameter: bool = False,
) -> Any:
    """Parenthesize one displayed nominal as an ASME reference dimension."""
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetSpecificAnnotation"
    )
    display = adapter._attempt(lambda: annotation.GetSpecificAnnotation())
    if display is None:
        raise RuntimeError(f"{label} has no display dimension")
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "SetText", "GetText"
    )
    prefix_text = "(<MOD-DIAM>" if diameter else "("
    display.SetText(1, prefix_text)  # swDimensionTextPrefix
    display.SetText(2, ")")  # swDimensionTextSuffix
    prefix = str(display.GetText(1) or "")
    suffix = str(display.GetText(2) or "")
    if (prefix, suffix) != (prefix_text, ")"):
        raise RuntimeError(
            f"failed to parenthesize {label}: prefix={prefix!r}, suffix={suffix!r}"
        )
    rebuild_drawing(adapter, label="set_reference_dimension")
    return display


@_telemetry.traced("drawing.dimension_precision")
def set_dimension_precision(
    adapter: Any, annotations: Iterable[Any], precision: dict[str, int]
) -> None:
    """Override the primary decimal places of specific NAMED dimensions.

    The document default (``set_units_mm``) is 2 decimals, which reads as false
    precision on most dims.  A dimension whose value is an exact conversion the
    notes cite to 3 places — e.g. the crank shaft bore, Ø9.525 = 3/8 in — must
    display 3 so the view matches the note (otherwise 9.53-on-view vs
    9.525-in-note reads as a contradiction).  Keyed on the parametric dimension
    name so a value collision can never repick the wrong dimension.

    The span carries how many annotations were SCANNED alongside how many were
    changed: recipes hand this collections of very different sizes, so without
    the scan count the duration cannot be attributed to its workload -- the same
    distinction the geometry scans in ``_gear_drawing_entities`` record.
    """
    # swDimensionPrecisionSettings_e.swDoNotChangePrecisionSetting: leave the
    # dual / tolerance precisions untouched, override only the primary.
    do_not_change = -1
    remaining = dict(precision)
    scanned = 0
    changed = 0
    for annotation in annotations:
        scanned += 1
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        digits = remaining.pop(name, None)
        if digits is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetPrecision3", "GetPrimaryPrecision2"
        )
        result = adapter._attempt(
            lambda d=display, n=digits: d.SetPrecision3(
                n, do_not_change, do_not_change, do_not_change
            )
        )
        if result is None:
            raise RuntimeError(f"failed to set precision on dimension {name!r}")
        # SetPrecision3 reports rejection via its RETURN STATUS, not by raising, so a
        # None-only check treats a failure code as success -- and the dim would ship
        # at the 2-decimal sheet default (Ø9.53) against a Ø9.525 note (codex #246).
        # The status enum's success value is undocumented, so verify the SIDE EFFECT:
        # read the primary precision back and confirm it took.
        applied = adapter._attempt(lambda d=display: d.GetPrimaryPrecision2())
        if applied != digits:
            raise RuntimeError(
                f"precision override on dimension {name!r} did not take: "
                f"requested {digits} decimals, dimension reports {applied}"
            )
        changed += 1
    _span_scan_attrs(scanned=scanned, changed=changed)
    if remaining:
        raise RuntimeError(f"dimension precision not applied: {sorted(remaining)}")
    rebuild_drawing(adapter, label="set_dimension_precision")


@_telemetry.traced("drawing.imported_precision")
def assert_imported_precision(
    adapter: Any, annotations: Iterable[Any], precision: dict[str, int]
) -> None:
    """Prove imported model dimensions kept their PART-authored decimal places.

    Policy rule 2 makes the model own display precision, so a migrated sheet
    may not rewrite it -- but it must still fail loud when an import loses the
    override, because a dimension that silently falls back to the drawing
    document's two-place default prints a tighter band than anyone specified.
    The read-only mirror of :func:`set_dimension_precision`: same name-keyed
    scan, ``GetPrimaryPrecision2`` only, and an unmatched name is an error.
    """
    remaining = dict(precision)
    scanned = 0
    for annotation in annotations:
        scanned += 1
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        digits = remaining.pop(name, None)
        if digits is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "GetPrimaryPrecision2"
        )
        applied = adapter._attempt(lambda d=display: d.GetPrimaryPrecision2())
        if applied != digits:
            raise RuntimeError(
                f"imported dimension {name!r} prints {applied} decimal places, but "
                f"its part authored {digits}; rebuild the source part"
            )
    _span_scan_attrs(scanned=scanned, changed=0)
    if remaining:
        raise RuntimeError(
            f"part-authored precision never reached the sheet: {sorted(remaining)}"
        )


@_telemetry.traced("drawing.reference_dimensions")
def set_reference_dimensions(
    adapter: Any, annotations: Iterable[Any], names: Iterable[str]
) -> None:
    """Parenthesize NAMED dimensions so they read as REFERENCE, not controlling.

    A fastener modeled at its thread MINOR diameter carries the real spec in a
    thread callout; the modeled OD is reference geometry, not a controlling
    dimension.  Showing that OD as a hard value contradicts the thread callout
    (a 5/16-18 thread's Ø6.20 minor cannot grow crests — codex machinist
    review), so the OD dim is boxed in parentheses: ASME reference-dimension
    notation.  Keyed on the parametric name so a value collision can never
    parenthesize the wrong dimension.  Fails loud if any name is unmatched.

    ``IDisplayDimension.ShowParenthesis`` only affects "text above the dimension
    line", which a leadered diameter callout does not have (it sets the flag but
    renders nothing), so instead bracket the value with a "(" prefix and ")"
    suffix via ``SetText`` — the same proven channel ``set_dimension_callouts``
    uses for the below-text — which renders on any dimension form.
    """
    text_prefix = 1  # swDimensionTextParts_e.swDimensionTextPrefix
    text_suffix = 2  # swDimensionTextParts_e.swDimensionTextSuffix
    # A custom prefix REPLACES the auto diameter glyph, so carry SolidWorks'
    # own "<MOD-DIAM>" token to keep the Ø on a diameter dim: "(Ø6.20)".
    open_paren = "(<MOD-DIAM>"
    wanted = set(names)
    marked: set[str] = set()
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in wanted:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText", "GetText"
        )
        adapter._attempt(lambda d=display: d.SetText(text_prefix, open_paren))
        adapter._attempt(lambda d=display: d.SetText(text_suffix, ")"))
        # SetText reports nothing, so verify the SIDE EFFECT: read the parts back
        # (a silent no-op would ship the OD as a controlling dim vs the thread).
        got_prefix = adapter._attempt(lambda d=display: d.GetText(text_prefix))
        got_suffix = adapter._attempt(lambda d=display: d.GetText(text_suffix))
        if str(got_prefix) != open_paren or str(got_suffix) != ")":
            raise RuntimeError(
                f"reference (parenthesis) mark on dimension {name!r} did not take: "
                f"prefix={got_prefix!r} suffix={got_suffix!r}"
            )
        marked.add(name)
    missing = wanted - marked
    if missing:
        raise RuntimeError(f"reference dimensions not applied: {sorted(missing)}")
    rebuild_drawing(adapter, label="set_reference_dimensions")


def offset_dimension_text(
    adapter: Any,
    annotations: Iterable[Any],
    positions: dict[str, tuple[float, float]],
) -> None:
    """Move named linear-dimension text off its dimension line with a leader."""
    remaining = dict(positions)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation", "SetPosition2"
        )
        name = dimension_name(adapter, annotation)
        position = remaining.pop(name, None)
        if position is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "OffsetText"
        )
        display.OffsetText = True
        if not annotation.SetPosition2(position[0], position[1], 0.0):
            raise RuntimeError(f"failed to offset dimension text {name!r}")
    if remaining:
        raise RuntimeError(f"dimension text not offset: {sorted(remaining)}")
    rebuild_drawing(adapter, label="offset_dimension_text")


_ARC_END_CENTER = 1  # swArcEndCondition_e.swArcEndConditionCenter


_ARC_END_MAX = 3  # swArcEndCondition_e.swArcEndConditionMax (furthest point)


def _set_arc_endpoints(
    adapter: Any, dimension: Any, *, condition: int, label: str
) -> Any:
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "GetDimension"
    )
    model_dimension = _early_bound(display.GetDimension(), "IDimension")
    draw = adapter.currentModel
    arc_end_set = False
    for index in (1, 2):
        if int(model_dimension.GetArcEndCondition(index)) == 0:
            continue
        result = int(model_dimension.SetArcEndCondition(index, condition))
        if result != 0:
            raise RuntimeError(
                f"failed to set {label} endpoint {index} to arc condition "
                f"{condition} (SolidWorks result {result})"
            )
        draw.GraphicsRedraw2()
        if int(model_dimension.GetArcEndCondition(index)) != condition:
            raise RuntimeError(f"{label} did not retain arc condition {condition}")
        arc_end_set = True
    if not arc_end_set:
        raise RuntimeError(f"{label} has no circular endpoint")
    return dimension


@_telemetry.traced("drawing.arc_center_endpoints", label_param="label")
def set_arc_endpoints_to_center(adapter: Any, dimension: Any, *, label: str) -> Any:
    """Re-anchor a dimension's circular endpoint(s) to the arc CENTER.

    A line-to-circle dimension keeps SolidWorks' default tangent/min-max arc
    condition, so the value locates the rim instead of the axis — off by the
    hole radius. Verify each flipped endpoint sticks; fail loud when the
    dimension has no circular endpoint at all.
    """
    return _set_arc_endpoints(
        adapter, dimension, condition=_ARC_END_CENTER, label=label
    )


@_telemetry.traced("drawing.arc_max_endpoints", label_param="label")
def set_arc_endpoints_to_max(adapter: Any, dimension: Any, *, label: str) -> Any:
    """Re-anchor a dimension's circular endpoint(s) to the arc's FURTHEST point.

    The overall length of a part with a rounded end runs to the arc's extreme,
    not its centre (a centre-anchored "overall" reads short by the radius and
    gets the stock sawn short -- Harvey #25).  SolidWorks resolves a
    line-to-arc pick to the centre by default, so the far-tangent condition is
    set explicitly and verified.
    """
    return _set_arc_endpoints(adapter, dimension, condition=_ARC_END_MAX, label=label)


def set_basic_dimension(adapter: Any, dimension: Any, *, label: str) -> Any:
    """Box a drawing-native locating dimension as BASIC and verify the result."""
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "GetDimension", "SetText", "GetText"
    )
    adapter._attempt(lambda: display.SetText(_DIMENSION_TEXT_CALLOUT_BELOW, ""))
    below_text = adapter._attempt(
        lambda: display.GetText(_DIMENSION_TEXT_CALLOUT_BELOW), default=""
    )
    if str(below_text or ""):
        raise RuntimeError(
            f"{label} BASIC dimension retained below-text {below_text!r}"
        )
    model_dimension = _sw_type_info.early_bound_or_flag(
        display.GetDimension(), "IDimension", "SetToleranceType", "GetToleranceType"
    )
    if model_dimension.SetToleranceType(TOL_BASIC) is not True:
        raise RuntimeError(f"failed to make {label} dimension BASIC")
    if int(model_dimension.GetToleranceType()) != TOL_BASIC:
        raise RuntimeError(f"{label} dimension did not retain BASIC tolerance")
    rebuild_drawing(adapter, label="set_basic_dimension")
    return dimension


def set_basic_dimensions(
    adapter: Any, annotations: Iterable[Any], names: Iterable[str]
) -> None:
    """Box named imported model dimensions as BASIC location dimensions."""
    remaining = set(names)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        set_basic_dimension(adapter, display, label=name)
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"dimensions not made BASIC: {sorted(remaining)}")
