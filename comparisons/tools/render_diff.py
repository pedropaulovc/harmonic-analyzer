# /// script
# requires-python = ">=3.11"
# dependencies = ["cadquery-ocp", "trimesh", "rtree", "numpy", "scipy",
#                 "pyvista"]
# ///
"""Render the assembly in 3D with parts that changed between two releases
highlighted in red, everything else ghosted grey.

Pipeline:
  1. read both release central directories (HTTP range, no full download);
  2. classify each scene-graph mesh: equal CRC -> unchanged (free); differing
     CRC -> fetch both STLs and confirm with a Hausdorff check (CRC alone
     over-reports -- it trips on tessellation/byte noise);
  3. assemble the v0.2.0 scene graph (boxes/harmonic-analyzer.json) with each
     instanced part STL placed by its SolidWorks transform, colour red if its
     mesh changed else grey;
  4. render N camera angles to PNG with an offscreen (xvfb) VTK context.

    uv run comparisons/tools/render_diff.py v0.1.1 v0.2.0 --out /tmp/diff
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import release_diff as rd  # noqa: E402

HILITE = (0.86, 0.12, 0.12)   # changed -> red
GHOST = (0.80, 0.80, 0.82)    # unchanged -> light grey


def base_part(key):
    return re.sub(r"(--t\d+|-stretch\d+)$", "", key)


def ci_get(cd, name):
    """Case-insensitive central-directory lookup (members use .STL)."""
    name = name.lower()
    for n, e in cd.items():
        if n.lower() == name:
            return e
    return None


def sw_matrix(xform):
    """SolidWorks ArrayData (row-vector) -> 4x4 column-vector matrix."""
    a, b, c, d, e, f, g, h, i, tx, ty, tz, s = xform[:13]
    return np.array([
        [a * s, d * s, g * s, tx],
        [b * s, e * s, h * s, ty],
        [c * s, f * s, i * s, tz],
        [0.0, 0.0, 0.0, 1.0],
    ])


def classify(tag_a, tag_b, keys, ca, cb, hidir, tol=0.01):
    """Return set of mesh keys whose geometry actually changed."""
    changed = set()
    for k in sorted(keys):
        ea = ci_get(ca, f"stl/{k}.stl") or ci_get(ca, f"stl/{base_part(k)}.stl")
        eb = ci_get(cb, f"stl/{k}.stl") or ci_get(cb, f"stl/{base_part(k)}.stl")
        if ea is None or eb is None:
            changed.add(k)            # new/missing -> treat as changed
            continue
        if ea["crc"] == eb["crc"]:
            continue                  # byte-identical -> unchanged (free)
        # CRC differs: confirm with geometry so byte-noise isn't highlighted
        bk = base_part(k)
        rd.extract(rd.asset_url(tag_a), ea, hidir / tag_a / f"{bk}.stl")
        rd.extract(rd.asset_url(tag_b), eb, hidir / tag_b / f"{bk}.stl")
        md = rd.mesh_deviation(tag_a, tag_b, bk)
        if md["hausdorff_mm"] > tol:
            changed.add(k)
        print(f"  verify {k:34s} Hausdorff={md['hausdorff_mm']:7.3f} mm -> "
              f"{'CHANGED' if k in changed else 'identical'}")
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag_a")
    ap.add_argument("tag_b")
    ap.add_argument("--out", default="/tmp/render_diff", type=Path)
    ap.add_argument("--res", type=int, default=1600)
    ap.add_argument("--ghost-opacity", type=float, default=0.18,
                    help="opacity of unchanged parts (0..1)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rd.CACHE.mkdir(parents=True, exist_ok=True)

    ua, ub = rd.asset_url(args.tag_a), rd.asset_url(args.tag_b)
    print("reading central directories ...", flush=True)
    ca, cb = rd.central_dir(ua), rd.central_dir(ub)

    # scene graph comes from the newer release
    import json
    scene_entry = cb["boxes/harmonic-analyzer.json"]
    scene_path = rd.extract(ub, scene_entry, rd.CACHE / args.tag_b / "scene.json")
    scene = json.loads(Path(scene_path).read_text())
    comps = scene["components"]
    keys = {(c.get("mesh") or c["part"]) for c in comps}
    print(f"scene: {len(comps)} components, {len(keys)} unique meshes")

    print("classifying changed meshes ...", flush=True)
    changed = classify(args.tag_a, args.tag_b, keys, ca, cb, rd.CACHE)
    changed_bases = {base_part(k) for k in changed}
    print(f"\nCHANGED parts ({len(changed_bases)}): "
          f"{', '.join(sorted(changed_bases))}\n")

    # fetch all v0.2.0 STLs needed for the scene
    print("fetching v0.2.0 meshes for render ...", flush=True)
    mesh_path = {}
    for k in sorted(keys):
        e = ci_get(cb, f"stl/{k}.stl")
        if e is None:
            continue
        mesh_path[k] = rd.extract(ub, e, rd.CACHE / args.tag_b / "stl" / f"{k}.stl")

    # build the scene (run under xvfb-run for an offscreen GL context)
    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=(args.res, args.res))
    pl.set_background("white")
    n_hi = 0
    for c in comps:
        key = c.get("mesh") or c["part"]
        if key not in mesh_path:
            continue
        m = pv.read(mesh_path[key])
        m.transform(sw_matrix(c["xform"]), inplace=True)
        is_changed = base_part(key) in changed_bases
        if is_changed:
            n_hi += 1
        pl.add_mesh(m, color=HILITE if is_changed else GHOST,
                    opacity=1.0 if is_changed else args.ghost_opacity,
                    smooth_shading=True, specular=0.2,
                    backface_culling=not is_changed)
    print(f"highlighted {n_hi} component instances")

    pl.add_text(f"{args.tag_a} -> {args.tag_b}  (red = changed geometry)",
                font_size=11, color="black")

    views = {
        "iso":   "iso",
        "front": "xy",
        "right": "yz",
        "top":   "xz",
    }
    outs = []
    for name, cpos in views.items():
        pl.camera_position = cpos
        if name == "iso":
            pl.camera.azimuth = 35
            pl.camera.elevation = 20
        pl.reset_camera()
        out = args.out / f"diff_{args.tag_a}_{args.tag_b}_{name}.png"
        pl.screenshot(str(out))
        outs.append(out)
        print("wrote", out)
    pl.close()
    print("\n".join(str(o) for o in outs))


if __name__ == "__main__":
    main()
