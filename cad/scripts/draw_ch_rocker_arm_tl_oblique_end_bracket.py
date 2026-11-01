r"""Create the drawing for the oblique-trammel jig's end bracket (MHA-CH-06-TL-28).

One part, two off (the title block's quantity). A 2.71 x 1/2 x 1 in flat at
2:1: the plan (the *Front view, looking down on the top face) carries the
six tap stations from the inner end and the length, all stacked below it,
the row's station from the -Y side face (left), the stock width (right) and
one native callout per tap over it, each leader on its own hole; the end
view, projected right of the plan, carries the stock thickness; the shaded
isometric rides top right at 1:1, clear of the title block. No datums
(drawing-guidelines.md rule 5). The two KP08 tap stations print exact
millimetres, labelled mm (owner ruling 4, 2026-11-01).

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_end_bracket.py ch-rocker-arm-tl-oblique-end-bracket
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
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
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_end_bracket_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import limits
from _drawing_metric_vendor import print_imported_metric_dimensions
from _supplier_dimensions import supplier_reference_dimension
from ch_rocker_arm_tl_oblique_callouts import set_callout_lengths_to_three_places
from ch_rocker_arm_tl_oblique_end_bracket_spec import (
    BAR_MATE_CALLOUT,
    BAR_TAP_DRILL,
    BAR_TAP_SPEC,
    BAR_TAP_X,
    BRACKET_LENGTH,
    BRACKET_THICK,
    BRACKET_WIDTH,
    CALLOUTS_BELOW,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HALF_WIDTH,
    HOLE_ROW_Y,
    KP08_MATE_CALLOUT,
    KP08_TAP_DRILL,
    KP08_TAP_SPEC,
    KP08_TAP_X,
    METRIC_DIMENSIONS,
    ROW_CALLOUT,
    STOCK_CALLOUT,
    STOCK_FRACTION_DENOMINATORS,
    TAP_CALLOUT_PLACES,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_end_bracket"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# The 68.9 bracket at 2:1 (ruling A′: flush with the 1/2 x 6 bar's column
# edge, four bar taps): the plan outline spans sheet x 96.1..233.9; the end
# view projects right of it on its centreline (third angle). The 1/2 x 1 bar
# on edge makes the end view 50.8 wide (outline x 267.6..318.4), so the 1:1
# iso stands 20 further right, its note under it, all above the title block
# (x 216 on, up to y 70) and under the 267 border. The tap callouts stand in
# three tiers a layout-audit row pitch apart (c4-r8: at 6 the audit merged
# each side's three blocks), high enough that the right-hand ones clear the
# end view; the plan drops 4 to keep the top tier under the border.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
ISO_SCALE = (1, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
PLAN_CENTER = (0.165, 0.1925)
END_CENTER = (0.293, PLAN_CENTER[1])
ISO_CENTER = (0.378, 0.195)
ISO_NOTE_XY = (0.350, 0.155)
ISO_HALF = (0.030, 0.025)  # the iso's half extents (sheet m)

# Every text position is a MODEL point (mm) off the part, mapped onto its
# view at run time (draw_ch_rocker_arm_tl_oblique_feed_lever). In the plan
# model +X runs right and +Y up; text sizes are sheet mm halved at 2:1.
# A keep point is its text block's centre; SolidWorks hangs the dimension
# line about TEXT_DROP below a one-line block and TWO_LINE_DROP below a
# two-line one (base bar readback), so every station's text sits on the
# part side of its line under the plan.
_H = BRACKET_THICK
_L = BRACKET_LENGTH
_HW = HALF_WIDTH
STACK_FIRST = 8.0 / _S
STACK_LANE = 6.0 / _S  # ASME Y14.5's 6 sheet mm between one-line lanes
TEXT_DROP = 2.7 / _S
TWO_LINE_DROP = 5.6 / _S
TEXT_GAP = 2.5 / _S  # a text's clearance from the line it sits beside
EXT_OVERSHOOT = 1.5 / _S  # an extension line's run past its dimension line
SIDE_LANE = 8.0 / _S  # first side-dimension line off the part
# One 3.5 mm capital's advance: the c4-r2 readback measured 2.43 .. 2.74
# sheet mm ("MATCHES KP08 BLOCK HOLES" the widest); take the widest.
GLYPH = 2.75 / _S
ROW_PITCH = 5.56 / _S  # text rows (draw_ch_rocker_arm_tl_oblique_pivot_block)
# The layout audit reads two blocks stacked closer than its 5.66 mm row pitch
# as one ([merged-blocks], c4-r8).
STACK_PITCH = 5.66 / _S


def text_half(text: str) -> float:
    """Half the widest line of ``text`` (model mm)."""
    return max(len(line) for line in text.split("\n")) * GLYPH / 2.0


def text_half_high(rows: int) -> float:
    """Half a ``rows``-line block's height (model mm), 3.5 mm glyphs."""
    return ((rows - 1) * ROW_PITCH + 3.5 / _S) / 2.0


