r"""Full-machine (top-assembly) build helpers: flexible subassemblies, engaged
SETUP clamps, the physical cross-sub couplings, and the saved operation motion
studies.

This module is on the TOP assembly's build recipe ONLY (imported by
``build_harmonic_analyzer_assembly.py``); iterating on it rebuilds the top,
never the sub fleet. It is ALSO imported off-recipe by ``verify.py`` /
``refresh_assembly.py`` (the operational DOF gate) and ``build_motion_study.py``
(the component-walk helpers) -- those scripts are not on any assembly recipe, so
the sharing costs nothing. It must never import ``verify.py`` or
``_assembly_postbuild.py`` (both deliberately OFF the build closure).

ARCHITECTURE (2026-07, the default-free top): the shipped
``harmonic-analyzer.SLDASM`` is the COMPLETE OPERATING MACHINE, not a display
of seven rigid blocks:

* the six moving subs (everything but frame) are floated, 3-plane grounded at
  identity, and set FLEXIBLE -- their default-``free`` internals (crank spin,
  rocker/rod chains, lever rocks, pen travel, paper crank) are live in the
  saved doc;
* the sub-recorded SETUP poses are clamped ENGAGED as permanent top-level
  mates (``SETUP_<key>``): drive-train's cone_swing / pinion_swing /
  pinion_cam and the 20 channel bar_amplitude stations (the bars are Fourier
  coefficient SETTINGS, clamped while the crank turns). These are NOT park
  drivers -- never deferred, never suppress-cycled, never closure-proven -- so
  they deliberately do NOT wear the ``PARK_`` prefix the park machinery
  discovers (``find_park_drivers`` / ``assert_park_closure``);
* every cross-sub coupling is authored physically: 20 cam ring<->lobe
  point-on-axis mates (``CAM_chNN``), the crank->paper chain tie
  (``CHAIN_crank_paper``), the summing->magnifying lever hand-off
  (``HANDOFF_levers``) and the WIRE-2 rim->pen scotch yoke (``WIRE2_pen``) --
  dragging the crank in the saved model articulates the whole machine down to
  the pen;
* TWO Basic Motion studies are saved in the doc (``author_operation_studies``):
  ``kinematic`` (crank motor only -- the robust demonstration class) and
  ``full`` (motor + the 20 channel springs + counter spring as real force
  elements -- the analogue-sum demonstration, marginal for the fixed-step
  integrator). Their auto-assigned names ride the
  ``.harmonic-analyzer.studies.json`` sidecar.

The amplitude preset stays a CONFIG concern, upstream of this module: the
``machine/amplitude.yaml preset`` drives ``channels.yaml amplitude_mm``
(asserted consistent by ``check:config``), the channel build stations its bars
from that same vector, and the recorded park specs therefore already carry the
preset -- the clamps here simply replay the recorded stations. There is no
study-time re-station any more: a mate edit under a saved motion study risks
the initial-animation-state corruption class (June lesson), so flipping the
preset means a config edit + rebuild (channel + top), keeping truth_model, the
channel geometry and the top clamps on ONE source of truth.
"""

from __future__ import annotations

import json
import math
from typing import Any

import _config
import _telemetry
from _common import OUT_SLDASM, _flag, _read_member, check, log
from _assembly import (
    UNDER_CONSTRAINED,
    _flag_only,
    _mate,
    coincident_mate,
    component_named_ref,
    gear_mate,
    is_locked_build,
    lock_mate,
    named_ref,
    park_spec_path,
)

TOP_ASM = "harmonic-analyzer"
# frame-1 stays fixed; everything else solves flexibly with the parent.
MOVING_SUBS = ("drive-train-1", "channel-1", "summing-1", "magnifier-1",
               "pen-1", "paper-drive-1")

N_CHANNELS = _config.active_count()

# Engaged setup clamps: the sub-recorded deferred park specs that must be HELD
# while the machine runs. A trailing "_" is a prefix match (per-channel keys).
# The operational DOF (crank_angle, rocker/rod swings, lever rocks, pen travel,
# paper crank) are deliberately NOT clamped -- they are what the machine runs on.
_SETUP_PARKS = {
    "drive-train": ("cone_swing", "pinion_swing", "pinion_cam"),
    "channel": ("bar_amplitude_",),
}
SETUP_PREFIX = "SETUP_"

# Saved-study parameters. CONFIG, not env (codex #217): they bake into the
# saved artifact (motor speed + spring rates of the saved studies), so they
# must ride the top's recipe/cache key -- the literal machine("operation", ...)
# reads tokenise machine/operation.yaml into the top's file_dep, and a sweep
# rebuilds only the top. (The runner may still override the DURATION of the
# resolved study at solve time -- that never re-saves the artifact.)
CRANK_RPM = float(_config.machine("operation", "crank_rpm"))
DURATION_S = float(_config.machine("operation", "duration_s"))

