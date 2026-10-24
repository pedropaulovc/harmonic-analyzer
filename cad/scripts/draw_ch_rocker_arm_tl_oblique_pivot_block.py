"""Manufacturing sheets for the plain shoulder-screw pivot blocks.

All sizes import native model dimensions; no bearing/cartridge sheets survive.
The plan origin is the carriage-pattern centre; section B-B shows the floor
from the carriage seat, not a competing counterbore-depth tolerance chain.
"""
from __future__ import annotations
import argparse
import sys
from _check import check
from _com import _early_bound
from _drawing_common import DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties
from _drawing_dimensions import assert_imported_precision
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from solidworks_mcp.adapters.solidworks.drawing import place_view
import ch_rocker_arm_tl_oblique_pivot_block_spec as part

SPEC = DRAWINGS_BY_NAME['ch_rocker_arm_tl_oblique_pivot_block']
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / 'out' / 'sldprt' / f'{PART_STEM}.SLDPRT'
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs['slddrw'],pdf=SPEC.outputs['pdf'],png=SPEC.outputs['png'])
SHEET_SCALE = (1.0,1.0)
# Sheet metres. The plan sits at x .170 so the 104 mm REAM text, the tap
# callout and the 4X callouts fit left of it inside the border, with short
# leaders. Plan geometry on the sheet: block x 139..201, y 185..225; origin
# (carriage-pattern centre) 181,205; bore 149,205; holes x 168/194, y 192/218.
# Section A runs along y 205 (x 135..205); B along x 168 (y 181..229).
# Hole columns and rows are dimensioned once each: CarriageDrills1X/3X chain
# below, 3Y/4Y chain on the +X side (1Y/2X/2Y/4X repeat the same 13.000).
PLAN_XY = (.170,.205)
PLAN_KEEP = {
    'BlockLength':(.170,.265),'BlockEndX':(.150,.252),'BoreX':(.165,.240),
    'BlockWidth':(.236,.195),'BlockSideY':(.224,.220),
    'CarriageDrills3Y':(.212,.1985),'CarriageDrills4Y':(.212,.2115),
    'CarriageDrills1X':(.158,.170),'CarriageDrills3X':(.204,.170),
    'BoreDia':(.078,.226),'CarriageDrills1Dia':(.110,.168),'CarriageCounterbores1Dia':(.095,.150),
}
# Section A-A: Z 0..24.3 prints at y 92.2..67.9 (top face down). The tap's
# dimension line rides the tap-only band (y 75.5..92.2), clear of the 7.65
# seat depth on its left.
SIDE_XY = (.170,.080)
SIDE_KEEP = {'BlockHeight':(.212,.080),'TopBoreDepth':(.120,.072),'TapDrillDia':(.084,.091)}
FLOOR_KEEP = {'CboreFloor':(.360,.155)}
ISO_XY, ISO_SCALE = (.355,.235), SHEET_SCALE
# TL-32: the plan drops 24 mm so its block lands where TL-22's does; the lug
# (x 171.75..190.25, y 137..185) takes the space below, so the hole-column
# chain and the lug's own sizes stand under the lug and A-A moves down 20 mm.
# Its taller pictorial prints at 1:2 to stay under the border.
FEED_PLAN_XY = (.170,.181)
FEED_PLAN_KEEP = PLAN_KEEP | {
    'CarriageDrills1X':(.158,.1145),'CarriageDrills3X':(.204,.1145),
    'LugWidth':(.181,.1305),'LugEndX':(.1635,.1225),
    'LugLength':(.248,.161),'LugEndY':(.260,.171),
}
FEED_SIDE_XY = (.170,.060)
FEED_SIDE_KEEP = {'BlockHeight':(.209,.060),'TopBoreDepth':(.120,.052),'TapDrillDia':(.084,.071)}
FEED_ISO_XY, FEED_ISO_SCALE = (.360,.225), (1,2)
# Nut interface, 2:1 *Left at .190,.175: Z runs right from the -Z face at
# x 165.7, Y=0 prints at y 223; holes at x 179.2/201.8, y 101.7/124.3; nut axis
# 190.5,113; section line C along x 190.5 (y 83..143). Rows and columns are
# dimensioned once: Y on the -Z column (Tap1Y/3Y) in lanes left of the view,
# Z on the upper row (Tap3Z/4Z) over the lug face; both clearance callouts sit
# under or beside the seat with short leaders.
NUT_KEEP = {
    'NutTap1Y':(.134,.160),'NutAxisY':(.144,.168),'NutTap3Y':(.154,.176),
    'NutTap3Z':(.1724,.150),'NutAxisZ':(.178,.157),'NutTap4Z':(.1837,.164),
    'NutSeatDia':(.140,.075),'NutClearanceDia':(.245,.110),
}
# C-C at 1:1 (x 284..346, y 106..194; X mirrors, so the lug's -X face with
# the 1.5 seat step prints at x 313.25, the seat at y 119): the depth text
# stands right of that face.
NUT_SECTION_XY = (.315,.150)
NUT_SECTION_KEEP = {'NutSeatDepth':(.326,.120)}
NUT_CALLOUT_XY = (.245,.088)
NUT_ISO_XY = (.380,.215)


