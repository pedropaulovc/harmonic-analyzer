"""Assembly-only helpers: mates, drivers, component placement, health/
interference gates, assembly save/refresh. Imported only by the assembly
build scripts (never by a leaf part), so edits here never invalidate parts.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from enum import StrEnum
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
    _early_bound,
    _read_member,
    active_configuration_name,
    check,
    log,
    set_isometric_view,
)

# The sprockets the chain seats on (the mounted T24 + crank T12 removables).
# A chain link touching one of these is intended MESH, not a fault: the chain
# rides the pitch circle so the links overlap the teeth in the shared z-plane
# (a coplanar single-plane stand-in). Whitelisted like link<->link contact in
# check_no_interference. Defined here (not in _common) so it stays off every
# part's recipe digest -- only the assemblies that read it rebuild on a change.
_CHAIN_SPROCKET_PREFIXES = ("transgear-removable",)
# Only the sprockets the roller chain actually WRAPS mesh it: the T12 crank wheel
# and the T24 knob wheel. The loose T18 spare (same "transgear-removable" stem, a
# different config) rests off the loop, so a chain-link overlap with IT is a real
# collision, NOT intended mesh -- discriminate by referenced configuration so the
# mesh whitelist below never masks a spare-part clash (codex #189 round-5).
_CHAIN_SPROCKET_CONFIGS = ("T12", "T24")


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
# leaving the translation clean while the rest pose is visibly wrong.
# Builds never actuate the freed operational DOF, so the as-saved pose must
# equal the authored rest pose for every component -- drift IS a defect.
_POSE_LEDGER: dict[str, tuple[list[float], list[float]]] = {}


def _ledger_record(name: str, position: list[float], rows: list[list[float]]) -> None:
    _POSE_LEDGER[name] = (list(position), [c for row in rows for c in row])


def reledger_to_solved(adapter: Any, name: str) -> None:
    """Re-anchor a placed component's pose-ledger entry to its CURRENT solved pose.

    For a component whose final orientation is DELEGATED to a feature solved
    AFTER it is placed -- a chain-component-pattern seed, whose tangent alignment
    the pattern owns and re-solves off the provisional authored chord angle (the
    pin-spacing chord is shorter than the wrap arc, so the two pin axes pull the
    seed straight) -- the place-time pose is not the invariant; the post-feature
    solved pose is. Call after the owning feature is built so assert_pose_ledger
    checks the pose that is actually intended to persist, not the placeholder.
    """
    array = component_transform(adapter, name)
    _ledger_record(
        name,
        [array[9] * 1000.0, array[10] * 1000.0, array[11] * 1000.0],
        [list(array[0:3]), list(array[3:6]), list(array[6:9])],
    )


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
    if not name:
        return 0
    model = adapter.currentModel
    feat = adapter._attempt(lambda: model.FeatureByName(name), default=None)
    if feat is None:
        return 0
    # Early-bound IFeature::GetErrorCode2 returns the [out] IsWarning in the tuple
    # (code, is_warning) -- pass nothing, consume the tuple. The old byref-VARIANT
    # arg is a dynamic-dispatch idiom; under InvokeTypes the call returns the tuple
    # regardless, so int(result) would crash on it.
    feat = _early_bound(feat, "IFeature")
    result = adapter._attempt(lambda: feat.GetErrorCode2(), default=None)
    if not result:
        return 0
    code = int(result[0] or 0)
    if code and bool(result[1]):
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
    "crank wheel axial",
    "crankshaft axial (on the plate)",
    "cylinder gear axial anchor",
    "cylinder gear axial pitch",
    "foot screw datum X",
    "foot screw datum Y",
    "foot screw datum Z",
    "fulcrum shaft datum x",
    "fulcrum shaft datum y",
    "hanger screw head plane",
    "knob wheel axial",
    "lever axial seat",
    "lever bushing axial z",
    "lift rod axial",
    "mag lever depth @npn",
    "mag lever knife line across @npn",
    # (was "pen rod travel snapshot" -- the label gained the PARK-driver tag
    # 2026-07-07; same mate, same learned side)
    "pen rod travel PARK driver (freed in default build)",
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
    # (was "rack pinion disc axial" -- the 120T disc's label became "reducer
    # disc" in the PR #196 real-train rework; same mate, same learned side.
    # Latent until 2026-07-07's full paper-drive rebuild re-keyed it.)
    "reducer disc axial",
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


def witness_from_ledger(comp_name: str, local_mm: list[float]) -> list[float]:
    """The AUTHORED world position (mm) of a component-local point, from the pose
    ledger -- the placed pose IS the design pose by construction (components are
    inserted on-solution), so this is the ground-truth target for an off-origin
    mate witness (issue #154). Raises for a component that was never placed
    through :func:`place_component` / :func:`place_components_batch`."""
    if comp_name not in _POSE_LEDGER:
        raise RuntimeError(
            f"witness_from_ledger: {comp_name!r} has no pose-ledger entry -- "
            "witness points require a component placed on-solution"
        )
    pos, rows = _POSE_LEDGER[comp_name]
    return [
        sum(local_mm[i] * rows[i * 3 + k] for i in range(3)) + pos[k]
        for k in range(3)
    ]


async def _mate(
    adapter: Any,
    label: str,
    kind: str,
    entities: list[Any],
    *,
    verify: tuple[str, list[float]] | None = None,
    witness: tuple[list[float], list[float]] | None = None,
    flip: bool = False,
    **kw: Any,
) -> Any:
    """Add a mate and ``check`` it; FAIL LOUD on a far-side flip when ``verify`` set.

    ``verify=(comp_name, target_origin_mm)`` enables the readback GUARD: after
    the mate solves, the component origin must stay within ``_MATE_TOL_MM`` of
    ``target_origin_mm`` (it was inserted there); otherwise the mate landed on
    the WRONG side. A mate created in a HARD error state (``_mate_hard_error``)
    is the same failure even when nothing moved -- SW's wrong-side add can fail
    IN PLACE. Returns the mate result data.

    ``witness=(local_mm, expected_world_mm)`` extends the guard with an
    OFF-ORIGIN point of the ``verify`` component (issue #154): an angle/parallel
    mate has two solutions, and for a component whose origin sits ON the mate's
    rotation axis the origin does not move under a branch flip -- the origin
    readback is structurally blind. The witness point (component-local, off the
    axis) separates the branches; its authored world position comes from the
    pose ledger (:func:`witness_from_ledger`) at build time and is persisted in
    the DOF-manifest spec for the transient kinematics replay. Requires
    ``verify``.

    ``flip`` seeds the solve's side. The correct side is DETERMINISTIC per mate
    (the sign rule XOR the reference's :data:`_FLIP_INVERT` polarity -- see
    ``_seed_flip``), so a caller that seeds it right lands on-target in ONE solve.
    A wrong seed does NOT self-heal: this used to delete + re-add flipped, but
    that inefficient reflip fired every build for an unseeded reference and is
    exactly what the seeding system exists to kill. Detection stays, but a miss
    now RAISES, naming the exact signature to toggle in ``_FLIP_INVERT`` so the
    fix is a one-line seed change, not a silent per-build reflip.
    """
    if witness is not None and verify is None:
        raise RuntimeError(f"{label!r}: witness requires verify (the component name)")
    # Span every mate (the single chokepoint all mate helpers funnel through),
    # so the full-build waterfall stays contiguous between part spans instead of
    # leaving the mate time as a gap. NAME the span
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
        w_moved = 0.0
        if witness is not None and comp_name:
            w_local, w_expected = witness
            w_actual = world_point(adapter, comp_name, list(w_local))
            w_moved = max(abs(a - e) for a, e in zip(w_actual, w_expected, strict=True))
        if moved <= _MATE_TOL_MM and w_moved <= _MATE_TOL_MM and not err:
            return res
        if w_moved > _MATE_TOL_MM >= moved and not err:
            # The origin held but the witness point moved: the mate solved the
            # WRONG BRANCH about an axis through the component origin -- the
            # failure mode the origin readback is structurally blind to (#154).
            msp.set_attribute("witness_miss", True)
            _telemetry.event(
                "mate.witness_miss", label=label, moved_mm=round(w_moved, 3))
            raise RuntimeError(
                f"witness MISS: {label!r} solved the WRONG branch -- the witness"
                f" point drifted {w_moved:.2f} mm from its authored pose while the"
                f" component origin held (origin on the mate axis). The intended"
                f" branch is no longer pinned by the mate graph: fix the mate's"
                f" angle/alignment or restore the ordering that pinned it."
            )
        msp.set_attribute("flip_miss", True)
        # The mate landed on the WRONG side. This is a deterministic seeding
        # bug, not a coin flip -- record the moment on the span, then FAIL LOUD
        # naming the exact signature to toggle. We do NOT self-heal by re-adding
        # flipped: that reflip fired every build for an unseeded reference and is
        # precisely the inefficiency the seeding system exists to eliminate.
        _telemetry.event(
            "mate.flip_miss", label=label, moved_mm=round(moved, 3), error=err)
        _seed_sig = _flip_sig(label) + (
            _orient_suffix(adapter, comp_name) if comp_name else "")
        raise RuntimeError(
            f"flip-seed MISS: {label!r} landed on the WRONG side"
            f" (off by {moved:.2f} mm, error={err}). The correct side is"
            f" DETERMINISTIC -- seed it: toggle sig {_seed_sig!r} in"
            f" _FLIP_INVERT (add it if absent, remove it if present) in"
            f" cad/scripts/_assembly.py, then rebuild. It XORs the sign rule for"
            f" this reference so the mate lands on-target in ONE solve. Do NOT"
            f" rely on a runtime reflip -- there is none any more."
        )

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
    witness_local: list[float] | None = None,
) -> Any:
    """Parallel mate between two planes / faces; pins ONE rotational DOF.

    The distance-free way to pin a leftover rotation (e.g. the immaterial spin of
    a concentric-/collinear-mated solid of revolution) -- coincident would force
    the planes flush (an unwanted translation), parallel only kills the spin.

    ``witness_local`` (issue #154): a component-local point OFF the pinned
    rotation's axis, for a ``verify`` component whose origin sits ON it -- the
    two parallel solutions leave the origin fixed, so only an off-origin point
    separates them. Expected world position derives from the pose ledger.
    """
    witness = None
    if witness_local is not None:
        if verify is None:
            raise RuntimeError(f"{label!r}: witness_local requires verify")
        witness = (list(witness_local), witness_from_ledger(verify[0], witness_local))
    return await _mate(
        adapter,
        label,
        "parallel",
        [ref_a, ref_b],
        alignment=alignment,
        verify=verify,
        witness=witness,
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

    ``free_dof_key`` marks this as a *freed operational DOF* (see the Kinematic
    DOF manifest section): the mate is NOT authored -- the slide stays free --
    and its resolved spec is RECORDED into the DOF manifest for the transient
    verify:kinematics replays. ``None`` is a hard pin, authored as before.
    """
    label = label or f"distance driver d={distance:g}"
    if flip is None:
        comp = verify[0] if verify else ""
        flip = _seed_flip(label, distance, _orient_suffix(adapter, comp))
    return await _driver_or_record(
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
    witness_local: list[float] | None = None,
) -> Any:
    """An angle mate used as a driving dimension pinning one rotational DOF.

    ``free_dof_key`` marks this as a *freed operational DOF*: the mate is NOT
    authored (the rotation stays free) and its resolved spec is RECORDED into
    the DOF manifest. See :func:`distance_driver` and the Kinematic DOF
    manifest section.

    ``witness_local`` (issue #154): an angle mate is satisfied at EITHER of two
    leans, and for a ``verify`` component whose origin sits ON the rotation axis
    the origin readback cannot tell them apart. Pass a component-local point off
    the axis; its authored world position (pose ledger) becomes the branch
    witness, checked when the driver is authored AND recorded into the DOF
    manifest so the transient replay is guarded the same way.
    """
    label = label or f"angle driver a={angle:g}"
    witness = None
    if witness_local is not None:
        if verify is None:
            raise RuntimeError(f"{label!r}: witness_local requires verify")
        witness = (list(witness_local), witness_from_ledger(verify[0], witness_local))
    return await _driver_or_record(
        adapter, "angle", ref_a, ref_b,
        label=label, verify=verify, free_dof_key=free_dof_key,
        witness=witness,
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

    ``free_dof_key`` forwards to the underlying :func:`distance_driver` so the
    spin becomes a *freed operational DOF*: recorded into the DOF manifest, not
    authored. The resolved plane + target distance ARE the recorded spec, so a
    transient replay re-authors the same pin without re-deriving the
    sensitivity choice.

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
    flip: bool = False,
    label: str = "rack_pinion",
    verify: tuple[str, list[float]] | None = None,
) -> Any:
    """Rack-pinion mate coupling a linear rack to a rotating pinion.

    ``rack_ref`` selects a linear rack edge/axis, ``pinion_ref`` the pinion's
    cylindrical face/axis. Set EITHER ``pinion_pitch_diameter`` (mm) OR
    ``rack_travel_per_revolution`` (mm) -- the adapter writes it into the mate
    definition (AddMate5 has no parameter for it). ``flip`` sets the mate's
    ``Reverse`` member when the solver's derived engagement sense runs the rack
    backward vs the physical tooth contact -- calibrate it from the
    verify:kinematics gate (the probe's signed feed assert), per the
    GEAR_SENSE/FEED_SIGN precedent.
    """
    return await _mate(
        adapter,
        label,
        "rack_pinion",
        [rack_ref, pinion_ref],
        pinion_pitch_diameter=pinion_pitch_diameter,
        rack_travel_per_revolution=rack_travel_per_revolution,
        flip=flip,
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
    configuration: str = "",
    label: str = "",
) -> str:
    """Insert a part at its exact final machine transform and assert it.

    ``position``/``rotation``/``rows`` ARE the machine-frame pose -- the crank
    at machine -X, the output side -Z (#151 re-authored the derivation
    machine-handed; the M6.8 ``mirror_placement`` reflection layer is gone).

    ``ground=True`` fixes the component (structure: shafts, mounts, bushings,
    supports, frame, fasteners, cosmetic springs). ``ground=False`` leaves it
    free for the caller's mates to constrain -- the moving parts whose DOF are
    driven from the crank. ``configuration`` selects a part configuration (the
    cone-gear tooth counts, the transgear-removable wheels). Either way the
    part is inserted on-solution so mate flip-recovery has a clean reference
    and the read-back assert holds.
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


_LOCAL_LINEAR_PATTERN = 108  # swFeatureNameID_e.swFmLocalLPattern
_LOCAL_CIRCULAR_PATTERN = 109  # swFeatureNameID_e.swFmLocalCirPattern
_GLOBAL_PATTERN_AXIS_PLANES = {
    "x": ("Top Plane", "Front Plane"),
    "y": ("Front Plane", "Right Plane"),
    "z": ("Top Plane", "Right Plane"),
}


class PatternDirection(StrEnum):
    FORWARD = "forward"
    REVERSE = "reverse"


def _top_features(model: Any) -> list[Any]:
    model = _early_bound(model, "IModelDoc2", "FirstFeature")
    features = []
    feature = _read_member(model, "FirstFeature")
    while feature is not None:
        feature = _early_bound(feature, "IFeature", "GetNextFeature")
        features.append(feature)
        feature = feature.GetNextFeature()
    return features


@_telemetry.traced("assembly.pattern_axis", label_param="axis")
def ensure_global_pattern_axis(adapter: Any, axis: str) -> str:
    """Create/reuse an assembly reference axis aligned to global X, Y, or Z."""
    key = axis.lower()
    try:
        planes = _GLOBAL_PATTERN_AXIS_PLANES[key]
    except KeyError as exc:
        raise ValueError(f"pattern axis must be x, y, or z; got {axis!r}") from exc

    from solidworks_mcp.adapters.com_variant import null_callout

    model = adapter.currentModel
    name = f"PatternAxis{key.upper()}"
    existing = adapter._attempt(lambda: model.FeatureByName(name), default=None)
    if existing is not None:
        return name

    model.ClearSelection2(True)
    for index, plane in enumerate(planes):
        selected = model.Extension.SelectByID2(
            plane,
            "PLANE",
            0.0,
            0.0,
            0.0,
            index > 0,
            0,
            null_callout(),
            0,
        )
        if not selected:
            raise RuntimeError(f"cannot select {plane} for global {key}-axis")
    if not model.InsertAxis2(True):
        raise RuntimeError(f"SOLIDWORKS rejected global {key}-axis creation")
    # InsertAxis2 places reference geometry before trailing MateGroup/pattern
    # features, so reverse position zero is not necessarily the new axis. Walk
    # backward only until the nearest RefAxis (normally 2-4 entries), avoiding
    # the old two full O(n) feature-tree scans (18-78 s on the traced assemblies).
    created = None
    count = int(adapter._attempt(lambda: model.GetFeatureCount(), default=0) or 0)
    for index in range(min(count, 64)):
        candidate = adapter._attempt(
            lambda i=index: model.FeatureByPositionReverse(i), default=None)
        if candidate is None:
            continue
        _flag(candidate, "IFeature")
        if str(candidate.GetTypeName2()) == "RefAxis":
            created = candidate
            break
    if created is None:
        raise RuntimeError(f"cannot read newly-created global {key}-axis")
    created.Name = name
    model.ClearSelection2(True)
    _telemetry.success(f"created assembly pattern axis {name}")
    return name


def _select_pattern_inputs(
    adapter: Any,
    seed_components: tuple[str, ...],
    direction_name: str,
    direction_type: str,
    direction2_name: str | None = None,
    direction2_type: str = "AXIS",
) -> None:
    from solidworks_mcp.adapters.com_variant import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    selected = model.Extension.SelectByID2(
        direction_name,
        direction_type,
        0.0,
        0.0,
        0.0,
        False,
        2,
        null_callout(),
        0,
    )
    if not selected:
        raise RuntimeError(
            f"cannot select pattern direction {direction_type} {direction_name!r}"
        )
    if direction2_name is not None:
        selected = model.Extension.SelectByID2(
            direction2_name,
            direction2_type,
            0.0,
            0.0,
            0.0,
            True,
            4,
            null_callout(),
            0,
        )
        if not selected:
            raise RuntimeError(
                "cannot select pattern direction 2 "
                f"{direction2_type} {direction2_name!r}"
            )
    for seed_component in seed_components:
        component = adapter._attempt(
            lambda name=seed_component: model.GetComponentByName(name), default=None
        )
        if component is None or not component.Select2(True, 1):
            raise RuntimeError(
                f"cannot select pattern seed component {seed_component!r}"
            )


def _new_pattern_components(model: Any, before: set[str]) -> list[Any]:
    components = model.GetComponents(False) or []
    return [
        component for component in components
        if str(_read_member(component, "Name2")) not in before
    ]


def assert_pattern_targets(
    adapter: Any,
    instances: Iterable[str],
    targets: Iterable[list[float]],
    rows: list[list[float]],
    label: str,
) -> None:
    """Match unordered native-pattern instances to authored poses and gate each."""
    unmatched = set(instances)
    for target in targets:
        matching = [
            name
            for name in unmatched
            if all(
                abs(component_transform(adapter, name)[9 + axis] * 1000.0 - target[axis])
                < 0.05
                for axis in range(3)
            )
        ]
        if len(matching) != 1:
            raise RuntimeError(f"{label} has {len(matching)} instances at {target}")
        name = matching[0]
        assert_component_placed(adapter, name, target, rows)
        _ledger_record(name, target, rows)
        unmatched.remove(name)
    if unmatched:
        raise RuntimeError(f"{label} has unexpected instances: {sorted(unmatched)}")


async def linear_component_pattern(
    adapter: Any,
    seed_components: Iterable[str],
    *,
    axis: str,
    spacing_mm: float,
    instances: int,
    direction: PatternDirection = PatternDirection.FORWARD,
    label: str = "linear fastener pattern",
) -> list[str]:
    """Pattern one or more seed components along a global assembly axis."""
    if instances < 2:
        raise ValueError("linear component pattern requires at least two instances")
    if spacing_mm <= 0.0:
        raise ValueError("linear component pattern spacing must be positive")
    seeds = tuple(seed_components)
    if not seeds:
        raise ValueError("linear component pattern requires at least one seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError("linear component pattern seeds must be unique")

    model = adapter.currentModel
    direction_name = ensure_global_pattern_axis(adapter, axis)
    before = {
        str(_read_member(component, "Name2"))
        for component in (model.GetComponents(False) or [])
    }
    async with _telemetry.aspan(
        f"pattern {label}", kind="linear", seeds=",".join(seeds),
        axis=axis.lower(), instances=instances, spacing_mm=spacing_mm,
    ):
        _select_pattern_inputs(adapter, seeds, direction_name, "AXIS")
        manager = _early_bound(
            model.FeatureManager, "IFeatureManager", "CreateDefinition", "CreateFeature"
        )
        definition = manager.CreateDefinition(_LOCAL_LINEAR_PATTERN)
        if definition is None:
            raise RuntimeError("cannot create local linear pattern definition")
        definition = _early_bound(definition, "ILocalLinearPatternFeatureData")
        definition.D1ReverseDirection = direction is PatternDirection.REVERSE
        definition.D1Spacing = spacing_mm / 1000.0
        definition.D1TotalInstances = instances
        definition.D2PatternSeedOnly = False
        definition.D2ReverseDirection = False
        definition.D2Spacing = 0.001
        definition.D2TotalInstances = 1
        definition.SynchronizeFlexibleComponents = False
        feature = manager.CreateFeature(definition)
        model.ClearSelection2(True)
        if feature is None:
            raise RuntimeError(f"SOLIDWORKS rejected {label}")
        feature = _early_bound(feature, "IFeature")
        feature.Name = label

        created = _new_pattern_components(model, before)
        expected = len(seeds) * (instances - 1)
        if len(created) != expected:
            raise RuntimeError(
                f"{label} created {len(created)} components, expected {expected}"
            )
        names = []
        for component in created:
            component = _early_bound(component, "IComponent2", "IsPatternInstance")
            name = str(_read_member(component, "Name2"))
            if not component.IsPatternInstance():
                raise RuntimeError(f"{name} is not owned by the component pattern")
            names.append(name)
        _telemetry.success(f"{label}: created {len(names)} pattern instances")
        return names


async def grid_component_pattern(
    adapter: Any,
    seed_components: Iterable[str],
    *,
    axis1: str,
    spacing1_mm: float,
    instances1: int,
    axis2: str,
    spacing2_mm: float,
    instances2: int,
    direction1: PatternDirection = PatternDirection.FORWARD,
    direction2: PatternDirection = PatternDirection.FORWARD,
    label: str = "rectangular component pattern",
) -> list[str]:
    """Pattern seeds as one native two-direction rectangular grid."""
    if instances1 < 2 or instances2 < 2:
        raise ValueError("grid component pattern requires two instances per axis")
    if spacing1_mm <= 0.0 or spacing2_mm <= 0.0:
        raise ValueError("grid component pattern spacing must be positive")
    if axis1.lower() == axis2.lower():
        raise ValueError("grid component pattern axes must differ")
    seeds = tuple(seed_components)
    if not seeds:
        raise ValueError("grid component pattern requires at least one seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError("grid component pattern seeds must be unique")

    model = adapter.currentModel
    direction1_name = ensure_global_pattern_axis(adapter, axis1)
    direction2_name = ensure_global_pattern_axis(adapter, axis2)
    before = {
        str(_read_member(component, "Name2"))
        for component in (model.GetComponents(False) or [])
    }
    async with _telemetry.aspan(
        f"pattern {label}", kind="grid", seeds=",".join(seeds),
        axis1=axis1.lower(), instances1=instances1, spacing1_mm=spacing1_mm,
        axis2=axis2.lower(), instances2=instances2, spacing2_mm=spacing2_mm,
    ):
        _select_pattern_inputs(
            adapter, seeds, direction1_name, "AXIS", direction2_name, "AXIS"
        )
        manager = model.FeatureManager
        _flag(manager, "IFeatureManager")
        definition = manager.CreateDefinition(_LOCAL_LINEAR_PATTERN)
        if definition is None:
            raise RuntimeError("cannot create local grid pattern definition")
        _flag(definition, "ILocalLinearPatternFeatureData")
        definition.D1ReverseDirection = direction1 is PatternDirection.REVERSE
        definition.D1Spacing = spacing1_mm / 1000.0
        definition.D1TotalInstances = instances1
        definition.D2PatternSeedOnly = False
        definition.D2ReverseDirection = direction2 is PatternDirection.REVERSE
        definition.D2Spacing = spacing2_mm / 1000.0
        definition.D2TotalInstances = instances2
        definition.SynchronizeFlexibleComponents = False
        feature = manager.CreateFeature(definition)
        model.ClearSelection2(True)
        if feature is None:
            raise RuntimeError(f"SOLIDWORKS rejected {label}")
        _flag(feature, "IFeature")
        feature.Name = label

        created = _new_pattern_components(model, before)
        expected = len(seeds) * (instances1 * instances2 - 1)
        if len(created) != expected:
            raise RuntimeError(
                f"{label} created {len(created)} components, expected {expected}"
            )
        names = []
        for component in created:
            _flag_only(component, "IsPatternInstance")
            name = str(_read_member(component, "Name2"))
            if not component.IsPatternInstance():
                raise RuntimeError(f"{name} is not owned by the component pattern")
            names.append(name)
        _telemetry.success(f"{label}: created {len(names)} pattern instances")
        return names


async def circular_component_pattern(
    adapter: Any,
    seed_components: Iterable[str],
    *,
    axis_name: str,
    instances: int,
    direction: PatternDirection = PatternDirection.FORWARD,
    label: str = "circular fastener pattern",
) -> list[str]:
    """Pattern seed components equally through 360 degrees around a named axis."""
    if instances < 2:
        raise ValueError("circular component pattern requires at least two instances")
    seeds = tuple(seed_components)
    if not seeds:
        raise ValueError("circular component pattern requires at least one seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError("circular component pattern seeds must be unique")

    model = adapter.currentModel
    before = {
        str(_read_member(component, "Name2"))
        for component in (model.GetComponents(False) or [])
    }
    async with _telemetry.aspan(
        f"pattern {label}", kind="circular", seeds=",".join(seeds),
        axis=axis_name, instances=instances,
    ):
        _select_pattern_inputs(adapter, seeds, axis_name, "AXIS")
        manager = _early_bound(
            model.FeatureManager, "IFeatureManager", "CreateDefinition", "CreateFeature"
        )
        definition = manager.CreateDefinition(_LOCAL_CIRCULAR_PATTERN)
        if definition is None:
            raise RuntimeError("cannot create local circular pattern definition")
        definition = _early_bound(definition, "ILocalCircularPatternFeatureData")
        definition.TotalInstances = instances
        definition.EqualSpacing = True
        definition.ReverseDirection = direction is PatternDirection.REVERSE
        definition.SynchronizeFlexibleComponents = False
        feature = manager.CreateFeature(definition)
        model.ClearSelection2(True)
        if feature is None:
            raise RuntimeError(f"SOLIDWORKS rejected {label}")
        feature = _early_bound(feature, "IFeature")
        feature.Name = label

        created = _new_pattern_components(model, before)
        expected = len(seeds) * (instances - 1)
        if len(created) != expected:
            raise RuntimeError(
                f"{label} created {len(created)} components, expected {expected}"
            )
        names = []
        for component in created:
            component = _early_bound(component, "IComponent2", "IsPatternInstance")
            name = str(_read_member(component, "Name2"))
            if not component.IsPatternInstance():
                raise RuntimeError(f"{name} is not owned by the component pattern")
            names.append(name)
        _telemetry.success(f"{label}: created {len(names)} pattern instances")
        return names

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
      * ``position`` -- origin (mm) in the machine frame,
      * ``rows`` -- rotation rows (images of the part X/Y/Z axes), machine frame,
      * ``rotation`` -- Euler angles (optional; carried only for parity with
        :func:`place_component`, the transform is built from ``rows``),
      * ``ground`` -- fix the component (default ``True``),
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
    BOTH the translation and the rotation (``array[0:9]`` vs the spec's rows --
    the same check the per-part ``assert_component_placed`` runs) so a
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
    finals: list[list[float]] = []  # final machine-frame origin per spec, mm
    expected_rows: list[list[float]] = []  # final rotation, flat 9, per spec
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
        rows = [list(r) for r in spec["rows"]]
        names.append(str(part_path(part)))  # raises if the .SLDPRT is missing
        transforms.extend(_placement_transform(rows, position))
        finals.append(position)
        expected_rows.append([c for row in rows for c in row])
        grounds.append(bool(spec.get("ground", True)))

    raw_model = adapter.currentModel
    asm = _early_bound(raw_model, "IAssemblyDoc", "AddComponents3")
    model_doc = _early_bound(raw_model, "IModelDoc2", "ClearSelection2")
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
                adapter._attempt(lambda: model_doc.ClearSelection2(True), default=None)
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
                adapter._attempt(lambda: model_doc.ClearSelection2(True), default=None)

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
    creator. ``GetComponents`` hands back transient dispatches, so each is
    wrapped as ``IComponent2`` before its zero-argument methods are invoked.
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
            # Wrap once as IComponent2 so both zero-arg methods invoke known
            # DISPIDs; Name2/IsFixed remain property reads.
            component = _early_bound(
                component, "IComponent2", "IsPatternInstance", "GetConstrainedStatus"
            )
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
# Kinematic DOF manifest -- freed operational DOF, recorded not authored
# ---------------------------------------------------------------------------
# The build leaves every OPERATIONAL degree of freedom (crank spin, rocker
# swing, carriage travel, ...) genuinely FREE: no driver mate is authored for
# it, because each part is inserted on its exact Python-solved transform and
# the real contact mates hold it there -- the saved pose is deterministic
# without full definition. What the build DOES record is a manifest entry per
# freed DOF (``free_dof_key`` on the ``*_driver`` helpers): the driving entity
# refs, rest value and resolved mate side, persisted as a ``.<stem>.dof.json``
# sidecar. That manifest is the machine-readable answer to "which entity
# drives this DOF at what rest value" -- ``verify:kinematics`` replays entries
# TRANSIENTLY (``_assembly_postbuild.author_dof_drives``) to sweep the
# mechanism (the pen Fourier sweep, the magnifier chain proof), always
# discarding the model unsaved.
#
# (History: this used to be the two-sided "park driver" machinery -- deferred
# PARK_* mates, a `locked` build mode authoring them engaged, and a release
# 0-DOF closure proof. Killed 2026-07-09: placement already makes the build
# deterministic, the closure re-proved what insertion fixed, and the replay
# path was a recurring bug source. Soundness now proves the free-DOF SET
# exactly instead -- see ``assert_free_dof_necessity``.)
_DOF_SPECS: list[dict[str, Any]] = []


def reset_dof_manifest() -> None:
    """Clear the recorded free-DOF specs. Call once near the top of a build so a
    multi-build process never leaks one assembly's manifest into the next."""
    _DOF_SPECS.clear()


def collected_dof_specs() -> list[dict[str, Any]]:
    """The free-DOF specs recorded so far this build (a shallow copy)."""
    return list(_DOF_SPECS)


def _record_dof_spec(
    key: str, kind: str, entities: list[Any],
    *, verify: tuple[str, list[float]] | None = None,
    witness: tuple[list[float], list[float]] | None = None, flip: bool = False,
    **params: Any,
) -> None:
    """Record one freed operational DOF as a machine-independent drive spec
    (entity refs by name + geometry-derived scalars + the resolved mate SIDE),
    for transient replay by the verify:kinematics sweeps.

    ``flip`` is the sign-derived seat side the driver helper already resolved
    (:func:`_seed_flip` for distance/spin drivers; ``False`` for angle drivers).
    Recording it lets :func:`_assembly_postbuild.author_dof_drives` re-author on
    the SAME side in one solve (#185's flip-free seeding, extended to the replay
    path -- the wire-swing replay hit a hard error-47 far-side add before this,
    2026-07-05).

    ``witness`` (issue #154) is the resolved off-origin branch witness
    ``(local_mm, expected_world_mm)`` -- persisted so the transient replay of a
    flip-ambiguous angle driver is guarded exactly like the build would be (the
    replay runs in a fresh process with no pose ledger, so the expected world
    position must ride the spec)."""
    _DOF_SPECS.append({
        "key": key,
        "kind": kind,
        "entities": [e.model_dump() for e in entities],
        "verify": [verify[0], [float(v) for v in verify[1]]] if verify else None,
        "witness": (
            [[float(v) for v in witness[0]], [float(v) for v in witness[1]]]
            if witness else None
        ),
        "flip": bool(flip),
        "params": {
            k: (float(v) if isinstance(v, (int, float)) else v)
            for k, v in params.items()
        },
    })
    _telemetry.debug(f"dof manifest {key}: {kind} drive recorded (not authored, flip={flip})")


async def _driver_or_record(
    adapter: Any, kind: str, ref_a: Any, ref_b: Any,
    *, label: str, verify: tuple[str, list[float]] | None,
    free_dof_key: str | None,
    witness: tuple[list[float], list[float]] | None = None,
    flip: bool = False, **params: Any,
) -> Any:
    """Author a driver mate, OR (a ``free_dof_key``) record it into the DOF
    manifest and skip -- the DOF stays free in the saved model.

    Returns the mate result dict when authored; a ``{"free_dof": key}`` sentinel
    when recorded. ``flip`` seeds the authored mate's side (see :func:`_mate`)
    AND is recorded in the spec, so a transient replay re-authors on the same
    resolved side (flip-free, like the build)."""
    if free_dof_key is not None:
        _record_dof_spec(
            free_dof_key, kind, [ref_a, ref_b],
            verify=verify, witness=witness, flip=flip, **params)
        return {"free_dof": free_dof_key, "name": ""}
    return await _mate(
        adapter, label, kind, [ref_a, ref_b],
        verify=verify, witness=witness, flip=flip, **params
    )


def dof_manifest_path(name: str) -> Any:
    """Sidecar path (next to ``<name>.SLDASM``) holding the free-DOF drive
    specs. ``name`` is the dashed assembly stem (``"drive-train"``)."""
    return OUT_SLDASM / f".{name}.dof.json"


def write_dof_manifest(name: str) -> Any:
    """Persist this build's recorded free-DOF specs beside ``<name>.SLDASM`` (a
    doit assembly output that rides the remote cache). With nothing recorded any
    stale sidecar is removed and ``None`` returned."""
    path = dof_manifest_path(name)
    if not _DOF_SPECS:
        path.unlink(missing_ok=True)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"stem": name, "specs": _DOF_SPECS}, indent=2))
    _telemetry.success(
        f"wrote {len(_DOF_SPECS)} free-DOF drive spec(s) -> {path.name}"
    )
    return path


