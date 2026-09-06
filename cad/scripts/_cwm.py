r"""CopyWithMates2 helpers -- one-call replication of a mated component slice.

Production home of the recipe the 2026-07-09 probes validated
(``diagnostics/diag_copy_with_mates.py`` / ``diag_copy_with_mates_slice.py``,
PR #220; full contract in ``memory/v018-perf-review.md``). The empirically
pinned rules this module encodes:

* Every array argument must be a NATIVE-TYPED SAFEARRAY, components as raw
  ``_oleobj_`` pointers -- plain Python lists marshal as ``VT_ARRAY|VT_VARIANT``
  and the mates are SILENTLY dropped.
* The return value LIES (False on success) -- callers judge from the model
  (component diff + mate count + poses), never from the call.
* ``Values``/flip slots enumerate the slice's EXTERNAL mates only (mates
  referencing an entity outside the copied set), tree-ordered among
  themselves; INTERNAL mates are re-bound between the copies and inherit
  their dimension values, but SolidWorks can reset an internal distance
  mate's ``Flipped`` side to false. Match that side to the seed explicitly
  through the documented writable ``IMate2::Flipped`` property. Every
  external dim slot must carry its REAL value -- a 0.0 re-values the copied
  dim to zero.
* FlipDimension is honoured per slot ONLY where that slot is copied with
  Repeat=False + a NewEntityToMateTo entity. On the Repeat=True path a
  re-valued dim's FlipDimension RESETS to False (the seed's state is not
  inherited and the flip array is ignored). So a copied external dim that must
  keep a non-False side, or reference its OWN neighbour instead of the seed's,
  is re-pointed with Repeat=False + its own entity (:func:`resolve_entity`) and
  the wanted ``flips`` -- NOT worked around with an always-positive ladder or a
  post-copy ``ModifyDefinition`` flip-heal. A MIXED Repeat array is valid
  (measured 2026-07-10): flip only the external DIM slot to Repeat=False and
  leave the shared-reference slots on Repeat=True.
* ``FlipAlignment`` is independent of ``FlipDimension``. Re-pointing a slot
  from a root plane to a component plane with the opposite directed normal can
  leave the copied mate unsolvable even when its distance side is correct; set
  ``flip_alignments`` for that slot instead of trying the other distance sign.
* A copy of a slice with FREED operational DOF carries a solver-state
  ATTRACTOR: the solver returns the copied chain to one deterministic wrong
  pose on the free manifold from ANY start, even though every copied mate is
  value/flip/alignment-identical to the seed's and satisfied at the design
  pose. Raw ``Transform2`` puts land exactly and are reverted by the next
  solve; ``SetTransformAndSolve3`` with the whole chain consistent at target
  reverts the same way. Only a real DRIVEN solve rewrites the copied mates'
  stored state: author transient drive mates pinning each free DOF at the
  design pose (exactly like an authored chain), then delete them.

This module is deliberately OUTSIDE ``_assembly.py``: it rides only the
recipe of the build scripts that import it (today ``build_channel_assembly``),
so a change here re-keys those assemblies alone, not the whole fleet.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import _telemetry
from _common import _early_bound, _flag_only

# pywin32 / solidworks_mcp COM imports stay FUNCTION-LOCAL (the _assembly.py
# convention): this module is imported by build_channel_assembly, which the
# SolidWorks-free gates import for pure geometry helpers on machines where
# pywin32 is not installed (it is a sys_platform == 'win32' dependency).


def mates_with_owners(adapter: Any, known_prefixes: set[str]) -> list[dict]:
    """EVERY top-level mate in tree order: name, type, owner part prefixes,
    owning instance names; for distance dims also D1 (mm) and the mate's own
    FlipDimension state (its side of the reference).

    ``known_prefixes`` classifies each mate entity's owning component by its
    part stem (instance suffix stripped); anything else -- including a root
    plane, whose ``ReferenceComponent`` is the assembly DOCUMENT (e.g.
    "Assem50"), not empty -- maps to ``"ROOT"``.
    """
    from solidworks_mcp.adapters.solidworks.assembly import (
        _mate_group_subfeatures,
        _read_member,
    )

    model = adapter.currentModel
    out: list[dict] = []
    for feat in _mate_group_subfeatures(adapter):
        tname = str(_read_member(feat, "GetTypeName2"))
        name = str(_read_member(feat, "Name"))
        mm = flip = None
        if tname == "MateDistanceDim":
            param = adapter._attempt(
                lambda n=name: model.Parameter(f"D1@{n}"), default=None)
            val = _read_member(param, "SystemValue") if param is not None else None
            mm = (val or 0.0) * 1000.0
            data = _read_member(feat, "GetDefinition")
            flip = bool(_read_member(data, "FlipDimension")) if data else None
        mate = _read_member(feat, "GetSpecificFeature2")
        owners: set[str] = set()
        instances: set[str] = set()
        for i in range(2):
            ent = adapter._attempt(
                lambda m=mate, k=i: m.MateEntity(k), default=None)
            owner = _read_member(ent, "ReferenceComponent") if ent else None
            nm = str(_read_member(owner, "Name2") or "") if owner else ""
            part = nm.rsplit("-", 1)[0] if nm else ""
            if part in known_prefixes:
                owners.add(part)
                instances.add(nm)
            else:
                owners.add("ROOT")
        out.append({"name": name, "type": tname, "mm": mm,
                    "owners": frozenset(owners), "instances": instances,
                    "flip": flip})
    return out


def _component(adapter: Any, name: str) -> Any:
    comp = _early_bound(adapter.currentModel, "IAssemblyDoc").GetComponentByName(name)
    if comp is None:
        raise RuntimeError(f"component not found: {name!r}")
    return comp


# --- Copied-mate error diagnostics -----------------------------------------
# `_assembly._mate` fails loud on a hard `swFeatureError_e` for every AUTHORED
# mate (`_mate_hard_error` + the flip-seed MISS raise). A CopyWithMates2 copy
# bypasses that path entirely, so a copied mate that lands UNSOLVED surfaces
# only indirectly -- as a pose assert in the caller ("landed N mm off its
# station"), which names the wrong cause (slot order) for what is really a mate
# SolidWorks refused to solve. These helpers close that gap.

_ERR_NAMES: dict[int, str] = {
    1: "(folder/component rollup)",
    2: "swFeatureErrorRebuild",
    38: "swFeatureErrorMateInvalidEdge",
    39: "swFeatureErrorMateInvalidFace",
    40: "swFeatureErrorMateFailedCreatingSurface",
    41: "swFeatureErrorMateInvalidEntity",
    42: "swFeatureErrorMateUnknownTangent",
    43: "swFeatureErrorMateDanglingGeometry",
    44: "swFeatureErrorMateEntityNotLinear",
    45: "swFeatureErrorMateEntityFailed",
    46: "swFeatureErrorMateOverdefined",
    47: "swFeatureErrorMateIlldefined",
    48: "swFeatureErrorMateBroken",
}
_ALIGN: dict[int, str] = {0: "ALIGNED", 1: "ANTI_ALIGNED", 2: "CLOSEST"}


def whats_wrong_hard_errors(adapter: Any) -> dict[str, int] | None:
    """Hard feature errors via ``GetWhatsWrong`` -- ~20 ms, no MateGroup walk.

    Returns ``None`` when the call yields nothing usable, so the caller can tell
    "cheap read unavailable" from "cheap read says clean" and fall back to the
    traversal scan rather than trusting a silent empty.

    Uses the TUPLE form (``ext.GetWhatsWrong()`` with no args, consuming
    ``(retval, feats, codes, warns)``) that `_assembly.whats_wrong` documents:
    under early binding InvokeTypes collects the three ``out`` arrays into the
    return value and leaves byref VARIANTs UNWRITTEN, which reads as "every
    model clean". Getting that wrong is what made an earlier version of this
    guard believe What's Wrong was unpopulated mid-build.
    """
    from solidworks_mcp.adapters.solidworks.assembly import _read_member

    ext = _read_member(adapter.currentModel, "Extension")
    if ext is None:
        return None
    ext = _early_bound(ext, "IModelDocExtension")
    res = adapter._attempt(lambda: ext.GetWhatsWrong(), default=None)
    if not res or len(res) < 4:
        return None
    _retval, feats, codes, warns = res
    feats, codes, warns = list(feats or []), list(codes or []), list(warns or [])
    out: dict[str, int] = {}
    for i, feat in enumerate(feats):
        code = int(codes[i]) if i < len(codes) else -1
        warn = bool(warns[i]) if i < len(warns) else False
        if code <= 0 or warn or feat is None:
            continue
        out[str(_read_member(_early_bound(feat, "IFeature"), "Name"))] = code
    return out


def _feature_hard_error(feat: Any) -> int:
    """This mate feature's HARD ``swFeatureError_e`` (0 when clean or a warning)."""
    from solidworks_mcp.adapters.solidworks.assembly import _read_member

    code = _read_member(_early_bound(feat, "IFeature"), "GetErrorCode2")
    if code is None:
        return 0  # member genuinely absent (test double / non-feature object)
    # `_read_member` returns the BOUND MEMBER ITSELF when calling it raised, so a
    # failed COM read arrives as a callable -- not as a tuple. Treating that as
    # "no tuple, therefore clean" is a safeguard that fails OPEN: the scan would
    # report a healthy copy while the mate is red. Distinguish it and raise.
    if callable(code):
        raise RuntimeError(
            "GetErrorCode2 could not be read for a mate feature -- the copied-"
            "mate check cannot prove the copy solved, so the build stops rather"
            " than passing an unverified copy")
    # Early-bound GetErrorCode2 returns (code, is_warning) -- the [out] param
    # rides the tuple, so int(result) would crash on it.
    if not isinstance(code, (list, tuple)):
        raise RuntimeError(
            f"GetErrorCode2 returned {type(code).__name__} {code!r}, expected the"
            " (code, is_warning) tuple -- the copied-mate check cannot be trusted")
    if not code[0] or code[1]:
        return 0
    return int(code[0])


