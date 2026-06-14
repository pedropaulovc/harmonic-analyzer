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
  4a. add 20 rod-pin<->rocker-bore coincident revolutes INSIDE channel.SLDASM
      (currentModel retargeted to the sub doc, never saved): the rod<->rocker
      pin joint cannot be a top-level mate because AddMate5 refuses a mate
      between two parts both nested in the same flexible sub (proven).
  4b. add 20 cross-assembly CAM couplings: each channel connecting-rod ring axis
      rides its drive-train cylinder-gear eccentric lobe axis (cross-sub, so it
      IS allowed at the top level). 4a + 4b are the 1-DOF four-bar that turns
      crank rotation into the per-channel rocker oscillation.
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
import os
import sys

from _common import (
    OUT_PNG, OUT_SLDASM, _flag, _read_member, check, coincident_mate,
    component_named_ref, log, named_ref, run_build,
)
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

# A point on the connecting-rod's Ø51 ring-bore circular edge (part-local mm); its
# arc centre is the ring centre = the rod origin (the cam pin point). See the
# phase-f motion-study memory (point-on-axis cam de-redundancy).
ROD_BORE_EDGE_MM = [25.5, 0.0, 1.5]

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

# Basic Motion spring-rate OVERRIDE (N/m). The geometric steel rates are
# k_ch ~ 2130 N/m, k_ct ~ 514 N/m -- the isolated POC (poc_spring_adder.py)
# proved k~2000 N/m ABORTS the fixed-step solve (omega too high), while k in the
# low-N/m..tens-of-N/m band tracks the moving-anchor sum cleanly. The full-model
# levers are heavier than the POC's 1.6 g bushing so they tolerate a higher rate,
# but 2 kN/m is over the line -- default to a solver-safe band and sweep via env.
# 0 or negative => fall back to the geometric helical rate.
SPRING_KCH = float(os.environ.get("SPRING_KCH", "50.0"))   # N/m, channel springs
SPRING_KCT = float(os.environ.get("SPRING_KCT", "25.0"))   # N/m, counter spring


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

    # channel: free the cam-follower chain. THREE families, three rules:
    #
    #  * rocker-arm -> recurring-only: suppress the constant spin driver, KEEP
    #    the per-station axial-Z hold so each rocker stays at its channel station
    #    (the rocker pivot revolute is a real two-part mate, untouched).
    #
    #  * channel-lever -> recurring-only: suppress the constant J4 spin driver so
    #    the lever is FREE to rotate about its fulcrum, KEEP its per-station
    #    axial-Z hold and its J4 fulcrum revolute. The lever is then driven by the
    #    in-sub gear off the rocker (_add_lever_gears, ratio = the channel
    #    coefficient), replacing the dead bar-foot-on-rocker CONTACT that Basic
    #    Motion ignores.
    #
    #  * amplitude-bar -> NOT suppressed. The bar is a COEFFICIENT SETTING: it
    #    must stay frozen at its slide station, NOT move during a run. Its spin +
    #    axial drivers are KEPT so it stays upright and pinned; its X/Y are not
    #    ground-pinned but ride the lever pin via the J3 coincident, so as the
    #    geared lever rotates the bar simply TRANSLATES upright with it (no foot
    #    constraint to fight, no closed loop, no over-constraint). Suppressing the
    #    bar drivers instead (the earlier probe) left all 20 bars free to swing
    #    about their lever pins -- with the foot support being an ignored CONTACT
    #    they flopped up into a black slab. Keep them pinned.
    #
    #  * connecting-rod -> suppress ALL of its drivers (ring-X/Y/Z AND the swing,
    #    which spin_driver implements as a DISTANCE mate). Artifact A pins the rod
    #    purely with these four drivers and deliberately omits the rod<->rocker
    #    and rod<->cam revolutes (build_channel_assembly._pin_design_pose). The
    #    rod must be FULLY free so the two new revolutes can define it: the in-sub
    #    rod-pin<->rocker-bore coincident (_add_rod_rocker_revolutes, authored in
    #    channel.SLDASM's own context) pins the pin to the rocker bore, and the
    #    top-level cam ring<->lobe (_add_cam_couplings, cross-sub) pins the ring
    #    to the eccentric lobe; together they are the 1-DOF four-bar driven by the
    #    crank. (Earlier theory that a kept ring-Z over-constrains was WRONG --
    #    probe_axis_isolate proved the real blocker is that AddMate5 refuses ANY
    #    top-level mate between two parts both nested in the same flexible sub, so
    #    pin<->rocker had to move INSIDE the sub, not be dropped for over-defn.)
    await _suppress_recurring(
        adapter, "channel-1", ("rocker-arm",), "channel rocker spin drivers")
    await _suppress_recurring(
        adapter, "channel-1", ("channel-lever",), "channel lever spin drivers")
    await _suppress_named(
        adapter, "channel-1", ("connecting-rod",), (DISTANCE, ANGLE),
        "channel rod drivers (free the rod fully)")


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


