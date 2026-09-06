"""Trace the current three drawing-unit setters on two owned blank drawings.

No original template, model or global preference is changed. One drawing records
each exact native setter return/readback; a fresh drawing runs the unchanged
adapter set_units_mm helper for comparison. No drawing is saved, rebuilt or
exported. This diagnoses the unit-system witness before template benchmarking.
Requires reviewed source, the coordinated seat and HARMONIC_SW_AUTOSTART=0.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
import _drawing_common as common  # noqa: E402
from solidworks_mcp.adapters.solidworks import drawing  # noqa: E402
from diagnostics._owned_native_documents import (  # noqa: E402
    DocumentKind,
    run_copy_diagnostic,
)
from diagnostics._owned_native_session import (  # noqa: E402
    require_owned_diagnostic_environment,
)
from diagnostics.benchmark_drawing_recipes import revision  # noqa: E402


def read_units(model):
    return {
        "system": int(
            model.GetUserPreferenceIntegerValue(drawing._SW_PREF_UNIT_SYSTEM)
        ),
        "linear": int(
            model.GetUserPreferenceIntegerValue(drawing._SW_PREF_UNITS_LINEAR)
        ),
        "decimals": int(
            model.GetUserPreferenceIntegerValue(drawing._SW_PREF_UNITS_LINEAR_DP)
        ),
    }


def trace_setters(model, decimals, rows, checkpoint):
    """Same order/values as current adapter, without swallowing native returns."""
    for name, preference, value in (
        ("unit_system", drawing._SW_PREF_UNIT_SYSTEM, drawing._SW_UNIT_SYSTEM_MMGS),
        ("linear_units", drawing._SW_PREF_UNITS_LINEAR, drawing._SW_LENGTH_MM),
        ("linear_decimals", drawing._SW_PREF_UNITS_LINEAR_DP, decimals),
    ):
        row = {"operation": name, "preference": preference, "value": value}
        rows.append(row)
        checkpoint()
        row["returned"] = model.SetUserPreferenceIntegerValue(preference, value)
        row["readback"] = read_units(model)
        checkpoint()


async def capture(adapter, report_root, decimals):
    if decimals not in (2, 3):
        raise ValueError("bounded unit control supports precision 2 or 3")
    template = common.PROJECT_DRWDOT.resolve(strict=True)
    report_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="unit-defaults-", dir=report_root))
    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(template)
    report = {
        "revision": revision("HEAD"),
        "template": str(template),
        "decimals": decimals,
        "status": "running",
        "setters": [],
    }
    path = directory / "units.json"

    def checkpoint():
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    checkpoint()
    try:
        with adapter.ownership.creating_document(
            DocumentKind.DRAWING, directory / "traced.SLDDRW"
        ):
            model = drawing.new_drawing(
                adapter,
                template=str(template),
                width=common.ASME_B_WIDTH_M,
                height=common.ASME_B_HEIGHT_M,
            )
        model = _early_bound(model, "IModelDoc2")
        report["before"] = read_units(model)
        checkpoint()
        trace_setters(model, decimals, report["setters"], checkpoint)
        report["traced_final"] = read_units(model)
        checkpoint()
        check("close unit trace drawing", await adapter.close_model(save=False))
        with adapter.ownership.creating_document(
            DocumentKind.DRAWING, directory / "helper.SLDDRW"
        ):
            model = drawing.new_drawing(
                adapter,
                template=str(template),
                width=common.ASME_B_WIDTH_M,
                height=common.ASME_B_HEIGHT_M,
            )
        report["helper_before"] = read_units(_early_bound(model, "IModelDoc2"))
        checkpoint()
        drawing.set_units_mm(adapter, decimals=decimals)
        report["helper_final"] = read_units(_early_bound(model, "IModelDoc2"))
        checkpoint()
        if report["before"] != report["helper_before"]:
            raise RuntimeError("fresh blank drawings had different initial units")
        if report["traced_final"] != report["helper_final"]:
            raise RuntimeError(
                "native traced setters differ from the actual adapter helper"
            )
        if any(row["returned"] is not True for row in report["setters"]):
            raise RuntimeError(
                "native unit setter rejected; inspect exact retained return/readback"
            )
        check("close unit helper drawing", await adapter.close_model(save=False))
        report["status"] = "captured_equal"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        checkpoint()
    return {"units": str(path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decimals", type=int, choices=(2, 3), default=2)
    parser.add_argument(
        "--report-root", type=Path, default=ROOT / "cad/out/reports/unit-defaults"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if args.worker:
        return run_copy_diagnostic(
            lambda adapter: capture(adapter, args.report_root, args.decimals)
        )
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--decimals",
            str(args.decimals),
            "--report-root",
            str(args.report_root.resolve()),
            "--worker",
        ],
        "drawing unit defaults control",
        log_stem="unit-defaults",
        com=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
