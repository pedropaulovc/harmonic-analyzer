# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Interactive pose editor — orbit/pan/zoom a pair's camera over its photo.

    uv run comparisons/tools/pose_edit.py <pair-id>
    uv run comparisons/tools/pose_edit.py --selftest

Opens windowed Blender on the pair's exact render scene with the reference
photo as a half-transparent camera background. The viewport is locked to the
render camera, so normal navigation (orbit = tilt, pan, sidebar ortho-scale =
zoom) IS the pose adjustment. Press N -> "Pose" tab -> "Save pose to
manifest" to write az/el/roll + target_mm + zoom back to the pair; the
sidecar staleness check then re-renders it on the next

    uv run comparisons/tools/render_offline.py --stale-only

and tune_align --write re-fits the residual 2D alignment if wanted.
--selftest round-trips compose->decompose over a pose grid (headless).
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import composite  # noqa: E402
import render_offline  # noqa: E402

WORKER = TOOLS / "pose_edit_worker.py"
BLENDER = render_offline.BLENDER


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pair_id", nargs="?")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        proc = subprocess.run(
            [str(BLENDER), "-b", "--factory-startup", "--python", str(WORKER),
             "--", "selftest"], capture_output=True, text=True)
        print(proc.stdout[-2000:])
        if proc.returncode or "SELFTEST OK" not in proc.stdout:
            print(proc.stderr[-2000:])
            return 1
        return 0

    if not args.pair_id:
        print("pair id required (or --selftest)")
        return 2
    manifest = composite.load_manifest()
    pair = next((p for p in manifest["pairs"] if p["id"] == args.pair_id), None)
    if pair is None:
        print(f"no pair {args.pair_id!r} in manifest")
        return 2

    src, geom = render_offline.model_paths(pair["model"])
    ref = composite.prepare_reference(pair)
    max_side = int(manifest.get("defaults", {}).get("width", 1600))
    w, h = render_offline.pair_size(ref, max_side)

    with tempfile.TemporaryDirectory(prefix="pose_edit_") as tmp:
        job_file = Path(tmp) / "job.json"
        job_file.write_text(json.dumps(geom | {
            "pair_id": pair["id"], "camera": pair["camera"],
            "width": w, "height": h, "ref": str(ref),
            "manifest": str(composite.MANIFEST),
        }), encoding="utf-8")
        print(f"opening {pair['id']} in Blender — N panel > Pose > Save pose")
        proc = subprocess.run([str(BLENDER), "--python", str(WORKER),
                               "--", str(job_file)], capture_output=True, text=True)
    saved = [ln for ln in proc.stdout.splitlines() if ln.startswith("POSE SAVED")]
    for ln in saved:
        print(ln)
    if not saved:
        print("no pose saved (Blender closed without Save)")
        return 0
    print("next: uv run comparisons/tools/render_offline.py --stale-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
