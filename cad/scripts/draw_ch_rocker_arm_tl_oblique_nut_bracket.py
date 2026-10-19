r"""Create the drawing for the oblique-trammel jig's nut bracket (MHA-CH-06-TL-29).

An 18.5 x 48 x 35.3 block at 2:1, three projected views about the nut face.
The nut face (*Left, from -X: the Y = 0 face at its top edge, the bottom
face at its left edge) carries the nut seat's stations from those two faces
and the four M3 taps' offsets from the seat's axis (the hidden reference
sketch NutPatternReference) outside its outline, the seat's native callout
under it and the taps' over its upper right.
The view over it (*Top, from +Y: the block face, turned so +X runs up, the
-X face at its bottom edge) carries the finished length and the height,
with the two #8 taps' native callout over it: spotted from TL-22 at
assembly, they print no station. The plan right of the nut face (*Front,
from +Z) carries the depth. The shaded isometric rides right of the plan.
No datums (drawing-guidelines.md rule 5).

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_nut_bracket.py ch-rocker-arm-tl-oblique-nut-bracket
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
import _drawing_hidden_sketches as hidden_sketches
from _drawing_dimensions import assert_imported_precision
from _drawing_hole_callout import add_native_hole_callout, compose_hole_callout_prefix
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _hole_callout_thread_class import omit_title_block_thread_class
from _paths import CAD_ROOT
from _printed_limits import limits
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_nut_bracket_spec as part_spec
from ch_rocker_arm_tl_oblique_nut_bracket_spec import (
    BLOCK_TAP_DRILL,
    BLOCK_TAP_PROCESS,
    BLOCK_TAP_SPEC,
    BLOCK_TAP_WALL_CALLOUT,
    BORE_Y,
    BORE_Z,
    BRACKET_HEIGHT,
    CBORE_DIA,
    DIMENSION_PREFIXES,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_X,
    NUT_HOLE_OFFSET,
    NUT_HOLE_Y,
    NUT_HOLE_Z,
    NUT_SEAT_MATE_CALLOUT,
    NUT_SEAT_PROCESS,
    NUT_TAP_DRILL,
    NUT_TAP_PROCESS,
    SCREW_X,
    SCREW_Z,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_nut_bracket"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 1)
# Outlines at 2:1 (sheet mm): the nut face (*Left) x 66..137, y 50..146,
# the seat's Z station and the M3 Z offsets in three lanes over it, its Y
# station and the M3 Y offsets left of it (lines x 24 and 58), the seat's
# callout under it and the M3 taps' over the plan, right of it; the block
# face (*Top, turned so +X runs up) in projection over it, x 66..137, y
# 198..235, its height hanging under it, its length right of it, its #8
# callout over it; the plan (*Front) right of the nut face, x 166..204, y
# 50..146. The title block is x >= 216, y <= 70.
FRONT_CENTER = (0.185, 0.098)
LEFT_CENTER = (0.1013, 0.098)
# The block face's model origin (X 0, the bracket's mid-length) stands at
# this sheet y and at the nut face's origin x (_project_block_face_view).
TOP_CENTER = (LEFT_CENTER[0], 0.2165)
# The ~55 mm pictorial: x ~307..363, y ~132..188.
ISO_CENTER = (0.335, 0.160)
ISO_NOTE_XY = (0.315, 0.115)
# Projection readbacks are geometric, not manufacturing bands.
PROJECTION_SLOP_M = 1e-5
PROJECTION_ANGLE_SLOP = 1e-6

# Every dimension's text position is a MODEL point (mm) off the part, mapped
# onto its view at run time (2 sheet mm per model mm).
_H = BRACKET_HEIGHT
FRONT_KEEP: dict[str, tuple[float, float, float]] = {
    # Left of the plan, in the gap to the nut-face view.
    "BracketDepth": (FACE_X - 6.0, -part_spec.BRACKET_DEPTH / 2.0, _H),
}
# The block face: +X up, +Z right; the -X face is its bottom edge, the
# bottom face (Z 0) its left edge, as in the nut face under it.
TOP_KEEP: dict[str, tuple[float, float, float]] = {
    # The height from the bottom face, hung under the view, over the nut
    # face's Z station (text y ~192).
    "BracketHeight": (FACE_X - 3.0, 0.0, _H / 2.0),
    # The length from the -X face right of the view (line x ~145), its text
    # between its extension lines.
    "BracketLength": (0.0, 0.0, _H + 5.0),
}
LEFT_KEEP: dict[str, tuple[float, float, float]] = {
    # The M3 offsets from the seat's axis (c4 review: located from the seat,
    # not the edges), outside the outline (c4-r8/r9, rule 14: inside it all
    # four texts and lines sat on the part). Each 11.3 mm span is narrower
    # than its text, so each text stands outboard. Over the view, three lanes
    # 5 apart, each one's extension lines ending under the next lane's text:
    # -Z innermost, its text left of the left edge (so of the 13.00's
    # extension line there); the seat's Z station (13.00) next, its text in
    # its span, left of the seat's line and right of the left column's
    # (which ends at the -Z lane); +Z outermost, its text right of the right
    # column's line.
    "NutPatternZ1": (FACE_X, 4.0, -6.0),
    "BoreZ": (FACE_X, 9.0, BORE_Z / 2.0),
    "NutPatternZ2": (FACE_X, 14.0, NUT_HOLE_Z[1] + 6.0),
    # Left of the view: the Y offsets share one line (x 58) 8 off the left
    # edge, each text beyond its span; a text beyond its span hangs on the
    # side away from the features its extension lines leave (r9: right of a
    # line right of the taps; draw_fr_harmonic_base: west), so here west,
    # clear of the edge. +Y over the upper taps, -Y under the lower taps,
    # over the bottom edge. The seat's Y station (35.00) outermost (x 24),
    # its text between its lines, west of the Y offsets' texts and of their
    # extension lines' ends.
    "NutPatternY1": (FACE_X, -(BORE_Y - NUT_HOLE_OFFSET) + 4.0, -4.0),
    "NutPatternY2": (FACE_X, -(BORE_Y + NUT_HOLE_OFFSET) - 4.0, -4.0),
    "BoreY": (FACE_X, -BORE_Y / 2.0, -21.0),
}
# swDimensionArrowsSide_e.swDimArrowsInside (draw_ch_bar_pivot_pin): left to
# the document's smart arrows, c4-r4 drew both Y offsets' arrows outside on
# their shared line, each one's tails into the other's span.
ARROWS_INSIDE = ("NutPatternY1", "NutPatternY2")
_DIM_ARROWS_INSIDE = 0
# Hole callouts: each leader runs from its shelf's near end at its hole's
# centre, landing on the rim; its text block centred at ``callout_xy``
# (sheet m).
# The #8 pair's leader drops from the shelf (right end x ~124, y ~238) to
# the far tap (x ~114, y ~227), crossing no line: the block face's height
# hangs under it and its length stands right of it. The four rows (the
# spot row first, the wall row last) span x ~20..124, y ~238..259.
_BLOCK_R = BLOCK_TAP_DRILL / 2.0
BLOCK_TAP_EDGE_MODEL = (
    part_spec.BLOCK_SCREW_POINTS[1][0] + 0.6 * _BLOCK_R,
    0.0,
    SCREW_Z + 0.8 * _BLOCK_R,
)
BLOCK_TAP_CALLOUT_XY = (0.0720, 0.2492)
# The M3 block's widest row is the mate's inventory id (c4-r9, rule 4), about
# 69 wide: under the view its shelf would end right of every tap and the
# leader rise up-left through the rows (c4-r7 struck "HOLES" so). Over the
# plan, right of the nut face (x ~142..213, y ~152..175), its shelf's left
# end (the bottom row's) drops down-left to the upper-right tap's upper-right
# edge, entering through the face's right edge, right of the +Z offset's
# extension line, crossing none.
_NUT_R = NUT_TAP_DRILL / 2.0
NUT_TAP_EDGE_MODEL = (
    FACE_X,
    -NUT_HOLE_Y[0] + 0.8 * _NUT_R,
    NUT_HOLE_Z[1] + 0.6 * _NUT_R,
)
NUT_TAP_CALLOUT_XY = (0.1775, 0.1635)
# The seat's five rows run x ~120..198, y ~15..45; its leader rises from the
# shelf's left end (x ~120, y ~15) to the bore (x 92, y 76), crossing y 64.7
# at x ~97: left of the lower-right M3 tap (x 103.3).
_CBORE_R = CBORE_DIA / 2.0
NUT_SEAT_EDGE_MODEL = (FACE_X, -BORE_Y - 0.8 * _CBORE_R, BORE_Z + 0.6 * _CBORE_R)
NUT_SEAT_CALLOUT_XY = (0.159, 0.030)

_SEAT_PLACES = part_spec.SEAT_PLACES
_PATTERN_PLACES = part_spec.PATTERN_PLACES
_CALLOUT = part_spec.CALLOUT_PLACES


part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        ("_drawing_hole_callout", "add_native_hole_callout"),
    )
)

requirement(
    "block_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), 0.0),),
    requirements=("depth",),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        # The datum every Y station prints from; the -Y side from it.
        "depth": (
            limits(part_spec.BRACKET_DEPTH, part_spec.SIZE_PLACES),
            ("BRACKET_DEPTH", "SIZE_PLACES"),
        ),
        "depth_ref": (part_spec.BRACKET_DEPTH, ("BRACKET_DEPTH",)),
    },
    precision={"depth": part_spec.SIZE_PLACES},
)

requirement(
    "nut_face",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), part_spec.BRACKET_FACE_X),),
    requirements=("length",),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": FACE_X},
            ("FACE_X",),
        ),
        # The datum every X station prints from; the +X end milled to length
        # from it, two places for the #8 taps' end walls.
        "length": (
            limits(part_spec.BRACKET_LENGTH, part_spec.LENGTH_PLACES),
            ("BRACKET_LENGTH", "LENGTH_PLACES", "WORST_WALLS"),
        ),
        "length_nominal": (part_spec.BRACKET_LENGTH, ("BRACKET_LENGTH",)),
    },
    precision={"length": part_spec.LENGTH_PLACES},
)

requirement(
    "bottom_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        # The datum every Z station prints from; the top face from it.
        "height": (
            limits(part_spec.BRACKET_HEIGHT, part_spec.SIZE_PLACES),
            ("BRACKET_HEIGHT", "SIZE_PLACES"),
        ),
        "height_nominal": (part_spec.BRACKET_HEIGHT, ("BRACKET_HEIGHT",)),
    },
    precision={"height": part_spec.SIZE_PLACES},
)

_INTO_NUT_FACE = ([1.0, 0.0, 0.0], ("__frame__",))

requirement(
    "nut_seat",
    kind="hole",
    faces=(
        CylinderFace(
            part_spec.SCREW_CLEARANCE_DIA,
            contains_y_mm=-BORE_Y,
            contains_z_mm=BORE_Z,
        ),
    ),
    requirements=("dia", "thru", "width", "height", "note"),
    fields={
        "at": (list(part_spec.NUT_SEAT_POINT), ("NUT_SEAT_POINT",)),
        "axis": _INTO_NUT_FACE,
        "dia": (
            limits(part_spec.SCREW_CLEARANCE_DIA, _CALLOUT, part_spec.DRILLED_BAND),
            ("SCREW_CLEARANCE_DIA", "DRILLED_BAND"),
        ),
        "dia_nominal": (part_spec.SCREW_CLEARANCE_DIA, ("SCREW_CLEARANCE_DIA",)),
        "thru": (True, ("NUT_SEAT_SPEC",)),
        # From the Y = 0 face and the bottom face at two places: the
        # bracket's place on TL-22 is match-drilled, so they carry walls only.
        "width": (limits(BORE_Y, _SEAT_PLACES), ("BORE_Y", "SEAT_PLACES")),
        "width_nominal": (BORE_Y, ("BORE_Y",)),
        "height": (limits(BORE_Z, _SEAT_PLACES), ("BORE_Z", "SEAT_PLACES")),
        "height_nominal": (BORE_Z, ("BORE_Z",)),
        "note": (
            " ".join(NUT_SEAT_MATE_CALLOUT.splitlines()),
            (
                "NUT_SEAT_MATE_CALLOUT",
                "NUT_SEAT_LOCATES_CALLOUT",
                "NUT_ID",
                "RULE_20_SHORTFALLS",
            ),
        ),
    },
    precision={"dia": _CALLOUT, "width": _SEAT_PLACES, "height": _SEAT_PLACES},
)

requirement(
    "nut_seat_counterbore",
    kind="counterbore",
    faces=(CylinderFace(CBORE_DIA, contains_y_mm=-BORE_Y, contains_z_mm=BORE_Z),),
    requirements=("dia", "depth"),
    fields={
        "parent": (
            "nut_seat",
            ("NUT_SEAT_SPEC", ("draw_ch_rocker_arm_tl_oblique_nut_bracket", "build")),
        ),
        # The spigot's matched fit: the model band (CBORE_BAND), its mate in
        # the seat's callout.
        "dia": (
            limits(CBORE_DIA, _CALLOUT, part_spec.CBORE_BAND),
            ("CBORE_DIA", "CBORE_BAND", "SPIGOT_FLOAT"),
        ),
        "dia_nominal": (CBORE_DIA, ("CBORE_DIA",)),
        "depth": (
            limits(part_spec.CBORE_DEPTH, _CALLOUT),
            ("CBORE_DEPTH", "CALLOUT_PLACES"),
        ),
        "depth_ref": (part_spec.CBORE_DEPTH, ("CBORE_DEPTH",)),
    },
    precision={"dia": _CALLOUT, "depth": _CALLOUT},
)

_NUT_DRILL = round(NUT_TAP_DRILL, 2)
for _index, (_x, _y, _z) in enumerate(part_spec.NUT_HOLE_POINTS, start=1):
    requirement(
        f"nut_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(NUT_TAP_DRILL, contains_y_mm=_y, contains_z_mm=_z),),
        requirements=(
            "thread",
            "dia",
            "depth",
            "width",
            "height",
            "note",
        ),
        fields={
            "at": ([_x, _y, _z], ("NUT_HOLE_POINTS",)),
            "axis": _INTO_NUT_FACE,
            # Metric: the wizard carries no thread class (ANSI-inch only).
            "thread": (part_spec.NUT_THREAD, ("NUT_TAP_SPEC", "NUT_THREAD")),
            "tap_drill_mm": (NUT_TAP_DRILL, ("NUT_TAP_SPEC",)),
            "dia": (
                limits(_NUT_DRILL, _CALLOUT, part_spec.DRILLED_BAND),
                ("NUT_TAP_DRILL", "DRILLED_BAND"),
            ),
            "dia_nominal": (_NUT_DRILL, ("NUT_TAP_DRILL",)),
            # The drill's depth (the STEP cylinder); the thread depth it
            # serves prints in the callout.
            "depth": (
                limits(part_spec.NUT_TAP_DRILL_DEPTH, _CALLOUT),
                ("NUT_TAP_DRILL_DEPTH", "NUT_TAP_THREAD_DEPTH"),
            ),
            "depth_ref": (part_spec.NUT_TAP_DRILL_DEPTH, ("NUT_TAP_DRILL_DEPTH",)),
            # On the nut's circle, each way from the seat's axis, within the
            # nut's float: the counterbore locates its spigot on the pattern.
            # The offsets print on NUT_PATTERN_REFERENCE. No height_from: a
            # height_from measures across the two parallel axes (8.0 radial),
            # not along one offset.
            "width": (
                limits(NUT_HOLE_OFFSET, _PATTERN_PLACES),
                (
                    "NUT_HOLE_OFFSET",
                    "PATTERN_PLACES",
                    "NUT_PATTERN_REFERENCE",
                    "NUT_PATTERN_ALLOWANCE",
                ),
            ),
            "width_nominal": (NUT_HOLE_OFFSET, ("NUT_HOLE_OFFSET",)),
            "height": (
                limits(NUT_HOLE_OFFSET, _PATTERN_PLACES),
                (
                    "NUT_HOLE_OFFSET",
                    "PATTERN_PLACES",
                    "NUT_PATTERN_REFERENCE",
                    "NUT_PATTERN_ALLOWANCE",
                ),
            ),
            "height_nominal": (NUT_HOLE_OFFSET, ("NUT_HOLE_OFFSET",)),
            "note": (
                " ".join(NUT_TAP_PROCESS.split()),
                ("NUT_TAP_PROCESS", "NUT_PATTERN_ALLOWANCE", "POSITION_RADIUS"),
            ),
        },
        precision={
            "dia": _CALLOUT,
            "depth": _CALLOUT,
            "width": _PATTERN_PLACES,
            "height": _PATTERN_PLACES,
        },
    )

_BLOCK_DRILL = round(BLOCK_TAP_DRILL, 2)
for _index, ((_x, _y, _z), _station) in enumerate(
    zip(part_spec.BLOCK_SCREW_POINTS, SCREW_X, strict=True), start=1
):
    requirement(
        f"block_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(BLOCK_TAP_DRILL, contains_x_mm=_x, contains_z_mm=_z),),
        requirements=("thread", "dia", "depth", "note"),
        fields={
            "at": ([_x, _y, _z], ("BLOCK_SCREW_POINTS",)),
            "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "thread": (
                f"{part_spec.BLOCK_THREAD} UNC-{BLOCK_TAP_SPEC.thread_class}",
                ("BLOCK_TAP_SPEC", "BLOCK_THREAD"),
            ),
            "tap_drill_mm": (BLOCK_TAP_DRILL, ("BLOCK_TAP_SPEC",)),
            "dia": (
                limits(_BLOCK_DRILL, _CALLOUT, part_spec.DRILLED_BAND),
                ("BLOCK_TAP_DRILL", "DRILLED_BAND"),
            ),
            "dia_nominal": (_BLOCK_DRILL, ("BLOCK_TAP_DRILL",)),
            "depth": (
                limits(part_spec.BLOCK_TAP_DRILL_DEPTH, _CALLOUT),
                ("BLOCK_TAP_DRILL_DEPTH", "BLOCK_TAP_THREAD_DEPTH"),
            ),
            "depth_ref": (
                part_spec.BLOCK_TAP_DRILL_DEPTH,
                ("BLOCK_TAP_DRILL_DEPTH",),
            ),
            # Spotted from TL-22 at assembly: no printed station; the model's
            # nominal stations from the -X face and the bottom face.
            "station_nominal": (_station, ("SCREW_X",)),
            "height_nominal": (SCREW_Z, ("SCREW_Z",)),
            "note": (
                f"{BLOCK_TAP_PROCESS.strip()} {BLOCK_TAP_WALL_CALLOUT}",
                (
                    "BLOCK_TAP_PROCESS",
                    "PIVOT_BLOCK_NUMBER",
                    "X_SET_BAND",
                    "BLOCK_TAP_WALL_CALLOUT",
                    "RULE_20_SHORTFALLS",
                ),
            ),
        },
        precision={"dia": _CALLOUT, "depth": _CALLOUT},
    )


def nut_seat_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """DRILL in the native THRU row and the mate rows under the callout.

    draw_ch_rocker_arm_tl_oblique_pivot_block's counterbore callout: the THRU
    row is one of the upper parts (5..7), so the process goes into it, after
    any instance count; the CalloutBelow part (8) carries the nut the seat
    serves and rule 20's wall statement.
    """
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected nut-seat callout parts: {definitions!r}")
    thru_parts = [part for part, text in definitions.items() if "THRU" in text.upper()]
    if len(thru_parts) != 1 or thru_parts[0] == 8:
        raise RuntimeError(f"nut-seat THRU row is not one upper part: {definitions!r}")
    if definitions[8].strip():
        raise RuntimeError(f"nut-seat callout already prints below: {definitions!r}")
    part = thru_parts[0]
    text = definitions[part]
    count = re.match(r"\s*<NUM_INST>X ", text)
    if count:
        updated = f"{text[: count.end()]}{NUT_SEAT_PROCESS} {text[count.end() :]}"
    else:
        updated = compose_hole_callout_prefix(NUT_SEAT_PROCESS, text)
    return {**definitions, part: updated, 8: NUT_SEAT_MATE_CALLOUT}


@_telemetry.traced("drawing.nut_bracket.nut_seat_callout")
def _set_nut_seat_callout(display: Any) -> None:
    """Write the nut seat's process and mate rows; prove they persisted."""
    native = _early_bound(display, "IDisplayDimension")

    def read(parts: tuple[int, ...]) -> dict[int, str]:
        # Multi-line text may read back with CR LF (draw_pd_support_bar).
        return {
            part: str(native.GetText(part) or "").replace("\r", "") for part in parts
        }

    definitions = read((5, 6, 7, 8))
    updated = nut_seat_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = read((5, 6, 7, 8))
    resolved = read((1, 2, 3, 4))
    if persisted != updated or NUT_SEAT_PROCESS not in (resolved[3] + resolved[1]):
        raise RuntimeError(
            "nut-seat callout rows did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
    _telemetry.info(f"nut-seat callout: {resolved!r}")


def _omit_block_tap_thread_class(display: Any) -> None:
    """The title block's THREADS row owns the UNC class (rule 2): the #8 row
    reads ``8-32 UNC``, not ``... - 2B``. The metric callout keeps whatever
    the wizard prints: the row covers UNC/UNF only."""
    omit_title_block_thread_class(display, label="block-screw taps")
    native = _early_bound(display, "IDisplayDimension")
    resolved = [str(native.GetText(part) or "") for part in (1, 2, 3, 4)]
    if any(BLOCK_TAP_SPEC.thread_class in text for text in resolved):
        raise RuntimeError(
            f"block-screw taps: callout still prints its class: {resolved!r}"
        )


def block_tap_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Rule 20's end-wall row, last under the #8 callout's native rows."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected #8 callout parts: {definitions!r}")
    if any(BLOCK_TAP_WALL_CALLOUT in text for text in definitions.values()):
        raise RuntimeError(f"#8 callout already states its end wall: {definitions!r}")
    below = definitions[8].rstrip("\n")
    row = (
        f"{below}\n{BLOCK_TAP_WALL_CALLOUT}"
        if below.strip()
        else BLOCK_TAP_WALL_CALLOUT
    )
    return {**definitions, 8: row}


