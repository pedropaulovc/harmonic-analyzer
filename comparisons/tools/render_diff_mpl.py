r"""No-GL changed-parts render: software (matplotlib Agg) fallback for headless
Windows where VTK/pyvista can't get an OpenGL context (opengl32.dll is a Windows
KnownDLL so mesa can't override it, and the pip vtk wheel's OSMesa path needs an
osmesa.dll that modern mesa builds no longer ship).

Draws the NEW scene: every component whose base part is in --changed is rendered
as real (decimated) RED geometry; everything else as a light-grey bounding-box
wireframe for spatial context. Four views to PNG via the Agg backend -- no GPU,
no GL context, no external driver.

    .render-venv/Scripts/python.exe comparisons/tools/render_diff_mpl.py \
        --scene cad/out/boxes/harmonic-analyzer.json --stl-dir cad/out/stl \
        --changed channel-spring-installed,measuring-stick,rocker-arm,transgear-removable \
        --out .render_diff_v020
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from mpl_toolkits.mplot3d.art3d import (  # noqa: E402
    Line3DCollection,
    Poly3DCollection,
)

HILITE = "#dc1f1f"
GHOST = "#c8c8cd"
FACE_BUDGET = 700  # decimate each red mesh to this many triangles


def base_part(key: str) -> str:
    return re.sub(r"(--t\d+|-stretch\d+)$", "", key)


def sw_matrix(xform):
    a, b, c, d, e, f, g, h, i, tx, ty, tz, s = xform[:13]
    return np.array([
        [a * s, d * s, g * s, tx],
        [b * s, e * s, h * s, ty],
        [c * s, f * s, i * s, tz],
        [0.0, 0.0, 0.0, 1.0],
    ])


def transform(mesh, m):
    v = np.asarray(mesh.vertices)
    vh = np.c_[v, np.ones(len(v))]
    return (m @ vh.T).T[:, :3]


def box_edges(lo, hi):
    """12 edges of an axis-aligned box [lo,hi] as segment endpoint pairs."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    e = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
         (0, 4), (1, 5), (2, 6), (3, 7)]
    return [(c[a], c[b]) for a, b in e]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, type=Path)
    ap.add_argument("--stl-dir", required=True, type=Path)
    ap.add_argument("--changed", required=True, help="comma base parts")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--old", default="v0.2.0")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    changed = {c.strip() for c in args.changed.split(",") if c.strip()}

    scene = json.loads(args.scene.read_text(encoding="utf-8"))
    comps = scene["components"]

    cache: dict[str, trimesh.Trimesh] = {}

    def load(mesh_key: str):
        if mesh_key not in cache:
            p = args.stl_dir / f"{mesh_key}.STL"
            if not p.exists():
                p = args.stl_dir / f"{base_part(mesh_key)}.STL"
            cache[mesh_key] = trimesh.load(p, process=False) if p.exists() else None
        return cache[mesh_key]

    red_tris: list = []          # list of (3,3) triangles for changed parts
    edges: list = []             # grey context bbox edges
    all_pts = []
    n_red = 0
    for c in comps:
        key = c.get("mesh") or c["part"]
        m = load(key)
        if m is None:
            continue
        pts = transform(m, sw_matrix(c["xform"]))
        lo, hi = pts.min(0), pts.max(0)
        all_pts.append(lo)
        all_pts.append(hi)
        if base_part(key) in changed:
            mm = m
            if len(m.faces) > FACE_BUDGET:
                try:
                    mm = m.simplify_quadric_decimation(FACE_BUDGET)
                except Exception:
                    mm = m
            vv = transform(mm, sw_matrix(c["xform"]))
            for f in mm.faces:
                red_tris.append(vv[f])
            n_red += 1
        else:
            edges.extend(box_edges(lo, hi))
    print(f"red instances={n_red}  red tris={len(red_tris)}  ghost boxes={len(edges)//12}")

    allp = np.array(all_pts)
    lo, hi = allp.min(0), allp.max(0)
    pad = (hi - lo) * 0.02
    lo, hi = lo - pad, hi + pad
    rng = hi - lo

    views = {
        "iso": (22, -58), "front": (6, -90), "right": (6, 0), "top": (89, -90),
    }
    written = []
    for name, (elev, azim) in views.items():
        fig = plt.figure(figsize=(9, 9), dpi=200)
        ax = fig.add_subplot(111, projection="3d")
        if edges:
            ax.add_collection3d(Line3DCollection(
                edges, colors=GHOST, linewidths=0.25, alpha=0.5))
        if red_tris:
            ax.add_collection3d(Poly3DCollection(
                red_tris, facecolor=HILITE, edgecolor="none", alpha=1.0))
        ax.set_xlim(lo[0], hi[0])
        ax.set_ylim(lo[1], hi[1])
        ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(tuple(rng))  # true proportions -> fills the frame
        ax.view_init(elev=elev, azim=azim)
        try:
            ax.set_proj_type("ortho")
        except Exception:
            pass
        ax.set_axis_off()
        ax.set_title(f"{args.old} -> new   (red = changed geometry)   [{name}]",
                     fontsize=9)
        out = args.out / f"diff_mpl_{name}.png"
        fig.savefig(out, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        written.append(out.name)
        print("wrote", out)
    (args.out / "diff_mpl_summary.json").write_text(json.dumps(
        {"old": args.old, "changed": sorted(changed),
         "red_instances": n_red, "images": written}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
