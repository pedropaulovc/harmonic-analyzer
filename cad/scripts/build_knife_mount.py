r"""Reproduction script: knife bearing support (book ch. 18, pp. 42-43).

The hardened-steel bearing block that suspends the summing lever's knife edge from the
top-frame casting's integral crossbar (hung by a 1/2-13 knife-hanger stud
threaded into the block top). The lever rocks as a FIRST-CLASS LEVER on the **top vertex line
of its hexagonal pivot trunnions** (build_summing_lever ``_hex_collar``); each
trunnion overhangs the lever body into one of these supports.

DESIGN (user direction, 2026-06-17, refs: ch30-p003, bore.png, ch18 p.43 photo):
a **circular bore around the hex trunnion**, so that *only the top knife edge
of the trunnion* contacts the bore -- the upper inner wall of the bore meets
the hex's top vertex line while every other facet clears. This is the true
knife-edge suspension: line contact at the ridge, free to rock, replacing the
M6.4 "diamond knife-bar in the lever tube bore" (which clashed with the lever's
solid pivot cylinder once the bore was removed). 2026-09-02 user re-read of
ch18 p.42: the block is an UNPAINTED HEAT-TREATED STEEL block (not brass) with
a CLOSE bore around the trunnion -- Ø12 over the 8.653 x 10.268 hex.  At
finished-size limits it clears the observed ±1.6-degree rocking sweep.

There are TWO supports, one per trunnion (placed front/back in the assembly at
|z| ~ 87). This single part is built once and placed twice.

Layout (part-local): origin = the **knife-edge contact line** = the hex top
vertex ridge (placed at machine (15, 984.83, +-87)); local Z = the bore/trunnion
axis, +Y up, +X across. The bore centre sits ``R_BORE`` below the origin so the
bore's upper inner wall lands on the ridge. The block rises from below the bore
up to just under the top-frame casting underside (999.7); the shortened hanger
stud engages 5.8735 mm of the block-top tap. A conventional 118-degree tap drill
retains at least 0.50 mm of uninterrupted material above the bore at limits.

The named "knife axis" is the contact ridge line itself (part origin); the
assembly mates the lever's knife ridge (``Axis3@summing-lever``) coincident to
it, so the lever rocks about the true knife edge (not the cylinder centre).

Dimensions: cad/DIMENSIONS.md ch. 18. Bore size remains low-confidence
photo-derived geometry; its hard constraints are ridge contact and the observed
rocking sweep at finished-size limits.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_knife_mount.py
"""

from __future__ import annotations

import json
import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_rectilinear_chain,
    dimension_between,
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
from summing_lever_spec import HEX_H, HEX_W
from _holes import blind_hole_volume_mm3, wizard_holes
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
)
from _part_pmi import author_part_pmi
from knife_mount_spec import (
    BORE_DIAMETER_TOLERANCE_MM,
    BORE_FROM_TOP_TOLERANCE_MM,
    BORE_FROM_TOP,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    MATING_HEX_SIZE_PLUS_MM,
    REQUIRED_ROCK_SWEEP_DEG,
    STUD_TAP_CROWN_WEB_MM,
    STUD_TAP_DIA,
    STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM,
    STUD_TAP_DRILL_DEPTH_MM,
    STUD_TAP_POINT_HEIGHT_MM,
    STUD_TAP_SPEC,
    STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM,
    STUD_TAP_THREAD_DEPTH_MM,
    STUD_TAP_WORST_CASE_CROWN_WEB_MM,
    STUD_TAP_WORST_CASE_RUNOUT_MM,
    SURFACE_FINISHES,
)

import _telemetry

PART_NAME = "knife-mount"
# ch18 p.42 (2026-09-02 user re-read): an unpainted HEAT-TREATED steel block,
# not the brass of the earlier registry/DFM pass.
MATERIAL = "Plain Carbon Steel"
HARDENED_STEEL = (0.30, 0.30, 0.31)  # dark heat-treated grey, left unpainted

# --- knife-edge geometry (kept in sync with the lever's hex trunnion) -------
RIDGE_Y = HEX_H / 2.0  # hex top vertex above the pivot/cylinder centreline (5.134)

