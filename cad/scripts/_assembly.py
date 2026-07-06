"""Assembly-only helpers: mates, drivers, component placement, health/
interference gates, assembly save/refresh. Imported only by the assembly
build scripts (never by a leaf part), so edits here never invalidate parts.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

import _telemetry
from _common import (
    DEFAULT_VIEWS,
    FULLY_CONSTRAINED,
    OUT_PNG,
    OUT_SLDASM,
    OUT_SLDPRT,
    UNDER_CONSTRAINED,
    _CHAIN_LINK_PREFIXES,
    _FEATURE_ERROR,
    _MATE_TOL_MM,
    _flag,
    _flag_only,
    _read_member,
    check,
    log,
    set_isometric_view,
)
from _transforms import mirror_placement

def insert_sketch_text(
    adapter: Any,
    text: str,
    x_mm: float,
    y_mm: float,
    *,
    height_mm: float,
    width_pct: int = 100,
    space_pct: int = 100,
    alignment: int = 0,
    label: str = "text",
) -> Any:
    """Insert sized sketch text into the OPEN 2D sketch; return the ISketchText.

    Raw-COM helper (``IModelDoc2::InsertSketchText`` to place the glyph
    contours, then ``ISketchText::GetTextFormat`` + ``ITextFormat::CharHeight``
    + ``ISketchText::SetTextFormat`` to size them) -- the MCP adapter wraps no
    text primitive, so engraved lettering reaches past it the same way
    :func:`insert_helix` / :func:`extrude_at_offset` reach ``InsertHelix`` /
    ``FeatureExtrusion3``. The caller owns the sketch: open it (``create_sketch``)
    before, ``exit_sketch`` + ``create_cut_extrude`` after to incise the glyphs.

    ``x_mm``/``y_mm`` are the text-block insertion point in the Front-sketch
    frame (= model X/Y for the origin sketch this project authors on). Without a
    selected guide curve ``alignment`` is ignored and the block is left-anchored
    at the insertion point (SOLIDWORKS API remark) -- callers centre by pre-
    computing the left x. ``height_mm`` is the cap height; ``width_pct`` evenly
    widens each glyph (6..1667), ``space_pct`` the inter-character spacing.

    NOTE: not yet exercised on the SolidWorks COM seat (this repo runs the build
    on Windows); the call shapes follow the 2023 API reference verbatim. Treat
    the first live run as the validation pass, same posture as the other raw-COM
    stopgaps here.
    """
    model = adapter.currentModel
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        sk_text = model.InsertSketchText(
            x_mm / 1000.0,
            y_mm / 1000.0,
            0.0,
            text,
            int(alignment),  # 0=left 1=centre 2=right 3=justified
            0,  # FlipDirection (guide-curve only)
            0,  # HorizontalMirror
            int(width_pct),  # WidthFactor %
            int(space_pct),  # SpaceBetweenChars %
        )
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    if sk_text is None:
        raise RuntimeError(f"insert_sketch_text {label!r}: InsertSketchText returned None")
    fmt = _read_member(sk_text, "GetTextFormat")
    if fmt is None:
        raise RuntimeError(f"insert_sketch_text {label!r}: GetTextFormat returned None")
    fmt.CharHeight = height_mm / 1000.0  # ITextFormat.CharHeight is metres
    ok = adapter._attempt(lambda: sk_text.SetTextFormat(False, fmt), default=False)
    if not ok:
        raise RuntimeError(f"insert_sketch_text {label!r}: SetTextFormat returned False")
    model.ClearSelection2(True)
    _telemetry.success(f"sketch text {label!r} h{height_mm:g} @ ({x_mm:g}, {y_mm:g})")
    return sk_text

def add_ellipse(
    adapter: Any, cx_mm: float, cy_mm: float, rx_mm: float, ry_mm: float, label: str = "ellipse"
) -> Any:
    """Add a full ellipse to the OPEN 2D sketch; return the sketch segment.

    Raw-COM (``ISketchManager::CreateEllipse``: centre + a point on each axis,
    metres). ``rx_mm``/``ry_mm`` are the semi-axes along sketch X/Y. Inference is
    suppressed via ``AddToDB`` like the other raw draws here. Used for the
    nameplate's central cartouche oval (no ellipse primitive on the adapter).
    """
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        seg = sketch_mgr.CreateEllipse(
            cx_mm / 1000.0, cy_mm / 1000.0, 0.0,
            (cx_mm + rx_mm) / 1000.0, cy_mm / 1000.0, 0.0,  # major-axis point (+X)
            cx_mm / 1000.0, (cy_mm + ry_mm) / 1000.0, 0.0,  # minor-axis point (+Y)
        )
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    if seg is None:
        raise RuntimeError(f"add_ellipse {label!r}: CreateEllipse returned None")
    adapter.currentModel.ClearSelection2(True)
    _telemetry.success(f"ellipse {label!r} r({rx_mm:g}, {ry_mm:g}) @ ({cx_mm:g}, {cy_mm:g})")
    return seg

async def apply_component_color(
    adapter: Any,
    name: str,
    rgb: tuple[float, float, float],
) -> None:
    """Per-INSTANCE component display colour in an assembly.

    A part colour cannot tint one instance of a multi-config part differently
    from another: a per-config part colour loses to the part's material
    appearance, and a body colour is global to the part document. The component
    instance appearance sits above both and is per-occurrence, so the four
    muntz_yellow cone tip-gear instances tint without touching the brass part or
    the other 16 cone gears. It is also exactly what the render pipeline reads
    (export_models comp_rgb -> IComponent2.GetMaterialPropertyValues2).

    Sets via IComponent2.SetMaterialPropertyValues2(values, swThisConfiguration,
    None) and asserts the readback (SW quantises to 8 bit/channel).
    """
    from solidworks_mcp.adapters.com_variant import double_array

    comp = adapter.currentModel.GetComponentByName(name)
    if comp is None:
        raise RuntimeError(f"component not found for colour: {name!r}")
    # No flag: Set/GetMaterialPropertyValues2 are both called WITH args, so late
    # binding dispatches them as methods unambiguously (issue #87).
    values = double_array([*rgb, 1.0, 1.0, 0.3, 0.31, 0.0, 0.0])
    # [R,G,B, ambient, diffuse, specular, shininess, transparency, emission]
    comp.SetMaterialPropertyValues2(values, 1, None)  # swThisConfiguration
    back_raw = adapter._attempt(
        lambda: comp.GetMaterialPropertyValues2(1, None), default=None
    )
    back = tuple(float(v) for v in (back_raw or ())[:3])
    if len(back) != 3 or any(abs(b - w) > 1 / 255 for b, w in zip(back, rgb)):
        raise RuntimeError(f"component colour readback mismatch on {name}: set {rgb}, got {back}")
    adapter._attempt(lambda: adapter.currentModel.GraphicsRedraw2(), default=None)
    log(f"component colour {name}: {tuple(round(v, 3) for v in back)}")

def component_transform(adapter: Any, name: str) -> list[float]:
    """Return a component's ``Transform2`` ArrayData (rotation rows in
    [0:9], translation in metres in [9:12])."""
    component = adapter.currentModel.GetComponentByName(name)
    if component is None:
        raise RuntimeError(f"component not found for transform readback: {name!r}")
    return [
        float(v)
        for v in _read_member(_read_member(component, "Transform2"), "ArrayData")
    ]

def world_point(adapter: Any, name: str, local_mm: list[float]) -> list[float]:
    """Map a component-local point (mm) to the assembly frame (mm).

    Uses the live ``Transform2`` ArrayData: world = local·R + t. Lets callers
    locate a named bore (its sketch-local centre) in the assembly after the
    component has been placed/mated, without re-deriving the mirror algebra.
    """
    a = component_transform(adapter, name)
    r, t = a[0:9], a[9:12]
    return [
        sum(local_mm[i] * r[i * 3 + k] for i in range(3)) + t[k] * 1000.0
        for k in range(3)
    ]

def component_origin(adapter: Any, name: str) -> list[float]:
    """A component's current origin (mm) in the assembly frame."""
    a = component_transform(adapter, name)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]

def part_path(part: str) -> str:
    """Resolve ``<part>.SLDPRT`` under the part-output dir, or raise."""
    path = (OUT_SLDPRT / f"{part}.SLDPRT").resolve()
    if not path.exists():
        raise RuntimeError(
            f"missing part {path}; run build_{part.replace('-', '_')}.py first"
        )
    return str(path)

# As-authored pose ledger (the foundational placement gate, 2026-07-05).
# ``place_component`` and ``place_components_batch`` record every inserted
# component's final (mirrored) world position AND rotation rows;
# ``save_assembly_and_images`` re-verifies ALL of them after the LAST solve,
# just before saving. Rationale: the per-mate ``verify=`` reads run
# mid-build -- a later re-solve can still hop an unsigned distance-mate
# branch (the 16T crank pinion rendered floating ~200 mm off its seat with
# every gate green: mates satisfied, nothing interfering). Rotation is
# checked too (Codex, 2026-07-05): a component can spin about its placed
# origin -- e.g. the lift rod / cam collars on the freed pinion_cam DOF --
# leaving the translation clean while the parked pose is visibly wrong.
# Builds never actuate the freed operational DOF, so the as-saved pose must
# equal the authored rest pose for every component -- drift IS a defect.
_POSE_LEDGER: dict[str, tuple[list[float], list[float]]] = {}


def _ledger_record(name: str, position: list[float], rows: list[list[float]]) -> None:
    _POSE_LEDGER[name] = (list(position), [c for row in rows for c in row])


def assert_pose_ledger(
    adapter: Any, tol_mm: float = 0.5, rot_tol: float = 1e-3,
) -> None:
    """Verify every ledger component still sits at its authored world pose."""
    offenders: list[str] = []
    for name, (expected, exp_rows) in _POSE_LEDGER.items():
        array = component_transform(adapter, name)
        actual = [array[9] * 1000.0, array[10] * 1000.0, array[11] * 1000.0]
        delta = max(abs(a - e) for a, e in zip(actual, expected, strict=True))
        if delta > tol_mm:
            offenders.append(
                f"{name}: {[round(v, 2) for v in actual]} != authored "
                f"{[round(v, 2) for v in expected]} (drift {delta:.2f})"
            )
            continue
        rot_drift = max(
            abs(a - e) for a, e in zip(array[0:9], exp_rows, strict=True)
        )
        if rot_drift > rot_tol:
            offenders.append(
                f"{name}: rotation {[round(v, 4) for v in array[0:9]]} != "
                f"authored {[round(v, 4) for v in exp_rows]} "
                f"(drift {rot_drift:.4f})"
            )
    n = len(_POSE_LEDGER)
    _POSE_LEDGER.clear()
    if offenders:
        raise RuntimeError(
            f"pose ledger: {len(offenders)} component(s) drifted from the "
            "authored pose after the final solve:\n  " + "\n  ".join(offenders)
        )
    _telemetry.success(f"pose ledger: all {n} placed components at authored pose")


def assert_component_placed(
    adapter: Any,
    name: str,
    origin_mm: list[float],
    rotation_rows: list[list[float]] | None = None,
    tol_mm: float = 0.5,
) -> None:
    """Assert a component sits at ``origin_mm`` with the given rotation.

    ``rotation_rows`` are the images of the component X/Y/Z axes in assembly
    space (``Transform2`` rows). Catches both wrong-side distance-mate flips
    (translation) and silent 180-degree plane-mate flips (rotation).
    """
    array = component_transform(adapter, name)
    actual = [array[9] * 1000.0, array[10] * 1000.0, array[11] * 1000.0]
    deltas = [abs(a - e) for a, e in zip(actual, origin_mm, strict=True)]
    if max(deltas) > tol_mm:
        raise RuntimeError(
            f"{name}: origin {actual} != expected {origin_mm} (tol {tol_mm} mm)"
        )
    if rotation_rows is not None:
        flat = [c for row in rotation_rows for c in row]
        drift = max(abs(a - e) for a, e in zip(array[0:9], flat, strict=True))
        if drift > 1e-3:
            raise RuntimeError(
                f"{name}: rotation {array[0:9]} != expected {flat} (drift {drift:.4f})"
            )
    _telemetry.success(f"{name} placed at {[round(v, 3) for v in actual]}")

def named_ref(name: str, entity_type: str) -> Any:
    """A ``MateEntityRef`` selecting an entity by qualified name."""
    from solidworks_mcp.adapters.base import MateEntityRef

    return MateEntityRef(entity_type=entity_type, name=name)

