"""Placement math + STL bbox: Euler/rotation conversion, mirror transforms
and the cached STL bounding-box reader. Split out of _common so assembly
placement math can change without invalidating any part build.
"""
from __future__ import annotations

import math
import struct

from _common import OUT_STL

_STL_BBOX_CACHE: dict[str, tuple[tuple[float, float], ...]] = {}

def stl_bbox_mm(stem: str) -> tuple[tuple[float, float], ...]:
    """((xmin, xmax), (ymin, ymax), (zmin, zmax)) of ``out/stl/<stem>.STL``
    in mm, part-local frame (export_models.py writes binary STLs in
    millimetres, untranslated)."""
    cached = _STL_BBOX_CACHE.get(stem)
    if cached is not None:
        return cached
    path = OUT_STL / f"{stem}.STL"
    data = path.read_bytes()
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    count = struct.unpack_from("<I", data, 80)[0] if len(data) >= 84 else -1
    if count >= 0 and len(data) >= 84 + 50 * count:
        for rec in struct.iter_unpack("<12fH", data[84 : 84 + 50 * count]):
            for base in (3, 6, 9):  # skip the facet normal
                for k in range(3):
                    v = rec[base + k]
                    if v < lo[k]:
                        lo[k] = v
                    if v > hi[k]:
                        hi[k] = v
    elif data[:5].lower() == b"solid":  # ASCII STL
        for line in data.decode("ascii", "ignore").splitlines():
            parts = line.split()
            if len(parts) == 4 and parts[0] == "vertex":
                for k in range(3):
                    v = float(parts[k + 1])
                    if v < lo[k]:
                        lo[k] = v
                    if v > hi[k]:
                        hi[k] = v
    else:
        raise RuntimeError(f"{path.name}: not a parsable STL ({count} facets?)")
    if not all(math.isfinite(v) for v in (*lo, *hi)):
        raise RuntimeError(f"{path.name}: no vertices found")
    bbox = tuple((lo[k], hi[k]) for k in range(3))  # STL already in mm
    # Unit guard: export_models writes mm STLs and stl_bbox_mm consumes them as
    # mm. A stale metres-unit cache (pre the 2026-06 mm normalization, which
    # dropped the *1000 here) yields a ~1000x-too-small bbox, which silently
    # mis-mirrors STL-bbox-mirrored parts -- platen-rack's z-centre read 0.003
    # instead of ~3 mm, shifting it ~6 mm into its neighbours. No real machine
    # part spans under a millimetre, so fail loud and force a cache rebuild
    # rather than place parts a few mm off.
    span = max(hi[k] - lo[k] for k in range(3))
    if span < 1.0:
        raise RuntimeError(
            f"{path.name}: bbox span {span:.4f} mm is implausibly small -- "
            "stale metres-unit STL cache? regenerate with "
            "`export_models.py --force`")
    _STL_BBOX_CACHE[stem] = bbox
    return bbox

def rows_from_euler(rotation_deg: list[float]) -> list[list[float]]:
    """Transform2 rotation rows for adapter euler angles (applied Rx, Ry, Rz
    to row vectors -- the convention assert_component_placed reads back)."""
    a, b, g = (math.radians(v) for v in rotation_deg)
    ca, sa, cb, sb, cg, sg = (
        math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(g), math.sin(g),
    )
    return [
        [cb * cg, cb * sg, -sb],
        [sa * sb * cg - ca * sg, sa * sb * sg + ca * cg, sa * cb],
        [ca * sb * cg + sa * sg, ca * sb * sg - sa * cg, ca * cb],
    ]

# Common component-placement rotation rows (Transform2 convention): IDENTITY plus
# the right-angle turns the assembly scripts reach for. They match rows_from_euler
# at the same angles; ``rot_z_rows`` builds an arbitrary spin about Z.
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
ROT_X_POS90 = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
ROT_X_NEG90 = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]


