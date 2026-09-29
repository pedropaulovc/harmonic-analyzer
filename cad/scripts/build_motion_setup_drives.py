r"""Setup-motion demonstrations for cone swing, cam-driven pinion and p0.

The crank is the operating input. The cone swing (p1) and each channel's
amplitude adjustment (p0) remain independent setup freedoms. Pinion engage
(p2) is NOT an additional DOF: the tangent mate couples the strap swing
to the free lift-rod/cam spin. The transient p2 study turns the cam in the
analytically derived engage direction and checks the bracket against its
contact trajectory; its 60° input is only a partial demonstration, not a
physical hard stop. A second strap motor would fight the active contact mate.

Each standalone subassembly is exercised in a transient Basic Motion study.
The saved model keeps the appropriate driver free, so there is no permanent
driver mate to suppress. The driven member must visibly move; the document is
discarded unsaved after the study.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_motion_setup_drives.py [p1|p2|p0|all]
"""

from __future__ import annotations

import math
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

# p1/p0: a gentle 3 RPM for 2 s; p2: 5 RPM for 2 s -> 60° of cam input,
# shorter than the analytically solved ~82° engage rotation. This transient
# demonstration has no modeled hard stop and does not claim one.
SWING_RPM = 3.0
SWING_DURATION = 2.0
SWING_MIN_DEG = 5.0  # p1/p0 driven members must advance at least this far
P2_CAM_RPM = 5.0
P2_CAM_SWEEP_DEG = P2_CAM_RPM * 360.0 / 60.0 * SWING_DURATION
_SWING_SAMPLE_STEPS = 12
_P2_INPUT_TOL_DEG = 2.0
_P2_SWING_TOL_DEG = 0.5
_P2_CONTACT_GAP_TOL_MM = 0.04


def _signed_planar_rotation_deg(reference, pose, row: int) -> float:
    """Signed world-XY rotation of one transform basis row from its reference."""
    x0, y0 = reference[row * 3 : row * 3 + 2]
    x1, y1 = pose[row * 3 : row * 3 + 2]
    return math.degrees(math.atan2(x0 * y1 - y0 * x1, x0 * x1 + y0 * y1))


def _expected_p2_swing_deg(cam_angle_deg: float) -> float:
    """Solve the cam-OD / pin-shank tangency without importing a CAD builder."""
    import pinion_rig_park_geometry as park

    cam_angle = math.radians(cam_angle_deg)
    lo, hi = 0.0, math.radians(1.0)
    gap_lo = park.cam_pin_gap(cam_angle, lo)
    while park.cam_pin_gap(cam_angle, hi) <= 0.0 and hi < math.pi / 2.0:
        hi = min(hi * 2.0, math.pi / 2.0)
    gap_hi = park.cam_pin_gap(cam_angle, hi)
    if abs(gap_lo) <= 1e-8:
        return 0.0
    if gap_lo >= 0.0 or gap_hi <= 0.0:
        raise RuntimeError(
            f"p2 cam angle {cam_angle_deg:+.2f}° does not bracket the "
            "analytical contact swing"
        )
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if park.cam_pin_gap(cam_angle, mid) > 0.0:
            hi = mid
        else:
            lo = mid
    return math.degrees((lo + hi) / 2.0)


