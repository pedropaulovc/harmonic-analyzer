"""Temporary two-view native wrap calibration, not the full Title-fit matrix.

A registry Title first passes the native contract with the untouched template.
Then an exact-style drawing-owned note exercises auto-box wrapping while the
original template's fixed box demonstrates an explicitly inert LineLength
change. A separate, unmodified overlong fixture must actually wrap in the
native template and in its exported PDF. Sources are never restamped between
these controls. Every artifact, including scratch geometry, is under cad/out.

The executable source selects this mode: no argv-only cache identity. Remove
this executable and its temporary task after native proof is recorded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import CAD_ROOT, discard_open_documents, run_build  # noqa: E402
from _drawing_registry import DrawingLayout  # noqa: E402
from diagnostics.probe_title_field_fit import (  # noqa: E402
    CASES,
    WRAPPED_CASE,
    WRAP_M,
    _force_wraps,
    _physical_wrap_failures,
    _scratch_part,
    _single_sheet,
    _wrapped_failures,
)

OUT = CAD_ROOT / "out" / "probe" / "title-wrap-control"
REPORT = OUT / "title-wrap-control.json"
PDFS = {
    "wrapped-landscape": OUT / "line-length-only-landscape.pdf",
    "overlong-landscape": OUT / "overlong-landscape.pdf",
}


async def probe(adapter: Any) -> dict[str, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    captures: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "mode": "native-wrap-control",
        "success_means": "positive native baseline, matched auto-box positive, explicitly inert fixed-box control, and real template physical-wrap refusal",
        "not_proven_here": "the full 12-capture Title-fit matrix, portrait layout, and per-configuration source isolation",
        "cases": {name: list(CASES[name]) for name in (WRAPPED_CASE, "overlong")},
        "wrap_m": WRAP_M,
        "captures": captures,
        "construction_observations": observations,
    }
    try:
        number, title = CASES[WRAPPED_CASE]
        part = await _scratch_part(adapter, "wrap-control-title29", number, title)
        short = _single_sheet(
            adapter,
            "wrapped-landscape",
            part,
            DrawingLayout.LANDSCAPE,
            number,
            title,
            lambda draw, ddoc, sheet_view, source: _force_wraps(
                adapter, draw, ddoc, sheet_view, observations, source
            ),
            pdf_path=PDFS["wrapped-landscape"],
        )
        captures.append(short)
        failures = _wrapped_failures(short)
        if failures:
            report["control_failures"] = failures
            raise RuntimeError("native wrap calibration controls failed:\n" + "\n".join(failures))

        number, title = CASES["overlong"]
        part = await _scratch_part(adapter, "wrap-control-overlong", number, title)
        physical = _single_sheet(
            adapter,
            "overlong-landscape",
            part,
            DrawingLayout.LANDSCAPE,
            number,
            title,
            pdf_path=PDFS["overlong-landscape"],
        )
        captures.append(physical)
        failures = _physical_wrap_failures(physical, short["mutations"]["template_original"])
        report["control_failures"] = failures
        if failures:
            raise RuntimeError("real template physical-wrap control failed:\n" + "\n".join(failures))
        discard_open_documents(adapter)
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        # Failed leaves do not publish normal outputs. Preserve the raw native,
        # source/state, paragraph, box, and glyph evidence in task.log too.
        _telemetry.info(f"title wrap control partial proof: {json.dumps(report, default=str)}")
        raise
    finally:
        REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return {"report": str(REPORT), **{key: str(path) for key, path in PDFS.items()}}


if __name__ == "__main__":
    sys.exit(run_build(probe))