def rot_z_rows(deg: float) -> list[list[float]]:
    """Transform2 rotation rows for a spin of ``deg`` about the local Z axis."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]

def euler_from_rows(rows: list[list[float]]) -> list[float]:
    """Inverse of rows_from_euler (degrees). At the b = +/-90 gimbal lock the
    g = 0 representative is returned."""
    sb = max(-1.0, min(1.0, -rows[0][2]))
    b = math.asin(sb)
    if abs(sb) > 1.0 - 1e-9:
        # row1 collapses to [sin(a -+ g), cos(a -+ g), 0]; pick g = 0.
        a = math.atan2(rows[1][0] * (1.0 if sb > 0 else -1.0), rows[1][1])
        return [math.degrees(a), math.degrees(b), 0.0]
    a = math.atan2(rows[1][2], rows[2][2])
    g = math.atan2(rows[0][1], rows[0][0])
    return [math.degrees(a), math.degrees(b), math.degrees(g)]

def _mirror_xform(
    position: list[float], rows: list[list[float]], axis: int, c: float
) -> tuple[list[float], list[list[float]]]:
    """Reflect a placement about the machine YZ plane, realising the result
    as a proper transform via the part-local mirror plane ``axis``-coord = c:
    pos' = mirror_x(pos + 2c * rows[axis]), rows' = (I - 2 e e^T) R Mx."""
    shifted = [position[k] + 2.0 * c * rows[axis][k] for k in range(3)]
    pos2 = [-shifted[0], shifted[1], shifted[2]]
    rows2 = [
        [rows[i][j] * (-1.0 if (i == axis) != (j == 0) else 1.0) for j in range(3)]
        for i in range(3)
    ]
    return pos2, rows2

# Machine-chirality mirror (M6.8). The original assembly was built as the
# mirror image of the real machine (crank at +X with the paper facing -Z;
# every ch. 30 plate and the Altgeld Hall photogrammetry put the crank at the
# viewer's RIGHT when facing the paper, i.e. machine -X). The fix reflects
# every component placement about the machine YZ plane (x -> -x) at the
# `_place()` boundary of each subassembly script, leaving all derivation
# math, solvers and checker-arbitrated slacks untouched.
#
# A reflection is not a rigid placement, so each mirrored placement is
# realised as M(T(part)) = (M o T o S)(part), valid only when S(part) == part
# for a part-local mirror symmetry S. MIRROR_PLANE declares S per part:
#
#   'x'  -- local YZ plane through the part STL bbox x-centre (default:
#           solids of revolution, x-symmetric castings, even-tooth gears
#           seeded with a tooth on local +X);
#   'z'  -- local XY plane through the bbox z-centre (flat or planar-XY
#           x-asymmetric linkages and wire forms; helix springs flip hand,
#           which is sub-visible at render scale);
#   'x0' -- local x = 0 exactly (parts whose build script is itself
#           mirrored as part of M6.8: summing-lever, magnifying-bracket,
#           pen-hanger);
#   ('x'|'z', c) -- explicit plane coordinate in mm, bypassing the STL
#           bbox (amplitude-bar: modeled cornered at origin, exactly
#           x-symmetric about BAR_WIDTH/2; its on-disk STL was a legacy
#           inch-unit export).
#
# Cosmetic asymmetries knowingly mirrored: measuring-stick engraved scale
# reads right-to-left (0.4 mm ticks), crank-arm fiducial dimple swaps face.
# Correctness is arbitrated downstream by assert_component_placed readback,
# the zero-interference gate, the analytic spring/rack/clearance gates and
# the photo comparison renders.
# ---------------------------------------------------------------------------
#
# Lives here (not _common): MIRROR_PLANE is read only by mirror_placement below
# and the channel-assembly stretched-spring loop -- never by a part build. Keep
# it off _common so it stays off every part's input hash; a placement-only edit
# then re-keys the assemblies (which import _transforms), not all ~70 parts.
MIRROR_PLANE: dict[str, str | tuple[str, float]] = {
    # channel
    "amplitude-bar": ("x", 3.175),
    "rocker-arm": "z",
    "connecting-rod": "z",
    "channel-lever": "z",
    "channel-spring-installed": "z",
    # drive train
    "crank-arm": "z",
    "crank-handle": "z",
    "transgear-latch": "z",
    # odd sprocket teeth break the 'x' tooth-pattern closure; the hub is
    # z-symmetric about the bbox centre (mesh resid 0.000)
    "chain-sprocket": "z",
    # output
    "boss-hook": "z",
    # spring-hook: the little channel plate hook, the boss-hook idiom one size
    # down. A planar wire in its local X-Y plane (achiral about local z=0), so
    # like the channel spring it engages it must take the SAME z-mirror -- the
    # default "x" would X-flip the chiral hook to the wrong side of the eye with
    # its arm reversed (it must mirror identically to channel-spring-installed).
    "spring-hook": ("z", 0.0),
    "counter-spring": "z",
    "gooseneck": "z",
    # gooseneck-clamp: default 'x' (block/bore/screw-head all x-centred);
    # 'z' was invalid -- the screw head sits one-sided at local z 12..18
    # (M6.8 rebuild: 2280 mm^3 clamp-vs-gooseneck interference)
    # pinion-bar / platen-rack: stub bore and tooth grid are NOT centred
    # in the bbox x-span, but both parts are exact z-extrusions
    "pinion-bar": "z",
    "platen-rack": "z",
    "magnifying-lever": "z",
    "magnifying-clamp": "z",
    "thumb-screw": "z",
    "magnifying-vertical-rod": "z",
    "pen-v-block": "z",
    "pen-frame": "z",
    "pen-set-screw": "z",
    "column-clamp": "z",
    # plain x-symmetric slab cornered at origin; explicit c avoids the
    # STL-bbox dependency for a part newer than the legacy export set
    "platen-paper": ("x", 129.75),
    # roller-chain links: flat XY parts, exactly symmetric about local z=0
    # (plates at +-plate_z, round bodies centred on z=0); achiral, so the
    # YZ-mirror is a proper rotation. Explicit c, no STL at first build.
    "chain-inner-link": ("z", 0.0),
    "chain-outer-link": ("z", 0.0),
    # centred symmetric bar; explicit c, no STL yet at first build
    "wheel-bar": ("x", 0.0),
    # knife bearing support: X-symmetric (bore + block centred on x0); explicit
    # so placement never depends on a stale/absent STL bbox (it mirrors with the
    # summing lever so the bore stays around the hex trunnion).
    "knife-mount": ("x", 0.0),
    # parts whose build scripts are themselves mirrored (M6.8)
    "summing-lever": "x0",
    "magnifying-bracket": "x0",
    "pen-hanger": "x0",
    # (crank-pedestal's "x0" entry died with the part: the merged
    # cone-pivot-post column absorbed it, 2026-07-03. The column's oblique
    # crank bore makes it chiral, but it stays on the default bbox-"x" path --
    # the bore's authored side is pinned empirically by the assembly's
    # crank-axis agreement asserts, not by the mirror entry.)
    # cone-swing-platform went chiral with the one-sided lock lobe + slot
    # (PR2, 2026-07-03), so its script is authored mirrored like the above
    # ("x0" keeps the placement off the STL bbox, whose centre the lobe
    # shifted 13.75 mm -- the default 'x' landed the plate 26.85 mm off)
    "cone-swing-platform": "x0",
    # rocker-arm-support (the unified support casting) is authored machine-handed
    # and lives in the non-mirroring frame.SLDASM -> NO mirror entry (it replaced
    # the old split rocker-arm-support + a-frame "x0" pair, 2026-06-19).
    # ch25 alignment-pinion set (restored 2026-07-02): every part exactly
    # symmetric about its local x = 0 plane (gear/rod axes, strap/block
    # mid-planes); explicit c, no STLs yet at first build
    "alignment-pinion": ("x", 0.0),
    "pinion-bracket": ("x", 0.0),
    "pinion-pivot-block": ("x", 0.0),
    "pinion-pivot-shaft": ("x", 0.0),
    "pinion-lever": ("x", 0.0),
    "pinion-lift-rod": ("x", 0.0),
    "pinion-handle": ("x", 0.0),
    # pinion-spring (PR4): planar-XY leaf, CHIRAL in x (foot east of the bend,
    # blade at the strap lean) but an exact mid-plane z-extrude -- the
    # counter-spring/chain-link z-idiom. The default 'x' mis-poses it (49 mm^3
    # spring-vs-strap interference, caught by the gate). Explicit c, no STL
    # dependency at first build.
    "pinion-spring": ("z", 0.0),
    # pinion-cam-pin (PR5): plain cylinder authored along Z, exact mid-plane
    # both-directions extrude about z = 0. Placed ROTATED (axis -> the strap's
    # leaned cam-bore axis), so the local-x reflection the default 'x' would
    # apply is not a symmetry of the placed pose; the z mid-plane is. Explicit
    # entry per the PR4 rule: every new part declares a symmetry it HAS.
    "pinion-cam-pin": ("z", 0.0),
    # M6.10 fasteners: authored in final orientation (axis along Y or Z),
    # exactly symmetric about local x = 0; explicit c, no STL at first build
    "hex-bolt": ("x", 0.0),
    "lag-screw": ("x", 0.0),
    "fillister-screw": ("x", 0.0),
    "pinch-screw": ("x", 0.0),
    "hanger-screw": ("x", 0.0),
    # slotted-screw (PR7): same fastener convention (axis -Y, x0-symmetric)
    "slotted-screw": ("x", 0.0),
    # PR2 round-3 cone-swing hardware (2026-07-03): all axisymmetric about the
    # local Y axis (bodies are origin-centred circles), so exactly x0-symmetric;
    # explicit c, no STL at first build (the memory's belt-and-braces rule)
    "cone-pivot-screw": ("x", 0.0),
    "swing-stop-screw": ("x", 0.0),
    "cone-tip-bushing": ("x", 0.0),
    "cone-tip-adjuster": ("x", 0.0),
    "cone-tip-pinch-screw": ("x", 0.0),
}

def mirror_placement(
    part: str,
    position: list[float],
    rotation: list[float],
    rows: list[list[float]] | None = None,
    configuration: str = "",
) -> tuple[list[float], list[float], list[list[float]]]:
    """Mirror one component placement about the machine YZ plane.

    Returns (position_mm, rotation_deg, rotation_rows) ready for
    insert_component + assert_component_placed."""
    if rows is None:
        rows = rows_from_euler(rotation)
    plane = MIRROR_PLANE.get(part, "x")
    explicit_c = None
    if isinstance(plane, tuple):
        plane, explicit_c = plane
    axis = 2 if plane == "z" else 0
    if explicit_c is not None:
        c = explicit_c
    elif plane == "x0":
        c = 0.0
    else:
        stem = f"{part}--{configuration}" if configuration else part
        try:
            bbox = stl_bbox_mm(stem)
        except FileNotFoundError:
            if not configuration:
                raise
            bbox = stl_bbox_mm(part)  # config STLs share the bbox centre
        c = 0.5 * (bbox[axis][0] + bbox[axis][1])
        if abs(c) < 2.0:
            # Parts are modeled about their functional axis, so a sub-mm
            # bbox centre is tessellation/tooth-seed noise (max seen 0.76,
            # the pivot-ball-mount's coarse ball facets), while genuine
            # mirror-plane offsets start at 3.0 (gooseneck-clamp). The
            # noise matters: line-to-line bores turn a 2c shift of microns
            # into real interference volumes (M6.8 drive-train rebuild:
            # 19 slivers up to 1.16 mm^3). Snap to the exact axis.
            c = 0.0
    pos2, rows2 = _mirror_xform(position, rows, axis, c)
    return pos2, euler_from_rows(rows2), rows2

def _selftest_mirror_math() -> None:
    cases = [
        [0.0, 0.0, 0.0],
        [90.0, 0.0, 0.0],
        [0.0, -21.0976, 0.0],
        [0.0, 0.0, 1.5],
        [13.0, 47.0, -152.0],
        [90.0, 90.0, 0.0],
        [-90.0, -90.0, 0.0],
        [180.0, 30.0, 180.0],
    ]
    for euler in cases:
        rows = rows_from_euler(euler)
        back = rows_from_euler(euler_from_rows(rows))
        drift = max(
            abs(a - b) for ra, rb in zip(rows, back, strict=True)
            for a, b in zip(ra, rb, strict=True)
        )
        if drift > 1e-9:
            raise AssertionError(f"euler roundtrip drift {drift} for {euler}")
        for axis, c in ((0, 7.25), (2, -3.5)):
            pos2, rows2 = _mirror_xform([11.0, -2.0, 5.0], rows, axis, c)
            det = (
                rows2[0][0] * (rows2[1][1] * rows2[2][2] - rows2[1][2] * rows2[2][1])
                - rows2[0][1] * (rows2[1][0] * rows2[2][2] - rows2[1][2] * rows2[2][0])
                + rows2[0][2] * (rows2[1][0] * rows2[2][1] - rows2[1][1] * rows2[2][0])
            )
            if abs(det - 1.0) > 1e-9:
                raise AssertionError(f"mirror rows not proper (det {det}) for {euler}")
            pos3, rows3 = _mirror_xform(pos2, rows2, axis, c)
            drift = max(
                max(abs(a - b) for a, b in zip(pos3, [11.0, -2.0, 5.0], strict=True)),
                max(
                    abs(a - b) for ra, rb in zip(rows3, rows, strict=True)
                    for a, b in zip(ra, rb, strict=True)
                ),
            )
            if drift > 1e-9:
                raise AssertionError(f"mirror not involutive (drift {drift}) for {euler}")


_selftest_mirror_math()