# A two-line block's far edge from its own line, plus the gap to the next.
MATE_LANE = TWO_LINE_DROP + text_half_high(2) + TEXT_GAP
# c4-r3: the row's station dimension line ran 6.35 sheet mm past the -Y side.
ROW_TAIL = 6.35 / _S
# The dimension lines below the plan, nearest first, shortest span nearest:
# the first block clears the row station's line tail, each next one the line
# above it; the length's one-line block clears the last station's line.
STATION_ORDER = (
    "BarTap1X",
    "KP08Tap1X",
    "BarTap2X",
    "BarTap3X",
    "KP08Tap2X",
    "BarTap4X",
)
_FIRST_LANE = -_HW - ROW_TAIL - TEXT_GAP - (TWO_LINE_DROP + text_half_high(2))
STATION_LANES = tuple(_FIRST_LANE - i * MATE_LANE for i in range(len(STATION_ORDER)))
LENGTH_LANE = STATION_LANES[-1] - (TEXT_GAP + TEXT_DROP + text_half_high(1))


def plan_sheet(x: float, y: float) -> tuple[float, float]:
    """Sheet xy (m) of a plan model point: the view centres on its outline."""
    return (
        PLAN_CENTER[0] + (x - _L / 2.0) * _S / 1000.0,
        PLAN_CENTER[1] + y * _S / 1000.0,
    )


_ROW_TEXT = "\n".join((f"{HOLE_ROW_Y / 25.4:.3f}".lstrip("0"), ROW_CALLOUT))
_ROW_ROWS = _ROW_TEXT.count("\n") + 1


def _outboard_left(mate: str) -> float:
    """Centre X of a station block standing left of the inner end's line."""
    return -(TEXT_GAP + text_half(mate))


_STATIONS = {
    name: KP08_MATE_CALLOUT if name.startswith("KP08") else BAR_MATE_CALLOUT
    for name in STATION_ORDER
}
# The plan. Every station is a DRO absolute from the inner end carrying its
# mate on a second line. The blocks are wider than their spans, so each
# stands left of the inner end's extension line, where none of the other
# stations' extension lines (all at X >= 7.5) pass (c4-r3: the 14 and 56
# stacks over the plan crowded the tap callouts off the 14 and 24 holes).
# Left of the plan: the row's station from the -Y side face, its three-line
# block between its own extension lines. Right of it: the stock width.
PLAN_KEEP: dict[str, tuple[float, float, float]] = {
    **{
        name: (
            _outboard_left(_STATIONS[name]),
            STATION_LANES[lane] + TWO_LINE_DROP,
            _H,
        )
        for lane, name in enumerate(STATION_ORDER)
    },
    "BracketLength": (_L / 2.0, LENGTH_LANE + TEXT_DROP, _H),
    "HoleRowY": (-(SIDE_LANE + TEXT_GAP + text_half(_ROW_TEXT)), -HOLE_ROW_Y / 2.0, _H),
    "BracketWidth": (_L + SIDE_LANE + 1.0, 0.0, _H),
}
# The end view (*Right): the thickness beside its span, off the -Y side.
END_KEEP: dict[str, tuple[float, float, float]] = {
    "BracketThick": (_L, -_HW - SIDE_LANE, _H / 2.0),
}

