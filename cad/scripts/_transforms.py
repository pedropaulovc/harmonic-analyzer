"""Placement math + STL bbox: Euler/rotation conversion, rotation-row
constants and the cached STL bounding-box reader. Split out of _common so
assembly placement math can change without invalidating any part build.
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


def compose_rows(
    a: list[list[float]], b: list[list[float]]
) -> list[list[float]]:
    """Rows of the composed placement: rotate a part by ``a``, THEN by ``b``
    (row-vector convention -- the matrix product ``a @ b``, matching how
    ``rows_from_euler`` chains Rx, Ry, Rz)."""
    return [
        [sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]

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

# Machine chirality (M6.8 -> #151). The assembly frame IS the real machine's:
# the crank sits at machine -X (the viewer's RIGHT when facing the paper, per
# every ch. 30 plate and the Altgeld Hall photogrammetry), the output side is
# -Z. Every placement is authored DIRECTLY in this frame. History: the original
# assembly was derived in the mirrored frame (crank +X) and reflected about the
# machine YZ plane at the place_component boundary (``mirror_placement``, with a
# per-part ``MIRROR_PLANE`` symmetry declaration under ``cad/config/placement/``);
# issue #151 re-authored the derivation machine-handed and deleted that layer --
# a reflection is not a rigid motion, so it demanded a symmetry claim per part
# that nothing could validate (#153) and re-keyed every assembly on each new
# part's entry (#156). Correctness is arbitrated by assert_component_placed
# readback + the pose ledger, the zero-interference gate, the analytic gates,
# and the photo comparison renders -- plus, for the #151 sweep itself, the
# as-saved pose equivalence probe (diagnostics/probe_pose_dump.py).

ROT_Y_180 = [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]


def _selftest_euler_roundtrip() -> None:
    cases = [
        [0.0, 0.0, 0.0],
        [90.0, 0.0, 0.0],
        [0.0, -21.0976, 0.0],
        [0.0, 0.0, 1.5],
        [13.0, 47.0, -152.0],
        [90.0, 90.0, 0.0],
        [-90.0, -90.0, 0.0],
        [180.0, 30.0, 180.0],
        [0.0, 180.0, 0.0],
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


_selftest_euler_roundtrip()
