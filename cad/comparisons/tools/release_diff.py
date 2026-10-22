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

The current identity map projects active and retired prior category identities,
composed with the sealed historical map for archived releases. Retirement reserves
release identities; it does not remove their historical pairings. A shared prior
vendor member can pair with every parent-specific clone without merging those
clones. Configuration suffixes and actual cache basenames are retained on both sides.
Overlapping identities in one bundle are rejected; new, deleted and renamed
members are separate from geometry verdicts. ``--parts`` accepts any mapped
historical or current spelling, but only members paired in both bundles.

    uv run cad/comparisons/tools/release_diff.py v0.1.1 v0.2.0
    uv run cad/comparisons/tools/release_diff.py v0.1.1 v0.2.0 --parts summing-lever,knife-mount
    uv run cad/comparisons/tools/release_diff.py v0.1.1 v0.2.0 --top 5   # auto-pick most-changed
"""

import argparse
import json
import re
import os
import struct
import urllib.request
import zlib
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

CACHE = Path(os.environ.get("RELEASE_DIFF_CACHE", "/tmp/release_diff_cache"))
IDENTITY_MAP = Path(__file__).resolve().parents[2] / "config" / "current-identity-map.json"
HISTORICAL_IDENTITY_MAP = IDENTITY_MAP.with_name("identity-migration-map.json")


def _check_stems(*stems):
    for stem in stems:
        if not isinstance(stem, str) or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", stem) is None:
            raise ValueError(f"identity map requires dashed lowercase stems: {stem!r}")


def load_identity_map(path=IDENTITY_MAP, historical_path=HISTORICAL_IDENTITY_MAP):
    """Map historical/prior stems to active or retired targets for comparisons only."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("release diff current identity map requires schema_version 1")
    mapping = {}
    targets = set()
    prior_numbers, target_numbers = set(), set()
    # Retired rows remain release provenance, not a source of active API entries.
    rows = payload["parts_and_assemblies"] + payload.get("retired_identities", [])
    for row in rows:
        old = row["old_stem"]
        current = tuple(identity["stem"] for identity in row["new_identities"])
        _check_stems(old, *current)
        if not current or old in mapping or len(set(current)) != len(current) or targets.intersection(current):
            raise ValueError(f"duplicate or empty current identity map entry: {old!r}, {current!r}")
        # Minimal stem-only maps remain useful for offline comparisons. Real rows
        # also reserve Numbers, independently in the prior and target namespaces.
        prior_number = row.get("old_number")
        if prior_number is not None:
            if prior_number in prior_numbers:
                raise ValueError(f"duplicate prior identity Number: {prior_number!r}")
            prior_numbers.add(prior_number)
        for identity in row["new_identities"]:
            number = identity.get("number")
            if number is not None:
                if number in target_numbers:
                    raise ValueError(f"duplicate target identity Number: {number!r}")
                target_numbers.add(number)
        mapping[old] = current
        targets.update(current)

    # These explicit post-v39 category changes bridge the sealed targets to the
    # prior vendor namespace. They are aliases only in historical comparisons.
    for row in payload.get("historical_current_aliases", []):
        old, prior, current = row["old_stem"], row["prior_current_stem"], row["current_stem"]
        _check_stems(old, prior, current)
        if current not in mapping.get(prior, ()):
            raise ValueError(f"historical alias has no current identity: {row!r}")
        if old in mapping and mapping[old] != (current,):
            raise ValueError(f"conflicting historical identity alias: {old!r}")
        mapping[old] = (current,)

    historical = json.loads(Path(historical_path).read_text(encoding="utf-8"))
    if historical.get("schema_version") != 2:
        raise ValueError("release diff historical identity map requires schema_version 2")
    old_stems, historical_targets = set(), set()
    for row in historical["identities"]:
        old, prior = row["old_stem"], row["new_stem"]
        if old is None:
            # Families introduced at that cutover have no archived counterpart.
            continue
        _check_stems(old, prior)
        if old in old_stems or prior in historical_targets:
            raise ValueError(f"duplicate historical identity map entry: {old!r}, {prior!r}")
        old_stems.add(old)
        historical_targets.add(prior)
        current = mapping.get(prior, (prior,))
        if old in mapping and mapping[old] != current:
            raise ValueError(f"conflicting historical identity alias: {old!r}")
        mapping[old] = current
    return mapping


