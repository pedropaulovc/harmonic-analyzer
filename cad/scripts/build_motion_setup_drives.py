r"""Setup-DOF articulation drives (plan step 5, the p0/p1/p2 motion studies).

The crank is the device's ONE operating DOF and the full-device study
(``build_motion_study.py``) drives it. The other three freedoms the refactor
opened are quasi-static SETUP DOFs -- the operator poses them by hand before a
run, then they hold:

    p1  cone disengage  -- the cone set swings horizontally out of mesh about the
                           cone-pivot-post's vertical pivot (ch.12, p.18).
    p2  pinion engage   -- the strap+alignment-pinion group swings on the torque
                           shaft to mesh the cylinder train (ch.25, p.66).
    p0  amplitude adjust -- each amplitude bar swings about its top pin; the swing
                           is the channel's amplitude coefficient (ch.17).

Each is proven the same way the crank is: a short Basic Motion sweep on the
STANDALONE subassembly that carries the DOF (drive-train for p1/p2, channel for
p0 -- far lighter than the flexible full device), with the park driver suppressed
so the joint is free and a rotary motor on the swing axis. The sampled pose of
the driven member must advance with the motor (``assert_motion_progressed``); a
frozen member would mean the "DOF" is actually still pinned. The sub is NEVER
saved (the on-disk rest pose stays bit-exact); each drive exports a short mp4.

Why the standalone sub and not the full device: these park drivers are TOP-LEVEL
mates of the standalone sub, so they suppress by name with no flexible-sub
indirection, and the swing axes are depth-1 component refs. The full-device study
already covers the crank; layering three more heavy flexible solves onto it buys
nothing the sub-level sweep does not prove.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_motion_setup_drives.py [p1|p2|p0|all]
"""

from __future__ import annotations

import sys
from typing import Any

from _common import OUT_PNG, OUT_SLDASM, check, log, run_build
from build_motion_study import (
    ANGLE,
    DISTANCE,
    _comp_xform,
    _entity_ref,
    _family,
    _find_one,
    _iter_mates,
    _real_parts,
    _reset_to_assembled,
    _rot_angle,
    assert_motion_progressed,
)

import _telemetry

# A setup DOF is posed by hand and then held, so the demonstration sweep is
# short and gentle: 3 RPM for 2 s -> ~36 deg of swing, enough to read the arc
# without spinning the member through a full turn (these joints have no hard
# stop in the kinematic model, so a fast/long motor would just keep rotating).
SWING_RPM = 3.0
SWING_DURATION = 2.0
SWING_MIN_DEG = 5.0  # the driven member must advance at least this far to pass


def _gear_mate_names(mates: list[dict[str, Any]]) -> list[str]:
    """Names of every gear mate in ``mates`` (mate type contains 'gear')."""
    return [m["name"] for m in mates if "gear" in str(m.get("type", "")).lower()]


def _family_driver_names(adapter: Any, root: str, family: str,
                         only_type: int | None = None) -> list[str]:
    """Names of the single-real-part DISTANCE/ANGLE park drivers on FAMILY.

    A park driver references exactly one real part plus a root plane, so
    ``_real_parts`` leaving a single name marks it. ``only_type`` narrows to the
    swing driver when a family also carries positional locators of the other
    type: the cone-pivot-post is LOCATED by three DISTANCE mates (height + plan
    X/Z) and its swing is held by the lone ANGLE driver, so p1 must suppress
    ANGLE only -- suppressing the distances too would unmoor the post in space.
    """
    names: list[str] = []
    for _f, _m, name, mtype, parts, _v in _iter_mates(
            adapter, adapter.currentModel, read_values=False, progress_every=40):
        if mtype not in (DISTANCE, ANGLE):
            continue
        if only_type is not None and mtype != only_type:
            continue
        reals = _real_parts(parts, root)
        if len(reals) == 1 and _family(reals[0]) == family:
            names.append(name)
    return names


