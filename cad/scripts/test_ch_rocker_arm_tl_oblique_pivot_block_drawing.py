"""Offline physical contracts for the simplified TL-22 shoulder-screw block."""
from __future__ import annotations
import ast
import math
from pathlib import Path
from types import SimpleNamespace
import pytest
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
    # Every counterbore wall meets the inch target; the one exception is the
    # M4 engagement (test_engagement_shortfall_is_the_declared_minor).
    assert [row['id'] for row in metadata['machinist_exceptions']]==['RV-01']


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
    # floor plus .189 (±.005 cut, .001 reading): the tip reaches .183 MIN,
    # .162 MIN (1.03D) of it full thread past the 0.75P tip chamfer, never
    # bottoming in the M4 x 5, and every cut fits the shortest bought screw.
    assert math.isclose(spec.CBORE_FLOOR,.570*INCH)
    assert math.isclose(spec.SCREW_REACH,.189*INCH)
    assert math.isclose(spec.SCREW_CUT_LENGTH,(.570+.189)*INCH)
    assert math.isclose(spec.REACH_MIN,.183*INCH)
    assert math.isclose(spec.ENGAGEMENT_MIN,spec.REACH_MIN-.75*.7)
    assert spec.ENGAGEMENT_TEXT=='.162'
    assert spec.ENGAGEMENT_DIAMETERS=='1.03D'
    assert spec.REACH_MAX<=spec.CARRIAGE_THREAD_DEPTH-.045+1e-9
    assert spec.SCREW_CUT_LENGTH_MAX<spec.SCREW_LENGTH-spec.SCREW_LENGTH_TOL
    assert spec.CALLOUTS_BELOW['CboreFloor']=='FLOOR FOR M4 X 20 CUT\nENGAGES .162 MIN (1.03D)'
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
    assert spec.BORE_X == spec.BORE_Y == trammel.PIN_OFFSET == 0.0
    assert math.isclose(spec.BLOCK_LENGTH / INCH, 1.64)
    assert math.isclose(spec.PLAN_BORE_X / INCH, .82)
    assert spec.BLOCK_X0 == -spec.BLOCK_X1
    assert min(spec.CBORE_NEAR_END_WALL_MIN, spec.BORE_CBORE_WEB_MIN,
               spec.SHIM_CBORE_GAP_MIN, spec.BORE_END_WALL_MIN) >= WALL_TARGET_MM


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
    assert "require_block_geometry(adapter, part)" in source
    assert "geometry.parameters" in source and "dimension.SystemValue" in source


def test_drawing_has_only_pivot_and_carriage_sections_under_enforcement():
    source=Path(__file__).with_name('draw_ch_rocker_arm_tl_oblique_pivot_block.py').read_text()
    tree=ast.parse(source)
    # Machinist review ENFORCE (#1974) carries over to the simplified block.
    assert any(isinstance(n,ast.Assign) and [t.id for t in n.targets if isinstance(t,ast.Name)]==['MACHINIST_REVIEW'] and ast.unparse(n.value)=='MachinistReviewMode.ENFORCE' for n in tree.body)
    # The sheet's views come from the builder it shares with TL-32.
    builder=Path(__file__).with_name('_oblique_block_drawing.py').read_text()
    assert 'carriage counterbore floor' in builder
    assert 'pivot shoulder seat' in builder
    assert 'add_feature_control_frame' not in builder
    assert 'create_section_view' in builder


def test_block_height_prints_on_a_right_view_level_with_the_plan():
    import _oblique_block_drawing as drawing
    assert drawing.RIGHT_XY[1]==drawing.PLAN_XY[1]
    assert set(drawing.RIGHT_KEEP)=={'BlockHeight'}
    assert 'BlockHeight' in spec.DRAWING_DIMENSIONS['Block']
    assert 'BlockHeight' not in drawing.SIDE_KEEP


def test_engagement_shortfall_is_the_declared_minor():
    (engagement,)=_config.parts(spec.PART_NAME)['machinist_exceptions']
    assert (engagement['id'],engagement['kind'])==('RV-01','minor')
    assert spec.ENGAGEMENT_TEXT in engagement['where']
    assert 'Owner exception confirmed' in engagement['reason']