def _assert_p2_cam_trajectory(
    bracket_samples, cam_samples, expected_cam_rotation_deg: float
) -> None:
    """Check signed cam travel and the bracket's analytical contact path."""
    import pinion_rig_park_geometry as park

    expected_count = _SWING_SAMPLE_STEPS + 1
    if len(bracket_samples) != expected_count or len(cam_samples) != expected_count:
        raise RuntimeError(
            f"p2 study needs {expected_count} paired cam/bracket poses, got "
            f"{len(cam_samples)} cam and {len(bracket_samples)} bracket samples"
        )
    if any(
        samples[index][1] is None
        for samples in (bracket_samples, cam_samples)
        for index in (0, -1)
    ):
        raise RuntimeError("p2 study needs valid rest and full-excursion poses")
    bracket_rest = bracket_samples[0][1]
    cam_rest = cam_samples[0][1]
    valid_samples = 0
    for index, ((time, bracket), (cam_time, cam)) in enumerate(
        zip(bracket_samples, cam_samples, strict=True)
    ):
        expected_time = SWING_DURATION * index / _SWING_SAMPLE_STEPS
        if not (
            math.isclose(time, expected_time, abs_tol=1e-9)
            and math.isclose(cam_time, expected_time, abs_tol=1e-9)
        ):
            raise RuntimeError(
                f"p2 study sample {index} is at {time:.3f}/{cam_time:.3f}s, "
                f"expected {expected_time:.3f}s"
            )

        if bracket is None or cam is None:
            continue
        valid_samples += 1

        cam_angle_deg = _signed_planar_rotation_deg(cam_rest, cam, row=0)
        expected_cam_deg = expected_cam_rotation_deg * (
            expected_time / SWING_DURATION
        )
        if abs(cam_angle_deg - expected_cam_deg) > _P2_INPUT_TOL_DEG:
            raise RuntimeError(
                f"p2 cam input at {time:.2f}s rotated {cam_angle_deg:+.2f}°, "
                f"expected {expected_cam_deg:+.2f}° from the contact-derived "
                "engage direction and 5 RPM study"
            )

        swing_deg = _signed_planar_rotation_deg(bracket_rest, bracket, row=1)
        expected_swing_deg = _expected_p2_swing_deg(cam_angle_deg)
        if abs(swing_deg - expected_swing_deg) > _P2_SWING_TOL_DEG:
            raise RuntimeError(
                f"p2 bracket at cam {cam_angle_deg:+.2f}° swung "
                f"{swing_deg:+.2f}°, expected {expected_swing_deg:+.2f}° "
                "from the cam-contact trajectory"
            )
        gap = park.cam_pin_gap(math.radians(cam_angle_deg), math.radians(swing_deg))
        if abs(gap) > _P2_CONTACT_GAP_TOL_MM:
            raise RuntimeError(
                f"p2 cam/bracket at {time:.2f}s leaves {gap:.3f} mm contact gap "
                f"(> {_P2_CONTACT_GAP_TOL_MM})"
            )
    if valid_samples < expected_count - 2:
        raise RuntimeError(
            f"p2 study has only {valid_samples} paired poses; "
            f"needs at least {expected_count - 2}"
        )

    actual_end_cam = _signed_planar_rotation_deg(
        cam_rest, cam_samples[-1][1], row=0
    )
    expected_end_swing = _expected_p2_swing_deg(expected_cam_rotation_deg)
    actual_end_swing = _signed_planar_rotation_deg(
        bracket_rest, bracket_samples[-1][1], row=1
    )
    if expected_cam_rotation_deg * actual_end_cam <= 0.0 or actual_end_swing <= 0.0:
        raise RuntimeError(
            f"p2 study did not swing into engagement: cam "
            f"{actual_end_cam:+.2f}°, bracket {actual_end_swing:+.2f}°"
        )
    if abs(actual_end_swing - expected_end_swing) > _P2_SWING_TOL_DEG:
        raise RuntimeError(
            f"p2 engaged-direction bracket excursion {actual_end_swing:.2f}° "
            f"does not match analytical {expected_end_swing:.2f}°"
        )


def _gear_mate_names(mates: list[dict[str, Any]]) -> list[str]:
    """Names of every gear mate in ``mates`` (mate type contains 'gear')."""
    return [m["name"] for m in mates if "gear" in str(m.get("type", "")).lower()]


