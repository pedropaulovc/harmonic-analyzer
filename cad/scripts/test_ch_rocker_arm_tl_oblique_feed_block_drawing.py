"""Physical contracts for TL-32's integral nut lug and its four taps,
transferred through the TL-VN-84 kit's brass flange nut (FeedNut) at assembly."""
from __future__ import annotations
import ast
import math
from pathlib import Path
import _config
import ch_rocker_arm_tl_oblique_feed_block_spec as spec
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as lead
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

INCH = 25.4
FOLDER = Path(__file__).parent


def test_identity_stock_and_common_pivot_interface():
    metadata=_config.parts(spec.PART_NAME)
    assert metadata['number']=='MHA-CH-06-TL-32'
    assert metadata['quantity']==spec.QUANTITY==1
    assert spec.UNIT=='in'
    # The metric KP08 axis height (owner ruling 4B), the M4 carriage
    # engagement (the jig's RV-05) and the clearance-to-tap wall (owner
    # ruling 2026-11-04, option B) are the declared minors.
    metric,engagement,wall=metadata['machinist_exceptions']
    assert (engagement['id'],engagement['kind'])==('RV-03','minor')
    assert pivot.ENGAGEMENT_TEXT in engagement['where']
    assert 'Owner exception confirmed' in engagement['reason']
    assert (metric['id'],metric['kind'])==('RV-02','minor')
    assert 'ruling 4B' in metric['reason']
    assert metric['where']=='VIEW D: the KP08 leadscrew axis 12.400 ±.13 mm'
    assert (wall['id'],wall['kind'])==('RV-04','minor')
    assert spec.NUT_WALL_MIN_TEXT in wall['where']
    assert '#2184' in wall['reason']
    assert 'TL-27' not in metadata['process'] and 'dowel' not in metadata['process']
    assert feed_nut.NUMBER in metadata['process']
    assert spec.BLOCK_HEIGHT==pivot.BLOCK_HEIGHT
    assert (spec.BLOCK_X0,spec.BLOCK_X1,spec.BLOCK_WIDTH)==(pivot.BLOCK_X0,pivot.BLOCK_X1,pivot.BLOCK_WIDTH)
    assert math.isclose(spec.LUG_X0-spec.BLOCK_X0,spec.PLAN_LUG_X)
    assert math.isclose(spec.LUG_X1-spec.LUG_X0,spec.LUG_WIDTH)
    assert spec.BLOCK_X0<spec.LUG_X0<spec.LUG_X1<spec.BLOCK_X1
    assert math.isclose(spec.BLOCK_WIDTH/2-spec.LUG_Y0,spec.PLAN_OVERALL_Y)
    assert spec.PLAN_OVERALL_Y<pivot.STOCK_WIDTH
    assert spec.LUG_Y1==-spec.BLOCK_WIDTH/2


def test_nut_face_carries_the_screw_clearance_and_four_through_taps_only():
    assert spec.NUT_FACE_X==spec.LUG_X0
    assert math.isclose(spec.NUT_AXIS_Y,-lead.SCREW_LATERAL)
    assert math.isclose(trammel.CARRIAGE_TOP_Z+spec.NUT_AXIS_Z,lead.SCREW_AXIS_Z)
    assert math.isclose(spec.SCREW_CLEARANCE_DIA,.351*INCH)
    assert spec.SCREW_CLEARANCE_DIA-printed_band_mm(3,unit=spec.UNIT)>lead.SCREW_MAJOR_DIA
    assert set(spec.DRAWING_DIMENSIONS)>={'NutClearanceProfile','NutPatternReference','LugProfile'}
    # Option B: the faced nut seats flat (no recess) and the countersunk
    # heads key it (no dowel hole).
    assert not any('Seat' in feature or 'Dowel' in feature for feature in spec.DRAWING_DIMENSIONS)
    model=(FOLDER/'_oblique_pivot_block_model.py').read_text(encoding='utf-8')
    assert 'NutDowel' not in model and 'DOWEL' not in model
    assert spec.NUT_TAP_SPEC.kind=='tapped' and spec.NUT_TAP_SPEC.size=='#4-40'
    assert spec.NUT_TAP_SPEC.end=='through_all'
    assert spec.NUT_TAP_DRILL==TAP_DRILL_MM['#4-40']
    assert spec.NUT_TAP_SPEC.size==feed_nut.SCREW_THREAD


