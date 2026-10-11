"""Native drawing hole-callout authoring and precision.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
from typing import Mapping
from _com import _early_bound
import _seat_forensics
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
import _telemetry
import contextlib
import json
from _drawing_common import rebuild_drawing
from _drawing_selection import _select_view_entity
from _drawing_selection_probe import describe_selected_entity


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
    (Harvey #13: say drill or ream; drawing-simplicity-policy.md rule 7).  The
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