@pytest.mark.parametrize("feed,fault", [
    (feed, fault)
    for feed in (False, True)
    for fault in (None, "missing", "axis", "diameter", "dimension", "extra_body")
] + [
    (True, fault)
    for fault in ("nut_missing", "nut_mirrored", "nut_rounded_body",
                  "nut_wrong_drill", "nut_unreadable_drill", "nut_no_definition")
])
def test_native_block_readback_refuses_moved_or_missing_geometry(monkeypatch, feed, fault):
    import _oblique_pivot_block_model as model
    import _drawing_precision
    import _gtol_face_read
    import _feature_tree
    from _gtol_face import SURFACE_CYLINDER, SURFACE_PLANE
    import ch_rocker_arm_tl_oblique_feed_block_spec as feed_spec

    part = feed_spec if feed else spec
    cylinders = []
    # A blind-tap Wizard can retain the exact inch drill conversion while
    # TAP_DRILL_MM stores three decimal mm. This is a binding fixture, not
    # a claim that worker10's unrecorded physical radius has been measured.
    native_drill_mm = .089 * INCH
    definition = SimpleNamespace(TapDrillDiameter=native_drill_mm / 1000.0)
    if fault == "nut_wrong_drill":
        definition.TapDrillDiameter = .0023
    if fault == "nut_unreadable_drill":
        definition.TapDrillDiameter = float("nan")
    feature = SimpleNamespace(
        GetTypeName2=lambda: "HoleWzd",
        GetDefinition=lambda: None if fault == "nut_no_definition" else definition,
    )
    monkeypatch.setattr(_feature_tree, "_feature_by_name", lambda adapter, name: feature)

    def cylinder(axis, centre, diameter):
        direction = [0.0, 0.0, 0.0]
        direction[axis] = 1.0
        cylinders.append(SimpleNamespace(
            identity=SURFACE_CYLINDER,
            parameters=tuple(v / 1000.0 for v in centre) + tuple(direction) + (diameter / 2000.0,),
        ))

    cylinder(2, (0.0, 0.0, 0.0), spec.BORE_DIA)
    cylinder(2, (0.0, 0.0, 0.0), spec.PIVOT_TAP_DRILL)
    for x, y in spec.BOLT_POINTS:
        for diameter in (spec.HOLE_DIA, spec.CBORE_DIA):
            cylinder(2, (x, y, 0.0), diameter)
    if feed:
        cylinder(0, (0.0, part.NUT_AXIS_Y, part.NUT_AXIS_Z), part.SCREW_CLEARANCE_DIA)
        for y, z in part.NUT_HOLES_YZ:
            cylinder(0, (0.0, y, z), native_drill_mm)
        # The merged +X end (owner ruling 2026-11-07), read by vertices.
        corners = [SimpleNamespace(GetPoint=lambda p=p: [v / 1000.0 for v in p])
                   for p in ((part.BLOCK_X1, part.LUG_Y0, 0.0),
                             (part.BLOCK_X1, part.BLOCK_WIDTH / 2, part.BLOCK_HEIGHT))]
        edge = SimpleNamespace(GetStartVertex=lambda: corners[0], GetEndVertex=lambda: corners[1])
        cylinders.append(SimpleNamespace(
            identity=SURFACE_PLANE, outward_normal=(1.0, 0.0, 0.0),
            parameters=(1.0, 0.0, 0.0, part.BLOCK_X1 / 1000.0, 0.0, 0.0), GetEdges=lambda: [edge],
        ))
    if fault == "missing":
        cylinders.pop(0)
    if fault in ("axis", "diameter"):
        values = list(cylinders[0].parameters)
        values[0 if fault == "axis" else 6] += 0.001
        cylinders[0].parameters = tuple(values)
    if fault == "nut_missing":
        cylinders.pop(11)
    if fault in ("nut_mirrored", "nut_rounded_body"):
        values = list(cylinders[11].parameters)
        if fault == "nut_mirrored":
            values[1] = -values[1]
        else:
            # Even the 0.0004 mm difference must fail if the solid disagrees
            # with its exact committed Wizard definition.
            values[6] = part.NUT_TAP_DRILL / 2000.0
        cylinders[11].parameters = tuple(values)
    body = SimpleNamespace(GetFaces=lambda: cylinders)
    document = SimpleNamespace(GetBodies2=lambda kind, visible: [body] * (2 if fault == "extra_body" else 1))
    adapter = SimpleNamespace(currentModel=document)
    monkeypatch.setattr(model, "_early_bound", lambda obj, kind: obj)
    monkeypatch.setattr(_gtol_face_read, "face_geometry", lambda face, **kwargs: face)

    def dimensions(adapter, feature, names):
        return {
            name: (None, SimpleNamespace(
                SystemValue=(part.DRAWING_VALUES[name] + (1.0 if fault == "dimension" else 0.0)) / 1000.0
            ))
            for name in names
        }

    monkeypatch.setattr(_drawing_precision, "_named_dimensions", dimensions)
    if fault is None:
        model.require_block_geometry(adapter, part)
    else:
        with pytest.raises(RuntimeError) as error:
            model.require_block_geometry(adapter, part)
        if fault in ("nut_missing", "nut_mirrored", "nut_rounded_body"):
            assert "observed solid cylinders" in str(error.value)
            assert "diameter_mm" in str(error.value) and "origin_mm" in str(error.value)


@pytest.mark.parametrize("raw_result", [False, True])
def test_committed_nut_drill_binds_dispatch_before_property_read(monkeypatch, raw_result):
    import _com
    import _feature_tree
    import _oblique_pivot_block_model as model
    import ch_rocker_arm_tl_oblique_feed_block_spec as feed_spec

    # A bare PyIDispatch has InvokeTypes but no _oleobj_ or named property.
    raw = SimpleNamespace(InvokeTypes=lambda *args: pytest.fail("unbound dispatch access"))
    wrapper = SimpleNamespace(_oleobj_=object(), TapDrillDiameter=.089 * INCH / 1000.0)
    bindings = []

    def bind(obj, interface):
        bindings.append((obj._oleobj_, interface))
        assert obj._oleobj_ is raw
        return wrapper

    monkeypatch.setattr(_com, "_early_bound", bind)
    feature = SimpleNamespace(GetTypeName2=lambda: "HoleWzd",
                              GetDefinition=lambda: raw if raw_result else wrapper)
    monkeypatch.setattr(_feature_tree, "_feature_by_name", lambda adapter, name: feature)
    assert model._native_nut_tap_diameter(None, feed_spec) == pytest.approx(.089 * INCH)
    assert bindings == ([(raw, "IWizardHoleFeatureData2")] if raw_result else [])


def test_nut_taps_are_blind_with_their_drill_depth_gated():
    """Main's TL-32 ruling (2026-11-07): the nut taps are blind. The readback
    refuses a through spec before touching the model, and the build gates
    the drill depth and charges each blind drill's cylinder and point."""
    import _oblique_pivot_block_model as model
    import ch_rocker_arm_tl_oblique_feed_block_spec as feed_spec
    from _hole_spec import HoleSpec

    assert feed_spec.NUT_TAP_SPEC.end == "blind"
    assert feed_spec.NUT_TAP_SPEC.depth_mm == feed_spec.NUT_TAP_DRILL_DEPTH < feed_spec.LUG_WIDTH
    through = SimpleNamespace(PART_NAME="through", NUT_TAP_SPEC=HoleSpec("tapped", "#4-40"))
    with pytest.raises(RuntimeError, match="must be blind"):
        model._native_nut_tap_diameter(None, through)
    source = Path(model.__file__).read_text(encoding="utf-8")
    assert "abs(nut_taps.depth_mm - part.NUT_TAP_DRILL_DEPTH) > 0.005" in source
    assert "blind_hole_volume_mm3(nut_taps.hole_dia_mm,nut_taps.depth_mm)" in source
    assert "nut_taps.hole_dia_mm/2)**2*part.LUG_WIDTH" not in source


@pytest.mark.parametrize("feed", [False, True])
def test_x_dimension_lanes_leave_the_cutting_line_and_narrow_witness_span(feed):
    import _oblique_block_drawing as drawing

    keep = drawing.FEED_PLAN_KEEP if feed else drawing.PLAN_KEEP
    # Measured font rectangles from the retained 0c3ed359 pivot PDF, not
    # synthetic native readbacks. These protect the authored paper lanes;
    # the fresh native drawing/layout/machinist gates remain authoritative.
    cut_x = (drawing.PLAN_XY[0] * 1000) + spec.CBORE_SECTION_X
    bore_x = drawing.PLAN_XY[0] * 1000
    bore_text_x = keep["PlanBoreX"][0] * 1000
    assert bore_text_x - 4.5257 - cut_x - .175 >= 1.5
    assert bore_x - .065 - (bore_text_x + 4.5257) >= 1.5
    narrow_text_x = keep["PlanHole1X"][0] * 1000
    assert narrow_text_x - 5.8188 - (cut_x + 6.35) - .065 >= 1.5
    far_text_x = keep["PlanHole2X"][0] * 1000
    assert far_text_x - 7.1118 - cut_x - .175 >= 1.5
    tiers = [keep[name][1] * 1000 for name in ("PlanBoreX", "PlanHole1X", "PlanHole2X")]
    assert all(upper - 3.1975 - (lower + 3.1818) >= 1.5
               for lower, upper in zip(tiers, tiers[1:]))
    assert keep["BlockLength"][1] * 1000 - .065 - (tiers[-1] + 3.1818) >= 1.5


