# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Offline (Blender) renderer for comparison pairs — no SolidWorks needed.

Consumes the STL/boxes render cache written by cad/scripts/export_models.py
and the same manifest cameras as cad/scripts/render_compare.py. One Blender
headless invocation per model renders all of its pairs; outputs are
white-composited, content-trimmed, and stored exactly like the SolidWorks
captures (same sidecars), then composites/scores are refreshed.

    uv run comparisons/tools/render_offline.py [--only id,..] [--model m]
                                               [--stale-only]
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import composite  # noqa: E402

REPO = composite.REPO
CAD_OUT = REPO / "cad" / "out"
WORKER = TOOLS / "blender_worker.py"
# Resolved LAZILY on first worker launch (blender_worker's render needs the >= 5.2
# gpu API), cached here. Deferred so the no-op path (nothing stale to render) never
# needs Blender, and so module consumers that import this without calling main()
# (comparisons/bench/render_server.py) still get a working path.
BLENDER: str | None = None
_BLENDER_OVERRIDE: str | None = None  # set by main() from --blender


def blender_exe() -> str:
    """Blender path, resolved on first call and cached in ``BLENDER``."""
    global BLENDER
    if BLENDER is None:
        BLENDER = resolve_blender(_BLENDER_OVERRIDE)
        print(f"blender: {BLENDER}", file=sys.stderr)
    return BLENDER


def resolve_blender(override: str | None = None) -> str:
    """Path to a Blender >= 5.2 for the headless worker.

    --blender / $HARMONIC_BLENDER win; else the highest >= 5.2 under the standard
    Windows install dir; else `blender` on PATH (Linux/macOS). Discovery (not a
    hard-coded version) is what lets the release's export stage refresh the gallery
    on whichever Blender the seat has -- a pinned "Blender 5.1" path silently broke
    it when that version was uninstalled."""
    cand = override or os.environ.get("HARMONIC_BLENDER")
    if cand:
        if not Path(cand).exists():
            raise SystemExit(f"Blender not found at {cand} (--blender / $HARMONIC_BLENDER)")
        return cand
    found = []
    for exe in glob.glob(r"C:/Program Files/Blender Foundation/Blender */blender.exe"):
        m = re.search(r"Blender (\d+)\.(\d+)", exe)
        if m and (int(m.group(1)), int(m.group(2))) >= (5, 2):
            found.append(((int(m.group(1)), int(m.group(2))), exe))
    if found:
        return max(found)[1]
    which = shutil.which("blender")
    if which:
        return which
    raise SystemExit(
        "no Blender >= 5.2 found; install it or set $HARMONIC_BLENDER / pass --blender")


STL_DIR = CAD_OUT / "stl"


