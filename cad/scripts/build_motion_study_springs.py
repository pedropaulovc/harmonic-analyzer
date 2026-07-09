r"""Operation-study stages `springs`/`full`: the real force elements + the
output cross-sub couplings. Imported lazily by build_motion_study.build:
``add_springs`` at level>=2, ``add_output_couplings`` at level>=3. Like the
rest of the study these only dirty the in-memory doc -- NEVER saved (the
artefact fleet on disk stays untouched).

SPRINGS (add_springs):
  * 20 channel springs -- each pulls a channel-lever tab eye down toward the
    summing-lever plate. As the cam chain rocks each channel-lever, its spring
    length changes, so the tension that channel applies to the summing lever
    changes; the summing lever rocks to the force balance = the analogue SUM of
    the 20 channels (the machine's whole point). All 20 share one k; the
    amplitude weighting lives in the bar stations, not the springs.
  * 1 counter spring -- gooseneck pin (structural) <-> boss-hook arm (keyed to
    the summing lever): the restoring bias against the channel pull.
  Both ends are ring-centre RefPoints created at RUNTIME via arc_center on the
  eye hole's circular edge, on the SHARED part doc (all instances inherit the
  point via GetCorresponding), NEVER saved. The 20 bottom eyes share ONE
  summing-lever plate point: every plate hole sits at the same X off the knife
  axis, so each spring's torque arm about the (Z) knife line is identical --
  one point reproduces the summing torque exactly.
  free_length=None starts each spring at its assembled length with ZERO force,
  so the motion is driven purely by the cam-chain length changes -- no fragile
  pretension calibration. NOTHING is suppressed: the summing lever's rock is a
  deferred-free DOF in the default-`free` build.

OUTPUT COUPLINGS (add_output_couplings):
  * summing -> magnifier hand-off: the magnifying lever knife-rocks ON the
    summing bar's ridge, COAXIAL with the summing knife line (asserted at
    build time in build_magnifier_assembly) -- so the hand-off is a 1:1 gear
    coupling about that shared Z axis (summing-lever Axis3 <-> magnifying-
    lever Axis2). The lever's rock is deferred-free; its knife-line position
    stays pinned by its authored structural drivers. From the lever, artifact
    A's live WIRE-1 chain (ball-jointed lever-wire + yoke mate) turns the
    magnifying wheel.
  * WIRE 2 (wheel -> pen) as a scotch yoke: a RefPoint on the wheel's Ø100 rim
    held COINCIDENT to the pen-rod's horizontal Top plane. As the wheel turns,
    the rim point's Y excursion drags the pen-rod (deferred-free travel) in Y;
    its X excursion slides freely along the infinite plane. pen_Y ~=
    50*sin(theta_wheel), linear in the small operating angles. Basic Motion
    enforces gears and point-on-plane coincidents (proven); the wires use only
    enforced primitives.
  * gravity (-Y) OPT-IN: on a ~1 m steel mechanism gravity dwarfs the
    solver-safe spring rates and destabilises the solve; the harmonic trace is
    a crank+spring-balance result, so gravity is noise here.

All couplings are CROSS-sub (channel<->summing, summing<->magnifier,
magnifier<->pen), so every mate is authored at the TOP level -- the old
same-flexible-sub AddMate5 restriction does not apply.
"""

from __future__ import annotations

from _common import (
    check,
    log,
)
from _assembly import (
    coincident_mate,
    component_named_ref,
    gear_mate,
    lock_mate,
)
from build_motion_study import (
    CH_SPRING,
    CT_SPRING,
    SPRING_KCH,
    SPRING_KCT,
    _by_z_rank,
    _comp_model_doc,
    _components,
    _entity_ref,
    _find_one,
    _k_helical,
    _read_member,
)
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

import _telemetry

# Part-local points ON each eye hole's circular edge (mm) -> arc_center -> the
# ring centre. Derived from the part scripts' own constants so a part rework
# moves them (or fails loud at import), not silently stale.
from build_channel_lever import LEVER_SPRING_X, LEVER_THICKNESS, SPRING_HOLE_DIA
from build_summing_lever import HOLE_DIA as PLATE_HOLE_DIA
from build_summing_lever import HOLE_X as PLATE_HOLE_X
from build_summing_lever import HOLE_Z as PLATE_HOLE_Z
from build_summing_lever import PLATE_T
from build_boss_hook import ARM_RUN, ELBOW_R, ROD_DIA, SHANK_RISE
from build_gooseneck import PIN_DIA, PIN_X, PIN_Y

