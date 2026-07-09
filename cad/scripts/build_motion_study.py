r"""The OPERATION simulation (artifact B): a throwaway SOLIDWORKS Basic Motion
study that opens the saved, default-`free` harmonic-analyzer.SLDASM and runs the
whole device from a single crank motor, with the 20 channel springs + counter
spring as real force elements and the two amplifying wires as motion couplings.
It NEVER re-saves any artefact (the .SLDASM fleet on disk stays untouched; the
study lives only in the dirtied in-memory doc + the exported video/samples).

ARCHITECTURE (2026-07, default-free DOF -- this is a full rewrite of the
2026-06-14 study, which targeted the retired `output-1` sub and re-derived by
suppression what the free build now simply ships):

  * The top assembly inserts SEVEN subs rigid+fixed (frame, drive-train,
    channel, summing, magnifier, pen, paper-drive). Six of them move; frame
    stays fixed.
  * Every moving sub is built `free`: its operational DOF carry NO park driver
    (deferred to the `.<stem>.park.json` sidecar), so once the sub is FLEXIBLE
    its internal kinematics are live with ZERO suppression -- the crank spins
    the geared train, J2/J5 close each channel's rocker->rod and
    rocker->bar->lever chains, the summing/magnifying levers rock on their
    knife lines, the WIRE-1 yoke turns the wheel, the pen carriage slides, and
    paper-drive's belt/chain + rack-pinion feed the platen. The old ~500 s
    mate-classifier walk is GONE because the mates it suppressed no longer
    exist.
  * What artifact A deliberately does NOT author is every CROSS-sub coupling
    (POST_ASSEMBLY == {}); those are exactly what this study adds:
      - 20 cam couplings: connecting-rod ring-centre point ON
        Axis3@cylinder-gear (the eccentric lobe axis), channel<->drive-train;
      - the crank->paper chain: paper-drive's crank-end sprocket tied 1:1 to
        the drive-train crankshaft it is coaxial with;
      - the summing->magnifier hand-off: the magnifying lever knife-rocks ON
        the summing bar's ridge, coaxial with the summing knife line ->
        coupled 1:1 about that shared axis;
      - WIRE 2: a point on the magnifying-wheel Ø100 rim held on the pen-rod's
        horizontal plane (scotch yoke) -- the wheel's rock drags the pen in Y;
      - 20 channel springs (channel-lever tab eye -> summing-lever plate) + 1
        counter spring (gooseneck -> boss-hook): the analogue SUM as a real
        force balance.
  * The three drive-train SETUP poses (cone_swing p1, pinion_swing p2,
    pinion_cam) are deferred-free in artifact A but must be HELD ENGAGED while
    the machine runs -- replayed from the park sidecar. The crank_angle park
    stays deferred (the motor owns that DOF). The per-channel bar_amplitude
    parks are replayed too (the bars are coefficient SETTINGS, clamped during
    operation); pass an amplitude preset to pin them at non-neutral stations
    for a visible harmonic trace.

Basic Motion (physical_simulation) is the licensed solver on this 3DEXPERIENCE
Makers seat -- MotionAnalysis is NOT licensed here. Basic Motion solves motors,
gears, springs and gravity, which is what this study needs.

    uv run python cad\scripts\build_motion_study.py [stage] [opts...]

``stage`` (default ``kinematic``) gates how far the build runs so the heavy
solve can be brought up incrementally:
    flex       -> flexible + engaged setup parks + bar clamps (no motor/solve)
    kinematic  -> + cam couplings + chain tie + crank motor + Calculate +
                  rocker/platen samples + video
    springs    -> + 21 spring force elements + summing-chain samples
    full       -> + lever hand-off + WIRE2 yoke + pen sample vs truth + video

``opts``: ``square`` pins the amplitude bars at the square-wave preset stations
(default: the as-built neutral, a_j = 0 -> a flat pen line); ``grav`` enables
gravity (default off: on a ~1 m mechanism gravity dwarfs the solver-safe spring
rates and destabilises the solve).
"""

from __future__ import annotations

import json
import math
import os
import sys

import _config
from _common import (
    OUT_PNG,
    OUT_SLDASM,
    _flag,
    _read_member,
    check,
    log,
    run_build,
)
from _assembly import (
    coincident_mate,
    component_named_ref,
    gear_mate,
    named_ref,
)
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

import _telemetry

# ---- study constants --------------------------------------------------------
ASM = "harmonic-analyzer"
# frame-1 stays fixed; everything else solves flexibly with the parent.
MOVING_SUBS = ("drive-train-1", "channel-1", "summing-1", "magnifier-1",
               "pen-1", "paper-drive-1")

CRANK_RPM = float(os.environ.get("MOTION_CRANK_RPM", "20.0"))  # 1 rev / 3 s
DURATION_S = float(os.environ.get("MOTION_DURATION_S", "6.0"))  # two crank revs
N_CHANNELS = _config.active_count()
ROCKER_MIN_DEG = 1.0      # dead-output gate: largest rocker swing must exceed
PEN_MIN_MM = 0.5          # dead-output gate: pen-tip travel must exceed
SUM_MIN_DEG = 0.05        # dead-output gate: summing-lever rock must exceed

