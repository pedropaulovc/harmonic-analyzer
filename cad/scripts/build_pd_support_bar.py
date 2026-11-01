r"""Reproduction script: platen support bar (book ch. 21/22, pp. 50-55, 62-63).

THE bar the platen rides on (book p.62 caption, singular): one rectangular
steel bar clamped across the two front columns by the two-piece column
clamps (build_sh_column_clamp_front.py and build_sh_column_clamp_back.py), carrying the hanging platen
(guides + locks on the platen back) and, on its own back face, the ch. 23
transgear hanger (pivot screw MHA-PD-VN-57) and the latch hook (MHA-PD-14).
Cross-section 1.010 tall x 9.5 deep (it fills the platen's guide channel to a
running clearance over the bottom rail; ``pd_support_bar_spec.BAR_HEIGHT``
carries the photo chain); 17.8 in long so the ends run ~29 past each column
(ch30 p002). The clamp line and hanger row keep their machine heights under the
top edge, so they stand below the bar's centre line.
The part builds in inch document units and its sheet prints decimal inch
(#290); the section and stations keep their millimetre interfaces.

Holes (all along local Z, the machine front-back axis):
* 4x clamp screws flanking each column (x +-197 -+ 17.5): round counterbores
  on the east column (END A, -X), which locate the bar, and counterbored
  slots along the bar on the west one, which take up the column pitch (owner
  ruling 2026-10-15, option A). The screw heads sit sub-flush in the BAR's
  front face so the refitted platen can slide across the east clamp, and
  thread into the back clamp arc.
* the hanger's #8-32 blind pivot tap and the latch hook's two #4-40 base-screw
  through taps, all entering the back face (``pd_support_bar_spec``).

The hanger holes make the bar x-ASYMMETRIC, so it is authored MACHINE-
handed and placed on its exact machine transform.

Layout: bar axis along X, origin at the bar centre; height along Y,
depth along Z (front face local z -4.5, back face +4.5; named plane
``BackFace``). Dimensions: memory/paper-drive-rework.md E1/E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_support_bar.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_pmi import author_part_pmi
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _sketch_rectangle import define_centered_rectangle
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _holes import wizard_holes
from _visibility import blank_reference_geometry
from _drawing_prefix import set_dimension_prefix
import _telemetry
from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations
from sh_column_clamp_fit import BORE_DIAMETRAL_CLEARANCE
from sh_column_clamp_fit import EAR_HEIGHT_BAND as BACK_ARC_TAP_HEIGHT_BAND
from sh_column_clamp_fit import EAR_STATION_BAND as BACK_ARC_TAP_STATION_BAND
from sh_vn_clamp_screw_spec import HEAD_DIA as CLAMP_HEAD_DIA
from sh_vn_clamp_screw_spec import HEAD_H as CLAMP_HEAD_H
from sh_vn_clamp_screw_spec import SHANK_DIA as CLAMP_SCREW_MAJOR
from _column_clamp_interface import BAR_DEPTH
from pd_support_bar_spec import (
    BACK_FACE_Z,
    BAR_HEIGHT,
    BAR_BAND_PLACES,
    BRACKET_TAP_CSK_DIA,
    BRACKET_TAP_SPEC,
    BRACKET_TAP_X,
    CLAMP_TAP_Y,
    HANGER_TAP_Y,
    HOLE_POSITION_TOL,
    PIVOT_TAP_CSK_DIA,
    PIVOT_TAP_DRILL_DIA,
    PIVOT_TAP_X,
    UNIT,
)
from pd_support_bar_drawing_spec import (
    CLAMP_HOLE_CALLOUT_PLACES,
    CLAMP_POSITION_PLACES,
    CLAMP_SLOT_CBORE_WIDTH_LIMITS,
    CLAMP_SLOT_CBORE_WIDTH_PLACES,
    CLAMP_SLOT_PLACES,
    CLAMP_SLOT_WIDTH_PLACES,
    CLAMP_STATION_NAMES,
    DIMENSION_PREFIXES,
    DRAWING_DIMENSIONS,
    HANGER_STATION_NAMES,
    ISOMETRIC_VIEW_NOTE,
    SHEET_PRECISION,
    SURFACE_FINISHES,
    TOL_MAX,
)

PART_NAME = "pd-support-bar"
MATERIAL = "Plain Carbon Steel"

# 17.8: ends at x +-226.06, ~29 past each Ø25.4 column (ch30 p002). An
# unmated overall length, so it prints .X.
BAR_LENGTH = 452.12  # 17.8

# The column line (frame) and the clamp-screw spacing (the MHA-SH-02 back-arc
# taps) are the frame's and the clamps', so they keep their millimetres and
# the stations print rounded.
COLUMN_X = 197.0  # frame column line (frame assembly)
CLAMP_SCREW_DX = 17.5  # clamp screws flank each column
# The stock 90280A201 #8-32 clamp screws pass through #8 clearance holes.
# Their .156 heads sit below the bar front: the right-shifted platen
# travels across the east clamp line, so proud heads would block its slide.
# The depth prints at .XX
# (pd_support_bar_drawing_spec.CLAMP_CBORE_DEPTH_PLACES) and the title block's
# ±.01 still leaves the head about .024 under the face at the shallowest: a
# clearance needs only a minimum, so the nominal moves, not the band (Main
# ruling on the r4 machinist over-specification).
CLAMP_CBORE_DIA = 8.509  # .335
CLAMP_CBORE_DEPTH = 4.826  # .19
CLAMP_HEAD_RECESS = CLAMP_CBORE_DEPTH - CLAMP_HEAD_H  # .034
CLAMP_THROUGH_HOLE_SPEC = HoleSpec("clearance", "#8")
CLAMP_HOLE_DIA = blind_cut_dia_mm(CLAMP_THROUGH_HOLE_SPEC)
CLAMP_HOLE_SPEC = HoleSpec(
    "counterbore_fillister",
    CLAMP_THROUGH_HOLE_SPEC.size,
    overrides_mm={
        "HoleDiameter": CLAMP_HOLE_DIA,
        "CounterBoreDiameter": CLAMP_CBORE_DIA,
        "CounterBoreDepth": CLAMP_CBORE_DEPTH,
    },
)

CLAMP_HOLE_X = tuple(
    s * (COLUMN_X + d) for s in (-1.0, 1.0) for d in (-CLAMP_SCREW_DX, CLAMP_SCREW_DX)
)

# --- Print rows (pd_support_bar_drawing_spec) ---------------------------------
# The hanger holes on the back face: stations from the left end, the row's
# height from the TOP face, which carries the platen's top rail.
LEFT_END_X = -BAR_LENGTH / 2.0
HANGER_ROW_HEIGHT = BAR_HEIGHT / 2.0 - HANGER_TAP_Y
HANGER_STATIONS = tuple(x - LEFT_END_X for x in (PIVOT_TAP_X, *BRACKET_TAP_X))
# The clamp holes on the front face: stations from the same (left, x = -226)
# end as the hanger row, so one end is the datum on both faces, and the
# height from the top face, its rise on the +X end.
CLAMP_ROW_START_X = LEFT_END_X
CLAMP_ROW_HEIGHT = BAR_HEIGHT / 2.0 - CLAMP_TAP_Y
CLAMP_ROW_X = tuple(sorted(CLAMP_HOLE_X))
CLAMP_STATIONS = tuple(x - CLAMP_ROW_START_X for x in CLAMP_ROW_X)

# The clamp holes' position band: a fixed-fastener stack, as the latch hook's
# on this bar's own taps. Each #8-32 screw stands in its MHA-SH-02 back-arc
# tap, which the clamp pair holds to ±BACK_ARC_TAP_STATION_BAND along the bar
# and ±BACK_ARC_TAP_HEIGHT_BAND in height (sh_column_clamp_fit), and passes
# the bar's #8 clearance hole, whose least size (DRILLED HOLES minus 0) clears
# the basic major by CLAMP_HOLE_FLOAT. A coordinate ±band is a diametral zone of
# 2·√2·band (the rounding to the printed places included), and the bar's
# zone plus the tap's must stay inside the float. The row height and
# stations, at .XXX, take the widest band that does: ±.006 (the .XX row's
# ±.01 would need more than the whole float).
CLAMP_HOLE_FLOAT = CLAMP_HOLE_DIA - CLAMP_SCREW_MAJOR
BACK_ARC_TAP_ZONE = 2.0 * math.hypot(
    BACK_ARC_TAP_STATION_BAND, BACK_ARC_TAP_HEIGHT_BAND
)


def clamp_position_zone(band: float) -> float:
    """Diametral zone a ±``band`` print of the clamp row gives a hole centre:
    twice its farthest printed corner off the model, over every station."""

    def reach(value: float) -> float:
        deviations = printed_deviations(
            value, CLAMP_POSITION_PLACES, (-band, band), unit=UNIT
        )
        return max(abs(d) for d in deviations)

    return 2.0 * max(
        math.hypot(reach(station), reach(CLAMP_ROW_HEIGHT))
        for station in CLAMP_STATIONS
    )


# One step of the printed places, in millimetres.
_CLAMP_POSITION_STEP = 25.4 * 10.0**-CLAMP_POSITION_PLACES
CLAMP_POSITION_BAND = _CLAMP_POSITION_STEP * max(
    (
        k
        for k in range(1, math.ceil(CLAMP_HOLE_FLOAT / _CLAMP_POSITION_STEP))
        if clamp_position_zone(k * _CLAMP_POSITION_STEP) + BACK_ARC_TAP_ZONE
        <= CLAMP_HOLE_FLOAT + 1e-9
    ),
    default=0,
)
if CLAMP_POSITION_BAND <= 0.0:
    raise AssertionError(
        "MHA-SH-VN-53 screws in the MHA-SH-02 taps through the support bar: no "
        f".XXX clamp-hole position band fits the {CLAMP_HOLE_FLOAT:.4f} float"
    )

# --- West clamp slots: owner ruling 2026-10-15, option A (PR #1471 r3) -------
# The bar spans the two columns, whose pitch is not the bar's: the top frame
# prints its socket pitch at .XX (fr_top_frame_spec "socket horizontal
# pitch") and the harmonic base's hole table each socket's X at .XX
# (draw_fr_harmonic_base), so at the bar the pitch may stand one .XX band
# off, or two. The round holes' along-bar float takes up neither, so the west
# pair (+X) are slots along the bar and the east pair (END A, -X) stay round
# and locate it. Rule 19 makes slots and fit-up a last resort; the owner chose
# them after seeing that no loose-band geometry closes the span: a looser
# round Ø5.41 holds the ±0.51 top-frame pitch by only 0.141 and fails the
# ±1.02 base-socket pitch, and transfer-drilling the bar off its columns
# makes each bar fit only its own frame. The fit-up this relies on: all four
# screws enter loose, the bar settles on the east pair at its height, then all
# four tighten.
COLUMN_PITCH_PLACES = 2
COLUMN_PITCH_DEVIATIONS = {
    "top frame socket pitch": printed_band_mm(COLUMN_PITCH_PLACES),
    "base socket coordinates": 2.0 * printed_band_mm(COLUMN_PITCH_PLACES),
}
CLAMP_ROUND_X = tuple(x for x in CLAMP_HOLE_X if x < 0.0)
CLAMP_SLOT_X = tuple(x for x in CLAMP_HOLE_X if x > 0.0)
# Each slot is the round hole's width run CLAMP_SLOT_TRAVEL each way along the
# bar, inside the round counterbore's width run as far and as deep: the east
# pair's screw, head seat and floor.
CLAMP_SLOT_RUN = 2.9972  # .118, straight sides, end centre to end centre
CLAMP_SLOT_TRAVEL = CLAMP_SLOT_RUN / 2.0
CLAMP_SLOT_WIDTH = CLAMP_HOLE_DIA
CLAMP_SLOT_CBORE_WIDTH = CLAMP_CBORE_DIA
CLAMP_SLOT_CBORE_RUN = CLAMP_SLOT_RUN
# The round holes print under the title block's DRILLED HOLES row; the milled
# slot carries the same limits on its own width.
DRILLED_HOLE_LIMITS = (0.0, drilled_oversize_mm(unit=UNIT))
CLAMP_SLOT_WIDTH_LIMITS = DRILLED_HOLE_LIMITS
# Each column clamp may stand off its column by half the bore's widest
# diametral clearance (sh_column_clamp_fit), the two clamps independently.
COLUMN_CLAMP_SHIFT = BORE_DIAMETRAL_CLEARANCE[1] / 2.0


def _printed_limits(
    value: float, places: int, limits: tuple[float, float] | None = None
) -> tuple[float, float]:
    lower, upper = printed_deviations(value, places, limits, unit=UNIT)
    return value + lower, value + upper


def clamp_shank_slack_along() -> float:
    """How far a clamp shank may stand along the bar off a round hole's
    centre (or a slot end's) at the worst height: the least hole's radial
    float less the height misalignment (the bar row's band plus the tap's)."""
    radial = CLAMP_HOLE_FLOAT / 2.0
    height = CLAMP_POSITION_BAND + BACK_ARC_TAP_HEIGHT_BAND
    return math.sqrt(radial**2 - height**2)


def clamp_east_pair_margin() -> float:
    """Along-bar slack left between the two round (east) holes: both screws
    stand in one clamp, so only the two bar stations' bands and the two taps'
    station bands open their spacing."""
    demand = 2.0 * (CLAMP_POSITION_BAND + BACK_ARC_TAP_STATION_BAND)
    return 2.0 * clamp_shank_slack_along() - demand


def clamp_slot_closure_margin(pitch_deviation: float) -> float:
    """Along-bar slack left between an east (round) and a west (slotted)
    screw when the columns stand ``pitch_deviation`` off the bar's pitch: the
    shortest slot's travel each way plus both shanks' slack, less the pitch
    error and every band between the two screws (both bar stations, both
    clamps' tap stations, both clamps' shift on their columns). The two west
    screws share the slots, so they close whenever each east-west pair does."""
    shortest_run, _ = _printed_limits(CLAMP_SLOT_RUN, CLAMP_SLOT_PLACES)
    capacity = shortest_run / 2.0 + 2.0 * clamp_shank_slack_along()
    demand = pitch_deviation + 2.0 * (
        CLAMP_POSITION_BAND + BACK_ARC_TAP_STATION_BAND + COLUMN_CLAMP_SHIFT
    )
    return capacity - demand


def clamp_head_bearing(widest_hole: float) -> float:
    """Least overlap of a clamp-screw head past the edge of a hole (or slot
    side) ``widest_hole`` across onto its counterbore floor: the shank pushed
    its full float across the hole, the head's far edge left nearest the
    hole's edge."""
    float_across = (widest_hole - CLAMP_SCREW_MAJOR) / 2.0
    return CLAMP_HEAD_DIA / 2.0 - widest_hole / 2.0 - float_across


def clamp_slot_head_clearance() -> float:
    """Least gap from a clamp-screw head to its slot counterbore's wall: the
    head centred anywhere the shank reaches in the widest, longest slot,
    against the narrowest, shortest counterbore. The slot and its counterbore
    are milled about the same centre; this gap is what their co-location
    error may spend."""
    _, widest = _printed_limits(
        CLAMP_SLOT_WIDTH, CLAMP_SLOT_WIDTH_PLACES, CLAMP_SLOT_WIDTH_LIMITS
    )
    _, longest_run = _printed_limits(CLAMP_SLOT_RUN, CLAMP_SLOT_PLACES)
    shortest_cbore_run, _ = _printed_limits(CLAMP_SLOT_CBORE_RUN, CLAMP_SLOT_PLACES)
    narrowest_cbore, _ = _printed_limits(
        CLAMP_SLOT_CBORE_WIDTH,
        CLAMP_SLOT_CBORE_WIDTH_PLACES,
        CLAMP_SLOT_CBORE_WIDTH_LIMITS,
    )
    float_across = (widest - CLAMP_SCREW_MAJOR) / 2.0
    overrun = max(0.0, (longest_run - shortest_cbore_run) / 2.0)
    return narrowest_cbore / 2.0 - (CLAMP_HEAD_DIA / 2.0 + float_across + overrun)


# The head's least bearing beside a slot is held to the round counterbores'
# own worst case (the same screw over the same DRILLED HOLES #8 clearance).
CLAMP_HEAD_BEARING_MIN = clamp_head_bearing(
    _printed_limits(CLAMP_HOLE_DIA, CLAMP_HOLE_CALLOUT_PLACES, DRILLED_HOLE_LIMITS)[1]
)
if clamp_east_pair_margin() < 0.0:
    raise AssertionError(
        "MHA-SH-VN-53 screws in one MHA-SH-02 clamp: the round east holes' "
        f"spacing over-runs their float by {-clamp_east_pair_margin():.3f}"
    )
if clamp_slot_closure_margin(max(COLUMN_PITCH_DEVIATIONS.values())) < 0.0:
    raise AssertionError(
        "MHA-SH-VN-53 screws in the two MHA-SH-02 clamps: the west slots do not "
        "take up the worst column pitch "
        f"({max(COLUMN_PITCH_DEVIATIONS.values()):.2f})"
    )
if (
    clamp_head_bearing(
        _printed_limits(
            CLAMP_SLOT_WIDTH, CLAMP_SLOT_WIDTH_PLACES, CLAMP_SLOT_WIDTH_LIMITS
        )[1]
    )
    < CLAMP_HEAD_BEARING_MIN
):
    raise AssertionError("MHA-SH-VN-53 heads bear less beside a slot than a round hole")
if clamp_slot_head_clearance() < 0.0:
    raise AssertionError(
        "MHA-SH-VN-53 heads reach past the slot counterbores' walls by "
        f"{-clamp_slot_head_clearance():.3f}"
    )

REFERENCE_SKETCHES = (
    "HangerRowReference",
    "ClampRowReference",
    "CountersinkReference",
)

# The rows' equations. Every row hole stands at a fixed offset from the bar
# centre (the Hole Wizard points, the pivot circle's undriven PivotTapX/Y),
# while the bar's ends and top face follow the BarLength/BarHeight globals.
# A station from the left end is therefore half the length plus the hole's
# x, and a row's height from the top face is half the height less the hole's
# y. With those equations, a Tools > Equations edit of either global keeps
# every reference row on its real holes.
BAR_HALF_LENGTH_EQUATION = '"BarLength" / 2'
BAR_HALF_HEIGHT_EQUATION = '"BarHeight" / 2'


@dataclass(frozen=True)
class ReferenceRow:
    """One hole row's hidden reference sketch: its feature name, the prefix of
    its anchor dimensions, its height dimension's name, the holes' model y and
    each hole's (station dimension name, model x)."""

    feature: str
    prefix: str
    height_name: str
    row_y: float
    holes: tuple[tuple[str, float], ...]


HANGER_ROW = ReferenceRow(
    "HangerRowReference",
    "Hanger",
    "HangerRowHeight",
    HANGER_TAP_Y,
    tuple(zip(HANGER_STATION_NAMES, (PIVOT_TAP_X, *BRACKET_TAP_X), strict=True)),
)
CLAMP_ROW = ReferenceRow(
    "ClampRowReference",
    "Clamp",
    "ClampRowHeight",
    CLAMP_TAP_Y,
    tuple(zip(CLAMP_STATION_NAMES, CLAMP_ROW_X, strict=True)),
)


def _plus_mm(equation: str, offset_mm: float) -> str:
    """``equation`` plus a fixed millimetre offset. The suffix is load-bearing:
    the part is an INCH document, whose equations read bare numbers in inches."""
    if offset_mm == 0.0:
        return equation
    sign = "+" if offset_mm > 0.0 else "-"
    return f"{equation} {sign} {abs(offset_mm):.10g}mm"


def row_equations(row: ReferenceRow) -> dict[str, str]:
    """The row's height and stations by dimension name, each as the equation
    that keeps it on the row's holes when BarLength or BarHeight changes."""
    return {
        row.height_name: _plus_mm(BAR_HALF_HEIGHT_EQUATION, -row.row_y),
        **{name: _plus_mm(BAR_HALF_LENGTH_EQUATION, x) for name, x in row.holes},
    }


def _as_construction(adapter, entity_id: str, label: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{label} did not take the construction flag")


# The bar's front face as a plane, for the west clamp slots' sketches.
FRONT_FACE_PLANE = "FrontFace"


def _sketch_uvw(
    adapter, model_mm: tuple[float, float, float]
) -> tuple[float, float, float]:
    """``model_mm`` in the active sketch's own ``(u, v, w)`` mm, ``w`` off its
    plane (``ModelToSketchTransform``; build_dt_cone_pivot_post_tl_bond_cradle's
    reader)."""
    from solidworks_mcp.adapters.com_variant import double_array

    sketch = _early_bound(adapter.currentModel.SketchManager.ActiveSketch, "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    point = _early_bound(
        utility.CreatePoint(double_array([v / 1000.0 for v in model_mm])), "IMathPoint"
    )
    moved = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    u, v, w = (float(c) * 1000.0 for c in moved.ArrayData)
    return u, v, w


def stadium_area(width: float, run: float) -> float:
    """A slot's area: ``width`` across, its straight sides ``run`` long."""
    return width * run + math.pi * (width / 2.0) ** 2


def _stadium_points(
    centre: tuple[float, float], *, along_u: bool, half_run: float, half_width: float
) -> tuple[tuple[float, float], ...]:
    """One slot's stadium in sketch ``(u, v)``, counter-clockwise, as
    build_fr_top_frame.slot_stadium_points draws it (copied: importing that
    build would key this part on the top frame's recipe). Returns ``(p1, p2,
    p3, p4, centre_b, centre_a)``: side a runs p1 -> p2, end b arcs about
    centre_b from p2 to p3, side b runs p3 -> p4 and end a arcs about
    centre_a from p4 back to p1. The slot runs along sketch u when
    ``along_u``, else along v."""
    u0, v0 = centre

    def at(du: float, dv: float) -> tuple[float, float]:
        return (u0 + du, v0 + dv) if along_u else (u0 - dv, v0 + du)

    return (
        at(-half_run, -half_width),
        at(half_run, -half_width),
        at(half_run, half_width),
        at(-half_run, half_width),
        at(half_run, 0.0),
        at(-half_run, 0.0),
    )


async def _author_clamp_slot_profile(
    adapter, feature: str, base: str, width: float, run: float
) -> tuple[list[tuple[str, str]], bool]:
    """One closed stadium per west clamp slot on the front face
    (``FRONT_FACE_PLANE``): ``width`` across, its straight sides ``run`` long
    along the bar, centred on the slot's station on the clamp line. The outer
    slot's (the detail's) width and run are ``{base}Width`` and
    ``{base}Travel``; the inner slot's carry the same names numbered 1. An
    offset plane's sketch axes are SOLIDWORKS' choice, so the centres map
    through ``_sketch_uvw``. Returns the sketch's drive jobs and whether its
    normal points out of the front face (-Z): a cut runs opposite the sketch
    normal unless reversed (build_fr_top_frame's slip holes and slots)."""
    front_z = -BAR_DEPTH / 2.0
    check(f"create_sketch {feature}", await adapter.create_sketch(FRONT_FACE_PLANE))
    outer = max(CLAMP_SLOT_X)
    u0, v0, w0 = _sketch_uvw(adapter, (outer, CLAMP_TAP_Y, front_z))
    u1, v1, _ = _sketch_uvw(adapter, (outer + 1.0, CLAMP_TAP_Y, front_z))
    du, dv = u1 - u0, v1 - v0
    if abs(abs(du) - 1.0) < 1e-4 and abs(dv) < 1e-4:
        u_is_x = True
    elif abs(abs(dv) - 1.0) < 1e-4 and abs(du) < 1e-4:
        u_is_x = False
    else:
        raise RuntimeError(f"{feature}: sketch axes are not along X/Y ({du:g}, {dv:g})")
    w_out = _sketch_uvw(adapter, (outer, CLAMP_TAP_Y, front_z - 1.0))[2] - w0
    if abs(abs(w_out) - 1.0) > 1e-4:
        raise RuntimeError(f"{feature}: sketch normal is not along Z (w {w_out:g})")
    dims = SketchDims()
    for index, x in enumerate(sorted(CLAMP_SLOT_X, reverse=True)):
        tag = str(index) if index else ""
        where = f"{feature} at x {x:g}"
        u, v, w = _sketch_uvw(adapter, (x, CLAMP_TAP_Y, front_z))
        if abs(w) > 1e-4:
            raise RuntimeError(f"{where} lies {w:g} mm off the sketch plane")
        p1, p2, p3, p4, c_end_b, c_end_a = _stadium_points(
            (u, v), along_u=u_is_x, half_run=run / 2.0, half_width=width / 2.0
        )
        set_sketch_direct_db(adapter, True)
        side_a = check(f"{where} side a", await adapter.add_line(*p1, *p2))
        end_b = check(f"{where} end b", await adapter.add_arc(*c_end_b, *p2, *p3))
        side_b = check(f"{where} side b", await adapter.add_line(*p3, *p4))
        end_a = check(f"{where} end a", await adapter.add_arc(*c_end_a, *p4, *p1))
        set_sketch_direct_db(adapter, False)
        for join, a, b in (
            ("side a - end b", f"{side_a}.end", f"{end_b}.start"),
            ("end b - side b", f"{end_b}.end", f"{side_b}.start"),
            ("side b - end a", f"{side_b}.end", f"{end_a}.start"),
            ("end a - side a", f"{end_a}.end", f"{side_a}.start"),
        ):
            check(
                f"{where} {join}",
                await adapter.add_sketch_constraint(a, b, "coincident"),
            )
        along = "horizontal" if u_is_x else "vertical"
        for side in (side_a, side_b):
            check(
                f"{where} {side} {along}",
                await adapter.add_sketch_constraint(side, None, along),
            )
        # Tangency closes the shape: both ends' radii follow from the sides'
        # spacing, the far side's length from the near side's.
        for a, b in (
            (side_a, end_b),
            (end_b, side_b),
            (side_b, end_a),
            (end_a, side_a),
        ):
            check(
                f"{where} {a} tangent {b}",
                await adapter.add_sketch_constraint(a, b, "tangent"),
            )
        # Emission order: the width across the sides, the near side's
        # straight run, then end a's centre anchors (one dimension per
        # off-axis coordinate, anchor_point_to_origin).
        await dimension_between(
            adapter,
            f"{side_a}.start",
            f"{side_b}.end",
            "vertical_distance" if u_is_x else "horizontal_distance",
            width,
            f"{where} width",
        )
        dims.record(f"{base}Width{tag}")
        await dimension_between(
            adapter,
            f"{side_a}.start",
            f"{side_a}.end",
            "horizontal_distance" if u_is_x else "vertical_distance",
            run,
            f"{where} run",
        )
        dims.record(f"{base}Travel{tag}")
        await anchor_point_to_origin(
            adapter, f"{end_a}.center", *c_end_a, f"{where} end a"
        )
        for axis, coordinate in zip("UV", c_end_a):
            if abs(coordinate) >= 1e-9:
                dims.record(f"{base}End{axis}{tag}")
    await ensure_fully_defined(adapter, f"{feature} sketch")
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    return dims.apply(adapter, feature), w_out > 0.0


async def _author_row(adapter, row: ReferenceRow) -> list[tuple[str, str]]:
    """One hole row as model dimensions on a hidden Front-plane sketch (the
    build_mg_wheel_bar BoreRowReference pattern): a construction chain on the
    row from the left bar end through each hole to a rise at the right end
    that drops from the top face to the row, so the stations read from the
    end and the row's height from the top face. Every dimension is driven
    from the bar globals (``row_equations``). The rise lies on the bar's end
    edge, so it is a plain sketch line, which prints inside that edge's
    heavier stroke; as construction geometry its grey dashes showed along the
    end (machinist review round 2)."""
    feature = row.feature
    rise_x = BAR_LENGTH / 2.0
    row_y = row.row_y
    start_x = LEFT_END_X
    equations = row_equations(row)
    top_y = BAR_HEIGHT / 2.0
    row_xs = (start_x, *(x for _, x in row.holes), rise_x)
    dims = SketchDims()
    check(f"create_sketch {feature}", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    rise = check(
        f"{feature} rise", await adapter.add_line(rise_x, top_y, rise_x, row_y)
    )
    legs = [
        check(f"{feature} leg {index}", await adapter.add_line(x0, row_y, x1, row_y))
        for index, (x0, x1) in enumerate(zip(row_xs, row_xs[1:]))
    ]
    set_sketch_direct_db(adapter, False)
    check(
        f"{feature} rise vertical",
        await adapter.add_sketch_constraint(rise, None, "vertical"),
    )
    for index, leg in enumerate(legs):
        _as_construction(adapter, leg, f"{feature} leg {index}")
        check(
            f"{feature} leg {index} horizontal",
            await adapter.add_sketch_constraint(leg, None, "horizontal"),
        )
    for index, (leg, after) in enumerate(zip(legs, [*legs[1:], None])):
        end = f"{rise}.end" if after is None else f"{after}.start"
        check(
            f"{feature} leg {index} chained",
            await adapter.add_sketch_constraint(f"{leg}.end", end, "coincident"),
        )
    await anchor_point_to_origin(
        adapter, f"{rise}.start", rise_x, top_y, f"{feature} top corner"
    )
    dims.record(f"{row.prefix}RiseX", BAR_HALF_LENGTH_EQUATION)
    dims.record(f"{row.prefix}RiseY", BAR_HALF_HEIGHT_EQUATION)
    await dimension_between(
        adapter,
        f"{rise}.start",
        f"{rise}.end",
        "vertical_distance",
        top_y - row_y,
        f"{feature} height",
    )
    dims.record(row.height_name, equations[row.height_name])
    start = f"{legs[0]}.start"
    await dimension_between(
        adapter, start, "origin", "horizontal_distance", abs(start_x), f"{feature} end"
    )
    dims.record(f"{row.prefix}StartX", BAR_HALF_LENGTH_EQUATION)
    # Each hole ends one leg; the last leg runs on to the rise.
    for leg, (name, x) in zip(legs[:-1], row.holes, strict=True):
        await dimension_between(
            adapter, start, f"{leg}.end", "horizontal_distance", x - start_x, name
        )
        dims.record(name, equations[name])
    await ensure_fully_defined(adapter, f"{feature} sketch")
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    return dims.apply(adapter, feature)


def _single_limit(
    adapter, feature: str, name: str, nominal: float, tol_type: int
) -> None:
    """A dimension printed as a single MIN or MAX limit: SOLIDWORKS prints the
    nominal then the limit word, so the model value is the limit itself."""
    label = f"{name}@{feature}"
    _, dimension = _named_dimension(adapter, feature, name)
    if not math.isclose(float(dimension.SystemValue), nominal / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {float(dimension.SystemValue) * 1000.0:.7f} is not "
            f"the limit {nominal:.7f}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = tol_type
    if not tolerance.SetValues(0.0, 0.0) or int(tolerance.Type) != tol_type:
        raise RuntimeError(f"{label}: cannot retain the single limit {tol_type}")
    _telemetry.success(f"{label}: single limit (swTolType {tol_type})")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations): the section and the length. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 452 = 452 in).
    # (The old ClampHoleDia/BracketHoleDia knobs are gone: the screw holes are
    # now native Hole Wizard features whose diameters come from the ANSI-inch
    # clearance/tap tables, not driven dims.)
    await set_global(adapter, "BarHeight", f"{BAR_HEIGHT}mm")
    await set_global(adapter, "BarDepth", f"{BAR_DEPTH}mm")
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Bar profile: width along X = length, height along Y; depth extruded along Z.
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter, BAR_LENGTH / 2.0, BAR_HEIGHT / 2.0, "bar", dims=bar,
        name_width="Length", drive_width='"BarLength"',
        name_depth="Height", drive_depth='"BarHeight"',
    )
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BAR_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bar")
    name_dimensions(adapter, "Bar", ["Depth"])

    expected = BAR_HEIGHT * BAR_DEPTH * BAR_LENGTH
    await volume_check(adapter, "bar", expected, 0.005 * expected)

    # Clamp-screw holes, through along Z on the clamp line (CLAMP_TAP_Y), drilled
    # from the bar FRONT face (local z = -BAR_DEPTH/2, where the clamp-screw heads
    # sit -- ch30 p002), while the bar is still a plain prism: one native Hole
    # Wizard feature, the east column's 2 clamp-screw #8 COUNTERBORES, which
    # locate the bar (the west pair are slots, below).
    front_z = -BAR_DEPTH / 2.0
    clamp_dia = CLAMP_HOLE_DIA
    wizard_holes(
        adapter, CLAMP_HOLE_SPEC,
        [[x, CLAMP_TAP_Y, front_z] for x in CLAMP_ROUND_X],
        (0.0, 0.0, -1.0), "clamp-screw counterbores (#8)", name="ClampHoles",
    )
    v_holes = len(CLAMP_ROUND_X) * (
        math.pi * (clamp_dia / 2.0) ** 2 * BAR_DEPTH
        + math.pi
        * ((CLAMP_CBORE_DIA / 2.0) ** 2 - (clamp_dia / 2.0) ** 2)
        * CLAMP_CBORE_DEPTH
    )
    expected -= v_holes
    await volume_check(adapter, "bar with clamp holes", expected, 0.02 * v_holes)

    # The west column's clamp screws pass counterbored slots along the bar,
    # which take up the column pitch (owner ruling 2026-10-15, option A; see
    # CLAMP_SLOT_TRAVEL): the round hole's width through, then the round
    # counterbore's width as deep, each run CLAMP_SLOT_RUN along the bar.
    check(
        f"create_plane {FRONT_FACE_PLANE} (Front Plane, {front_z})",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=front_z
            )
        ),
    )
    name_last_feature(adapter, FRONT_FACE_PLANE)
    slot_jobs, _ = await _author_clamp_slot_profile(
        adapter, "ClampSlotProfile", "ClampSlot", CLAMP_SLOT_WIDTH, CLAMP_SLOT_RUN
    )
    drive_jobs += slot_jobs
    # Mid-plane, so either sketch normal cuts: half the total depth each way
    # from the front face, a millimetre past the back face.
    check(
        "cut clamp slots (through)",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * (BAR_DEPTH + 1.0), both_directions=True)
        ),
    )
    name_last_feature(adapter, "ClampSlots")
    slot_area = stadium_area(CLAMP_SLOT_WIDTH, CLAMP_SLOT_RUN)
    v_slots = len(CLAMP_SLOT_X) * slot_area * BAR_DEPTH
    expected -= v_slots
    # A cut the wrong way leaves the solid untouched and fails here.
    await volume_check(adapter, "bar with clamp slots", expected, 0.01 * v_slots)
    cbore_jobs, normal_out = await _author_clamp_slot_profile(
        adapter,
        "ClampSlotCboreProfile",
        "ClampSlotCbore",
        CLAMP_SLOT_CBORE_WIDTH,
        CLAMP_SLOT_CBORE_RUN,
    )
    drive_jobs += cbore_jobs
    check(
        "cut clamp slot counterbores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=CLAMP_CBORE_DEPTH, reverse_direction=not normal_out
            )
        ),
    )
    name_last_feature(adapter, "ClampSlotCounterbores")
    name_dimensions(adapter, "ClampSlotCounterbores", ["ClampSlotCboreDepth"])
    v_slot_cbores = (
        len(CLAMP_SLOT_X)
        * (stadium_area(CLAMP_SLOT_CBORE_WIDTH, CLAMP_SLOT_CBORE_RUN) - slot_area)
        * CLAMP_CBORE_DEPTH
    )
    expected -= v_slot_cbores
    await volume_check(
        adapter, "bar with clamp slot counterbores", expected, 0.01 * v_slot_cbores
    )
    blank_reference_geometry(adapter, ((FRONT_FACE_PLANE, "PLANE"),))

    # Latch hook's base screws: two #4-40 taps THROUGH from the back face (their
    # exits on the front face lie under the platen footprint), then a
    # 90-degree countersink on both mouths of each.
    bracket_dia = blind_cut_dia_mm(BRACKET_TAP_SPEC)
    wizard_holes(
        adapter, BRACKET_TAP_SPEC,
        [[x, HANGER_TAP_Y, BACK_FACE_Z] for x in BRACKET_TAP_X],
        (0.0, 0.0, 1.0),
        f"latch-hook base-screw taps ({BRACKET_TAP_SPEC.size} through)",
        name="BracketTaps",
    )
    r_bracket = bracket_dia / 2.0
    v_bracket = len(BRACKET_TAP_X) * math.pi * r_bracket**2 * BAR_DEPTH
    expected -= v_bracket
    await volume_check(adapter, "bar with bracket taps", expected, 0.03 * v_bracket)
    bracket_csk = (BRACKET_TAP_CSK_DIA - bracket_dia) / 2.0
    check(
        "countersink bracket-tap mouths",
        await adapter.add_chamfer(
            bracket_csk,
            [
                [x + r_bracket, HANGER_TAP_Y, z_face]
                for x in BRACKET_TAP_X
                for z_face in (-BACK_FACE_Z, BACK_FACE_Z)
            ],
        ),
    )
    name_last_feature(adapter, "BracketTapCountersinks")
    v_bracket_csk = (
        2 * len(BRACKET_TAP_X) * math.pi * bracket_csk**2 * (r_bracket + bracket_csk / 3.0)
    )
    expected -= v_bracket_csk
    await volume_check(
        adapter, "bracket-tap countersinks", expected, 0.03 * v_bracket_csk + 0.05
    )

    # Hanger pivot: the #8-32 tap runs THROUGH, so the MHA-PD-VN-57 tip can be
    # faced below the front face and staked at its mouth. A plain cut from the
    # back face, mid-plane past both faces, keeps the print's own TAP callout
    # on the drill diameter.
    check(
        f"create_plane BackFace (Front Plane, +{BACK_FACE_Z})",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=BACK_FACE_Z)
        ),
    )
    name_last_feature(adapter, "BackFace")
    pivot = SketchDims()
    check("create_sketch pivot tap drill", await adapter.create_sketch("BackFace"))
    await define_circle(
        adapter,
        PIVOT_TAP_X,
        HANGER_TAP_Y,
        PIVOT_TAP_DRILL_DIA / 2.0,
        "pivot tap drill",
        dims=pivot,
        names=("PivotTapX", "PivotTapY", "PivotTapDrillDia"),
        drives=(None, None, None),
    )
    await ensure_fully_defined(adapter, "pivot tap drill sketch")
    check("exit_sketch pivot tap drill", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotTapProfile")
    drive_jobs += pivot.apply(adapter, "PivotTapProfile")
    check(
        "cut pivot tap drill (through)",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BAR_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotTap")
    r_pivot = PIVOT_TAP_DRILL_DIA / 2.0
    v_pivot = math.pi * r_pivot**2 * BAR_DEPTH
    expected -= v_pivot
    await volume_check(adapter, "bar with pivot tap drill", expected, 0.03 * v_pivot)
    pivot_csk = (PIVOT_TAP_CSK_DIA - PIVOT_TAP_DRILL_DIA) / 2.0
    check(
        "countersink pivot-tap mouths",
        await adapter.add_chamfer(
            pivot_csk,
            [
                [PIVOT_TAP_X + r_pivot, HANGER_TAP_Y, z_face]
                for z_face in (-BACK_FACE_Z, BACK_FACE_Z)
            ],
        ),
    )
    name_last_feature(adapter, "PivotTapCountersinks")
    v_pivot_csk = 2 * math.pi * pivot_csk**2 * (r_pivot + pivot_csk / 3.0)
    expected -= v_pivot_csk
    await volume_check(
        adapter, "pivot-tap countersinks", expected, 0.03 * v_pivot_csk + 0.05
    )

    # Drawing references, hidden in the part (blank_reference_sketches) and
    # shown per view by the drawing: the countersinks' MAX diameters on the
    # back face, and each hole row's stations and height.
    countersinks = SketchDims()
    check("create_sketch CountersinkReference", await adapter.create_sketch("BackFace"))
    for x, dia, label, names in (
        (
            PIVOT_TAP_X,
            PIVOT_TAP_CSK_DIA,
            "pivot countersink",
            ("PivotCskX", "PivotCskY", "PivotCskDia"),
        ),
        (
            BRACKET_TAP_X[0],
            BRACKET_TAP_CSK_DIA,
            "bracket countersink",
            ("BracketCskX", "BracketCskY", "BracketCskDia"),
        ),
    ):
        await define_circle(
            adapter,
            x,
            HANGER_TAP_Y,
            dia / 2.0,
            label,
            dims=countersinks,
            names=names,
            drives=(None, None, None),
        )
    await ensure_fully_defined(adapter, "CountersinkReference sketch")
    check("exit_sketch CountersinkReference", await adapter.exit_sketch())
    name_last_feature(adapter, "CountersinkReference")
    drive_jobs += countersinks.apply(adapter, "CountersinkReference")
    drive_jobs += await _author_row(adapter, HANGER_ROW)
    drive_jobs += await _author_row(adapter, CLAMP_ROW)
    blank_reference_geometry(adapter, (("BackFace", "PLANE"),))

    # Apply the deferred drive equations after the model exists, then re-check:
    # every equation evaluates to the value just built, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bar (equations neutral)", expected, 0.005 * expected)

    # The bottom rail's running clearance under the bar spends the height's
    # .XXX band, and the pivot screw's tip recess and the bracket-screw tips
    # the thickness's (pd_support_bar_spec.BAR_HEIGHT_BAND, BAR_DEPTH_BAND).
    # Both are the title block's .XXX row, so the model dimensions carry
    # them as their three places alone: an explicit ±.005 would restate the
    # title block (drawing-guidelines rule 2; r4 machinist review).
    apply_drawing_precision(
        adapter,
        {"BarProfile": {"Height": BAR_BAND_PLACES}, "Bar": {"Depth": BAR_BAND_PLACES}},
    )

    # The rest of the print's places, then its bands and limits: the hanger
    # holes' row and stations carry the pivot and hook positions' ±.002
    # (HOLE_POSITION_TOL; paper_drive_geom and transgear_hanger_joints read
    # HOLE_POSITION_BAND, its printed reach), the clamp holes' row and
    # stations the MHA-SH-02 taps' CLAMP_POSITION_BAND; the countersinks their
    # single MAX limits. The bands are millimetres; UNIT prints them in inches.
    apply_drawing_precision(adapter, SHEET_PRECISION)
    for name in ("HangerRowHeight", *HANGER_STATION_NAMES):
        set_dimension_symmetric_tolerance(
            adapter,
            "HangerRowReference",
            name,
            HOLE_POSITION_TOL,
            display_unit=UNIT,
        )
    for name in ("ClampRowHeight", *CLAMP_STATION_NAMES):
        set_dimension_symmetric_tolerance(
            adapter,
            "ClampRowReference",
            name,
            CLAMP_POSITION_BAND,
            display_unit=UNIT,
        )
    _single_limit(
        adapter, "CountersinkReference", "PivotCskDia", PIVOT_TAP_CSK_DIA, TOL_MAX
    )
    _single_limit(
        adapter, "CountersinkReference", "BracketCskDia", BRACKET_TAP_CSK_DIA, TOL_MAX
    )
    # The milled west slots' width carries the drilled holes' limits (it is
    # their float the closure and head checks above spend); both slots share
    # one detail, so their widths print their count.
    set_dimension_bilateral_tolerance(
        adapter,
        "ClampSlotProfile",
        "ClampSlotWidth",
        *CLAMP_SLOT_WIDTH_LIMITS,
        places=CLAMP_SLOT_WIDTH_PLACES,
        display_unit=UNIT,
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "ClampSlotCboreProfile",
        "ClampSlotCboreWidth",
        *CLAMP_SLOT_CBORE_WIDTH_LIMITS,
        places=CLAMP_SLOT_CBORE_WIDTH_PLACES,
        display_unit=UNIT,
    )
    for (feature_name, dimension_name), prefix in DIMENSION_PREFIXES.items():
        set_dimension_prefix(adapter, feature_name, dimension_name, prefix)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    # The platen's slide faces (top edge, front face) carry their roughness
    # on the MODEL as plain annotations; the drawing points at them.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
