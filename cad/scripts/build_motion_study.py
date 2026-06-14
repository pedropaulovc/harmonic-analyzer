r"""Phase F (artifact B): the OPERATION simulation -- a throwaway SOLIDWORKS
Motion study that opens the static, fully-defined harmonic-analyzer.SLDASM and
drives the whole device from a single crank motor, with the channel/counter
springs as real force elements and the two amplifying wires as motion
couplings. It NEVER re-saves the .SLDASM (artifact A stays fully-defined on
disk; this study lives only in the dirtied in-memory doc + an exported video).

Pipeline (see plan from-other-conversation-current-tender-meteor.md, Part 3):

  1. open harmonic-analyzer.SLDASM (the 4 subs inserted rigid + fixed).
  2. for the 3 MOVING subs (channel/drive-train/output; frame stays fixed):
     float -> ground the rigid pose at identity with 3 coincident plane mates
     -> set_component_solving FLEXIBLE, so their internal mates solve with the
     parent and a top-level motor/cam/spring reaches the parts inside them.
  3. suppress the internal DRIVER dims that pin the DOF Motion must control:
       * drive-train: the single crank-angle driver (frees the whole gear train)
       * channel:     the per-rocker spin + per-rod swing drivers (frees the
                      rocker->rod cam followers); the 20 amplitude-bar slides
                      stay pinned (they are coefficient settings)
       * output:      the 4 compliant-chain snapshot drivers (summing-lever,
                      magnifying-lever, magnifying-wheel rocks + pen-rod travel);
                      the platen + clamp settings stay pinned
     -- all via suppress_mate(component=<sub>), resolved inside the sub doc,
     never saving the sub.
  4. add 20 cross-assembly CAM concentrics: each channel connecting-rod ring
     bore rides its drive-train cylinder-gear eccentric lobe (the coupling that
     turns crank rotation into the per-channel rocker oscillation).
  5. crank MOTOR: a rotary constant-speed motor on the crankshaft axis -- the
     one physical input that runs the device.
  6. 21 SPRING force elements: 20 channel springs + 1 counter spring, k from
     k = G*d^4 / (8*D^3*n), G(steel) = 79.3 GPa, geometry per part script.
  7. the TWO WIRES as motion couplings: WIRE 1 vertical-rod/fixture -> wheel hub
     (Ø20), WIRE 2 wheel rim (Ø100) -> pen-rod, 5x amplification.
  8. gravity (-Y); Calculate(); export an .mp4; sample the pen-marker tip over a
     crank revolution and compare to the synthesized harmonic curve.

Basic Motion (physical_simulation) is the licensed solver on this 3DEXPERIENCE
Makers seat -- MotionAnalysis is NOT licensed here. Basic Motion solves motors,
springs, gravity and contact, which is what this study needs.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_motion_study.py [stage]

``stage`` (default ``kinematic``) gates how far the build runs so the heavy
solve can be brought up incrementally:
    flex       -> flexible + suppress only (no motor/solve)
    kinematic  -> + cam concentrics + crank motor + Calculate + pen sample
    springs    -> + 21 spring force elements
    full       -> + the two wires + gravity + video + harmonic-curve compare
"""

from __future__ import annotations

import math
import sys

from _common import (
    OUT_PNG, OUT_SLDASM, _flag, _read_member, check, coincident_mate,
    component_named_ref, log, named_ref, run_build,
)

# ---- study constants --------------------------------------------------------
ASM = "harmonic-analyzer"
MOVING_SUBS = ("drive-train-1", "channel-1", "output-1")  # frame-1 stays fixed
FRAME_SUB = "frame-1"

CRANK_RPM = 20.0          # gentle: 1 rev / 3 s at 20 RPM
DURATION_S = 6.0          # two crank revolutions
N_CHANNELS = 20

# swMateType_e
COINCIDENT, CONCENTRIC, DISTANCE, ANGLE = 0, 1, 5, 6
_MATE_NAME = {0: "COINCIDENT", 1: "CONCENTRIC", 4: "TANGENT", 5: "DISTANCE",
              6: "ANGLE", 9: "CAMFOLLOWER", 10: "GEAR", 13: "RACKPINION",
              16: "LOCK"}

