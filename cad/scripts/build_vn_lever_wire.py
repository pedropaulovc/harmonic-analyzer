r"""Reproduction script: lever wire -- WIRE 1 of the amplification chain (book
ch. 20-21, pp. 46-53).

The steel wire that hangs from the output fixture on the magnifying lever's
vertical rod and wraps the brass drum (MHA-MG-010, Ø18.9) pressed on the
magnifying wheel's front spigot (ch. 20 p. 48: "the output fixture rides on
it and the wire to the magnifying wheel hooks below"; ch. 21 p. 51 shows it
riding the hub). Modeled as the
STRAIGHT REST-POSE RUN only -- a plain cylinder from the fixture's
spigot-groove front tangent to the XY-tangent point on the drum. The
fixture/drum wraps, the tie-off and the wire's compliance are NOT modeled (the kinematic
coupling stays a Motion-study gear mate -- cad/docs/motion-policy.md); every
surface stands >= 0.25 off its neighbour so the interference gate reads zero
(vn_lever_wire_geom.RUN_GAPS: the run vs the rim, spoke and boss pen-side
faces, and the drum-end z inside the drum's span).

Endpoint derivation lives in the drawing-free ``vn_lever_wire_geom`` module (the
part's length is the distance between them); ``build_mg_magnifier_assembly``
imports ``WIRE_START``/``WIRE_END``/``WIRE_LEN`` from THERE and asserts them
against its own layout anchors, so a layout move fails loud instead of
leaving a floating wire -- while this script's drawing-contract imports stay
out of the assembly/wheel recipe closures. The drum-end Z (DRUM_END_Z) is the
drum's axial middle, between the boss front face and the spigot front end,
all read off the wheel mid-plane (the pen-rod line ``paper_drive_geom.PEN_Z_MID``).

The wire is also the CARRIER of the WIRE-1 coupling: its own Top plane
(perpendicular to the wire axis, through the drum end) contains the wheel's
drum-pitch yoke point (``YOKE_POINT``) on the coplanar A1 route
(``vn_lever_wire_geom`` asserts it). The magnifying wheel's
``WireYokePoint`` is held COINCIDENT to it (the scotch-yoke primitive the
Motion study's WIRE 2 already proved SolidWorks enforces), so the wheel's
spin is tied to the lever group's travel along the wire axis -- the
linearized inextensible-wire constraint, sign and ratio straight from the
geometry. Exact at the rest pose; a linearization away from it (same
convention as the Motion study's WIRE 2 yoke).

Stock: purchased McMaster-Carr 9666K56 music wire (0.031 in, ASTM A228), cut
from the coil (MHA-VN-066); modelled at the Ø0.8 design nominal, which lies in
the catalogue band (``vn_lever_wire_geom``).

Layout: wire axis along +Y from the origin (the assembly turns it onto the
DRUM->HOOK direction -- the part ORIGIN is the DRUM end, so the Top plane
sits at the drum-end tangency), length ``WIRE_LEN``.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_lever_wire.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _com_invoke, _early_bound
from _dimensions import drive_dimension, set_global
from _feature_tree import _feature_by_name, feature_name_by_type, name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _visibility import blank_reference_geometry
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from vn_lever_wire_spec import (
    BALLOON_RING_FRACTION,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FRONT_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "vn-lever-wire"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring

# The endpoint/yoke SOLVER lives in the drawing-free ``vn_lever_wire_geom`` module
# (codex #360): the wheel + assembly import the anchors from THERE, so this
# build script's drawing-contract imports (``vn_lever_wire_spec``) never enter
# their recipe closures. Re-exported here unchanged for this build's own use.
from vn_lever_wire_geom import (  # noqa: E402
    WIRE_DIA,
    WIRE_LEN,
)

# The balloon ring (BalloonRingSplit): a projected split line round the wire
# at BALLOON_RING_FRACTION of the run from the drum end. It changes no shape;
# it only gives MHA-MG-000's balloon a model edge on the free span, where
# before the wire's only edges were its two end circles, one inside the wheel
# and one under the fixture spigot (machinist review r4, balloon 19).
BALLOON_RING_STATION = BALLOON_RING_FRACTION * WIRE_LEN
_SPLIT_OVERHANG = 0.5  # the cross line overhangs the wire so it rings it whole
_CYLINDER_IDENTITY = 4002  # swSurfaceTypes_e.CYLINDER_TYPE


def _wire_cylinder_areas(adapter) -> list[tuple[object, float]]:
    """Every Ø WIRE_DIA cylinder face of the body with its area in mm^2."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    faces: list[tuple[object, float]] = []
    for body in part.GetBodies2(0, False) or ():
        face = _early_bound(body, "IBody2").GetFirstFace()
        while face is not None:
            surface = _com_invoke(face, "IFace2", "GetSurface")
            if (
                surface is not None
                and int(_com_invoke(surface, "ISurface", "Identity")) == _CYLINDER_IDENTITY
                and math.isclose(
                    float(tuple(_com_invoke(surface, "ISurface", "CylinderParams"))[6])
                    * 1000.0,
                    WIRE_DIA / 2.0,
                    abs_tol=1e-4,
                )
            ):
                faces.append((face, float(_early_bound(face, "IFace2").GetArea()) * 1e6))
            face = _early_bound(face, "IFace2").GetNextFace()
    return faces