def split_mesh_key(key):
    """Separate the exporter configuration, or a generated stretch qualifier."""
    stem, separator, configuration = key.partition("--")
    if separator:
        return stem, separator + configuration
    suffix = re.search(r"-stretch\d+$", key)
    return (key[:suffix.start()], suffix.group()) if suffix else (key, "")


def canonical_keys(key, mapping):
    """Project only the stem, retaining every target and the complete qualifier."""
    stem, suffix = split_mesh_key(key)
    stem = stem.lower()
    return tuple(target + suffix for target in mapping.get(stem, (stem,)))


def identity_inventory(keys, mapping):
    """Index projected identities; distinct current clones never collapse."""
    inventory = {}
    for actual in keys:
        for logical in canonical_keys(actual, mapping):
            if logical in inventory:
                raise ValueError(
                    f"duplicate logical identity {logical!r}: {inventory[logical]!r}, {actual!r}"
                )
            inventory[logical] = actual
    return inventory


def paired_keys(old_keys, new_keys, mapping):
    """Return every new-actual -> old-actual pair, reusing shared prior sources."""
    old = identity_inventory(old_keys, mapping)
    new = identity_inventory(new_keys, mapping)
    pairs = {}
    for logical, actual in new.items():
        if logical not in old:
            continue
        previous = old[logical]
        if actual in pairs and pairs[actual] != previous:
            raise ValueError(
                f"ambiguous prior identity for {actual!r}: {pairs[actual]!r}, {previous!r}"
            )
        pairs[actual] = previous
    return pairs


# --------------------------------------------------------------------------- #
# partial-zip reader (central directory + per-member range fetch)
# --------------------------------------------------------------------------- #
def _range_response(url, start, end):
    """Reject ignored/truncated ranges before reading a potentially huge asset."""
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)",
                             r.headers.get("Content-Range", ""))
        if r.status != 206 or match is None:
            raise ValueError(f"release asset did not honor HTTP range {start}-{end}")
        first, last, total = map(int, match.groups())
        if first != start or last != min(end, total - 1) or last < first:
            raise ValueError("release asset returned an inconsistent Content-Range")
        data = r.read(last - first + 2)
        if len(data) != last - first + 1:
            raise ValueError("release asset returned a truncated or oversized range")
        return data, total


def _get(url, start, end):
    return _range_response(url, start, end)[0]


def asset_url(tag):
    return ("https://github.com/pedropaulovc/harmonic-analyzer/releases/"
            f"download/{tag}/harmonic-analyzer-{tag}.zip")


def central_dir(url):
    _, total = _range_response(url, 0, 0)
    tail = _get(url, max(0, total - 65557), total - 1)
    eocd = tail.rfind(b"PK\x05\x06")
    if eocd < 0 or len(tail) - eocd < 22:
        raise ValueError("release asset has no valid ZIP end record")
    (_, disk, cd_disk, disk_entries, entries, cd_size, cd_off, comment) = struct.unpack(
        "<IHHHHIIH", tail[eocd:eocd + 22])
    if disk or cd_disk or disk_entries != entries or eocd + 22 + comment != len(tail):
        raise ValueError("release asset has an invalid or multi-disk ZIP directory")
    if cd_off == 0xFFFFFFFF:
        loc = tail.rfind(b"PK\x06\x07")
        z64 = struct.unpack("<Q", tail[loc + 8:loc + 16])[0]
        z = _get(url, z64, z64 + 56)
        cd_size = struct.unpack("<Q", z[40:48])[0]
        cd_off = struct.unpack("<Q", z[48:56])[0]
    if cd_off < 0 or cd_size < 0 or cd_off + cd_size > total:
        raise ValueError("release asset ZIP directory lies outside the asset")
    if not cd_size:
        if entries:
            raise ValueError("release asset has an empty ZIP directory with members")
        return {}
    cd = _get(url, cd_off, cd_off + cd_size - 1)
    out, p = {}, 0
    while p < len(cd):
        if cd[p:p + 4] != b"PK\x01\x02" or len(cd) - p < 46:
            raise ValueError("release asset has a malformed ZIP directory entry")
        f = struct.unpack("<IHHHHHHIIIHHHHHII", cd[p:p + 46])
        n, m, k = f[10], f[11], f[12]
        if p + 46 + n + m + k > len(cd):
            raise ValueError("release asset has a truncated ZIP directory entry")
        name = cd[p + 46:p + 46 + n].decode("utf-8" if f[3] & 0x800 else "cp437")
        if name in out:
            raise ValueError(f"duplicate release ZIP member: {name!r}")
        extra = cd[p + 46 + n:p + 46 + n + m]
        method, comp, uncomp, lho = f[4], f[8], f[9], f[16]
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
        out[name] = dict(name=name, method=method, comp=comp,
                         uncomp=uncomp, lho=lho, crc=f[7], flags=f[3])
        p += 46 + n + m + k
    if entries != 0xFFFF and len(out) != entries:
        raise ValueError("release asset ZIP directory member count does not match")
    return out