# A point on the connecting-rod's ring-bore circular edge (part-local mm); its
# arc centre is the ring centre = the cam-pin point (point-on-axis cam
# de-redundancy, see memory). RING_BORE_DIA 30.8 / RING_THICKNESS 3.0
# (build_connecting_rod.py) -> edge at (r=15.4, z=+1.5).
ROD_BORE_EDGE_MM = [15.4, 0.0, 1.5]

# swMateType_e
COINCIDENT, CONCENTRIC, DISTANCE, ANGLE = 0, 1, 5, 6
_MATE_NAME = {0: "COINCIDENT", 1: "CONCENTRIC", 4: "TANGENT", 5: "DISTANCE",
              6: "ANGLE", 9: "CAMFOLLOWER", 10: "GEAR", 13: "RACKPINION",
              16: "LOCK"}

RIGID, FLEXIBLE = "rigid", "flexible"

# Spring stiffness k = G*d^4 / (8*D^3*n); steel shear modulus. The GEOMETRIC
# steel rates (~2.1 kN/m channel, ~0.5 kN/m counter) are far too stiff for the
# fixed-step Basic Motion integrator (poc_spring_adder: k~2000 N/m ABORTS the
# solve; k in the low-N/m..tens band tracks the moving-anchor sum cleanly), so
# the study defaults to a solver-safe band, env-sweepable. 0/negative => the
# geometric helical rate.
G_STEEL = 79.3e9  # Pa
CH_SPRING = dict(d=1.0, D=5.5, n=28.0, free_mm=32.0)
CT_SPRING = dict(d=1.8, D=10.7, n=165.0, free_mm=315.0)
SPRING_KCH = float(os.environ.get("SPRING_KCH", "50.0"))   # N/m, channel
SPRING_KCT = float(os.environ.get("SPRING_KCT", "25.0"))   # N/m, counter

# Motion samples land here (JSON per stage) for the SW-free plot/report step.
OUT_MOTION = (OUT_PNG.parent / "reports" / "motion")


def _k_helical(d_mm: float, D_mm: float, n: float) -> float:
    """Linear rate (N/m) of a helical compression/extension spring."""
    d, D = d_mm / 1000.0, D_mm / 1000.0
    return G_STEEL * d**4 / (8.0 * D**3 * n)


# ---- component / mate walk helpers (shared with the probes) ------------------
# GetComponents(False) returns the WHOLE nested tree -- hundreds of nodes once
# the moving subs are flexible, each costing a Name2 COM round-trip. Every walk
# is timed (logged); callers that need it more than once enumerate ONCE and
# pass the (comp, name) list down. ``toplevel=True`` is the tiny fast list.
def _components(adapter, model=None, toplevel=False):
    """``[(comp, Name2), ...]`` for every component; logs the walk + its cost."""
    import time as _t
    model = model or adapter.currentModel
    t0 = _t.perf_counter()
    raw = adapter._attempt(lambda: model.GetComponents(bool(toplevel)), default=None) or []
    out = []
    for c in raw:
        # No flag: Name2 is a property read (issue #87).
        out.append((c, str(_read_member(c, "Name2"))))
    scope = "top-level" if toplevel else "full-tree"
    log(f"    [enumerated {len(out)} components, {scope}, {_t.perf_counter() - t0:.1f}s]")
    return out


def _find_comps(adapter, needle, model=None, comps=None):
    """Components whose Name2 contains ``needle``; pass ``comps`` to reuse a walk."""
    if comps is None:
        comps = _components(adapter, model)
    return [(c, nm) for c, nm in comps if needle in nm]


def _part_family(name2):
    """Component Name2 -> exact part family (never prefix-confused).

    ``"drive-train-1/cylinder-gear-1"`` -> ``"cylinder-gear"``.
    """
    part = name2.split("/")[-1]
    return part.rsplit("-", 1)[0]


def _find_family(adapter, family, model=None, comps=None):
    """Components whose part family equals ``family`` EXACTLY (dispatch, name)."""
    if comps is None:
        comps = _components(adapter, model)
    return [(c, nm) for c, nm in comps if _part_family(nm) == family]


def _find_one(adapter, needle, model=None, comps=None, toplevel=False):
    if comps is None:
        comps = _components(adapter, model, toplevel=toplevel)
    hits = [(c, nm) for c, nm in comps if needle in nm]
    return hits[0] if hits else (None, None)


def _sub_model(adapter, sub_name):
    log(f"  resolving {sub_name} model doc ...")
    comp, _ = _find_one(adapter, sub_name, toplevel=True)
    if comp is None:
        raise RuntimeError(f"sub component not found: {sub_name}")
    model = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if model is None:
        raise RuntimeError(f"GetModelDoc2 returned None for {sub_name}")
    return comp, model


def _mate_parts(adapter, mate):
    """Distinct PART names a mate references (planes/origins -> None, skipped)."""
    parts = []
    n = int(adapter._attempt(lambda: mate.GetMateEntityCount(), default=0))
    for i in range(n):
        me = adapter._attempt(lambda k=i: mate.MateEntity(k), default=None)
        if me is None:
            continue
        _flag(me, "IMateEntity2")
        rc = adapter._attempt(lambda e=me: e.ReferenceComponent2, default=None)
        if rc is None:
            rc = adapter._attempt(lambda e=me: e.ReferenceComponent, default=None)
        if rc is not None:
            # No flag: Name2 is a property read (issue #87).
            parts.append(str(_read_member(rc, "Name2")))
    return parts