# One native callout per tap over the plan, its count dropped (c4-r3: a 2X
# callout's leader lands on one hole only, leaving the other's thread to a
# guess; with the bar and KP08 taps interleaved a 4X would leave it worse).
# Each leader runs from its shelf's near end to its hole's centre: the 7.5,
# 14 and 24 callouts stand up-left of their holes, the 46, 56 and 62.5 ones
# up-right, each side rising a tier toward the bracket's middle so no leader
# crosses another, a callout or a line (every station hangs under the plan;
# ruling A′ added the 46 and 62.5 bar taps). The tiers clear the +Y side by
# 1 and stand a block plus the audit's row pitch apart (c4-r8). Each tuple:
# the tap kind, its X, the text block's centre (model X, Y) and the side (-1
# left, +1 right) whose upper rim the edge pick takes.
TAP_DRILLS = {"bar": BAR_TAP_DRILL, "kp08": KP08_TAP_DRILL}
# Each callout's two rows, about this wide (glyphs): "Ø.136 THRU ALL" /
# "8-32 UNC THRU ALL" and "Ø.107 THRU ALL" / "6-32 UNC THRU ALL".
CALLOUT_GLYPHS = {"bar": 17, "kp08": 17}
_TIER_PITCH = 2.0 * text_half_high(2) + STACK_PITCH + 0.1  # 7.46
TAP_TIERS = tuple(
    _HW + 5.0 + text_half_high(2) + 0.2 + k * _TIER_PITCH for k in range(3)
)


def _tap_callout(
    kind: str, x: float, tier: int, side: int, run: float
) -> tuple[str, float, tuple[float, float], int]:
    """A callout ``run`` past its hole on ``side``, its shelf's near end there."""
    half = CALLOUT_GLYPHS[kind] * GLYPH / 2.0
    return kind, x, (x + side * (run + half), TAP_TIERS[tier]), side


TAP_CALLOUTS: tuple[tuple[str, float, tuple[float, float], int], ...] = (
    _tap_callout("bar", BAR_TAP_X[0], 0, -1, 2.5),
    _tap_callout("kp08", KP08_TAP_X[0], 1, -1, 3.0),
    _tap_callout("bar", BAR_TAP_X[1], 2, -1, 4.0),
    _tap_callout("bar", BAR_TAP_X[2], 2, 1, 4.0),
    _tap_callout("kp08", KP08_TAP_X[1], 1, 1, 2.0),
    _tap_callout("bar", BAR_TAP_X[3], 0, 1, 1.0),
)


def tap_edge_model(kind: str, x: float, side: int) -> tuple[float, float, float]:
    """A point on the tap's upper rim, on the side its leader comes from."""
    radius = TAP_DRILLS[kind] / 2.0
    return (x + side * 0.6 * radius, 0.8 * radius, _H)


part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        ("_drawing_hole_callout", "add_native_hole_callout"),
    )
)

_INTO_BRACKET = ([0.0, 0.0, -1.0], ("__frame__",))
_PLACES = part_spec.HOLE_PLACES
_UNIT = part_spec.UNIT


def _limits(model: float, places: int) -> list[float]:
    """A general-band dimension's acceptance limits on the inch sheet: the
    title block's band about the value printed at ``places``."""
    return limits(model, places, unit=_UNIT)


def _stock_limits(model: float, band: float) -> list[float]:
    """An as-bought size's supplier band about its nominal."""
    return [round(model - band, 12), round(model + band, 12)]


def _printed(model: float, places: int) -> float:
    """The millimetres of ``model`` printed at ``places`` inch decimals."""
    return round(round(model / 25.4, places) * 25.4, 9)


