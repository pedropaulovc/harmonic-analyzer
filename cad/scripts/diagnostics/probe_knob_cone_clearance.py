r"""Exact sweep of cone-lock-knob radial offset against rotating cone gear #2.

The knob is stationary while the cone train rotates.  This throwaway assembly
tests candidate platform-local knob X stations over one complete tooth pitch of
the second cone gear and reports the worst exact SolidWorks interference volume.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pythoncom  # noqa: E402
from win32com.client import VARIANT  # noqa: E402

import _config  # noqa: E402
from _common import _early_bound, _read_member, check, log, run_build  # noqa: E402
from _assembly import place_component  # noqa: E402
from _transforms import compose_rows, rot_z_rows  # noqa: E402
import build_drive_train_assembly as dta  # noqa: E402


def _transform(rows: list[list[float]], position_mm: list[float]) -> list[float]:
    return [
        *(value for row in rows for value in row),
        *(value / 1000.0 for value in position_mm),
        1.0,
        0.0,
        0.0,
        0.0,
    ]


def _put_transform(adapter, name: str, rows, position_mm) -> None:
    asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
    component = asm.GetComponentByName(name)
    if component is None:
        raise RuntimeError(f"component {name!r} not found")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    component.Transform2 = utility.CreateTransform(
        VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8,
            _transform(rows, position_mm),
        )
    )


def _pair_volume(adapter, wanted: tuple[str, str]) -> float:
    asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
    manager = _read_member(asm, "InterferenceDetectionManager")
    manager = _early_bound(manager, "IInterferenceDetectionMgr")
    manager.TreatCoincidenceAsInterference = False
    manager.TreatSubAssembliesAsComponents = True
    manager.IncludeMultibodyPartInterferences = True
    manager.MakeInterferingPartsTransparent = False
    manager.CreateFastenersFolder = False
    manager.UseTransform = False
    volume = 0.0
    for interference in list(manager.GetInterferences() or []):
        interference = _early_bound(interference, "IInterference")
        pair = tuple(
            sorted(
                str(_read_member(component, "Name2"))
                for component in list(_read_member(interference, "Components") or [])
            )
        )
        if pair == wanted:
            volume += float(_read_member(interference, "Volume") or 0.0) * 1e9
    manager.Done()
    return volume


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())
    teeth = _config.cone_teeth(1)
    station = dta.SHAFT_T120_STATION + dta.GEAR_AXIS_SHIFT + dta.SEAT_PITCH
    centre = dta.cone_station(station)
    gear_position = [
        centre[0] - dta.CONE_FACE / 2.0 * dta.SIN_I,
        dta.Y_DRIVE,
        centre[2] - dta.CONE_FACE / 2.0 * dta.COS_I,
    ]
    gear = await place_component(
        adapter,
        "cone-gear",
        gear_position,
        [0.0, dta.INCLINE_DEG, 0.0],
        dta.ROT_Y_INCLINE,
        ground=True,
        configuration=f"T{teeth:03d}",
        label=f"cone gear #2 T{teeth:03d}",
    )
    knob_x, knob_z = dta._plate_local_to_machine(24.5, dta.PLAT_SLOT_E_Z)
    knob_position = [knob_x, dta.Y_BASE_TOP + dta.PLAT_T, knob_z]
    knob = await place_component(
        adapter,
        "cone-lock-knob",
        knob_position,
        [0.0, 0.0, 0.0],
        dta.IDENTITY,
        ground=True,
        label="stationary cone lock knob",
    )
    pair = tuple(sorted((gear, knob)))
    pitch = 360.0 / teeth
    candidates = tuple(
        dict.fromkeys((24.5, dta.PLAT_SLOT_E_X, 27.0, 28.0, 28.5, 29.0, 29.5))
    )
    worst_by_x: dict[float, float] = {}
    for local_x in candidates:
        knob_x, knob_z = dta._plate_local_to_machine(local_x, dta.PLAT_SLOT_E_Z)
        knob_position = [knob_x, dta.Y_BASE_TOP + dta.PLAT_T, knob_z]
        _put_transform(adapter, knob, dta.IDENTITY, knob_position)
        worst = 0.0
        for step in range(19):
            phase = step * pitch / 18.0
            rows = compose_rows(rot_z_rows(phase), dta.ROT_Y_INCLINE)
            _put_transform(adapter, gear, rows, gear_position)
            worst = max(worst, _pair_volume(adapter, pair))
        log(f"knob local X {local_x:4.1f} mm: worst {worst:.4f} mm^3")
        worst_by_x[local_x] = worst
    if worst_by_x[24.5] < 0.0005:
        raise RuntimeError("24.5 mm collision positive control unexpectedly cleared")
    selected_worst = worst_by_x[dta.PLAT_SLOT_E_X]
    if selected_worst >= 0.0005:
        raise RuntimeError(
            f"selected knob station {dta.PLAT_SLOT_E_X:.1f} mm collides: "
            f"worst {selected_worst:.4f} mm^3"
        )
    log(
        f"selected knob station {dta.PLAT_SLOT_E_X:.1f} mm clears; "
        f"24.5 mm positive control worst {worst_by_x[24.5]:.4f} mm^3"
    )
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
