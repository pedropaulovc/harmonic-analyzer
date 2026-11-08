"""Shared sheet builder for the oblique jig's pivot and feed blocks (TL-22, TL-32).

Each block's own ``draw_<stem>.py`` reads its own registry row and calls
:func:`draw_block`, so neither drawing's recipe folds the other's row.

Manufacturing sheets for the plain shoulder-screw pivot blocks.

Both sheets print decimal inch (each part's ``drawing_unit``). All sizes
import native model dimensions; no bearing/cartridge sheets survive.
Plan X locations run from the -X (left) edge through the hidden
``PlanDatumReference`` sketch; Y from the shoulder seat's axis. Section B-B
shows the floor from the carriage seat, not a competing counterbore-depth
tolerance chain. TL-32's nut face is VIEW D on its own 2:1 sheet, its arrow on
the plan. The layout notes below give sheet millimetres.
"""
from __future__ import annotations
import math
from typing import Any
from _check import check
from _com import _early_bound
from _drawing_common import (DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, rebuild_drawing,
                             remove_notes_matching)
from _drawing_dimensions import assert_imported_precision, dimension_name, offset_dimension_text
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _paths import CAD_ROOT
from _drawing_metric_vendor import print_imported_metric_dimensions
from _part_properties import part_drawing_unit
from _layout_audit import arrowhead_segments
import _telemetry
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view
import ch_rocker_arm_tl_oblique_pivot_block_spec as part
from ch_rocker_arm_tl_oblique_callouts import set_callout_lengths_to_three_places

