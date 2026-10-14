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
the R3 dome's shrinking diameter is not banded engagement) -- PRESSED on and
retained per the bracket sheet. The rod is modelled at its nominal Ø6 end to
end -- the zone is a band, not a step -- so no model edge bounds it: a
centerline on the axis from the zone start to the tip, located from the
origin by the rod length, and a construction witness along the rod's bottom
outline from the zone start to the tangent carry the zone's start from the
tip, its cylinder length and its diameter with the press band natively
(drawing-simplicity-policy.md `How the repository implements the guidelines`: the model, not a note, owns it; ch_rod_pivot_pin's
``BlankReference``).

``RodStock`` (blanked, on the Front plane): the rod's stock diameter with the
cold-drawn bar's band, printed once at mid-length, away from the press zone.
The revolve profile cannot carry it -- its top line's height is already the
dome radius's, so a second diameter over-defines the capsule -- hence a
construction witness from the axis to the top outline, doubled off a short
centerline on the axis, the PressZone idiom. The front view shows both.

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
from _part_pmi import author_part_pmi
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
from _drawing_dimension_insert import add_diametric_linear_dimension
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
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISO_VIEW_NOTE,
    ROD_DIA_BAND,
    SURFACE_FINISHES,
)

PART_NAME = "mg-magnifying-lever"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

R = ROD_DIA / 2.0
if PRESS_ZONE_DIA != ROD_DIA:
    raise AssertionError("the press zone is the modelled rod, not a step")
# The banded zone starts PRESS_ZONE_LENGTH back from the east dome tip and
# ends where that dome starts: the straight engagement.
PRESS_ZONE_END = ROD_LENGTH - R
# abs_tol 1e-9: the inch stations (6-1/2, 6-5/16, 3/16) are not exact binary
# fractions in mm, so exact float equality fails on representation alone.
if not math.isclose(ROD_LENGTH - PRESS_ZONE_X[0], PRESS_ZONE_LENGTH, abs_tol=1e-9):
    raise AssertionError("the press zone does not start its length from the tip")
if not math.isclose(PRESS_ZONE_END - PRESS_ZONE_X[0], COLLAR_ENGAGEMENT, abs_tol=1e-9):
    raise AssertionError("the press zone witness is not the collar engagement")
