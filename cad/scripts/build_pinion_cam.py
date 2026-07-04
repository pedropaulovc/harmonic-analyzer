r"""Reproduction script: pinion lift cam (book ch. 25; 2 used, PR8).

The eccentric steel collar pinned to the lift rod at each strap station
(``page001_img01`` back-tail close-up): the strap's follower pin RESTS
ON its OD from above, so turning the lever (rod + both cams spin as
one) raises the surface under the pin and swings the drum into mesh.
Photo reads at 9.45 px/mm against the Ø6.35 rods: collar OD ~9.5, a
~Ø3.2 set-pin dome proud of the OD (locks the collar to the rod and
stops axial drift -- review item 8b), pin-on-collar tangency at park.

Eccentricity 1.0 (photo-consistent): full lift 2.0 vs the 1.08 the
4.1-deg engage swing needs (15 * tan 4.1 -- the pin rides 15 west of
the pivot), and the thin side keeps a 0.575 wall over the bore.

Layout: bore axis Z through the ORIGIN (rides the rod), authored in the
PARK pose -- collar centre at (0, -ECC), heavy side and the set-pin
boss straight DOWN, so the OD top is at its lowest (disengaged rest).
Collar z 0..9; boss along -Y at z 2.5, 2.0 proud of the OD.

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_cam.py
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
    extrude_at_offset,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "pinion-cam"
MATERIAL = "Plain Carbon Steel"  # bright steel collar (img01)

CAM_OD = 9.5  # collar OD, photo-scaled vs the Ø6.35 rod (med)
CAM_LEN = 9.0  # along the rod (med)
ECC = 1.0  # bore offset -> 2.0 full lift; 0.575 min wall over the bore
BORE = 6.35  # rides the lift rod (derived)
BOSS_DIA = 3.2  # set-pin dome, photo ~3.2 (low)
BOSS_PROUD = 2.0  # proud of the OD at the thick (down/park) side
BOSS_Z = 2.5  # boss axis station from the front face

CAM_R = CAM_OD / 2.0
BORE_R = BORE / 2.0
BOSS_R = BOSS_DIA / 2.0
# Boss tip y and an anchor INSIDE the collar at every boss radius: the collar
# surface below the centre (0, -ECC) along the boss axis plane spans
# y = -ECC - sqrt(CAM_R^2 - x^2) for |x| <= BOSS_R -- deepest -5.75, shallowest
# -ECC - sqrt(CAM_R^2 - BOSS_R^2) = -5.47.
_BOSS_TIP_Y = -(ECC + CAM_R + BOSS_PROUD)  # -7.75
_BOSS_TOP_Y = -4.0  # fully inside the collar for all |x| <= BOSS_R

V_COLLAR = math.pi * (CAM_R**2 - BORE_R**2) * CAM_LEN


def _boss_added() -> float:
    """Boss volume OUTSIDE the collar OD: Simpson over x in [-BOSS_R, BOSS_R]
    of chord(x) * (surface(x) - tip), chord = the boss disc's z-extent."""
    n = 2000
    h = 2.0 * BOSS_R / n

    def f(x: float) -> float:
        chord = 2.0 * math.sqrt(max(BOSS_R**2 - x * x, 0.0))
        surface = -(ECC + math.sqrt(max(CAM_R**2 - x * x, 0.0)))
        return chord * (surface - _BOSS_TIP_Y)

    s = f(-BOSS_R) + f(BOSS_R)
    s += 4.0 * sum(f(-BOSS_R + (2 * k - 1) * h) for k in range(1, n // 2 + 1))
    s += 2.0 * sum(f(-BOSS_R + 2 * k * h) for k in range(1, n // 2))
    return s * h / 3.0


V_BOSS = _boss_added()  # ~17.5


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "CamOd", f"{CAM_OD}mm")
    await set_global(adapter, "CamLen", f"{CAM_LEN}mm")
    await set_global(adapter, "Ecc", f"{ECC}mm")
    await set_global(adapter, "BoreDia", f"{BORE}mm")
    await set_global(adapter, "BossDia", f"{BOSS_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Collar: circle centred ECC below the bore/origin, extruded z 0..CAM_LEN.
    collar = SketchDims()
    check("create_sketch collar", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, -ECC, CAM_R, "collar", dims=collar,
        names=("CollarCx", "CollarCy", "CollarOd"),
        drives=(None, '"Ecc"', '"CamOd"'),
    )
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    drive_jobs += collar.apply(adapter, "CollarProfile")
    check(
        "extrude collar",
        await adapter.create_extrusion(ExtrusionParameters(depth=CAM_LEN)),
    )
    name_last_feature(adapter, "Collar")
    v_solid = math.pi * CAM_R**2 * CAM_LEN
    volume = await volume_check(adapter, "collar", v_solid, 0.005 * v_solid)

    # Rod bore on the origin axis (fully inside the collar: ECC + BORE_R =
    # 4.175 < CAM_R).
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_R, "bore", dims=bore,
        names=("BoreCx", "BoreCy", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.5 * CAM_LEN, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    volume = await volume_check(adapter, "bore", V_COLLAR, 0.005 * V_COLLAR)

    # Set-pin boss (item 8b): a radial stub straight DOWN the heavy side,
    # 2.0 proud of the OD -- the img01 dome. Top sketch (u, v) -> (X, -Z);
    # extruded -Y from an anchor plane fully inside the collar.
    boss = SketchDims()
    check("create_sketch boss", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, -BOSS_Z, BOSS_R, "set-pin boss", dims=boss,
        names=("BossCx", "BossCz", "BossDia"),
        drives=(None, None, '"BossDia"'),
    )
    await ensure_fully_defined(adapter, "boss sketch")
    check("exit_sketch boss", await adapter.exit_sketch())
    name_last_feature(adapter, "BossProfile")
    drive_jobs += boss.apply(adapter, "BossProfile")
    extrude_at_offset(adapter, _BOSS_TOP_Y - _BOSS_TIP_Y, _BOSS_TIP_Y)
    name_last_feature(adapter, "SetPinBoss")
    volume = await volume_check(adapter, "set-pin boss", volume + V_BOSS, 0.1 * V_BOSS)

    # Named bore axis for the rod mate (Axis1).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "cam bore axis")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven cam (equations neutral)", volume, 0.01 * V_COLLAR)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
