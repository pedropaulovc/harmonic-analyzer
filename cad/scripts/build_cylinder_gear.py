r"""Reproduction script: cylinder gear with integral eccentric cam (book ch. 13).

All 20 cylinder gears are identical (DIMENSIONS.md ch. 13: 120 teeth each,
derived from the k/80 gear law), so this is a single non-configured part --
no equation-manager globals or configurations; the involute tooth-gap profile
reuses the cone gear's live-validated ``CreateEquationSpline2`` technique
(see ``build_cone_gear.py``) with literal numeric expressions (document
units = inches, trig in radians inside curve expressions).

Features, in order:

1. Gear blank: disc at tip radius ``Ra`` (OD 4.067"), face width 3 mm,
   extruded z = 0..3 from the Front plane. The face width comes from the
   M6 axial-budget resolution (Appendix C #6): face/pitch = 0.38 measured
   on the p.22 stack macro x the 7.5 mm axial pitch.
2. One tooth gap (six equation curves: two involute flanks, base chord, two
   radial extensions, outer clearance arc) cut through, then circular-
   patterned 120x about the gear axis (reference axis Top x Right = Z).
3. Integral eccentric cam: disc OD 2.0", thickness 3.5 mm (the 4.5 mm
   inter-face gap minus 0.5 mm air per side; supersedes the legacy 0.4"
   which alone exceeded the 7.5 mm pitch), centre offset -Y by the 0.2"
   eccentricity, boss-extruded z = 3..6.5 from an offset reference
   plane (the cam shares the layout of the superseded standalone
   ``build_eccentric_cam.py``: lobe -Y, keyway +Y).
4. Alignment notch: 3 mm deep square notch (width estimated = depth) cut
   into the gear rim at +Y ("notches aligned to top = cosine mode",
   pp. 66-67) -- gear face only, after the pattern so it is not replicated.
5. Shaft bore 3/8" through gear + cam, on the gear axis.
6. Keyway 1/8" x 0.06" past the bore, pointing +Y (away from the cam lobe).

Every feature's volume delta is asserted against an analytic expectation
(same DP 30 / PA 14.5 deg tooth profile as the cone set, narrower face).
The notch delta integrates the
exact involute solid-fraction over the notch window (the notch floor sits
below the base circle, so part of the window is full annulus and part is
tooth-fraction fill).

Dimensions: cad/DIMENSIONS.md "Chapter 13".

Layout: gear axis = Z through the origin, gear z = 0..3 mm, cam z = 3..6.5,
cam lobe -Y, notch and keyway +Y.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_cylinder_gear.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)
from _gear import build_fixed_gear, volume_check
from build_cone_gear import gear_facts

PART_NAME = "cylinder-gear"
MATERIAL = "Brass"  # ch. 13 text p.22: polished brass

TEETH = 120  # DIMENSIONS.md ch13: derived from gear law k/80 (high)
FACE_WIDTH = 3.0  # DIMENSIONS.md ch13: 0.38 face/pitch x 7.5 axial pitch (scaled, med)
CAM_DIAMETER = 2.0 * IN  # 50.8  DIMENSIONS.md ch13: integral cam diameter (legacy, med)
CAM_THICKNESS = 3.5  # DIMENSIONS.md ch13: axial-budget resolution, Appendix C #6 (derived, med)
ECCENTRICITY = 0.2 * IN  # 5.08  DIMENSIONS.md ch13: cam eccentricity (legacy, med)
BORE_DIAMETER = 0.375 * IN  # 9.525 DIMENSIONS.md ch13: cam bore (legacy, med)
KEYWAY_WIDTH = 0.125 * IN  # 3.175 DIMENSIONS.md ch13: keyway width (legacy, med)
KEYWAY_DEPTH = 0.06 * IN  # 1.524 DIMENSIONS.md ch13: keyway depth past bore (legacy, med)
NOTCH_DEPTH = 3.0  # DIMENSIONS.md ch13: alignment notch depth, text p.22 (high)
NOTCH_WIDTH = 3.0  # DIMENSIONS.md ch13: square notch, width estimated = depth (low)

BORE_RADIUS = BORE_DIAMETER / 2.0
KEYWAY_TOP_Y = BORE_RADIUS + KEYWAY_DEPTH
KEYWAY_BOTTOM_Y = BORE_RADIUS / 2.0  # inside the bore; exact value immaterial
KEYWAY_HALF_WIDTH = KEYWAY_WIDTH / 2.0

FACTS = gear_facts(TEETH)  # inches; same DP/PA as the cone set by construction
RA_MM = FACTS["Ra"] * IN  # 51.6467 -- gear OD/2 = 4.067"/2 (high)
RB_MM = FACTS["Rb"] * IN
NOTCH_FLOOR = RA_MM - NOTCH_DEPTH
NOTCH_OUTER = RA_MM + 1.5  # clearance past the OD so the cut always opens

THROUGH_ALL = FACE_WIDTH + CAM_THICKNESS + 2.0  # bore/keyway cut depth


def is_solid(x: float, y: float) -> bool:
    """Exact solid test for the toothed disc cross-section at (x, y) in mm.

    Mirrors the modeled cut: gap floor is the base-circle CHORD (between the
    two flank starts), flanks are the involute from ``Delta``/``Gamma-Delta``
    (see build_cone_gear's profile derivation).
    """
    r = math.hypot(x, y)
    if r > RA_MM:
        return False
    gamma, delta = FACTS["Gamma"], FACTS["Delta"]
    psi = math.atan2(y, x) % gamma
    if r >= RB_MM:
        t = math.sqrt((r / RB_MM) ** 2 - 1.0)
        inv = t - math.atan(t)
        return not (delta - inv < psi < gamma - delta + inv)
    if not (delta < psi < gamma - delta):
        return True
    r_chord = RB_MM * math.cos((gamma - 2.0 * delta) / 2.0) / math.cos(psi - gamma / 2.0)
    return r <= r_chord


def notch_solid_area(step: float = 0.004) -> float:
    """Solid area (mm^2) of the toothed disc inside the notch window."""
    nx = max(2, round(NOTCH_WIDTH / step))
    ny = max(2, round((NOTCH_OUTER - NOTCH_FLOOR) / step))
    dx = NOTCH_WIDTH / nx
    dy = (NOTCH_OUTER - NOTCH_FLOOR) / ny
    hits = 0
    for i in range(nx):
        x = -NOTCH_WIDTH / 2.0 + (i + 0.5) * dx
        for j in range(ny):
            y = NOTCH_FLOOR + (j + 0.5) * dy
            if is_solid(x, y):  # notch at +Y: window coords are (x, y) global
                hits += 1
    return hits * dx * dy


def keyway_area_outside_bore() -> float:
    """Keyway rectangle area (mm^2) outside the bore circle (midpoint rule).

    The rectangle bottom (``BORE_RADIUS/2``) is fully inside the bore for
    ``|x| <= KEYWAY_HALF_WIDTH``, so the boundary is the circle itself.
    """
    n = 4000
    dx = KEYWAY_WIDTH / n
    area = 0.0
    for i in range(n):
        x = -KEYWAY_HALF_WIDTH + (i + 0.5) * dx
        area += (KEYWAY_TOP_Y - math.sqrt(BORE_RADIUS**2 - x * x)) * dx
    return area


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Toothed disc (blank + gap + 120x pattern, z = 0..FACE_WIDTH); the
    # volume must reproduce the cone gear's T120 configuration.
    v_teeth = await build_fixed_gear(adapter, TEETH, FACE_WIDTH)
    volume = v_teeth

    # ------------------------------------------------------------------
    # Integral cam on the far gear face (z = 7..17.16), lobe -Y.
    # ------------------------------------------------------------------
    plane = check(
        "create_plane cam (Front + face width)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=FACE_WIDTH
            )
        ),
    )
    check(f"create_sketch cam on {plane.name}", await adapter.create_sketch(plane.name))
    await define_circle(adapter, 0.0, -ECCENTRICITY, CAM_DIAMETER / 2.0, "cam disc")
    await ensure_fully_defined(adapter, "cam sketch")
    check("exit_sketch cam", await adapter.exit_sketch())
    check(
        "extrude cam",
        await adapter.create_extrusion(ExtrusionParameters(depth=CAM_THICKNESS)),
    )
    v_cam = math.pi * (CAM_DIAMETER / 2.0) ** 2 * CAM_THICKNESS
    volume = await volume_check(adapter, "cam boss", volume + v_cam, 0.005 * v_cam)

    # The offset plane and the extrude direction both have ambiguous signs:
    # assert the cam actually landed at z > FACE_WIDTH, on -Y.
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"cam COM check failed: {mass.error}")
    com = [float(c) for c in mass.data.center_of_mass]
    com_z = (v_teeth * FACE_WIDTH / 2.0 + v_cam * (FACE_WIDTH + CAM_THICKNESS / 2.0)) / volume
    com_y = v_cam * -ECCENTRICITY / volume
    if abs(com[2] - com_z) > 0.1 or abs(com[1] - com_y) > 0.1:
        raise RuntimeError(
            f"cam misplaced: COM {com}, expected y {com_y:.3f} z {com_z:.3f} "
            "-- offset-plane side or extrude direction flipped"
        )
    print(f"  OK  cam placement: COM y {com[1]:.3f} z {com[2]:.3f}")

    # ------------------------------------------------------------------
    # Alignment notch at +Y (top = cosine mode), gear face only.
    # ------------------------------------------------------------------
    check("create_sketch notch", await adapter.create_sketch("Front"))
    # Inference OFF: with it on, the bottom corners snap coincident onto the
    # flank-start vertices at the base circle ~0.5 mm away (live-caught: the
    # rectangle came back 3.32 mm wide with its floor at r = Rb and the width
    # dimension silently driven).
    set_sketch_direct_db(adapter, True)
    notch = await add_line_chain(
        adapter,
        [
            (-NOTCH_WIDTH / 2.0, NOTCH_FLOOR),
            (NOTCH_WIDTH / 2.0, NOTCH_FLOOR),
            (NOTCH_WIDTH / 2.0, NOTCH_OUTER),
            (-NOTCH_WIDTH / 2.0, NOTCH_OUTER),
        ],
    )
    set_sketch_direct_db(adapter, False)
    bottom, right, top, left = notch
    for ent, relation in (
        (bottom, "horizontal"),
        (top, "horizontal"),
        (right, "vertical"),
        (left, "vertical"),
    ):
        check(f"notch {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check(
        "dimension notch width",
        await adapter.add_sketch_dimension(bottom, None, "linear", NOTCH_WIDTH),
    )
    check(
        "dimension notch height",
        await adapter.add_sketch_dimension(
            right, None, "linear", NOTCH_OUTER - NOTCH_FLOOR
        ),
    )
    await ensure_fully_defined(adapter, "notch sketch", fix_entities=notch)
    check("exit_sketch notch", await adapter.exit_sketch())
    check(
        "cut notch",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=FACE_WIDTH + 1.0)
        ),
    )
    v_notch = notch_solid_area() * FACE_WIDTH
    volume = await volume_check(adapter, "notch", volume - v_notch, 0.03 * v_notch)

    # ------------------------------------------------------------------
    # Shaft bore through gear + cam (the bore circle is fully inside the
    # eccentric cam disc: 5.08 + 4.76 < 25.4).
    # ------------------------------------------------------------------
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, BORE_RADIUS, "bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=THROUGH_ALL)),
    )
    v_bore = math.pi * BORE_RADIUS**2 * (FACE_WIDTH + CAM_THICKNESS)
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # ------------------------------------------------------------------
    # Keyway pointing +Y, through gear + cam (eccentric-cam recipe).
    # ------------------------------------------------------------------
    check("create_sketch keyway", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)  # same snap risk against the bore edge
    keyway = await add_line_chain(
        adapter,
        [
            (-KEYWAY_HALF_WIDTH, KEYWAY_BOTTOM_Y),
            (KEYWAY_HALF_WIDTH, KEYWAY_BOTTOM_Y),
            (KEYWAY_HALF_WIDTH, KEYWAY_TOP_Y),
            (-KEYWAY_HALF_WIDTH, KEYWAY_TOP_Y),
        ],
    )
    set_sketch_direct_db(adapter, False)
    bottom, right, top, left = keyway
    for ent, relation in (
        (bottom, "horizontal"),
        (top, "horizontal"),
        (right, "vertical"),
        (left, "vertical"),
    ):
        check(f"keyway {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check(
        "dimension keyway width",
        await adapter.add_sketch_dimension(bottom, None, "linear", KEYWAY_WIDTH),
    )
    check(
        "dimension keyway height",
        await adapter.add_sketch_dimension(
            right, None, "linear", KEYWAY_TOP_Y - KEYWAY_BOTTOM_Y
        ),
    )
    await ensure_fully_defined(adapter, "keyway sketch", fix_entities=keyway)
    check("exit_sketch keyway", await adapter.exit_sketch())
    check(
        "cut keyway",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=THROUGH_ALL)),
    )
    v_key = keyway_area_outside_bore() * (FACE_WIDTH + CAM_THICKNESS)
    await volume_check(adapter, "keyway", volume - v_key, 0.02 * v_key)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