# Exact under-constrained component families allowed for assemblies that ship
# with operational free DOF. Shared by incremental refresh and verify:soundness
# so neither path can save/approve a stray freedom the other rejects.
_ALLOWED_FREE_STEMS: dict[str, tuple[str, ...]] = {
    "channel": ("rocker-arm", "connecting-rod", "amplitude-bar", "channel-lever"),
    "summing": ("summing-lever", "boss-hook"),
    "pen": ("pen-rod", "pen-marker", "pen-wire"),
    "drive-train": (
        "alignment-pinion", "cone-gear", "cone-gear-shaft", "cone-pivot-post",
        "cone-swing-platform", "cone-tip-adjuster", "cone-tip-block",
        "cone-tip-bushing", "cone-tip-pinch-screw", "crank-arm",
        "crank-drive-gear", "crank-handle", "crank-pinion", "crankshaft",
        "cylinder-gear", "pinion-arbor", "pinion-bracket", "pinion-cam",
        "pinion-cam-pin", "pinion-handle", "pinion-lever", "pinion-lift-rod",
    ),
    "magnifier": (
        "lever-wire", "magnifying-bracket", "magnifying-clamp",
        "magnifying-lever", "magnifying-vertical-rod", "magnifying-wheel",
        "output-fixture", "thumb-screw",
    ),
    "paper-drive": (
        "fillister-screw", "guide-lock", "platen", "platen-clip",
        "platen-guide", "platen-paper", "platen-rack", "rack-pinion",
        "transgear-feed-pinion", "transgear-knob-shaft", "transgear-pinion",
        "transgear-removable",
    ),
}