def _stale(path: Path, src: Path, what: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — run cad/scripts/export_models.py")
    if path.stat().st_mtime < src.stat().st_mtime:
        raise RuntimeError(f"{what} older than {src.name} — re-run export_models.py")


def model_paths(model: str) -> tuple[Path, dict]:
    """(solidworks artefact, worker-job geometry fields).

    Parts: single STL + appearance RGB from colors.json. Assemblies: the
    boxes/scene JSON + the per-part STL dir (each referenced part checked
    against its own SLDPRT).
    """
    dashed = model.replace("_", "-")
    asm = CAD_OUT / "sldasm" / f"{dashed}.SLDASM"
    prt = CAD_OUT / "sldprt" / f"{dashed}.SLDPRT"
    if asm.exists():
        scene = CAD_OUT / "boxes" / f"{dashed}.json"
        _stale(scene, asm, scene.name)
        data = json.loads(scene.read_text(encoding="utf-8"))
        comps = data.get("components") or []
        if not comps or any("mesh" not in c for c in comps):
            raise RuntimeError(f"{scene.name} has no mesh scene graph — re-run export_models.py")
        for stem, mesh in {(c["part"], c["mesh"]) for c in comps}:
            part_src = CAD_OUT / "sldprt" / f"{stem}.SLDPRT"
            _stale(STL_DIR / f"{mesh}.STL", part_src, f"{mesh}.STL")
        return asm, {"scene": str(scene), "parts_dir": str(STL_DIR)}
    if not prt.exists():
        raise FileNotFoundError(f"no artefact for {model}")
    stl = STL_DIR / f"{dashed}.STL"
    _stale(stl, prt, stl.name)
    colors_file = STL_DIR / "colors.json"
    colors = json.loads(colors_file.read_text(encoding="utf-8")) if colors_file.exists() else {}
    return prt, {"stl": str(stl), "rgb": colors.get(dashed)}


def _sidecar(pair_id: str) -> Path:
    return composite.COMP / "render" / f"{pair_id}.meta.json"


def is_stale(pair: dict, src: Path) -> bool:
    img = composite.pair_paths(pair["id"])["render"]
    sc = _sidecar(pair["id"])
    if not img.exists() or not sc.exists():
        return True
    try:
        meta = json.loads(sc.read_text(encoding="utf-8"))
    except ValueError:
        return True  # truncated sidecar (interrupted run) -> re-render heals it
    return (
        meta.get("camera") != pair["camera"]
        or meta.get("reference") != pair["reference"]
        or meta.get("model_mtime") != src.stat().st_mtime
    )


def pair_size(ref_img: Path, max_side: int) -> tuple[int, int]:
    with Image.open(ref_img) as img:
        rw, rh = img.size
    scale = min(max_side * 1.4, 2400) / max(rw, rh)
    return max(1, round(rw * scale)), max(1, round(rh * scale))


def _run_worker(geom: dict, jobpairs: list[dict], tmpdir: Path, model: str,
                probe: bool = False) -> str:
    """Run one blender worker invocation; return stdout (raises on failure)."""
    job_file = tmpdir / f"{model}.{'probe' if probe else 'render'}.json"
    payload = geom | ({"probe": True} if probe else {}) | {"pairs": jobpairs}
    job_file.write_text(json.dumps(payload), encoding="utf-8")
    proc = subprocess.run(
        [blender_exe(), "-b", "--factory-startup", "-P", str(WORKER), "--", str(job_file)],
        capture_output=True, text=True)
    ok = proc.returncode == 0 and (probe or "RENDERED" in proc.stdout)
    if not ok:
        print(proc.stdout[-3000:])
        print(proc.stderr[-2000:])
        raise RuntimeError(f"blender {'probe' if probe else 'render'} failed for {model}")
    return proc.stdout


def _bench_paths(out_root: Path, pid: str) -> dict[str, Path]:
    return {"ref": out_root / "ref" / f"{pid}.jpg",
            "render": out_root / "render" / f"{pid}.jpg",
            "sidecar": out_root / "render" / f"{pid}.meta.json"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated pair ids")
    ap.add_argument("--model")
    ap.add_argument("--stale-only", action="store_true")
    # Bench (comparisons/bench) fixed-frame flags — see docs/pose-presentation-benchmark.md.
    ap.add_argument("--manifest", help="alternate manifest json (bench synthetic cases)")
    ap.add_argument("--out-root", help="write ref/render/sidecars under DIR/{ref,render}/ "
                    "instead of the shipping comparisons/ tree")
    ap.add_argument("--no-trim", action="store_true",
                    help="skip content-trim (fixed framing — trimming cancels target/zoom signal)")
    ap.add_argument("--canvas", help="fixed render canvas WxH (overrides per-ref sizing)")
    ap.add_argument("--fixed-frame", action="store_true",
                    help="honor each pair's frozen{need_w,canvas} — freeze the aim_camera fit")
    ap.add_argument("--skip-composites", action="store_true",
                    help="do not regenerate the gallery composites/scores")
    ap.add_argument("--probe-out", help="compute base framing per pair, write json, render nothing")
    ap.add_argument("--blender", help="Blender >= 5.2 exe (default: $HARMONIC_BLENDER or the "
                                      "highest installed)")
    args = ap.parse_args()
    # Stash the override only; resolve lazily on first worker launch (blender_exe),
    # so the no-op path (nothing stale) certifies a current gallery without needing
    # Blender installed on the seat.
    global _BLENDER_OVERRIDE
    _BLENDER_OVERRIDE = args.blender
    only = set(args.only.split(",")) if args.only else None
    out_root = Path(args.out_root) if args.out_root else None
    canvas = None
    if args.canvas:
        cw, ch = args.canvas.lower().split("x")
        canvas = (int(cw), int(ch))

    manifest = composite.load_manifest(Path(args.manifest)) if args.manifest \
        else composite.load_manifest()
    max_side = int(manifest.get("defaults", {}).get("width", 1600))
    by_model: dict[str, list[dict]] = {}
    for pair in manifest["pairs"]:
        if only and pair["id"] not in only:
            continue
        if args.model and pair["model"] != args.model:
            continue
        src, _geom = model_paths(pair["model"])
        if args.stale_only and not out_root and not is_stale(pair, src):
            continue
        by_model.setdefault(pair["model"], []).append(pair)
    if not by_model:
        print("nothing to render")
        return 0

    def size_for(pair) -> tuple[int, int]:
        if args.fixed_frame and pair.get("frozen", {}).get("canvas"):
            return tuple(pair["frozen"]["canvas"])
        if canvas:
            return canvas
        ref = composite.prepare_reference(
            pair, out=_bench_paths(out_root, pair["id"])["ref"] if out_root else None)
        return pair_size(ref, max_side)

    n_total = sum(len(v) for v in by_model.values())
    with tempfile.TemporaryDirectory(prefix="harm_render_") as tmp:
        tmpdir = Path(tmp)

        # --- probe mode: emit base framing, render nothing ---
        if args.probe_out:
            framing: dict[str, dict] = {}
            for model, pairs in sorted(by_model.items()):
                _src, geom = model_paths(model)
                sizes = {p["id"]: size_for(p) for p in pairs}
                jobpairs = [{"id": p["id"], "camera": p["camera"],
                             "width": sizes[p["id"]][0], "height": sizes[p["id"]][1]}
                            for p in pairs]
                out = _run_worker(geom, jobpairs, tmpdir, model, probe=True)
                for line in out.splitlines():
                    if line.startswith("PROBE "):
                        d = json.loads(line[6:])
                        d["canvas"] = list(sizes[d["id"]])
                        framing[d["id"]] = d
            Path(args.probe_out).write_text(json.dumps(framing, indent=1), encoding="utf-8")
            print(f"probe framing for {len(framing)} pairs -> {args.probe_out}", flush=True)
            return 0

        print(f"offline-rendering {n_total} pairs across {len(by_model)} models", flush=True)
        rendered: set[str] = set()
        for model, pairs in sorted(by_model.items()):
            src, geom = model_paths(model)
            jobs = []
            for pair in pairs:
                w, h = size_for(pair)
                job = {"id": pair["id"], "camera": pair["camera"], "width": w, "height": h,
                       "out": str(tmpdir / f"{pair['id'].replace('/', '_')}.png"), "_size": (w, h)}
                if args.fixed_frame and pair.get("frozen", {}).get("need_w") is not None:
                    job["frozen"] = {"need_w": pair["frozen"]["need_w"]}
                jobs.append(job)
            print(f"  {model}: {len(pairs)} pairs, blender starting ...", flush=True)
            out = _run_worker(geom, [{k: v for k, v in j.items() if k != "_size"} for j in jobs],
                              tmpdir, model)
            del out
            for pair, j in zip(pairs, jobs, strict=True):
                img = Image.open(Path(j["out"])).convert("RGBA")
                bg = Image.new("RGB", img.size, pair["reference"].get("background", "black"))
                bg.paste(img, mask=img.getchannel("A"))
                paths = _bench_paths(out_root, pair["id"]) if out_root \
                    else {"render": composite.pair_paths(pair["id"])["render"],
                          "sidecar": _sidecar(pair["id"])}
                paths["render"].parent.mkdir(parents=True, exist_ok=True)
                bg.save(paths["render"], **composite.JPEG_OPTS)
                if not args.no_trim:
                    composite.trim_render_file(
                        paths["render"],
                        background=pair["reference"].get("background", "black"))
                paths["sidecar"].write_text(json.dumps({
                    "camera": pair["camera"], "reference": pair["reference"],
                    "size": list(j["_size"]), "model_mtime": src.stat().st_mtime,
                    "engine": "blender",
                    # exact uniform colour behind the render's pixels --
                    # composite._content_mask seeds its knockout flood from it
                    "render_bg": pair["reference"].get("background", "black"),
                }), encoding="utf-8")
                rendered.add(pair["id"])
                print(f"  OK  {pair['id']}", flush=True)

    if not args.skip_composites and not out_root:
        composite.regenerate(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