def test_b_letters_clear_upper_witnesses_border_and_lower_drill_leader():
    import _oblique_block_drawing as drawing

    # Translate the retained PDF's normal-size B rectangles with their
    # cutting-line endpoints. No font ladder or manufactured result is used.
    upper_move = drawing.FLOOR_CUT_TOP_Y * 1000 - 229.066
    upper_bottom, upper_top = 226.3757 + upper_move, 234.5777 + upper_move
    highest_witness = drawing.PLAN_KEEP["BlockLength"][1] * 1000 + 1.0
    assert upper_bottom - highest_witness - .065 >= 1.5
    assert 266.7 - upper_top >= 2.0
    lower_end = drawing.PLAN_XY[1] * 1000 - spec.BLOCK_WIDTH / 2 - drawing.FLOOR_CUT_BOTTOM_OVERRUN_MM
    lower_top = 186.4457 + lower_end - 180.934
    # Actual diagonal leader: underline elbow to the lower-left drill rim.
    x0, y0, x1, y1 = 136.2924, 159.6389, 155.7679, 190.0745
    leader_at_letter_left = y0 + (148.2252 - x0) * (y1 - y0) / (x1 - x0)
    assert leader_at_letter_left - lower_top - .065 >= 3.0
    # The lower arrow shaft/head is also below that leader, not just B.
    leader_at_arrow_left = y0 + (153.5 - x0) * (y1 - y0) / (x1 - x0)
    assert leader_at_arrow_left - (lower_end + 1.25) - .175 >= 3.0


def test_printed_callouts_read_size_process_depth_and_name_each_mate_once():
    """Machinist review of 957501d1 (TL-22 and TL-32): size first, the
    counterbore by its symbol with its depth REF against B-B's floor, mates
    by MHA number, no reason on the overalls or the seat depth, and no
    assembly instruction on the floor."""
    import _oblique_block_drawing as drawing

    printed = drawing.BLOCK_CALLOUTS
    # Every printed dimension is imported on both sheets, so the applier
    # finds it; each exists in the part's own dimension set.
    for keep in (drawing.PLAN_KEEP | drawing.SIDE_KEEP | drawing.FLOOR_KEEP,
                 drawing.FEED_PLAN_KEEP | drawing.FEED_SIDE_KEEP | drawing.FEED_FLOOR_KEEP):
        assert set(printed) <= set(keep)
    assert set(printed) <= set(spec.DRAWING_PRECISION_BY_NAME)
    assert all(set(parts) <= set(drawing.TEXT_PARTS) for parts in printed.values())
    # No process or count stands above a size.
    assert all(parts.get('above', '') == '' for parts in printed.values())
    words = '\n'.join(text for parts in printed.values() for text in parts.values())
    for retired in ('SETS ', 'FROM TOP', 'SECTION', 'HGH15CA', 'M4 X 20', 'COUNTERBORE', 'BELOW SHOULDER'):
        assert retired not in words
    assert printed['CarriageCounterbores3Dia'] == {
        'prefix': '4X <HOLE-SPOT><MOD-DIAM>', 'suffix': ' <HOLE-DEPTH> (.390)', 'above': '', 'below': ''}
    assert math.isclose((spec.BLOCK_HEIGHT - spec.CBORE_FLOOR) / INCH, .390)
    assert printed['BoreDia']['suffix'] == ' REAM <HOLE-DEPTH> (.359)'
    assert math.isclose(spec.BORE_DEPTH / INCH, .359, abs_tol=5e-5)
    assert printed['TapDrillDia'] == {'suffix': ' DRILL THRU', 'above': '', 'below': '5/16-18 UNC THRU'}
    assert printed['CarriageDrills1Dia']['prefix'] == '4X <MOD-DIAM>'
    for name in ('TopBoreDepth', 'BlockLength', 'BlockWidth'):
        assert printed[name] == {'below': ''}
    # Mates by their registry numbers; the carriage is the rail kit's member.
    screw = _config.parts('ch-rocker-arm-tl-vn-oblique-pivot-screw')['number']
    kit = _config.parts('ch-rocker-arm-tl-vn-oblique-rail-kit')['number']
    assert (drawing.PIVOT_SCREW_NUMBER, drawing.CARRIAGE_NUMBER) == (screw, kit)
    assert printed['BoreDia']['below'] == f'LOCATING FIT ON {screw} SHOULDER'
    assert printed['CarriageDrills1Dia']['below'] == f'MATCHES {kit} CARRIAGE'
    # The floor keeps RV-01's plain fact, in the words its exception quotes.
    (engagement,) = _config.parts(spec.PART_NAME)['machinist_exceptions']
    assert printed['CboreFloor'] == {'below': f'ENGAGES {spec.ENGAGEMENT_TEXT} MIN ({spec.ENGAGEMENT_DIAMETERS})'}
    assert printed['CboreFloor']['below'] in engagement['where']


def test_sheet_callout_overrides_replace_only_the_parts_they_name():
    import _oblique_block_drawing as drawing

    merged = drawing.block_callouts({'BoreDia': {'below': 'X'}, 'NutCentreY': {'above': ''}})
    assert merged['BoreDia'] == {**drawing.BLOCK_CALLOUTS['BoreDia'], 'below': 'X'}
    assert merged['NutCentreY'] == {'above': ''}
    assert drawing.block_callouts() == drawing.BLOCK_CALLOUTS
    assert drawing.BLOCK_CALLOUTS['BoreDia']['below'] != 'X'
    with pytest.raises(ValueError):
        drawing.block_callouts({'BoreDia': {'callout': ''}})