RIGID, FLEXIBLE = "rigid", "flexible"

# Spring stiffness k = G*d^4 / (8*D^3*n); steel shear modulus.
G_STEEL = 79.3e9  # Pa
# channel spring: wire d 1.0, OD 6.5 -> mean D 5.5, active coils n 28, free 32mm
CH_SPRING = dict(d=1.0, D=5.5, n=28.0, free_mm=32.0)
# counter spring: wire d 1.8, OD 12.5 -> mean D 10.7, n 165, free body 315mm
CT_SPRING = dict(d=1.8, D=10.7, n=165.0, free_mm=315.0)


def _k_helical(d_mm: float, D_mm: float, n: float) -> float:
    """Linear rate (N/m) of a helical compression/extension spring."""
    d, D = d_mm / 1000.0, D_mm / 1000.0
    return G_STEEL * d**4 / (8.0 * D**3 * n)


# ---- nested-component helpers (GetComponentByName fails on 'sub/part') -------
# GetComponents(False) returns the WHOLE nested tree -- and once the moving subs
# are flexible that is hundreds of nodes, each costing a Name2 COM round-trip.
# It is the dominant hidden cost of the silent stretches, so every walk is timed
# (logged) and callers that need it more than once enumerate ONCE and pass the
# (comp, name) list down. ``toplevel=True`` returns only the top-level instances
# (the moving subs) -- a tiny, fast list; use it whenever no nested part is
# needed (e.g. verifying a sub's Solving state).
def _components(adapter, model=None, toplevel=False):
    """``[(comp, Name2), ...]`` for every component; logs the walk + its cost."""
    import time as _t
    model = model or adapter.currentModel
    t0 = _t.perf_counter()
    raw = adapter._attempt(lambda: model.GetComponents(bool(toplevel)), default=None) or []
    out = []
    for c in raw:
        _flag(c, "IComponent2")
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
    """Component Name2 -> exact part family.

    ``"drive-train-1/cylinder-gear-1"`` -> ``"cylinder-gear"`` and
    ``"drive-train-1/cylinder-gear-shaft-1"`` -> ``"cylinder-gear-shaft"`` --
    so a family match never confuses a part with another whose name it is a
    prefix of (the substring ``"cylinder-gear"`` matched the shaft too).
    """
    part = name2.split("/")[-1]
    return part.rsplit("-", 1)[0]


def _find_family(adapter, family, model=None, comps=None):
    """Components whose part family equals ``family`` EXACTLY (dispatch, name).

    Use this, not :func:`_find_comps`, whenever the needle is a prefix of a
    longer real part name (``cylinder-gear`` vs ``cylinder-gear-shaft``). Pass
    ``comps`` to reuse a single enumeration.
    """
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
            _flag(rc, "IComponent2")
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
    slow part) for callers that classify by family/type alone -- e.g. the
    drive-train crank driver, found by name, needs no value.

    ``progress_every`` > 0 logs a heartbeat every N mates walked -- the mate
    walk on a flexible sub is ~1-2s/mate (parts walk), so a few hundred mates
    is minutes of otherwise-silent work.
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
    """Sub instance name -> the doc-root part name it shows up as in its own
    mate group ("drive-train-1" -> "drive-train")."""
    return sub_name.rsplit("-", 1)[0]


def _real_parts(parts, root):
    """Distinct real part names, dropping the assembly-root pseudo-part.

    A driver dim references one real part + the sub root (the root plane the dim
    is measured against, which GetMateEntity reports as a component named after
    the sub doc). Structural mates reference two real parts.
    """
    return sorted({p for p in parts if p != root})


def _lone_real(parts, root):
    rp = _real_parts(parts, root)
    return rp[0] if len(rp) == 1 else None


def _family(part_name):
    """"rocker-arm-12" -> "rocker-arm" (strip the trailing instance suffix)."""
    return part_name.rsplit("-", 1)[0]