_FROM_LOW_SIDE = (
    "bracket_low_side",
    (("draw_ch_rocker_arm_tl_oblique_end_bracket", "build"),),
)

# The bottom face, on the base bar's top.
requirement(
    "bar_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("thickness", "length", "width"),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "thickness": (
            _stock_limits(part_spec.BRACKET_THICK, part_spec.THICK_STOCK_BAND),
            ("BRACKET_THICK", "THICK_STOCK_BAND"),
        ),
        "thickness_nominal": (part_spec.BRACKET_THICK, ("BRACKET_THICK",)),
        "length": (
            _limits(part_spec.BRACKET_LENGTH, part_spec.LENGTH_PLACES),
            ("BRACKET_LENGTH", "LENGTH_PLACES"),
        ),
        "length_nominal": (part_spec.BRACKET_LENGTH, ("BRACKET_LENGTH",)),
        "width": (
            _stock_limits(part_spec.BRACKET_WIDTH, part_spec.WIDTH_STOCK_BAND),
            ("BRACKET_WIDTH", "WIDTH_STOCK_BAND"),
        ),
        "width_nominal": (part_spec.BRACKET_WIDTH, ("BRACKET_WIDTH",)),
    },
    precision={
        "thickness": part_spec.STOCK_PLACES,
        "length": part_spec.LENGTH_PLACES,
        "width": part_spec.STOCK_PLACES,
    },
)

# The -Y side face: the datum the row's station measures from.
requirement(
    "bracket_low_side",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), part_spec.HALF_WIDTH),),
    requirements=(),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "y", "value": -part_spec.HALF_WIDTH},
            ("HALF_WIDTH",),
        ),
    },
)


def _row_fields() -> dict[str, tuple[Any, tuple[Any, ...]]]:
    return {
        "height": (
            _limits(part_spec.HOLE_ROW_Y, _PLACES),
            ("HOLE_ROW_Y", "HOLE_PLACES"),
        ),
        "height_nominal": (part_spec.HOLE_ROW_Y, ("HOLE_ROW_Y",)),
        "height_from": _FROM_LOW_SIDE,
    }


for _index, _x in enumerate(part_spec.BAR_TAP_X, start=1):
    _drill = _printed(part_spec.BAR_TAP_DRILL, TAP_CALLOUT_PLACES)
    requirement(
        f"bar_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.BAR_TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru", "note"),
        fields={
            "at": ([_x, 0.0, part_spec.BRACKET_THICK], ("BAR_TAP_X", "BRACKET_THICK")),
            "axis": _INTO_BRACKET,
            "thread": (
                f"{part_spec.BAR_SCREW} UNC-{part_spec.BAR_TAP_SPEC.thread_class}",
                ("BAR_TAP_SPEC", "BAR_SCREW"),
            ),
            "tap_drill_mm": (part_spec.BAR_TAP_DRILL, ("BAR_TAP_SPEC",)),
            # The native callout prints the tap drill to three places (.136).
            "dia": (
                limits(_drill, TAP_CALLOUT_PLACES, part_spec.DRILLED_BAND),
                ("BAR_TAP_DRILL", "DRILLED_BAND"),
            ),
            "nominal_dia": (_drill, ("BAR_TAP_DRILL",)),
            "thru": (True, ("BAR_TAP_SPEC",)),
            # A DRO absolute from the inner end: base bar 1's bracket holes.
            "station": (
                _limits(_x, _PLACES),
                (
                    "BAR_TAP_X",
                    "HOLE_PLACES",
                    ("ch_rocker_arm_tl_vn_oblique_leadscrew_spec", "BRACKET_BAR_HOLES_X"),
                ),
            ),
            "station_nominal": (_x, ("BAR_TAP_X",)),
            **_row_fields(),
            "note": (
                BAR_MATE_CALLOUT,
                ("BAR_MATE_CALLOUT", "BAR_PATTERN_ALLOWANCE", "POSITION_RADIUS"),
            ),
        },
        precision={"dia": TAP_CALLOUT_PLACES, "station": _PLACES, "height": _PLACES},
    )