SHEET_SCALE = (1.0,1.0)
# SolidWorks' own descriptive note for TL-32's Hole Wizard nut taps; the native
# tap callout already states the thread.
TAPPED_HOLE_NOTE = '#4-40 Tapped Hole'
# Sheet metres. B-B still cuts the -X M4 column, avoiding the integral +X
# lug. Its upper arrow stands ABOVE all X-dimension tiers; its lower arrow
# stands below the clearance-hole leader. Do not shrink the existing fonts.
# The retained 0c3ed359 pivot PDF put B at x148.225..151.669 mm, directly on
# the x149.172 datum witnesses. At y259 its bottom is y256.310, above the
# highest witness (y254.500), and its top y264.512 clears the y266.7 border.
# Keep dimension text right of the x157 cutting line, not on that line.
# X ordinates remain native baseline dimensions from the finished -X edge;
# Y starts at the pivot axis. Native layout and machinist-review own fit.
PLAN_XY = (.170,.205)
PLAN_KEEP = {
    'BlockLength':(.170,.2535),'PlanHole2X':(.1665,.248),'PlanHole1X':(.171,.2395),
    'PlanBoreX':(.1635,.231),
    'BlockWidth':(.2595,.203),'BlockSideY':(.231,.220),
    'CarriageDrills3Y':(.222,.1985),'CarriageDrills4Y':(.222,.2115),
    'BoreDia':(.078,.196),'CarriageDrills1Dia':(.085,.168),'CarriageCounterbores3Dia':(.245,.150),
    # The tap's Ø on its circle at the seat's floor, from high on the upper
    # left: the leader enters the plan's left edge under the length stack's
    # extension lines and passes over the A-A arrow's letter. In A-A its
    # extension lines rose from the top face through the empty Ø.3750 seat
    # (machinist review, delta 20261104T040714425Z); on the bottom face with
    # them hidden, its arrows ran along the edge (#2119's final
    # 20261103T190306489Z).
    'TapDrillDia':(.071,.2455),
}
# TL-22 and TL-32 share this top tier (machinist review of c40296ac, TL-32
# sheet 1; TL-22's PDF placed it identically). With the value over its
# reason, the two rows were centred at (240, 258.5) mm, right of the 1.64 at
# its own height. Their underline sat on the y253.5 dimension line, so the
# leader ran from mid-span along the line, through its right arrowhead and
# across the right extension line. The 13 mm under the border cannot hold two
# rows plus a clear rise, so the reason prints on the value's row
# ("1.64 SETS COUNTERBORE END WALL": about 82 mm at that PDF's 2.74 mm a
# character, in a 6.38 mm row). The row is centred so it spans x 162..244
# and y 257.8..264.2: 5 mm right of the x157 cutting line, 2.5 mm under the
# border, and its underline about 5 mm over the dimension line. The leader
# then rises steeply above the span, clear of both extension lines and the
# arrowheads.
BLOCK_LENGTH_TEXT_XY = (.203,.261)
ROW_DIMENSIONS = ('CarriageDrills3Y','CarriageDrills4Y')
# A-A remains below the plan, top face up. Its depth text stays outboard
# left of the dimension line; the baseline and actual section span come
# from the model, not the retired asymmetric block's sheet coordinates.
SIDE_XY = (.170,.080)
SIDE_KEEP = {'TopBoreDepth':(.120,.088)}
# TL-22 prints the block height (the Block extrusion's depth) on a standard
# Right view level with the plan: neither its B-B nor its A-A ever imported a
# full-height dimension (farm rounds 1 to 9), though TL-32's B-B does. Top
# face toward the plan (x 283), bottom at x 307, between the plan's 1.58
# callout (ends ~x 277) and the pictorial (from ~x 311); the height prints
# under it, clear of the 4X COUNTERBORE callout at y 150.
RIGHT_XY = (.300,PLAN_XY[1])  # 5 mm clear of the plan's SETS COUNTERBORE row
RIGHT_KEEP = {'BlockHeight':(.300,.176)}
SEAT_DEPTH_TEXT_XY = (.078,.104)
# B-B: Y up, its +Y face (Y 20) at y 142.5, Z across with the top face toward
# the plan (x 322.85) and the carriage seat at x 347.15; the caption ends
# above the title block (at y 122.5 TL-22's SCALE row met it, farm run
# 20261027T181901497Z). Under the view, the 24.30 met the SECTION B-B
# caption on TL-32 (farm run 20261027T171931429Z). Above it, the floor's
# value and its two-row note stand right of x 353, clear of the block
# height's extension lines (x 322.85, 347.15); the dimension line underlines
# the last row, ~8.3 mm under the value's anchor, so the anchor stands
# 13.5 mm over the +Y face (at 8.5 mm the line ran along the face, farm run
# 20261027T181901497Z).
FLOOR_XY = (.335,.1225)
FLOOR_KEEP = {'CboreFloor':(.380,.156)}
FEED_FLOOR_KEEP = FLOOR_KEEP | {'SectionBlockHeight':(.335,.172)}
# A-A retains its short overrun. B-B needs independent physical lanes:
# the top is a paper ordinate, the bottom is 16 mm past the block edge.
# The latter puts B's top at y174.446 on TL-22, below the drill leader's
# y178.287 at B's left edge. The -X cut never enters TL-32's +X lug.
FLOOR_CUT_TOP_Y = .259
FLOOR_CUT_BOTTOM_OVERRUN_MM = 16.0
# The section letters print smaller than the document default, and the
# cutting-line arrows shorter, so A's right letter, past the block's +X edge,
# ends under row 4Y's extension line (y 218): at the template's arrows its
# foot stood ~15.5 mm above the line whatever the letter height (farm run
# 20261027T175531766Z). swUserPreferenceDoubleValue_e (swconst.tlb R2026x),
# document scope: section arrowhead length, arrow width, arrow length.
SECTION_LETTER_HEIGHTS = (.005, .0045, .004, .0035, .003)
SECTION_LETTER_CLEARANCE = .001
_PREF_SECTION_ARROW = {27: .0025, 28: .001, 29: .0035}
_PREF_OPTION_NONE = 0
# The 1:1 pictorial's top vertex touched the border at y .235 (review of farm
# run 20261027T181901497Z); 7 mm lower it stays clear of B-B's 24.30 (y 175).
ISO_XY, ISO_SCALE = (.355,.228), SHEET_SCALE
# TL-32's plan drops to allow its column-side lug below the block. PlanLugX
# has its own baseline lane; the lug's +X side is the block's end (owner
# ruling 2026-11-07), so no lug width prints. B-B stops beyond the block
# because its -X column no longer crosses the lug. The taller pictorial
# retains its own 1:2 scale.
FEED_PLAN_XY = (.170,.181)
FEED_PLAN_KEEP = PLAN_KEEP | {
    'PlanLugX':(.1554,.1225),'PlanOverallY':(.285,.181),
    # 84d's counterbore leader crossed VIEW D at y160.934; its text also
    # met D's sheet reference. Raise only this callout: its bottom row starts
    # y165.219 and its top ends y182.765, below the y184.937 width witness.
    'CarriageCounterbores3Dia':(.245,.174),
}
FEED_SIDE_XY = (.170,.060)
FEED_SIDE_KEEP = {'TopBoreDepth':(.120,.068)}
FEED_SEAT_DEPTH_TEXT_XY = (.078,.084)
FEED_ISO_XY, FEED_ISO_SCALE = (.360,.225), (1,2)
# VIEW D looks at the lug's +X nut face; its arrow approaches from the right.
VIEW_LETTER = 'D'
VIEW_LETTER_HEIGHT = .005
VIEW_ARROW_RUN = .015
# VIEW D prints on sheet 2. Keep that reference centred under D, with a
# separate text row; it is not a face/sheet qualifier for the counterbores.
VIEW_SHEET_REF = '(SHEET 2)'
VIEW_SHEET_REF_OFFSET = (-.0075, -.011)
# VIEW D is the standard Right view at 2:1. Relative to the former Left
# view its Z direction reverses: mirror the annotation lanes about NUT_XY,
# not the model or its native dimensions. The lug end remains below the block.
NUT_XY, NUT_SCALE = (.190,.175), (2,1)
NUT_KEEP = {
    'NutCentreY':(.276,.100),'NutCentreZ':(.246,.0772),
    'NutClearanceDia':(.245,.133),'NutClock':(.1479,.0958),
}
NUT_CAPTION = 'VIEW D'
NUT_CAPTION_XY = (.178,.058)  # the note's left edge; centred under the view
# TL-32's cut-face sections hang their captions 6 mm under the face.
SECTION_CAPTION_GAP = .006
NUT_CALLOUT_XY = (.112,.165)
NUT_ISO_XY = (.380,.215)
_ARROWS_INSIDE = 0  # swDimArrowsInside
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym


