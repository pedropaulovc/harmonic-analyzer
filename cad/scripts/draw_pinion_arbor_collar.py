r"""Create the curated machinist drawing for the pinion-arbor collar (R1a).

A plain turned steel collar: Ø15 x 20, a drilled Ø8 slide bore, and one
1/16 in spring-pin hole through both walls at the length's centre.  The
profile lies as it sits in the lathe (axis horizontal) and looks along the
pin hole, so the hole is a solid circle located from the right-hand end face;
the end view to its left owns the bore callout, and its OD moves onto the
profile (rule 7: diameters on the side view).

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_arbor_collar.py pinion-arbor-collar
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
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
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import audit_sheet, format_findings
from diagnostics.drawing_layout_audit import collect_document
from pinion_arbor_collar_spec import (
    BORE_CALLOUT,
    COLLAR_LEN,
    COLLAR_OD,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_HOLE_CALLOUT,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_arbor_collar"]
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

SHEET_SCALE = (3.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # model mm -> sheet m

# Third angle: the profile turns *Top by -90 deg, so model +Z runs LEFT and
# the end face the collar is dimensioned from (z 0) is the profile's right
# end.  The end view looks along -Z from the +Z end, so it projects on the
# LEFT of the profile, sharing its axis height.
PROFILE_CENTER = (0.205, 0.165)
END_CENTER = (0.085, PROFILE_CENTER[1])
ISO_CENTER = (0.345, 0.205)

_PROFILE_RIGHT = PROFILE_CENTER[0] + COLLAR_LEN * _S / 2.0  # z 0 face, 0.235
_PROFILE_TOP = PROFILE_CENTER[1] + COLLAR_OD * _S / 2.0  # 0.1875
_PROFILE_BOTTOM = PROFILE_CENTER[1] - COLLAR_OD * _S / 2.0  # 0.1425

# The bore is a solid circle only end-on, so its callout stays there (a
# standard drilled hole is defined by its callout, rule 7); its leader runs
# up-left, clear of the OD centre mark.
END_KEEP = {
    "BoreDia": (0.040, 0.210),
    "CollarOd": (0.040, 0.120),  # moved onto the profile below
}
# Length under the profile, pin station over it from the right end face, the
# pin hole's leader up-left to its circle, and the OD right of the part.
PROFILE_KEEP = {
    "Depth": (PROFILE_CENTER[0], _PROFILE_BOTTOM - 0.022),
    "PinHoleCz": (_PROFILE_RIGHT - 0.012, _PROFILE_TOP + 0.020),
    "PinHoleDia": (0.160, _PROFILE_TOP + 0.030),
}
OD_ON_PROFILE = (_PROFILE_RIGHT + 0.025, PROFILE_CENTER[1])
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "PinHoleDia": PIN_HOLE_CALLOUT,
}
# Text on a line and text on text are defects; leader crossings stay logged.
BLOCKING_LAYOUT_FINDINGS = frozenset({"text-on-line", "text-on-text"})


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
        raise RuntimeError(f"failed to select model dimension {name}: {selection_name!r}")
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


def _assert_layout_clean(findings: list[Any]) -> None:
    """Fail the sheet on text over ink; log every other audit finding."""
    blocking = [f for f in findings if f.kind in BLOCKING_LAYOUT_FINDINGS]
    advisory = [f for f in findings if f.kind not in BLOCKING_LAYOUT_FINDINGS]
    if advisory:
        _telemetry.warn(
            f"pinion-arbor-collar layout audit: {len(advisory)} advisory finding(s)\n"
            + format_findings(advisory),
            advisory=len(advisory),
        )
    if blocking:
        raise RuntimeError(
            f"pinion-arbor-collar layout audit: {len(blocking)} blocking finding(s)\n"
            + format_findings(blocking)
        )
    _telemetry.success("pinion-arbor-collar layout audit: no text over ink")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-arbor-collar source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Pinion Arbor Collar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion arbor retention collar; spring-pinned; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=(3, 1))
    # Looking along model Y presents the pin hole as a true circle; -90 deg
    # lays the axis horizontal, as the collar sits in the lathe.
    profile = place_view(adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=(3, 1))
    native_profile = _early_bound(profile, "IView")
    native_profile.Angle = -math.pi / 2.0
    if abs(math.remainder(float(native_profile.Angle) + math.pi / 2.0, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to orient the collar profile horizontally")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (end, profile, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="collar end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="collar profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    od_donors = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) == "CollarOd"
    ]
    if len(od_donors) != 1:
        raise RuntimeError("expected one collar OD donor dimension")
    moved_od = _move_dimension(
        adapter, od_donors[0], profile, OD_ON_PROFILE, source_view=end
    )
    end_annotations = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) != "CollarOd"
    ]
    annotations = [*end_annotations, *profile_annotations, moved_od]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add center marks to the collar end view")
    if not auto_center_marks(adapter, profile, holes=True, size=0.0015):
        raise RuntimeError("failed to add center mark to the collar pin hole")
    # The turning axis, picked on the OD face between the pin hole and the
    # left end so the pick cannot land on the hole.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0] - 0.015, PROFILE_CENTER[1] + COLLAR_OD * _S / 4.0),
        label="pinion arbor collar axis centerline",
    )

    add_property_linked_note(adapter, "Isometric View Note", 0.320, 0.160)
    rebuild_drawing(adapter, label="pinion arbor collar layout audit")
    _assert_layout_clean(
        [finding for sheet in collect_document(adapter) for finding in audit_sheet(sheet)]
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Arbor Collar Manufacturing Drawing",
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