def component_named_ref(
    component: str, name: str, entity_type: str = "AXIS",
) -> Any:
    """A ``MateEntityRef`` selecting a named reference feature inside a nested
    component via ``IComponent2.GetCorresponding``.

    ``component`` is the slash path ``"sub/part"`` (e.g.
    ``"channel-1/connecting-rod-1"``); ``name`` is the part-local named feature
    (e.g. ``"Axis1"``). This is the depth-2-safe selection path: a hand-built
    ``Axis1@part@sub@title`` string resolves one level deep but returns False
    for a part nested in a flexible subassembly, whereas the adapter maps the
    base ``IFeature`` through the component's ``GetCorresponding`` (depth-
    agnostic, mirror-safe, ~600x faster than a cylindrical-face walk). See the
    phase-f-motion-study memory + PR #64.
    """
    from solidworks_mcp.adapters.base import MateEntityRef

    return MateEntityRef(entity_type=entity_type, component=component, name=name)

def bore_axis_ref(point_mm: list[float], entity_type: str = "FACE") -> Any:
    """A ``MateEntityRef`` selecting a cylindrical face/axis by a point on it.

    ``point_mm`` is in the FINAL (mirrored) machine frame -- the same frame the
    component occupies after :func:`place_component` -- so concentric /
    coincident selections land on the as-built geometry. Use a point on the
    bore wall at mid-depth; ``entity_type="AXIS"`` with a name is the fallback
    when no stable face point exists.
    """
    from solidworks_mcp.adapters.base import MateEntityRef

    return MateEntityRef(entity_type=entity_type, point=list(point_mm))

async def _add_mate(
    adapter: Any,
    kind: str,
    entities: list[Any],
    *,
    distance: float = 0.0,
    angle: float = 0.0,
    alignment: str = "closest",
    lock_rotation: bool = False,
    gear_ratio: Iterable[float] | None = None,
    pinion_pitch_diameter: float = 0.0,
    rack_travel_per_revolution: float = 0.0,
    flip: bool = False,
) -> Any:
    from solidworks_mcp.adapters.base import AddMateParameters

    return await adapter.add_mate(
        AddMateParameters(
            mate_type=kind,
            entities=entities,
            alignment=alignment,
            flip=flip,
            distance=abs(distance),
            angle=angle,
            lock_rotation=lock_rotation,
            gear_ratio=list(gear_ratio) if gear_ratio else [],
            pinion_pitch_diameter=pinion_pitch_diameter,
            rack_travel_per_revolution=rack_travel_per_revolution,
        )
    )

def _mate_hard_error(adapter: Any, name: str) -> int:
    """The named mate feature's HARD ``swFeatureError_e`` code (0 if clean or
    only a warning). SW can create a mate in an ERROR state (e.g. 47 "cannot
    be solved -- dimension flipped") WITHOUT moving anything, so a motion-based
    readback alone misses a wrong-side add -- the magnifier wire-swing park
    replay authored "OK", left the wire at pose, and the closure gate found the
    corpse (2026-07-05). One FeatureByName + GetErrorCode2 per mate; warnings
    (e.g. legitimate over-define co-flags) stay tolerated."""
    import pythoncom
    from win32com.client import VARIANT

    if not name:
        return 0
    model = adapter.currentModel
    feat = adapter._attempt(lambda: model.FeatureByName(name), default=None)
    if feat is None:
        return 0
    _flag_only(feat, "GetErrorCode2")
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BOOL, False)
    code = int(adapter._attempt(lambda: feat.GetErrorCode2(warn), default=0) or 0)
    if code and bool(warn.value):
        return 0
    return code


# --- Deterministic flip seeding for distance drivers ------------------------
# A distance mate is two-sided: abs(d) fixes the gap, `flip` picks the side. The
# correct side is a function of the SIGN of the (signed) target coordinate the
# build already computed -- a part at z=-40 sits on the far side of the datum
# from one at z=+40 -- so `flip = (signed < 0)` lands the great majority on-
# target in ONE solve, no delete-and-re-add. A minority of references have their
# default side inverted relative to the coordinate's + direction (the part
# plane's normal opposes the datum's); those signatures live in `_FLIP_INVERT`
# and XOR the rule. The set is DETERMINED ONCE during development: build with it
# empty, and every mate that still needs a recovery WARNS with its signature
# (see `_mate`); add those signatures here and rebuild -> zero flips. The
# readback guard in `_mate` stays as the safety net AND regression alarm: a flip
# in a normal build means this heuristic broke for that mate -- re-learn its side.
_FLIP_INVERT: frozenset[str] = frozenset({
    # Per-signature flip polarity, learned once from the discovery build (see
    # `_seed_flip`/`_orient_suffix`): a signature here seats on the side
    # OPPOSITE the plain sign rule. Rotation/mirror twins carry an ` @<diag>`
    # orientation suffix so each is seeded independently of its sibling.
    # Re-derive after a mate/geometry change: build with this empty, read the
    # `flip-seed MISS` warns, paste their sigs here, rebuild -> zero flips.
    "alignment pinion axial",
    "arbor pedestal datum X",
    "arbor pedestal datum Y",
    "arbor pedestal datum Y @npn",
    "arbor pedestal datum Z",
    "axial seat",
    "cam follower back seat depth",
    "cam follower front seat depth",
    "cone gear axial seat",
    "cone lock knob datum X",
    "cone lock knob datum Y",
    "cone lock knob datum Z",
    "cone pivot screw datum X",
    "cone pivot screw datum Y",
    "cone pivot screw datum Z",
    "cone platform height",
    "cone shaft axial",
    "crankshaft axial (on the plate)",
    "cylinder gear axial anchor",
    "cylinder gear axial pitch",
    "foot screw datum X",
    "foot screw datum Y",
    "foot screw datum Z",
    "fulcrum shaft datum x",
    "fulcrum shaft datum y",
    "lever axial seat",
    "lever bushing axial z",
    "lift rod axial",
    "mag lever depth @npn",
    "mag lever knife line across @npn",
    "pen rod travel snapshot",
    "pinch head seat @ppn",
    "pinion arbor axial",
    "pinion cam back set pin axial",
    "pinion cam front set pin axial",
    "pinion pivot block datum Y @npn",
    "pinion pivot shaft datum X",
    "pinion pivot shaft datum Y",
    "pinion pivot shaft datum Z",
    "pinion spring datum Y @npn",
    "pivot ball mount datum x",
    "pivot ball mount datum y",
    "pivot ball mount datum z",
    "pivot bushing axial z",
    "platen feed snapshot",
    "slotted screw datum X",
    "slotted screw datum Y",
    "slotted screw datum Z",
    "spring hook datum y @npn",
    "swing stop screw datum X",
    "swing stop screw datum Y",
    "swing stop screw datum Z",
    "tip block axial seat",
    "tip bushing axial seat",
})


def _flip_sig(label: str) -> str:
    """Canonical, index/coordinate-free signature of a driver ``label``.

    Strips the volatile per-instance parts -- the ``-> x,y`` target, the
    ``d=<dist>`` distance, and every digit-bearing token (channel/tooth indices
    like ``-7``, ``ch16``, ``T120``, ``J4``) -- leaving the structural descriptor
    (``"spring hook datum y"``). Mates that share a signature are the same seat
    stamped across a pattern, so they share one flip polarity. Keys
    :data:`_FLIP_INVERT`; generated with the SAME transform over the mined flip
    logs, so seeds and runtime signatures match by construction."""
    s = re.sub(r"\s*->.*$", "", label)
    s = re.sub(r"\bd=[+-]?[0-9.]+", "", s)
    s = re.sub(r"\b\w*\d\w*\b", " ", s)
    s = re.sub(r"[-\s]+", " ", s).strip()
    return s


def _orient_suffix(adapter: Any, comp_name: str) -> str:
    """Orientation fingerprint of a component, disambiguating a flip signature.

    A datum-plane distance mate's correct side depends on which way the part's
    same-name plane normal points, and a FIXED rotation of the part flips it: the
    NORTH arbor pedestal is the SOUTH casting rotated 180 deg about Y, so its Right
    (X) and Front (Z) plane normals invert while Top (Y) is unchanged -- the two
    pedestals need OPPOSITE flip on X/Z. They share one :func:`_flip_sig` (the
    instance index is stripped so a 20-channel pattern collapses to one entry), so
    without this they collide on a single polarity. Tag the signature with the sign
    of the component's rotation-matrix diagonal (``ppp`` = identity, dropped; the
    ry180 twin is ``npn``): same-oriented instances still share one entry, while a
    rotation/mirror twin gets its own -- learned independently. Empty for a missing
    name (a driver without a ``verify`` component)."""
    if not comp_name:
        return ""
    xf = component_transform(adapter, comp_name)
    signs = "".join("n" if xf[i] < -1e-6 else "p" for i in (0, 4, 8))
    return "" if signs == "ppp" else " @" + signs


def _seed_flip(label: str, signed: float, suffix: str = "") -> bool:
    """The deterministic first-solve side for a distance driver: the sign of the
    signed target coordinate, XOR the reference's learned polarity. ``suffix`` is
    the caller's orientation fingerprint (:func:`_orient_suffix`), appended to the
    signature so a rotation/mirror twin is disambiguated from its sibling."""
    return (signed < 0.0) ^ ((_flip_sig(label) + suffix) in _FLIP_INVERT)


async def _mate(
    adapter: Any,
    label: str,
    kind: str,
    entities: list[Any],
    *,
    verify: tuple[str, list[float]] | None = None,
    flip: bool = False,
    **kw: Any,
) -> Any:
    """Add a mate and ``check`` it; recover a far-side flip when ``verify`` set.

    ``verify=(comp_name, target_origin_mm)`` enables readback-and-flip: after
    the mate solves, the component origin must stay within ``_MATE_TOL_MM`` of
    ``target_origin_mm`` (it was inserted there); otherwise the mate is deleted
    and re-added with the OPPOSITE flip, then re-checked. A mate created in a
    HARD error state (``_mate_hard_error``) triggers the same recovery even
    when nothing moved -- SW's wrong-side add can fail IN PLACE. Returns the
    (final) mate result data.

    ``flip`` seeds the FIRST solve's side. Default ``False`` keeps the historic
    behaviour (lean on the recovery). A caller that already knows the correct
    side passes the right ``flip`` so the part lands on-target in ONE solve --
    no delete-and-re-add, so the part never visibly jumps. The recovery stays as
    a safety net (re-adds with ``not flip``), so a wrong guess still self-heals.
    """
    from solidworks_mcp.adapters.base import MateRefParameters

    # Span every mate (the single chokepoint all mate helpers funnel through),
    # including flip-recovery, so the full-build waterfall stays contiguous
    # between part spans instead of leaving the mate time as a gap. NAME the span
    # for the caller's descriptive ``label`` (e.g. "mate top@crank_pin <-> ...")
    # rather than the generic mate ``kind`` -- a waterfall of 40 identical
    # "mate distance" rows is unreadable; the mate TYPE stays as an attribute.
    async with _telemetry.aspan(label, kind=kind, label=label) as msp:
        res = check(label, await _add_mate(adapter, kind, entities, flip=flip, **kw))
        err = _mate_hard_error(adapter, res.get("name", ""))
        if verify is None and not err:
            return res
        moved = 0.0
        comp_name: str | None = None
        target_origin: list[float] = []
        if verify is not None:
            comp_name, target_origin = verify
            array = component_transform(adapter, comp_name)
            moved = max(abs(array[9 + i] * 1000.0 - target_origin[i]) for i in range(3))
        if moved <= _MATE_TOL_MM and not err:
            return res
        msp.set_attribute("flipped", True)
        # A flip-recovery is a moment in this mate's span timeline, not a
        # standalone status line -- record it as a span event so the trace shows
        # WHEN in the mate the re-solve happened and by how far it was off.
        _telemetry.event(
            "mate.flip_recovery", label=label, moved_mm=round(moved, 3), error=err)
        _seed_sig = _flip_sig(label) + (
            _orient_suffix(adapter, comp_name) if comp_name else "")
        _telemetry.warn(
            f"flip-seed MISS: {label!r} off by {moved:.2f} mm, error={err}"
            f" -> re-adding flipped  (learn: add sig {_seed_sig!r} to _FLIP_INVERT)"
        )
        check(
            f"{label} (delete wrong side)",
            await adapter.delete_mate(MateRefParameters(name=res.get("name", ""))),
        )
        res = check(
            f"{label} (flipped)",
            await _add_mate(adapter, kind, entities, flip=not flip, **kw),
        )
        err = _mate_hard_error(adapter, res.get("name", ""))
        if err:
            raise RuntimeError(
                f"{label}: mate in hard error state {err} after flip recovery")
        if comp_name is not None:
            array = component_transform(adapter, comp_name)
            moved = max(
                abs(array[9 + i] * 1000.0 - target_origin[i]) for i in range(3))
            if moved > _MATE_TOL_MM:
                raise RuntimeError(
                    f"{label}: component still off target by {moved:.2f} mm")
        return res

