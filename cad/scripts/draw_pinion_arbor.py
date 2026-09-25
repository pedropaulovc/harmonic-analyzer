r"""Create the integral MHA-102 pinion-arbor manufacturing drawing."""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from typing import Any

import _drawing_leaders
import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    _drawing_component_name,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import audit_sheet, format_findings
from pinion_arbor_pin_spec import PIN_HOLE_CALLOUT, PIN_HOLE_DIA
from pinion_arbor_spec import (
    BACK_CAP_R,
    BACK_CAP_SAG,
    BACK_JOURNAL_Z,
    BOND_ZONE_DIA_Z,
    CROSS_HOLE_CALLOUT,
    DRAWING_PRECISION_BY_NAME,
    DRUM_STATION,
    FRONT_JOURNAL_Z,
    HEAD_CAP_SAG,
    HEAD_CENTER_Z,
    HEAD_DIA,
    HEAD_FRONT_Z,
    HEAD_REAR_Z,
    JOURNAL_LEN,
    NECK_DIA,
    NECK_END_Z,
    OVERALL_LEN,
    PIN_Z,
    SHAFT_DIA,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    iter_views,
    place_view,
)
from diagnostics.drawing_layout_audit import collect_document

SPEC = DRAWINGS_BY_NAME["pinion_arbor"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (1.0, 1.0)
PRINCIPAL_CENTER = (0.200, 0.170)
ISO_CENTER = (0.365, 0.225)
DETAIL_CENTER = (0.165, 0.235)
DETAIL_SCALE = (2, 1)
DETAIL_RADIUS_MM = 15.0
DETAIL_RATIO = DETAIL_SCALE[0] / DETAIL_SCALE[1]
# The native "DETAIL A / SCALE 2:1" label sits centred under its own detail
# circle, this far below it (the label's anchor is its top edge): clear of the
# HeadLen text that rides the circle's lower edge.
DETAIL_LABEL_DROP = 0.012
DETAIL_LABEL_XY = (
    DETAIL_CENTER[0],
    DETAIL_CENTER[1]
    - DETAIL_RADIUS_MM * DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
    - DETAIL_LABEL_DROP,
)
# Profile scale is 1:1 with the head to the right, so model z maps to sheet
# x = 0.200 - (z - 106.35) / 1000.  The lands are centred on their straps, so
# their centres (x 0.252 front, 0.099 back) hold whatever the derived land
# length; only their ends move.  The front land's length rides above the
# shaft and its diameter hangs below; the back land's are swapped (see
# BACK_JOURNAL_TEXT_X).  The stations from the Ø15 head rear face stack
# below the shaft.
# The view is placed on its geometry's centre, midway between the two crown
# apexes, not on a typed station: the old 106.725 sat 0.375 mm off (half the
# head's 0.75 mm forward growth, rule 12), and leaf neckc2-07af measured the
# drum witness at x 246.5, the bond-zone witness at 192.6 and the (1.2) apex
# extension at 78.9 mm, where 106.725 put them at 246.9, 193.0 and 79.3.
FRONT_APEX_Z = HEAD_FRONT_Z - HEAD_CAP_SAG
# The back crown's apex, the profile's left end (x 0.0789).
BACK_APEX_Z = FRONT_APEX_Z + OVERALL_LEN
MODEL_Z_AT_SHEET_ORIGIN_X = (FRONT_APEX_Z + BACK_APEX_Z) / 2.0


def _sheet_x(model_z: float) -> float:
    return PRINCIPAL_CENTER[0] - (model_z - MODEL_Z_AT_SHEET_ORIGIN_X) / 1000.0


# Each land's two ends on the sheet, (head side, crown side), from the spec's
# stations and land length: every land witness, and every text placed against
# one, follows the spec when the lands move (pinioncluster's #858 re-lay).
FRONT_LAND_X = (_sheet_x(FRONT_JOURNAL_Z), _sheet_x(FRONT_JOURNAL_Z + JOURNAL_LEN))
BACK_LAND_X = (_sheet_x(BACK_JOURNAL_Z), _sheet_x(BACK_JOURNAL_Z + JOURNAL_LEN))
Lands = tuple[tuple[float, float], tuple[float, float]]
LANDS: Lands = (FRONT_LAND_X, BACK_LAND_X)


def _mid(ends: tuple[float, float]) -> float:
    return (ends[0] + ends[1]) / 2.0


# Each land's diameter is measured at a short witness JOURNAL_DIA_POINT_FROM_
# CROWN_END in from its crown-side end (build_pinion_arbor's constant of the
# same name; test_each_land_diameter_is_measured_a_short_extension_from_its_line
# pins the two equal), and its line stands JOURNAL_DIA_LINE_OFFSET from that point, so
# its extensions are ~1 mm rather than a run along the flank (Main,
# 2026-09-24).  The text hangs away from the side its extensions come from:
# left of the front line, right of the back one.
JOURNAL_DIA_POINT_FROM_CROWN_END = 2.0
JOURNAL_DIA_LINE_OFFSET = 0.001
FRONT_JOURNAL_DIA_POINT_X = _sheet_x(
    FRONT_JOURNAL_Z + JOURNAL_LEN - JOURNAL_DIA_POINT_FROM_CROWN_END
)
BACK_JOURNAL_DIA_POINT_X = _sheet_x(
    BACK_JOURNAL_Z + JOURNAL_LEN - JOURNAL_DIA_POINT_FROM_CROWN_END
)
# The back land is boxed in below the shaft (the back-crown and overall
# witnesses at x 0.079-0.081 on its crown side, the back station's witness on
# its head side), so its diameter hangs ABOVE the shaft, its text right of the
# line over the land, and its length dimension moves below.
BACK_JOURNAL_TEXT_X = BACK_JOURNAL_DIA_POINT_X + JOURNAL_DIA_LINE_OFFSET
BACK_JOURNAL_DIA_Y = 0.1945
# The drum station's text block (~35 mm "DRUM STATION" callout) ends 4 mm left
# of its drum-end witness: between that witness and the head face, the
# neck-end witness drops through.
DRUM_STATION_TEXT_WIDTH = 0.035
DRUM_STATION_WITNESS_X = _sheet_x(HEAD_REAR_Z + DRUM_STATION)
DRUM_STATION_TEXT_XY = (
    DRUM_STATION_WITNESS_X - 0.004 - DRUM_STATION_TEXT_WIDTH / 2.0,
    0.123,
)
# The front land's diameter text hangs LEFT of its line (x-0.026 .. x+0.001,
# measured at 4e97c4d8), and the drum station's witness drops through the
# whole band below the shaft (run 059b5b0f: text-on-line at x 246.0).  Its
# line stands on the land 1 mm crown side of its measuring point, so the text
# block ends on that point, JOURNAL_DIA_POINT_FROM_CROWN_END in from the
# land's crown end, short of the drum witness by what the spec leaves between
# the two (test_the_front_diameter_text_ends_short_of_the_drum_witness holds
# at least 2 mm).
JOURNAL_DIA_TEXT_OVERHANG = 0.001
FRONT_JOURNAL_DIA_X = FRONT_JOURNAL_DIA_POINT_X - JOURNAL_DIA_LINE_OFFSET
# The bond-zone diameter stands over the part's witness (x 0.195) but hangs
# its text ABOVE the shaft: below it, beside the front "JOURNAL" shelf, the
# two read as one paired callout (Main and Fable, 63468ee9).  Above, its line
# rises a few mm off the silhouette to the shelf, right of the DETAIL A label
# and under detail A's "(3.0)", and short of the front land's length witnesses.
BOND_ZONE_TEXT_XY = (_sheet_x(BOND_ZONE_DIA_Z), 0.190)
# The drum-station and bond-zone reference sketches stand alone, so the
# profile shows them, and each ends on a short construction witness lying ON
# the lower Ø8 outline.  The view paints that witness construction grey over
# the black silhouette, which at 1:1 read as a break in the outline, i.e. a
# groove or relief to a machinist (Main, 5471a6ef).  Each is re-coloured in
# the view to the outline's black; the model sketch and its dimension are
# untouched.  The spans (model z, mm) mirror build_pinion_arbor's
# DRUM_STATION_POINT_LEN / BOND_ZONE_WITNESS_LEN, pinned by test.
REFERENCE_WITNESS_COLOR = 0  # COLORREF black, the outline's colour.
DRUM_STATION_POINT_LEN = 1.0
BOND_ZONE_WITNESS_LEN = 4.0
REFERENCE_WITNESSES = {
    "DrumStationReference": (
        HEAD_REAR_Z + DRUM_STATION - DRUM_STATION_POINT_LEN,
        HEAD_REAR_Z + DRUM_STATION,
    ),
    "BondZoneReference": (BOND_ZONE_DIA_Z, BOND_ZONE_DIA_Z + BOND_ZONE_WITNESS_LEN),
}
SW_SEL_EXT_SKETCH_SEGS = 24  # swSelectType_e.swSelEXTSKETCHSEGS
SW_SKETCH_LINE = 0  # swSketchSegments_e.swSketchLINE
REFERENCE_WITNESS_LEN_TOL = 0.01  # mm; the witnesses are fully defined sketch lengths
# A reference line IS the witness when both its projected ends sit this close
# to the witness's (sheet m, 1:1): fully defined sketch geometry, so only float
# noise separates them, and the nearest other line (the sketch's own axis) is
# 4 mm away.
WITNESS_END_TOL_M = 5e-5
# A witness's two sheet endpoints (m).
Span = tuple[tuple[float, float], tuple[float, float]]
# Exported-raster proof that the outline stays unbroken over each witness:
# the grey witness core measured 107-128 and the black outline 0 (5471a6ef
# PNG), so every raster column over a span needs at least two dark pixels
# within a few rows of the flank.
OUTLINE_DARK_MAX = 60
OUTLINE_CORE_ROWS = 2
OUTLINE_SEARCH_ROWS = 6
# ---------------------------------------------------------------------------
# Profile leader corners
#
# No leader may cross, touch or run along a dimension or extension line
# (drawing-simplicity rule 8; Main's eye-pass of neckc3-a652).  Two leaders on
# the a652 sheet did: the pin hole's Ø1.59 dropped straight down through the
# 39.0 COLLAR PIN's dimension line and along its pin extension, and the back
# crown's SR7.3 rose at 45° from the lower left, past the crown's ±33° arc,
# through the (242.2) OVERALL and 227.5 witnesses under the part.  The
# positions below are derived from the model and from ink measured on that
# sheet's 300 dpi export (11.811 px/mm), and profile_leader_findings proves
# them before any COM work.
#
# Every sheet dimension's text is placed at its commanded position; each
# extent below is (left, down, right, up) from it, in sheet metres.
PROFILE_AXIS_Y = PRINCIPAL_CENTER[1]
# The SR7.3's arc: the back crown's sphere, centred on the axis R in from the
# apex.  Its ends meet the Ø8 land's flanks, so a radial leader lands on the
# crown only within asin(4 / 7.27) = 33.4° of the axis.
BACK_CAP_CENTER = (_sheet_x(BACK_APEX_Z - BACK_CAP_R), PROFILE_AXIS_Y)
BACK_CAP_R_M = BACK_CAP_R / 1000.0 * SHEET_SCALE[0] / SHEET_SCALE[1]
BACK_CAP_HALF_ANGLE_DEG = math.degrees(math.asin(SHAFT_DIA / 2.0 / BACK_CAP_R))
# a652: "SR7.3" for (45.0, 140.0) printed x 39.3-50.55, y 138.2-141.65 mm, its
# shoulder 37.85-53.72 mm at y 137.2, and the leader left the shoulder's
# circle-side end along the radius (45.3° through the centre at 86.2, 170).
BACK_CAP_R_TEXT_EXTENT = (0.0057, 0.0018, 0.00555, 0.00165)
BACK_CAP_R_SHOULDER = (0.00715, 0.00872, 0.0028)  # left, right (the bend), drop
# The leader now comes in from the upper left, 25° above the axis: inside the
# arc with 8° to spare, and over the crown where nothing stands once the (1.2)
# moved under the part.  The bend sits 26 mm out along that radius, which puts
# the text above-right of the end view, clear of the Ø15's leader.
BACK_CAP_R_LANDING_DEG = 25.0
BACK_CAP_R_BEND_RADIUS = 0.026


def _on_radius(
    center: tuple[float, float], radius: float, degrees_above_left: float
) -> tuple[float, float]:
    """The point ``radius`` from ``center`` along a ray that leaves it to the
    left, ``degrees_above_left`` above the horizontal."""
    angle = math.radians(degrees_above_left)
    return (center[0] - radius * math.cos(angle), center[1] + radius * math.sin(angle))


BACK_CAP_R_BEND = _on_radius(BACK_CAP_CENTER, BACK_CAP_R_BEND_RADIUS, BACK_CAP_R_LANDING_DEG)
BACK_CAP_R_LANDING = _on_radius(BACK_CAP_CENTER, BACK_CAP_R_M, BACK_CAP_R_LANDING_DEG)
BACK_CAP_R_TEXT_XY = (
    BACK_CAP_R_BEND[0] - BACK_CAP_R_SHOULDER[1],
    BACK_CAP_R_BEND[1] + BACK_CAP_R_SHOULDER[2],
)
# The (1.2) BACK CROWN stands UNDER the part (Main, neckc3-a652 ruling b), its
# extensions dropping along the (242.2)'s from the apex and the 227.5's from
# the root, so the crown's upper left is free for the SR7.3.  a652 printed it
# for (55.0, 220.0): "(1.2)" x 50.6-59.3, y 220.1-224.5; "BACK CROWN" x
# 39.1-70.8, y 215.8-218.9; its line 5.6 mm under the position, from under
# the text's left end (38.65) to 6.3 mm past the root.  Its row at y 128.4
# sits between the back land's length row (140.2 at a652) and the back
# station's (112.2).
BACK_CAP_SAG_XY = (0.055, 0.134)
BACK_CAP_SAG_TEXT_EXTENT = (0.0159, 0.0042, 0.0158, 0.0045)
BACK_CAP_SAG_LINE_LEFT = 0.01635
BACK_CAP_SAG_LINE_DROP = 0.00558
# The pin hole's leader comes in from the upper left, leaning
# PIN_LEADER_LEAN (dx per dy) off vertical along its radius, so it passes left
# of the 39.0's outside-arrow tail (x 262.1 at its row) and right of the front
# land length's head-end witness, whose arrows now stand inside
# (LAND_ARROWS_INSIDE: at a652 their tail ran to x 266.5 and left no straight
# way in).  a652
# printed the callout for (250.0, 222.0) at x 233.2-267.0, y 215.3-229.2 mm,
# its shoulder 232.33-269.16 mm at y 214.7.
PIN_X = _sheet_x(PIN_Z)
PIN_HOLE_CENTER = (PIN_X, PROFILE_AXIS_Y)
PIN_HOLE_TEXT_EXTENT = (0.01683, 0.00669, 0.01704, 0.00719)
PIN_HOLE_SHOULDER = (0.01767, 0.01916, 0.0073)  # left, right (the bend), drop
PIN_LEADER_LEAN = 0.31
PIN_SHOULDER_Y = 0.206
PIN_HOLE_BEND = (
    PIN_X - PIN_LEADER_LEAN * (PIN_SHOULDER_Y - PROFILE_AXIS_Y),
    PIN_SHOULDER_Y,
)
PIN_HOLE_TEXT_XY = (
    PIN_HOLE_BEND[0] - PIN_HOLE_SHOULDER[1],
    PIN_HOLE_BEND[1] + PIN_HOLE_SHOULDER[2],
)
# swDimensionArrowsSide_e (enums/swDimensionArrowsSide_e.md); read back after
# setting, as draw_cone_tip_block's proven _set_arrow_sides does (mha092-72ab).
DIM_ARROWS_INSIDE = 0
# Both land lengths stand their arrows inside, so no arrow tail reaches past
# a land end towards a neighbour whatever the spec does to the lands.  At a652
# SolidWorks put them outside: the front tail ran 6.35 mm right of the land's
# head end into the pin leader's path, and the back tail 6.35 mm left of its
# crown end, to within 2.25 mm of the (1.2)'s apex witness (1.65 once #858
# moves that end 0.6 mm crown-wards).
LAND_ARROWS_INSIDE = ("FrontJournalLen", "BackJournalLen")
# The 11.25 stands LEFT of its neck witness: at (0.340, 0.100) its line ran
# right to the text through the (242.2)'s front-apex witness at x 321.1
# (Main, round 4).  Left, it runs from the text to the neck witness under the
# 227.5's block's right end with nothing standing between.
NECK_LEN_XY = (0.284, 0.100)
# Rendered width and height of a two-place "Ø8.00 -0.01/-0.0x" callout block,
# measured on the 63468ee9 sheet.
DIAMETER_BLOCK_SIZE = (0.027, 0.014)
# The texts placed against a land ride with it: each keeps the offset from its
# land (or, for the front station, from its span's middle) at which leaf a652
# printed it clear, so a spec move of the lands carries text and witness
# together rather than closing the gap between them.
FRONT_LAND_LEN_TEXT_DX = 0.0013
BACK_LAND_LEN_TEXT_DX = -0.0012
FRONT_STATION_TEXT_DX = -0.0009
FRONT_LAND_LEN_Y = 0.188
BACK_LAND_LEN_Y = 0.143
FRONT_STATION_Y = 0.130


def land_keep(lands: Lands = LANDS) -> dict[str, tuple[float, float]]:
    """The land-borne texts' positions for ``lands`` ((head side, crown side)
    sheet x of the front and back lands)."""
    front, back = lands
    head_rear = _sheet_x(HEAD_REAR_Z)
    return {
        "FrontJournalLen": (_mid(front) + FRONT_LAND_LEN_TEXT_DX, FRONT_LAND_LEN_Y),
        # Below the shaft, clear of the back crown's witnesses.
        "BackJournalLen": (_mid(back) + BACK_LAND_LEN_TEXT_DX, BACK_LAND_LEN_Y),
        "FrontJournalFromHeadRear": (
            _mid((front[0], head_rear)) + FRONT_STATION_TEXT_DX,
            FRONT_STATION_Y,
        ),
    }


PRINCIPAL_KEEP = {
    **land_keep(),
    "FrontJournalDia": (FRONT_JOURNAL_DIA_X, 0.150),
    "BondZoneDia": BOND_ZONE_TEXT_XY,
    "BackJournalDia": (BACK_JOURNAL_TEXT_X, BACK_JOURNAL_DIA_Y),
    # The drum station stacks between the two land stations, its text left of
    # its own drum-end witness.  The back station's text moves left to clear
    # it; it stands 60 mm from the back land's head end, so no land move
    # reaches it.
    "DrumStationFromHeadRear": DRUM_STATION_TEXT_XY,
    "BackJournalFromHeadRear": (0.170, 0.115),
    # Left of its neck witness, clear of the (242.2)'s front-apex witness.
    "NeckLen": NECK_LEN_XY,
    "BackRimFromHeadRear": (0.205, 0.095),
    "OverallLen": (0.205, 0.080),
    # Under the part, left of the back crown (BACK_CAP_SAG_XY).
    "BackCapSagDim": BACK_CAP_SAG_XY,
    # Radial leader in from the upper left, 25° above the axis, over a crown
    # no witness rises from (BACK_CAP_R_TEXT_XY).
    "BackCapR": BACK_CAP_R_TEXT_XY,
    # R1a's collar pin hole (x 0.269) stands over the front land's stations,
    # so both its dimensions stand ABOVE the shaft: the station from the head
    # rear face in a row well over the Ø15 head, and the hole's leader leaning
    # in from the upper left, between that row's left arrow tail and the front
    # land length's head-end witness (PIN_HOLE_TEXT_XY).
    "PinStationFromHeadRear": (0.288, 0.207),
    "PinHoleDia": PIN_HOLE_TEXT_XY,
}
DETAIL_KEEP = {
    "HeadLen": (0.165, 0.201),
    "HeadCapR": (0.195, 0.262),
    "HeadCapSagDim": (0.205, 0.210),
    # Above the hole's centre line, so the leader drops onto the hole edge.
    "CrossHoleDia": (0.245, 0.256),
}
# The Ø15 head and the Ø10.5 neck are Front-plane circles, so they print
# where they show true: on an END view (Main's option C, 2026-09-25).  They
# fit nowhere else.  On the 1:1 profile the Ø10.5 has no x: its text must end
# left of the collar-pin station witness (x 0.3076, stacktop-dbe47ae3) while
# its witnesses must stay inside detail A's fence (x >= 0.300, c486b6e1).
# Detail A takes a moved dimension in no form (move, copy and a centre drop
# all refused, farm bisect neckbisect-ecef, run 20260925T134711864Z-47d629b0),
# and a hidden reference sketch's diameter never arrived in its import
# (84e55ff68, leaf neckref-84e5).  The end-on view that imported both as the
# old donor (824056ef9) therefore stays on the sheet as a real projected view.
#
# ASME third angle: *Front looks along -Z, from the +Z end.  The profile runs
# +Z to the LEFT (the back crown is its left end, x 0.0793), so this is the
# profile's LEFT view: left of it, on its row (the axis at the profile's y),
# at its 1:1 scale, and turned like the profile so model +X points down the
# sheet in both and +Y (towards the profile's viewer) points at the profile.
# From the back end every step grows towards the head, so the Ø8, Ø10.5 and
# Ø15 all show as visible circles; from the head end the Ø15 hides the neck.
END_CENTER = (0.047, PRINCIPAL_CENTER[1])
END_SCALE = SHEET_SCALE
VIEW_ANGLE = -math.pi / 2.0
# Both diameters print LEFT of the view, each text's shoulder running left
# from its circle-side (right) end: the Ø15 above-left, the Ø10.5 below-left,
# their leaders entering from the upper and lower left and crossing at the
# common centre as concentric diameters must.  The right side is fenced by the
# back crown's (1.2) apex extension line rising at x 78.9: with the Ø10.5
# up-right of the view (0.062, 0.188) the layout audit boxed its text to x 79.9
# and failed text-on-line (leaf neckc2-07af, 07afe186b).
END_KEEP = {
    "HeadDia": (0.030, 0.196),
    "NeckDia": (0.026, 0.158),
}
END_VIEW_LABEL = "integral-arbor end view"
# The sheet position tolerance for the end view's centre after placement.
END_CENTER_TOL_M = 1e-5
# _sheet_x's drift from the profile's real projection that is worth a warning.
PROFILE_DRIFT_WARN_M = 5e-5

# ---------------------------------------------------------------------------
# End-view ink audit
#
# The layout audit this module gates (_assert_no_text_on_line) compares text
# with lines and text with text, but no text with a view's model outline or an
# arrowhead, and the shared layout check boxes every dimension as a nominal
# 8 mm CollisionScope.NONE square (_drawing_common._dim_element), so it
# compares no dimension text at all.  So the end view's corner of the sheet
# audits its own ink before any COM work (cone-tip-block's
# sheet_ink_collisions, 287c5cf6a): the two diameters' texts against each
# other, the neighbouring profile callouts, every view's outline, every line
# and arrowhead standing in that corner, and the sheet border.
#
# Extents are (left, down, right, up) from the position the module commands,
# in sheet metres, as leaf neckc2-07af measured them on both diameters (the
# two agree to 0.1 mm):
# - the layout audit's text box, the box its text-on-line gate compares:
#   HeadDia [22.8,193.2]..[47.9,196.7] mm for (30.0, 196.0), NeckDia
#   [54.8,185.2]..[79.9,188.7] mm for (62.0, 188.0);
# - the printed text inside it: [28.1..40.6] and [60.1..72.6] mm;
# - the shoulder, 2.8 mm under the position, reaching 10.0 mm towards the
#   circle and 8.5 mm away from it: HeadDia's 21.5..40.0, NeckDia's 52.0..70.5.
END_DIA_AUDIT_EXTENT = (0.0072, 0.0028, 0.0179, 0.0007)
END_DIA_CORE_EXTENT = (0.0019, 0.0028, 0.0106, 0.0007)
END_DIA_SHOULDER_TOWARD = 0.0100
END_DIA_SHOULDER_AWAY = 0.0085
END_DIA_SHOULDER_DROP = 0.0028
# The profile's callouts in that corner, measured on the a652 sheet
# (BACK_CAP_R_TEXT_EXTENT, BACK_CAP_SAG_TEXT_EXTENT) and the back JOURNAL block
# right of its line (DIAMETER_BLOCK_SIZE).  Their lines come from
# profile_corner_ink: neckc2-07af measured the (1.2)'s apex extension at
# (78.9,171.0)->(78.9,215.4) mm for a text at y 220, which that model gives.
NEIGHBOUR_TEXT_EXTENTS = {
    "BackCapR": BACK_CAP_R_TEXT_EXTENT,
    "BackCapSagDim": BACK_CAP_SAG_TEXT_EXTENT,
    "BackJournalDia": (0.0010, 0.0075, 0.0270, 0.0075),
}
# Air an end-view text keeps: to a foreign line, and to any arrowhead tip
# (Main: 2 mm); to another text, a view's model outline and the inner border.
END_LINE_CLEARANCE = 0.0020
END_ARROW_CLEARANCE = 0.0020
END_TEXT_CLEARANCE = 0.0010
END_OUTLINE_CLEARANCE = 0.0010
# The landscape B sheet's inner border, read off the a1a694a6 render at
# 12.5-13.4 mm; the larger is taken.
SHEET_INNER_LEFT = 0.0134

InkBox = tuple[float, float, float, float]
InkLine = tuple[tuple[float, float], tuple[float, float]]
DIAMETERS = {"HeadDia": HEAD_DIA, "NeckDia": NECK_DIA}


def _ink_box(point: tuple[float, float], extent: tuple[float, float, float, float]) -> InkBox:
    left, down, right, up = extent
    return (point[0] - left, point[1] - down, point[0] + right, point[1] + up)


def _circle_box(center: tuple[float, float], radius: float) -> InkBox:
    return (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)


def end_view_text_boxes(
    keep: dict[str, tuple[float, float]] = END_KEEP,
    principal: dict[str, tuple[float, float]] = PRINCIPAL_KEEP,
) -> dict[str, InkBox]:
    """The end view's diameter texts (as the layout audit boxes them) and the
    profile callouts beside them."""
    boxes = {name: _ink_box(point, END_DIA_AUDIT_EXTENT) for name, point in keep.items()}
    for name, extent in NEIGHBOUR_TEXT_EXTENTS.items():
        boxes[name] = _ink_box(principal[name], extent)
    return boxes


def sheet_view_outlines(end_center: tuple[float, float] = END_CENTER) -> dict[str, InkBox]:
    """Each view's model outline: the end view's Ø15, the profile, detail A."""
    axis_y = PRINCIPAL_CENTER[1]
    head_r = HEAD_DIA / 2000.0
    return {
        "end view": _circle_box(end_center, head_r),
        "profile": (
            _sheet_x(BACK_APEX_Z),
            axis_y - head_r,
            _sheet_x(FRONT_APEX_Z),
            axis_y + head_r,
        ),
        "detail A": _circle_box(DETAIL_CENTER, DETAIL_RATIO * DETAIL_RADIUS_MM / 1000.0),
    }


def diameter_ink(
    text_xy: tuple[float, float], center: tuple[float, float], diameter: float
) -> tuple[InkLine, InkLine, InkLine, tuple[tuple[float, float], tuple[float, float]]]:
    """A circle diameter's shoulder, leader and through-line, and its two arrow tips.

    The shoulder runs under the text, its circle-side end where the leader
    leaves for the near arrow; the line runs on through the centre to the far
    arrow.
    """
    toward = 1.0 if text_xy[0] < center[0] else -1.0
    shoulder_y = text_xy[1] - END_DIA_SHOULDER_DROP
    start = (text_xy[0] + toward * END_DIA_SHOULDER_TOWARD, shoulder_y)
    far_end = (text_xy[0] - toward * END_DIA_SHOULDER_AWAY, shoulder_y)
    dx, dy = start[0] - center[0], start[1] - center[1]
    length = math.hypot(dx, dy)
    radius = diameter / 2000.0
    near = (center[0] + dx / length * radius, center[1] + dy / length * radius)
    far = (center[0] - dx / length * radius, center[1] - dy / length * radius)
    return (far_end, start), (start, near), (near, far), (near, far)


def sheet_corner_ink(
    keep: dict[str, tuple[float, float]] = END_KEEP,
    end_center: tuple[float, float] = END_CENTER,
    principal: dict[str, tuple[float, float]] = PRINCIPAL_KEEP,
) -> tuple[dict[str, InkLine], dict[str, tuple[float, float]]]:
    """The lines standing in the end view's corner, keyed by owner and run, and
    the end-view arrowhead tips."""
    corner = profile_ink(principal)
    _, sag = corner["BackCapSagDim"]
    _, crown = corner["BackCapR"]
    lines: dict[str, InkLine] = {
        "BackCapSagDim line": sag[0],
        "BackCapSagDim apex extension": sag[1],
        "BackCapSagDim root extension": sag[2],
        "BackCapR shoulder": crown[0],
        "BackCapR leader": crown[1],
    }
    arrows: dict[str, tuple[float, float]] = {}
    for name, xy in keep.items():
        shoulder, leader, through, tips = diameter_ink(xy, end_center, DIAMETERS[name])
        lines[f"{name} shoulder"] = shoulder
        lines[f"{name} leader"] = leader
        lines[f"{name} line"] = through
        arrows[f"{name} near arrow"], arrows[f"{name} far arrow"] = tips
    return lines, arrows


def _box_gap(a: InkBox, b: InkBox) -> float:
    """Air between two boxes along their clearer axis; negative when they overlap."""
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


def _line_meets_box(line: InkLine, box: InkBox) -> bool:
    """Liang-Barsky: whether any part of ``line`` lies inside ``box``."""
    (x0, y0), (x1, y1) = line
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - box[0]), (dx, box[2] - x0), (-dy, y0 - box[1]), (dy, box[3] - y0)):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        t = q / p
        if p < 0.0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def _grown(box: InkBox, by: float) -> InkBox:
    return (box[0] - by, box[1] - by, box[2] + by, box[3] + by)