def _project(adapter,view,point,label):
    return model_point_in_view(adapter,view,tuple(v/1000 for v in point),label=label)


def _displays(adapter, annotations, names) -> dict[str, Any]:
    """The named imported dimensions' ``IDisplayDimension``s, every name found."""
    found = {}
    for annotation in annotations:
        annotation = _early_bound(annotation, 'IAnnotation')
        name = dimension_name(adapter, annotation)
        if name in names:
            found[name] = _early_bound(annotation.GetSpecificAnnotation(), 'IDisplayDimension')
    missing = sorted(set(names) - set(found))
    if missing:
        raise RuntimeError(f'block dimensions not imported: {missing}')
    return found


@_telemetry.traced("drawing.pivot_tap_arrow_inside")
def _place_pivot_tap_arrow_inside(adapter, plan, annotations, contract):
    """Keep the imported source; put its arrow body inside the drill circle.

    Retained 4031 leader endpoints indicate an inner-circle tip, but an
    outside arrow body can cross the outer reamed ring. Set the documented
    diameter ArrowSide, not an unsupported annotation reattachment or a
    text move. The part and its cutting sketch remain untouched.

    SDK v3.12.1: GetArrowHeadAtIndex2 returns [tip3, dir3, width, height,
    style, normal3]. Reuse the layout audit's calibrated direction-to-base
    convention to prove the whole native triangle lies inside the bore.
    """
    displays = _displays(adapter, annotations, ('TapDrillDia', 'BoreDia'))
    sources = {}
    rim_specs = {
        'TapDrillDia': ('PivotTapProfile', part.PIVOT_TAP_DRILL, contract.BLOCK_HEIGHT - part.BORE_DEPTH),
        'BoreDia': ('TopBoreProfile', part.BORE_DIA, contract.BLOCK_HEIGHT),
    }
    for name, display in displays.items():
        feature, diameter, _ = rim_specs[name]
        dimension = _early_bound(display.GetDimension2(0), 'IDimension')
        if dimension is None or str(dimension.FullName).split('@')[:2] != [name, feature]:
            raise RuntimeError(f'{name}: missing native {feature} source')
        value = float(dimension.SystemValue)
        if not math.isfinite(value) or not math.isclose(value, diameter / 1000, rel_tol=0, abs_tol=1e-9):
            raise RuntimeError(f'{name}: native diameter reads {value!r} m')
        # GetText(0), swDimensionTextAll, is unsupported. Parts 1..4 read
        # resolved text; 5..8 retain its native token-bearing definitions.
        text = tuple(str(display.GetText(which) or '') for which in range(1, 9))
        if text[2:4] != (contract.CALLOUTS_ABOVE[name], contract.CALLOUTS_BELOW[name]):
            raise RuntimeError(f'{name}: native process/thread callout changed: {text!r}')
        annotation = _early_bound(display.GetAnnotation(), 'IAnnotation')
        position = tuple(float(v) for v in annotation.GetPosition())
        if len(position) != 3 or not all(math.isfinite(v) for v in position):
            raise RuntimeError(f'{name}: unreadable native text position')
        sources[name] = (dimension, str(dimension.FullName), value, text, position, int(display.ArrowSide))

    @_telemetry.traced("drawing.pivot_tap_arrow_readback")
    def settled():
        edges = scan_view_edges(plan, label='pivot tap and reamed seat rims')
        measured = {}
        for name, display in displays.items():
            source, full_name, value, text, position, arrow_side = sources[name]
            dimension = _early_bound(display.GetDimension2(0), 'IDimension')
            annotation = _early_bound(display.GetAnnotation(), 'IAnnotation')
            if (
                dimension is None or int(adapter.swApp.IsSame(dimension, source)) != 1
                or str(dimension.FullName) != full_name or float(dimension.SystemValue) != value
                or tuple(str(display.GetText(which) or '') for which in range(1, 9)) != text
                or annotation.IsDangling()
            ):
                raise RuntimeError(f'{name}: lost its native source/value/callout')
            expected_side = _ARROWS_INSIDE if name == 'TapDrillDia' else arrow_side
            if int(display.ArrowSide) != expected_side:
                raise RuntimeError(f'{name}: native arrow side changed from {expected_side}')
            actual_position = tuple(float(v) for v in annotation.GetPosition())
            if (len(actual_position) != 3 or not all(math.isfinite(v) for v in actual_position)
                    or math.dist(actual_position, position) > 1e-5):
                raise RuntimeError(f'{name}: native text moved while placing its arrow')
            _, diameter, z = rim_specs[name]
            circle = edges.circle_at(
                (part.BORE_X, part.BORE_Y, z), diameter / 2, axis=(0.0, 0.0, 1.0),
                center_tol_mm=1e-6, radius_tol_mm=1e-6, label=name,
            ).circle
            if not all(math.isfinite(v) for v in circle):
                raise RuntimeError(f'{name}: unreadable native mouth circle {circle!r}')
            cx, cy, cz, _, _, _, radius = circle
            centre = _project(adapter, plan, (cx, cy, cz), f'{name} centre')
            rim = _project(adapter, plan, (cx + radius, cy, cz), f'{name} rim')
            sheet_radius = math.dist(centre, rim)
            data = _early_bound(display.GetDisplayData(), 'IDisplayData')
            if data is None or int(data.GetArrowHeadCount()) != 1:
                raise RuntimeError(f'{name}: expected one native diameter arrow')
            arrow = tuple(float(v) for v in (data.GetArrowHeadAtIndex2(0) or ()))
            # 0.01 paper mm rejects the neighbouring concentric circle
            # (1.499 mm away at 1:1), while allowing native display roundoff.
            if (len(arrow) != 12 or not all(math.isfinite(v) for v in arrow)
                    or not all(math.isfinite(v) for v in centre)
                    or not math.isfinite(sheet_radius) or sheet_radius <= 0
                    or abs(math.dist(arrow[:2], centre) - sheet_radius) > 1e-5):
                raise RuntimeError(f'{name}: native arrow missed its own rim: {arrow!r}')
            triangle = arrowhead_segments(arrow)
            if name == 'TapDrillDia':
                # A disk is convex: containing the three native vertices
                # contains the complete open (0) or filled (1) triangle
                # (swArrowStyle_e), not just its rim tip.
                if (arrow[8] not in (0, 1) or arrow[6] <= 0 or arrow[7] <= 0 or len(triangle) != 3
                        or any(math.dist((edge.x0, edge.y0), centre) > sheet_radius + 1e-5
                               for edge in triangle)):
                    raise RuntimeError('TapDrillDia: native arrow body is not inside the drill circle')
            measured[name] = {
                'source': full_name, 'mouth_circle_mm': list(circle),
                'arrow_sheet_data': list(arrow), 'sheet_radius_m': sheet_radius,
            }
        _telemetry.info('pivot callout native rim readback', rims=measured)

    _set_arrow_side(adapter, annotations, ('TapDrillDia',), _ARROWS_INSIDE)
    settled()
    return settled


