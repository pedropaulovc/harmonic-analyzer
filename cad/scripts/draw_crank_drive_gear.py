r"""Create the curated manufacturing drawing for the crank-drive gear (64T).

Recreated under ``cad/docs/drawing-simplicity-policy.md``. The sheet is a
face view, a longitudinal centre section and an isometric of a helical
toothed disc with a local +X D-bore, and five native model dimensions --
outside diameter, four-place face width, round bore diameter, across-flat and
south-entry chamfer -- plus the gear-data block rule 6 keeps for the
crossed-axis tooth system.

No datums, no feature control frames: a gear slipped onto a shaft land is not
on the GD&T allowlist (rules 3-4), and the retired end-face perpendicularity
and tooth-tip runout frames said nothing a hobby shop could hold that the bore
and blank limits do not already imply. The one roughness symbol is rule 5's
running-surface case: the bore is a size-toleranced fit and a fit lives on the
peaks too. The decimal places are the PART's
(``crank_drive_gear_spec.DRAWING_PRECISION``, applied natively by
``build_crank_drive_gear``); this script only reads them back off the sheet.

Drawn 3:2 -- at 1:1 a 65 mm disc left two thirds of a B sheet empty, and the
face view's 64 teeth need the size to read as teeth.
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
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leaders import (
    assert_leaders_clear,
    dimension_segments,
    leader_segments,
    section_line_segments,
    set_near_side_diameter,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from build_crank_drive_gear import BORE_DIAMETRAL_CLEARANCE
from crank_drive_gear_notes import SHAFT_MATE_NUMBER
from gear_seat_fit import FLAT_AF_CLEARANCE
from crank_drive_gear_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    OUTSIDE_DIA,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["crank_drive_gear"]
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

SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
FRONT_CENTER = (0.135, 0.145)
SECTION_CENTER = (0.290, 0.145)
ISO_CENTER = (0.365, 0.150)
GEAR_DATA_POS = (0.016, 0.262)
# One short tooth-edge note below the gear data; the D-bore fit is carried by
# the two native model dimensions and their feature callout.
MANUFACTURING_NOTES_POS = (0.016, 0.042)

# Half the printed tooth-tip circle, in sheet metres: the face view's silhouette
# radius and the section's half-height, which every dimension is placed clear
# of.
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / (VIEW_SCALE[1] * 2000.0)  # 0.0489
# Half the printed face width: the section's half-WIDTH, so the three views
# can be proven not to overlap offline.
FACE_WIDTH_HALF = FACE_WIDTH * VIEW_SCALE[0] / (VIEW_SCALE[1] * 2000.0)  # 0.0054

# End view: round diameter on the lower left, AF in the lane right of the
# tooth tips and tip diameter above. Dimension text centres on its keep
# point; the A-A arrows and letters stand right of the cutting line's ends
# (crank-pinion sheet), so the tip text sits left of it and its leader,
# aimed at the centre from the text's near end, lands clear of the line.
# The flat itself appears on local +X in the face view.
FRONT_KEEP = {
    "OutsideDia": (FRONT_CENTER[0] - 0.035, FRONT_CENTER[1] + HALF_OD + 0.016),
    "BoreDia": (FRONT_CENTER[0] - 0.078, FRONT_CENTER[1] - 0.062),
    "BoreAF": (FRONT_CENTER[0] + 0.090, FRONT_CENTER[1] + 0.028),
}
# Longitudinal centre section A-A instead of a plain side view: the south bore
# chamfer is internal, and a targeted import delivers a chamfer's size only
# where its edges are drawn. The hidden-line side view returned FaceWidth
# alone (farm run 20260929T061328212Z at 70d2e52); draw_rocker_arm_support's
# RimChamfer is the same case. Cut bottom to top, as draw_crank_pinion does,
# the arrows point +X: the section keeps the +X (flat) half seen from -X, so
# the part's +Z (north) face is on its right and the chamfered south face on
# its left, toward the face view.
SECTION_LINE_OVERRUN = 0.005
# The native caption's top centre, under the section and above the title block.
SECTION_CAPTION_XY = (SECTION_CENTER[0], 0.090)
# Face width above the section; the chamfer's leg dimension runs left off the
# south face into the lane under the AF callout, as RimChamferSize does.
SECTION_KEEP = {
    "FaceWidth": (SECTION_CENTER[0], SECTION_CENTER[1] + HALF_OD + 0.014),
    "BoreSouthChamferSize": (SECTION_CENTER[0] - 0.045, SECTION_CENTER[1] - 0.005),
}

# Native bands on both bore dimensions set the fitted clearance. The callout
# adds process, extent and mating part; it does not repeat those dimensions.
BORE_CALLOUT = (
    "REAM THRU\n"
    f"({BORE_DIAMETRAL_CLEARANCE[0]:.3f}-{BORE_DIAMETRAL_CLEARANCE[1]:.3f} DIAMETRAL\n"
    f"CLEARANCE ON {SHAFT_MATE_NUMBER})"
)
AF_CALLOUT = (
    f"ACROSS FLAT ON {SHAFT_MATE_NUMBER}\n"
    f"({FLAT_AF_CLEARANCE[0]:.3f}-{FLAT_AF_CLEARANCE[1]:.3f} AF CLEARANCE)"
)
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "BoreAF": AF_CALLOUT,
    # The leg and its +0.10/-0.00 band are native; the chamfer feature is
    # 45° on the model, and this suffix identifies the south entry only.
    "BoreSouthChamferSize": " X 45 DEG\nSOUTH BORE ENTRY",
}

# The tip diameter lands on its near (top) rim, the round clearance on
# the lower left, the AF callout on the upper right and the finish on the
# lower right of the surviving circular bore wall.
BORE_SHEET_RADIUS = BORE_DIA * VIEW_SCALE[0] / (VIEW_SCALE[1] * 2000.0)
FINISH_ATTACH = (
    FRONT_CENTER[0] + BORE_SHEET_RADIUS * math.cos(math.pi / 4.0),
    FRONT_CENTER[1] - BORE_SHEET_RADIUS * math.sin(math.pi / 4.0),
)
FINISH_SYMBOL = (FRONT_CENTER[0] + 0.045, FRONT_CENTER[1] - 0.062)
# The finish symbol reads at the sheet's note height, like every other Ra
# in the set; left at the document default it printed twice that.
FINISH_CHAR_HEIGHT = 0.0025
# Past the bore's own radius, only the leaders that land on it arrive.
TIP_DIA_KEEP_OUT = 2.0 * BORE_SHEET_RADIUS
# Where each leader must END, from the gear centre (sheet metres): the tip
# diameter on the tip circle, the bore callout and finish on the bore rim.
# A reading outside its band means the segments are not sheet metres.
TIP_DIA_LANDING = (0.8 * HALF_OD, 1.2 * HALF_OD)
BORE_LANDING = (0.5 * BORE_SHEET_RADIUS, 1.5 * BORE_SHEET_RADIUS)
# The cutting line's strokes end past the tooth tips.
SECTION_LINE_LANDING = (0.0, HALF_OD + SECTION_LINE_OVERRUN + 0.005)


def _hide_tangent_edges(view: Any, label: str) -> None:
    """Drop a view's tangent edges, and prove they went.

    On a 64-tooth TRUE helix every flank-to-tip and flank-to-root transition
    projects as its own curve, so an edge-on view of the rim arrives as a
    stripe field of 128 helical lines -- ink that carries no fact the gear
    data does not state, and that no dimension can be placed on top of. The
    isometric keeps its tangent edges: there the helix is the thing being
    shown.
    """
    view.SetDisplayTangentEdges2(0)
    if int(view.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError(f"failed to hide {label}-view tangent edges")
    view.UpdateViewDisplayGeometry()


def _position_section_caption(adapter: Any, view: Any) -> None:
    """Move the native linked A-A caption under the section, fields intact."""
    candidates = []
    for raw_note in _early_bound(view, "IView").GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>")):
            candidates.append((note, linked_text))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one native linked section caption, found {len(candidates)}")
    note, linked_text = candidates[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*SECTION_CAPTION_XY, 0.0):
        raise RuntimeError("failed to position the 64T section caption")
    rebuild_drawing(adapter, label="position 64T section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], SECTION_CAPTION_XY) > 1e-6:
        raise RuntimeError("64T section caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("64T section caption lost its native fields")


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


def _add_bore_arc_center_mark(adapter: Any, view: Any) -> None:
    """Mark the D-bore axis on its far (-X) circular arc, not the flat."""
    draw = adapter.currentModel
    drawing_doc = _sw_type_info.early_bound_or_flag(
        draw, "IDrawingDoc", "ActivateView", "InsertCenterMark3"
    )
    if not drawing_doc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate 64T front view for bore centre")
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        "", "EDGE", FRONT_CENTER[0] - BORE_SHEET_RADIUS, FRONT_CENTER[1], 0.0,
        False, 0, null_callout(), 0,
    ):
        raise RuntimeError("failed to select the round side of the D-bore")
    center_mark = drawing_doc.InsertCenterMark3(2, False, False)
    draw.ClearSelection2(True)
    if center_mark is None:
        raise RuntimeError("failed to mark the D-bore axis")


def _bore_leaders_clear(
    adapter: Any, front: Any, annotations: list[Any], finish: Any
) -> None:
    """Fail unless the finish reads at note height, no two bore leaders cross,
    and none but the AF dimension touches the A-A cutting line."""
    finish_annotation = finish.GetAnnotation()
    height = float(finish_annotation.GetTextFormat(0).CharHeight)
    if abs(height - FINISH_CHAR_HEIGHT) > 1e-6:
        raise RuntimeError(f"bore finish text height {height} is not {FINISH_CHAR_HEIGHT}")
    tip = _named(adapter, annotations, "OutsideDia")
    set_near_side_diameter(tip, "tip diameter")
    rebuild_drawing(adapter, label="tip diameter near-side leader")
    tip_segments = dimension_segments(tip)
    bore_segments = dimension_segments(_named(adapter, annotations, "BoreDia"))
    finish_segments = leader_segments(finish_annotation)
    assert_leaders_clear(
        {
            "OutsideDia": tip_segments,
            "BoreDia": bore_segments,
            "BoreAF": dimension_segments(_named(adapter, annotations, "BoreAF")),
            "BoreFinish": finish_segments,
        },
        centre=FRONT_CENTER,
        keep_out={"OutsideDia": TIP_DIA_KEEP_OUT},
        lands_within={
            "OutsideDia": TIP_DIA_LANDING,
            "BoreDia": BORE_LANDING,
            "BoreAF": BORE_LANDING,
            "BoreFinish": BORE_LANDING,
        },
        label="crank drive gear bore",
    )
    # AF runs from the round wall across the axis to the flat, so it spans
    # any centre cut; every leader that lands on one rim stays off the line.
    assert_leaders_clear(
        {
            "OutsideDia": tip_segments,
            "BoreDia": bore_segments,
            "BoreFinish": finish_segments,
            "SectionLine": section_line_segments(adapter, front),
        },
        centre=FRONT_CENTER,
        keep_out={},
        lands_within={
            "OutsideDia": TIP_DIA_LANDING,
            "BoreDia": BORE_LANDING,
            "BoreFinish": BORE_LANDING,
            "SectionLine": SECTION_LINE_LANDING,
        },
        label="crank drive gear leaders vs A-A",
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-drive-gear source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank-Drive Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank-drive gear; steel; 64T helical",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        front,
        line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - HALF_OD - SECTION_LINE_OVERRUN),
        line_end=(FRONT_CENTER[0], FRONT_CENTER[1] + HALF_OD + SECTION_LINE_OVERRUN),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="64T longitudinal centre section",
    )
    _position_section_caption(adapter, section)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # The bore profile is a circular arc closed by a flat; the D-shape is
    # explicit in the face view and the section needs no hidden edges.
    for view in (front, section, iso):
        set_hidden_lines_removed(adapter, view)
    _hide_tangent_edges(front, "front")
    _hide_tangent_edges(section, "section")

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter, front_annotations,
        {name: DIMENSION_CALLOUTS[name] for name in FRONT_KEEP if name in DIMENSION_CALLOUTS},
    )
    set_dimension_callouts(
        adapter, section_annotations,
        {"BoreSouthChamferSize": DIMENSION_CALLOUTS["BoreSouthChamferSize"]},
    )
    assert_imported_precision(
        adapter, front_annotations + section_annotations, DRAWING_PRECISION_BY_NAME
    )
    _add_bore_arc_center_mark(adapter, front)
    # The bore is the part's one fit surface, and a fit is a function of the
    # peaks as well as the size: REAM names the operation, not the finish it
    # leaves. The roughness is the project's general machined grade, authored
    # on the PART and read back here (policy rule 5's running-surface case).
    finish = add_surface_finish(
        adapter,
        front,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "crank_drive_gear_bore"),
        label="crank-drive gear bore finish",
        entity=visible_circle_edge(adapter, front, BORE_DIA),
        leader_attach_xy=FINISH_ATTACH,
        char_height=FINISH_CHAR_HEIGHT,
    )
    _bore_leaders_clear(adapter, front, front_annotations, finish)

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_POS, char_height=0.0025
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank-Drive Gear Manufacturing Drawing",
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