def _mate_value(adapter, mate, mtype):
    if mtype not in (DISTANCE, ANGLE):
        return None
    dd = adapter._attempt(lambda: mate.DisplayDimension2(0), default=None)
    if dd is None:
        return None
    _flag(dd, "IDisplayDimension")
    dim = adapter._attempt(lambda: dd.GetDimension2(0), default=None)
    if dim is None:
        dim = adapter._attempt(lambda: dd.GetDimension(), default=None)
    if dim is None:
        return None
    _flag(dim, "IDimension")
    return adapter._attempt(lambda: dim.Value, default=None)


def _iter_mates(adapter, model, read_values=True, progress_every=0):
    """Yield (feature, mate, name, mtype, parts, value) for MODEL's mate group.

    ``read_values=False`` skips the per-mate DisplayDimension2 round-trip (the
    slow part) for callers that classify by family/type alone.
    ``progress_every`` > 0 logs a heartbeat every N mates walked.
    """
    _flag(model, "IModelDoc2")
    feat = _read_member(model, "FirstFeature")
    seen = 0
    for _ in range(50000):
        if not feat:
            break
        _flag(feat, "IFeature")
        if _read_member(feat, "GetTypeName2") == "MateGroup":
            sub = _read_member(feat, "GetFirstSubFeature")
            for _ in range(50000):
                if not sub:
                    break
                _flag(sub, "IFeature")
                name = str(_read_member(sub, "Name"))
                mate = adapter._attempt(lambda s=sub: s.GetSpecificFeature2(), default=None)
                if mate is not None:
                    _flag(mate, "IMate2")
                    mtype = int(adapter._attempt(lambda m=mate: m.Type, default=-1))
                    parts = _mate_parts(adapter, mate)
                    val = _mate_value(adapter, mate, mtype) if read_values else None
                    seen += 1
                    if progress_every and seen % progress_every == 0:
                        log(f"    ... walked {seen} mates")
                    yield sub, mate, name, mtype, parts, val
                sub = _read_member(sub, "GetNextSubFeature")
        feat = _read_member(feat, "GetNextFeature")


def _root_title(sub_name):
    """Sub instance name -> the doc-root pseudo-part name in its own mate group
    ("drive-train-1" -> "drive-train")."""
    return sub_name.rsplit("-", 1)[0]


def _real_parts(parts, root):
    """Distinct real part names, dropping the assembly-root pseudo-part."""
    return sorted({p for p in parts if p != root})


def _lone_real(parts, root):
    rp = _real_parts(parts, root)
    return rp[0] if len(rp) == 1 else None


def _family(part_name):
    """"rocker-arm-12" -> "rocker-arm" (strip the trailing instance suffix)."""
    return part_name.rsplit("-", 1)[0]


def _entity_ref(name2, prefix, etype):
    """A depth-2-safe ``MateEntityRef`` for a named feature inside a nested part.

    ``name2`` is the component path ("channel-1/connecting-rod-1"), ``prefix``
    the part-local named feature ("Axis1"). Maps the base IFeature through
    ``IComponent2.GetCorresponding`` (PR #64) -- the hand-built reversed
    ``Axis1@part@sub@asm`` string resolves only one level deep.
    """
    return component_named_ref(name2, prefix, etype)


def _comp_xform(adapter, comp):
    """Component world transform as a 16-float array, or None if unreadable.

    After a heavy Basic Motion solve, Transform2 (or its ArrayData)
    occasionally returns None on a set_motion_time sample -- a transient COM
    read, not a real error; callers skip that sample."""
    t = _read_member(comp, "Transform2")
    data = _read_member(t, "ArrayData") if t is not None else None
    if data is None:
        return None
    return [float(v) for v in data]


def _comp_z_mm(adapter, comp):
    a = _comp_xform(adapter, comp)
    return a[11] * 1000.0 if a else 0.0


def _by_z_rank(adapter, family, comps=None):
    """Components of part FAMILY, sorted by world Z (station order).

    The 20 instances of each moving part span the 20 channel stations
    monotonically in Z, so the i-th entry of two such lists is the same
    station -- robust pairing without trusting instance-suffix order."""
    hits = _find_family(adapter, family, comps=comps)
    return sorted(hits, key=lambda t: _comp_z_mm(adapter, t[0]))


def _world(a, local_mm):
    r, t = a[0:9], a[9:12]
    return [sum(local_mm[i] * r[i * 3 + k] for i in range(3)) + t[k] * 1000.0
            for k in range(3)]