# Spring stiffness k = G*d^4 / (8*D^3*n); steel shear modulus. The GEOMETRIC
# steel rates (~2.1 kN/m channel, ~0.5 kN/m counter) are far too stiff for the
# fixed-step Basic Motion integrator (poc_spring_adder: k~2000 N/m ABORTS the
# solve; low-N/m..tens tracks the moving-anchor sum cleanly), so the saved
# study uses a solver-safe band from config. 0/negative => the geometric
# helical rate.
G_STEEL = 79.3e9  # Pa
CH_SPRING = dict(d=1.0, D=5.5, n=28.0, free_mm=32.0)
CT_SPRING = dict(d=1.8, D=10.7, n=165.0, free_mm=315.0)
SPRING_KCH = float(_config.machine("operation", "spring_k_channel"))
SPRING_KCT = float(_config.machine("operation", "spring_k_counter"))

# swMateType_e values the walk helpers classify by.
COINCIDENT, CONCENTRIC, DISTANCE, ANGLE = 0, 1, 5, 6


def _k_helical(d_mm: float, D_mm: float, n: float) -> float:
    """Linear rate (N/m) of a helical compression/extension spring."""
    d, D = d_mm / 1000.0, D_mm / 1000.0
    return G_STEEL * d**4 / (8.0 * D**3 * n)


# ---- component / mate walk helpers (shared with the study + probes) ----------
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


def _comp_model_doc(adapter, comp):
    """A component's model doc. GetModelDoc2 is a METHOD -- the component
    dispatches from :func:`_components` are deliberately UNFLAGGED (#87), so
    an unflagged call raises ('str' object not callable) and _attempt reads
    None; flag the single dispatch at the point of use (cost two live runs)."""
    _flag(comp, "IComponent2")
    return adapter._attempt(lambda: comp.GetModelDoc2(), default=None)


def _sub_model(adapter, sub_name):
    log(f"  resolving {sub_name} model doc ...")
    comp, _ = _find_one(adapter, sub_name, toplevel=True)
    if comp is None:
        raise RuntimeError(f"sub component not found: {sub_name}")
    model = _comp_model_doc(adapter, comp)
    if model is None:
        # After a flex-solve rebuild a component dispatch can refuse
        # GetModelDoc2 (lightweight/stale COM read) even though the sub doc IS
        # open in the session as a reference -- resolve it by document path
        # instead (observed live on drive-train-1 after flexing all 6 subs).
        path = str((OUT_SLDASM / f"{sub_name.rsplit('-', 1)[0]}.SLDASM").resolve())
        model = adapter._attempt(
            lambda: adapter.swApp.GetOpenDocumentByName(path), default=None)
        if model is not None:
            log(f"  {sub_name}: GetModelDoc2 None; resolved by path instead")
    if model is None:
        raise RuntimeError(
            f"model doc unresolved for {sub_name} (GetModelDoc2 None and "
            f"no open document matches its path)")
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


def _family(part_name):
    """"rocker-arm-12" -> "rocker-arm" (strip the trailing instance suffix)."""
    return part_name.rsplit("-", 1)[0]


def _comp_xform(adapter, comp):
    """Component world transform as a 16-float array, or None if unreadable.

    After a heavy solve, Transform2 (or its ArrayData) occasionally returns
    None on a sample -- a transient COM read, not a real error; callers skip
    that sample."""
    t = _read_member(comp, "Transform2")
    data = _read_member(t, "ArrayData") if t is not None else None
    if data is None:
        return None
    return [float(v) for v in data]


def _comp_z_mm(adapter, comp):
    """World Z (mm) of a component -- STRICT: raises on an unreadable transform.

    This feeds :func:`_by_z_rank`, which pairs the 20 cam couplings and the 20
    springs by Z station order at BUILD time -- one silently-zeroed transform
    would mate a rod to the wrong gear while every count check still passes
    (codex #217). A transient None here means the model needs a re-solve, not
    a default."""
    a = _comp_xform(adapter, comp)
    if a is None:
        name = str(_read_member(comp, "Name2"))
        raise RuntimeError(
            f"unreadable Transform2 for {name!r} -- refusing to Z-rank with a "
            "placeholder (would silently mis-pair cam/spring stations); "
            "re-solve and retry")
    return a[11] * 1000.0


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


