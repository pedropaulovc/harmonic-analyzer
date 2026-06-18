# /// script
# requires-python = ">=3.11"
# dependencies = ["cadquery-ocp", "trimesh", "rtree", "numpy", "scipy"]
# ///
"""Geometry diff between two release CAD bundles (e.g. v0.1.1 vs v0.2.0).

Two ID-independent comparisons per part, neither of which cares about STEP
entity renumbering or line order:

  (3b) BOOLEAN CUT on the STEP solids -- exact "what changed":
       removed = volume(A - B), added = volume(B - A). Both ~0  => identical
       solids; the leftovers are exactly the material that came/went.

  (3c) MESH DEVIATION on the STL meshes -- tolerance-based "how much / where":
       symmetric Hausdorff distance (max of directed A->B and B->A nearest-
       surface distances) plus mean deviation, in mm.

Bundles are read straight from the GitHub release zips over HTTP range
requests -- only the central directory and the needed members are fetched,
never the whole 460 MB asset.

    uv run comparisons/tools/release_diff.py v0.1.1 v0.2.0
    uv run comparisons/tools/release_diff.py v0.1.1 v0.2.0 --parts summing-lever,knife-mount
    uv run comparisons/tools/release_diff.py v0.1.1 v0.2.0 --top 5   # auto-pick most-changed
"""

import argparse
import os
import struct
import sys
import urllib.request
import zlib
from pathlib import Path

import numpy as np
import trimesh

CACHE = Path(os.environ.get("RELEASE_DIFF_CACHE", "/tmp/release_diff_cache"))


# --------------------------------------------------------------------------- #
# partial-zip reader (central directory + per-member range fetch)
# --------------------------------------------------------------------------- #
def _get(url, start, end):
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req) as r:
        return r.read()


def asset_url(tag):
    return ("https://github.com/pedropaulovc/harmonic-analyzer/releases/"
            f"download/{tag}/harmonic-analyzer-{tag}.zip")


def central_dir(url):
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req) as r:
        total = int(r.headers["Content-Range"].split("/")[1])
    tail = _get(url, max(0, total - 65536), total - 1)
    eocd = tail.rfind(b"PK\x05\x06")
    (_, _, _, _, _, cd_size, cd_off, _) = struct.unpack(
        "<IHHHHIIH", tail[eocd:eocd + 22])
    if cd_off == 0xFFFFFFFF:
        loc = tail.rfind(b"PK\x06\x07")
        z64 = struct.unpack("<Q", tail[loc + 8:loc + 16])[0]
        z = _get(url, z64, z64 + 56)
        cd_size = struct.unpack("<Q", z[40:48])[0]
        cd_off = struct.unpack("<Q", z[48:56])[0]
    cd = _get(url, cd_off, cd_off + cd_size - 1)
    out, p = {}, 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        f = struct.unpack("<IHHHHHHIIIHHHHHII", cd[p:p + 46])
        n, m, k = f[10], f[11], f[12]
        name = cd[p + 46:p + 46 + n].decode("utf-8", "replace")
        extra = cd[p + 46 + n:p + 46 + n + m]
        method, comp, uncomp, lho = f[4], f[8], f[9], f[16]
        ep = 0
        while ep + 4 <= len(extra):
            hid, hsz = struct.unpack("<HH", extra[ep:ep + 4])
            blk, bp = extra[ep + 4:ep + 4 + hsz], 0
            if hid == 1:
                if uncomp == 0xFFFFFFFF:
                    uncomp = struct.unpack("<Q", blk[bp:bp + 8])[0]; bp += 8
                if comp == 0xFFFFFFFF:
                    comp = struct.unpack("<Q", blk[bp:bp + 8])[0]; bp += 8
                if lho == 0xFFFFFFFF:
                    lho = struct.unpack("<Q", blk[bp:bp + 8])[0]; bp += 8
            ep += 4 + hsz
        out[name] = dict(name=name, method=method, comp=comp,
                         uncomp=uncomp, lho=lho)
        p += 46 + n + m + k
    return out


def extract(url, entry, dest):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size == entry["uncomp"]:
        return dest
    lh = _get(url, entry["lho"], entry["lho"] + 30 - 1)
    n, m = struct.unpack("<HH", lh[26:30])
    off = entry["lho"] + 30 + n + m
    raw = _get(url, off, off + entry["comp"] - 1)
    data = raw if entry["method"] == 0 else zlib.decompress(raw, -15)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def member(cd, sub, base, ext):
    for cand in (f"{sub}/{base}{ext}", f"{sub}/{base}{ext.upper()}"):
        for name, e in cd.items():
            if name.lower() == cand.lower():
                return e
    return None


# --------------------------------------------------------------------------- #
# (3b) boolean-cut on STEP solids
# --------------------------------------------------------------------------- #
def read_step(path):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_ReturnStatus
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed: {path}")
    reader.TransferRoots()
    return reader.OneShape()


def solid_volume(shape):
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return props.Mass()  # mm^3


