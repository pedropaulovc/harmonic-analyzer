r"""Reproduction script: pinion swing bracket (book ch. 25; 2 used).

The polished-steel strap that carries one end of the alignment-pinion
drum (p. 68 close-ups, shot from the BACK side): a short rounded-end
flat bar with a O6.35 pivot bore below (the torque shaft,
build_pinion_pivot_shaft.py) and a O8 arbor bore above (the steel
arbor, build_pinion_arbor.py) -- plus a BLIND O4 bore in the WEST EDGE
just below the pivot (PR8, page001_img01): it seats the cam-follower
pin (build_pinion_cam_pin.py) that rests ON the lift rod's eccentric
cam collar (build_pinion_cam.py) from above, so turning the lever
raises the collar under the pin and swings the drum east into mesh.
(PR5's O3 tail CROSS-bore at drop 6.25 is retired: the photo puts the
fatter pin near pivot height, and only a blind edge seat clears the
pivot bore there -- a through bore at drop 2 would cut into it.)

Layout: pivot bore at the origin, arbor bore at (0, C2C), strap up +Y,
thickness z 0..5; pin bore along X into the -X edge at (y -PIN_DROP,
z mid), PIN_SEAT deep from the x -9 tangent plane -- its mouth is
already on the r9 cap arc (the edge at y -2 sits at x -8.775). The
assembly composes a Ry(180) into the strap's lean pose, so local -x (the
pin-bore edge) reads machine WEST and the origin lands at the strap's
NORTH face.

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_bracket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from pinion_bracket_geometry import (
    ARBOR_BORE,
    C2C,
    PIN_BORE,
    PIN_DROP,
    PIN_SEAT,
    PIVOT_BORE,
    R_END,
    THICKNESS,
    WIDTH,
)
from pinion_bracket_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
)

import _telemetry

PART_NAME = "pinion-bracket"
MATERIAL = "Plain Carbon Steel"  # p.68: bright steel strap
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)


def _pin_bore_removed() -> float:
    """Material removed by the blind edge bore: for each (dy, dz) point of
    the bore disc the removed length runs from the cap arc surface
    x = -sqrt(R_END^2 - y^2) east to the bore bottom x = -(R_END - PIN_SEAT).
    z drops out (the disc's z-chord scales it); Simpson over dy."""
    r = PIN_BORE / 2.0
    bottom = -(R_END - PIN_SEAT)  # -5
    n = 2000
    h = 2.0 * r / n

    def f(dy: float) -> float:
        y = -PIN_DROP + dy
        chord = 2.0 * math.sqrt(max(r * r - dy * dy, 0.0))
        surface = -math.sqrt(max(R_END**2 - y * y, 0.0))
        return chord * max(bottom - surface, 0.0)

    total = f(-r) + f(r)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * f(-r + i * h)
    return total * h / 3.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the strap width (= cap radius x 2), the
    # bore-to-bore centre distance and the bore diameters. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads BARE
    # numbers in document units (an unsuffixed 22 = 22 in). Thickness is the
    # extrude feature parameter (built with the literal); StrapThickness is
    # declared so a GUI edit sees the knob.
    await set_global(adapter, "StrapWidth", f"{WIDTH}mm")
    await set_global(adapter, "C2C", f"{C2C}mm")
    await set_global(adapter, "StrapThickness", f"{THICKNESS}mm")
    await set_global(adapter, "PivotBore", f"{PIVOT_BORE}mm")
    await set_global(adapter, "ArborBore", f"{ARBOR_BORE}mm")
    await set_global(adapter, "PinBore", f"{PIN_BORE}mm")
    await set_global(adapter, "PinDrop", f"{PIN_DROP}mm")
    await set_global(adapter, "PinSeatDepth", f"{PIN_SEAT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Outer rounded-bar loop + both bores in ONE sketch -> single extrude.
    # Inference OFF: the bottom cap arc endpoints sit near the origin.
    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    bottom_cap = check(
        "add bottom cap arc",
        await adapter.add_arc(0.0, 0.0, -R_END, 0.0, R_END, 0.0),
    )
    check("add right edge", await adapter.add_line(R_END, 0.0, R_END, C2C))
    top_cap = check(
        "add top cap arc",
        await adapter.add_arc(0.0, C2C, R_END, C2C, -R_END, C2C),
    )
    check("add left edge", await adapter.add_line(-R_END, C2C, -R_END, 0.0))
    # Pivot bore on the origin (only its diameter recorded); arbor bore on the +Y
    # axis (x 0): one centre dim (the rise, driven by the positive C2C) + diameter.
    await define_circle(
        adapter, 0.0, 0.0, PIVOT_BORE / 2.0, "pivot bore", dims=strap,
        names=("PivotBoreCx", "PivotBoreCz", "PivotBoreDia"),
        drives=(None, None, '"PivotBore"'),
    )
    arbor_bore = await define_circle(
        adapter, 0.0, C2C, ARBOR_BORE / 2.0, "arbor bore", dims=strap,
        names=("ArborBoreCx", "ArborBoreCz", "ArborBoreDia"),
        drives=(None, '"C2C"', '"ArborBore"'),
    )
    set_sketch_direct_db(adapter, False)
    # Cap arcs: centre + radius + endpoint alignment (one angle constraint
    # per endpoint -- centre + radius + both endpoints fully located would
    # over-define an arc's 5 DOF). The side edges carry no relations of
    # their own: their endpoints merged with the cap endpoints at creation,
    # so the four h-aligned cap ends pin them too.
    check(
        "anchor bottom cap centre",
        await adapter.add_sketch_constraint(
            f"{bottom_cap}.center", "origin", "coincident"
        ),
    )
    check(
        "bottom cap radius",
        await adapter.add_sketch_dimension(bottom_cap, None, "radial", R_END),
    )
    strap.record("BottomCapRadius", '"StrapWidth" / 2')
    # The top cap is CONCENTRIC with the arbor bore -- that is the design intent,
    # so say it as a constraint instead of re-dimensioning the rise. (The obvious
    # alternative, anchor_point_to_origin + an ArborCentreRise = "C2C" equation,
    # fails live: SolidWorks rejects ANY equation binding on that point-to-origin
    # distance dim -- even a literal 43mm -- erroring the Equations folder on
    # rebuild, while the identical dim on the bore circle takes "C2C" fine.
    # Probed 2026-07-02; same bug class as the magnifying-lever dome radius.)
    check(
        "top cap centre concentric with arbor bore",
        await adapter.add_sketch_constraint(
            f"{top_cap}.center", f"{arbor_bore}.center", "coincident"
        ),
    )
    check(
        "top cap radius",
        await adapter.add_sketch_dimension(top_cap, None, "radial", R_END),
    )
    strap.record("TopCapRadius", '"StrapWidth" / 2')
    for cap, end in (
        (bottom_cap, "start"),
        (bottom_cap, "end"),
        (top_cap, "start"),
        (top_cap, "end"),
    ):
        check(
            f"cap {end} level",
            await adapter.add_sketch_constraint(
                f"{cap}.{end}", f"{cap}.center", "horizontal_points"
            ),
        )
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    check(
        "extrude strap",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "Strap")
    depth_dim = name_dimensions(adapter, "Strap", ["Depth"])
    drive_jobs += [(depth_dim[0], '"StrapThickness"')]
    area = (
        WIDTH * C2C
        + math.pi * R_END**2
        - math.pi * (PIVOT_BORE / 2.0) ** 2
        - math.pi * (ARBOR_BORE / 2.0) ** 2
    )
    expected = area * THICKNESS
    await volume_check(adapter, "strap", expected, 0.005 * expected)

    # Blind cam-pin seat (PR8): O4 along X into the -X edge at (y -PIN_DROP,
    # z mid), PIN_SEAT deep from a tangent plane at x -R_END. Both signs are
    # computed UP FRONT, not probed by exception-retry (#194): the seat is on
    # the -X edge, so the offset plane sits at Right - R_END (global x = -9);
    # and the sketch rides that Right-parallel plane, whose local +u maps to
    # global -Z (SolidWorks' standard Right-plane orientation), so the circle
    # centre sits at u = -THICKNESS/2 to land at global z = +THICKNESS/2 --
    # mid-thickness, INSIDE the 0..THICKNESS body. The mirror combo
    # (u = +THICKNESS/2 -> z = -2.5) lands outside the body, so FeatureCut3
    # rejects the empty profile ("Parameter not optional") -- exactly the
    # self-correcting retry #194 removed. The centre-u dim is an UNSIGNED
    # distance from the origin, so it displays as its magnitude and the drive
    # '"StrapThickness" / 2' is positive on the flipped side (unit-safe). Two
    # assertions keep a wrong plane handedness or a mislocated circle LOUD: the
    # removed volume vs analytic (the strap is x-symmetric BEFORE this cut, so
    # a volumetric pass alone cannot tell the -x seat from its +x mirror) and
    # the centre-of-mass x sign (material removed at -x pushes the COM to +x).
    v_bore = _pin_bore_removed()
    res = await adapter.get_mass_properties()
    vol_before = res.data.volume
    check(
        f"create_plane PinSeatPlane (Right, {-R_END:+g})",
        await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Right Plane", offset=-R_END,
        )),
    )
    name_last_feature(adapter, "PinSeatPlane")
    seat = SketchDims()
    u_mid = -THICKNESS / 2.0
    check("create_sketch pin seat", await adapter.create_sketch("PinSeatPlane"))
    await define_circle(
        adapter, u_mid, -PIN_DROP, PIN_BORE / 2.0, "pin seat", dims=seat,
        names=("PinSeatCz", "PinSeatCy", "PinSeatDia"),
        drives=('"StrapThickness" / 2', '"PinDrop"', '"PinBore"'),
    )
    await ensure_fully_defined(adapter, "pin seat sketch")
    check("exit_sketch pin seat", await adapter.exit_sketch())
    name_last_feature(adapter, "PinSeatProfile")
    drive_jobs += seat.apply(adapter, "PinSeatProfile")
    cut = await adapter.create_cut_extrude(ExtrusionParameters(depth=PIN_SEAT))
    if not cut.is_success:
        raise RuntimeError(f"pin seat cut failed: {cut.error}")
    res = await adapter.get_mass_properties()
    removed = vol_before - res.data.volume
    if abs(removed - v_bore) > 0.02 * v_bore + 0.5:
        raise RuntimeError(
            f"pin seat cut removed {removed:.1f} mm^3, expected {v_bore:.1f} "
            "-- circle misplaced/resized or wrong side"
        )
    com = res.data.center_of_mass
    com_x = com[0] * 1000.0 if com is not None else None
    if com_x is None or com_x <= 0.02:
        raise RuntimeError(
            f"pin seat landed on the wrong edge (COM x {com_x}) -- "
            "the -x seat must push the COM to +x"
        )
    _telemetry.success(
        f"pin seat (plane {-R_END:+g}, u {u_mid:+g}) removed "
        f"{removed:.1f} mm^3 (analytic {v_bore:.1f}), COM x {com_x:+.3f}"
    )
    name_last_feature(adapter, "PinSeat")
    seat_depth_dim = name_dimensions(adapter, "PinSeat", ["Depth"])
    drive_jobs += [(seat_depth_dim[0], '"PinSeatDepth"')]
    expected -= v_bore
    await volume_check(adapter, "strap with pin seat", expected, 0.005 * expected)

    # Named bore axes for the assembly: the pivot bore (Axis1) rides the torque
    # shaft, the arbor bore (Axis2) journals the pinion. The p2 swing group keys
    # off these (concentric to the shaft + lock the pinion in -- build_drive_train).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pivot bore")
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", C2C, "arbor bore")
    # Pin seat axis (along X): Front @ mid-thickness x Top @ -PIN_DROP. The
    # follower pin mates coaxial to this in the assembly, riding the swing.
    await name_bore_axis(
        adapter, "Front Plane", THICKNESS / 2.0, "Top Plane", -PIN_DROP, "pin seat"
    )

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven strap (equations neutral)", expected, 0.005 * expected)

    # Manufacturing drawing support: mark exactly the print's dimensions (the
    # drawing recipe imports the marked set and must find every one of these),
    # and stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