# ---- build-lock guard ---------------------------------------------------------
def require_free_movers() -> None:
    """The full-machine assembly presupposes default-``free`` movers: the
    couplings drive DOF a ``locked`` sub has pinned (a locked drive-train's
    crank cannot spin under the chain tie; a locked channel's bars cannot take
    the amplitude clamps). A ``locked`` mover is a pinned-export configuration,
    incompatible with the operating machine -- fail loud rather than author a
    contradictory mate web."""
    locked = [stem for stem in ("drive_train", "channel", "summing",
                                "magnifier", "pen", "paper_drive")
              if is_locked_build(_config.machine("build_lock", stem))]
    if locked:
        raise RuntimeError(
            f"harmonic-analyzer requires every moving sub built `free`, but "
            f"{locked} are `locked` (machine/build_lock.yaml) -- the top-level "
            "couplings/clamps drive DOF a locked sub has pinned")


# ---- float + ground + ONE batched flexible toggle -----------------------------
async def flex_moving_subs(adapter) -> None:
    """Float the six movers, ground each at identity by its three standard
    planes, then set all six FLEXIBLE in ONE ``CompConfigProperties5`` call.

    A fixed component cannot be flexible (it silently refuses), hence
    float+ground first -- the three plane coincidences pin the sub's placement
    exactly where ``fix`` did, but leave its INTERNALS solvable with the
    parent. ``CompConfigProperties5`` acts on the SELECTION, so selecting all
    six movers (append) pays the blocking flex re-solve ONCE instead of six
    times (~16 min -> one solve). Per-component ``Solving`` readback keeps the
    silent-refusal failure mode loud."""
    from solidworks_mcp.adapters.base import ComponentRefParameters
    from solidworks_mcp.adapters.solidworks.assembly import (
        _COMP_FULLY_RESOLVED,
        _COMP_SOLVING,
        _get_component,
        _select_component,
    )

    asm = adapter.currentModel
    flexible = _COMP_SOLVING["flexible"]
    with _telemetry.span("top.flex", subs=len(MOVING_SUBS)):
        for sub in MOVING_SUBS:
            check(f"float {sub}",
                  await adapter.float_component(ComponentRefParameters(name=sub)))
            for plane in ("Front Plane", "Top Plane", "Right Plane"):
                await coincident_mate(
                    adapter, named_ref(f"{plane}@{sub}", "PLANE"),
                    named_ref(plane, "PLANE"), label=f"ground {sub} {plane}")
        adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)

        adapter._attempt(lambda: asm.ClearSelection2(True))
        for i, sub in enumerate(MOVING_SUBS):
            if not _select_component(adapter, sub, 0, i > 0):
                raise RuntimeError(f"batch flexible: cannot select {sub}")
        log(f"  set {len(MOVING_SUBS)} subs FLEXIBLE in one batched call -- "
            "blocking solve ...")
        adapter._attempt(lambda: asm.CompConfigProperties5(
            _COMP_FULLY_RESOLVED, flexible, True, False, "", False, False))
        adapter._attempt(lambda: asm.ClearSelection2(True))
        for sub in MOVING_SUBS:
            comp = _get_component(adapter, sub)
            solving = int(adapter._attempt(lambda c=comp: c.Solving, default=-1))
            if solving != flexible:
                raise RuntimeError(
                    f"{sub} did not go flexible (Solving={solving}; a fixed "
                    "subassembly silently refuses -- float + ground first)")
        _telemetry.event("top.flexed", subs=len(MOVING_SUBS))
        adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)


# ---- engaged SETUP clamps (from the sub park sidecars) -------------------------
def _load_park_specs(stem: str) -> list[dict[str, Any]]:
    """Deferred park specs recorded beside ``<stem>.SLDASM`` (``[]`` if none).

    A local copy of the sidecar read: the canonical loader lives in
    ``_assembly_postbuild``, which build-path modules must not import (it is
    deliberately OFF every assembly recipe)."""
    path = park_spec_path(stem)
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("specs", [])


def _key_matches(key, patterns):
    return any(key == p or (p.endswith("_") and key.startswith(p))
               for p in patterns)


def _retarget_entity(e: dict[str, Any], sub: str) -> dict[str, Any]:
    """Map a sub-recorded mate-entity ref into TOP-assembly context.

    The sub sits at IDENTITY, so geometry is unmoved -- only the addressing
    changes: a component path gains the sub-instance prefix, and a one-level
    ``Feat@comp`` name string becomes the depth-2-safe ``component=`` form
    (``GetCorresponding`` resolves nested parts where the hand-built reversed
    name string silently fails). A BARE name (the sub doc's own standard
    plane) stays as-is: at identity the top's same-named plane IS the same
    plane. Point-only refs (world mm) are untouched for the same reason."""
    e = dict(e)
    comp = e.get("component")
    name = e.get("name")
    if comp:
        e["component"] = f"{sub}/{comp}"
    elif name and "@" in name:
        feat, _, owner = name.partition("@")
        e["name"] = feat
        e["component"] = f"{sub}/{owner}"
    return e


