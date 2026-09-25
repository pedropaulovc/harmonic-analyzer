r"""Create the integral MHA-102 pinion-arbor manufacturing drawing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
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
from _surface_finish import surface_finish_by_key
from pinion_arbor_pin_spec import PIN_HOLE_CALLOUT
from pinion_arbor_spec import (
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
    OVERALL_LEN,
    SHAFT_DIA,
    SURFACE_FINISHES,
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
# x = 0.200 - (z - 106.725) / 1000.  The lands are centred on their straps, so
# their centres (x 0.252 front, 0.099 back) hold whatever the derived land
# length; only their ends move.  The front land's length rides above the
# shaft and its diameter hangs below; the back land's are swapped (see
# BACK_JOURNAL_TEXT_X).  The stations from the Ø15 head rear face stack
# below the shaft.
MODEL_Z_AT_SHEET_ORIGIN_X = 106.725
# The back crown's apex, the profile's left end (x 0.0793).
BACK_APEX_Z = HEAD_FRONT_Z - HEAD_CAP_SAG + OVERALL_LEN


def _sheet_x(model_z: float) -> float:
    return PRINCIPAL_CENTER[0] - (model_z - MODEL_Z_AT_SHEET_ORIGIN_X) / 1000.0


# Each land's Ra arrow lands RA_ARROW_FROM_HEAD_END in from the land's
# head-side end, and its symbol hangs RA_SHOULDER further head side on a short
# bent-leader shoulder.  The front symbol hangs below the shaft, its left edge
# clear of that end's station witness.  At c6eb7f6f the back symbol did the
# same and its shoulder ran through the 199.9 / 19.0 witness below the shaft
# (Main).  Nothing rises from the back land above the shaft, so its symbol
# hangs there, over the land's head-side end and under the raised back
# JOURNAL diameter (BACK_JOURNAL_DIA_Y).
RA_ARROW_FROM_HEAD_END = 2.0
RA_SYMBOL_OFFSET = 0.0033
RA_SHOULDER = RA_SYMBOL_OFFSET + RA_ARROW_FROM_HEAD_END / 1000.0
FRONT_RA_X = _sheet_x(FRONT_JOURNAL_Z) + RA_SYMBOL_OFFSET
BACK_RA_XY = (
    _sheet_x(BACK_JOURNAL_Z + RA_ARROW_FROM_HEAD_END) + RA_SHOULDER,
    0.179,
)
# Rendered extent of an Ra 1.6 symbol about its insertion point (left, right,
# top; the point is the shoulder's end under the triangle's vertex), measured
# on the c6eb7f6f sheet.
RA_SYMBOL_EXTENT = (-0.0019, 0.0151, 0.0062)
FLANK_SIGN = {"lower": -1.0, "upper": 1.0}
# Each land's diameter is measured at a short witness JOURNAL_DIA_POINT_FROM_
# CROWN_END in from its crown-side end (build_pinion_arbor, pinned equal by
# test), and its line stands 1 mm from that point, so its extensions are ~1 mm
# rather than a run along the flank (Main, 2026-09-24).  The text hangs away
# from the side its extensions come from: left of the front line, right of the
# back one.
JOURNAL_DIA_POINT_FROM_CROWN_END = 2.0
JOURNAL_DIA_LINE_OFFSET = 0.001
FRONT_JOURNAL_DIA_POINT_X = _sheet_x(
    FRONT_JOURNAL_Z + JOURNAL_LEN - JOURNAL_DIA_POINT_FROM_CROWN_END
)
BACK_JOURNAL_DIA_POINT_X = _sheet_x(
    BACK_JOURNAL_Z + JOURNAL_LEN - JOURNAL_DIA_POINT_FROM_CROWN_END
)
# The back land is boxed in below the shaft (the back-crown and overall
# witnesses at x 0.079-0.081 on its crown side, the 199.9 witness and the Ra
# leader on its head side), so its diameter hangs ABOVE the shaft, its text
# right of the line over the land and clear of the back-crown sag witnesses,
# and its 19.0 length moves below.  The block rides high enough that the
# back Ra symbol fits under it, over the land.
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
# line stands on the land 1 mm crown side of its measuring point, the text
# block ending ~2.4 mm short of that witness.
JOURNAL_DIA_TEXT_OVERHANG = 0.001
FRONT_JOURNAL_DIA_X = FRONT_JOURNAL_DIA_POINT_X - JOURNAL_DIA_LINE_OFFSET
# The bond-zone diameter stands over the part's witness (x 0.195) but hangs
# its text ABOVE the shaft: below it, beside the front "JOURNAL" shelf, the
# two read as one paired callout (Main and Fable, 63468ee9).  Above, its line
# rises a few mm off the silhouette to the shelf, right of the DETAIL A label
# and under detail A's "(3.0)", and short of the front land's 19.0 witnesses.
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
REFERENCE_WITNESS_LEN_TOL = 0.01  # mm; the witnesses are fully defined sketch lengths
# Exported-raster proof that the outline stays unbroken over each witness:
# the grey witness core measured 107-128 and the black outline 0 (5471a6ef
# PNG), so every raster column over a span needs at least two dark pixels
# within a few rows of the flank.
OUTLINE_DARK_MAX = 60
OUTLINE_CORE_ROWS = 2
OUTLINE_SEARCH_ROWS = 6
# Rendered width and height of a two-place "Ø8.00 -0.01/-0.0x" callout block,
# measured on the 63468ee9 sheet.
DIAMETER_BLOCK_SIZE = (0.027, 0.014)
PRINCIPAL_KEEP = {
    "FrontJournalLen": (0.252, 0.188),
    # Below the shaft, under the back Ra symbol and its leader.
    "BackJournalLen": (0.097, 0.143),
    "FrontJournalDia": (FRONT_JOURNAL_DIA_X, 0.150),
    "BondZoneDia": BOND_ZONE_TEXT_XY,
    "BackJournalDia": (BACK_JOURNAL_TEXT_X, BACK_JOURNAL_DIA_Y),
    "FrontJournalFromHeadRear": (0.283, 0.130),
    # The drum station stacks between the two land stations, its text left of
    # its own drum-end witness.  The back station's text moves left to clear
    # it.
    "DrumStationFromHeadRear": DRUM_STATION_TEXT_XY,
    "BackJournalFromHeadRear": (0.170, 0.115),
    # Right of the overall-length witness at the front crown apex (x 0.3215).
    "NeckLen": (0.340, 0.100),
    "BackRimFromHeadRear": (0.205, 0.095),
    "OverallLen": (0.205, 0.080),
    "BackCapSagDim": (0.055, 0.220),
    # Radial leader down-left from the back crown, below the shaft axis and
    # clear of the (1.2) sag reference above it and the overall witnesses.
    "BackCapR": (0.045, 0.140),
    # R1a's collar pin hole (x 0.269) sits over the front land's Ra symbol,
    # so both its dimensions stand ABOVE the shaft: the station from the head
    # rear face in a row well over the Ø15 head, and the hole's leader rising
    # left of that row's witness, above the 19.0's right arrow tail.
    "PinStationFromHeadRear": (0.288, 0.207),
    "PinHoleDia": (0.250, 0.222),
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
# Both diameters stand above the view, their leaders running down through the
# common centre (the two lines cross there, as concentric diameters do): the
# Ø15 up-left towards the border, the Ø10.5 up-right towards the profile, the
# rows 8 mm apart so no text shares a height with the other.
END_KEEP = {
    "HeadDia": (0.030, 0.196),
    "NeckDia": (0.062, 0.188),
}
END_VIEW_LABEL = "integral-arbor end view"
# The sheet position tolerance for the end view's centre after placement.
END_CENTER_TOL_M = 1e-5

# ---------------------------------------------------------------------------
# End-view ink audit
#
# The layout audit this module gates (_assert_no_text_on_line) compares text
# with lines and text with text, but no text with a view's model outline, and
# the shared layout check boxes every dimension as a nominal 8 mm
# CollisionScope.NONE square (_drawing_common._dim_element), so it compares
# no dimension text at all.  So the end view's corner of the sheet audits its
# own ink before any COM work (cone-tip-block's sheet_ink_collisions, 287c5cf6a):
# the two diameters' text blocks against each other, the neighbouring profile
# callouts, every view's outline, the lines that stand in that corner and the
# sheet border.
#
# Extents are (left, down, right, up) of the printed ink from the position the
# module commands, in sheet metres.  A circle diameter prints its text about
# its position with the leader's shoulder ~2 mm past each end (wheel-axle's
# Ø35.00: ±8.3 mm by -2.3/+2.1 mm, rk3 render), while the layout audit boxed
# the profile's Ø10.5 from 15.6 mm left of its position to 11.5 mm right,
# 2.8 mm down and 0.7 mm up (stacktop-dbe47ae3).  The end-view box covers
# both, 15.6 mm to either side.
END_DIA_TEXT_EXTENT = (0.0156, 0.0030, 0.0156, 0.0025)
# Where the leader leaves the shoulder: its circle-side end, this far along
# and below the text position (wheel-axle's shoulders end ~1.5 mm past a
# ~7 mm half-text, ~2.5 mm under its centre).
END_DIA_SHOULDER = (0.0090, 0.0025)
# The profile's callouts in that corner, measured on the a1a694a6 render
# (4.63 px/mm): "SR7.3" x 38.9-50.7, y 137.3-142.3 mm with its shelf to 54 mm;
# "(1.2) / BACK CROWN" x 38.9-71.2, y 214.6-225.0 mm with its shelf to 77 mm;
# the back JOURNAL block right of its line (DIAMETER_BLOCK_SIZE).
NEIGHBOUR_TEXT_EXTENTS = {
    "BackCapR": (0.0065, 0.0030, 0.0095, 0.0025),
    "BackCapSagDim": (0.0165, 0.0060, 0.0225, 0.0055),
    "BackJournalDia": (0.0010, 0.0075, 0.0270, 0.0075),
}
# The SR7.3 leader leaves its shelf end for the crown 2.9 mm under the axis.
BACK_CAP_R_LEADER_DROP = 0.0029
# A text block keeps this much air to another text block, and to any view's
# model outline, line or the sheet's inner border.
END_TEXT_CLEARANCE = 0.0010
END_OUTLINE_CLEARANCE = 0.0010
# The landscape B sheet's inner border, measured on the a1a694a6 render.
SHEET_INNER_LEFT = 0.0125

InkBox = tuple[float, float, float, float]
InkLine = tuple[tuple[float, float], tuple[float, float]]


def _ink_box(point: tuple[float, float], extent: tuple[float, float, float, float]) -> InkBox:
    left, down, right, up = extent
    return (point[0] - left, point[1] - down, point[0] + right, point[1] + up)


def _circle_box(center: tuple[float, float], radius: float) -> InkBox:
    return (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)


def end_view_text_boxes(keep: dict[str, tuple[float, float]] = END_KEEP) -> dict[str, InkBox]:
    """The end view's diameter texts and the profile callouts beside them."""
    boxes = {name: _ink_box(point, END_DIA_TEXT_EXTENT) for name, point in keep.items()}
    for name, extent in NEIGHBOUR_TEXT_EXTENTS.items():
        boxes[name] = _ink_box(PRINCIPAL_KEEP[name], extent)
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
            _sheet_x(HEAD_FRONT_Z - HEAD_CAP_SAG),
            axis_y + head_r,
        ),
        "detail A": _circle_box(DETAIL_CENTER, DETAIL_RATIO * DETAIL_RADIUS_MM / 1000.0),
    }