def test_four_taps_sit_on_the_nut_pcd_on_the_lug_diagonals_and_are_transferred():
    # Owner option-B sketch (2026-11-04): the nut's four holes at 45° to the
    # lug's faces; Main ruling 2026-11-03: transferred through the seated nut
    # at TL-00 assembly, located on the sheet by the transfer callout alone.
    assert len(spec.NUT_HOLES_YZ)==feed_nut.SCREW_COUNT==4
    quadrants=set()
    for y,z in spec.NUT_HOLES_YZ:
        dy,dz=y-spec.NUT_AXIS_Y,z-spec.NUT_AXIS_Z
        assert math.isclose(math.hypot(dy,dz),feed_nut.HOLE_PCD/2)
        assert math.isclose(abs(dy),abs(dz))
        quadrants.add((dy>0,dz>0))
    assert len(quadrants)==4
    assert spec.NUT_CLOCK_DEG==45.0 and spec.NUT_CLOCK_TOL_DEG==5.0
    assert spec.TRANSFER_PROCESS=='TRANSFER THROUGH MHA-CH-06-TL-VN-84\nFEED NUT AT ASSEMBLY;\n'
    assert spec.DRAWING_DIMENSIONS['NutPatternReference']==spec.NUT_PATTERN_PRINTED==('NutCentreZ','NutCentreY')
    values=spec.DRAWING_VALUES
    assert math.isclose(values['NutCentreY'],spec.NUT_AXIS_Y-spec.LUG_Y0)
    assert {name:spec.DRAWING_PRECISION_BY_NAME[name] for name in spec.NUT_PATTERN_PRINTED}=={
        'NutCentreZ':3,'NutCentreY':3}
    # r1 review: the .515 names its mate; the D arrow says where VIEW D prints.
    assert spec.CALLOUTS_BELOW['NutCentreY']=='ON KP08 LEADSCREW AXIS'
    assert spec.CALLOUTS_BELOW['NutCentreZ']=='FROM CARRIAGE FACE\nON KP08 LEADSCREW AXIS'
    import _oblique_block_drawing as drawing
    assert drawing.VIEW_SHEET_REF=='(SHEET 2)'
    assert set(drawing.NUT_KEEP)=={'NutCentreY','NutCentreZ','NutClearanceDia'}
    source=(FOLDER/'_oblique_block_drawing.py').read_text(encoding='utf-8')
    assert source.count('process=contract.TRANSFER_PROCESS')==1
    # The callout lands on the tap at the view's upper right (+Y, +Z).
    tree=ast.parse(source)
    [index]=[n.slice.value for n in ast.walk(tree) if isinstance(n,ast.Subscript)
             and ast.unparse(n.value)=='contract.NUT_HOLES_YZ']
    assert spec.NUT_HOLES_YZ[index]==max(spec.NUT_HOLES_YZ)
    assert spec.NUT_HOLES_YZ[index][1]==max(z for _y,z in spec.NUT_HOLES_YZ)


def test_clearance_is_the_smallest_three_place_drill_over_the_vertical_stack():
    # TL-28's as-bought 1 in (±.012) and the lug's 12.400 ±.13 mm put the
    # leadscrew up to .435 mm off the clearance's axis (Codjiflo P1 on #2112).
    assert math.isclose(spec.LEADSCREW_OFFSET_Z,.012*INCH+printed_band_mm(3,unit='mm'))
    assert round(spec.LEADSCREW_OFFSET_Z,4)==.4348
    assert spec.LEADSCREW_RADIAL_CLEARANCE>spec.LEADSCREW_OFFSET
    assert round((spec.LEADSCREW_RADIAL_CLEARANCE-spec.LEADSCREW_OFFSET)*1000)==5
    # Ø.350 would not clear the stack.
    assert (.350*INCH-lead.SCREW_MAJOR_DIA)/2<spec.LEADSCREW_OFFSET