def _rot_angle(a0, a1):
    """Relative rotation magnitude (deg) between two component transforms."""
    def cols(a):
        return ((a[0], a[1], a[2]), (a[3], a[4], a[5]), (a[6], a[7], a[8]))
    c0, c1 = cols(a0), cols(a1)
    tr = sum(c1[k][i] * c0[k][i] for k in range(3) for i in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


# ---- generic named-suppress (kept for the diagnostics probes) ----------------
async def _suppress_named(adapter, sub_name, families, mtypes, label):
    """Suppress every single-real-part mate in SUB whose part family matches.

    The free build defers its park drivers, so the operation study itself needs
    no suppression -- this survives for the hand-run diagnostics probes that
    still poke authored structural mates.
    """
    _, model = _sub_model(adapter, sub_name)
    root = _root_title(sub_name)
    targets = []
    log(f"  {label}: scanning {sub_name} mates ...")
    for _f, _m, name, mtype, parts, _val in _iter_mates(
            adapter, model, read_values=False, progress_every=20):
        if mtype not in mtypes:
            continue
        lone = _lone_real(parts, root)
        if lone is not None and _family(lone) in families:
            targets.append(name)
    await _do_suppress(adapter, sub_name, targets, label)
    return targets


async def _do_suppress(adapter, sub_name, targets, label):
    # currentModel MUST stay the top assembly: suppress_mate(component=sub)
    # resolves the component against currentModel then retargets itself.
    from solidworks_mcp.adapters.base import SuppressMateParameters
    log(f"  {label}: suppressing {len(targets)} mates in {sub_name}")
    for name in targets:
        check(f"suppress {name}@{sub_name}",
              await adapter.suppress_mate(SuppressMateParameters(
                  name=name, suppress=True, component=sub_name)))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)


# ---- stage: float + ground + flex --------------------------------------------
async def _flex_subs(adapter):
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters, SetComponentSolvingParameters,
    )
    asm = adapter.currentModel
    for sub in MOVING_SUBS:
        check(f"float {sub}", await adapter.float_component(ComponentRefParameters(name=sub)))
        for plane in ("Front Plane", "Top Plane", "Right Plane"):
            await coincident_mate(
                adapter, named_ref(f"{plane}@{sub}", "PLANE"),
                named_ref(plane, "PLANE"), label=f"ground {sub} {plane}")
        adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
        log(f"  set {sub} FLEXIBLE -- blocking solve ...")
        check(f"flexible {sub}", await adapter.set_component_solving(
            SetComponentSolvingParameters(name=sub, solving=FLEXIBLE)))
        comp, _ = _find_one(adapter, sub, toplevel=True)
        solving = int(adapter._attempt(lambda c=comp: c.Solving, default=-1))
        log(f"  {sub} Solving={solving} (1=flexible)")
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)


# ---- stage: replay the ENGAGED setup parks -----------------------------------
# Deferred park drivers = ABSENT = free. The operation study leaves the DOF the
# machine RUNS on free (crank_angle, rocker/rod swings, lever rocks, pen travel,
# paper crank) and re-authors ENGAGED only the SETUP poses that must be held
# while it runs: the three drive-train setup swings, and the 20 bar_amplitude
# clamps (the bars are coefficient SETTINGS -- in the real machine each bar is
# clamped at its station while the crank turns). A trailing "_" is a prefix
# match (the per-channel key families).
_SETUP_PARKS = {
    "drive-train": ("cone_swing", "pinion_swing", "pinion_cam"),
    "channel": ("bar_amplitude_",),
}


def _key_matches(key, patterns):
    return any(key == p or (p.endswith("_") and key.startswith(p))
               for p in patterns)


def _square_station(key):
    """bar_amplitude_{j} -> the square-preset station a_j (mm from the pivot).

    Row j synthesises harmonic n = 20 - j (channels.yaml); the square preset is
    the textbook odd-harmonic partial sum a_j = fundamental / n (odd n), 0
    (even n), fundamental = machine amplitude.fundamental_station_mm (80).
    """
    j = int(key.rsplit("_", 1)[1])
    n = int(_config.channels()[j]["harmonic_n"])
    fund = float(_config.machine("amplitude", "fundamental_station_mm"))
    return fund / n if n % 2 else 0.0


def _patch_bar_spec(spec, preset):
    """Re-station a recorded bar_amplitude spec for a non-config preset.

    The recorded spec pins the bar at its as-built station (foot X from the
    assembly Right Plane = PIVOT.x + a_j). For a transient preset the study
    replays the SAME mate at the preset's station: distance -> PIVOT.x + a_j',
    verify dropped (the recorded world point is only valid at the recorded
    station). J5 (foot radius from the rocker arc centre) is invariant along
    the R800 arc, so re-stationing is always consistent with it.
    """
    if preset == "config":
        return spec
    from build_channel_assembly import PIVOT
    a_j = _square_station(spec["key"])
    spec = dict(spec, params=dict(spec["params"]), verify=None, witness=None)
    spec["params"]["distance"] = PIVOT[0] + a_j
    return spec


