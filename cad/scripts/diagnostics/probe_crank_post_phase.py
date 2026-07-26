r"""Exact phase sweep for the recentered post / 64T / 16T clearances.

Builds a throwaway three-component assembly from the production parts and
transforms.  The 64T is spun through one tooth pitch while the external 16T is
counter-spun at the 4:1 ratio, preserving the tooth-in-gap relationship.  Each
sample records exact SolidWorks interference volumes for post/64T and 64T/16T.

Run with SolidWorks already open::

    uv run python cad\scripts\diagnostics\probe_crank_post_phase.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pythoncom  # noqa: E402
from win32com.client import VARIANT  # noqa: E402

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
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    array = VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        _transform(rows, position_mm),
    )
    component.Transform2 = math_utility.CreateTransform(array)


def _interference_volumes(adapter) -> dict[tuple[str, str], float]:
    asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
    manager = _read_member(asm, "InterferenceDetectionManager")
    manager = _early_bound(manager, "IInterferenceDetectionMgr")
    manager.TreatCoincidenceAsInterference = False
    manager.TreatSubAssembliesAsComponents = True
    manager.IncludeMultibodyPartInterferences = True
    manager.MakeInterferingPartsTransparent = False
    manager.CreateFastenersFolder = False
    manager.UseTransform = False
    volumes: dict[tuple[str, str], float] = {}
    for interference in list(manager.GetInterferences() or []):
        interference = _early_bound(interference, "IInterference")
        pair = tuple(
            sorted(
                str(_read_member(component, "Name2"))
                for component in list(_read_member(interference, "Components") or [])
            )
        )
        volumes[pair] = volumes.get(pair, 0.0) + float(
            _read_member(interference, "Volume") or 0.0
        ) * 1e9
    manager.Done()
    return volumes


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())
    post_position = dta.cone_station(dta.POST_STATION)
    post_position[1] = dta.Y_BASE_TOP + dta.PLAT_T
    post = await place_component(
        adapter,
        "cone-pivot-post",
        post_position,
        [0.0, 180.0, 0.0],
        dta.ROT_Y_180,
        ground=True,
        label="fixed v2 post",
    )
    gear_centre = dta.cone_station(dta.GEAR64_STATION + dta.GEAR_AXIS_SHIFT)
    gear_position = [
        gear_centre[0] - dta.GEAR64_FACE / 2.0 * dta.SIN_I,
        dta.Y_DRIVE,
        gear_centre[2] - dta.GEAR64_FACE / 2.0 * dta.COS_I,
    ]
    gear = await place_component(
        adapter,
        "crank-drive-gear",
        gear_position,
        [0.0, dta.INCLINE_DEG, 0.0],
        dta.ROT_Y_INCLINE,
        ground=True,
        label="64T at recentered design station",
    )
    pinion_position = [
        dta.X_CRANK,
        dta.Y_CRANK,
        dta.PINION_TOOTH_Z - dta.PINION_FACE / 2.0,
    ]
    pinion = await place_component(
        adapter,
        "crank-pinion",
        pinion_position,
        [0.0, 0.0, -dta.PINION_SEED_DEG],
        rot_z_rows(-dta.PINION_SEED_DEG),
        ground=True,
        label="16T at paired design phase",
    )

    post_pair = tuple(sorted((post, gear)))
    mesh_pair = tuple(sorted((gear, pinion)))
    worst_post = 0.0
    worst_mesh = 0.0
    pitch = 360.0 / 64.0
    for step in range(46):
        phase = step * pitch / 45.0
        gear_rows = compose_rows(rot_z_rows(phase), dta.ROT_Y_INCLINE)
        pinion_rows = rot_z_rows(-dta.PINION_SEED_DEG - 4.0 * phase)
        _put_transform(adapter, gear, gear_rows, gear_position)
        _put_transform(adapter, pinion, pinion_rows, pinion_position)
        volumes = _interference_volumes(adapter)
        post_volume = volumes.get(post_pair, 0.0)
        mesh_volume = volumes.get(mesh_pair, 0.0)
        log(
            f"phase {phase:6.3f} deg: post/64T {post_volume:8.4f} mm^3; "
            f"64T/16T {mesh_volume:8.4f} mm^3"
        )
        worst_post = max(worst_post, post_volume)
        worst_mesh = max(worst_mesh, mesh_volume)

    if worst_post >= 0.0005 or worst_mesh >= 0.0005:
        raise RuntimeError(
            "full coupled phase sweep is not clear: "
            f"post/64T worst {worst_post:.4f} mm^3, "
            f"64T/16T worst {worst_mesh:.4f} mm^3"
        )
    log(
        f"full coupled phase sweep clear: post/64T worst {worst_post:.4f} mm^3; "
        f"64T/16T worst {worst_mesh:.4f} mm^3"
    )
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
