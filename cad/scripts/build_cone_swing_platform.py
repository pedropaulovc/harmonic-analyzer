r"""Reproduction script: cone swing platform (book ch. 12, p. 18 "pivot").

The wedge-shaped plate the whole cone-gear set rides on. The book's
top-down photo (p. 18) labels the TIP end "pivot": the pivot post, the
cone shaft and the tip clamp block all stand ON this plate, and the whole
unit swings horizontally about a vertical axis near the shaft's thin tip
to dis/engage the 16T pinion from the 64T cylinder gear (video 4/4,
engage/disengage stills). Swing separation grows with distance from the
pivot, so pivoting at the TIP gives the big-end gears -- the ones that
need real working-depth clearance -- the largest throw.

Plan shape is the p.18 wedge: a trapezoid, wide under the big end and
tapering toward the pivot. Dimensions estimated from the p.18 top-down
vs the 64T gear and the v4 stills (low).

Layout: plate lying on the Top plane, extruded +Y by the thickness.
Origin at the SWING PIVOT (the assembly rotates the plate about this
point); local +Z runs along increasing cone station, so the wide south
edge sits at local z = NORTH_OVERHANG - PLATE_LEN and the narrow north
edge overhangs the pivot by NORTH_OVERHANG. A O6.35 pivot hole marks the
pivot screw. A LOCK LOBE on the wide end's machine-west flank carries
the OPEN-ENDED LOCK NOTCH the cone-lock-knob's stud rides (v4_t00411
"knob"; see the constants block) -- the notch's mouth opens through the
lobe's outer edge, so disengaging swings the plate clear of the stud
entirely (v4_t00417) and the screwed-down knob then fences the mouth,
locking the plate engaged OR disengaged. The lobe makes the part CHIRAL,
so the
script is AUTHORED MIRRORED under MIRROR_PLANE "x0" (constants block has
the details). Named refs for the assembly: "swing pivot"
(vertical axis through the origin) and "PlateTop" (datum plane on the
top face -- the riders' seat mate, FootSeat/DeckTop pattern).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_swing_platform.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    drive_dimension,
    ensure_fully_defined,
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

PART_NAME = "cone-swing-platform"
MATERIAL = "Plain Carbon Steel"  # black-finished steel plate (p.18 dark wedge)

PLATE_T = 6.35  # 1/4" plate (low)
HALF_WIDTH_S = 20.0  # south (big-end) half-width -- wide end of the wedge
HALF_WIDTH_N = 12.0  # north (pivot/tip) half-width -- narrow end
PLATE_LEN = 214.0  # north edge -> south edge along the cone axis: covers the
# pivot post's south flank by 0.5 while keeping ~3.9 air to the crank pedestal
# engaged and ~1.9 at the disengaged swing -- the south edge is slanted in
# machine z, so the assembly asserts the gap in the plate's own frame at BOTH
# poses
NORTH_OVERHANG = 7.0  # pivot -> north edge (plate continues past the pivot)
PIVOT_HOLE_DIA = 6.35  # pivot screw clearance hole at the origin

THROUGH_CUT_DEPTH = 40.0  # mid-plane total (both_directions splits it half per
# side of the sketch plane); must exceed 2x any extent crossed

# --- lock lobe + notch (the v4_t00411 clamp knob rides this) -----------------
# A lobe on the wide end's machine-WEST flank carries an OPEN-ENDED lock
# notch: a slot-width channel from the engaged stud seat out THROUGH the
# lobe's outer edge (the mouth). The cone-lock-knob's stud (fixed to the
# base, between the pivot post and the arbor pedestal) sits at the notch's
# closed end when engaged; on disengage the plate swings until its edge
# passes the stud entirely -- v4_t00417 shows the bolt standing PAST the
# plate edge. That open mouth is what makes the DISENGAGED lock work:
# screwed down with no plate under it, the knob's washer drops past
# plate-top level and fences the mouth, so the plate cannot swing back in
# until the knob is raised (and tightened ON the plate it clamps ENGAGED).
# The notch runs along the swing arc's CHORD: at R~192 over ~3 deg to the
# mouth the sagitta is ~0.07, absorbed by the O6.35-stud-in-8.0 clearance.
#
# AUTHORED MIRRORED (the crank-pedestal precedent): the lobe made this part
# CHIRAL, so it carries MIRROR_PLANE "x0" in _transforms.py and every local-x
# below is the NEGATION of the machine-effective value -- mirror_placement
# realises the insertion as this part reflected about its own x = 0, landing
# the lobe machine-west. The assembly negates x at its transform boundary.
LOBE_X_IN = 15.0  # lobe rectangle's inner edge x -- overlaps the taper
LOBE_REACH = 19.5  # inner edge -> outer extent (x 15 -> 34.5): machine-west,
# clear of the arbor-pedestal block (asserted in the assembly). Sized with the
# notch: the mouth sits washer-radius past the engaged seat (the knob's O18
# washer still beds fully across the notch line when clamped), and the short
# exit keeps the disengage swing small enough that the plate's south edge
# stays off the crank pedestal (asserted in the assembly at both poses).
LOBE_Z_N = -179.5  # lobe north edge (local z)
LOBE_Z_S = -197.0  # lobe south edge
SLOT_W = 8.0  # notch width: O6.35 stud + chord-vs-arc slack (see above)
SLOT_E_X, SLOT_E_Z = 24.5, -190.1  # engaged stud centre (authored frame)
SLOT_R = math.hypot(SLOT_E_X, SLOT_E_Z)  # 191.67 about the swing pivot
# The plate swings + (big end away from the drum), so in PLATE coords the
# fixed stud sweeps the INVERSE rotation; in the AUTHORED (mirrored) frame
# that is unit direction (-z, x)/R at E -- outward (+x), slightly north (+z).
_SLOT_TX, _SLOT_TZ = -SLOT_E_Z / SLOT_R, SLOT_E_X / SLOT_R
# Stud travel (in plate coords) from the engaged seat to the mouth: where the
# chord crosses the lobe's outer edge. Past this the stud is OUT of the plate;
# the assembly derives the disengaged pose (edge clear of the knob washer,
# DISENGAGE_DEG) from it.
NOTCH_EXIT_TRAVEL = (LOBE_X_IN + LOBE_REACH - SLOT_E_X) / _SLOT_TX  # 10.08
_MOUTH_OVERSHOOT = 4.0  # cut ends past the edge so the mouth opens clean
_SLOT_OUT_X = SLOT_E_X + (NOTCH_EXIT_TRAVEL + _MOUTH_OVERSHOOT) * _SLOT_TX
_SLOT_OUT_Z = SLOT_E_Z + (NOTCH_EXIT_TRAVEL + _MOUTH_OVERSHOOT) * _SLOT_TZ


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 216.3 = 216.3 in).
    await set_global(adapter, "PlateT", f"{PLATE_T}mm")
    await set_global(adapter, "HalfWidthS", f"{HALF_WIDTH_S}mm")
    await set_global(adapter, "HalfWidthN", f"{HALF_WIDTH_N}mm")
    await set_global(adapter, "PlateLen", f"{PLATE_LEN}mm")
    await set_global(adapter, "NorthOverhang", f"{NORTH_OVERHANG}mm")
    await set_global(adapter, "PivotHoleDia", f"{PIVOT_HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Trapezoid plan on the Top plane (sketch (x, y) -> global (X, -Z), so the
    # north edge at local z +NORTH_OVERHANG is sketch y -NORTH_OVERHANG). The
    # tapered side lines are sloped, so direct-to-DB keeps inference from
    # snapping them.
    plate = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    plan_pts = [
        (-HALF_WIDTH_N, -NORTH_OVERHANG),  # north-west (anchor)
        (HALF_WIDTH_N, -NORTH_OVERHANG),  # north-east
        (HALF_WIDTH_S, PLATE_LEN - NORTH_OVERHANG),  # south-east
        (-HALF_WIDTH_S, PLATE_LEN - NORTH_OVERHANG),  # south-west
    ]
    lines = await add_line_chain(adapter, plan_pts)
    set_sketch_direct_db(adapter, False)
    # Anchor vertex 0 is off both axes -> 2 anchor dims (x, z) first; then seg0
    # north edge (horizontal), seg1 east taper (dx + dy), seg2 south edge
    # (horizontal); seg3 ends at the anchor -> skipped by closure = 6 dims.
    await define_polygon_chain(
        adapter, lines, plan_pts, label="plate plan", dims=plate,
        names=["NorthHalfW", "NorthOverhangDim", "NorthEdge",
               "TaperDx", "PlateLenDim", "SouthEdge"],
        drives=['"HalfWidthN"', '"NorthOverhang"', '2 * "HalfWidthN"',
                '"HalfWidthS" - "HalfWidthN"', '"PlateLen"',
                '2 * "HalfWidthS"'],
    )
    await ensure_fully_defined(adapter, "plate plan")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_T)),
    )
    name_last_feature(adapter, "Plate")
    v_plate = (HALF_WIDTH_S + HALF_WIDTH_N) * PLATE_LEN * PLATE_T
    volume = await volume_check(adapter, "plate", v_plate, 0.005 * v_plate)

    # Pivot screw hole at the origin. Origin circle: only the diameter dim.
    hole = SketchDims()
    check("create_sketch pivot hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, PIVOT_HOLE_DIA / 2.0, "pivot hole", dims=hole,
        names=("PivotCx", "PivotCz", "PivotHoleDiaDim"),
        drives=(None, None, '"PivotHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pivot hole sketch")
    check("exit_sketch pivot hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotHoleProfile")
    drive_jobs += hole.apply(adapter, "PivotHoleProfile")
    check(
        "cut pivot hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotHole")
    v_hole = math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 * PLATE_T
    volume = await volume_check(adapter, "pivot hole", volume - v_hole, 0.01 * v_hole)

    # Lock lobe: axis-aligned rectangle overlapping the taper edge (authored
    # local +x = machine-west, see the AUTHORED MIRRORED note above), merged
    # into the plate (sketch y = -local z).
    await set_global(adapter, "LobeReach", f"{LOBE_REACH}mm")
    await set_global(adapter, "LobeSpan", f"{LOBE_Z_N - LOBE_Z_S}mm")
    await set_global(adapter, "SlotW", f"{SLOT_W}mm")
    lobe = SketchDims()
    check("create_sketch lock lobe", await adapter.create_sketch("Top"))
    lobe_pts = [
        (LOBE_X_IN, -LOBE_Z_N),  # inner-north (anchor, inside the plate)
        (LOBE_X_IN + LOBE_REACH, -LOBE_Z_N),  # outer-north
        (LOBE_X_IN + LOBE_REACH, -LOBE_Z_S),  # outer-south
        (LOBE_X_IN, -LOBE_Z_S),  # inner-south
    ]
    lobe_lines = await add_line_chain(adapter, lobe_pts)
    await define_polygon_chain(
        adapter, lobe_lines, lobe_pts, label="lock lobe", dims=lobe,
        names=["LobeAnchorX", "LobeAnchorZ", "LobeNorth", "LobeWest",
               "LobeSouth"],
        drives=[None, None, '"LobeReach"', '"LobeSpan"', '"LobeReach"'],
    )
    await ensure_fully_defined(adapter, "lock lobe sketch")
    check("exit_sketch lock lobe", await adapter.exit_sketch())
    name_last_feature(adapter, "LockLobeProfile")
    drive_jobs += lobe.apply(adapter, "LockLobeProfile")
    check(
        "extrude lock lobe",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_T)),
    )
    name_last_feature(adapter, "LockLobe")
    # Merged delta = rectangle minus its overlap with the trapezoid (the
    # taper edge is linear in y, so the trapezoid rule is exact).
    def _taper_x(y: float) -> float:
        return (HALF_WIDTH_N
                + (HALF_WIDTH_S - HALF_WIDTH_N) * (y + NORTH_OVERHANG) / PLATE_LEN)
    _span = LOBE_Z_N - LOBE_Z_S
    _overlap = ((_taper_x(-LOBE_Z_N) - LOBE_X_IN)
                + (_taper_x(-LOBE_Z_S) - LOBE_X_IN)) / 2.0 * _span
    v_lobe = (LOBE_REACH * _span - _overlap) * PLATE_T
    volume = await volume_check(adapter, "lock lobe", volume + v_lobe, 0.005 * v_lobe)

    # Lock notch: open-ended channel = rotated rectangle cut (engaged seat ->
    # past the lobe's outer edge, opening the mouth) + ONE end-cap circle cut
    # at the closed engaged end. The mouth crossing is symmetric about the
    # chord centreline, so the in-material rectangle volume is exactly
    # width x NOTCH_EXIT_TRAVEL. Sketch-frame direction/normal of the chord:
    _dx, _dy = _SLOT_TX, -_SLOT_TZ
    _nx, _ny = (-_dy * SLOT_W / 2.0, _dx * SLOT_W / 2.0)
    _e = (SLOT_E_X, -SLOT_E_Z)
    _out = (_SLOT_OUT_X, -_SLOT_OUT_Z)
    slot = SketchDims()
    check("create_sketch lock notch", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    slot_pts = [
        (_e[0] + _nx, _e[1] + _ny),
        (_out[0] + _nx, _out[1] + _ny),
        (_out[0] - _nx, _out[1] - _ny),
        (_e[0] - _nx, _e[1] - _ny),
    ]
    slot_lines = await add_line_chain(adapter, slot_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(
        adapter, slot_lines, slot_pts, label="lock notch", dims=slot,
        names=["SlotAnchorX", "SlotAnchorZ", "SlotRunDx", "SlotRunDy",
               "SlotEndDx", "SlotEndDy", "SlotBackDx", "SlotBackDy"],
        drives=[None] * 8,
    )
    await ensure_fully_defined(adapter, "lock notch sketch")
    check("exit_sketch lock notch", await adapter.exit_sketch())
    name_last_feature(adapter, "LockNotchProfile")
    drive_jobs += slot.apply(adapter, "LockNotchProfile")
    check(
        "cut lock notch",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LockNotch")
    v_slot = NOTCH_EXIT_TRAVEL * SLOT_W * PLATE_T
    volume = await volume_check(adapter, "lock notch", volume - v_slot, 0.01 * v_slot)

    # Closed-end cap at the engaged seat (the mouth end is open -- no W cap).
    v_cap = math.pi * (SLOT_W / 2.0) ** 2 / 2.0 * PLATE_T
    cap = SketchDims()
    check("create_sketch notch cap E", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, _e[0], _e[1], SLOT_W / 2.0, "notch cap E", dims=cap,
        names=("CapECx", "CapECz", "CapEDia"),
        drives=(None, None, '"SlotW"'),
    )
    await ensure_fully_defined(adapter, "notch cap E sketch")
    check("exit_sketch notch cap E", await adapter.exit_sketch())
    name_last_feature(adapter, "LockNotchCapEProfile")
    drive_jobs += cap.apply(adapter, "LockNotchCapEProfile")
    check(
        "cut notch cap E",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LockNotchCapE")
    volume = await volume_check(adapter, "notch cap E", volume - v_cap, 0.02 * v_cap)

    # Apply the deferred drive equations after the model + a rebuild exist, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven platform (equations neutral)", volume, 0.01 * v_hole
    )

    # Vertical swing axis through the pivot hole -- the assembly floats the
    # plate and rotates it (and every rider on it) about this axis; the p1
    # disengage DOF. The plate is inserted with a pure Ry incline, which leaves
    # this axis vertical, so a rotation about it is the horizontal swing the
    # book describes.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "swing pivot")

    # PlateTop datum: a reference plane ON the top face (+PlateT). The pivot
    # post and tip block seat COINCIDENT to it (FootSeat/DeckTop pattern) so
    # the riders' height mates are flip-free and face-pick-free.
    check(
        "create_plane PlateTop (Top Plane, +PLATE_T)",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=PLATE_T)
        ),
    )
    name_last_feature(adapter, "PlateTop")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
