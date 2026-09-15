"""Recalibrate the fixed native spring seats in ``cad/config/machine/springs.yaml``.

The production assemblies insert every supplier spring at a FIXED measured
placement and only certify it (zero native overlap, bounded separation). That
table goes stale whenever an anchor part moves -- the channel lever's spring
hole, the gooseneck's arm end, the summing lever's tap stations, or a supplier
end loop. This driver re-measures it with the same native predicates the gate
uses, on the same three-part fixtures the retired in-build search used:

* channel: ``channel-lever`` (at the station's solved tilt) + ``spring-hook``
  + one ``9432K31`` length variant, per distinct calibrated amplitude;
* counter: ``boss-hook`` + one ``1330K524`` at the preset's balance length +
  ``gooseneck``, per preset (the gooseneck height is the measured output).

Each contact's native collision/clear boundary is located to 1e-6 mm, and the
component is then seated ``springs.boolean_stability_mm`` past it, on the clear
side, where the distance is measured and recorded. The boundary is NOT the
physical contact: SolidWorks' Boolean fails (status 1058) while ClosestDistance
still reads ~2.4e-5 mm at the tangent hook-on-bore pose, and the gate treats
that failure as interference -- so the boundary is where the Boolean starts
succeeding, and that edge MOVES: ~2.3e-6 mm between rebuilds of the same swept
spring and ~6e-7 mm between a fixture and the mated assembly (2026-09-15: two
calibration runs, then `assembly:channel` rejecting a fixture-certified seat by
6.3e-7 mm). A seat placed ON the edge is a coin flip at the gate; the allowance
covers the measured scatter and nothing else. The channel variant is rebuilt at its corrected inside length and
re-measured until both boundaries sit at the allowance within half of it.
Every seed comes from ``spring_mount_geom`` (the catalogue-nominal poses),
never from the table being replaced, so a stale table cannot bias the new one.

Run with SolidWorks open (the parts must already be built)::

    uv run cad/scripts/diagnostics/calibrate_spring_seats.py --write

Without ``--write`` the measurements only go to the JSON report.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from dataclasses import asdict, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import dodo  # noqa: E402
import _config  # noqa: E402
import _telemetry  # noqa: E402
import channel_kinematics  # noqa: E402
import channel_spring_stock_geom as channel_stock  # noqa: E402
import gooseneck_geom  # noqa: E402
import spring_mount_geom as spring_mounts  # noqa: E402
from _assembly import (  # noqa: E402
    assert_pose_ledger,
    check_no_interference,
    component_origin,
    component_transform,
    place_component,
    place_components_batch,
)
from _common import (  # noqa: E402
    SPRING_BLACK,
    _early_bound,
    apply_color,
    apply_material,
    check,
    force_rebuild,
    run_build,
    save_part_and_images,
)
from _cwm import put_component_pose  # noqa: E402
from _spring import build_spring  # noqa: E402
from _stock_fastener import _blank_recipe_references  # noqa: E402
from _transforms import ROT_Y_180, compose_rows, euler_from_rows, rot_z_rows  # noqa: E402
from build_channel_assembly import ARM_MID_DZ, FULCRUM, IDENTITY, z_station  # noqa: E402
from cone_pivot_post_installation import SUMMING_Z  # noqa: E402
from diagnostics._seat_search import ContactSolution, solve_component_contact  # noqa: E402
from diagnostics.diag_build_1330K524 import build_1330K524  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
SPRINGS_YAML = ROOT / "cad/config/machine/springs.yaml"
_MAX_CHANNEL_REFITS = 8


def _pose_record(pose: spring_mounts.SpringPose) -> dict:
    return {
        "length_mm": pose.length_mm,
        "lower_eye_xy": list(pose.lower_eye_xy),
        "upper_eye_xy": list(pose.upper_eye_xy),
        "axis_xy": list(pose.axis_xy),
        "centre_xy": list(pose.centre_xy),
        "clocking": pose.clocking,
    }


def _owned_titles(adapter, fixture, names: list[str]) -> list[str]:
    assembly = _early_bound(fixture, "IAssemblyDoc")
    titles = [str(fixture.GetTitle())]
    for name in names:
        component = _early_bound(assembly.GetComponentByName(name), "IComponent2")
        document = _early_bound(component.GetModelDoc2(), "IModelDoc2")
        titles.append(str(document.GetTitle()))
    return titles


def _close_all(adapter, titles: list[str]) -> None:
    for title in dict.fromkeys(titles):
        adapter.swApp.CloseDoc(title)
    adapter.currentModel = None


def _close_active_part(adapter) -> None:
    adapter.swApp.CloseDoc(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle())
    adapter.currentModel = None


def _land(
    adapter, name: str, direction: tuple[float, float, float], offset_mm: float
) -> None:
    target = component_transform(adapter, name)
    for axis, value in enumerate(direction):
        target[9 + axis] += value * offset_mm / 1000.0
    put_component_pose(adapter, name, target)
    actual = component_transform(adapter, name)
    if max(abs(a - b) for a, b in zip(actual, target, strict=True)) > 1e-12:
        raise RuntimeError(f"{name}: native seating transform readback mismatch")


def _allowance_mm() -> float:
    allowance = float(_config.machine("springs", "boolean_stability_mm"))
    if not math.isfinite(allowance) or allowance <= 0.0:
        raise ValueError("springs.boolean_stability_mm must be finite and positive")
    return allowance


def _correction_mm(contact: ContactSolution, allowance: float) -> float:
    """How far the moving component must still separate to sit ``allowance``
    past the native boundary (negative: it is already further out)."""
    return contact.clear_offset_mm + allowance


def _seated(label: str, contact: ContactSolution, allowance: float) -> bool:
    correction = _correction_mm(contact, allowance)
    seated = abs(correction) <= allowance / 2.0 and contact.seed_distance_mm is not None
    _telemetry.info(
        f"{label}: native boundary at {contact.clear_offset_mm:+.3e} mm, "
        f"pose distance {contact.seed_distance_mm}, correction {correction:+.3e} mm"
        f" -> {'seated' if seated else 'refit'}"
    )
    return seated


# --------------------------------------------------------------- channel


async def _calibrate_channel(
    adapter, amplitude: float, variant_index: int, report: dict
) -> dict:
    """Measure one channel station; returns the springs.yaml ``channel_seats`` row."""
    station = 0
    z_mid = z_station(station) + ARM_MID_DZ
    pose = spring_mounts.channel_pose(amplitude)
    seed = pose
    variant = f"channel-spring-calib{variant_index:02d}"
    state = channel_kinematics.solve_state(amplitude)
    lever_rows = compose_rows(rot_z_rows(state["lever_tilt"]), ROT_Y_180)
    ux, uy = pose.axis_xy
    radius = channel_stock.WIRE_DIA_MM / 2.0
    allowance = _allowance_mm()
    iterations: list[dict] = []
    report["channel"].append(
        {
            "amplitude_mm": amplitude,
            "seed": _pose_record(seed),
            "iterations": iterations,
        }
    )
    for refit in range(_MAX_CHANNEL_REFITS):
        await build_spring(adapter, variant, pose.length_mm, views=[])
        _close_active_part(adapter)
        titles: list[str] = []
        try:
            check("create channel seat fixture", await adapter.create_assembly())
            fixture = _early_bound(adapter.currentModel, "IModelDoc2")
            lever = await place_component(
                adapter,
                "channel-lever",
                [FULCRUM[0], FULCRUM[1], z_mid],
                euler_from_rows(lever_rows),
                lever_rows,
                label=f"channel-lever a={amplitude:g}",
            )
            spring, hook = await place_components_batch(
                adapter,
                [
                    {
                        "part": variant,
                        "position": [*pose.centre_xy, z_mid],
                        "rotation": [0.0, 0.0, 0.0],
                        "rows": pose.rotation_rows,
                        "ground": True,
                    },
                    {
                        "part": "spring-hook",
                        "position": [*spring_mounts.CHANNEL_ANCHOR_XY, z_mid],
                        "rotation": [0.0, 0.0, 0.0],
                        "rows": IDENTITY,
                        "ground": True,
                    },
                ],
                label="channel seat fixture",
            )
            titles = _owned_titles(adapter, fixture, [lever, spring, hook])
            lower = solve_component_contact(
                adapter,
                spring,
                hook,
                (-ux, -uy, 0.0),
                radius,
                label=f"channel {amplitude:g} lower",
                locate_only=True,
            )
            upper = solve_component_contact(
                adapter,
                spring,
                lever,
                (ux, uy, 0.0),
                radius,
                label=f"channel {amplitude:g} upper",
                locate_only=True,
            )
            seated = _seated(
                f"channel {amplitude:g} lower", lower, allowance
            ) and _seated(f"channel {amplitude:g} upper", upper, allowance)
            iterations.append(
                {
                    "refit": refit + 1,
                    "length_mm": pose.length_mm,
                    "lower": asdict(lower),
                    "upper": asdict(upper),
                }
            )
            if seated:
                check_no_interference(adapter)
                assert_pose_ledger(adapter)
        finally:
            _close_all(adapter, titles)
        if seated:
            channel_stock.check_length_mm(pose.length_mm)
            _telemetry.success(
                f"channel a={amplitude:g}: seated after {refit + 1} refit(s), "
                f"L={pose.length_mm:.9f} mm, eyes x {pose.lower_eye_xy[0]:.6f}/{pose.upper_eye_xy[0]:.6f}"
            )
            return {
                "amplitude_mm": amplitude,
                "pose": _pose_record(pose),
                "final_distance_mm": {
                    "lower": lower.seed_distance_mm,
                    "upper": upper.seed_distance_mm,
                },
            }
        move_lower = _correction_mm(lower, allowance)
        move_upper = _correction_mm(upper, allowance)
        lower_eye = tuple(
            pose.lower_eye_xy[k] - pose.axis_xy[k] * move_lower for k in range(2)
        )
        upper_eye = tuple(
            pose.upper_eye_xy[k] + pose.axis_xy[k] * move_upper for k in range(2)
        )
        pose = replace(
            pose,
            length_mm=channel_stock.check_length_mm(
                pose.length_mm + move_lower + move_upper
            ),
            lower_eye_xy=lower_eye,
            upper_eye_xy=upper_eye,
            centre_xy=tuple(
                (a + b) / 2.0 for a, b in zip(lower_eye, upper_eye, strict=True)
            ),
        )
    raise RuntimeError(f"channel a={amplitude:g}: native seating did not converge")


# --------------------------------------------------------------- counter


async def _build_counter_variant(adapter, name: str, length_mm: float) -> None:
    check("create_part", await adapter.create_part())
    try:
        await build_1330K524(adapter, None, length_mm=length_mm)
    finally:
        if hasattr(adapter, "_mcm_com_map"):
            delattr(adapter, "_mcm_com_map")
    _blank_recipe_references(adapter)
    await force_rebuild(adapter)
    await apply_material(adapter, str(_config.parts("counter-spring")["material"]))
    await apply_color(adapter, SPRING_BLACK)
    await save_part_and_images(adapter, name, [])
    _close_active_part(adapter)


async def _calibrate_counter(
    adapter, preset: str, amplitudes: list[float], report: dict
) -> dict:
    """Measure one preset's counter seat; returns the ``presets.<name>.counter`` row."""
    balance = spring_mounts.solve_bank_balance(amplitudes)
    if not balance.static_balance or balance.counter_pose is None:
        raise RuntimeError(f"{preset}: counter cannot balance the channel bank")
    seed = balance.counter_pose
    ux, uy = seed.axis_xy
    gooseneck_y = (
        seed.upper_eye_xy[1]
        + spring_mounts.counter_upper_support_offset(seed.axis_xy)
        - gooseneck_geom.ARM_Y
    )
    variant = f"counter-spring-calib-{preset}"
    await _build_counter_variant(adapter, variant, seed.length_mm)
    lower_direction = (-ux, -uy, 0.0)
    upper_direction = (0.0, -1.0, 0.0)
    bracket = spring_mounts.MIN_CLEARANCE_MM / 2.0
    titles: list[str] = []
    try:
        check("create counter seat fixture", await adapter.create_assembly())
        fixture = _early_bound(adapter.currentModel, "IModelDoc2")
        boss, counter, gooseneck = await place_components_batch(
            adapter,
            [
                {
                    "part": "boss-hook",
                    "position": [*spring_mounts.COUNTER_ANCHOR_XY, SUMMING_Z],
                    "rotation": [0.0, 0.0, 0.0],
                    "rows": IDENTITY,
                    "ground": True,
                },
                {
                    "part": variant,
                    "position": [*seed.centre_xy, SUMMING_Z],
                    "rotation": euler_from_rows(seed.rotation_rows),
                    "rows": seed.rotation_rows,
                    "ground": True,
                },
                {
                    "part": "gooseneck",
                    "position": [spring_mounts.COLUMN_X, gooseneck_y, SUMMING_Z],
                    "rotation": [0.0, 180.0, 0.0],
                    "rows": ROT_Y_180,
                    "ground": True,
                },
            ],
            label="counter seat fixture",
        )
        titles = _owned_titles(adapter, fixture, [boss, counter, gooseneck])
        allowance = _allowance_mm()
        lower = solve_component_contact(
            adapter,
            counter,
            boss,
            lower_direction,
            bracket,
            label=f"{preset} counter lower",
            locate_only=True,
        )
        _land(adapter, counter, lower_direction, _correction_mm(lower, allowance))
        upper = solve_component_contact(
            adapter,
            gooseneck,
            counter,
            upper_direction,
            bracket,
            label=f"{preset} counter upper",
            locate_only=True,
        )
        _land(adapter, gooseneck, upper_direction, _correction_mm(upper, allowance))
        lower_check = solve_component_contact(
            adapter,
            counter,
            boss,
            lower_direction,
            bracket,
            label=f"{preset} counter lower verify",
            locate_only=True,
        )
        upper_check = solve_component_contact(
            adapter,
            gooseneck,
            counter,
            upper_direction,
            bracket,
            label=f"{preset} counter upper verify",
            locate_only=True,
        )
        for label, contact in (("lower", lower_check), ("upper", upper_check)):
            if not _seated(f"{preset} counter {label}", contact, allowance):
                raise RuntimeError(
                    f"{preset} counter {label}: landed pose is not seated ({contact!r})"
                )
        check_no_interference(adapter)
        actual_centre = component_origin(adapter, counter)
        actual_gooseneck_y = component_origin(adapter, gooseneck)[1]
    finally:
        _close_all(adapter, titles)
    dx, dy = (actual_centre[i] - seed.centre_xy[i] for i in range(2))
    pose = replace(
        seed,
        centre_xy=tuple(actual_centre[:2]),
        lower_eye_xy=(seed.lower_eye_xy[0] + dx, seed.lower_eye_xy[1] + dy),
        upper_eye_xy=(seed.upper_eye_xy[0] + dx, seed.upper_eye_xy[1] + dy),
    )
    report["counter"].append(
        {
            "preset": preset,
            "seed": _pose_record(seed),
            "seed_gooseneck_origin_y_mm": gooseneck_y,
            "lower": asdict(lower),
            "upper": asdict(upper),
            "lower_verify": asdict(lower_check),
            "upper_verify": asdict(upper_check),
        }
    )
    _telemetry.success(
        f"{preset} counter: spring moved {_correction_mm(lower, allowance):.9g} mm along -axis, gooseneck "
        f"{_correction_mm(upper, allowance):.9g} mm along -Y; L={pose.length_mm:.9f}, eyes x "
        f"{pose.lower_eye_xy[0]:.6f}/{pose.upper_eye_xy[0]:.6f}, gooseneck y {actual_gooseneck_y:.9f}"
    )
    return {
        "pose": _pose_record(pose),
        "gooseneck_origin_y_mm": actual_gooseneck_y,
        "final_distance_mm": {
            "lower": lower_check.seed_distance_mm,
            "upper": upper_check.seed_distance_mm,
        },
    }


