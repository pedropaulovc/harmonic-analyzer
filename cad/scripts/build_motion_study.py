r"""The OPERATION runner: solve, sample and export the SAVED Basic Motion
studies that build_harmonic_analyzer_assembly.py ships inside
harmonic-analyzer.SLDASM. It NEVER re-saves any artefact.

ARCHITECTURE (2026-07, the default-free TOP -- this replaces the runtime study
BUILDER, which assembled flexible subs + clamps + couplings + springs on every
run): artifact A now authors the whole operating machine (see
_assembly_top.py) -- six flexible subs, the 23 engaged ``SETUP_*`` clamps, the
20 ``CAM_chNN`` couplings, ``CHAIN_crank_paper``, ``HANDOFF_levers``,
``WIRE2_pen``, and TWO saved Basic Motion studies whose auto-assigned names
ride the ``.harmonic-analyzer.studies.json`` sidecar:

    kinematic  -> crank motor only (the robust demonstration class)
    full       -> motor + the 21 spring force elements (the analogue-sum
                  demonstration; the coupled web sits at the fixed-step
                  integrator's stability edge)

This script only prepares, solves and measures:

  * suppress each channel's J2 rod-AXIAL mate on the STANDALONE channel doc
    (Basic Motion solver margin: the axial + the cam point-on-axis leaves each
    of the 20 loops redundant by exactly 1, and Basic Motion is
    redundancy-intolerant. The ARTIFACT keeps the axials LIVE -- the static
    solve is Gruebler-exact with them; this is an integrator tolerance, not a
    statics problem). In-memory only; the top binds to the dirtied doc;
  * open the top, resolve the requested SAVED study by its sidecar name
    (re-applying the duration), add opt-in gravity (a motion ELEMENT --
    allowed under a saved study, unlike a mate), solve from the assembled
    pose, sample the kinematic / summing / pen signals with fail-loud gates,
    and export the video + samples JSON (``cad/out/reports/motion/``,
    rendered by motion_report.py).

NOTHING here authors or edits a mate on the top doc: a mate edit under a
saved motion study risks the initial-animation-state corruption class (June
lesson). The old ``flex``/``springs`` stages are GONE -- their work is the
artifact's now.

    uv run python cad\scripts\build_motion_study.py [stage] [opts...]

``stage`` (default ``kinematic``): which SAVED study to solve -- ``kinematic``
or ``full``. ``opts``: ``grav`` enables gravity (default off: on a ~1 m
mechanism gravity dwarfs the solver-safe spring rates and destabilises the
solve). The amplitude preset is a CONFIG concern now (machine/amplitude.yaml
-> channels.yaml -> the channel build -> the top clamps); there is no
study-time re-station.
"""

from __future__ import annotations

import json
import math
import os
import sys

from _common import (
    OUT_PNG,
    OUT_SLDASM,
    check,
    log,
    run_build,
)

# The component/mate walk helpers live beside the top-build logic now; the
# re-exports keep this module the stable import surface for the ~25
# diagnostics probes (and build_motion_setup_drives / build_mobility_probe).
from _assembly_top import (  # noqa: F401 -- re-exported for the probes
    ANGLE,
    COINCIDENT,
    CONCENTRIC,
    DISTANCE,
    MOVING_SUBS,
    N_CHANNELS,
    TOP_ASM,
    _by_z_rank,
    _comp_model_doc,
    _comp_xform,
    _comp_z_mm,
    _components,
    _family,
    _find_family,
    _find_one,
    _iter_mates,
    _mate_parts,
    _mate_value,
    _part_family,
    _real_parts,
    _root_title,
    _rot_angle,
    _sub_model,
    _world,
    load_studies_sidecar,
    truth_state,
)
from _assembly import component_named_ref

import _telemetry

# ---- runner constants ---------------------------------------------------------
ASM = TOP_ASM
ROCKER_MIN_DEG = 1.0      # dead-output gate: EVERY rocker swing must exceed
PEN_MIN_MM = 0.5          # dead-output gate: pen-tip travel must exceed
SUM_MIN_DEG = 0.05        # dead-output gate: summing-lever rock must exceed
PLATEN_MIN_MM = 1.0       # dead-output gate: platen feed must exceed (the chain
                          # tie is an artifact mate now -- measured ~19 mm/2 revs)