def test_transfer_spot_enters_every_hole_and_the_heads_clear_the_nut_body():
    # A #29 spot enters the smallest accepted hole; at the largest it leaves
    # the tap 0.073 off the hole's axis.
    assert spec.TRANSFER_SPOT_DIA<feed_nut.HOLE_DIA_MIN
    assert math.isclose(spec.FIT_UP_RESIDUAL,(feed_nut.HOLE_DIA_MAX-.136*INCH)/2)
    assert round(spec.FIT_UP_RESIDUAL,3)==.073
    # A held head lies between its countersink's axis and its tap's, so the
    # gap charges the larger offset once. The catalogue head clears the
    # largest body at that worst case, and by more re-centred in its
    # countersink; every head stands proud, so its top Ø is the one beside
    # the body.
    assert feed_nut.HEAD_PROUD_MIN>0.0
    head_r=feed_nut.SCREW_DIMS.head_dia/2
    station=feed_nut.HOLE_PCD/2-feed_nut.HOLE_STATION_BAND
    body_r=feed_nut.BODY_DIA_MAX/2
    assert spec.FIT_UP_RESIDUAL>feed_nut.CSK_ECCENTRICITY_MAX
    worst=station-spec.FIT_UP_RESIDUAL-head_r-body_r
    assert math.isclose(sum(spec.HEAD_TO_BODY_TERMS.values()),worst)
    assert spec.HEAD_TO_BODY_MIN==sum(spec.HEAD_TO_BODY_TERMS.values())
    assert round(spec.HEAD_TO_BODY_MIN,3)==.035
    centred=station-feed_nut.CSK_ECCENTRICITY_MAX-head_r-body_r
    assert math.isclose(spec.HEAD_TO_BODY_CENTRED,centred)
    assert round(spec.HEAD_TO_BODY_CENTRED,3)==.088
    # B18.6.3's sharp-edge Ø.225 head reaches the body even re-centred, so
    # F2's seated-head check stays.
    sharp_r=.225*INCH/2
    assert math.isclose(spec.HEAD_TO_BODY_SHARP_CENTRED,centred-(sharp_r-head_r))
    assert math.isclose(spec.HEAD_TO_BODY_SHARP_MIN,worst-(sharp_r-head_r))
    assert spec.HEAD_TO_BODY_SHARP_MIN<spec.HEAD_TO_BODY_SHARP_CENTRED<0.0


def test_rv04_ruling_states_the_computed_walls():
    # The owner's ruling text carries the spec's worst-case and nominal walls:
    # only the worst case falls under the .080 target.
    [rv04]=[e for e in _config.parts(spec.PART_NAME)['machinist_exceptions'] if e['id']=='RV-04']
    nominal_mm=feed_nut.HOLE_PCD/2-THREAD_MAJOR_MM['#4-40']/2-spec.SCREW_CLEARANCE_DIA/2
    assert WALL_FLOOR_MM<=spec.NUT_WALL_MIN_MM<WALL_TARGET_MM<=nominal_mm
    def inch(mm): return f'{math.floor(mm/INCH*1000+1e-9)/1000:.3f}'.lstrip('0')
    assert f'wall {inch(spec.NUT_WALL_MIN_MM)} in ({spec.NUT_WALL_MIN_MM:.2f} mm)' in rv04['reason']
    assert f'{inch(nominal_mm)} nominal' in rv04['reason']
    assert spec.NUT_WALL_MIN_TEXT in rv04['where']


def test_clearance_to_tap_wall_is_the_stated_shortfall_and_every_face_wall_meets_target():
    walls=spec.LUG_WALLS_MM
    clearance=walls['taps to the leadscrew clearance']
    assert clearance==min(walls.values())==spec.NUT_WALL_MIN_MM
    assert WALL_FLOOR_MM<=clearance<WALL_TARGET_MM
    assert all(v>=WALL_TARGET_MM for k,v in walls.items() if k!='taps to the leadscrew clearance')
    # The radial wall at the clocking limit: the offset's largest component
    # along a tap at 50° from the lug's Y axis, the tap at its least radius.
    a=math.radians(spec.NUT_CLOCK_DEG+spec.NUT_CLOCK_TOL_DEG)
    toward=spec.LEADSCREW_OFFSET_Y*math.cos(a)+spec.LEADSCREW_OFFSET_Z*math.sin(a)
    radius=feed_nut.HOLE_PCD/2-feed_nut.HOLE_STATION_BAND-spec.FIT_UP_RESIDUAL
    clearance_r=(spec.SCREW_CLEARANCE_DIA+drilled_oversize_mm(unit=spec.UNIT))/2
    expected=radius-toward-THREAD_MAJOR_MM['#4-40']/2-clearance_r
    assert math.isclose(clearance,expected)
    assert spec.NUT_WALL_MIN_TEXT=='WALL .060 MIN TO TAPS'
    assert spec.NUT_WALL_MIN<=clearance
    assert spec.CALLOUTS_BELOW['NutClearanceDia']==f'LEADSCREW CLEARANCE\n{spec.NUT_WALL_MIN_TEXT}'
    assert spec.CALLOUTS_ABOVE['NutClearanceDia']=='DRILL THRU'


def test_nut_screws_stop_inside_the_through_tap():
    assert feed_nut.SCREW_TIP_REACH_MAX<spec.LUG_WIDTH


