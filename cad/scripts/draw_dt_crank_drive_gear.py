r"""Create the curated manufacturing drawing for the crank-drive gear (64T).

Recreated under ``cad/docs/drawing-guidelines.md``. The sheet is a
face view, a longitudinal centre section through the keyway and an isometric
of a helical toothed disc with a round bore keyed on local +X, and six native
model dimensions -- outside diameter, four-place face width, round bore
diameter, keyway width and T, and south-entry chamfer -- plus the gear-data block drawing-guidelines.md rule 7 (notes: few, flagged, never a method) keeps
for the crossed-axis tooth system and one numbered note, the keyed bore's
matched fit, that the bore and keyway dimensions link.

No datums, no feature control frames: a gear slipped onto a shaft land is not
on the GD&T allowlist (drawing-guidelines.md rule 5 (avoid excessive GD&T)), and the retired end-face perpendicularity
and tooth-tip runout frames said nothing a hobby shop could hold that the bore
and blank limits do not already imply. The one roughness symbol is drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)'s
running-surface case: the bore is a size-toleranced fit and a fit lives on the
peaks too. The decimal places are the PART's
(``crank_drive_gear_spec.DRAWING_PRECISION``, applied natively by
``build_crank_drive_gear``); this script only reads them back off the sheet.

Drawn 3:2 so the face view's 64 teeth read as teeth on the B sheet. The
sheet prints decimal inch (the part's ``drawing_unit: in``).
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
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
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leaders import (
    assert_leaders_clear,
    dimension_segments,
    section_line_segments,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_crank_drive_gear_notes import GEAR_DATA, KEY_MATE_NUMBER, SHAFT_MATE_NUMBER
from dt_crank_drive_gear_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    OUTSIDE_DIA,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_drive_gear"]
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
# The property-linked block hangs down from GEAR_DATA_POS one 2.5 mm note line
# per row: on farm run 20261001T110844152Z the 15 rows' cap tops ran 261.7 to
# 212.8 mm (3.50 mm pitch) and the last row's descenders reached 208.9 mm.
# (machinist review r1 of #1641); the only other note is the keyed bore's
# numbered fit note (NOTES_XY).
GEAR_DATA_LINE_PITCH = 0.0035
GEAR_DATA_BOTTOM = GEAR_DATA_POS[1] - len(GEAR_DATA.splitlines()) * GEAR_DATA_LINE_PITCH

# Half the printed tooth-tip circle, in sheet metres: the face view's silhouette
# radius and the section's half-height, which every dimension is placed clear
# of.
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / (VIEW_SCALE[1] * 2000.0)
# Half the printed face width: the section's half-WIDTH, so the three views
# can be proven not to overlap offline.
FACE_WIDTH_HALF = FACE_WIDTH * VIEW_SCALE[0] / (VIEW_SCALE[1] * 2000.0)

# End view: round diameter on the lower left, keyway T in the lane right of
# the tooth tips with the keyway width under it, and tip diameter above.
# Dimension text centres on its keep point. The A-A cutting line crosses the
# face on the bore axis, below the tip leader and above the bore leader; only
# T's witness lines, which start on the axis, meet it. The keyway width's
# dimension line stands right of the cutting line's end, so it never meets it.
# The keyway itself appears on local +X in the face view.
#
# The tip text sits up and right of the teeth, right of every gear-data row
# that reaches its height and under the face-width block, so its callout can
# name the mesh its band serves (machinist review r1 of #1641: the mate was
# named only in GEAR DATA).
TIP_DIA_CALLOUT = "FIXED-CENTRE MESH\nWITH MHA-DT-10"
# The T block's widest line is its value; it stands in the lane right of
# the tooth tips, over 3 mm beyond the padded front-view clearance guard and
# over 14 mm to the padded section, without moving its model anchors or the
# chamfer below it. The width block takes the same lane below the cutting
# line.
FRONT_KEEP = {
    "OutsideDia": (FRONT_CENTER[0] + 0.055, FRONT_CENTER[1] + 0.067),
    "BoreDia": (FRONT_CENTER[0] - 0.078, FRONT_CENTER[1] - 0.062),
    "KeywayT": (FRONT_CENTER[0] + 0.099, FRONT_CENTER[1] + 0.028),
    "KeywayWidth": (FRONT_CENTER[0] + 0.099, FRONT_CENTER[1] - 0.035),
}
# Longitudinal centre section A-A instead of a plain side view: the south
# bore chamfer is internal, and a targeted import delivers the chamfer's
# size only into a section whose plane holds the keyway. Probe run
# 20260929T113615557Z-0f9264a5 (223e44d) imported BoreSouthChamfer into each
# candidate view before any other view held it: the cut along +X gave
# BoreSouthChamferSize, while the cut along +Y, *Right and *Back gave
# nothing. Farm run 20260929T064504232Z (525b753) printed FaceWidth alone
# from the +Y cut, and the hidden-line side view did the same at 70d2e52.
# The line runs left to right through the bore axis, and the view is turned
# (``_turn_section_axis_across``) so the gear axis reads left to right like
# the side view it replaces: the chamfered south face on the left, toward
# the face view, and the +Z (north) face on the right.
SECTION_LINE_OVERRUN = 0.005
# The native caption's top centre, under the section and above the title block.
SECTION_CAPTION_XY = (SECTION_CENTER[0], 0.085)
# The native caption's fields: name and letter only, no scale compartment.
SECTION_CAPTION_TEXT = "<VLNAME> <VLLABEL>"
# The cut runs along the face view's horizontal centre line, so A-A projects
# with the keyway to the right; ``_turn_section_axis_across`` turns it 90° CCW
# so the gear axis reads across the sheet. The native caption reads SECTION
# A-A only: the section is drawn at the sheet's 3:2, so it prints no scale
# (drawing-guidelines.md rule 9: a scale equal to the sheet's restates the
# title block). The turn prints in a note centred under the caption, as
# draw_mg_magnifying_wheel labels its turned section, and the turn proves the
# direction (machinist review r3 of #1641: a turned section with no rotation
# label).
ROTATION_NOTE = "ROTATED 90\N{DEGREE SIGN} CCW"
# Top-left anchored, capitals about 2.6 mm a character, its top 9 mm under
# the caption's (a one-line caption's 6.35 mm SECTION letters above it).
ROTATION_NOTE_TOP = SECTION_CAPTION_XY[1] - 0.009
ROTATION_NOTE_CHAR = 0.0026
ROTATION_NOTE_XY = (
    SECTION_CAPTION_XY[0] - len(ROTATION_NOTE) * ROTATION_NOTE_CHAR / 2.0,
    ROTATION_NOTE_TOP,
)
# Face width up and left of the section, its dimension line run out past the
# south witness line so neither witness line strikes the text (machinist
# review r1 of #1641); the chamfer's leg dimension runs left off the south
# face into the lane under the T callout, as RimChamferSize does.
SECTION_KEEP = {
    "FaceWidth": (SECTION_CENTER[0] - 0.040, SECTION_CENTER[1] + HALF_OD + 0.016),
    "BoreSouthChamferSize": (SECTION_CENTER[0] - 0.028, SECTION_CENTER[1] - 0.005),
}
# The face width's +/-.001 is the gear's term in the solid cone-gear stack
# on the cone gear shaft (dt_cone_gear_stack); rule 4 asks that the stack be
# named where the band prints. Below the value: r3 of #1641 set it above, and
# the above lane neither broke its lines nor printed (layout audit
# text-unmatched), while the native below lane prints on every sheet.
FACE_WIDTH_CALLOUT = "SETS CONE GEAR STACK\nON MHA-DT-04"

# Native bands on the bore and keyway dimensions set the fitted clearances:
# the fleet gear-seat fit (gear_seat_fit) on MHA-DT-04's land 1, .0008 wide
# on the round, and cone_land_key's width and T for the MHA-DT-VN-71 key.
# The round's fit route is a matched fit to the finished land with its
# acceptance (drawing-guidelines.md rule 4), named once in numbered note 1
# that the bore and keyway dimensions link (rule 4: one feature with several
# tight dimensions names its mate once). The round bore's callout carries
# REAM, rule 12's process for a fit bore (no flat left for a reamer to cut
# away, so dt-crank-drive-gear.yaml RV-01 is retired); the keyway's bands
# are its requirement and print no process. The mate's name lives here, not beside its number in
# crank_drive_gear_notes, which is in the part's rebuild closure;
# test_crank_drive_gear_drawing checks it against the registry.
SHAFT_MATE_NAME = "CONE GEAR SHAFT"
KEY_MATE_NAME = "KEY"
BORE_FIT_NOTE_NUMBER = 1
BORE_FIT_NOTE = "\n".join(
    (
        f"{BORE_FIT_NOTE_NUMBER}. SLIDING FIT ON {SHAFT_MATE_NAME} {SHAFT_MATE_NUMBER} LAND 1,",
        f"   MADE TO ITS MEASURED LAND; DRIVEN BY {KEY_MATE_NAME}",
        f"   {KEY_MATE_NUMBER}; SLIDES ON, NO ROCK.",
    )
)
# The sheet's numbered notes, in one block (rule 7: at most four short
# lines), top-left anchored at the lower left: under the round bore's
# callout, left of the title block (x 0.216), inside the border.
SHEET_NOTES = BORE_FIT_NOTE
NOTES_XY = (0.016, 0.060)
BORE_CALLOUT = f"REAM THRU\nSEE NOTE {BORE_FIT_NOTE_NUMBER}"
KEYWAY_WIDTH_CALLOUT = f"KEYWAY\nSEE NOTE {BORE_FIT_NOTE_NUMBER}"
KEYWAY_T_CALLOUT = f"KEYWAY TO FAR SIDE\nSEE NOTE {BORE_FIT_NOTE_NUMBER}"
DIMENSION_CALLOUTS = {
    "OutsideDia": TIP_DIA_CALLOUT,
    "BoreDia": BORE_CALLOUT,
    "KeywayWidth": KEYWAY_WIDTH_CALLOUT,
    "KeywayT": KEYWAY_T_CALLOUT,
    "FaceWidth": FACE_WIDTH_CALLOUT,
    # The leg is native and prints under the title block's .XX band; the
    # chamfer feature is 45° on the model. The callout says why the chamfer
    # is there; the leader shows which end (fan-out r1: "THIS END" made a
    # third row of words, rule 7). SolidWorks sets the block's widest line
    # against the leg's own dimension line, whose extension lines overrun it
    # by 1 mm: two trailing spaces on every line keep that ink clear (r3 of
    # #1641 printed RUNOUT's T on the line).
    "BoreSouthChamferSize": (
        " X 45\N{DEGREE SIGN}  \nCLEARS COLLAR ROOT  \nOF MHA-DT-04  "
    ),
}

# The tip diameter lands on its near (upper right) rim and the round
# diameter on the lower left of the circular bore wall.
BORE_SHEET_RADIUS = BORE_DIA * VIEW_SCALE[0] / (VIEW_SCALE[1] * 2000.0)
# Past the bore's own radius, only the leaders that land on it arrive.
TIP_DIA_KEEP_OUT = 2.0 * BORE_SHEET_RADIUS
# Where each leader must END, from the gear centre (sheet metres): the tip
# diameter on the tip circle, the bore callout on the bore rim.
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
    """Drop the A-A caption's scale, move it under the section and label the
    turn under it.

    The caption keeps its native name and letter fields; the section is at
    the sheet's scale, so its scale fields go (as draw_dt_cone_pivot_post
    captions its A-A). The turn is a plain note centred under it.
    """
    candidates = []
    for raw_note in _early_bound(view, "IView").GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>")):
            candidates.append(note)
    if len(candidates) != 1:
        raise RuntimeError(f"expected one native linked section caption, found {len(candidates)}")
    note = candidates[0]
    note.PropertyLinkedText = SECTION_CAPTION_TEXT
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*SECTION_CAPTION_XY, 0.0):
        raise RuntimeError("failed to position the 64T section caption")
    rebuild_drawing(adapter, label="position 64T section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], SECTION_CAPTION_XY) > 1e-6:
        raise RuntimeError("64T section caption position did not persist")
    if str(note.PropertyLinkedText or "") != SECTION_CAPTION_TEXT:
        raise RuntimeError("64T section caption did not keep name-and-letter fields only")
    if add_note(adapter, ROTATION_NOTE, *ROTATION_NOTE_XY) is None:
        raise RuntimeError(f"failed to label section A-A {ROTATION_NOTE}")


def _section_axes(adapter: Any, view: Any) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet directions of the gear axis (+Z) and the keyway's direction (+X)."""
    origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="64T section origin")
    axes = []
    for xyz, name in (((0.0, 0.0, 0.001), "gear axis"), ((0.001, 0.0, 0.0), "keyway direction")):
        point = model_point_in_view(adapter, view, xyz, label=f"64T section {name}")
        axes.append((point[0] - origin[0], point[1] - origin[1]))
    return axes[0], axes[1]


