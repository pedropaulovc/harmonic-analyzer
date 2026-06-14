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

from _common import check, component_named_ref, log
from build_motion_study import (
    ANGLE, CH_SPRING, CT_SPRING, _by_z_rank, _components, _find_one, _k_helical,
    _read_member, _suppress_named,
)
from solidworks_mcp.adapters.solidworks.assembly import _byref_i4

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
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, _byref_i4()), default=None)
    adapter.currentModel = adapter._attempt(lambda: adapter.swApp.ActiveDoc, default=part)
    pt = check(f"eye point {label}", await adapter.create_reference_point(
        CreateReferencePointParameters(mode="arc_center", edge_point=edge_point)))
    name = pt.get("name") if isinstance(pt, dict) else getattr(pt, "name", None)
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, _byref_i4()), default=None)
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
    k_ch = _k_helical(CH_SPRING["d"], CH_SPRING["D"], CH_SPRING["n"])
    log(f"  channel spring k = {k_ch:.1f} N/m ; {len(levers)} channel-levers")

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
    k_ct = _k_helical(CT_SPRING["d"], CT_SPRING["D"], CT_SPRING["n"])
    log(f"  counter spring k = {k_ct:.1f} N/m")
    cres = await adapter.add_motion_spring(MotionSpringParameters(
        spring_type="linear",
        endpoints=[component_named_ref(goose_n, goose_pt, "POINT"),
                   component_named_ref(hook_n, hook_pt, "POINT")],
        spring_constant=k_ct, free_length=CT_FREE_LEN, study_name=""))
    log(f"  counter spring: {'OK' if cres.is_success else 'FAIL ' + str(cres.error)}")
    return ok + (1 if cres.is_success else 0)


async def add_wires_gravity(adapter):
    """Stage `full`: the two amplifying wires (motion couplings) + gravity.

    Implemented in F5; for now this is a placeholder so the level>=3 import
    resolves. (Stage `springs` never calls this.)
    """
    raise NotImplementedError("add_wires_gravity: F5 (wires + gravity) pending")
