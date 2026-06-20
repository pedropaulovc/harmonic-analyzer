r"""CadQuery stand-in for ``build_cylinder_gear.py`` (book ch. 13, pp. 22-25).

The production part is authored against the SolidWorks MCP adapter, which needs
a live SolidWorks session. This module reproduces the *same* cylinder-gear
geometry with CadQuery so the part can be built, exported (STEP/STL) and
rendered head-less -- e.g. to eyeball the p.23-labelled alignment **notch**.

Why this stand-in exists (the notch fix)
----------------------------------------
The SolidWorks script models the alignment mark as a 3 mm x 3 mm *square*
notch (``NOTCH_WIDTH = 3.0`` -- "width estimated = depth", low confidence).
The book photographs tell a different story: the p.23 close-up literally
labelled "notch" shows the reference mark as a **single radial slit** -- in
effect one missing tooth, a thin saw-kerf cut into the rim, not a broad
square pocket (book text: "a reference mark-a single notch about 3 mm in
depth"; only the *depth* is stated, the width is not). This stand-in cuts the
notch as that thin slit (``SLIT_WIDTH``), centred on +Y exactly over a tooth
crest (+Y = 30*gamma is a tooth centre at 120 T), so it reads as the missing
tooth the photos show.

Geometry mirrors the SolidWorks script (DIMENSIONS.md ch. 13), lengths in mm:
  * Toothed disc: involute 120 T blank at tip radius ``Ra`` (OD 62.2 mm),
    face width 3 mm, z = 0..3. Same DP 49.82 / PA 14.5 deg profile as the
    cone set -- here the full toothed outline is generated analytically and
    extruded once (the SolidWorks path cuts one gap and circular-patterns it
    120x; the resulting solid is identical).
  * Integral eccentric cam: disc OD 30.6 mm, thickness 3.5 mm, centre offset
    -Y by the 3.06 mm eccentricity, z = 3..6.5.
  * Alignment notch: a thin radial **slit** (the missing-tooth reference
    mark), 3 mm deep, at +Y, cut through the full face width.
  * Plain shaft bore Ø3/8 in through gear + cam, on the gear axis (no keyway
    -- M6.2 keyway refutation).

Layout: gear axis = Z through the origin, gear z = 0..3 mm, cam z = 3..6.5,
cam lobe -Y, notch +Y.

Run::

    /home/user/cqenv/bin/python cad/scripts/build_cylinder_gear_cadquery.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cadquery as cq

# --- dimensions (kept in sync with build_cylinder_gear.py) -------------------
IN = 25.4  # mm per inch (document units)

TEETH = 120  # DIMENSIONS.md ch13: derived from gear law k/80
DP = 49.82  # cad/config/machine.yaml gear_train.diametral_pitch (= 122*25.4/62.2)
PA_DEG = 14.5  # pressure angle, period-typical assumption (low)

FACE_WIDTH = 3.0  # DIMENSIONS.md ch13: 0.38 face/pitch x 7.5 axial pitch (scaled)
CAM_DIAMETER = 30.6  # DIMENSIONS.md ch13: integral cam diameter, scaled 0.6022
CAM_THICKNESS = 3.5  # DIMENSIONS.md ch13: axial-budget (7.0565 channel pitch)
ECCENTRICITY = 3.06  # DIMENSIONS.md ch13: cam eccentricity, scaled 0.6022
BORE_DIAMETER = 0.375 * IN  # 9.525 -- plain bore, NO keyway (M6.2 refutation)

NOTCH_DEPTH = 3.0  # DIMENSIONS.md ch13: alignment notch depth, text p.22 (high)
# The notch is "just a slit" cut with a SAW between two teeth -- the p.23 photo
# labelled "notch" shows a thin kerf, and the real gears are NOT missing a tooth
# (all 120 stay complete). So it is a narrow saw kerf seated in the tooth VALLEY
# nearest +Y, 3 mm deep; the flanking tooth crests are untouched. The book gives
# only the depth; the kerf width is a slitting-saw value (low confidence).
KERF_WIDTH = 0.4

BORE_RADIUS = BORE_DIAMETER / 2.0


def gear_facts(teeth: int, dp: float = DP, pa_deg: float = PA_DEG) -> dict[str, float]:
    """Python mirror of build_cone_gear.gear_facts (lengths in inches)."""
    pa = math.radians(pa_deg)
    rb = teeth / dp * math.cos(pa) / 2.0
    ra = (teeth + 2.0) / dp / 2.0
    tmax = math.sqrt((ra / rb) ** 2 - 1.0)
    delta = math.pi / (2.0 * teeth) + math.tan(pa) - pa
    gamma = 2.0 * math.pi / teeth
    return {
        "Rb": rb,
        "Ra": ra,
        "Tmax": tmax,
        "Delta": delta,
        "Gamma": gamma,
        "ThetaL": math.atan(tmax) - tmax + delta,
        "ThetaU": tmax - math.atan(tmax) - delta + gamma,
    }


FACTS = gear_facts(TEETH, DP)
RA_MM = FACTS["Ra"] * IN  # 31.10 -- gear OD/2
RB_MM = FACTS["Rb"] * IN
NOTCH_FLOOR = RA_MM - NOTCH_DEPTH
NOTCH_OUTER = RA_MM + 1.5  # clearance past the OD so the slit always opens


def _toothed_profile_points(samples: int = 16) -> list[tuple[float, float]]:
    """Closed CCW outline of the 120-tooth involute disc (mm).

    Walks every tooth: up the upper flank of gap k (base->tip), across the
    tip land at ``Ra``, down the lower flank of gap k+1 (tip->base), then the
    root land at ``Rb`` to the next tooth. This is the exact complement of the
    SolidWorks "cut one gap, pattern 120x" recipe (same flank/chord
    parametrisation as build_cone_gear.gap_area_in_disc).
    """
    rb, ra = RB_MM, RA_MM
    tmax, delta, gamma = FACTS["Tmax"], FACTS["Delta"], FACTS["Gamma"]
    theta_l, theta_u = FACTS["ThetaL"], FACTS["ThetaU"]
    pts: list[tuple[float, float]] = []

    def rot(x: float, y: float, a: float) -> tuple[float, float]:
        c, s = math.cos(a), math.sin(a)
        return (x * c - y * s, x * s + y * c)

    arc_n = max(3, samples // 3)
    for k in range(TEETH):
        base = k * gamma
        nxt = (k + 1) * gamma
        # 1) upper flank of gap k: A2 (base) -> B2 (tip)
        for i in range(samples):
            t = tmax * i / samples
            ph = t - delta + gamma
            x = rb * (math.cos(ph) + t * math.sin(ph))
            y = rb * (math.sin(ph) - t * math.cos(ph))
            pts.append(rot(x, y, base))
        # 2) tip land arc at Ra: B2(k) -> B1(k+1)
        a0, a1 = theta_u + base, theta_l + nxt
        for i in range(arc_n):
            a = a0 + (a1 - a0) * i / arc_n
            pts.append((ra * math.cos(a), ra * math.sin(a)))
        # 3) lower flank of gap k+1: B1 (tip) -> A1 (base)
        for i in range(samples):
            t = tmax * (samples - i) / samples
            ph = t - delta
            x = rb * (math.cos(ph) + t * math.sin(ph))
            y = rb * (t * math.cos(ph) - math.sin(ph))
            pts.append(rot(x, y, nxt))
        # 4) root land arc at Rb: A1(k+1) -> A2(k+1)
        a0, a1 = delta + nxt, (gamma - delta) + nxt
        for i in range(arc_n):
            a = a0 + (a1 - a0) * i / arc_n
            pts.append((rb * math.cos(a), rb * math.sin(a)))

    # Drop consecutive near-duplicates (zero-length edges break the wire).
    out: list[tuple[float, float]] = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-7:
            out.append(p)
    return out


def build() -> cq.Workplane:
    # 1) Toothed disc, z = 0..FACE_WIDTH.
    profile = _toothed_profile_points()
    gear = (
        cq.Workplane("XY")
        .polyline(profile)
        .close()
        .extrude(FACE_WIDTH)
    )

    # 2) Integral eccentric cam on the far face, lobe -Y, z = FACE..FACE+CAM.
    cam = (
        cq.Workplane("XY")
        .workplane(offset=FACE_WIDTH)
        .center(0.0, -ECCENTRICITY)
        .circle(CAM_DIAMETER / 2.0)
        .extrude(CAM_THICKNESS)
    )
    part = gear.union(cam)

    # 3) Alignment notch: a thin saw KERF seated in the tooth valley nearest
    #    +Y, 3 mm deep, cut through the full face width. +Y (90 deg = 30*gamma)
    #    is a tooth CREST at 120 T, so the kerf is rotated by +gamma/2 (1.5 deg)
    #    to sit in the adjacent root valley -- it deepens one gap without
    #    removing any tooth (all 120 crests stay intact).
    kerf = (
        cq.Workplane("XY")
        .workplane(offset=-0.5)
        .center(0.0, (NOTCH_FLOOR + NOTCH_OUTER) / 2.0)
        .rect(KERF_WIDTH, NOTCH_OUTER - NOTCH_FLOOR)
        .extrude(FACE_WIDTH + 1.0)
        .rotate((0, 0, 0), (0, 0, 1), math.degrees(FACTS["Gamma"] / 2.0))
    )
    part = part.cut(kerf)

    # 4) Shaft bore through gear + cam on the gear axis (no keyway).
    bore = (
        cq.Workplane("XY")
        .workplane(offset=-1.0)
        .circle(BORE_RADIUS)
        .extrude(FACE_WIDTH + CAM_THICKNESS + 2.0)
    )
    part = part.cut(bore)
    return part


def render_mpl(stl_path: Path, png_path: Path) -> None:
    """Shaded matplotlib render (head-less): face-on + 3/4 iso, notch at +Y."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402
    import numpy as np  # noqa: E402
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402
    from stl import mesh as stlmesh  # noqa: E402

    m = stlmesh.Mesh.from_file(str(stl_path))
    tris = m.vectors
    n = m.normals.astype(float).copy()
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n /= ln
    light = np.array([0.3, 0.45, 0.85])
    light /= np.linalg.norm(light)
    inten = np.clip(np.abs(n @ light), 0, 1) * 0.72 + 0.28
    colors = np.clip(inten[:, None] * np.array([0.80, 0.66, 0.30]), 0, 1)  # brass

    def panel(ax, elev, azim, title, box):
        ax.add_collection3d(
            Poly3DCollection(
                tris, facecolors=colors, edgecolors=(0, 0, 0, 0.10), linewidths=0.05
            )
        )
        ax.set_title(title, fontsize=9)
        ax.view_init(elev=elev, azim=azim)
        lim = RA_MM + 4
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_zlim(-lim, lim)
        ax.set_box_aspect(box)
        ax.tick_params(labelsize=6)

    fig = plt.figure(figsize=(12, 6.5), dpi=140)
    a1 = fig.add_subplot(1, 2, 1, projection="3d")
    panel(
        a1, 90, -90,
        "face-on (+Y up): 120 T involute, OD 62.2 mm,\n"
        "alignment notch = thin saw kerf in the valley near +Y (teeth intact)",
        (1, 1, 1),
    )
    a1.set_zticks([])
    a2 = fig.add_subplot(1, 2, 2, projection="3d")
    panel(
        a2, 22, -68,
        "3/4 iso: integral eccentric cam (lobe -Y, z 3..6.5),\n"
        "Ø3/8 in plain bore, kerf notch near +Y",
        (1, 1, 1),
    )
    fig.tight_layout()
    fig.savefig(str(png_path), bbox_inches="tight", facecolor="white")
    print(f"wrote {png_path} (matplotlib)")