def _in_box(point: tuple[float, float], box: InkBox) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _lines_cross(first: InkLine, second: InkLine) -> bool:
    """Whether two runs cross or touch (collinear overlaps included)."""
    (p, q), (r, s) = first, second
    d1, d2 = _cross(r, s, p), _cross(r, s, q)
    d3, d4 = _cross(p, q, r), _cross(p, q, s)
    if ((d1 > 0.0) != (d2 > 0.0)) and ((d3 > 0.0) != (d4 > 0.0)) and d1 and d2 and d3 and d4:
        return True
    return any(
        d == 0.0 and _in_box(point, _line_box(line))
        for d, point, line in ((d1, p, second), (d2, q, second), (d3, r, first), (d4, s, first))
    )


def _line_box(line: InkLine) -> InkBox:
    (x0, y0), (x1, y1) = line
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def end_view_ink_collisions(
    texts: dict[str, InkBox],
    outlines: dict[str, InkBox],
    lines: dict[str, InkLine],
    arrows: dict[str, tuple[float, float]] | None = None,
    *,
    audited: tuple[str, ...] = tuple(END_KEEP),
) -> list[str]:
    """Every ``audited`` text too near another text, an outline, a foreign line,
    an arrowhead or the sheet's inner border, and every one of its leader runs
    that crosses a foreign line.  A line keyed ``"<name> ..."`` is the text's
    own ink and is not foreign to it; every arrowhead, its own included, is."""
    findings: list[str] = []
    for name in audited:
        box = texts[name]
        for other, other_box in sorted(texts.items()):
            if other == name or (other in audited and other < name):
                continue
            gap = _box_gap(box, other_box)
            if gap < END_TEXT_CLEARANCE:
                findings.append(
                    f"text-on-text: {name!r} and {other!r} stand {gap * 1000.0:.2f} mm apart"
                )
        for view, outline in sorted(outlines.items()):
            gap = _box_gap(box, outline)
            if gap < END_OUTLINE_CLEARANCE:
                findings.append(
                    f"text-on-outline: {name!r} stands {gap * 1000.0:.2f} mm from the "
                    f"{view} outline"
                )
        for owner, line in sorted(lines.items()):
            if owner.split(" ")[0] == name:
                continue
            if _line_meets_box(line, _grown(box, END_LINE_CLEARANCE)):
                findings.append(
                    f"text-on-line: {owner} runs within {END_LINE_CLEARANCE * 1000.0:.1f} mm "
                    f"of {name!r}"
                )
        for tip_name, tip in sorted((arrows or {}).items()):
            if _in_box(tip, _grown(box, END_ARROW_CLEARANCE)):
                findings.append(
                    f"text-on-arrow: {tip_name} at ({tip[0] * 1000.0:.1f}, "
                    f"{tip[1] * 1000.0:.1f}) mm is within "
                    f"{END_ARROW_CLEARANCE * 1000.0:.1f} mm of {name!r}"
                )
        if box[0] - SHEET_INNER_LEFT < END_OUTLINE_CLEARANCE:
            findings.append(
                f"outside-border: {name!r} starts {(box[0] - SHEET_INNER_LEFT) * 1000.0:.2f} "
                "mm inside the sheet's inner border"
            )
        # A leader and its shoulder cross nothing; only the two through-lines
        # meet, at the common centre, as concentric diameters must.
        for run in ("shoulder", "leader"):
            own = lines.get(f"{name} {run}")
            if own is None:
                continue
            for owner, line in sorted(lines.items()):
                if owner.split(" ")[0] == name or not _lines_cross(own, line):
                    continue
                findings.append(f"leader-crosses-line: {name}'s {run} crosses {owner}")
    return findings


