r"""Create the manufacturing drawing for the transgear front bushing (MHA-PD-025).

A turned brass ring: Ø12 O.D. over a reamed Ø3.900 bore, a 0.5 x 45 deg
chamfer on the ring face's O.D. edge, faced to fit at assembly, so its
modelled length prints as a REFERENCE under the fit-at-assembly callout and
the MHA-PD-000 step that sets it.  The profile lies as it sits in the lathe
(axis horizontal): the ``*Top`` view turned a quarter turn, so model +Z runs
LEFT and the nose face (z 0) is the profile's right end, the chamfered ring
face its left end.  Each end face carries its running finish, the length
sits under the profile, the chamfer's leg above its corner and the O.D.
moves onto the profile (rule 7: diameters on the side view).  The end view
to its left (third angle, looking along -Z from the +Z end) keeps the bore,
a solid circle only end-on.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_transgear_front_bushing.py pd-transgear-front-bushing
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _layout_geometry import audit_sheet, format_findings
from _surface_finish import surface_finish_by_key
from diagnostics.drawing_layout_audit import collect_document
from pd_paper_drive_assembly_steps import step_ref
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import place_view
from pd_transgear_front_bushing_spec import (
    BORE_CALLOUT,
    BORE_DIA,
    CHAMFER_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FRONT_CHAMFER,
    ISOMETRIC_VIEW_SCALE,
    LENGTH,
    LENGTH_CALLOUT,
    OD,
    SURFACE_FINISHES,
)


SPEC = DRAWINGS_BY_NAME["pd_transgear_front_bushing"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# A Ø12 x 5 ring: 5:1 keeps the four sizes, the fit callout and the three
# finishes legible on the landscape sheet.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # model mm -> sheet m
# The *Top view turned -90 degrees: model +Z runs to paper-left.
PROFILE_ANGLE = -math.pi / 2.0
PROFILE_CENTER = (0.200, 0.170)
# Third angle: the end view seen from the +Z end sits LEFT of the profile, on
# its axis.
END_CENTER = (0.090, PROFILE_CENTER[1])
ISO_CENTER = (0.340, 0.190)

_PROFILE_NOSE_X = PROFILE_CENTER[0] + LENGTH * _S / 2.0  # z 0, right end
_PROFILE_RING_X = PROFILE_CENTER[0] - LENGTH * _S / 2.0  # z LENGTH, left end
_PROFILE_TOP = PROFILE_CENTER[1] + OD * _S / 2.0
_PROFILE_BOTTOM = PROFILE_CENTER[1] - OD * _S / 2.0

# Faced to fit at MHA-PD-000's front-bushing step (m); the pointer comes from
# the step registry.
FIT_STEP_KEY = "front-bushing-faced-to-fit"

# The bore stays on the end view, where it is a circle: a reamed through
# hole, fully defined by its callout (rule 7), it needs no section, and the
# profile is hidden-lines-removed (a dimension never lands on a hidden line).
# The O.D. arrives there too and is moved onto the profile below.
END_KEEP = {
    "BoreDia": (0.060, 0.225),
    "RingOd": (0.045, 0.120),  # donor: moved onto the profile
}
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "RingLength": f"{LENGTH_CALLOUT},\nPER {step_ref(FIT_STEP_KEY)}",
    "FrontChamferSize": CHAMFER_CALLOUT,
}
# The length under the profile.  Its four-line reference block is wider
# than the 5.0 between its extension lines, so it stands off to the right,
# under the O.D. dimension, where no extension line runs through it.  The
# chamfer's leg sits above the chamfered (left) corner; the O.D. right of the
# part, its dimension line far enough out that the nose face's finish symbol
# sits between them.
PROFILE_KEEP = {
    "RingLength": (_PROFILE_NOSE_X + 0.045, _PROFILE_BOTTOM - 0.022),
    "FrontChamferSize": (
        _PROFILE_RING_X + FRONT_CHAMFER * _S / 2.0,
        _PROFILE_TOP + 0.018,
    ),
}
OD_ON_PROFILE = (_PROFILE_NOSE_X + 0.040, PROFILE_CENTER[1])

# Each face's pick lies on its edge line between the bore and the chamfer's
# inner edge.  The ring face's symbol stands left of the part, clear of the
# chamfer dimension above; the nose face's stands right of the part inside
# the O.D.'s extension-line band, below the axis, short of the O.D.
# dimension line.
_FACE_PICK_UP = PROFILE_CENTER[1] + (BORE_DIA + OD) / 4.0 * _S
_FACE_PICK_DOWN = PROFILE_CENTER[1] - (BORE_DIA + OD) / 4.0 * _S
FACE_FINISHES = {
    "ring_face": (
        (_PROFILE_RING_X, _FACE_PICK_UP),
        (_PROFILE_RING_X - 0.030, PROFILE_CENTER[1] + 0.012),
    ),
    "nose_face": (
        (_PROFILE_NOSE_X, _FACE_PICK_DOWN),
        (_PROFILE_NOSE_X + 0.014, PROFILE_CENTER[1] - 0.008),
    ),
}
# The bore runs on the pin (rule 5): its finish sits on the end view, where
# the bore is a circle.  The leader lands on the bore circle at -135 deg,
# away from the Ø callout's landing upper right; the symbol stands left of
# the O.D. below the horizontal centre line, its ink growing up and right
# short of the line and of the O.D. circle.  Every symbol keeps one height.
_BORE_SHEET_RADIUS = BORE_DIA * _S / 2.0
BORE_FINISH_ATTACH = (
    END_CENTER[0] + _BORE_SHEET_RADIUS * math.cos(math.radians(-135.0)),
    END_CENTER[1] + _BORE_SHEET_RADIUS * math.sin(math.radians(-135.0)),
)
BORE_FINISH_SYMBOL = (END_CENTER[0] - OD * _S / 2.0 - 0.022, END_CENTER[1] - 0.012)
FINISH_CHAR_HEIGHT = 0.0025
NOTES_XY = (0.020, 0.075)
ISO_NOTE_XY = (0.315, 0.145)
# Text over ink, an extension line through its own text and a mark printed
# twice are defects; leader crossings stay logged.
BLOCKING_LAYOUT_FINDINGS = frozenset(
    {
        "text-on-line",
        "text-on-text",
        "extension-through-own-text",
        "duplicate-annotation",
    }
)


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a model dimension to the projection that shows its extension lines."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name,
        "DIMENSION",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
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


# swCenterMarkStyle_e.swCenterMark_Single: AutoInsertCenterMarks2 marks the
# concentric O.D. and bore circles separately, one mark printed over the other.
CENTER_MARK_SINGLE = 2


def _mark_bore_axis(adapter: Any, view: Any) -> None:
    """One centre mark on the bore, picked on its -X point."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the bushing end view")
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        "",
        "EDGE",
        END_CENTER[0] - BORE_DIA * _S / 2.0,
        END_CENTER[1],
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError("failed to select the bushing bore circle")
    mark = drawing.InsertCenterMark3(CENTER_MARK_SINGLE, False, False)
    draw.ClearSelection2(True)
    if mark is None:
        raise RuntimeError("failed to centre-mark the bushing bore")