@_telemetry.traced("drawing.nut_bracket.block_tap_wall_row")
def _set_block_tap_wall_row(display: Any) -> None:
    """Write the #8 callout's end-wall row (CalloutBelow); prove it persisted."""
    native = _early_bound(display, "IDisplayDimension")

    def read(parts: tuple[int, ...]) -> dict[int, str]:
        return {
            part: str(native.GetText(part) or "").replace("\r", "") for part in parts
        }

    updated = block_tap_callout_definitions(read((5, 6, 7, 8)))
    native.SetText(4, updated[8])  # swDimensionTextCalloutBelow
    persisted = read((5, 6, 7, 8))
    resolved = read((1, 2, 3, 4))
    if persisted != updated or BLOCK_TAP_WALL_CALLOUT not in resolved[4]:
        raise RuntimeError(
            "#8 callout end-wall row did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
    _telemetry.info(f"#8 callout: {resolved!r}")


def _view_mapper(adapter: Any, view: Any):
    """Return model point (mm) -> sheet xy (m) through the view's transform."""
    transform = _early_bound(
        _early_bound(view, "IView").ModelToViewTransform, "IMathTransform"
    )
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def to_sheet(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([c / 1000.0 for c in model_mm])),
            "IMathPoint",
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    return to_sheet


def _require_axis(
    adapter: Any,
    view: Any,
    axis: tuple[float, float, float],
    angle: float,
    label: str,
) -> None:
    """A unit model axis (mm) must project at ``angle`` (rad) at 2:1."""
    to_sheet = _view_mapper(adapter, view)
    (ox, oy), (tx, ty) = to_sheet((0.0, 0.0, 0.0)), to_sheet(axis)
    dx, dy = tx - ox, ty - oy
    if (
        abs(math.hypot(dx, dy) - VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0)
        > PROJECTION_SLOP_M
        or abs(math.remainder(math.atan2(dy, dx) - angle, math.tau))
        > PROJECTION_ANGLE_SLOP
    ):
        raise RuntimeError(
            f"{label}: projected axis {(dx, dy)} is not at {angle:g} rad"
        )


@_telemetry.traced("drawing.nut_bracket.block_face_projection")
def _project_block_face_view(adapter: Any, left: Any, top: Any) -> None:
    """Stand the block face in third-angle projection over the nut face.

    The nut face shows +Z right and +Y up. Seen from +Y over it, the block
    face has +X up (its -X face next to the nut face) and +Z right; *Top
    places +X across, so it turns by the measured angle (draw_mg_output_
    fixture's end view), then its origin moves onto the nut face's x
    (c4-r3: the 90 deg turned block face beside the plan).
    """
    _require_axis(adapter, left, (0.0, 0.0, 1.0), 0.0, "nut face +Z")
    _require_axis(adapter, left, (0.0, 1.0, 0.0), math.pi / 2.0, "nut face +Y")
    native = _early_bound(top, "IView")
    to_sheet = _view_mapper(adapter, native)
    (ox, oy), (tx, ty) = to_sheet((0.0, 0.0, 0.0)), to_sheet((1.0, 0.0, 0.0))
    if math.hypot(tx - ox, ty - oy) <= PROJECTION_SLOP_M:
        raise RuntimeError("block face +X has no measurable projected direction")
    # No assumed +90/-90: rotate the measured +X direction to sheet up.
    native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(ty - oy, tx - ox)
    rebuild_drawing(adapter, label="turn nut bracket block face")
    _require_axis(adapter, native, (1.0, 0.0, 0.0), math.pi / 2.0, "block face +X")
    _require_axis(adapter, native, (0.0, 0.0, 1.0), 0.0, "block face +Z")
    target = (_view_mapper(adapter, left)((0.0, 0.0, 0.0))[0], TOP_CENTER[1])
    at = _view_mapper(adapter, native)((0.0, 0.0, 0.0))
    position = tuple(float(value) for value in native.Position)
    moved = [position[axis] + target[axis] - at[axis] for axis in range(2)]
    if native.SetViewPosition(double_array(moved), False) is not True:
        raise RuntimeError("failed to pin the nut bracket block face in projection")
    rebuild_drawing(adapter, label="pin nut bracket block face")
    at = _view_mapper(adapter, native)((0.0, 0.0, 0.0))
    if math.dist(at, target) > PROJECTION_SLOP_M:
        raise RuntimeError(
            f"block face origin {at} is not over the nut face's {target}"
        )
    _telemetry.success(f"block face in projection: +X up, +Z right; origin {at}")


def _set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, prefix)  # swDimensionTextPrefix
        if str(display.GetText(1) or "") != prefix:
            raise RuntimeError(f"dimension prefix {prefix!r} did not persist")
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