def assert_end_view_ink_clear() -> None:
    """Refuse an end-view placement whose own text collides, before any COM work."""
    lines, arrows = sheet_corner_ink()
    findings = end_view_ink_collisions(
        end_view_text_boxes(), sheet_view_outlines(), lines, arrows
    )
    if findings:
        raise RuntimeError(
            "pinion-arbor end-view ink collides:\n"
            + "\n".join(f"  - {finding}" for finding in findings)
        )
    _telemetry.debug("pinion-arbor end-view ink clear")


# ---------------------------------------------------------------------------
# Leaders against dimension and extension lines
#
# The sheet's rule (Main, neckc3-a652): a leader may not cross, touch or run
# along any dimension or extension line.  A T-junction counts (a leader's end
# on a line's interior, or a line's end on a leader), and so does a leader
# lying along a line: _drawing_leaders.segments_cross, whose only exemption is
# a shared endpoint.  A T is allowed only where LEADER_TOUCHING declares the
# pair with its reason; this sheet declares none.  The shared layout audit
# compares leaders only with leaders and views, so this sheet applies the rule
# itself, to its own annotations, until _drawing_leaders carries it.
#
# A leader-bearing annotation is every radial or diametric dimension (all its
# runs lead to a circle or arc) and every non-dimension annotation with ink.
# Every other dimension is linear: a dimension line and extension lines.
LEADER_DIMENSIONS = frozenset(
    {
        "PinHoleDia",
        "BackCapR",
        "HeadDia",
        "NeckDia",
        "CrossHoleDia",
        "HeadCapR",
        "FrontJournalDia",
        "BackJournalDia",
        "BondZoneDia",
    }
)
LEADER_TOUCHING: dict[frozenset[str], str] = {}
# Linear dimensions may meet only where the sheet says so.  Baseline
# dimensions from one face share their witness by design; each such sharing
# is named here, and it covers only strokes ON that witness: the two vertical
# extension lines lying along each other, or one dimension's line meeting the
# other's extension where it lies along its own.
SHARED_WITNESSES = {
    # Main's ruling b (neckc3-a652): the (1.2) drops along the (242.2)'s apex
    # witness and the 227.5's root witness.
    "back crown apex": frozenset({"BackCapSagDim", "OverallLen"}),
    "back crown root": frozenset({"BackCapSagDim", "BackRimFromHeadRear"}),
    # The stations under the shaft all run from the Ø15 head's rear face.
    "Ø15 head rear face": frozenset(
        {
            "FrontJournalFromHeadRear",
            "DrumStationFromHeadRear",
            "BackJournalFromHeadRear",
            "BackRimFromHeadRear",
            "NeckLen",
        }
    ),
    # The back land's length and its station both end at its head-side end.
    "back land head-side end": frozenset({"BackJournalLen", "BackJournalFromHeadRear"}),
    # Detail A's 10.5 and (3.0) both end at the head's front face.
    "head front face": frozenset({"HeadLen", "HeadCapSagDim"}),
}
# Report-only crossings (Main, round 4): the Ø10.5 neck's extension line,
# dropping to the 11.25 under the other stations, crosses their dimension
# lines.  Keyed (extension owner, dimension-line owner); any other crossing,
# or any other stroke of these pairs, still fails.
EXPECTED_CROSSINGS = {
    ("NeckLen", "FrontJournalFromHeadRear"): "the neck witness drops through the front station",
    ("NeckLen", "DrumStationFromHeadRear"): "the neck witness drops through the drum station",
    ("NeckLen", "BackJournalFromHeadRear"): "the neck witness drops through the back station",
}
# A stroke within this of vertical or horizontal is an extension line or a
# dimension line of these horizontal dimensions.
AXIS_ALIGNED_M = 1e-4
LineRole = str  # "leader" or "linear"
SheetInk = dict[str, tuple[LineRole, list[InkLine]]]

