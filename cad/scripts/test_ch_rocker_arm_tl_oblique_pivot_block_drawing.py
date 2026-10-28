"""Offline physical contracts for the simplified TL-22 shoulder-screw block."""
from __future__ import annotations
import ast
import math
from pathlib import Path
import _config
import ch_rocker_arm_tl_oblique_pivot_block_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _printed_tolerance import printed_band_mm


def test_rectangular_rail_two_block_and_new_stock():
    assert (spec.BLOCK_X0,spec.BLOCK_X1,spec.BLOCK_WIDTH,spec.BLOCK_HEIGHT)==(-42,20,40,24.3)
    assert spec.BLOCK_HEIGHT == trammel.PIVOT_BLOCK_HEIGHT
    assert (spec.STOCK_THICKNESS,spec.STOCK_WIDTH)==(25.4,88.9)
    metadata=_config.parts(spec.PART_NAME)
    assert metadata['number']=='MHA-CH-06-TL-22'
    assert metadata['quantity']==spec.QUANTITY==1
    assert not metadata.get('machinist_exceptions')


def test_pivot_shoulder_bottoms_with_full_form_thread_engagement():
    assert (spec.BORE_X,spec.BORE_Y)==(-32,0)
    assert (spec.BORE_DIA,spec.BORE_BAND,spec.BORE_DEPTH)==(10,(.015,0),7.65)
    assert spec.PIVOT_TAP=='M8x1.25'
    assert spec.PIVOT_TAP_DRILL==6.8
    assert spec.PIVOT_THREAD_LENGTH==spec.BLOCK_HEIGHT-spec.BORE_DEPTH
    # Full-form thread: the screw's 13 less 1.5 pitches, held to RV-05's floor.
    assert spec.PIVOT_THREAD_ENGAGEMENT==13-1.5*1.25
    assert round(spec.PIVOT_THREAD_ENGAGEMENT/8,2)>=spec.PIVOT_THREAD_ENGAGEMENT_MIN_D
    assert spec.PIVOT_THREAD_ENGAGEMENT<1.5*8
    assert spec.PIVOT_THREAD_LENGTH>13
    min_text=spec.CALLOUTS_BELOW['TapDrillDia'].splitlines()[-1]
    assert float(min_text.split()[0])<=spec.PIVOT_THREAD_ENGAGEMENT
    assert spec.BORE_X==trammel.PIN_OFFSET
    assert spec.BORE_LIMITS == (10.0, 10.015)
    assert math.isclose(spec.PIVOT_LOCATING_CLEARANCE_MIN, 0.0, abs_tol=1e-9)
    assert math.isclose(spec.PIVOT_LOCATING_CLEARANCE_MAX, 0.040, abs_tol=1e-9)


def test_carriage_pattern_floor_and_vendor_thread_bottom_are_unchanged():
    assert set(spec.BOLT_POINTS)=={(-13,-13),(-13,13),(13,-13),(13,13)}
    assert tuple(2*x for x in (spec.BOLT_X,spec.BOLT_Y))==trammel.CARRIAGE_BOLT_SPAN
    assert (spec.HOLE_DIA,spec.CBORE_DIA,spec.CBORE_FLOOR)==(4.5,8,15.6)
    assert math.isclose(spec.CBORE_DEPTH,8.7)
    assert math.isclose(spec.ENGAGEMENT_MIN,3.85)
    assert math.isclose(spec.ENGAGEMENT_MAX,4.95)
    assert spec.ENGAGEMENT_MAX<=spec.CARRIAGE_THREAD_DEPTH-.05+1e-9
    assert spec.DRAWING_PRECISION[spec.CBORE_FLOOR_REFERENCE]['CboreFloor']==3
    assert spec.CBORE_FLOOR-printed_band_mm(3)>0


def test_no_bearing_web_wing_cap_or_side_features_survive():
    assert min(spec.WALLS_MM.values())>=2
    for name in ('WING_WIDTH','SHOULDER_HOLE_DIA','CAP_TAP_POINTS','CAP_REGISTER_POINTS',
                 'SIDE_SCREW_HOLES','SEAT_POSITION_DIA','BEARING_OD'):
        assert not hasattr(spec,name)
    assert set(spec.CALLOUTS_BELOW)<=set(spec.DRAWING_PRECISION_BY_NAME)


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