def boolean_cut(tag_a, tag_b, base):
    """Return removed/added material volumes (mm^3) via exact CAD booleans."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    a = read_step(CACHE / tag_a / f"{base}.step")
    b = read_step(CACHE / tag_b / f"{base}.step")
    va, vb = solid_volume(a), solid_volume(b)
    removed = solid_volume(BRepAlgoAPI_Cut(a, b).Shape())   # in A, not in B
    added = solid_volume(BRepAlgoAPI_Cut(b, a).Shape())     # in B, not in A
    return dict(vol_a=va, vol_b=vb, removed=removed, added=added,
                net=vb - va)


# --------------------------------------------------------------------------- #
# (3c) mesh deviation on STL meshes
# --------------------------------------------------------------------------- #
def _directed(src, dst, n=60000):
    pts = src.sample(min(n, max(2000, len(src.vertices))))
    _, dist, _ = dst.nearest.on_surface(pts)
    return dist


def mesh_deviation(tag_a, tag_b, base):
    a = trimesh.load(CACHE / tag_a / f"{base}.stl", process=False)
    b = trimesh.load(CACHE / tag_b / f"{base}.stl", process=False)
    d_ab = _directed(a, b)
    d_ba = _directed(b, a)
    hausdorff = float(max(d_ab.max(), d_ba.max()))
    mean_dev = float((d_ab.mean() + d_ba.mean()) / 2)
    return dict(
        hausdorff_mm=hausdorff,
        mean_dev_mm=mean_dev,
        vol_a_mm3=float(a.volume), vol_b_mm3=float(b.volume),
        area_a_mm2=float(a.area), area_b_mm2=float(b.area),
        bbox_a=a.extents.tolist(), bbox_b=b.extents.tolist(),
        tris_a=len(a.faces), tris_b=len(b.faces))


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag_a")
    ap.add_argument("tag_b")
    ap.add_argument("--parts", help="comma-separated part basenames")
    ap.add_argument("--top", type=int, default=0,
                    help="auto-select N parts with largest STEP byte delta")
    ap.add_argument("--no-boolean", action="store_true",
                    help="skip the (3b) STEP boolean cut")
    args = ap.parse_args()

    ua, ub = asset_url(args.tag_a), asset_url(args.tag_b)
    print(f"reading central directories ...", flush=True)
    ca, cb = central_dir(ua), central_dir(ub)

    def steps(cd):
        return {Path(n).stem.lower(): e for n, e in cd.items()
                if n.lower().startswith("step/") and n.lower().endswith(".step")}
    sa, sb = steps(ca), steps(cb)
    common = sorted(set(sa) & set(sb))

    # free signal: STEP uncompressed-size delta, used for --top ranking
    deltas = sorted(((k, sb[k]["uncomp"] - sa[k]["uncomp"]) for k in common),
                    key=lambda r: -abs(r[1]))

    if args.parts:
        parts = [p.strip().lower() for p in args.parts.split(",")]
    elif args.top:
        parts = [k for k, _ in deltas[:args.top]]
    else:
        # default: every part whose STEP size moved at all, capped, plus a
        # zero-delta control so "identical" output is demonstrated too
        parts = [k for k, d in deltas if d != 0][:6]
        ctrl = next((k for k, d in deltas if d == 0), None)
        if ctrl:
            parts.append(ctrl)

    print(f"\n{args.tag_a} vs {args.tag_b}: {len(common)} common parts; "
          f"analyzing {len(parts)}: {', '.join(parts)}\n")

    for base in parts:
        # fetch the two STEP + two STL members for this part
        for tag, url, cd in ((args.tag_a, ua, ca), (args.tag_b, ub, cb)):
            for sub, ext in (("step", ".step"), ("stl", ".stl")):
                e = member(cd, sub, base, ext)
                if e is None:
                    print(f"  !! {tag}: missing {sub}/{base}{ext}")
                    continue
                extract(url, e, CACHE / tag / f"{base}{ext}")

        print(f"### {base}")
        try:
            md = mesh_deviation(args.tag_a, args.tag_b, base)
            verdict = ("IDENTICAL (within mesh tol)"
                       if md["hausdorff_mm"] < 1e-3 else "CHANGED")
            print(f"  (3c) mesh:    Hausdorff={md['hausdorff_mm']:.4f} mm  "
                  f"mean={md['mean_dev_mm']:.5f} mm  -> {verdict}")
            print(f"               vol {md['vol_a_mm3']:.1f} -> "
                  f"{md['vol_b_mm3']:.1f} mm^3 "
                  f"({md['vol_b_mm3'] - md['vol_a_mm3']:+.1f})   "
                  f"tris {md['tris_a']} -> {md['tris_b']}")
            bb_a = "x".join(f"{v:.1f}" for v in md["bbox_a"])
            bb_b = "x".join(f"{v:.1f}" for v in md["bbox_b"])
            print(f"               bbox {bb_a} -> {bb_b} mm")
        except Exception as ex:
            print(f"  (3c) mesh:    FAILED ({ex})")

        if not args.no_boolean:
            try:
                bc = boolean_cut(args.tag_a, args.tag_b, base)
                eq = bc["removed"] < 1e-3 and bc["added"] < 1e-3
                print(f"  (3b) solid:   removed={bc['removed']:.2f} mm^3  "
                      f"added={bc['added']:.2f} mm^3  net={bc['net']:+.2f} mm^3 "
                      f"-> {'IDENTICAL solids' if eq else 'CHANGED'}")
                print(f"               vol {bc['vol_a']:.1f} -> "
                      f"{bc['vol_b']:.1f} mm^3")
            except Exception as ex:
                print(f"  (3b) solid:   FAILED ({ex})")
        print()


if __name__ == "__main__":
    main()
