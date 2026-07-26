r"""Reproduction script: crank pinion (book ch. 11/12, pp. 16, 20).

The pinion on the crankshaft that meshes the dark steel crank-drive gear
at the cone set's large end (`build_crank_drive_gear.py`), implementing
the book-stated 4:1 crank-to-cone reduction (p. 16). Tooth count/DP per
the Appendix C #9 split, with DP 25.7311 fixed by the manually
rederived v2 post's cast-in crank axis. A plain straight spur
with a root-relieved floor; the crossed-mesh accommodation lives on the
64T (see its docstring for the full rederivation).

Dimensions: cad/config/dimensions.yaml ch12 crank-drive gear row +
Appendix C #9. Face slightly wider than the drive gear's (meshing-pair
practice, axial alignment slack).

Layout: gear axis = Z through the origin, disc z = 0..12 mm.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pinion.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    IN,
    SketchDims,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _gear import build_fixed_gear, volume_check
from crank_pinion_spec import DRAWING_DIMENSIONS, DRAWING_NOTES, GEAR_DATA

PART_NAME = "crank-pinion"
MATERIAL = "Plain Carbon Steel"  # steel like its mate (p.19/20)

TEETH = 16  # DIMENSIONS.md ch12 / Appendix C #9 estimate (low)
DP = _config.machine("gear_train", "crank_drive_diametral_pitch")  # cad/config/machine.yaml (low)
PA_DEG = 14.5
FACE_WIDTH = 10.8  # mm: spans the 64T row north of the v2 crank boss.
# (The old 12.0 "slightly wider than the drive gear's 10" was a low-
# confidence read; 11.0 fit the line-of-centres overhang model but grazed
# the true rim minimum at the tight 2026-07-14 fit.)
# = build_drive_train_assembly PINION_FACE.
BORE_DIAMETER = 0.375 * IN  # 9.525 -- crankshaft dia (med)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): face width and bore diameter carry the
    # load-bearing mm suffix (INCH document; the equation manager reads bare
    # numbers in document units, so an unsuffixed length blows the part up 25.4x).
    # FaceWidth is the cut-bore depth knob (a feature parameter, not a driven
    # sketch dim). TEETH/DP stay module constants -- the gear blank/gap/pattern is
    # built by build_fixed_gear with literal numerics, off this self-naming path.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")

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

    # On-axis bore (centre 0,0): define_circle emits only the diameter dim, so
    # only the "Dia" slot is recorded -- the X/Z names are ignored.
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
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 2.0)),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * (BORE_DIAMETER / 2.0) ** 2 * FACE_WIDTH
    await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "bore axis")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven crank pinion (equations neutral)", volume - v_bore, 0.01 * v_bore
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Mark the bore as the single manufacturing model dimension and stamp the
    # title-block + gear-data properties the curated drawing reads.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
