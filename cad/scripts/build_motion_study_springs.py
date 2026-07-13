r"""Phase F stage `springs`/`full`: the real force elements + couplings for the
operation motion study (artifact B). Imported lazily by build_motion_study.build:
``add_springs`` at level>=2, ``add_wires_gravity`` at level>=3. Like the rest of
the study these only dirty the in-memory doc -- NEVER saved (artifact A on disk
stays fully-defined).

SPRINGS (add_springs):
  * 20 channel springs -- each pulls a channel-lever tab eye down toward the
    summing-lever plate. As the cam chain rocks each channel-lever, its spring
    length changes, so the spring tension that channel applies to the summing
    lever changes; the summing-lever rocks to the force balance = the analogue
    SUM of the 20 channels (the machine's whole point). All 20 are the SAME
    spring (k equal); the amplitude weighting lives in the bar lever arms, not k.
  * 1 counter spring -- gooseneck (structural) <-> boss-hook (locked to the
    summing-lever); a restoring bias against the channel pull.
  k = G*d^4/(8*D^3*n) (steel) from the part geometry (CH_SPRING/CT_SPRING in
  build_motion_study). free_length=None starts each spring at its assembled
  length with ZERO force, so the motion is driven purely by the cam-chain length
  changes -- no fragile pretension calibration (tune later for amplitude, F6).

  The summing-lever rock driver (an ANGLE snapshot dim in output.SLDASM) is
  SUPPRESSED here so the springs can actually move it. The 20 bottom eyes share
  ONE summing-lever datum point: every plate hole sits at the same X off the
  knife axis, so each spring's torque arm about the (Z) knife line is identical
  -- one point reproduces the summing torque exactly (the per-hole Z does not
  contribute to Z-axis torque).

Each spring endpoint is a ring-centre RefPoint created at RUNTIME via arc_center
on the eye hole's circular edge, on the SHARED part doc (all instances inherit it
via GetCorresponding), NEVER saved -- same recipe as the cam ring point. Local
edge points validated live (probe_eye_points.py).
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
)
from build_motion_study import (
    ANGLE, CH_SPRING, CT_SPRING, DISTANCE, SPRING_KCH, SPRING_KCT, _by_z_rank,
    _components, _entity_ref, _family, _find_one, _iter_mates, _k_helical,
    _lone_real, _mate_value, _read_member, _sub_model, _suppress_named,
)

# Part-local points ON each eye hole's circular edge (mm) -> arc_center -> centre.
CH_LEVER_EYE = [179.8, 0.0, 0.0]       # channel-lever tab hole Ø4.0 @ (177.8,0,0)
SUM_LEVER_EYE = [39.35, 8.0, -69.05]   # summing-lever plate hole 0 Ø4.5, top face
GOOSENECK_EYE = [-109.0, 165.0, 0.0]   # gooseneck counter-spring pin end-face
BOSS_HOOK_EYE = [6.5, 16.5, 0.0]       # boss-hook rod end-face circle

# Free length: None = start at assembled length with zero force (no pretension to
# calibrate; motion comes from cam-chain length changes). Tunable for amplitude.
CH_FREE_LEN = None
CT_FREE_LEN = None


async def _eye_point(adapter, comp_needle, edge_point, label, comps=None):
    """Create a mateable eye-centre RefPoint on a SHARED part doc (never saved).

    arc_center on the eye hole's circular edge -> the ring centre. Selection in a
    component's part doc requires it be the ACTIVE doc -> ActivateDoc3 round-trip.
    All instances of the part inherit the point via GetCorresponding. Returns the
    point feature name (e.g. "Point2").
    """
    from solidworks_mcp.adapters.base import CreateReferencePointParameters
    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    comp, _ = _find_one(adapter, comp_needle, comps=comps)
    if comp is None:
        raise RuntimeError(f"{comp_needle} not found for eye point {label}")
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if part is None:
        raise RuntimeError(f"{comp_needle} part doc unresolved")
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, 0), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    pt = check(f"eye point {label}", await adapter.create_reference_point(
        CreateReferencePointParameters(mode="arc_center", edge_point=edge_point)))
    name = pt.get("name") if isinstance(pt, dict) else getattr(pt, "name", None)
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, 0), default=None)
    adapter.currentModel = top
    if not name:
        raise RuntimeError(f"eye point {label} returned no name")
    log(f"  eye point {label} on {part_title} = {name!r}")
    return name


async def add_springs(adapter):
    from solidworks_mcp.adapters.base import MotionSpringParameters

    # 1) free the summing-lever rock (the ANGLE snapshot dim) so springs move it.
    await _suppress_named(
        adapter, "output-1", ("summing-lever",), (ANGLE,),
        "summing-lever rock (free for springs)")

    # 2) eye datum points on the shared part docs (inherited by all instances).
    comps = _components(adapter)
    lever_pt = await _eye_point(adapter, "channel-lever-1", CH_LEVER_EYE,
                                "channel-lever tab", comps=comps)
    plate_pt = await _eye_point(adapter, "summing-lever-1", SUM_LEVER_EYE,
                                "summing-lever hole", comps=comps)
    goose_pt = await _eye_point(adapter, "gooseneck-1", GOOSENECK_EYE,
                                "gooseneck counter-top", comps=comps)
    hook_pt = await _eye_point(adapter, "boss-hook-1", BOSS_HOOK_EYE,
                               "boss-hook counter-bottom", comps=comps)

    sum_name = _find_one(adapter, "summing-lever-1", comps=comps)[1]
    levers = _by_z_rank(adapter, "channel-lever", comps=comps)
    k_geom = _k_helical(CH_SPRING["d"], CH_SPRING["D"], CH_SPRING["n"])
    k_ch = SPRING_KCH if SPRING_KCH > 0 else k_geom
    log(f"  channel spring k = {k_ch:.1f} N/m (geometric {k_geom:.0f} N/m, "
        f"override {SPRING_KCH:.1f}) ; {len(levers)} channel-levers")

    # 3) 20 channel springs: channel-lever tab eye <-> shared summing-lever eye.
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

    # 4) counter spring: gooseneck (structural) <-> boss-hook (on summing-lever).
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
    log(f"  counter spring: {'OK' if cres.is_success else 'FAIL ' + str(cres.error)}")
    return ok + (1 if cres.is_success else 0)


# WIRE1 lumped gear ratio summing-lever(Z) <-> magnifying-wheel(Z). [1,1] for
# transmission validation; the real 5x amplification is calibrated in F6 via this
# ratio together with the WIRE2 rim radius. The mag-lever rock stays pinned (its
# skew X-axis cannot be geared) -- its motion is lumped into this gear ratio.
RATIO_SUM_WHEEL = [1.0, 1.0]
# Part-local points on the magnifying-wheel Ø100 rim OD edge (mm); the rim is
# extruded both-directions about the Front plane so the edge z is +/-4 or +/-8 --
# try a few until one selects (validated live in probe_yoke_only.py: z=+4).
RIM_EDGE_CANDIDATES = [[50.0, 0.0, 4.0], [50.0, 0.0, 8.0], [50.0, 0.0, -4.0],
                       [50.0, 0.0, -8.0], [0.0, 50.0, 4.0]]


async def _suppress_pen_travel(adapter):
    """Suppress the pen-rod Y-travel snapshot (the largest-value pen-rod DISTANCE
    = the Top<->Top plane Y position; confirmed Distance12 via probe_pen_mates) so
    the WIRE2 yoke can drag the pen freely in Y."""
    from solidworks_mcp.adapters.base import SuppressMateParameters
    _, model = _sub_model(adapter, "output-1")
    best = (None, -1.0)
    for _f, mate, name, mtype, parts, _v in _iter_mates(adapter, model, read_values=False):
        lone = _lone_real(parts, "output")
        if mtype != DISTANCE or lone is None or _family(lone) != "pen-rod":
            continue
        val = _mate_value(adapter, mate, mtype) or 0.0
        if val > best[1]:
            best = (name, val)
    if best[0] is None:
        raise RuntimeError("pen-rod Y-travel snapshot not found")
    log(f"  suppress pen-rod Y-travel {best[0]}")
    check("suppress pen travel", await adapter.suppress_mate(
        SuppressMateParameters(name=best[0], suppress=True, component="output-1")))


async def _rim_point(adapter, comps=None):
    """RefPoint at radius 50 on the magnifying-wheel rim, on the SHARED wheel part
    doc (inherited by every instance via GetCorresponding; never saved). Selection
    in the part doc requires it be ACTIVE -> ActivateDoc3 round-trip. Returns the
    point feature name (e.g. "Point3")."""
    from solidworks_mcp.adapters.base import CreateReferencePointParameters
    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    wh, _ = _find_one(adapter, "magnifying-wheel-1", comps=comps)
    if wh is None:
        raise RuntimeError("magnifying-wheel-1 not found for rim point")
    part = adapter._attempt(lambda: wh.GetModelDoc2(), default=None)
    if part is None:
        raise RuntimeError("magnifying-wheel part doc unresolved")
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, 0), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    name = None
    for ep in RIM_EDGE_CANDIDATES:
        res = await adapter.create_reference_point(CreateReferencePointParameters(
            mode="along_curve", edge_point=ep, along="percentage", percentage=0.0))
        if res.is_success:
            name = res.data.get("name") if isinstance(res.data, dict) else getattr(
                res.data, "name", None)
            log(f"  rim RefPoint edge_point={ep} -> {name!r}")
            break
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, 0), default=None)
    adapter.currentModel = top
    if not name:
        raise RuntimeError("rim RefPoint creation failed on the wheel")
    return name


async def _add_wire1_gear(adapter):
    """WIRE1 gear summing-lever(Z) <-> magnifying-wheel(Z), parallel axes.

    The gear over-defines intermittently with alignment="closest": a fresh open
    resolves the closest side to "aligned" on some runs and "anti_aligned" on
    others, and only one side is consistent with the suppressed rocks (the other
    over-defines). Within a single run the pose is fixed, so DON'T rely on
    "closest" -- try both explicit alignments; one is always accepted. A failed
    AddMate5 creates no mate, so no cleanup is needed between attempts.
    """
    last = None
    for alignment in ("aligned", "anti_aligned"):
        try:
            w1 = await gear_mate(
                adapter, _entity_ref("summing-lever-1", "Axis1", "AXIS"),
                _entity_ref("magnifying-wheel-1", "Axis1", "AXIS"),
                RATIO_SUM_WHEEL, alignment=alignment, label="WIRE1 summing->wheel")
            if w1.get("name"):
                log(f"  WIRE1 gear: {w1['name']} (alignment={alignment})")
                return w1
        except Exception as exc:  # noqa: BLE001
            last = exc
            log(f"    WIRE1 gear alignment={alignment} rejected: {exc}")
    raise RuntimeError(f"WIRE1 gear failed both alignments: {last}")


async def add_wires_gravity(adapter, with_gravity=False):
    """Stage `full`: the two amplifying wires (motion couplings) + gravity.

      WIRE1  gear summing-lever(Z) <-> magnifying-wheel(Z)  (parallel, lumped 5x)
      WIRE2  scotch-yoke: a RefPoint on the wheel Ø100 rim (radius 50) held
             COINCIDENT to the pen-rod's horizontal Top plane. As the wheel turns,
             the rim point's Y excursion drags the pen-rod in Y (its X excursion
             slides freely along the infinite plane); pen_Y ~= 50*sin(theta_wheel),
             linear in the small operating angles. Basic Motion does NOT enforce a
             rack-pinion mate in-sub (proven), but DOES enforce gears and the
             coincident point-on-plane -- so both wires use enforced primitives.

    Both are authored INSIDE output.SLDASM's doc: the four chain parts share the
    one output-1 flexible sub, so a top-level mate between any two is rejected.
    Run after add_springs (which suppressed the summing-lever rock). NEVER saves.
    """
    from solidworks_mcp.adapters.base import MotionGravityParameters

    comps = _components(adapter)

    # 1) free the driven output DOF the wires control: wheel rock (WIRE1 spins it)
    #    + pen-rod Y travel (WIRE2 yoke drags it). The mag-lever rock stays pinned.
    await _suppress_named(adapter, "output-1", ("magnifying-wheel",), (ANGLE,),
                          "wheel rock (free for WIRE1)")
    await _suppress_pen_travel(adapter)

    # 2) rim datum point on the shared wheel doc (before retargeting currentModel).
    rim_pt = await _rim_point(adapter, comps=comps)

    # 3) both wires authored INSIDE output.SLDASM's own document.
    _, out_doc = _sub_model(adapter, "output-1")
    top = adapter.currentModel
    adapter.currentModel = out_doc
    w1 = None
    try:
        w1 = await _add_wire1_gear(adapter)
        w2 = await coincident_mate(
            adapter, _entity_ref("magnifying-wheel-1", rim_pt, "POINT"),
            _entity_ref("pen-rod-1", "Top Plane", "PLANE"),
            label="WIRE2 yoke rim->pen")
        log(f"  WIRE2 yoke: {w2.get('name')}")
    finally:
        adapter._attempt(lambda: out_doc.ForceRebuild3(False), default=None)
        adapter.currentModel = top

    # 4) gravity (-Y), OPT-IN: on a ~1 m steel mechanism gravity forces dwarf the
    #    weak channel/counter springs (k ~ 0.5-2 kN/m) and can destabilise the
    #    dynamic Basic Motion solve; the harmonic trace is a crank+spring-balance
    #    result, so gravity is noise here. Off by default; pass `grav` to enable.
    grav_ok = None
    if with_gravity:
        g = await adapter.add_gravity(MotionGravityParameters(
            axis="y", reverse=True, study_name=""))
        grav_ok = g.is_success
        log(f"  gravity -Y: {'OK' if g.is_success else 'FAIL ' + str(g.error)}")
    else:
        log("  gravity: SKIPPED (pass `grav` to enable)")
    return {"wire1": w1.get("name") if w1 else None, "wire2": True,
            "gravity": grav_ok}