# Linear dimension ink, measured on the a652 sheet: a one-line value's line
# prints 2.8 mm under its position, a two-line block's 5.5-5.6 mm; extension
# lines start 1.0 mm off the feature and run 0.9-1.1 mm past the line; an
# outside arrow's arrowhead and tail run 6.3-6.4 mm past its extension line.
# SolidWorks put the arrows inside every long station and outside the land
# lengths, the 39.0 and the (1.2); a line runs on under a text standing outside its
# extensions, to 1.0-1.3 mm past the text's far end (DrumStation, (1.2),
# the 11.25 at a652).
ONE_LINE_DROP = 0.0028
TWO_LINE_DROP = 0.0056
PIN_STATION_LINE_DROP = 0.0055
DRUM_STATION_LINE_DROP = 0.00555
EXTENSION_GAP = 0.0010
EXTENSION_OVERSHOOT = 0.0010
OUTSIDE_ARROW_RUN = 0.00635
ARROWS_OUTSIDE = frozenset(
    {"BackJournalLen", "FrontJournalLen", "PinStationFromHeadRear", "BackCapSagDim"}
)
DRUM_STATION_LINE_LEFT = 0.01675
NECK_LEN_LINE_REACH = 0.00705


def _fmt_line(line: InkLine) -> str:
    (x0, y0), (x1, y1) = line
    return f"({x0 * 1000:.1f},{y0 * 1000:.1f})->({x1 * 1000:.1f},{y1 * 1000:.1f})mm"


def _vertical(line: InkLine) -> bool:
    return abs(line[0][0] - line[1][0]) <= AXIS_ALIGNED_M


def _horizontal(line: InkLine) -> bool:
    return abs(line[0][1] - line[1][1]) <= AXIS_ALIGNED_M


def _along(first: InkLine, second: InkLine) -> bool:
    """Two vertical strokes on one x sharing some of their length."""
    if not (_vertical(first) and _vertical(second)):
        return False
    if abs(first[0][0] - second[0][0]) > _drawing_leaders.COLLINEAR_TOLERANCE:
        return False
    low = max(min(first[0][1], first[1][1]), min(second[0][1], second[1][1]))
    high = min(max(first[0][1], first[1][1]), max(second[0][1], second[1][1]))
    return high - low > _drawing_leaders.COLLINEAR_TOLERANCE


def _on_shared_witness(
    first: InkLine, second: InkLine, first_runs: list[InkLine], second_runs: list[InkLine]
) -> bool:
    """Whether the meeting of two strokes lies on a witness both dimensions
    share: the extensions themselves, or one's stroke meeting the other's
    extension where it lies along one of its own."""
    return (
        _along(first, second)
        or any(_along(second, own) for own in first_runs)
        or any(_along(first, own) for own in second_runs)
    )


def _expected_crossing(
    first: str, a: InkLine, second: str, b: InkLine
) -> str | None:
    for (extension, line), reason in EXPECTED_CROSSINGS.items():
        if (first, second) == (extension, line) and _vertical(a) and _horizontal(b):
            return reason
        if (second, first) == (extension, line) and _vertical(b) and _horizontal(a):
            return reason
    return None


def leader_line_findings(ink: SheetInk) -> list[str]:
    """Every leader stroke meeting a linear dimension's stroke, and every
    meeting of two linear dimensions the sheet does not name."""
    findings: list[str] = []
    leaders = {name: runs for name, (role, runs) in ink.items() if role == "leader"}
    linear = {name: runs for name, (role, runs) in ink.items() if role == "linear"}
    for name, runs in sorted(leaders.items()):
        for other, lines in sorted(linear.items()):
            if other == name:
                continue
            touching = (
                "allowed" if frozenset({name, other}) in LEADER_TOUCHING else "crossing"
            )
            for run in runs:
                for line in lines:
                    if _drawing_leaders.segments_cross(run, line, touching=touching):
                        findings.append(
                            f"leader-crossing: {name}'s leader {_fmt_line(run)} meets "
                            f"{other}'s line {_fmt_line(line)}"
                        )
    names = sorted(linear)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            shared = any({first, second} <= group for group in SHARED_WITNESSES.values())
            for a in linear[first]:
                for b in linear[second]:
                    if not _drawing_leaders.segments_cross(a, b):
                        continue
                    if shared and _on_shared_witness(a, b, linear[first], linear[second]):
                        continue
                    if _expected_crossing(first, a, second, b):
                        continue
                    findings.append(
                        f"line-crossing: {first}'s {_fmt_line(a)} meets "
                        f"{second}'s {_fmt_line(b)}"
                    )
    return findings


def expected_crossings_found(ink: SheetInk) -> list[str]:
    """The report-only crossings present in ``ink``, for the leaf log."""
    linear = {name: runs for name, (role, runs) in ink.items() if role == "linear"}
    found = []
    for (extension, line), reason in sorted(EXPECTED_CROSSINGS.items()):
        if any(
            _drawing_leaders.segments_cross(a, b)
            for a in linear.get(extension, ())
            for b in linear.get(line, ())
            if _vertical(a) and _horizontal(b)
        ):
            found.append(f"{extension} x {line}: {reason}")
    return found


def _linear_ink(
    text_xy: tuple[float, float],
    line_drop: float,
    first: tuple[float, float],
    second: tuple[float, float],
    *,
    arrows_inside: bool,
    text_reach: tuple[float, float] | None = None,
) -> list[InkLine]:
    """A horizontal dimension's line and its two vertical extension lines.

    ``text_reach`` = (left, right): how far the line runs either side of a
    text standing outside the extensions.
    """
    row = text_xy[1] - line_drop
    lo, hi = sorted((first[0], second[0]))
    if not arrows_inside:
        lo, hi = lo - OUTSIDE_ARROW_RUN, hi + OUTSIDE_ARROW_RUN
    if text_reach is not None:
        lo = min(lo, text_xy[0] - text_reach[0])
        hi = max(hi, text_xy[0] + text_reach[1])
    lines: list[InkLine] = [((lo, row), (hi, row))]
    for x, y in (first, second):
        sign = 1.0 if row > y else -1.0
        lines.append(((x, y + sign * EXTENSION_GAP), (x, row + sign * EXTENSION_OVERSHOOT)))
    return lines


