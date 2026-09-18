r"""Shared machinery for the McMaster reverse-engineering replicas.

Extracted from ``diag_build_91829A560.py`` (the validated shoulder-screw
replica) so every subsequent part replica -- see ``diag_build_mcmaster.py`` --
reuses the same session helpers, vendor gates and report/render flow instead
of re-proving them per part.

Ground truth comes straight from each part's harvest JSON
(``cad/out/reports/mcmaster-<part>-dump.json``, written by
``diag_dump_part.py``): mass properties, COM and the per-face area multiset.
Nothing vendor-derived is hardcoded here.

Gate policy (relative, with absolute floors -- the fleet spans 65 mm^3 to
9628 mm^3, so the 91829A560 script's absolute tolerances don't transfer):

- volume:   |delta| <= max(0.02 mm^3, 0.02 %)
- surface:  |delta| <= max(0.10 mm^2, 0.05 %)
- COM:      each axis within 0.02 mm of the vendor's
- faces:    vendor count <= FACE_MULTISET_LIMIT -> exact sorted-area multiset
            (per-face |delta| <= max(0.06 mm^2, 0.1 %)); above the limit
            (the knurled parts: 1382/3974 faces) -> exact face COUNT plus the
            sorted TOP-K largest areas (the structural, non-knurl faces).

The McMaster ``.SLDPRT`` files are (c) McMaster-Carr, reference-only: they are
never saved or modified, and replica artefacts go only under the gitignored
``cad/out/reference/``.
"""

from __future__ import annotations

import json
import math
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    CAD_ROOT,
    REFERENCES_DIR,
    _early_bound,
    _read_member,
    check,
    log_profile_geometry,
    record_sketch_closure,
)
from diagnostics.sketch_profile import (  # noqa: E402
    Line,
    Segment,
    closed_loops,
    endpoint_merges,
)

OUT_DIR = CAD_ROOT / "out" / "reference"
REPORTS_DIR = CAD_ROOT / "out" / "reports"
MCMASTER_DIR = REFERENCES_DIR / "mcmaster"

SW_BODY_ADD = 15903  # swBodyOperationType_e.SWBODYADD

FACE_MULTISET_LIMIT = 60  # above this, gate count + top-K instead of multiset
FACE_TOP_K = 30


def _rev_frustum(h: float, r1: float, r2: float) -> float:
    """Volume of a revolved cone frustum (full cone when one radius is 0)."""
    return math.pi / 3.0 * h * (r1 * r1 + r1 * r2 + r2 * r2)


def _spherical_cap_volume(r_rim: float, h: float) -> float:
    """Volume of a spherical cap of rim radius r_rim and height h."""
    return math.pi * h * (3.0 * r_rim * r_rim + h * h) / 6.0