# Motion samples land here (JSON per stage) for the SW-free plot/report step.
OUT_MOTION = (OUT_PNG.parent / "reports" / "motion")


def _entity_ref(name2, prefix, etype):
    """A depth-2-safe ``MateEntityRef`` for a named feature inside a nested part
    (kept for the probes; see ``_assembly.component_named_ref``)."""
    return component_named_ref(name2, prefix, etype)


# ---- runtime eye points (kept for the diagnostics probes/POCs) ----------------
async def _eye_point(adapter, comp_needle, edge_points, label, comps=None):
    """Create a mateable eye-centre RefPoint on a SHARED part doc (never saved).

    The MACHINE parts carry permanent named points now (``_refpoints.py``:
    RingCenter / SpringEye / RimPoint), so the operation runner never calls
    this -- it survives for the hand-run POC rigs (poc_spring_adder /
    poc_damper_check), whose throwaway parts have no named points.
    arc_center on the eye hole's circular edge -> the ring centre;
    ``edge_points`` is a candidate list tried in order (a union can consume
    part of the circle). Selection in a component's part doc requires it be
    the ACTIVE doc -> ActivateDoc3 round-trip.
    """
    from solidworks_mcp.adapters.base import CreateReferencePointParameters
    from solidworks_mcp.adapters.solidworks.assembly import _byref_i4
    from _common import _read_member
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


# ---- generic named-suppress (kept for the diagnostics probes) ----------------
async def _suppress_named(adapter, sub_name, families, mtypes, label):
    """Suppress every single-real-part mate in SUB whose part family matches.

    The free build defers its park drivers, so the operation runner itself
    needs no classifier walk -- this survives for the hand-run diagnostics
    probes that still poke authored structural mates.
    """
    _, model = _sub_model(adapter, sub_name)
    root = _root_title(sub_name)
    targets = []
    log(f"  {label}: scanning {sub_name} mates ...")
    for _f, _m, name, mtype, parts, _val in _iter_mates(
            adapter, model, read_values=False, progress_every=20):
        if mtype not in mtypes:
            continue
        real = _real_parts(parts, root)
        if len(real) == 1 and _family(real[0]) in families:
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


# ---- Basic Motion margin: de-redundant the cam loops --------------------------
async def _free_rod_axial_standalone(adapter, n_channels):
    """Suppress each channel's J2 rod-axial mate (Front@rod <-> Front@rocker)
    on the STANDALONE channel doc, BEFORE the top opens. ``n_channels`` is the
    BUILT channel count (from the studies sidecar, not live config).

    Per rod, the channel authors J2 as coincident-axes (4 constraints) + this
    axial distance (1); the top's cam point-on-axis adds 2 more -> 7 on 6 DOF
    = each of the 20 loops redundant by exactly 1, and Basic Motion is
    redundancy-intolerant (June: redundant parallel loops froze the solve; the
    exactly-constrained recipe had NO rod axial -- the rod's Z-float is
    benign, the loop forces are planar). Done on the standalone doc because
    the top carries the SAVED studies: suppressing a mate in the open top
    would be a mate edit under a study (the corruption class). The top then
    binds to this dirtied in-memory doc. NOTHING is saved.
    """
    from solidworks_mcp.adapters.base import SuppressMateParameters
    channel_path = str((OUT_SLDASM / "channel.SLDASM").resolve())
    # open_model FLAGS the doc dispatch and sets adapter.currentModel itself --
    # never overwrite it with a raw swApp.ActiveDoc read (an unflagged dispatch
    # silently breaks GetTitle() inside the adapter's mate-entity name
    # qualification; cost one live run to find).
    check("open channel (rod-axial de-redundancy)",
          await adapter.open_model(channel_path))
    model = adapter.currentModel
    targets = []
    for _f, _m, name, mtype, parts, _v in _iter_mates(
            adapter, model, read_values=False, progress_every=40):
        if mtype != DISTANCE:
            continue
        fams = {_family(p) for p in _real_parts(parts, "channel")}
        if fams == {"connecting-rod", "rocker-arm"}:
            targets.append(name)
    log(f"  rod-axial de-redundancy: suppressing {len(targets)} J2 axial mates")
    for name in targets:
        check(f"suppress {name} (rod axial)", await adapter.suppress_mate(
            SuppressMateParameters(name=name, suppress=True)))
    adapter._attempt(lambda: model.ForceRebuild3(False), default=None)
    if len(targets) < n_channels:
        raise RuntimeError(
            f"rod-axial de-redundancy found only {len(targets)} J2 axial "
            f"mates (expected {n_channels}) -- channel mate shape drifted")


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