def _radial_leader_ink(
    text_xy: tuple[float, float],
    shoulder: tuple[float, float, float],
    center: tuple[float, float],
    radius: float,
    *,
    through: str,
) -> tuple[list[InkLine], tuple[float, float]]:
    """A radius or diameter leader: the shoulder under its text, the run from
    the shoulder's circle-side end along the radius to the arrow tip, and the
    line on from the tip to the centre (``through="center"``, a radius) or to
    the far side (``through="far"``, a diameter).  Returns the runs and the
    tip."""
    left, right, drop = shoulder
    bend = (text_xy[0] + right, text_xy[1] - drop)
    dx, dy = bend[0] - center[0], bend[1] - center[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    tip = (center[0] + ux * radius, center[1] + uy * radius)
    end = center if through == "center" else (center[0] - ux * radius, center[1] - uy * radius)
    return [((text_xy[0] - left, bend[1]), bend), (bend, tip), (tip, end)], tip


def profile_ink(
    keep: dict[str, tuple[float, float]] = PRINCIPAL_KEEP,
    arrows_outside: frozenset[str] = ARROWS_OUTSIDE - frozenset(LAND_ARROWS_INSIDE),
    lands: Lands = LANDS,
) -> SheetInk:
    """The profile's station dimensions and its two tight leaders (the pin
    hole's Ø1.59 and the back crown's SR7.3), modelled from the commanded
    positions, with the lands' ends at ``lands``."""
    axis = PROFILE_AXIS_Y
    land = SHAFT_DIA / 2000.0
    head = HEAD_DIA / 2000.0
    head_rear = _sheet_x(HEAD_REAR_Z)
    apex = _sheet_x(BACK_APEX_Z)
    root = _sheet_x(BACK_APEX_Z - BACK_CAP_SAG)
    front_land, back_land = (sorted(ends) for ends in lands)

    def linear(name, first, second, drop, text_reach=None):
        def flank(x: float, radius: float) -> tuple[float, float]:
            return (x, axis + radius if keep[name][1] > axis else axis - radius)

        return (
            "linear",
            _linear_ink(
                keep[name],
                drop,
                flank(*first),
                flank(*second),
                arrows_inside=name not in arrows_outside,
                text_reach=text_reach,
            ),
        )

    pin_runs, _ = _radial_leader_ink(
        keep["PinHoleDia"], PIN_HOLE_SHOULDER, PIN_HOLE_CENTER, PIN_HOLE_DIA / 2000.0, through="far"
    )
    crown_runs, _ = _radial_leader_ink(
        keep["BackCapR"], BACK_CAP_R_SHOULDER, BACK_CAP_CENTER, BACK_CAP_R_M, through="center"
    )
    neck = _sheet_x(NECK_END_Z)
    return {
        "PinHoleDia": ("leader", pin_runs),
        "BackCapR": ("leader", crown_runs),
        "PinStationFromHeadRear": linear(
            "PinStationFromHeadRear", (PIN_X, 0.0), (head_rear, head), PIN_STATION_LINE_DROP
        ),
        "FrontJournalLen": linear(
            "FrontJournalLen", (front_land[0], land), (front_land[1], land), ONE_LINE_DROP
        ),
        "FrontJournalFromHeadRear": linear(
            "FrontJournalFromHeadRear", (front_land[1], land), (head_rear, head), ONE_LINE_DROP
        ),
        "DrumStationFromHeadRear": linear(
            "DrumStationFromHeadRear",
            (DRUM_STATION_WITNESS_X, land),
            (head_rear, head),
            DRUM_STATION_LINE_DROP,
            text_reach=(DRUM_STATION_LINE_LEFT, 0.0),
        ),
        "BackJournalFromHeadRear": linear(
            "BackJournalFromHeadRear", (back_land[1], land), (head_rear, head), ONE_LINE_DROP
        ),
        "NeckLen": linear(
            "NeckLen",
            (neck, NECK_DIA / 2000.0),
            (head_rear, head),
            ONE_LINE_DROP,
            text_reach=(NECK_LEN_LINE_REACH, NECK_LEN_LINE_REACH),
        ),
        "BackJournalLen": linear(
            "BackJournalLen", (back_land[0], land), (back_land[1], land), ONE_LINE_DROP
        ),
        "BackCapSagDim": linear(
            "BackCapSagDim",
            (apex, 0.0),
            (root, land),
            BACK_CAP_SAG_LINE_DROP,
            text_reach=(BACK_CAP_SAG_LINE_LEFT, 0.0),
        ),
        "OverallLen": linear(
            "OverallLen", (apex, 0.0), (_sheet_x(FRONT_APEX_Z), 0.0), TWO_LINE_DROP
        ),
        "BackRimFromHeadRear": linear(
            "BackRimFromHeadRear", (root, land), (head_rear, head), TWO_LINE_DROP
        ),
    }


def back_crown_landing_problems(
    center: tuple[float, float],
    landing: tuple[float, float],
    *,
    radius: float = BACK_CAP_R_M,
    tol: float = 5e-5,
) -> list[str]:
    """Why a radius leader's landing is not on the back crown: off the SR7.3's
    radius at sheet scale, or outside the arc between the Ø8 flanks."""
    problems = []
    reach = math.dist(center, landing)
    if abs(reach - radius) > tol:
        problems.append(
            f"lands {reach * 1000:.2f} mm from the centre, not on the "
            f"{radius * 1000:.2f} mm radius"
        )
    angle = math.degrees(math.atan2(landing[1] - center[1], center[0] - landing[0]))
    if abs(angle) >= BACK_CAP_HALF_ANGLE_DEG:
        problems.append(
            f"lands {angle:.1f}° off the axis, outside the crown's arc "
            f"(half-angle {BACK_CAP_HALF_ANGLE_DEG:.1f}°)"
        )
    return problems


def assert_profile_leaders_clear() -> None:
    """Refuse a modelled leader or station that meets a line it may not, or an
    SR7.3 that misses the crown, before any COM work."""
    problems = [
        *leader_line_findings(profile_ink()),
        *(
            f"SR7.3 {problem}"
            for problem in back_crown_landing_problems(BACK_CAP_CENTER, BACK_CAP_R_LANDING)
        ),
    ]
    if problems:
        raise RuntimeError(
            "pinion-arbor profile leaders collide:\n"
            + "\n".join(f"  - {problem}" for problem in problems)
        )
    _telemetry.debug("pinion-arbor profile leaders clear")

DIMENSION_CALLOUTS = {
    # One name for the axial datum every station runs from (Fable m1): the
    # head end has two shoulders, Ø8-Ø10.5 and Ø10.5-Ø15.
    # <MOD-DIAM> carries its own leading gap, so no space before it.
    "BackRimFromHeadRear": f"FROM BACK CROWN ROOT TO<MOD-DIAM>{HEAD_DIA:.0f} HEAD REAR FACE",
    "DrumStationFromHeadRear": "DRUM STATION",
    "OverallLen": "OVERALL",
    "BackCapSagDim": "BACK CROWN",
    "CrossHoleDia": CROSS_HOLE_CALLOUT,
    "FrontJournalDia": "JOURNAL",
    "BackJournalDia": "JOURNAL",
    "BondZoneDia": "BOND ZONE",
    "PinStationFromHeadRear": "COLLAR PIN",
    "PinHoleDia": PIN_HOLE_CALLOUT,
}
# The turning axis runs the full part and this far past each crown.
AXIS_OVERSHOOT_MM = 3.0


def _orient_like_profile(view: Any, *, label: str) -> None:
    """Turn a view so model +X points down the sheet, as on the profile."""
    native = _early_bound(view, "IView")
    native.Angle = VIEW_ANGLE
    if abs(math.remainder(float(native.Angle) - VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError(f"failed to orient the {label}")


def _place_end_view(adapter: Any) -> Any:
    """Place the profile's third-angle left view with its axis on END_CENTER.

    The view is placed on its geometry's centre, which for the end-on arbor is
    the turning axis; the turn and any residual offset are measured, not
    assumed, and a view still off END_CENTER after one correction fails loud.
    """
    draw = adapter.currentModel
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=END_SCALE)
    _orient_like_profile(end, label=END_VIEW_LABEL)
    draw.EditRebuild3()
    center = model_point_in_view(adapter, end, (0.0, 0.0, 0.0), label="end view axis")
    if math.dist(center, END_CENTER) > END_CENTER_TOL_M:
        native = _early_bound(end, "IView")
        position = tuple(float(value) for value in native.Position)
        target = [position[axis] + END_CENTER[axis] - center[axis] for axis in range(2)]
        if not native.SetViewPosition(double_array(target), False):
            raise RuntimeError(f"failed to centre the {END_VIEW_LABEL}")
        draw.EditRebuild3()
        center = model_point_in_view(adapter, end, (0.0, 0.0, 0.0), label="end view axis")
    if math.dist(center, END_CENTER) > END_CENTER_TOL_M:
        raise RuntimeError(
            f"{END_VIEW_LABEL} axis sits at ({center[0] * 1000:.2f}, "
            f"{center[1] * 1000:.2f}) mm, not on END_CENTER"
        )
    return end


def end_view_projection_problems(
    end: dict[str, tuple[float, float]],
    profile: dict[str, tuple[float, float]],
    *,
    radius: float,
    tol: float = END_CENTER_TOL_M,
) -> list[str]:
    """Why the end view is not the profile's third-angle left view, if it is not.

    ``end`` holds the end view's sheet points for the model origin (``"axis"``),
    ``(radius, 0, 0)`` (``"+x"``) and ``(0, radius, 0)`` (``"+y"``); ``profile``
    the profile's for the origin (``"axis"``), ``(radius, 0, 0)`` (``"+x"``)
    and the back-crown apex on the axis (``"left end"``).  Both views are 1:1.
    """
    problems = []
    axis = end["axis"]
    if abs(axis[1] - profile["axis"][1]) > tol:
        problems.append(
            f"axis at y {axis[1] * 1000:.2f} mm, off the profile's row "
            f"(y {profile['axis'][1] * 1000:.2f} mm)"
        )
    if axis[0] >= profile["left end"][0]:
        problems.append("not left of the profile's +Z (back-crown) end")
    for key, want in (("+x", (0.0, -radius)), ("+y", (radius, 0.0))):
        got = (end[key][0] - axis[0], end[key][1] - axis[1])
        if math.dist(got, want) > tol:
            problems.append(
                f"model {key} maps to ({got[0] * 1000:.2f}, {got[1] * 1000:.2f}) mm, "
                f"want ({want[0] * 1000:.2f}, {want[1] * 1000:.2f})"
            )
    profile_x = (
        profile["+x"][0] - profile["axis"][0],
        profile["+x"][1] - profile["axis"][1],
    )
    if math.dist(profile_x, (0.0, -radius)) > tol:
        problems.append(
            f"the profile maps model +x to ({profile_x[0] * 1000:.2f}, "
            f"{profile_x[1] * 1000:.2f}) mm, not straight down"
        )
    return problems


def _assert_end_view_projects_the_profile(adapter: Any, end: Any, principal: Any) -> None:
    radius = HEAD_DIA / 2000.0
    end_points = {
        key: model_point_in_view(adapter, end, xyz, label=f"end view {key}")
        for key, xyz in (
            ("axis", (0.0, 0.0, 0.0)),
            ("+x", (radius, 0.0, 0.0)),
            ("+y", (0.0, radius, 0.0)),
        )
    }
    profile_points = {
        key: model_point_in_view(adapter, principal, xyz, label=f"profile {key}")
        for key, xyz in (
            ("axis", (0.0, 0.0, 0.0)),
            ("+x", (radius, 0.0, 0.0)),
            ("left end", (0.0, 0.0, BACK_APEX_Z / 1000.0)),
        )
    }
    problems = end_view_projection_problems(end_points, profile_points, radius=radius)
    if problems:
        raise RuntimeError(
            f"pinion-arbor: the {END_VIEW_LABEL} is not the profile's left view: "
            + "; ".join(problems)
        )
    _telemetry.success(
        f"pinion-arbor: {END_VIEW_LABEL} projects the profile's +Z end on its row, axis at "
        f"({end_points['axis'][0] * 1000:.2f}, {end_points['axis'][1] * 1000:.2f}) mm"
    )
    # Every derived profile placement reads _sheet_x: say how far it sits
    # from the real projection, so a moved view origin is visible in the log.
    drift = profile_points["left end"][0] - _sheet_x(BACK_APEX_Z)
    message = (
        f"pinion-arbor: the profile's back-crown apex projects to x "
        f"{profile_points['left end'][0] * 1000:.2f} mm, _sheet_x "
        f"{_sheet_x(BACK_APEX_Z) * 1000:.2f} mm ({drift * 1000:+.2f} mm)"
    )
    if abs(drift) > PROFILE_DRIFT_WARN_M:
        _telemetry.warn(message)
    else:
        _telemetry.info(message)


def end_view_owner_problems(
    names_by_view: dict[str, list[str]], end_name: str
) -> list[str]:
    """Each end-view diameter must print once, on the end view, and nowhere else."""
    problems = []
    for name in END_KEEP:
        owners = [view for view, names in names_by_view.items() for item in names if item == name]
        if owners != [end_name]:
            problems.append(f"{name} printed on {owners}, want [{end_name!r}]")
    return problems


def _assert_end_view_owns_its_diameters(adapter: Any, end: Any) -> None:
    names_by_view = {
        view_name(adapter, view): sorted(
            dimension_name(adapter, annotation)
            for annotation in (
                _early_bound(item, "IAnnotation")
                for item in (_early_bound(view, "IView").GetAnnotations() or ())
            )
            if int(annotation.GetType()) == _SW_DISPLAY_DIMENSION
        )
        for view in iter_views(adapter)
    }
    end_name = view_name(adapter, end)
    _telemetry.info(
        "pinion-arbor dimensions by view: "
        + "; ".join(f"{view}: {names}" for view, names in names_by_view.items())
    )
    problems = end_view_owner_problems(names_by_view, end_name)
    if problems:
        raise RuntimeError("pinion-arbor end-view diameters: " + "; ".join(problems))
    _telemetry.success(f"pinion-arbor: {sorted(END_KEEP)} print on {end_name} only")


def _head_detail(adapter: Any, parent_view: Any) -> Any:
    """Create an enlarged native detail of the crowded turned head."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent_view, "IView")
    if not drawing.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError("failed to activate integral-arbor detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        parent_view,
        (0.0, 0.0, HEAD_CENTER_Z / 1000.0),
        label="integral-arbor head detail centre",
    )
    radius = DETAIL_RADIUS_MM / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(
            point.MultiplyTransform(transform), "IMathPoint"
        )
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create integral-arbor detail fence")
    detail = drawing.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,
        *DETAIL_SCALE,
        "A",
        1,
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create integral-arbor head detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("integral-arbor head detail has invalid bounds")
    target = [
        position[axis]
        + DETAIL_CENTER[axis]
        - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position integral-arbor head detail")
    draw.EditRebuild3()
    return detail


def _add_turning_axis(adapter: Any, view: Any) -> None:
    """Draw one centreline over the whole turned axis.

    The journal split lines cut the Ø8 cylinder into five faces, so a
    face-derived ``InsertCenterLine2`` would cover a single zone.  The axis is
    instead a view-sketch centreline between two model points on it, created
    direct-to-database so screen-space inference cannot snap an end onto the
    crown apex.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the integral-arbor profile for its axis")
    draw.ClearSelection2(True)
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    front_z = HEAD_FRONT_Z - HEAD_CAP_SAG - AXIS_OVERSHOOT_MM
    points = []
    for z in (front_z, front_z + OVERALL_LEN + 2.0 * AXIS_OVERSHOOT_MM):
        x, y = model_point_in_view(
            adapter, view, (0.0, 0.0, z / 1000.0), label="integral-arbor axis end"
        )
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if segment is None:
        raise RuntimeError("failed to create the integral-arbor turning axis")
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("integral-arbor turning axis colour did not persist")
    draw.ClearSelection2(True)
    draw.EditRebuild3()


@dataclass(frozen=True)
class WitnessCandidate:
    """One line of a reference sketch, as it projects into the profile."""

    name: str
    length_mm: float
    construction: bool
    ends: Span
    segment: Any = field(compare=False, repr=False)

    def describe(self) -> str:
        (x0, y0), (x1, y1) = self.ends
        return (
            f"{self.name} {self.length_mm:.3f} mm construction={self.construction} "
            f"({x0 * 1000:.2f},{y0 * 1000:.2f})-({x1 * 1000:.2f},{y1 * 1000:.2f}) mm"
        )


def _same_ends(first: Span, second: Span, *, tol: float = WITNESS_END_TOL_M) -> bool:
    """Two segments share both sheet endpoints, in either order."""
    forward = all(math.dist(a, b) <= tol for a, b in zip(first, second))
    backward = all(math.dist(a, b) <= tol for a, b in zip(first, reversed(second)))
    return forward or backward


def matching_witnesses(
    candidates: list[WitnessCandidate], expected_ends: Span, expected_len_mm: float
) -> list[WitnessCandidate]:
    """The candidates that ARE the witness: construction, its length, its ends."""
    return [
        candidate
        for candidate in candidates
        if candidate.construction
        and abs(candidate.length_mm - expected_len_mm) <= REFERENCE_WITNESS_LEN_TOL
        and _same_ends(candidate.ends, expected_ends)
    ]


def _reference_sketch(view: Any, sketch_name: str) -> tuple[Any, int]:
    """The part's own reference sketch behind ``view``, and its part-level
    visibility (swVisibilityState_e: 1 hidden, 2 shown) for the log."""
    referenced = _early_bound(view, "IView").ReferencedDocument
    if referenced is None:
        raise RuntimeError(f"{sketch_name}: the profile view references no document")
    raw = _early_bound(referenced, "IPartDoc").FeatureByName(sketch_name)
    if raw is None:
        raise RuntimeError(f"{sketch_name}: no such feature in the arbor part")
    feature = _early_bound(raw, "IFeature")
    return _early_bound(feature.GetSpecificFeature2(), "ISketch"), int(feature.Visible)


def _sketch_line_model_ends(
    adapter: Any, sketch: Any, segment: Any
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """A sketch line's two endpoints in model space (m), through the sketch's
    own transform rather than an assumed plane orientation."""
    line = _early_bound(segment, "ISketchLine")
    to_sketch = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    to_model = _early_bound(to_sketch.Inverse(), "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    ends = []
    for accessor in ("GetStartPoint2", "GetEndPoint2"):
        point = _early_bound(adapter._get_attr_or_call(line, accessor), "ISketchPoint")
        xyz = [float(adapter._get_attr_or_call(point, axis)) for axis in ("X", "Y", "Z")]
        sketch_point = _early_bound(utility.CreatePoint(double_array(xyz)), "IMathPoint")
        model = _early_bound(sketch_point.MultiplyTransform(to_model), "IMathPoint")
        ends.append(tuple(float(value) for value in model.ArrayData)[:3])
    return ends[0], ends[1]


def _witness_candidates(
    adapter: Any, view: Any, sketch_name: str
) -> tuple[list[WitnessCandidate], int]:
    """Every line of the reference sketch, projected into ``view``, and the
    sketch's part-level visibility."""
    sketch, visible = _reference_sketch(view, sketch_name)
    candidates = []
    for raw in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw, "ISketchSegment")
        if int(segment.GetType()) != SW_SKETCH_LINE:
            continue
        ends = tuple(
            model_point_in_view(adapter, view, xyz, label=f"{sketch_name} line end")
            for xyz in _sketch_line_model_ends(adapter, sketch, segment)
        )
        candidates.append(
            WitnessCandidate(
                name=str(segment.GetName()),
                length_mm=float(segment.GetLength()) * 1000.0,
                construction=bool(segment.ConstructionGeometry),
                ends=ends,
                segment=segment,
            )
        )
    return candidates, visible


def _selection_problem(draw: Any, witness: WitnessCandidate) -> str | None:
    """None when exactly ``witness`` is selected; otherwise what is."""
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    count = int(manager.GetSelectedObjectCount2(-1))
    if count != 1:
        return f"{count} objects selected"
    kind = int(manager.GetSelectedObjectType3(1, -1))
    if kind != SW_SEL_EXT_SKETCH_SEGS:
        return f"selection is type {kind}"
    # Identify the selection by its own name, length and construction flag,
    # not its sketch's name: an ISketch is not an IFeature dispatch, so
    # rebinding it reads another member (7885c0d9 got a matrix for ``Name``).
    segment = _early_bound(manager.GetSelectedObject6(1, -1), "ISketchSegment")
    name = str(segment.GetName())
    length = float(segment.GetLength()) * 1000.0
    construction = bool(segment.ConstructionGeometry)
    if (
        name != witness.name
        or abs(length - witness.length_mm) > REFERENCE_WITNESS_LEN_TOL
        or not construction
    ):
        return f"selection is {name} ({length:.3f} mm, construction={construction})"
    return None


def _select_witness(adapter: Any, view: Any, sketch_name: str, witness: WitnessCandidate) -> str:
    """Select exactly ``witness`` in ``view`` by identity, never by a screen pick.

    First the part's own segment with the view in its ISelectData (the
    documented way to select a model entity in a drawing view, as the arbor
    pedestal's dimensions do); then its qualified name through the view, the
    form model features are selected by (_drawing_common._select_model_feature).
    Every attempt is checked against the witness and logged.
    """
    draw = adapter.currentModel
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    qualified = (
        f"{witness.name}@{sketch_name}@{_drawing_component_name(adapter, view)}"
        f"@{view_name(adapter, view)}"
    )

    def select_in_view() -> bool:
        data = manager.CreateSelectData()
        data.View = view
        return bool(_early_bound(witness.segment, "ISketchSegment").Select4(False, data))

    def select_by_name() -> bool:
        return bool(
            draw.Extension.SelectByID2(
                qualified, "EXTSKETCHSEGMENT", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
            )
        )

    attempts = []
    for method, select in (
        ("Select4 in view", select_in_view),
        (f"SelectByID2 {qualified!r}", select_by_name),
    ):
        draw.ClearSelection2(True)
        returned = select()
        problem = _selection_problem(draw, witness) if returned else "returned False"
        attempts.append(f"{method}: {problem or 'OK'}")
        _telemetry.debug(
            f"pinion-arbor: {sketch_name} witness {witness.name} via {method}: "
            f"returned={returned}, {problem or 'selected exactly the witness'}"
        )
        if problem is None:
            return method
        draw.ClearSelection2(True)
    raise RuntimeError(
        f"{sketch_name} witness {witness.describe()} could not be selected by "
        f"identity: {'; '.join(attempts)}"
    )


def _blacken_reference_witnesses(adapter: Any, view: Any) -> dict[str, Span]:
    """Draw each reference sketch's flank witness in the outline's black.

    The witness is chosen by identity: the part's own reference sketch is
    read, its lines are projected into the view, and exactly one must be a
    construction line of the witness's length on the witness's two sheet
    endpoints.  No screen pick: on the 56fa631bc leaf a SelectByID2 at the
    witness's midpoint returned the 227.5 mm BackRimReference axis (Line1)
    instead of the 1 mm drum-station witness.

    Returns each witness's sheet endpoints for the exported-raster check.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    label = view_name(adapter, view)
    flank_x = SHAFT_DIA / 2000.0
    spans: dict[str, Span] = {}
    with _telemetry.span(
        "drawing.blacken_reference_witnesses", view=label, witnesses=len(REFERENCE_WITNESSES)
    ) as span:
        if not drawing.ActivateView(label):
            raise RuntimeError("failed to activate the integral-arbor profile for its witnesses")
        candidates_seen = 0
        for sketch_name, (z0, z1) in REFERENCE_WITNESSES.items():
            ends = tuple(
                model_point_in_view(
                    adapter, view, (flank_x, 0.0, z / 1000.0), label=f"{sketch_name} witness end"
                )
                for z in (z0, z1)
            )
            candidates, visible = _witness_candidates(adapter, view, sketch_name)
            candidates_seen += len(candidates)
            for candidate in candidates:
                _telemetry.debug(f"pinion-arbor: {sketch_name} candidate {candidate.describe()}")
            matches = matching_witnesses(candidates, ends, z1 - z0)
            if len(matches) != 1:
                (x0, y0), (x1, y1) = ends
                raise RuntimeError(
                    f"{sketch_name} (part visibility {visible}): {len(matches)} of "
                    f"{len(candidates)} sketch lines match "
                    f"its {z1 - z0:.3f} mm construction witness at "
                    f"({x0 * 1000:.2f},{y0 * 1000:.2f})-({x1 * 1000:.2f},{y1 * 1000:.2f}) mm; "
                    "candidates: " + "; ".join(candidate.describe() for candidate in candidates)
                )
            witness = matches[0]
            method = _select_witness(adapter, view, sketch_name, witness)
            drawing.SetLineColor(REFERENCE_WITNESS_COLOR)
            draw.ClearSelection2(True)
            spans[sketch_name] = ends
            mid = ((ends[0][0] + ends[1][0]) / 2.0, (ends[0][1] + ends[1][1]) / 2.0)
            _telemetry.info(
                f"pinion-arbor: {sketch_name} flank witness {witness.name} drawn black at "
                f"sheet ({mid[0] * 1000:.1f}, {mid[1] * 1000:.1f}) mm, selected by {method} "
                f"(part visibility {visible})",
                sketch=sketch_name,
            )
        span.set_attribute("candidates", candidates_seen)
        span.set_attribute("blackened", len(spans))
        draw.EditRebuild3()
    return spans


def _broken_outline_columns(
    raster: Any,
    spans: dict[str, tuple[tuple[float, float], tuple[float, float]]],
    sheet_size: tuple[float, float],
) -> dict[str, list[int]]:
    """Return, per witness, the raster columns where the outline is not dark."""
    gray = raster.convert("L")
    scale = gray.width / sheet_size[0]
    broken = {}
    for name, ((x0, y), (x1, _)) in spans.items():
        row = round((sheet_size[1] - y) * scale)
        rows = range(row - OUTLINE_SEARCH_ROWS, row + OUTLINE_SEARCH_ROWS + 1)
        columns = range(round(min(x0, x1) * scale), round(max(x0, x1) * scale) + 1)
        broken[name] = [
            column
            for column in columns
            if sum(gray.getpixel((column, r)) <= OUTLINE_DARK_MAX for r in rows)
            < OUTLINE_CORE_ROWS
        ]
    return {name: columns for name, columns in broken.items() if columns}


def _assert_outline_unbroken(
    png: Any,
    spans: dict[str, tuple[tuple[float, float], tuple[float, float]]],
    sheet_size: tuple[float, float],
) -> None:
    from PIL import Image

    with Image.open(png) as raster:
        broken = _broken_outline_columns(raster, spans, sheet_size)
    if broken:
        detail = "; ".join(
            f"{name}: {len(columns)} column(s) from x={columns[0]} px"
            for name, columns in broken.items()
        )
        raise RuntimeError(f"pinion-arbor: Ø8 outline broken over reference witness: {detail}")
    _telemetry.info(
        f"pinion-arbor: Ø8 outline unbroken over {len(spans)} reference witnesses",
        witnesses=len(spans),
    )


def _position_detail_label(adapter: Any, detail: Any) -> None:
    """Centre the native detail label under its own detail circle."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("failed to pin sheet scale before positioning detail label")
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    target = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("failed to position native detail label")
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, target) > 1e-8:
        raise RuntimeError(f"native detail label position did not persist: {actual}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    assert_end_view_ink_clear()
    assert_profile_leaders_clear()

    check("open pinion-arbor source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Integral Pinion Arbor Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "integral arbor and grip head; reamed, bonded crossrod hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # The end view is placed first, where the old donor was: its whole-model
    # import is the path that delivered HeadDia and NeckDia end-on (824056ef9).
    end = _place_end_view(adapter)
    # Looking along model Y presents the reamed cross-hole as a true
    # circle while retaining the entire turned profile in one horizontal view.
    principal = place_view(
        adapter, str(SOURCE), "*Top", *PRINCIPAL_CENTER, scale=SHEET_SCALE
    )
    _orient_like_profile(principal, label="integral arbor horizontally")
    drawing_model.EditRebuild3()
    _assert_end_view_projects_the_profile(adapter, end, principal)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (end, principal, iso):
        set_hidden_lines_removed(adapter, view)

    detail = _head_detail(adapter, principal)
    set_hidden_lines_removed(adapter, detail)
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label=END_VIEW_LABEL
    )
    principal_annotations = curate_view_dimensions(
        adapter, principal, keep=PRINCIPAL_KEEP, view_label="integral-arbor profile"
    )
    detail_annotations = curate_view_dimensions(
        adapter, detail, keep=DETAIL_KEEP, view_label="integral-arbor head detail"
    )
    for label, kept in (
        ("end", end_annotations),
        ("principal", principal_annotations),
        ("detail", detail_annotations),
    ):
        names = sorted(dimension_name(adapter, annotation) for annotation in kept)
        _telemetry.info(
            f"pinion-arbor {label} view kept {len(kept)} imported dimensions: {names}",
            view=label,
            kept=len(kept),
            names=",".join(names),
        )
    _assert_end_view_owns_its_diameters(adapter, end)
    annotations = [
        *end_annotations,
        *principal_annotations,
        *detail_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _set_arrow_sides(
        adapter,
        principal_annotations,
        {name: DIM_ARROWS_INSIDE for name in LAND_ARROWS_INSIDE},
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name, label in {
        "HeadCapSagDim": "front-crown height reference",
        "BackCapSagDim": "back-crown descriptive reference",
        "OverallLen": "overall length reference",
    }.items():
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {label}")
        set_reference_dimension(adapter, matches[0], label=label)

    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to add center mark to the detailed grip cross-hole")
    _add_turning_axis(adapter, principal)
    witness_spans = _blacken_reference_witnesses(adapter, principal)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.335, 0.255)
    _position_detail_label(adapter, detail)
    rebuild_drawing(adapter, label="pinion arbor layout audit")
    sheets = collect_document(adapter)
    _log_end_view_ink(sheets, view_name(adapter, end))
    _assert_no_text_on_line([f for sheet in sheets for f in audit_sheet(sheet)])
    _assert_sheet_leaders_clear(sheets)
    _assert_back_crown_radius_lands(
        sheets,
        model_point_in_view(
            adapter,
            principal,
            (0.0, 0.0, (BACK_APEX_Z - BACK_CAP_R) / 1000.0),
            label="back crown SR7.3 centre",
        ),
    )
    fence_center = model_point_in_view(
        adapter,
        principal,
        (0.0, 0.0, HEAD_CENTER_Z / 1000.0),
        label="integral-arbor detail fence centre",
    )
    far_on_axis = model_point_in_view(
        adapter,
        principal,
        (0.0, 0.0, (HEAD_CENTER_Z + OVERALL_LEN) / 1000.0),
        label="integral-arbor axis direction",
    )
    arrows = _dimension_arrows(adapter, principal)
    # The tips ride the message text, not only an attribute: a farm leaf's
    # task.log and the fleet workspace carry the text alone.
    directions = ", ".join(
        f"{name} tip ({tx * 1000:.1f}, {ty * 1000:.1f}) mm dir ({dx:.3f}, {dy:.3f})"
        for name, ((tx, ty), (dx, dy)) in sorted(arrows.items())
    )
    _telemetry.info(
        f"pinion-arbor: {len(arrows)} profile dimensions carry a readable "
        f"arrowhead: {directions}",
        arrows=len(arrows),
        directions=directions,
    )
    _assert_witnesses_clear_of_detail_fence(
        [
            annotation
            for sheet in sheets
            for annotation in sheet.annotations
            if annotation.owner == view_name(adapter, principal)
            and annotation.kind == "dim"
        ],
        center=fence_center,
        radius=DETAIL_RADIUS_MM / 1000.0,
        arrows=arrows,
        axis=_unit(far_on_axis[0] - fence_center[0], far_on_axis[1] - fence_center[1]),
    )

    sheet = _early_bound(
        _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
    )
    properties = tuple(float(value) for value in sheet.GetProperties2())
    sheet_size = (properties[5], properties[6])
    outputs = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Integral Pinion Arbor Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )
    _assert_outline_unbroken(PNG, witness_spans, sheet_size)
    return outputs


def sheet_ink(annotations: list[Any]) -> SheetInk:
    """The audit's annotations as the leader rule reads them: each radial or
    diametric dimension and each non-dimension annotation with ink is a
    leader, every other dimension is linear."""
    ink: SheetInk = {}
    for annotation in annotations:
        runs = [
            ((segment.x0, segment.y0), (segment.x1, segment.y1))
            for segment in annotation.segments
        ]
        if not runs:
            continue
        linear = annotation.kind == "dim" and annotation.label not in LEADER_DIMENSIONS
        name = annotation.label
        while name in ink:
            name += "'"
        ink[name] = ("linear" if linear else "leader", runs)
    return ink


def _assert_sheet_leaders_clear(sheets: list[Any]) -> None:
    """The sheet's leader rule on the rendered ink: no leader meets a
    dimension or extension line, no two linear dimensions meet unnamed, and no
    surface-finish symbol remains (the journal lands' Ra is a note)."""
    annotations = [annotation for sheet in sheets for annotation in sheet.annotations]
    symbols = sorted(a.label for a in annotations if a.kind == "surface-finish")
    ink = sheet_ink(annotations)
    findings = leader_line_findings(ink)
    expected = expected_crossings_found(ink)
    leaders = sorted(name for name, (role, _runs) in ink.items() if role == "leader")
    _telemetry.info(
        f"pinion-arbor sheet leaders: {len(leaders)} leader-bearing {leaders}, "
        f"{len(ink) - len(leaders)} linear; report-only crossings {expected}",
        leaders=len(leaders),
        expected=len(expected),
    )
    if symbols:
        findings.append(f"surface-finish symbols on the sheet: {symbols}")
    if findings:
        raise RuntimeError(
            "pinion-arbor: leaders meet lines on the sheet:\n"
            + "\n".join(f"  - {finding}" for finding in findings)
        )
    _telemetry.success("pinion-arbor: no leader meets a dimension or extension line")


# How near a BackCapR stroke's end must come to the SR7.3's radius (or to its
# centre, for the stroke SolidWorks runs on to it) to count as landing there.
LANDING_TOL_M = 1e-4


def _assert_back_crown_radius_lands(sheets: list[Any], center: tuple[float, float]) -> None:
    """The SR7.3's arrow lands on the back crown: a BackCapR stroke ends on the
    7.27 mm radius about the crown's centre, inside the crown's arc.  a652's
    landed on the arc's extension past the Ø8 flank."""
    runs = [
        ((segment.x0, segment.y0), (segment.x1, segment.y1))
        for sheet in sheets
        for annotation in sheet.annotations
        if annotation.label == "BackCapR"
        for segment in annotation.segments
    ]
    if not runs:
        raise RuntimeError("pinion-arbor: the SR7.3 carries no ink to land")
    ends = [end for run in runs for end in run]
    landing = min(ends, key=lambda end: abs(math.dist(end, center) - BACK_CAP_R_M))
    proof = "a stroke ends on the radius"
    if abs(math.dist(landing, center) - BACK_CAP_R_M) > LANDING_TOL_M:
        # One stroke may run from the bend straight on to the centre: then it
        # crosses the radius where the arrow stands.
        for run in runs:
            near, far = sorted(run, key=lambda end: math.dist(end, center))
            if math.dist(near, center) <= LANDING_TOL_M < math.dist(far, center) - BACK_CAP_R_M:
                length = math.dist(far, center)
                landing = (
                    center[0] + (far[0] - center[0]) / length * BACK_CAP_R_M,
                    center[1] + (far[1] - center[1]) / length * BACK_CAP_R_M,
                )
                proof = "a stroke runs from the centre out through the radius"
                break
    problems = back_crown_landing_problems(center, landing, tol=LANDING_TOL_M)
    reach = math.dist(landing, center)
    angle = math.degrees(math.atan2(landing[1] - center[1], center[0] - landing[0]))
    _telemetry.info(
        f"pinion-arbor: SR7.3 lands at ({landing[0] * 1000:.2f}, {landing[1] * 1000:.2f}) mm, "
        f"{reach * 1000:.3f} mm from the crown centre ({center[0] * 1000:.2f}, "
        f"{center[1] * 1000:.2f}) at {angle:.1f}° "
        f"(arc half-angle {BACK_CAP_HALF_ANGLE_DEG:.1f}°); "
        f"({proof}); {len(runs)} strokes {[_fmt_line(run) for run in runs]}",
        reach_mm=reach * 1000,
        angle_deg=angle,
    )
    if problems:
        raise RuntimeError(
            "pinion-arbor: the SR7.3 misses the back crown: " + "; ".join(problems)
        )


def _set_arrow_sides(adapter: Any, annotations: list[Any], sides: dict[str, int]) -> None:
    """Stand each named dimension's arrows on its swDimensionArrowsSide_e side,
    read back (draw_cone_tip_block's _set_arrow_sides, farm-proven at
    mha092-72ab)."""
    remaining = dict(sides)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        side = remaining.pop(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = side
        if int(display.ArrowSide) != side:
            raise RuntimeError(f"{name} did not keep its arrows on side {side}")
    if remaining:
        raise RuntimeError(f"no dimension to set arrow sides: {sorted(remaining)}")


# Text on text joined the gate with the bond-zone callout's move above the
# shaft, beside the DETAIL A label (63468ee9 read 0 advisory findings).
# Leader on leader joined with the back Ra symbol's move above the shaft: at
# c6eb7f6f its shoulder crossed the back land length's witness (Main).  Both
# symbols have since become the JOURNAL LANDS note; a leader meeting a
# dimension or extension line is _assert_sheet_leaders_clear's.
BLOCKING_LAYOUT_FINDINGS = frozenset(
    {"text-on-line", "text-on-text", "leader-crosses-leader"}
)


def _assert_no_text_on_line(findings: list[Any]) -> None:
    """Fail the sheet when any annotation's text sits on another's line or text.

    Main's eye-pass of 30620a85 found the back-crown and overall witnesses
    running through the back journal's "8.00" and "JOURNAL".  The native audit
    reads every dimension's rendered witness, dimension and leader segments, so
    that defect is now a build failure with sheet-millimetre fix coordinates.
    Text on text is gated too, since the bond-zone callout moved above the
    shaft beside the DETAIL A label.  The audit's other finding kinds are
    logged, not gated: the diametric Ø6 leader crossing the SR10.9 leader
    inside detail A is conventional ink, and so is the one crossing two
    concentric diameters must make on the end view (_is_end_view_centre_crossing).
    """
    blocking = [
        f
        for f in findings
        if f.kind in BLOCKING_LAYOUT_FINDINGS and not _is_end_view_centre_crossing(f)
    ]
    advisory = [f for f in findings if f not in blocking]
    if advisory:
        _telemetry.warn(
            f"pinion-arbor layout audit: {len(advisory)} advisory finding(s)\n"
            + format_findings(advisory),
            advisory=len(advisory),
        )
    if blocking:
        raise RuntimeError(
            f"pinion-arbor layout audit: {len(blocking)} blocking finding(s)\n"
            + format_findings(blocking)
        )
    _telemetry.success(
        f"pinion-arbor layout audit: no text on a foreign line or text "
        f"({len(advisory)} advisory)"
    )


def _is_end_view_centre_crossing(finding: Any) -> bool:
    """The Ø15 and Ø10.5 lines crossing at the end view's common centre.

    Both run through the centre of their concentric circles, so they cross
    there wherever their texts stand; ASME diameter lines do.  Only that pair,
    only a leader crossing, and only inside the Ø10.5 is excused: a crossing
    anywhere else, or by any other annotation, still blocks.
    """
    if finding.kind != "leader-crosses-leader" or finding.at_mm is None:
        return False
    if {finding.a, finding.b} != set(END_KEEP):
        return False
    center_mm = (END_CENTER[0] * 1000.0, END_CENTER[1] * 1000.0)
    return math.dist(finding.at_mm, center_mm) <= NECK_DIA / 2.0


def _log_end_view_ink(sheets: list[Any], end_name: str) -> None:
    """Log the end view's diameters as the layout audit read them: the rendered
    ink behind END_DIA_TEXT_EXTENT, for the eye pass to calibrate it."""
    for annotation in (
        annotation
        for sheet in sheets
        for annotation in sheet.annotations
        if annotation.owner == end_name and annotation.label in END_KEEP
    ):
        boxes = " ".join(box.format_mm() for box in annotation.text_boxes) or "(no text)"
        runs = " ".join(
            f"{segment.role}:{segment.format_mm()}" for segment in annotation.segments
        )
        _telemetry.info(
            f"pinion-arbor: end-view {annotation.label} text {boxes}; runs {runs}",
            label=annotation.label,
        )


FENCE_TOL_M = 0.0002
# A run within this angle of its dimension's measured direction is that
# dimension's line; within this angle of the perpendicular, an extension line.
# Anything between is neither and is judged like an extension line.
DIRECTION_TOL_RAD = math.radians(5.0)
# An arrowhead's tip lies on its own dimension line, or on its extension past
# a run that stops at the arrow's base.
ARROW_ON_LINE_TOL_M = 0.0005
ARROW_REACH_M = 0.005
# swAnnotationType_e.swDisplayDimension
_SW_DISPLAY_DIMENSION = 4

Arrow = tuple[tuple[float, float], tuple[float, float]]


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length == 0.0:
        raise ValueError("a direction needs a non-zero vector")
    return dx / length, dy / length


def _dimension_arrows(adapter: Any, view: Any) -> dict[str, Arrow]:
    """Each dimension's first arrowhead on ``view``: its tip and unit direction.

    ``IDisplayData`` labels no run as extension or dimension line, and
    ``IDimension::DimensionLineDirection`` answers feature dimensions only,
    while this sheet mixes feature and sketch dimensions.  An arrowhead, the
    one signal every dimension carries, points along its own
    dimension line (``IDisplayData::GetArrowHeadAtIndex2``: tip[3], dir[3],
    ...), so it names the dimension's measured direction on the sheet.
    """
    arrows = {}
    for item in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(item, "IAnnotation")
        if int(annotation.GetType()) != _SW_DISPLAY_DIMENSION:
            continue
        data = annotation.GetDisplayData()
        if data is None:
            continue
        data = _early_bound(data, "IDisplayData")
        for index in range(int(data.GetArrowHeadCount() or 0)):
            values = [float(value) for value in (data.GetArrowHeadAtIndex2(index) or ())]
            if len(values) < 6 or math.hypot(values[3], values[4]) < 1e-9:
                continue
            arrows[str(annotation.GetName())] = (
                (values[0], values[1]),
                _unit(values[3], values[4]),
            )
            break
    return arrows


def _segment_kind(segment: Any, measured: tuple[float, float]) -> str:
    """Classify one straight run against its own dimension's measured direction."""
    direction = _unit(segment.x1 - segment.x0, segment.y1 - segment.y0)
    along = abs(direction[0] * measured[0] + direction[1] * measured[1])
    if along >= math.cos(DIRECTION_TOL_RAD):
        return "dimension-line"
    if along <= math.sin(DIRECTION_TOL_RAD):
        return "extension-line"
    return "oblique"


def _on_line_through(point: tuple[float, float], segment: Any) -> bool:
    """``point`` lies on ``segment``'s line, within an arrow's reach of its ends."""
    direction = _unit(segment.x1 - segment.x0, segment.y1 - segment.y0)
    dx, dy = point[0] - segment.x0, point[1] - segment.y0
    along = dx * direction[0] + dy * direction[1]
    across = abs(dx * direction[1] - dy * direction[0])
    return (
        across <= ARROW_ON_LINE_TOL_M
        and -ARROW_REACH_M <= along <= segment.length + ARROW_REACH_M
    )


def _measured_direction(annotation: Any, arrow: Arrow | None) -> tuple[float, float] | None:
    """The arrowhead's direction, once its tip is proven to sit on its own line."""
    if arrow is None:
        return None
    tip, measured = arrow
    on_own_line = any(
        _segment_kind(segment, measured) == "dimension-line"
        and _on_line_through(tip, segment)
        for segment in annotation.segments
        if segment.length > 0.0
    )
    if not on_own_line:
        raise RuntimeError(
            f"{annotation.label!r}: arrowhead at ({tip[0] * 1000:.1f},"
            f"{tip[1] * 1000:.1f})mm lies on none of its own parallel runs; "
            "its measured direction is unreadable"
        )
    return measured


def _assert_witnesses_clear_of_detail_fence(
    annotations: list[Any],
    *,
    center: tuple[float, float],
    radius: float,
    arrows: dict[str, Arrow],
    axis: tuple[float, float],
) -> None:
    """No extension line may run out through the detail-A fence on the profile.

    The head sits inside the fence, so every head dimension starts inside it.
    Each crossing run is judged against ITS OWN dimension (Main's ruling on
    run 492a7be5).  The dimension line, parallel to the measured direction,
    may cross the fence to reach its text, as any line may cross a line.  An
    extension line, perpendicular to it, may leave only as a station witness,
    belonging to a dimension measured along the turning axis, which drops to
    the station stack.  Anything else leaving the circle (the Ø15.0 witnesses
    did, with the "A" label between them) reads as part of the detail callout.
    A dimension with no readable arrowhead is judged as all extension lines.
    """
    offenders = []
    for annotation in annotations:
        crossing = []
        for segment in annotation.segments:
            if segment.role != "line":
                continue
            ends = ((segment.x0, segment.y0), (segment.x1, segment.y1))
            far = max(math.dist(end, center) for end in ends)
            near = _segment_distance(center, ends)
            if near < radius - FENCE_TOL_M and far > radius + FENCE_TOL_M:
                crossing.append(segment)
        if not crossing:
            continue
        measured = _measured_direction(annotation, arrows.get(annotation.label))
        axial = measured is not None and abs(
            measured[0] * axis[0] + measured[1] * axis[1]
        ) >= math.cos(DIRECTION_TOL_RAD)
        for segment in crossing:
            kind = "extension-line" if measured is None else _segment_kind(segment, measured)
            if kind == "dimension-line":
                continue
            if kind == "extension-line" and axial:
                continue
            offenders.append(
                f"{annotation.label!r} {kind} "
                f"({segment.x0 * 1000:.1f},{segment.y0 * 1000:.1f})-"
                f"({segment.x1 * 1000:.1f},{segment.y1 * 1000:.1f})mm"
            )
    if offenders:
        raise RuntimeError(
            f"pinion-arbor: {len(offenders)} extension line(s) cross the detail-A "
            "fence:\n  " + "\n  ".join(offenders)
        )
    _telemetry.success("pinion-arbor: no extension line crosses the detail-A fence")


def _segment_distance(
    point: tuple[float, float],
    ends: tuple[tuple[float, float], tuple[float, float]],
) -> float:
    (x0, y0), (x1, y1) = ends
    dx, dy = x1 - x0, y1 - y0
    span = dx * dx + dy * dy
    if span == 0.0:
        return math.dist(point, (x0, y0))
    t = max(0.0, min(1.0, ((point[0] - x0) * dx + (point[1] - y0) * dy) / span))
    return math.dist(point, (x0 + t * dx, y0 + t * dy))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