async def _replay_setup_parks(adapter, preset="config"):
    """Re-author the deferred SETUP-pose park drivers ENGAGED before the study.

    Replayed in each sub's OWN doc (ActivateDoc3 round-trip -- API selection
    needs the active doc; the docs are NEVER saved), leaving every other
    recorded driver deferred (= free, what the study drives). ``preset``
    re-stations the channel amplitude clamps (see :func:`_patch_bar_spec`).
    """
    from _assembly import is_locked_build
    from _assembly_postbuild import load_park_specs, replay_park_specs

    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    for sub in MOVING_SUBS:
        stem = sub[:-2]  # component "-1" -> doc stem
        patterns = _SETUP_PARKS.get(stem, ())
        if not patterns:
            continue
        if is_locked_build(_config.machine("build_lock", stem.replace("-", "_"))):
            if preset != "config" and stem == "channel":
                raise RuntimeError(
                    "channel is built `locked` -- its amplitude clamps are "
                    "authored in the artefact and cannot be transiently "
                    "re-stationed; rebuild `free` or use the config preset")
            log(f"{sub}: built `locked`, setup parks already authored")
            continue
        specs = [s for s in load_park_specs(stem) if _key_matches(s["key"], patterns)]
        if not specs:
            raise RuntimeError(
                f"{stem}: no setup park specs matching {patterns} in the park "
                f"sidecar -- stale artefact or renamed free_dof_key; rebuild "
                f"the assembly")
        if stem == "channel":
            specs = [_patch_bar_spec(s, preset) for s in specs]
        _, model = _sub_model(adapter, sub)
        sub_title = str(_read_member(model, "GetTitle"))
        adapter._attempt(
            lambda t=sub_title: adapter.swApp.ActivateDoc3(t, False, 2, _byref_i4()),
            default=None)
        adapter.currentModel = adapter._attempt(
            lambda: adapter.swApp.ActiveDoc, default=model)
        log(f"{sub}: replaying {len(specs)} deferred setup park driver(s) "
            f"(engaged): {[s['key'] for s in specs]}")
        await replay_park_specs(adapter, specs)
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()),
        default=None)
    adapter.currentModel = top


# ---- stage: cam couplings (channel <-> drive-train, cross-sub) ---------------
async def _add_ring_centre_point(adapter):
    """Create a mateable ring-centre RefPoint on the SHARED connecting-rod part.

    The cam pin must be POSITION-ONLY (point-on-axis, 2 constraints) -- a
    collinear-axes pin re-fixes the rod orientation the J2 rod<->rocker
    revolute already fixes, over-constraining 20 parallel loops so Basic Motion
    solves erratically (proven 2026-06-14). The rod's ORIGIN feature is NOT
    mateable, so create a real RefPoint at the ring centre: the arc centre of
    the ring-bore edge. All instances share connecting-rod.SLDPRT, so ONE point
    is inherited by every instance via GetCorresponding; the part is NEVER
    saved. Selection in a part doc requires it be ACTIVE -> ActivateDoc3
    round-trip. Returns the point feature name.
    """
    from solidworks_mcp.adapters.base import CreateReferencePointParameters
    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    rod_comp, _ = _find_one(adapter, "connecting-rod-1")
    if rod_comp is None:
        raise RuntimeError("connecting-rod-1 not found for ring-centre point")
    part = adapter._attempt(lambda: rod_comp.GetModelDoc2(), default=None)
    if part is None:
        raise RuntimeError("connecting-rod part doc unresolved")
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    pt = check("create ring-centre RefPoint", await adapter.create_reference_point(
        CreateReferencePointParameters(mode="arc_center", edge_point=ROD_BORE_EDGE_MM)))
    name = pt.get("name") if isinstance(pt, dict) else getattr(pt, "name", None)
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = top
    if not name:
        raise RuntimeError("ring-centre RefPoint creation returned no name")
    log(f"  ring-centre point on {part_title} = {name!r} (shared by all rods)")
    return name


async def _add_cam_couplings(adapter, comps=None):
    """Per channel, at TOP level: rod ring-centre POINT on cam lobe Axis3.

    Cross-sub (drive-train<->channel), allowed at top level. The cam lobe
    orbits as the gear turns -> the rod ring follows -> via the artifact-A J2
    revolute the rod pin drives the rocker -> J5 closes rocker->bar->lever.
    """
    from solidworks_mcp.adapters.base import RotateComponentParameters
    point_name = await _add_ring_centre_point(adapter)
    if comps is None:
        log("  enumerating components for cam pairing (single full-tree walk) ...")
        comps = _components(adapter)
    gears = _by_z_rank(adapter, "cylinder-gear", comps=comps)
    rods = _by_z_rank(adapter, "connecting-rod", comps=comps)
    n = min(len(gears), len(rods))
    log(f"  cam couplings: {len(gears)} gears, {len(rods)} rods -> {n} channels")
    cam_ok = 0
    for i in range(n):
        gear_comp, gear_n = gears[i]
        rod_n = rods[i][1]
        # PERTURB before mating: at the design pose the rod ring point lies ON
        # the eccentric lobe Axis3 (degenerate zero-distance) and AddMate5
        # rejects the point-on-axis as "over-defines". Spin the gear ~20 deg
        # about its own axis so the lobe orbits OFF the stationary ring point;
        # the closing ForceRebuild3 snaps the gear back to its mate pose and
        # the added mate just holds (proven decisively, probe_perturb_cam).
        a = _comp_xform(adapter, gear_comp)
        await adapter.rotate_component(RotateComponentParameters(
            name=gear_n, angle=20.0, axis_vector=[a[6], a[7], a[8]],
            axis_point=[a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0], mode="exact"))
        try:
            cam = await coincident_mate(
                adapter, _entity_ref(rod_n, point_name, "POINT"),
                _entity_ref(gear_n, "Axis3", "AXIS"),
                label=f"ch{i:02d} cam lobe <-> rod ring point")
            cam_ok += 1 if cam.get("name") else 0
        except Exception as exc:  # noqa: BLE001 -- per-channel diagnostics
            log(f"    ch{i:02d} cam coupling FAILED: {exc}")
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    log(f"  cam couplings: {cam_ok}/{n}")
    if cam_ok < n:
        raise RuntimeError(f"cam couplings incomplete: {cam_ok}/{n}")
    return cam_ok