def _retarget_spec(spec: dict[str, Any], sub: str) -> dict[str, Any]:
    spec = dict(spec)
    spec["entities"] = [_retarget_entity(e, sub) for e in spec["entities"]]
    if spec.get("verify"):
        inst, pt = spec["verify"][0], spec["verify"][1]
        spec["verify"] = [f"{sub}/{inst}", list(pt)]
    return spec


async def replay_setup_clamps(adapter) -> list[str]:
    """Author the sub-recorded SETUP poses ENGAGED as permanent top-level mates.

    drive-train's three setup swings + channel's 20 bar_amplitude stations,
    retargeted from the sub park sidecars into top context (see
    :func:`_retarget_entity`). The bar stations arrive PRE-SET: the channel
    build stationed its bars from ``channels.yaml amplitude_mm`` (itself
    asserted against the ``machine/amplitude.yaml preset`` by check:config),
    so the recorded specs already carry the configured preset. Renamed
    ``SETUP_<key>`` -- deliberately NOT ``PARK_<key>``: these are ordinary
    operating mates of the machine assembly, and the ``PARK_`` prefix is
    reserved for the park machinery (deferred/cycled/closure-proven drivers).
    Returns the new mate names."""
    from solidworks_mcp.adapters.base import MateEntityRef

    names: list[str] = []
    with _telemetry.span("top.setup_clamps") as gsp:
        for stem, patterns in _SETUP_PARKS.items():
            specs = [s for s in _load_park_specs(stem)
                     if _key_matches(s["key"], patterns)]
            expected = N_CHANNELS if stem == "channel" else len(patterns)
            if len(specs) != expected:
                raise RuntimeError(
                    f"{stem}: {len(specs)} setup park spec(s) matching {patterns} "
                    f"in the sidecar, expected {expected} -- stale artefact or "
                    f"renamed free_dof_key; rebuild {stem}")
            sub = f"{stem}-1"
            log(f"{stem}: clamping {len(specs)} setup pose(s) engaged at top "
                f"level: {[s['key'] for s in specs]}")
            for spec in specs:
                spec = _retarget_spec(spec, sub)
                entities = [MateEntityRef(**e) for e in spec["entities"]]
                verify = None
                if spec.get("verify"):
                    verify = (spec["verify"][0], list(spec["verify"][1]))
                witness = None
                if spec.get("witness"):
                    witness = (list(spec["witness"][0]), list(spec["witness"][1]))
                res = await _mate(
                    adapter, f"clamp {SETUP_PREFIX}{spec['key']}", spec["kind"],
                    entities, verify=verify, witness=witness,
                    flip=bool(spec.get("flip", False)), **spec.get("params", {}))
                names.append(await _rename_mate(
                    adapter, res, f"{SETUP_PREFIX}{spec['key']}"))
        gsp.set_attribute("clamps", len(names))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    return names


# ---- physical cross-sub couplings ---------------------------------------------
async def _rename_mate(adapter, res: dict[str, Any], new: str) -> str:
    from solidworks_mcp.adapters.base import RenameFeatureParameters
    old = res.get("name")
    if not old:
        raise RuntimeError(f"coupling mate has no resolvable name ({res!r})")
    check(f"rename {old!r} -> {new!r}",
          await adapter.rename_feature(RenameFeatureParameters(
              old_name=old, new_name=new)))
    return new


async def add_cam_couplings(adapter, comps) -> list[str]:
    """Per channel: the rod's ``RingCenter`` point ON the cam lobe ``Axis3``
    (``CAM_chNN``). Cross-sub (drive-train<->channel), authored at top level.

    The cam pin is POSITION-ONLY (point-on-axis, 2 constraints): a
    collinear-axes pin would re-fix the rod orientation the J2 rod<->rocker
    revolute already fixes, over-constraining 20 parallel loops. Channel's J2
    rod-AXIAL mates stay LIVE -- Gruebler over the closed loop (gear + rocker
    + rod: 18 DOF; bearing 5 + pivot 5 + J2 revolute+axial 5 + cam 2 = 17)
    leaves exactly 1 DOF (the gear spin), so the loop is exactly constrained,
    not redundant. (The motion study still suppresses the axials transiently
    for Basic Motion solver margin -- an integrator tolerance, not a statics
    problem.)

    PERTURB before mating: at the design pose the ring point lies ON the
    eccentric lobe axis (degenerate zero-distance) and AddMate5 rejects the
    point-on-axis as "over-defines". Spin the gear ~20 deg about its own axis
    first; the closing ForceRebuild3 snaps it back and the mate holds (proven
    decisively, probe_perturb_cam)."""
    from solidworks_mcp.adapters.base import RotateComponentParameters

    with _telemetry.span("top.cam_couplings") as gsp:
        gears = _by_z_rank(adapter, "cylinder-gear", comps=comps)
        rods = _by_z_rank(adapter, "connecting-rod", comps=comps)
        if len(gears) != N_CHANNELS or len(rods) != N_CHANNELS:
            raise RuntimeError(
                f"cam couplings: found {len(gears)} cylinder-gears / "
                f"{len(rods)} connecting-rods, expected {N_CHANNELS} each")
        names: list[str] = []
        for i in range(N_CHANNELS):
            gear_comp, gear_n = gears[i]
            rod_n = rods[i][1]
            a = _comp_xform(adapter, gear_comp)
            await adapter.rotate_component(RotateComponentParameters(
                name=gear_n, angle=20.0, axis_vector=[a[6], a[7], a[8]],
                axis_point=[a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0],
                mode="exact"))
            cam = await coincident_mate(
                adapter, component_named_ref(rod_n, "RingCenter", "POINT"),
                component_named_ref(gear_n, "Axis3", "AXIS"),
                label=f"CAM ch{i:02d} rod ring <-> cam lobe")
            names.append(await _rename_mate(adapter, cam, f"CAM_ch{i:02d}"))
        gsp.set_attribute("cams", len(names))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    return names


