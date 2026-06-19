# /// script
# requires-python = ">=3.11"
# dependencies = ["trimesh", "rtree", "numpy", "scipy", "pyvista"]
# ///
"""Render the assembly in 3D with parts that changed between two bundles
highlighted in red over an x-ray ghost of the unchanged body.

Each side is a *source* -- either a published GitHub release (read over HTTP
range requests, no full-asset download) or a local staged bundle directory
(``<dir>/stl/*.STL`` + ``<dir>/boxes/harmonic-analyzer.json``). The local form
is what ``cut_release.py`` uses: the new release is still on disk and only the
previous release is fetched from GitHub.

Pipeline:
  1. classify every scene-graph mesh -- equal signature (zip CRC32 / file
     CRC32) is unchanged for free; differing signature is confirmed with a
     Hausdorff check so byte/tessellation noise is not highlighted;
  2. assemble the *new* scene graph, placing each instanced part STL by its
     SolidWorks transform, colour red if its mesh changed else ghost grey;
  3. render N camera angles to PNG with an offscreen VTK context and write a
     diff_summary.json (changed parts + per-mesh deviation + image names).

    # release vs release
    uv run comparisons/tools/render_diff.py v0.1.1 v0.2.0 --out /tmp/diff
    # previous release vs local staged bundle (what cut_release does)
    uv run comparisons/tools/render_diff.py --old-release v0.2.0 \
        --new-local cad/out/release/harmonic-analyzer-v0.3.0 --out <stage>/diff

On Linux run under ``xvfb-run`` for the offscreen GL context; on Windows the
native driver serves it directly.
"""

import argparse
import json
import os
import re
import struct
import sys
import urllib.request
import zlib
from pathlib import Path

import numpy as np

# Headless software OpenGL (Mesa OSMesa) for VTK on this no-GPU box. MUST run
# before pyvista/vtk import so VTK selects the OSMesa render window. No-op off
# Windows (platform GL / xvfb serves offscreen there).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from osmesa_win import enable_offscreen_gl

enable_offscreen_gl()

import pyvista as pv
import trimesh

CACHE = Path(os.environ.get("RELEASE_DIFF_CACHE", "/tmp/release_diff_cache"))
HILITE = (0.86, 0.12, 0.12)   # changed -> red
GHOST = (0.80, 0.80, 0.82)    # unchanged -> light grey


