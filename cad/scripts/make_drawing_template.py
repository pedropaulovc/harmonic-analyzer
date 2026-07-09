r"""Create the project drawing template (``cad/templates/harmonic-analyzer.drwdot``).

Derives a clean ANSI B-landscape (17x11 in / 431.8x279.4 mm) drawing template from
the seat's stock ANSI sheet format, strips the unused stock tables (revision / BOM /
general) that clutter a single-part print, sets it born-ASME (third-angle, mm), and
saves it into the repo so the drawing pipeline uses a PROJECT-owned, reproducible
template instead of each seat's default ``.drwdot``. The template is COMMITTED so the
sheet/border/title-block bytes are pinned into release provenance.

One-off / regenerate-on-demand — NOT on the build spine. Run with SolidWorks open::

    uv run python cad\scripts\make_drawing_template.py
"""

from __future__ import annotations

import sys

from _common import run_build
from _drawing import TEMPLATE_DRWDOT

import _telemetry

from solidworks_mcp.adapters.solidworks import drawing as dwg

# The stock ANSI B landscape sheet format (border + title block); resolved from the
# install's sheetformat dir so it works across seats.
ANSI_B_FORMAT = "b - landscape.slddrt"


async def build(adapter) -> dict[str, str]:
    # 1. Blank drawing from the seat default template.
    dwg.new_drawing(adapter)

    # 2. Apply the stock ANSI B landscape sheet format (border + zones + title block).
    fmt = dwg.resolve_sheet_format(adapter, ANSI_B_FORMAT)
    if fmt:
        dwg.apply_sheet_format(adapter, fmt)
        _telemetry.info(f"applied ANSI sheet format: {fmt}")
    else:
        _telemetry.warn(f"{ANSI_B_FORMAT!r} not found on this seat; keeping template default")

    # 3. Born ASME: third-angle projection, mm.
    dwg.setup_sheet(adapter, scale=(1, 1), first_angle=False)
    dwg.set_units_mm(adapter, decimals=2)

    # 4. Strip the stock unused tables (revision / BOM / general).
    removed = dwg.delete_all_tables(adapter)
    _telemetry.info(f"stripped {removed} stock table(s)")

    # 5. Save as the project template.
    path = dwg.save_as_template(adapter, str(TEMPLATE_DRWDOT))
    _telemetry.info(f"project drawing template saved: {path}")
    return {"template": path}


if __name__ == "__main__":
    sys.exit(run_build(build))
