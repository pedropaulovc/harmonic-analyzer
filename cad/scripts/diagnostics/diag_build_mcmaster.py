r"""Diagnostic: rebuild the McMaster-Carr reference fasteners from scratch --
the fleet-wide successor of ``diag_build_91829A560.py`` (which stays as the
validated single-part original).

Replicas use vendor model harvests from ``cad/references/mcmaster/`` and
the corresponding ``cad/out/reports/mcmaster-<part>-dump.json``.
90280A837 and 91794A112 start from the supplied catalog dimensions and the
existing fillister family equations; their native comparison is required
before release.
Gates run against the vendor's own mass properties and face-area multiset
(see ``diag_mcmaster_lib.gate_and_save``).

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
import _telemetry  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    MCMASTER_DIR,
    REPORTS_DIR,
    run_replica,
)
from diagnostics.diag_build_90114A511 import build_90114A511  # noqa: E402
from diagnostics.diag_build_90126A211 import build_90126A211  # noqa: E402
from diagnostics.diag_build_90280A108 import build_90280A108  # noqa: E402
from diagnostics.diag_build_90280A194 import build_90280A194  # noqa: E402
from diagnostics.diag_build_90280A199 import build_90280A199  # noqa: E402
from diagnostics.diag_build_90280A201 import build_90280A201  # noqa: E402
from diagnostics.diag_build_90280A837 import build_90280A837  # noqa: E402
from diagnostics.diag_build_91247A720 import build_91247A720  # noqa: E402
from diagnostics.diag_build_91255A148 import build_91255A148  # noqa: E402
from diagnostics.diag_build_91410A538 import build_91410A538  # noqa: E402
from diagnostics.diag_build_91794A112 import build_91794A112  # noqa: E402
from diagnostics.diag_build_92240A539 import build_92240A539  # noqa: E402
from diagnostics.diag_build_91882A221 import build_91882A221  # noqa: E402
from diagnostics.diag_build_91882A425 import build_91882A425  # noqa: E402
from diagnostics.diag_build_9275K141 import build_9275K141  # noqa: E402
from diagnostics.diag_build_92865A585 import build_92865A585  # noqa: E402
from diagnostics.diag_build_93075A194 import build_93075A194  # noqa: E402
from diagnostics.diag_build_94025A150 import build_94025A150  # noqa: E402
from diagnostics.diag_build_94025A164 import build_94025A164  # noqa: E402
from diagnostics.diag_build_99607A213 import build_99607A213  # noqa: E402

REGISTRY = {
    "90126A211": build_90126A211,
    "94025A150": build_94025A150,
    "94025A164": build_94025A164,
    "90114A511": build_90114A511,
    "92240A539": build_92240A539,
    "91410A538": build_91410A538,
    "93075A194": build_93075A194,
    "92865A585": build_92865A585,
    "91247A720": build_91247A720,
    "91255A148": build_91255A148,
    "99607A213": build_99607A213,
    "91882A221": build_91882A221,
    "91882A425": build_91882A425,
    "90280A108": build_90280A108,
    "90280A194": build_90280A194,
    "90280A199": build_90280A199,
    "90280A201": build_90280A201,
    "90280A837": build_90280A837,
    "91794A112": build_91794A112,
    "9275K141": build_9275K141,
}


def _selected_parts() -> list[str]:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--all" in sys.argv[1:]:
        return list(REGISTRY)
    if not args:
        raise SystemExit(
            f"usage: diag_build_mcmaster.py <part_no>...|--all "
            f"(known: {', '.join(REGISTRY)})"
        )
    unknown = [a for a in args if a not in REGISTRY]
    if unknown:
        raise SystemExit(
            f"no builder for: {', '.join(unknown)} (known: {', '.join(REGISTRY)})"
        )
    return args


def _missing_inputs(part_no: str) -> str | None:
    """Why ``part_no`` cannot replicate here, or None when it can.

    The vendor files are local-only (gitignored, never committed), so a clean
    checkout has none: the replica needs the user's download and its harvest.
    """
    vendor = MCMASTER_DIR / f"{part_no}.SLDPRT"
    if not vendor.exists():
        return (
            f"vendor SLDPRT not present locally ({vendor}); download it from "
            f"https://www.mcmaster.com/{part_no}/ to cad/references/mcmaster/ "
            "(gitignored, never committed)"
        )
    dump = REPORTS_DIR / f"mcmaster-{part_no}-dump.json"
    if not dump.exists():
        return f"no harvest ({dump}); run diagnostics/diag_dump_part.py on {vendor}"
    return None


async def build(adapter) -> dict[str, str]:
    selected = _selected_parts()
    missing = {p: why for p in selected if (why := _missing_inputs(p))}
    if missing and "--all" not in sys.argv[1:]:
        raise SystemExit("; ".join(f"{p}: {why}" for p, why in missing.items()))
    for part_no, why in missing.items():
        _telemetry.warn(f"skipping {part_no}: {why}")
    artefacts: dict[str, str] = {}
    for part_no in selected:
        if part_no in missing:
            continue
        artefacts.update(await run_replica(adapter, part_no, REGISTRY[part_no]))
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