async def _add_rod_rocker_revolutes(adapter):
    """Per channel, INSIDE channel.SLDASM: rod pin Axis2 <-> rocker bore Axis2.

    This is the rod<->rocker pin joint of the four-bar, and it CANNOT be a
    top-level mate. AddMate5 rejects a mate between two components that are both
    nested in the SAME flexible sub -- proven decisively (probe_axis_isolate):
    the same rod.Axis2 mates fine CROSS-sub to gear.Axis3 (OK), but same-sub to
    rocker.Axis2 it FAILS "unknown error" on every alignment, coincident AND
    concentric; rod.Axis1<->rocker.Axis2 (also same-sub) fails too. Authored as a
    SIBLING mate in the channel sub's own document it succeeds, and with the
    top-level cam coupling added afterwards the four-bar closes (the 0.39 mm
    layout slack is absorbed by a ~0.2 deg rocker rotation -- the
    circle-intersection test holds: |127-120.92| <= 178.6 <= 127+120.92). Proven
    end-to-end by probe_sub_mate.py (sub pin<->bore OK, cam-after OK).

    Run AFTER the rod ring drivers are suppressed (rod free) and BEFORE the
    top-level cam couplings. currentModel is retargeted to the sub doc for the
    AddMate then restored; the sub is dirtied but NEVER saved (artifact A stays
    fully-defined on disk). coincident, not concentric (concentric on two axes is
    rejected by AddMate5 even cross-sub).
    """
    _, ch_doc = _sub_model(adapter, "channel-1")
    top = adapter.currentModel
    adapter.currentModel = ch_doc
    ok = n = 0
    try:
        log("  enumerating channel.SLDASM parts for in-sub rod<->rocker ...")
        comps = _components(adapter, ch_doc)
        rods = _by_z_rank(adapter, "connecting-rod", comps=comps)
        rockers = _by_z_rank(adapter, "rocker-arm", comps=comps)
        n = min(len(rods), len(rockers))
        log(f"  in-sub rod<->rocker: {len(rods)} rods, {len(rockers)} rockers "
            f"-> {n} channels")
        for i in range(n):
            rod_n, rk_n = rods[i][1], rockers[i][1]
            try:
                res = await coincident_mate(
                    adapter, _entity_ref(rod_n, "Axis2", "AXIS"),
                    _entity_ref(rk_n, "Axis2", "AXIS"),
                    label=f"ch{i:02d} rod pin <-> rocker bore (in channel)")
                ok += 1 if res.get("name") else 0
            except Exception as exc:  # noqa: BLE001 -- first-run diagnostics
                log(f"    ch{i:02d} in-sub rod->rocker FAILED: {exc}")
        adapter._attempt(lambda: ch_doc.ForceRebuild3(False), default=None)
    finally:
        adapter.currentModel = top
    log(f"  in-sub rod<->rocker revolutes: {ok}/{n}")
    return ok


