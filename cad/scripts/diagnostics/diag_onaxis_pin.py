r"""Diagnostic: why does the on-axis pin-hole `horizontal_distance` dim fail?

Minimal repro for the build_transgear_removable bore+pins failure (batch-2
validation): bore circle coincident at the origin, second circle at (9.5, 0),
`horizontal_points` to origin succeeds, the driving `horizontal_distance`
dim then fails. Scenarios isolate the suspects: the origin-occluding bore
centre, sketch inference at circle creation, and relation-before-dim order.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_onaxis_pin.py
"""

from __future__ import annotations

import sys
from typing import Any

from _common import check, run_build, set_sketch_direct_db

PIN_X = 9.5
PIN_R = 1.75
BORE_R = 6.0

RESULTS: list[tuple[str, bool, str]] = []


async def _try(label: str, coro) -> bool:
    res = await coro
    ok = bool(res.is_success)
    RESULTS.append((label, ok, "" if ok else str(res.error)))
    print(f"  {'OK ' if ok else 'XX '} {label}" + ("" if ok else f": {res.error}"))
    return ok


async def _scenario(adapter: Any, name: str, with_bore: bool, direct_db: bool,
                    dim_first: bool) -> None:
    print(f"--- scenario {name} (bore={with_bore}, direct_db={direct_db}, "
          f"dim_first={dim_first})")
    check(f"{name}: create_sketch", await adapter.create_sketch("Front"))
    if direct_db:
        set_sketch_direct_db(adapter, True)
    if with_bore:
        bore = check(f"{name}: add bore", await adapter.add_circle(0.0, 0.0, BORE_R))
        await _try(f"{name}: bore coincident origin",
                   adapter.add_sketch_constraint(f"{bore}.center", "origin", "coincident"))
        await _try(f"{name}: bore diameter",
                   adapter.add_sketch_dimension(bore, None, "diameter", 2 * BORE_R))
    pin = check(f"{name}: add pin", await adapter.add_circle(PIN_X, 0.0, PIN_R))
    if direct_db:
        set_sketch_direct_db(adapter, False)
    steps = [
        ("hdist", adapter.add_sketch_dimension(
            f"{pin}.center", "origin", "horizontal_distance", PIN_X)),
        ("horizontal_points", adapter.add_sketch_constraint(
            f"{pin}.center", "origin", "horizontal_points")),
    ]
    if not dim_first:
        steps.reverse()
    for step_label, coro in steps:
        await _try(f"{name}: {step_label}", coro)
    await _try(f"{name}: pin diameter",
               adapter.add_sketch_dimension(pin, None, "diameter", 2 * PIN_R))
    res = await adapter.check_sketch_fully_defined()
    state = res.data.get("definition_state") if res.is_success and res.data else "?"
    print(f"  ..  {name}: sketch state = {state}")
    check(f"{name}: exit_sketch", await adapter.exit_sketch())


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # A: exact repro — bore first, inference ON, relation then dim.
    await _scenario(adapter, "A", with_bore=True, direct_db=False, dim_first=False)
    # B: no bore — is the origin-occluding point the trigger?
    await _scenario(adapter, "B", with_bore=False, direct_db=False, dim_first=False)
    # C: bore, but circles created direct-to-DB (no inference).
    await _scenario(adapter, "C", with_bore=True, direct_db=True, dim_first=False)
    # D: bore, inference ON, dim added BEFORE the relation.
    await _scenario(adapter, "D", with_bore=True, direct_db=False, dim_first=True)

    # E: same as A but with a solid disc behind the sketch plane (the real
    # bore+pins sketch sits on the Front plane against the gear blank's
    # z=0 face — inference can see model geometry there).
    check("create_sketch disc", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    disc = check("add disc", await adapter.add_circle(0.0, 0.0, 26.0))
    set_sketch_direct_db(adapter, False)
    await _try("disc coincident origin",
               adapter.add_sketch_constraint(f"{disc}.center", "origin", "coincident"))
    await _try("disc diameter",
               adapter.add_sketch_dimension(disc, None, "diameter", 52.0))
    check("exit_sketch disc", await adapter.exit_sketch())
    check("extrude disc",
          await adapter.create_extrusion(ExtrusionParameters(depth=5.0)))
    await _scenario(adapter, "E", with_bore=True, direct_db=False, dim_first=False)

    # F: fresh part with equation-manager globals (the gear scripts set ~12
    # before any geometry), then the repro sequence.
    from build_cone_gear import set_global

    check("create_part F", await adapter.create_part())
    await set_global(adapter, "ToothCount", "24", 24.0)
    await set_global(adapter, "DP", "12.7", 12.7)
    await set_global(adapter, "Ra", '("ToothCount" + 2) / "DP" / 2', (24 + 2) / 12.7 / 2)
    await _scenario(adapter, "F", with_bore=True, direct_db=False, dim_first=False)

    # G: fresh part, disc made the gear-blank way — a Top-plane rectangle
    # REVOLVED about an on-axis centerline through the origin (the known
    # degenerate-topology pattern) — then the repro sequence on Front.
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part G", await adapter.create_part())
    check("create_sketch G blank", await adapter.create_sketch("Top"))
    rect = [(0.0, 0.0), (26.0, 0.0), (26.0, -5.0), (0.0, -5.0)]
    from _common import add_line_chain, define_rectilinear_chain, ensure_fully_defined

    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(adapter, lines, rect, label="G blank")
    set_sketch_direct_db(adapter, True)
    check("G centerline", await adapter.add_centerline(0.0, -1.0, 0.0, -4.0))
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "G blank sketch")
    check("exit_sketch G blank", await adapter.exit_sketch())
    check("revolve G blank", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    await _scenario(adapter, "G", with_bore=True, direct_db=False, dim_first=False)

    # H: same on-axis-revolve part; pin dimmed against the BORE CENTRE
    # instead of the origin (point-pair dim with no origin operand).
    check("create_sketch H", await adapter.create_sketch("Front"))
    bore = check("H: add bore", await adapter.add_circle(0.0, 0.0, BORE_R))
    await _try("H: bore coincident origin",
               adapter.add_sketch_constraint(f"{bore}.center", "origin", "coincident"))
    await _try("H: bore diameter",
               adapter.add_sketch_dimension(bore, None, "diameter", 2 * BORE_R))
    pin = check("H: add pin", await adapter.add_circle(PIN_X, 0.0, PIN_R))
    await _try("H: horizontal_points pin->origin",
               adapter.add_sketch_constraint(f"{pin}.center", "origin", "horizontal_points"))
    await _try("H: hdist pin->bore.center",
               adapter.add_sketch_dimension(f"{pin}.center", f"{bore}.center",
                                            "horizontal_distance", PIN_X))
    await _try("H: pin diameter",
               adapter.add_sketch_dimension(pin, None, "diameter", 2 * PIN_R))
    res = await adapter.check_sketch_fully_defined()
    state = res.data.get("definition_state") if res.is_success and res.data else "?"
    print(f"  ..  H: sketch state = {state}")
    check("H: exit_sketch", await adapter.exit_sketch())

    # I: same on-axis-revolve part, geometry created direct-to-DB (no
    # inference — the pin sits ON the revolve's seam edge along +X).
    await _scenario(adapter, "I", with_bore=True, direct_db=True, dim_first=False)
    print("\n=== summary ===")
    for label, ok, err in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  [{err}]"))
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