def assert_manifest_dof_state(adapter: Any, asm_name: str) -> None:
    """Apply the refresh DOF gate that matches the assembly's saved contract.

    A non-empty DOF manifest means the assembly intentionally ships with those
    operational freedoms. Prove their exact recorded witness instances remain
    under-constrained; assemblies without a manifest retain the strict 0-DOF gate.
    The exhaustive coupled-family check remains in ``verify:soundness``.
    """
    path = dof_manifest_path(asm_name)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        assert_components_fully_defined(adapter)
        return
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError(f"invalid free-DOF manifest {path}: {exc}") from exc
    specs = payload.get("specs") if isinstance(payload, dict) else None
    if not isinstance(specs, list) or not specs:
        raise RuntimeError(f"free-DOF manifest {path} has no specs")
    instances: list[str] = []
    for spec in specs:
        verify = spec.get("verify") if isinstance(spec, dict) else None
        instance = verify[0] if isinstance(verify, list) and verify else None
        if not isinstance(instance, str) or not instance:
            raise RuntimeError(f"free-DOF manifest {path} has a spec without a witness")
        instances.append(instance)
    assert_free_dof_necessity(
        adapter,
        len(specs),
        required_instances=tuple(dict.fromkeys(instances)),
        allowed_stems=_ALLOWED_FREE_STEMS.get(asm_name, ()),
    )






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
        component = _early_bound(
            component, "IComponent2", "IsPatternInstance", "GetConstrainedStatus"
        )
        comp_name = str(_read_member(component, "Name2"))
        if bool(_read_member(component, "IsFixed")):
            continue
        if bool(adapter._attempt(lambda c=component: c.IsPatternInstance(), default=False)):
            continue
        status = int(adapter._attempt(lambda c=component: c.GetConstrainedStatus(), default=-1))
        if status == UNDER_CONSTRAINED:
            under.append(comp_name)
    return under


