r"""Reproduction script: pinion swing bracket (book ch. 25; 2 used).

The polished-steel strap that carries one end of the alignment-pinion
drum (p. 68 close-ups, shot from the BACK side): a short rounded-end
flat bar with TWO Ø6.35 bores -- the bottom one pivots on the torque
shaft (build_pinion_pivot_shaft.py), the top one journals the drum's
arbor stub (build_alignment_pinion.py) -- plus a small Ø3 CROSS-BORE
through the tail cap below the pivot. That bore presses the cam-follower
pin (build_pinion_cam_pin.py, PR5): the lift rod's radial cam pin
(build_pinion_lift_rod.py) sweeps up beneath the follower and lifts it,
swinging the drum into mesh (p. 69 close-up with the rotation arrows).

Layout: pivot bore at the origin, arbor bore at (0, C2C), strap up +Y,
thickness z 0..5; cam-pin bore along X at (y -CAM_DROP, z mid).

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
    blank_sketch,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    feature_name_by_type,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

import _telemetry

PART_NAME = "pinion-bracket"
MATERIAL = "Plain Carbon Steel"  # p.68: bright steel strap

WIDTH = 18.0  # ch25 strap width, photo-scaled vs the 42T drum tip Ø22.4 in
# v4_pinion_018 (strap ~0.8x the tip OD; the teeth stand proud of BOTH flanks
# -- the old 22 sat flush with the tips). Assembly guard: build_drive_train's
# STRAP_R_END must match WIDTH / 2.
C2C = 43.0  # pivot bore to arbor bore (ch30 GT 2026-07-02, was 31): the pinion
# now parks LEVEL with the drive axis, 42.0 above the pivot bore, so the strap
# spans sqrt(42^2 + 9.22^2) at a 12.4 deg west lean in the disengaged rest
# (build_drive_train_assembly STRAP_C2C / STRAP_LEAN_DEG -- must match)
THICKNESS = 5.0  # photo-scaled (low)
BORE = 6.35  # both bores: torque shaft below, drum arbor stub above (derived)
CAM_BORE = 3.0  # cam-follower pin press bore (photo-scaled vs the 6.35 shafts
# in the p.69 close-up, low). Assembly guard: build_drive_train's
# SPRING-style cam asserts and build_pinion_cam_pin PIN_DIA must match.
CAM_DROP = 6.25  # pivot bore centre -> cam bore centre, down the strap
# centreline. Bounded on both sides: web to the pivot bore
# 6.25 - 1.5 - 3.175 = 1.575, rim to the cap edge 9 - 6.25 - 1.5 = 1.25.
# build_drive_train's cam geometry (and build_pinion_cam_pin's span) key off
# this drop -- must match.

R_END = WIDTH / 2.0


def _cam_bore_removed() -> float:
    """Material removed by the cam cross-bore: integral over the bore's y-band
    of (cap chord length at y) x (bore z-width at y), Simpson with 2000
    panels. The bore is fully inside the thickness (z 1..4 of 0..5) and clear
    of the pivot bore (y -4.75..-7.75 vs pivot r 3.175), so the cap's outer
    circle is the only boundary that matters."""
    r = CAM_BORE / 2.0
    n = 2000
    h = 2.0 * r / n

    def f(dy: float) -> float:
        y = -CAM_DROP + dy  # dy in [-r, r]
        return 2.0 * math.sqrt(max(R_END**2 - y * y, 0.0)) * 2.0 * math.sqrt(
            max(r * r - dy * dy, 0.0)
        )

    total = f(-r) + f(r)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * f(-r + i * h)
    return total * h / 3.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the strap width (= cap radius x 2), the
    # bore-to-bore centre distance and the bore diameter. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads BARE
    # numbers in document units (an unsuffixed 22 = 22 in). Thickness is the
    # extrude feature parameter (built with the literal); StrapThickness is
    # declared so a GUI edit sees the knob.
    await set_global(adapter, "StrapWidth", f"{WIDTH}mm")
    await set_global(adapter, "C2C", f"{C2C}mm")
    await set_global(adapter, "StrapThickness", f"{THICKNESS}mm")
    await set_global(adapter, "Bore", f"{BORE}mm")
    await set_global(adapter, "CamBore", f"{CAM_BORE}mm")
    await set_global(adapter, "CamDrop", f"{CAM_DROP}mm")

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
        adapter, 0.0, 0.0, BORE / 2.0, "pivot bore", dims=strap,
        names=("PivotBoreCx", "PivotBoreCz", "PivotBoreDia"),
        drives=(None, None, '"Bore"'),
    )
    arbor_bore = await define_circle(
        adapter, 0.0, C2C, BORE / 2.0, "arbor bore", dims=strap,
        names=("ArborBoreCx", "ArborBoreCz", "ArborBoreDia"),
        drives=(None, '"C2C"', '"Bore"'),
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
    area = (
        WIDTH * C2C
        + math.pi * R_END**2
        - 2.0 * math.pi * (BORE / 2.0) ** 2
    )
    expected = area * THICKNESS
    await volume_check(adapter, "strap", expected, 0.005 * expected)

    # Cam-follower pin cross-bore (PR5): a Ø3 hole ALONG X through the tail
    # cap, CAM_DROP below the pivot, at mid-thickness. Sketched on the Right
    # plane and cut mid-plane both directions -- symmetric about x 0, so the
    # cut itself has no handedness; only the sketch-u -> part-Z sign is
    # ambiguous, probed by volume read-back exactly like the amplitude bar's
    # top-pin hole (drive jobs held back until the winning side is proven).
    v_bore = _cam_bore_removed()
    res = await adapter.get_mass_properties()
    vol_before = res.data.volume
    for idx, u_mid in enumerate((THICKNESS / 2.0, -THICKNESS / 2.0)):
        # Per-attempt profile name (the amplitude-bar idiom): a failed first
        # attempt leaves its BLANKED sketch behind under its own name, so a
        # shared name would make the retry's dim lookup (cam.apply) bind the
        # deferred CamBore* equations to the orphan instead of the profile
        # that actually cut (review catch on #163).
        prof_name = f"CamBoreProfile{idx}"
        cam = SketchDims()
        check("create_sketch cam bore", await adapter.create_sketch("Right"))
        await define_circle(
            adapter, u_mid, -CAM_DROP, CAM_BORE / 2.0, "cam bore", dims=cam,
            names=("CamBoreCz", "CamBoreCy", "CamBoreDia"),
            drives=('"StrapThickness" / 2', '"CamDrop"', '"CamBore"'),
        )
        await ensure_fully_defined(adapter, "cam bore sketch")
        check("exit_sketch cam bore", await adapter.exit_sketch())
        name_last_feature(adapter, prof_name)
        cam_jobs = cam.apply(adapter, prof_name)
        cut = await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * R_END, both_directions=True)
        )
        if not cut.is_success:
            _telemetry.debug(
                f"cam bore cut at sketch u={u_mid:+g} failed ({cut.error}); flipping"
            )
            orphan = feature_name_by_type(adapter, "ProfileFeature")
            if orphan:
                blank_sketch(adapter, orphan)
            continue
        res = await adapter.get_mass_properties()
        removed = vol_before - res.data.volume
        if abs(removed - v_bore) < 0.02 * v_bore + 0.5:
            _telemetry.success(
                f"cam bore at sketch u={u_mid:+g} removed {removed:.1f} mm^3"
                f" (analytic {v_bore:.1f})"
            )
            name_last_feature(adapter, "CamBore")
            drive_jobs += cam_jobs
            expected -= v_bore
            break
        if removed < 0.5:
            _telemetry.debug(
                f"cam bore cut at sketch u={u_mid:+g} removed nothing; flipping"
            )
            continue
        raise RuntimeError(
            f"cam bore cut removed {removed:.1f} mm^3, expected {v_bore:.1f}"
            " -- circle misplaced/resized"
        )
    else:
        raise RuntimeError("cam bore cut removed no material on either u sign")
    await volume_check(adapter, "strap with cam bore", expected, 0.005 * expected)

    # Named bore axes for the assembly: the pivot bore (Axis1) rides the torque
    # shaft, the arbor bore (Axis2) journals the pinion. The p2 swing group keys
    # off these (concentric to the shaft + lock the pinion in -- build_drive_train).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pivot bore")
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", C2C, "arbor bore")
    # Cam-pin bore axis (along X): Front @ mid-thickness x Top @ -CAM_DROP. The
    # follower pin mates coaxial to this in the assembly, riding the swing.
    await name_bore_axis(
        adapter, "Front Plane", THICKNESS / 2.0, "Top Plane", -CAM_DROP, "cam pin bore"
    )

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven strap (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