# Each eye is a CANDIDATE list -- a union (the gooseneck lug eats the pin
# end-face's top arc; probed live) can consume part of a circular edge, so
# several points on the same circle are tried in order.
# channel-lever spring tab: Ø4 hole at (177.8, 0), faces z = +/-1.5.
CH_LEVER_EYE = [
    [LEVER_SPRING_X + SPRING_HOLE_DIA / 2.0, 0.0, LEVER_THICKNESS / 2.0],
    [LEVER_SPRING_X, SPRING_HOLE_DIA / 2.0, LEVER_THICKNESS / 2.0],
]
# summing-lever plate hole 0 (all 20 share X, so one point serves all springs):
# Ø2 at (39.85, top face y +2.54, z -66.3).
SUM_PLATE_EYE = [
    [PLATE_HOLE_X + PLATE_HOLE_DIA / 2.0, PLATE_T / 2.0, PLATE_HOLE_Z[0]],
    [PLATE_HOLE_X, PLATE_T / 2.0, PLATE_HOLE_Z[0] + PLATE_HOLE_DIA / 2.0],
]
# gooseneck counter-spring pin: Ø4 revolved along X about y 163, tip end-face
# at x -98. The lug union eats the top arc -- (x, 165, 0) FAILS, side/bottom
# points select (probed live, probe_gooseneck_pin_edge).
GOOSENECK_EYE = [
    [PIN_X[1], PIN_Y, PIN_DIA / 2.0],
    [PIN_X[1], PIN_Y - PIN_DIA / 2.0, 0.0],
    [PIN_X[0], PIN_Y, PIN_DIA / 2.0],
]
# boss-hook arm: Ø3 rod along X at y 15, end face at x 6.5.
BOSS_HOOK_EYE = [
    [ELBOW_R + ARM_RUN, SHANK_RISE + ELBOW_R + ROD_DIA / 2.0, 0.0],
    [ELBOW_R + ARM_RUN, SHANK_RISE + ELBOW_R, ROD_DIA / 2.0],
    [ELBOW_R + ARM_RUN, SHANK_RISE + ELBOW_R - ROD_DIA / 2.0, 0.0],
]

# Free length: None = start at assembled length with zero force (no pretension
# to calibrate; motion comes from cam-chain length changes).
CH_FREE_LEN = None
CT_FREE_LEN = None

# Points on the magnifying-wheel Ø100 rim OD edge (part-local mm); the rim is
# extruded both-directions (RIM_AXIAL 8 -> edges at z +/-4). A few candidates
# tried in order until one selects.
RIM_EDGE_CANDIDATES = [[50.0, 0.0, 4.0], [50.0, 0.0, -4.0], [0.0, 50.0, 4.0]]