def assert_free_dof_necessity(
    adapter: Any,
    expected_count: int,
    *,
    resolve: bool = True,
    required_stems: tuple[str, ...] = (),
    required_instances: tuple[str, ...] = (),
    allowed_stems: tuple[str, ...] = (),
) -> None:
    """Build/soundness DOF gate for a model with freed operational DOF.

    The freed DOF have no driver mates in the saved model (see the Kinematic
    DOF manifest section), so the gate reads the component constrained-status
    walk and proves the free SET from both directions:

    * NECESSITY: at least ``expected_count`` top-level components read
      under-constrained, i.e. the operational DOF genuinely ARE free (a mate
      did not silently freeze one).

    The aggregate count alone cannot tell WHICH DOF is free -- the crank spin
    alone under-constrains several crank-chain components, so a count check
    passes even with a second freed DOF accidentally pinned (codex review
    2026-07-04). ``required_stems`` therefore names one component family per
    freed DOF (instance suffixes stripped) that MUST read under-constrained.

    ``required_instances`` names EXACT component instances (no stem-collapse) that
    must read under-constrained -- use it when several instances share a stem and
    only a SPECIFIC one carries the freed DOF (e.g. paper-drive has three
    ``transgear-removable`` instances -- T12 crank, T24 knob, T18 spare -- but only
    the T12 crank spin is the operational DOF; a stem check would pass if the T24
    were free and the T12 pinned, codex #189). Pass the runtime instance name.

    * EXACT SET (``allowed_stems``): every under-constrained component's stem
      must be in ``allowed_stems`` -- the exhaustive list of families expected
      to move (the freed DOF's own parts PLUS everything coupled to them).
      This is the sufficiency direction the retired release park-closure used
      to prove by authoring drivers to 0 DOF: an UNINTENDED freedom (a
      forgotten mate on a structural part) now fails here, in every soundness
      pass, instead of only at release. Omit it to skip the exact-set check
      (necessity only).

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
                "-- a freed DOF is pinned by another mate, or the model is "
                "over-constrained (the 'free' model is actually frozen)"
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
        if required_instances:
            missing_inst = [n for n in required_instances if n not in under]
            gsp.set_attribute("required_instances", ",".join(required_instances))
            if missing_inst:
                raise RuntimeError(
                    f"free-DOF necessity: required instance(s) {missing_inst} read "
                    f"fully defined -- that freed DOF is pinned (a sibling instance "
                    f"may be free instead). Under-constrained: {sorted(under)}"
                )
        if allowed_stems:
            allowed = set(allowed_stems)
            stray = sorted(
                n for n in under if re.sub(r"-\d+$", "", n) not in allowed
            )
            gsp.set_attribute("stray_under_constrained", len(stray))
            if stray:
                raise RuntimeError(
                    f"free-DOF exact-set: component(s) {stray} read under-"
                    f"constrained but are NOT in the allowed free set "
                    f"{sorted(allowed)} -- an unintended freedom (a missing/"
                    "dropped mate on a structural part), or a newly coupled "
                    "family that must be added to the allowed list"
                )
        _telemetry.success(
            f"{len(under)} under-constrained component(s) >= {expected_count} expected "
            "free DOF (necessity"
            + ("; exact-set: no strays)" if allowed_stems else ")")
        )




def component_names(adapter: Any) -> list[str]:
    """Top-level component names (``Name2``) of the active assembly."""
    asm = _early_bound(adapter.currentModel, "IAssemblyDoc", "GetComponents")
    components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    names = []
    for component in components:
        # No flag: Name2 is a property read (issue #87).
        names.append(str(_read_member(component, "Name2")))
    return names


def delete_assembly_feature(adapter: Any, name: str) -> None:
    """Delete an assembly feature by name (Select2 + DeleteSelection2).

    Used by the component-pattern sense retries (channel bushing banks, frame
    column/screw pairs): a flipped pattern is removed whole (instances go with
    the feature; the seeds survive) before re-creating it with ``FlipDir1``.
    Fails loud when the feature is still present after."""
    model = adapter.currentModel
    feat = adapter._attempt(lambda: model.FeatureByName(name), default=None)
    if feat is None:
        raise RuntimeError(f"feature to delete not found: {name!r}")
    adapter._attempt(lambda: model.ClearSelection2(True), default=None)
    if not adapter._attempt(lambda: feat.Select2(False, 0), default=False):
        raise RuntimeError(f"failed to select feature for delete: {name!r}")
    if not adapter._attempt(lambda: model.Extension.DeleteSelection2(0), default=False):
        adapter._attempt(lambda: model.EditDelete(), default=None)
    if adapter._attempt(lambda: model.FeatureByName(name), default=None) is not None:
        raise RuntimeError(f"feature {name!r} still present after delete")

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
    asm = _early_bound(
        adapter.currentModel,
        "IAssemblyDoc",
        "ToolsCheckInterference",
        "InterferenceDetectionManager",
    )
    with _telemetry.span("gate.interference") as isp:
        log("interference detection: starting ...")
        adapter._attempt(lambda: asm.ToolsCheckInterference(), default=None)
        mgr = _read_member(asm, "InterferenceDetectionManager")
        if mgr is None:
            raise RuntimeError("InterferenceDetectionManager unavailable")
        mgr = _early_bound(mgr, "IInterferenceDetectionMgr", "GetInterferences")
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
        chain_mesh_contacts = []
        for interference in list(interferences or []):
            interference = _early_bound(interference, "IInterference")
            names = []
            configs = []
            for comp in list(_read_member(interference, "Components") or []):
                # No flag: Name2 / ReferencedConfiguration are property reads (issue #87).
                names.append(str(_read_member(comp, "Name2")))
                configs.append(str(_read_member(comp, "ReferencedConfiguration") or ""))
            volume_mm3 = float(_read_member(interference, "Volume") or 0.0) * 1e9
            if all(n.startswith(_CHAIN_LINK_PREFIXES) for n in names) and len(names) == 2:
                chain_contacts.append(volume_mm3)
                continue
            # Chain link <-> sprocket: intended mesh. The chain seats on the
            # pitch circle so its links overlap the removables' teeth in the
            # shared z-plane (a coplanar single-plane stand-in). Whitelisted
            # like the link<->link contact above -- but ONLY for a sprocket the
            # chain actually wraps (config T12/T24); a link overlapping the loose
            # T18 spare is a real clash and must NOT be whitelisted (codex #189).
            links = [n for n in names if n.startswith(_CHAIN_LINK_PREFIXES)]
            sprockets = [
                n for n, cfg in zip(names, configs)
                if n.startswith(_CHAIN_SPROCKET_PREFIXES) and cfg in _CHAIN_SPROCKET_CONFIGS
            ]
            if len(names) == 2 and len(links) == 1 and len(sprockets) == 1:
                chain_mesh_contacts.append(volume_mm3)
                continue
            details.append(f"{' & '.join(names)}: {volume_mm3:.2f} mm^3")
        adapter._attempt(lambda: mgr.Done(), default=None)
        isp.set_attribute("hits", len(details))
        isp.set_attribute("chain_contacts", len(chain_contacts))
        isp.set_attribute("chain_mesh_contacts", len(chain_mesh_contacts))
        if chain_contacts:
            _telemetry.debug(
                f"{len(chain_contacts)} chain-internal link contacts"
                f" (<= {max(chain_contacts):.2f} mm^3) allowed -- articulating chain"
            )
        if chain_mesh_contacts:
            _telemetry.debug(
                f"{len(chain_mesh_contacts)} chain<->sprocket mesh contacts"
                f" (<= {max(chain_mesh_contacts):.2f} mm^3) allowed -- chain seated"
                f" on the pitch circle"
            )
        if details:
            raise RuntimeError(
                f"{len(details)} interference(s): " + "; ".join(details)
            )
        _telemetry.success("interference check: none found")

def whats_wrong(adapter: Any, model: Any) -> list[tuple[str, int, bool]]:
    """Return ``[(feature_name, error_code, is_warning), ...]`` for a model.

    Reads the What's Wrong dialog via ``GetWhatsWrong``. Early-bound
    ``IModelDocExtension::GetWhatsWrong`` collects its three ``out object`` arrays
    into the return tuple ``(retval, features, codes, warnings)`` -- pass nothing
    and consume the tuple. The old byref-VARIANT idiom leaves those VARIANTs
    UNWRITTEN under InvokeTypes, so it silently reported every model clean (a
    broken assembly would slip the deep-health gate). Empty when the model is
    clean or the call is unavailable.
    """
    ext = _read_member(model, "Extension")
    if ext is None:
        return []
    ext = _early_bound(ext, "IModelDocExtension")
    res = adapter._attempt(lambda: ext.GetWhatsWrong(), default=None)
    if not res:
        return []
    _retval, feats, codes, warns = res
    feats = list(feats or [])
    codes = list(codes or [])
    warns = list(warns or [])
    out: list[tuple[str, int, bool]] = []
    for i, feat in enumerate(feats):
        name = "?"
        if feat is not None:
            feat = _early_bound(feat, "IFeature")
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
    raw_model = model or adapter.currentModel
    model_doc = _early_bound(raw_model, "IModelDoc2", "ForceRebuild3")
    asm_doc = _early_bound(raw_model, "IAssemblyDoc", "GetComponents")
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
                rebuilt = adapter._attempt(
                    lambda: model_doc.ForceRebuild3(False), default=None
                )

            targets = [(label or "top", model_doc)]
            if deep:
                comps = adapter._attempt(
                    lambda: asm_doc.GetComponents(False), default=None
                ) or []
                for comp in comps:
                    # Wrap once as IComponent2 so GetModelDoc2 invokes its known
                    # DISPID; Name2 remains a property read.
                    comp = _early_bound(comp, "IComponent2", "GetModelDoc2")
                    name = str(_read_member(comp, "Name2"))
                    if "/" in name:  # top-level instances only; their docs cover nested parts
                        continue
                    sub = adapter._attempt(lambda c=comp: c.GetModelDoc2(), default=None)
                    if sub is not None and sub is not raw_model:
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
        body = _early_bound(body, "IBody2")
        fault = adapter._attempt(lambda b=body: b.Check3, default=None)
        if fault is None:
            continue
        fault = _early_bound(fault, "IFaultEntity")
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
    model = _early_bound(adapter.currentModel, "IModelDoc2", "ShowNamedView2")
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
    requested = {f"{asm_name}_{view}.png" for view in views}
    for stale in png_dir.glob(f"{asm_name}_*.png"):
        if stale.name not in requested:
            stale.unlink()
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
    # Establish a clean solved state for the health and pose gates.
    final_rebuild_before_save(adapter, asm_name)
    # Fail fast: never save a broken assembly. Catches mate errors (e.g. a gear
    # mate whose entity went suppressed = the silent drive-train corruption) that
    # the DOF and interference gates miss -- a fixed/grounded component passes
    # the DOF gate even with broken mates. deep=True also inspects each
    # subassembly's own document, where a sub's internal mate errors live.
    assert_model_healthy(adapter, label=asm_name, deep=True, rebuilt=True)
    # ... and never save a solver-drifted one: every placed component must
    # still sit at its authored pose after the FINAL solve (see _POSE_LEDGER).
    assert_pose_ledger(adapter)
    OUT_SLDASM.mkdir(parents=True, exist_ok=True)
    asm_path = (OUT_SLDASM / f"{asm_name}.SLDASM").resolve()
    # Save on isometric so the .SLDASM opens isometric; runs AFTER any
    # remap_front_to_machine_front (which re-bases the standard views) so the
    # re-based Front/Back/etc. used by the gallery stay correct.
    set_isometric_view(adapter)
    # Gate reads and view setup can touch solve state. Rebuild again at the actual
    # save chokepoint; the earlier solve+pose check proves this solve is idempotent.
    final_rebuild_before_save(adapter, asm_name)
    _save_new_assembly_as_copy(adapter, asm_path)
    try:
        # Record the resolved-geometry fingerprint of the just-built assembly so a
        # later in-place refresh of it (unchanged) is a true no-op and never bumps
        # the md5 -- otherwise the first refresh after a from-scratch build would
        # re-save once and cascade up the tree (see save_assembly_in_place /
        # _massprops_sidecar).
        digest = await assembly_geometry_digest(adapter, asm_name)
        sidecar = _massprops_sidecar(asm_name)
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(digest + "\n", encoding="utf-8")
        artefacts = {"assembly": str(asm_path)}
        artefacts.update(await _export_assembly_images(adapter, asm_name, views))
    finally:
        _discard_copy_source(adapter)
    # Reopen the just-saved artifact and reconcile its persisted rebuild mark
    # (issue #267): the ForceRebuild3(False) above dirtied every referenced child
    # part IN MEMORY, so the copy-save recorded a rebuild stamp absent from the
    # on-disk parts and a fresh open would report NeedsRebuild2 != 0. Runs after
    # the copy source is discarded so the reopen loads clean children from disk.
    await reconcile_saved_rebuild_state(adapter, asm_name, asm_path)
    return artefacts


@_telemetry.traced("assembly.save_copy")
def _save_new_assembly_as_copy(adapter: Any, asm_path: Any) -> None:
    """Save a freshly built assembly without rewriting referenced artifacts.

    Creating a native component pattern marks its seed component document dirty.
    A plain ``SaveAs3(..., options=0)`` then raises the blocking "Component
    documents must be saved" dialog. Save the new assembly as a copy with
    Silent (1) | Copy (2) | AvoidRebuildOnSave (8): Copy writes the assembly
    while leaving the dirty seed documents alone, and the assembly task never
    rewrites artifacts owned by part or child-assembly tasks. The full-build path
    always owns a new, unsaved assembly document; refreshes use
    :func:`save_assembly_in_place` instead.

    ``SaveAs3``'s integer return is unreliable across late-bound COM, so success
    is gated on this call producing a new, non-empty target file.
    """
    options = 1 | 2 | 8
    model = adapter.currentModel
    if asm_path.exists():
        adapter._attempt(lambda: adapter.swApp.CloseDoc(str(asm_path)), default=None)
        asm_path.unlink()

    result = adapter._attempt(
        lambda: model.SaveAs3(str(asm_path), 0, options), default=None
    )
    if not asm_path.exists() or asm_path.stat().st_size <= 0:
        raise RuntimeError(
            f"SaveAs3(Silent|Copy|AvoidRebuild) produced no file: "
            f"{asm_path} (rc={result!r})"
        )
    _telemetry.success(f"save assembly copy -> {asm_path} (rc={result!r})")


@_telemetry.traced("assembly.discard_copy_source")
def _discard_copy_source(adapter: Any) -> None:
    """Close the dirty untitled source left active by ``SaveAs3(..., Copy)``."""
    model = adapter.currentModel
    title = adapter._attempt(lambda: str(model.GetTitle()), default="")
    if not title:
        raise RuntimeError("cannot discard copy-saved assembly without its title")

    adapter.swApp.CloseDoc(title)
    still_open = adapter._attempt(
        lambda: adapter.swApp.GetOpenDocument(title), default=None
    )
    if still_open is not None:
        raise RuntimeError(f"copy-saved assembly source remained open: {title}")
    adapter.currentModel = None
    _telemetry.success(f"discard dirty assembly source {title!r}")

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


def saved_rebuild_status(adapter: Any, model: Any = None) -> int:
    """Read ``IModelDocExtension.NeedsRebuild2`` from the active document."""
    target = adapter.currentModel if model is None else model
    extension = _read_member(target, "Extension")
    if extension is None:
        raise RuntimeError("active document has no IModelDocExtension")
    status = _read_member(extension, "NeedsRebuild2")
    if status is None:
        raise RuntimeError("IModelDocExtension.NeedsRebuild2 is unavailable")
    return int(status)


def assert_saved_rebuild_clean(adapter: Any, label: str) -> None:
    """Fail when a freshly opened saved assembly still requests a rebuild."""
    status = saved_rebuild_status(adapter)
    if status != 0:  # swModelRebuildStatus_e bitmask: 1 non-frozen, 2 frozen
        raise RuntimeError(
            f"{label}.SLDASM opens with NeedsRebuild2={status}; "
            "the persisted model was not fully rebuilt before save"
        )
    _telemetry.success(f"saved rebuild state clean ({label})")


def final_rebuild_before_save(adapter: Any, label: str, model: Any = None) -> None:
    """Deep-rebuild after all gates and prove the exact state being saved clean.

    Interference/health inspection can touch solve state after an earlier
    rebuild.  This final chokepoint runs after every mutating/gating operation,
    immediately before Save3/SaveAs3, so the persisted assembly cannot inherit
    a non-frozen ``NeedsRebuild2`` flag (issue #202).
    """
    target = adapter.currentModel if model is None else model
    with _telemetry.span("assembly.final_rebuild", asm=label) as sp:
        rebuilt = adapter._attempt(
            lambda: target.ForceRebuild3(False), default=None
        )
        status = saved_rebuild_status(adapter, target)
        sp.set_attribute("needs_rebuild", status)
        if rebuilt is False or rebuilt is None:
            raise RuntimeError(f"{label}: final ForceRebuild3 returned {rebuilt!r}")
        if status != 0:
            raise RuntimeError(
                f"{label}: final rebuild left NeedsRebuild2={status}; refusing save"
            )
        _telemetry.success(f"final rebuild clean before save ({label})")


async def reconcile_saved_rebuild_state(adapter: Any, asm_name: str, asm_path: Any) -> None:
    """Reopen a just-saved assembly and, if it loads needing a rebuild, EditRebuild3
    + in-place Save3 so the persisted artifact reopens clean (issue #267).

    Root cause (proven by ``diagnostics/probe_rebuild_matrix.py`` /
    ``probe_child_dirty.py``): ``final_rebuild_before_save`` and the deep health
    gate each ``ForceRebuild3(False)`` -- a DEEP rebuild that descends into every
    subassembly and marks every referenced child part document dirty IN MEMORY
    (``GetSaveFlag`` -> True). The ensuing copy/in-place save then records rebuild
    stamps that don't exist on the untouched on-disk parts, so a later fresh open
    reports ``NeedsRebuild2 != 0`` even though geometry is correct and nothing is
    faulted (``GetWhatsWrong`` clean, all components fully constrained). Neither
    ``EditRebuild3`` nor ``ForceRebuild3(True)`` (TopOnly) dirties the children, so
    reopening from disk (children clean) + ``EditRebuild3`` reconciles the assembly,
    and the in-place ``Save3`` persists the clean mark WITHOUT rewriting any part
    file. A post-``ForceRebuild3(False)`` rebuild in the SAME document instance
    cannot un-dirty it -- the reopen is required. ``verify:soundness``'s
    ``saved-rebuild-clean`` gate is the independent backstop that this held.
    """
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    with _telemetry.span("assembly.reconcile_rebuild", asm=asm_name) as sp:
        await adapter.open_model(str(asm_path))
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        status = saved_rebuild_status(adapter, model)
        sp.set_attribute("needs_rebuild_on_open", status)
        if status == 0:
            _telemetry.success(f"saved artifact already clean, no reconcile ({asm_name})")
            return
        rebuilt = adapter._attempt(lambda: model.EditRebuild3(), default=None)
        if rebuilt is False or rebuilt is None:
            raise RuntimeError(
                f"{asm_name}: reconcile EditRebuild3 returned {rebuilt!r}")
        result = adapter._attempt(lambda: model.Save3(1, 0, 0), default=None)  # Silent, in place
        in_mem = saved_rebuild_status(adapter, model)
        if in_mem != 0:
            raise RuntimeError(
                f"{asm_name}: reconcile left NeedsRebuild2={in_mem} after EditRebuild3+Save3 "
                f"(save result={result!r})")
        _telemetry.success(f"reconciled saved rebuild state ({asm_name}, was {status})")


async def assembly_geometry_digest(adapter: Any, asm_name: str) -> str:
    """A deterministic fingerprint of an assembly's RESOLVED geometry across every
    configuration: exact-BREP mass properties (mass / volume / surface area / centre
    of mass / moments of inertia) PLUS every top-level component's rounded pose (the
    aggregates alone are blind to a light component re-solving elsewhere -- codex
    #241). It changes iff a component's geometry changed or moved >= 0.1 mm and
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
        if multi and active_configuration_name(adapter) != cfg:
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
        # Per-top-level-component POSE rows (codex #241): the aggregates above
        # are blind to a LIGHT component moving -- a 10 g screw re-solving 5 mm
        # over shifts the whole-assembly COM by ~10 um, far under the 1e-4
        # rounding -- exactly the branch-flip class the refresh gates exist to
        # catch. Folding each top-level component's rounded pose makes any
        # >= 0.1 mm rigid re-solve flip the fingerprint (-> gates + save),
        # while a reload of unchanged parts re-solves to identical poses
        # (solver noise ~1e-12 is absorbed by the rounding), so a true no-op
        # stays byte-stable. Child-INTERNAL motion is gated by the child's own
        # refresh; the residual cross-child clash a child-internal move could
        # introduce at an unchanged child pose is caught loud by
        # verify:soundness, which reopens every saved assembly on every build.
        # ONE GetComponents walk reading Name2 + Transform2 off each live
        # component -- a per-name component_transform() loop pays an O(n)
        # GetComponentByName scan per component (measured ~140 s for the 122
        # top-level components; this walk is ~seconds). Row shape and sort
        # match the per-name form exactly, so the digest VALUE is unchanged.
        asm = adapter.currentModel
        comps = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
        pose_rows = []
        for comp in comps:
            a16 = [float(v) for v in _read_member(
                _read_member(comp, "Transform2"), "ArrayData")]
            pose_rows.append((
                str(_read_member(comp, "Name2")),
                tuple(round(v, 6) for v in a16[0:9]),
                tuple(round(v, 4) for v in a16[9:12]),
            ))
        rows.extend((cfg, *pr) for pr in sorted(pose_rows))
    if multi and rest is not None and active_configuration_name(adapter) != rest:
        check(f"re-activate {rest}", await adapter.set_active_configuration(rest))
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()


def select_mates_folder(adapter: Any, model: Any = None) -> bool:
    """Select the active assembly's Mates folder -- the precondition for
    ``IAssemblyDoc.AutoMateRepair``. The folder is a ``MateGroup`` feature that sits
    at/near the END of the top-level tree, so scan from the back (a couple of COM
    round-trips) instead of walking all ~150 component features forward (~50 s).
    Falls back to a full forward walk if an in-context feature pushed it off the
    tail."""
    if model is None:
        model = adapter.currentModel
    model = _early_bound(
        model,
        "IModelDoc2",
        "GetFeatureCount",
        "FeatureByPositionReverse",
        "FirstFeature",
    )
    count = int(adapter._attempt(lambda: model.GetFeatureCount(), default=0) or 0)
    for i in range(min(count, 8)):  # MateGroup is the last top-level feature (i=0)
        feat = adapter._attempt(lambda i=i: model.FeatureByPositionReverse(i), default=None)
        if feat is None:
            continue
        feat = _early_bound(feat, "IFeature", "GetTypeName2", "Select2")
        if str(adapter._attempt(lambda f=feat: f.GetTypeName2(), default="")) == "MateGroup":
            return bool(adapter._attempt(lambda f=feat: f.Select2(False, 0), default=False))
    feat = adapter._attempt(lambda: model.FirstFeature(), default=None)
    while feat is not None:
        feat = _early_bound(
            feat, "IFeature", "GetTypeName2", "Select2", "GetNextFeature"
        )
        if str(adapter._attempt(lambda f=feat: f.GetTypeName2(), default="")) == "MateGroup":
            return bool(adapter._attempt(lambda f=feat: f.Select2(False, 0), default=False))
        feat = adapter._attempt(lambda f=feat: f.GetNextFeature(), default=None)
    return False
def _rebuild_faults(adapter: Any) -> list[str]:
    """Non-warning What's Wrong entries for the active model, formatted for a log."""
    return [
        f"{name} [{_FEATURE_ERROR.get(code, code)}]"
        for name, code, warn in whats_wrong(adapter, adapter.currentModel)
        if not warn
    ]
def repair_dangling_mates(adapter: Any, model: Any = None) -> int:
    """Auto-heal mates whose referenced topology was re-IDed by a from-scratch part
    rebuild (the "sharp edge"): ``IAssemblyDoc.AutoMateRepair`` re-binds the broken
    mates in place (~5 s) instead of a ~500 s full re-insert/re-mate.

    Returns the count AutoMateRepair reports as repaired. Its own return code is
    ADVISORY ONLY -- it returns PartialSuccess with a large FailedMates array (the
    assembly's already-valid mates, which it cannot "re-repair") even on a fully
    successful heal -- so the CALLER must judge success from a fresh ``whats_wrong``
    + the standard DOF/interference/health gates, never from this code.
    """
    raw_model = adapter.currentModel if model is None else model
    asm = _early_bound(
        raw_model,
        "IAssemblyDoc",
        "AutoMateRepair",
    )
    if not select_mates_folder(adapter, raw_model):
        log("AutoMateRepair: could not select the Mates folder -- skipping repair")
        return 0
    # Early-bound IAssemblyDoc::AutoMateRepair returns its two [out] arrays in the
    # tuple (retval, processed, failed) -- pass nothing, consume the tuple.
    result = adapter._attempt(lambda: asm.AutoMateRepair(), default=None)
    ret, processed, failed = result if result else (-1, None, None)
    n_proc = len(list(processed or [])) if processed is not None else 0
    n_fail = len(list(failed or [])) if failed is not None else 0
    log(f"AutoMateRepair: ret={ret} (1=PartialSuccess is normal) "
        f"re-bound {n_proc} mate(s), {n_fail} already-valid skipped")
    return n_proc
def save_assembly_in_place(
    adapter: Any,
    asm_name: str,
    geometry_changed: bool,
    *,
    model: Any = None,
) -> None:
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
    asm = _early_bound(adapter.currentModel if model is None else model, "IModelDoc2")
    sldasm = OUT_SLDASM / f"{asm_name}.SLDASM"
    if not geometry_changed:
        # No-op refresh: resolved geometry identical to the last save. Do NOT
        # rewrite -- a fresh md5 here would invalidate the parent for nothing.
        log(f"{sldasm.name}: geometry unchanged -- .SLDASM left intact (no md5 bump)")
        return

    # This is the shared last-mile chokepoint for refreshes, config hooks, and
    # verify --auto-repair. Nothing geometry-touching may run between it and Save3.
    final_rebuild_before_save(adapter, asm_name, asm)

    if not bool(adapter._attempt(lambda: asm.GetSaveFlag(), default=True)):
        log(f"{sldasm.name} reported clean -- forcing rewrite for md5 propagation")
        adapter._attempt(lambda: asm.SetSaveFlag(), default=None)

    before = sldasm.stat().st_mtime
    options = 1 | 8  # swSaveAsOptions_Silent | swSaveAsOptions_AvoidRebuildOnSave
    # Early-bound IModelDoc2::Save3 returns its two [out] codes in the tuple
    # (retval, errors, warnings) -- pass literal 0 for the [out] slots and consume
    # the tuple (mirrors io.py's in-place Save3). The byref-VARIANT idiom leaves
    # err/warn unwritten and makes `ret` a truthy tuple under InvokeTypes.
    result = adapter._attempt(lambda: asm.Save3(options, 0, 0), default=None)
    ret, err, warn = result if result else (False, None, None)

    after = sldasm.stat().st_mtime
    if after <= before:
        raise RuntimeError(
            f"{sldasm.name} mtime unchanged after Save3(Silent) "
            f"(ret={ret}, err={err}, warn={warn})")
    log(f"saved {sldasm.name} via Save3(Silent) (ret={ret}, err={err}, "
        f"warn={warn})")
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
    rest/export pose is re-activated and, when the refresh actually changed
    the resolved geometry (mass-properties fingerprint moved, or a mate was
    auto-repaired), the standard gates run: ``assert_components_fully_defined``
    (free DOF), ``check_no_interference`` (overlaps), ``assert_model_healthy``
    (deep mate health). Any gate raises a ``RuntimeError`` naming the culprit
    and the ``.SLDASM`` is left untouched (the in-place save never runs) -- so
    an UNHEALABLE dangling mate (AutoMateRepair could not re-bind it) or a
    geometry change that grows into a neighbour (interference) HALTS the build
    rather than saving a stale/broken artefact. A fingerprint-identical,
    repair-free reload SKIPS the gates (they would re-prove the last gated
    save; ``verify:soundness`` re-proves the artefact independently on every
    build). The caller escalates to a full from-scratch rebuild via the
    ``full`` escape (delete the target + ``doit assembly:<stem>``).
    """
    asm_path = (OUT_SLDASM / f"{asm_name}.SLDASM").resolve()
    if not asm_path.exists():
        raise RuntimeError(
            f"missing assembly {asm_path}; build it from scratch first")
    with _telemetry.span("open", asm=asm_name):
        check(f"open {asm_name}", await adapter.open_model(str(asm_path)))
        opened_rebuild_status = saved_rebuild_status(adapter)
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
                if active_configuration_name(adapter) != cfg:
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
    if rest is not None and active_configuration_name(adapter) != rest:
        with _telemetry.span("reactivate", config=rest):
            check(f"re-activate {rest}", await adapter.set_active_configuration(rest))

    # Establish the solved state inspected by the fingerprint and gates. The save
    # chokepoint performs one final idempotent rebuild after those reads.
    final_rebuild_before_save(adapter, asm_name)

    # Fingerprint BEFORE the gates (v0.18 perf finding 4): the mass-properties
    # digest decides BOTH whether to save (an in-place Save3 always rewrites a
    # fresh md5, which would invalidate the parent even for a no-op reload of
    # unchanged parts) AND whether the gates must run at all. When the
    # reloaded parts left the resolved geometry identical to what the last
    # successful (gated) refresh/build saved -- and nothing was auto-repaired
    # -- the three gates would re-prove exactly what that run already proved,
    # and on the top assembly they are the bulk of the refresh wall-clock
    # (measured 274 s of a 780 s no-op refresh: DOF 115 s + interference 12 s
    # + deep health 147 s). A successful AutoMateRepair forces the changed
    # path even on an unchanged fingerprint (a PID-churn-only rebuild): the
    # re-bound mate state is new and must be re-gated AND re-saved, or every
    # later refresh re-dangles and re-heals the same mates forever.
    digest = await assembly_geometry_digest(adapter, asm_name)
    sidecar = _massprops_sidecar(asm_name)
    try:
        prev = sidecar.read_text(encoding="utf-8").strip()
    except OSError:
        prev = None
    persisted_dirty = opened_rebuild_status != 0
    geometry_changed = prev != digest or repaired_any or persisted_dirty
    if persisted_dirty:
        _telemetry.warn(
            f"refresh {asm_name}: saved artifact opened with "
            f"NeedsRebuild2={opened_rebuild_status}; forcing gates + clean re-save"
        )

    if geometry_changed:
        # Gates -- each already raises a RuntimeError naming the culprit. No
        # fallback: a failure leaves the .SLDASM untouched (the save below
        # never runs).
        assert_manifest_dof_state(adapter, asm_name)
        check_no_interference(adapter)
        assert_model_healthy(adapter, label=asm_name, deep=True)
    else:
        # No-op reload: the per-config rebuild-fault check above already ran
        # clean, the geometry the gates would inspect is fingerprint-identical
        # to the last gated save, and verify:soundness independently reopens
        # the saved artefact and runs the full battery on every build.
        _telemetry.event("refresh.noop_gates_skipped", asm=asm_name)
        log(f"refresh {asm_name}: fingerprint unchanged, no repairs -- gates "
            "skipped (proven by the last gated save; verify:soundness "
            "re-proves the artefact independently)")

    with _telemetry.span("save", asm=asm_name, changed=geometry_changed):
        if geometry_changed:
            set_isometric_view(adapter)  # opens isometric; only when we actually re-save
        save_assembly_in_place(adapter, asm_name, geometry_changed)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(digest + "\n", encoding="utf-8")

    artefacts = {"assembly": str(asm_path)}
    artefacts.update(await _export_assembly_images(adapter, asm_name, views))
    # Same #267 reconcile the full-build path runs: the in-place Save3 followed a
    # final_rebuild_before_save (ForceRebuild3(False)) that dirtied the children in
    # memory, so a fresh open would report needs-rebuild. Only when we actually
    # re-saved -- a no-op reload left the (already-reconciled) artifact untouched
    # and byte-stable, and reopening it would needlessly bump the parent's md5.
    if geometry_changed:
        await reconcile_saved_rebuild_state(adapter, asm_name, asm_path)
    return artefacts