def _point_in_solid(solid: cq.Solid, x: float, y: float, z: float) -> bool:
    """True if (x, y, z) mm is inside/on the solid (OCC point classifier)."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON

    cls = BRepClass3d_SolidClassifier(solid.wrapped)
    cls.Perform(gp_Pnt(x, y, z), 1e-6)
    return cls.State() in (TopAbs_IN, TopAbs_ON)


def _verify_teeth_intact(solid: cq.Solid) -> None:
    """The kerf must NOT remove a tooth: every tooth crest stays solid, and
    the kerf itself must have bitten the valley below the base circle."""
    gamma = FACTS["Gamma"]
    z = FACE_WIDTH / 2.0
    missing = []
    for k in range(TEETH):  # crest centres at (k+1)*gamma, tip just inside Ra
        a = (k + 1) * gamma
        if not _point_in_solid(solid, (RA_MM - 0.15) * math.cos(a),
                               (RA_MM - 0.15) * math.sin(a), z):
            missing.append(k)
    if missing:
        raise RuntimeError(f"{len(missing)} tooth crest(s) removed (idx {missing[:5]}...)")
    # Kerf bite: a point in the +Y valley, below the base circle (normally
    # solid web), must now be empty.
    av = math.pi / 2.0 + gamma / 2.0
    rk = (NOTCH_FLOOR + RB_MM) / 2.0  # between kerf floor and base circle
    if _point_in_solid(solid, rk * math.cos(av), rk * math.sin(av), z):
        raise RuntimeError("kerf did not cut the +Y valley")
    print(f"  OK  all {TEETH} tooth crests intact; kerf seated in +Y valley")


def main() -> int:
    out = Path(__file__).resolve().parent.parent / "out" / "cylinder-gear-cq"
    out.parent.mkdir(parents=True, exist_ok=True)
    part = build()

    solid = part.val()
    _verify_teeth_intact(solid)
    vol = solid.Volume()
    bb = solid.BoundingBox()
    print(f"volume: {vol:,.1f} mm^3")
    print(
        f"bbox: X {bb.xmin:.1f}..{bb.xmax:.1f} ({bb.xlen:.1f})  "
        f"Y {bb.ymin:.1f}..{bb.ymax:.1f} ({bb.ylen:.1f})  "
        f"Z {bb.zmin:.1f}..{bb.zmax:.1f} ({bb.zlen:.1f})"
    )

    cq.exporters.export(part, str(out.with_suffix(".step")))
    cq.exporters.export(
        part, str(out.with_suffix(".stl")), tolerance=0.004, angularTolerance=0.015
    )
    print(f"wrote {out.with_suffix('.step')} and .stl")
    render_mpl(out.with_suffix(".stl"), out.with_suffix(".png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
