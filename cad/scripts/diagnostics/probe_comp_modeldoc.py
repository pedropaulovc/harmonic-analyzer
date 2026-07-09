r"""Throwaway probe: on the still-open flexed top, does GetModelDoc2 on a
nested component dispatch work once the dispatch is FLAGGED IComponent2
(#87 dropped whole-interface flagging in component loops)? Never saves.

    uv run python cad\scripts\diagnostics\probe_comp_modeldoc.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import _read_member, check, log, run_build  # noqa: E402
from build_motion_study import _comp_model_doc, _components, _find_one  # noqa: E402


async def build(adapter):
    from _common import OUT_SLDASM
    check("open channel", await adapter.open_model(
        str((OUT_SLDASM / "channel.SLDASM").resolve())))
    comps = _components(adapter)
    for needle in ("connecting-rod-1", "channel-lever-1", "rocker-arm-1"):
        comp, name = _find_one(adapter, needle, comps=comps)
        if comp is None:
            log(f"{needle}: NOT FOUND")
            continue
        raw = adapter._attempt(lambda c=comp: c.GetModelDoc2(), default=None)
        doc = _comp_model_doc(adapter, comp)
        title = str(_read_member(doc, "GetTitle")) if doc is not None else None
        log(f"{needle} ({name}): raw={'ok' if raw is not None else 'None'} "
            f"flagged={'ok' if doc is not None else 'None'} title={title!r}")
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