# Where the stock diameter prints: mid-length, under the clamp's travel.
ROD_DIA_STATION = ROD_LENGTH / 2.0


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
    # docstring. A centerline on the axis from the zone start to the east tip,
    # and a witness along the rod's bottom outline from the zone start to the
    # dome tangent (made construction, so the shown sketch prints no outline
    # of its own; on the bottom so the zone's lengths print below the rod
    # with their extension lines clear of it). Four display dims, in creation
    # order: the tip station from the origin (unmarked; the profile prints the
    # overall length), the zone's start back from the tip, the cylinder's
    # length to the tangent (printed as a reference), then the diameter to the
    # witness's start -- doubled off the axis, the way the pivot pins print
    # theirs.
    zone = SketchDims()
    check("create_sketch press zone", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    zone_axis = check(
        "press zone axis",
        await adapter.add_centerline(PRESS_ZONE_X[0], 0.0, ROD_LENGTH, 0.0),
    )
    zone_witness = check(
        "press zone witness",
        await adapter.add_line(PRESS_ZONE_X[0], -R, PRESS_ZONE_END, -R),
    )
    set_sketch_direct_db(adapter, False)
    _make_construction(adapter, zone_witness)
    for line in (zone_axis, zone_witness):
        check(
            f"press zone {line} horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
    check(
        "press zone axis on the rod axis",
        await adapter.add_sketch_constraint(
            f"{zone_axis}.start", "origin", "horizontal_points"
        ),
    )
    check(
        "press zone witness start over the axis start",
        await adapter.add_sketch_constraint(
            f"{zone_axis}.start", f"{zone_witness}.start", "vertical_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{zone_axis}.end",
        "origin",
        "horizontal_distance",
        ROD_LENGTH,
        "press zone PressZoneTip",
    )
    zone.record("PressZoneTip", '"RodLength"')
    await dimension_between(
        adapter,
        f"{zone_witness}.start",
        f"{zone_axis}.end",
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
    await add_diametric_linear_dimension(
        adapter,
        zone_axis,
        f"{zone_witness}.start",
        ((PRESS_ZONE_X[0] + PRESS_ZONE_END) / 2.0, R + 6.0),
        "PressZoneDia",
    )
    zone.record("PressZoneDia", '"RodDia"')
    await ensure_fully_defined(adapter, "press zone sketch")
    check("exit_sketch press zone", await adapter.exit_sketch())
    name_last_feature(adapter, "PressZone")
    drive_jobs += zone.apply(adapter, "PressZone")

    # REFERENCE sketch (blanked before save): the stock diameter -- see the
    # module docstring. A short centerline on the axis, the construction
    # witness rising from its midpoint to the top outline. Three display dims,
    # in creation order: the witness's station from the origin and the
    # centerline's length (both unmarked), then the diameter to the witness's
    # top, doubled off the centerline.
    stock = SketchDims()
    check("create_sketch rod stock", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    stock_axis = check(
        "rod stock axis",
        await adapter.add_centerline(
            ROD_DIA_STATION - R, 0.0, ROD_DIA_STATION + R, 0.0
        ),
    )
    stock_witness = check(
        "rod stock witness",
        await adapter.add_line(ROD_DIA_STATION, 0.0, ROD_DIA_STATION, R),
    )
    set_sketch_direct_db(adapter, False)
    _make_construction(adapter, stock_witness)
    check(
        "rod stock axis horizontal",
        await adapter.add_sketch_constraint(stock_axis, None, "horizontal"),
    )
    check(
        "rod stock witness vertical",
        await adapter.add_sketch_constraint(stock_witness, None, "vertical"),
    )
    check(
        "rod stock axis on the rod axis",
        await adapter.add_sketch_constraint(
            f"{stock_axis}.start", "origin", "horizontal_points"
        ),
    )
    check(
        "rod stock witness foot at the axis midpoint",
        await adapter.add_sketch_constraint(
            f"{stock_witness}.start", stock_axis, "midpoint"
        ),
    )
    await dimension_between(
        adapter,
        f"{stock_witness}.start",
        "origin",
        "horizontal_distance",
        ROD_DIA_STATION,
        "rod stock RodDiaStation",
    )
    stock.record("RodDiaStation", '"RodLength" / 2')
    await dimension_between(
        adapter,
        f"{stock_axis}.start",
        f"{stock_axis}.end",
        "horizontal_distance",
        ROD_DIA,
        "rod stock RodStockAxis",
    )
    stock.record("RodStockAxis", '"RodDia"')
    await add_diametric_linear_dimension(
        adapter,
        stock_axis,
        f"{stock_witness}.end",
        (ROD_DIA_STATION, R + 6.0),
        "RodDia",
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

    # Manufacturing drawing support: the stock diameter carries the cold-drawn
    # bar's band, the press zone's diameter the geom's tighter (upper, lower)
    # band and its start from the tip the collar length's axial band, all
    # natively (drawing-simplicity-policy.md `How the repository implements the guidelines`), places come from the spec, then mark exactly
    # the print's dimensions (the drawing recipe imports the marked set and
    # must find every one of these), author the OD finish on the part, and
    # stamp the make-critical title-block properties. The reference sketches
    # are blanked for the assembly renders; the front view shows them per view.
    set_dimension_bilateral_tolerance(
        adapter, "RodStock", "RodDia", *deviations(ROD_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PressZone", "PressZoneDia", *deviations(PRESS_ZONE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "PressZone", "PressZoneStart", *deviations(PRESS_ZONE_LENGTH_BAND)
    )
    # A diametric linear dimension on a side-view sketch prints no Ø by itself
    # (build_dt_pinion_arbor's journals; the v41 sheet read "6.000 0/-0.008").
    set_dimension_prefix(adapter, "PressZone", "PressZoneDia", "<MOD-DIAM>")
    set_dimension_prefix(adapter, "RodStock", "RodDia", "<MOD-DIAM>")
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Iso View Note": ISO_VIEW_NOTE,
        },
    )
    blank_reference_sketches(adapter, ("PressZone", "RodStock"))
    # Annotation changes must leave the rod intact through the final rebuild,
    # not merely at the earlier, pre-annotation equation check.
    await force_rebuild(adapter)
    await volume_check(adapter, "final rod (annotations neutral)", v_rod, 0.005 * v_rod)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
