"""Map pose_studio part deltas back to SolidWorks edit targets.

Reads ``comparisons/findings/<pair>_deltas.json`` (written by pose_studio's
*Export Part Deltas*) and, for each hand-moved part, prints where in the CAD
source to apply the change. Parts that moved by the SAME delta are grouped --
a rigid-group drag reports as one edit, not N.

* a **resize** (``scale`` != 1) -> the dimension constants in the part's
  ``cad/scripts/build_<stem>.py``, each shown with its confidence tag. Only the
  ``(low)`` / photo-scaled constants are fair game; a ``(high)`` book-annotated
  dim that "needs" changing means the *pose* is still off, not the geometry.
* a **shift** (``translate_mm`` != 0) -> the part is positioned by a contact
  mate in whichever ``build_<assembly>.py`` inserts it (parts sit on solved
  transforms, so there's rarely a free offset knob -- trace the shift to an
  upstream driving dimension, and expect verify:soundness to police it).

SolidWorks-free: pure text analysis of the build scripts. Run:

    python comparisons/tools/map_deltas.py --pair harmonic_analyzer--ch30-p003-img01
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
_T_MM, _S = 0.5, 0.005  # noise floors (match the exporter)


def _stem_candidates(raw: str) -> list[str]:
    """Canonical-stem candidates for a raw part/object label, most-specific
    first: drop Blender's ``.001`` dup suffix, a parametric ``--t24`` suffix,
    and a trailing ``-1`` instance number."""
    out: list[str] = []

    def add(s: str) -> None:
        if s and s not in out:
            out.append(s)

    s = re.sub(r"\.\d+$", "", raw)                 # platen-1.001 -> platen-1
    add(s)
    if "--" in s:
        add(s.split("--")[0])                      # transgear-removable--t24 -> transgear-removable
    m = re.match(r"(.+)-\d+$", s)                  # platen-1 -> platen
    if m:
        add(m.group(1))
        if "--" in m.group(1):
            add(m.group(1).split("--")[0])
    return out


def _build_script(stem: str) -> Path:
    return _SCRIPTS / f"build_{stem.replace('-', '_')}.py"


def _canonical(raw: str) -> str:
    """The candidate whose build_<stem>.py exists, else the first candidate."""
    cands = _stem_candidates(raw)
    for c in cands:
        if _build_script(c).exists():
            return c
    return cands[0] if cands else raw


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
    """Assembly build scripts that INSERT+mate this part: they call
    ``place_component`` AND contain a stem literal (``"<stem>"``). Tries the
    canonical stem and its parametric/instance candidates, so a multi-line call,
    a loop variable, or a ``--t24`` name all resolve. Scoped to
    ``build_*_assembly.py``. A reused part may list >1 assembly."""
    literals = {f'"{c}"' for c in _stem_candidates(stem)} | {f'"{stem}"'}
    hits = []
    for script in sorted(_SCRIPTS.glob("build_*_assembly.py")):
        text = script.read_text(encoding="utf-8")
        if "place_component" in text and any(lit in text for lit in literals):
            hits.append(script.name)
    return hits


def _tag(comment: str) -> str:
    m = re.search(r"\((high|low|med|medium)\)", comment)
    return m.group(1) if m else "?"


def _group_key(entry: dict) -> tuple:
    return (tuple(round(v, 1) for v in entry["translate_mm"]),
            tuple(round(s, 3) for s in entry["scale"]))


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
    # Group parts that moved by the same delta (a rigid-group drag).
    groups: dict[tuple, list[dict]] = {}
    for e in moved:
        groups.setdefault(_group_key(e), []).append(e)

    print(f"# {path.name}  ({data.get('source', '?')})")
    print(f"# {len(moved)} moved part(s) in {len(groups)} rigid group(s) · "
          f"{data.get('units', '')}\n")

    for gi, (key, members) in enumerate(groups.items(), 1):
        (dt, sf) = key
        stems = sorted({_canonical(m["part"]) for m in members})
        names = ", ".join(sorted(m["name"] for m in members))
        print(f"== group {gi}: {len(members)} part(s) -> {', '.join(stems)} ==")
        print(f"   parts: {names}")

        if max(abs(s - 1.0) for s in sf) >= _S:
            print(f"   RESIZE  scale = {list(sf)}  -> build_<stem>.py constants:")
            for stem in stems:
                consts = _dim_constants(stem)
                if not consts:
                    print(f"     [{stem}] no dimension constants found")
                for name, val, comment in consts:
                    t = _tag(comment)
                    mark = ("  <- editable" if t == "low"
                            else "  <- LOCKED (book-annotated: pose is the suspect)"
                            if t == "high" else "")
                    print(f"     [{stem}] {name:<18} = {val:<8} ({t}){mark}")

        if max(abs(v) for v in dt) >= _T_MM:
            asms = sorted({a for stem in stems for a in _positioning_assemblies(stem)})
            print(f"   SHIFT   translate_mm = {list(dt)}  -> positioned by mates in:")
            for a in asms:
                print(f"     {a}")
            if not asms:
                print("     (no assembly places these stems -- check the names)")
            print("     (no free offset: trace to an upstream driving dim; "
                  "verify:soundness polices interference/DOF)")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
