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
  * 1 counter spring -- gooseneck (structural) <-> stock counter anchor (locked to the
    summing-lever); a restoring bias against the channel pull.
  Catalogue rates are the default; explicit positive SPRING_KCH / SPRING_KCT
  overrides are in N/m. Supplier display coils are not force-law inputs.
  free_length=None preserves ZERO installed preload, omitting stock initial
  tension. Combined with the lumped-Z endpoint below, this is qualitative
  motion only, NOT proof of static balance or tolerance performance.

  The summing lever arrives operationally free in summing.SLDASM; a legacy
  snapshot driver, if present in an older artefact, is suppressed here. The 20 bottom eyes share
  ONE summing-lever datum point at the stock anchor eye height and X offset.
  This retains the existing lumped motion model, not an exact per-station
  spring model: the common Z station changes each spring's 3D length and
  direction. Per-station force fidelity is outside this endpoint cutover.

Each spring endpoint is a RefPoint created at RUNTIME from an authoritative
part-local support datum, on the SHARED part doc (all instances inherit it via
GetCorresponding), NEVER saved. A direct sketch point avoids topology-dependent
edge picks on the stock anchors' swept-wire eyes and the new tapped plate.
"""

from __future__ import annotations

import sys

import _telemetry

from _common import (
    check,
    log,
)
from _assembly import (
    coincident_mate,
    component_named_ref,
)
from _assembly_couplings import (
    gear_mate,
)
from build_motion_study import (
    ANGLE,
    DISTANCE,
    SPRING_KCH,
    SPRING_KCT,
    STOCK_KCH,
    STOCK_KCT,
    _by_z_rank,
    _components,
    _entity_ref,
    _family,
    _find_one,
    _iter_mates,
    _lone_real,
    _read_member,
    _sub_model,
    _suppress_named,
)
import channel_lever_spec as _CL
import gooseneck_geom as _GN
import summing_lever_spec as _SL
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1

# Part-local support centres (mm), not points to select on model edges.
CH_LEVER_EYE = (_CL.LEVER_SPRING_X, 0.0, 0.0)
# Keep the lumped endpoint on the moving summing lever, not on the grounded
# cosmetic spring-hook instances in channels.SLDASM. Their threaded seating
# puts the stock eye centre this far above the plate's top face.
SUM_LEVER_EYE = (
    _SL.HOLE_X + ANCHOR_9489T111.eye_centre_mm[0],
    _SL.PLATE_T / 2.0
    - ANCHOR_9489T111.thread_start_y_mm
    + ANCHOR_9489T111.eye_centre_mm[1],
    _SL.HOLE_Z_FIRST + ANCHOR_9489T111.eye_centre_mm[2],
)
# The stock double-loop spring is centred along the exposed screw shank,
# as in spring_mount_geom.COUNTER_UPPER_EYE_X (in the assembly frame).
GOOSENECK_EYE = (
    _GN.ARM_END_X - _GN.SCREW_SHANK_LEN / 2.0,
    _GN.ARM_Y,
    0.0,
)
COUNTER_ANCHOR_EYE = ANCHOR_9490T1.eye_centre_mm

# Free length: None = assembled length, zero installed preload. This deliberately
# omits stock initial tension; the study remains qualitative motion only.
CH_FREE_LEN = None
CT_FREE_LEN = None


async def _eye_point(adapter, comp_needle, local_point, label, comps=None):
    """Create a fixed support RefPoint on a shared part doc; never save it.

    Use the direct sketch-point promotion recipe from build_magnifying_wheel.
    A 3D sketch uses part-local coordinates without a selected plane or edge.
    """
    import pythoncom
    from win32com.client import VARIANT

    top = adapter.currentModel
    top_title = str(_read_member(top, "GetTitle"))
    comp, _ = _find_one(adapter, comp_needle, comps=comps)
    if comp is None:
        raise RuntimeError(f"{comp_needle} not found for eye point {label}")
    part = _read_member(comp, "GetModelDoc2")
    if part is None:
        raise RuntimeError(f"{comp_needle} part doc unresolved")
    part_title = str(_read_member(part, "GetTitle"))
    sketch = None
    sketch_open = False
    direct_db = None
    with _telemetry.span("feature.motion_eye_point", label=label):
        try:
            adapter.swApp.ActivateDoc3(part_title, False, 2, 0)
            active = _read_member(adapter.swApp, "ActiveDoc")
            if active is None or str(_read_member(active, "GetTitle")) != part_title:
                raise RuntimeError(
                    f"cannot activate {part_title} for eye point {label}"
                )
            adapter.currentModel = part
            part.ClearSelection2(True)
            sketch = part.SketchManager
            sketch.Insert3DSketch(True)
            sketch_open = True
            direct_db = sketch.AddToDB
            sketch.AddToDB = True
            point = sketch.CreatePoint(*(value / 1000.0 for value in local_point))
            if point is None:
                raise RuntimeError(f"eye sketch point {label} creation failed")
            sketch.AddToDB = direct_db
            # Same SAFEARRAY shape and native fix relation as the adapter's
            # add_sketch_constraint; legacy SketchAddConstraints can no-op.
            active_sketch = _read_member(sketch, "ActiveSketch")
            entities = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [point])
            relation = active_sketch.RelationManager.AddRelation(entities, 17)
            if relation is None:
                raise RuntimeError(f"eye sketch point {label} fix relation failed")
            sketch.Insert3DSketch(True)
            sketch_open = False
            if int(_read_member(active_sketch, "GetConstrainedStatus")) != 3:
                raise RuntimeError(f"eye sketch point {label} is not fully constrained")
            # Select2 avoids Select4's late-bound ISelectData type mismatch.
            if not point.Select2(False, 0):
                raise RuntimeError(f"cannot select eye sketch point {label}")
            feature = part.FeatureManager.InsertReferencePoint(7, 0, 0.0, 1)
            if isinstance(feature, tuple):
                feature = next((item for item in feature if item is not None), None)
            if feature is None:
                raise RuntimeError(f"eye RefPoint {label} creation failed")
            name = _read_member(feature, "Name")
            if not name:
                raise RuntimeError(f"eye point {label} returned no name")
            log(f"  eye point {label} on {part_title} = {name!r} at {local_point} mm")
            return str(name)
        finally:
            original_error = sys.exception()
            cleanup_errors = []
            if sketch is not None and direct_db is not None:
                try:
                    sketch.AddToDB = direct_db
                except Exception as exc:
                    cleanup_errors.append(exc)
            if sketch_open:
                try:
                    sketch.Insert3DSketch(True)
                except Exception as exc:
                    cleanup_errors.append(exc)
            try:
                part.ClearSelection2(True)
            except Exception as exc:
                cleanup_errors.append(exc)
            try:
                adapter.swApp.ActivateDoc3(top_title, False, 2, 0)
                active = _read_member(adapter.swApp, "ActiveDoc")
                if active is None or str(_read_member(active, "GetTitle")) != top_title:
                    raise RuntimeError(f"cannot restore assembly {top_title}")
                adapter.currentModel = top
            except Exception as exc:
                cleanup_errors.append(exc)
            if cleanup_errors:
                if original_error is not None:
                    for exc in cleanup_errors:
                        original_error.add_note(f"eye point cleanup failed: {exc!r}")
                else:
                    raise ExceptionGroup(
                        f"eye point {label} cleanup failed", cleanup_errors
                    )


async def add_springs(adapter):
    from solidworks_mcp.adapters.base import MotionSpringParameters

    # 1) free the summing-lever rock (the ANGLE snapshot dim) so springs move it.
    await _suppress_named(
        adapter,
        "summing-1",
        ("summing-lever",),
        (ANGLE,),
        "summing-lever rock (free for springs)",
    )

    # 2) eye datum points on the shared part docs (inherited by all instances).
    comps = _components(adapter)
    lever_pt = await _eye_point(
        adapter, "channel-lever-1", CH_LEVER_EYE, "channel-lever tab", comps=comps
    )
    plate_pt = await _eye_point(
        adapter,
        "summing-lever-1",
        SUM_LEVER_EYE,
        "summing-lever stock anchor datum",
        comps=comps,
    )
    goose_pt = await _eye_point(
        adapter, "gooseneck-1", GOOSENECK_EYE, "gooseneck counter-top", comps=comps
    )
    hook_pt = await _eye_point(
        adapter, "boss-hook-1", COUNTER_ANCHOR_EYE, "9490T1 counter-bottom", comps=comps
    )

    sum_name = _find_one(adapter, "summing-lever-1", comps=comps)[1]
    levers = _by_z_rank(adapter, "channel-lever", comps=comps)
    k_ch = SPRING_KCH if SPRING_KCH > 0 else STOCK_KCH
    log(
        f"  channel spring k = {k_ch:.1f} N/m (catalogue {STOCK_KCH:.3f} N/m, "
        f"override {SPRING_KCH:.1f}) ; {len(levers)} channel-levers"
    )

    # 3) 20 channel springs: channel-lever tab eye <-> shared summing-lever eye.
    ok = 0
    for i, (_c, lever_n) in enumerate(levers):
        try:
            res = await adapter.add_motion_spring(
                MotionSpringParameters(
                    spring_type="linear",
                    endpoints=[
                        component_named_ref(lever_n, lever_pt, "POINT"),
                        component_named_ref(sum_name, plate_pt, "POINT"),
                    ],
                    spring_constant=k_ch,
                    free_length=CH_FREE_LEN,
                    study_name="",
                )
            )
            ok += 1 if res.is_success else 0
            if not res.is_success:
                log(f"    ch{i:02d} spring FAIL: {res.error}")
        except Exception as exc:  # noqa: BLE001
            log(f"    ch{i:02d} spring EXC: {exc}")
    log(f"  channel springs: {ok}/{len(levers)}")

    # 4) counter spring: gooseneck (structural) <-> boss-hook (on summing-lever).
    goose_n = _find_one(adapter, "gooseneck-1", comps=comps)[1]
    hook_n = _find_one(adapter, "boss-hook-1", comps=comps)[1]
    k_ct = SPRING_KCT if SPRING_KCT > 0 else STOCK_KCT
    log(
        f"  counter spring k = {k_ct:.1f} N/m (catalogue {STOCK_KCT:.3f} N/m, "
        f"override {SPRING_KCT:.1f})"
    )
    cres = await adapter.add_motion_spring(
        MotionSpringParameters(
            spring_type="linear",
            endpoints=[
                component_named_ref(goose_n, goose_pt, "POINT"),
                component_named_ref(hook_n, hook_pt, "POINT"),
            ],
            spring_constant=k_ct,
            free_length=CT_FREE_LEN,
            study_name="",
        )
    )
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
RIM_EDGE_CANDIDATES = [
    [50.0, 0.0, 4.0],
    [50.0, 0.0, 8.0],
    [50.0, 0.0, -4.0],
    [50.0, 0.0, -8.0],
    [0.0, 50.0, 4.0],
]


async def _suppress_pen_travel(adapter):
    """Suppress an explicitly authored transient pen-travel drive, if present.

    Default-free ``pen.SLDASM`` has no Y-travel mate.  Its two remaining
    pen-rod distance mates locate depth/across and must never be suppressed.
    """
    from solidworks_mcp.adapters.base import SuppressMateParameters

    _, model = _sub_model(adapter, "pen-1")
    travel_name = None
    for _f, mate, name, mtype, parts, _v in _iter_mates(
        adapter, model, read_values=False
    ):
        lone = _lone_real(parts, "pen")
        if mtype != DISTANCE or lone is None or _family(lone) != "pen-rod":
            continue
        if name == "DRIVE_pen_travel":
            travel_name = name
            break
    if travel_name is None:
        log("  pen-rod travel is already free (default-free artefact)")
        return
    log(f"  suppress pen-rod Y-travel {travel_name}")
    check(
        "suppress pen travel",
        await adapter.suppress_mate(
            SuppressMateParameters(name=travel_name, suppress=True, component="pen-1")
        ),
    )


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
    part = _read_member(wh, "GetModelDoc2")
    if part is None:
        raise RuntimeError("magnifying-wheel part doc unresolved")
    part_title = str(_read_member(part, "GetTitle"))
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(part_title, False, 2, 0), default=None
    )
    adapter.currentModel = adapter._attempt(
        lambda: adapter.swApp.ActiveDoc, default=part
    )
    name = None
    for ep in RIM_EDGE_CANDIDATES:
        res = await adapter.create_reference_point(
            CreateReferencePointParameters(
                mode="along_curve", edge_point=ep, along="percentage", percentage=0.0
            )
        )
        if res.is_success:
            name = (
                res.data.get("name")
                if isinstance(res.data, dict)
                else getattr(res.data, "name", None)
            )
            log(f"  rim RefPoint edge_point={ep} -> {name!r}")
            break
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(top_title, False, 2, 0), default=None
    )
    adapter.currentModel = top
    if not name:
        raise RuntimeError("rim RefPoint creation failed on the wheel")
    return name


async def _add_wire1_gear(adapter, summing_name=None, wheel_name=None):
    """WIRE1 gear summing-lever(Z) <-> magnifying-wheel(Z), parallel axes.

    The gear over-defines intermittently with alignment="closest": a fresh open
    resolves the closest side to "aligned" on some runs and "anti_aligned" on
    others, and only one side is consistent with the suppressed rocks (the other
    over-defines). Within a single run the pose is fixed, so DON'T rely on
    "closest" -- try both explicit alignments; one is always accepted. A failed
    AddMate5 creates no mate, so no cleanup is needed between attempts.
    """
    comps = None
    if summing_name is None or wheel_name is None:
        comps = _components(adapter)
    summing_name = summing_name or _find_one(adapter, "summing-lever-1", comps=comps)[1]
    wheel_name = wheel_name or _find_one(adapter, "magnifying-wheel-1", comps=comps)[1]
    if summing_name is None or wheel_name is None:
        raise RuntimeError("WIRE1 split-sub component path unresolved")
    last = None
    for alignment in ("aligned", "anti_aligned"):
        try:
            w1 = await gear_mate(
                adapter,
                _entity_ref(summing_name, "Axis1", "AXIS"),
                _entity_ref(wheel_name, "Axis1", "AXIS"),
                RATIO_SUM_WHEEL,
                alignment=alignment,
                label="WIRE1 summing->wheel",
            )
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

    The output chain is split across summing, magnifier and pen subassemblies,
    so both couplings are authored at the top level between separate flexible
    subs. Run after add_springs. NEVER saves.
    """
    from solidworks_mcp.adapters.base import MotionGravityParameters

    comps = _components(adapter)

    # 1) free the driven output DOF the wires control: wheel rock (WIRE1 spins it)
    #    + pen-rod Y travel (WIRE2 yoke drags it). The mag-lever rock stays pinned.
    await _suppress_named(
        adapter,
        "magnifier-1",
        ("magnifying-wheel",),
        (ANGLE,),
        "wheel rock (free for WIRE1)",
    )
    await _suppress_pen_travel(adapter)

    # 2) rim datum point on the shared wheel doc (before retargeting currentModel).
    rim_pt = await _rim_point(adapter, comps=comps)

    # 3) both wires authored at top level between the split flexible subs.
    summing_name = _find_one(adapter, "summing-lever-1", comps=comps)[1]
    wheel_name = _find_one(adapter, "magnifying-wheel-1", comps=comps)[1]
    pen_name = _find_one(adapter, "pen-rod-1", comps=comps)[1]
    if summing_name is None or wheel_name is None or pen_name is None:
        raise RuntimeError("split output-chain component path unresolved")
    w1 = await _add_wire1_gear(adapter, summing_name, wheel_name)
    w2 = await coincident_mate(
        adapter,
        _entity_ref(wheel_name, rim_pt, "POINT"),
        _entity_ref(pen_name, "Top Plane", "PLANE"),
        label="WIRE2 yoke rim->pen",
    )
    log(f"  WIRE2 yoke: {w2.get('name')}")

    # 4) gravity (-Y), OPT-IN: on a ~1 m steel mechanism gravity forces dwarf the
    #    weak channel/counter springs (k ~ 0.5-2 kN/m) and can destabilise the
    #    dynamic Basic Motion solve; the harmonic trace is a crank+spring-balance
    #    result, so gravity is noise here. Off by default; pass `grav` to enable.
    grav_ok = None
    if with_gravity:
        g = await adapter.add_gravity(
            MotionGravityParameters(axis="y", reverse=True, study_name="")
        )
        grav_ok = g.is_success
        log(f"  gravity -Y: {'OK' if g.is_success else 'FAIL ' + str(g.error)}")
    else:
        log("  gravity: SKIPPED (pass `grav` to enable)")
    return {"wire1": w1.get("name") if w1 else None, "wire2": True, "gravity": grav_ok}