def walk_hard_errors(adapter: Any) -> dict[str, int]:
    """Hard mate errors by WALKING MateGroup -- the fallback, not the fast path.

    Correct but expensive, and the cost is getting TO each feature rather than
    reading it: 104 subfeatures measured 5.62 s (~54 ms each) against 0.45 s for
    all 104 `GetErrorCode2` reads. Only used when
    :func:`whats_wrong_hard_errors` cannot answer.
    """
    from solidworks_mcp.adapters.solidworks.assembly import (
        _mate_group_subfeatures, _read_member,
    )

    found: dict[str, int] = {}
    for feat in _mate_group_subfeatures(adapter):
        code = _feature_hard_error(feat)
        if code:
            found[str(_read_member(feat, "Name"))] = code
    return found


def new_mate_errors(adapter: Any) -> dict[str, int]:
    """Hard feature errors that appeared SINCE the last call.

    Prefers `GetWhatsWrong` (~20 ms, no traversal), falling back to the
    MateGroup walk only when that call cannot answer. A/B logged inside a live
    build across 37 copies -- 36 clean plus a failing one -- showed the two
    agree exactly, including ``walk={'Distance32': 47}`` vs
    ``whatswrong={'Distance32': 47}``.

    Fails CLOSED throughout: an unreadable `GetErrorCode2` raises rather than
    counting as clean (:func:`_feature_hard_error`), and a `GetWhatsWrong` that
    returns nothing USABLE re-scans by walking instead of reporting "clean".
    """
    found = whats_wrong_hard_errors(adapter)
    if found is None:
        _telemetry.warn(
            "GetWhatsWrong returned nothing usable -- falling back to the"
            " MateGroup walk so the copied-mate check cannot silently pass")
        found = walk_hard_errors(adapter)

    # Report only errors not already known, so a pre-existing fault is never
    # blamed on this copy (both paths read the WHOLE document).
    known: set[str] = getattr(adapter, "_cwm_known_errors", set())
    adapter._cwm_known_errors = known | set(found)
    return {n: c for n, c in found.items() if n not in known}