def _set_arrow_side(adapter, annotations, names, side) -> None:
    for name, display in _displays(adapter, annotations, names).items():
        display.ArrowSide = side
        if int(display.ArrowSide) != side:
            raise RuntimeError(f'{name}: arrows did not move to side {side}')
    rebuild_drawing(adapter, label=f'arrow side {side}')


# swDimensionTextParts_e (swconst.tlb, SOLIDWORKS 3DEXPERIENCE R2026x, read
# 2026-11-07): swDimensionTextSuffix = 2, swDimensionTextCalloutBelow = 4.
_TEXT_SUFFIX = 2
_TEXT_CALLOUT_BELOW = 4


@_telemetry.traced("drawing.block_callout_to_value_row", label_param="name")
def _inline_below_callout(adapter, annotations, name: str, text: str) -> None:
    """Move the model's below-callout ``text`` of dimension ``name`` onto its
    value's row as a suffix. The words and the native value are unchanged;
    only the row moves. Refuses a callout other than the spec's.

    COM contract (sldworks.tlb R2026x, IDisplayDimension, audited
    2026-11-07): ``GetText(WhichText: VT_I4) -> VT_BSTR`` and
    ``SetText(WhichText: VT_I4, Text: VT_BSTR) -> VT_VOID``. SetText reports
    nothing and replaces (never appends to) the part, so both parts are read
    back and the move is accepted only on the exact pair."""
    display = _displays(adapter, annotations, (name,))[name]
    below = str(display.GetText(_TEXT_CALLOUT_BELOW) or '')
    if below != text:
        raise RuntimeError(f'{name}: below-callout reads {below!r}, expected {text!r}')
    suffix = f' {text}'
    display.SetText(_TEXT_SUFFIX, suffix)
    display.SetText(_TEXT_CALLOUT_BELOW, '')
    read = (str(display.GetText(_TEXT_SUFFIX) or ''), str(display.GetText(_TEXT_CALLOUT_BELOW) or ''))
    if read != (suffix, ''):
        raise RuntimeError(f'{name}: callout did not move onto the value row, reads {read!r}')
    rebuild_drawing(adapter, label=f'{name} callout on its value row')


