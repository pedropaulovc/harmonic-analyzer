r"""McMaster 91255A108 -- black-oxide alloy steel button head SHCS, #4-40 x 3/8".

The SKU is [INFERENCE]: the 3/8 in length of the 91255A series by the 91255A
numbering this repository records (106 = 1/4 in, 148 = #6-32 x 1/2 in) and
McMaster's sibling series (90280A108 = #4-40 x 3/8), not yet read live; the
vendor check is pending (``guide_lock_screw_spec``).  Everything but the
length is the 91255A106 page read live on 2026-09-30 (#4-40 UNC class 3A,
fully threaded, flat tip, button head Ø0.213 in x 0.059 in, 1/16 in hex drive,
ASME B18.3 / ASTM F835) -- a length change within one series.

Built by the button-head family recipe (``diag_mcmaster_button_head.build_button_head``,
see ``diag_build_91255A106``'s docstring for the [INFERENCE] head, socket and thread laws) with the
length 3/8 in (9.525) under the head.  No vendor SLDPRT is downloaded or
committed, so the standalone run is catalog-only.

Ruling R9-48: the MHA-VN-046 guide-lock screws grew from 1/4 in so the worst-case
engagement in the platen guide's through tap holds 1.5D.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91255A108.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_91255a108 import DIMS  # noqa: E402
from diagnostics.diag_mcmaster_button_head import (  # noqa: E402
    build_button_head,
    catalog_run,
)


@stock_recipe("91255A108", threaded=True)
async def build_91255A108(adapter, truth=None):
    await build_button_head(adapter, DIMS)


async def build_catalog(adapter) -> dict[str, str]:
    return await catalog_run(adapter, DIMS, build_91255A108)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build

    sys.exit(run_build(build_catalog))