def _assert_layout_clean(findings: list[Any]) -> None:
    """Fail the sheet on text over ink; log every other audit finding."""
    blocking = [f for f in findings if f.kind in BLOCKING_LAYOUT_FINDINGS]
    advisory = [f for f in findings if f.kind not in BLOCKING_LAYOUT_FINDINGS]
    if advisory:
        _telemetry.warn(
            f"transgear-front-bushing layout audit: {len(advisory)} advisory "
            "finding(s)\n" + format_findings(advisory),
            advisory=len(advisory),
        )
    if blocking:
        raise RuntimeError(
            f"transgear-front-bushing layout audit: {len(blocking)} blocking "
            "finding(s)\n" + format_findings(blocking)
        )
    _telemetry.success("transgear-front-bushing layout audit: no text over ink")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-front-bushing source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Front Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear cluster front bushing; turned brass, faced to fit",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    profile = place_view(
        adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=VIEW_SCALE
    )
    native_profile = _early_bound(profile, "IView")
    native_profile.Angle = PROFILE_ANGLE
    if (
        abs(math.remainder(float(native_profile.Angle) - PROFILE_ANGLE, 2.0 * math.pi))
        > 1e-9
    ):
        raise RuntimeError("failed to lay the bushing profile horizontal")
    drawing_model.EditRebuild3()
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISOMETRIC_VIEW_SCALE
    )
    for view in (end, profile, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="bushing end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="bushing profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    od_donors = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) == "RingOd"
    ]
    if len(od_donors) != 1:
        raise RuntimeError("expected one bushing O.D. donor dimension")
    moved_od = _move_dimension(
        adapter, od_donors[0], profile, OD_ON_PROFILE, source_view=end
    )
    end_annotations = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) != "RingOd"
    ]
    annotations = [*end_annotations, *profile_annotations, moved_od]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the bore's band are authored on the part; the sheet only proves the
    # import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # Faced to fit at assembly: the modelled length prints as a REFERENCE
    # value and the callout under it is the requirement; the blank it is
    # faced from is the Manufacturing Notes' make-to size.
    length_annotations = [
        annotation
        for annotation in profile_annotations
        if dimension_name(adapter, annotation) == "RingLength"
    ]
    if len(length_annotations) != 1:
        raise RuntimeError("profile does not carry exactly one bushing length")
    set_reference_dimension(adapter, length_annotations[0], label="bushing length")
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _mark_bore_axis(adapter, end)
    # The turning axis, picked on the O.D. face above it.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0], PROFILE_CENTER[1] + OD * _S / 4.0),
        label="front bushing axis centerline",
    )
    for key, label in (
        ("ring_face", "bushing ring face finish"),
        ("nose_face", "bushing nose face finish"),
    ):
        pick, symbol = FACE_FINISHES[key]
        add_surface_finish(
            adapter,
            profile,
            edge_xy=pick,
            symbol_xy=symbol,
            control=surface_finish_by_key(SURFACE_FINISHES, key),
            label=label,
            char_height=FINISH_CHAR_HEIGHT,
        )
    add_surface_finish(
        adapter,
        end,
        symbol_xy=BORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
        label="bushing bore finish",
        entity=visible_circle_edge(adapter, end, BORE_DIA),
        leader_attach_xy=BORE_FINISH_ATTACH,
        char_height=FINISH_CHAR_HEIGHT,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    rebuild_drawing(adapter, label="front bushing layout audit")
    _assert_layout_clean(
        [
            finding
            for sheet in collect_document(adapter)
            for finding in audit_sheet(sheet)
        ]
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Front Bushing Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