async def plane_distance_mate(
    adapter: Any,
    comp_name: str,
    comp_plane: str,
    base_plane: str,
    base_name: str,
    distance: float,
    target_origin: list[float],
) -> Any:
    """Place ``comp_plane`` at a SIGNED offset from the base datum, flip-free.

    The structural-placement workhorse: three orthogonal calls fully define a
    grounded part against the reference part's principal planes. The reference
    part (``base_name``) is the assembly's origin-fixed first component, so its
    principal planes coincide with the assembly datum planes -- offsetting from
    ``base_plane`` (an assembly datum) is geometrically the base part's plane.

    ``distance`` is SIGNED and its sign alone selects the side (a positive offset
    steps along ``+base_plane`` normal), so there is no mate flip and no
    delete-and-re-add recovery. For a non-zero offset we build ONE assembly
    reference plane at ``create_plane(base_plane, offset=distance)`` -- the signed
    offset lands it on the correct side in a single shot -- and mate
    ``comp_plane`` COINCIDENT to it. For ``distance == 0`` the datum itself is the
    target, so ``comp_plane`` is mated coincident straight to ``base_plane@base_name``.

    A coincident cannot put the part on the wrong distance-side the way a distance
    mate's ambiguous side once did (the offset plane fixes the position;
    ``alignment="closest"`` keeps the inserted orientation). ``target_origin``
    still feeds the readback guard in :func:`coincident_mate`, now a pure
    tripwire: a correct signed offset lands on-target in one solve, so the guard
    confirms rather than recovers.
    """
    label = f"mate {comp_plane}@{comp_name} <-> {base_plane}@{base_name} d={distance:g}"
    if abs(distance) <= 1e-9:
        target_ref = named_ref(f"{base_plane}@{base_name}", "PLANE")
    else:
        from solidworks_mcp.adapters.base import CreatePlaneParameters

        plane = check(
            f"create_plane {base_plane}{distance:+g} for {comp_name}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane=base_plane, offset=distance
                )
            ),
        )
        target_ref = named_ref(getattr(plane, "name", plane), "PLANE")
    return await coincident_mate(
        adapter,
        named_ref(f"{comp_plane}@{comp_name}", "PLANE"),
        target_ref,
        label=label,
        verify=(comp_name, target_origin),
    )

