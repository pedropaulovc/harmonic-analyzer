r"""Reproduction script: crank pedestal (book ch. 11 / eight-views, ch30 GT).

Green CYLINDRICAL pedestal at the machine's front-right that carries the
crankshaft AND houses the cone-swing journal. The ch30 quarter views
(page003 315deg, page009 45deg) show one round green column -- elliptical
top face with a two-screw split bearing cap, domed oiler button on the
flank -- standing fully on the base; the 2026-07-02 re-anchor's "slab"
read came from the true side views, where the column hides behind a frame
column and the crank arm. The corridor math agrees with the photos: from
the cone shaft's proud front stub end (machine z -123, the GT cone_front
boss) to the 64T south face there is ~49 of depth, which a O46.2 cylinder
fills with ~2 air each side -- the slab + side-by-side pivot block never
fit that corridor and ended up off the base (front face -145 vs the base
bottom plate corner -139.7).

The cone-swing pivot nests INSIDE: a bottom-entry O26 vertical cavity
(centred on the swing axis at cone shaft station -12.25, offset
(-2.03, -1.71) from the pedestal axis in the authored-mirrored part
frame -- see the FRAME note at the literals) houses the floated
``cone-pivot-post`` journal block (O24 x 63 -- see its script), and two
straight shaft windows through the front/rear walls pass the inclined
cone shaft (12.52 deg to Z; within one 8-12 wall the drift is < 2.7, so a
straight window centred per wall contains it with ~1 air -- no angled
plane needed). The shaft's front stub emerges through the front window
and its end stands ~2.5 proud of the curved flank at the drive height:
exactly the domed boss the photos show (GT cone_front).

Dimensions: cad/DIMENSIONS.md ch. 13 "Drive-train layout" + "Drive
supports" (photo-scaled + ch30 GT triangulation).

Layout: cylinder standing on the Top plane, axis through the origin,
crank through-bore along Z at y = BORE_HEIGHT; cavity + windows at the
part-frame offsets asserted against ``cone_station(-12.25)`` by
``build_drive_train_assembly``.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pedestal.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    IN,
    SketchDims,
    apply_color,
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
    volume_check,
)

PART_NAME = "crank-pedestal"
MATERIAL = "Gray Cast Iron"  # green-painted casting like the base

PEDESTAL_DIA = 46.2  # ch13 layout: front view, 278 px / 6.02 px/mm; ch30 quarter
# views confirm a round column, and O46.2 exactly fills the stub-boss -> 64T corridor
PEDESTAL_HEIGHT = 110.0  # ch13 layout: front view top at ~110 above base top
BORE_DIA = 0.375 * IN  # 9.525: crankshaft diameter (ch. 11, legacy, med)
BORE_HEIGHT = 94.16  # ch30 GT: crank axle 144.96 machine = 94.16 above base top
# (must equal build_drive_train_assembly Y_CRANK - Y_BASE_TOP -- asserted there)

# Cone-swing journal housing. The cavity is centred on the swing axis
# (cone shaft station -12.25), OFFSET from the pedestal axis; the two shaft
# windows are straight Z tunnels, each centred on the inclined shaft's crossing
# of its wall. All five literals are asserted against the live cone-shaft line
# by build_drive_train_assembly (module-level, SolidWorks-free) -- edit there
# first, then mirror here.
#
# FRAME (M6.8 machine-chirality): these x offsets make the part CHIRAL, so --
# like summing-lever / pen-hanger -- the script is authored MIRRORED
# (MIRROR_PLANE "x0" in _transforms): part-frame x = MINUS the assembly
# script's machine-frame offset. mirror_placement then lands the authored
# geometry at the true (GT, crank at machine -X) position. z is not mirrored.
CAVITY_DIA = 26.0  # cone-pivot-post block O24 + 1 radial air
CAVITY_X = -2.03  # -(cone_station(-12.25) - placement): authored-mirrored x
CAVITY_Z = -1.71
CAVITY_HEIGHT = 65.0  # block 63 + 2 air above; bottom-entry (block stands on base)
JOURNAL_Y = 54.0  # cone drive height above base top (= post BORE_HEIGHT)
WINDOW_F_DIA = 13.5  # front-wall window: shaft crossing + ellipse 9.76 + air
WINDOW_F_X = -5.70  # authored-mirrored (machine-frame crossing +5.70)
WINDOW_R_DIA = 14.0  # rear-wall window: shaft crossing + ellipse + air
WINDOW_R_X = 2.11  # authored-mirrored (machine-frame crossing -2.11)
WINDOW_CUT = PEDESTAL_DIA / 2.0 + 2.0  # one-sided depth: clears the curved face

PEDESTAL_RADIUS = PEDESTAL_DIA / 2.0
BORE_RADIUS = BORE_DIA / 2.0


def _simpson(f, a: float, b: float, n: int = 4000) -> float:
    h = (b - a) / n
    s = f(a) + f(b) + 4.0 * sum(f(a + (2 * k - 1) * h) for k in range(1, n // 2 + 1))
    s += 2.0 * sum(f(a + 2 * k * h) for k in range(1, n // 2))
    return s * h / 3.0


def _bore_removed() -> float:
    """Material removed by the crank through-bore: a z-cylinder r=BORE_RADIUS
    crossing the O46.2 column -- z-chord 2*sqrt(R^2-x^2) integrated over the
    bore disc (the bore sits at y 94.16, clear of every other cut)."""
    R, r = PEDESTAL_RADIUS, BORE_RADIUS
    return _simpson(
        lambda x: 2.0 * math.sqrt(max(R * R - x * x, 0.0))
        * 2.0 * math.sqrt(max(r * r - x * x, 0.0)),
        -r, r,
    )


def _window_removed(wx: float, w_dia: float, front: bool) -> float:
    """Material removed by one one-sided window tunnel (z in (-cut,0] for the
    front, [0,+cut) for the rear): per x, the outer chord half on that side
    minus what the cavity already removed there, integrated over the window
    disc (its y band, 54 +/- r, meets no other feature)."""
    R = PEDESTAL_RADIUS
    r = w_dia / 2.0
    q_c = lambda x: math.sqrt(max(CAVITY_DIA**2 / 4.0 - (x - CAVITY_X) ** 2, 0.0))

    def depth(x: float) -> float:
        half = math.sqrt(max(R * R - x * x, 0.0))
        lo, hi = (-half, 0.0) if front else (0.0, half)
        c_lo, c_hi = CAVITY_Z - q_c(x), CAVITY_Z + q_c(x)
        overlap = max(0.0, min(hi, c_hi) - max(lo, c_lo))
        return (hi - lo) - overlap

    return _simpson(
        lambda x: 2.0 * math.sqrt(max(r * r - (x - wx) ** 2, 0.0)) * depth(x),
        wx - r, wx + r,
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 46 = 46 in, blowing the part up 25.4x).
    # Heights/depths are feature parameters (not sketch dims), so nothing
    # drives them; exposing them is still a useful knob per the exemplars.
    await set_global(adapter, "PedestalDia", f"{PEDESTAL_DIA}mm")
    await set_global(adapter, "PedestalHeight", f"{PEDESTAL_HEIGHT}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")
    await set_global(adapter, "CavityDia", f"{CAVITY_DIA}mm")
    # Negative sketch coordinates: each dim displays the magnitude, so the
    # global holds the magnitude and the drive negates nothing
    # (build_harmonic_base _pos_drive rationale).
    await set_global(adapter, "CavityXMag", f"{-CAVITY_X}mm")
    # Top-plane sketch Y is model -Z (see build_harmonic_base HOLE_XZ): the
    # global holds the SKETCH value so the drive equation stays sign-clean.
    await set_global(adapter, "CavityZSk", f"{-CAVITY_Z}mm")
    await set_global(adapter, "JournalY", f"{JOURNAL_Y}mm")
    await set_global(adapter, "WindowFDia", f"{WINDOW_F_DIA}mm")
    await set_global(adapter, "WindowFXMag", f"{-WINDOW_F_X}mm")
    await set_global(adapter, "WindowRDia", f"{WINDOW_R_DIA}mm")
    await set_global(adapter, "WindowRX", f"{WINDOW_R_X}mm")

    # Each sketch records its dim names + drive equations inline; the deferred
    # drive batch at the end runs once the whole model + a rebuild exists.
    drive_jobs: list[tuple[str, str]] = []

    # Origin-centred column. Origin circle: only the diameter is a dim.
    pedestal = SketchDims()
    check("create_sketch pedestal", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, PEDESTAL_RADIUS, "pedestal circle", dims=pedestal,
        names=("PedestalCx", "PedestalCz", "PedestalDia"),
        drives=(None, None, '"PedestalDia"'),
    )
    await ensure_fully_defined(adapter, "pedestal sketch")
    check("exit_sketch pedestal", await adapter.exit_sketch())
    name_last_feature(adapter, "PedestalProfile")
    drive_jobs += pedestal.apply(adapter, "PedestalProfile")
    check(
        "extrude pedestal",
        await adapter.create_extrusion(ExtrusionParameters(depth=PEDESTAL_HEIGHT)),
    )
    name_last_feature(adapter, "Pedestal")
    v_cyl = math.pi * PEDESTAL_RADIUS**2 * PEDESTAL_HEIGHT
    volume = await volume_check(adapter, "pedestal cylinder", v_cyl, 0.005 * v_cyl)

    # Crankshaft bore along Z at the drive height (Front-plane sketch,
    # symmetric cut clears the full column). On-axis in X (x 0), so
    # define_circle emits only the Z centre dim + the diameter.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_HEIGHT, BORE_RADIUS, "bore", dims=bore,
        names=("BoreCx", "BoreHeight", "BoreDia"),
        drives=(None, '"BoreHeight"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PEDESTAL_DIA + 4.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    v_bore = _bore_removed()
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Swing-journal cavity: bottom-entry O26 vertical pocket centred on the
    # swing axis (offset from the pedestal axis), housing the floated
    # cone-pivot-post block. Blind up from the foot; the foot becomes an
    # annulus and the block stands on the BASE through the opening.
    cavity = SketchDims()
    check("create_sketch cavity", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, CAVITY_X, -CAVITY_Z, CAVITY_DIA / 2.0, "cavity", dims=cavity,
        names=("CavityCx", "CavityCz", "CavityDia"),
        drives=('"CavityXMag"', '"CavityZSk"', '"CavityDia"'),
    )
    await ensure_fully_defined(adapter, "cavity sketch")
    check("exit_sketch cavity", await adapter.exit_sketch())
    name_last_feature(adapter, "CavityProfile")
    drive_jobs += cavity.apply(adapter, "CavityProfile")
    check(
        "cut cavity",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=CAVITY_HEIGHT)),
    )
    name_last_feature(adapter, "Cavity")
    v_cavity = math.pi * (CAVITY_DIA / 2.0) ** 2 * CAVITY_HEIGHT
    volume = await volume_check(adapter, "cavity", volume - v_cavity, 0.01 * v_cavity)

    # Front shaft window: straight -Z tunnel through the front wall, centred on
    # the inclined shaft's front-wall crossing. CUT direction convention
    # (empirical, 2026-07-02): a cut-extrude defaults to the -sketch-normal
    # side (-Z on a Front sketch) when material lies on both sides;
    # ``reverse_direction=True`` flips to +Z. (The nameplate exemplar is a
    # BOSS, which defaults the other way -- +normal.) Proof: with the flags
    # swapped, this window's volume check missed by +489.5 mm^3 = the
    # cavity-overlap difference 3.42 mm x the window disc area between the
    # two walls.
    win_f = SketchDims()
    check("create_sketch window front", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, WINDOW_F_X, JOURNAL_Y, WINDOW_F_DIA / 2.0, "front window",
        dims=win_f,
        names=("WindowFCx", "WindowFCy", "WindowFDia"),
        drives=('"WindowFXMag"', '"JournalY"', '"WindowFDia"'),
    )
    await ensure_fully_defined(adapter, "front window sketch")
    check("exit_sketch window front", await adapter.exit_sketch())
    name_last_feature(adapter, "WindowFrontProfile")
    drive_jobs += win_f.apply(adapter, "WindowFrontProfile")
    check(
        "cut window front",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=WINDOW_CUT)),
    )
    name_last_feature(adapter, "WindowFront")
    v_wf = _window_removed(WINDOW_F_X, WINDOW_F_DIA, front=True)
    volume = await volume_check(adapter, "front window", volume - v_wf, 0.03 * v_wf)

    # Rear shaft window: straight +Z tunnel through the rear wall (+Z needs
    # the flip -- see the front-window direction note).
    win_r = SketchDims()
    check("create_sketch window rear", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, WINDOW_R_X, JOURNAL_Y, WINDOW_R_DIA / 2.0, "rear window",
        dims=win_r,
        names=("WindowRCx", "WindowRCy", "WindowRDia"),
        drives=('"WindowRX"', '"JournalY"', '"WindowRDia"'),
    )
    await ensure_fully_defined(adapter, "rear window sketch")
    check("exit_sketch window rear", await adapter.exit_sketch())
    name_last_feature(adapter, "WindowRearProfile")
    drive_jobs += win_r.apply(adapter, "WindowRearProfile")
    check(
        "cut window rear",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=WINDOW_CUT, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "WindowRear")
    v_wr = _window_removed(WINDOW_R_X, WINDOW_R_DIA, front=False)
    volume = await volume_check(adapter, "rear window", volume - v_wr, 0.03 * v_wr)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pedestal (equations neutral)", volume, 0.03 * v_wr
    )

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", BORE_HEIGHT, "Right Plane", 0.0, "bore axis")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
