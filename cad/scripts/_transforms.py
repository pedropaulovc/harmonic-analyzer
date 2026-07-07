"""Placement math + STL bbox: Euler/rotation conversion, mirror transforms
and the cached STL bounding-box reader. Split out of _common so assembly
placement math can change without invalidating any part build.
"""
from __future__ import annotations

import math
import struct

import _config_asm
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
# The per-part mirror-plane symmetry declaration S now lives in its OWN config
# family -- ``cad/config/placement/<dashed-name>.yaml`` (``mirror_plane:``) --
# read via ``_config_asm.placement`` in ``mirror_placement`` below (issue #156).
# It was a module-level dict here, which put it in EVERY assembly's helper
# closure: adding one new part's entry re-keyed all 8 assemblies -> a full
# spine of FULL rebuilds. Per-file, a placement edit now re-keys only the
# assemblies that PLACE that part (``placement/*`` -> referenced-part rows in
# dodo/_buildgraph), and never the part itself (placement is assembly-time).
# A part with NO file takes the default bbox-``x`` plane, exactly as before.

# In-process placement override for parts GENERATED at assembly-build time (no
# config file, no STL yet) -- e.g. build_channel_assembly's per-channel stretched
# springs (channel-spring-installed-stretchNN). Replaces the old mutate-the-shared-
# MIRROR_PLANE-dict hack; keyed the same, read first by mirror_placement. Not a
# config input, so it never touches the recipe/cache digest (these ephemeral parts
# are rebuilt fresh each run anyway).
_RUNTIME_PLACEMENT: dict[str, str | tuple[str, float]] = {}


def set_runtime_placement(part: str, mirror_plane: str | tuple[str, float]) -> None:
    """Register a mirror-plane symmetry for a dynamically-generated part (see
    ``_RUNTIME_PLACEMENT``). ``mirror_plane`` uses the same vocabulary as the
    ``placement/*.yaml`` ``mirror_plane`` field."""
    _RUNTIME_PLACEMENT[part] = mirror_plane


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
    # Per-part symmetry S: a runtime override (dynamically-built parts) wins, else
    # cad/config/placement/<part>.yaml (default 'x'). A tuple/list [axis, c] carries
    # an explicit plane coordinate (YAML yields a list).
    plane = _RUNTIME_PLACEMENT.get(part) or _config_asm.placement(part).get("mirror_plane", "x")
    explicit_c = None
    if isinstance(plane, (list, tuple)):
        plane, explicit_c = plane[0], float(plane[1])
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