def prime_mate_baseline(adapter: Any) -> None:
    """Record the current hard errors so the next call reports only NEW ones."""
    new_mate_errors(adapter)


def mate_error_prose(adapter: Any, names: list[str]) -> dict[str, str]:
    """SolidWorks' OWN wording for each named feature's error.

    No API returns a per-feature description -- `GetWhatsWrong` and
    `GetErrorCode2` both yield only a numeric code, and that code is COARSER
    than the UI text (47's enum blurb is the generic "This mate cannot be
    solved. Consider: deleting / dragging / adding more mates", while the live
    message distinguishes "Planes are parallel but their **alignment is
    reversed**" from the dimension-flipped wording). But SolidWorks writes the
    prose into the SESSION MESSAGE STACK on a rebuild, so:
    drain -> ForceRebuild3 -> read -> split.

    EXPENSIVE (the rebuild dominates, ~22 s measured mid-build) -- failure path
    only. Traps: `GetErrorMessages` is read-and-CLEAR and keeps only the last 20
    messages (drain BEFORE the rebuild or you parse stale text), and every
    problem arrives concatenated into ONE string with no separator
    (``...red error icons.Coincident37: This mate is over...Distance32: The
    components...``), so the split anchors on the feature NAMES, never on
    punctuation. The text is UI-LOCALIZED while the code is not -- decide on the
    code, explain with the text.
    """
    app = getattr(adapter, "swApp", None)
    if app is None:
        return {}

    def _drain() -> list[str]:
        # Three [out] params: call BARE and consume the return tuple
        # (count, Msgs, MsgIDs, MsgTypes). This used to read a byref VARIANT
        # first and fall back to the tuple, because the call site could not know
        # whether `adapter.swApp` was early-bound. `_early_bound` now raises
        # rather than handing back a raw dispatch, so the tuple is the only
        # possible shape and the dual read is gone.
        ret = app.GetErrorMessages()
        if isinstance(ret, (list, tuple)) and len(ret) >= 2:
            return list(ret[1] or [])
        return []

    _drain()  # so we read only what the rebuild below emits
    _early_bound(adapter.currentModel, "IModelDoc2").ForceRebuild3(False)
    blob = "\n".join(_drain())
    hits = sorted((blob.index(f"{n}: "), n) for n in names if f"{n}: " in blob)
    out: dict[str, str] = {}
    for k, (pos, name) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(blob)
        out[name] = " ".join(blob[pos + len(name) + 2:end].split())
    return out


