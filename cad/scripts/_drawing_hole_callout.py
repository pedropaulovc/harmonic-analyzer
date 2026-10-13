"""Native hole-callout authoring, selected-entity diagnostics and precision.

Hole-Wizard drawings use native callout formatting and selected-entity
diagnostics here, while other sheets need neither concern.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any, Callable, Mapping

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_selection import _select_view_entity
import _seat_forensics
import _telemetry


# swSelectType_e names for the kinds a drawing-view pick can resolve to; an
# unlisted code is reported as its number, never mapped to a guess.
_SELECT_TYPE_NAMES = {
    0: "NOTHING",
    1: "EDGE",
    2: "FACE",
    3: "VERTEX",
    9: "SKETCH",
    10: "SKETCHSEGMENT",
    11: "SKETCHPOINT",
    12: "DRAWINGVIEW",
    13: "GTOL",
    14: "DIMENSION",
    15: "NOTE",
    20: "COMPONENT",
    24: "EXTSKETCHSEGMENT",
    25: "EXTSKETCHPOINT",
    28: "CENTERMARKS",
    35: "SFSYMBOL",
    46: "SILHOUETTE",
    103: "CENTERLINE",
}


def _probe(
    bag: dict[str, Any], key: str, read: Callable[[], Any], *, record: bool = True
) -> Any:
    """Record ONE forensic read in ``bag`` -- its value, or its own failure.

    A description that cannot be read must say so under ``<key>_error`` and
    let the next read run: this executes on the success path of every hole
    callout (the BEFORE snapshot) and on the failure path after a refusal,
    and a diagnostic that raises there either fails a good sheet or masks the
    real failure.
    ``record=False`` keeps only the failure (for wrapper bindings, whose value
    is a COM object no telemetry channel can carry).
    """
    try:
        value = read()
    except Exception as exc:  # noqa: BLE001 - forensics never raise (see above)
        bag[f"{key}_error"] = f"{type(exc).__name__}: {exc}"
        return None
    if record:
        bag[key] = value
    return value


def _feature_identity(face: Any) -> str:
    """``<feature name>(<feature type>)`` of the feature that owns ``face``."""
    feature = _early_bound(face, "IFace2").GetFeature()
    if feature is None:
        return "<no feature>"
    feature = _early_bound(feature, "IFeature")
    return f"{feature.Name}({feature.GetTypeName2()})"


def describe_selected_entity(
    adapter: Any,
    view: Any,
    entity: Any,
    *,
    entity_type: str,
    requested_xy: tuple[float, float] | None,
    label: str,
) -> dict[str, Any]:
    """What a drawing-view pick actually resolved to, as scalar telemetry fields.

    The failure this exists for: ``AddHoleCallout2`` answered ``None`` to a
    coordinate pick that had succeeded (drawing:ch_rocker_arm, worker5,
    2026-09-20) and the leaf log could not say whether the selected EDGE was
    the hole rim, the strap arc 2.3 sheet-mm below it, or the hidden back-face
    rim under it. Recorded: the view (name, scale, position, outline), the
    requested sheet point, the selection set (count and every entry's
    ``swSelectType_e``), and for an edge its curve (circle centre/radius or
    line endpoints, model mm), its vertices and the feature owning each
    adjacent face -- which names the hole feature, or does not.

    Called only at the hole-callout boundary (:func:`add_native_hole_callout`),
    not on every pick: it is ~10 COM reads per call, and a generic pick has
    nothing to compare them against. Every read is guarded (:func:`_probe`);
    a value that could not be read is reported as ``<key>_error`` rather than
    raising. Values are scalars or JSON strings so they ride a span event, a
    log record and ``capture.json`` unchanged.
    """
    bag: dict[str, Any] = {
        "label": label,
        "entity_type": entity_type,
        "pick": "coordinate" if requested_xy is not None else "entity",
    }
    if requested_xy is not None:
        bag["requested_x"] = float(requested_xy[0])
        bag["requested_y"] = float(requested_xy[1])
    _probe(bag, "view_name", lambda: view_name(adapter, view))
    bound_view = _probe(bag, "view", lambda: _early_bound(view, "IView"), record=False)
    if bound_view is not None:
        _probe(bag, "view_scale", lambda: float(bound_view.ScaleDecimal))
        _probe(
            bag,
            "view_position",
            lambda: json.dumps([float(v) for v in bound_view.Position]),
        )
        _probe(
            bag,
            "view_outline",
            lambda: json.dumps([float(v) for v in bound_view.GetOutline()]),
        )
    selection_manager = _probe(
        bag,
        "selection_manager",
        lambda: _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr"),
        record=False,
    )
    count = None
    if selection_manager is not None:
        count = _probe(
            bag,
            "selected_count",
            lambda: int(selection_manager.GetSelectedObjectCount2(-1)),
        )
    if count:
        _probe(
            bag,
            "selected_types",
            lambda: json.dumps(
                [
                    _SELECT_TYPE_NAMES.get(code, code)
                    for code in (
                        int(selection_manager.GetSelectedObjectType3(index, -1))
                        for index in range(1, count + 1)
                    )
                ]
            ),
        )
    kind = entity_type.upper()
    if kind == "SILHOUETTE":
        _probe(
            bag,
            "face_feature",
            lambda: _feature_identity(
                _early_bound(entity, "ISilhouetteEdge").GetFace()
            ),
        )
        return bag
    if kind != "EDGE":
        return bag
    edge = _probe(bag, "edge", lambda: _early_bound(entity, "IEdge"), record=False)
    if edge is None:
        return bag
    curve = _probe(
        bag, "curve", lambda: _early_bound(edge.GetCurve(), "ICurve"), record=False
    )
    if curve is not None:
        if _probe(bag, "is_circle", lambda: bool(curve.IsCircle())):
            # CircleParams = (centre xyz, axis xyz, radius), metres -- ONE
            # property read, then sliced.
            def circle_mm() -> str:
                params = [float(v) for v in curve.CircleParams]
                return json.dumps(
                    [round(v * 1000.0, 4) for v in params[:3]]
                    + [round(params[6] * 1000.0, 4)]
                )

            _probe(bag, "circle_mm", circle_mm)
        elif _probe(bag, "is_line", lambda: bool(curve.IsLine())):
            _probe(
                bag,
                "line_mm",
                lambda: json.dumps(
                    [
                        [
                            round(float(v) * 1000.0, 4)
                            for v in _early_bound(vertex, "IVertex").GetPoint()
                        ]
                        for vertex in (edge.GetStartVertex(), edge.GetEndVertex())
                    ]
                ),
            )
    _probe(
        bag,
        "adjacent_features",
        lambda: json.dumps(
            [
                _feature_identity(face)
                for face in (edge.GetTwoAdjacentFaces2() or ())
                if face is not None
            ]
        ),
    )
    return bag


def compose_hole_callout_prefix(process: str, existing: str) -> str:
    """The hole callout's prefix definition: ``process`` ahead of the native
    format text.  A process ending in a line break puts the native size on
    its own row; otherwise the two join with one space.  (Stripping the
    break put the post's whole size row on one 117 mm line: RD1 probe,
    917-s1-rd1probe.)"""
    separator = "\n" if process.rstrip(" ").endswith("\n") else " "
    return process.rstrip() + separator + existing.lstrip()


@_telemetry.traced("drawing.hole_callout", label_param="label")
def add_native_hole_callout(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float] | None = None,
    callout_xy: tuple[float, float],
    label: str,
    edge: Any | None = None,
    process: str | None = None,
) -> Any:
    """Insert an associative Hole Wizard callout on a selected drawing edge.

    ``process`` is the shop instruction a machinist reads first -- ``"DRILL"``,
    ``"15/64 DRILL"``, ``"REAM"`` -- written into the callout's PREFIX
    compartment so the sheet reads ``15/64 DRILL <MOD-DIAM>5.95 THRU ALL``
    (Harvey #13: say drill or ream; drawing-guidelines.md rule 12 (hole and slot callouts say what to do)).  The
    size and depth stay native and associative; only the prefix is text.

    The callout DISPLAYS the part's hole tolerance; it does not own one. Set the
    fit on the hole feature in the SLDPRT (``_holes.wizard_holes``'s
    ``dia_tolerance_mm``) and it renders here as
    ``<MOD-DIAM>3.05 +0.10/0.00 THRU ALL``. Toleranceing the drawing dimension
    instead silently does nothing: ``IDimensionTolerance::SetValues`` returns
    True and stores the value -- ``GetMaxValue2`` reads it right back -- and the
    callout still prints the bare nominal.
    """
    selected = _select_view_entity(
        adapter, view, "EDGE", edge_xy, label=label, entity=edge
    )
    # Snapshot what AddHoleCallout2 is about to be handed, BEFORE the call: the
    # API may clear the selection or invalidate the entity, and on a passing
    # leaf this line is the positive control the failing one is read against.
    # DEBUG plus the span event: every record reaches OTLP/App Insights
    # regardless of console verbosity (the OTel handler sits at DEBUG; the
    # verbosity flag filters only stderr), so this is not a task.log line by
    # default. One record per callout. Emission is guarded: telemetry must
    # never fail a sheet (the console formatter prints only the message, hence
    # the JSON in it).
    before = describe_selected_entity(
        adapter, view, selected, entity_type="EDGE", requested_xy=edge_xy, label=label
    )
    with contextlib.suppress(Exception):
        _telemetry.event("drawing.hole_callout_selection", **before)
        _telemetry.debug(
            f"hole callout {label}: selected edge before AddHoleCallout2: "
            + json.dumps(before, default=str, sort_keys=True)
        )
    draw = adapter.currentModel
    ddoc = _early_bound(
        draw, "IDrawingDoc"
    )  # IDrawingDoc view for drawing-only methods (same dispatch)
    display = ddoc.AddHoleCallout2(callout_xy[0], callout_xy[1], 0.0)
    if display is None:
        # A None here says only "no callout": the seat is about to be torn down
        # with the drawing unsaved and the selection undescribed (rocker_arm,
        # worker5, 2026-09-20 -- "no forensic artefacts captured"). Describe the
        # selection again AFTER the refusal -- kept apart from the BEFORE
        # snapshot, never overwriting it, so a cleared selection or an
        # invalidated entity reads as what the API DID, not as what it was
        # given -- then let the capture save the sheet, the seat image,
        # SolidWorks' own error stack and the screen-space pick geometry
        # before raising. Only capture_com_failure raises; the console line
        # is guarded so a failed sink can neither replace the failure nor
        # prevent the capture.
        after = describe_selected_entity(
            adapter,
            view,
            selected,
            entity_type="EDGE",
            requested_xy=edge_xy,
            label=label,
        )
        with contextlib.suppress(Exception):
            _telemetry.error(
                f"hole callout {label}: AddHoleCallout2 returned None at sheet "
                f"({callout_xy[0]:g}, {callout_xy[1]:g}); selection "
                + json.dumps(
                    {"before": before, "after": after}, default=str, sort_keys=True
                )
            )
        _seat_forensics.capture_com_failure(
            adapter,
            f"hole-callout {label}",
            f"failed to insert native hole callout ({label})",
            api="IDrawingDoc.AddHoleCallout2",
            callout_x=callout_xy[0],
            callout_y=callout_xy[1],
            **{f"before_{key}": value for key, value in before.items()},
            **{f"after_{key}": value for key, value in after.items()},
        )
    # AddHoleCallout2 leaves its PropertyManager page open.  Accept it through
    # the documented swCommands_PmOK command so doit remains unattended.
    if not adapter.swApp.RunCommand(-2, ""):  # swCommands_e.swCommands_PmOK
        raise RuntimeError(f"failed to accept native hole callout ({label})")
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "IsHoleCallout", "GetAnnotation"
    )
    if not display.IsHoleCallout():
        raise RuntimeError(f"inserted annotation is not a hole callout ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        display.GetAnnotation(), "IAnnotation", "SetPosition2"
    )
    if not annotation.SetPosition2(callout_xy[0], callout_xy[1], 0.0):
        raise RuntimeError(f"failed to position native hole callout ({label})")
    if process:
        # Prefix the definition, not GetText(Prefix)'s resolved values: writing
        # resolved thread text severs its Hole Wizard variables. Native save /
        # reopen proof retains all five variables with PrefixDefinition (5).
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText", "GetText"
        )
        existing = str(display.GetText(5) or "")  # swDimensionTextPrefixDefinition
        if not existing.strip():
            raise RuntimeError(f"hole callout has no format text to prefix ({label})")
        prefix = compose_hole_callout_prefix(process, existing)
        display.SetText(1, prefix)
        if str(display.GetText(5) or "") != prefix:
            raise RuntimeError(
                f"hole callout process prefix did not persist ({label}): "
                f"{display.GetText(5)!r}"
            )
        _telemetry.debug(f"hole callout {label}: prefix {prefix!r}")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="add_native_hole_callout")
    return display


@_telemetry.traced("drawing.hole_callout_precision", label_param="label")
def set_hole_callout_precision(
    display: Any, precision: Mapping[str, int], *, label: str
) -> None:
    """Set the decimals of named Hole Wizard length variables, natively.

    ``precision`` maps a callout variable name (``"hw-tapdrldepth"``,
    ``"hw-threaddepth"``) to its number of decimals. Per VARIABLE, because
    ``IDisplayDimension::SetPrecision3`` is per callout ("does not support
    setting the Primary ... values for hole callouts") and flattening the
    whole callout would cost the tap-drill DIAMETER its two places; every
    length token carries its own ``ICalloutLengthVariable::Precision``, so
    only the named ones change and each value stays the native variable.
    A blind depth printed ``16.00`` asks the shop for the .XX band; ``16.0``
    puts it under the general .X tolerance it actually needs.
    """
    from win32com.client.dynamic import Dispatch as dynamic_dispatch  # noqa: PLC0415

    remaining = dict(precision)
    for raw in display.GetHoleCalloutVariables() or ():
        name = str(dynamic_dispatch(raw._oleobj_).VariableName)
        decimals = remaining.pop(name, None)
        if decimals is None:
            continue
        length = _early_bound(raw, "ICalloutLengthVariable")
        length.Precision = int(decimals)
        if int(length.Precision) != int(decimals):
            raise RuntimeError(f"{label}: {name} precision did not persist")
    if remaining:
        raise RuntimeError(
            f"{label}: hole callout has no native variables {sorted(remaining)}"
        )
