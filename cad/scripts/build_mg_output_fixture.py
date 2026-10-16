r"""Reproduction script: output fixture (MHA-MG-006; book ch. 20 p. 48).

The small brass hex block that slides on the vertical rod to set the trace's
height on the paper (the photographed fixture): the lever wire hooks into the
full-radius groove on its turned spigot, and a #4-40 thumb screw in the axial
tap through the spigot face locks it to the rod.

Layout (part frame, ``mg_output_fixture_geom``): the origin is the rod-bore
centre, the hex axis local +X from the free end (x = FREE_END_X) to the
spigot face (x = SPIGOT_FACE_X), flats facing +/-Z, corners on +/-Y.

* ``HexProfile``: the 3/8 hex on the ``FreeEnd`` plane, extruded to the
  shoulder.  It carries the flats (``HexAf``); its corners sit on the
  vertical through the sketch origin (the bore axis) and its two flats are
  equal, so the rod bore is centred between the flats with no dimension to
  either one.
* ``TurnedProfile``: the spigot as a Top-plane rectangle from the free end to
  the spigot face, revolved about local X (inside the hex it adds nothing:
  its Ø is under the flats).  It carries the rod bore's stations, from the
  free end (``RodStation``) and to the spigot face (``BoreStation``), the
  shoulder from the free end (``HexLength``), ``SpigotDia``, and the overall
  length as a DRIVEN dimension (``OverallLength``, REF on the sheet).
* ``GrooveProfile``: the full-radius groove, a Top-plane circle drawn as two
  semicircles meeting at the root, revolved as a cut.  Its centreline runs
  from the bore axis to the spigot face, so ``GrooveStation`` runs from the
  face; ``GrooveRadius`` sizes it (a single MAX limit) and ``GrooveRootDia``
  is the diametric dimension from the axis to the root point.
* ``RodBoreProfile``: the drilled Ø5.2 cross bore along local Y.
* ``AxialTap``: one blind Hole Wizard #4-40 tap from the spigot face (the
  thumb screw's receiver): full thread to where its axis breaks into the
  rod bore, the tap drill on to the bore axis, its point in the bore.
* ``HookAnchorPoint``: the lever wire's hook at the groove root's +Z side.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_output_fixture.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _feature_tree import name_last_feature
from _holes import cross_hole_volume_mm3, wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from mg_output_fixture_geom import (
    FREE_END_X,
    GROOVE_CENTRE_R,
    GROOVE_RADIUS,
    GROOVE_ROOT_DIA,
    GROOVE_X,
    HEX_AF,
    HEX_CORNER_RADIUS,
    HEX_LENGTH,
    HOOK_LOCAL,
    OVERALL_LENGTH,
    ROD_BORE_DIA,
    ROD_STATION,
    SHOULDER_X,
    SPIGOT_DIA,
    SPIGOT_FACE_X,
    SPIGOT_LENGTH,
    TAP_DRILL_DIA,
    TAP_SPEC,
)
from mg_output_fixture_spec import (
    BORE_STATION,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    GROOVE_STATION,
    SINGLE_LIMITS,
)

PART_NAME = "mg-output-fixture"
MATERIAL = "Brass"  # C36000 free-cutting brass (the registry row names it)

SPIGOT_R = SPIGOT_DIA / 2.0
BORE_R = ROD_BORE_DIA / 2.0
DRILL_R = TAP_DRILL_DIA / 2.0
# The rod bore's mid-plane cut: past both corners.
BORE_CUT_DEPTH = 2.0 * HEX_CORNER_RADIUS + 2.0
# The cross-section's corner offset from the axis, for the hex sketch's
# equation (the corner radius is the flats over sqrt(3)).
_CORNER_PER_AF = 1.0 / math.sqrt(3.0)
_SAVED_DRAWING_PROPERTIES = ("Manufacturing Notes",)

# --- Analytic volumes (mm^3) -----------------------------------------------------
V_HEX = math.sqrt(3.0) / 2.0 * HEX_AF**2 * HEX_LENGTH
V_SPIGOT = math.pi * SPIGOT_R**2 * SPIGOT_LENGTH


def _groove_volume() -> float:
    """Spigot material the full-radius groove removes: the circular segment
    of the groove circle under the spigot OD, swept round the axis (Pappus)."""
    above = GROOVE_CENTRE_R - SPIGOT_R  # centre height over the OD
    half_chord_sq = GROOVE_RADIUS**2 - above**2
    area = GROOVE_RADIUS**2 * math.acos(above / GROOVE_RADIUS) - above * math.sqrt(
        half_chord_sq
    )
    centroid_r = GROOVE_CENTRE_R - (2.0 / 3.0) * half_chord_sq**1.5 / area
    return 2.0 * math.pi * centroid_r * area


def _bore_volume() -> float:
    """Hex material the Ø bore across the corners removes: over the bore's
    cross-section the hex's chord along Y is 2(R - |z|/sqrt(3)), so the
    volume is 2R·πr² less (2/sqrt(3))·∬|z| dA = (2/sqrt(3))·(4/3)r³."""
    return 2.0 * math.pi * HEX_CORNER_RADIUS * BORE_R**2 - 8.0 * BORE_R**3 / (
        3.0 * math.sqrt(3.0)
    )


def _tap_volume() -> float:
    """The tap drill from the spigot face into the rod bore: the full drill
    cylinder to the bore axis less the drill's share of the bore's half on
    the face side (half the perpendicular cross-hole volume).  The drill
    stops at the bore axis, its point in the bore's air short of the far wall
    (``mg_output_fixture_spec`` proves it), so the point removes nothing."""
    return (
        math.pi * DRILL_R**2 * SPIGOT_FACE_X
        - cross_hole_volume_mm3(TAP_DRILL_DIA, ROD_BORE_DIA) / 2.0
    )


V_GROOVE = _groove_volume()
V_BORE = _bore_volume()
V_TAP = _tap_volume()
V_TOTAL = V_HEX + V_SPIGOT - V_GROOVE - V_BORE - V_TAP


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("HexAf", HEX_AF),
        ("RodStation", ROD_STATION),
        ("HexLength", HEX_LENGTH),
        ("BoreStation", BORE_STATION),
        ("SpigotDia", SPIGOT_DIA),
        ("GrooveStation", GROOVE_STATION),
        ("GrooveRadius", GROOVE_RADIUS),
        ("GrooveRootDia", GROOVE_ROOT_DIA),
        ("RodBoreDia", ROD_BORE_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Hex: the free end's plane, the bar's section, extruded to the shoulder
    check(
        "create_plane FreeEnd",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=FREE_END_X
            )
        ),
    )
    name_last_feature(adapter, "FreeEnd")
    blank_reference_geometry(adapter, (("FreeEnd", "PLANE"),))
    free_end_offset = name_dimensions(adapter, "FreeEnd", ["FreeEndOffset"])[0]
    drive_jobs.append((free_end_offset, '"RodStation"'))
    drive_jobs += await _hex_profile(adapter)
    # The negative-offset Right plane keeps the +X normal (build_fr_top_frame's
    # set pocket), so the boss runs from the free end to the shoulder.
    check(
        "extrude hex",
        await adapter.create_extrusion(ExtrusionParameters(depth=HEX_LENGTH)),
    )
    name_last_feature(adapter, "Hex")
    drive_jobs.append(("D1@Hex", '"HexLength"'))
    volume = await volume_check(adapter, "hex", V_HEX, 0.005 * V_HEX)
    await _centroid_x_check(adapter, "hex", (FREE_END_X + SHOULDER_X) / 2.0)
    await bbox_extent_check(adapter, "hex length", "x", HEX_LENGTH)
    await bbox_extent_check(adapter, "hex across the flats", "z", HEX_AF)
    await bbox_extent_check(
        adapter, "hex across the corners", "y", 2.0 * HEX_CORNER_RADIUS
    )

    # --- Spigot: turned from the free end, revolved about local X ---------------
    drive_jobs += await _turned_profile(adapter)
    check("revolve spigot", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Spigot")
    volume = await volume_check(
        adapter, "hex and spigot", volume + V_SPIGOT, 0.005 * (volume + V_SPIGOT)
    )
    await bbox_extent_check(adapter, "overall length", "x", OVERALL_LENGTH)

    # --- Full-radius wire groove -------------------------------------------------
    drive_jobs += await _groove_profile(adapter)
    check(
        "revolve groove",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Groove")
    volume = await volume_check(
        adapter, "wire groove", volume - V_GROOVE, 0.02 * V_GROOVE
    )

    # --- Rod bore across the corners (along local Y) ----------------------------
    rod = SketchDims()
    check("create_sketch rod bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_R,
        "rod bore",
        dims=rod,
        names=(None, None, "RodBoreDia"),
        drives=(None, None, '"RodBoreDia"'),
    )
    await ensure_fully_defined(adapter, "rod bore sketch")
    check("exit_sketch rod bore", await adapter.exit_sketch())
    name_last_feature(adapter, "RodBoreProfile")
    drive_jobs += rod.apply(adapter, "RodBoreProfile")
    check(
        "cut rod bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BORE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RodBore")
    volume = await volume_check(adapter, "rod bore", volume - V_BORE, 0.01 * V_BORE)

    # --- Thumb-screw tap: from the spigot face into the rod bore ----------------
    tap = wizard_holes(
        adapter,
        TAP_SPEC,
        [[SPIGOT_FACE_X, 0.0, 0.0]],
        (1.0, 0.0, 0.0),
        f"thumb-screw tap ({TAP_SPEC.size} into the rod bore)",
        name="AxialTap",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += tap.placement_drive_jobs
    volume = await volume_check(adapter, "axial tap", volume - V_TAP, 0.03 * V_TAP)

    # --- The lever wire's hook ---------------------------------------------------
    await _make_hook_point(adapter)

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven output fixture (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )
    _assert_hook_point(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # Places are the tolerance statement (drawing-guidelines.md rule 3 (decimal places carry the tolerance)): the part carries
    # them and the groove radius's single MAX limit, the drawing reads them back.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for dimension_name, (feature_name, tol_type) in SINGLE_LIMITS.items():
        _single_limit(adapter, feature_name, dimension_name, tol_type)
    # The last dimension edit is behind us: the saved geometry must still be
    # the analytic part.
    await force_rebuild(adapter)
    await volume_check(adapter, "output fixture as saved", V_TOTAL, 0.005 * V_TOTAL)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES}
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


async def _hex_profile(adapter: Any) -> list[tuple[str, str]]:
    """The 3/8 hex on ``FreeEnd``, corners on the sketch's vertical axis.

    On the negative-offset Right plane sketch x is model -Z (build_fr_top_frame
    module docstring).  Both corners sit on the vertical through the origin
    (the bore axis), each a corner radius off it; each flat is vertical, with
    equal sides either side of it.  The two flats equal make the two halves
    the same width, so the origin is centred between the flats and the rod
    bore needs no location from either; the corner radius tied to the flats
    makes the section regular.  The flats are dimensioned point to point
    across the hex.
    """
    half_af, corner = HEX_AF / 2.0, HEX_CORNER_RADIUS
    points = [
        (0.0, corner),
        (half_af, corner / 2.0),
        (half_af, -corner / 2.0),
        (0.0, -corner),
        (-half_af, -corner / 2.0),
        (-half_af, corner / 2.0),
    ]
    hexd = SketchDims()
    check("create_sketch hex", await adapter.create_sketch("FreeEnd"))
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for flat in (lines[1], lines[4]):
        check(
            f"hex flat {flat} vertical",
            await adapter.add_sketch_constraint(flat, None, "vertical"),
        )
    for first, second in ((0, 1), (1, 2), (3, 4), (4, 5)):
        check(
            f"hex sides {first}={second}",
            await adapter.add_sketch_constraint(lines[first], lines[second], "equal"),
        )
    # Equal flats, equal halves: the bore axis centred between the flats.
    check(
        "hex flats equal (bore centred)",
        await adapter.add_sketch_constraint(lines[1], lines[4], "equal"),
    )
    corner_drive = f'"HexAf" * {_CORNER_PER_AF!r}'
    await anchor_point_to_origin(adapter, f"{lines[0]}.start", 0.0, corner, "hex top corner")
    hexd.record("HexCornerTop", corner_drive)
    await anchor_point_to_origin(adapter, f"{lines[3]}.start", 0.0, -corner, "hex bottom corner")
    hexd.record("HexCornerBottom", corner_drive)
    await dimension_between(
        adapter,
        f"{lines[1]}.start",
        f"{lines[4]}.start",
        "horizontal_distance",
        HEX_AF,
        "hex across the flats",
    )
    hexd.record("HexAf", '"HexAf"')
    await ensure_fully_defined(adapter, "hex profile")
    check("exit_sketch hex", await adapter.exit_sketch())
    name_last_feature(adapter, "HexProfile")
    return hexd.apply(adapter, "HexProfile")


async def _turned_profile(adapter: Any) -> list[tuple[str, str]]:
    """The spigot's Ø from the free end to the spigot face (Top plane: sketch
    (x, y) is model (X, -Z)), split at the shoulder.  The rod bore (the sketch
    origin) is the axial datum: the free end and the spigot face each carry
    their own station from it, and the shoulder runs from the free end.

    The centreline merges into both axis corners at creation, so the chain's
    own relations define it (build_pd_transgear_thumbnut's head profile).  The
    overall length is made driven before the face's station exists, so the
    sketch is never over-defined (build_pn_pen_v_block's flat height)."""
    points = [
        (FREE_END_X, 0.0),
        (FREE_END_X, SPIGOT_R),
        (SHOULDER_X, SPIGOT_R),
        (SPIGOT_FACE_X, SPIGOT_R),
        (SPIGOT_FACE_X, 0.0),
    ]
    turned = SketchDims()
    check("create_sketch turned profile", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "turned axis", await adapter.add_centerline(FREE_END_X, 0.0, SPIGOT_FACE_X, 0.0)
    )
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for line, relation in zip(
        lines, ("vertical", "horizontal", "horizontal", "vertical", "horizontal")
    ):
        check(
            f"turned profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    free_end = f"{lines[0]}.start"
    face_on_axis = f"{lines[3]}.end"
    await anchor_point_to_origin(adapter, free_end, FREE_END_X, 0.0, "free end on the axis")
    turned.record("RodStation", '"RodStation"')
    await add_diametric_linear_dimension(
        adapter, axis, lines[2], (GROOVE_X, SPIGOT_R + 4.0), "SpigotDia"
    )
    turned.record("SpigotDia", '"SpigotDia"')
    await dimension_between(
        adapter, free_end, f"{lines[1]}.end", "horizontal_distance", HEX_LENGTH, "shoulder"
    )
    turned.record("HexLength", '"HexLength"')
    overall = await dimension_between(
        adapter,
        free_end,
        face_on_axis,
        "horizontal_distance",
        OVERALL_LENGTH,
        "overall length (REF)",
    )
    _make_driven(adapter, overall, "overall length")
    turned.record("OverallLength")
    await dimension_between(
        adapter,
        face_on_axis,
        "origin",
        "horizontal_distance",
        BORE_STATION,
        "spigot face from the bore axis",
    )
    turned.record("BoreStation", '"BoreStation"')
    await ensure_fully_defined(adapter, "turned profile")
    check("exit_sketch turned profile", await adapter.exit_sketch())
    name_last_feature(adapter, "TurnedProfile")
    return turned.apply(adapter, "TurnedProfile")


async def _groove_profile(adapter: Any) -> list[tuple[str, str]]:
    """The groove circle on the Top plane, stationed from the spigot face.

    The revolve axis runs from the bore axis to the spigot face, so its end is
    the face on the axis.  The circle is two semicircles meeting at the
    root and at the crown, both plumb over the centre (the build_dt_crank_arm
    end-cap recipe), so the root is a sketch point: ``GrooveRootDia`` is a
    diametric dimension from the axis to it.  A diametric dimension to a
    circle measures its single distance, not the doubled Ø, so it cannot
    carry the root.  The axis stays the sketch's only centreline (the
    revolve's implicit axis)."""
    groove = SketchDims()
    root_v = GROOVE_CENTRE_R - GROOVE_RADIUS  # sketch v of the root
    crown_v = GROOVE_CENTRE_R + GROOVE_RADIUS
    check("create_sketch groove", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "groove axis", await adapter.add_centerline(0.0, 0.0, SPIGOT_FACE_X, 0.0)
    )
    # add_arc sweeps CCW p1 -> p2: crown -> root bulges to the free end,
    # root -> crown to the spigot face; the shared ends merge at creation.
    toward_free_end = check(
        "groove arc toward the free end",
        await adapter.add_arc(
            GROOVE_X, GROOVE_CENTRE_R, GROOVE_X, crown_v, GROOVE_X, root_v
        ),
    )
    toward_face = check(
        "groove arc toward the spigot face",
        await adapter.add_arc(
            GROOVE_X, GROOVE_CENTRE_R, GROOVE_X, root_v, GROOVE_X, crown_v
        ),
    )
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(adapter, f"{axis}.start", 0.0, 0.0, "groove axis at the bore")
    await anchor_point_to_origin(
        adapter, f"{axis}.end", SPIGOT_FACE_X, 0.0, "groove axis to the spigot face"
    )
    groove.record("GrooveDatum", '"BoreStation"')
    # Crown and root plumb over the first arc's centre make it a semicircle;
    # the root plumb over the second's makes that one concentric.
    for point, centre in (
        (f"{toward_free_end}.start", f"{toward_free_end}.center"),
        (f"{toward_free_end}.end", f"{toward_free_end}.center"),
        (f"{toward_face}.start", f"{toward_face}.center"),
    ):
        check(
            f"groove {point} plumb over its centre",
            await adapter.add_sketch_constraint(point, centre, "vertical_points"),
        )
    await dimension_between(
        adapter,
        f"{axis}.end",
        f"{toward_free_end}.center",
        "horizontal_distance",
        GROOVE_STATION,
        "groove from the spigot face",
    )
    groove.record("GrooveStation", '"GrooveStation"')
    check(
        "groove radius",
        await adapter.add_sketch_dimension(toward_face, None, "radial", GROOVE_RADIUS),
    )
    groove.record("GrooveRadius", '"GrooveRadius"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        f"{toward_face}.start",
        (GROOVE_X, -GROOVE_CENTRE_R),
        "GrooveRootDia",
    )
    groove.record("GrooveRootDia", '"GrooveRootDia"')
    await ensure_fully_defined(adapter, "groove profile")
    check("exit_sketch groove", await adapter.exit_sketch())
    name_last_feature(adapter, "GrooveProfile")
    return groove.apply(adapter, "GrooveProfile")


def _make_driven(adapter: Any, dimension_id: str, label: str) -> None:
    """Turn a just-made sketch dimension into a DRIVEN (reference) one
    (build_pn_pen_v_block._make_driven)."""
    display = _early_bound(adapter._sketch_entities[dimension_id], "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(dimension.DrivenState) != 1:
        raise RuntimeError(f"{label}: dimension did not become driven")


def _single_limit(adapter: Any, feature: str, dimension_name: str, tol_type: int) -> None:
    """A dimension as a single limit (swTolMAX prints the model value then
    MAX, so the model IS the limit; build_ch_rocker_arm_tl_filing_stud)."""
    _, dimension = _named_dimension(adapter, feature, dimension_name)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = tol_type
    if int(tolerance.Type) != tol_type:
        raise RuntimeError(f"{dimension_name}@{feature}: single-limit type did not persist")



async def _centroid_x_check(adapter: Any, label: str, expected_x: float) -> None:
    """Fail if the body grew to the wrong side of its sketch plane."""
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"{label}: get_mass_properties failed: {mass.error}")
    com_x = float(mass.data.center_of_mass[0])
    if abs(com_x - expected_x) > 0.01:
        raise RuntimeError(
            f"{label}: centre of mass x {com_x:.4f} mm, expected {expected_x:.4f} "
            "(the extrusion ran the wrong way off FreeEnd)"
        )
    _telemetry.success(f"{label}: centre of mass x {com_x:.4f} mm")


async def _make_hook_point(adapter: Any) -> None:
    """``HookAnchorPoint``, the lever-wire ball joint's fixture-side anchor.

    No adapter writer exists for a free-XYZ reference point, so: a hidden
    Top-plane sketch point (sketch (x, y) is model (X, -Z)) promoted by
    ``InsertReferencePoint(swRefPointSketchPoint = 7)`` and renamed -- the
    build_mg_magnifying_wheel WireYokePoint recipe."""
    x, y = _hook_sketch_xy()
    check("create_sketch hook anchor", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    sketches = adapter.currentModel.SketchManager
    sk_point = sketches.CreatePoint(x / 1000.0, y / 1000.0, 0.0)
    set_sketch_direct_db(adapter, False)
    if sk_point is None:
        raise RuntimeError("hook anchor sketch point creation failed")
    check("exit_sketch hook anchor", await adapter.exit_sketch())
    name_last_feature(adapter, "HookAnchorSketch")
    blank_sketch(adapter, "HookAnchorSketch")
    _make_hook_ref_point(adapter)
    _assert_hook_point(adapter)


def _hook_sketch_xy() -> tuple[float, float]:
    """The hook's Top-plane sketch coordinates (local Y is the sketch plane)."""
    if HOOK_LOCAL[1] != 0.0:
        raise AssertionError("the hook must lie on the Top plane")
    return HOOK_LOCAL[0], -HOOK_LOCAL[2]


def _hook_sketch_points(adapter: Any) -> list[Any]:
    """The ISketchPoint list of HookAnchorSketch (exactly one expected);
    members via ``_read_member`` (the pywin32 late-binding walk idiom)."""
    model = adapter.currentModel
    feat = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feat:
            break
        if str(_read_member(feat, "Name")) == "HookAnchorSketch":
            sketch = _read_member(feat, "GetSpecificFeature2")
            return list(_read_member(sketch, "GetSketchPoints2") or [])
        feat = _read_member(feat, "GetNextFeature")
    raise RuntimeError("HookAnchorSketch not found")


def _make_hook_ref_point(adapter: Any) -> None:
    """Promote the anchor sketch point to the named ``HookAnchorPoint``
    reference-point feature (raw COM -- see ``_make_hook_point``)."""
    model = adapter.currentModel
    pts = _hook_sketch_points(adapter)
    if len(pts) != 1:
        raise RuntimeError(f"HookAnchorSketch: expected 1 point, found {len(pts)}")
    model.ClearSelection2(True)
    if not pts[0].Select2(False, 0):  # Select4's ISelectData arg = Type mismatch
        raise RuntimeError("cannot select the hook anchor sketch point")
    feat = model.FeatureManager.InsertReferencePoint(7, 0, 0.0, 1)
    model.ClearSelection2(True)
    if isinstance(feat, tuple):  # late binding marshals the object return boxed
        feat = next((f for f in feat if f is not None), None)
    if feat is None:
        raise RuntimeError("InsertReferencePoint(sketch point) returned null")
    feat.Name = "HookAnchorPoint"
    if str(_read_member(feat, "Name")) != "HookAnchorPoint":
        raise RuntimeError("reference point rename failed")
    # Hidden but still selectable by name for the lever-wire ball joint.
    blank_reference_geometry(adapter, (("HookAnchorPoint", "DATUMPOINT"),))
    _telemetry.success("HookAnchorPoint reference point created")


def _assert_hook_point(adapter: Any) -> None:
    """Fail loud if the (undimensioned, hidden) anchor point drifted from its
    authored sketch coords -- the ball joint's geometry must stay exact."""
    pts = _hook_sketch_points(adapter)
    x_mm = float(_read_member(pts[0], "X")) * 1000.0
    y_mm = float(_read_member(pts[0], "Y")) * 1000.0
    exp_x, exp_y = _hook_sketch_xy()
    if abs(x_mm - exp_x) > 1e-3 or abs(y_mm - exp_y) > 1e-3:
        raise RuntimeError(
            f"hook anchor drifted: ({x_mm:.4f}, {y_mm:.4f}) != ({exp_x:.4f}, {exp_y:.4f})"
        )
    _telemetry.success(f"hook anchor holds at ({x_mm:.4f}, {y_mm:.4f})")


if __name__ == "__main__":
    sys.exit(run_build(build))