# ---------------------------------------------------------------- driver


def _merge_yaml(
    channel_rows: list[dict], counters: dict[str, dict], source: str
) -> None:
    import yaml

    document = yaml.safe_load(SPRINGS_YAML.read_text(encoding="utf-8"))
    springs = document["springs"]
    springs["source"] = source
    springs["channel_seats"] = channel_rows
    for preset, counter in counters.items():
        springs["presets"][preset]["counter"] = counter
    text = yaml.safe_dump(document, sort_keys=False, allow_unicode=False, width=88)
    header = "\n".join(
        line
        for line in SPRINGS_YAML.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    )
    SPRINGS_YAML.write_text(header + "\n" + text, encoding="utf-8", newline="\n")


async def calibrate(
    adapter, presets: list[str], output: Path, write: bool, source: str
) -> dict[str, str]:
    table = _config.machine("springs", "presets")
    unknown = [name for name in presets if name not in table]
    if unknown:
        raise ValueError(f"unknown presets {unknown}; have {sorted(table)}")
    amplitudes = list(
        dict.fromkeys(
            float(a) for name in presets for a in table[name]["amplitudes_mm"]
        )
    )
    if any(a < 0.0 or not math.isfinite(a) for a in amplitudes):
        raise ValueError(
            f"preset amplitudes must be finite and nonnegative: {amplitudes}"
        )
    if write:
        # _merge_yaml REPLACES springs.channel_seats, and channel_seat() matches an
        # amplitude exactly (no fit, no interpolation), so a write that calibrated
        # only some presets would delete the rows the omitted ones need. Refuse it
        # here, before the COM run, rather than leave a table that fails at build.
        missing = [
            (name, a)
            for name in sorted(table)
            for a in (float(x) for x in table[name]["amplitudes_mm"])
            if a not in amplitudes
        ]
        if missing:
            raise ValueError(
                "--write rewrites every channel seat, so the calibrated presets must "
                f"cover all configured amplitudes; missing {missing}. Calibrate "
                f"{sorted(table)} together, or drop --write."
            )
    report: dict = {
        "status": "started",
        "presets": presets,
        "channel": [],
        "counter": [],
    }
    channel_rows: list[dict] = []
    counters: dict[str, dict] = {}
    try:
        for index, amplitude in enumerate(amplitudes):
            channel_rows.append(
                await _calibrate_channel(adapter, amplitude, index, report)
            )
        for name in presets:
            counters[name] = await _calibrate_counter(
                adapter, name, [float(a) for a in table[name]["amplitudes_mm"]], report
            )
        report["channel_seats"] = channel_rows
        report["counters"] = counters
        report["status"] = "completed"
        if write:
            _merge_yaml(channel_rows, counters, source)
            report["written"] = str(SPRINGS_YAML)
        return {"report": str(output)}
    except BaseException:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        raise
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--presets", nargs="+", default=["neutral", "square"])
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "cad/out/reports/spring-seat-calibration.json",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="rewrite springs.yaml with the measurements",
    )
    parser.add_argument(
        "--source",
        default="Native fixture calibration (diagnostics/calibrate_spring_seats.py); "
        "full saved-assembly acceptance is required by the build gates.",
    )
    args = parser.parse_args()
    with dodo._com_seat("calibrate-spring-seats"):
        return run_build(
            lambda adapter: calibrate(
                adapter, args.presets, args.output.resolve(), args.write, args.source
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