def test_sections_print_no_sheet_scale_and_b_b_joins_its_pieces():
    """SCALE 1 : 1 printed under both sections of the 1:1 sheet, and B-B's
    cut face alone left three hatched pieces (machinist review of 957501d1):
    each section is cut on the pinned sheet and its caption refuses a scale
    field; B-B prints the material beyond the cut, hidden lines removed."""
    import _oblique_block_drawing as drawing

    source = Path(drawing.__file__).read_text(encoding='utf-8')
    body = source[source.index('async def draw_block'):]
    pin = '    _pin_sheet_scale(adapter, SHEET_SCALE)\n'
    assert body.count('create_section_view(') == 2
    assert pin + '    side = create_section_view(' in body
    assert pin + '    floor = create_section_view(' in body
    assert "_section_caption(side, 'A')" in body
    beyond = source[source.index('def _section_with_material_beyond'):source.index('def _pin_sheet_scale')]
    assert 'SetDisplayOnlySurfaceCut(False)' in beyond and 'set_hidden_lines_removed(adapter, view)' in beyond
    assert 'SetDisplayOnlySurfaceCut(True)' not in source
    assert "'<VLSCALEV>' in linked" in source
    # B-B looks -X from the -X column: TL-32's lug stands behind its plane.
    import ch_rocker_arm_tl_oblique_feed_block_spec as feed
    assert spec.CBORE_SECTION_X < feed.LUG_X0


_PIVOT_GENERATED_TEXT = (
    'REAM <MOD-DIAM>.3750 +.0015/+.0010 <HOLE-DEPTH>.359\n'
    '  LOCATING FIT, TL-VN-77 SHOULDER\n'
    'DRILL <MOD-DIAM>.257 THRU\n'
    '5/16-18 UNC TAP THRU BELOW SEAT'
)


def _pivot_text_contract():
    return SimpleNamespace(
        UNIT=spec.UNIT, DRAWING_VALUES=dict(spec.DRAWING_VALUES),
        DRAWING_PRECISION_BY_NAME=dict(spec.DRAWING_PRECISION_BY_NAME),
        BORE_BAND=spec.BORE_BAND, BORE_PLACES=spec.BORE_PLACES, PIVOT_TAP=spec.PIVOT_TAP,
    )


def test_compact_pivot_text_is_four_spec_generated_rows_at_normal_height():
    import _oblique_block_drawing as drawing

    assert drawing._pivot_stack_text(spec) == _PIVOT_GENERATED_TEXT
    assert drawing.PIVOT_NOTE_HEIGHT == .0035
    assert len(drawing._pivot_stack_text(spec).splitlines()) == 4
    assert drawing._pivot_stack_semantics(_PIVOT_GENERATED_TEXT) == drawing._pivot_stack_semantics(
        _PIVOT_GENERATED_TEXT.replace('<MOD-DIAM>', 'Ø').replace('<HOLE-DEPTH>', '↧').replace('\n', '\r\n')
    )


@pytest.mark.parametrize('change,printed', (
    ('BoreDia', '<MOD-DIAM>.5000'), ('TopBoreDepth', '<HOLE-DEPTH>.400'),
    ('TapDrillDia', '<MOD-DIAM>.250'), ('band', '+.0020/+.0010'),
    ('precision', '<MOD-DIAM>.375'), ('thread', '3/8-16 UNC TAP'),
))
def test_generated_pivot_text_tracks_spec_values_bands_places_and_thread(change, printed):
    import _oblique_block_drawing as drawing
    from _title_block_units import MM_PER_INCH

    contract = _pivot_text_contract()
    if change in ('BoreDia', 'TopBoreDepth', 'TapDrillDia'):
        contract.DRAWING_VALUES[change] = {'BoreDia': .5, 'TopBoreDepth': .4, 'TapDrillDia': .25}[change] * MM_PER_INCH
    elif change == 'band':
        contract.BORE_BAND = (.002 * MM_PER_INCH, .001 * MM_PER_INCH)
    elif change == 'precision':
        contract.DRAWING_PRECISION_BY_NAME['BoreDia'] = 3
    else:
        contract.PIVOT_TAP = '3/8-16'
    text = drawing._pivot_stack_text(contract)
    assert printed in text and text != _PIVOT_GENERATED_TEXT


def test_generated_pivot_text_refuses_wrong_units_and_inverted_band():
    import _oblique_block_drawing as drawing

    contract = _pivot_text_contract()
    contract.UNIT = 'mm'
    with pytest.raises(RuntimeError, match='inch'):
        drawing._pivot_stack_text(contract)
    contract.UNIT = 'in'
    contract.BORE_BAND = tuple(reversed(spec.BORE_BAND))
    with pytest.raises(ValueError, match='inverted'):
        drawing._pivot_stack_text(contract)


def test_compact_pivot_estimate_retains_margin_in_measured_lower_right_lane():
    import _oblique_block_drawing as drawing

    text = drawing._pivot_stack_text(spec)
    box = drawing._pivot_stack_estimate(text)
    assert box.mm() == pytest.approx((189.0, 103.7, 306.5, 126.0))
    assert drawing.PIVOT_STACK_LANE == (.185, .100, .312, .130)
    left, bottom, right, top = drawing.PIVOT_STACK_LANE
    assert min(box.xmin - left, box.ymin - bottom, right - box.xmax, top - box.ymax) == pytest.approx(.0037)
    # The estimator uses one cap-height per glyph, 1.6-height row pitch,
    # plus 1 mm all-round padding. Exported PDF glyphs remain the real gate.
    with pytest.raises(RuntimeError, match='lane margin'):
        drawing._pivot_stack_estimate(text.replace('SHOULDER', 'SHOULDER' + 'W' * 20))
    with pytest.raises(RuntimeError, match='four short lines'):
        drawing._pivot_stack_estimate(text + '\nEXTRA ROW')