def _mate_state(adapter: Any, name: str) -> str:
    """``IMate2`` alignment/flip state of a named mate feature, for the report."""
    from solidworks_mcp.adapters.solidworks.assembly import _read_member

    # FeatureByName is declared on IAssemblyDoc, not IModelDoc2 (same dispatch).
    doc = _early_bound(adapter.currentModel, "IAssemblyDoc")
    feat = adapter._attempt(lambda: doc.FeatureByName(name), default=None)
    if feat is None:
        return ""
    mate = _read_member(_early_bound(feat, "IFeature"), "GetSpecificFeature2")
    if mate is None:
        return ""
    align = _read_member(mate, "Alignment")
    align_txt = _ALIGN.get(int(align), str(align)) if align is not None else "?"
    return (f"IMate2: type={_read_member(mate, 'Type')}"
            f" alignment={align_txt}"
            f" flipped={_read_member(mate, 'Flipped')}"
            f" canBeFlipped={_read_member(mate, 'CanBeFlipped')}")


def _slot_report(
    n_mates: int,
    values_m: list[float],
    rep: list[bool],
    flip_dim: list[bool],
    flip_align: list[bool],
    ents_src: list[Any],
) -> str:
    """Every CopyWithMates2 slot argument this call actually passed."""
    def _at(seq: list, i: int) -> Any:
        return seq[i] if i < len(seq) else "?"

    lines = []
    for i in range(n_mates):
        val = _at(values_m, i)
        val_txt = f"{val * 1000.0:.4f} mm" if isinstance(val, (int, float)) else "-"
        lines.append(
            f"    slot {i}: repeat={str(_at(rep, i)):5}"
            f" value={val_txt:>14}"
            f" flip_dimension={str(_at(flip_dim, i)):5}"
            f" flip_alignment={str(_at(flip_align, i)):5}"
            f" new_entity={'set' if _at(ents_src, i) is not None else '-'}"
        )
    return "\n".join(lines)