def _family_driver_names(adapter: Any, root: str, family: str,
                         only_type: int | None = None) -> list[str]:
    """Names of the single-real-part DISTANCE/ANGLE drive mates on FAMILY.

    A drive mate references exactly one real part plus a root plane, so
    ``_real_parts`` leaving a single name marks it. ``only_type`` narrows to the
    swing driver when a family also carries positional locators of the other
    type: the cone-swing-platform is LOCATED by three DISTANCE mates (height +
    plan X/Z) and its swing is held by the lone ANGLE driver, so p1 must suppress
    ANGLE only -- suppressing the distances too would unmoor the plate in space.
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


def _assert_dof_already_free(names: list[str], label: str) -> None:
    """Assert a freed-DOF family has no authored drive mate to suppress.

    Every freed DOF's drive spec is recorded into the DOF manifest, never
    authored (AGENTS.md "Default-free DOF") -- the family is already free.
    A non-empty ``names`` means a driver got authored unexpectedly; fail loud
    rather than silently suppressing it away (Codex catch, 2026-07-05).
    """
    if names:
        raise RuntimeError(
            f"{label}: found {len(names)} authored drive mate(s) {names} -- "
            "freed-DOF drivers are never authored; rebuild the assembly")
    log(f"  {label}: DOF already free "
        "(recorded in the DOF manifest, not authored)")


async def _run_swing_study(
    adapter: Any,
    motor_axis,
    driven_needle: str,
    label: str,
    video_tag: str,
    *,
    rpm: float = SWING_RPM,
    reverse: bool = False,
    p2_cam_input_needle: str | None = None,
    expected_cam_rotation_deg: float | None = None,
) -> dict[str, str]:
    """Motor one free input, prove its coupled member moves, never save."""
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
        f"{motor_axis.name}@{motor_axis.component} ({rpm} RPM, reverse={reverse})")
    check("add_motor", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=motor_axis, speed=rpm,
        reverse=reverse, study_name="")))

    await _reset_to_assembled(adapter)
    log(f"  {label}: Calculate() -- short sub-level swing solve ...")
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))

    if (p2_cam_input_needle is None) != (expected_cam_rotation_deg is None):
        raise ValueError("p2 cam trajectory needs both an input component and angle")
    cam_input = None
    if p2_cam_input_needle is not None:
        cam_input, _ = _find_one(adapter, p2_cam_input_needle)
        if cam_input is None:
            raise RuntimeError(
                f"{label}: cam input member {p2_cam_input_needle!r} not found"
            )
    driven, _ = _find_one(adapter, driven_needle)
    if driven is None:
        raise RuntimeError(f"{label}: driven member {driven_needle!r} not found")
    samples = []
    cam_samples = []
    for s in range(_SWING_SAMPLE_STEPS + 1):
        t = SWING_DURATION * s / _SWING_SAMPLE_STEPS
        check(f"set_time {t:.2f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name="")))
        samples.append((t, _comp_xform(adapter, driven)))
        if cam_input is not None:
            cam_samples.append((t, _comp_xform(adapter, cam_input)))
    base = next((a for _t, a in samples if a is not None), None)
    span = max((_rot_angle(base, a) for _t, a in samples if a is not None),
               default=0.0) if base is not None else 0.0
    log(f"  {label}: {driven_needle} swing span = {span:.2f} deg over "
        f"{SWING_DURATION}s")

    # The ordinary setup members need only a real arc. p2 instead checks the
    # measured signed cam input and every bracket pose against cam tangency.
    assert_motion_progressed(samples, SWING_DURATION, label,
                             min_frac=0.75, stall_frac=0.25)
    if expected_cam_rotation_deg is not None:
        _assert_p2_cam_trajectory(
            samples, cam_samples, expected_cam_rotation_deg
        )
    elif span < SWING_MIN_DEG:
        raise RuntimeError(
            f"{label}: driven member swung only {span:.2f} deg "
            f"(< {SWING_MIN_DEG}) -- the motor did not couple to it")

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
    suppress every gear mesh); the platform's swing is already free (its
    ANGLE drive spec is recorded, never authored), then motor the plate about
    its tip-end vertical pivot (Axis1, "swing pivot"). The driven needle is
    the pivot POST: it rides the plate 194.5 from the pivot, so its arc
    proves the riders follow the swing."""
    path = str(OUT_SLDASM / "drive-train.SLDASM")
    check("open drive-train", await adapter.open_model(path))
    mates = check("list mates", await adapter.list_mates())
    await _suppress(adapter, _gear_mate_names(mates), "p1 gear meshes")
    _assert_dof_already_free(_family_driver_names(
        adapter, "drive-train", "cone-swing-platform", only_type=ANGLE),
        "p1 cone-platform swing")
    plate, plate_name = _find_one(adapter, "cone-swing-platform")
    if plate is None:
        raise RuntimeError("p1: cone-swing-platform not found")
    motor_axis = _entity_ref(plate_name, "Axis1", "AXIS")
    return await _run_swing_study(
        adapter, motor_axis, "cone-pivot-post",
        "p1 cone disengage", "drive-train-p1-cone-swing")


async def _drive_p2(adapter: Any) -> dict[str, str]:
    """p2: turn the cam toward contact; the mate couples the strap swing."""
    import pinion_rig_park_geometry as park

    probe = math.radians(1.0)
    if not park.cam_pin_gap(-probe, 0.0) < 0.0 < park.cam_pin_gap(probe, 0.0):
        raise RuntimeError("p2 cam's clockwise engage direction left the rest contact")
    path = str(OUT_SLDASM / "drive-train.SLDASM")
    check("open drive-train", await adapter.open_model(path))
    _assert_dof_already_free(_family_driver_names(
        adapter, "drive-train", "pinion-lift-rod", only_type=ANGLE),
        "p2 cam input")
    rod, rod_name = _find_one(adapter, "pinion-lift-rod")
    if rod is None:
        raise RuntimeError("p2: pinion-lift-rod not found")
    motor_axis = _entity_ref(rod_name, "Axis1", "AXIS")
    expected_cam_rotation_deg = -P2_CAM_SWEEP_DEG
    return await _run_swing_study(
        adapter, motor_axis, "pinion-bracket-1",
        "p2 cam-driven bracket engage", "drive-train-p2-pinion-swing",
        rpm=P2_CAM_RPM, reverse=True,
        p2_cam_input_needle="pinion-lift-rod",
        expected_cam_rotation_deg=expected_cam_rotation_deg)


async def _drive_p0(adapter: Any) -> dict[str, str]:
    """p0: an amplitude bar swings about its top pin (the channel's amplitude
    coefficient). ONE bar's amplitude DOF is already free (its drive spec is
    recorded, never authored -- the other 19 bars stay pinned by their own
    recorded specs), then motor it about its top-pin bore (Axis1)."""
    path = str(OUT_SLDASM / "channel.SLDASM")
    check("open channel", await adapter.open_model(path))
    bar, bar_name = _find_one(adapter, "amplitude-bar")
    if bar is None:
        raise RuntimeError("p0: amplitude-bar not found")
    _assert_dof_already_free(
        _part_driver_names(adapter, "channel", bar_name), f"p0 amplitude ({bar_name})")
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