def base_part(key):
    """Strip per-config suffixes (cone-gear--t024, ...-stretch07) to the part."""
    return re.sub(r"(--t\d+|-stretch\d+)$", "", key)


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #
class ReleaseSource:
    """A published GitHub release zip, read incrementally over HTTP ranges."""

    def __init__(self, tag):
        self.tag = tag
        self.label = tag
        self.url = ("https://github.com/pedropaulovc/harmonic-analyzer/releases/"
                    f"download/{tag}/harmonic-analyzer-{tag}.zip")
        self.cd = self._central_dir()
        self._ci = {n.lower(): e for n, e in self.cd.items()}

    def _get(self, start, end):
        req = urllib.request.Request(self.url,
                                     headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(req) as r:
            return r.read()

    def _central_dir(self):
        req = urllib.request.Request(self.url, headers={"Range": "bytes=0-0"})
        with urllib.request.urlopen(req) as r:
            total = int(r.headers["Content-Range"].split("/")[1])
        tail = self._get(max(0, total - 65536), total - 1)
        eocd = tail.rfind(b"PK\x05\x06")
        (_, _, _, _, _, cd_size, cd_off, _) = struct.unpack(
            "<IHHHHIIH", tail[eocd:eocd + 22])
        if cd_off == 0xFFFFFFFF:
            loc = tail.rfind(b"PK\x06\x07")
            z64 = struct.unpack("<Q", tail[loc + 8:loc + 16])[0]
            z = self._get(z64, z64 + 56)
            cd_size = struct.unpack("<Q", z[40:48])[0]
            cd_off = struct.unpack("<Q", z[48:56])[0]
        cd = self._get(cd_off, cd_off + cd_size - 1)
        out, p = {}, 0
        while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
            f = struct.unpack("<IHHHHHHIIIHHHHHII", cd[p:p + 46])
            n, m, k = f[10], f[11], f[12]
            name = cd[p + 46:p + 46 + n].decode("utf-8", "replace")
            extra = cd[p + 46 + n:p + 46 + n + m]
            method, comp, uncomp, lho, crc = f[4], f[8], f[9], f[16], f[7]
            ep = 0
            while ep + 4 <= len(extra):
                hid, hsz = struct.unpack("<HH", extra[ep:ep + 4])
                blk, bp = extra[ep + 4:ep + 4 + hsz], 0
                if hid == 1:
                    if uncomp == 0xFFFFFFFF:
                        uncomp = struct.unpack("<Q", blk[bp:bp + 8])[0]
                        bp += 8
                    if comp == 0xFFFFFFFF:
                        comp = struct.unpack("<Q", blk[bp:bp + 8])[0]
                        bp += 8
                    if lho == 0xFFFFFFFF:
                        lho = struct.unpack("<Q", blk[bp:bp + 8])[0]
                        bp += 8
                ep += 4 + hsz
            out[name] = dict(method=method, comp=comp, uncomp=uncomp,
                             lho=lho, crc=crc)
            p += 46 + n + m + k
        return out

    def _entry(self, rel):
        e = self._ci.get(rel.lower())
        return None if e is None else (rel, e)

    def _stl_entry(self, key):
        return (self._entry(f"stl/{key}.stl")
                or self._entry(f"stl/{base_part(key)}.stl"))

    def crc(self, key):
        e = self._stl_entry(key)
        return None if e is None else e[1]["crc"]

    def stl(self, key):
        e = self._stl_entry(key)
        if e is None:
            return None
        rel, ent = e
        dest = CACHE / self.tag / Path(rel).name
        if dest.exists() and dest.stat().st_size == ent["uncomp"]:
            return dest
        lh = self._get(ent["lho"], ent["lho"] + 30 - 1)
        n, m = struct.unpack("<HH", lh[26:30])
        off = ent["lho"] + 30 + n + m
        raw = self._get(off, off + ent["comp"] - 1)
        data = raw if ent["method"] == 0 else zlib.decompress(raw, -15)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest

    def scene(self):
        rel = "boxes/harmonic-analyzer.json"
        e = self._entry(rel)
        if e is None:
            raise SystemExit(f"!! {self.tag} has no {rel} (pre-bundle release?)")
        dest = CACHE / self.tag / "scene.json"
        ent = e[1]
        lh = self._get(ent["lho"], ent["lho"] + 30 - 1)
        n, m = struct.unpack("<HH", lh[26:30])
        off = ent["lho"] + 30 + n + m
        raw = self._get(off, off + ent["comp"] - 1)
        data = raw if ent["method"] == 0 else zlib.decompress(raw, -15)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return json.loads(data)


class LocalSource:
    """A staged release bundle on disk: stl/*.STL + boxes/<top>.json."""

    def __init__(self, root):
        self.root = Path(root)
        self.label = f"local:{self.root.name}"
        self._stls = {p.stem.lower(): p
                      for p in (self.root / "stl").glob("*")
                      if p.suffix.lower() == ".stl"}
        self._crc = {}

    def _path(self, key):
        return (self._stls.get(key.lower())
                or self._stls.get(base_part(key).lower()))

    def crc(self, key):
        p = self._path(key)
        if p is None:
            return None
        if p not in self._crc:
            self._crc[p] = zlib.crc32(p.read_bytes()) & 0xFFFFFFFF
        return self._crc[p]

    def stl(self, key):
        return self._path(key)

    def scene(self):
        cands = sorted((self.root / "boxes").glob("*.json"))
        if not cands:
            raise SystemExit(f"!! no boxes/*.json under {self.root}")
        return json.loads(cands[0].read_text(encoding="utf-8"))


def make_source(release, local):
    return ReleaseSource(release) if release else LocalSource(local)


# --------------------------------------------------------------------------- #
def sw_matrix(xform):
    """SolidWorks ArrayData (row-vector) -> 4x4 column-vector matrix."""
    a, b, c, d, e, f, g, h, i, tx, ty, tz, s = xform[:13]
    return np.array([
        [a * s, d * s, g * s, tx],
        [b * s, e * s, h * s, ty],
        [c * s, f * s, i * s, tz],
        [0.0, 0.0, 0.0, 1.0],
    ])


def _hausdorff(pa, pb, n=40000, budget=4_000_000):
    """Approximate symmetric Hausdorff (mm) between two STL meshes.

    Query set per direction = vertices (deterministic feature points where the
    max deviation almost always sits) plus surface samples, so a small local
    change is not missed by random sampling alone. Point-to-surface distance is
    queried in chunks sized to keep points*triangles under ``budget`` -- bounds
    peak memory (trimesh's closest-point is brute force).
    """
    a = trimesh.load(pa, process=False)
    b = trimesh.load(pb, process=False)

    def query_points(mesh):
        v = np.asarray(mesh.vertices)
        if len(v) >= n:                       # stride huge meshes
            return v[np.linspace(0, len(v) - 1, n).astype(int)]
        return np.vstack([v, mesh.sample(n - len(v))])

    def directed(src, dst):
        pts = query_points(src)
        chunk = max(256, budget // max(1, len(dst.faces)))
        m = 0.0
        for i in range(0, len(pts), chunk):
            _, d, _ = dst.nearest.on_surface(pts[i:i + chunk])
            m = max(m, float(d.max()))
        return m
    return max(directed(a, b), directed(b, a))


def classify(old, new, keys, tol=0.01):
    """Return ({changed mesh keys}, {key: hausdorff_mm})."""
    changed, devs = set(), {}
    # Cheap CRC32 pass first (zip CRC / file hash): an identical signature is an
    # unchanged mesh for free, so the expensive Hausdorff verify -- and the
    # per-key HTTP range fetch of the OLD release -- only runs on the meshes
    # whose bytes actually differ. Surface those counts up front so the verify
    # loop below reads as measurable progress, not a stall.
    to_verify = []
    for k in sorted(keys):
        c_old = old.crc(k)
        if c_old is None:
            changed.add(k)            # new part -> changed
            devs[k] = float("inf")
            continue
        if c_old == new.crc(k):
            continue                  # identical signature -> unchanged (free)
        to_verify.append(k)
    identical = len(keys) - len(changed) - len(to_verify)
    print(f"CRC pass: {len(changed)} new, {len(to_verify)} to geometry-verify, "
          f"{identical} identical (of {len(keys)} meshes)", flush=True)
    for i, k in enumerate(to_verify, 1):
        po, pn = old.stl(k), new.stl(k)
        d = _hausdorff(po, pn) if (po and pn) else float("inf")
        devs[k] = d
        verdict = "identical"
        if d > tol:
            changed.add(k)
            verdict = "CHANGED"
        print(f"  [{i}/{len(to_verify)}] verify {k:34s} ~Hausdorff={d:8.3f} mm "
              f"-> {verdict}", flush=True)
    return changed, devs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old", nargs="?", help="old release tag (shorthand)")
    ap.add_argument("new", nargs="?", help="new release tag (shorthand)")
    ap.add_argument("--old-release")
    ap.add_argument("--old-local")
    ap.add_argument("--new-release")
    ap.add_argument("--new-local")
    ap.add_argument("--out", default="/tmp/render_diff", type=Path)
    ap.add_argument("--summary-json", type=Path)
    ap.add_argument("--res", type=int, default=1600)
    ap.add_argument("--ghost-opacity", type=float, default=0.18)
    args = ap.parse_args()

    old_rel = args.old_release or args.old
    new_rel = args.new_release or args.new
    if not (old_rel or args.old_local) or not (new_rel or args.new_local):
        ap.error("need an old and a new source (tags or --*-local)")
    args.out.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    print(f"old: {old_rel or args.old_local}   new: {new_rel or args.new_local}")
    old = make_source(old_rel, args.old_local)
    new = make_source(new_rel, args.new_local)

    scene = new.scene()
    comps = scene["components"]
    keys = {(c.get("mesh") or c["part"]) for c in comps}
    print(f"scene: {len(comps)} components, {len(keys)} unique meshes")

    print("classifying changed meshes ...", flush=True)
    changed, devs = classify(old, new, keys)
    changed_bases = sorted({base_part(k) for k in changed})
    print(f"\nCHANGED parts ({len(changed_bases)}): "
          f"{', '.join(changed_bases) or '(none)'}\n", flush=True)

    # build the scene from the NEW bundle
    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=(args.res, args.res))
    pl.set_background("white")
    n_hi = 0
    for idx, c in enumerate(comps, 1):
        key = c.get("mesh") or c["part"]
        p = new.stl(key)
        if p is None:
            continue
        m = pv.read(p)
        m.transform(sw_matrix(c["xform"]), inplace=True)
        # colour by the EXACT mesh key (per-configuration): only the configs whose
        # own Hausdorff check changed go red, not every config of the base part.
        is_changed = key in changed
        n_hi += is_changed
        pl.add_mesh(m, color=HILITE if is_changed else GHOST,
                    opacity=1.0 if is_changed else args.ghost_opacity,
                    smooth_shading=True, specular=0.2,
                    backface_culling=not is_changed)
        if idx % 50 == 0 or idx == len(comps):
            print(f"  scene build {idx}/{len(comps)} instances ...", flush=True)
    print(f"highlighted {n_hi} component instances", flush=True)
    pl.add_text(f"{old.label} -> {new.label}  (red = changed geometry)",
                font_size=11, color="black")

    images = []
    views = (("iso", "iso"), ("front", "xy"), ("right", "yz"), ("top", "xz"))
    print(f"rendering {len(views)} camera views at {args.res}px ...", flush=True)
    for name, cpos in views:
        pl.camera_position = cpos
        if name == "iso":
            pl.camera.azimuth = 35
            pl.camera.elevation = 20
        pl.reset_camera()
        out = args.out / f"diff_{name}.png"
        pl.screenshot(str(out))
        images.append(out.name)
        print("wrote", out, flush=True)
    pl.close()

    summary = {
        "old": old.label, "new": new.label,
        "changed_parts": changed_bases,
        "changed_meshes": {k: (None if devs[k] == float("inf") else devs[k])
                           for k in sorted(changed)},
        "instances_highlighted": int(n_hi),
        "images": images,
    }
    sj = args.summary_json or (args.out / "diff_summary.json")
    sj.write_text(json.dumps(summary, indent=2))
    print("summary:", sj)


if __name__ == "__main__":
    main()