def _diameter_line(
    text_xy: tuple[float, float], center: tuple[float, float], diameter: float
) -> InkLine:
    """A circle diameter's line: from its shoulder, through the centre, to the far arrow."""
    toward = 1.0 if text_xy[0] < center[0] else -1.0
    start = (
        text_xy[0] + toward * END_DIA_SHOULDER[0],
        text_xy[1] - END_DIA_SHOULDER[1],
    )
    dx, dy = center[0] - start[0], center[1] - start[1]
    length = math.hypot(dx, dy)
    radius = diameter / 2000.0
    return start, (center[0] + dx / length * radius, center[1] + dy / length * radius)


def sheet_corner_lines(
    keep: dict[str, tuple[float, float]] = END_KEEP,
    end_center: tuple[float, float] = END_CENTER,
) -> dict[str, InkLine]:
    """The lines standing in the end view's corner, keyed by their owner."""
    axis_y = PRINCIPAL_CENTER[1]
    shaft_top = axis_y + SHAFT_DIA / 2000.0
    sag_x, sag_y = PRINCIPAL_KEEP["BackCapSagDim"]
    witness_top = sag_y - NEIGHBOUR_TEXT_EXTENTS["BackCapSagDim"][1] + 0.0005
    radius_x, radius_y = PRINCIPAL_KEEP["BackCapR"]
    extent = NEIGHBOUR_TEXT_EXTENTS["BackCapR"]
    diameters = {"HeadDia": HEAD_DIA, "NeckDia": NECK_DIA}
    return {
        "BackCapSagDim apex witness": (
            (_sheet_x(BACK_APEX_Z), shaft_top),
            (_sheet_x(BACK_APEX_Z), witness_top),
        ),
        "BackCapSagDim root witness": (
            (_sheet_x(BACK_APEX_Z - BACK_CAP_SAG), shaft_top),
            (_sheet_x(BACK_APEX_Z - BACK_CAP_SAG), witness_top),
        ),
        "BackCapR": (
            (radius_x + extent[2], radius_y - extent[1]),
            (_sheet_x(BACK_APEX_Z), axis_y - BACK_CAP_R_LEADER_DROP),
        ),
        **{
            name: _diameter_line(xy, end_center, diameters[name])
            for name, xy in keep.items()
        },
    }


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


