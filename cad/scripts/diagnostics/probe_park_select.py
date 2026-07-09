r"""Throwaway probe: why does 'Right Plane@cone-swing-platform-1' fail
SelectByID2 on a standalone-opened drive-train.SLDASM? Tries the recorded
2-segment form, the 3-segment (@doc) form, and lists the top components.
NON_PART_SCRIPT; never saves.

    uv run python cad\scripts\diagnostics\probe_park_select.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import OUT_SLDASM, _read_member, check, log, run_build  # noqa: E402
from _assembly_postbuild import discard_open_documents  # noqa: E402


async def build(adapter):
    discard_open_documents(adapter)
    path = str((OUT_SLDASM / "drive-train.SLDASM").resolve())
    check("open drive-train", await adapter.open_model(path))
    model = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=None)
    adapter.currentModel = model
    title = str(_read_member(model, "GetTitle"))
    log(f"active doc title = {title!r}")

    comps = adapter._attempt(lambda: model.GetComponents(True), default=None) or []
    names = [str(_read_member(c, "Name2")) for c in comps]
    hits = [n for n in names if "cone-swing" in n or "pinion" in n]
    log(f"top-level comps: {len(names)}; cone/pinion hits: {hits}")

    ext = _read_member(model, "Extension")
    for name in (
        "Right Plane@cone-swing-platform-1",
        f"Right Plane@cone-swing-platform-1@{title}",
        "Right Plane@cone-swing-platform-1@drive-train",
        "Right Plane@cone-swing-platform-1@drive-train.SLDASM",
    ):
        ok = adapter._attempt(
            lambda nm=name: ext.SelectByID2(nm, "PLANE", 0, 0, 0, False, 0, None, 0),
            default=None)
        log(f"SelectByID2({name!r}) -> {ok}")
        adapter._attempt(lambda: model.ClearSelection2(True), default=None)
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