def test_round_flange_stays_within_the_lug_face():
    assert 0.0<=spec.NUT_Z[0]<spec.NUT_Z[1]<=spec.BLOCK_HEIGHT
    assert spec.LUG_Y0<=spec.NUT_Y[0]<spec.NUT_Y[1]<spec.LUG_Y1
    assert math.isclose(spec.NUT_Z[1]-spec.NUT_Z[0],
                        feed_nut.FLANGE_DIA_MAX+2*(spec.METRIC_BAND+spec.LEADSCREW_OFFSET_Z))


def test_plan_ordinates_start_on_the_left_edge():
    values=spec.DRAWING_VALUES
    assert math.isclose(values['PlanBoreX'],pivot.BORE_X-pivot.BLOCK_X0)
    for name,(x,_y) in zip(('PlanHole1X','PlanHole2X'),pivot.PLAN_DATUM_HOLES):
        assert math.isclose(values[name],x-pivot.BLOCK_X0)
    assert math.isclose(values['PlanLugX'],spec.LUG_X0-spec.BLOCK_X0)
    assert math.isclose(values['LugWidth'],spec.LUG_X1-spec.LUG_X0)
    assert math.isclose(values['PlanOverallY'],spec.BLOCK_WIDTH/2-spec.LUG_Y0)
    assert not {'BlockEndX','BoreX','LugEndX','LugEndY','LugLength'}&set(spec.DRAWING_PRECISION_BY_NAME)


def test_reference_lines_on_the_printed_outline_are_plain_sketch_lines():
    # Shown in the plan and VIEW D, the reference sketches' lines lie on the
    # -X edge, the lug's -X face and the lug end; as construction lines their
    # dash font printed over those outlines (machinist review, farm run
    # 20261105T054045952Z). The circles on the holes stay construction.
    tree=ast.parse((FOLDER/'_oblique_pivot_block_model.py').read_text(encoding='utf-8'))
    functions={node.name:node for node in tree.body if isinstance(node,ast.AsyncFunctionDef)}

    def calls(node):
        return [call for call in ast.walk(node) if isinstance(call,ast.Call) and isinstance(call.func,ast.Name)]

    def creates(call,method):
        return any(isinstance(arg,ast.Call) and isinstance(arg.func,ast.Attribute) and arg.func.attr==method
                   for arg in call.args)

    assert '_as_construction' not in {call.func.id for call in calls(functions['_drawn'])}
    assert '_as_construction' in {call.func.id for call in calls(functions['_construction'])}
    for name,lines in (('_plan_datum_reference',2),('_nut_pattern_reference',1)):
        wrappers=[call.func.id for call in calls(functions[name]) if creates(call,'add_line')]
        assert wrappers==['_drawn']*lines, (name,wrappers)
    circles=[call.func.id for call in calls(functions['_construction_circle']) if creates(call,'add_circle')]
    assert circles==['_construction']



def test_nut_and_lug_clear_both_end_blocks_at_both_travel_limits():
    assert math.isclose(spec.NUT_REACH_X[0],spec.NUT_FACE_X-feed_nut.REACH)
    assert feed_nut.REACH==feed_nut.LENGTH_MAX
    for station in trammel.CARRIAGE_TRAVEL:
        lo,hi=(station+v for v in spec.NUT_REACH_X)
        for box in lead.KP08_BOXES.values():
            assert max(box[0]-hi,lo-box[1])>=lead.FEED_GAP
    # The -X gap to the near KP08 at the longest faced nut (13.8).
    near=min(gap for (name,_station),gap in spec.FEED_GAPS.items() if name=='KP08 near')
    assert round(near,1)==2.8


def test_feed_entrypoints_use_the_native_shared_geometry_and_not_a_separate_bracket():
    builder=(FOLDER/'build_ch_rocker_arm_tl_oblique_feed_block.py').read_text()
    assert 'build_block_model(adapter, spec)' in builder
    shared=(FOLDER/'_oblique_pivot_block_model.py').read_text()
    assert 'NutTaps' in shared and 'NutClearance' in shared and 'LugProfile' in shared
    assert 'NutSeat' not in shared
    assert 'part.NUT_HOLES_YZ' in shared
    drawing=(FOLDER/'draw_ch_rocker_arm_tl_oblique_feed_block.py').read_text()
    assert 'draw_block(adapter,SPEC,part,read_source_properties=_read_source_properties)' in drawing


def test_only_the_kp08_axis_height_prints_exact_millimetres():
    # Owner ruling 4 (2026-11-01): the KP08 vendor line prints exact mm; the
    # nut's taps print nothing (transferred).
    assert spec.METRIC_DIMENSIONS=={('NutPatternReference','NutCentreZ'):(3,printed_band_mm(3,unit='mm'))}
