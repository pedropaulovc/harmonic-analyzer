r"""Estimate, offline, which title-block MATERIAL / FINISH values overflow.

finalize_drawing holds each drawn part's Material Specification to ONE line
of the MATERIAL cell and its Finish to TWO lines of the FINISH cell
(``assert_title_block_resolves``), and rejects placeholders. That gate needs a
seat; this is the seat-free forecast over the checked-out registry, so a
registry merge (the #877 integration checklist) can be sized before a leaf.

Calibration, MHA-102 at 7f7fc1717 (300 dpi render): the value font is Century
Gothic at ~36.6 px; "AISI 1018 cold-finished steel" predicts 481 px against
474 inked, and the FINISH line "bright machined; protect with ISO VG 32
machine-oil" (938 px) fit while "... film" (1008 px) wrapped. Lines are
counted by greedy word wrap at 938 px, the conservative width. An estimate,
not proof: the leaf's INote.GetExtent check decides.

    uv run python cad/scripts/diagnostics/title_block_fit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _config  # noqa: E402
from _drawing_common import TITLE_BLOCK_PLACEHOLDER  # noqa: E402
from _drawing_registry import DRAWINGS  # noqa: E402

FONT = Path("C:/Windows/Fonts/GOTHIC.TTF")
FONT_PX = 40 * 935 / 1023
WRAP_PX = 938.0
CELL_LINES = {"material_specification": 1, "finish": 2}


def _width(font, text: str) -> float:
    return font.getlength(text) * FONT_PX / 100


def lines(font, text: str, width: float = WRAP_PX) -> int:
    """Greedy word-wrap line count. A word wider than ``width`` cannot wrap
    at all, so it counts one line past the cell: an overflow, never a fit."""
    count, line = 1, ""
    for word in text.split():
        if _width(font, word) > width:
            return count + (2 if line else 1)
        trial = f"{line} {word}".strip()
        if _width(font, trial) <= width:
            line = trial
            continue
        count, line = count + 1, word
    return count


def main() -> int:
    from PIL import ImageFont

    if not FONT.is_file():
        raise SystemExit(f"{FONT} is missing: the estimate is calibrated on Century Gothic")
    font = ImageFont.truetype(str(FONT), 100)
    drawn = sorted({spec.source.stem for spec in DRAWINGS if spec.source_kind == "part"})
    problems = []
    for stem in drawn:
        row = _config.parts(stem)
        for field, cap in CELL_LINES.items():
            text = str(row.get(field) or "")
            if TITLE_BLOCK_PLACEHOLDER.match(text):
                problems.append(f"{stem}: {field} is blank or a placeholder ({text!r})")
                continue
            used = lines(font, text)
            if used > cap:
                problems.append(
                    f"{stem}: {field} ~{_width(font, text):.0f} px wraps to {used} lines (cell holds {cap}): {text!r}"
                )
    print(f"{len(drawn)} drawn parts; {len(problems)} forecast problems")
    for problem in problems:
        print(f"  {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