async def tie_paper_chain(adapter, comps) -> str:
    """Tie paper-drive's crank-end T12 sprocket 1:1 to the drive-train
    crankshaft it is coaxial with (``CHAIN_crank_paper``).

    In the real machine they are one keyed shaft; the 1:1 gear mate on the
    coaxial Axis1s co-rotates them, so paper-drive's belt/chain feature +
    rack-pinion feed the platen off the crank. The T12 is picked by
    ``ReferencedConfiguration`` (XY probing found nothing near the crank --
    the knob T24 and spare T18 share the part family). Fail LOUD: this is an
    artefact mate now, not a demonstration nicety."""
    crank_n = _find_one(adapter, "crankshaft-1", comps=comps)[1]
    t12_n = None
    cands = []
    for comp, nm in _find_family(adapter, "transgear-removable", comps=comps):
        if not nm.startswith("paper-drive"):
            continue
        cfg = str(_read_member(comp, "ReferencedConfiguration"))
        cands.append((nm, cfg))
        if cfg == "T12":
            t12_n = nm
            break
    if not crank_n or not t12_n:
        raise RuntimeError(
            f"chain tie: components unresolved (crank={crank_n!r}, "
            f"t12={t12_n!r}; candidates {cands})")
    last: Exception | None = None
    for alignment in ("aligned", "anti_aligned"):
        try:
            res = await gear_mate(
                adapter, component_named_ref(crank_n, "Axis1", "AXIS"),
                component_named_ref(t12_n, "Axis1", "AXIS"),
                [1.0, 1.0], alignment=alignment, label="CHAIN crank->paper 1:1")
            if res.get("name"):
                log(f"  chain tie: {t12_n} (alignment={alignment})")
                return await _rename_mate(adapter, res, "CHAIN_crank_paper")
        except Exception as exc:  # noqa: BLE001 -- try the other alignment first
            last = exc
            log(f"    chain tie alignment={alignment} rejected: {exc}")
    raise RuntimeError(f"chain tie failed both alignments: {last}")


async def add_output_couplings(adapter, comps) -> list[str]:
    """The summing->magnifier hand-off + the WIRE-2 scotch yoke, authored as
    permanent top-level mates (the WIRE-1 precedent: magnifier's saved yoke
    mate IS the linearized inextensible-wire constraint).

    * ``HANDOFF_levers``: the magnifying lever knife-rocks ON the summing
      bar's ridge, coaxial with the summing knife line -- coupled 1:1 about
      that shared Z axis. The gear pair uses the OFFSET axes
      (``Axis1@summing-lever``, 5.134 mm off the knife line): a COAXIAL gear
      pair is degenerate (the coupling sense comes from the centre line).
      Falls back to a LOCK mate (rigid carry, physically the same
      idealisation) if the gear is rejected on both alignments.
    * ``WIRE2_pen``: the wheel's ``RimPoint`` held on the pen-rod's Top
      plane -- the wheel's rock drags the pen in Y, the X excursion slides
      free along the infinite plane.
    """
    sum_n = _find_one(adapter, "summing-lever-1", comps=comps)[1]
    mag_n = _find_one(adapter, "magnifying-lever-1", comps=comps)[1]
    wheel_n = _find_one(adapter, "magnifying-wheel-1", comps=comps)[1]
    rod_n = _find_one(adapter, "pen-rod-1", comps=comps)[1]
    missing = [lbl for lbl, n in (("summing-lever-1", sum_n),
                                  ("magnifying-lever-1", mag_n),
                                  ("magnifying-wheel-1", wheel_n),
                                  ("pen-rod-1", rod_n)) if not n]
    if missing:
        raise RuntimeError(f"output couplings: components unresolved: {missing}")

    handoff = None
    last: Exception | None = None
    for alignment in ("aligned", "anti_aligned"):
        try:
            res = await gear_mate(
                adapter, component_named_ref(sum_n, "Axis1", "AXIS"),
                component_named_ref(mag_n, "Axis2", "AXIS"),
                [1.0, 1.0], alignment=alignment,
                label="HANDOFF summing->magnifying lever 1:1")
            if res.get("name"):
                handoff = res
                break
        except Exception as exc:  # noqa: BLE001 -- alignment fallback chain
            last = exc
            log(f"    hand-off gear alignment={alignment} rejected: {exc}")
    if handoff is None:
        _telemetry.warn(f"hand-off gear failed both alignments ({last}); "
                        "falling back to a lock mate")
        handoff = await lock_mate(
            adapter, component_named_ref(sum_n, "Axis3", "AXIS"),
            component_named_ref(mag_n, "Axis2", "AXIS"),
            label="HANDOFF summing->magnifying lever (lock)")
    names = [await _rename_mate(adapter, handoff, "HANDOFF_levers")]

    w2 = await coincident_mate(
        adapter, component_named_ref(wheel_n, "RimPoint", "POINT"),
        component_named_ref(rod_n, "Top Plane", "PLANE"),
        label="WIRE2 yoke rim -> pen")
    names.append(await _rename_mate(adapter, w2, "WIRE2_pen"))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    return names


