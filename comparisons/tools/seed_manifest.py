# /// script
# requires-python = ">=3.11"
# ///
"""Seed comparisons/manifest.json from the curation catalog + the photo index.

Rules (all poses start status="rough"; the discrepancy loop refines them):
- catalog keep=true entries:
    class "machine" (or harmonic_analyzer tagged) -> model harmonic_analyzer
    book sources (isolated studio shots)          -> model = first component part
    video sources (in-context close-ups)          -> enclosing subsystem assembly
  camera az/el from the curation view_guess.
- photogrammetry: the "Component -> best photos" table in photogrammetry/raw/README.md,
  first-claim-wins per photo; az/el from the full-index view phrases.
  Model = enclosing subsystem assembly (machine photographed assembled).
- video references point at stills/full/v<N>_t<sssss>.png (run
  extract_frames.py first).

Default is a merge: existing manifest pairs (same id) are preserved verbatim
so hand-tuned poses survive re-seeding; --reset rebuilds from scratch.

Usage:
    uv run comparisons/tools/seed_manifest.py [--reset]
"""

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "cad" / "scripts"
CATALOG = REPO / "references" / "curation" / "stills_catalog.json"
PHOTOS_MD = REPO / "photogrammetry" / "raw" / "README.md"
MANIFEST = REPO / "comparisons" / "manifest.json"

def part_stems() -> set[str]:
    return {
        f.stem.removeprefix("build_")
        for f in SCRIPTS.glob("build_*.py")
        if not f.stem.endswith("_assembly") and f.stem != "build_all"
    }


# --- photogrammetry ----------------------------------------------------------

# component label in the photo index -> focus part stems ("" label rows are skipped)
PHOTO_FOCUS = {
    "crank": ["crank_arm", "crank_handle", "crankshaft"],
    "cone gear set": ["cone_gear"],
    "cylinder gear set": ["cylinder_gear"],
    "connecting rods / cross shafts": ["connecting_rod"],
    "rocker arms (top comb)": ["rocker_arm"],
    "amplitude bars": ["amplitude_bar"],
    "measuring stick / cord hanger": ["measuring_stick"],
    "channel springs": ["channel_spring"],
    "channel levers": ["channel_lever"],
    "summing lever": ["summing_lever"],
    "counter spring": ["counter_spring"],
    "gooseneck guide tube": ["gooseneck"],
    "magnifying lever": ["magnifying_lever"],
    "magnifying wheel": ["magnifying_wheel"],
    "platen + rack": ["platen", "platen_rack"],
    "pen mechanism (modern)": ["pen_frame", "pen_marker"],
    "translational gearing / chain": ["transgear_pinion", "chain_sprocket"],
    "pinion gear": ["pinion_drum"],
    "tube frame columns": ["tube_frame"],
    "top casting": ["top_frame"],
    "base casting": ["harmonic_base"],
    "rocker arm supports (a-frames)": ["a_frame", "rocker_arm_support"],
    # "nameplate" intentionally skipped: no CAD part
}

VIEW_AZ = [
    ("rear-left", -140), ("rear", 180), ("front-left", -35), ("left 3/4", -40),
    ("oblique left", -35), ("top-left", -30), ("left-front", -25), ("left", -45),
    ("front-right", 35), ("right-front", 35), ("right oblique", 40),
    ("oblique right", 35), ("top-down right", 30), ("right", 45),
]
VIEW_EL = [
    ("top-down steep", 75), ("top-down", 55), ("from below", -25), ("below", -25),
    ("elevated", 30), ("high", 30), ("low-angle", -8), ("low", -5),
]


def view_to_euler(view: str) -> dict:
    v = view.lower()
    az = next((a for phrase, a in VIEW_AZ if phrase in v), 0)
    el = next((e for phrase, e in VIEW_EL if phrase in v), 8)
    return {"az_deg": az, "el_deg": el}


