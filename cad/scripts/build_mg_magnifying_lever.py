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
x=0), profile revolved 360 deg about a centerline on the axis.

``PressZone`` (blanked, on the Front plane): the last
mg_lever_press_fit_geom.PRESS_ZONE_LENGTH of the rod, which is PRESSED into
the MHA-MG-001 bracket collar and retained with Loctite 638 (user ruling
2026-10-11). The rod is modelled at its nominal Ø6 end to end -- the zone is a
band, not a step -- so no model edge bounds it; a construction witness along
the rod's top outline over the zone, with the axis under it, carries the
zone's length from the dome tip and its diameter with the press band natively
(policy rule 2: the model, not a note, owns it; ch_rod_pivot_pin's
``BlankReference``). The front view shows it.

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
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_prefix,
)
from mg_lever_press_fit_geom import (
    PRESS_ZONE_DIA,
    PRESS_ZONE_DIA_BAND,
    PRESS_ZONE_LENGTH,
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
    END_VIEW_NOTE,
    ISO_VIEW_NOTE,
)

PART_NAME = "mg-magnifying-lever"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

R = ROD_DIA / 2.0
if PRESS_ZONE_DIA != ROD_DIA:
    raise AssertionError("the press zone is the modelled rod, not a step")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the rod length and diameter, and the
    # press zone's length (the bracket collar's). The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 165 = 165 in, blowing
    # the part up 25.4x).
    await set_global(adapter, "RodLength", f"{ROD_LENGTH}mm")
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "PressZoneLen", f"{PRESS_ZONE_LENGTH}mm")

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
    # anchored on the axis, ONE radial dim (the left dome's radius is
    # already forced by its anchored centre + the anchored origin end --
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
    # then the right dome centre (x = L - R, one horizontal dim), then the right
    # dome radius. The origin-corner anchor is a coincident relation (no dim) and
    # the horizontal / vertical-points constraints carry no dims either -- three
    # display dims total.
    await anchor_point_to_origin(
        adapter, f"{cap_left}.center", R, 0.0, "left dome centre"
    )
    profile.record("LeftDomeCentre", '"RodDia" / 2')
    await anchor_point_to_origin(
        adapter, f"{cap_right}.center", ROD_LENGTH - R, 0.0, "right dome centre"
    )
    profile.record("RightDomeCentre", '"RodLength" - "RodDia" / 2')
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
    # docstring. Witness along the rod's top outline over the zone (made
    # construction, so the shown sketch prints no outline of its own), the
    # axis segment under it carrying only relations. Three display dims, in
    # creation order: the zone length between the witness's ends, the zone's
    # end station from the origin (the dome tip; unmarked, the overall length
    # is the note's), then the diameter to the witness's start -- doubled off
    # the axis, the way the pivot pins print theirs.
    zone = SketchDims()
    check("create_sketch press zone", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    zone_axis = check(
        "press zone axis",
        await adapter.add_centerline(PRESS_ZONE_X[0], 0.0, PRESS_ZONE_X[1], 0.0),
    )
    zone_witness = check(
        "press zone witness",
        await adapter.add_line(PRESS_ZONE_X[0], R, PRESS_ZONE_X[1], R),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[zone_witness], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{zone_witness}: failed to become construction geometry")
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
    for end in ("start", "end"):
        check(
            f"press zone axis {end} under the witness {end}",
            await adapter.add_sketch_constraint(
                f"{zone_axis}.{end}", f"{zone_witness}.{end}", "vertical_points"
            ),
        )
    await dimension_between(
        adapter,
        f"{zone_witness}.start",
        f"{zone_witness}.end",
        "horizontal_distance",
        PRESS_ZONE_LENGTH,
        "press zone PressZoneLen",
    )
    zone.record("PressZoneLen", '"PressZoneLen"')
    await dimension_between(
        adapter,
        f"{zone_witness}.end",
        "origin",
        "horizontal_distance",
        PRESS_ZONE_X[1],
        "press zone PressZoneEnd",
    )
    zone.record("PressZoneEnd", '"RodLength"')
    await add_diametric_linear_dimension(
        adapter,
        zone_axis,
        f"{zone_witness}.start",
        ((PRESS_ZONE_X[0] + PRESS_ZONE_X[1]) / 2.0, R + 6.0),
        "PressZoneDia",
    )
    zone.record("PressZoneDia", '"RodDia"')
    await ensure_fully_defined(adapter, "press zone sketch")
    check("exit_sketch press zone", await adapter.exit_sketch())
    name_last_feature(adapter, "PressZone")
    drive_jobs += zone.apply(adapter, "PressZone")

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

    # Manufacturing drawing support: the press zone's diameter carries the
    # geom's (upper, lower) stock band natively (policy rule 2), places come
    # from the spec, then mark exactly the print's dimensions (the drawing
    # recipe imports the marked set and must find every one of these) and
    # stamp the make-critical title-block properties. The reference sketch is
    # blanked for the assembly renders; the front view shows it per view.
    set_dimension_bilateral_tolerance(
        adapter, "PressZone", "PressZoneDia", *deviations(PRESS_ZONE_DIA_BAND)
    )
    # A diametric linear dimension on a side-view sketch prints no Ø by itself
    # (build_dt_pinion_arbor's journals; the v41 sheet read "6.000 0/-0.008").
    set_dimension_prefix(adapter, "PressZone", "PressZoneDia", "<MOD-DIAM>")
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
            "Iso View Note": ISO_VIEW_NOTE,
        },
    )
    blank_reference_sketches(adapter, ("PressZone",))
    # Annotation changes must leave the rod intact through the final rebuild,
    # not merely at the earlier, pre-annotation equation check.
    await force_rebuild(adapter)
    await volume_check(adapter, "final rod (annotations neutral)", v_rod, 0.005 * v_rod)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