async def _eye_point(adapter, comp_needle, edge_points, label, comps=None):
    """Create a mateable eye-centre RefPoint on a SHARED part doc (never saved).

    arc_center on the eye hole's circular edge -> the ring centre;
    ``edge_points`` is a candidate list tried in order (a union can consume
    part of the circle). Selection in a component's part doc requires it be
    the ACTIVE doc -> ActivateDoc3 round-trip. All instances of the part
    inherit the point via GetCorresponding. Returns the point feature name.
    """
    from solidworks_mcp.adapters.base import CreateReferencePointParameters
    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    comp, _ = _find_one(adapter, comp_needle, comps=comps)
    if comp is None:
        raise RuntimeError(f"{comp_needle} not found for eye point {label}")
    part = _comp_model_doc(adapter, comp)
    if part is None:
        raise RuntimeError(f"{comp_needle} part doc unresolved")
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    name = None
    try:
        for ep in edge_points:
            res = await adapter.create_reference_point(
                CreateReferencePointParameters(mode="arc_center", edge_point=ep))
            if res.is_success:
                data = res.data
                name = data.get("name") if isinstance(data, dict) else getattr(
                    data, "name", None)
                log(f"  eye point {label}: edge {ep} -> {name!r}")
                break
            log(f"    eye point {label}: edge {ep} rejected")
    finally:
        adapter._attempt(
            lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
        adapter.currentModel = top
    if not name:
        raise RuntimeError(
            f"eye point {label}: no candidate edge selected on {part_title} "
            f"({edge_points})")
    log(f"  eye point {label} on {part_title} = {name!r}")
    return name


async def add_springs(adapter, comps=None):
    from solidworks_mcp.adapters.base import MotionSpringParameters

    if comps is None:
        comps = _components(adapter)

    # Eye datum points on the shared part docs (inherited by all instances).
    lever_pt = await _eye_point(adapter, "channel-lever-1", CH_LEVER_EYE,
                                "channel-lever tab", comps=comps)
    plate_pt = await _eye_point(adapter, "summing-lever-1", SUM_PLATE_EYE,
                                "summing-lever plate hole", comps=comps)
    goose_pt = await _eye_point(adapter, "gooseneck-1", GOOSENECK_EYE,
                                "gooseneck counter-top", comps=comps)
    hook_pt = await _eye_point(adapter, "boss-hook-1", BOSS_HOOK_EYE,
                               "boss-hook counter-bottom", comps=comps)

    sum_name = _find_one(adapter, "summing-lever-1", comps=comps)[1]
    levers = _by_z_rank(adapter, "channel-lever", comps=comps)
    k_geom = _k_helical(CH_SPRING["d"], CH_SPRING["D"], CH_SPRING["n"])
    k_ch = SPRING_KCH if SPRING_KCH > 0 else k_geom
    log(f"  channel spring k = {k_ch:.1f} N/m (geometric {k_geom:.0f} N/m, "
        f"override {SPRING_KCH:.1f}); {len(levers)} channel-levers")

    # 20 channel springs: channel-lever tab eye <-> shared summing-lever eye.
    ok = 0
    for i, (_c, lever_n) in enumerate(levers):
        try:
            res = await adapter.add_motion_spring(MotionSpringParameters(
                spring_type="linear",
                endpoints=[component_named_ref(lever_n, lever_pt, "POINT"),
                           component_named_ref(sum_name, plate_pt, "POINT")],
                spring_constant=k_ch, free_length=CH_FREE_LEN, study_name=""))
            ok += 1 if res.is_success else 0
            if not res.is_success:
                log(f"    ch{i:02d} spring FAIL: {res.error}")
        except Exception as exc:  # noqa: BLE001
            log(f"    ch{i:02d} spring EXC: {exc}")
    log(f"  channel springs: {ok}/{len(levers)}")
    if ok < len(levers):
        raise RuntimeError(f"channel springs incomplete: {ok}/{len(levers)}")

    # Counter spring: gooseneck pin (structural) <-> boss-hook (summing lever).
    goose_n = _find_one(adapter, "gooseneck-1", comps=comps)[1]
    hook_n = _find_one(adapter, "boss-hook-1", comps=comps)[1]
    k_ct_geom = _k_helical(CT_SPRING["d"], CT_SPRING["D"], CT_SPRING["n"])
    k_ct = SPRING_KCT if SPRING_KCT > 0 else k_ct_geom
    log(f"  counter spring k = {k_ct:.1f} N/m (geometric {k_ct_geom:.0f} N/m, "
        f"override {SPRING_KCT:.1f})")
    cres = await adapter.add_motion_spring(MotionSpringParameters(
        spring_type="linear",
        endpoints=[component_named_ref(goose_n, goose_pt, "POINT"),
                   component_named_ref(hook_n, hook_pt, "POINT")],
        spring_constant=k_ct, free_length=CT_FREE_LEN, study_name=""))
    if not cres.is_success:
        raise RuntimeError(f"counter spring failed: {cres.error}")
    log("  counter spring: OK")
    return ok + 1


async def _couple_levers(adapter, comps):
    """Summing -> magnifier hand-off: 1:1 co-rotation about the shared knife line.

    The magnifying lever rides the summing bar's ridge, coaxial with the
    summing knife axis (machine (-15, 995.13), along Z; asserted at build
    time). A 1:1 gear mate on the two coaxial axes co-rotates them -- the
    knife-edge carry idealised as a hinge coupling. Falls back to a LOCK mate
    (rigid carry, physically the same idealisation) if the coaxial gear is
    rejected.
    """
    sum_n = _find_one(adapter, "summing-lever-1", comps=comps)[1]
    mag_n = _find_one(adapter, "magnifying-lever-1", comps=comps)[1]
    if not sum_n or not mag_n:
        raise RuntimeError(f"lever hand-off components unresolved "
                           f"({sum_n!r}, {mag_n!r})")
    last = None
    for alignment in ("aligned", "anti_aligned"):
        try:
            res = await gear_mate(
                adapter, _entity_ref(sum_n, "Axis3", "AXIS"),
                _entity_ref(mag_n, "Axis2", "AXIS"),
                [1.0, 1.0], alignment=alignment,
                label="hand-off summing->magnifying lever 1:1")
            if res.get("name"):
                log(f"  lever hand-off gear: {res['name']} (alignment={alignment})")
                return res
        except Exception as exc:  # noqa: BLE001
            last = exc
            log(f"    lever hand-off gear alignment={alignment} rejected: {exc}")
    _telemetry.warn(f"lever hand-off gear failed both alignments ({last}); "
                    f"falling back to a lock mate")
    res = await lock_mate(
        adapter, _entity_ref(sum_n, "Axis3", "AXIS"),
        _entity_ref(mag_n, "Axis2", "AXIS"),
        label="hand-off summing->magnifying lever (lock)")
    log(f"  lever hand-off lock: {res.get('name')}")
    return res


async def _rim_point(adapter, comps=None):
    """RefPoint at radius 50 on the magnifying-wheel rim, on the SHARED wheel
    part doc (never saved). Returns the point feature name."""
    from solidworks_mcp.adapters.base import CreateReferencePointParameters
    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    wh, _ = _find_one(adapter, "magnifying-wheel-1", comps=comps)
    if wh is None:
        raise RuntimeError("magnifying-wheel-1 not found for rim point")
    part = _comp_model_doc(adapter, wh)
    if part is None:
        raise RuntimeError("magnifying-wheel part doc unresolved")
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    name = None
    try:
        for ep in RIM_EDGE_CANDIDATES:
            res = await adapter.create_reference_point(CreateReferencePointParameters(
                mode="along_curve", edge_point=ep, along="percentage", percentage=0.0))
            if res.is_success:
                name = res.data.get("name") if isinstance(res.data, dict) else getattr(
                    res.data, "name", None)
                log(f"  rim RefPoint edge_point={ep} -> {name!r}")
                break
    finally:
        adapter._attempt(
            lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
        adapter.currentModel = top
    if not name:
        raise RuntimeError("rim RefPoint creation failed on the wheel")
    return name


async def add_output_couplings(adapter, comps=None, with_gravity=False):
    """Stage `full`: the summing->magnifier hand-off + WIRE 2 + opt-in gravity.

    Everything cross-sub, authored at the top level; artifact A's live WIRE-1
    chain inside magnifier already turns the wheel with the lever, so only the
    hand-off INTO magnifier and the yoke OUT of it are added here.
    """
    from solidworks_mcp.adapters.base import MotionGravityParameters

    if comps is None:
        comps = _components(adapter)

    await _couple_levers(adapter, comps)

    rim_pt = await _rim_point(adapter, comps=comps)
    wheel_n = _find_one(adapter, "magnifying-wheel-1", comps=comps)[1]
    rod_n = _find_one(adapter, "pen-rod-1", comps=comps)[1]
    if not rod_n:
        raise RuntimeError("pen-rod-1 not found for the WIRE2 yoke")
    w2 = await coincident_mate(
        adapter, _entity_ref(wheel_n, rim_pt, "POINT"),
        _entity_ref(rod_n, "Top Plane", "PLANE"),
        label="WIRE2 yoke rim->pen")
    log(f"  WIRE2 yoke: {w2.get('name')}")

    grav_ok = None
    if with_gravity:
        g = await adapter.add_gravity(MotionGravityParameters(
            axis="y", reverse=True, study_name=""))
        grav_ok = g.is_success
        log(f"  gravity -Y: {'OK' if g.is_success else 'FAIL ' + str(g.error)}")
    else:
        log("  gravity: SKIPPED (pass `grav` to enable)")
    return {"wire2": w2.get("name"), "gravity": grav_ok}
