r"""Reproduction script: cylinder gear with integral eccentric cam (book ch. 13).

All 20 cylinder gears are identical (DIMENSIONS.md ch. 13: 120 teeth each,
derived from the k/80 gear law), so this is a single non-configured part (no
configurations). The involute tooth-gap profile reuses the cone gear's
live-validated ``CreateEquationSpline2`` technique (see ``build_cone_gear.py``)
with literal numeric expressions (document units = inches, trig in radians
inside curve expressions) -- that geometry is MESH-CRITICAL (it must conjugate
the mating gear) and is therefore kept fully literal: no equation-manager
globals, no recorded/driven sketch dims on the toothed blank or tooth-gap
sketches. The ORDINARY auxiliary features (cam disc, alignment notch, shaft
bore) DO carry self-naming + editable globals + deferred driving, like the
other parametric parts.

Features, in order:

1. Gear blank: disc at tip radius ``Ra`` (OD 2.449" = 62.2 mm), face width 3 mm,
   extruded z = 0..3 from the Front plane. The face width comes from the
   M6 axial-budget resolution (Appendix C #6): face/pitch = 0.38 measured
   on the p.22 stack macro x the 7.5 mm axial pitch.
2. One tooth gap (six equation curves: two involute flanks, base chord, two
   radial extensions, outer clearance arc) cut through, then circular-
   patterned 120x about the gear axis (reference axis Top x Right = Z).
3. Integral eccentric cam (book ch. 13, pp. 22-25): one of the 20 cams that
   convert each gear's rotation into the near-sinusoidal reciprocation of its
   connecting rod (displacement = ECCENTRICITY x sin(theta)). Disc OD 30.6 mm,
   thickness 3.5 mm (the 4.5 mm inter-face gap minus 0.5 mm air per side; the
   axial budget rides the unchanged 7.0565 channel pitch), centre offset +Y by
   the 8.64 mm eccentricity, boss-extruded z = 3..6.5 from an offset reference
   plane (cam disc centred on the bore, offset +Y by the eccentricity -- the
   lobe points +Y, the NOTCH side: the ch14 end views prove the rocker tips sit
   at the TOP of their stroke at notch-up/0-cranks, so lobe-up is the cos-mode
   home pose; the pre-ROM-fit build authored it -Y, 180 deg off). The throw is
   MEASURED from the ch14 end-view ROM fit (tip half-amplitude 9.458 mm x
   127.37/139.5); the real machine drives the rod with a CUT TEMPLATE cam (the
   p.25 teardrop outline; Michelson 1898 closing note), modeled here as the
   kinematically-equivalent circular eccentric-and-strap -- the ring centre
   follows the same simple-harmonic orbit the template was cut to produce.
   (This is the former standalone ``build_eccentric_cam.py`` / ``eccentric-cam``
   part, MHA-029, now folded into the gear -- the cam was always integral.)
4. Alignment notch: 3 mm deep saw KERF cut between two teeth (the p.23
   "notch" photo shows a thin kerf -- the real gears keep all 120 teeth, NOT
   a missing tooth). +Y (90 deg = 30*gamma) is a tooth crest at 120 T, so the
   kerf is seated in the adjacent root valley (90 deg + gamma/2); the flanking
   crests stay intact. "Notches aligned to top = cosine mode" (pp. 66-67).
   Gear face only, after the pattern so it is not replicated.
5. Plain shaft bore 3/8" through gear + cam, on the gear axis. No keyway:
   gear k turns k/80 rev per crank turn (ch. 29 gear law), so the 20 gears
   all spin at DIFFERENT speeds and cannot be keyed to a common shaft --
   they run free on a stationary arbor (DIMENSIONS.md ch. 13, "M6.2 keyway
   refutation"). The legacy keyway was fiction and was removed in M6.2.

Every feature's volume delta is asserted against an analytic expectation
(same DP 49.82 / PA 14.5 deg tooth profile as the cone set, narrower face).
The notch delta integrates the
exact involute solid-fraction over the notch window (the notch floor sits
below the base circle, so part of the window is full annulus and part is
tooth-fraction fill).

Dimensions: cad/DIMENSIONS.md "Chapter 13".

Layout: gear axis = Z through the origin, gear z = 0..3 mm, cam z = 3..6.5,
cam lobe +Y, notch +Y (lobe on the notch side).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cylinder_gear.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    SketchDims,
    _flag,
    _read_member,
    add_line_chain,
    anchor_point_to_origin,
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
    set_sketch_direct_db,
)
from _gear import build_fixed_gear, volume_check
from build_cone_gear import DP, gear_facts  # DP = train diametral_pitch (machine.yaml)

import _telemetry

PART_NAME = "cylinder-gear"
MATERIAL = "Brass"  # ch. 13 text p.22: polished brass

TEETH = 120  # DIMENSIONS.md ch13: derived from gear law k/80 (high)
FACE_WIDTH = 3.0  # DIMENSIONS.md ch13: 0.38 face/pitch x 7.5 axial pitch (scaled, med)
CAM_DIAMETER = 30.6  # DIMENSIONS.md ch13: integral cam bearing diameter; the rod ring
# bore Ø30.8 measured on the p.25 overlay (Ø29.83 at the gear-OD scale) confirms it (med)
CAM_THICKNESS = 3.5  # DIMENSIONS.md ch13: axial-budget (7.0565 channel pitch, unchanged) (med)
ECCENTRICITY = 8.64  # DIMENSIONS.md ch13: cam throw MEASURED from the ch14 end-view ROM
# fit (2026-07-02): tip half-amplitude 9.458 mm over the 20-tip least-squares cos fit at
# the channel-pitch scale, x r_pin/r_tipface = 127.37/139.5. Supersedes the scaled-0.6022
# legacy 3.06 (the lobe also flips to +Y -- see the module docstring). (med)
BORE_DIAMETER = 0.375 * IN  # 9.525 DIMENSIONS.md ch13: cam bore (legacy, med)
NOTCH_DEPTH = 3.0  # DIMENSIONS.md ch13: alignment notch depth, text p.22 (high)
# The notch is "just a slit" cut with a SAW between two teeth -- the p.23 photo
# labelled "notch" shows a thin kerf, and the real gears are NOT missing a tooth
# (all 120 stay complete). So it is a narrow saw kerf seated in the tooth VALLEY
# nearest +Y, 3 mm deep, leaving the flanking crests intact. The book gives only
# the depth; the kerf width is a slitting-saw value (low; supersedes the legacy
# 3.0 square and the interim missing-tooth slit).
NOTCH_WIDTH = 0.4  # DIMENSIONS.md ch13: alignment-notch saw-kerf width (low)
NOTCH_CLEARANCE = 1.5  # kerf overshoot past the OD so the cut always opens (geom)

BORE_RADIUS = BORE_DIAMETER / 2.0

FACTS = gear_facts(TEETH, DP)  # inches; same DP/PA as the cone set by construction
RA_MM = FACTS["Ra"] * IN  # 31.10 -- gear OD/2 = 2.449"/2 = 62.2/2 (low, ch13 scaling)
RB_MM = FACTS["Rb"] * IN
NOTCH_FLOOR = RA_MM - NOTCH_DEPTH
NOTCH_OUTER = RA_MM + NOTCH_CLEARANCE  # clearance past the OD so the cut always opens
# +Y (90 deg = 30*gamma) is a tooth CREST at 120 T, so the kerf cannot sit on
# +Y without deleting that tooth. Seat the (axis-aligned, near-vertical) kerf in
# the adjacent root valley at 90 deg + gamma/2: its centreline x is the valley
# radius projected onto X. Over the kerf's short radial span the valley is ~1.5
# deg off vertical, so a vertical slot at this x stays inside the gap (verified:
# all 120 crests remain, removed solid ~0.60 mm^2).
NOTCH_X = (NOTCH_FLOOR + RA_MM) / 2.0 * math.cos(math.pi / 2.0 + FACTS["Gamma"] / 2.0)

THROUGH_ALL = FACE_WIDTH + CAM_THICKNESS + 2.0  # bore cut depth


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
    """Solid area (mm^2) of the toothed disc inside the kerf window.

    The kerf is the vertical slot ``x in [NOTCH_X +- W/2], y in [floor, outer]``
    seated in the +Y valley; most of the window is empty gap, so the removed
    solid is small (~0.60 mm^2) -- the kerf only bites the root web, not teeth.
    """
    nx = max(2, round(NOTCH_WIDTH / step))
    ny = max(2, round((NOTCH_OUTER - NOTCH_FLOOR) / step))
    dx = NOTCH_WIDTH / nx
    dy = (NOTCH_OUTER - NOTCH_FLOOR) / ny
    hits = 0
    for i in range(nx):
        x = NOTCH_X - NOTCH_WIDTH / 2.0 + (i + 0.5) * dx
        for j in range(ny):
            y = NOTCH_FLOOR + (j + 0.5) * dy
            if is_solid(x, y):  # kerf in the +Y valley: window coords are global
                hits += 1
    return hits * dx * dy


def _ref_axis_start_mm(adapter, axis_name: str) -> list[float] | None:
    """Start point (mm) of a named reference axis via IRefAxis.GetRefAxisParams."""
    model = adapter.currentModel
    feat = _read_member(model, "FirstFeature")
    for _ in range(50000):
        if not feat:
            return None
        _flag(feat, "IFeature")
        if str(_read_member(feat, "Name")) == axis_name:
            axis = adapter._attempt(lambda f=feat: f.GetSpecificFeature2(), default=None)
            if axis is None:
                return None
            _flag(axis, "IRefAxis")
            p = adapter._attempt(lambda a=axis: a.GetRefAxisParams(), default=None)
            if p is None:
                return None
            return [float(p[0]) * 1000.0, float(p[1]) * 1000.0, float(p[2]) * 1000.0]
        feat = _read_member(feat, "GetNextFeature")
    return None


async def _name_lobe_axis(adapter) -> str:
    """Named reference axis through the eccentric cam-lobe centre (part-local
    x 0, y +ECCENTRICITY), along Z, for the motion study's cam->rod coupling.

    The Henrici cam coupling (artifact B) makes each connecting-rod ring
    (Axis1@connecting-rod) coaxial with its drive-train cylinder-gear lobe. A
    face-based concentric on this geared part is catastrophic (walking ~thousands
    of tooth faces) and the lobe face will not select through the nested,
    flexible sub. A *named* axis is fast, mirror-agnostic and selects by name --
    the same pattern the bore axis already uses. The offset-plane sign for
    "Top Plane + ECC" is verified against GetRefAxisParams (Y must land at the
    lobe side, +ECC), so a flipped SW offset convention fails loudly here rather
    than silently building a wrong-side cam axis.
    """
    axis_name = await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", ECCENTRICITY, "cam lobe axis"
    )
    start = _ref_axis_start_mm(adapter, axis_name)
    if start is None:
        raise RuntimeError(f"could not read lobe axis {axis_name} params")
    if abs(start[0]) > 0.1 or abs(start[1] - ECCENTRICITY) > 0.1:
        raise RuntimeError(
            f"lobe axis misplaced at (x={start[0]:.3f}, y={start[1]:.3f}); "
            f"expected (0, {ECCENTRICITY:.3f}) -- Top Plane offset sign flipped"
        )
    _telemetry.success(f"lobe axis {axis_name} at (x {start[0]:.3f}, y {start[1]:.3f})")
    return axis_name


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations) for the ORDINARY auxiliary features --
    # the cam disc, the alignment notch and the shaft bore. The toothed blank and
    # its 120x tooth-gap pattern are NOT exposed here: that geometry is
    # mesh-critical (it must conjugate the mating gear), so build_fixed_gear keeps
    # it literal and no sketch dim on it is recorded or driven. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads BARE
    # numbers in document units (an unsuffixed 30.6 would be read as 30.6 in).
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "CamDiameter", f"{CAM_DIAMETER}mm")
    await set_global(adapter, "CamThickness", f"{CAM_THICKNESS}mm")
    await set_global(adapter, "Eccentricity", f"{ECCENTRICITY}mm")
    await set_global(adapter, "BoreDiameter", f"{BORE_DIAMETER}mm")
    await set_global(adapter, "NotchDepth", f"{NOTCH_DEPTH}mm")
    await set_global(adapter, "NotchWidth", f"{NOTCH_WIDTH}mm")
    await set_global(adapter, "NotchClearance", f"{NOTCH_CLEARANCE}mm")

    # Drive equations for the auxiliary sketches are collected here and applied in
    # one deferred batch at the end (every target must resolve against the
    # finished model, after a rebuild).
    drive_jobs: list[tuple[str, str]] = []

    # Toothed disc (blank + gap + 120x pattern, z = 0..FACE_WIDTH); the
    # volume must reproduce the cone gear's T120 configuration. Mesh-critical
    # geometry -- left fully literal (no SketchDims, no driving).
    v_teeth = await build_fixed_gear(adapter, TEETH, FACE_WIDTH, dp=DP)
    volume = v_teeth

    # ------------------------------------------------------------------
    # Integral cam on the far gear face (z = 3..6.5), lobe +Y (notch side).
    # ------------------------------------------------------------------
    plane = check(
        "create_plane cam (Front + face width)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=FACE_WIDTH
            )
        ),
    )
    # Cam disc: ordinary auxiliary circle, centre offset +Y by the eccentricity.
    # On-axis in X (x 0 -> no X dim); the +Y offset is one centre dim (displayed
    # as the unsigned magnitude, so it drives to +"Eccentricity") plus diameter.
    check(f"create_sketch cam on {plane.name}", await adapter.create_sketch(plane.name))
    # On a custom offset plane the x=0 anchor still emits an X dim (3 dims, not
    # the 2 a Front/Top origin circle would), so the helper's recorded count
    # can't be predicted here -- name the feature but record no dims (like the
    # gooseneck sweep profile). CamDiameter/Eccentricity stay declared as knobs.
    await define_circle(adapter, 0.0, ECCENTRICITY, CAM_DIAMETER / 2.0, "cam disc")
    await ensure_fully_defined(adapter, "cam sketch")
    check("exit_sketch cam", await adapter.exit_sketch())
    name_last_feature(adapter, "CamProfile")
    check(
        "extrude cam",
        await adapter.create_extrusion(ExtrusionParameters(depth=CAM_THICKNESS)),
    )
    name_last_feature(adapter, "CamBoss")
    v_cam = math.pi * (CAM_DIAMETER / 2.0) ** 2 * CAM_THICKNESS
    volume = await volume_check(adapter, "cam boss", volume + v_cam, 0.005 * v_cam)

    # The offset plane and the extrude direction both have ambiguous signs:
    # assert the cam actually landed at z > FACE_WIDTH, on +Y.
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"cam COM check failed: {mass.error}")
    com = [float(c) for c in mass.data.center_of_mass]
    com_z = (v_teeth * FACE_WIDTH / 2.0 + v_cam * (FACE_WIDTH + CAM_THICKNESS / 2.0)) / volume
    com_y = v_cam * ECCENTRICITY / volume
    if abs(com[2] - com_z) > 0.1 or abs(com[1] - com_y) > 0.1:
        raise RuntimeError(
            f"cam misplaced: COM {com}, expected y {com_y:.3f} z {com_z:.3f} "
            "-- offset-plane side or extrude direction flipped"
        )
    _telemetry.success(f"cam placement: COM y {com[1]:.3f} z {com[2]:.3f}")

    # ------------------------------------------------------------------
    # Alignment notch at +Y (top = cosine mode): a thin saw KERF seated in
    # the tooth valley nearest +Y (between two teeth, no tooth removed --
    # p.23 "notch" photo), gear face only. The slot is axis-aligned at
    # x = NOTCH_X (the valley centreline projected onto X).
    # ------------------------------------------------------------------
    notch_dims = SketchDims()
    check("create_sketch notch", await adapter.create_sketch("Front"))
    # Inference OFF: with it on, the bottom corners snap coincident onto the
    # flank-start vertices at the base circle ~0.5 mm away (live-caught: the
    # rectangle came back 3.32 mm wide with its floor at r = Rb and the width
    # dimension silently driven).
    set_sketch_direct_db(adapter, True)
    notch = await add_line_chain(
        adapter,
        [
            (NOTCH_X - NOTCH_WIDTH / 2.0, NOTCH_FLOOR),
            (NOTCH_X + NOTCH_WIDTH / 2.0, NOTCH_FLOOR),
            (NOTCH_X + NOTCH_WIDTH / 2.0, NOTCH_OUTER),
            (NOTCH_X - NOTCH_WIDTH / 2.0, NOTCH_OUTER),
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
    # Record each manual dim into SketchDims in CREATION order (the crank-pin
    # pattern): width, then height, then the two anchor dims the general-case
    # anchor_point_to_origin emits (horizontal X, then vertical Z). The width and
    # height carry clean global knobs; the anchor position is the +Y valley
    # centreline (X) and the kerf floor (Z) -- both derived from the gear tip
    # radius / valley angle (mesh geometry), so they are NAMED for readability but
    # left UNDRIVEN (no clean editable knob; driving them off RA_MM would couple
    # the kerf placement to the meshing profile). NOTCH_OUTER - NOTCH_FLOOR
    # collapses to NOTCH_DEPTH + NOTCH_CLEARANCE (RA_MM cancels), so the height IS
    # cleanly knob-driven.
    check(
        "dimension notch width",
        await adapter.add_sketch_dimension(bottom, None, "linear", NOTCH_WIDTH),
    )
    notch_dims.record("NotchWidth", '"NotchWidth"')
    check(
        "dimension notch height",
        await adapter.add_sketch_dimension(
            right, None, "linear", NOTCH_OUTER - NOTCH_FLOOR
        ),
    )
    notch_dims.record("NotchHeight", '"NotchDepth" + "NotchClearance"')
    await anchor_point_to_origin(
        adapter, f"{bottom}.start", NOTCH_X - NOTCH_WIDTH / 2.0, NOTCH_FLOOR, "notch corner"
    )
    notch_dims.record("NotchAnchorX", None)
    notch_dims.record("NotchAnchorZ", None)
    await ensure_fully_defined(adapter, "notch sketch")
    check("exit_sketch notch", await adapter.exit_sketch())
    name_last_feature(adapter, "NotchProfile")
    drive_jobs += notch_dims.apply(adapter, "NotchProfile")
    check(
        "cut notch",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=FACE_WIDTH + 1.0)
        ),
    )
    name_last_feature(adapter, "NotchKerf")
    v_notch = notch_solid_area() * FACE_WIDTH
    # Looser band than the old square: the kerf removes only ~1.8 mm^3, so the
    # grid-integration error on notch_solid_area is relatively larger.
    volume = await volume_check(adapter, "notch", volume - v_notch, 0.06 * v_notch)

    # ------------------------------------------------------------------
    # Shaft bore through gear + cam (the bore circle is fully inside the
    # eccentric cam disc: ecc 8.64 + bore_r 4.76 = 13.40 < cam_r 15.3,
    # a 1.90 mm wall at the thin side).
    # ------------------------------------------------------------------
    # Shaft bore: ordinary on-axis circle (origin centre -> no centre dims, just
    # the diameter), driven by the BoreDiameter knob.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_RADIUS, "bore", dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDiameter"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=THROUGH_ALL)),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * BORE_RADIUS**2 * (FACE_WIDTH + CAM_THICKNESS)
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Named bore axis (gear axis = Z through the origin) for view-independent
    # assembly mate selection: the gear rides the arbor coincident axis-to-axis
    # and meshes its cone gear via a gear mate (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "bore axis")

    # Axis3: the eccentric cam-lobe centre axis (motion-study cam->rod coupling).
    await _name_lobe_axis(adapter)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move; the re-check is the proof. Only the
    # auxiliary cam/notch/bore dims are driven -- the tooth-gap geometry stays
    # literal (volume_check here is from _gear, the same one used above).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    volume = await volume_check(
        adapter, "driven cylinder gear (equations neutral)", volume, 0.01 * v_bore
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