async def _sample_transforms(adapter, probes, n_steps, duration, study_name=""):
    """Sample (t -> transform) rows for PROBES = [(comp, label), ...].

    Returns {label: [(t, xform_or_None), ...]}. One set_motion_time per step,
    all probes read per frame (cached dispatches DO reflect motion across
    SetTime frames -- proven; the full-tree walk is paid once by the caller).
    """
    from solidworks_mcp.adapters.base import MotionTimeParameters
    rows = {label: [] for _c, label in probes}
    for s in range(n_steps + 1):
        t = duration * s / n_steps
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


async def _sample_kinematic(adapter, comps, duration, study, n_channels):
    """Crank + EVERY rocker + platen over the run -- the kinematic-stage signal.

    Gates: (1) solve-lock on the crank (constant-rate motor must track);
    (2) dead-output on EACH of the ``n_channels`` BUILT rockers (count from
    the studies sidecar, not live config) -- the top authors one CAM_chNN
    coupling per channel, and a single dead cam/rod loop must fail the proof,
    not hide behind a moving neighbour (codex #217 round 3);
    (3) dead-output on the platen -- the chain tie is an artefact mate now,
    so a missing or unfed platen is a real regression.
    """
    probes = []
    rockers = _by_z_rank(adapter, "rocker-arm", comps=comps)
    if len(rockers) < n_channels:
        raise RuntimeError(
            f"only {len(rockers)} rocker-arm component(s) found -- expected "
            f"{n_channels} (one per built channel); the cam bank is incomplete")
    for comp, name in rockers:
        probes.append((comp, f"rocker@{name.split('/')[-1]}"))
    cyl = _by_z_rank(adapter, "cylinder-gear", comps=comps)
    if cyl:
        # Distinguishes "gear train turns but cams decoupled" (cylgear > 0,
        # rockers 0) from "whole train jammed" (cylgear ~ 0 with the crank
        # grinding) in one look.
        probes.append((cyl[0][0], "cylgear"))
    crank, _ = _find_one(adapter, "crankshaft-1", comps=comps)
    if crank is not None:
        probes.append((crank, "crankshaft"))
    platen, _platen_n = _find_one(adapter, "platen-1", comps=comps)
    if platen is None:
        raise RuntimeError(
            "platen-1 not found -- cannot prove the crank->chain->rack paper "
            "feed (CHAIN_crank_paper is an artifact mate; the platen must exist)")
    probes.append((platen, "platen"))
    rows = await _sample_transforms(adapter, probes, 12, duration, study)

    spans = {}
    for label, samples in rows.items():
        if label == "platen":
            # linear feed: track world translation magnitude
            pts = [(t, _world(a, [0, 0, 0])) for t, a in samples if a is not None]
            if pts:
                d = max(math.dist(pts[0][1], p) for _t, p in pts)
                spans[label] = d
            continue
        spans[label] = _span(_rot_series(samples))
    log(f"  kinematic spans: { {k: round(v, 2) for k, v in spans.items()} }")

    if crank is not None:
        assert_motion_progressed(rows["crankshaft"], duration, "crankshaft")
        dead = sorted(k for k, v in spans.items()
                      if k.startswith("rocker") and v < ROCKER_MIN_DEG)
        if dead:
            raise RuntimeError(
                f"DEAD OUTPUT: crank drove the full run but {len(dead)}/"
                f"{len(rockers)} rocker(s) swung < {ROCKER_MIN_DEG} deg: "
                f"{dead} -- those cam-follower loops are decoupled.")
        feed = spans.get("platen", 0.0)
        if feed < PLATEN_MIN_MM:
            raise RuntimeError(
                f"DEAD OUTPUT: platen fed only {feed:.2f} mm "
                f"(< {PLATEN_MIN_MM}) -- the crank->chain->rack paper train is "
                f"decoupled (CHAIN_crank_paper / belt / rack-pinion).")
    return {"spans_deg": {k: v for k, v in spans.items() if k != "platen"},
            "platen_feed_mm": spans.get("platen"),
            "rows": _rows_json(rows)}