def vendor_truth(part_no: str) -> dict:
    """Load the harvest JSON for one part -- the gate's ground truth."""
    path = REPORTS_DIR / f"mcmaster-{part_no}-dump.json"
    if not path.exists():
        raise FileNotFoundError(
            f"no harvest for {part_no}: run diag_dump_part.py first ({path})"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def vendor_face_areas(truth: dict) -> list[float]:
    areas = []
    for body in truth.get("bodies") or []:
        for face in body.get("faces") or []:
            areas.append(round(float(face["area_mm2"]), 4))
    return sorted(areas)


def mass_properties(adapter) -> dict:
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    ext = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
    mp = ext.CreateMassProperty()
    return {
        "volume_mm3": round(float(_read_member(mp, "Volume")) * 1e9, 4),
        "surface_mm2": round(float(_read_member(mp, "SurfaceArea")) * 1e6, 4),
        "com_mm": [
            round(float(v) * 1000.0, 6)
            for v in (_read_member(mp, "CenterOfMass") or [])
        ],
    }


def bodies(adapter) -> list:
    part = _early_bound(adapter.currentModel, "IPartDoc")
    return list(part.GetBodies2(0, False) or [])


def face_areas(adapter) -> list[float]:
    # Multi-body parts are legitimate (91247A720 ships raised grade marks
    # as separate bodies); the face-count gate catches unmerged splits.
    areas = []
    for b in bodies(adapter):
        body = _early_bound(b, "IBody2")
        for f in body.GetFaces() or []:
            f = _early_bound(f, "IFace2")
            areas.append(round(float(_read_member(f, "GetArea")) * 1e6, 4))
    return sorted(areas)


async def export_views(adapter, stem: str) -> dict[str, str]:
    out = {}
    for view in ("front", "isometric"):
        img = (OUT_DIR / f"{stem}_{view}.png").resolve()
        check(
            f"export_image {stem} {view}",
            await adapter.export_image(
                {
                    "file_path": str(img),
                    "format_type": "png",
                    "width": 1600,
                    "height": 1000,
                    "view_orientation": view,
                }
            ),
        )
        out[view] = str(img)
    return out


# swUserPreferenceToggle_e ids, confirmed by a live swconst.tlb walk on an
# R2026x seat (see ``memory/solidworks-center-rectangle-determinism.md``).
_SW_SKETCH_AUTOMATIC_RELATIONS = 9
_SW_SKETCH_INFER_FROM_MODEL = 95
_SW_SKETCH_INFERENCE = 249

# What a recipe REQUIRES while it draws.  All three off.
#
# SolidWorks inference snapping is PIXEL-based and therefore view-dependent:
# it has silently re-solved a scripted arc by snapping its centre to a
# centreline midpoint and an endpoint to a horizontal alignment, at distances
# that depend on the current zoom; it has flattened a 0.6-degree taper line
# into a cylinder by inferring ``horizontal``; and -- this is what
# ``swSketchInferFromModel`` adds over the two toggles this file used to
# suppress -- it has snapped a scripted circle authored 0.0508 from the shank
# silhouette out to the silhouette's own radius (seen live, recorded at
# ``diag_build_93075A194.py``'s runout circle).  That last one is inference
# FROM MODEL GEOMETRY, which id 249 alone does not govern.
#
# No recipe is allowed to require any of these ON: profiles are closed with
# explicit ``merge`` relations instead (see :func:`draw_closed_profile`).
SKETCH_DRAWING_STATE: dict[str, tuple[int, bool]] = {
    "swSketchAutomaticRelations": (_SW_SKETCH_AUTOMATIC_RELATIONS, False),
    "swSketchInferFromModel": (_SW_SKETCH_INFER_FROM_MODEL, False),
    "swSketchInference": (_SW_SKETCH_INFERENCE, False),
}

# What a seat must look like BETWEEN leaves.
#
# This is deliberately NOT :data:`SKETCH_DRAWING_STATE`, and it is deliberately
# the opposite of the state a crashed suppression block leaks.  These are
# APPLICATION-level preferences, so they outlive the document, the recipe and
# the leaf; a leaf that dies mid-suppression (SolidWorks crash, COM
# disconnect, a watchdog ``os._exit``, a killed process) leaves them FALSE for
# the rest of the seat's life.  If the between-leaves baseline were also
# FALSE, a poisoned seat would be indistinguishable from a healthy one and the
# pool's leaf-admission audit could never detect or repair it.  Restoring TRUE
# on the way out keeps "FALSE between leaves" a reliable signal of an
# unwound-crash, and costs recipe correctness nothing because every recipe
# asserts what it needs on the way in.
#
# MUST match ``REQUIRED_TOGGLES`` in the pool repo's ``agent/seat_settings.py``,
# which is the source of truth for the fleet; the two repos cannot import each
# other, so this constant is the harmonic-side copy.
SEAT_SKETCH_BASELINE: dict[str, tuple[int, bool]] = {
    "swSketchAutomaticRelations": (_SW_SKETCH_AUTOMATIC_RELATIONS, True),
    "swSketchInferFromModel": (_SW_SKETCH_INFER_FROM_MODEL, True),
    "swSketchInference": (_SW_SKETCH_INFERENCE, True),
}

# The snap family, RECORDED and never written.
#
# ids read off this install's ``swconst.tlb`` (SOLIDWORKS 3DEXPERIENCE R2026x,
# ``swUserPreferenceToggle_e``), the same walk that confirms 9/95/249 above.
#
# These are not asserted, for two reasons.  They are ON by default, so "on" is
# not drift; and :data:`SKETCH_DRAWING_STATE` turns off ``swSketchInference``,
# which SOLIDWORKS documents as "Enable snapping" -- the master switch for the
# whole family -- so a recipe that draws under the guard is already immune to
# every one of them.  Authoring straight to the sketch database
# (:func:`draw_closed_profile`) has no snap stage at all.
#
# They are recorded because the failing 2026-09-17 leaf's log contains NO
# record of any of them, and two govern the specific competitor that most
# plausibly broke the logo ring: ``swSketchSnapsCenterPoints`` (the inner
# triangle's vertices sit exactly ON the outer corner arcs' centres, so every
# outer arc endpoint has a snap competitor at exactly 0.400 mm) and
# ``swSketchSnapsNearest``, documented as "your pointer does not need to be in
# the immediate vicinity of another sketch entity to show inference or snap to
# that point" -- i.e. an effectively unbounded screen-space snap radius.  One
# line per leaf costs nothing and makes the next failure diagnosable.
SKETCH_SNAP_AUDIT: dict[str, int] = {
    "swSketchSnapsPoints": 266,
    "swSketchSnapsCenterPoints": 267,
    "swSketchSnapsMidPoints": 268,
    "swSketchSnapsQuadrantPoints": 269,
    "swSketchSnapsIntersections": 270,
    "swSketchSnapsNearest": 271,
    "swSketchSnapsTangent": 272,
    "swSketchSnapsPerpendicular": 273,
    "swSketchSnapsParallel": 274,
    "swSketchSnapsHVLines": 275,
    "swSketchSnapsHVPoints": 276,
    "swSketchSnapsLength": 277,
    "swSketchSnapsGrid": 278,
    "swSketchSnapsAngle": 280,
}


def audit_sketch_snaps(adapter, label: str) -> dict[str, bool | None]:
    """Record the seat's snap family.  Reads only -- never writes, never raises.

    ``None`` for a member this build does not expose.  The return is the
    evidence the 2026-09-17 leaf did not have.
    """
    app = adapter.swApp
    state: dict[str, bool | None] = {}
    for name, toggle in SKETCH_SNAP_AUDIT.items():
        raw = adapter._attempt(
            lambda toggle=toggle: app.GetUserPreferenceToggle(toggle), default=None
        )
        state[name] = None if raw is None else bool(raw)
    _telemetry.info(
        f"{label}: sketch snaps "
        + ", ".join(f"{n[len('swSketchSnaps'):]}={v}" for n, v in state.items())
    )
    return state


def apply_sketch_preferences(
    adapter, state: dict[str, tuple[int, bool]]
) -> list[str]:
    """Force the sketch preferences in ``state``; report the names changed.

    Idempotent, and it never reads a value in order to put it back later --
    save-and-restore-observed is what made the poisoning permanent, because the
    first run on a poisoned seat records the poisoned value as "the original"
    and faithfully writes it back forever.  Every write target here is a
    declared constant, so nothing can latch.

    A refused write is DETECTED BY READ-BACK, never by the call's return
    value.  ``ISldWorks.SetUserPreferenceToggle`` is declared ``VT_VOID``
    (dispid 45, retval ``(24, 0)`` in this install's makepy module), so
    pywin32 hands back ``None`` on SUCCESS and ``if not app.Set...()`` would
    reject every write that worked.  The ``VT_BOOL`` form of this method
    belongs to other interfaces -- ``IModelDoc``/``IModelDoc2`` (dispid 65844)
    and ``IModelDocExtension`` (dispid 159) -- and ``adapter.swApp`` is none of
    them.  This is the repo's standing COM rule (truth-test only a real
    ``VARIANT_BOOL``; verify a void mutator by authoritative read-back) and the
    same shape that once produced a false dimension-prefix failure from
    ``IDisplayDimension.SetText``.  ``_common._write_preferences`` verifies the
    same API the same way, for the same reason.

    Checking at all is what keeps two silent lies out: a seat that declines the
    write leaves :func:`no_sketch_inference` drawing with inference still live,
    and leaves :func:`assert_seat_sketch_baseline` announcing a repair that
    never happened to the pool's leaf-admission audit.  A refusal RAISES here,
    unlike ``_write_preferences`` (which reports), because these three are
    application-level system options a recipe declares it needs, not the
    per-document family that is write-ignored by design; and raising is what
    routes a refused SUPPRESSION into ``no_sketch_inference``'s failed-ENTRY
    path, which puts the declared baseline back before propagating.
    """
    app = adapter.swApp
    changed: list[str] = []
    for name, (toggle, required) in state.items():
        if bool(app.GetUserPreferenceToggle(toggle)) != required:
            changed.append(name)
        app.SetUserPreferenceToggle(toggle, required)
        settled = bool(app.GetUserPreferenceToggle(toggle))
        if settled != required:
            raise RuntimeError(
                f"the seat refused to set {name} (toggle {toggle}) to "
                f"{required}: it still reads back {settled} after the write"
            )
    return changed


def assert_seat_sketch_baseline(adapter, label: str) -> list[str]:
    """Put the seat at :data:`SEAT_SKETCH_BASELINE` before a recipe runs.

    Called at the start of every recipe, in both the replica entry point and
    the production stock-fastener path, so a recipe never inherits ambient
    application state and a seat poisoned by an earlier crashed leaf is
    repaired by the next one.  Drift is warned about by name: it is evidence a
    previous leaf on this seat did not unwind.

    The snap family is RECORDED at the same time (:func:`audit_sketch_snaps`),
    because the leaf that failed on 2026-09-17 logged nothing about any seat
    preference and so could only be diagnosed by argument.
    """
    drifted = apply_sketch_preferences(adapter, SEAT_SKETCH_BASELINE)
    if drifted:
        _telemetry.warn(
            f"{label}: seat sketch preferences were off-baseline and have been "
            f"reset: {', '.join(drifted)} (a previous leaf on this seat did not "
            "unwind its suppression block)"
        )
    audit_sketch_snaps(adapter, label)
    return drifted


@contextmanager
def no_sketch_inference(adapter):
    """Force :data:`SKETCH_DRAWING_STATE` for a block of raw sketch drawing.

    On exit the seat goes to :data:`SEAT_SKETCH_BASELINE` -- a declared
    constant, never the observed previous value -- so the block cannot latch a
    poisoned state and cannot leave the seat looking crash-damaged to the
    pool's leaf-admission audit.

    REENTRANT, by depth count on the adapter.  Restoring an application-level
    preference on the way out of an inner block is wrong in both possible
    designs: restoring the observed previous value hands the outer block a
    value an inner block chose, and restoring a declared baseline switches
    inference back ON while the outer block is still drawing.  Only the
    outermost exit restores.  No nesting exists in the fleet today (checked
    across all 15 files that use this contextmanager, lexically and through
    calls), so this is a guard against the next caller, not a fix for a live
    bug -- but it is cheap and the failure it prevents is silent.

    Correctness does not depend on this contextmanager: every recipe asserts
    the seat baseline at its start, and profiles are closed by explicit
    relations rather than by inference.  It is scoping -- it makes a recipe
    self-describing at the point it draws, and it narrows the window in which
    a crash can leak the suppressed state at all.

    The counter is raised only AFTER the suppression write succeeds.  Raising
    it first would pin it forever if ``apply_sketch_preferences`` threw --
    ``SetUserPreferenceToggle`` is a COM call on a seat that may be dying, and
    a seat that silently declines the write fails its read-back, which
    ``apply_sketch_preferences`` turns into a raise -- because the ``finally``
    that lowers it would never have been entered.
    Every later block on that adapter would then see a nonzero depth and
    quietly become a no-op: suppression never applied, baseline never
    restored, for the life of the process.  That is the silent-disable this
    contextmanager exists to prevent, so it must not be reachable through its
    own error path.

    A half-applied suppression is itself a poisoned seat, so a failed ENTRY
    puts the declared baseline back before the exception propagates.
    """
    depth = getattr(adapter, "_sketch_drawing_depth", 0)
    if depth == 0:
        try:
            apply_sketch_preferences(adapter, SKETCH_DRAWING_STATE)
        except Exception:
            apply_sketch_preferences(adapter, SEAT_SKETCH_BASELINE)
            raise
    adapter._sketch_drawing_depth = depth + 1
    try:
        yield
    finally:
        adapter._sketch_drawing_depth = depth
        if depth == 0:
            apply_sketch_preferences(adapter, SEAT_SKETCH_BASELINE)


def assert_profile_closed(
    adapter, label: str, *, loops: int, feature: str
) -> dict:
    """Decide, from ONE closure read, whether the profile really closed.

    Call immediately after ``exit_sketch``, and pass the ``feature`` name the
    sketch was just given by ``name_last_feature``.  The read itself belongs to
    ``_common.record_sketch_closure``, which logs one uniform line, emits a
    ``sketch.closure`` span event and returns the verdict -- so the seat is
    interrogated ONCE and both the forensics record and this decision come from
    the same numbers.  This function only decides the raise.

    ``feature`` is REQUIRED rather than defaulted because of how that read
    resolves a sketch when it is not told which one: caller dispatch, then a
    named feature, then the LAST ``ProfileFeature``, then
    ``GetActiveSketch2``.  After ``exit_sketch`` there is no active sketch, so
    the last-profile-feature branch answers -- correct for a recipe that
    authored one sketch, silently WRONG for a recipe that authored two before
    checking.  A verdict on the wrong sketch is worse than no verdict, and the
    caller always knows the name it just assigned.

    The decision turns on the verdict's TRI-STATE ``closure``:

    * ``"closed"`` -- contours exist.  Accepted.
    * ``"open"`` -- the seat reported zero contours.  That is a MEASUREMENT of
      the exact failure mode this module exists to prevent, so it raises.
    * ``"unknown"`` -- the read failed.  The ABSENCE of a measurement, not a
      measurement of absence, so it must NOT raise: an RPC hiccup becoming a
      geometry failure would be a guard that fails closed on healthy geometry,
      which is worse than no guard.

    A contour count that merely disagrees with ``loops`` also does not raise.
    ``record_sketch_closure`` warns about it, and the count cannot be trusted
    to fail a build while it is unmeasured whether a revolve centreline in the
    same sketch registers as a contour (99607A213 draws exactly that).

    The offline gates have already run by the time this is called:
    :func:`endpoint_merges` refuses any vertex not shared by exactly two
    segment ends, and :func:`minor_arc` refuses an endpoint that has arrived
    at its arc's centre -- which is the realised shape of an inference snap,
    since an outer arc's nearest wrong target is its own centre.  Those bound
    the authored INTENT.  This read-back is what bounds the seat's OUTCOME,
    and it is a gate in its own right, because nothing between the two is
    asserted any more: :func:`draw_closed_profile` authors exact-coordinate
    endpoints into the sketch database and the database welds them at
    creation, so there is no per-pair return value to check.

    Returns the verdict dict, so the caller can pass its counts into
    :func:`capture_com_failure` as context instead of re-reading the sketch.

    ``coincident_point_pairs`` is what turns that weld from an assumption
    into a measurement, and it is the direct fingerprint of the failure: a
    closed N-segment chain whose endpoints welded keeps N points at N
    distinct places, while the same chain unwelded keeps 2N points sitting in
    N coincident pairs.  ``_point_census`` fills it in whenever the seat
    returned point coordinates it could read -- it is gated on ``places``
    being non-empty, so an unreadable census degrades it to absent, which is
    honest: the number was not measured, and an absent number must not raise
    for the same reason ``"unknown"`` closure does not.  That is the opposite
    of ``unmerged_points``, which ``_sketch_state`` derives only when it is
    given ``expected_points`` and which this path therefore could NEVER
    populate -- a permanently absent number in the one message that has to be
    readable off a dead leaf's log.  ``expected_points`` is not plumbed
    through to supply it, because it would be wrong here: it is compared
    against the sketch's TOTAL point count, and 99607A213 draws a revolve
    centreline in this same sketch, so the authored vertex count would
    understate the total by that centreline's two points and report a healthy
    profile as having two unwelded endpoints.
    """
    verdict = record_sketch_closure(
        adapter, label, feature, expect_contours=loops
    )
    unwelded = verdict.get("coincident_point_pairs")
    if verdict.get("closure") == "open":
        raise RuntimeError(
            f"{label}: profile did not close -- the seat reports "
            f"{verdict.get('contour_count')} contours over "
            f"{verdict.get('segment_count')} segments "
            f"({verdict.get('point_count')} sketch points over "
            f"{verdict.get('distinct_point_positions')} distinct places, "
            f"coincident_point_pairs={unwelded})."
            "  The coordinates closed offline, so this is a geometry defect "
            "in the profile, not a seat setting."
        )
    if unwelded:
        raise RuntimeError(
            f"{label}: {unwelded} endpoint pair(s) did not weld -- the seat "
            f"kept {verdict.get('point_count')} sketch points over "
            f"{verdict.get('distinct_point_positions')} distinct places. "
            "Exact-coordinate endpoints authored straight into the sketch "
            "database are coalesced there at creation; two points left "
            "sitting at one place mean that did not happen, so the loop is "
            "held together by coordinates alone and any edit will open it."
        )
    return verdict



async def draw_closed_profile(
    adapter, segments: tuple[Segment, ...], *, label: str, loops: int
) -> list[str]:
    """Author ``segments`` as EXPLICITLY closed loops, whatever the seat thinks.

    Inference cannot participate, by two independent mechanisms.  The segments
    go straight to the sketch database (``AddToDB = True``), which bypasses the
    inference stage entirely -- that is the same switch
    ``diagnostics/exp_inference_zoom.py`` flips to MEASURE inference, so it is
    the one control this repo has already characterised.  And the seat's
    sketch-inference / automatic-relations user preferences are forced off for
    the duration (:func:`no_sketch_inference`), so a future change of drawing
    path cannot quietly re-admit it.

    That matters because inference snapping is SCREEN-space: its tolerance is
    pixels, and nothing on the authoring path fits, orients or even reads the
    view (the only ``ViewZoomtofit2``/``ShowNamedView2`` calls in the adapter
    are inside ``export_image``, i.e. after the geometry exists).  A profile
    authored through inference therefore depends on the seat's window size and
    the template's zoom -- unasserted, unrecorded, and different per worker.
    Writing direct to the database has no pixel term at all, which is why this
    path produces identical geometry at any view scale.

    Closure then comes from the database, not from a relation.  The segments
    are authored so that adjacent ends carry BIT-IDENTICAL coordinates, and
    an exact-coordinate endpoint written straight to the sketch DB is
    coalesced there at creation: the loop closes with no relation at all.
    That is not an assumption, it is the behaviour ``_common.add_line_chain``
    has always relied on -- it authors ZERO closure relations and its loops
    close, on every worker, for every rectilinear part in the fleet.

    So this function does NOT ask for a ``merge`` relation, and asking would
    be worse than redundant.  ``swConstraintType_MERGEPOINTS`` merges two
    DISTINCT points (``probe_point_anchoring`` case 7a proves it live, on two
    points 5 mm apart); applied to a pair the database has already welded
    into one point it has nothing to merge, and
    ``ISketchRelationManager.AddRelation`` answers ``None`` without raising.
    The adapter cannot tell that apart from a refusal, so it reports
    "SolidWorks rejected 'merge' relation" -- which is exactly what failed
    both profiles on 2026-09-18, on three different workers, always on the
    FIRST pair, because every pair is in that state.

    :func:`endpoint_merges` is still what pairs the endpoints, on exact float
    equality, and it still refuses any vertex not shared by exactly two
    segment ends.  It now states the coincidences the database is REQUIRED to
    weld rather than a list of relations to issue, and
    :func:`assert_profile_closed` measures that it did: an unwelded pair
    survives the sketch as two points at one place and raises there.

    ``loops`` is the number of closed loops the profile must form -- 2 for a
    ring (outer boundary plus the hole), 1 for a plain region.  It is ASSERTED
    offline, against the coordinates, before any COM call: that assertion plus
    the measured weld ARE the closure guarantee, and together with
    :func:`minor_arc`'s refusal of a zero-radius arc they are what catches a
    corner that an inference snap would have collapsed.

    The authored INTENT is recorded before drawing
    (``_common.log_profile_geometry``); the seat's OUTCOME is read once after
    ``exit_sketch`` by :func:`assert_profile_closed`, which the CALLER invokes
    because the read resolves the last profile feature's sketch and so needs
    the sketch closed.  The pair is what makes a success comparable with a
    failure -- the leaf that failed on 2026-09-17 recorded neither.

    Returns the created entity IDs, in ``segments`` order.
    """
    merges = endpoint_merges(segments)
    found = len(closed_loops(segments))
    if found != loops:
        raise ValueError(
            f"{label}: profile forms {found} closed loop(s), expected {loops}"
        )
    # The author's INTENT, in pure Python, before a single COM call: authored
    # points, distinct places, expected merges.  Set against the seat's
    # outcome in assert_profile_closed, this is what turns "it failed" into
    # "it failed HERE, and here is what it should have been".
    log_profile_geometry(
        label,
        [end for segment in segments for end in (segment.start, segment.end)],
    )
    ids: list[str] = []
    with no_sketch_inference(adapter):
        sketch_mgr = adapter.currentSketchManager
        prev_add_to_db = bool(sketch_mgr.AddToDB)
        sketch_mgr.AddToDB = True
        try:
            for index, segment in enumerate(segments):
                if isinstance(segment, Line):
                    result = await adapter.add_line(
                        segment.start[0], segment.start[1],
                        segment.end[0], segment.end[1],
                    )
                else:
                    result = await adapter.add_arc(
                        segment.center[0], segment.center[1],
                        segment.start[0], segment.start[1],
                        segment.end[0], segment.end[1],
                    )
                kind = "line" if isinstance(segment, Line) else "arc"
                ids.append(check(f"{label}: add_{kind} {index}", result))
        finally:
            sketch_mgr.AddToDB = prev_add_to_db
    # No relation loop: see the docstring.  The endpoints are already ONE
    # point each by the time the AddToDB block exits, so there is nothing
    # left to relate and MERGEPOINTS would be refused for precisely that
    # reason.  assert_profile_closed measures the weld instead.
    _telemetry.info(
        f"{label}: {len(segments)} segments, {len(merges)} endpoint "
        f"coincidence(s) for the sketch DB to weld, {loops} loops authored"
    )
    return ids


def offset_plane(adapter, name: str, offset_mm: float, base: str = "Top Plane"):
    """Reference plane parallel to ``base`` at (signed) offset_mm."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        base, "PLANE", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select {base}")
    flags = 8 | (256 if offset_mm < 0 else 0)  # Distance | OptionFlip
    plane = model.FeatureManager.InsertRefPlane(
        flags, abs(offset_mm) / 1000.0, 0, 0, 0, 0
    )
    if plane is None:
        raise RuntimeError(f"InsertRefPlane failed for {name}")
    plane.Name = name
    model.ClearSelection2(True)
    return name


def split_at_plane(adapter, plane_name: str, feature_name: str) -> list[dict]:
    """Vendor-style Split2: split the body at ``plane_name``, keep every
    piece, and return [{name, box_mm}] per resulting body."""
    import pythoncom
    from win32com.client import VARIANT
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from _common import name_last_feature

    model = adapter.currentModel
    fm = model.FeatureManager
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        plane_name, "PLANE", 0, 0, 0, True, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select {plane_name} for the split")
    pre = fm.PreSplitBody2
    if callable(pre):
        pre = pre()
    if not pre or len(pre) < 2:
        raise RuntimeError(f"PreSplitBody2 returned {pre!r}, expected >=2")
    split = fm.PostSplitBody2(
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(pre)),
        False,  # keep every body in the part
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [None] * len(pre)),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [""] * len(pre)),
        "",
    )
    if split is None:
        raise RuntimeError("PostSplitBody2 failed")
    model.ClearSelection2(True)
    name_last_feature(adapter, feature_name)
    out = []
    for b in bodies(adapter):
        b2 = _early_bound(b, "IBody2")
        box = [float(x) * 1000.0 for x in (b2.GetBodyBox() or [])]
        out.append({"name": str(_read_member(b2, "Name")), "box_mm": box})
    return out


def thread_sweep_cut(
    adapter,
    profile: str,
    path: str,
    body_name: str | None,
    feature_name: str,
    tangency: tuple[int, int] = (1, 1),
):
    """The decoded vendor Cut-Sweep: obsolete ``InsertCutSwept5`` with the
    profile at mark 1, the helix at mark 4 and (optionally) an explicit
    SOLIDBODY scope -- the modern CreateDefinition path fails body-scoped
    cuts (see the 91829A560 postmortem)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from solidworks_mcp.adapters.solidworks.features import (
        _flag_feature_methods,
        _select_named_feature,
    )
    from _common import name_last_feature

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, profile, 1, False):
        raise RuntimeError(f"cannot select sweep profile {profile!r} (mark 1)")
    if not _select_named_feature(adapter, path, 4, True):
        raise RuntimeError(f"cannot select sweep path {path!r} (mark 4)")
    scoped = body_name is not None
    if scoped and not model.Extension.SelectByID2(
        body_name, "SOLIDBODY", 0, 0, 0, True, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select body {body_name!r} for scope")
    feature_manager = _flag_feature_methods(
        model.FeatureManager, "IFeatureManager", "InsertCutSwept5"
    )
    with _telemetry.span("feature.thread_sweep_cut", label=feature_name):
        swept = feature_manager.InsertCutSwept5(
            False,  # Propagate
            True,  # Alignment (vendor AlignWithEndFaces=True)
            0,  # TwistCtrlOption: swTwistControlFollowPath
            False,  # KeepTangency
            False,  # BAdvancedSmoothing
            *tangency,  # Start/EndMatchingType (per-part vendor value)
            False,
            0.0,
            0.0,
            0,  # thin body
            10,  # PathAlign: swMinimumTwist (vendor PathAlignmentType)
            scoped,  # UseFeatScope
            not scoped,  # UseAutoSelect
            0.0,  # TwistAngle
            True,  # BMergeSmoothFaces
            False,
            False,
            False,  # assembly scope
            False,
            0.0,  # CircularProfile
            -1,  # Direction (vendor)
        )
    model.ClearSelection2(True)
    if swept is None:
        raise RuntimeError(f"InsertCutSwept5 returned None for {feature_name}")
    name_last_feature(adapter, feature_name)
    return swept


def thread_sweep_cut_modern(adapter, profile: str, path: str, feature_name: str):
    """Modern sweep-cut authoring: CreateDefinition(swFmSweepCut) with the
    vendor's exact read-back option values, then CreateFeature.  The
    obsolete InsertCutSwept5 under-removes ~0.4% of the groove volume vs
    the vendor's feature (measured on 91829A560 AND 94025A150); this path
    reproduces the vendor's authoring route.  (It failed on 91829A560 only
    for the BODY-SCOPED case -- single-body parts can use it.)"""
    from solidworks_mcp.adapters.solidworks.features import (
        _select_named_feature,
    )
    from _common import name_last_feature

    SW_FM_SWEEP_CUT = 18  # swFeatureNameID_e.swFmSweepCut
    model = adapter.currentModel
    fm = model.FeatureManager
    data = _early_bound(fm.CreateDefinition(SW_FM_SWEEP_CUT), "ISweepFeatureData")
    model.ClearSelection2(True)
    if not _select_named_feature(adapter, profile, 1, False):
        raise RuntimeError(f"cannot select sweep profile {profile!r} (mark 1)")
    if not _select_named_feature(adapter, path, 4, True):
        raise RuntimeError(f"cannot select sweep path {path!r} (mark 4)")
    # Vendor Cut-Sweep option set (read off their feature data).
    data.AlignWithEndFaces = True
    data.TwistControlType = 0  # swTwistControlFollowPath
    data.PathAlignmentType = 10  # swMinimumTwist
    data.Direction = -1
    data.MergeSmoothFaces = True
    data.MaintainTangency = False
    data.AdvancedSmoothing = False
    data.StartTangencyType = 1
    data.EndTangencyType = 1
    data.AutoSelect = True
    with _telemetry.span("feature.thread_sweep_cut_modern", label=feature_name):
        swept = fm.CreateFeature(data)
    model.ClearSelection2(True)
    if swept is None:
        raise RuntimeError(
            f"CreateFeature (sweep cut) returned None for {feature_name}"
        )
    name_last_feature(adapter, feature_name)
    return swept


def combine_union(adapter, feature_name: str = "BodyUnion"):
    """Vendor Combine: union every body back into one."""
    import pythoncom
    from win32com.client import VARIANT
    from _common import name_last_feature

    model = adapter.currentModel
    bl = bodies(adapter)
    if len(bl) < 2:
        raise RuntimeError(f"combine needs >=2 bodies, got {len(bl)}")
    model.ClearSelection2(True)
    comb = model.FeatureManager.InsertCombineFeature(
        SW_BODY_ADD,
        None,
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, bl),
    )
    if comb is None:
        raise RuntimeError("InsertCombineFeature (union) failed")
    name_last_feature(adapter, feature_name)
    return comb