async def _add_balloon_ring(adapter) -> list[tuple[str, str]]:
    """Ring the wire at BALLOON_RING_STATION with a projected split line.

    One Front-plane sketch (u -> model X, v -> model Y, the wire axis): a
    centreline up the axis from the drum end to the station, driven from
    WireLength, and a cross line centred on its top end that projects both
    ways into a full ring (the MHA-PN-007 thread-limit pattern).
    """
    reach = WIRE_DIA / 2.0 + _SPLIT_OVERHANG
    dims = SketchDims()
    check("create_sketch balloon ring", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "balloon ring axis",
        await adapter.add_centerline(0.0, 0.0, 0.0, BALLOON_RING_STATION),
    )
    split = check(
        "balloon ring split line",
        await adapter.add_line(-reach, BALLOON_RING_STATION, reach, BALLOON_RING_STATION),
    )
    set_sketch_direct_db(adapter, False)
    for entity, relation in ((axis, "vertical"), (split, "horizontal")):
        check(
            f"balloon ring {entity} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    check(
        "balloon ring split centred on the axis",
        await adapter.add_sketch_constraint(f"{axis}.end", split, "midpoint"),
    )
    await anchor_point_to_origin(
        adapter, f"{axis}.start", 0.0, 0.0, "balloon ring axis on the drum end"
    )
    await dimension_between(
        adapter,
        f"{axis}.start",
        f"{axis}.end",
        "vertical_distance",
        BALLOON_RING_STATION,
        "balloon ring station",
    )
    dims.record("BalloonRingStation", f'"WireLength" * {BALLOON_RING_FRACTION}')
    await dimension_between(
        adapter,
        f"{split}.start",
        f"{split}.end",
        "horizontal_distance",
        2.0 * reach,
        "balloon ring split reach",
    )
    dims.record(None, None)
    await ensure_fully_defined(adapter, "balloon ring sketch")
    check("exit_sketch balloon ring", await adapter.exit_sketch())
    name_last_feature(adapter, "BalloonRingReference")
    drive_jobs = dims.apply(adapter, "BalloonRingReference")

    # Projected split line: the sketch at mark 4, the wire cylinder at mark 1.
    before = _wire_cylinder_areas(adapter)
    if len(before) != 1:
        raise RuntimeError(
            f"BalloonRingSplit: expected the one wire cylinder, got {len(before)}"
        )
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "BalloonRingReference", "SKETCH", 0.0, 0.0, 0.0, False, 4, null_callout(), 0
    ):
        raise RuntimeError("BalloonRingSplit: failed to select the split sketch")
    selection_manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    selection_data = _early_bound(selection_manager.CreateSelectData(), "ISelectData")
    selection_data.Mark = 1
    if not _early_bound(before[0][0], "IEntity").Select4(True, selection_data):
        raise RuntimeError("BalloonRingSplit: failed to select the wire cylinder")
    previous = feature_name_by_type(adapter, "PLine")
    model.InsertSplitLineProject(False, False)  # both directions: a full ring
    model.ClearSelection2(True)
    created = feature_name_by_type(adapter, "PLine")
    if not created or created == previous:
        raise RuntimeError("BalloonRingSplit: projected split line was not created")
    _feature_by_name(adapter, created).Name = "BalloonRingSplit"
    areas = sorted(area for _face, area in _wire_cylinder_areas(adapter))
    expected = sorted(
        math.pi * WIRE_DIA * run
        for run in (BALLOON_RING_STATION, WIRE_LEN - BALLOON_RING_STATION)
    )
    if len(areas) != 2 or any(
        abs(got - want) > 0.01 * want for got, want in zip(areas, expected)
    ):
        raise RuntimeError(
            f"BalloonRingSplit: wire faces {areas} mm^2, expected {expected}"
        )
    # The reference sketch stays out of every view.
    blank_sketch(adapter, "BalloonRingReference")
    return drive_jobs


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
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
    # Shape-neutral: a split line only adds the MHA-MG-000 balloon's edge.
    drive_jobs += await _add_balloon_ring(adapter)
    await volume_check(adapter, "wire with balloon ring", v_wire, 0.005 * v_wire)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: every equation evaluates to the value just built,
    # so the geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven lever wire (equations neutral)", v_wire, 0.005 * v_wire)

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

    # HubPoint: the DRUM-end face centre (= the part origin), same arc-centre
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
    # Hidden but still selectable by name for the hook and swing mates.
    blank_reference_geometry(
        adapter, (("HookPoint", "DATUMPOINT"), ("HubPoint", "DATUMPOINT"))
    )

    # Named centreline axis (local Y): the drum STAND-OFF mate holds this axis
    # at the offset-tangency distance from the wheel's Axis1 (axis-axis
    # distance -- skew lines have ONE minimal distance, so no far-side flip,
    # and name selection survives solver motion, unlike a point-picked face).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "wire axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: the Ø0.8 wire carries NO marked model
    # dimension (nothing on it is a dependable pick), so the mark loop is a no-op
    # over an empty contract; only the make-critical properties are stamped.  The
    # straight rest-run length is COMPUTED here and APPENDED to the notes, so
    # the derived value is never duplicated in the (import-pure) spec.  It is
    # deliberately NOT called a cut length: hook + wrap development is absent.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    notes = (
        DRAWING_NOTES
        + f"\nSTRAIGHT REST-RUN LENGTH {WIRE_LEN:.1f} END FACE TO END FACE;"
        + " NOT A CUT LENGTH."
    )
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": notes,
            "Front View Note": FRONT_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
