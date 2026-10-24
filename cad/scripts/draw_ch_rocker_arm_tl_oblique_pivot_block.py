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
PLAN_KEEP = {
    'BlockLength':(.130,.265),'BlockWidth':(.212,.205),
    'BlockEndX':(.110,.245),'BlockSideY':(.225,.220),
    'BoreX':(.100,.150),'BoreDia':(.045,.225),
    'CarriageDrills1X':(.105,.138),'CarriageDrills1Y':(.200,.195),
    'CarriageDrills2X':(.105,.126),'CarriageDrills2Y':(.215,.215),
    'CarriageDrills3X':(.145,.114),'CarriageDrills3Y':(.230,.195),
    'CarriageDrills4X':(.145,.102),'CarriageDrills4Y':(.245,.215),
    'CarriageDrills1Dia':(.035,.180),'CarriageCounterbores1Dia':(.035,.150),
}
SIDE_KEEP = {'BlockHeight':(.220,.080),'TopBoreDepth':(.080,.075),'TapDrillDia':(.035,.080)}
FLOOR_KEEP = {'CboreFloor':(.360,.155)}


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
    plan = place_view(adapter,str(source),'*Front',.130,.205,scale=SHEET_SCALE)
    side = create_section_view(adapter,plan,
        line_start=_project(adapter,plan,(-46,0,contract.BLOCK_HEIGHT),'pivot cut start'),
        line_end=_project(adapter,plan,(24,0,contract.BLOCK_HEIGHT),'pivot cut end'),
        view_xy=(.130,.080),section_label='A',scale=(1,1),label='pivot shoulder seat')
    iso = place_view(adapter,str(source),'*Isometric',.355,.235,scale=SHEET_SCALE)
    keep = dict(PLAN_KEEP)
    if is_feed:
        keep |= {'LugWidth':(.130,.025),'LugLength':(.050,.165),
                 'LugEndX':(.080,.035),'LugEndY':(.265,.175)}
    annotations = []
    for view,positions,label in ((plan,keep,'plan'),(side,SIDE_KEEP,'pivot section direction')):
        set_hidden_lines_removed(adapter,view)
        annotations += curate_view_dimensions(adapter,view,keep=positions,view_label=label,
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    start = _project(adapter,plan,(-13,-24,contract.BLOCK_HEIGHT),'floor cut start')
    end = _project(adapter,plan,(-13,24,contract.BLOCK_HEIGHT),'floor cut end')
    floor = create_section_view(adapter,plan,line_start=start,line_end=end,view_xy=(.335,.125),
                                section_label='B',scale=(1,1),label='carriage counterbore floor')
    annotations += curate_view_dimensions(adapter,floor,keep=FLOOR_KEEP,view_label='B-B floor',
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    set_hidden_lines_removed(adapter,iso)
    add_property_linked_note(adapter,'Isometric View Note',.305,.185)
    if is_feed:
        drawing.ActivateSheet(sheets[1])
        nut = place_view(adapter,str(source),'*Left',.190,.175,scale=(2,1))
        nut_iso = place_view(adapter,str(source),'*Isometric',.365,.225,scale=(1,1))
        set_hidden_lines_removed(adapter,nut)
        set_hidden_lines_removed(adapter,nut_iso)
        positions = {'NutAxisY':(.190,.070),'NutAxisZ':(.090,.175),'NutSeatDia':(.070,.235),
                     'NutClearanceDia':(.320,.160)}
        for i in range(1,5):
            positions[f'NutTap{i}Z']=(.080-i*.012,.120+i*.015)
            positions[f'NutTap{i}Y']=(.180,.060-i*.010)
        nut_annotations = curate_view_dimensions(adapter,nut,keep=positions,view_label='nut face',
                      dimensions_by_feature=contract.DRAWING_DIMENSIONS)
        nut_section = create_section_view(adapter,nut,
            line_start=_project(adapter,nut,(contract.NUT_FACE_X,-70,contract.NUT_AXIS_Z),'nut cut start'),
            line_end=_project(adapter,nut,(contract.NUT_FACE_X,-40,contract.NUT_AXIS_Z),'nut cut end'),
            view_xy=(.340,.105),section_label='C',scale=(2,1),label='nut spigot seat depth')
        nut_annotations += curate_view_dimensions(adapter,nut_section,
            keep={'NutSeatDepth':(.330,.065)},view_label='C-C nut seat',
            dimensions_by_feature=contract.DRAWING_DIMENSIONS)
        y,z = contract.NUT_HOLES_YZ[0]
        edge = _project(adapter,nut,(contract.NUT_FACE_X,y+contract.NUT_TAP_DRILL/2,z),'nut tap mouth')
        add_native_hole_callout(adapter,nut,edge_xy=edge,callout_xy=(.310,.255),
                                label='four nut flange taps',process='4X DRILL TO PRINT\n')
        annotations += nut_annotations
    precision = {name:places for dims in contract.DRAWING_PRECISION.values() for name,places in dims.items()}
    assert_imported_precision(adapter,annotations,precision)
    drawing.ActivateSheet(sheets[0])
    outputs = DrawingOutputs(slddrw=spec.outputs['slddrw'],pdf=spec.outputs['pdf'],png=spec.outputs['png'])
    return await finalize_drawing(adapter,outputs,pdf_title='Rocker Oblique Trammel Block Manufacturing Drawing',
                                  scale=SHEET_SCALE,layout=spec.layout)


async def build(adapter):
    return await draw_block(adapter,SPEC,part)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))