def extract(url, entry, dest):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size == entry["uncomp"]:
        if zlib.crc32(dest.read_bytes()) & 0xFFFFFFFF == entry["crc"]:
            return dest
    if entry.get("flags", 0) & 1 or entry["method"] not in (0, 8):
        raise ValueError(f"unsupported release ZIP member encoding: {entry['name']!r}")
    lh = _get(url, entry["lho"], entry["lho"] + 30 - 1)
    if lh[:4] != b"PK\x03\x04":
        raise ValueError("release ZIP member has no valid local header")
    flags, method = struct.unpack("<HH", lh[6:10])
    n, m = struct.unpack("<HH", lh[26:30])
    name = _get(url, entry["lho"] + 30, entry["lho"] + 30 + n - 1)
    name = name.decode("utf-8" if flags & 0x800 else "cp437")
    if name != entry["name"] or method != entry["method"] or flags != entry["flags"]:
        raise ValueError(f"release ZIP member identity mismatch: {entry['name']!r}")
    off = entry["lho"] + 30 + n + m
    raw = _get(url, off, off + entry["comp"] - 1) if entry["comp"] else b""
    if method == 0:
        data = raw
    else:
        inflater = zlib.decompressobj(-15)
        data = inflater.decompress(raw, entry["uncomp"] + 1)
        if not inflater.eof or inflater.unconsumed_tail or inflater.unused_data:
            raise ValueError(f"release ZIP member has invalid/oversized deflate data: {entry['name']!r}")
    if len(data) != entry["uncomp"] or zlib.crc32(data) & 0xFFFFFFFF != entry["crc"]:
        raise ValueError(f"release ZIP member size/CRC mismatch: {entry['name']!r}")
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


