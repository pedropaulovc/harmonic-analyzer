r"""Create the curated machinist drawing for the tube-frame column.

The SLDPRT remains authoritative. This recipe supplies the regular open tube's
orthographic views, diameter/cut-length/cross-hole dimensions, and manufacturing
notes; shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The tube axis runs along +Y, so the length view is the ``*Front`` orientation
and the chamfered end view is ``*Top``, aligned above it in third-angle
projection. The portrait sheet uses the long axis for the 1018.765 mm cut
length at 1:5; the end view carries a 2:1 override. The isometric is pictorial only.

Run with SolidWorks open::

    uv run python cad\scripts\draw_tube_frame.py tube-frame
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    property_link,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
    view_name,
)
from tube_frame_spec import (
    COLUMN_LENGTH,
    CROSS_HOLE_DIAMETER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LOWER_CROSS_HOLE_Y,
    OUTER_DIA,
    TOP_END_CHAMFER,
)


SPEC = DRAWINGS_BY_NAME["tube_frame"]
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

SHEET_SCALE = (1.0, 5.0)  # 1:5 whole sheet (1018.765 mm cut tube)
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
    "TopChamfer": (LENGTH_CENTER[0] + 0.040, LENGTH_CENTER[1] + 0.120),
}
CROSS_HOLE_CALLOUT = {
    "CrossHoleDia": "2 STA; MATCH-DRILL CLEARANCE THRU BOTH WALLS"
}
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
        ")\nSOCKETS MHA-035/MHA-077 ARE"
        "\nMATCH-FIT TO THIS ASSIGNED TUBE"
        "\nCLOSE HAND-SLIP; NO PERCEPTIBLE ROCK"
    )
    display.SetText(2, od_suffix)
    if str(display.GetText(2) or "") != od_suffix:
        raise RuntimeError("OD reference fit text did not persist")
    draw.EditRebuild3()
    return annotation


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
            "Manufacturing Notes",
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
            "Manufacturing Notes",
            "End View Note",
            "Isometric View Note",
            "Length View Note",
            "Top End Callout",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    set_hidden_lines_removed(adapter, iso)

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
    set_dimension_callouts(adapter, dimensions, CROSS_HOLE_CALLOUT, location="above")
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
    # drawing document's two places would print the 1018.8 cut length as
    # 1018.77 and ask for a band the match-cut note explicitly refuses.
    assert_imported_precision(adapter, dimensions, DRAWING_PRECISION_BY_NAME)
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
    chamfers = [
        annotation
        for annotation in dimensions
        if dimension_name(adapter, annotation) == "TopChamfer"
    ]
    if len(chamfers) != 1:
        raise RuntimeError(f"expected one native top chamfer, got {len(chamfers)}")
    chamfer = _early_bound(chamfers[0].GetSpecificAnnotation(), "IDisplayDimension")
    native_chamfer = _early_bound(chamfer.GetDimension2(0), "IDimension")
    if abs(float(native_chamfer.SystemValue) * 1000.0 - TOP_END_CHAMFER) > 1e-5:
        raise RuntimeError("native top chamfer differs from source size")
    chamfer.ShowParenthesis = False
    chamfer.SetText(1, "")
    # Keep the native value/suffix on one line. Multiline suffix text on this
    # imported model dimension rendered only its final line in the native PDF.
    cap_acceptance = " ".join(source_properties["Top End Callout"].splitlines())
    chamfer.SetText(3, cap_acceptance)
    chamfer.SetText(4, "")
    chamfer_suffix = " X 45 DEG"
    chamfer.SetText(2, chamfer_suffix)
    chamfer.ShowDimensionValue = True
    if (
        bool(chamfer.ShowParenthesis)
        or not bool(chamfer.ShowDimensionValue)
        or str(chamfer.GetText(1) or "")
        or str(chamfer.GetText(2) or "") != chamfer_suffix
        or str(chamfer.GetText(3) or "") != cap_acceptance
        or str(chamfer.GetText(4) or "")
    ):
        raise RuntimeError("native chamfer value/cap callout lanes did not persist")
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the annulus end view")

    # Both end rims receive native centre marks; the length view exposes both
    # cross-drilled stations through visible hidden geometry.

    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.135, 0.198
    )
    add_note(adapter, f"TOP {property_link('End View Note')}", 0.060, 0.400)
    add_property_linked_note(adapter, "Isometric View Note", 0.175, 0.215)
    add_property_linked_note(adapter, "Length View Note", 0.075, 0.083)
    for view in (length, end):
        set_hidden_lines_visible(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Tube Frame Column Manufacturing Drawing",
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