def _turn_section_axis_across(adapter: Any, view: Any) -> None:
    """Turn A-A so the gear axis reads left to right, keyway side up.

    Cut along +X, the section lands with the axis vertical. A left-to-right
    axis puts the south face, the chamfered one, toward the face view. With
    the keyway up the sight runs along -Y, so the A-A arrows point down, away
    from the T dimension line above the cutting line.
    """
    native = _early_bound(view, "IView")
    section = _early_bound(native.GetSection(), "IDrSection")
    axis, keyway = _section_axes(adapter, native)
    if axis[0] * keyway[1] - axis[1] * keyway[0] < 0.0:
        reversed_cut = not bool(section.GetReversedCutDirection())
        section.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="reverse 64T section")
        if bool(section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("64T section cutting direction did not persist")
        axis, keyway = _section_axes(adapter, native)
    # SolidWorks lays the aligned section in projection, the keyway along the
    # cutting line as in the face view: rightward. Turning it up is
    # 90° counter-clockwise, which ROTATION_NOTE prints; any other start
    # would make the label false, so it fails the build instead.
    if keyway[0] <= 0.0 or abs(keyway[1]) > 1e-8:
        raise RuntimeError(
            f"64T section does not lay the keyway rightward before its turn ({keyway=}), "
            f"so {ROTATION_NOTE!r} would be false"
        )
    native.Angle = float(native.Angle) - math.atan2(axis[1], axis[0])
    rebuild_drawing(adapter, label="turn 64T section")
    axis, keyway = _section_axes(adapter, native)
    if axis[0] <= 0.0 or abs(axis[1]) > 1e-8 or keyway[1] <= 0.0 or abs(keyway[0]) > 1e-8:
        raise RuntimeError(f"64T section did not turn axis-across: {axis=}, {keyway=}")
    _telemetry.info(
        f"64T section turned: angle={float(native.Angle):.6f} rad, "
        f"reversed={bool(section.GetReversedCutDirection())}"
    )


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


def _add_bore_arc_center_mark(adapter: Any, view: Any) -> None:
    """Mark the bore axis on its far (-X) circular arc, away from the keyway."""
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
        raise RuntimeError("failed to select the round side of the keyed bore")
    center_mark = drawing_doc.InsertCenterMark3(2, False, False)
    draw.ClearSelection2(True)
    if center_mark is None:
        raise RuntimeError("failed to mark the keyed bore axis")


def _bore_leaders_clear(adapter: Any, front: Any, annotations: list[Any]) -> None:
    """Fail unless no two face-view leaders cross and none but the keyway T
    dimension touches the A-A cutting line."""
    tip = _named(adapter, annotations, "OutsideDia")
    set_near_side_diameter(tip, "tip diameter")
    # Native, the bore diameter's line runs rim to rim through the centre,
    # across the centre cut (run 20260929T120308584Z); one arrow on the
    # lower-left rim keeps it below the line, as draw_crank_arm's hub seat.
    bore = _named(adapter, annotations, "BoreDia")
    set_near_side_diameter(bore, "bore diameter")
    rebuild_drawing(adapter, label="tip and bore diameter near-side leaders")
    tip_segments = dimension_segments(tip)
    bore_segments = dimension_segments(bore)
    width_segments = dimension_segments(_named(adapter, annotations, "KeywayWidth"))
    assert_leaders_clear(
        {
            "OutsideDia": tip_segments,
            "BoreDia": bore_segments,
            "KeywayT": dimension_segments(_named(adapter, annotations, "KeywayT")),
            "KeywayWidth": width_segments,
        },
        centre=FRONT_CENTER,
        keep_out={"OutsideDia": TIP_DIA_KEEP_OUT},
        lands_within={
            "OutsideDia": TIP_DIA_LANDING,
            "BoreDia": BORE_LANDING,
            "KeywayT": BORE_LANDING,
            "KeywayWidth": BORE_LANDING,
        },
        label="crank drive gear bore",
    )
    # T runs from the round wall across the axis to the keyway top, so it
    # spans any centre cut; every leader that lands on one rim stays off the line.
    assert_leaders_clear(
        {
            "OutsideDia": tip_segments,
            "BoreDia": bore_segments,
            "KeywayWidth": width_segments,
            "SectionLine": section_line_segments(adapter, front),
        },
        centre=FRONT_CENTER,
        keep_out={},
        lands_within={
            "OutsideDia": TIP_DIA_LANDING,
            "BoreDia": BORE_LANDING,
            "KeywayWidth": BORE_LANDING,
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
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
        line_start=(FRONT_CENTER[0] - HALF_OD - SECTION_LINE_OVERRUN, FRONT_CENTER[1]),
        line_end=(FRONT_CENTER[0] + HALF_OD + SECTION_LINE_OVERRUN, FRONT_CENTER[1]),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="64T longitudinal centre section",
    )
    _turn_section_axis_across(adapter, section)
    _position_section_caption(adapter, section)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # The bore profile is a circular arc closed by the keyway; the keyed
    # shape is explicit in the face view and the section needs no hidden edges.
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
    # Every callout reads below its value.
    set_dimension_callouts(
        adapter, front_annotations,
        {name: DIMENSION_CALLOUTS[name] for name in FRONT_KEEP if name in DIMENSION_CALLOUTS},
    )
    set_dimension_callouts(
        adapter, section_annotations,
        {name: DIMENSION_CALLOUTS[name] for name in SECTION_KEEP},
    )
    assert_imported_precision(
        adapter, front_annotations + section_annotations, DRAWING_PRECISION_BY_NAME
    )
    _add_bore_arc_center_mark(adapter, front)
    # No roughness symbol: the keyed bore is a gear seat, not a running surface
    # (drawing-guidelines.md rule 6; dt_crank_drive_gear_spec.SURFACE_FINISHES).
    _bore_leaders_clear(adapter, front, front_annotations)

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025)
    if add_note(adapter, SHEET_NOTES, *NOTES_XY) is None:
        raise RuntimeError("failed to add the 64T's numbered notes")
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
