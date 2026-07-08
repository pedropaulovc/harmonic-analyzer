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
import json
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
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")
WORKER = TOOLS / "blender_worker.py"


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated pair ids")
    ap.add_argument("--model")
    ap.add_argument("--stale-only", action="store_true")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None

    manifest = composite.load_manifest()
    max_side = int(manifest.get("defaults", {}).get("width", 1600))
    by_model: dict[str, list[dict]] = {}
    for pair in manifest["pairs"]:
        if only and pair["id"] not in only:
            continue
        if args.model and pair["model"] != args.model:
            continue
        src, _geom = model_paths(pair["model"])
        if args.stale_only and not is_stale(pair, src):
            continue
        by_model.setdefault(pair["model"], []).append(pair)
    if not by_model:
        print("nothing to render")
        return 0

    n_total = sum(len(v) for v in by_model.values())
    print(f"offline-rendering {n_total} pairs across {len(by_model)} models", flush=True)
    rendered: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="harm_render_") as tmp:
        tmpdir = Path(tmp)
        for model, pairs in sorted(by_model.items()):
            src, geom = model_paths(model)
            jobs = []
            for pair in pairs:
                ref = composite.prepare_reference(pair)
                w, h = pair_size(ref, max_side)
                jobs.append({"id": pair["id"], "camera": pair["camera"],
                             "width": w, "height": h,
                             "out": str(tmpdir / f"{pair['id']}.png"),
                             "_size": (w, h)})
            job_file = tmpdir / f"{model}.json"
            job_file.write_text(json.dumps(
                geom | {"pairs": [{k: v for k, v in j.items() if k != "_size"}
                                  for j in jobs]}),
                encoding="utf-8")
            print(f"  {model}: {len(pairs)} pairs, blender starting ...", flush=True)
            proc = subprocess.run(
                [str(BLENDER), "-b", "--factory-startup", "-P", str(WORKER),
                 "--", str(job_file)],
                capture_output=True, text=True)
            if proc.returncode or "RENDERED" not in proc.stdout:
                print(proc.stdout[-3000:])
                print(proc.stderr[-2000:])
                raise RuntimeError(f"blender failed for {model}")

            for pair, j in zip(pairs, jobs, strict=True):
                png = Path(j["out"])
                img = Image.open(png).convert("RGBA")
                # background matches the reference photography: black studio
                # by default, reference.background overrides (e.g. "white"
                # for the white-backdrop book shots)
                bg = Image.new("RGB", img.size,
                               pair["reference"].get("background", "black"))
                bg.paste(img, mask=img.getchannel("A"))
                out = composite.pair_paths(pair["id"])["render"]
                out.parent.mkdir(parents=True, exist_ok=True)
                bg.save(out, **composite.JPEG_OPTS)
                composite.trim_render_file(
                    out, background=pair["reference"].get("background", "black"))
                _sidecar(pair["id"]).write_text(json.dumps({
                    "camera": pair["camera"], "reference": pair["reference"],
                    "size": list(j["_size"]), "model_mtime": src.stat().st_mtime,
                    "engine": "blender",
                    # exact uniform colour behind the render's pixels --
                    # composite._content_mask seeds its knockout flood from it
                    "render_bg": pair["reference"].get("background", "black"),
                }), encoding="utf-8")
                rendered.add(pair["id"])
                print(f"  OK  {pair['id']}", flush=True)

    composite.regenerate(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