# ---- stage 2: float + ground + flex -----------------------------------------
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
        log(f"  set {sub} FLEXIBLE -- blocking solve, expect ~50-200s ...")
        check(f"flexible {sub}", await adapter.set_component_solving(
            SetComponentSolvingParameters(name=sub, solving=FLEXIBLE)))
        log(f"  verify {sub} Solving (top-level walk; first tree access may "
            f"trigger the deferred flex solve) ...")
        comp, _ = _find_one(adapter, sub, toplevel=True)
        solving = int(adapter._attempt(lambda c=comp: c.Solving, default=-1))
        log(f"  {sub} Solving={solving} (1=flexible)")
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)


# ---- stage 3: suppress the driver dims inside each sub -----------------------
# A driver dim references ONE real part + the sub root, and splits into:
#   * POSE / SPIN drivers -- the SAME value across all 20 channels (the rocker
#     spin angle, the rod ring X/Y + swing). These pin the DOF the cam should
#     control -> SUPPRESS.
#   * AXIAL-Z station holds -- a value that VARIES per channel (the part's Z
#     along the pitch). These hold the part at its station -> KEEP.
# So bucket single-real-part distance values by family: a value recurring across
# many instances is a pose driver; a per-instance-unique value is an axial hold.
SUPPRESS_RECUR = 5  # a value seen in >= this many instances == pose/spin driver


async def _suppress_named(adapter, sub_name, families, mtypes, label):
    """Suppress every single-real-part mate whose part is in FAMILIES.

    For unique drivers (e.g. the crank angle) where bucketing does not apply.
    """
    from solidworks_mcp.adapters.base import SuppressMateParameters
    _, model = _sub_model(adapter, sub_name)
    root = _root_title(sub_name)
    targets = []
    log(f"  {label}: scanning {sub_name} mates ...")
    for _f, _m, name, mtype, parts, val in _iter_mates(
            adapter, model, read_values=False, progress_every=20):
        if mtype not in mtypes:
            continue
        lone = _lone_real(parts, root)
        if lone is not None and _family(lone) in families:
            targets.append(name)
    await _do_suppress(adapter, sub_name, targets, label)
    return targets


async def _suppress_recurring(adapter, sub_name, families, label):
    """Suppress single-real-part DISTANCE mates whose value recurs across
    instances (pose/spin), keeping per-instance-unique values (axial holds)."""
    from collections import Counter
    _, model = _sub_model(adapter, sub_name)
    root = _root_title(sub_name)
    items = []  # (mate_name, family, rounded_value)
    log(f"  {label}: scanning {sub_name} mates ...")
    # Walk WITHOUT values (the slow DisplayDimension2 round-trip); read the value
    # lazily only for the family-matching single-real-part DISTANCE candidates.
    for _f, mate, name, mtype, parts, _val in _iter_mates(
            adapter, model, read_values=False, progress_every=20):
        if mtype != DISTANCE:
            continue
        lone = _lone_real(parts, root)
        if lone is None or _family(lone) not in families:
            continue
        val = _mate_value(adapter, mate, mtype)
        if val is None:
            continue
        items.append((name, _family(lone), round(val * 1000.0, 1)))
    counts = Counter((fam, v) for _n, fam, v in items)
    targets = [n for n, fam, v in items if counts[(fam, v)] >= SUPPRESS_RECUR]
    kept = [(fam, v) for (fam, v), c in counts.items() if c < SUPPRESS_RECUR]
    log(f"  {label}: pose buckets {sorted({(f, v) for _n, f, v in items if counts[(f, v)] >= SUPPRESS_RECUR})}")
    log(f"  {label}: keeping {len(kept)} per-instance axial values")
    await _do_suppress(adapter, sub_name, targets, label)
    return targets


async def _do_suppress(adapter, sub_name, targets, label):
    # currentModel MUST stay the top assembly: suppress_mate(component=sub_name)
    # resolves the component against currentModel then retargets to its model doc
    # itself (GetModelDoc2). Switching currentModel to the sub doc here makes that
    # component lookup fail ("Component not found: 'drive-train-1'").
    from solidworks_mcp.adapters.base import SuppressMateParameters
    log(f"  {label}: suppressing {len(targets)} mates in {sub_name}")
    for name in targets:
        check(f"suppress {name}@{sub_name}",
              await adapter.suppress_mate(SuppressMateParameters(
                  name=name, suppress=True, component=sub_name)))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)