def _assert_copy_solved(
    adapter: Any,
    comp_names: list[str],
    n_mates: int,
    values_m: list[float],
    rep: list[bool],
    flip_dim: list[bool],
    flip_align: list[bool],
    ents_src: list[Any],
) -> None:
    """Raise if the copy just made left any of ITS OWN mates unsolvable."""
    new = new_mate_errors(adapter)
    if not new:
        return

    _telemetry.event(
        "cwm.copied_mate_error",
        components=",".join(comp_names),
        mates=n_mates,
        errors=",".join(f"{n}={c}" for n, c in sorted(new.items())),
    )

    # The prose costs a full ForceRebuild3 -- affordable only because we are
    # aborting anyway. Best-effort: a failure to read it must not swallow the
    # error that matters, so the report degrades to codes rather than raising
    # from inside the reporter.
    try:
        prose = mate_error_prose(adapter, sorted(new))
    except Exception as exc:  # noqa: BLE001
        prose = {}
        _telemetry.warn(f"could not read SolidWorks mate-error prose: {exc!r}")

    detail = []
    for name, code in sorted(new.items()):
        detail.append(f"  {name} -- {_ERR_NAMES.get(code, '?')}"
                      f" (swFeatureError_e {code})")
        text = prose.get(name)
        if text:
            detail.append(f"      SolidWorks: {text}")
        state = _mate_state(adapter, name)
        if state:
            detail.append(f"      {state}")

    raise RuntimeError(
        f"CopyWithMates2 left {len(new)} copied mate(s) UNSOLVED -- copying"
        f" {comp_names} across {n_mates} external-mate slot(s).\n"
        + "\n".join(detail)
        + "\n  slot arguments this call passed:\n"
        + _slot_report(n_mates, values_m, rep, flip_dim, flip_align, ents_src)
        + "\n  FlipAlignment is independent of FlipDimension."
        "  Read the message above before assuming a slot-order bug: an"
        " alignment complaint means the copy's mate is geometrically"
        " unsatisfiable with the passed slot state, NOT necessarily mis-slotted."
        " FlipDimension only picks which side of the dimension is measured;"
        " compare the reported flip_alignment value with the directed normal"
        " of each repeat=False NewEntityToMateTo reference."
    )


def component_mate_count(adapter: Any, name: str) -> int:
    """How many mates reference this component -- ONE ``IComponent2::GetMates``
    call (the API docs' own remedy for the slow mate-list iteration; the
    MateGroup tree walk measured ~20 s per pass on the channel assembly, so
    per-copy validation must not walk the tree)."""
    comp = _component(adapter, name)
    _flag_only(comp, "GetMates")
    mates = adapter._attempt(lambda: comp.GetMates(), default=None)
    return len(mates or [])


def component_constrained_status(adapter: Any, name: str) -> int:
    """The component's ``GetConstrainedStatus`` (swConstrainedStatus_e:
    2 = under-constrained, 3 = fully, 4 = over, 5/6 = no/invalid solution).
    A copied mate that lands unsolvable drives its components to 4-6, so this
    is the cheap per-copy health read (a mate can be CREATED in error state
    without moving anything)."""
    comp = _component(adapter, name)
    _flag_only(comp, "GetConstrainedStatus")
    return int(adapter._attempt(lambda: comp.GetConstrainedStatus(), default=-1))


def external_mate_rows(rows: list[dict], slice_instances: set[str]) -> list[dict]:
    """The slice's EXTERNAL mates in tree order -- the ``Values`` slot order.

    ``rows`` is a :func:`mates_with_owners` read (pre-fetched so one traversal
    serves both the slice count and the slot mapping). A mate is external when
    it touches a slice instance AND references an entity outside the copied
    set (a root plane, or another component). The slot index of each returned
    row is its list position (rule measured 2026-07-09; the sentinel-
    calibration cross-check lives in
    ``diagnostics/diag_copy_with_mates_slice.py --calibrate``).
    """
    return [
        r for r in rows
        if (r["instances"] & slice_instances)
        and ("ROOT" in r["owners"] or (r["instances"] - slice_instances))
    ]