@pytest.mark.parametrize('start_y_mm', (103.7, 109.6, 126.0))
def test_lower_right_pivot_route_clears_retained_389_annotation_ink(start_y_mm):
    import _oblique_block_drawing as drawing
    from _drawing_layout_check import LeaderSegment, _proper_crossing

    # Native389 / 0e989113 pivot layout report: actual sheet-mm segments.
    # The retired native192 leader is the positive crossing control.
    cut_b = LeaderSegment('B-B', 'section', .157, .168934, .157, .259)
    retired = LeaderSegment('native192', 'note', .1042, .2096, .1652, .205)
    assert _proper_crossing(retired, cut_b, tol=1e-9) == pytest.approx((.157, .2056183607))
    offset = spec.BORE_DIA / (2000 * math.sqrt(2))
    tip = (drawing.PLAN_XY[0] + offset, drawing.PLAN_XY[1] - offset)
    start = (drawing.PIVOT_STACK_XY[0], start_y_mm / 1000)
    shaft = LeaderSegment('candidate', 'note', *start, *tip)
    length = math.dist(start, tip)
    direction = tuple((a - b) / length for a, b in zip(start, tip))
    triangle = drawing.arrowhead_segments(
        (*tip, 0.0, *direction, 0.0, .003556, .000762, 0.0, 0.0, 0.0, 1.0))
    route = [shaft, *(LeaderSegment('arrow', 'note', edge.x0, edge.y0, edge.x1, edge.y1)
                      for edge in triangle)]
    recorded_mm = (
        ('A-A', 145.172, 205, 194.828, 205),
        ('PlanBoreX witness', 170, 213.2625, 170, 229.2219),
        ('BlockLength left witness', 149.172, 185.934, 149.172, 254.5),
        ('BlockLength right witness', 190.828, 185.934, 190.828, 254.5),
        ('BlockWidth/SideY lower witness', 191.828, 184.934, 260.5, 184.934),
        ('BlockWidth upper witness', 191.828, 225.066, 260.5, 225.066),
        ('BlockWidth lower dimension', 259.5, 184.934, 259.5, 194.6656),
        ('BlockWidth upper dimension', 259.5, 225.066, 259.5, 211.3344),
        ('BlockSideY dimension', 231, 184.934, 231, 217.2219),
        ('Y station witness', 178.2625, 205, 232, 205),
        ('CarriageDrills3Y witness', 188.786, 192, 223, 192),
        ('CarriageDrills3Y lower dimension', 222, 192, 222, 195.7219),
        ('CarriageDrills3Y upper dimension', 222, 205, 222, 201.2781),
        ('CarriageDrills4Y witness', 188.786, 218, 223, 218),
        ('drill leader', 155.7679, 190.0745, 136.2924, 159.6389),
        ('drill diameter line', 158.2321, 193.9255, 155.7679, 190.0745),
        ('drill shoulder', 136.2924, 159.6389, 35.2951, 159.6389),
        ('counterbore leader', 184.9007, 188.5522, 210.7628, 141.6389),
        ('counterbore diameter line', 181.0993, 195.4478, 184.9007, 188.5522),
        ('counterbore shoulder', 210.7628, 141.6389, 277.6497, 141.6389),
        ('TopBoreDepth top witness', 173.7625, 92.192, 119, 92.192),
        ('TopBoreDepth floor witness', 173.7625, 83.0734, 119, 83.0734),
        ('TopBoreDepth dimension', 120, 83.0734, 120, 92.192),
        ('TopBoreDepth leader', 120, 87.6327, 113.8701, 98.4438),
        ('TopBoreDepth shoulder', 113.8701, 98.4438, 42.1299, 98.4438),
        ('BlockHeight right witness', 312.192, 183.934, 312.192, 172.2219),
        ('BlockHeight left witness', 287.808, 183.934, 287.808, 172.2219),
        ('BlockHeight dimension', 312.192, 173.2219, 287.808, 173.2219),
        ('CboreFloor right witness', 347.192, 138.786, 347.192, 148.6656),
        ('CboreFloor left witness', 332.714, 138.786, 332.714, 148.6656),
        ('CboreFloor dimension/shoulder', 332.714, 147.6656, 410.0295, 147.6656),
        ('centre lower tail', 170, 200, 170, 197.7375),
        ('centre right tail', 175, 205, 177.2625, 205),
        ('lower-right centre left tail', 180.5, 192, 178.214, 192),
        ('lower-right centre vertical', 183, 187.214, 183, 196.786),
        ('lower-left centre right tail', 159.5, 192, 161.786, 192),
    )
    recorded = [cut_b, *(LeaderSegment(label, 'annotation', *(v / 1000 for v in coordinates))
                         for label, *coordinates in recorded_mm)]
    for segment in route:
        for obstacle in recorded:
            assert _proper_crossing(segment, obstacle, tol=1e-9) is None, obstacle.label
        # Centre marks need real air, not merely a non-crossing predicate.
        for obstacle in recorded[-5:]:
            a, b = (segment.x0, segment.y0), (segment.x1, segment.y1)
            c, d = (obstacle.x0, obstacle.y0), (obstacle.x1, obstacle.y1)
            assert min(drawing._segment_distance(a, c, d), drawing._segment_distance(b, c, d),
                       drawing._segment_distance(c, a, b), drawing._segment_distance(d, a, b)) > .001
        for x, y in spec.BOLT_POINTS:
            centre = (drawing.PLAN_XY[0] + x / 1000, drawing.PLAN_XY[1] + y / 1000)
            assert drawing._segment_distance(centre, (segment.x0, segment.y0),
                                             (segment.x1, segment.y1)) >= spec.CBORE_DIA / 2000 + .001
    # All remaining plan X-size/ordinate lines are ABOVE the entire route.
    assert max(segment.y0 for segment in route) < .2132625
    assert max(segment.y1 for segment in route) < .2132625
    # Crossing the part's bottom outline is allowed: it is not the
    # BlockWidth/BlockSideY extension, which starts at x191.828.
    outline = LeaderSegment('part outline', 'geometry', .149172, .184934, .190828, .184934)
    crossing = _proper_crossing(shaft, outline, tol=1e-9)
    assert crossing is not None and crossing[0] < .191828
    box = drawing._pivot_stack_estimate(drawing._pivot_stack_text(spec))
    assert box.ymin - .097780 == pytest.approx(.00592)  # A-A view outline
    assert .317220 - box.xmax == pytest.approx(.01072)  # B-B view outline
    assert .1425728 - box.ymax == pytest.approx(.0165728)  # existing counterbore caption