async def _sample_summing_chain(adapter, comps, duration, study):
    """channel-lever / summing-lever / magnifying-wheel rotation over the run --
    the spring-summing signal. Gate: the summing lever must actually rock."""
    probes = []
    for needle in ("channel-lever-1", "summing-lever-1", "magnifying-lever-1",
                   "magnifying-wheel-1"):
        comp, name = _find_one(adapter, needle, comps=comps)
        if comp is not None:
            probes.append((comp, needle.rsplit("-1", 1)[0]))
    rows = await _sample_transforms(adapter, probes, 12, duration, study)
    spans = {label: _span(_rot_series(samples)) for label, samples in rows.items()}
    log(f"  summing-chain spans(deg): { {k: round(v, 2) for k, v in spans.items()} }")
    if spans.get("summing-lever", 0.0) < SUM_MIN_DEG:
        raise RuntimeError(
            f"DEAD OUTPUT: summing-lever rocked only "
            f"{spans.get('summing-lever', 0.0):.3f} deg (< {SUM_MIN_DEG}) -- "
            f"the 20-spring force balance never moved it; check the spring "
            f"elements and that the channel levers are oscillating.")
    return {"spans_deg": spans, "rows": _rows_json(rows)}


async def _sample_pen(adapter, comps, duration, study, n_steps=48):
    """Pen-marker tip world-Y over the run + the dead-output gate.

    Returns the (t, y_mm) series for the truth-curve comparison asset."""
    marker, _ = _find_one(adapter, "pen-marker", comps=comps)
    if marker is None:
        raise RuntimeError("pen-marker not found for the pen sample")
    rows = await _sample_transforms(
        adapter, [(marker, "pen-marker")], n_steps, duration, study)
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


async def _reset_to_assembled(adapter, study_name=""):
    """Return the model to its assembled pose before calculate_motion.

    calculate_motion is POSE-DEPENDENT: solving from a previous run's settled
    pose makes the closed-loop cam mechanism lock (proven), whereas solving
    from the assembled pose reliably moves. ``study_name`` targets the named
    saved study explicitly (empty = the active one; the runner passes the
    resolved name so the reset can never land on a different study's timeline
    -- codex #217 round 2).
    """
    from solidworks_mcp.adapters.base import MotionTimeParameters
    await adapter.set_motion_time(MotionTimeParameters(time=0.0, study_name=study_name))
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3(), default=None)
    log("  reset to assembled pose (set_time 0 + rebuild) before solve")