def component_mate_dump(adapter: Any, name: str) -> list[dict]:
    """Per-mate diagnostic read off ``IComponent2::GetMates``: swMateType_e
    ``type``, ``flipped`` side, ``alignment`` and the driving dim (mm, None
    for dimension-less mates). No names -- IMate2 has no feature accessor --
    but positionally comparable between a seed chain and its copy (both
    authored/copied in the same mate order), which is what the copy-vs-seed
    divergence hunt needs."""
    from solidworks_mcp.adapters.solidworks.assembly import _read_member

    comp = _component(adapter, name)
    _flag_only(comp, "GetMates")
    out: list[dict] = []
    for mate in adapter._attempt(lambda: comp.GetMates(), default=None) or []:
        _flag_only(mate, "DisplayDimension2")
        mm = None
        dd = adapter._attempt(lambda m=mate: m.DisplayDimension2(0), default=None)
        if dd is not None:
            dim = _read_member(dd, "GetDimension")
            val = _read_member(dim, "SystemValue") if dim is not None else None
            mm = None if val is None else float(val) * 1000.0
        out.append({
            "type": int(_read_member(mate, "Type") or -1),
            "flipped": bool(_read_member(mate, "Flipped")),
            "alignment": int(_read_member(mate, "Alignment") or -1),
            "mm": mm,
        })
    return out


@_telemetry.traced("copy_with_mates.distance_mate_lookup", label_param="name")
def _component_distance_mate(
    adapter: Any, name: str, distance_mm: float, *, tolerance_mm: float = 0.01,
) -> Any:
    """Return one uniquely-sized distance mate on ``name``.

    ``IComponent2::GetMates`` is the cheap component-local lookup. Matching
    the driving value makes this independent of the mate array's order, which
    differs between an authored seed and its CopyWithMates2 copy.
    """
    from solidworks_mcp.adapters.solidworks.assembly import _read_member

    comp = _component(adapter, name)
    _flag_only(comp, "GetMates")
    matches: list[Any] = []
    for mate in adapter._attempt(lambda: comp.GetMates(), default=None) or []:
        if int(_read_member(mate, "Type") or -1) != 5:  # swMateDISTANCE
            continue
        _flag_only(mate, "DisplayDimension2")
        display = adapter._attempt(
            lambda m=mate: m.DisplayDimension2(0), default=None)
        dim = _read_member(display, "GetDimension") if display is not None else None
        value = _read_member(dim, "SystemValue") if dim is not None else None
        if value is None:
            continue
        if abs(float(value) * 1000.0 - distance_mm) <= tolerance_mm:
            matches.append(mate)
    if len(matches) != 1:
        raise RuntimeError(
            f"{name}: found {len(matches)} distance mates at {distance_mm:.3f} mm;"
            " expected exactly one"
        )
    return matches[0]


def component_distance_mate_flip(
    adapter: Any, name: str, distance_mm: float, *, tolerance_mm: float = 0.01,
) -> bool:
    """Read the side of one uniquely-sized distance mate on ``name``."""
    from solidworks_mcp.adapters.solidworks.assembly import _read_member

    mate = _component_distance_mate(
        adapter, name, distance_mm, tolerance_mm=tolerance_mm)
    return bool(_read_member(mate, "Flipped"))


def ensure_component_distance_mate_flip(
    adapter: Any,
    name: str,
    distance_mm: float,
    expected: bool,
    *,
    tolerance_mm: float = 0.01,
) -> bool:
    """Make one copied distance mate use the seed's side.

    Returns ``True`` only when a write was needed. The official API exposes
    ``IMate2::Flipped`` as a writable property, so this repairs the copied
    INTERNAL mate directly without deleting/re-authoring it or walking the
    assembly's MateGroup tree.
    """
    from solidworks_mcp.adapters.solidworks.assembly import _read_member

    mate = _component_distance_mate(
        adapter, name, distance_mm, tolerance_mm=tolerance_mm)
    current = bool(_read_member(mate, "Flipped"))
    if current == expected:
        return False
    if not bool(_read_member(mate, "CanBeFlipped")):
        raise RuntimeError(
            f"{name}: {distance_mm:.3f} mm mate is not flippable"
        )
    with _telemetry.span(
        "assembly.copy_internal_mate_flip",
        component=name,
        distance_mm=distance_mm,
        from_flip=current,
        to_flip=expected,
    ):
        mate.Flipped = bool(expected)
    readback = bool(_read_member(mate, "Flipped"))
    if readback != expected:
        raise RuntimeError(
            f"{name}: internal distance mate flip readback {readback} != {expected}"
        )
    _telemetry.event(
        "cwm.internal_mate_flip_corrected",
        component=name,
        distance_mm=distance_mm,
        from_flip=current,
        to_flip=expected,
    )
    return True