# ---- stage: crank->paper chain tie (drive-train <-> paper-drive) -------------
async def _tie_paper_chain(adapter, comps=None):
    """Tie paper-drive's crank-end T12 sprocket 1:1 to the drive-train
    crankshaft it is coaxial with.

    Paper-drive owns the whole crank->paper chain train, placing its crank-end
    T12 (a transgear-removable in config T12) ON the crankshaft axis at world
    (-122.8, 144.96), spin along Z -- in the real machine they are one keyed
    shaft. Artifact A leaves the two subs independent; a 1:1 gear mate on the
    coaxial Axis1s co-rotates them, so the belt/chain feature + rack-pinion
    inside paper-drive feed the platen off the crank. Best-effort: the paper
    feed is a demonstration nicety, so a failure warns and the study continues
    without it.
    """
    if comps is None:
        comps = _components(adapter)
    crank_n = _find_one(adapter, "crankshaft-1", comps=comps)[1]
    # The crank-end T12 = the transgear-removable instance in PAPER-DRIVE whose
    # world XY sits on the crankshaft axis (the knob T24 + spare T18 are the
    # other instances; XY separates them decisively).
    cs_comp, _ = _find_one(adapter, "crankshaft-1", comps=comps)
    cs_a = _comp_xform(adapter, cs_comp)
    t12_n = None
    for comp, nm in _find_family(adapter, "transgear-removable", comps=comps):
        if not nm.startswith("paper-drive"):
            continue
        a = _comp_xform(adapter, comp)
        if a and math.hypot((a[9] - cs_a[9]) * 1000.0,
                            (a[10] - cs_a[10]) * 1000.0) < 5.0:
            t12_n = nm
            break
    if not crank_n or not t12_n:
        _telemetry.warn(f"chain tie: components unresolved "
                        f"(crank={crank_n!r}, t12={t12_n!r}) -- skipping")
        return None
    for alignment in ("aligned", "anti_aligned"):
        try:
            res = await gear_mate(
                adapter, _entity_ref(crank_n, "Axis1", "AXIS"),
                _entity_ref(t12_n, "Axis1", "AXIS"),
                [1.0, 1.0], alignment=alignment, label="chain crank->paper 1:1")
            if res.get("name"):
                log(f"  chain tie: {res['name']} ({t12_n}, alignment={alignment})")
                return res
        except Exception as exc:  # noqa: BLE001
            log(f"    chain tie alignment={alignment} rejected: {exc}")
    _telemetry.warn("chain tie failed both alignments -- continuing without "
                    "platen feed")
    return None


# ---- stage: crank motor -------------------------------------------------------
async def _add_crank_motor(adapter):
    from solidworks_mcp.adapters.base import MotionMotorParameters
    cs_comp, cs_name = _find_one(adapter, "crankshaft")
    if cs_comp is None:
        raise RuntimeError("crankshaft component not found")
    axis = _entity_ref(cs_name, "Axis1", "AXIS")
    log(f"  crank motor on Axis1@{cs_name} ({CRANK_RPM} RPM) ...")
    res = check("add_motor crank", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=axis, speed=CRANK_RPM, study_name="")))
    return res