# ---- saved operation motion studies -------------------------------------------
def studies_sidecar_path() -> Any:
    """Sidecar recording the saved studies' auto-assigned names (+ the baked
    motor/duration), next to the .SLDASM (rides the remote cache)."""
    return OUT_SLDASM / f".{TOP_ASM}.studies.json"


def load_studies_sidecar() -> dict[str, Any]:
    path = studies_sidecar_path()
    if not path.exists():
        raise RuntimeError(
            f"missing {path.name} -- the saved operation studies' names are "
            "unknown; rebuild harmonic-analyzer")
    return json.loads(path.read_text())


async def _add_crank_motor(adapter, comps, study_name: str) -> None:
    from solidworks_mcp.adapters.base import MotionMotorParameters
    cs_name = _find_one(adapter, "crankshaft-1", comps=comps)[1]
    if not cs_name:
        raise RuntimeError("crankshaft component not found for the motor")
    log(f"  crank motor on Axis1@{cs_name} ({CRANK_RPM} RPM, study "
        f"{study_name!r}) ...")
    check(f"add_motor crank ({study_name})", await adapter.add_motor(
        MotionMotorParameters(
            motor_type="rotary",
            entity=component_named_ref(cs_name, "Axis1", "AXIS"),
            speed=CRANK_RPM, study_name=study_name)))


async def _add_springs(adapter, comps, study_name: str) -> None:
    """The 20 channel springs (channel-lever ``SpringEye`` -> the shared
    summing-lever plate ``SpringEye``) + the counter spring (gooseneck ->
    boss-hook), as real force elements of ``study_name``.

    All endpoints are the PERMANENT part reference points the part builds
    author (no runtime ActivateDoc3 round-trips). ``free_length=None`` starts
    each spring at its assembled length with ZERO force, so the motion is
    driven purely by the cam-chain length changes -- no fragile pretension
    calibration. All 20 share one k; the amplitude weighting lives in the bar
    stations, not the springs."""
    from solidworks_mcp.adapters.base import MotionSpringParameters

    sum_name = _find_one(adapter, "summing-lever-1", comps=comps)[1]
    goose_n = _find_one(adapter, "gooseneck-1", comps=comps)[1]
    hook_n = _find_one(adapter, "boss-hook-1", comps=comps)[1]
    levers = _by_z_rank(adapter, "channel-lever", comps=comps)
    missing = [lbl for lbl, n in (("summing-lever-1", sum_name),
                                  ("gooseneck-1", goose_n),
                                  ("boss-hook-1", hook_n)) if not n]
    if missing or len(levers) != N_CHANNELS:
        raise RuntimeError(
            f"springs: components unresolved (missing {missing}, "
            f"{len(levers)}/{N_CHANNELS} channel-levers)")

    k_geom = _k_helical(CH_SPRING["d"], CH_SPRING["D"], CH_SPRING["n"])
    k_ch = SPRING_KCH if SPRING_KCH > 0 else k_geom
    log(f"  channel spring k = {k_ch:.1f} N/m (geometric {k_geom:.0f} N/m, "
        f"override {SPRING_KCH:.1f}); {len(levers)} channel-levers")
    for i, (_c, lever_n) in enumerate(levers):
        res = await adapter.add_motion_spring(MotionSpringParameters(
            spring_type="linear",
            endpoints=[component_named_ref(lever_n, "SpringEye", "POINT"),
                       component_named_ref(sum_name, "SpringEye", "POINT")],
            spring_constant=k_ch, free_length=None, study_name=study_name))
        if not res.is_success:
            raise RuntimeError(f"ch{i:02d} spring failed: {res.error}")
    log(f"  channel springs: {len(levers)}/{len(levers)}")

    k_ct_geom = _k_helical(CT_SPRING["d"], CT_SPRING["D"], CT_SPRING["n"])
    k_ct = SPRING_KCT if SPRING_KCT > 0 else k_ct_geom
    log(f"  counter spring k = {k_ct:.1f} N/m (geometric {k_ct_geom:.0f} N/m, "
        f"override {SPRING_KCT:.1f})")
    cres = await adapter.add_motion_spring(MotionSpringParameters(
        spring_type="linear",
        endpoints=[component_named_ref(goose_n, "SpringEye", "POINT"),
                   component_named_ref(hook_n, "SpringEye", "POINT")],
        spring_constant=k_ct, free_length=None, study_name=study_name))
    if not cres.is_success:
        raise RuntimeError(f"counter spring failed: {cres.error}")
    log("  counter spring: OK")