async def _export_video(adapter, stage, study):
    from solidworks_mcp.adapters.base import MotionExportParameters
    # The export grabs the live viewport (screen renderer) -- frame the whole
    # machine from the gallery's 3/4 view first.
    model = adapter.currentModel
    adapter._attempt(lambda: model.ShowNamedView2("*Trimetric", -1), default=None)
    adapter._attempt(lambda: model.ViewZoomtofit2(), default=None)
    vid = (OUT_PNG.parent / f"{ASM}-operation-{stage}.mp4").resolve()
    res = await adapter.export_motion_video(MotionExportParameters(
        file_path=str(vid), study_name=study, frames_per_second=25.0))
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
    if stage not in ("kinematic", "full"):
        raise RuntimeError(f"unknown stage {stage!r}; pick kinematic|full")
    opts = set(sys.argv[2:])

    sidecar = load_studies_sidecar()
    study = sidecar["studies"].get(stage)
    if not study:
        raise RuntimeError(
            f"no saved {stage!r} study recorded in the sidecar "
            f"({sidecar.get('studies')}) -- rebuild harmonic-analyzer")
    rpm = float(sidecar.get("rpm", 0.0))
    duration = float(os.environ.get("MOTION_DURATION_S",
                                    sidecar.get("duration_s", 6.0)))
    # The truth state comes from the BUILD-time studies sidecar -- the inputs
    # the SETUP_* clamps were actually authored against -- not from live
    # config, which can move between the build and this hand-run solve
    # (codex #217 round 2). Older sidecars predate the record: fall back to
    # the live truth state with a loud warning (rebuild the top to bake it).
    amplitude = sidecar.get("amplitude")
    if amplitude is None:
        _telemetry.warn(
            "studies sidecar records no truth state (pre-record artifact) "
            "-- labelling samples with LIVE config; rebuild harmonic-analyzer "
            "to bake it")
        amplitude = truth_state()
    # The BUILT channel count: the coefficient vector is recorded sliced to
    # the stations the build instantiated, so its length is authoritative --
    # a live active_count edit after the build must move neither the prep nor
    # the gates (codex #217 round 4).
    n_channels = len(amplitude["coefficients_mm"])
    log(f"stage = {stage} -> saved study {study!r} (motor {rpm} RPM baked; "
        f"duration {duration}s) channels={n_channels}")

    # A prior run's in-memory state (and any dirty doc) must not leak into
    # this solve; CloseDoc discards dirty docs without the save prompt.
    from _assembly_postbuild import discard_open_documents
    discard_open_documents(adapter)

    # Solver-margin prep FIRST, on the standalone channel doc; the top then
    # binds to the dirtied in-memory doc (see _free_rod_axial_standalone).
    with _telemetry.span("motion.derigidify"):
        await _free_rod_axial_standalone(adapter, n_channels)

    asm_path = str((OUT_SLDASM / f"{ASM}.SLDASM").resolve())
    check("open harmonic-analyzer", await adapter.open_model(asm_path))
    log(f"opened {asm_path}")
    # The top opens with nested components LIGHTWEIGHT (seat default), and a
    # lightweight component's GetModelDoc2 reads None (broke sub-doc + part
    # resolution live). Resolve everything once.
    n = adapter._attempt(
        lambda: adapter.currentModel.ResolveAllLightWeightComponents(False),
        default=None)
    log(f"  ResolveAllLightWeightComponents -> {n}")

    log("  enumerating components (single full-tree walk, reused everywhere) ...")
    comps = _components(adapter)

    # Resolve the SAVED study by name (create_motion_study with a name is
    # resolve-only: re-applies type + duration and activates). No mates are
    # authored past this point -- only motion elements are legal additions.
    check("ensure_motion_addin", await adapter.ensure_motion_addin())
    from solidworks_mcp.adapters.base import (
        MotionGravityParameters, MotionStudyParameters, MotionStudyRefParameters,
    )
    check(f"resolve saved study {study!r}", await adapter.create_motion_study(
        MotionStudyParameters(name=study, study_type="physical_simulation",
                              duration=duration, activate=True)))
    # A gravity run materially changes the solve, so its artefacts are
    # labelled `<stage>-grav` -- it can never overwrite (or be mistaken for)
    # the default no-gravity run's samples/video (codex #217 round 3).
    grav = "grav" in opts
    run_label = f"{stage}-grav" if grav else stage
    if grav:
        # Fail loud: a rejected gravity element would otherwise record a
        # plain no-gravity solve under the `-grav` label (codex #217 round 4).
        check("add gravity -Y", await adapter.add_gravity(
            MotionGravityParameters(axis="y", reverse=True, study_name=study)))
        log("  gravity -Y: OK")

    await _reset_to_assembled(adapter, study)
    log("  Calculate() -- blocking solve of the whole device ...")
    with _telemetry.span("motion.calculate", study=study):
        check("calculate_motion", await adapter.calculate_motion(
            MotionStudyRefParameters(name=study)))

    payload = {"stage": stage, "study": study, "rpm": rpm,
               "duration_s": duration, "channels": n_channels,
               "gravity": grav, "amplitude": amplitude}
    with _telemetry.span("motion.sample"):
        payload["kinematic"] = await _sample_kinematic(
            adapter, comps, duration, study, n_channels)
        if stage == "full":
            payload["summing"] = await _sample_summing_chain(
                adapter, comps, duration, study)
            payload["pen"] = await _sample_pen(adapter, comps, duration, study)

    artefacts = {"samples": _write_samples(run_label, payload)}
    vid = await _export_video(adapter, run_label, study)
    if vid:
        artefacts["video"] = vid
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