def boolean_cut(tag_a, tag_b, base_a, base_b):
    """Return removed/added material volumes (mm^3) via exact CAD booleans."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    a = read_step(CACHE / tag_a / f"{base_a}.step")
    b = read_step(CACHE / tag_b / f"{base_b}.step")
    va, vb = solid_volume(a), solid_volume(b)
    removed = solid_volume(BRepAlgoAPI_Cut(a, b).Shape())   # in A, not in B
    added = solid_volume(BRepAlgoAPI_Cut(b, a).Shape())     # in B, not in A
    return dict(vol_a=va, vol_b=vb, removed=removed, added=added,
                net=vb - va)


# --------------------------------------------------------------------------- #
# (3c) mesh deviation on STL meshes
# --------------------------------------------------------------------------- #
def _query_points(mesh, n=40000):
    """Deterministic feature points (vertices) + surface samples, capped at n.

    Vertices are corners/edges -- where the max surface deviation almost always
    sits -- so including them keeps a small local change from being missed when
    no random sample lands on it. Capped at n points (a huge mesh's vertices are
    strided deterministically) to bound work; samples top up the budget.
    """
    v = np.asarray(mesh.vertices)
    if len(v) >= n:
        return v[np.linspace(0, len(v) - 1, n).astype(int)]
    return np.vstack([v, mesh.sample(n - len(v))])


def _surface_dist(dst, pts, budget=4_000_000):
    """Nearest point-to-surface distance for each pt, chunked.

    trimesh's closest-point is brute force (O(points x triangles)), so query in
    chunks sized to keep points*triangles under ``budget`` -- bounds peak memory
    regardless of how many query points or triangles a mesh has.
    """
    chunk = max(256, budget // max(1, len(dst.faces)))
    out = np.empty(len(pts))
    for i in range(0, len(pts), chunk):
        _, d, _ = dst.nearest.on_surface(pts[i:i + chunk])
        out[i:i + chunk] = d
    return out


def _directed(src, dst):
    return _surface_dist(dst, _query_points(src))


def mesh_deviation(tag_a: str, tag_b: str, base_a: str, base_b: str) -> dict[str, Any]:
    a = trimesh.load(CACHE / tag_a / f"{base_a}.stl", process=False)
    b = trimesh.load(CACHE / tag_b / f"{base_b}.stl", process=False)
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
    ap.add_argument("--identity-map", type=Path, default=IDENTITY_MAP,
                    help="current schema-1 identity table (composed with sealed historical identities)")
    ap.add_argument("--top", type=int, default=0,
                    help="auto-select N parts with largest STEP byte delta")
    ap.add_argument("--no-boolean", action="store_true",
                    help="skip the (3b) STEP boolean cut")
    args = ap.parse_args()

    ua, ub = asset_url(args.tag_a), asset_url(args.tag_b)
    print("reading central directories ...", flush=True)
    ca, cb = central_dir(ua), central_dir(ub)

    mapping = load_identity_map(args.identity_map)

    def steps(cd):
        entries = [(Path(n).stem.lower(), e) for n, e in cd.items()
                   if n.lower().startswith("step/") and n.lower().endswith(".step")]
        identity_inventory((key for key, _ in entries), mapping)
        return dict(entries)
    sa, sb = steps(ca), steps(cb)
    pairs = paired_keys(sa, sb, mapping)
    common = sorted(pairs)
    added = sorted(set(sb) - set(pairs))
    deleted = sorted(set(sa) - set(pairs.values()))
    print(f"new parts: {', '.join(added) or '(none)'}")
    print(f"deleted parts: {', '.join(deleted) or '(none)'}")
    renamed = {new: old for new, old in pairs.items() if new != old}
    print(f"renamed parts: {renamed}")

    # CRC32 (from the central directory) is the change signal: a geometry edit can
    # rewrite coordinates while preserving the exact byte count, so STEP size is
    # NOT a reliable gate. Rank CRC-different parts by |size delta| only for a
    # stable, readable order.
    changed_crc = [k for k in common if sa[pairs[k]]["crc"] != sb[k]["crc"]]
    same_crc = [k for k in common if sa[pairs[k]]["crc"] == sb[k]["crc"]]
    changed_crc.sort(key=lambda k: -abs(sb[k]["uncomp"] - sa[pairs[k]]["uncomp"]))

    if args.parts:
        requested = {p.strip(): set(canonical_keys(p.strip(), mapping))
                     for p in args.parts.split(",")}
        candidates = {key: set(canonical_keys(key, mapping)) for key in common}
        parts = [key for key, logical in candidates.items()
                 if any(logical & selected for selected in requested.values())]
        missing = [name for name, selected in requested.items()
                   if not any(selected & candidates[key] for key in parts)]
        if missing:
            ap.error(f"requested parts are not paired in both bundles: {sorted(missing)}")
    elif args.top:
        parts = changed_crc[:args.top]
    else:
        # default: every CRC-changed part, capped, plus a CRC-identical control
        # so "identical" output is demonstrated too
        parts = changed_crc[:6]
        if same_crc:
            parts.append(same_crc[0])

    print(f"\n{args.tag_a} vs {args.tag_b}: {len(common)} common parts; "
          f"analyzing {len(parts)}: {', '.join(parts)}\n")

    for base in parts:
        base_a, base_b = pairs[base], base
        # fetch the two STEP + two STL members for this part, tracking which
        # (sub-folder) are present in BOTH bundles -- an analysis whose input is
        # missing from either side must be skipped, never run against a stale
        # cache file left by an earlier part.
        present = {"step": True, "stl": True}
        for sub, ext in (("step", ".step"), ("stl", ".stl")):
            for tag, url, cd, actual in (
                (args.tag_a, ua, ca, base_a), (args.tag_b, ub, cb, base_b),
            ):
                e = member(cd, sub, actual, ext)
                if e is None:
                    print(f"  !! {tag}: missing {sub}/{actual}{ext}")
                    present[sub] = False
                    continue
                extract(url, e, CACHE / tag / f"{actual}{ext}")

        print(f"### {base}")
        if not present["stl"]:
            print("  (3c) mesh:    SKIPPED (member missing from a bundle)")
        else:
            try:
                md = mesh_deviation(args.tag_a, args.tag_b, base_a, base_b)
                verdict = ("IDENTICAL (within mesh tol)"
                           if md["hausdorff_mm"] < 1e-3 else "CHANGED")
                print(f"  (3c) mesh:    ~Hausdorff={md['hausdorff_mm']:.4f} mm  "
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

        if not args.no_boolean and not present["step"]:
            print("  (3b) solid:   SKIPPED (member missing from a bundle)")
        elif not args.no_boolean:
            try:
                bc = boolean_cut(args.tag_a, args.tag_b, base_a, base_b)
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