def _size_note(adapter, note, height: float, *, label: str) -> None:
    annotation = _early_bound(note.GetAnnotation(), 'IAnnotation')
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f'{label} has no text format')
    text_format.CharHeight = height
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f'failed to size {label}')
    rebuild_drawing(adapter, label=label)


def _section_letter_tops(dr_section) -> list[float]:
    """Sheet y of each cutting-line letter's top (GetTextInfo: x, y, z per
    letter at its top-left, draw_fr_harmonic_base.section_line_boxes)."""
    info = [float(v) for v in (dr_section.GetTextInfo() or ())]
    if len(info) < 6:
        raise RuntimeError(f'section {dr_section.GetLabel()!r}: unreadable letter positions {info!r}')
    return [info[1], info[4]]


def _cut_face_only(adapter, view, letter: str, anchor: tuple[float, float, float],
                   target: tuple[float, float], caption_top: tuple[float, float],
                   sheet_scale: tuple[float, float]) -> None:
    """Print only the cut face (rule 9): on TL-32 a line run past the part
    also printed the lug or the block beyond the plane, 88 mm tall (farm run
    20261027T190843112Z). R2026x declares the setter void; only its bool
    getter is truth-tested (draw_ch_rocker_arm_tl_vn_oblique_leadscrew_kit).
    The view keeps the place SolidWorks centred on the larger outline, and
    the centre mark of a hole beyond the plane (farm run
    20261027T192802646Z), so the marks go and the view moves until the model
    point ``anchor`` (mm) lands on ``target`` (sheet m)."""
    bound = _early_bound(view, 'IView')
    cut = _early_bound(bound.GetSection(), 'IDrSection')
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label=f'section {letter} cut face only')
    if not bool(cut.GetDisplayOnlySurfaceCut()):
        raise RuntimeError(f'section {letter} kept geometry beyond the cut')
    marks = tuple(bound.GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ())
    if marks:
        draw = adapter.currentModel
        draw.ClearSelection2(True)
        for index, mark in enumerate(marks):
            if not _early_bound(mark, 'IAnnotation').Select2(index > 0, 0):
                raise RuntimeError(f'cannot select section {letter} centre mark')
        draw.EditDelete()  # VT_VOID: the re-read below is the proof
        draw.ClearSelection2(True)
        rebuild_drawing(adapter, label=f'delete section {letter} centre marks')
        if bound.GetAnnotationsByType(_CENTER_MARK_ANNOTATION):
            raise RuntimeError(f'section {letter} centre marks survived deletion')
    landed = _project(adapter, view, anchor, f'section {letter} anchor')
    position = [float(v) for v in bound.Position]
    move = [position[i] + target[i] - landed[i] for i in range(2)]
    if bound.SetViewPosition(double_array(move), False) is not True:
        raise RuntimeError(f'section {letter}: position {move!r} refused')
    rebuild_drawing(adapter, label=f'section {letter} re-anchored')
    landed = _project(adapter, view, anchor, f'section {letter} anchor after move')
    _telemetry.info(f'section {letter}: {len(marks)} centre marks deleted; anchor at {landed!r}, '
                    f'target {target!r}')
    if math.dist(landed, target) > 5e-5:
        raise RuntimeError(f'section {letter}: anchor landed at {landed!r}, not {target!r}')
    _place_caption(adapter, view, caption_top, letter, sheet_scale)


def _place_caption(adapter, view, target, letter: str, sheet_scale) -> None:
    """Move the section's native caption so its box's top centre lands on
    ``target``: it kept its place under the larger outline, on the title
    block (farm run 20261027T195248081Z). The sheet scale is pinned first so
    finalization cannot move it after (draw_ch_rocker_arm_tl_vn_oblique_leadscrew_kit
    ``_place_view_caption``)."""
    label = f'section {letter} caption'
    sheet = _early_bound(_early_bound(adapter.currentModel, 'IDrawingDoc').GetCurrentSheet(), 'ISheet')
    if not sheet.SetScale(*sheet_scale, False, False):
        raise RuntimeError(f'cannot pin the sheet scale before the {label}')
    notes = tuple(_early_bound(view, 'IView').GetNotes() or ())
    if len(notes) != 1:
        raise RuntimeError(f'expected one native {label}, found {len(notes)} notes')
    note = _early_bound(notes[0], 'INote')
    annotation = _early_bound(note.GetAnnotation(), 'IAnnotation')
    # On the 2:1 sheet the caption steps ~0.48 mm at a time: a section
    # caption's top swung between 0.26 mm under and 0.21 mm over its target
    # for ten passes (farm run 20261027T200846410Z), so half a millimetre is
    # landed.
    for attempt in range(6):
        extent = [float(v) for v in note.GetExtent()]
        error = (target[0] - (extent[0] + extent[3]) / 2, target[1] - extent[4])
        _telemetry.info(f'{label} pass {attempt}: box {extent!r}, error {error!r}')
        if max(abs(error[0]), abs(error[1])) < 5e-4:
            break
        x, y, z = (float(v) for v in annotation.GetPosition())
        if not annotation.SetPosition2(x + error[0], y + error[1], z):
            raise RuntimeError(f'failed to move the {label}')
        rebuild_drawing(adapter, label=f'place {label}')
    else:
        raise RuntimeError(f'{label} stayed at {extent!r}, its top centre wanted at {target!r}')
    _telemetry.info(f'{label}: box {extent!r}')