async def author_operation_studies(adapter, comps) -> dict[str, str]:
    """Author + SAVE the two Basic Motion operation studies in the top doc.

    ``kinematic`` = crank motor only (the robust demonstration class: cams +
    chain + wires under one motor). ``full`` = motor + the 21 spring force
    elements (the analogue-sum demonstration; the coupled web sits at the
    fixed-step integrator's stability edge, so it stays a SEPARATE study --
    the kinematic one must not inherit its marginality). Studies are created
    AFTER every mate exists: motion ELEMENTS belong to a study, but a mate
    authored under an existing study risks the initial-animation-state
    corruption class (June lesson). SolidWorks assigns the study names
    (``create_motion_study`` resolves-by-name only for existing studies), so
    the names ride the ``.harmonic-analyzer.studies.json`` sidecar for the
    study runner to look up."""
    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    from solidworks_mcp.adapters.base import MotionStudyParameters

    names: dict[str, str] = {}
    with _telemetry.span("top.studies") as gsp:
        for stage in ("kinematic", "full"):
            made = check(
                f"create_motion_study ({stage})",
                await adapter.create_motion_study(MotionStudyParameters(
                    name="", study_type="physical_simulation",
                    duration=DURATION_S, activate=True)))
            study = made["name"]
            log(f"  study {stage!r} = {study!r}")
            await _add_crank_motor(adapter, comps, study)
            if stage == "full":
                with _telemetry.span("top.springs", study=study):
                    await _add_springs(adapter, comps, study)
            names[stage] = study
        gsp.set_attribute("studies", ",".join(names.values()))
    path = studies_sidecar_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"studies": names, "rpm": CRANK_RPM, "duration_s": DURATION_S,
         # The truth state the SETUP_* clamps were built against (this same
         # process replayed them), recorded HERE at build time so the study
         # runner labels its samples with the curve that is actually baked
         # into the machine -- reading live config at solve/report time
         # would mislabel the trace if config moved after the build
         # (codex #217).
         "amplitude": truth_state()},
        indent=1))
    _telemetry.success(f"saved operation studies {names} -> {path.name}")
    return names


def truth_state() -> dict:
    """The FULL truth-model input set the built machine embodies, sliced to
    the ACTIVE channels (the only stations physically instantiated --
    ``pen_y`` summed over all 20 rows would compare a debug build against
    harmonics it doesn't have). Persisted in the studies sidecar so
    ``motion_report`` reconstructs the identical curve without touching live
    config (codex #217 round 3)."""
    chans = _config.active_channels()
    return {
        "preset": str(_config.machine("amplitude", "preset")),
        "coefficients_mm": [float(c["amplitude_mm"]) for c in chans],
        "harmonics": [int(c["harmonic_n"]) for c in chans],
        "phases_deg": [float(c["phase_deg"]) for c in chans],
        "magnify": float(_config.machine("output", "magnify_factor")),
    }


# ---- the operational DOF gate --------------------------------------------------
# One part family per live kinematic chain that MUST read under-constrained in
# the saved top: the crank train (crankshaft/cylinder-gear), each channel's
# cam-driven loop (rocker/rod) and its J5-coupled lever, the spring-summed
# output chain (summing-lever + its lock-mated boss-hook), the hand-off-coupled
# magnifier chain (lever/wheel/wire), and the WIRE2-coupled pen carriage.
# amplitude-bar is deliberately ABSENT: the SETUP clamps pin it (see the
# calibration check below).
TOP_REQUIRED_UNDER_STEMS = (
    "crankshaft", "cylinder-gear", "rocker-arm", "connecting-rod",
    "channel-lever", "summing-lever", "boss-hook", "magnifying-lever",
    "magnifying-wheel", "lever-wire", "pen-rod", "pen-marker",
)


