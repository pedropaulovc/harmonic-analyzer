r"""Create the curated machinist drawing for the tube-frame column.

The SLDPRT remains authoritative. This recipe supplies the regular open tube's
orthographic views, diameter/cut-length/cross-hole dimensions, the top-end
chamfer dimension, and their fit-up callouts;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The tube axis runs along +Y, so the length view is the ``*Front`` orientation
and the chamfered end view is ``*Top``, aligned above it in third-angle
projection. The portrait sheet uses the long axis for the 40.109 in cut
length at 1:5; the end view carries a 2:1 override. The isometric is pictorial only.

Run with SolidWorks open::

    uv run python cad\scripts\draw_fr_tube_frame.py fr-tube-frame
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edges import (
    face_silhouettes_through,
    scan_view_edges,
    visible_view_entities,
)
from _drawing_notes import add_property_linked_note, property_link
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _gtol_cone import ConeFace
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from fr_tube_frame_spec import (
    COLUMN_LENGTH,
    CROSS_HOLE_CALLOUT as CROSS_HOLE_CALLOUT_TEXT,
    CROSS_HOLE_DIAMETER,
    CROSS_HOLE_MATES_SUFFIX,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH_FIT_CALLOUT,
    LENGTH_SUPPLY_CALLOUT,
    LOWER_CROSS_HOLE_Y,
    OUTER_DIA,
    TOP_END_CHAMFER,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["fr_tube_frame"]
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

SHEET_SCALE = (1.0, 5.0)  # 1:5 whole sheet (40.109 in cut tube)
END_VIEW_SCALE = 2.0
ISO_VIEW_SCALE = (1, 10)
# The aligned length/end views occupy the left-centre of the portrait sheet;
# fitting notes and the pictorial view fill the upper-right field.
LENGTH_CENTER = (0.110, 0.220)
END_CENTER = (LENGTH_CENTER[0], 0.360)
ISO_CENTER = (0.220, 0.280)

# Per-view survivors of the marked-dimension import.
END_KEEP: dict[str, tuple[float, float]] = {}
# The three station values park left of the tube, each on its own dimension
# line, so the lines have to stand far enough apart that no value's text sits
# in a neighbour's corridor. At 0.036/0.020 the (12.70) text was 23 mm wide
# across lines 21 mm apart, so BOTH the cut length's and the upper station's
# lines printed through it (native layout audit: two text-on-line findings and
# the leader crossing between them).
LENGTH_KEEP = {
    "Length": (LENGTH_CENTER[0] - 0.050, LENGTH_CENTER[1]),
    "LowerHoleY": (LENGTH_CENTER[0] - 0.025, LENGTH_CENTER[1] - 0.075),
    "UpperHoleY": (LENGTH_CENTER[0] - 0.015, LENGTH_CENTER[1] + 0.075),
    "CrossHoleDia": (
        LENGTH_CENTER[0] + 0.085,
        LENGTH_CENTER[1] - COLUMN_LENGTH / 10000.0 + LOWER_CROSS_HOLE_Y / 5000.0,
    ),
}
# The top-end break is a native chamfer dimension (``AddChamferDim``) whose
# leader lands on the chamfer itself. The part's ``TopChamfer`` is a linear
# distance: imported, it drew opposed arrows on the top face's extension well
# right of the tube and named no edge (machinist review 5bca52e r2/r3).
# ``AddChamferDim`` ignores its text point (run 20261027T080236834Z: asked
# for x 200 mm, it centred the 103.6 mm block at x 141.6 over the end view,
# four text-on-view/line audit findings), so the text is set after insertion
# by ``SetPosition2``, which places the block's centre at x and the cap line
# at y with the value line's shoulder 5.6 mm under it. Centred at x 198 mm
# the block (146..250 mm) clears the end view's outline (x <= 141 mm); the
# shoulder at 333 mm stays 4.8 mm over the isometric's outline (328.2 mm).
CHAMFER_TEXT_XY = (0.198, 0.3386)
_CHAMFER_POSITION_TOLERANCE_M = 0.001
# The chamfer dimension prints the part-authored break places (two, .XX) and
# a whole-degree angle: ".02 X 45°".
CHAMFER_PLACES = DRAWING_PRECISION_BY_NAME["TopChamfer"]
IMPORTED_PRECISION = {
    name: places
    for name, places in DRAWING_PRECISION_BY_NAME.items()
    if name != "TopChamfer"
}
_CHAMFER_DIMENSION = 10  # swDimensionType_e.swChamferDimension
# swDetailingChamferDimLeaderTextStyle_e.swDetailChamferDimDistAng
_CHAMFER_TEXT_DIST_ANG = 2
_CHAMFER_LENGTH = 0  # IDisplayDimension.ChamferPrecision index: length
_CHAMFER_ANGLE = 1  # IDisplayDimension.ChamferPrecision index: angle
# The cut length is set at assembly: the supply size rides above the (40.109)
# reference and the cut-to-fit stack below it (rule 19), so the requirement
# is flagged on the length itself rather than in the note block.
ABOVE_CALLOUTS = {
    "CrossHoleDia": CROSS_HOLE_CALLOUT_TEXT,
    "Length": LENGTH_SUPPLY_CALLOUT,
}
BELOW_CALLOUTS = {"Length": LENGTH_FIT_CALLOUT}
_CALLOUT_ABOVE = 3  # swDimensionTextParts_e.swDimensionTextCalloutAbove
_CALLOUT_BELOW = 4  # swDimensionTextParts_e.swDimensionTextCalloutBelow
_LEADER_LINE_NONE = 3  # swLeaderLineVisibility_e.swLeaderLineNone


@_telemetry.traced("drawing.outer_diameter")
def _add_outer_diameter_reference(
    adapter: Any,
    view: Any,
    *,
    text_xy: tuple[float, float],
) -> Any:
    """Dimension the full-OD circle at the top chamfer's cylindrical shoulder."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate OD reference view {name!r}")
    # Select the model edge, not a sheet-coordinate hit within the pick aperture
    # of the smaller top rim. The full OD survives at the chamfer's lower edge.
    center = (0.0, (COLUMN_LENGTH - TOP_END_CHAMFER) / 1000.0, 0.0)
    radius = OUTER_DIA / 2000.0
    matches = []
    for raw in visible_view_entities(view, 1, label="tube top full-OD shoulder"):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsCircle():
            continue
        values = tuple(float(value) for value in curve.CircleParams)
        if abs(values[6] - radius) > 1e-7:
            continue
        if any(abs(values[index] - center[index]) > 1e-7 for index in range(3)):
            continue
        if abs(abs(values[4]) - 1.0) > 1e-7:
            continue
        matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one tube top full-OD shoulder edge, found {len(matches)}"
        )
    draw.ClearSelection2(True)
    if not view.SelectEntity(matches[0], False):
        raise RuntimeError("failed to select tube top full-OD shoulder edge")
    display = draw.AddDiameterDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to add OD reference dimension")
    native = _early_bound(display, "IDisplayDimension")
    measured_mm = float(
        _early_bound(native.GetDimension2(0), "IDimension").SystemValue
    ) * 1000.0
    if abs(measured_mm - OUTER_DIA) > 1e-5:
        raise RuntimeError(
            f"tube OD reference measured {measured_mm:g}, expected {OUTER_DIA:g} mm"
        )
    display = _sw_type_info.early_bound_or_flag(
        display,
        "IDisplayDimension",
        "GetAnnotation",
        "SetText",
        "GetText",
        "SetSecondArrow",
        "GetUseDocSecondArrow",
        "GetSecondArrow",
        "SetBrokenLeader2",
        "GetUseDocBrokenLeader",
        "GetBrokenLeader2",
    )
    adapter._attempt(lambda: setattr(display, "Diametric", True))
    if not bool(adapter._attempt(lambda: display.Diametric)):
        raise RuntimeError("OD reference dimension is not diametric")
    adapter._attempt(lambda: setattr(display, "ArrowSide", 1))
    if int(adapter._attempt(lambda: display.ArrowSide)) != 1:
        raise RuntimeError("OD reference did not retain its outside arrow")
    display.SetSecondArrow(False, False)
    if bool(display.GetUseDocSecondArrow()) or bool(display.GetSecondArrow()):
        raise RuntimeError("OD reference retained its opposite-side arrow")
    adapter._attempt(lambda: setattr(display, "SolidLeader", False))
    if display.SetBrokenLeader2(False, 2) != 0:
        raise RuntimeError("failed to apply broken horizontal OD leader")
    if bool(display.GetUseDocBrokenLeader()) or int(display.GetBrokenLeader2()) != 2:
        raise RuntimeError("OD broken leader style did not persist")
    annotation = display.GetAnnotation()
    if annotation is None:
        raise RuntimeError("OD reference dimension has no annotation")
    display = set_reference_dimension(
        adapter,
        annotation,
        label="outer diameter reference",
        diameter=True,
    )
    od_suffix = (
        ")\nSOCKETS MHA-FR-01/MHA-FR-02 ARE"
        "\nMATCH-FIT TO THIS ASSIGNED TUBE"
        "\nCLOSE HAND-SLIP; NO PERCEPTIBLE ROCK"
    )
    display.SetText(2, od_suffix)
    if str(display.GetText(2) or "") != od_suffix:
        raise RuntimeError("OD reference fit text did not persist")
    draw.EditRebuild3()
    return annotation