# --- bore: close around the hex trunnion, actual top-ridge line contact -----
R_BORE = 6.0  # Ø12 bore around the 8.653 x 10.268 hex trunnion
TOP_CLEAR = 0.0  # bore crown is tangent to the lever's top-vertex knife ridge
BORE_CY = TOP_CLEAR - R_BORE  # -6.0; upper inner wall lies on the knife axis

# --- block (bearing body, held to the crossbar) ----------------------------
SUPPORT_Z_THICK = 16.0  # axial depth; centred tap retains wall at .XX limits
BLK_HALF_X = 12.0  # bore wall + flank (24 across, photo-scaled)
WALL = 3.0  # material below the bore
BLK_BOT = BORE_CY - R_BORE - WALL  # -15.0

# Mount: the block top seat hangs MOUNT_GAP below the top-frame casting
# underside (the integral crossbar's flush lower face); the knife-hanger stud
# threaded into the block top carries the hang (build_summing_assembly).
KNIFE_Y = 979.7  # machine y of the pivot centreline (build_summing_assembly KNIFE)
CASTING_UNDERSIDE_Y = 999.7  # top-frame casting underside (integral crossbar)
MOUNT_GAP = 0.25  # design clearance to the casting (sliver-flag margin)
CONTACT_Y = KNIFE_Y + RIDGE_Y  # machine y of the knife-edge contact line (984.834)
BLK_TOP = CASTING_UNDERSIDE_Y - CONTACT_Y - MOUNT_GAP  # exact local top 14.616


# --- hanger-stud tap: 1/2-13 UNC-2B blind in the block top ------------------
# A conventional 118-degree drill and bottoming tap accept the 5.5-mm-shortened
# hanger stud while their native depth bands preserve an uninterrupted crown.



def _minimum_hex_rock_clearance_mm() -> float:
    """Return the worst noncontact-vertex clearance over the required sweep."""
    bore_radius = R_BORE - BORE_DIAMETER_TOLERANCE_MM / 2.0
    width = HEX_W + MATING_HEX_SIZE_PLUS_MM
    height = HEX_H + MATING_HEX_SIZE_PLUS_MM
    vertices = (
        (-width / 2.0, -height / 4.0),
        (-width / 2.0, -3.0 * height / 4.0),
        (0.0, -height),
        (width / 2.0, -3.0 * height / 4.0),
        (width / 2.0, -height / 4.0),
    )
    sweep = math.radians(REQUIRED_ROCK_SWEEP_DEG)
    clearance = math.inf
    for x, y in vertices:
        candidates = [-sweep, sweep]
        stationary = math.atan2(x, y)
        for half_turn in range(-2, 3):
            angle = stationary + half_turn * math.pi
            if -sweep <= angle <= sweep:
                candidates.append(angle)
        maximum_radius = max(
            math.sqrt(
                x * x
                + y * y
                + bore_radius * bore_radius
                + 2.0
                * bore_radius
                * (x * math.sin(angle) + y * math.cos(angle))
            )
            for angle in candidates
        )
        clearance = min(clearance, bore_radius - maximum_radius)
    return clearance


def _hole_dimension_inventory_entry(display, dimension) -> dict[str, object]:
    """Describe one native Hole Wizard display dimension for failure forensics."""
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    return {
        "full_name": str(dimension.FullName),
        "name": str(dimension.Name),
        "value_mm": float(dimension.SystemValue) * 1000.0,
        "dimension_type": int(dimension.GetType()),
        "reference": bool(dimension.IsReference()),
        "read_only": bool(dimension.ReadOnly),
        "display_type": int(display.GetType()),
        "hole_callout": bool(display.IsHoleCallout()),
        "tolerance_type": int(tolerance.Type),
        "tolerance_lower_mm": float(tolerance.GetMinValue()) * 1000.0,
        "tolerance_upper_mm": float(tolerance.GetMaxValue()) * 1000.0,
        "primary_precision": int(display.GetPrimaryPrecision2()),
        "tolerance_precision": int(display.GetPrimaryTolPrecision2()),
    }


