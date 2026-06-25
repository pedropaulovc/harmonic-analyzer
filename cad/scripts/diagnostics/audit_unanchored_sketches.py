r"""Static audit: find add_line_chain sketches with NO explicit origin anchor.

The inference-suppression fix (add_line_chain/define_circle now draw with
AddToDB=True) removed the SolidWorks habit of auto-snapping an exact-(0,0)
vertex onto the origin. Sketches that relied on that snap for full definition
are now under_defined (transgear_removable blank, measuring_stick body, ...).

This walks every build_*.py, slices each create_sketch .. exit_sketch block,
and flags blocks that contain an add_line_chain but NO anchoring signal:
  - anchor_point_to_origin / anchor_point_to_point helper, OR
  - an add_sketch_constraint(..., "origin", ...) (coincident/vertical/horizontal
    points to origin), OR
  - a merge into a pre-anchored arc/circle in the SAME block whose centre is
    constrained to the origin.

A flagged block is a SUSPECT to inspect -- not all are bugs (some chains close
onto an already-pinned arc via exact-coordinate merge, which the regex can't
prove), but every genuine under_defined regression shows up here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry

SCRIPTS = sorted((Path(__file__).resolve().parents[1]).glob("build_*.py"))

# any of these tokens inside the sketch block => an explicit anchor is present
ANCHOR_TOKENS = (
    "anchor_point_to_origin",
    "anchor_point_to_point",
    '"origin"',
    "'origin'",
    # these helpers add the origin anchor INTERNALLY (in _common.py), so a
    # block that routes its chain through one of them is anchored even though
    # the anchor call is not literally in the call-site block:
    "define_rectilinear_chain",
    "define_polygon_chain",
)


def sketch_blocks(text: str):
    """Yield (start_line, block_text) for each create_sketch..exit_sketch span."""
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if "create_sketch" in l]
    for s in starts:
        end = next((j for j in range(s + 1, len(lines))
                    if "exit_sketch" in lines[j]), len(lines))
        yield s + 1, "\n".join(lines[s:end + 1])


def main() -> int:
    suspects = []
    for f in SCRIPTS:
        text = f.read_text(encoding="utf-8")
        for ln, block in sketch_blocks(text):
            if "add_line_chain" not in block:
                continue
            if any(tok in block for tok in ANCHOR_TOKENS):
                continue
            # merge-into-anchored-arc heuristic: an add_arc whose .center is
            # later made coincident -- already covered by "origin" token above,
            # so reaching here means no origin reference at all.
            label = re.search(r'create_sketch\([^)]*\)', block)
            suspects.append((f.name, ln, label.group(0) if label else ""))
    if not suspects:
        _telemetry.info("no unanchored add_line_chain sketches found")
        return 0
    _telemetry.warn(f"{len(suspects)} SUSPECT unanchored add_line_chain sketch block(s):")
    for name, ln, lbl in suspects:
        _telemetry.info(f"{name}:{ln}   {lbl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