_KP08_PLACES = part_spec.KP08_TAP_PLACES
_KP08_BAND = (part_spec.KP08_TAP_BAND, -part_spec.KP08_TAP_BAND)
for _index, _x in enumerate(part_spec.KP08_TAP_X, start=1):
    _drill = _printed(part_spec.KP08_TAP_DRILL, TAP_CALLOUT_PLACES)
    requirement(
        f"kp08_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.KP08_TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru", "note"),
        fields={
            "at": ([_x, 0.0, part_spec.BRACKET_THICK], ("KP08_TAP_X", "BRACKET_THICK")),
            "axis": _INTO_BRACKET,
            "thread": (
                f"{part_spec.KP08_THREAD} UNC-{part_spec.KP08_TAP_SPEC.thread_class}",
                ("KP08_TAP_SPEC", "KP08_THREAD"),
            ),
            "tap_drill_mm": (part_spec.KP08_TAP_DRILL, ("KP08_TAP_SPEC",)),
            "dia": (
                limits(_drill, TAP_CALLOUT_PLACES, part_spec.DRILLED_BAND),
                ("KP08_TAP_DRILL", "DRILLED_BAND"),
            ),
            "nominal_dia": (_drill, ("KP08_TAP_DRILL",)),
            "thru": (True, ("KP08_TAP_SPEC",)),
            # A DRO absolute from the inner end: the KP08's 42 bolt spacing,
            # exact millimetres with its own band (owner ruling 4).
            "station": (
                limits(_x, _KP08_PLACES, _KP08_BAND),
                (
                    "KP08_TAP_X",
                    "KP08_TAP_PLACES",
                    "KP08_TAP_BAND",
                    ("ch_rocker_arm_tl_vn_oblique_leadscrew_spec", "BRACKET_KP08_HOLES_X"),
                    ("ch_rocker_arm_tl_vn_oblique_leadscrew_spec", "KP08_BOLT_SPACING"),
                ),
            ),
            "station_nominal": (_x, ("KP08_TAP_X",)),
            **_row_fields(),
            "note": (
                KP08_MATE_CALLOUT,
                ("KP08_MATE_CALLOUT", "KP08_PATTERN_ALLOWANCE", "POSITION_RADIUS"),
            ),
        },
        precision={
            "dia": TAP_CALLOUT_PLACES,
            "station": _KP08_PLACES,
            "height": _PLACES,
        },
    )


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


def _omit_tap_thread_class(display: Any, *, label: str) -> None:
    """The title block's THREADS row owns the UNC class (rule 2): the #8 rows
    read ``8-32 UNC THRU ALL`` and the KP08 rows ``6-32 UNC THRU ALL``, not
    ``... - 2B ...``."""
    omit_title_block_thread_class(display, label=label)
    native = _early_bound(display, "IDisplayDimension")
    resolved = [str(native.GetText(part) or "") for part in (1, 2, 3, 4)]
    classes = {BAR_TAP_SPEC.thread_class, KP08_TAP_SPEC.thread_class}
    if any(cls in text for text in resolved for cls in classes):
        raise RuntimeError(f"{label}: callout still prints its class: {resolved!r}")


_COUNT = re.compile(r"<NUM_INST>X\s*")
_PRINTED_COUNT = re.compile(r"^\s*\d+X\s", re.MULTILINE)


def single_hole_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Drop the instance count: this callout's leader names one hole."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected hole-callout parts: {definitions!r}")
    counts = [part for part, text in definitions.items() for _ in _COUNT.finditer(text)]
    if len(counts) != 1:
        raise RuntimeError(f"hole callout lacks one instance count: {definitions!r}")
    (part,) = counts
    return {**definitions, part: _COUNT.sub("", definitions[part], count=1)}