def _stacked_pivot_fixture(monkeypatch):
    import _oblique_block_drawing as drawing
    from _drawing_edges import ViewEdge, ViewEdges
    from _fit_deviations import deviations

    plan, outer, inner = object(), object(), object()
    origin = drawing.PLAN_XY
    rim_offset = spec.BORE_DIA / (2000 * math.sqrt(2))
    landing = (origin[0] + rim_offset, origin[1] - rim_offset)
    start = (drawing.PIVOT_STACK_XY[0], drawing.PIVOT_STACK_XY[1] - .0154)
    length = math.dist(start, landing)
    direction = tuple((a - b) / length for a, b in zip(start, landing))
    source_rows, displays = {}, {}
    for name, feature in (
        ('BoreDia', 'TopBoreProfile'), ('TopBoreDepth', 'TopBore'), ('TapDrillDia', 'PivotTapProfile'),
    ):
        lower, upper = deviations(spec.BORE_BAND) if name == 'BoreDia' else (0.0, 0.0)
        tolerance = SimpleNamespace(Type=2 if name == 'BoreDia' else 0, lower=lower / 1000, upper=upper / 1000)
        tolerance.GetMinValue = lambda tolerance=tolerance: tolerance.lower
        tolerance.GetMaxValue = lambda tolerance=tolerance: tolerance.upper
        dimension = SimpleNamespace(FullName=f'{name}@{feature}@block.Part',
                                    SystemValue=spec.DRAWING_VALUES[name] / 1000, Tolerance=tolerance)
        above, below = spec.CALLOUTS_ABOVE.get(name, ''), spec.CALLOUTS_BELOW.get(name, '')
        row = source_rows[name] = SimpleNamespace(
            dimension=dimension, texts=('', '', above, below, '', '', above, below),
            places=spec.DRAWING_PRECISION_BY_NAME[name], tolerance_places=-3,
        )
        xy = drawing.SEAT_DEPTH_TEXT_XY if name == 'TopBoreDepth' else drawing.PLAN_KEEP[name]
        annotation = SimpleNamespace(Visible=1, OwnerType=0, position=(*xy, 0.0), dangling=False)
        annotation.GetPosition = lambda annotation=annotation: annotation.position
        annotation.IsDangling = lambda annotation=annotation: annotation.dangling
        row.annotation = annotation
        displays[name] = SimpleNamespace(
            GetDimension2=lambda index, row=row: row.dimension,
            GetText=lambda which, row=row: row.texts[which - 1],
            GetPrimaryPrecision2=lambda row=row: row.places,
            GetPrimaryTolPrecision2=lambda row=row: row.tolerance_places,
            GetAnnotation=lambda annotation=annotation: annotation,
        )
    # Synthetic COM geometry, not a claim about the next native sheet.
    note = SimpleNamespace(text=_PIVOT_GENERATED_TEXT)
    native = SimpleNamespace(
        Visible=1, OwnerType=0, Owner=plan, position=(*drawing.PIVOT_STACK_XY, 0.0),
        leaders=1, attached=outer, dangling=False,
        points=(*start, 0.0, *landing, 0.0),
        arrow=(*landing, 0.0, *direction, 0.0, .003556, .000762, 0.0, 0.0, 0.0, 1.0),
        arrow_count=1, font=SimpleNamespace(CharHeight=.005),
    )
    native.GetPosition = lambda: native.position
    native.GetLeaderCount = lambda: native.leaders
    native.GetLeaderPointsAtIndex = lambda index: native.points
    native.GetAttachedEntities3 = lambda: [native.attached]
    native.GetAttachedEntityCount3 = lambda: 1
    native.GetAttachedEntityTypes = lambda: [1]
    native.IsDangling = lambda: native.dangling
    native.GetTextFormat = lambda index: native.font
    native.SetTextFormat = lambda index, use_doc, value: True
    native.GetDisplayData = lambda: SimpleNamespace(
        GetArrowHeadCount=lambda: native.arrow_count, GetArrowHeadAtIndex2=lambda index: native.arrow,
    )
    note.GetAnnotation = lambda: native
    note.GetText = lambda: note.text
    inserted = []

    def add_note(adapter, view, **kwargs):
        assert view is plan and kwargs['entity'] is outer
        assert kwargs['leader_attach_xy'] == pytest.approx(landing)
        assert kwargs['note_xy'] == drawing.PIVOT_STACK_XY
        assert kwargs['text'] == _PIVOT_GENERATED_TEXT
        inserted.append(kwargs)
        return note

    circles = [
        ViewEdge(edge=inner, line=None, vertices=None,
                 circle=(spec.BORE_X, spec.BORE_Y, spec.BLOCK_HEIGHT - spec.BORE_DEPTH,
                         0.0, 0.0, 1.0, spec.PIVOT_TAP_DRILL / 2)),
        ViewEdge(edge=outer, line=None, vertices=None,
                 circle=(spec.BORE_X, spec.BORE_Y, spec.BLOCK_HEIGHT, 0.0, 0.0, 1.0, spec.BORE_DIA / 2)),
    ]
    monkeypatch.setattr(drawing, '_early_bound', lambda obj, interface: obj)
    monkeypatch.setattr(drawing, '_displays',
                        lambda adapter, annotations, names: {name: displays[name] for name in names})
    monkeypatch.setattr(drawing, 'scan_view_edges',
                        lambda *args, **kwargs: ViewEdges('fixture', tuple(circles)))
    monkeypatch.setattr(drawing, '_project',
                        lambda adapter, view, point, label: (origin[0] + point[0] / 1000,
                                                           origin[1] + point[1] / 1000))
    monkeypatch.setattr(drawing, 'add_attached_note', add_note)
    rebuilds = []

    def rebuild(adapter, *, label):
        rebuilds.append(label)
        wanted = 1 if label == 'pivot generated callout note height' else 3
        assert source_rows['BoreDia'].annotation.Visible == wanted
        assert source_rows['TapDrillDia'].annotation.Visible == wanted
        assert source_rows['TopBoreDepth'].annotation.Visible == 1

    monkeypatch.setattr(drawing, 'rebuild_drawing', rebuild)
    reports = []
    monkeypatch.setattr(drawing._telemetry, 'info', lambda message, **kwargs: reports.append(kwargs))
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    return SimpleNamespace(drawing=drawing, adapter=adapter, plan=plan, rows=source_rows, note=note,
                           native=native, landing=landing, origin=origin, inner=inner, circles=circles,
                           inserted=inserted, rebuilds=rebuilds, reports=reports)


