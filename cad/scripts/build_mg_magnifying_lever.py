r"""Reproduction script: magnifying lever rod (book ch. 20, pp. 46-49).

The round brass rod affixed to the summing lever that magnifies its sweep
up to 4x. Plain rod with domed (hemispherical) ends, clearly visible in
the p.47 close-up. The sliding clamp block, vertical rod, thumb screw and
output fixture are separate parts (build_magnifying_*.py).

Dimensions: cad/DIMENSIONS.md "Chapter 20" — Ø6 photo-scaled (low).
M6.4 revision: the M2 "310 from the 4x constraint" length is REFUTED by
the calibrated ch. 30 front view (p1): the rod spans x ~ -200..-35 at
y ~982, i.e. ~165 long. Magnification comes from the ratio of the clamp
radius (vertical-rod position along this rod, measured from the bracket
collar near the summing-lever plate) to the summing lever's own ratio --
the p.46/p.48 insets show the CLAMP sliding, not a 310 rod.

Layout: rod axis along +X from the origin (tip of the pivot-end dome at
x=0), profile revolved 360 deg about a centerline on the axis. The profile
dimensions the overall length tip to tip (what a caliper picks up), not to the
far dome centre.

``PressZone`` (blanked, on the Front plane): the cylinder the MHA-MG-001
bracket collar grips -- PRESS_ZONE_LENGTH back from the east dome TIP to its
start, running to the dome tangent (mg_lever_press_fit_geom.COLLAR_ENGAGEMENT,
the R3 dome's shrinking diameter is not banded engagement). The collar is
pressed on at the MHA-MG-000 assembly step. The rod is modelled at its nominal
Ø6 end to end -- the zone is a band, not a step -- so no model edge bounds it:
a solid line across the bar at the zone's start marks it on the print (the
zone reads between that line and the dome's tangent edge) and carries the
zone's diameter; a construction witness along the rod's bottom outline from
the zone start to the tangent carries its cylinder length; a construction arc
along the east dome's lower outline from the tangent to the tip carries the
tip, so the zone's start is dimensioned from the tip with the press band
natively (drawing-simplicity-policy.md `How the repository implements the
guidelines`: the model, not a note, owns it; ch_rod_pivot_pin's
``BlankReference``). Every other entity lies ON the silhouette, so the shown
sketch adds no stray line inside the rod.

``RodStock`` (blanked, on the Front plane): the rod's stock diameter, plain
bar stock (no band), printed once at mid-length, away from the press zone.
The revolve profile cannot carry it -- its top line's height is already the
dome radius's, so a second diameter over-defines the capsule -- hence two
short construction lines ON the top and bottom outlines, the diameter between
them. The front view shows both sketches.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_magnifying_lever.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _part_checks import report_mass_properties, volume_check
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
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import set_dimension_bilateral_tolerance
from mg_lever_press_fit_geom import (
    COLLAR_ENGAGEMENT,
    PRESS_ZONE_DIA,
    PRESS_ZONE_DIA_BAND,
    PRESS_ZONE_LENGTH,
    PRESS_ZONE_LENGTH_BAND,
    ROD_DIA,
)
from mg_magnifying_lever_geom import (
    KNIFE_LOCAL_X,
    KNIFE_LOCAL_Y,
    PRESS_ZONE_X,
    ROD_LENGTH,
)
from mg_magnifying_lever_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISO_VIEW_NOTE,
)

PART_NAME = "mg-magnifying-lever"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

R = ROD_DIA / 2.0
if PRESS_ZONE_DIA != ROD_DIA:
    raise AssertionError("the press zone is the modelled rod, not a step")
# The banded zone starts PRESS_ZONE_LENGTH back from the east dome tip and
# ends where that dome starts: the straight engagement.
PRESS_ZONE_END = ROD_LENGTH - R
if ROD_LENGTH - PRESS_ZONE_X[0] != PRESS_ZONE_LENGTH:
    raise AssertionError("the press zone does not start its length from the tip")
if PRESS_ZONE_END - PRESS_ZONE_X[0] != COLLAR_ENGAGEMENT:
    raise AssertionError("the press zone witness is not the collar engagement")
# Where the stock diameter prints: mid-length, under the clamp's travel.
ROD_DIA_STATION = ROD_LENGTH / 2.0

# The reference sketches' entities, Front-plane part (x, y) mm, rod axis on
# y = 0.  The zone-start mark is the ONE line the shown sketches draw inside
# the rod: across the bar at the zone's start, both ends on the outline.
# Everything else lies ON the silhouette -- the zone's witness on the bottom
# outline, its tip arc on the east dome's lower outline (centre, start, end;
# counter-clockwise from the tangent to the tip), the stock's two lines on the
# top and bottom outlines -- so the print shows no stray line inside the rod.
PRESS_ZONE_START_LINE = ((PRESS_ZONE_X[0], -R), (PRESS_ZONE_X[0], R))
PRESS_ZONE_WITNESS = ((PRESS_ZONE_X[0], -R), (PRESS_ZONE_END, -R))
PRESS_ZONE_TIP_ARC = ((PRESS_ZONE_END, 0.0), (PRESS_ZONE_END, -R), (ROD_LENGTH, 0.0))
ROD_STOCK_LINES = tuple(
    ((ROD_DIA_STATION - R, y), (ROD_DIA_STATION + R, y)) for y in (R, -R)
)


def silhouette_offset(x: float, y: float) -> float:
    """Distance (mm) of a Front-plane point from the capsule's outline: the
    two straight flanks between the dome tangents, the two hemispheres
    beyond them.  Zero means ON the silhouette."""
    if R <= x <= ROD_LENGTH - R:
        return abs(abs(y) - R)
    centre = R if x < R else ROD_LENGTH - R
    return abs(math.hypot(x - centre, y) - R)


for _start, _end in (PRESS_ZONE_WITNESS, *ROD_STOCK_LINES):
    # A straight entity on a flank: both ends on it, at one height.
    if not (
        R <= _start[0] < _end[0] <= ROD_LENGTH - R
        and _start[1] == _end[1]
        and silhouette_offset(*_start) == silhouette_offset(*_end) == 0.0
    ):
        raise AssertionError(f"reference line {(_start, _end)} leaves the outline")
if not (
    PRESS_ZONE_TIP_ARC[0] == (ROD_LENGTH - R, 0.0)
    and all(silhouette_offset(*point) == 0.0 for point in PRESS_ZONE_TIP_ARC[1:])
):
    raise AssertionError("the zone's tip arc must lie on the east dome's outline")
_mark_bottom, _mark_top = PRESS_ZONE_START_LINE
if not (
    R < _mark_bottom[0] == _mark_top[0] < ROD_LENGTH - R
    and silhouette_offset(*_mark_bottom) == silhouette_offset(*_mark_top) == 0.0
    and _mark_bottom[1] < 0.0 < _mark_top[1]
):
    raise AssertionError("the zone-start mark must span the bar inside its outline")


def _make_construction(adapter, entity: str) -> None:
    """Turn one sketch segment into construction geometry, and prove it."""
    segment = _early_bound(adapter._sketch_entities[entity], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity}: failed to become construction geometry")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the rod length and diameter, and the
    # collar's length from the dome tip (the press zone's reach). The mm
    # suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 165 = 165
    # in, blowing the part up 25.4x).
    await set_global(adapter, "RodLength", f"{ROD_LENGTH}mm")
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "CollarLen", f"{PRESS_ZONE_LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, ROD_LENGTH, 0.0),
    )
    # Half-profile: top line, two quarter-arc dome caps, closing axis line.
    top = check(
        "add_line top",
        await adapter.add_line(R, R, ROD_LENGTH - R, R),
    )
    cap_right = check(
        "add_arc right dome",
        await adapter.add_arc(ROD_LENGTH - R, 0.0, ROD_LENGTH, 0.0, ROD_LENGTH - R, R),
    )
    axis_line = check(
        "add_line axis",
        await adapter.add_line(ROD_LENGTH, 0.0, 0.0, 0.0),
    )
    cap_left = check(
        "add_arc left dome",
        await adapter.add_arc(R, 0.0, R, R, 0.0, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    # 14-unknown half-profile: origin corner anchored, both dome centres
    # on the axis (the left one dimensioned from the origin corner), the
    # tip-to-tip length, ONE radial dim on the right dome (it puts that
    # centre R back from the right tip; the left dome's radius is already
    # forced by its anchored centre + the anchored origin end --
    # dimensioning it too over-defines), the top edge horizontal with its
    # start vertically aligned over the left centre. The centerline
    # merged into the two axis corners, so it carries no constraints.
    check(
        "anchor origin corner",
        await adapter.add_sketch_constraint(
            f"{axis_line}.end", "origin", "coincident"
        ),
    )
    check(
        "axis line horizontal",
        await adapter.add_sketch_constraint(axis_line, None, "horizontal"),
    )
    # Record each manual display dim into SketchDims as it is created (creation
    # order): the left dome centre is on the axis (x = R, one horizontal dim),
    # then the overall length between the two tips (the axis line's ends,
    # merged with the domes' apexes -- build_ch_fulcrum_shaft's idiom), then
    # the right dome radius. The origin-corner anchor is a coincident relation
    # (no dim) and the horizontal / horizontal-points / vertical-points
    # constraints carry no dims either -- three display dims total.
    await anchor_point_to_origin(
        adapter, f"{cap_left}.center", R, 0.0, "left dome centre"
    )
    profile.record("LeftDomeCentre", '"RodDia" / 2')
    check(
        "right dome centre on the axis",
        await adapter.add_sketch_constraint(
            f"{cap_right}.center", "origin", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{axis_line}.start",
        f"{axis_line}.end",
        "horizontal_distance",
        ROD_LENGTH,
        "rod OverallLength",
    )
    profile.record("OverallLength", '"RodLength"')
    check(
        "right dome radius",
        await adapter.add_sketch_dimension(cap_right, None, "radial", R),
    )
    profile.record("DomeRadius", '"RodDia" / 2')
    check(
        "top horizontal",
        await adapter.add_sketch_constraint(top, None, "horizontal"),
    )
    check(
        "top start over left centre",
        await adapter.add_sketch_constraint(
            f"{top}.start", f"{cap_left}.center", "vertical_points"
        ),
    )
    await ensure_fully_defined(adapter, "rod profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += profile.apply(adapter, "RodProfile")

    check(
        "revolve rod",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Rod")

    # Cylindrical body (length L - 2R, radius R) plus a full sphere from the two
    # hemispherical end domes: V = pi R^2 (L - 2R) + 4/3 pi R^3.
    v_rod = math.pi * R * R * (ROD_LENGTH - 2.0 * R) + 4.0 / 3.0 * math.pi * R**3
    await volume_check(adapter, "rod", v_rod, 0.005 * v_rod)

    # REFERENCE sketch (blanked before save): the press zone -- see the module
    # docstring and PRESS_ZONE_START_LINE. The zone-start mark across the bar
    # (a SOLID line: the print shows it), a construction witness along the
    # rod's bottom outline from the mark's foot to the dome tangent (on the
    # bottom so the zone's lengths print below the rod with their extension
    # lines clear of it), and a construction arc along the east dome's lower
    # outline from the witness's end, tangent to it, to the tip on the axis.
    # Four display dims, in creation order: the tip station from the origin
    # (unmarked; the profile prints the overall length), the zone's start back
    # from the tip, the cylinder's length to the tangent (printed as a
    # reference), then the diameter across the mark.
    zone = SketchDims()
    check("create_sketch press zone", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    (mark_x0, mark_y0), (mark_x1, mark_y1) = PRESS_ZONE_START_LINE
    zone_mark = check(
        "press zone start mark",
        await adapter.add_line(mark_x0, mark_y0, mark_x1, mark_y1),
    )
    (witness_x0, witness_y0), (witness_x1, witness_y1) = PRESS_ZONE_WITNESS
    zone_witness = check(
        "press zone witness",
        await adapter.add_line(witness_x0, witness_y0, witness_x1, witness_y1),
    )
    (arc_cx, arc_cy), (arc_x0, arc_y0), (arc_x1, arc_y1) = PRESS_ZONE_TIP_ARC
    zone_tip_arc = check(
        "press zone tip arc",
        await adapter.add_arc(arc_cx, arc_cy, arc_x0, arc_y0, arc_x1, arc_y1),
    )
    set_sketch_direct_db(adapter, False)
    _make_construction(adapter, zone_witness)
    _make_construction(adapter, zone_tip_arc)
    for first, second, relation in (
        (zone_mark, None, "vertical"),
        (zone_witness, None, "horizontal"),
        (f"{zone_mark}.start", f"{zone_witness}.start", "coincident"),
        (f"{zone_witness}.end", f"{zone_tip_arc}.start", "coincident"),
        (zone_witness, zone_tip_arc, "tangent"),
        (f"{zone_tip_arc}.center", "origin", "horizontal_points"),
        (f"{zone_tip_arc}.end", "origin", "horizontal_points"),
    ):
        check(
            f"press zone {first} {relation} {second}",
            await adapter.add_sketch_constraint(first, second, relation),
        )
    await dimension_between(
        adapter,
        f"{zone_tip_arc}.end",
        "origin",
        "horizontal_distance",
        ROD_LENGTH,
        "press zone PressZoneTip",
    )
    zone.record("PressZoneTip", '"RodLength"')
    await dimension_between(
        adapter,
        f"{zone_witness}.start",
        f"{zone_tip_arc}.end",
        "horizontal_distance",
        PRESS_ZONE_LENGTH,
        "press zone PressZoneStart",
    )
    zone.record("PressZoneStart", '"CollarLen"')
    await dimension_between(
        adapter,
        f"{zone_witness}.start",
        f"{zone_witness}.end",
        "horizontal_distance",
        COLLAR_ENGAGEMENT,
        "press zone PressZoneLen",
    )
    zone.record("PressZoneLen", '"CollarLen" - "RodDia" / 2')
    await dimension_between(
        adapter,
        f"{zone_mark}.start",
        f"{zone_mark}.end",
        "vertical_distance",
        PRESS_ZONE_DIA,
        "press zone PressZoneDia",
    )
    zone.record("PressZoneDia", '"RodDia"')
    await ensure_fully_defined(adapter, "press zone sketch")
    check("exit_sketch press zone", await adapter.exit_sketch())
    name_last_feature(adapter, "PressZone")
    drive_jobs += zone.apply(adapter, "PressZone")

    # REFERENCE sketch (blanked before save): the stock diameter -- see the
    # module docstring and ROD_STOCK_LINES. Two short construction lines on
    # the top and bottom outlines at mid-length, the bottom one under the top
    # one. Four display dims, in creation order: the lines' station from the
    # origin, their length and the top line's height (all unmarked), then the
    # diameter between the two lines' starts.
    stock = SketchDims()
    check("create_sketch rod stock", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    stock_lines: list[str] = []
    for side, ((x0, y0), (x1, y1)) in zip(("top", "bottom"), ROD_STOCK_LINES):
        stock_lines.append(
            check(f"rod stock {side} line", await adapter.add_line(x0, y0, x1, y1))
        )
    stock_top, stock_bottom = stock_lines
    set_sketch_direct_db(adapter, False)
    for line in (stock_top, stock_bottom):
        _make_construction(adapter, line)
    for first, second, relation in (
        (stock_top, None, "horizontal"),
        (stock_bottom, None, "horizontal"),
        (f"{stock_bottom}.start", f"{stock_top}.start", "vertical_points"),
        (f"{stock_bottom}.end", f"{stock_top}.end", "vertical_points"),
    ):
        check(
            f"rod stock {first} {relation} {second}",
            await adapter.add_sketch_constraint(first, second, relation),
        )
    await dimension_between(
        adapter,
        f"{stock_top}.start",
        "origin",
        "horizontal_distance",
        ROD_DIA_STATION - R,
        "rod stock RodDiaStation",
    )
    stock.record("RodDiaStation", '"RodLength" / 2 - "RodDia" / 2')
    await dimension_between(
        adapter,
        f"{stock_top}.start",
        f"{stock_top}.end",
        "horizontal_distance",
        ROD_DIA,
        "rod stock RodStockSpan",
    )
    stock.record("RodStockSpan", '"RodDia"')
    await dimension_between(
        adapter,
        f"{stock_top}.start",
        "origin",
        "vertical_distance",
        R,
        "rod stock RodStockTop",
    )
    stock.record("RodStockTop", '"RodDia" / 2')
    await dimension_between(
        adapter,
        f"{stock_bottom}.start",
        f"{stock_top}.start",
        "vertical_distance",
        ROD_DIA,
        "rod stock RodDia",
    )
    stock.record("RodDia", '"RodDia"')
    await ensure_fully_defined(adapter, "rod stock sketch")
    check("exit_sketch rod stock", await adapter.exit_sketch())
    name_last_feature(adapter, "RodStock")
    drive_jobs += stock.apply(adapter, "RodStock")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven rod (equations neutral)", v_rod, 0.005 * v_rod)

    # Named rod axis (local X through the origin = the revolve axis); the
    # bracket collar is pressed onto the rod's east end, concentric with it.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "rod axis")

    # KnifeAxis (Axis2): the knife-edge pivot line, local Z through
    # (KNIFE_LOCAL_X, KNIFE_LOCAL_Y) -- see the module-level block. The line is
    # outside the rod body (the physical rod attaches to the summing bar 50 mm
    # past its own domed end; the attachment is not modeled), which is fine for
    # a reference axis: the assembly pivots the lever about it.
    await name_bore_axis(adapter, "Right Plane", KNIFE_LOCAL_X,
                         "Top Plane", KNIFE_LOCAL_Y, "knife axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: the stock diameter is plain bar stock
    # (no band; the title block's .X governs it), the press zone's diameter
    # carries the geom's tighter (upper, lower) band and its start from the tip
    # the collar length's axial band, both natively
    # (drawing-simplicity-policy.md `How the repository implements the
    # guidelines`), places come from the spec, then mark exactly the print's
    # dimensions (the drawing recipe imports the marked set and must find
    # every one of these) and stamp the make-critical title-block properties.
    # The rod OD carries no finish: the clamp only slides on it to be set, then
    # pinches it (drawing-guidelines.md rule 6). The reference sketches are
    # blanked for the assembly renders; the front view shows them per view.
    set_dimension_bilateral_tolerance(
        adapter, "PressZone", "PressZoneDia", *deviations(PRESS_ZONE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PressZone", "PressZoneStart", *deviations(PRESS_ZONE_LENGTH_BAND)
    )
    # A linear dimension across a side-view sketch prints no Ø by itself
    # (build_dt_pinion_arbor's journals; the v41 sheet read "6.000 0/-0.008").
    set_dimension_prefix(adapter, "PressZone", "PressZoneDia", "<MOD-DIAM>")
    set_dimension_prefix(adapter, "RodStock", "RodDia", "<MOD-DIAM>")
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME, {"Iso View Note": ISO_VIEW_NOTE})
    blank_reference_sketches(adapter, ("PressZone", "RodStock"))
    # Annotation changes must leave the rod intact through the final rebuild,
    # not merely at the earlier, pre-annotation equation check.
    await force_rebuild(adapter)
    await volume_check(adapter, "final rod (annotations neutral)", v_rod, 0.005 * v_rod)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
