r"""Create the manufacturing drawing for the output fixture (MHA-MG-006).

The SLDPRT is authoritative: every printed dimension, its places and its
band are model dimensions marked for the drawing
(``mg_output_fixture_spec.DRAWING_DIMENSIONS``); this recipe places views,
keeps each dimension where it reads, and proves the import kept the part's
places. Sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The side view is the ``*Top`` orientation, as in the lathe: the hex axis
horizontal, looking straight down the reamed rod bore, the flats edge-on top
and bottom.  It carries every axial station from the free end, the spigot
and groove sizes and the bore's Ø; the groove's root Ø nests inside the
spigot's, right of the face, each a dimension line standing across its
diameter.  The end view is the ``*Right`` projection, looking at the spigot
face with the flats standing vertical; it carries the flats as a stock
reference, (9.525), and the #4-40 tap's native callout: the drill and its
controlling depth, then the thread and its nominal depth as a reference,
(10.1), INTO BORE.  The notes name the plug tap and say the rod bore ends
the thread.  The rod bore is centred on the hex axis (a note), so nothing
locates it from a flat.  Hidden lines stay off: the tap is a standard hole
its callout states.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_output_fixture.py mg-output-fixture
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

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
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leaders import Segment, dimension_segments
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from _gear_drawing_entities import visible_circle_edge
from mg_output_fixture_geom import (
    FREE_END_X,
    GROOVE_ROOT_DIA,
    GROOVE_X,
    HEX_AF,
    HEX_CORNER_RADIUS,
    SHOULDER_X,
    SPIGOT_FACE_X,
    TAP_DRILL_DEPTH,
    TAP_DRILL_DIA,
    TAP_LENGTH,
)
from mg_output_fixture_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
    ROD_BORE_CALLOUT,
    TAP_CALLOUT_PRECISION,
    TAP_DEPTH_PLACES,
    TAP_DRILL_DEPTH_VARIABLE,
    TAP_PROCESS,
    TAP_SPEC,
    TAP_THREAD_DEPTH_VARIABLE,
)


SPEC = DRAWINGS_BY_NAME["mg_output_fixture"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# A 17.7 x 11 part: 4:1 leaves room for the side view's eight dimensions.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.125, 0.180)
END_CENTER = (0.262, SIDE_CENTER[1])
# Low right, over the title block: the end view's tap callout runs out to
# the right at the hole's height, above it.
ISO_CENTER = (0.372, 0.115)
NOTES_XY = (0.016, 0.078)
# The side view is centred on the part's axial extent.
_AXIAL_MID = (FREE_END_X + SPIGOT_FACE_X) / 2.0
_HALF_AF = HEX_AF / 2.0


def _side_x(model_x_mm: float) -> float:
    """Sheet X of a station along the hex axis on the side view."""
    return SIDE_CENTER[0] + (model_x_mm - _AXIAL_MID) * _S / 1000.0


def _side_y(sketch_v_mm: float) -> float:
    """Sheet Y of a Top-plane sketch height on the side view (sheet up is
    sketch +v, model -Z)."""
    return SIDE_CENTER[1] + sketch_v_mm * _S / 1000.0


_SIDE_TOP = _side_y(_HALF_AF)
_SIDE_BOTTOM = _side_y(-_HALF_AF)
# Printed text extents on the 2026-10-12 farm sheets (the layout audit's
# boxes), used to hold each text clear of the witnesses beside it.  The two
# turned Ø texts print the same glyphs: retry09's " Ø9.00 ±0.05 " and
# " Ø7.00 ±0.05 " each ran 29.8 mm (runs of 1.29, 5.28 and 23.25 mm,
# 20261012T124257186Z).
TURNED_DIA_TEXT_HALF_WIDTH = 0.0149
BORE_CALLOUT_HALF_WIDTH = 0.0138  # Ø5.20 +0.03/0.00 over REAM THRU: 27.5 mm
BORE_CALLOUT_HALF_HEIGHT = 0.0073  # shoulder to the +0.03 row's top: 14.6 mm
# Every station on the side view is witnessed from the free end's mid point,
# the ridge between the two hex faces the view looks across: the hex and
# groove stations rise from it, the bore's station and the overall length
# hang from it, so witnesses cover the free end's whole height bar the ridge
# and fence the bore in from the left.  The bore's Ø therefore reads over
# the hex, mid-span between the free end's and the shoulder's witnesses, its
# leader rising from the bore's upper rim across the hex's top edge alone;
# the hex and groove stations stack over it, each text mid-span.  The
# overall length runs under the view, outermost; its witness hangs from the
# spigot face's top corner down the face.  The groove's radius (its sketch
# sits on the upper side, sketch +v) reads beyond the face, just over the
# spigot's top edge, its shoulder clear.  The bore's station (a 20 mm span
# under a 22 mm text) reads outside, left of the free end.
#
# The two turned Ø stack right of the face, the smaller inside: the groove
# root's extension lines run from the two roots across the face-side lip to
# its dimension line, which stands root to root, and the spigot's stands a
# pitch further out.  Each text breaks its own dimension line, the root's
# below the axis and the spigot's above, so neither text crosses the other's
# line and the two never read as one row.  Retry09 hung the root's text
# under the view instead: SolidWorks ran its dimension line 20 mm down out of
# the groove into a 30 mm horizontal shoulder beside the bore's station, and
# the Ø read as an axial length (machinist review09).
_FACE_SHEET_X = _side_x(SPIGOT_FACE_X)
# Air from the root Ø's text to the face and the overall length's witness.
_TEXT_TO_FACE = 0.004
# The spigot's dimension line outboard of the root's: each text then clears
# the other's dimension line by 5 mm.
_STACKED_DIA_PITCH = 0.020
# Each Ø text's offset from the axis: the two texts' centres 10 mm apart.
_STACKED_DIA_STAGGER = 0.005
_GROOVE_ROOT_DIA_X = _FACE_SHEET_X + _TEXT_TO_FACE + TURNED_DIA_TEXT_HALF_WIDTH
_HEX_MID_X = _side_x((FREE_END_X + SHOULDER_X) / 2.0)
SIDE_KEEP = {
    "RodBoreDia": (_HEX_MID_X, _SIDE_TOP + 0.011),
    "HexLength": (_HEX_MID_X, _SIDE_TOP + 0.025),
    "GrooveStation": (_side_x((FREE_END_X + GROOVE_X) / 2.0), _SIDE_TOP + 0.035),
    "OverallLength": (_side_x(_AXIAL_MID), _SIDE_BOTTOM - 0.032),
    "RodStation": (_side_x(FREE_END_X) - 0.015, _SIDE_BOTTOM - 0.010),
    "GrooveRootDia": (_GROOVE_ROOT_DIA_X, SIDE_CENTER[1] - _STACKED_DIA_STAGGER),
    "SpigotDia": (
        _GROOVE_ROOT_DIA_X + _STACKED_DIA_PITCH,
        SIDE_CENTER[1] + _STACKED_DIA_STAGGER,
    ),
    "GrooveRadius": (_FACE_SHEET_X + 0.012, _SIDE_TOP + 0.006),
}
# The groove's root Ø is a doubled distance, the groove's axis to its root
# point (build_mg_output_fixture._groove_profile: AddSpecificDimension
# swDiametricLinearDimension, Diametric proven on the part), so the sheet
# reads it as a diameter only while its dimension line stands across the
# groove, root to root.  Diametric toggles a doubled distance between the
# radial-linear and diametric-linear types; no seat has yet shown which
# Type2 a diametric one reports, so the proof takes either with Diametric
# set, and logs which.
_DOUBLED_DISTANCE_TYPES = {
    14: "swRadialLinearDimension",
    15: "swDiametricLinearDimension",
}
GROOVE_ROOT_SHEET_YS = (
    _side_y(-GROOVE_ROOT_DIA / 2.0),
    _side_y(GROOVE_ROOT_DIA / 2.0),
)
# GetDisplayData reads the window's rendering, up to ~1.1 mm off the print at
# fit (the layout doc's COM traps); retry09's stray leg ran 20 mm.
GROOVE_ROOT_INK_SLOP = 0.0015
# SolidWorks starts an extension line 1 mm off its feature (retry09: the
# spigot Ø's, 1.0 mm right of the face).
EXTENSION_START_GAP = 0.001
# The end view stands the flats vertical (``*Right`` looks along -X, sheet
# right is model -Z).  Its one dimension, the flats' stock reference,
# witnesses the near (right) flat from its top corner and reads above the
# hex, mid-span, so nothing hangs down that flat where the tap's leader
# crosses it.
_END_HALF_HEIGHT = HEX_CORNER_RADIUS * _S / 1000.0
_END_HALF_WIDTH = HEX_AF / 2.0 * _S / 1000.0
END_KEEP = {
    "HexAf": (END_CENTER[0], END_CENTER[1] + _END_HALF_HEIGHT + 0.022),
}
# The tap callout reads right of the end view at the hole's height: its
# leader leaves the drill circle a few degrees above the horizontal centre
# mark and crosses only the near flat, below the witness rising from the
# flat's top corner.  ``callout_xy`` is the text's centre; the shoulder sits
# under the bottom row, ~5.6 mm below the centre (the v1 sheet's ink: centre
# (292, 134), shoulder end (254.0, 128.4)).  The v1 sheet's 28-glyph thread
# row, TAP TO BORE 4-40 UNC-2B THRU, ran ~76 mm; retry09's
# TAP INTO BORE 4-40 UNC - 2B (depth) 10.1 printed 81.7 mm, centred on
# callout_xy (20261012T124257186Z).  The reference brackets, (10.1), add two
# ~1.2 mm glyphs: ~84 mm, inside the ~87 mm this half width holds.
_TAP_CALLOUT_HALF_WIDTH = 0.0435
_TAP_CALLOUT_SHOULDER_DROP = 0.0056
TAP_CALLOUT_XY = (
    END_CENTER[0] + _END_HALF_WIDTH + 0.006 + _TAP_CALLOUT_HALF_WIDTH,
    END_CENTER[1] + 0.004 + _TAP_CALLOUT_SHOULDER_DROP,
)
# What the native callout must print: the thread itself, not just the drill.
_TAP_THREAD_TEXT = f"{TAP_SPEC.size.lstrip('#')} UNC"
# A band on either depth: the thread's is REF (bracketed), the drill's is the
# title block's .X.
_BAND_MARKS = ("<MOD-PM>", "±", "+/-")
# SolidWorks' own descriptive "#4-40 Tapped Hole" note: the native callout
# states the thread, so none may reach the print.  How many SolidWorks pins
# is the tap's, measured, not derived: with the same three views, the same
# sketch-only targeted imports (the tap is never imported) and the same
# centre-mark recipe, the up-to-next tap (TAP TO BORE 4-40 UNC - 2B THRU)
# brought one on swmaker000005 and on swmaker000009 (farm runs
# 20261012T025810090Z, 20261012T064524082Z: "removed 1 redundant final
# drawing notes"), and the blind tap that replaced it brings none (retry08,
# 20261012T111849499Z on swmaker000005: "removed 0 ..., expected 1").
# finalize_drawing still sweeps every sheet for the note, so one that comes
# back fails the census instead of printing beside the callout.
TAPPED_HOLE_NOTE = "Tapped Hole"
AUTO_TAPPED_HOLE_NOTES = 0


def _states_depth(text: str, depth_mm: float, *, reference: bool) -> bool:
    """Whether ``text`` prints ``depth_mm`` at the tap's depth places as a
    whole number (10.1 is not 110.1 or 10.15): in reference brackets, (10.1),
    when ``reference``, else bare."""
    printed = re.escape(f"{depth_mm:.{TAP_DEPTH_PLACES}f}")
    number = rf"(?<![\d.]){printed}(?!\d)"
    if reference:
        return re.search(rf"\(\s*{number}\s*\)", text) is not None
    return re.search(rf"(?:^|[^(\s])\s*{number}(?!\s*\))", text) is not None


def _tap_callout_resolved(resolved_parts: dict[int, str]) -> bool:
    """Whether the thumb-screw tap's callout reads as a blind tap into the
    bore: one thread row carries the process, the thread, its class and its
    nominal thread depth as a reference, (10.1), never bare; the drill row
    its controlling depth, bare; nothing is banded; and nothing says THRU
    (the tap stops in the bore, short of its far wall)."""
    lines = [text for text in resolved_parts.values() if text.strip()]
    thread = [text for text in lines if _TAP_THREAD_TEXT in text]
    drill = [text for text in lines if _TAP_THREAD_TEXT not in text]
    return (
        not any("THRU" in text for text in lines)
        and not any(mark in text for text in lines for mark in _BAND_MARKS)
        and len(thread) == 1
        and TAP_PROCESS in thread[0]
        and TAP_SPEC.thread_class in thread[0]
        and _states_depth(thread[0], TAP_LENGTH, reference=True)
        and not _states_depth(thread[0], TAP_LENGTH, reference=False)
        and any(_states_depth(text, TAP_DRILL_DEPTH, reference=False) for text in drill)
        and not any(_states_depth(text, TAP_DRILL_DEPTH, reference=True) for text in lines)
    )


# swDimensionTextParts_e: a hole callout's definitions (5-8: prefix, suffix,
# callout above, callout below) and the writable part each is set through
# (1-4), as draw_fr_harmonic_base._set_cross_tap_callout_text writes 3 and
# reads back 7.
_CALLOUT_DEFINITION_PARTS = {5: 1, 6: 2, 7: 3, 8: 4}
_THREAD_DEPTH_TOKEN = f"<{TAP_THREAD_DEPTH_VARIABLE}>"
_DRILL_DEPTH_TOKEN = f"<{TAP_DRILL_DEPTH_VARIABLE}>"


def reference_thread_depth_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """The callout's definitions with the thread depth's variable bracketed,
    ``(<hw-threaddepth>)``, and every other character as it was.

    ASME Y14.5 marks a reference dimension by enclosing it in parentheses.
    The variable stays in the definition, so the bracketed value is still the
    model's thread depth.  Exactly one unbracketed thread-depth variable must
    be defined, and the drill depth's, which governs, exactly once and bare.
    """
    joined = "\n".join(definitions.values())
    if (
        joined.count(_THREAD_DEPTH_TOKEN) != 1
        or f"({_THREAD_DEPTH_TOKEN}" in joined
        or joined.count(_DRILL_DEPTH_TOKEN) != 1
        or f"({_DRILL_DEPTH_TOKEN}" in joined
    ):
        raise RuntimeError(
            f"expected one bare {_THREAD_DEPTH_TOKEN} and one bare "
            f"{_DRILL_DEPTH_TOKEN} in the tap callout's definitions: {definitions!r}"
        )
    return {
        part: text.replace(_THREAD_DEPTH_TOKEN, f"({_THREAD_DEPTH_TOKEN})")
        for part, text in definitions.items()
    }


def _reference_thread_depth(display: Any) -> None:
    """Bracket the native callout's thread depth as REF, in the definition.

    Only the definition holding the thread depth is written; the readback
    must hold all four, the process prefix and the bare drill depth included.
    """
    before = {part: str(display.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS}
    wanted = reference_thread_depth_definitions(before)
    (part,) = [part for part in before if wanted[part] != before[part]]
    display.SetText(_CALLOUT_DEFINITION_PARTS[part], wanted[part])
    after = {part: str(display.GetText(part) or "") for part in _CALLOUT_DEFINITION_PARTS}
    if after != wanted:
        raise RuntimeError(
            f"thumb-screw tap thread depth did not persist as REF: wanted {wanted!r}, "
            f"read {after!r}"
        )
    _telemetry.success(
        f"thumb-screw tap thread depth bracketed REF: definition {part} {wanted[part]!r}"
    )


def _check_tap_callout(display: Any) -> None:
    """Prove the callout states the tap, its depths and its process."""
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    if not _tap_callout_resolved(resolved):
        raise RuntimeError(
            f"thumb-screw tap callout does not state {TAP_PROCESS} "
            f"{_TAP_THREAD_TEXT}-{TAP_SPEC.thread_class} to "
            f"({TAP_LENGTH:.{TAP_DEPTH_PLACES}f}) REF over a bare "
            f"{TAP_DRILL_DEPTH:.{TAP_DEPTH_PLACES}f} drill: {resolved!r}"
        )
    _telemetry.success(f"thumb-screw tap callout reads {resolved!r}")


def _groove_root_ink_problem(segments: list[Segment], line_x: float) -> str | None:
    """Why the groove root Ø's ink does not read as a diameter across the
    groove, or None.

    Its dimension line stands at ``line_x`` from one root to the other and
    leaves neither; one extension line runs from each root, starting at the
    groove, out to that line; and it draws nothing else: no leg out of the
    groove, no shoulder under a text.
    """
    slop = GROOVE_ROOT_INK_SLOP
    groove_x = _side_x(GROOVE_X)
    line_ys: list[float] = []
    extension_xs: dict[float, list[float]] = {root: [] for root in GROOVE_ROOT_SHEET_YS}
    for (x0, y0), (x1, y1) in segments:
        if abs(x0 - line_x) <= slop and abs(x1 - line_x) <= slop:
            line_ys += [y0, y1]
            continue
        roots = [
            root
            for root in GROOVE_ROOT_SHEET_YS
            if abs(y0 - root) <= slop and abs(y1 - root) <= slop
        ]
        if not roots:
            return (
                f"stroke ({x0 * 1000:.2f}, {y0 * 1000:.2f})-({x1 * 1000:.2f}, "
                f"{y1 * 1000:.2f}) mm is neither its dimension line nor a root's "
                "extension line"
            )
        extension_xs[roots[0]] += [x0, x1]
    low, high = GROOVE_ROOT_SHEET_YS
    if not line_ys:
        return f"no dimension line at x {line_x * 1000:.2f} mm"
    if abs(min(line_ys) - low) > slop or abs(max(line_ys) - high) > slop:
        return (
            f"dimension line spans y {min(line_ys) * 1000:.2f}..{max(line_ys) * 1000:.2f}"
            f" mm, not root to root, {low * 1000:.2f}..{high * 1000:.2f} mm"
        )
    for root, xs in extension_xs.items():
        if not xs:
            return f"no extension line from the root at y {root * 1000:.2f} mm"
        if (
            min(xs) < groove_x - slop
            or min(xs) > groove_x + EXTENSION_START_GAP + slop
            or max(xs) < line_x - slop
        ):
            return (
                f"extension line at y {root * 1000:.2f} mm spans x "
                f"{min(xs) * 1000:.2f}..{max(xs) * 1000:.2f} mm, not the groove at "
                f"{groove_x * 1000:.2f} mm out to the dimension line"
            )
    return None


def _prove_groove_root_diameter(annotation: Any) -> None:
    """Prove the sheet's groove root Ø is the part's doubled distance and
    prints across the groove, root to root."""
    display = _early_bound(
        _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    kind, diametric = int(display.Type2), bool(display.Diametric)
    if kind not in _DOUBLED_DISTANCE_TYPES or not diametric:
        raise RuntimeError(
            f"GrooveRootDia is dimension type {kind}, Diametric {diametric}: not "
            "the part's doubled distance from the groove's axis to its root"
        )
    line_x = SIDE_KEEP["GrooveRootDia"][0]
    segments = dimension_segments(annotation)
    problem = _groove_root_ink_problem(segments, line_x)
    if problem is not None:
        raise RuntimeError(f"GrooveRootDia does not print across the groove: {problem}")
    _telemetry.success(
        f"groove root Ø is {_DOUBLED_DISTANCE_TYPES[kind]} ({kind}), Diametric, "
        f"{len(segments)} strokes standing root to root at x {line_x * 1000:.2f} mm"
    )


# The template centre-marks every hole as each view is placed (the knife
# mount's convention, #913), so the end view arrives with its tap marked:
# AutoInsertCenterMarks2 printed a second mark over it (DetailItem347/350,
# 2026-10-12 farm sheet), and so did an explicit InsertCenterMark3 on the
# drill circle (run05: found 2).  The sheet adds none; it proves the one.
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
# How far the mark's ink centre may sit from the tap's axis on the sheet.
CENTER_MARK_AXIS_SLOP = 0.0005


def _ink_centre(annotation: Any, label: str) -> tuple[float, float]:
    """The centre of the box of every line an annotation draws, in sheet
    metres: a single mark's arms and extended lines are symmetric about its
    axis."""
    data = _early_bound(annotation, "IAnnotation").GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label} has no display data")
    data = _early_bound(data, "IDisplayData")
    lines = [
        tuple(float(value) for value in data.GetLineAtIndex2(index))
        for index in range(int(data.GetLineCount()))
    ]
    if not lines:
        raise RuntimeError(f"{label} draws no line")
    # GetLineAtIndex2: (colour, line type, unused, unused, start xyz, end xyz).
    xs = [value for line in lines for value in (line[4], line[7])]
    ys = [value for line in lines for value in (line[5], line[8])]
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def _prove_tap_centre_mark(adapter: Any, view: Any, drill_edge: Any) -> None:
    """Prove the end view carries exactly one centre mark, on the tap's axis
    (the drill circle's centre projected to the sheet)."""
    curve = _early_bound(drill_edge, "IEdge").GetCurve()
    if curve is None:
        raise RuntimeError("the thumb-screw tap drill edge has no curve")
    circle = _early_bound(curve, "ICurve").CircleParams
    if circle is None or len(circle) < 3:
        raise RuntimeError("the thumb-screw tap drill edge reports no circle centre")
    axis = model_point_in_view(
        adapter,
        view,
        (float(circle[0]), float(circle[1]), float(circle[2])),
        label="thumb-screw tap axis",
    )
    marks = tuple(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != 1:
        raise RuntimeError(
            f"expected one tap centre mark on the end view, found {len(marks)}"
        )
    centre = _ink_centre(marks[0], "thumb-screw tap centre mark")
    offset = math.hypot(centre[0] - axis[0], centre[1] - axis[1])
    if offset > CENTER_MARK_AXIS_SLOP:
        raise RuntimeError(
            f"the end view's centre mark sits {offset * 1000.0:.2f} mm off the tap "
            f"axis: mark {centre}, axis {axis}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open output-fixture source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Output Fixture Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "output fixture; 3/8 hex brass; reamed rod bore; wire groove; #4-40 tap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Top", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places (and so each dimension's general row) are authored on the part;
    # the sheet only proves the import kept them.
    assert_imported_precision(
        adapter, [*side_annotations, *end_annotations], DRAWING_PRECISION_BY_NAME
    )
    set_dimension_callouts(adapter, side_annotations, {"RodBoreDia": ROD_BORE_CALLOUT})
    # The flats are the bar's as supplied: a stock reference, not a size the
    # shop holds to three places.
    end_by_name = {dimension_name(adapter, a): a for a in end_annotations}
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, end_by_name[name], label=f"MHA-MG-006 {name} stock reference"
        )
    if not auto_center_marks(adapter, side, holes=True, size=0.0025):
        raise RuntimeError("failed to add the rod bore's center mark to the side view")
    # The tap drill's edge on the spigot face: the one visible circle of the
    # Hole Wizard feature from the end.  Its axis carries the view's one
    # centre mark, and the native callout prints the drill row and, under
    # it, the process on the thread row; both depths print at one place, the
    # thread's bracketed as REF.
    tap_drill = visible_circle_edge(adapter, end, TAP_DRILL_DIA)
    _prove_tap_centre_mark(adapter, end, tap_drill)
    tap_callout = add_native_hole_callout(
        adapter,
        end,
        edge=tap_drill,
        callout_xy=TAP_CALLOUT_XY,
        label="#4-40 thumb-screw tap",
        process=TAP_PROCESS,
    )
    _reference_thread_depth(tap_callout)
    set_hole_callout_precision(
        tap_callout, TAP_CALLOUT_PRECISION, label="#4-40 thumb-screw tap depths"
    )
    _check_tap_callout(tap_callout)
    # Last before the notes: everything that moves ink on the side view has run.
    side_by_name = {dimension_name(adapter, a): a for a in side_annotations}
    _prove_groove_root_diameter(side_by_name["GrooveRootDia"])
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Output Fixture Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # The blind tap pins no descriptive note (``AUTO_TAPPED_HOLE_NOTES``);
        # the sweep proves none reached any sheet.
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=AUTO_TAPPED_HOLE_NOTES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