async def concentric_mate(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    *,
    lock_rotation: bool = False,
    alignment: str = "closest",
    label: str = "concentric",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Concentric (coaxial) mate; ``lock_rotation`` removes the spin DOF too."""
    return await _mate(
        adapter,
        label,
        "concentric",
        [ref_a, ref_b],
        lock_rotation=lock_rotation,
        alignment=alignment,
        verify=verify,
    )

async def coincident_mate(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    *,
    alignment: str = "closest",
    label: str = "coincident",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Coincident mate between two faces / planes / points."""
    return await _mate(
        adapter,
        label,
        "coincident",
        [ref_a, ref_b],
        alignment=alignment,
        verify=verify,
    )

async def parallel_mate(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    *,
    alignment: str = "closest",
    label: str = "parallel",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Parallel mate between two planes / faces; pins ONE rotational DOF.

    The distance-free way to pin a leftover rotation (e.g. the immaterial spin of
    a concentric-/collinear-mated solid of revolution) -- coincident would force
    the planes flush (an unwanted translation), parallel only kills the spin.
    """
    return await _mate(
        adapter,
        label,
        "parallel",
        [ref_a, ref_b],
        alignment=alignment,
        verify=verify,
    )

async def distance_driver(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    distance: float,
    *,
    label: str = "",
    verify: tuple[str, list[float]] | None = None,
    free_dof_key: str | None = None,
    flip: bool | None = None,
) -> Any:
    """A distance mate used as a driving dimension pinning one slide DOF.

    ``distance`` is SIGNED: its magnitude is the gap, and its SIGN selects the
    mate side deterministically -- ``flip`` defaults to :func:`_seed_flip` (the
    sign of ``distance`` XOR the reference's learned polarity), so the part lands
    on-target in ONE solve with no delete-and-re-add flip recovery. Pass an
    explicit ``flip`` to override the sign rule. (Callers that pass a bare
    magnitude get ``flip=False``, the historic behaviour.)

    ``free_dof_key`` marks this as a *freed operational-DOF* park driver (see the
    Park drivers section): in a deferred (default-``free``) build it is RECORDED
    as a spec and NOT authored -- leaving the slide free and saving the mate
    solve -- while a ``locked`` build authors it engaged and renames it
    ``PARK_<key>``. ``None`` is a hard pin, authored as before.
    """
    label = label or f"distance driver d={distance:g}"
    if flip is None:
        comp = verify[0] if verify else ""
        flip = _seed_flip(label, distance, _orient_suffix(adapter, comp))
    return await _driver_or_defer(
        adapter, "distance", ref_a, ref_b,
        label=label, verify=verify, free_dof_key=free_dof_key, flip=flip,
        distance=abs(distance),
    )

async def angle_driver(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    angle: float,
    *,
    label: str = "",
    verify: tuple[str, list[float]] | None = None,
    free_dof_key: str | None = None,
) -> Any:
    """An angle mate used as a driving dimension pinning one rotational DOF.

    ``free_dof_key`` marks this as a *freed operational-DOF* park driver: in a
    deferred (default-``free``) build it is RECORDED and NOT authored (leaving the
    rotation free); a ``locked`` build authors it engaged and renames it
    ``PARK_<key>``. See :func:`distance_driver` and the Park drivers section.
    """
    label = label or f"angle driver a={angle:g}"
    return await _driver_or_defer(
        adapter, "angle", ref_a, ref_b,
        label=label, verify=verify, free_dof_key=free_dof_key,
        angle=angle,
    )

async def spin_driver(
    adapter: Any,
    off_axis_ref: Any,
    pivot_xy: tuple[float, float],
    target_xy: tuple[float, float],
    *,
    label: str = "",
    verify: tuple[str, list[float]] | None = None,
    free_dof_key: str | None = None,
) -> Any:
    """Pin a revolute's spin via a distance from an off-pivot bore to a plane.

    ``free_dof_key`` (a park key) forwards to the underlying :func:`distance_driver`
    so the spin becomes a *freed operational-DOF* park driver: recorded (not
    authored) in a deferred ``free`` build, engaged + ``PARK_<key>`` in a ``locked``
    build. The resolved plane + target distance ARE the recorded spec, so the
    replay re-authors the same pin without re-deriving the sensitivity choice.

    A plane-plane *angle* mate is unreliable here: a mirrored part flips its
    plane normals, so the true dihedral is ``180 - tilt`` and both flip
    solutions miss. Instead lock the better-conditioned in-plane coordinate of
    a bore that is offset from the rotation axis (``off_axis_ref``, a named
    AXIS): a Z-parallel axis's distance to the Top plane is its ``y``, to the
    Right plane its ``x``. Rotating by ``dφ`` moves the bore's ``x`` by
    ``-Δy·dφ`` and its ``y`` by ``+Δx·dφ`` (Δ = bore − pivot), so pin ``y``
    (Top) when the offset is mostly horizontal (``|Δx| ≥ |Δy|``), else ``x``
    (Right) -- whichever has the larger rotation sensitivity. ``target_xy`` is
    the bore's on-solution assembly position (see :func:`world_point`).
    """
    dx = target_xy[0] - pivot_xy[0]
    dy = target_xy[1] - pivot_xy[1]
    if abs(dx) >= abs(dy):
        plane, target = "Top Plane", target_xy[1]
    else:
        plane, target = "Right Plane", target_xy[0]
    label = label or f"spin driver via {plane} d={abs(target):g}"
    return await distance_driver(
        adapter,
        off_axis_ref,
        named_ref(plane, "PLANE"),
        target,  # SIGNED: distance_driver abs()es the mate value but needs the
        # sign to seed the seat side (which side of the plane the off-axis bore
        # is on). Passing abs() defeated the seeding -> every deferred rod_swing
        # replay flipped (108.95 mm each) in the preflight (2026-07-05).
        label=label,
        verify=verify,
        free_dof_key=free_dof_key,
    )

async def tangent_mate(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    *,
    alignment: str = "closest",
    label: str = "tangent",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Tangent mate (e.g. an amplitude-bar notch riding a rocker arc)."""
    return await _mate(
        adapter,
        label,
        "tangent",
        [ref_a, ref_b],
        alignment=alignment,
        verify=verify,
    )

async def lock_mate(adapter: Any, ref_a: Any, ref_b: Any, *, label: str = "lock") -> Any:
    """Lock mate: rigidly fix two components' relative pose (e.g. crank parts)."""
    return await _mate(adapter, label, "lock", [ref_a, ref_b])

async def gear_mate(
    adapter: Any,
    ref_a: Any,
    ref_b: Any,
    ratio: Iterable[float],
    *,
    alignment: str = "closest",
    label: str = "",
) -> Any:
    """Gear mate coupling two rotations at ``ratio=[numerator, denominator]``.

    The ratio is tooth counts (driver:driven); verify the sign/direction with a
    kinematic rotate after meshing, per the plan's gear-ratio risk.
    """
    ratio = list(ratio)
    label = label or f"gear {ratio[0]:g}:{ratio[1]:g}"
    return await _mate(
        adapter, label, "gear", [ref_a, ref_b], gear_ratio=ratio, alignment=alignment
    )

async def cam_follower_mate(
    adapter: Any, cam_ref: Any, follower_ref: Any, *, label: str = "cam_follower"
) -> Any:
    """Cam-follower mate; the adapter applies the cam selection mark (8)."""
    return await _mate(adapter, label, "cam_follower", [cam_ref, follower_ref])

async def rack_pinion_mate(
    adapter: Any,
    rack_ref: Any,
    pinion_ref: Any,
    *,
    pinion_pitch_diameter: float = 0.0,
    rack_travel_per_revolution: float = 0.0,
    label: str = "rack_pinion",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Rack-pinion mate coupling a linear rack to a rotating pinion.

    ``rack_ref`` selects a linear rack edge/axis, ``pinion_ref`` the pinion's
    cylindrical face/axis. Set EITHER ``pinion_pitch_diameter`` (mm) OR
    ``rack_travel_per_revolution`` (mm) -- the adapter writes it into the mate
    definition (AddMate5 has no parameter for it). Verify the feed direction
    with a kinematic rotate, per the plan's gear-ratio risk.
    """
    return await _mate(
        adapter,
        label,
        "rack_pinion",
        [rack_ref, pinion_ref],
        pinion_pitch_diameter=pinion_pitch_diameter,
        rack_travel_per_revolution=rack_travel_per_revolution,
        verify=verify,
    )

async def place_component(
    adapter: Any,
    part: str,
    position: list[float],
    rotation: list[float],
    rows: list[list[float]],
    *,
    ground: bool = True,
    mirror: bool = True,
    configuration: str = "",
    label: str = "",
) -> str:
    """Insert a part at its exact final (mirrored) transform and assert it.

    ``ground=True`` fixes the component (structure: shafts, mounts, bushings,
    supports, frame, fasteners, cosmetic springs). ``ground=False`` leaves it
    free for the caller's mates to constrain -- the moving parts whose DOF are
    driven from the crank. ``configuration`` selects a part configuration (the
    cone-gear tooth counts, the transgear-removable wheels). Either way the
    part is inserted on-solution so mate flip-recovery has a clean reference
    and the read-back assert holds.

    ``mirror=True`` (default) routes the placement through ``mirror_placement``,
    which reflects it about the machine YZ plane using the part's declared symmetry
    (``cad/config/placement/<part>.yaml``, default ``"x"``). Pass ``mirror=False`` for a SINGLE machine-handed
    part with no mirror twin -- e.g. the maker's nameplate -- whose ``position``/
    ``rows`` are already the exact machine transform; the default ``"x"`` reflection
    would otherwise flip it across X (onto the wrong side, text reversed).
    """
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    label = label or part
    # One span per part: insert + (fix) + placement assert for THIS component, so
    # the full-build waterfall shows where each part's time went and a failed
    # insert/mate is attributed to the part by name.
    async with _telemetry.aspan(
        f"part {label}", part=part, ground=ground,
        configuration=configuration or "default",
    ) as psp:
        if mirror:
            position, rotation, rows = mirror_placement(
                part, position, rotation, rows, configuration
            )
        path = (OUT_SLDPRT / f"{part}.SLDPRT").resolve()
        if not path.exists():
            raise RuntimeError(
                f"missing part {path}; run build_{part.replace('-', '_')}.py first"
            )
        data = check(
            f"insert {label} @ ({position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f})",
            await adapter.insert_component(
                InsertComponentParameters(
                    file_path=str(path),
                    position=position,
                    rotation=rotation,
                    configuration=configuration,
                )
            ),
        )
        name = data["name"]
        psp.set_attribute("component", name)
        if ground and not data.get("fixed"):
            check(
                f"fix {label}",
                await adapter.fix_component(ComponentRefParameters(name=name)),
            )
        assert_component_placed(adapter, name, position, rows)
        _ledger_record(name, position, rows)
        return name

def _placement_transform(rows: list[list[float]], position_mm: list[float]) -> list[float]:
    """The 16-double ``IMathTransform`` for a component at ``rows``/``position_mm``.

    Matches the ``Transform2.ArrayData`` layout SolidWorks reports (and that
    :func:`component_transform` / :func:`assert_component_placed` already
    validate): the 3x3 rotation row-major in [0:9], the translation (METRES) in
    [9:12], the scale (1.0) at [12], the last three unused. Feeding
    ``AddComponents3`` this exact layout makes the read-back assert hold by
    construction -- the same matrix SW would have produced via per-part insert.
    """
    flat_rows = [c for row in rows for c in row]
    return [
        *flat_rows,
        position_mm[0] / 1000.0,
        position_mm[1] / 1000.0,
        position_mm[2] / 1000.0,
        1.0, 0.0, 0.0, 0.0,
    ]


async def place_components_batch(
    adapter: Any,
    specs: list[dict[str, Any]],
    *,
    label: str = "batch",
) -> list[str]:
    """Insert many components in ONE ``AddComponents3`` call, then fix
    the grounded ones (``Select2`` each, then ONE ``FixComponent``) -- the COM-call-
    cheap path for repeated GROUNDED structure (cosmetic springs, shaft bushings)
    that carries no mates.

    Each ``spec`` is a dict:

      * ``part`` -- part stem (``<part>.SLDPRT`` under the part-output dir),
      * ``position`` -- origin (mm) in the pre-mirror machine frame,
      * ``rows`` -- rotation rows (images of the part X/Y/Z axes), pre-mirror,
      * ``rotation`` -- Euler angles (optional; carried only for parity with
        :func:`place_component`, the transform is built from ``rows``),
      * ``ground`` -- fix the component (default ``True``),
      * ``mirror`` -- route through ``mirror_placement`` (default ``True``),
      * ``label`` -- log label (optional).

    Why this is safe to batch where :func:`place_component` is not: these parts
    are GROUND (no mates) and inserted at an exact transform, so there is no mate
    flip to recover and no insertion-pose coupling -- the placement IS the final
    pose. The moving parts (rocker/rod/bar/lever) keep the per-part
    :func:`place_component` path because their insertion pose seeds mate
    flip-recovery (see ``_revolute`` / ``_pin_design_pose`` in the channel build).

    A read-back assert runs per component (reading the returned ``IComponent2``'s
    own ``Transform2``, with NO ``GetComponentByName`` round-trip): it matches each
    component to its spec by ORIGIN (bijective, so it tolerates ``AddComponents3``
    returning the array in a different order than ``Names`` rather than
    false-failing on identical repeated parts -- the 19 bushings), then asserts
    BOTH the translation and the rotation (``array[0:9]`` vs the spec's mirrored
    rows -- the same check the per-part ``assert_component_placed`` runs) so a
    misoriented or mislanded part fails loud immediately. The SAME origin match
    drives the per-spec ``ground`` flag and the returned ``Name2`` order, so a
    reorder can never fix/return the wrong component. Returns the component
    ``Name2`` list in ``specs`` order.

    The ``AddComponents3`` arrays cross the pywin32 late-binding boundary
    VARIANT-wrapped (the SAFEARRAY rule): ``VT_ARRAY|VT_BSTR``
    names/coord-system-names, ``VT_ARRAY|VT_R8`` transforms. The grounded
    components are then fixed via per-component ``Select2`` + one ``FixComponent``
    (see the selection block below for why not ``MultiSelect2``/``Select4``).
    """
    import pythoncom
    from win32com.client import VARIANT

    if not specs:
        return []

    names: list[str] = []
    transforms: list[float] = []
    finals: list[list[float]] = []  # final (mirrored) origin per spec, mm
    expected_rows: list[list[float]] = []  # final (mirrored) rotation, flat 9, per spec
    grounds: list[bool] = []
    for spec in specs:
        part = spec["part"]
        if spec.get("configuration"):
            raise RuntimeError(
                f"place_components_batch: per-component configuration "
                f"{spec['configuration']!r} unsupported (AddComponents3 places the "
                f"default config); use place_component for {part!r}"
            )
        position = list(spec["position"])
        rotation = list(spec.get("rotation", [0.0, 0.0, 0.0]))
        rows = [list(r) for r in spec["rows"]]
        if spec.get("mirror", True):
            position, rotation, rows = mirror_placement(part, position, rotation, rows, "")
        names.append(str(part_path(part)))  # raises if the .SLDPRT is missing
        transforms.extend(_placement_transform(rows, position))
        finals.append(position)
        expected_rows.append([c for row in rows for c in row])
        grounds.append(bool(spec.get("ground", True)))

    asm = adapter.currentModel
    _flag(asm, "IAssemblyDoc")
    names_arg = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, names)
    xforms_arg = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, transforms)
    coordsys_arg = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [""] * len(names))

    # COM-touching entry point -> open a span (AGENTS.md no-gap tracing invariant),
    # segmented into insert | readback+assert | fix child spans so the slow batch
    # op is never an unsegmented hole under the task span.
    out_names: list[str] = [""] * len(specs)
    grounded_comps: list[Any] = []
    async with _telemetry.aspan(
        f"batch {label}", count=len(specs), grounded=sum(grounds),
    ):
        with _telemetry.span("batch.insert", count=len(names)):
            raw = adapter._attempt(
                lambda: asm.AddComponents3(names_arg, xforms_arg, coordsys_arg),
                default=None,
            )
        if raw is None:
            raise RuntimeError(
                f"{label}: AddComponents3 returned None for {len(names)} components"
            )
        comps = list(raw) if isinstance(raw, (list, tuple)) else [raw]
        if len(comps) != len(specs):
            raise RuntimeError(
                f"{label}: AddComponents3 returned {len(comps)} components, "
                f"expected {len(specs)}"
            )
        _telemetry.debug(f"{label}: AddComponents3 inserted {len(comps)} components")

        # Match each returned component to its spec by ORIGIN (bijective, 0.5 mm
        # tol), then derive the ground flag + name + rotation assert from the
        # MATCHED spec. AddComponents3 may return the array in a different order
        # than Names, so zip(comps, specs) is unsafe: a reorder would fix the wrong
        # component (leaving the intended grounded one floating) and scramble
        # out_names. One Transform2 read/comp feeds the match AND the placement
        # assert (translation in [9:12] + rotation in [0:9], same check the per-part
        # assert_component_placed runs -- a bad AddComponents3 rotation/mirror
        # packing lands the origin right but the orientation wrong, e.g. spring
        # eye/threading pose). The pose is set at insert, so reading it before the
        # fix is correct (FixComponent only pins the current pose).
        #
        # NB: deliberately NO per-component _flag(comp, "IComponent2"). Flagging the
        # whole interface is 165 _FlagAsMethod GetIDsOfNames round-trips PER
        # component (~0.45 s each -> ~26 s for the 58-part bank) and we need none of
        # it: Name2/Transform2/ArrayData are property reads and Select2 is a method
        # called WITH args (late binding dispatches it as a method unambiguously, no
        # flag). Verified placing + selecting N/N with zero flagging.
        with _telemetry.span("batch.readback", count=len(comps)):
            used = [False] * len(specs)
            for comp in comps:
                array = [
                    float(v)
                    for v in _read_member(_read_member(comp, "Transform2"), "ArrayData")
                ]
                actual = [array[9] * 1000.0, array[10] * 1000.0, array[11] * 1000.0]
                best, best_i = float("inf"), -1
                for i, exp in enumerate(finals):
                    if used[i]:
                        continue
                    d = max(abs(a - e) for a, e in zip(actual, exp))
                    if d < best:
                        best, best_i = d, i
                if best_i < 0 or best > 0.5:
                    raise RuntimeError(
                        f"{label}: a component landed at "
                        f"{[round(v, 3) for v in actual]} matching no expected "
                        f"origin (nearest {best:.3f} mm > 0.5 mm tol)"
                    )
                rot_drift = max(
                    abs(a - e)
                    for a, e in zip(array[0:9], expected_rows[best_i], strict=True)
                )
                if rot_drift > 1e-3:
                    raise RuntimeError(
                        f"{label}: component at {[round(v, 3) for v in actual]} "
                        f"rotation {[round(v, 4) for v in array[0:9]]} != expected "
                        f"{[round(v, 4) for v in expected_rows[best_i]]} "
                        f"(drift {rot_drift:.4f})"
                    )
                used[best_i] = True
                out_names[best_i] = str(_read_member(comp, "Name2"))
                # Same save-time pose guarantee as the per-part path: batched
                # components (grounded or not) enter the ledger too (Codex,
                # 2026-07-05 -- the channel build batches ground=False banks).
                _POSE_LEDGER[out_names[best_i]] = (
                    list(finals[best_i]), list(expected_rows[best_i]),
                )
                if grounds[best_i]:
                    grounded_comps.append(comp)

        # Append every grounded component to the selection (IComponent2::Select2,
        # one cheap call per component -- no mate solve), then fix the WHOLE
        # selection in ONE FixComponent -> ONE solve, vs. one solve per part.
        # Select2 is called on each raw dispatch directly. The alternatives fail
        # under the adapter's forced late binding: MultiSelect2 silently selects 0
        # (a SAFEARRAY of late-bound dispatch wrappers does not marshal -- raw
        # _oleobj_ pointers raise "Type mismatch" too), and Select4 raises "Type
        # mismatch" on its ISelectData arg. Select2(Append, Mark) takes only
        # bool/int -- nothing to marshal -- so it is the late-binding-safe path.
        if grounded_comps:
            with _telemetry.span("batch.fix", grounded=len(grounded_comps)):
                adapter._attempt(lambda: asm.ClearSelection2(True), default=None)
                n_sel = sum(
                    1
                    for comp in grounded_comps
                    if adapter._attempt(lambda c=comp: c.Select2(True, 0), default=False)
                )
                if n_sel != len(grounded_comps):
                    raise RuntimeError(
                        f"{label}: Select2 selected {n_sel}/{len(grounded_comps)} "
                        f"grounded components"
                    )
                adapter._attempt(lambda: asm.FixComponent(), default=None)
                adapter._attempt(lambda: asm.ClearSelection2(True), default=None)

    _telemetry.success(
        f"{label}: inserted {len(specs)} components"
        f" (1x AddComponents3), fixed {len(grounded_comps)}"
        f" (Select2 + 1x FixComponent)"
    )
    return out_names


def assert_components_fully_defined(adapter: Any, *, resolve: bool = True) -> None:
    """Raise when any top-level component is neither fixed, fully defined,
    nor a pattern instance.

    ``IComponent2::GetConstrainedStatus`` returns swConstrainedStatus_e
    (2 = under, 3 = fully, 4 = over constrained). Component-pattern
    instances (chain pattern beads) report under-constrained even though
    the owning feature drives their transforms -- ``IsPatternInstance``
    exempts them; their actual positions are gate-asserted by the pattern
    creator. ``GetComponents`` hands back unflagged dispatches, so the
    IComponent2 methods must be flagged first or the call resolves as a
    property and raises.
    """
    asm = adapter.currentModel
    # Inserting/fixing a component marks the mate solver dirty: until the
    # assembly is rebuilt, GetConstrainedStatus returns a STALE swNoSolution
    # (5) for every mated part even though the mates are consistent and the
    # parts have not moved (probed live -- a ForceRebuild3 restores the true
    # status). Always re-solve before reading the gate.
    problems = []
    with _telemetry.span("gate.dof") as gsp:
        # Re-solve the mate solver before reading the gate (stale-status reason
        # above) -- the ForceRebuild3 is the bulk of the gate's wall-clock, so it
        # gets its own child span rather than sitting in an unspanned gap.
        # ``resolve=False``: the soundness suite already re-solved ONCE after open
        # (verify._verify_static_one) and does not mutate the model between gates,
        # so the rebuild here would be redundant -- skip it and just read status.
        with _telemetry.span("dof.resolve"):
            if resolve:
                adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
            components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
        gsp.set_attribute("components", len(components))
        log(f"checking {len(components)} components for free DOF ...")
        # NO span per component. A span per component floods the trace with one
        # near-instant (~50 ms) "OK" leaf span EACH -- 144 of them for `channel`,
        # 335 across a soundness pass -- drowning the few spans that carry signal.
        # The per-component status stays a debug log line (live console detail);
        # the gate.dof span carries the aggregate verdict (fixed / pattern /
        # offending counts), and any offender is named in the raised error, which
        # this gate's span records. Same de-noising as health.whats_wrong below.
        fixed = pattern = 0
        for component in components:
            # Flag ONLY the two zero-arg methods called below; Name2/IsFixed are
            # property reads (issue #87 -- not the 165-method IComponent2 flag).
            _flag_only(component, "IsPatternInstance", "GetConstrainedStatus")
            comp_name = str(_read_member(component, "Name2"))
            if bool(_read_member(component, "IsFixed")):
                fixed += 1
                log(f"{comp_name}: fixed")
                continue
            if bool(
                adapter._attempt(lambda c=component: c.IsPatternInstance(), default=False)
            ):
                pattern += 1
                log(f"{comp_name}: pattern instance (feature-driven)")
                continue
            status = int(
                adapter._attempt(lambda c=component: c.GetConstrainedStatus(), default=-1)
            )
            log(f"{comp_name}: constrained status {status}")
            if status != FULLY_CONSTRAINED:
                kind = "under" if status == UNDER_CONSTRAINED else f"status={status}"
                problems.append(f"{comp_name} ({kind})")
        gsp.set_attribute("fixed", fixed)
        gsp.set_attribute("pattern", pattern)
        gsp.set_attribute("not_fully_defined", len(problems))
        _telemetry.success(f"checked {len(components)} components for free DOF")
    if problems:
        raise RuntimeError("components not fully defined: " + ", ".join(problems))


# ---------------------------------------------------------------------------
# Park drivers -- freed-operational-DOF "reproducibility lock" mates
# ---------------------------------------------------------------------------
# A PARK driver pins one OPERATIONAL degree of freedom (e.g. the crank spin)
# purely so a fully-defined snapshot has a deterministic pose. In the default
# `free` build these freed-DOF drivers are NOT authored at all -- authoring each
# is an expensive mate solve that is only suppressed away again -- so the build
# is faster and the saved model leaves the DOF genuinely free (a working
# kinematic model). Instead each driver is RECORDED as a resolved spec
# (``free_dof_key`` on the ``*_driver`` helpers) and re-authored transiently by
# the release preflight (``preflight_release.py`` -> :func:`assert_park_closure`),
# which proves the drivers are the sole freedom then DISCARDS the model without
# saving. A `locked` build authors them engaged and renames each to a
# ``PARK_<key>`` feature (the fully-defined byte-reproducible snapshot).
#
# NB "freed-DOF park driver" (deferred here) is distinct from an ENGAGED setup
# driver held at a pose in the free model (e.g. the pinion-swing PARK on the
# drive-train): those do real work in the saved model, so they are authored as
# usual (plain ``mark_park_driver``), never deferred.
PARK_PREFIX = "PARK_"

# Deferral state (set once per build via :func:`set_park_defer`). When on, a
# ``*_driver`` call carrying a ``free_dof_key`` records its resolved spec into
# ``_PARK_SPECS`` instead of solving the mate.
_PARK_DEFER = False
_PARK_SPECS: list[dict[str, Any]] = []


def set_park_defer(defer: bool) -> None:
    """Enable/disable deferral of freed-operational-DOF park drivers and reset the
    recorded-spec buffer. Call once near the top of a build: ``set_park_defer(not
    LOCK)`` -- a ``free`` build defers+records, a ``locked`` build authors inline."""
    global _PARK_DEFER
    _PARK_DEFER = bool(defer)
    _PARK_SPECS.clear()


def park_deferred() -> bool:
    """True when freed-DOF park drivers are being deferred (a ``free`` build)."""
    return _PARK_DEFER


def collected_park_specs() -> list[dict[str, Any]]:
    """The park-driver specs recorded so far this build (a shallow copy)."""
    return list(_PARK_SPECS)


def _record_park_spec(
    key: str, kind: str, entities: list[Any],
    *, verify: tuple[str, list[float]] | None = None, flip: bool = False,
    **params: Any,
) -> None:
    """Record one deferred freed-DOF park driver as a machine-independent spec
    (entity refs by name + geometry-derived scalars + the resolved mate SIDE),
    for replay in the preflight.

    ``flip`` is the sign-derived seat side the driver helper already resolved
    (:func:`_seed_flip` for distance/spin drivers; ``False`` for angle drivers).
    Recording it lets :func:`replay_park_specs` re-author on the SAME side in one
    solve -- extending #185's flip-free seeding into the replay path, so the
    preflight park closure no longer leans on the flip-recovery net (the wire-
    swing replay hit a hard error-47 far-side add before this, 2026-07-05)."""
    _PARK_SPECS.append({
        "key": key,
        "kind": kind,
        "entities": [e.model_dump() for e in entities],
        "verify": [verify[0], [float(v) for v in verify[1]]] if verify else None,
        "flip": bool(flip),
        "params": {
            k: (float(v) if isinstance(v, (int, float)) else v)
            for k, v in params.items()
        },
    })
    _telemetry.debug(f"deferred PARK_{key}: {kind} recorded (not authored, flip={flip})")


async def _driver_or_defer(
    adapter: Any, kind: str, ref_a: Any, ref_b: Any,
    *, label: str, verify: tuple[str, list[float]] | None,
    free_dof_key: str | None, flip: bool = False, **params: Any,
) -> Any:
    """Author a driver mate, OR (freed-DOF key + deferral on) record it and skip.

    Returns the mate result dict when authored; a ``{"deferred_park": key}``
    sentinel when deferred. When a ``free_dof_key`` is authored (``locked`` build
    or a normal non-deferred run) the feature is renamed ``PARK_<key>`` so the
    tree documents it and the DOF gate can find it. ``flip`` seeds the authored
    mate's side (see :func:`_mate`) AND is recorded in the deferred spec, so the
    replay re-authors on the same resolved side (flip-free, like the build)."""
    if free_dof_key is not None and _PARK_DEFER:
        _record_park_spec(
            free_dof_key, kind, [ref_a, ref_b], verify=verify, flip=flip, **params)
        return {"deferred_park": free_dof_key, "name": ""}
    res = await _mate(
        adapter, label, kind, [ref_a, ref_b], verify=verify, flip=flip, **params
    )
    if free_dof_key is not None:
        await mark_park_driver(adapter, res, free_dof_key)
    return res


def park_spec_path(name: str) -> Any:
    """Sidecar path (next to ``<name>.SLDASM``) holding the deferred park-driver
    specs. ``name`` is the dashed assembly stem (``"drive-train"``)."""
    return OUT_SLDASM / f".{name}.park.json"


def write_park_specs(name: str) -> Any:
    """Persist this build's recorded park specs beside ``<name>.SLDASM`` (a doit
    assembly output that rides the remote cache). With nothing deferred (a
    ``locked`` build) any stale sidecar is removed and ``None`` returned."""
    path = park_spec_path(name)
    if not _PARK_SPECS:
        path.unlink(missing_ok=True)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"stem": name, "specs": _PARK_SPECS}, indent=2))
    _telemetry.success(
        f"wrote {len(_PARK_SPECS)} deferred park spec(s) -> {path.name}"
    )
    return path


def load_park_specs(name: str) -> list[dict[str, Any]]:
    """Read the deferred park specs for ``<name>.SLDASM`` (``[]`` if none)."""
    path = park_spec_path(name)
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("specs", [])


async def replay_park_specs(adapter: Any, specs: list[dict[str, Any]]) -> list[str]:
    """Author every recorded deferred park driver ENGAGED on the ACTIVE assembly
    and rename it ``PARK_<key>``; return the new names.

    Used by the release preflight (and the mobility/motion diagnostics) to
    reconstitute the freed operational DOF on a reopened default-``free`` model.
    Reconstructs each :class:`MateEntityRef` from the recorded fields, replays the
    exact mate on the RECORDED side (``spec["flip"]`` -- the build's sign-derived
    seat, #185), with the original flip-recovery ``verify`` target as the safety
    net, then re-solves."""
    from solidworks_mcp.adapters.base import MateEntityRef

    names: list[str] = []
    for spec in specs:
        entities = [MateEntityRef(**e) for e in spec["entities"]]
        verify = None
        if spec.get("verify"):
            verify = (spec["verify"][0], list(spec["verify"][1]))
        res = await _mate(
            adapter,
            f"replay PARK_{spec['key']}",
            spec["kind"],
            entities,
            verify=verify,
            flip=bool(spec.get("flip", False)),
            **spec.get("params", {}),
        )
        names.append(await mark_park_driver(adapter, res, spec["key"]))
    if names:
        adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    return names


async def mark_park_driver(adapter: Any, mate: Any, key: str) -> str:
    """Rename a just-created park-driver mate feature to ``PARK_<key>``.

    ``mate`` is the dict a ``*_driver`` helper returns (it carries the SW
    feature ``name``). Renaming uses ``IFeature::Name`` (a settable property)
    via the adapter's ``rename_feature`` -- which resolves mates through
    ``FeatureByName`` like ``delete_mate`` does. ``PARK_<key>`` must be unique
    in the tree (distinct keys) and free of SW-reserved characters. Returns the
    new name.
    """
    from solidworks_mcp.adapters.base import RenameFeatureParameters

    old = mate.get("name") if isinstance(mate, dict) else str(mate)
    if not old:
        raise RuntimeError(f"mark_park_driver: mate has no resolvable name ({mate!r})")
    new = f"{PARK_PREFIX}{key}"
    check(
        f"mark park driver {old!r} -> {new!r}",
        await adapter.rename_feature(RenameFeatureParameters(old_name=old, new_name=new)),
    )
    return new


async def find_park_drivers(adapter: Any) -> list[tuple[str, bool]]:
    """``(name, suppressed)`` for every top-level ``PARK_*`` mate of the active
    assembly (via ``list_mates``, which returns ``name``/``type``/``suppressed``)."""
    mates = check("list mates", await adapter.list_mates())
    return [
        (str(m["name"]), bool(m["suppressed"]))
        for m in mates
        if str(m["name"]).startswith(PARK_PREFIX)
    ]


BUILD_LOCK_MODES = ("free", "locked")


def is_locked_build(mode: str) -> bool:
    """``True`` for ``locked``, ``False`` for ``free``; raise on anything else.

    The ``build_lock`` flag is read in two places (the build script and verify);
    routing both through here means a typo (``Locked``/``lock``) fails LOUD at the
    point of use instead of silently degrading a pinned-snapshot request to a free
    build.
    """
    if mode not in BUILD_LOCK_MODES:
        raise RuntimeError(
            f"invalid build_lock mode {mode!r}; expected one of {BUILD_LOCK_MODES}"
        )
    return mode == "locked"


def _under_constrained_components(adapter: Any, *, resolve: bool = True) -> list[str]:
    """Re-solve and return the non-fixed, non-pattern top-level components that read
    UNDER-constrained (status 2) -- i.e. carry a real free DOF. Mirrors the status
    read in :func:`assert_components_fully_defined` but collects the free ones.

    ``resolve=False`` skips the rebuild when the caller already re-solved (the
    soundness suite's single shared rebuild)."""
    asm = adapter.currentModel
    if resolve:
        adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    under = []
    for component in components:
        _flag_only(component, "IsPatternInstance", "GetConstrainedStatus")
        comp_name = str(_read_member(component, "Name2"))
        if bool(_read_member(component, "IsFixed")):
            continue
        if bool(adapter._attempt(lambda c=component: c.IsPatternInstance(), default=False)):
            continue
        status = int(adapter._attempt(lambda c=component: c.GetConstrainedStatus(), default=-1))
        if status == UNDER_CONSTRAINED:
            under.append(comp_name)
    return under


async def assert_expected_free_dof(adapter: Any, expected_count: int) -> None:
    """Assert the assembly has EXACTLY ``expected_count`` free operational DOF,
    pinned only by suppressed ``PARK_*`` park-driver mates.

    The currently-suppressed ``PARK_*`` mates ARE the intended free DOF (each
    pins one). SolidWorks exposes no scalar DOF count, so the count is proven from
    BOTH sides -- necessity and sufficiency -- so neither a dead nor a redundant
    park driver can falsely certify a frozen model as kinematic:

    * NECESSITY (the free pose is genuinely free): in the as-built (suppressed)
      pose, at least ``expected_count`` top-level components read under-constrained.
      Suppressing a park driver that another mate already pins would free nothing,
      and this catches it -- the closure alone would not.
    * SUFFICIENCY / count (the drivers are the SOLE freedom): re-engage every park
      driver, re-solve, and assert the model is then fully defined (0
      under-constrained), so the true DOF count equals the number suppressed.

    The suppression state is ALWAYS restored (``finally``), leaving the model
    exactly as found (the as-built free pose) even if the closure check raises --
    so a caught failure never leaves later gates running against a locked/dirty
    model.

    ``expected_count == 0`` (a locked build, or an assembly with no parked DOF)
    has nothing to cycle and reduces to a plain
    :func:`assert_components_fully_defined`.
    """
    from solidworks_mcp.adapters.base import SuppressMateParameters

    asm = adapter.currentModel
    # This gate cycles EVERY park driver (suppress -> re-engage -> re-suppress),
    # each a COM round-trip, plus three ForceRebuild3s -- for `channel` that is
    # ~60 drivers, so the gate is minutes of wall-clock. Segment the phases into
    # named child spans (mirroring gate.dof/gate.health) so the waterfall shows
    # WHERE the time goes -- discovery vs the necessity read vs the two
    # suppress/re-suppress loops -- instead of one opaque multi-minute span.
    with _telemetry.span("gate.dof_expected_free") as gsp:
        with _telemetry.span("park.discover") as dsp:
            parked = await find_park_drivers(adapter)
            dsp.set_attribute("park_drivers", len(parked))
        free = [name for name, suppressed in parked if suppressed]
        gsp.set_attribute("park_drivers", len(parked))
        gsp.set_attribute("expected_free_dof", expected_count)
        gsp.set_attribute("free_dof", len(free))
        if len(free) != expected_count:
            raise RuntimeError(
                f"expected {expected_count} free DOF (suppressed {PARK_PREFIX}* mates) "
                f"but found {len(free)}: {sorted(free)}"
            )
        # NECESSITY: the as-built (suppressed) pose must actually carry the freedom.
        # One spin DOF frees a whole chain, so >= expected_count under-constrained.
        if expected_count:
            with _telemetry.span("park.necessity") as nsp:
                free_under = _under_constrained_components(adapter)
                nsp.set_attribute("free_under_constrained", len(free_under))
            gsp.set_attribute("free_under_constrained", len(free_under))
            if len(free_under) < expected_count:
                raise RuntimeError(
                    f"expected >= {expected_count} under-constrained component(s) in the "
                    f"free pose after suppressing {sorted(free)} but found "
                    f"{len(free_under)}: suppressing the park driver(s) freed nothing -- "
                    "another mate still pins the DOF (the 'free' model is actually frozen)"
                )
        # SUFFICIENCY: re-engage the park drivers and prove the model is then rigid,
        # ALWAYS restoring the as-built free pose (suppress moves no part).
        try:
            with _telemetry.span("park.engage") as esp:
                esp.set_attribute("drivers", len(free))
                for name in free:
                    check(
                        f"unsuppress {name}",
                        await adapter.suppress_mate(SuppressMateParameters(name=name, suppress=False)),
                    )
                adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
            assert_components_fully_defined(adapter)  # 0 under-constrained, drivers engaged
        finally:
            with _telemetry.span("park.restore") as rsp:
                rsp.set_attribute("drivers", len(free))
                for name in free:
                    check(
                        f"re-suppress {name}",
                        await adapter.suppress_mate(SuppressMateParameters(name=name, suppress=True)),
                    )
                adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
        _telemetry.success(
            f"{len(free)} free DOF confirmed (necessity: free pose under-constrained; "
            f"sufficiency: re-engaged {len(free)} park driver(s) -> 0 under-constrained); "
            "restored free pose"
        )


def assert_free_dof_necessity(
    adapter: Any,
    expected_count: int,
    *,
    resolve: bool = True,
    required_stems: tuple[str, ...] = (),
) -> None:
    """Build/soundness DOF gate for a default-``free`` model whose freed park
    drivers are DEFERRED (not authored -- see the Park drivers section).

    Because the park mates do not exist in the saved model there is nothing to
    re-engage, so this proves only NECESSITY: at least ``expected_count`` top-level
    components read under-constrained, i.e. the operational DOF genuinely ARE free
    (a mate did not silently freeze one). The exact-count SUFFICIENCY proof --
    author the drivers -> 0 DOF -- moves to the release preflight
    (:func:`assert_park_closure`), which is where the recorded specs exist. This is
    the deliberate build-time/release-time split: a fast build stays fast (no park
    solves on every run), the strict closure runs at release (opt-in, infrequent).

    The aggregate count alone cannot tell WHICH DOF is free -- the crank spin
    alone under-constrains several crank-chain components, so a count check
    passes even with a second freed DOF accidentally pinned (codex review
    2026-07-04). ``required_stems`` therefore names one component family per
    freed DOF (instance suffixes stripped) that MUST read under-constrained.

    ``expected_count == 0`` reduces to :func:`assert_components_fully_defined`.
    ``resolve=False`` skips the rebuild (soundness re-solved once after open)."""
    if expected_count == 0:
        assert_components_fully_defined(adapter, resolve=resolve)
        return
    with _telemetry.span("gate.dof_free_necessity") as gsp:
        under = _under_constrained_components(adapter, resolve=resolve)
        gsp.set_attribute("expected_free_dof", expected_count)
        gsp.set_attribute("free_under_constrained", len(under))
        if len(under) < expected_count:
            raise RuntimeError(
                f"expected >= {expected_count} free operational DOF but only "
                f"{len(under)} component(s) read under-constrained: {sorted(under)} "
                "-- a deferred park driver's DOF is pinned by another mate, or the "
                "model is over-constrained (the 'free' model is actually frozen)"
            )
        if required_stems:
            present = {re.sub(r"-\d+$", "", n) for n in under}
            missing = [s for s in required_stems if s not in present]
            gsp.set_attribute("required_stems", ",".join(required_stems))
            if missing:
                raise RuntimeError(
                    f"free-DOF necessity: required famil(ies) {missing} read fully "
                    f"defined -- that freed DOF is pinned. Under-constrained: "
                    f"{sorted(under)}"
                )
        _telemetry.success(
            f"{len(under)} under-constrained component(s) >= {expected_count} expected "
            "free DOF (necessity; sufficiency proven in the release preflight)"
        )


async def assert_park_closure(
    adapter: Any, specs: list[dict[str, Any]], expected_count: int
) -> None:
    """Release-preflight SUFFICIENCY gate: on a reopened default-``free`` model,
    prove the deferred park drivers are the SOLE freedom.

    * NECESSITY: the spec count equals ``expected_count`` and, before authoring,
      at least ``expected_count`` top-level components read under-constrained (the
      freedom really is present in the shipped free model).
    * SUFFICIENCY: :func:`replay_park_specs` authors every recorded driver engaged
      and re-solves; the model must then be fully defined (0 under-constrained), so
      the true free-DOF count equals the number of drivers.

    The caller MUST discard the document WITHOUT saving -- this mutates the
    in-memory model (authoring real mates), and the shipped ``.SLDASM`` must stay
    the free kinematic model."""
    with _telemetry.span("gate.park_closure") as gsp:
        gsp.set_attribute("expected_free_dof", expected_count)
        gsp.set_attribute("specs", len(specs))
        if len(specs) != expected_count:
            raise RuntimeError(
                f"park spec count {len(specs)} != expected free DOF {expected_count} "
                "-- the recorded specs disagree with the configured free-DOF count "
                "(rebuild the assembly)"
            )
        under = _under_constrained_components(adapter)
        gsp.set_attribute("free_under_constrained", len(under))
        if len(under) < expected_count:
            raise RuntimeError(
                f"expected >= {expected_count} under-constrained component(s) in the "
                f"free pose but found {len(under)}: {sorted(under)} -- the shipped "
                "model is already frozen (the deferred park drivers freed nothing)"
            )
        names = await replay_park_specs(adapter, specs)
        gsp.set_attribute("authored", len(names))
        # SUFFICIENCY: with every driver engaged the model must be rigid.
        assert_components_fully_defined(adapter)
        _telemetry.success(
            f"park closure OK: {len(under)} free -> authored {len(names)} PARK_* "
            "driver(s) -> 0 under-constrained (sufficiency); model NOT saved"
        )


def component_names(adapter: Any) -> list[str]:
    """Top-level component names (``Name2``) of the active assembly."""
    asm = adapter.currentModel
    components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    names = []
    for component in components:
        # No flag: Name2 is a property read (issue #87).
        names.append(str(_read_member(component, "Name2")))
    return names

def check_no_interference(adapter: Any) -> None:
    """Run interference detection on the active assembly; raise on any hit.

    Raw-COM stopgap until the MCP adapter implements ``check_interference``
    (``IAssemblyDoc::InterferenceDetectionManager``; the tool-layer call
    currently returns a simulated result without adapter support).
    Coincident/tangent contact is not treated as interference.

    Chain-internal contact (a pair of roller-chain links touching each other)
    is allowed and reported separately, not raised: a chain is an articulating
    connected mechanism whose links are in contact at every joint, so on the
    tight wraps the rigid links unavoidably touch their neighbours (the same
    way the gate already tolerates face-flush and tangent contacts). Any link
    touching a NON-link part is still a hard fault.
    """
    asm = adapter.currentModel
    with _telemetry.span("gate.interference") as isp:
        log("interference detection: starting ...")
        _flag(asm, "IAssemblyDoc")
        adapter._attempt(lambda: asm.ToolsCheckInterference(), default=None)
        mgr = _read_member(asm, "InterferenceDetectionManager")
        if mgr is None:
            raise RuntimeError("InterferenceDetectionManager unavailable")
        _flag(mgr, "IInterferenceDetectionMgr")
        mgr.TreatCoincidenceAsInterference = False
        mgr.TreatSubAssembliesAsComponents = True
        mgr.IncludeMultibodyPartInterferences = True
        mgr.MakeInterferingPartsTransparent = False
        mgr.CreateFastenersFolder = False
        mgr.UseTransform = False
        with _telemetry.span("interference.compute"):
            log("interference detection: computing interferences ...")
            interferences = adapter._attempt(lambda: mgr.GetInterferences(), default=None)
        details = []
        chain_contacts = []
        for interference in list(interferences or []):
            _flag(interference, "IInterference")
            names = []
            for comp in list(_read_member(interference, "Components") or []):
                # No flag: Name2 is a property read (issue #87).
                names.append(str(_read_member(comp, "Name2")))
            volume_mm3 = float(_read_member(interference, "Volume") or 0.0) * 1e9
            if all(n.startswith(_CHAIN_LINK_PREFIXES) for n in names) and len(names) == 2:
                chain_contacts.append(volume_mm3)
                continue
            details.append(f"{' & '.join(names)}: {volume_mm3:.2f} mm^3")
        adapter._attempt(lambda: mgr.Done(), default=None)
        isp.set_attribute("hits", len(details))
        isp.set_attribute("chain_contacts", len(chain_contacts))
        if chain_contacts:
            _telemetry.debug(
                f"{len(chain_contacts)} chain-internal link contacts"
                f" (<= {max(chain_contacts):.2f} mm^3) allowed -- articulating chain"
            )
        if details:
            raise RuntimeError(
                f"{len(details)} interference(s): " + "; ".join(details)
            )
        _telemetry.success("interference check: none found")

def _byref_variant() -> Any:
    """An in/out ``VT_BYREF | VT_VARIANT`` for ``out object`` COM params.

    ``IModelDocExtension::GetWhatsWrong`` takes three ``out object`` arrays;
    under pywin32 late binding a bare call RAISES and bare ``None`` mis-types.
    Mirrors :func:`com_variant.byref_long`; read the filled value via ``.value``.
    """
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_VARIANT, None)

def whats_wrong(adapter: Any, model: Any) -> list[tuple[str, int, bool]]:
    """Return ``[(feature_name, error_code, is_warning), ...]`` for a model.

    Reads the What's Wrong dialog via ``GetWhatsWrong`` (byref out-params).
    Empty when the model is clean or the call is unavailable.
    """
    ext = _read_member(model, "Extension")
    if ext is None:
        return []
    f, e, w = _byref_variant(), _byref_variant(), _byref_variant()

    def _call() -> tuple[Any, Any, Any]:
        ext.GetWhatsWrong(f, e, w)
        return f.value, e.value, w.value

    res = adapter._attempt(_call, default=None)
    if not res:
        return []
    feats, codes, warns = res
    feats = list(feats or [])
    codes = list(codes or [])
    warns = list(warns or [])
    out: list[tuple[str, int, bool]] = []
    for i, feat in enumerate(feats):
        name = "?"
        if feat is not None:
            _flag(feat, "IFeature")
            name = str(_read_member(feat, "Name"))
        code = int(codes[i]) if i < len(codes) else -1
        warn = bool(warns[i]) if i < len(warns) else False
        out.append((name, code, warn))
    return out

_REBUILD_UNSET: Any = object()


def assert_model_healthy(
    adapter: Any, *, label: str = "", model: Any = None, deep: bool = True,
    rebuilt: Any = _REBUILD_UNSET,
) -> None:
    """Force-rebuild and raise on any ERROR-state feature/mate -- fail fast.

    The motion build mutates the assembly (float, flexible, suppress, cross-sub
    mates, motor); a single failed step leaves a component with a red rebuild
    error (the drive-train red-X) that otherwise survives silently into the
    study and only surfaces as garbage motion. This names the culprit the
    instant it appears.

    A non-warning What's Wrong entry, or ``ForceRebuild3`` returning False, is a
    hard fault and raises. Warnings (under-defined flexible subs, etc.) are
    logged, not raised. With ``deep`` each top-level component's own document is
    also checked -- a flexible subassembly's internal mate error does NOT appear
    in the parent's What's Wrong, only in the sub document's.
    """
    model = model or adapter.currentModel
    _flag(model, "IModelDoc2")
    with _telemetry.span("gate.health", label=label or "top", deep=deep) as hsp:
        # The deep ForceRebuild3 + sub-document collection is the bulk of the
        # gate's wall-clock; span it so it is not an unspanned leading gap before
        # the per-target whats_wrong checks.
        with _telemetry.span("health.rebuild"):
            # ``rebuilt`` may be supplied by a caller that already re-solved this
            # model (the soundness suite's single shared rebuild); only
            # ForceRebuild3 here when it was NOT (standalone/build/motion callers).
            # A False result -- from either path -- is still a hard health fault.
            if rebuilt is _REBUILD_UNSET:
                rebuilt = adapter._attempt(lambda: model.ForceRebuild3(False), default=None)

            targets = [(label or "top", model)]
            if deep:
                comps = adapter._attempt(lambda: model.GetComponents(False), default=None) or []
                for comp in comps:
                    # Flag ONLY GetModelDoc2 (zero-arg); Name2 is a property
                    # read (issue #87 -- not the 165-method IComponent2 flag).
                    _flag_only(comp, "GetModelDoc2")
                    name = str(_read_member(comp, "Name2"))
                    if "/" in name:  # top-level instances only; their docs cover nested parts
                        continue
                    sub = adapter._attempt(lambda c=comp: c.GetModelDoc2(), default=None)
                    if sub is not None and sub is not model:
                        targets.append((name, sub))

        errors: list[str] = []
        warnings: list[str] = []
        # ONE span around the WHOLE What's Wrong sweep, not one per target. A span
        # per target floods the trace with up to N (144 for `channel`, 343 across a
        # soundness pass) near-instant "OK" leaf spans printed back-to-back -- the
        # "multiple whats_wrong calls in sequence" noise. The target count is an
        # attribute; any real error/warning is surfaced in the log + raised error.
        with _telemetry.span("health.whats_wrong", targets=len(targets)) as wsp:
            for tlabel, doc in targets:
                for name, code, warn in whats_wrong(adapter, doc):
                    entry = f"{tlabel}:{name} [{_FEATURE_ERROR.get(code, code)}]"
                    (warnings if warn else errors).append(entry)
            wsp.set_attribute("errors", len(errors))
            wsp.set_attribute("warnings", len(warnings))
        if rebuilt is False:
            errors.append(f"{label or 'top'}: ForceRebuild3 returned False")

        hsp.set_attribute("targets", len(targets))
        hsp.set_attribute("warnings", len(warnings))
        hsp.set_attribute("errors", len(errors))
        if warnings:
            _telemetry.warn(
                f"{len(warnings)} health warning(s): " + "; ".join(warnings[:12])
            )
        if errors:
            raise RuntimeError(
                f"model unhealthy ({label or 'top'}): {len(errors)} error(s) -- "
                + "; ".join(errors[:20])
            )
        _telemetry.success(f"model healthy ({label or 'top'})")

def body_faults(adapter: Any, model: Any) -> list[tuple[str, int]]:
    """Return ``[(body_name, fault_count), ...]`` for any faulty solid bodies.

    ``IBody2.Check3`` -> ``IFaultEntity`` flags degenerate geometry (touching
    edge vertices, sub-tolerance faces/edges, poorly defined curves) that a
    rebuild can leave behind after a boolean on a near-singular feature -- the
    on-axis-revolve / 0.00 mm^3 sliver failure class. Catches part-level
    corruption that What's Wrong (feature/mate state) does not. Empty = clean.
    """
    bodies = adapter._attempt(lambda: model.GetBodies2(0, False), default=None)
    if bodies is None:
        return []
    if not isinstance(bodies, (list, tuple)):
        bodies = [bodies]
    faults: list[tuple[str, int]] = []
    for body in bodies:
        if body is None:
            continue
        _flag(body, "IBody2")
        fault = adapter._attempt(lambda b=body: b.Check3, default=None)
        if fault is None:
            continue
        _flag(fault, "IFaultEntity")
        count = int(_read_member(fault, "Count") or 0)
        if count > 0:
            faults.append((str(_read_member(body, "Name")), count))
    return faults

def remap_front_to_machine_front(adapter: Any) -> None:
    """Redefine the active document's standard views so SolidWorks ``Front``
    shows the MACHINE front (the paper/output side at -Z).

    The machine is authored in machine coordinates with the output side at -Z
    (see build_harmonic_analyzer_assembly), so SolidWorks' native Front view --
    which looks toward -Z from the +Z side -- renders the BACK. The machine front
    is exactly what SolidWorks currently calls the Back view (camera on the -Z
    side, crank at the viewer's right). ``IModelDocExtension.UpdateStandardViews``
    re-bases the whole orthographic set so that orientation becomes Front; NO
    geometry moves, so the comparison-render euler azimuth convention (az 0 = +Z)
    is untouched -- only the named standard views and the interactive open-on-Front
    change. Leaves Front active so the saved document opens on the machine front.
    """
    SW_FRONT, SW_BACK = 1, 2  # swStandardViews_e
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    model.ShowNamedView2("", SW_BACK)  # orient to the machine front
    ok = model.Extension.UpdateStandardViews("", SW_FRONT)
    if not ok:
        raise RuntimeError("UpdateStandardViews(swFrontView) returned False")
    model.ShowNamedView2("", SW_FRONT)  # activate the (now machine-front) Front
    adapter._zoom_to_fit(model)
    log("standard views remapped: Front now shows the machine front (-Z paper side)")

async def _export_assembly_images(
    adapter: Any, asm_name: str, views: Iterable[str]
) -> dict[str, str]:
    """Export PNG views to ``cad/out/png/<asm>`` (gitignored build output).

    Factored out of :func:`save_assembly_and_images` so the refresh primitive
    (:func:`refresh_assembly`) shares the exact same export tail. Returns
    ``{<view>: path}``; the caller adds the assembly path.

    Does NOT touch the committed ``docs/images`` README renders -- those are
    refreshed deliberately via ``python cad/scripts/trim_renders.py`` and
    committed on purpose, so a model build never dirties a tracked file (which
    would otherwise block ``doit release``'s clean-tree preflight).
    """
    png_dir = OUT_PNG / asm_name
    png_dir.mkdir(parents=True, exist_ok=True)
    artefacts: dict[str, str] = {}
    views = list(views)
    async with _telemetry.aspan("export_images", count=len(views)):
        for view in views:
            img_path = (png_dir / f"{asm_name}_{view}.png").resolve()
            async with _telemetry.aspan("export_image", view=view):
                check(
                    f"export_image {view}",
                    await adapter.export_image(
                        {
                            "file_path": str(img_path),
                            "format_type": "png",
                            "width": 1600,
                            "height": 1000,
                            "view_orientation": view,
                        }
                    ),
                )
            artefacts[view] = str(img_path)

    return artefacts

async def save_assembly_and_images(
    adapter: Any, asm_name: str, views: Iterable[str] = DEFAULT_VIEWS
) -> dict[str, str]:
    """Save the assembly to ``cad/out/sldasm`` and PNG views to ``cad/out/png``."""
    # Fail fast: never save a broken assembly. Catches mate errors (e.g. a gear
    # mate whose entity went suppressed = the silent drive-train corruption) that
    # the DOF and interference gates miss -- a fixed/grounded component passes
    # the DOF gate even with broken mates. deep=True also inspects each
    # subassembly's own document, where a sub's internal mate errors live.
    assert_model_healthy(adapter, label=asm_name, deep=True)
    # ... and never save a solver-drifted one: every placed component must
    # still sit at its authored pose after the FINAL solve (see _POSE_LEDGER).
    assert_pose_ledger(adapter)
    OUT_SLDASM.mkdir(parents=True, exist_ok=True)
    asm_path = (OUT_SLDASM / f"{asm_name}.SLDASM").resolve()
    # Save on isometric so the .SLDASM opens isometric; runs AFTER any
    # remap_front_to_machine_front (which re-bases the standard views) so the
    # re-based Front/Back/etc. used by the gallery stay correct.
    set_isometric_view(adapter)
    check(f"save_file -> {asm_path}", await adapter.save_file(str(asm_path)))
    # Record the resolved-geometry fingerprint of the just-built assembly so a later
    # in-place refresh of it (unchanged) is a true no-op and never bumps the md5 --
    # otherwise the first refresh after a from-scratch build would re-save once and
    # cascade up the tree (see save_assembly_in_place / _massprops_sidecar).
    digest = await assembly_geometry_digest(adapter, asm_name)
    sidecar = _massprops_sidecar(asm_name)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(digest + "\n", encoding="utf-8")

    artefacts = {"assembly": str(asm_path)}
    artefacts.update(await _export_assembly_images(adapter, asm_name, views))
    return artefacts

def _massprops_sidecar(asm_name: str):
    """Sidecar holding the last-saved resolved-geometry fingerprint of an assembly.

    A parent assembly's doit dependency on a child is the child ``.SLDASM``'s md5,
    and SolidWorks rewrites a ``.SLDASM`` with fresh save metadata (new bytes -> new
    md5) on EVERY in-place save. So an unconditional re-save of an *unchanged*
    assembly bumps its md5 and spuriously invalidates the parent, which then
    re-saves and invalidates ITS parent -- a no-op "reconciliation" refresh that
    cascades up the whole tree one level per ``doit`` run (the post-release
    not-a-no-op). Gating the re-save on a real change to THIS fingerprint keeps a
    no-op refresh byte-stable, so the build reaches a true fixpoint. Lives under the
    gitignored ``cad/out/sldasm`` next to the recipe sidecar."""
    return OUT_SLDASM / f".{asm_name}.massprops.sha"


async def assembly_geometry_digest(adapter: Any, asm_name: str) -> str:
    """A deterministic fingerprint of an assembly's RESOLVED geometry across every
    configuration: exact-BREP mass properties (mass / volume / surface area / centre
    of mass / moments of inertia). It changes iff a component's geometry changed and
    is immune to SolidWorks' volatile save metadata (unlike the ``.SLDASM`` bytes) and
    to tessellation noise (unlike an STL hash). Leaves the doc on the rest pose.

    Used to decide whether an in-place refresh actually changed anything: a part edit
    that re-solves the assembly shifts the mass properties (so the parent must rebuild
    -> bump the md5), while a pure reload of unchanged parts does not (keep the file
    byte-stable -> no phantom cascade).

    Why NOT hash the referenced part files instead (codex review on #83): a
    from-scratch part rebuild regenerates the part's persistent reference IDs, so its
    ``.SLDPRT`` bytes differ for byte-IDENTICAL geometry (observed: pivot-shaft
    61710 -> 61000 B on a no-change rebuild). A content-hash key would therefore flag
    every PID-churn-only rebuild as "changed" and force-save -> the very parent-md5
    cascade this fingerprint exists to suppress. A geometry-derived key is the point.

    Known residual gap (accepted, narrow): a part-APPEARANCE-only edit (a part-level
    display colour with no geometry change) leaves these values fixed, so it does not
    bump the .SLDASM md5. The immediate assembly still re-renders (refresh always
    re-exports its PNGs), but ANCESTOR renders won't auto-regenerate. In practice the
    colours that matter are applied at assembly scope via ``apply_component_color``
    (the FULL path -> recipe change -> save), so this only bites a bare part recolour;
    force a rebuild (delete the .SLDASM target) if one must propagate up."""
    configs = check("list configurations", await adapter.list_configurations())
    rest = "Default" if "Default" in configs else (configs[0] if configs else None)
    # Only switch configs for a genuinely multi-config assembly. A config switch
    # regenerates the whole model (~80-160 s each on the 122-component top), so for
    # the single-config case (the rest pose is already active after the gates) we
    # read mass properties in place and never activate/re-activate.
    multi = len(configs) > 1
    rows: list[Any] = []
    for cfg in configs:
        if multi:
            check(f"activate {cfg}", await adapter.set_active_configuration(cfg))
        res = await adapter.get_mass_properties()
        if not res.is_success:
            raise RuntimeError(
                f"{asm_name}: get_mass_properties failed for config {cfg!r}: "
                f"{res.error}")
        mp = res.data
        moi = mp.moments_of_inertia
        rows.append((
            cfg,
            round(float(mp.mass), 6),
            round(float(mp.volume), 3),
            round(float(mp.surface_area), 3),  # catches edits that preserve mass+volume+inertia
            tuple(round(float(c), 4) for c in mp.center_of_mass),
            tuple(round(float(moi[k]), 4)
                  for k in ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")),
        ))
    if multi and rest is not None:
        check(f"re-activate {rest}", await adapter.set_active_configuration(rest))
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()


def save_assembly_in_place(adapter: Any, asm_name: str, geometry_changed: bool) -> None:
    """Save ``<asm_name>.SLDASM`` in place with a silent ``ModelDoc2.Save3``.

    For an assembly OPENED from its own path (a refresh or a config-hook reopen)
    the active doc IS the file, so the correct save is an in-place
    ``Save3(swSaveAsOptions_Silent | AvoidRebuildOnSave, &err, &warn)`` -- NOT the
    adapter's ``save_file``, both of whose branches are wrong for an
    opened-in-place doc:

      * ``save_file(PATH)`` -> SaveAs branch does ``CloseDoc(PATH)`` +
        ``os.remove(PATH)`` before ``SaveAs3``; when the active doc IS that path
        this disconnects the doc and deletes the file -- it destroyed
        drive-train.SLDASM twice.
      * ``save_file()`` (no path) -> ``Save3(1, None, None)``; ``None`` for the
        two [out] byref params fails the COM call, so it falls through to the
        blocking parameterless ``Save()`` "Component documents must be saved"
        modal.

    Passing the two [out] params as real pywin32 BYREF VARIANTs makes ``Save3``
    write silently and return the error/warning codes. The option mask is
    ``swSaveAsOptions_Silent (1) | swSaveAsOptions_AvoidRebuildOnSave (8)`` -- the
    canonical bitmask, NOT ``SaveReferenced`` (which is **4**, long mislabeled as 8
    here and in the MCP adapter's ``io.py``): ``Silent`` suppresses the save
    dialogs; ``AvoidRebuildOnSave`` skips the redundant save-time rebuild (the
    health/DOF/interference gates already ``ForceRebuild3``'d the model, so the
    in-memory geometry is current) and thereby avoids a save-triggered rebuild
    re-dirtying the referenced parts. ``SaveReferenced`` (4) is DELIBERATELY
    omitted: the referenced ``.SLDPRT``/sub-``.SLDASM`` files are the authoritative
    outputs of their own ``part:``/``assembly:`` tasks, and an assembly save must
    never rewrite them -- that is the parent-md5 byte-churn the build-idempotency
    keying in ``dodo.ContentChecker`` exists to neutralise. The mtime assertion
    proves the file was rewritten (never deleted). Proven by
    ``repro_inplace_save.py`` (ret=True, err=0, warn=0, the active config persists
    on reopen).

    ``geometry_changed`` gates the bump. Every in-place ``Save3`` rewrites fresh
    save metadata -> a new md5, and the parent's doit dep is this file's md5, so an
    unconditional save of an UNCHANGED assembly spuriously invalidates the parent
    and cascades a no-op reconciliation refresh up the tree (see
    ``_massprops_sidecar``). When the resolved-geometry fingerprint is unchanged we
    therefore skip the save outright, leaving the ``.SLDASM`` byte-identical so the
    parent stays valid. When it changed we force the rewrite even if SolidWorks
    reports the doc clean (a reload of changed PART geometry leaves the assembly's
    own data -- component refs + mates + transforms -- untouched, so ``GetSaveFlag``
    can read false): ``SetSaveFlag`` + ``Save3`` push the new geometry's md5 to the
    parent (codex review #5).
    """
    import pythoncom
    from win32com.client import VARIANT

    asm = adapter.currentModel
    sldasm = OUT_SLDASM / f"{asm_name}.SLDASM"
    if not geometry_changed:
        # No-op refresh: resolved geometry identical to the last save. Do NOT
        # rewrite -- a fresh md5 here would invalidate the parent for nothing.
        log(f"{sldasm.name}: geometry unchanged -- .SLDASM left intact (no md5 bump)")
        return

    if not bool(adapter._attempt(lambda: asm.GetSaveFlag(), default=True)):
        log(f"{sldasm.name} reported clean -- forcing rewrite for md5 propagation")
        adapter._attempt(lambda: asm.SetSaveFlag(), default=None)

    before = sldasm.stat().st_mtime
    err = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warn = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    options = 1 | 8  # swSaveAsOptions_Silent | swSaveAsOptions_AvoidRebuildOnSave
    ret = adapter._attempt(lambda: asm.Save3(options, err, warn), default=False)

    after = sldasm.stat().st_mtime
    if after <= before:
        raise RuntimeError(
            f"{sldasm.name} mtime unchanged after Save3(Silent) "
            f"(ret={ret}, err={err.value}, warn={warn.value})")
    log(f"saved {sldasm.name} via Save3(Silent) (ret={ret}, err={err.value}, "
        f"warn={warn.value})")

def _rebuild_faults(adapter: Any) -> list[str]:
    """Non-warning What's Wrong entries for the active model, formatted for a log."""
    return [
        f"{name} [{_FEATURE_ERROR.get(code, code)}]"
        for name, code, warn in whats_wrong(adapter, adapter.currentModel)
        if not warn
    ]


def select_mates_folder(adapter: Any) -> bool:
    """Select the active assembly's Mates folder -- the precondition for
    ``IAssemblyDoc.AutoMateRepair``. The folder is a ``MateGroup`` feature that sits
    at/near the END of the top-level tree, so scan from the back (a couple of COM
    round-trips) instead of walking all ~150 component features forward (~50 s).
    Falls back to a full forward walk if an in-context feature pushed it off the
    tail."""
    model = adapter.currentModel
    count = int(adapter._attempt(lambda: model.GetFeatureCount(), default=0) or 0)
    for i in range(min(count, 8)):  # MateGroup is the last top-level feature (i=0)
        feat = adapter._attempt(lambda i=i: model.FeatureByPositionReverse(i), default=None)
        if feat is None:
            continue
        _flag(feat, "IFeature")
        if str(adapter._attempt(lambda f=feat: f.GetTypeName2(), default="")) == "MateGroup":
            return bool(adapter._attempt(lambda f=feat: f.Select2(False, 0), default=False))
    feat = adapter._attempt(lambda: model.FirstFeature(), default=None)
    while feat is not None:
        _flag(feat, "IFeature")
        if str(adapter._attempt(lambda f=feat: f.GetTypeName2(), default="")) == "MateGroup":
            return bool(adapter._attempt(lambda f=feat: f.Select2(False, 0), default=False))
        feat = adapter._attempt(lambda f=feat: f.GetNextFeature(), default=None)
    return False


def repair_dangling_mates(adapter: Any) -> int:
    """Auto-heal mates whose referenced topology was re-IDed by a from-scratch part
    rebuild (the "sharp edge"): ``IAssemblyDoc.AutoMateRepair`` re-binds the broken
    mates in place (~5 s) instead of a ~500 s full re-insert/re-mate.

    Returns the count AutoMateRepair reports as repaired. Its own return code is
    ADVISORY ONLY -- it returns PartialSuccess with a large FailedMates array (the
    assembly's already-valid mates, which it cannot "re-repair") even on a fully
    successful heal -- so the CALLER must judge success from a fresh ``whats_wrong``
    + the standard DOF/interference/health gates, never from this code.
    """
    asm = adapter.currentModel
    _flag(asm, "IAssemblyDoc")
    if not select_mates_folder(adapter):
        log("AutoMateRepair: could not select the Mates folder -- skipping repair")
        return 0
    processed, failed = _byref_variant(), _byref_variant()
    ret = adapter._attempt(lambda: asm.AutoMateRepair(processed, failed), default=-1)
    n_proc = len(list(processed.value or [])) if processed.value is not None else 0
    n_fail = len(list(failed.value or [])) if failed.value is not None else 0
    log(f"AutoMateRepair: ret={ret} (1=PartialSuccess is normal) "
        f"re-bound {n_proc} mate(s), {n_fail} already-valid skipped")
    return n_proc


async def refresh_assembly(
    adapter: Any, asm_name: str, views: Iterable[str] = DEFAULT_VIEWS
) -> dict[str, str]:
    """Reload an assembly's parts in place -- the cheap incremental rebuild.

    A ``.SLDASM`` is a thin reference layer over its part files (component refs +
    mates + transforms, not baked geometry), so when only a referenced
    ``.SLDPRT``/sub-``.SLDASM`` changed, reopening the assembly + per-config
    ``ForceRebuild3`` loads the new geometry WITHOUT re-inserting/re-mating the
    ~122 components a from-scratch ``create_assembly`` costs (~500 s). This is the
    cheap path of the incremental build graph (see ``dodo.py``).

    Self-healing, then fail loud. Every configuration is force-rebuilt. A
    non-warning What's Wrong fault -- typically a mate dangled because a
    from-scratch part rebuild re-IDed the face it selected -- first triggers an
    in-place ``AutoMateRepair`` (the broken mates re-bind in ~5 s instead of a
    ~500 s full re-insert/re-mate); only if the re-read is STILL faulted does the
    refresh raise, naming the config + the broken feature/mate. Then the
    rest/export pose is re-activated and the
    standard gates run: ``assert_components_fully_defined`` (free DOF),
    ``check_no_interference`` (overlaps), ``assert_model_healthy`` (deep mate
    health). Any gate raises a ``RuntimeError`` naming the culprit and the
    ``.SLDASM`` is left untouched (the in-place save never runs) -- so an
    UNHEALABLE dangling mate (AutoMateRepair could not re-bind it) or a geometry
    change that grows into a neighbour (interference) HALTS the build rather than
    saving a stale/broken artefact. The caller escalates to a full from-scratch
    rebuild via the ``full`` escape (delete the target + ``doit assembly:<stem>``).
    """
    asm_path = (OUT_SLDASM / f"{asm_name}.SLDASM").resolve()
    if not asm_path.exists():
        raise RuntimeError(
            f"missing assembly {asm_path}; build it from scratch first")
    with _telemetry.span("open", asm=asm_name):
        check(f"open {asm_name}", await adapter.open_model(str(asm_path)))
        configs = check("list configurations", await adapter.list_configurations())
    log(f"refresh {asm_name}: {len(configs)} configuration(s): {configs}")
    # The deterministic export/rest pose: Default is the saved, rendered pose the
    # top-level assembly references, and the DOF gate runs on it.
    rest = "Default" if "Default" in configs else (configs[0] if configs else None)

    # Per-config rebuild: load the new part geometry into EVERY configuration so a
    # config-specific break (a config whose mesh entity moved) is caught here, not
    # silently saved. Any under-defined-by-design config is NOT a fault --
    # whats_wrong reports feature/mate rebuild errors, not free DOF.
    repaired_any = False
    with _telemetry.span("rebuild_configs", count=len(configs)):
        for cfg in configs:
            with _telemetry.span("rebuild_config", config=cfg):
                check(f"activate {cfg}", await adapter.set_active_configuration(cfg))
                adapter._attempt(
                    lambda: adapter.currentModel.ForceRebuild3(False), default=None)
                faults = _rebuild_faults(adapter)
                if faults:
                    # The sharp edge: a from-scratch part rebuild re-IDs the faces
                    # its mates selected, dangling them. Auto-heal in place with
                    # AutoMateRepair before failing, then rebuild + re-read. Success
                    # is judged by the CLEAN re-read below + the standard gates --
                    # not by AutoMateRepair's own return code.
                    log(f"refresh {asm_name}: configuration {cfg!r} has {len(faults)} "
                        f"rebuild fault(s) (dangling mate / re-IDed face?); auto-healing ...")
                    repaired_any = repair_dangling_mates(adapter) > 0 or repaired_any
                    adapter._attempt(
                        lambda: adapter.currentModel.ForceRebuild3(False), default=None)
                    faults = _rebuild_faults(adapter)
                if faults:
                    raise RuntimeError(
                        f"refresh {asm_name}: configuration {cfg!r} STILL has rebuild faults "
                        f"after AutoMateRepair (unhealable -- escalate to a full rebuild: "
                        f"delete the .SLDASM target + `doit assembly:{asm_name}`): "
                        + ", ".join(faults))
                log(f"refresh {asm_name}: configuration {cfg} rebuilt clean")

    # Back to the rest pose for the gates + save: the saved active config and the
    # exported PNGs must match the from-scratch build's deterministic pose.
    if rest is not None:
        with _telemetry.span("reactivate", config=rest):
            check(f"re-activate {rest}", await adapter.set_active_configuration(rest))

    # Gates -- each already raises a RuntimeError naming the culprit. No fallback.
    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    assert_model_healthy(adapter, label=asm_name, deep=True)

    # Decide whether this refresh actually changed the resolved geometry before
    # saving: an in-place Save3 always rewrites a fresh md5, which would invalidate
    # the parent even for a no-op reload of unchanged parts. Gate the bump on the
    # mass-properties fingerprint so a true no-op leaves the .SLDASM byte-stable.
    # A successful AutoMateRepair ALSO forces the save even when the fingerprint is
    # unchanged (a PID-churn-only rebuild): the re-bound mate PIDs MUST persist, or
    # every later refresh re-dangles and re-heals the same mates forever.
    digest = await assembly_geometry_digest(adapter, asm_name)
    sidecar = _massprops_sidecar(asm_name)
    try:
        prev = sidecar.read_text(encoding="utf-8").strip()
    except OSError:
        prev = None
    geometry_changed = prev != digest or repaired_any

    with _telemetry.span("save", asm=asm_name, changed=geometry_changed):
        if geometry_changed:
            set_isometric_view(adapter)  # opens isometric; only when we actually re-save
        save_assembly_in_place(adapter, asm_name, geometry_changed)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(digest + "\n", encoding="utf-8")

    artefacts = {"assembly": str(asm_path)}
    artefacts.update(await _export_assembly_images(adapter, asm_name, views))
    return artefacts
