"""Open one assembly on the SolidWorks seat and export it as glTF binary (.glb).

Reuses the pipeline's proven ``open_model`` -> ``_save_as`` (SaveAs3, format
inferred from the .glb extension), so the output matches what ``export_models``
writes: metre units, one node per visible component, appearance PBR materials.

    cd cad/scripts && uv run python export_glb.py [stem | path/to.SLDASM]

Default stem is ``harmonic-analyzer`` -> ``cad/out/sldasm/<stem>.SLDASM`` ->
``cad/out/gltf/<stem>.glb``. Fails loud (no partial glb) if the assembly's
component references did not resolve on open.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from _common import _early_bound, check, log, run_build
from export_models import OUT_GLTF, OUT_SLDASM, _save_as

import _telemetry

# swComponentSuppressionState_e: 0 suppressed/not-loaded, 5 id-mismatch are the
# broken states; 1 lightweight, 2 fully-resolved, 3 resolved, 4 fully-lightweight
# all carry exportable geometry.
_MISSING_STATES = {0, 5}


def _src() -> Path:
    arg = sys.argv[1] if len(sys.argv) > 1 else "harmonic-analyzer"
    p = Path(arg)
    if p.suffix.lower() == ".sldasm":
        return p
    return OUT_SLDASM / f"{arg.replace('_', '-')}.SLDASM"


async def build(adapter: Any) -> dict[str, str]:
    src = _src()
    if not src.is_file():
        raise SystemExit(f"assembly not found: {src}")
    OUT_GLTF.mkdir(parents=True, exist_ok=True)

    check(f"open {src.name}", await adapter.open_model(str(src)))
    doc = adapter.currentModel

    # Silent OpenDoc6 loads unresolved references as SUPPRESSED rather than
    # prompting, so a missing part is a quiet gap in the glb -- gate on it.
    asm = _early_bound(doc, "IAssemblyDoc")  # same dispatch, exposes GetComponents
    comps = adapter._attempt(lambda: asm.GetComponents(False), default=None) or []
    states = [adapter._attempt(lambda c=c: _early_bound(c, "IComponent2").GetSuppression2(),
                               default=-1) for c in comps]
    missing = sum(1 for s in states if s in _MISSING_STATES)
    loaded = len(comps) - missing
    log(f"{src.name}: {len(comps)} components ({loaded} loaded, {missing} suppressed/mismatched)")
    # No-partial-glb guarantee: ANY unresolved component would be silently omitted
    # from the export, so abort on the first one (a large partial can still clear a
    # component floor). An empty/near-empty enumeration means open never resolved.
    if len(comps) < 100:
        raise SystemExit(
            f"only {len(comps)} components enumerated -- references did not resolve "
            f"(expected ~400); aborting so no partial glb is written")
    if missing:
        raise SystemExit(
            f"{missing} of {len(comps)} components unresolved (suppressed/id-mismatch) -- "
            f"they would be omitted from the glb; aborting so no partial glb is written")

    glb = OUT_GLTF / f"{src.stem}.glb"
    _save_as(doc, glb)
    _telemetry.success(f"saved {glb} ({glb.stat().st_size / 1e6:.1f} MB)")
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    return {"glb": str(glb), "components": str(len(comps)), "loaded": str(loaded)}


if __name__ == "__main__":
    sys.exit(run_build(build))