def _project(adapter,view,point,label):
    return model_point_in_view(adapter,view,tuple(v/1000 for v in point),label=label)


async def draw_block(adapter, spec, contract, *, read_source_properties=None):
    source = CAD_ROOT/'out'/'sldprt'/f'{spec.artifact_stem}.SLDPRT'
    check('open block',await adapter.open_model(str(source)))
    if read_source_properties is None:
        read_required_properties(adapter.currentModel,('Number','Material Specification','Finish','Quantity'),
                                 required=('Number','Material Specification','Finish','Quantity'))
    else:
        read_source_properties(adapter)
    drawing,_ = new_project_drawing(adapter,property_view=spec.artifact_stem,scale=SHEET_SCALE,layout=spec.layout)
    is_feed = hasattr(contract,'NUT_FACE_X')
    sheets = ('Pivot and carriage','Nut interface') if is_feed else ('Pivot and carriage',)
    create_blank_drawing_sheets(adapter,sheets,label='block sheets')
    drawing = _early_bound(drawing,'IDrawingDoc')
    drawing.ActivateSheet(sheets[0])
    plan_xy, plan_keep, side_xy, side_keep, iso_xy, iso_scale = (
        (FEED_PLAN_XY, FEED_PLAN_KEEP, FEED_SIDE_XY, FEED_SIDE_KEEP, FEED_ISO_XY, FEED_ISO_SCALE)
        if is_feed else (PLAN_XY, PLAN_KEEP, SIDE_XY, SIDE_KEEP, ISO_XY, ISO_SCALE))
    plan = place_view(adapter,str(source),'*Front',*plan_xy,scale=SHEET_SCALE)
    side = create_section_view(adapter,plan,
        line_start=_project(adapter,plan,(-46,0,contract.BLOCK_HEIGHT),'pivot cut start'),
        line_end=_project(adapter,plan,(24,0,contract.BLOCK_HEIGHT),'pivot cut end'),
        view_xy=side_xy,section_label='A',scale=(1,1),label='pivot shoulder seat')
    iso = place_view(adapter,str(source),'*Isometric',*iso_xy,scale=iso_scale)
    annotations = []
    for view,positions,label in ((plan,plan_keep,'plan'),(side,side_keep,'pivot section direction')):
        set_hidden_lines_removed(adapter,view)
        annotations += curate_view_dimensions(adapter,view,keep=positions,view_label=label,
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    start = _project(adapter,plan,(-13,-24,contract.BLOCK_HEIGHT),'floor cut start')
    end = _project(adapter,plan,(-13,24,contract.BLOCK_HEIGHT),'floor cut end')
    # TL-32's full cut would carry the whole lug beyond the plane; the removed
    # section keeps B-B to the block, as on TL-22.
    floor = create_section_view(adapter,plan,line_start=start,line_end=end,view_xy=(.335,.125),
                                section_label='B',scale=(1,1),partial=is_feed,
                                label='carriage counterbore floor')
    annotations += curate_view_dimensions(adapter,floor,keep=FLOOR_KEEP,view_label='B-B floor',
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    set_hidden_lines_removed(adapter,iso)
    add_property_linked_note(adapter,'Isometric View Note',.305,.185)
    if is_feed:
        drawing.ActivateSheet(sheets[1])
        nut = place_view(adapter,str(source),'*Left',.190,.175,scale=(2,1))
        nut_iso = place_view(adapter,str(source),'*Isometric',*NUT_ISO_XY,scale=FEED_ISO_SCALE)
        set_hidden_lines_removed(adapter,nut)
        set_hidden_lines_removed(adapter,nut_iso)
        nut_annotations = curate_view_dimensions(adapter,nut,keep=NUT_KEEP,view_label='nut face',
                      dimensions_by_feature=contract.DRAWING_DIMENSIONS)
        # 1:1 keeps the full Z=12.4 slice (the removed, partial form imports no
        # NutSeat depth) right of the callouts and clear of the title block.
        nut_section = create_section_view(adapter,nut,
            line_start=_project(adapter,nut,(contract.NUT_FACE_X,-70,contract.NUT_AXIS_Z),'nut cut start'),
            line_end=_project(adapter,nut,(contract.NUT_FACE_X,-40,contract.NUT_AXIS_Z),'nut cut end'),
            view_xy=NUT_SECTION_XY,section_label='C',scale=(1,1),label='nut spigot seat depth')
        nut_annotations += curate_view_dimensions(adapter,nut_section,
            keep=NUT_SECTION_KEEP,view_label='C-C nut seat',
            dimensions_by_feature=contract.DRAWING_DIMENSIONS)
        # The callout picks the +Z column's lower tap, right of section line C
        # at the nut axis, so its short leader from the right crosses neither
        # the line nor its label.
        y,z = contract.NUT_HOLES_YZ[1]
        edge = _project(adapter,nut,(contract.NUT_FACE_X,y+contract.NUT_TAP_DRILL/2,z),'nut tap mouth')
        add_native_hole_callout(adapter,nut,edge_xy=edge,callout_xy=NUT_CALLOUT_XY,
                                label='four nut flange taps',process='4X DRILL TO PRINT\n')
        annotations += nut_annotations
    # Every printed dimension keeps its part-authored places; the repeated
    # row/column locations left off the sheet print nothing to check.
    kept = {*plan_keep, *side_keep, *FLOOR_KEEP, *((*NUT_KEEP, *NUT_SECTION_KEEP) if is_feed else ())}
    precision = {name:places for dims in contract.DRAWING_PRECISION.values()
                 for name,places in dims.items() if name in kept}
    assert_imported_precision(adapter,annotations,precision)
    drawing.ActivateSheet(sheets[0])
    outputs = DrawingOutputs(slddrw=spec.outputs['slddrw'],pdf=spec.outputs['pdf'],png=spec.outputs['png'])
    return await finalize_drawing(adapter,outputs,pdf_title='Rocker Oblique Trammel Block Manufacturing Drawing',
                                  scale=SHEET_SCALE,layout=spec.layout,
                                  # SolidWorks pins its own "#4-40 Tapped Hole" notes by the nut
                                  # taps, whose Hole Wizard callout already states the thread.
                                  # Finalize's all-sheet sweep: farm run 20261024T115707908Z (1:1
                                  # C-C) found 1.
                                  redundant_note_substrings=('#4-40 Tapped Hole',) if is_feed else (),
                                  expected_redundant_notes=1 if is_feed else 0)


async def build(adapter):
    return await draw_block(adapter,SPEC,part)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))
