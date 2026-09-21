r"""Reproduction script: crank pinion (book ch. 11/12, pp. 16, 19, 20).

The pinion on the crankshaft that meshes the dark steel crank-drive gear
at the cone set's large end (`build_crank_drive_gear.py`), implementing
the book-stated 4:1 crank-to-cone reduction (p. 16). Tooth count/DP per
the Appendix C #9 split, with DP 25.7311 fixed by the manually
rederived v2 post's cast-in crank axis. A plain straight spur
with a root-relieved floor; the crossed-mesh accommodation lives on the
64T (see its docstring for the full rederivation). On its outboard face
a plain hub boss at the tooth root (ch12 p.19 page002_img02 / img06)
carries the 1/8 in retention pin that keys the pinion to the crankshaft
through a match-drilled radial cross-hole (crank_pinion_spec).

Dimensions: cad/config/dimensions.yaml ch12 crank-drive gear row +
Appendix C #9. Face slightly wider than the drive gear's (meshing-pair
practice, axial alignment slack).

Layout: gear axis = Z through the origin, teeth z = 0..10.8 mm, boss
z = 10.8..17.28 mm, pin cross-hole along X at z = 14.04.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pinion.py
"""

from __future__ import annotations

import math
import sys

import _config
import _telemetry
from _common import (
    IN,
    SketchDims,
    _feature_by_name,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _gear import build_fixed_gear, volume_check
from _holes import cross_hole_volume_mm3, wizard_hole_on_cylinder
from _part_pmi import author_part_pmi
from crank_pinion_spec import (
    BORE_DIA_BAND,
    BOSS_CHAMFER,
    BOSS_DIA,
    BOSS_LENGTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FACE_WIDTH,
    GEAR_DATA,
    OUTSIDE_DIA,
    OVERALL_LENGTH,
    PIN_DIA,
    PIN_HOLE_SPEC,
    PIN_STATION,
    SURFACE_FINISHES,
)

PART_NAME = "crank-pinion"
MATERIAL = "Plain Carbon Steel"  # steel like its mate (p.19/20)

TEETH = 16  # DIMENSIONS.md ch12 / Appendix C #9 estimate (low)
DP = _config.machine("gear_train", "crank_drive_diametral_pitch")  # cad/config/machine.yaml (low)
PA_DEG = 14.5
# FACE_WIDTH (10.8: spans the 64T row north of the v2 crank boss) lives in
# crank_pinion_spec with the boss and pin it sizes; build_drive_train_assembly's
# PINION_FACE asserts equality. (The old 12.0 "slightly wider than the drive
# gear's 10" was a low-confidence read; 11.0 fit the line-of-centres overhang
# model but grazed the true rim minimum at the tight 2026-07-14 fit.)
BORE_DIAMETER = 0.375 * IN  # 9.525 -- crankshaft dia (med)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): every length carries the load-bearing
    # mm suffix (INCH document; the equation manager reads bare numbers in
    # document units, so an unsuffixed length blows the part up 25.4x).
    # FaceWidth drives the gear blank's extrude depth, OutsideDia its tip
    # circle: both are printed dimensions, so both are knobs. TEETH/DP stay
    # module constants -- the tooth gap and pattern are built by
    # build_fixed_gear with literal numerics, off this self-naming path.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "OutsideDia", f"{OUTSIDE_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")
    await set_global(adapter, "BossDia", f"{BOSS_DIA}mm")
    await set_global(adapter, "BossLength", f"{BOSS_LENGTH}mm")
    await set_global(adapter, "BossChamfer", f"{BOSS_CHAMFER}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Root-relieved floor (real dedendum): the mating 64T's tips reach
    # 0.71 mm BELOW this 16T's base circle at working depth -- the stock
    # base-chord gap floor (fine for the big-count train pairs) starves a
    # 16-tooth pinion, and was half of why the old mesh could not close
    # (2026-07-14 rederive; see build_crank_drive_gear.py's docstring).
    # The pinion stays a plain straight spur otherwise -- the book's
    # removable "gear on the crankshaft can be changed" stock member; the
    # crossing accommodation (helix + backlash) lives on the 64T.
    volume = await build_fixed_gear(
        adapter, TEETH, FACE_WIDTH, dp=DP, pa_deg=PA_DEG, root_relief=True,
    )

    # build_fixed_gear is shared by five recipes, so it leaves the blank under
    # the adapter's default names. Name the blank extrude and its absorbed
    # profile sketch here: the two sizes the turner sets before a cutter
    # touches the part -- face width and outside diameter -- print as NATIVE
    # model dimensions (drawing-simplicity-policy.md rule 1), which means they
    # must be named, driven, toleranced and marked like any other. Driving both
    # is also the guard on these default names: a rename that resolved the
    # wrong feature would move the blank and the equation-neutral volume gate
    # below would fail loud instead of printing a dimension of something else.
    _feature_by_name(adapter, "Boss-Extrude1").Name = "GearBlank"
    _telemetry.success("feature 'Boss-Extrude1' -> 'GearBlank'")
    drive_jobs += [
        (name_dimensions(adapter, "GearBlank", ["FaceWidth"])[0], '"FaceWidth"')
    ]
    _feature_by_name(adapter, "Sketch1").Name = "GearBlankProfile"
    _telemetry.success("feature 'Sketch1' -> 'GearBlankProfile'")
    drive_jobs += [
        (
            name_dimensions(adapter, "GearBlankProfile", ["OutsideDia"])[0],
            '"OutsideDia"',
        )
    ]

    # Hub boss (ch12 p.19): the root-circle cylinder extruded from the SAME
    # faced end as the teeth, through the toothed length and BOSS_LENGTH past
    # it, so its depth IS the part's overall length -- one conspicuous native
    # dimension from one faced end (policy rule 7). Inside the toothed length
    # the cylinder lies within the blank's solid core (its surface is the
    # relieved gap floors' own root arc), so the merge adds exactly the
    # outboard stub, which the volume gate proves.
    boss = SketchDims()
    check("create_sketch boss", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BOSS_DIA / 2.0, "boss", dims=boss,
        names=("BossCx", "BossCz", "BossDia"),
        drives=(None, None, '"BossDia"'),
    )
    await ensure_fully_defined(adapter, "boss sketch")
    check("exit_sketch boss", await adapter.exit_sketch())
    name_last_feature(adapter, "BossProfile")
    drive_jobs += boss.apply(adapter, "BossProfile")
    check(
        "extrude boss",
        await adapter.create_extrusion(ExtrusionParameters(depth=OVERALL_LENGTH)),
    )
    name_last_feature(adapter, "Boss")
    drive_jobs += [
        (
            name_dimensions(adapter, "Boss", ["OverallLength"])[0],
            '"FaceWidth" + "BossLength"',
        )
    ]
    v_boss = math.pi * (BOSS_DIA / 2.0) ** 2 * BOSS_LENGTH
    volume = await volume_check(adapter, "hub boss", volume + v_boss, 0.01 * v_boss)

    # On-axis bore (centre 0,0) through teeth and boss: define_circle emits
    # only the diameter dim, so only the "Dia" slot is recorded -- the X/Z
    # names are ignored.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIAMETER / 2.0, "bore", dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=OVERALL_LENGTH + 2.0)
        ),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * (BORE_DIAMETER / 2.0) ** 2 * OVERALL_LENGTH
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Boss end break: the photographed rounding as the sized 45-degree chamfer
    # rule 7 prefers, on the boss's outer end edge. A cone of this size on the
    # bore's edge instead would remove a different volume, so the gate below
    # is also the guard on the coordinate edge pick.
    check(
        "chamfer boss end",
        await adapter.add_chamfer(BOSS_CHAMFER, [[BOSS_DIA / 2.0, 0.0, OVERALL_LENGTH]]),
    )
    name_last_feature(adapter, "BossBreak")
    drive_jobs += [
        (name_dimensions(adapter, "BossBreak", ["BossChamfer"])[0], '"BossChamfer"')
    ]
    v_chamfer = math.pi * BOSS_CHAMFER**2 * (BOSS_DIA / 2.0 - BOSS_CHAMFER / 3.0)
    volume = await volume_check(
        adapter, "boss end break", volume - v_chamfer, 0.2 * v_chamfer
    )

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train). Stays Axis2: the cross-hole comes
    # after it and creates no axis of its own.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "bore axis")

    # Retention-pin cross-hole (crank_pinion_spec): a native 1/8 in drill
    # radially through the boss wall on local -X at the boss's mid-length,
    # through-all so it exits the far wall too (the pin is flush both sides).
    # The station rides an offset plane whose distance is the printed
    # PinStation dimension; the Top plane pins the azimuth. Match-drilled at
    # assembly with the crankshaft, whose own hole carries the mesh clocking.
    check(
        "create_plane PinStationPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=PIN_STATION
            )
        ),
    )
    name_last_feature(adapter, "PinStationPlane")
    drive_jobs += [
        (
            name_dimensions(adapter, "PinStationPlane", ["PinStation"])[0],
            '"FaceWidth" + "BossLength" / 2',
        )
    ]
    wizard_hole_on_cylinder(
        adapter,
        PIN_HOLE_SPEC,
        [-BOSS_DIA / 2.0, 0.0, PIN_STATION],
        "retention-pin cross-hole",
        name="PinHole",
        point_planes=("PinStationPlane", "Top Plane"),
    )
    # Two boss walls = the full-cylinder cross-drill minus the bore's share.
    v_pin_hole = cross_hole_volume_mm3(PIN_DIA, BOSS_DIA) - cross_hole_volume_mm3(
        PIN_DIA, BORE_DIAMETER
    )
    volume = await volume_check(
        adapter, "retention-pin cross-hole", volume - v_pin_hole, 0.02 * v_pin_hole
    )

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND)
    )
    # No band on the blank's outside diameter: the title block's .XX general
    # grade fits inside the crossed mesh's radial room (crank_pinion_spec).
    # None on the boss either -- nothing runs on it.
    await volume_check(
        adapter, "driven crank pinion (equations neutral)", volume, 0.01 * v_bore
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Mark this part's manufacturing dimensions, author the decimal
    # places they print with (policy rule 2: the model owns both the band and
    # its spelling -- the drawing only reads them back), and stamp the
    # title-block + gear-data properties the curated drawing reads.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