def _dump_sub_mates(adapter, sub_name):
    """Log every mate in a sub doc -- ground truth for the suppress classifier."""
    _, model = _sub_model(adapter, sub_name)
    root = _root_title(sub_name)
    log(f"  --- mates in {sub_name} (root={root}) ---")
    for _f, _m, name, mtype, parts, val in _iter_mates(adapter, model):
        lone = _lone_real(parts, root)
        vstr = ""
        if val is not None and mtype == DISTANCE:
            vstr = f" val={val * 1000.0:.2f}mm"
        elif val is not None and mtype == ANGLE:
            vstr = f" val={math.degrees(val):.2f}deg"
        log(f"    {name:16s} {_MATE_NAME.get(mtype, mtype)!s:11s} "
            f"lone={lone} parts={_real_parts(parts, root)}{vstr}")


async def _suppress_drivers(adapter, level, dump=False):
    if dump:
        for sub in MOVING_SUBS:
            _dump_sub_mates(adapter, sub)

    # drive-train: the crank-angle driver (crank-handle <-> root) -- unique, so
    # matched by name. Frees the whole gear train to spin from the motor.
    await _suppress_named(
        adapter, "drive-train-1", ("crank-handle",), (DISTANCE, ANGLE),
        "crank driver")

    # channel: free the cam-follower chain -- the rocker spin + the rod ring
    # X/Y/swing pose drivers (recurring values). Keep every per-station axial
    # hold, and leave the amplitude-bar + channel-lever pinned (they move only
    # once the bar tangent / output wires are added, later stages).
    await _suppress_recurring(
        adapter, "channel-1", ("rocker-arm", "connecting-rod"),
        "channel cam-follower drivers")


# ---- stage 4: per-channel cam + rod couplings (named axes) -------------------
def _entity_ref(name2, prefix, etype):
    """A depth-2-safe ``MateEntityRef`` for a named axis inside a nested part.

    ``name2`` is the top-level component path ("channel-1/connecting-rod-1") and
    ``prefix`` the part-local named feature ("Axis1"). The hand-built reversed
    string ``Axis1@connecting-rod-1@channel-1@harmonic-analyzer`` resolves only
    one level deep and returns False for a part nested in a flexible sub; the
    component+name ref maps the base IFeature through GetCorresponding instead
    (PR #64). ``GetCorresponding`` is depth-agnostic, so the assembly title is
    no longer threaded through.
    """
    return component_named_ref(name2, prefix, etype)


def _comp_z_mm(adapter, comp):
    return _comp_xform(adapter, comp)[11] * 1000.0


def _by_z_rank(adapter, family, comps=None):
    """Components of part FAMILY, sorted by world Z (station order).

    The 20 instances of each moving part span the 20 channel stations
    monotonically in Z, so the i-th entry of two such lists is the same
    station -- robust pairing without trusting instance-suffix order (a rod's
    Z sits between its own gear and the next station's gear, so nearest-Z
    pairing would mis-match). Exact-family match so ``cylinder-gear`` does not
    also drag in ``cylinder-gear-shaft``. Pass ``comps`` to reuse one walk.
    """
    hits = _find_family(adapter, family, comps=comps)
    return sorted(hits, key=lambda t: _comp_z_mm(adapter, t[0]))