def _set_arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    remaining = set(ARROWS_INSIDE)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        remaining.discard(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"nut bracket {name} did not keep its arrows inside")
    if remaining:
        raise RuntimeError(
            f"no nut bracket dimension to set arrows inside: {sorted(remaining)}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open nut bracket source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Nut Bracket Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel nut bracket; 6061-T6 flat; MHA-CH-06-TL-29",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, top, left, iso):
        set_hidden_lines_removed(adapter, view)
    _project_block_face_view(adapter, left, top)

    annotations = []
    for view, keep, view_label in (
        (front, FRONT_KEEP, "nut bracket plan"),
        (top, TOP_KEEP, "nut bracket block face"),
    ):
        mapper = _view_mapper(adapter, view)
        annotations += curate_view_dimensions(
            adapter,
            view,
            keep={name: mapper(xyz) for name, xyz in keep.items()},
            view_label=view_label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    # The M3 offsets live on NutPatternReference, a sketch the part saves
    # hidden: the nut face shows it per view (_drawing_hidden_sketches).
    on_left = _view_mapper(adapter, left)
    annotations += hidden_sketches.curate_view_dimensions(
        adapter,
        left,
        keep={name: on_left(xyz) for name, xyz in LEFT_KEEP.items()},
        view_label="nut bracket nut face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)
    _set_arrows_inside(adapter, annotations)

    for view, label in ((top, "block face"), (left, "nut face")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to the {label} view")
    on_top = _view_mapper(adapter, top)
    block_taps = add_native_hole_callout(
        adapter,
        top,
        edge_xy=on_top(BLOCK_TAP_EDGE_MODEL),
        callout_xy=BLOCK_TAP_CALLOUT_XY,
        label="block-screw taps",
        process=BLOCK_TAP_PROCESS,
    )
    _omit_block_tap_thread_class(block_taps)
    _set_block_tap_wall_row(block_taps)
    add_native_hole_callout(
        adapter,
        left,
        edge_xy=on_left(NUT_TAP_EDGE_MODEL),
        callout_xy=NUT_TAP_CALLOUT_XY,
        label="nut-screw taps",
        process=NUT_TAP_PROCESS,
    )
    _set_nut_seat_callout(
        add_native_hole_callout(
            adapter,
            left,
            edge_xy=on_left(NUT_SEAT_EDGE_MODEL),
            callout_xy=NUT_SEAT_CALLOUT_XY,
            label="nut seat",
        )
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Nut Bracket Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "... Tapped Hole" note beside each tap
        # carrying a hole callout (base bar, end bracket: one per
        # callout). c4-r2's "#8-32 Tapped Hole" (DetailItem349) sat across
        # the #8 leader; each callout already states its thread. Two tap
        # features with callouts (#8-32, M3x0.5), two notes.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=2,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