# ---- sampling + fail-loud gates ----------------------------------------------
def assert_motion_progressed(samples, duration, label="driven",
                             min_frac=0.85, stall_frac=0.25):
    """Fail fast on a LOCKED / aborted Basic Motion solve.

    Basic Motion exposes NO solver-status API (Calculate() returns True even
    when the solve aborts mid-run; the results object needs the unlicensed
    Motion add-in), so the solved POSES are the only signal. A solve that
    aborts replays the last computed frame for every later sample, so the
    motor-driven member's pose plateaus; self-calibrate the healthy per-step
    advance (median moving step) and flag where the tail drops below
    ``stall_frac`` of it.
    """
    steps = [(t1, _rot_angle(a0, a1))
             for (t0, a0), (t1, a1) in zip(samples, samples[1:])
             if a0 is not None and a1 is not None]
    if not steps:
        log(f"  solve-lock check: '{label}' no valid pose samples (skipped)")
        return

    moving = sorted(d for _t, d in steps if d > 1e-4)
    if not moving:
        raise RuntimeError(
            f"MOTION SOLVE LOCKED: '{label}' never moved -- the motor-driven "
            f"member is frozen for the entire run (corrupted study / red "
            f"timeline).")

    typical = moving[len(moving) // 2]          # median healthy step (deg)
    floor = stall_frac * typical
    last_good = 0.0
    for t1, d in steps:
        if d >= floor:
            last_good = t1
    if last_good < min_frac * duration:
        raise RuntimeError(
            f"MOTION SOLVE LOCKED: '{label}' tracked the motor (>= {floor:.3f} "
            f"deg/step) only through t={last_good:.2f}s of {duration:.2f}s -- "
            f"typical healthy step {typical:.3f} deg, tail stalled to ~0. A "
            f"stalled tail = an aborted Basic Motion solve; likely an "
            f"over-constrained closed loop.")
    log(f"  solve-lock check: '{label}' tracked motor to t={last_good:.2f}s/"
        f"{duration:.2f}s (typical {typical:.3f} deg/step, OK)")


async def _sample_transforms(adapter, probes, n_steps, study_name=""):
    """Sample (t -> transform) rows for PROBES = [(comp, label), ...].

    Returns {label: [(t, xform_or_None), ...]}. One set_motion_time per step,
    all probes read per frame (cached dispatches DO reflect motion across
    SetTime frames -- proven; the full-tree walk is paid once by the caller).
    """
    from solidworks_mcp.adapters.base import MotionTimeParameters
    rows = {label: [] for _c, label in probes}
    for s in range(n_steps + 1):
        t = DURATION_S * s / n_steps
        check(f"set_time {t:.2f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name=study_name)))
        for comp, label in probes:
            rows[label].append((t, _comp_xform(adapter, comp)))
    return rows


def _rot_series(samples):
    """[(t, xform)] -> [(t, deg-from-first-valid)] rotation series."""
    base = next((a for _t, a in samples if a is not None), None)
    if base is None:
        return []
    return [(t, _rot_angle(base, a)) for t, a in samples if a is not None]


def _span(series):
    vals = [v for _t, v in series]
    return (max(vals) - min(vals)) if vals else 0.0


async def _sample_kinematic(adapter, comps, n_probe=3):
    """Crank + rockers + platen over the run -- the kinematic-stage signal.

    Gates: (1) solve-lock on the crank (constant-rate motor must track);
    (2) dead-output on the rockers (a decoupled cam chain solves cleanly with
    a dead output). Platen feed is reported, not gated (chain tie best-effort).
    """
    probes = []
    for comp, name in _by_z_rank(adapter, "rocker-arm", comps=comps)[:n_probe]:
        probes.append((comp, f"rocker@{name.split('/')[-1]}"))
    crank, _ = _find_one(adapter, "crankshaft-1", comps=comps)
    if crank is not None:
        probes.append((crank, "crankshaft"))
    platen, platen_n = _find_one(adapter, "platen-1", comps=comps)
    if platen is not None:
        probes.append((platen, "platen"))
    rows = await _sample_transforms(adapter, probes, n_steps=12)

    spans = {}
    for label, samples in rows.items():
        if label == "platen":
            # linear feed: track world-Y/X translation magnitude
            pts = [(t, _world(a, [0, 0, 0])) for t, a in samples if a is not None]
            if pts:
                d = max(math.dist(pts[0][1], p) for _t, p in pts)
                spans[label] = d
            continue
        spans[label] = _span(_rot_series(samples))
    log(f"  kinematic spans: { {k: round(v, 2) for k, v in spans.items()} }")

    if crank is not None:
        assert_motion_progressed(rows["crankshaft"], DURATION_S, "crankshaft")
        rocker_max = max((v for k, v in spans.items() if k.startswith("rocker")),
                         default=0.0)
        if rocker_max < ROCKER_MIN_DEG:
            raise RuntimeError(
                f"DEAD OUTPUT: crank drove the full run but the largest rocker "
                f"swing was only {rocker_max:.2f} deg (< {ROCKER_MIN_DEG}) -- "
                f"the cam-follower chain is decoupled.")
    return {"spans_deg": {k: v for k, v in spans.items() if k != "platen"},
            "platen_feed_mm": spans.get("platen"),
            "rows": _rows_json(rows)}


async def _sample_summing_chain(adapter, comps):
    """channel-lever / summing-lever / magnifying-wheel rotation over the run --
    the spring-summing signal. Gate: the summing lever must actually rock."""
    probes = []
    for needle in ("channel-lever-1", "summing-lever-1", "magnifying-lever-1",
                   "magnifying-wheel-1"):
        comp, name = _find_one(adapter, needle, comps=comps)
        if comp is not None:
            probes.append((comp, needle.rsplit("-1", 1)[0]))
    rows = await _sample_transforms(adapter, probes, n_steps=12)
    spans = {label: _span(_rot_series(samples)) for label, samples in rows.items()}
    log(f"  summing-chain spans(deg): { {k: round(v, 2) for k, v in spans.items()} }")
    if spans.get("summing-lever", 0.0) < SUM_MIN_DEG:
        raise RuntimeError(
            f"DEAD OUTPUT: summing-lever rocked only "
            f"{spans.get('summing-lever', 0.0):.3f} deg (< {SUM_MIN_DEG}) -- "
            f"the 20-spring force balance never moved it; check the spring "
            f"elements and that the channel levers are oscillating.")
    return {"spans_deg": spans, "rows": _rows_json(rows)}


async def _sample_pen(adapter, comps, n_steps=48):
    """Pen-marker tip world-Y over the run + the dead-output gate.

    Returns the (t, y_mm) series for the truth-curve comparison asset."""
    marker, _ = _find_one(adapter, "pen-marker", comps=comps)
    if marker is None:
        raise RuntimeError("pen-marker not found for the pen sample")
    rows = await _sample_transforms(adapter, [(marker, "pen-marker")], n_steps)
    series = [(t, _world(a, [0.0, 0.0, 0.0])[1])
              for t, a in rows["pen-marker"] if a is not None]
    ys = [y for _t, y in series]
    span = (max(ys) - min(ys)) if ys else 0.0
    log(f"  pen-tip Y span = {span:.3f} mm over {len(series)} samples")
    if span < PEN_MIN_MM:
        raise RuntimeError(
            f"DEAD OUTPUT: pen-tip travelled only {span:.3f} mm "
            f"(< {PEN_MIN_MM}) -- the summing->wheel->pen chain never moved.")
    return {"series_t_y": series, "span_mm": span}


def _rows_json(rows):
    """Transform rows -> JSON-serializable {label: [(t, deg)]} rotation series."""
    return {label: _rot_series(samples) for label, samples in rows.items()}


async def _reset_to_assembled(adapter):
    """Return the model to its assembled pose before calculate_motion.

    calculate_motion is POSE-DEPENDENT: solving from a previous run's settled
    pose makes the closed-loop cam mechanism lock (proven), whereas solving
    from the assembled pose reliably moves.
    """
    from solidworks_mcp.adapters.base import MotionTimeParameters
    await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=""))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3(), default=None)
    log("  reset to assembled pose (set_time 0 + rebuild) before solve")


