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
# UPPER_SNAKE = <value>  # ... trailing comment (carries the (high)/(low) tag).
# Value is captured up to the '#' so expression-valued dims (0.375 * IN,
# BAR_FRONT_Z - 6.0, (315.5, 349.5)) are surfaced too, not just bare numbers.
_CONST = re.compile(r"^([A-Z][A-Z0-9_]+)\s*=\s*(.+?)\s*#\s*(.*)$")
_T_MM, _S, _R_DEG = 0.5, 0.005, 0.2  # noise floors (match the exporter)


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


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _camera_basis(cam: dict):
    """(right, up, depth) unit axes for a manifest euler camera -- the pure part
    of blender_worker.camera_axes (no bpy). depth points toward the camera; a
    free viewport drag has ~0 depth component, so it exposes the true 2-DOF move
    and flags that the shift carries NO front-back (depth) information."""
    import math
    az, el, roll = (math.radians(cam.get(k, 0.0))
                    for k in ("az_deg", "el_deg", "roll_deg"))
    o = (math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))
    up = (0.0, 1.0, 0.0)
    rx = _cross(up, o)
    n = math.sqrt(sum(c * c for c in rx)) or 1.0
    r = tuple(c / n for c in rx)
    u0 = _cross(o, r)
    cr, sr = math.cos(roll), math.sin(roll)
    rr = tuple(cr * a + sr * b for a, b in zip(r, u0))
    uu = tuple(-sr * a + cr * b for a, b in zip(r, u0))
    return rr, uu, o


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _group_key(entry: dict) -> tuple:
    return (tuple(round(v, 1) for v in entry["translate_mm"]),
            tuple(round(s, 3) for s in entry["scale"]),
            tuple(round(a, 1) for a in entry.get("rotate_deg", [0, 0, 0])))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pair", required=True, help="pair id (matches the deltas filename)")
    ap.add_argument("--findings", default=None, help="override deltas json path")
    ap.add_argument("--merge-tol", type=float, default=0.0, metavar="MM",
                    help="merge groups whose shift deltas are within MM of each "
                         "other (default 0 = exact). Use to fold an imprecise "
                         "multi-select back into one intended move.")
    args = ap.parse_args()

    path = Path(args.findings) if args.findings else (
        _REPO / "comparisons" / "findings" / f"{args.pair}_deltas.json")
    if not path.exists():
        raise SystemExit(f"no deltas file: {path}\n"
                         "run pose_studio.py, move parts, press Export Part Deltas")

    data = json.loads(path.read_text(encoding="utf-8"))
    moved = data.get("moved", [])
    cam = data.get("camera") or {}
    basis = _camera_basis(cam) if cam.get("az_deg") is not None else None
    # Group parts that moved by the same delta (a rigid-group drag), then
    # optionally merge near-equal groups (--merge-tol) so an imprecise
    # multi-select folds back into one intended move. Only groups with the same
    # scale key merge; the merged shift is the mean of its members' translates.
    exact: dict[tuple, list[dict]] = {}
    for e in moved:
        exact.setdefault(_group_key(e), []).append(e)

    clusters: list[list[dict]] = []
    refs: list[tuple] = []
    for (dt, sf, dr), members in exact.items():
        hit = None
        for i, (rdt, rsf, rdr) in enumerate(refs):
            if rsf == sf and rdr == dr and args.merge_tol > 0 and \
                    max(abs(a - b) for a, b in zip(dt, rdt)) <= args.merge_tol:
                hit = i
                break
        if hit is None:
            refs.append((dt, sf, dr))
            clusters.append(list(members))
        else:
            clusters[hit].extend(members)

    print(f"# {path.name}  ({data.get('source', '?')})")
    tol_note = f" · merge-tol {args.merge_tol:g} mm" if args.merge_tol > 0 else ""
    print(f"# {len(moved)} moved part(s) in {len(clusters)} group(s){tol_note} · "
          f"{data.get('units', '')}\n")

    for gi, members in enumerate(clusters, 1):
        n = len(members)
        dt = tuple(round(sum(m["translate_mm"][i] for m in members) / n, 3)
                   for i in range(3))
        sf = tuple(round(sum(m["scale"][i] for m in members) / n, 4)
                   for i in range(3))
        dr = tuple(round(sum(m.get("rotate_deg", [0, 0, 0])[i] for m in members) / n, 3)
                   for i in range(3))
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
            if basis is not None:
                r, u, o = basis
                print(f"   in-view: right {_dot(dt, r):+.1f}  up {_dot(dt, u):+.1f}  "
                      f"depth {_dot(dt, o):+.1f} mm  "
                      f"({'≈0 depth: 2-DOF drag, front-back UNCONSTRAINED — confirm in a 2nd view'
                        if abs(_dot(dt, o)) < 1.0 else 'has depth: verify it is real, not view-plane'})")
            asms = sorted({a for stem in stems for a in _positioning_assemblies(stem)})
            print(f"   SHIFT   translate_mm = {list(dt)}  -> positioned by mates in:")
            for a in asms:
                print(f"     {a}")
            if not asms:
                print("     (no assembly places these stems -- check the names)")
            print("     (no free offset: trace to an upstream driving dim; "
                  "verify:soundness polices interference/DOF)")

        if max(abs(a) for a in dr) >= _R_DEG:
            asms = sorted({a for stem in stems for a in _positioning_assemblies(stem)})
            print(f"   ROTATE  rotate_deg = {list(dr)}  -> mate ORIENTATION "
                  f"(angle/axis of the placing mate) in:")
            for a in asms:
                print(f"     {a}")
            if not asms:
                print("     (no assembly places these stems -- check the names)")

        if (max(abs(s - 1.0) for s in sf) < _S and max(abs(v) for v in dt) < _T_MM
                and max(abs(a) for a in dr) < _R_DEG):
            print("   (sub-noise-floor: nothing actionable)")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
