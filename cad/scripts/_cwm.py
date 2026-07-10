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
  their dims. Every external dim slot must carry its REAL value -- a 0.0
  re-values the copied dim to zero.
* On the Repeat=True path a re-valued dim's FlipDimension RESETS to False
  (the seed's state is not inherited and the flip array is ignored), so a
  copied external dim must be formulated with the WANTED side as the False
  side -- in practice: an always-positive ladder off a one-sided anchor.
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

from typing import Any

import pythoncom
from win32com.client import VARIANT

import _telemetry
from _common import _flag_only
from solidworks_mcp.adapters.solidworks.assembly import (
    _create_math_transform,
    _mate_group_subfeatures,
    _read_member,
)


def mates_with_owners(adapter: Any, known_prefixes: set[str]) -> list[dict]:
    """EVERY top-level mate in tree order: name, type, owner part prefixes,
    owning instance names; for distance dims also D1 (mm) and the mate's own
    FlipDimension state (its side of the reference).

    ``known_prefixes`` classifies each mate entity's owning component by its
    part stem (instance suffix stripped); anything else -- including a root
    plane, whose ``ReferenceComponent`` is the assembly DOCUMENT (e.g.
    "Assem50"), not empty -- maps to ``"ROOT"``.
    """
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
    comp = adapter.currentModel.GetComponentByName(name)
    if comp is None:
        raise RuntimeError(f"component not found: {name!r}")
    return comp


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
    comp = _component(adapter, name)
    xform = _create_math_transform(adapter, list(array16))
    comp.Transform2 = xform


def copy_with_mates(
    adapter: Any, comp_names: list[str], n_mates: int, values_m: list[float],
    flips: list[bool] | None = None,
) -> None:
    """One native-typed ``CopyWithMates2`` of the given component slice.

    ``values_m`` (metres) maps positionally onto the slice's external-mate
    slots (:func:`external_mate_rows`); entries under dimension-less slots
    are dead. ``flips`` is passed through for completeness -- measured as
    IGNORED on the Repeat path (a re-valued dim resets to flip=False), so
    the caller must formulate external dims False-side (see module doc).

    The call's return value is IGNORED (it lies); the caller validates from
    the model (component-name diff, mate recount, poses, health).
    """
    model = adapter.currentModel
    raw = []
    for name in comp_names:
        c = model.GetComponentByName(name)
        if c is None:
            raise RuntimeError(f"copy_with_mates: component not found: {name!r}")
        raw.append(c._oleobj_)
    args = (
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, raw),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [True] * n_mates),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [None] * n_mates),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, list(values_m)),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n_mates),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL,
                list(flips) if flips is not None else [False] * n_mates),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, [False] * n_mates),
        VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, [0] * n_mates),
    )
    # Span per the COM-operation invariant (AGENTS.md): the multi-second
    # copy+solve must not read as an unsegmented gap in the trace.
    with _telemetry.span("assembly.copy_with_mates",
                         components=len(raw), mates=n_mates):
        adapter._attempt(lambda: model.CopyWithMates2(*args), default=None)
