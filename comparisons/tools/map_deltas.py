"""Map pose_studio part deltas back to SolidWorks edit targets.

Reads ``comparisons/findings/<pair>_deltas.json`` (written by pose_studio's
*Export Part Deltas*) and, for each hand-moved part, prints where in the CAD
source to apply the change:

* a **resize** (``scale`` != 1) -> the dimension constants in the part's
  ``cad/scripts/build_<stem>.py``, each shown with its confidence tag. Only the
  ``(low)`` / photo-scaled constants are fair game; a ``(high)`` book-annotated
  dim that "needs" changing means the *pose* is still off, not the geometry.
* a **shift** (``translate_mm`` != 0) -> the part is positioned by a contact
  mate in whichever ``build_<assembly>.py`` inserts it (parts sit on solved
  transforms, so there's rarely a free offset knob -- trace the shift to an
  upstream driving dimension, and expect verify:soundness to police it).

SolidWorks-free: pure text analysis of the build scripts. Run:

    uv run comparisons/tools/map_deltas.py --pair harmonic_analyzer--ch30-p003-img01
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO / "cad" / "scripts"
# UPPER_SNAKE = <number>  # ... trailing comment (carries the (high)/(low) tag)
_CONST = re.compile(r"^([A-Z][A-Z0-9_]+)\s*=\s*(-?\d+\.?\d*)\s*#\s*(.*)$")


def _build_script(stem: str) -> Path:
    return _SCRIPTS / f"build_{stem.replace('-', '_')}.py"


def _dim_constants(stem: str) -> list[tuple[str, str, str]]:
    script = _build_script(stem)
    if not script.exists():
        return []
    out = []
    for line in script.read_text(encoding="utf-8").splitlines():
        m = _CONST.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2), m.group(3)))
    return out


def _positioning_assemblies(stem: str) -> list[str]:
    """Assembly build scripts that INSERT+mate this part. An assembly qualifies
    when it calls ``place_component`` AND the stem literal ``"<stem>"`` appears
    anywhere in it -- this catches the multi-line call form (stem on its own
    line), loop-variable placement (``for arc in ("column-clamp-front", ...)``)
    and batch blocks alike. Scoped to ``build_*_assembly.py`` so a neighbouring
    part/wire/motion script that merely name-drops the stem doesn't count. A
    reused part may list >1 assembly (it's placed in each)."""
    quoted = f'"{stem}"'
    hits = []
    for script in sorted(_SCRIPTS.glob("build_*_assembly.py")):
        text = script.read_text(encoding="utf-8")
        if "place_component" in text and quoted in text:
            hits.append(script.name)
    return hits


def _tag(comment: str) -> str:
    m = re.search(r"\((high|low|med|medium)\)", comment)
    return m.group(1) if m else "?"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pair", required=True, help="pair id (matches the deltas filename)")
    ap.add_argument("--findings", default=None, help="override deltas json path")
    args = ap.parse_args()

    path = Path(args.findings) if args.findings else (
        _REPO / "comparisons" / "findings" / f"{args.pair}_deltas.json")
    if not path.exists():
        raise SystemExit(f"no deltas file: {path}\n"
                         "run pose_studio.py, move parts, press Export Part Deltas")

    data = json.loads(path.read_text(encoding="utf-8"))
    moved = data.get("moved", [])
    print(f"# {path.name}  ({data.get('source', '?')})")
    print(f"# {len(moved)} moved part(s) · {data.get('units', '')}\n")

    for entry in moved:
        stem = entry["part"]
        dt = entry["translate_mm"]
        sf = entry["scale"]
        dr = entry.get("rotate_deg", [0, 0, 0])
        print(f"== {entry['name']}  (part: {stem}) ==")

        if max(abs(s - 1.0) for s in sf) >= 0.005:
            print(f"  RESIZE  scale = {sf}  -> edit build_{stem.replace('-', '_')}.py:")
            consts = _dim_constants(stem)
            if not consts:
                print(f"    (no build_{stem.replace('-', '_')}.py dimension constants found)")
            for name, val, comment in consts:
                mark = "  <- editable" if _tag(comment) == "low" else (
                    "  <- LOCKED (book-annotated: pose is the suspect)"
                    if _tag(comment) == "high" else "")
                print(f"    {name:<18} = {val:<8} ({_tag(comment)}){mark}")

        if max(abs(v) for v in dt) >= 0.5:
            print(f"  SHIFT   translate_mm = {dt}  -> positioned by a mate in:")
            asms = _positioning_assemblies(stem)
            for a in asms:
                print(f"    {a}")
            if not asms:
                print("    (no assembly references this stem -- check the part name)")
            print("    (no free offset: trace to an upstream driving dim; "
                  "verify:soundness will police interference/DOF)")

        if max(abs(a) for a in dr) >= 0.2:
            print(f"  ROTATE  rotate_deg = {dr}  -> mate orientation in the assembly above")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