async def _add_ring_centre_point(adapter):
    """Create a mateable ring-centre RefPoint on the SHARED connecting-rod part.

    The cam pin must be POSITION-ONLY (point-on-axis, 2 constraints) -- a
    collinear-axes pin re-fixes the rod orientation the rod<->rocker pin already
    fixes, over-constraining 20 parallel loops so Basic Motion solves erratically
    (proven: the same model recalcs to 11.9/0/0 deg). The rod's ORIGIN feature is
    NOT mateable (AddMate5 unknown error), so create a real RefPoint at the ring
    centre: the arc centre of the Ø51 bore edge. All 20 instances share
    connecting-rod.SLDPRT, so ONE point on that part doc is inherited by every
    instance via GetCorresponding; the part is NEVER saved (artifact A on disk is
    untouched). Selection in a component's part doc requires it be the ACTIVE doc
    -> ActivateDoc3 round-trip. Returns the point feature name (e.g. "Point2").
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


async def _add_cam_couplings(adapter):
    """Per channel, at TOP level: rod ring-centre POINT on cam lobe Axis3 (cross-sub).

    A POINT-ON-AXIS coincident: the rod ring-centre RefPoint
    (_add_ring_centre_point) on Axis3@cylinder-gear (the eccentric cam-lobe axis).
    This is 2 constraints (position only) -- it pins the ring to the orbiting lobe
    WITHOUT re-fixing the rod orientation that the rod<->rocker pin already fixes,
    so the 20 parallel four-bar loops are NOT over-constrained and Basic Motion
    solves reliably (a collinear-axes pin made the solve erratic; see memory).
    Cross-sub (drive-train<->channel), allowed at top level. The cam lobe orbits
    as the gear turns -> the rod ring follows -> via the in-sub rod<->rocker
    revolute the rod pin drives the rocker -> the rocker oscillates about its
    (artifact-A) pivot revolute.
    """
    from solidworks_mcp.adapters.base import RotateComponentParameters
    point_name = await _add_ring_centre_point(adapter)
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
        # PERTURB before mating: at the EXACT design pose the rod ring point lies
        # ON the eccentric lobe Axis3 (degenerate zero-distance), and AddMate5
        # rejects a point-on-axis there as "over-defines the assembly". Spin the
        # gear ~20 deg about its own axis so the eccentric lobe orbits the axis OFF
        # the stationary rod ring point -> non-degenerate -> the mate adds cleanly
        # (proven decisively: control FAIL vs perturbed 3/3, probe_perturb_cam).
        # The closing ForceRebuild3 snaps every gear back to its concentric+axial
        # mate pose, dragging the ring back onto the lobe; the added mate then just
        # holds. Read the gear's spin axis from its world transform (local Z ->
        # cols 6..8, origin -> cols 9..11 in metres).
        a = _comp_xform(adapter, gear_comp)
        await adapter.rotate_component(RotateComponentParameters(
            name=gear_n, angle=20.0, axis_vector=[a[6], a[7], a[8]],
            axis_point=[a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0], mode="exact"))
        if i == 0:
            log(f"    ch00 names: gear={gear_n!r} rod={rod_n!r} point={point_name!r}")
        try:
            cam = await coincident_mate(
                adapter, _entity_ref(rod_n, point_name, "POINT"),
                _entity_ref(gear_n, "Axis3", "AXIS"),
                label=f"ch{i:02d} cam lobe <-> rod ring point")
            cam_ok += 1 if cam.get("name") else 0
        except Exception as exc:  # noqa: BLE001 -- first-run diagnostics
            log(f"    ch{i:02d} cam coupling FAILED: {exc}")
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    log(f"  cam couplings: {cam_ok}/{n}")
    return cam_ok


# ---- stage 4c: per-channel rocker->lever transmission gear -------------------
# The integration coefficient of channel k is the linkage gain dtheta_lever /
# dtheta_rocker, set by the amplitude bar's slide position: rotating the rocker
# by dtheta moves the foot contact (at radius R_foot up the rocker arc) by
# ~R_foot*dtheta, which pushes the lever bar-pin (at radius L_lever from the
# fulcrum) by ~R_foot/L_lever * dtheta. So coefficient = R_foot / L_lever, and
# MOVING the bar (changing R_foot) changes the coefficient -- exactly the machine
# input. Basic Motion ignores the bar-foot-on-rocker CONTACT, so the gain cannot
# come from the physical linkage; we encode it as a GEAR ratio rocker<->lever
# (gears ARE enforced in-sub -- proven, probe_channel_gear). ``ratio_fn(i)``
# returns the [rocker, lever] ratio for channel i; default 1:1 (the F6b wiring +
# flop-fix gate -- the geometry-derived per-bar coefficient is the F6c tuning
# step). The bar stays pinned (frozen at its slide station) and rides the geared
# lever via the J3 coincident, so it neither flops nor locks the lever.
async def _add_lever_gears(adapter, ratio_fn=None):
    from _common import gear_mate
    _, ch_doc = _sub_model(adapter, "channel-1")
    top = adapter.currentModel
    adapter.currentModel = ch_doc
    ok = n = 0
    try:
        log("  enumerating channel.SLDASM parts for in-sub rocker<->lever gears ...")
        comps = _components(adapter, ch_doc)
        rockers = _by_z_rank(adapter, "rocker-arm", comps=comps)
        levers = _by_z_rank(adapter, "channel-lever", comps=comps)
        n = min(len(rockers), len(levers))
        log(f"  in-sub lever gears: {len(rockers)} rockers, {len(levers)} levers "
            f"-> {n} channels")
        for i in range(n):
            rocker_n, lever_n = rockers[i][1], levers[i][1]
            ratio = ratio_fn(i) if ratio_fn else [1.0, 1.0]
            done = False
            for alignment in ("aligned", "anti_aligned"):
                try:
                    g = await gear_mate(
                        adapter, _entity_ref(rocker_n, "Axis1", "AXIS"),
                        _entity_ref(lever_n, "Axis1", "AXIS"),
                        ratio, alignment=alignment,
                        label=f"ch{i:02d} rocker->lever gear (coeff)")
                    if g.get("name"):
                        ok += 1
                        done = True
                        break
                except Exception as exc:  # noqa: BLE001 -- first-run diagnostics
                    if i == 0:
                        log(f"    ch00 gear alignment={alignment} rejected: {exc}")
            if not done and i == 0:
                log("    ch00 gear FAILED both alignments")
        adapter._attempt(lambda: ch_doc.ForceRebuild3(False), default=None)
    finally:
        adapter.currentModel = top
    log(f"  in-sub rocker<->lever gears: {ok}/{n}")
    return ok


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
    """Component world transform as a 16-float array, or None if unreadable.

    After a heavy Basic Motion solve, Transform2 (or its ArrayData) occasionally
    returns None on a set_motion_time sample -- a transient COM read, not a real
    error. Return None so callers skip that sample instead of crashing the run."""
    t = _read_member(comp, "Transform2")
    data = _read_member(t, "ArrayData") if t is not None else None
    if data is None:
        return None
    return [float(v) for v in data]


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
        a = _comp_xform(adapter, marker)
        if a is None:
            log(f"    t={t:5.2f}s pen tip=n/a (transient transform read)")
            continue
        tip = _world(a, [0.0, 0.0, 0.0])
        samples.append((t, tip))
        log(f"    t={t:5.2f}s pen tip=({tip[0]:.2f},{tip[1]:.2f},{tip[2]:.2f})")
    if samples:
        ys = [tip[1] for _t, tip in samples]
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
    """Sample crank + a few rockers' rotation over the run -- the motion signal.

    The crankshaft is sampled last in every row so a single look distinguishes
    the two failure modes: crank span 0 => the motor never drove (solve/over-
    constraint failure); crank span > 0 with rockers 0 => the cam-follower chain
    failed to transmit under the dynamic solve."""
    from solidworks_mcp.adapters.base import MotionTimeParameters
    probes = _by_z_rank(adapter, "rocker-arm")[:n_probe]
    crank, _ = _find_one(adapter, "crankshaft-1")
    if crank is not None:
        probes = probes + [(crank, "crankshaft")]
    base = {}
    spans = {}
    for s in range(13):
        t = DURATION_S * s / 12.0
        check(f"set_time {t:.2f}", await adapter.set_motion_time(
            MotionTimeParameters(time=t, study_name=study_name)))
        row = []
        for comp, name in probes:
            a = _comp_xform(adapter, comp)
            if a is None:
                row.append("  n/a")
                continue
            base.setdefault(name, a)
            ang = _rot_angle(base[name], a)
            spans[name] = max(spans.get(name, 0.0), ang)
            row.append(f"{ang:5.1f}")
        log(f"    t={t:4.2f}s rock(deg)=[{', '.join(row)}] (last=crank)")
    log(f"  rock spans: {dict((k, round(v, 1)) for k, v in spans.items())} "
        f"(crank 0 => motor didn't drive; rockers 0 w/ crank>0 => cam chain broke)")
    return spans


async def _sample_part_rot(adapter, needle, study_name="", n_steps=12):
    """Rotation span (deg) of a single named part over the run -- e.g. the
    summing-lever rocking under the spring force balance (the analogue SUM)."""
    from solidworks_mcp.adapters.base import MotionTimeParameters
    comp, name = _find_one(adapter, needle)
    if comp is None:
        log(f"    {needle} not found")
        return 0.0
    base = None
    span = 0.0
    for s in range(n_steps + 1):
        t = DURATION_S * s / n_steps
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=study_name))
        a = _comp_xform(adapter, comp)
        if base is None:
            base = a
        span = max(span, _rot_angle(base, a))
    log(f"  {needle} rock span = {span:.2f} deg (0 => the springs never moved it)")
    return span


async def _sample_chain(adapter, study_name="", n_steps=12):
    """Per-timestep rotation of the spring-driven summing chain -- the F6 signal.

    Samples channel-lever (the spring's moving end, driven by the cam->bar->lever
    linkage), summing-lever (the analogue SUM = force balance of the 20 springs),
    and magnifying-wheel (geared to the summing-lever). If the channel-lever
    oscillates but the summing-lever jumps once and holds, the spring force
    balance is snapping to a static equilibrium instead of tracking the inputs."""
    from solidworks_mcp.adapters.base import MotionTimeParameters
    parts = []
    for needle in ("channel-lever-1", "summing-lever-1", "magnifying-wheel-1"):
        comp, name = _find_one(adapter, needle)
        if comp is not None:
            parts.append((needle, comp))
    if not parts:
        return
    base = {}
    spans = {}
    for s in range(n_steps + 1):
        t = DURATION_S * s / n_steps
        await adapter.set_motion_time(MotionTimeParameters(time=t, study_name=study_name))
        row = []
        for needle, comp in parts:
            a = _comp_xform(adapter, comp)
            if a is None:
                row.append(f"{needle.split('-1')[0]}=  n/a")
                continue
            base.setdefault(needle, a)
            ang = _rot_angle(base[needle], a)
            spans[needle] = max(spans.get(needle, 0.0), ang)
            row.append(f"{needle.split('-1')[0]}={ang:6.2f}")
        log(f"    t={t:4.2f}s  {'  '.join(row)}")
    log(f"  chain spans(deg): {dict((k.split('-1')[0], round(v, 1)) for k, v in spans.items())}")
    return spans


async def _reset_to_assembled(adapter):
    """Return the model to its assembled pose before calculate_motion.

    calculate_motion is POSE-DEPENDENT: solving from a previous run's moved/
    settled pose makes the closed-loop cam mechanism lock (proven: identical
    recalcs gave 11.9/0/0 deg), whereas solving from the assembled pose reliably
    moves. set_motion_time(0) then a forced rebuild restores the mate-solved pose.
    """
    from solidworks_mcp.adapters.base import MotionTimeParameters
    await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=""))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3(), default=None)
    log("  reset to assembled pose (set_time 0 + rebuild) before solve")


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

    await _add_rod_rocker_revolutes(adapter)
    await _add_cam_couplings(adapter)
    await _add_lever_gears(adapter)
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
        await add_wires_gravity(adapter, with_gravity="grav" in sys.argv[2:])

    await _reset_to_assembled(adapter)
    log("  Calculate() -- blocking solve of the whole device, expect ~270s ...")
    check("calculate_motion", await adapter.calculate_motion(
        MotionStudyRefParameters(name="")))
    await _sample_rockers(adapter)
    if level >= 2:
        await _sample_chain(adapter)
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