@pytest.mark.parametrize('fault', (
    None, 'unicode_crlf', 'duplicate_captions', 'drill_value', 'depth_value',
    'missing_band', 'rounded_band', 'negative_band', 'printed_places', 'missing_diameter', 'note_height',
    'source_identity', 'source_feature', 'source_value', 'source_precision', 'source_band', 'source_tokens',
    'source_position', 'source_shown', 'depth_hidden', 'wrong_owner', 'hidden_note', 'note_position',
    'two_leaders', 'wrong_attachment', 'inner_tip', 'centre_crossing',
    'upper_left_crossing', 'upper_right_crossing', 'lower_left_crossing', 'lower_right_crossing',
    'arrow_inside', 'two_arrows', 'malformed_arrow',
))
def test_generated_pivot_callout_preserves_native_sources_and_outside_route(monkeypatch, fault):
    case = _stacked_pivot_fixture(monkeypatch)
    proof = case.drawing._stack_pivot_callout(case.adapter, case.plan, [], spec)
    assert len(case.inserted) == 1 and len(case.rebuilds) == 2
    assert case.native.font.CharHeight == case.drawing.PIVOT_NOTE_HEIGHT
    assert case.reports[0]['estimated_text_bounds_mm'] == pytest.approx((189.0, 103.7, 306.5, 126.0))
    tap = case.rows['TapDrillDia']
    if fault == 'unicode_crlf':
        case.note.text = case.note.text.replace('<MOD-DIAM>', 'Ø').replace('<HOLE-DEPTH>', '↧').replace('\n', '\r\n')
    elif fault == 'duplicate_captions':
        case.note.text = case.note.text.replace('REAM', 'REAM REAM')
    elif fault == 'drill_value':
        case.note.text = case.note.text.replace('.257', '.258')
    elif fault == 'depth_value':
        case.note.text = case.note.text.replace('.359', '.360')
    elif fault == 'missing_band':
        case.note.text = case.note.text.replace('+.0015/+.0010', '')
    elif fault == 'rounded_band':
        case.note.text = case.note.text.replace('.0015', '.002')
    elif fault == 'negative_band':
        case.note.text = case.note.text.replace('+.0010', '-.0010')
    elif fault == 'printed_places':
        case.note.text = case.note.text.replace('.3750', '.375')
    elif fault == 'missing_diameter':
        case.note.text = case.note.text.replace('<MOD-DIAM>', '', 1)
    elif fault == 'note_height':
        case.native.font.CharHeight = .004
    elif fault == 'source_identity':
        tap.dimension = SimpleNamespace(**vars(tap.dimension))
    elif fault == 'source_feature':
        tap.dimension.FullName = 'TapDrillDia@TopBoreProfile@block.Part'
    elif fault == 'source_value':
        tap.dimension.SystemValue += .001
    elif fault == 'source_precision':
        tap.places = 2
    elif fault == 'source_band':
        case.rows['BoreDia'].dimension.Tolerance.upper += .00001
    elif fault == 'source_tokens':
        tap.texts = (*tap.texts[:4], 'CHANGED', *tap.texts[5:])
    elif fault == 'source_position':
        tap.annotation.position = (.050, .050, 0.0)
    elif fault == 'source_shown':
        tap.annotation.Visible = 1
    elif fault == 'depth_hidden':
        case.rows['TopBoreDepth'].annotation.Visible = 3
    elif fault == 'wrong_owner':
        case.native.Owner = object()
    elif fault == 'hidden_note':
        case.native.Visible = 3
    elif fault == 'note_position':
        case.native.position = (case.native.position[0] + .001, *case.native.position[1:])
    elif fault == 'two_leaders':
        case.native.leaders = 2
    elif fault == 'wrong_attachment':
        case.native.attached = case.inner
    elif fault == 'inner_tip':
        offset = spec.PIVOT_TAP_DRILL / (2000 * math.sqrt(2))
        inner = (case.origin[0] + offset, case.origin[1] - offset)
        case.native.points = (*case.native.points[:3], *inner, 0.0)
        case.native.arrow = (*inner, *case.native.arrow[2:])
    elif fault == 'centre_crossing':
        case.native.points = (*case.origin, 0.0, *case.landing, 0.0)
    elif fault in ('upper_left_crossing', 'upper_right_crossing', 'lower_left_crossing', 'lower_right_crossing'):
        sx = -1 if 'left' in fault else 1
        sy = 1 if 'upper' in fault else -1
        obstacle = (case.origin[0] + sx * spec.BOLT_X / 1000, case.origin[1] + sy * spec.BOLT_Y / 1000)
        case.native.points = (*obstacle, 0.0, *case.landing, 0.0)
    elif fault == 'arrow_inside':
        case.native.arrow = (*case.native.arrow[:3], -case.native.arrow[3], -case.native.arrow[4],
                             *case.native.arrow[5:])
    elif fault == 'two_arrows':
        case.native.arrow_count = 2
    elif fault == 'malformed_arrow':
        case.native.arrow = case.native.arrow[:6]
    if fault in (None, 'unicode_crlf'):
        proof()
        assert len(case.rebuilds) == 2 and len(case.reports) == 2
    else:
        with pytest.raises(RuntimeError):
            proof()


@pytest.mark.parametrize('fault', ('feature', 'value', 'precision', 'band'))
def test_generated_note_refuses_native_sources_that_disagree_with_spec_before_insertion(monkeypatch, fault):
    case = _stacked_pivot_fixture(monkeypatch)
    if fault == 'feature':
        case.rows['TapDrillDia'].dimension.FullName = 'TapDrillDia@WrongFeature@block.Part'
    elif fault == 'value':
        case.rows['TapDrillDia'].dimension.SystemValue += .001
    elif fault == 'precision':
        case.rows['TapDrillDia'].places = 2
    else:
        case.rows['BoreDia'].dimension.Tolerance.upper += .00001
    with pytest.raises(RuntimeError):
        case.drawing._stack_pivot_callout(case.adapter, case.plan, [], spec)
    assert not case.inserted


def test_generated_note_must_agree_with_spec_before_hiding_source_dimensions(monkeypatch):
    case = _stacked_pivot_fixture(monkeypatch)
    case.note.text = 'WRONG TEXT'
    with pytest.raises(RuntimeError, match='disagrees with spec text'):
        case.drawing._stack_pivot_callout(case.adapter, case.plan, [], spec)
    assert all(row.annotation.Visible == 1 for row in case.rows.values())
    assert case.rebuilds == ['pivot generated callout note height']