def end_view_ink_collisions(
    texts: dict[str, InkBox],
    outlines: dict[str, InkBox],
    lines: dict[str, InkLine],
    *,
    audited: tuple[str, ...] = tuple(END_KEEP),
) -> list[str]:
    """Every ``audited`` text too near another text, an outline, a foreign line
    or the sheet's inner border."""
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
            if owner != name and _line_meets_box(line, _grown(box, END_TEXT_CLEARANCE)):
                findings.append(f"text-on-line: {owner}'s line runs through {name!r}")
        if box[0] - SHEET_INNER_LEFT < END_OUTLINE_CLEARANCE:
            findings.append(
                f"outside-border: {name!r} starts {(box[0] - SHEET_INNER_LEFT) * 1000.0:.2f} "
                "mm inside the sheet's inner border"
            )
    return findings


def assert_end_view_ink_clear() -> None:
    """Refuse an end-view placement whose own text collides, before any COM work."""
    findings = end_view_ink_collisions(
        end_view_text_boxes(), sheet_view_outlines(), sheet_corner_lines()
    )
    if findings:
        raise RuntimeError(
            "pinion-arbor end-view ink collides:\n"
            + "\n".join(f"  - {finding}" for finding in findings)
        )
    _telemetry.debug("pinion-arbor end-view ink clear")


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
# Each land's Ra symbol hangs off one flank on the land's head side of its
# diameter line, clear of the split-line rings at the land ends.
JOURNAL_FINISHES = {
    "front_journal": (
        FRONT_JOURNAL_Z + RA_ARROW_FROM_HEAD_END,
        (FRONT_RA_X, 0.150),
        "lower",
    ),
    "back_journal": (BACK_JOURNAL_Z + RA_ARROW_FROM_HEAD_END, BACK_RA_XY, "upper"),
}


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


