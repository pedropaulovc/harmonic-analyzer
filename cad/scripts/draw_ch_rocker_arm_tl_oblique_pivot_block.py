"""Manufacturing sheets for the plain shoulder-screw pivot blocks.

Both sheets print decimal inch (each part's ``drawing_unit``). All sizes
import native model dimensions; no bearing/cartridge sheets survive.
Plan X locations run from the -X (left) edge through the hidden
``PlanDatumReference`` sketch; Y from the shoulder seat's axis. Section B-B
shows the floor from the carriage seat, not a competing counterbore-depth
tolerance chain. TL-32's nut face is VIEW D on its own 2:1 sheet, its arrow on
the plan. The layout notes below give sheet millimetres.
"""
from __future__ import annotations
import argparse
import math
import sys
from typing import Any
from _check import check
from _com import _early_bound
from _drawing_common import (DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, rebuild_drawing,
                             remove_notes_matching)
from _drawing_dimensions import assert_imported_precision, dimension_name, offset_dimension_text
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _drawing_metric_vendor import print_imported_metric_dimensions
from _part_properties import part_drawing_unit
import _telemetry
from _session import run_build
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view
import ch_rocker_arm_tl_oblique_pivot_block_spec as part
from ch_rocker_arm_tl_oblique_callouts import set_callout_lengths_to_three_places

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME['ch_rocker_arm_tl_oblique_pivot_block']
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / 'out' / 'sldprt' / f'{PART_STEM}.SLDPRT'
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs['slddrw'],pdf=SPEC.outputs['pdf'],png=SPEC.outputs['png'])
SHEET_SCALE = (1.0,1.0)
# SolidWorks' own descriptive note for TL-32's Hole Wizard nut taps; the native
# tap callout already states the thread.
TAPPED_HOLE_NOTE = '#4-40 Tapped Hole'
# Sheet metres. The plan sits at x .170 so the 112 mm REAM text, the tap
# callout and the 4X callouts fit left of it inside the border, with short
# leaders. Plan geometry on the sheet: block x 139..201, y 185..225; frame
# centre 181,205; bore 149,205; holes x 168/194, y 192/218.
# Both sections are removed sections whose cutting lines run 4 mm past both
# block edges, so each prints the whole profile at its cut (review of farm
# run 20261027T171931429Z: a cut stopping inside the block printed a slice
# that read as a complete small part). Both look away from the plan (third
# angle, review of farm run 20261024T133158704Z), so their letters stand on
# the plan side: A along y 205 from x 205 to 135, its letters up between the
# seat axis's extension line (y 205) and row 4Y's (y 218); B along x 194
# from y 229 down, letters left at x ~176..182 (TL-22 to y 181; TL-32 stops
# inside the block at y 210, since its lug fills x 171.75..190.25 below).
# The REAM and 4X DRILL callouts stand under the A letter at x 135, their
# leaders rising to the seat and hole 1 from the lower left; the 4X
# COUNTERBORE stands lower right, its leader on hole 3 (review: two leaders
# converged on hole 1).
# X ordinates stand above the plan in 9 mm lanes from the -X edge (x 139):
# the 10.00 to the seat, its text right of its 10 mm span, then the two hole
# columns and the 62.00 overall, 8 mm under the border. The 62.00's text and
# the counterbore end wall it sets stand off right of the +X edge, leadered,
# one row under the value, the block centred on its point: inline, the
# callout row pushed the line onto the 55.000's text, and centred at y .2615
# the value crossed the border (farm run 20261028T152045278Z). Rows are
# dimensioned once each from the seat axis: 3Y/4Y on the +X side at x .222,
# clear of A's right letter, arrows inside so neither's outside tail strikes
# the other's text (review r1-r3); BlockSideY at x .231 and BlockWidth past
# its shouldered text, its three rows centred on the point over the bottom
# edge's extension line, 4 mm right of BlockSideY's arrow tail (at x .255
# 1.6 mm, same run) and left of TL-32's 88.00 (x .285).
PLAN_XY = (.170,.205)
PLAN_KEEP = {
    'BlockLength':(.170,.259),'PlanHole2X':(.1665,.250),'PlanHole1X':(.1535,.241),
    'PlanBoreX':(.157,.232),
    'BlockWidth':(.2595,.203),'BlockSideY':(.231,.220),
    'CarriageDrills3Y':(.222,.1985),'CarriageDrills4Y':(.222,.2115),
    'BoreDia':(.078,.196),'CarriageDrills1Dia':(.085,.168),'CarriageCounterbores3Dia':(.245,.150),
}
BLOCK_LENGTH_TEXT_XY = (.240,.2585)
ROW_DIMENSIONS = ('CarriageDrills3Y','CarriageDrills4Y')
# Section A-A looks up the sheet (third-angle: placed below the plan, its
# arrows point away from it, review of farm run 20261024T133158704Z), so the
# top face prints on top: Z 0..24.3 at y 67.9..92.2, the seat floor at y
# 84.55. On TL-22 the tap's dimension line stands 6 mm under the bottom face
# (its last row underlined ~8 mm under the text anchor), its extension lines
# dropping from the tap's walls: inside the full section it crossed the
# hatching (review of farm run 20261027T201345346Z). TL-32, whose sheet
# shipped with it, keeps it on the tap-only band near the bottom face, its
# extension lines (which would rise through the Ø10 seat) hidden. The
# 7.650 seat depth keeps its line at x .120, arrows inside so the line is
# drawn for the text leader to land on, and stands its text, with the stack
# it sets, off to the upper left in the empty band under the plan's
# callouts. The ~72 mm two-row text is centred on the point and must end
# left of x .120, or the leader to its right end crosses its last letters
# (farm run 20261024T133158704Z).
# A-A is centred on its cut span (X -46..+24), the block's own centre, so its
# -X face lands at x 139 under the plan's.
SIDE_XY = (.170,.080)
SIDE_KEEP = {'TopBoreDepth':(.120,.088),'TapDrillDia':(.084,.070)}
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
# TL-32: the plan drops 24 mm so its block lands where TL-22's does; the lug
# (x 171.75..190.25, y 137..185) takes the space below. Under it: LugWidth,
# arrows and text inside its 18.5 mm span, then the lug face from the -X
# edge. B's line runs on past the lug's end to y 105, under both: its lower
# arrow and letter point left, into the lug's lane, so a line stopping at
# the block's -Y edge put them on the lug, and one stopping inside the block
# printed a strip read as a whole part (review of farm run
# 20261027T181901497Z). The 88.00 overall stands outermost on the +X side,
# past the 4X COUNTERBORE callout. A-A moves down 20 mm. Its taller
# pictorial prints at 1:2 to stay under the border.
FEED_PLAN_XY = (.170,.181)
FEED_PLAN_KEEP = PLAN_KEEP | {
    'LugWidth':(.181,.1305),'PlanLugX':(.1554,.1225),'PlanOverallY':(.285,.181),
}
FEED_FLOOR_CUT_END_Y = -100
FEED_SIDE_XY = (.170,.060)
FEED_SIDE_KEEP = {'TopBoreDepth':(.120,.068),'TapDrillDia':(.084,.058)}
FEED_SEAT_DEPTH_TEXT_XY = (.078,.084)
FEED_ISO_XY, FEED_ISO_SCALE = (.360,.225), (1,2)
# VIEW D looks at the lug's -X (nut) face: its letter's leader is the viewing
# arrow, level with the lug's mid-length, 15 mm left of that face.
VIEW_LETTER = 'D'
VIEW_LETTER_HEIGHT = .005
VIEW_ARROW_RUN = .015
# VIEW D prints on sheet 2: the arrow's letter says so on a row under it,
# centred under the letter, clear of the 4X DRILL leader above (review of
# farm run 20261101T175835750Z).
VIEW_SHEET_REF = '(SHEET 2)'
VIEW_SHEET_REF_OFFSET = (-.010, -.008)
# Nut interface, VIEW D, *Left at 2:1 on a 2:1 sheet, at .190,.175: Z runs
# right from the bottom face at x 165.7, Y=0 prints at y 223, the lug end
# (Y -68) at y 87; the leadscrew axis at 190.5,113, the TL-27 nut's two taps
# on its line at y 95.7 (tap 1, toward the lug end) and 130.3. The axis
# stands from the lug end / carriage-face corner, each tap .340 from the axis
# (2X, one each side: no tap on the other). Left of the view: the axis's .515
# (x 104, as before) and, under the lug end, the 12.400 mm height, its three
# rows outboard left of the bottom face's extension line, which then stops at
# the lug end instead of running up the view's edge. Right of the view, clear
# of its edge (x 214): both taps' .340 on one lane, each with its mate row,
# centred between the axis's extension line and its own tap's. The Ø.340
# clearance callout comes in from the upper left, crossing only the view's
# edge; the tap callout from the lower right onto tap 1's rim, under every
# right-hand extension line.
NUT_XY, NUT_SCALE = (.190,.175), (2,1)
NUT_KEEP = {
    'NutCentreY':(.104,.100),'NutCentreZ':(.134,.0772),
    # Arrows outside, each .340 on its own lane, the second's lane right of
    # the first's text, so neither line's arrow run reaches the other's text
    # (feed-nut2: on one lane the runs struck the texts, and arrows inside
    # touched them).
    'NutTap1Y':(.247,.1044),'NutTap2Y':(.282,.1216),
    'NutClearanceDia':(.135,.150),
}
NUT_CAPTION = 'VIEW D'
NUT_CAPTION_XY = (.178,.058)  # the note's left edge; centred under the view
# TL-32's cut-face sections hang their captions 6 mm under the face.
SECTION_CAPTION_GAP = .006
# Under tap 1's lane's arrow run (which reaches y 89).
NUT_CALLOUT_XY = (.240,.080)
NUT_ISO_XY = (.380,.215)
_ARROWS_INSIDE = 0  # swDimArrowsInside
_ARROWS_OUTSIDE = 1  # swDimArrowsOutside
_WITNESS_NONE = 3  # swWitnessLineVisibility_e.swWitnessLineNone
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


