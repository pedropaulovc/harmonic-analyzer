r"""Dump (or diff) every component's as-saved world transform, per assembly.

The #151 machine-handed re-authoring must be a NO-OP on world geometry: every
component of every assembly keeps its exact world pose; only the algebra that
derives the pose changes (pre-mirror frame + mirror_placement -> machine-handed
direct). This probe makes that invariant machine-checkable:

  1. BEFORE the sweep:  ``uv run python cad/scripts/diagnostics/probe_pose_dump.py
     dump cad/out/reports/pose-golden``  (SolidWorks open; reads the built
     .SLDASM fleet as-saved, NO rebuild -- the shipping poses are the truth).
  2. Rebuild the fleet on the sweep branch.
  3. AFTER:  ``... dump cad/out/reports/pose-swept`` then
     ``... diff cad/out/reports/pose-golden cad/out/reports/pose-swept``.

``diff`` is SolidWorks-free. Component instance names (``part-N``, nested
``sub-1/part-N``) are stable across a re-run of the same insertion order, so
they key the match; a renamed/added/removed component is reported loud rather
than silently skipped. Tolerances: 1e-3 mm translation, 1e-6 rotation-row --
the re-authored algebra must reproduce the same numbers, not merely similar
ones (the mirror math is exact; only float noise is allowed).
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import OUT_SLDASM, _flag, _read_member, log  # noqa: E402

ASSEMBLIES = (
    "frame",
    "channel",
    "drive-train",
    "magnifier",
    "summing",
    "pen",
    "paper-drive",
    "harmonic-analyzer",
)

TRANS_TOL_MM = 1e-3
ROT_TOL = 1e-6


async def dump(out_dir: Path) -> None:
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True))
    out_dir.mkdir(parents=True, exist_ok=True)

    for stem in ASSEMBLIES:
        path = (OUT_SLDASM / f"{stem}.SLDASM").resolve()
        if not path.exists():
            raise RuntimeError(f"{stem}: {path} missing -- build the fleet first")
        await adapter.open_model(str(path))
        doc = adapter.currentModel
        _flag(doc, "IModelDoc2")
        # NO ForceRebuild3: the as-SAVED pose is the invariant being pinned.
        poses: dict[str, list[float]] = {}
        comps = adapter._attempt(lambda: doc.GetComponents(False), default=None) or []
        for c in comps:
            _flag(c, "IComponent2")
            name = str(_read_member(c, "Name2"))
            xf = adapter._attempt(lambda cc=c: cc.Transform2, default=None)
            if xf is None:  # a suppressed/lightweight component has no transform
                poses[name] = []
                continue
            poses[name] = [float(v) for v in _read_member(xf, "ArrayData")][:12]
        (out_dir / f"{stem}.json").write_text(
            json.dumps(poses, indent=1, sort_keys=True), encoding="utf-8"
        )
        log(f"{stem}: dumped {len(poses)} top-level component poses")
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True))

    await adapter.disconnect()


def diff(golden_dir: Path, other_dir: Path) -> int:
    failures = 0
    for stem in ASSEMBLIES:
        golden = json.loads((golden_dir / f"{stem}.json").read_text(encoding="utf-8"))
        other = json.loads((other_dir / f"{stem}.json").read_text(encoding="utf-8"))
        missing = sorted(set(golden) - set(other))
        added = sorted(set(other) - set(golden))
        offenders: list[str] = []
        for name in sorted(set(golden) & set(other)):
            g, o = golden[name], other[name]
            if not g or not o:
                if bool(g) != bool(o):
                    offenders.append(f"{name}: transform presence changed")
                continue
            dt = max(abs(a - b) * 1000.0 for a, b in zip(g[9:12], o[9:12]))
            dr = max(abs(a - b) for a, b in zip(g[0:9], o[0:9]))
            if dt > TRANS_TOL_MM or dr > ROT_TOL:
                offenders.append(
                    f"{name}: moved {dt:.4f} mm / rot drift {dr:.2e}"
                )
        ok = not (missing or added or offenders)
        status = "OK" if ok else "DRIFT"
        log(f"{stem}: {status} ({len(golden)} golden vs {len(other)} components)")
        for name in missing:
            log(f"  MISSING in new build: {name}")
        for name in added:
            log(f"  ADDED in new build:   {name}")
        for line in offenders:
            log(f"  {line}")
        if not ok:
            failures += 1
    return failures


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "dump":
        asyncio.run(dump(Path(sys.argv[2])))
        return 0
    if len(sys.argv) >= 4 and sys.argv[1] == "diff":
        failures = diff(Path(sys.argv[2]), Path(sys.argv[3]))
        log("pose diff: " + ("CLEAN" if not failures else f"{failures} assemblies drifted"))
        return 1 if failures else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