def required_t12_instances() -> tuple[str, ...]:
    """The exact paper-drive T12 crank instance(s), in TOP context, from the
    sub's recorded park spec (three transgear-removable siblings share the
    stem, and only the T12 carries the freed crank spin -- codex #189)."""
    return tuple(
        f"paper-drive-1/{s['verify'][0]}"
        for s in _load_park_specs("paper-drive")
        if s.get("verify") and isinstance(s["verify"][0], str)
    )


def assert_top_operational_dof(adapter: Any, *, resolve: bool = True) -> None:
    """The top assembly's DOF gate: the operating machine's kinematic chains
    must be genuinely LIVE in the saved model.

    The six movers are flexible and 3-plane grounded, so their PLACEMENT is
    fully defined -- the freedom lives in the NESTED components. Walk the full
    tree and require, among the non-fixed/non-pattern components that read
    UNDER-constrained: (1) a floor of ``3*N_CHANNELS + 12`` (each channel's
    gear/rocker/rod trio plus the crank + output chains), (2) every family in
    :data:`TOP_REQUIRED_UNDER_STEMS`, (3) the exact paper-drive T12 crank
    instance. This is a NECESSITY gate (nothing froze the machine); the
    functional proof that the couplings DRIVE the chains is the saved motion
    study (build_motion_study.py).

    CALIBRATION: whether a nested component's ``GetConstrainedStatus`` reads
    the PARENT'S flexible solve or the sub-document's own solve is not
    documented. The clamped ``amplitude-bar`` family disambiguates: the top
    SETUP clamps pin it while the sub doc leaves it free, so it reading
    under-constrained here means the statuses are sub-doc-solve and the gate's
    positive signal is weak -- WARN loudly (the motion study remains the
    functional proof) rather than fail a healthy build on an undocumented COM
    semantic."""
    asm = adapter.currentModel
    with _telemetry.span("gate.dof_top_operational") as gsp:
        if resolve:
            adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
        raw = adapter._attempt(lambda: asm.GetComponents(False), default=None) or []
        under: list[str] = []
        for component in raw:
            _flag_only(component, "IsPatternInstance", "GetConstrainedStatus")
            name = str(_read_member(component, "Name2"))
            if bool(_read_member(component, "IsFixed")):
                continue
            if bool(adapter._attempt(
                    lambda c=component: c.IsPatternInstance(), default=False)):
                continue
            status = int(adapter._attempt(
                lambda c=component: c.GetConstrainedStatus(), default=-1))
            if status == UNDER_CONSTRAINED:
                under.append(name)
        floor = 3 * N_CHANNELS + 12
        present = {_part_family(n) for n in under}
        gsp.set_attribute("components", len(raw))
        gsp.set_attribute("under_constrained", len(under))
        gsp.set_attribute("floor", floor)

        if len(under) < floor:
            raise RuntimeError(
                f"top operational DOF: only {len(under)} nested component(s) "
                f"read under-constrained (< floor {floor}) -- the machine's "
                f"kinematic chains are frozen. Under-constrained: {sorted(under)}")
        missing = [s for s in TOP_REQUIRED_UNDER_STEMS if s not in present]
        if missing:
            raise RuntimeError(
                f"top operational DOF: required famil(ies) {missing} read fully "
                f"defined -- that chain is frozen (a coupling or clamp pinned "
                f"it). Under-constrained families: {sorted(present)}")
        t12 = required_t12_instances()
        if not t12:
            # The top requires every mover built `free` (require_free_movers),
            # and a free paper-drive always records its T12 crank spec -- an
            # empty result means the sidecar is missing/unrestored, and
            # skipping would silently drop the only paper-drive-specific
            # live-DOF check (codex #217 round 3).
            raise RuntimeError(
                "top operational DOF: no T12 crank instance recorded in "
                ".paper-drive.park.json -- sidecar missing or empty, so the "
                "paper-crank liveness check cannot run; rebuild paper-drive "
                "(`doit assembly:paper_drive`)")
        if not any(inst in under for inst in t12):
            raise RuntimeError(
                f"top operational DOF: paper-drive T12 crank {t12} reads fully "
                "defined -- the chain-tied paper crank is frozen")
        if "amplitude-bar" in present:
            _telemetry.warn(
                "top DOF gate calibration: the CLAMPED amplitude-bar family "
                "reads under-constrained -- nested GetConstrainedStatus is "
                "likely reporting the sub-document solve, so this gate's "
                "positive signal is weak; trust the motion study for the "
                "functional proof")
        _telemetry.success(
            f"top operational DOF OK: {len(under)} nested component(s) live "
            f"(floor {floor}); all required chains under-constrained")
