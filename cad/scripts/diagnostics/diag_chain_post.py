r"""Diagnostic: minimal assembly of drive-chain + cone-pivot-post at their
top-level world placements; report each component's world box and the
interference pair, to localize the 0.00 mm^3 sliver found in the M6.8
top-level rebuild (the slack arc should clear the post top by 1.1 mm).

Run: C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_chain_post.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import OUT_SLDPRT, check, run_build  # noqa: E402
from _common import _flag, _read_member  # type: ignore[attr-defined]  # noqa: E402

# Placements copied from the assembly scripts (pre-mirror frames).
CHAIN_POS = ([65.0, 241.78, -83.3], [0.0, 0.0, 0.0],
             [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
# cone-pivot-post placement from build_drive_train_assembly (read there:
# rotated block at the cone big-end station).
import math  # noqa: E402

INCLINE_DEG = 21.0976
C, S = math.cos(math.radians(INCLINE_DEG)), math.sin(math.radians(INCLINE_DEG))
ROT_Y_INCLINE = [[C, 0.0, S], [0.0, 1.0, 0.0], [-S, 0.0, C]]


async def build(adapter) -> dict[str, str]:

    # Recover the post's exact placement from the saved drive-train.SLDASM
    # instead of duplicating its derivation: open it and read the comp box.
    check("open drive-train", await adapter.open_model(
        str((OUT_SLDPRT.parent / "sldasm" / "drive-train.SLDASM").resolve())))
    asm = adapter.currentModel
    _flag(asm, "IAssemblyDoc")
    boxes = {}
    for comp in list(adapter._attempt(lambda a=asm: a.GetComponents(False), default=None) or []):
        _flag(comp, "IComponent2")
        name = str(_read_member(comp, "Name2"))
        if "cone-pivot-post" in name or "transgear-removable" in name:
            box = adapter._attempt(lambda c=comp: c.GetBox(False, False), default=None)
            if box:
                boxes[name] = [round(float(v) * 1000.0, 2) for v in box]
    for n, b in boxes.items():
        print(f"  drive-train {n}: x {b[0]}..{b[3]}  y {b[1]}..{b[4]}  z {b[2]}..{b[5]}")

    check("open output", await adapter.open_model(
        str((OUT_SLDPRT.parent / "sldasm" / "output.SLDASM").resolve())))
    asm = adapter.currentModel
    _flag(asm, "IAssemblyDoc")
    for comp in list(adapter._attempt(lambda a=asm: a.GetComponents(False), default=None) or []):
        _flag(comp, "IComponent2")
        name = str(_read_member(comp, "Name2"))
        if "drive-chain" in name or "transgear-removable" in name or "knob-shaft" in name:
            box = adapter._attempt(lambda c=comp: c.GetBox(False, False), default=None)
            if box:
                b = [round(float(v) * 1000.0, 2) for v in box]
                print(f"  output {name}: x {b[0]}..{b[3]}  y {b[1]}..{b[4]}  z {b[2]}..{b[5]}")
    return {"ok": "1"}


if __name__ == "__main__":
    sys.exit(run_build(build))