def _blacken_reference_witnesses(
    adapter: Any, view: Any
) -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    """Draw each reference sketch's flank witness in the outline's black.

    Returns each witness's sheet endpoints for the exported-raster check.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the integral-arbor profile for its witnesses")
    flank_x = SHAFT_DIA / 2000.0
    spans = {}
    for sketch_name, (z0, z1) in REFERENCE_WITNESSES.items():
        ends = tuple(
            model_point_in_view(
                adapter, view, (flank_x, 0.0, z / 1000.0), label=f"{sketch_name} witness end"
            )
            for z in (z0, z1)
        )
        mid = ((ends[0][0] + ends[1][0]) / 2.0, (ends[0][1] + ends[1][1]) / 2.0)
        draw.ClearSelection2(True)
        _early_bound(view, "IView").UpdateViewDisplayGeometry()
        if not draw.Extension.SelectByID2(
            "", "EXTSKETCHSEGMENT", mid[0], mid[1], 0.0, False, 0, null_callout(), 0
        ):
            raise RuntimeError(f"failed to select the {sketch_name} flank witness")
        selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
        kind = int(selection.GetSelectedObjectType3(1, -1))
        if kind != SW_SEL_EXT_SKETCH_SEGS:
            raise RuntimeError(f"{sketch_name} witness pick resolved to type {kind}")
        segment = _early_bound(selection.GetSelectedObject6(1, -1), "ISketchSegment")
        # Identify the pick by its own length, not its sketch's name: an
        # ISketch is not an IFeature dispatch, so rebinding it reads another
        # member (7885c0d9 got a 16-double matrix back for ``Name``).  The
        # only other flank construction segment here is the front land's
        # 19 mm witness.
        name = str(segment.GetName())
        length = float(segment.GetLength()) * 1000.0
        expected = z1 - z0
        construction = bool(segment.ConstructionGeometry)
        if abs(length - expected) > REFERENCE_WITNESS_LEN_TOL or not construction:
            raise RuntimeError(
                f"{sketch_name} witness pick resolved to {name} "
                f"({length:.3f} mm, want {expected:.3f}; construction={construction})"
            )
        drawing.SetLineColor(REFERENCE_WITNESS_COLOR)
        draw.ClearSelection2(True)
        spans[sketch_name] = ends
        _telemetry.info(
            f"pinion-arbor: {sketch_name} flank witness drawn black at sheet "
            f"({mid[0] * 1000:.1f}, {mid[1] * 1000:.1f}) mm",
            sketch=sketch_name,
        )
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
    for key, (station_z, symbol_xy, flank) in JOURNAL_FINISHES.items():
        land_x, axis_y = model_point_in_view(
            adapter,
            principal,
            (0.0, 0.0, station_z / 1000.0),
            label=f"arbor {key} finish station",
        )
        add_surface_finish(
            adapter,
            principal,
            edge_xy=(land_x, axis_y + FLANK_SIGN[flank] * SHAFT_DIA / 2000.0),
            symbol_xy=symbol_xy,
            control=surface_finish_by_key(SURFACE_FINISHES, key),
            label=f"arbor {key} finish",
            entity_type="SILHOUETTE",
            char_height=0.0025,
        )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.335, 0.255)
    _position_detail_label(adapter, detail)
    rebuild_drawing(adapter, label="pinion arbor layout audit")
    sheets = collect_document(adapter)
    _log_end_view_ink(sheets, view_name(adapter, end))
    _assert_no_text_on_line([f for sheet in sheets for f in audit_sheet(sheet)])
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


# Text on text joined the gate with the bond-zone callout's move above the
# shaft, beside the DETAIL A label (63468ee9 read 0 advisory findings).
# Leader on leader joined with the back Ra symbol's move above the shaft: at
# c6eb7f6f its shoulder crossed the back land's 19.0 witness (Main).
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