def insert_helix(
    adapter,
    pitch_mm: float,
    revolutions: float,
    *,
    clockwise: bool = True,
    reversed_dir: bool = False,
    start_angle_rad: float,
    feature_name: str,
):
    """InsertHelix on the ACTIVE sketch (it consumes it)."""
    from _common import name_last_feature

    adapter.currentModel.InsertHelix(
        reversed_dir,
        clockwise,
        False,
        False,  # Tapered / Outward
        0,  # swHelixDefinedByPitchAndRevolution
        0.0,  # Height (derived)
        pitch_mm / 1000.0,
        revolutions,
        0.0,  # TaperAngle
        start_angle_rad,
    )
    name_last_feature(adapter, feature_name)


def _sketch_manager(adapter):
    """``ISketchManager`` off the model, for raw sketch-entity calls.

    The adapter only caches its own wrapper while a sketch IT opened is
    active, so raw ``CreatePoint``/``CreateCenterLine`` calls go through the
    model's manager (the per-replica builders keep an identical local copy for
    their vendor-frame sketches).
    """
    return _early_bound(adapter.currentModel.SketchManager, "ISketchManager")


@_telemetry.traced("stock.shank.trim")
async def trim_factory_shank(adapter, a, cut) -> None:
    """Cut the finished shank end into a COMPLETE stock anchor, then deburr it.

    The production trim of both routing eyebolts (``StockAnchor`` ``a``, its
    :func:`stock_anchor_geom.trim` result ``cut``): the vendor solid is built
    whole from the stock ``Shank Lg.``, so this removes only free-end metal and
    restores the 45 deg deburr at the new end.  The factory helix, its cutter
    and every surviving thread surface stay put.  AddToDB stays off (via
    ``no_sketch_inference``) so the cutting profile cannot snap to a nearby
    thread edge.
    """
    from _common import (
        SketchDims,
        add_line_chain,
        anchor_point_to_origin,
        dimension_between,
        drive_dimension,
        force_rebuild,
        name_last_feature,
    )
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    radius, chamfer = a.thread_major_radius_mm, a.end_chamfer_mm
    y = cut.shank_end_y_mm
    with no_sketch_inference(adapter):
        check("create trim sketch", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter,
            [
                [-2 * radius, a.shank_end_y_mm - a.thread_major_dia_mm],
                [2 * radius, a.shank_end_y_mm - a.thread_major_dia_mm],
                [2 * radius, y],
                [-2 * radius, y],
            ],
        )
        dims = SketchDims()
        for line, direction in zip(
            lines, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
        ):
            check(
                "trim profile relation",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await anchor_point_to_origin(
            adapter,
            f"{lines[0]}.start",
            -2 * radius,
            a.shank_end_y_mm - a.thread_major_dia_mm,
            "trim cutter margin",
        )
        dims.record("CutterLeft")
        dims.record("CutterBottom")
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "horizontal_distance",
            4 * radius,
            "trim cutter width",
        )
        dims.record("CutterWidth")
        # This point is the exterior eye-top datum in the supplier frame, not
        # another cut control. It adds no profile or solid geometry.
        eye_top = _sketch_manager(adapter).CreatePoint(0, a.eye_od_mm / 2000, 0)
        if eye_top is None:
            raise RuntimeError("cannot create stock eye-top datum point")
        datum = adapter._register_sketch_entity("Point", eye_top)
        await anchor_point_to_origin(
            adapter, datum, 0, a.eye_od_mm / 2, "stock eye top"
        )
        dims.record("StockEyeTop")
        await dimension_between(
            adapter,
            datum,
            f"{lines[2]}.start",
            "vertical_distance",
            a.eye_od_mm / 2 - y,
            "finished overall",
        )
        dims.record("FinishedOverall")
        check("close trim sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "StockTrimProfile")
        dims.apply(adapter, "StockTrimProfile")
        check(
            "trim stock shank",
            await adapter.create_cut_extrude(
                ExtrusionParameters(
                    depth=4 * a.thread_major_dia_mm, both_directions=True
                )
            ),
        )
        name_last_feature(adapter, "StockTrim")
        check("create deburr sketch", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter,
            [
                [radius - chamfer, y],
                [radius + chamfer, y],
                [radius + chamfer, y + chamfer],
                [radius, y + chamfer],
            ],
        )
        dims = SketchDims()
        for line, direction in zip(
            lines[:3], ("horizontal", "vertical", "horizontal"), strict=True
        ):
            check(
                "deburr profile relation",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await anchor_point_to_origin(
            adapter,
            f"{lines[1]}.start",
            radius + chamfer,
            y,
            "deburr cutter outer corner",
        )
        dims.record("CutterRadius")
        dims.record("CutEnd")
        await dimension_between(
            adapter,
            f"{lines[3]}.start",
            "origin",
            "horizontal_distance",
            radius,
            "stock major radius",
        )
        dims.record("StockMajorRadius")
        await dimension_between(
            adapter,
            f"{lines[3]}.start",
            f"{lines[3]}.end",
            "horizontal_distance",
            chamfer,
            "end chamfer width",
        )
        dims.record("ChamferWidth")
        # Select both actual segments. Smart Dimension on one segment plus its
        # vertex did not yield a driving angular control in this profile.
        from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

        model = adapter.currentModel
        model.ClearSelection2(True)
        _select_sketch_entities(adapter, [lines[0], lines[3]], 0)
        display, status = _early_bound(
            model.Extension, "IModelDocExtension"
        ).AddSpecificDimension(
            (radius + 2 * chamfer) / 1000, (y + chamfer / 2) / 1000, 0, 3, 0
        )
        model.ClearSelection2(True)
        if display is None:
            raise RuntimeError(f"cannot create native chamfer angle: {status}")
        display = _early_bound(display, "IDisplayDimension")
        angle = _early_bound(display.GetDimension2(0), "IDimension")
        expected_angle = math.pi / 4
        actual_angle = abs(float(angle.SystemValue))
        if abs(actual_angle - expected_angle) > 1e-8:
            if (
                abs(math.pi - actual_angle - expected_angle) > 1e-8
                or not display.SupplementaryAngle()
            ):
                raise RuntimeError(
                    f"chamfer angle measured {math.degrees(actual_angle)} degrees"
                )
        angle.DrivenState = 2  # swDimensionDriving
        if (
            int(angle.DrivenState) != 2
            or abs(abs(float(angle.SystemValue)) - expected_angle) > 1e-8
        ):
            raise RuntimeError(
                "native chamfer angle is not a driving 45-degree control"
            )
        dims.record("ChamferAngle")
        axis = _sketch_manager(adapter).CreateCenterLine(
            0, (y - chamfer) / 1000, 0, 0, (y + 2 * chamfer) / 1000, 0
        )
        if axis is None:
            raise RuntimeError("stock deburr axis failed")
        axis_id = adapter._register_sketch_entity("Line", axis)
        check(
            "fix supplier shank axis",
            await adapter.add_sketch_constraint(axis_id, None, "fix"),
        )
        check("close deburr sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "StockDeburrProfile")
        dims.apply(adapter, "StockDeburrProfile")
        check(
            "deburr trimmed stock",
            await adapter.create_revolve(RevolveParameters(angle=360, is_cut=True)),
        )
        name_last_feature(adapter, "StockDeburr")
        await drive_dimension(
            adapter,
            "CutEnd@StockDeburrProfile",
            '"FinishedOverall@StockTrimProfile" - "StockEyeTop@StockTrimProfile"',
        )
    await force_rebuild(adapter)
    solid_bodies = bodies(adapter)
    if len(solid_bodies) != 1:
        raise RuntimeError("stock trim must leave one solid anchor")
    body = _early_bound(solid_bodies[0], "IBody2")
    extent = body.GetExtremePoint(0, -1, 0)
    if not extent[0] or abs(extent[2] * 1000 - y) > 1e-6:
        raise RuntimeError(f"trimmed shank end {extent} does not match Y={y} mm")
    _telemetry.event(
        "stock.trimmed",
        length_mm=cut.shank_length_mm,
        removed_mm=cut.removed_length_mm,
        end_y_mm=y,
    )


async def gate_and_save(adapter, part_no: str, truth: dict) -> dict:
    """Run the vendor ground-truth gates, save the replica + report + renders,
    then render the vendor part beside it.  Raises on any gate failure
    (after saving, so the failed model is on disk to inspect)."""
    v_mass = truth["mass"]
    v_vol = float(v_mass["volume_mm3"])
    v_surf = float(v_mass["surface_area_mm2"])
    v_com = [float(x) for x in v_mass["com_mm"]]
    v_faces = vendor_face_areas(truth)

    props = mass_properties(adapter)
    areas = face_areas(adapter)
    replica = OUT_DIR / f"{part_no}-replica.SLDPRT"
    report_path = OUT_DIR / f"{part_no}-replica-report.json"

    vol_tol = max(0.02, v_vol * 2e-4)
    surf_tol = max(0.10, v_surf * 5e-4)
    exact_multiset = len(v_faces) <= FACE_MULTISET_LIMIT

    # The dump reads COM in the VENDOR frame (its own axes); the replica is
    # authored head-up on Top, so map: replica (x, y, z) ~ vendor frame via
    # the builder-declared axis map in truth-space.  Builders author so the
    # replica COM y equals the vendor COM z minus the builder's declared
    # origin shift; each builder records that shift in adapter._mcm_com_map.
    com_map = getattr(adapter, "_mcm_com_map", None)
    exp_com = com_map(v_com) if com_map else v_com

    deltas = (
        [round(a - b, 4) for a, b in zip(areas, v_faces)]
        if len(areas) == len(v_faces)
        else None
    )
    top_k = sorted(areas)[-FACE_TOP_K:]
    v_top_k = sorted(v_faces)[-FACE_TOP_K:]
    report = {
        "part_no": part_no,
        "replica": str(replica),
        "vendor": str(MCMASTER_DIR / f"{part_no}.SLDPRT"),
        "volume_mm3": props["volume_mm3"],
        "vendor_volume_mm3": v_vol,
        "volume_delta": round(props["volume_mm3"] - v_vol, 4),
        "surface_mm2": props["surface_mm2"],
        "vendor_surface_mm2": v_surf,
        "surface_delta": round(props["surface_mm2"] - v_surf, 4),
        "com_mm": props["com_mm"],
        "vendor_com_mm": v_com,
        "expected_com_mm": exp_com,
        "face_count": len(areas),
        "vendor_face_count": len(v_faces),
        "face_gate": "multiset" if exact_multiset else f"count+top{FACE_TOP_K}",
        "face_areas": areas if exact_multiset else top_k,
        "vendor_face_areas": v_faces if exact_multiset else v_top_k,
        "face_area_deltas": deltas if exact_multiset else None,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _telemetry.info(f"report -> {report_path}")

    problems = []
    mass_problems = []
    if abs(report["volume_delta"]) > vol_tol:
        mass_problems.append(
            f"volume delta {report['volume_delta']:+.4f} mm^3 (tol {vol_tol:.4f})"
        )
    if abs(report["surface_delta"]) > surf_tol:
        mass_problems.append(
            f"surface delta {report['surface_delta']:+.4f} mm^2 (tol {surf_tol:.4f})"
        )
    problems.extend(mass_problems)
    if len(areas) != len(v_faces):
        problems.append(f"face count {len(areas)} != vendor {len(v_faces)}")
    elif exact_multiset:
        face_tol = max(0.06, max(v_faces) * 1e-3)
        worst = max(abs(d) for d in deltas)
        if worst > face_tol:
            problems.append(f"face area max delta {worst:.4f} (tol {face_tol:.4f})")
    else:
        face_tol = max(0.06, max(v_faces) * 1e-3)
        worst = max(abs(a - b) for a, b in zip(top_k, v_top_k, strict=True))
        if worst > face_tol:
            problems.append(
                f"top-{FACE_TOP_K} face area max delta {worst:.4f} (tol {face_tol:.4f})"
            )
    com = props["com_mm"]
    if com and exp_com and any(abs(a - b) > 0.02 for a, b in zip(com, exp_com)):
        problems.append(f"COM {com} != expected {exp_com}")

    # Save FIRST so a gate failure still leaves the model on disk to inspect.
    check(f"save -> {replica}", await adapter.save_file(str(replica.resolve())))
    artefacts = {"part": str(replica), "report": str(report_path)}
    artefacts.update(await export_views(adapter, f"{part_no}-replica"))

    # Some vendor bodies carry an IMassProperty integration artifact: their
    # stored mass numbers disagree with their OWN face-area sum (92865A585:
    # mpsurf 1680.39 vs facesum 1679.83, and a matching +0.58 mm^3 phantom
    # that survives a full feature re-execution on SW2026).  When ONLY the
    # volume/surface gates fail and the vendor truth is self-inconsistent
    # beyond the surface tolerance, arbitrate with tessellation: export
    # both bodies to STL and compare trimesh volume/area, which is
    # integrator-independent (the 92865A585 pair agrees to 1e-4 mm^3).
    vendor_selfincons = abs(sum(v_faces) - v_surf)
    if (
        mass_problems
        and len(mass_problems) == len(problems)
        and vendor_selfincons > max(0.10, v_surf * 1e-4)
    ):
        _telemetry.warn(
            f"{part_no}: vendor mass block self-inconsistent by "
            f"{vendor_selfincons:.4f} mm^2 -- arbitrating via STL"
        )
        import trimesh

        rep_stl = OUT_DIR / f"{part_no}-replica.stl"
        ven_stl = OUT_DIR / f"{part_no}-vendor.stl"
        # export each from a FRESH open -- exporting the live session doc
        # produced a truncated mesh (stale selection state)
        await close_all(adapter)
        for src, dst in (
            (replica, rep_stl),
            (MCMASTER_DIR / f"{part_no}.SLDPRT", ven_stl),
        ):
            check(f"open for STL {src.name}", await adapter.open_model(str(src)))
            m = _early_bound(adapter.currentModel, "IModelDoc2")
            m.ClearSelection2(True)
            if m.SaveAs3(str(dst), 0, 2) not in (0, True):
                _telemetry.warn(f"STL export returned non-zero for {src.name}")
            await close_all(adapter)
        mr = trimesh.load(str(rep_stl))
        mv = trimesh.load(str(ven_stl))
        stl_dv = float(mr.volume - mv.volume)
        stl_da = float(mr.area - mv.area)
        report["stl_volume_mm3"] = round(float(mr.volume), 4)
        report["stl_vendor_volume_mm3"] = round(float(mv.volume), 4)
        report["stl_volume_delta"] = round(stl_dv, 4)
        report["stl_area_delta"] = round(stl_da, 4)
        report["vendor_mass_selfinconsistency_mm2"] = round(vendor_selfincons, 4)
        if abs(stl_dv) <= vol_tol and abs(stl_da) <= surf_tol:
            report["face_gate"] += "+stl-arbitrated"
            _telemetry.warn(
                f"{part_no}: STL arbitration PASSED "
                f"(dv {stl_dv:+.4f} mm^3, da {stl_da:+.4f} mm^2) -- "
                f"vendor mass block overruled"
            )
            problems = [p for p in problems if p not in mass_problems]
        else:
            problems.append(
                f"STL arbitration failed too: dv {stl_dv:+.4f}, da {stl_da:+.4f}"
            )
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if problems:
        raise RuntimeError(
            f"{part_no} replica differs from vendor: " + "; ".join(problems)
        )
    _telemetry.success(
        f"{part_no} replica matches vendor: volume {props['volume_mm3']:.4f} "
        f"mm^3 (vendor {v_vol}), {len(areas)} faces "
        f"[{report['face_gate']} gate]"
    )
    return artefacts


async def close_all(adapter):
    """Discard every open document (the vendor part is NEVER saved)."""
    closed = adapter._attempt(
        lambda: adapter.swApp.CloseAllDocuments(True), default=False
    )
    if not closed:
        raise RuntimeError("CloseAllDocuments failed")
    adapter.currentModel = None


async def render_vendor(adapter, part_no: str) -> dict[str, str]:
    """Open the vendor part read-only for the eyeball pair, render, close."""
    vendor = MCMASTER_DIR / f"{part_no}.SLDPRT"
    check(f"open vendor {part_no}", await adapter.open_model(str(vendor)))
    out = {
        f"vendor_{k}": p
        for k, p in (await export_views(adapter, f"{part_no}-vendor")).items()
    }
    await close_all(adapter)
    return out


async def run_replica(adapter, part_no: str, builder) -> dict[str, str]:
    """One part end to end: create -> build -> gate/save -> render pair."""
    truth = vendor_truth(part_no)
    artefacts: dict[str, str] = {}
    with _telemetry.span("replica.build", label=part_no):
        check(f"create_part {part_no}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, part_no)
        await builder(adapter, truth)
        artefacts.update(await gate_and_save(adapter, part_no, truth))
        await close_all(adapter)
        artefacts.update(await render_vendor(adapter, part_no))
    return artefacts


def replica_main(part_no: str, builder) -> int:
    """`__main__` body for a single-part replica script."""
    from _common import run_build

    async def build(adapter) -> dict[str, str]:
        return await run_replica(adapter, part_no, builder)

    return run_build(build)
