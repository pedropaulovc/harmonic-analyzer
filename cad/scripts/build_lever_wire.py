r"""Reproduction script: lever wire -- WIRE 1 of the amplification chain (book
ch. 20-21, pp. 46-53).

The steel wire that hangs from the output fixture on the magnifying lever's
vertical rod and wraps the magnifying wheel's 20 mm grooved brass hub (ch. 20
p. 48: "the output fixture rides on it and the wire to the magnifying wheel
hooks below"; ch. 21 p. 51 shows it riding the hub groove). Modeled as the
STRAIGHT REST-POSE RUN only -- a plain cylinder from the fixture's cross-hole
mouth to the XY-tangent point on the hub groove. The hub wrap, the hook/knot
at the fixture and the wire's compliance are NOT modeled (the kinematic
coupling stays a Motion-study gear mate -- docs/motion-policy.md); every
surface stands >= 0.25 off its neighbour so the interference gate reads zero
(the binding pair is the axle flange's back-face edge vs the spoke fronts --
see the HUB_END_Z note below).

Endpoint derivation lives HERE (the part's length is the distance between
them); ``build_magnifier_assembly`` imports ``WIRE_START``/``WIRE_END``/
``WIRE_LEN`` and asserts them against its own layout anchors, so a layout
move fails loud instead of leaving a floating wire. The hub-end Z sits in
the clear axial lane between the wheel-axle flange back face (-141.9) and
the spoke front faces (-144.9).

The wire is also the CARRIER of the WIRE-1 coupling: ``YokePlane``, a named
reference plane parallel to Top (perpendicular to the wire axis) through the
wheel's hub-pitch yoke point (``YOKE_POINT``). The magnifying wheel's
``WireYokePoint`` is held COINCIDENT to it (the scotch-yoke primitive the
Motion study's WIRE 2 already proved SolidWorks enforces), so the wheel's
spin is tied to the lever group's travel along the wire axis -- the
linearized inextensible-wire constraint, sign and ratio straight from the
geometry. Exact at the rest pose; a linearization away from it (same
convention as the Motion study's WIRE 2 yoke).

Dimensions: cad/config/dimensions.yaml ch. 20-21 -- wire dia photo-scaled
(the book wire is hair-thin; 0.8 keeps it renderable, low confidence).

Layout: wire axis along +Y from the origin (the assembly turns it onto the
HUB->HOOK direction -- the part ORIGIN is the HUB end, so the Top plane and
its YokePlane offset sit at the hub-end tangency), length ``WIRE_LEN``.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_lever_wire.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "lever-wire"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

WIRE_DIA = 0.8  # hair-thin in the photos; renderable stand-in (low)
CLEARANCE = 0.25  # surface stand-off (interference-gate margin convention)

# --- endpoint anchors (magnifier frame; asserted by build_magnifier_assembly)
#
# DEPTH RE-ANCHOR (2026-07-04, ch30 p.4): the side view shows the whole output
# line -- this wire, the wheel, the rim wire, the pen rod -- as ONE plumb
# vertical at the machine front. The old lever depth (z -85) hung the hook 50
# behind the wheel plane, an ~8 deg lean the photo refutes. A PERFECTLY planar
# wire is impossible (the rim ring z -142.9..-150.9 blocks every straight
# in-band approach, and the hub pokes only 1.0 past the rim per side), so the
# real wire leans SLIGHTLY, ducking behind the rim's back face into the hub's
# back groove band. Solving the clearance system (>= 0.25 surface everywhere;
# rim back-face bound at radius 43.35, axle-flange bound inside radius 17.9,
# spoke fronts at -144.9) gives the hook/hub-end pair below: a 10 mm z drop
# over the ~371 run = 1.5 deg, visually plumb.
CLAMP_X = 150.0  # sliding clamp / vertical rod / fixture line
# The wire TIES through the fixture's cross hole and hangs beside the vertical
# rod, just under the collar's bottom face: wire r + 0.25 below it in y, and
# off the rod axis in -z by rod r 2.5 + wire r 0.4 + 0.25 = 3.15 (the front
# face of the rod). So HOOK_Z = VROD_Z - 3.15 with VROD_Z = -134.8
# (LEVER_ROD_Z -128.3 -- the ONLY depth window: the top-frame ring rail
# (z -101..-123, y >= 999.7) forces the thumb-screw head band deeper than
# -128.25 and the front column forces the rod deeper than -127.95, while the
# wire's rim-duck feasibility caps the hook at ~-137.96).
HOOK_Y = 925.35  # FIXTURE_Y0 926 - wire r 0.4 - 0.25 (under the collar bottom)
HOOK_Z = -137.95
WHEEL_X = 53.0  # magnifying-wheel centre
WHEEL_BAR_Y = 565.0
HUB_DIA = 20.0  # ch. 21 annotated (build_magnifying_wheel.HUB_DIA)
# Hub-end Z: in the hub's back groove band, between the rim-duck bound
# (z >= -142.25 while the run is radially inside the rim ring) and the
# axle-flange bound (<= -142.55 wherever radius < 17.9).
HUB_END_Z = -142.77

# XY tangent from the hook to the hub circle inflated by wire r + clearance,
# on the west (hook) side: the wire grazes the groove and the wrap is implied.
# (-acos picks the tangent whose contact point faces the hook at machine +x;
# the pre-#151 mirrored frame used +acos for the reflected tangent.)
_R_EFF = HUB_DIA / 2.0 + WIRE_DIA / 2.0 + CLEARANCE
_VX, _VY = CLAMP_X - WHEEL_X, HOOK_Y - WHEEL_BAR_Y  # hub centre -> hook (2D)
_THETA = math.atan2(_VY, _VX) - math.acos(_R_EFF / math.hypot(_VX, _VY))

WIRE_START = (CLAMP_X, HOOK_Y, HOOK_Z)  # hook end
WIRE_END = (
    WHEEL_X + _R_EFF * math.cos(_THETA),
    WHEEL_BAR_Y + _R_EFF * math.sin(_THETA),
    HUB_END_Z,
)  # hub end = the PART ORIGIN (local +Y runs hub -> hook)
WIRE_LEN = round(math.dist(WIRE_START, WIRE_END), 3)

# --- WIRE-1 yoke (the coupling mate's geometry) -------------------------------
# The wheel-side yoke point: on the hub PITCH circle (groove radius + wire
# radius -- where the wire centreline rides) at the SAME tangency azimuth, in
# the wheel's mid-plane (machine z -146.9). Its XY radial offset from the wire
# end is perpendicular to the wire axis by tangency, so only the z step feeds
# the YokePlane offset below.
WHEEL_MID_Z = -146.9  # wheel mid-plane (build_magnifier_assembly.WHEEL_MID_Z)
YOKE_PITCH_R = HUB_DIA / 2.0 + WIRE_DIA / 2.0  # 10.4: wire-centreline pitch
YOKE_POINT = (
    WHEEL_X + YOKE_PITCH_R * math.cos(_THETA),
    WHEEL_BAR_Y + YOKE_PITCH_R * math.sin(_THETA),
    WHEEL_MID_Z,
)
# YokePlane: parallel to the part's Top plane (perpendicular to the wire axis)
# through YOKE_POINT. Signed offset along local +Y (= the hub->hook direction).
_Y_LOCAL = [(s - e) / WIRE_LEN for s, e in zip(WIRE_START, WIRE_END, strict=True)]
YOKE_PLANE_OFFSET = round(
    sum((q - e) * y for q, e, y in zip(YOKE_POINT, WIRE_END, _Y_LOCAL, strict=True)), 4
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        CreateReferencePointParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 380 = 380 in).
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    await set_global(adapter, "WireLength", f"{WIRE_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Wire body: on-axis circle (centre at the origin), so define_circle emits
    # only the diameter dim; extruded +Y for the full run length.
    body = SketchDims()
    check("create_sketch wire", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, WIRE_DIA / 2.0, "wire", dims=body,
        names=("WireCx", "WireCz", "WireDiaDim"),
        drives=(None, None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "wire sketch")
    check("exit_sketch wire", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += body.apply(adapter, "WireProfile")
    check(
        "extrude wire",
        await adapter.create_extrusion(ExtrusionParameters(depth=WIRE_LEN)),
    )
    name_last_feature(adapter, "Wire")
    drive_jobs.append(("D1@Wire", '"WireLength"'))
    v_wire = math.pi * (WIRE_DIA / 2.0) ** 2 * WIRE_LEN
    await volume_check(adapter, "wire", v_wire, 0.005 * v_wire)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: every equation evaluates to the value just built,
    # so the geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven lever wire (equations neutral)", v_wire, 0.005 * v_wire)

    # YokePlane: the WIRE-1 coupling plane, parallel to Top (perpendicular to
    # the wire axis) through the wheel's hub-pitch yoke point -- see module
    # docstring. Blanked so the infinite plane never renders in assemblies.
    check(
        "create_plane YokePlane",
        await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Top Plane", offset=YOKE_PLANE_OFFSET)),
    )
    name_last_feature(adapter, "YokePlane")
    _blank_ref_plane(adapter, "YokePlane")

    # HookPoint: reference point at the hook-end face centre (the top circular
    # edge's arc centre -- adapter-native, deterministic). The assembly's ball
    # joint holds it coincident to the fixture's HookAnchorPoint, so the wire
    # PIVOTS at the hook instead of sweeping rigidly with the lever group.
    check(
        "ref point HookPoint",
        await adapter.create_reference_point(CreateReferencePointParameters(
            mode="arc_center", edge_point=[WIRE_DIA / 2.0, WIRE_LEN, 0.0])),
    )
    name_last_feature(adapter, "HookPoint")

    # HubPoint: the HUB-end face centre (= the part origin), same arc-centre
    # idiom on the bottom edge. The assembly's wire-SWING park driver pins this
    # point's distance to a machine plane: the swing lever arm is the whole
    # wire length, so the driver is well-conditioned where the old
    # plane-plane ANGLE (parked at 0.74 deg, a Jacobian extremum) authored
    # satisfied but pinned nothing -- caught by the release-preflight park
    # closure, 2026-07-05.
    check(
        "ref point HubPoint",
        await adapter.create_reference_point(CreateReferencePointParameters(
            mode="arc_center", edge_point=[WIRE_DIA / 2.0, 0.0, 0.0])),
    )
    name_last_feature(adapter, "HubPoint")

    # Named centreline axis (local Y): the hub STAND-OFF mate holds this axis
    # at the offset-tangency distance from the wheel's Axis1 (axis-axis
    # distance -- skew lines have ONE minimal distance, so no far-side flip,
    # and name selection survives solver motion, unlike a point-picked face).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "wire axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


def _blank_ref_plane(adapter, name: str) -> None:
    """Hide a reference plane (shown ref geometry renders in every assembly
    instance -- the fix_shown_sketches BlankRefGeom idiom, applied at build)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(name, "PLANE", 0, 0, 0, False, 0, null_callout(), 0):
        raise RuntimeError(f"blank ref plane: cannot select {name!r}")
    model.BlankRefGeom()
    model.ClearSelection2(True)


if __name__ == "__main__":
    sys.exit(run_build(build))
