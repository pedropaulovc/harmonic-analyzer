"""Measure a channel spring seat against the MATED lever, not the fixture's.

Builds a one-channel assembly, then at the native-contact gate (instead of
asserting) records the lever's solved transform against its analytic rows,
the spring/lever and spring/hook native states and distances, and re-runs the
seat search in place. Never saves: raises after writing the report.

    uv run cad/scripts/diagnostics/probe_channel_seat_in_assembly.py
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("CHANNEL_COUNT", "1")

import dodo  # noqa: E402
import _native_spring_contact as contact  # noqa: E402
import build_channel_assembly as bca  # noqa: E402
import channel_kinematics  # noqa: E402
import channel_spring_stock_geom as channel_stock  # noqa: E402
import settled_spring_seats  # noqa: E402
from _assembly import component_transform  # noqa: E402
from _common import _early_bound, run_build  # noqa: E402
from _transforms import ROT_Y_180, compose_rows, rot_z_rows  # noqa: E402
from diagnostics._seat_search import solve_component_contact  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "cad/out/reports/channel-seat-in-assembly.json"


class _Probed(RuntimeError):
    pass


def _distance(adapter, first: str, second: str) -> float:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    assembly = _early_bound(adapter.currentModel, "IAssemblyDoc")
    a = _early_bound(assembly.GetComponentByName(first), "IComponent2")
    b = _early_bound(assembly.GetComponentByName(second), "IComponent2")
    return float(model.ClosestDistance(a, b)[0]) * 1000.0


def _probe(adapter, asm_name: str, *, channel_count: int) -> None:
    del asm_name, channel_count
    amplitude = float(bca.amplitudes_for_probe[0])
    seat = settled_spring_seats.channel_seat(amplitude)
    found = contact._assembly_spring_instances(
        adapter, contact._CHANNEL_CONTACT_FAMILIES
    )
    spring = found["channel-spring-installed"][0].name
    hook = found["spring-hook"][0].name
    lever = found["channel-lever"][0].name
    state = channel_kinematics.solve_state(amplitude)
    rows = compose_rows(rot_z_rows(state["lever_tilt"]), ROT_Y_180)
    z_mid = bca.z_station(0) + bca.ARM_MID_DZ
    analytic = [
        *rows[0],
        *rows[1],
        *rows[2],
        bca.FULCRUM[0] / 1000.0,
        bca.FULCRUM[1] / 1000.0,
        z_mid / 1000.0,
    ]
    actual = component_transform(adapter, lever)
    ux, uy = seat.pose.axis_xy
    report = {
        "amplitude_mm": amplitude,
        "seat": asdict(seat.pose),
        "lever_transform_actual": actual,
        "lever_transform_analytic": analytic,
        "lever_rows_deviation": max(abs(a - b) for a, b in zip(actual[:9], analytic)),
        "lever_origin_deviation_mm": [
            (a - b) * 1000.0 for a, b in zip(actual[9:12], analytic[9:12])
        ],
        "spring_transform": component_transform(adapter, spring),
    }
    for label, first, second in (("upper", spring, lever), ("lower", spring, hook)):
        evidence = None
        try:
            evidence = asdict(
                contact.native_component_interference(
                    adapter, first, second, label=label
                )
            )
        except Exception as exc:  # noqa: BLE001 -- diagnostic: record, do not decide
            evidence = {"error": repr(exc)}
        report[f"{label}_native"] = evidence
        report[f"{label}_distance_mm"] = _distance(adapter, first, second)
    radius = channel_stock.WIRE_DIA_MM / 2.0
    report["search_lower"] = asdict(
        solve_component_contact(
            adapter, spring, hook, (-ux, -uy, 0.0), radius, label="assembly lower"
        )
    )
    report["search_upper"] = asdict(
        solve_component_contact(
            adapter, spring, lever, (ux, uy, 0.0), radius, label="assembly upper"
        )
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    raise _Probed(f"probe complete: {OUTPUT}")


def main() -> int:
    bca.amplitudes_for_probe = bca._config.amplitudes()
    bca.assert_assembly_spring_contacts = _probe
    with dodo._com_seat("probe-channel-seat-in-assembly"):
        try:
            return run_build(bca.build)
        except _Probed:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
