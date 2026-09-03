r"""Reproduction script: lever wire -- WIRE 1 of the amplification chain (book
ch. 20-21, pp. 46-53).

The steel wire that hangs from the output fixture on the magnifying lever's
vertical rod and wraps the magnifying wheel's 20 mm grooved brass hub (ch. 20
p. 48: "the output fixture rides on it and the wire to the magnifying wheel
hooks below"; ch. 21 p. 51 shows it riding the hub groove). Modeled as the
STRAIGHT REST-POSE RUN only -- a plain cylinder from the fixture's cross-hole
mouth to the XY-tangent point on the hub groove. The hub wrap, the hook/knot
at the fixture and the wire's compliance are NOT modeled (the kinematic
coupling stays a Motion-study gear mate -- cad/docs/motion-policy.md); every
surface stands >= 0.25 off its neighbour so the interference gate reads zero
(the binding pair is the axle flange's back-face edge vs the spoke fronts --
see the HUB_END_Z note below).

Endpoint derivation lives in the drawing-free ``lever_wire_geom`` module (the
part's length is the distance between them); ``build_magnifier_assembly``
imports ``WIRE_START``/``WIRE_END``/``WIRE_LEN`` from THERE and asserts them
against its own layout anchors, so a layout move fails loud instead of
leaving a floating wire -- while this script's drawing-contract imports stay
out of the assembly/wheel recipe closures. The hub-end Z sits in the clear
axial lane between the wheel-axle flange back face (-141.9) and the spoke
front faces (-144.9).

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
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
)
from lever_wire_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    FRONT_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    WIRE_DIA_TOLERANCE_MM,
)

PART_NAME = "lever-wire"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# The endpoint/yoke SOLVER lives in the drawing-free ``lever_wire_geom`` module
# (codex #360): the wheel + assembly import the anchors from THERE, so this
# build script's drawing-contract imports (``lever_wire_spec``) never enter
# their recipe closures. Re-exported here unchanged for this build's own use.
from lever_wire_geom import (  # noqa: E402
    WIRE_DIA,
    WIRE_LEN,
    YOKE_PLANE_OFFSET,
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
    # The extrusion depth IS the straight rest-run: named ``Depth`` so the
    # print can mark it (the fleet's shaft idiom) and shown there as a
    # reference dimension.
    depth_dim = name_dimensions(adapter, "Wire", ["Depth"])
    drive_jobs.append((depth_dim[0], '"WireLength"'))
    v_wire = math.pi * (WIRE_DIA / 2.0) ** 2 * WIRE_LEN
    await volume_check(adapter, "wire", v_wire, 0.005 * v_wire)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: every equation evaluates to the value just built,
    # so the geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    # The bought wire's diameter band rides the MODEL dimension (policy rule
    # 2), so the 10:1 end view prints it natively -- never a note figure.
    set_dimension_symmetric_tolerance(
        adapter, "WireProfile", "WireDiaDim", WIRE_DIA_TOLERANCE_MM
    )
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

    # Manufacturing drawing support: mark exactly the print's two model
    # dimensions (the banded Ø on the profile circle, the straight rest-run as
    # the extrusion depth) and stamp the make-critical properties.  The
    # rest-run is a REFERENCE dimension on the sheet, not a cut length: hook
    # + wrap development is absent from the model.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Front View Note": FRONT_VIEW_NOTE,
            "End View Note": END_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
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