def _part_driver_names(adapter: Any, root: str, part: str) -> list[str]:
    """Names of every single-real DISTANCE/ANGLE driver pinning EXACTLY ``part``.

    For p0 only ONE bar is driven, so its drivers are matched by full instance
    name (``amplitude-bar-7``), not family -- the other 19 bars stay pinned.
    """
    names: list[str] = []
    for _f, _m, name, mtype, parts, _v in _iter_mates(
            adapter, adapter.currentModel, read_values=False, progress_every=40):
        if mtype not in (DISTANCE, ANGLE):
            continue
        reals = _real_parts(parts, root)
        if len(reals) == 1 and reals[0] == part:
            names.append(name)
    return names


async def _suppress(adapter: Any, names: list[str], label: str) -> None:
    from solidworks_mcp.adapters.base import SuppressMateParameters
    if not names:
        raise RuntimeError(f"{label}: found no mate to suppress (driver missing?)")
    for name in names:
        check(f"suppress {name}", await adapter.suppress_mate(
            SuppressMateParameters(name=name, suppress=True)))
    log(f"  {label}: suppressed {len(names)} mate(s): {names}")


async def _run_swing_study(adapter: Any, motor_axis, driven_needle: str,
                           label: str, video_tag: str) -> dict[str, str]:
    """Add a rotary motor on ``motor_axis``, solve a short sweep, prove the
    driven member articulates, export an mp4. Never saves the doc."""
    from solidworks_mcp.adapters.base import (
        MotionExportParameters,
        MotionMotorParameters,
        MotionStudyParameters,
        MotionStudyRefParameters,
        MotionTimeParameters,
    )

    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    made = check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=SWING_DURATION, activate=True)))
    log(f"  {label}: study {made['name']!r}, motor on "
        f"{motor_axis.name}@{motor_axis.component} ({SWING_RPM} RPM)")
    check("add_motor", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=motor_axis, speed=SWING_RPM, study_name="")))

    await _reset_to_assembled(adapter)
    log(f"  {label}: Calculate() -- short sub-level swing solve ...")
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))

    driven, _ = _find_one(adapter, driven_needle)
    if driven is None:
        raise RuntimeError(f"{label}: driven member {driven_needle!r} not found")
    samples = []
    steps = 12
    for s in range(steps + 1):
        t = SWING_DURATION * s / steps
        check(f"set_time {t:.2f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name="")))
        samples.append((t, _comp_xform(adapter, driven)))
    base = next((a for _t, a in samples if a is not None), None)
    span = max((_rot_angle(base, a) for _t, a in samples if a is not None),
               default=0.0) if base is not None else 0.0
    log(f"  {label}: {driven_needle} swing span = {span:.2f} deg over "
        f"{SWING_DURATION}s")

    # Two gates: the member tracked the motor the whole run (no aborted solve),
    # and it covered a real arc (the DOF is genuinely free, not still pinned).
    assert_motion_progressed(samples, SWING_DURATION, label,
                             min_frac=0.75, stall_frac=0.25)
    if span < SWING_MIN_DEG:
        raise RuntimeError(
            f"{label}: driven member swung only {span:.2f} deg (< {SWING_MIN_DEG}) "
            f"-- the setup DOF is still pinned (park driver not freed?) or the "
            f"motor did not couple to it")

    vid = (OUT_PNG.parent / f"{video_tag}.mp4").resolve()
    res = await adapter.export_motion_video(MotionExportParameters(
        file_path=str(vid), study_name="", frames_per_second=25.0))
    out = {"dof": label, "span_deg": f"{span:.2f}"}
    if res.is_success:
        log(f"  {label}: video {res.data['bytes']} bytes -> {vid}")
        out["video"] = str(vid)
    return out


async def _drive_p1(adapter: Any) -> dict[str, str]:
    """p1: cone set swings out of mesh. Decouple the 21 gear meshes (the cone
    cluster cannot stay velocity-coupled to the cylinders while leaving mesh, so
    suppress every gear mesh) and free the post's swing (its lone ANGLE park
    driver), then motor the post about its vertical pivot."""
    path = str(OUT_SLDASM / "drive-train.SLDASM")
    check("open drive-train", await adapter.open_model(path))
    mates = check("list mates", await adapter.list_mates())
    await _suppress(adapter, _gear_mate_names(mates), "p1 gear meshes")
    await _suppress(adapter, _family_driver_names(
        adapter, "drive-train", "cone-pivot-post", only_type=ANGLE),
        "p1 cone-post swing park")
    post, post_name = _find_one(adapter, "cone-pivot-post")
    if post is None:
        raise RuntimeError("p1: cone-pivot-post not found")
    motor_axis = _entity_ref(post_name, "Axis2", "AXIS")
    return await _run_swing_study(
        adapter, motor_axis, "cone-pivot-post",
        "p1 cone disengage", "drive-train-p1-cone-swing")


async def _drive_p2(adapter: Any) -> dict[str, str]:
    """p2: the strap+pinion rigid group swings on the torque shaft to engage.
    Free the swing (the front strap's lone ANGLE park driver, PARK_pinion_swing
    -- the group's axial DISTANCE seats stay engaged, exactly the p1 locator
    pattern), then motor a strap about its pivot bore (Axis1, collinear with
    the torque shaft); the journaled pinion must ride the arc."""
    path = str(OUT_SLDASM / "drive-train.SLDASM")
    check("open drive-train", await adapter.open_model(path))
    await _suppress(adapter, _family_driver_names(
        adapter, "drive-train", "pinion-bracket", only_type=ANGLE),
        "p2 pinion swing park")
    bracket, bracket_name = _find_one(adapter, "pinion-bracket")
    if bracket is None:
        raise RuntimeError("p2: pinion-bracket not found")
    motor_axis = _entity_ref(bracket_name, "Axis1", "AXIS")
    return await _run_swing_study(
        adapter, motor_axis, "alignment-pinion",
        "p2 pinion engage", "drive-train-p2-pinion-swing")


async def _drive_p0(adapter: Any) -> dict[str, str]:
    """p0: an amplitude bar swings about its top pin (the channel's amplitude
    coefficient). Free ONE bar (suppress its own single-real drivers, leaving the
    other 19 pinned), then motor it about its top-pin bore (Axis1)."""
    path = str(OUT_SLDASM / "channel.SLDASM")
    check("open channel", await adapter.open_model(path))
    bar, bar_name = _find_one(adapter, "amplitude-bar")
    if bar is None:
        raise RuntimeError("p0: amplitude-bar not found")
    # In a default-`free` build the amplitude park driver is DEFERRED (recorded, not
    # authored -- see AGENTS.md "Default-free DOF"), so the bar's amplitude slide is
    # ALREADY free: there is nothing to suppress. Suppress only if the driver exists
    # (a `locked` build, where it is authored + engaged).
    driver_names = _part_driver_names(adapter, "channel", bar_name)
    if driver_names:
        await _suppress(adapter, driver_names, f"p0 amplitude park ({bar_name})")
    else:
        log(f"  p0: {bar_name} amplitude DOF already free "
            "(deferred park driver -- not authored in the free build)")
    motor_axis = _entity_ref(bar_name, "Axis1", "AXIS")
    return await _run_swing_study(
        adapter, motor_axis, bar_name,
        "p0 amplitude adjust", "channel-p0-amplitude-swing")


_DRIVES = {"p1": _drive_p1, "p2": _drive_p2, "p0": _drive_p0}


async def build(adapter: Any) -> dict[str, str]:
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    which = list(_DRIVES) if stage == "all" else [stage]
    if any(s not in _DRIVES for s in which):
        raise RuntimeError(f"unknown stage {stage!r}; pick {sorted(_DRIVES)} or 'all'")
    log(f"setup-DOF drives: {which}")

    results = []
    for s in which:
        log(f"=== {s} ===")
        results.append(await _DRIVES[s](adapter))
        # Throwaway study lives only in the dirtied in-memory doc -- discard it.
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)

    _telemetry.info("SETUP-DOF ARTICULATION DRIVES (sub-level Basic Motion sweeps):")
    for r in results:
        _telemetry.info(f"{r['dof']:22s} swing {r['span_deg']:>6s} deg"
                        + (f"  -> {r['video']}" if r.get("video") else "  (no video)"))
    return {r["dof"]: r.get("video", r["span_deg"]) for r in results}


if __name__ == "__main__":
    sys.exit(run_build(build))