def parse_photos_md() -> tuple[dict[str, list[str]], dict[str, str]]:
    """Return ({component label: [photo suffixes]}, {suffix: view phrase})."""
    text = PHOTOS_MD.read_text(encoding="utf-8")
    best: dict[str, list[str]] = {}
    views: dict[str, str] = {}
    section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if not line.startswith("|") or line.startswith("|--") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if "component" in section and len(cells) >= 2 and cells[0] != "component":
            label = cells[0].lower()
            suffixes = re.findall(r"\b(\d{9})\b", cells[1])
            if suffixes:
                best[label] = suffixes
        if "full index" in section and len(cells) >= 3 and cells[0] != "file":
            m = re.match(r"\d{9}", cells[0])
            if m:
                views[m.group()] = cells[2]
    return best, views


def photo_path(suffix: str) -> str:
    return f"photogrammetry/raw/20250828_{suffix}_iOS.jpg"


# --- pair construction -------------------------------------------------------

def make_pair(pid: str, model: str, ref_path: str, source: str, camera: dict,
              focus: list[str], notes: str, frame: list[str] | None = None) -> dict:
    cam = {"mode": "euler", "roll_deg": 0.0, "zoom": 1.0,
           "target_mm": None, "perspective": None, **camera}
    if frame:
        # In-context reference: render the whole assembly with the camera
        # framed on these components (render_compare.resolve_framing).
        cam["frame_components"] = frame
    return {
        "id": pid,
        "model": model,
        "reference": {"path": ref_path, "source": source},
        "camera": cam,
        "align": {"scale": 1.0, "dx_px": 0, "dy_px": 0},
        "component_focus": focus,
        "status": "rough",
        "notes": notes,
    }


def seed_from_catalog(parts: set[str]) -> list[dict]:
    entries = json.loads(CATALOG.read_text(encoding="utf-8"))["entries"]
    pairs = []
    for e in entries:
        if not e.get("keep"):
            continue
        comps = [c for c in e.get("components", [])]
        cls = e.get("class")
        if cls not in ("machine", "machine-detail", "mixed", "drawing"):
            continue
        frame: list[str] = []
        if cls == "machine" or "harmonic_analyzer" in comps:
            model = "harmonic_analyzer"
        else:
            if not comps:
                continue
            c0 = next((c for c in comps if c in parts), None)
            if e["source"].startswith("ch") and c0 and len(comps) <= 2:
                # Isolated studio shot of one part -> compare the part itself.
                model = c0
            else:
                # In-context shot: the photo shows the component mounted in
                # the complete machine -> render the full assembly with the
                # camera framed on the tagged components.
                model = "harmonic_analyzer"
                frame = comps
        vg = e.get("view_guess") or {}
        camera = {"az_deg": vg.get("az_deg", 15), "el_deg": vg.get("el_deg", 8)}
        if e["source"].startswith("video"):
            vnum = e["source"].removeprefix("video")
            ref = f"references/engineerguy-youtube/stills/full/v{vnum}_t{int(e['time_s']):05d}.png"
            src = f"engineerguy video {vnum} @ {e['time_s']}s"
        else:
            ref = e["path"]
            src = f"book {e['source']}"
        pairs.append(make_pair(f"{model}--{e['id']}", model, ref, src, camera,
                               comps, e.get("notes", ""), frame=frame))
    return pairs


def seed_from_photos() -> list[dict]:
    best, views = parse_photos_md()
    claimed: set[str] = set()
    pairs = []
    for label, focus in PHOTO_FOCUS.items():
        for suffix in best.get(label, []):
            if suffix in claimed:
                continue
            claimed.add(suffix)
            # The machine is photographed fully assembled in its case.
            model = "harmonic_analyzer"
            camera = view_to_euler(views.get(suffix, ""))
            pairs.append(make_pair(
                f"{model}--photo-{suffix}", model, photo_path(suffix),
                f"photogrammetry {suffix} ({views.get(suffix, '?')})",
                camera, focus, label, frame=focus,
            ))
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="discard existing pairs")
    args = ap.parse_args()

    fresh = seed_from_catalog(part_stems()) + seed_from_photos()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    existing = {} if args.reset else {p["id"]: p for p in manifest.get("pairs", [])}
    added = 0
    for p in fresh:
        if p["id"] not in existing:
            existing[p["id"]] = p
            added += 1
    manifest["pairs"] = sorted(existing.values(), key=lambda p: p["id"])
    MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    models = {p["model"] for p in manifest["pairs"]}
    print(f"manifest: {len(manifest['pairs'])} pairs ({added} added) across {len(models)} models")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