@_telemetry.traced("drawing.top_chamfer")
def _add_top_chamfer_dimension(
    adapter: Any,
    view: Any,
    *,
    text_xy: tuple[float, float],
    callout_above: str,
) -> Any:
    """Dimension the top-end OD break with a native chamfer dimension.

    In the length view the 45-degree break is the cone face's silhouette on
    the +X flank (sheet right), resolved from its model face and a projected
    point on the line it draws. Its lead-in is the top end face's outer rim,
    the circular edge the chamfer leaves at the top, seen edge-on as the end
    line. The OD flank cannot serve: farm leaves 20261027T073053Z and
    20261027T075752Z read every one of the view's 4 silhouettes as the cone's
    (two coincident per flank) and its 5 visible edges as 3 circles plus 2
    cross-hole curves, so no selectable entity draws the OD flank. Both picks
    are selected as objects, so no seat hit-test is involved. Returns the
    settled check that re-proves the dimension after the final rebuild.
    """
    radius = OUTER_DIA / 2.0
    chamfer_mid = model_point_in_view(
        adapter,
        view,
        (
            (radius - TOP_END_CHAMFER / 2.0) / 1000.0,
            (COLUMN_LENGTH - TOP_END_CHAMFER / 2.0) / 1000.0,
            0.0,
        ),
        label="tube top chamfer flank point",
    )
    chamfer = face_silhouettes_through(
        adapter,
        view,
        {"chamfer": (ConeFace(45.0), chamfer_mid)},
        label="tube top chamfer",
    )["chamfer"]
    lead_in = (
        scan_view_edges(view, label="tube top end rim")
        .circle_at(
            (0.0, COLUMN_LENGTH, 0.0),
            radius - TOP_END_CHAMFER,
            axis=(0.0, 1.0, 0.0),
            label="tube top end rim",
        )
        .edge
    )
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate top chamfer view {name!r}")
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = manager.CreateSelectData()
    data.View = view
    # Chamfered edge first, then its lead-in (SOLIDWORKS chamfer-dimension order).
    chamfer = _sw_type_info.early_bound_or_flag(chamfer, "ISilhouetteEdge", "Select2")
    if not bool(chamfer.Select2(False, data)):
        raise RuntimeError("failed to select the tube top chamfer silhouette")
    if not bool(_early_bound(lead_in, "IEntity").Select4(True, data)):
        raise RuntimeError("failed to select the tube top end rim edge")
    selected = int(manager.GetSelectedObjectCount2(-1))
    if selected != 2:
        raise RuntimeError(
            f"tube top chamfer selection holds {selected} entities, not 2"
        )
    display = ddoc.AddChamferDim(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to add the tube top chamfer dimension")
    display = _early_bound(display, "IDisplayDimension")
    display.ChamferTextStyle = _CHAMFER_TEXT_DIST_ANG
    display.SetChamferPrecision(_CHAMFER_LENGTH, CHAMFER_PLACES)
    display.SetChamferPrecision(_CHAMFER_ANGLE, 0)
    display.ShowParenthesis = False
    display.SetText(1, "")
    display.SetText(2, "")
    display.SetText(3, callout_above)
    display.SetText(4, "")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError("tube top chamfer dimension has no annotation")
    if not annotation.SetPosition2(text_xy[0], text_xy[1], 0.0):
        raise RuntimeError("failed to position the tube top chamfer text")

    def settled() -> None:
        if bool(annotation.IsDangling()):
            raise RuntimeError("tube top chamfer dimension is dangling")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        values = tuple(native.GetSystemChamferValues(0.0, 0.0) or ())
        if len(values) != 3 or not bool(values[0]):
            raise RuntimeError(f"tube top chamfer reads no chamfer values: {values!r}")
        length_mm, angle_deg = float(values[1]) * 1000.0, math.degrees(float(values[2]))
        if abs(length_mm - TOP_END_CHAMFER) > 1e-5 or abs(angle_deg - 45.0) > 1e-6:
            raise RuntimeError(
                f"tube top chamfer measures {length_mm:g} mm x {angle_deg:g} deg, "
                f"expected {TOP_END_CHAMFER:g} mm x 45 deg"
            )
        lanes = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
        if (
            int(display.Type2) != _CHAMFER_DIMENSION
            or int(display.ChamferTextStyle) != _CHAMFER_TEXT_DIST_ANG
            or int(display.ChamferPrecision(_CHAMFER_LENGTH)) != CHAMFER_PLACES
            or int(display.ChamferPrecision(_CHAMFER_ANGLE)) != 0
            or bool(display.ShowParenthesis)
            or lanes != {1: "", 2: "", 3: callout_above, 4: ""}
        ):
            raise RuntimeError(
                "tube top chamfer dimension style/lanes did not persist: "
                f"type={display.Type2}, style={display.ChamferTextStyle}, "
                f"places=({display.ChamferPrecision(_CHAMFER_LENGTH)}, "
                f"{display.ChamferPrecision(_CHAMFER_ANGLE)}), lanes={lanes!r}"
            )
        placed = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if (
            len(placed) < 2
            or math.dist(placed[:2], text_xy) > _CHAMFER_POSITION_TOLERANCE_M
        ):
            raise RuntimeError(
                f"tube top chamfer text moved: {placed!r}, requested {text_xy!r}"
            )

    settled()
    return settled


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open tube-frame source", await adapter.open_model(str(SOURCE)))
    source_properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "End View Note",
            "Isometric View Note",
            "Length View Note",
            "Top End Callout",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "End View Note",
            "Isometric View Note",
            "Length View Note",
            "Top End Callout",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Tube Frame Column Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "tube frame; column; steel tube; polished",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    length = place_view(adapter, str(SOURCE), "*Front", *LENGTH_CENTER, scale=(1, 5))
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=(2, 1))
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    # The length view shows both stations as visible circles, so dashed bore
    # lines there would say nothing (MR r2): hidden lines removed, BEFORE the
    # chamfer dimension is attached to its silhouettes, so no later display
    # change regenerates them under it. The end view joins them (PR #1436
    # invariant; machinist review: its circles printed as draft polygons):
    # a precision-quality mode set right after placement, before its OD
    # reference and centre marks; it ends with hidden lines visible below.
    for view in (iso, length, end):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    outer_diameter = _add_outer_diameter_reference(
        adapter,
        end,
        text_xy=(END_CENTER[0] + 0.090, END_CENTER[1] + 0.020),
    )
    length_annotations = curate_view_dimensions(
        adapter,
        length,
        keep=LENGTH_KEEP,
        view_label="length",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    dimensions = [outer_diameter, *length_annotations]
    set_dimension_callouts(adapter, dimensions, ABOVE_CALLOUTS, location="above")
    set_dimension_callouts(adapter, dimensions, BELOW_CALLOUTS, location="below")
    hole_text = model_point_in_view(
        adapter,
        length,
        (0.0, LOWER_CROSS_HOLE_Y / 1000.0, 0.0),
        label="lower cross-hole source sketch centre",
    )
    for annotation in length_annotations:
        if dimension_name(adapter, annotation) != "CrossHoleDia":
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError("dimension callout has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText", "GetText"
        )
        display.SetText(4, "")
        if str(display.GetText(4) or ""):
            raise RuntimeError("failed to clear underlined below-dimension callout")
        # Each station's match-drill mate, on the value line (rule 7).
        display.SetText(2, CROSS_HOLE_MATES_SUFFIX)
        if str(display.GetText(2) or "") != CROSS_HOLE_MATES_SUFFIX:
            raise RuntimeError("cross-hole mates suffix did not persist")
        if str(display.GetText(_CALLOUT_ABOVE) or "") != CROSS_HOLE_CALLOUT_TEXT:
            raise RuntimeError("cross-hole match-drill callout did not persist")
        display = _early_bound(display, "IDisplayDimension")
        hole_dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if "CrossHoleProfile" not in str(hole_dimension.FullName):
            raise RuntimeError("cross-hole callout lost its source sketch association")
        measured_mm = float(hole_dimension.SystemValue) * 1000.0
        if abs(measured_mm - CROSS_HOLE_DIAMETER) > 1e-5:
            raise RuntimeError(
                f"cross-hole callout measured {measured_mm:g}, expected {CROSS_HOLE_DIAMETER:g}"
            )
        display.DisplayAsLinear = False
        display.Diametric = True
        display.ArrowSide = 1
        display.SetSecondArrow(False, False)
        display.SolidLeader = False
        if display.SetBrokenLeader2(False, 2) != 0:
            raise RuntimeError("failed to apply broken horizontal cross-hole leader")
        if (
            bool(display.SolidLeader)
            or bool(display.GetUseDocBrokenLeader())
            or int(display.GetBrokenLeader2()) != 2
            or bool(display.GetUseDocSecondArrow())
            or bool(display.GetSecondArrow())
        ):
            raise RuntimeError("cross-hole leader style did not persist")
        if bool(display.DisplayAsLinear) or not bool(display.Diametric):
            raise RuntimeError("cross-hole callout did not retain diametric presentation")
        # A diametric callout hangs on its own leader, so SOLIDWORKS also drew
        # the dimension LEADER-LINE pair from the hole straight past the text
        # (a 93 mm diagonal run measured through IAnnotation::GetDisplayData)
        # on top of the broken leader's horizontal shoulder. Hiding the leader
        # lines leaves exactly the shoulder run and its arrow at the hole;
        # ``OffsetText`` is not available on radial/diametric dimensions, and
        # ``ArcExtensionLineOrOppositeSide`` is already False here.
        display.LeaderVisibility = _LEADER_LINE_NONE
        if int(display.LeaderVisibility) != _LEADER_LINE_NONE:
            raise RuntimeError("cross-hole callout kept its dimension leader line")
        # ``curate_view_dimensions`` already placed the text at the station
        # ``LENGTH_KEEP`` derives arithmetically; prove that station is the
        # projected source-sketch centre instead of moving the text again.
        placed = tuple(
            float(value) for value in (_early_bound(annotation, "IAnnotation").GetPosition() or ())
        )
        if len(placed) < 2:
            raise RuntimeError(
                f"cross-hole callout has no position read-back: {placed!r}"
            )
        if abs(placed[1] - hole_text[1]) > 1e-6:
            raise RuntimeError(
                "cross-hole callout is not aligned with its source station: "
                f"{placed[1] * 1000.0:g} vs {hole_text[1] * 1000.0:g} mm"
            )
    # The part authored these places (tube_frame_spec.DRAWING_PRECISION); this
    # sheet only proves they survived the import. A silent fallback to the
    # drawing document's places would print the 40.109 cut length at the
    # wrong grid and ask for a band the match-cut note explicitly refuses.
    assert_imported_precision(adapter, dimensions, IMPORTED_PRECISION)
    for name in ("Length", "LowerHoleY", "UpperHoleY"):
        references = [
            annotation
            for annotation in dimensions
            if dimension_name(adapter, annotation) == name
        ]
        if len(references) != 1:
            raise RuntimeError(
                f"expected one {name} reference dimension, got {len(references)}"
            )
        display = set_reference_dimension(
            adapter,
            references[0],
            label=f"{name} reference",
        )
        if name == "Length":
            # The supply minimum and the cut-to-fit stack are the only place
            # the sheet states them; a dropped SetText must fail the sheet.
            lanes = {
                part: str(display.GetText(part) or "").replace("\r\n", "\n")
                for part in (_CALLOUT_ABOVE, _CALLOUT_BELOW)
            }
            if lanes != {
                _CALLOUT_ABOVE: LENGTH_SUPPLY_CALLOUT,
                _CALLOUT_BELOW: LENGTH_FIT_CALLOUT,
            }:
                raise RuntimeError(f"length supply/cut-to-fit callouts did not persist: {lanes!r}")
    # Single line: the property is the cap's fit requirement (rule 4 names
    # the mate) riding above the native chamfer value.
    cap_acceptance = " ".join(source_properties["Top End Callout"].splitlines())
    chamfer_settled = _add_top_chamfer_dimension(
        adapter, length, text_xy=CHAMFER_TEXT_XY, callout_above=cap_acceptance
    )
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the annulus end view")

    add_note(adapter, f"TOP {property_link('End View Note')}", 0.060, 0.400)
    add_property_linked_note(adapter, "Isometric View Note", 0.175, 0.215)
    add_property_linked_note(adapter, "Length View Note", 0.075, 0.083)
    # The end view's hidden lines carry the cross-hole through both walls
    # (rule 9).
    set_hidden_lines_visible(adapter, end)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Tube Frame Column Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(chamfer_settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