async def _add_cam_couplings(adapter):
    """Per channel: cam lobe <-> rod ring, then rod pin <-> rocker bore.

    Both are two-axis COINCIDENT mates on named reference axes (AddMate rejects
    concentric on two axes): Axis3@cylinder-gear is the eccentric cam-lobe axis,
    Axis1@connecting-rod the ring axis, Axis2@connecting-rod the rod-pin axis,
    Axis2@rocker-arm the rocker rod-bore axis. Named axes are fast (no face walk
    on the geared part) and mirror-agnostic. The cam lobe orbits as the gear
    turns -> the rod ring follows -> the rod pin drives the rocker -> the rocker
    oscillates about its (artifact-A) pivot revolute. Proven on the 1-channel
    rig (probe_one_channel_motion.py).
    """
    log("  enumerating components for cam pairing (single full-tree walk) ...")
    comps = _components(adapter)
    gears = _by_z_rank(adapter, "cylinder-gear", comps=comps)
    rods = _by_z_rank(adapter, "connecting-rod", comps=comps)
    rockers = _by_z_rank(adapter, "rocker-arm", comps=comps)
    n = min(len(gears), len(rods), len(rockers))
    log(f"  cam couplings: {len(gears)} gears, {len(rods)} rods, "
        f"{len(rockers)} rockers -> {n} channels")
    cam_ok = rod_ok = 0
    for i in range(n):
        gear_n, rod_n, rk_n = gears[i][1], rods[i][1], rockers[i][1]
        if i == 0:
            log(f"    ch00 names: gear={gear_n!r} rod={rod_n!r} rocker={rk_n!r}")
        try:
            cam = await coincident_mate(
                adapter, _entity_ref(rod_n, "Axis1", "AXIS"),
                _entity_ref(gear_n, "Axis3", "AXIS"),
                label=f"ch{i:02d} cam lobe <-> rod ring")
            cam_ok += 1 if cam.get("name") else 0
        except Exception as exc:  # noqa: BLE001 -- first-run diagnostics
            log(f"    ch{i:02d} cam coupling FAILED: {exc}")
        try:
            rod = await coincident_mate(
                adapter, _entity_ref(rod_n, "Axis2", "AXIS"),
                _entity_ref(rk_n, "Axis2", "AXIS"),
                label=f"ch{i:02d} rod pin <-> rocker bore")
            rod_ok += 1 if rod.get("name") else 0
        except Exception as exc:  # noqa: BLE001 -- first-run diagnostics
            log(f"    ch{i:02d} rod->rocker FAILED: {exc}")
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    log(f"  couplings: cam {cam_ok}/{n}, rod->rocker {rod_ok}/{n}")
    return cam_ok, rod_ok


# ---- stage 5: crank motor ---------------------------------------------------
async def _add_crank_motor(adapter):
    from solidworks_mcp.adapters.base import MotionMotorParameters
    cs_comp, cs_name = _find_one(adapter, "crankshaft")
    if cs_comp is None:
        raise RuntimeError("crankshaft component not found")
    # Motor on the crankshaft BORE axis by name (Axis1) -- a component-face ref
    # walks the sprocket faces; the named axis is fast and nested-safe. The
    # component+name ref maps via GetCorresponding (depth-2 safe through the
    # flexible drive-train sub).
    axis = _entity_ref(cs_name, "Axis1", "AXIS")
    log(f"  crank motor on {axis.name}@{axis.component} ({CRANK_RPM} RPM) ...")
    res = check("add_motor crank", await adapter.add_motor(MotionMotorParameters(
        motor_type="rotary", entity=axis, speed=CRANK_RPM, study_name="")))
    return res


# ---- pen sampling -----------------------------------------------------------
def _comp_xform(adapter, comp):
    t = _read_member(comp, "Transform2")
    return [float(v) for v in _read_member(t, "ArrayData")]


def _world(a, local_mm):
    r, t = a[0:9], a[9:12]
    return [sum(local_mm[i] * r[i * 3 + k] for i in range(3)) + t[k] * 1000.0
            for k in range(3)]