def _tolerance_hole_depth(
    adapter,
    feature_name: str,
    dimension_token: str,
    deviations_mm: tuple[float, float],
) -> None:
    """Apply and read back one native Hole Wizard depth tolerance in the part."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    feature = model.FeatureByName(feature_name)
    if feature is None:
        raise RuntimeError(f"missing Hole Wizard feature {feature_name!r}")
    feature = _early_bound(feature, "IFeature")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError(f"{feature_name}: Hole Wizard definition is unavailable")
    definition = _early_bound(definition, "IWizardHoleFeatureData2")
    matches = []
    thread_depth_candidates = []
    inventory = []
    display = feature.GetFirstDisplayDimension()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        dimension = display.GetDimension()
        if dimension is not None:
            dimension = _early_bound(dimension, "IDimension")
            full_name = str(dimension.FullName)
            normalized = "".join(
                character for character in full_name.lower() if character.isalnum()
            )
            entry = _hole_dimension_inventory_entry(display, dimension)
            inventory.append(entry)
            if dimension_token in normalized:
                matches.append((display, dimension))
            owner = full_name.split("@", 2)
            if (
                dimension_token == "fullthreaddepth"
                and len(owner) >= 2
                and owner[1].lower().startswith("hole thread")
                and int(display.GetType()) == 2
                and not bool(dimension.ReadOnly)
                and abs(
                    float(dimension.SystemValue) - float(definition.ThreadDepth)
                )
                <= 1e-9
            ):
                thread_depth_candidates.append((display, dimension, entry))
        display = feature.GetNextDisplayDimension(display)

    semantic_rename = None
    if not matches and dimension_token == "fullthreaddepth":
        if len(thread_depth_candidates) == 1:
            display, dimension, entry = thread_depth_candidates[0]
            prior_full_name = str(dimension.FullName)
            dimension.Name = "Full Thread Depth"
            renamed_full_name = str(dimension.FullName)
            renamed_normalized = "".join(
                character
                for character in renamed_full_name.lower()
                if character.isalnum()
            )
            if "fullthreaddepth" not in renamed_normalized:
                raise RuntimeError(
                    f"{feature_name}: semantic thread-depth rename did not persist: "
                    f"{renamed_full_name!r}"
                )
            entry["renamed_full_name"] = renamed_full_name
            semantic_rename = {
                "from": prior_full_name,
                "to": renamed_full_name,
            }
            matches.append((display, dimension))
        elif thread_depth_candidates:
            semantic_rename = {
                "candidate_count": len(thread_depth_candidates),
                "status": "ambiguous",
            }

    evidence = {
        "event": "native_hole_dimension_inventory",
        "feature": feature_name,
        "requested_token": dimension_token,
        "definition": {
            "TapDrillDepth_mm": float(definition.TapDrillDepth) * 1000.0,
            "ThreadDepth_mm": float(definition.ThreadDepth) * 1000.0,
        },
        "semantic_rename": semantic_rename,
        "dimensions": inventory,
    }
    _telemetry.info(json.dumps(evidence, sort_keys=True))
    if len(matches) != 1:
        raise RuntimeError(
            f"{feature_name}: expected one {dimension_token} display dimension, "
            f"found {len(matches)}; native evidence: "
            f"{json.dumps(evidence, sort_keys=True)}"
        )
    display, dimension = matches[0]
    lower_mm, upper_mm = deviations_mm
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 2  # swTolBILAT
    if not tolerance.SetValues(lower_mm / 1000.0, upper_mm / 1000.0):
        raise RuntimeError(
            f"{feature_name} {dimension_token}: rejected native depth tolerance"
        )
    lower = float(tolerance.GetMinValue()) * 1000.0
    upper = float(tolerance.GetMaxValue()) * 1000.0
    if (
        int(tolerance.Type) != 2
        or abs(lower - lower_mm) > 1e-6
        or abs(upper - upper_mm) > 1e-6
    ):
        raise RuntimeError(
            f"{feature_name} {dimension_token}: tolerance readback "
            f"{lower:+.3f}/{upper:+.3f} mm"
        )
    display.SetPrecision3(2, -1, 2, -1)
    if (
        int(display.GetPrimaryPrecision2()) != 2
        or int(display.GetPrimaryTolPrecision2()) != 2
    ):
        raise RuntimeError(
            f"{feature_name} {dimension_token}: depth precision did not persist"
        )
    readback = feature.GetDefinition()
    if readback is None:
        raise RuntimeError(
            f"{feature_name} {dimension_token}: definition unavailable after tolerance"
        )
    readback = _early_bound(readback, "IWizardHoleFeatureData2")
    if (
        abs(float(readback.TapDrillDepth) - float(definition.TapDrillDepth)) > 1e-9
        or abs(float(readback.ThreadDepth) - float(definition.ThreadDepth)) > 1e-9
    ):
        raise RuntimeError(
            f"{feature_name} {dimension_token}: depth nominal changed while "
            "authoring its tolerance"
        )


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the bore radius + its top clearance,
    # the block half-width / wall / axial thickness, and the local block top. The
    # derived globals (BoreCy / BlkBot) are equations of the primitives so the
    # bore centre and block bottom track when a primitive changes. The mm suffix
    # is load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 12.7 = 12.7 in, 25.4x too big).
    await set_global(adapter, "RBore", f"{R_BORE}mm")
    await set_global(adapter, "TopClear", f"{TOP_CLEAR}mm")
    await set_global(adapter, "SupportZThick", f"{SUPPORT_Z_THICK}mm")
    await set_global(adapter, "BlkHalfX", f"{BLK_HALF_X}mm")
    await set_global(adapter, "Wall", f"{WALL}mm")
    await set_global(adapter, "BlkTop", f"{BLK_TOP}mm")
    await set_global(adapter, "BoreCy", '"TopClear" - "RBore"')
    await set_global(adapter, "BlkBot", '"BoreCy" - "RBore" - "Wall"')

    # Each sketch records its dim names + drive equations as the define_* helper
    # emits them; the equations are collected here and applied in one deferred
    # batch at the end (every target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Bearing block and knife bore: one actual Front-plane profile with an
    # outer rectangle and inner circle, extruded symmetrically about the tap's
    # axial centre plane. BoreFromSide and BoreFromTop directly drive the real
    # bore centre relative to the real block profile; there are no detached
    # manufacturing-dimension replicas.
    block_dims = SketchDims()
    check("create_sketch block and bore", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLK_HALF_X, BLK_BOT),
        (BLK_HALF_X, BLK_BOT),
        (BLK_HALF_X, BLK_TOP),
        (-BLK_HALF_X, BLK_TOP),
    ]
    block = await add_line_chain(adapter, block_rect)
    await define_rectilinear_chain(
        adapter,
        block,
        block_rect,
        label="block",
        dims=block_dims,
        names=["BlockWidth", "BlockHeight", "BoreFromSide", "BlockAnchorZ"],
        drives=[
            '2 * "BlkHalfX"',
            '"BlkTop" - "BlkBot"',
            '"BlkHalfX"',
            '-"BlkBot"',
        ],
    )
    set_sketch_direct_db(adapter, True)
    try:
        bore_result = await adapter.add_circle(0.0, BORE_CY, R_BORE)
    finally:
        set_sketch_direct_db(adapter, False)
    bore = check("add actual knife-bore circle", bore_result)
    check(
        "align knife-bore and hanger-tap centreline",
        await adapter.add_sketch_constraint(
            f"{bore}.center", "origin", "vertical_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{block[2]}.start",
        f"{bore}.center",
        "vertical_distance",
        BORE_FROM_TOP,
        "actual bore from top seat",
    )
    block_dims.record("BoreFromTop", '"BlkTop" - "BoreCy"')
    check(
        "dimension actual knife-bore diameter",
        await adapter.add_sketch_dimension(
            bore, None, "diameter", 2.0 * R_BORE
        ),
    )
    block_dims.record("BoreDia", '2 * "RBore"')
    await ensure_fully_defined(adapter, "block and bore profile")
    check("exit_sketch block and bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block_dims.apply(adapter, "BlockProfile")
    check(
        "extrude block with knife bore",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SUPPORT_Z_THICK, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Block")
    depth_dim = name_dimensions(adapter, "Block", ["Depth"])
    drive_jobs += [(depth_dim[0], '"SupportZThick"')]
    expected = (
        2.0 * BLK_HALF_X * (BLK_TOP - BLK_BOT)
        - math.pi * R_BORE**2
    ) * SUPPORT_Z_THICK
    vol = await _volume(adapter)
    _telemetry.info(f"volume after block and bore: {vol:.1f} mm^3")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"block-and-bore volume {vol:.1f} != {expected:.1f}")

    # The bore crown and lever ridge share the named knife axis: actual contact,
    # not the former 0.25-mm modeled gap.
    hex_top = 0.0
    contact_error = (BORE_CY + R_BORE) - hex_top
    if abs(contact_error) > 1e-9:
        raise RuntimeError(f"knife contact error is {contact_error:.6f} mm")
    # Every noncontact vertex must remain inside the minimum finished bore for
    # the complete observed rock range, with both trunnion sizes at maximum
    # material.  The former static 0.5-mm shoulder threshold had no mechanical
    # basis and rejected the valid nominal contact geometry.
    rock_clearance = _minimum_hex_rock_clearance_mm()
    if rock_clearance <= 0.0:
        raise RuntimeError(
            "hex trunnion interferes with the knife bore over "
            f"+/-{REQUIRED_ROCK_SWEEP_DEG:g} degrees: "
            f"{rock_clearance:.6f} mm clearance at limits"
        )
    _telemetry.info(
        "knife trunnion clearance at size and motion limits: "
        f"{rock_clearance:.6f} mm"
    )

    # Hanger-stud tap: native 1/2-13 blind bottoming tap on the trunnion-axis
    # centreline.  HoleWizard5 reads depth as the cylindrical drill shoulder;
    # its ordinary 118-degree point ends above the functional bore crown.
    tap_runout = STUD_TAP_DRILL_DEPTH_MM - STUD_TAP_THREAD_DEPTH_MM
    two_pitches = 2.0 * 25.4 / 13.0
    if tap_runout < two_pitches or STUD_TAP_WORST_CASE_RUNOUT_MM < two_pitches:
        raise RuntimeError(
            "stud tap has insufficient bottoming-tap lead: "
            f"{tap_runout:.4f} mm nominal, "
            f"{STUD_TAP_WORST_CASE_RUNOUT_MM:.4f} mm at limits"
        )
    tap_crown_web = (
        BLK_TOP
        - (BORE_CY + R_BORE)
        - STUD_TAP_DRILL_DEPTH_MM
        - STUD_TAP_POINT_HEIGHT_MM
    )
    if abs(tap_crown_web - STUD_TAP_CROWN_WEB_MM) > 1e-9:
        raise RuntimeError(
            "stud tap crown-web contract drifted: "
            f"model {tap_crown_web:.4f} mm, spec {STUD_TAP_CROWN_WEB_MM:.4f} mm"
        )
    if (
        tap_crown_web < 0.5
        or STUD_TAP_WORST_CASE_CROWN_WEB_MM < 0.5
    ):
        raise RuntimeError(
            "stud tap crown web is insufficient: "
            f"{tap_crown_web:.4f} mm nominal, "
            f"{STUD_TAP_WORST_CASE_CROWN_WEB_MM:.4f} mm at limits"
        )
    wizard_holes(
        adapter,
        STUD_TAP_SPEC,
        [[0.0, BLK_TOP, 0.0]],
        (0.0, 1.0, 0.0),
        "hanger-stud tapped hole (1/2-13)",
        name="StudTap",
        placement_dims=[((None, None), (None, None))],
        # no expect_dia_mm: a BLIND hole's definition reads 0.0 for both
        # diameter knobs on this seat (the tripwire is through-hole only);
        # the pinned dia is what HoleWizard5 was handed, and the volume
        # gate below proves the cut.
    )
    _tolerance_hole_depth(
        adapter,
        "StudTap",
        "tapdrilldepth",
        STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM,
    )
    _tolerance_hole_depth(
        adapter,
        "StudTap",
        "fullthreaddepth",
        STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM,
    )
    expected -= blind_hole_volume_mm3(STUD_TAP_DIA, STUD_TAP_DRILL_DEPTH_MM)
    vol = await _volume(adapter)
    _telemetry.info(f"volume after stud tap: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"stud tap volume {vol:.1f} != {expected:.1f}")

    # Named axis = the knife-edge contact ridge line (part origin, along Z). The
    # assembly mates Axis3@summing-lever (the hex ridge) coincident to it.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "knife axis")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: each equation evaluates to the value just built, so
    # the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven knife mount (equations neutral)", expected, 0.01 * expected
    )


    await apply_material(adapter, MATERIAL)
    # ch18 p.42: heat-treated and left unpainted -- a dark grey, not the
    # database steel's bright render nor the frame's green.
    await apply_color(adapter, HARDENED_STEEL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    set_dimension_symmetric_tolerance(
        adapter,
        "BlockProfile",
        "BoreDia",
        BORE_DIAMETER_TOLERANCE_MM,
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "BlockProfile",
        "BoreFromTop",
        BORE_FROM_TOP_TOLERANCE_MM,
    )
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
