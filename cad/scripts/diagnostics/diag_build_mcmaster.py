r"""Diagnostic: rebuild the McMaster-Carr reference fasteners from scratch --
the fleet-wide successor of ``diag_build_91829A560.py`` (which stays as the
validated single-part original).

Every replica is a PURE reverse-engineering of its vendor model in
``cad/references/mcmaster/``: all numbers come from that part's harvest JSON
(``diag_dump_part.py`` -> ``cad/out/reports/mcmaster-<part>-dump.json``) or
were read live off the open vendor document -- nothing is imported from the
repo's part specs.  Gates run against the vendor's own mass properties and
face-area multiset, loaded from the same harvest (see
``diag_mcmaster_lib.gate_and_save``).

Each part lives in its own ``diag_build_<part_no>.py`` (runnable standalone,
like the 91829A560 original); the two parametric families share their recipe
modules (``diag_mcmaster_fillister.py`` / ``diag_mcmaster_thumb.py``).  This
driver just fans the fleet out.

Run (SolidWorks already open)::

    uv run python cad\scripts\diagnostics\diag_build_mcmaster.py 90126A211
    uv run python cad\scripts\diagnostics\diag_build_mcmaster.py --all

Output (replica .SLDPRT + report JSON + render pairs) goes to the gitignored
``cad/out/reference/``.  The McMaster files are (c) McMaster-Carr,
reference-only: opened read-only for the render pair, never saved.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import run_build  # noqa: E402
from diagnostics.diag_mcmaster_lib import run_replica  # noqa: E402
from diagnostics.diag_build_90114A511 import build_90114A511  # noqa: E402
from diagnostics.diag_build_90126A211 import build_90126A211  # noqa: E402
from diagnostics.diag_build_90280A108 import build_90280A108  # noqa: E402
from diagnostics.diag_build_90280A194 import build_90280A194  # noqa: E402
from diagnostics.diag_build_90280A196 import build_90280A196  # noqa: E402
from diagnostics.diag_build_90280A199 import build_90280A199  # noqa: E402
from diagnostics.diag_build_90280A201 import build_90280A201  # noqa: E402
from diagnostics.diag_build_91247A720 import build_91247A720  # noqa: E402
from diagnostics.diag_build_91410A538 import build_91410A538  # noqa: E402
from diagnostics.diag_build_91783A722 import build_91783A722  # noqa: E402
from diagnostics.diag_build_91882A221 import build_91882A221  # noqa: E402
from diagnostics.diag_build_91882A412 import build_91882A412  # noqa: E402
from diagnostics.diag_build_92865A585 import build_92865A585  # noqa: E402
from diagnostics.diag_build_93075A194 import build_93075A194  # noqa: E402
from diagnostics.diag_build_94025A150 import build_94025A150  # noqa: E402
from diagnostics.diag_build_99607A213 import build_99607A213  # noqa: E402

REGISTRY = {
    "90126A211": build_90126A211,
    "94025A150": build_94025A150,
    "90114A511": build_90114A511,
    "91783A722": build_91783A722,
    "91410A538": build_91410A538,
    "93075A194": build_93075A194,
    "92865A585": build_92865A585,
    "91247A720": build_91247A720,
    "99607A213": build_99607A213,
    "91882A221": build_91882A221,
    "91882A412": build_91882A412,
    "90280A108": build_90280A108,
    "90280A194": build_90280A194,
    "90280A196": build_90280A196,
    "90280A199": build_90280A199,
    "90280A201": build_90280A201,
}


def _selected_parts() -> list[str]:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--all" in sys.argv[1:]:
        return list(REGISTRY)
    if not args:
        raise SystemExit(
            f"usage: diag_build_mcmaster.py <part_no>...|--all "
            f"(known: {', '.join(REGISTRY)})")
    unknown = [a for a in args if a not in REGISTRY]
    if unknown:
        raise SystemExit(f"no builder for: {', '.join(unknown)} "
                         f"(known: {', '.join(REGISTRY)})")
    return args


async def build(adapter) -> dict[str, str]:
    artefacts: dict[str, str] = {}
    for part_no in _selected_parts():
        artefacts.update(await run_replica(adapter, part_no, REGISTRY[part_no]))
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
