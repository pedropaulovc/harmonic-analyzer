# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "numpy"]
# ///
"""Aggressive camera + 2D-align search for the photo-vs-CAD comparison pairs.

Coordinate descent on each pair's camera (az, el, roll, focal_length_mm) with
the 2D align (scale/dx/dy) re-optimised (silhouette IoU) for every candidate.
Objective = RMS mismatch (composite.score_pair; LOWER is better), tie-broken by
higher IoU. Stops after `--patience` consecutive rounds with no global mean-RMS
improvement.

Efficiency: every candidate camera for EVERY pair in a round is rendered in ONE
Blender invocation (Blender startup, not per-frame render, is the cost), then
scored on CPU. Best params per pair are written back to the manifest each round
so a crash/stop leaves the manifest at the best-so-far.

    uv run comparisons/tools/search_camera.py [--only id,..] [--patience 5]
        [--rounds 100] [--axes az,el,roll,focal] [--steps az=4,el=3,roll=1,focal=15]

Engine: offline Blender (scores only comparable within one engine).
"""
import argparse
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import composite  # noqa: E402
import render_offline  # noqa: E402

WORK_H = 240          # align-search resolution (matches tune_align)
REF_THRESH = 40       # ref silhouette = brighter than this on the black studio bg
CLAMP = {"focal_length_mm": (35.0, 400.0), "el_deg": (-89.0, 89.0)}


# --------------------------------------------------------------------------- #
# scoring on explicit image paths (composite.* are pair_id-bound)
# --------------------------------------------------------------------------- #
def _crop_to_content(render_path: Path):
    ren = Image.open(render_path)
    mask = composite._content_mask(ren)
    bbox = mask.getbbox() or (0, 0, ren.width, ren.height)
    return ren.crop(bbox), mask.crop(bbox)


def _fit(ren, mask, ref_size, align):
    rw, rh = ref_size
    s = min(rw / ren.width, rh / ren.height) * align.get("scale", 1.0)
    w, h = max(1, round(ren.width * s)), max(1, round(ren.height * s))
    r = ren.resize((w, h), Image.LANCZOS)
    m = mask.resize((w, h), Image.NEAREST)
    dx = align.get("dx_px", 0) + (rw - w) // 2
    dy = align.get("dy_px", 0) + (rh - h) // 2
    return r, m, (dx, dy)


def score_align(render_path: Path, ref_path: Path, align: dict) -> tuple[float, float]:
    """(RMS, IoU) for a render+align against a ref, full resolution (numpy)."""
    ref = Image.open(ref_path).convert("L")
    ren, mask = _crop_to_content(render_path)
    r, m, off = _fit(ren, mask, ref.size, align)
    canvas = Image.new("L", ref.size, 0)
    canvas.paste(r.convert("L"), off)
    mcanvas = Image.new("L", ref.size, 0)
    mcanvas.paste(m, off)
    refa = np.asarray(ref, dtype=np.int16)
    cana = np.asarray(canvas, dtype=np.int16)
    mma = np.asarray(mcanvas, dtype=bool)
    rma = refa > REF_THRESH
    n = int(mma.sum())
    rms = float(np.sqrt((((refa - cana)[mma]) ** 2).mean())) if n else 999.0
    union = int((mma | rma).sum())
    iou = int((mma & rma).sum()) / union if union else 0.0
    return round(rms, 2), round(iou, 4)