def _set_section_arrows(adapter) -> None:
    """Set this document's cutting-line arrow sizes, read back, raise on
    mismatch (draw_dt_cone_gear_shaft._pin_witness_line_extension)."""
    extension = _early_bound(adapter.currentModel, 'IModelDoc2').Extension
    for key, value in _PREF_SECTION_ARROW.items():
        before = float(extension.GetUserPreferenceDouble(key, _PREF_OPTION_NONE))
        ok = extension.SetUserPreferenceDouble(key, _PREF_OPTION_NONE, value)
        applied = float(extension.GetUserPreferenceDouble(key, _PREF_OPTION_NONE))
        if not ok or abs(applied - value) > 1e-7:
            raise RuntimeError(f'section arrow preference {key}: set {value} returned {ok!r}, '
                               f'reads {applied}, was {before}')
        _telemetry.info(f'section arrow preference {key}: {before * 1000:.2f} -> {applied * 1000:.2f} mm')


def _set_section_letter_height(adapter, dr, height: float) -> None:
    text_format = _early_bound(dr.GetTextFormat(), 'ITextFormat')
    text_format.CharHeight = height
    if not dr.SetTextFormat(False, text_format):
        raise RuntimeError(f'section {dr.GetLabel()!r}: letter height {height} refused')
    rebuild_drawing(adapter, label='section letter height')


def _fit_section_letters(adapter, fitted, matched, *, below_y: float) -> None:
    """Shrink ``fitted``'s cutting-line letters until both tops stand
    ``SECTION_LETTER_CLEARANCE`` under ``below_y``, and print ``matched``'s at
    the same height. Every height tried is logged with the letter tops, so a
    seat that moves the letters differently reads off the leaf log."""
    fit = _early_bound(_early_bound(fitted, 'IView').GetSection(), 'IDrSection')
    tops: list[float] = []
    for height in SECTION_LETTER_HEIGHTS:
        _set_section_letter_height(adapter, fit, height)
        tops = _section_letter_tops(fit)
        _telemetry.info(f'section letters at {height * 1000:g} mm: tops {tops!r}, limit {below_y!r}')
        if max(tops) <= below_y - SECTION_LETTER_CLEARANCE:
            break
    else:
        _telemetry.warn(f'section letters still reach y {max(tops)!r} against {below_y!r} at '
                        f'{SECTION_LETTER_HEIGHTS[-1] * 1000:g} mm')
    for view in matched:
        _set_section_letter_height(adapter, _early_bound(_early_bound(view, 'IView').GetSection(), 'IDrSection'),
                                   height)


def _view_arrow(adapter, plan, contract) -> None:
    """The lettered viewing arrow onto the lug's +X nut face."""
    tip = _project(adapter, plan, (contract.NUT_FACE_X, (contract.LUG_Y0 + contract.LUG_Y1) / 2,
                                   contract.BLOCK_HEIGHT), 'view D arrow tip')
    text_xy = (tip[0] + VIEW_ARROW_RUN, tip[1] + VIEW_LETTER_HEIGHT / 2)
    note = add_leader_note(adapter, VIEW_LETTER, text_xy=text_xy, attach_xy=tip, view=plan,
                           label=f'view {VIEW_LETTER} viewing arrow')
    _size_note(adapter, note, VIEW_LETTER_HEIGHT, label=f'view {VIEW_LETTER} arrow letter')
    ref = add_note(adapter, VIEW_SHEET_REF, text_xy[0] + VIEW_SHEET_REF_OFFSET[0],
                   text_xy[1] + VIEW_SHEET_REF_OFFSET[1])
    if ref is None:
        raise RuntimeError(f'failed to insert the view {VIEW_LETTER} sheet reference')