def _set_arrow_side(adapter, annotations, names, side) -> None:
    for name, display in _displays(adapter, annotations, names).items():
        display.ArrowSide = side
        if int(display.ArrowSide) != side:
            raise RuntimeError(f'{name}: arrows did not move to side {side}')
    rebuild_drawing(adapter, label=f'arrow side {side}')


def _hide_witness_lines(adapter, annotations, name) -> None:
    display = _displays(adapter, annotations, (name,))[name]
    display.WitnessVisibility = _WITNESS_NONE
    if int(display.WitnessVisibility) != _WITNESS_NONE:
        raise RuntimeError(f'{name}: extension lines still shown')
    rebuild_drawing(adapter, label='tap drill extension lines hidden')


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
    getter is truth-tested (draw_ch_rocker_arm_tl_vn_oblique_leadscrew).
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
    finalization cannot move it after (draw_ch_rocker_arm_tl_vn_oblique_leadscrew
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
    """The lettered viewing arrow onto the lug's -X face (draw_dt_cone_tip_block)."""
    tip = _project(adapter, plan, (contract.LUG_X0, (contract.LUG_Y0 + contract.LUG_Y1) / 2,
                                   contract.BLOCK_HEIGHT), 'view D arrow tip')
    text_xy = (tip[0] - VIEW_ARROW_RUN, tip[1] + VIEW_LETTER_HEIGHT / 2)
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
    # left, and the plan's top face prints toward the plan in both. The lines
    # run past the block (layout notes above), with short arrows.
    _set_section_arrows(adapter)
    side = create_section_view(adapter,plan,
        line_start=_project(adapter,plan,(part.BLOCK_X1+4,0,contract.BLOCK_HEIGHT),'pivot cut start'),
        line_end=_project(adapter,plan,(part.BLOCK_X0-4,0,contract.BLOCK_HEIGHT),'pivot cut end'),
        view_xy=side_xy,section_label='A',scale=(1,1),partial=True,label='pivot shoulder seat')
    iso = place_view(adapter,str(source),'*Isometric',*iso_xy,scale=iso_scale)
    set_hidden_lines_removed(adapter,plan)
    plan_annotations = curate_view_dimensions(adapter,plan,keep=plan_keep,view_label='plan',
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    _set_arrow_side(adapter, plan_annotations, ROW_DIMENSIONS + (('LugWidth',) if is_feed else ()), _ARROWS_INSIDE)
    set_hidden_lines_removed(adapter,side)
    side_annotations = curate_view_dimensions(adapter,side,keep=side_keep,view_label='pivot section direction',
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    if is_feed:
        _hide_witness_lines(adapter, side_annotations, 'TapDrillDia')
    _set_arrow_side(adapter, side_annotations, ('TopBoreDepth',), _ARROWS_INSIDE)
    offset_dimension_text(adapter, side_annotations, {'TopBoreDepth': seat_text_xy})
    offset_dimension_text(adapter, plan_annotations, {'BlockLength': BLOCK_LENGTH_TEXT_XY})
    annotations = plan_annotations + side_annotations
    x = part.CBORE_SECTION_X
    start = _project(adapter,plan,(x,part.BLOCK_WIDTH/2+4,contract.BLOCK_HEIGHT),'floor cut start')
    end_y = FEED_FLOOR_CUT_END_Y if is_feed else -part.BLOCK_WIDTH/2-4
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
        nut = place_view(adapter,str(source),'*Left',*NUT_XY,scale=NUT_SCALE)
        nut_iso = place_view(adapter,str(source),'*Isometric',*NUT_ISO_XY,scale=FEED_ISO_SCALE)
        set_hidden_lines_removed(adapter,nut)
        set_hidden_lines_removed(adapter,nut_iso)
        nut_annotations = curate_view_dimensions(adapter,nut,keep=NUT_KEEP,view_label='nut face',
                      dimensions_by_feature=contract.DRAWING_DIMENSIONS)
        # Held outside, read back: on their staggered lanes (NUT_KEEP) the
        # arrow runs pass clear of the other .340's text.
        _set_arrow_side(adapter, nut_annotations, ('NutTap1Y', 'NutTap2Y'), _ARROWS_OUTSIDE)
        print_imported_metric_dimensions(adapter, nut_annotations,
                                          {name: places for (_, name), (places, _) in contract.METRIC_DIMENSIONS.items()})
        caption = add_note(adapter, NUT_CAPTION, *NUT_CAPTION_XY)
        if caption is None:
            raise RuntimeError('failed to insert the VIEW D caption')
        _size_note(adapter, caption, VIEW_LETTER_HEIGHT, label='VIEW D caption')
        # The callout reaches tap 1 (toward the lug end) from the lower
        # right, under the taps' right-hand extension lines. The title
        # block's THREADS row owns the class; each .340 names the mate.
        y,z = contract.NUT_HOLES_YZ[0]
        rim = contract.NUT_TAP_DRILL/2/math.sqrt(2)
        edge = _project(adapter,nut,(contract.NUT_FACE_X,y-rim,z+rim),'nut tap mouth')
        taps = add_native_hole_callout(adapter,nut,edge_xy=edge,callout_xy=NUT_CALLOUT_XY,
                                       label='feed nut screw taps')
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
                                  expected_redundant_notes=0)


async def build(adapter):
    return await draw_block(adapter,SPEC,part)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))