@_telemetry.traced("drawing.end_bracket.single_hole_callout")
def _call_out_one_hole(display: Any, *, label: str) -> None:
    """Write the count-free definition; prove no row prints a count."""
    native = _early_bound(display, "IDisplayDimension")

    def read(parts: tuple[int, ...]) -> dict[int, str]:
        return {
            part: str(native.GetText(part) or "").replace("\r", "") for part in parts
        }

    definitions = read((5, 6, 7, 8))
    updated = single_hole_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = read((5, 6, 7, 8))
    resolved = read((1, 2, 3, 4))
    if persisted != updated or any(
        _PRINTED_COUNT.search(text) for text in resolved.values()
    ):
        raise RuntimeError(
            f"{label}: callout still prints a count: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
    _telemetry.info(f"{label}: {resolved!r}")


def _activate_view(adapter: Any, view: Any, *, label: str) -> None:
    """Make ``view`` the active view (a note lands in the active view)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} view {name!r}")


_STOCK_SIZES = {"BracketWidth": BRACKET_WIDTH, "BracketThick": BRACKET_THICK}


def _stock_references(adapter: Any, annotations: list[Any]) -> None:
    """The as-bought width and thickness print as REF stock fractions over
    STOCK (#290, draw_mg_magnifying_lever's rod stock)."""
    by_name: dict[str, list[Any]] = {}
    for item in annotations:
        by_name.setdefault(dimension_name(adapter, item), []).append(item)
    for name, size in _STOCK_SIZES.items():
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        display = _early_bound(
            _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        supplier_reference_dimension(
            adapter,
            display,
            label=f"end bracket stock {name}",
            units="in",
            precision=DRAWING_PRECISION_BY_NAME[name],
            expected_mm=size,
            fraction_denominator=STOCK_FRACTION_DENOMINATORS[name],
            callout=STOCK_CALLOUT,
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open end bracket source", await adapter.open_model(str(SOURCE)))
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel End Bracket Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel end bracket; aluminum flat bar; MHA-CH-06-TL-28",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (plan, end, iso):
        set_hidden_lines_removed(adapter, view)

    on_plan = _view_mapper(adapter, plan)
    on_end = _view_mapper(adapter, end)
    # The plan shows the hidden HoleRowReference sketch, whose .250 it prints.
    annotations = [
        *curate_view_dimensions(
            adapter,
            plan,
            keep={name: on_plan(xyz) for name, xyz in PLAN_KEEP.items()},
            view_label="end bracket plan",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            end,
            keep={name: on_end(xyz) for name, xyz in END_KEEP.items()},
            view_label="end bracket end",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places are authored on the part; the sheet only proves the import kept
    # them, then writes the mate callouts and the stock references.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    print_imported_metric_dimensions(
        adapter,
        annotations,
        {
            name: places
            for (_feature, name), (places, _band) in METRIC_DIMENSIONS.items()
        },
    )
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    _stock_references(adapter, annotations)

    if not auto_center_marks(adapter, plan, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the plan")
    for kind, x, (text_x, text_y), side in TAP_CALLOUTS:
        label = f"{'base-bar' if kind == 'bar' else 'KP08'} screw tap at {x / 25.4:.3f}"
        callout = add_native_hole_callout(
            adapter,
            plan,
            edge_xy=on_plan(tap_edge_model(kind, x, side)),
            callout_xy=on_plan((text_x, text_y, _H)),
            label=label,
        )
        _call_out_one_hole(callout, label=label)
        _omit_tap_thread_class(callout, label=label)
        set_callout_lengths_to_three_places(callout, label=label)

    # The property-linked blocks land in the active view: the plan.
    _activate_view(adapter, plan, label="plan")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel End Bracket Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "... Tapped Hole" note to the plan for each
        # tap feature in it (draw_fr_harmonic_base counts features x views),
        # not per callout; each callout already states it. Two tap features
        # (six callouts), two notes.
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