async def _export_video(adapter, stage):
    from solidworks_mcp.adapters.base import MotionExportParameters
    vid = (OUT_PNG.parent / f"{ASM}-operation-{stage}.mp4").resolve()
    res = await adapter.export_motion_video(MotionExportParameters(
        file_path=str(vid), study_name="", frames_per_second=25.0))
    if res.is_success:
        log(f"  video {res.data['bytes']} bytes -> {vid}")
        return str(vid)
    _telemetry.warn(f"video export failed: {res.error}")
    return None


def _write_samples(stage, payload):
    OUT_MOTION.mkdir(parents=True, exist_ok=True)
    path = OUT_MOTION / f"{stage}-samples.json"
    path.write_text(json.dumps(payload, indent=1))
    log(f"  samples -> {path}")
    return str(path)


# ---- main --------------------------------------------------------------------
async def build(adapter):
    stage = sys.argv[1] if len(sys.argv) > 1 else "kinematic"
    order = {"flex": 0, "kinematic": 1, "springs": 2, "full": 3}
    if stage not in order:
        raise RuntimeError(f"unknown stage {stage!r}; pick {sorted(order)}")
    level = order[stage]
    opts = set(sys.argv[2:])
    preset = "square" if "square" in opts else "config"
    log(f"stage = {stage} (level {level}) preset={preset} "
        f"rpm={CRANK_RPM} dur={DURATION_S}s channels={N_CHANNELS}")

    # A prior run's in-memory motion study triggers the blocking "Update
    # Initial Animation State" modal on the next mate edit (proven); start from
    # a clean session. CloseDoc discards dirty docs without the save prompt.
    from _assembly_postbuild import discard_open_documents
    discard_open_documents(adapter)

    asm_path = str((OUT_SLDASM / f"{ASM}.SLDASM").resolve())
    check("open harmonic-analyzer", await adapter.open_model(asm_path))
    log(f"opened {asm_path}")

    with _telemetry.span("motion.flex"):
        await _flex_subs(adapter)
        await _replay_setup_parks(adapter, preset)
    if level < 1:
        log("stage flex complete (no motor/solve)")
        return {}

    log("  enumerating components (single full-tree walk, reused everywhere) ...")
    comps = _components(adapter)

    with _telemetry.span("motion.couplings"):
        await _add_cam_couplings(adapter, comps=comps)
        await _tie_paper_chain(adapter, comps=comps)

    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    from solidworks_mcp.adapters.base import MotionStudyParameters, MotionStudyRefParameters
    made = check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION_S, activate=True)))
    log(f"  study {made['name']!r}")
    await _add_crank_motor(adapter)

    if level >= 2:
        from build_motion_study_springs import add_springs
        with _telemetry.span("motion.springs"):
            await add_springs(adapter, comps=comps)
    if level >= 3:
        from build_motion_study_springs import add_output_couplings
        with _telemetry.span("motion.output"):
            await add_output_couplings(adapter, comps=comps,
                                       with_gravity="grav" in opts)

    await _reset_to_assembled(adapter)
    log("  Calculate() -- blocking solve of the whole device ...")
    with _telemetry.span("motion.calculate"):
        check("calculate_motion", await adapter.calculate_motion(
            MotionStudyRefParameters(name="")))

    payload = {"stage": stage, "preset": preset, "rpm": CRANK_RPM,
               "duration_s": DURATION_S, "channels": N_CHANNELS}
    with _telemetry.span("motion.sample"):
        payload["kinematic"] = await _sample_kinematic(adapter, comps)
        if level >= 2:
            payload["summing"] = await _sample_summing_chain(adapter, comps)
        if level >= 3:
            payload["pen"] = await _sample_pen(adapter, comps)

    artefacts = {"samples": _write_samples(stage, payload)}
    vid = await _export_video(adapter, stage)
    if vid:
        artefacts["video"] = vid
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