def best_align(render_path: Path, ref_path: Path) -> dict:
    """Coarse+refine IoU grid (mirrors tune_align) -> align dict (full-res px), numpy."""
    ref = Image.open(ref_path).convert("L")
    rw, rh = ref.size
    small = (max(1, round(rw * WORK_H / rh)), WORK_H)
    refmask = np.asarray(ref.resize(small, Image.BILINEAR), dtype=np.int16) > REF_THRESH
    _ren, mask = _crop_to_content(render_path)
    s0 = min(small[0] / mask.width, small[1] / mask.height)
    base = mask.resize((max(1, round(mask.width * s0)), max(1, round(mask.height * s0))),
                       Image.NEAREST)
    sw, sh = small

    def iou(scale, dx, dy):
        w = max(1, round(base.width * scale))
        h = max(1, round(base.height * scale))
        canvas = Image.new("L", small, 0)
        canvas.paste(base.resize((w, h), Image.NEAREST),
                     ((sw - w) // 2 + dx, (sh - h) // 2 + dy))
        m = np.asarray(canvas, dtype=bool)
        union = int((m | refmask).sum())
        return int((m & refmask).sum()) / union if union else 0.0

    best, best_iou = (1.0, 0, 0), -1.0
    for k100 in range(80, 185, 5):
        for dx in range(-48, 49, 8):
            for dy in range(-48, 49, 8):
                v = iou(k100 / 100, dx, dy)
                if v > best_iou:
                    best_iou, best = v, (k100 / 100, dx, dy)
    k, bdx, bdy = best
    for k100 in range(round(k * 100) - 4, round(k * 100) + 5, 2):
        for dx in range(bdx - 7, bdx + 8, 2):
            for dy in range(bdy - 7, bdy + 8, 2):
                v = iou(k100 / 100, dx, dy)
                if v > best_iou:
                    best_iou, best = v, (k100 / 100, dx, dy)
    k, dx, dy = best
    up = rh / WORK_H
    return {"scale": round(k, 3), "dx_px": round(dx * up), "dy_px": round(dy * up)}


# --------------------------------------------------------------------------- #
# candidate generation
# --------------------------------------------------------------------------- #
def cam_get(cam: dict, axis: str) -> float:
    if axis == "focal":
        return float((cam.get("perspective") or {}).get("focal_length_mm") or 100.0)
    return float(cam.get(f"{axis}_deg", 0.0))


def cam_set(cam: dict, axis: str, val: float) -> dict:
    c = copy.deepcopy(cam)
    if axis == "focal":
        lo, hi = CLAMP["focal_length_mm"]
        c.setdefault("perspective", {})
        c["perspective"] = dict(c.get("perspective") or {})
        c["perspective"]["focal_length_mm"] = round(min(hi, max(lo, val)), 2)
        return c
    key = f"{axis}_deg"
    if axis == "el":
        lo, hi = CLAMP["el_deg"]
        val = min(hi, max(lo, val))
    c[key] = round(val, 2)
    return c


def candidates(cam: dict, axes: list[str], steps: dict[str, float]) -> list[tuple[str, dict]]:
    """current + (axis +/- step) for each axis. Labelled for the render job."""
    out = [("base", copy.deepcopy(cam))]
    for ax in axes:
        v = cam_get(cam, ax)
        for sgn in (+1, -1):
            out.append((f"{ax}{'+' if sgn > 0 else '-'}{steps[ax]}",
                        cam_set(cam, ax, v + sgn * steps[ax])))
    return out


# --------------------------------------------------------------------------- #
def render_batch(model: str, jobs: list[dict], tmpdir: Path) -> None:
    """One Blender invocation rendering every candidate in `jobs`."""
    _src, geom = render_offline.model_paths(model)
    job_file = tmpdir / f"{model}.job.json"
    job_file.write_text(json.dumps(geom | {"pairs": jobs}), encoding="utf-8")
    proc = subprocess.run(
        [str(render_offline.BLENDER), "-b", "--factory-startup", "-P",
         str(render_offline.WORKER), "--", str(job_file)],
        capture_output=True, text=True)
    if proc.returncode or "RENDERED" not in proc.stdout:
        print(proc.stdout[-2000:])
        print(proc.stderr[-1500:])
        raise RuntimeError(f"blender failed for {model}")
    # black-composite + content-trim every candidate PNG, like render_offline
    for j in jobs:
        png = Path(j["out"])
        img = Image.open(png).convert("RGBA")
        bg = Image.new("RGB", img.size, "black")
        bg.paste(img, mask=img.getchannel("A"))
        bg.save(png, **composite.JPEG_OPTS)
        composite.trim_render_file(png)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--rounds", type=int, default=100)
    ap.add_argument("--axes", default="az,el,roll,focal")
    ap.add_argument("--steps", default="az=4,el=3,roll=1,focal=20")
    ap.add_argument("--min-step", type=float, default=0.5,
                    help="halve a stalled axis step until below this, then drop it")
    ap.add_argument("--search-h", type=int, default=700,
                    help="candidate render height for ranking (final winner is "
                         "re-rendered full-res by render_offline)")
    args = ap.parse_args()
    axes = args.axes.split(",")
    steps0 = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in args.steps.split(",")}
    only = set(args.only.split(",")) if args.only else None

    manifest = composite.load_manifest()
    pairs = [p for p in manifest["pairs"] if not only or p["id"] in only]
    max_side = int(manifest.get("defaults", {}).get("width", 1600))

    # per-pair live state: best camera, best align, best rms/iou, per-axis step
    state = {}
    for p in pairs:
        ref = composite.prepare_reference(p)
        cam = copy.deepcopy(p["camera"])
        # fresh align for the current (base) camera's on-disk render, so base is
        # scored on equal footing with candidates (which all get a fresh align).
        align = best_align(composite.pair_paths(p["id"])["render"], ref)
        rms, iou = score_align(composite.pair_paths(p["id"])["render"], ref, align)
        state[p["id"]] = {"cam": cam, "align": align, "rms": rms, "iou": iou,
                          "ref": ref, "model": p["model"],
                          "steps": dict(steps0), "size": render_offline.pair_size(ref, max_side)}
        print(f"  start {p['id']}: RMS {rms} IoU {iou}", flush=True)

    def mean_rms():
        return sum(s["rms"] for s in state.values()) / len(state)

    print(f"START mean RMS {mean_rms():.2f}", flush=True)
    stale = 0
    with tempfile.TemporaryDirectory(prefix="cam_search_") as tmp:
        tmpdir = Path(tmp)
        for rnd in range(1, args.rounds + 1):
            improved_global = False
            # one render job across ALL pairs' candidates this round
            jobs, meta = [], {}
            for p in pairs:
                st = state[p["id"]]
                act_axes = [a for a in axes if st["steps"][a] >= args.min_step]
                if not act_axes:
                    continue
                w, h = st["size"]
                for label, cam in candidates(st["cam"], act_axes, st["steps"]):
                    cid = f"{p['id']}@@{label}"
                    out = tmpdir / f"{cid.replace('/', '_')}.png"
                    jobs.append({"id": cid, "camera": cam, "width": w, "height": h,
                                 "out": str(out)})
                    meta[cid] = (p["id"], label, cam, out)
            if not jobs:
                print("all axes converged", flush=True)
                break
            by_model = {}
            for j in jobs:
                pid = j["id"].split("@@")[0]
                by_model.setdefault(state[pid]["model"], []).append(j)
            for model, mjobs in by_model.items():
                render_batch(model, mjobs, tmpdir)

            # score every candidate; adopt the best per pair
            for p in pairs:
                st = state[p["id"]]
                cur_best = (st["rms"], -st["iou"], "base", st["cam"], st["align"])
                for cid, (pid, label, cam, out) in meta.items():
                    if pid != p["id"]:
                        continue
                    if not Path(out).exists():
                        continue
                    align = best_align(out, st["ref"])
                    rms, iou = score_align(out, st["ref"], align)
                    if (rms, -iou) < (cur_best[0], cur_best[1]):
                        cur_best = (rms, -iou, label, cam, align)
                if cur_best[2] != "base":
                    st["rms"], st["iou"] = cur_best[0], -cur_best[1]
                    st["cam"], st["align"] = cur_best[3], cur_best[4]
                    improved_global = True
                    print(f"  r{rnd} {p['id']}: -> RMS {st['rms']} IoU {st['iou']}"
                          f"  via {cur_best[2]}", flush=True)
                else:
                    # no axis helped at current steps -> halve them all
                    for a in axes:
                        st["steps"][a] = round(st["steps"][a] / 2, 3)

            # write best-so-far back to manifest every round
            for p in manifest["pairs"]:
                if p["id"] in state:
                    p["camera"] = state[p["id"]]["cam"]
                    p["align"] = state[p["id"]]["align"]
            composite.MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

            m = mean_rms()
            stale = 0 if improved_global else stale + 1
            print(f"ROUND {rnd}: mean RMS {m:.2f}  (stale {stale}/{args.patience})", flush=True)
            if stale >= args.patience:
                print(f"STOP: no improvement in {args.patience} rounds", flush=True)
                break

    print(f"FINAL mean RMS {mean_rms():.2f}", flush=True)
    for pid, s in sorted(state.items()):
        print(f"  {pid}: RMS {s['rms']} IoU {s['iou']}  cam {s['cam']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