async def draw_block(adapter, spec, contract, *, read_source_properties=None):
    source = CAD_ROOT/'out'/'sldprt'/f'{spec.artifact_stem}.SLDPRT'
    check('open block',await adapter.open_model(str(source)))
    if read_source_properties is None:
        read_required_properties(adapter.currentModel,('Number','Material Specification','Finish','Quantity'),
                                 required=('Number','Material Specification','Finish','Quantity'))
    else:
        read_source_properties(adapter)
    drawing,_ = new_project_drawing(adapter,property_view=spec.artifact_stem,scale=SHEET_SCALE,layout=spec.layout,
                                    unit=part_drawing_unit(spec.artifact_stem))
    is_feed = hasattr(contract,'NUT_FACE_X')
    sheets = ('Pivot and carriage','Nut interface') if is_feed else ('Pivot and carriage',)
    create_blank_drawing_sheets(adapter,sheets,label='block sheets')
    drawing = _early_bound(drawing,'IDrawingDoc')
    drawing.ActivateSheet(sheets[0])
    plan_xy, plan_keep, side_xy, side_keep, seat_text_xy, iso_xy, iso_scale, floor_keep = (
        (FEED_PLAN_XY, FEED_PLAN_KEEP, FEED_SIDE_XY, FEED_SIDE_KEEP, FEED_SEAT_DEPTH_TEXT_XY, FEED_ISO_XY, FEED_ISO_SCALE,
         FEED_FLOOR_KEEP)
        if is_feed else (PLAN_XY, PLAN_KEEP, SIDE_XY, SIDE_KEEP, SEAT_DEPTH_TEXT_XY, ISO_XY, ISO_SCALE, FLOOR_KEEP))
    plan = place_view(adapter,str(source),'*Front',*plan_xy,scale=SHEET_SCALE)
    # Each cutting line runs so its arrows point away from the section it
    # names (third-angle): A-A below the plan looks up, B-B right of it looks
    # left. A-A stays short; B-B's ends use the reserved annotation lanes.
    _set_section_arrows(adapter)
    side = create_section_view(adapter,plan,
        line_start=_project(adapter,plan,(part.BLOCK_X1+4,0,contract.BLOCK_HEIGHT),'pivot cut start'),
        line_end=_project(adapter,plan,(part.BLOCK_X0-4,0,contract.BLOCK_HEIGHT),'pivot cut end'),
        view_xy=side_xy,section_label='A',scale=(1,1),partial=True,label='pivot shoulder seat')
    iso = place_view(adapter,str(source),'*Isometric',*iso_xy,scale=iso_scale)
    set_hidden_lines_removed(adapter,plan)
    plan_annotations = curate_view_dimensions(adapter,plan,keep=plan_keep,view_label='plan',
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    settled_checks = ()
    if not is_feed:
        settled_checks = (_place_pivot_tap_arrow_inside(adapter, plan, plan_annotations, contract),)
    _set_arrow_side(adapter, plan_annotations, ROW_DIMENSIONS, _ARROWS_INSIDE)
    set_hidden_lines_removed(adapter,side)
    side_annotations = curate_view_dimensions(adapter,side,keep=side_keep,view_label='pivot section direction',
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    _set_arrow_side(adapter, side_annotations, ('TopBoreDepth',), _ARROWS_INSIDE)
    offset_dimension_text(adapter, side_annotations, {'TopBoreDepth': seat_text_xy})
    _inline_below_callout(adapter, plan_annotations, 'BlockLength', contract.CALLOUTS_BELOW['BlockLength'])
    offset_dimension_text(adapter, plan_annotations, {'BlockLength': BLOCK_LENGTH_TEXT_XY})
    annotations = plan_annotations + side_annotations
    x = part.CBORE_SECTION_X
    cut_axis = _project(adapter,plan,(x,part.BLOCK_WIDTH/2,contract.BLOCK_HEIGHT),'floor cut axis')
    if cut_axis[1] + .004 > FLOOR_CUT_TOP_Y:
        raise RuntimeError('B-B top arrow lane does not clear the block')
    start = (cut_axis[0], FLOOR_CUT_TOP_Y)
    end_y = -part.BLOCK_WIDTH/2-FLOOR_CUT_BOTTOM_OVERRUN_MM
    end = _project(adapter,plan,(x,end_y,contract.BLOCK_HEIGHT),'floor cut end')
    floor = create_section_view(adapter,plan,line_start=start,line_end=end,view_xy=FLOOR_XY,
                                section_label='B',scale=(1,1),partial=True,
                                label='carriage counterbore floor')
    # Both blocks print B-B as its cut face only (rule 9), the top face's +Y
    # corner where the full B-B put it. TL-32's B-B also prints the block
    # height (CboreFloorReference's interior line); TL-22 prints it on A-A.
    _cut_face_only(adapter, floor, 'B', (x, part.BLOCK_WIDTH/2, contract.BLOCK_HEIGHT),
                   (FLOOR_XY[0]-contract.BLOCK_HEIGHT/2000, FLOOR_XY[1]+part.BLOCK_WIDTH/2000),
                   (FLOOR_XY[0], FLOOR_XY[1]-part.BLOCK_WIDTH/2000-SECTION_CAPTION_GAP), SHEET_SCALE)
    row_4y = _project(adapter,plan,(part.BLOCK_X1,part.BOLT_Y,contract.BLOCK_HEIGHT),'row 4Y')
    _fit_section_letters(adapter, side, (floor,), below_y=row_4y[1])
    annotations += curate_view_dimensions(adapter,floor,keep=floor_keep,view_label='B-B floor',
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    right_keep = {}
    if not is_feed:
        right = place_view(adapter,str(source),'*Right',*RIGHT_XY,scale=SHEET_SCALE)
        set_hidden_lines_removed(adapter,right)
        right_keep = RIGHT_KEEP
        annotations += curate_view_dimensions(adapter,right,keep=right_keep,view_label='right end',
                         dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    set_hidden_lines_removed(adapter,iso)
    sheet_scales = None
    if is_feed:
        _view_arrow(adapter, plan, contract)
        drawing.ActivateSheet(sheets[1])
        nut = place_view(adapter,str(source),'*Right',*NUT_XY,scale=NUT_SCALE)
        nut_iso = place_view(adapter,str(source),'*Isometric',*NUT_ISO_XY,scale=FEED_ISO_SCALE)
        set_hidden_lines_removed(adapter,nut)
        set_hidden_lines_removed(adapter,nut_iso)
        nut_annotations = curate_view_dimensions(adapter,nut,keep=NUT_KEEP,view_label='nut face',
                      dimensions_by_feature=contract.DRAWING_DIMENSIONS)
        print_imported_metric_dimensions(adapter, nut_annotations,
                                          {name: places for (_, name), (places, _) in contract.METRIC_DIMENSIONS.items()})
        caption = add_note(adapter, NUT_CAPTION, *NUT_CAPTION_XY)
        if caption is None:
            raise RuntimeError('failed to insert the VIEW D caption')
        _size_note(adapter, caption, VIEW_LETTER_HEIGHT, label='VIEW D caption')
        # The +Y/+Z tap is upper-left in this Right view. Its callout
        # approaches from the left; the title block owns the thread class.
        # row says where the taps come from (TL-00 says how).
        y,z = contract.NUT_HOLES_YZ[3]
        rim = contract.NUT_TAP_DRILL/2/math.sqrt(2)
        edge = _project(adapter,nut,(contract.NUT_FACE_X,y+rim,z+rim),'nut tap mouth')
        taps = add_native_hole_callout(adapter,nut,edge_xy=edge,callout_xy=NUT_CALLOUT_XY,
                                       label='feed nut screw taps',process=contract.TRANSFER_PROCESS)
        omit_title_block_thread_class(taps, label='feed nut screw taps')
        set_callout_lengths_to_three_places(taps, label='feed nut screw taps')
        rebuild_drawing(adapter, label='feed nut screw tap callout')
        annotations += nut_annotations
        sheet_scales = {sheets[0]: SHEET_SCALE, sheets[1]: NUT_SCALE}
    # Every printed dimension keeps its part-authored places; the repeated
    # row/column locations left off the sheet print nothing to check.
    kept = {*plan_keep, *side_keep, *floor_keep, *right_keep, *(NUT_KEEP if is_feed else ())}
    precision = {name:places for dims in contract.DRAWING_PRECISION.values()
                 for name,places in dims.items() if name in kept}
    assert_imported_precision(adapter,annotations,precision)
    if is_feed:
        # SolidWorks pins its own TAPPED_HOLE_NOTE once per view that picks up
        # the one NutTaps feature, and which views do is its choice: the same
        # recipe and model printed 1 on main 6d7f35476 and 2 on 1e2b7b540
        # (draw_fr_top_frame._auto_tapped_hole_notes). So the count is logged
        # by sheet, not gated, and finalize's sweep proves none reaches the print.
        removed = {}
        for sheet_name in sheets:
            drawing.ActivateSheet(sheet_name)
            removed[sheet_name] = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
        _telemetry.info(f'removed automatic {TAPPED_HOLE_NOTE!r} notes by sheet: {removed}')
    drawing.ActivateSheet(sheets[0])
    outputs = DrawingOutputs(slddrw=spec.outputs['slddrw'],pdf=spec.outputs['pdf'],png=spec.outputs['png'])
    return await finalize_drawing(adapter,outputs,pdf_title='Rocker Oblique Trammel Block Manufacturing Drawing',
                                  scale=SHEET_SCALE,layout=spec.layout,sheet_scales=sheet_scales,
                                  redundant_note_substrings=(TAPPED_HOLE_NOTE,) if is_feed else (),
                                  expected_redundant_notes=0, settled_checks=settled_checks)
