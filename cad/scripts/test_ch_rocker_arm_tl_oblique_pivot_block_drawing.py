"""Offline physical contracts for the simplified TL-22 shoulder-screw block."""
from __future__ import annotations
import ast
import math
from pathlib import Path
import _config
import ch_rocker_arm_tl_oblique_pivot_block_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_band_mm

INCH = 25.4


def test_rectangular_rail_two_block_and_new_stock():
    assert spec.UNIT == 'in'
    assert math.isclose(spec.BLOCK_X1-spec.BLOCK_X0,spec.BLOCK_LENGTH)
    assert math.isclose(spec.BORE_X-spec.BLOCK_X0,spec.PLAN_BORE_X)
    assert spec.BLOCK_HEIGHT == trammel.PIVOT_BLOCK_HEIGHT
    assert spec.BLOCK_HEIGHT<spec.STOCK_THICKNESS and spec.BLOCK_WIDTH<spec.STOCK_WIDTH
    metadata=_config.parts(spec.PART_NAME)
    assert metadata['number']=='MHA-CH-06-TL-22'
    assert metadata['quantity']==spec.QUANTITY==1
    # Every counterbore wall now meets the inch target: no exception survives.
    assert not metadata.get('machinist_exceptions')


def test_pivot_shoulder_bottoms_with_full_form_thread_engagement():
    assert (spec.BORE_X,spec.BORE_Y)==(trammel.PIN_OFFSET,0)
    assert spec.PIVOT_TAP==pivot_screw.THREAD
    assert spec.PIVOT_TAP_DRILL<spec.BORE_LIMITS[0]
    assert spec.PIVOT_THREAD_LENGTH==spec.BLOCK_HEIGHT-spec.BORE_DEPTH
    # Full-form thread: the shop-cut thread less 1.5 pitches, 1.5D at its worst.
    assert math.isclose(spec.PIVOT_THREAD_ENGAGEMENT,
                        pivot_screw.CUT_THREAD_LENGTH-1.5*pivot_screw.THREAD_PITCH)
    assert spec.PIVOT_THREAD_ENGAGEMENT_MIN>=1.5*pivot_screw.THREAD_DIA
    # The cut tip stays inside the block bottom by .011 at every band.
    assert spec.PIVOT_TIP_CLEARANCE_MIN>=0.011*INCH-1e-9
    assert spec.PIVOT_TIP_CLEARANCE>spec.PIVOT_TIP_CLEARANCE_MIN
    # The shoulder slides in the reamed seat: clearance at every band.
    assert 0.0<spec.PIVOT_LOCATING_CLEARANCE_MIN<spec.PIVOT_LOCATING_CLEARANCE_MAX
    assert spec.PIVOT_LOCATING_CLEARANCE_MAX<=0.0025*INCH+1e-9


def test_carriage_screws_cut_to_fit_from_the_lowered_floor():
    assert set(spec.BOLT_POINTS)=={(-13,-13),(-13,13),(13,-13),(13,13)}
    assert tuple(2*x for x in (spec.BOLT_X,spec.BOLT_Y))==trammel.CARRIAGE_BOLT_SPAN
    assert 4.0<spec.HOLE_DIA<spec.CBORE_DIA
    assert math.isclose(spec.CBORE_DEPTH,spec.BLOCK_HEIGHT-spec.CBORE_FLOOR)
    # Owner ruling 2026-11-01 (option A): floor .570, each M4 x 20 cut to its
    # floor plus .189 (±.005 cut, .001 reading): .183 MIN (1.16D), never
    # bottoming in the M4 x 5, and every cut fits the shortest bought screw.
    assert math.isclose(spec.CBORE_FLOOR,.570*INCH)
    assert math.isclose(spec.SCREW_REACH,.189*INCH)
    assert math.isclose(spec.SCREW_CUT_LENGTH,(.570+.189)*INCH)
    assert math.isclose(spec.ENGAGEMENT_MIN,.183*INCH)
    assert spec.ENGAGEMENT_TEXT=='.183'
    assert spec.ENGAGEMENT_MIN>=1.16*4.0
    assert spec.ENGAGEMENT_MAX<=spec.CARRIAGE_THREAD_DEPTH-.045+1e-9
    assert spec.SCREW_CUT_LENGTH_MAX<spec.SCREW_LENGTH-spec.SCREW_LENGTH_TOL
    assert spec.CALLOUTS_BELOW['CboreFloor']=='FLOOR FOR M4 X 20 CUT\nENGAGES .183 MIN (1.16D)'
    assert spec.DRAWING_PRECISION[spec.CBORE_FLOOR_REFERENCE]['CboreFloor']==3
    assert spec.CBORE_FLOOR-printed_band_mm(3,unit=spec.UNIT)>0


def test_no_bearing_web_wing_cap_or_side_features_survive():
    assert min(spec.WALLS_MM.values())>=WALL_TARGET_MM
    for name in ('WING_WIDTH','SHOULDER_HOLE_DIA','CAP_TAP_POINTS','CAP_REGISTER_POINTS',
                 'SIDE_SCREW_HOLES','SEAT_POSITION_DIA','BEARING_OD'):
        assert not hasattr(spec,name)
    assert set(spec.CALLOUTS_BELOW)<=set(spec.DRAWING_PRECISION_BY_NAME)


def test_outline_bands_keep_the_counterbore_walls_at_target():
    places=spec.DRAWING_PRECISION_BY_NAME
    assert places['BlockLength']==places['BlockWidth']
    assert spec.CBORE_END_WALL_MIN>=WALL_TARGET_MM
    assert spec.CBORE_SIDE_WALL_MIN>=WALL_TARGET_MM


def test_native_builder_owns_real_solids_dimensions_and_final_volume():
    source=Path(__file__).with_name('_oblique_pivot_block_model.py').read_text()
    tree=ast.parse(source)
    literals={node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)}
    assert {'Block','TopBore','PivotTap','CarriageDrills','CarriageCounterbores'}<=literals
    assert 'finished block' in literals
    assert 'BoreDia' in literals
    assert 'TopBoreDepth' in literals
    assert 'SeatFillets' not in literals
    assert 'BottomBore' not in literals


def test_drawing_has_only_pivot_and_carriage_sections_under_enforcement():
    source=Path(__file__).with_name('draw_ch_rocker_arm_tl_oblique_pivot_block.py').read_text()
    tree=ast.parse(source)
    # Machinist review ENFORCE (#1974) carries over to the simplified block.
    assert any(isinstance(n,ast.Assign) and [t.id for t in n.targets if isinstance(t,ast.Name)]==['MACHINIST_REVIEW'] and ast.unparse(n.value)=='MachinistReviewMode.ENFORCE' for n in tree.body)
    assert 'carriage counterbore floor' in source
    assert 'pivot shoulder seat' in source
    assert 'add_feature_control_frame' not in source
    assert 'create_section_view' in source


def test_block_height_prints_on_a_right_view_level_with_the_plan():
    import draw_ch_rocker_arm_tl_oblique_pivot_block as drawing
    assert drawing.RIGHT_XY[1]==drawing.PLAN_XY[1]
    assert set(drawing.RIGHT_KEEP)=={'BlockHeight'}
    assert 'BlockHeight' in spec.DRAWING_DIMENSIONS['Block']
    assert 'BlockHeight' not in drawing.SIDE_KEEP