@pytest.mark.parametrize('feed', (False, True))
def test_stacked_callout_keeps_imported_precision_gate_and_is_pivot_only(feed):
    source = Path(__file__).with_name('_oblique_block_drawing.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == 'draw_block')
    initial = next(node for node in build.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'settled_checks'
                           for target in node.targets))
    conditional = next(node for node in build.body if isinstance(node, ast.If)
                       and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                               and child.func.id == '_stack_pivot_callout' for child in ast.walk(node)))
    precision = next(node for node in build.body if isinstance(node, ast.Expr)
                     and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                     and node.value.func.id == 'assert_imported_precision')
    assert build.body.index(precision) < build.body.index(conditional)
    assert ast.unparse(precision.value) == 'assert_imported_precision(adapter, annotations, precision)'
    calls, proof = [], object()

    def stack(*args):
        calls.append(args)
        return proof

    env = dict(is_feed=feed, adapter=object(), plan=object(), annotations=[],
               contract=object(), _stack_pivot_callout=stack)
    exec(compile(ast.Module(body=[initial, conditional], type_ignores=[]), '<pivot-routing>', 'exec'), env)
    assert len(calls) == (0 if feed else 1)
    assert env['settled_checks'] == (() if feed else (proof,))
    finalizer = next(node for node in ast.walk(build) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'finalize_drawing')
    assert ast.unparse(next(keyword.value for keyword in finalizer.keywords
                           if keyword.arg == 'settled_checks')) == 'settled_checks'
    pdf_guard = next(node for node in build.body if isinstance(node, ast.If)
                     and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                             and child.func.id == '_assert_pivot_pdf_text' for child in ast.walk(node)))
    export = next(node for node in build.body if isinstance(node, ast.Assign)
                  and isinstance(node.value, ast.Await)
                  and node.value.value is finalizer)
    assert build.body.index(export) < build.body.index(pdf_guard)
    pdf_calls = []
    outputs = SimpleNamespace(pdf=Path('pivot.pdf'))
    report_path = Path('pivot-layout.json')
    env.update(outputs=outputs, spec=SimpleNamespace(artifact_stem='pivot'),
               layout_report_path=lambda stem: report_path,
               _assert_pivot_pdf_text=lambda *args: pdf_calls.append(args))
    exec(compile(ast.Module(body=[pdf_guard], type_ignores=[]), '<pivot-pdf-routing>', 'exec'), env)
    assert pdf_calls == ([] if feed else [(outputs.pdf, report_path, env['contract'])])


@pytest.mark.parametrize('fault', (
    None, 'split_symbols', 'unordered_display', 'missing_page', 'extra_page',
    'wrong_report', 'missing_row', 'missing_display', 'wrong_value', 'text_outside',
    'other_text', 'model_edge', 'duplicate_note',
))
def test_pivot_exported_pdf_rows_gate_real_text_not_leader_extent(monkeypatch, fault):
    import json
    from dataclasses import replace
    import _oblique_block_drawing as drawing
    from _layout_audit import LayoutAuditMode, audit_report, ink_key
    from _pdf_ink import PageInk, Span, Stroke, page_ink

    rows = drawing._pivot_stack_text(spec).splitlines()
    offset = spec.BORE_DIA / (2000 * math.sqrt(2))
    landing = (drawing.PLAN_XY[0] + offset, drawing.PLAN_XY[1] - offset)
    texts = [{'t': row, 'pos': [.190, .125 - index * .0056, 0.0],
              'h': .0035, 'ref': 0}
             for index, row in enumerate(rows)]
    spans = [
        Span(ink_key(row), .190, .1215 - index * .0056,
             .290, .125 - index * .0056, ())
        for index, row in enumerate(rows)
    ]
    # Historical e4a597af whole-note extent is deliberately retained: it must
    # never replace the relocated exported glyphs/independent leader proof.
    note = {
        'type': 6, 'name': 'PivotStack', 'visible': 1, 'owner_type': 0,
        'note': {'text': '\n'.join(rows), 'balloon': False, 'extent': [
            .0247960066889632, .20546646153846154, -1.4542750301607925e-15,
            .1649071638795986, .22500577257525084, -1.5907173098783955e-15,
        ]},
        'display': {'texts': texts},
        'leaders': [[.190, .1096, 0.0, *landing, 0.0]],
    }
    annotations = [note]
    strokes = [Stroke(.190, .1096, *landing, .00013, (0, 0, 0), False, False, True)]
    if fault == 'split_symbols':
        first = spans.pop(0)
        spans[:0] = [
            replace(first, text='REAM', xmax=.199),
            replace(first, text='.3750+.0015/+.0010', xmin=.202, xmax=.248),
            replace(first, text='.359', xmin=.251, xmax=.263),
        ]
    elif fault == 'unordered_display':
        texts.reverse()
    elif fault == 'missing_row':
        spans.pop()
    elif fault == 'missing_display':
        texts.pop()
    elif fault == 'wrong_value':
        spans[0] = replace(spans[0], text=spans[0].text.replace('.3750', '.3751'))
    elif fault == 'text_outside':
        spans[0] = replace(spans[0], xmax=.320)
    elif fault == 'other_text':
        spans.append(replace(spans[0], text='FOREIGN TEXT'))
        annotations.append({
            'type': 6, 'name': 'Other', 'visible': 1,
            'note': {'text': 'FOREIGN TEXT', 'balloon': False},
            'display': {'texts': [{**texts[0], 't': 'FOREIGN TEXT'}]},
        })
    elif fault == 'model_edge':
        strokes.append(Stroke(.185, .123, .295, .123, .00035, (0, 0, 0), False, False, True))
    elif fault == 'duplicate_note':
        annotations.append({**note, 'name': 'DuplicatePivot'})
    page = PageInk(.4318, .2794, (), tuple(spans), tuple(strokes))
    dump = {
        'schema': 1, 'stem': 'pivot', 'sheet': 'Sheet1', 'page': 0,
        'width': page.width, 'height': page.height,
        'zone': dict.fromkeys(('left', 'right', 'bottom', 'top'), .0127),
        'title_block': [.216, 0.0, page.width, .066],
        'views': [{'name': 'Plan', 'outline': [.015, .070, .318, .240],
                   'annotations': annotations}],
        'sheet_annotations': [], 'tables': [], 'read_errors': {},
        'ink': page_ink(page),
    }
    report, _ = audit_report('pivot', LayoutAuditMode.REPORT, [dump])
    if fault == 'wrong_report':
        report['stem'] = 'other'
    report_path = SimpleNamespace(read_text=lambda **kwargs: json.dumps(report))
    pages = [] if fault == 'missing_page' else [page, page] if fault == 'extra_page' else [page]
    pdf = Path('pivot.pdf')

    def read_pdf(path):
        assert path == pdf
        return pages

    monkeypatch.setattr(drawing, 'read_pdf_ink', read_pdf)
    if fault in (None, 'split_symbols', 'unordered_display'):
        drawing._assert_pivot_pdf_text(pdf, report_path, spec)
    else:
        with pytest.raises(RuntimeError):
            drawing._assert_pivot_pdf_text(pdf, report_path, spec)