@dataclass(frozen=True)
class PreparedComponentPoses:
    """Component handles and target transforms for one live assembly document.

    Prepare only after the copied components exist. The caller may change mates
    between resets, but must keep these components and the source document open.
    A reset performs the same ordered Transform2 writes as put_component_pose;
    it does not rebuild, add constraints, or change which DOF remain free.
    """

    _adapter: Any
    _model: Any
    _poses: tuple[tuple[Any, Any], ...]

    def groups(self, component_count: int) -> tuple[PreparedComponentPoses, ...]:
        """Partition ordered component slices without another COM lookup/allocation."""
        if component_count <= 0 or len(self._poses) % component_count:
            raise ValueError("prepared component poses require complete groups")
        return tuple(
            PreparedComponentPoses(
                self._adapter, self._model, self._poses[start:start + component_count]
            )
            for start in range(0, len(self._poses), component_count)
        )

    def apply(self) -> None:
        with _telemetry.span("cwm.pose_reset", components=len(self._poses)) as sp:
            if self._adapter.currentModel is not self._model:
                raise RuntimeError("prepared component poses: assembly document changed")
            written = 0
            try:
                for component, transform in self._poses:
                    component.Transform2 = transform
                    written += 1
            finally:
                sp.set_attribute("pose_writes", written)


def prepare_component_poses(
    adapter: Any, targets: Iterable[tuple[str, list[float]]]
) -> PreparedComponentPoses:
    """Resolve each component and allocate its target transform once, without moving it.

    Repeated resets between transient drivers previously looked up every component
    and allocated the identical IMathTransform again. Keeping these handles within
    the current document preserves the solver sequence while removing that work.
    """
    from solidworks_mcp.adapters.solidworks.assembly import _create_math_transform

    rows = list(targets)
    poses = []
    with _telemetry.span("cwm.pose_prepare", components=len(rows)) as sp:
        for name, array16 in rows:
            component = _component(adapter, name)
            transform = _create_math_transform(adapter, list(array16))
            poses.append((component, transform))
        sp.set_attribute("transform_allocations", len(poses))
    return PreparedComponentPoses(adapter, adapter.currentModel, tuple(poses))


def put_component_pose(adapter: Any, name: str, array16: list[float]) -> None:
    """Reposition a component to ``array16`` WITHOUT a mate solve (an
    ``IComponent2.Transform2`` property put).

    One half of the copy-landing recipe (see the module doc's attractor
    bullet): a put alone is reverted by the next solve (the solver re-solves
    the copied chain from its stored state, not from current positions), and
    a driver alone solves to the NEAREST solution branch -- which, from the
    attractor pose, is the wrong one (measured: the copied channel lever
    solved to the mirror intersection of its J3 pin circles, ~1 mm residuals
    everywhere). So the caller PUTS the chain at the design pose to make the
    design branch the nearest one, authors the transient drivers to rewrite
    the stored state, re-putting between adds (each add re-seats the still-
    free siblings), then deletes the drivers.
    """
    from solidworks_mcp.adapters.solidworks.assembly import _create_math_transform

    comp = _component(adapter, name)
    xform = _create_math_transform(adapter, list(array16))
    comp.Transform2 = xform


def resolve_entity(adapter: Any, ref: Any) -> Any:
    """Resolve a :func:`~_assembly.named_ref` / ``MateEntityRef`` to its live COM
    entity object -- the thing a ``NewEntityToMateTo`` slot wants.

    Selects the ref (reusing the adapter's own per-mark selection logic) and
    harvests it back with ``ISelectionMgr::GetSelectedObject6``, exactly as the
    mate-creation path does. Clears the selection either side so the harvest is
    unambiguous. Raises loud if the ref does not select/resolve -- a silent
    ``None`` here would marshal as a null ``NewEntityToMateTo`` and drop the
    copy's mate reference."""
    from solidworks_mcp.adapters.solidworks.assembly import (
        _harvest_selected,
        _select_mate_entity,
    )

    model = adapter.currentModel
    _flag_only(model, "ClearSelection2")
    adapter._attempt(lambda: model.ClearSelection2(True), default=None)
    if not _select_mate_entity(adapter, ref, 0):
        raise RuntimeError(f"resolve_entity: select failed for {ref!r}")
    ent = _harvest_selected(adapter, model, 1)[0]
    adapter._attempt(lambda: model.ClearSelection2(True), default=None)
    return ent


