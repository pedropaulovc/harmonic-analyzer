# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Generate the pose-presentation-benchmark case grid (docs/pose-presentation-benchmark.md).

Perturbs the manifest cameras one parameter at a time (plus a seeded mixed
tier and an unperturbed control), converts image-plane target deltas to
world-space along the *unperturbed* camera's right/up basis, freezes the
aim_camera fit (target0 / need_w0 / canvas) so a rotation/target/zoom
perturbation moves the model in a fixed frame instead of silently re-fitting,
and renders every case through render_offline.py's fixed-frame path.

Ground truth is written to comparisons/bench/cases.jsonl (TRACKED — never under
the ignored out/): case_id -> delta, the rendered camera, the frozen frame, and
the base r/u basis the scorer needs to interpret target reads. Stimuli land
under --out-root/render/ with the case id as filename; presentations.py builds
the per-arm sheets from ref+render, run.py serves them under opaque ids.

    uv run comparisons/bench/gen_cases.py            # 6 first-pass pairs, 45 cases each
    uv run comparisons/bench/gen_cases.py --all      # all 18 manifest pairs
    uv run comparisons/bench/gen_cases.py --pairs id1,id2 --no-render   # regen ground truth only
"""

import argparse
import json
import math
import random
import subprocess
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
TOOLS = BENCH.parent / "tools"
REPO = BENCH.parents[1]
sys.path.insert(0, str(TOOLS))
import composite  # noqa: E402

CASES_JSONL = BENCH / "cases.jsonl"          # tracked ground truth
DEFAULT_OUT = BENCH / "out"

# The 6 stratified first-pass pairs (docs runbook step 3), manifest-exact ids.
FIRST_PASS_PAIRS = [
    "harmonic_analyzer--ch30-p002-img01",   # wide, dark
    "harmonic_analyzer--ch30-p007-img01",   # wide, dark, oblique
    "harmonic_analyzer--ch12-p002-img09",   # macro, dark
    "harmonic_analyzer--ch12-p001-img02",   # macro, white bg
    "harmonic_analyzer--ch17-p002-img06",   # macro, occlusion-heavy
    "harmonic_analyzer--ch23-p004-img02",   # down-look macro
]

# Perturbation grid — full 45/pair (generation renders the full grid once so
# T3's ±1/±7/±5 levels exist even though the T1 sub-grid is a subset).
ROT_LEVELS = [-15, -7, -3, -1, 1, 3, 7, 15]          # deg, per az/el/roll
TGT_LEVELS = [-40, -15, -5, 5, 15, 40]               # mm, per target-x/target-y
ZOOM_LEVELS = [0.85, 1.18]                           # multiplicative factors
N_MIXED = 6                                          # seeded 2-3 param combos

# Uniform pools the mixed tier samples from (single-parameter levels above).
MIXED_POOL = {
    "az_deg": ROT_LEVELS, "el_deg": ROT_LEVELS, "roll_deg": ROT_LEVELS,
    "tx_mm": TGT_LEVELS, "ty_mm": TGT_LEVELS, "zoom": ZOOM_LEVELS,
}


# --- camera basis (replicated from blender_worker.camera_axes; that module
# imports bpy so cannot be imported here — keep the two in lockstep) ----------
def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def camera_axes(az_deg, el_deg, roll_deg=0.0):
    az, el, roll = (math.radians(v) for v in (az_deg, el_deg, roll_deg))
    o = (math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))
    if abs(math.cos(el)) < 1e-9:
        up = (0.0, 0.0, -1.0) if el > 0 else (0.0, 0.0, 1.0)
    else:
        up = (0.0, 1.0, 0.0)
    r = _norm(_cross(up, o))
    u0 = _cross(o, r)
    cr, sr = math.cos(roll), math.sin(roll)
    rr = tuple(cr * a + sr * b for a, b in zip(r, u0))
    uu = tuple(-sr * a + cr * b for a, b in zip(r, u0))
    return rr, uu, o


def _fmt(v):
    """Filesystem-safe level tag: +7, -15, 085 (no unit, no sign for zoom)."""
    return f"{v:+g}"


def _delta_tag(delta: dict) -> str:
    keymap = {"az_deg": "az", "el_deg": "el", "roll_deg": "roll",
              "tx_mm": "tx", "ty_mm": "ty", "zoom": "zoom"}
    parts = []
    for k, v in delta.items():
        if k == "zoom":
            parts.append(f"zoom{round(v * 100):03d}")
        else:
            parts.append(f"{keymap[k]}{_fmt(v)}")
    return "_".join(parts)


def _apply(base_cam: dict, target0, r0, u0, delta: dict) -> dict:
    """Build the rendered camera for a delta dict (image-plane target -> world)."""
    cam = json.loads(json.dumps(base_cam))  # deep copy
    cam["az_deg"] = base_cam.get("az_deg", 0.0) + delta.get("az_deg", 0.0)
    cam["el_deg"] = base_cam.get("el_deg", 0.0) + delta.get("el_deg", 0.0)
    cam["roll_deg"] = base_cam.get("roll_deg", 0.0) + delta.get("roll_deg", 0.0)
    tx, ty = delta.get("tx_mm", 0.0), delta.get("ty_mm", 0.0)
    cam["target_mm"] = [target0[i] + tx * r0[i] + ty * u0[i] for i in range(3)]
    cam["zoom"] = float(base_cam.get("zoom") or 1.0) * delta.get("zoom", 1.0)
    return cam


def _single_deltas() -> list[dict]:
    out = [{}]  # control
    for lv in ROT_LEVELS:
        out += [{"az_deg": lv}, {"el_deg": lv}, {"roll_deg": lv}]
    for lv in TGT_LEVELS:
        out += [{"tx_mm": lv}, {"ty_mm": lv}]
    for f in ZOOM_LEVELS:
        out.append({"zoom": f})
    return out


def _mixed_deltas(pair_id: str) -> list[dict]:
    rng = random.Random(f"{pair_id}:mixed")
    params = list(MIXED_POOL)
    out = []
    for _ in range(N_MIXED):
        k = rng.choice([2, 3])
        chosen = rng.sample(params, k)
        out.append({p: rng.choice(MIXED_POOL[p]) for p in chosen})
    return out


def _tier(delta: dict, is_mixed: bool) -> str:
    if not delta:
        return "control"
    return "mixed" if is_mixed else "single"


def probe_framing(pairs, out_root: Path, refresh: bool) -> dict:
    """Resolve base framing (target0/need_w0/canvas) per pair via a blender probe."""
    probe_json = out_root / "probe.json"
    have = json.loads(probe_json.read_text(encoding="utf-8")) if probe_json.exists() else {}
    # render_offline --probe-out OVERWRITES the file with only the pairs it ran, so
    # probe ALL requested pairs in one call (one blender load) when any is missing.
    if refresh or not all(p["id"] in have for p in pairs):
        only = ",".join(p["id"] for p in pairs)
        subprocess.run([sys.executable, str(TOOLS / "render_offline.py"),
                        "--only", only, "--out-root", str(out_root),
                        "--probe-out", str(probe_json)], check=True)
        have = json.loads(probe_json.read_text(encoding="utf-8"))
    return have


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", help="comma-separated manifest ids (default: 6 first-pass)")
    ap.add_argument("--all", action="store_true", help="all 18 manifest pairs")
    ap.add_argument("--out-root", default=str(DEFAULT_OUT))
    ap.add_argument("--no-render", action="store_true", help="write ground truth only")
    ap.add_argument("--refresh-probe", action="store_true")
    args = ap.parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    manifest = composite.load_manifest()
    by_id = {p["id"]: p for p in manifest["pairs"]}
    if args.all:
        want = list(by_id)
    elif args.pairs:
        want = args.pairs.split(",")
    else:
        want = FIRST_PASS_PAIRS
    pairs = [by_id[i] for i in want if i in by_id]
    missing = [i for i in want if i not in by_id]
    if missing:
        raise SystemExit(f"unknown pair ids: {missing}")

    framing = probe_framing(pairs, out_root, args.refresh_probe)

    rows = []
    case_pairs = []  # synthetic manifest entries for render_offline
    for pair in pairs:
        pid = pair["id"]
        fr = framing[pid]
        target0 = tuple(fr["target"])
        need_w0, canvas = fr["need_w"], fr["canvas"]
        base_cam = pair["camera"]
        r0, u0, _o0 = camera_axes(base_cam.get("az_deg", 0.0), base_cam.get("el_deg", 0.0),
                                  base_cam.get("roll_deg", 0.0))
        singles = _single_deltas()
        mixed = _mixed_deltas(pid)
        for delta in singles + mixed:
            is_mixed = delta in mixed
            tier = _tier(delta, is_mixed)
            tag = "ctrl" if tier == "control" else \
                (f"mix{mixed.index(delta) + 1}" if is_mixed else _delta_tag(delta))
            case_id = f"{pid}+{tag}"
            cam = _apply(base_cam, target0, r0, u0, delta)
            frozen = {"need_w": need_w0, "canvas": canvas}
            rows.append({
                "case_id": case_id, "pair_id": pid, "tier": tier,
                "delta": delta, "camera": cam, "base_camera": base_cam,
                "frozen": frozen, "target0": list(target0),
                "basis": {"r": list(r0), "u": list(u0)},
                "align": pair.get("align") or {},
                "background": pair["reference"].get("background", "black"),
            })
            case_pairs.append({
                "id": case_id, "model": pair["model"], "camera": cam,
                "reference": pair["reference"], "frozen": frozen,
            })

    CASES_JSONL.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {len(rows)} cases across {len(pairs)} pairs -> {CASES_JSONL}", flush=True)

    if args.no_render:
        return 0

    bench_manifest = out_root / "cases_manifest.json"
    bench_manifest.write_text(json.dumps(
        {"version": manifest.get("version"), "defaults": manifest.get("defaults", {}),
         "pairs": case_pairs}), encoding="utf-8")
    print(f"rendering {len(case_pairs)} case stimuli (fixed-frame) ...", flush=True)
    subprocess.run([sys.executable, str(TOOLS / "render_offline.py"),
                    "--manifest", str(bench_manifest), "--out-root", str(out_root),
                    "--no-trim", "--fixed-frame", "--skip-composites"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