async def _sample_pen(adapter, study_name=""):
    from solidworks_mcp.adapters.base import MotionTimeParameters
    samples = []
    steps = 24
    marker, _ = _find_one(adapter, "pen-marker")  # enumerate ONCE, not per step
    if marker is None:
        log("    pen-marker not found")
        return samples
    for s in range(steps + 1):
        t = DURATION_S * s / steps
        check(f"set_time {t:.2f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name=study_name)))
        tip = _world(adapter, _comp_xform(adapter, marker), [0.0, 0.0, 0.0])
        samples.append((t, tip))
        log(f"    t={t:5.2f}s pen tip=({tip[0]:.2f},{tip[1]:.2f},{tip[2]:.2f})")
    if samples:
        ys = [p[1][1] for _t, p in samples]
        log(f"  pen-tip Y span = {max(ys) - min(ys):.3f} mm "
            f"(0 => the pen never moved)")
    return samples


def _rot_angle(a0, a1):
    """Relative rotation magnitude (deg) between two component transforms."""
    def cols(a):
        return ((a[0], a[1], a[2]), (a[3], a[4], a[5]), (a[6], a[7], a[8]))
    c0, c1 = cols(a0), cols(a1)
    tr = sum(c1[k][i] * c0[k][i] for k in range(3) for i in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


async def _sample_rockers(adapter, study_name="", n_probe=3):
    """Sample a few rockers' rotation over the run -- the kinematic-stage motion
    signal (the cam-follower chain, before the output wires exist)."""
    from solidworks_mcp.adapters.base import MotionTimeParameters
    rockers = _by_z_rank(adapter, "rocker-arm")[:n_probe]
    base = {}
    spans = {}
    for s in range(13):
        t = DURATION_S * s / 12.0
        check(f"set_time {t:.2f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name=study_name)))
        row = []
        for comp, name in rockers:
            a = _comp_xform(adapter, comp)
            base.setdefault(name, a)
            ang = _rot_angle(base[name], a)
            spans[name] = max(spans.get(name, 0.0), ang)
            row.append(f"{ang:5.1f}")
        log(f"    t={t:4.2f}s rock(deg)=[{', '.join(row)}]")
    log(f"  rocker rock spans: {[f'{v:.1f}' for v in spans.values()]} "
        f"(0 => the cam chain never moved)")
    return spans


# ---- main -------------------------------------------------------------------
async def build(adapter):
    stage = sys.argv[1] if len(sys.argv) > 1 else "kinematic"
    order = {"flex": 0, "kinematic": 1, "springs": 2, "full": 3}
    if stage not in order:
        raise RuntimeError(f"unknown stage {stage!r}; pick {sorted(order)}")
    level = order[stage]
    dump = "dump" in sys.argv[2:]  # the mate-inventory walk is ~10 min; opt-in
    log(f"stage = {stage} (level {level}) dump={dump}")

    asm_path = str((OUT_SLDASM / f"{ASM}.SLDASM").resolve())
    check("open harmonic-analyzer", await adapter.open_model(asm_path))
    log(f"opened {asm_path}")

    await _flex_subs(adapter)
    await _suppress_drivers(adapter, level, dump=dump)
    if level < 1:
        log("stage flex complete (no motor/solve)")
        return {}

    await _add_cam_couplings(adapter)
    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    from solidworks_mcp.adapters.base import MotionStudyParameters, MotionStudyRefParameters
    made = check("create_motion_study", await adapter.create_motion_study(
        MotionStudyParameters(name="", study_type="physical_simulation",
                              duration=DURATION_S, activate=True)))
    log(f"  study {made['name']!r}")
    await _add_crank_motor(adapter)

    # springs / wires / gravity layered in later stages (see _springs/_wires).
    if level >= 2:
        from build_motion_study_springs import add_springs  # noqa: F401
        await add_springs(adapter)
    if level >= 3:
        from build_motion_study_springs import add_wires_gravity
        await add_wires_gravity(adapter)

    log("  Calculate() -- blocking solve of the whole device, expect ~270s ...")
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))
    await _sample_rockers(adapter)
    samples = await _sample_pen(adapter) if level >= 3 else []

    artefacts = {}
    if level >= 3 and samples:
        from solidworks_mcp.adapters.base import MotionExportParameters
        vid = (OUT_PNG.parent / f"{ASM}-operation.mp4").resolve()
        res = await adapter.export_motion_video(MotionExportParameters(
            file_path=str(vid), study_name="", frames_per_second=25.0))
        if res.is_success:
            log(f"  video {res.data['bytes']} bytes -> {vid}")
            artefacts["video"] = str(vid)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