def copy_with_mates(
    adapter: Any, comp_names: list[str], n_mates: int, values_m: list[float],
    flips: list[bool] | None = None,
    flip_alignments: list[bool] | None = None,
    repeat: list[bool] | None = None,
    new_entities: list[Any] | None = None,
    assert_solved: bool = True,
) -> None:
    """One native-typed ``CopyWithMates2`` of the given component slice.

    ``values_m`` (metres) maps positionally onto the slice's external-mate
    slots (:func:`external_mate_rows`); entries under dimension-less slots
    are dead.

    ``repeat`` (per external-mate slot) chooses each slot's reference source:
    ``True`` reuses the seed's existing mate reference; ``False`` mates the copy
    to ``new_entities[slot]`` instead. Default (``None``) = all-``True`` (the
    seed's references), the legacy behaviour. ``new_entities`` is the matching
    list of resolved COM entities (see :func:`resolve_entity`) or ``None`` per
    slot; only the ``repeat=False`` slots are read. A **MIXED** array is valid
    and measured (2026-07-10): switching only the external DIM slot to
    ``repeat=False`` + own ``new_entities`` + ``flips`` HONOURS FlipDimension on
    that slot while the other slots keep the seed's references untouched -- the
    surgical way to re-point one external dim without re-plumbing the rest.

    ``flips`` (per slot) is the FlipDimension array. It is HONOURED on a
    ``repeat=False`` slot (the copy's re-valued dim lands on the requested side)
    and IGNORED on a ``repeat=True`` slot (that path resets a re-valued dim to
    flip=False -- see module doc). So a dim that must keep a non-False side is
    re-pointed with ``repeat=False`` + its own entity, not left on the Repeat
    path with an always-positive ladder.

    ``flip_alignments`` is the separate CopyWithMates2 ``FlipAlignment``
    array. Use it when a re-pointed entity has the opposite directed normal
    from the seed reference; changing ``FlipDimension`` cannot repair an
    alignment error.

    The call's return value is IGNORED (it lies); the caller validates from
    the model (component-name diff, mate recount, poses, health).

    ``assert_solved`` (default True) closes the copied-mate blind spot: this
    path bypasses `_assembly._mate`, whose `_mate_hard_error` check fails loud on
    every AUTHORED mate, so a copied mate SolidWorks refuses to solve would
    otherwise surface only as the caller's downstream pose assert -- which blames
    the slot map for what is really an unsolvable mate. Any NEW hard
    `swFeatureError_e` this call introduces raises here instead, quoting
    SolidWorks' own wording and dumping every slot argument passed. Cost is two
    `GetWhatsWrong` reads per copy, ~20 ms each; the expensive prose fetch runs
    on the FAILURE path only.
    """
    import pythoncom
    from win32com.client import VARIANT

    model = _early_bound(adapter.currentModel, "IAssemblyDoc")  # IAssemblyDoc: GetComponentByName + CopyWithMates2 only
    raw = []
    for name in comp_names:
        c = model.GetComponentByName(name)
        if c is None:
            raise RuntimeError(f"copy_with_mates: component not found: {name!r}")
        raw.append(c._oleobj_)
    rep = list(repeat) if repeat is not None else [True] * n_mates
    ents_src = new_entities if new_entities is not None else [None] * n_mates
    ents = [e._oleobj_ if e is not None else None for e in ents_src]
    flip_dim = list(flips) if flips is not None else [False] * n_mates
    flip_align = (
        list(flip_alignments)
        if flip_alignments is not None else [False] * n_mates
    )
    args = (
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, raw),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, rep),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, ents),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, list(values_m)),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, flip_align),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, flip_dim),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n_mates),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, [0] * n_mates),
    )
    # Span per the COM-operation invariant (AGENTS.md): the multi-second
    # copy+solve must not read as an unsegmented gap in the trace.
    with _telemetry.span("assembly.copy_with_mates",
                         components=len(raw), mates=n_mates):
        if assert_solved:
            prime_mate_baseline(adapter)  # pre-existing faults are not ours
        adapter._attempt(lambda: model.CopyWithMates2(*args), default=None)
        if not assert_solved:
            return
        _assert_copy_solved(
            adapter,
            comp_names,
            n_mates,
            list(values_m),
            rep,
            flip_dim,
            flip_align,
            ents_src,
        )
