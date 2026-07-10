"""Transient free-DOF drive replay, split out of _assembly.py so its churn does
not re-key the 8-assembly BUILD cache.

These functions run ONLY on the verify/diagnostics path -- NEVER on the assembly
BUILD path (no build_<stem>_assembly.py imports them), so they are deliberately
OUTSIDE the assembly recipe/helper closure: load the recorded free-DOF manifest
(``.<stem>.dof.json``, written by ``_assembly.write_dof_manifest``) and author
its drive mates TRANSIENTLY on a reopened model, so verify:kinematics can sweep
the mechanism (the pen Fourier sweep, the magnifier chain proof). Callers MUST
discard the mutated document unsaved (:func:`discard_open_documents`).

Because this module is on NO assembly build closure, a change to it does not bump
any .SLDASM digest -- so verify: tasks depend on it DIRECTLY (see POSTBUILD_PY in
dodo.py) to stay fresh. (The incremental-REFRESH helpers, which ARE build-path,
live in _assembly.py where they ride the assembly recipe -- codex #193.)

Dependencies point ONE way: this module imports helpers from _assembly; _assembly
never imports this module.
"""
from __future__ import annotations

import json

from typing import Any

from _assembly import (
    _mate,
    dof_manifest_path,
)
from _common import _read_member, check

# Transiently authored drive mates are named ``DRIVE_<key>`` so the kinematics
# sweeps can target them (e.g. the pen equation drives ``D1@DRIVE_pen_travel``).
# They exist only in-memory: the caller discards the document unsaved.
DRIVE_PREFIX = "DRIVE_"


def discard_open_documents(adapter: Any) -> None:
    """Close every open document WITHOUT a "Save Modified Documents" prompt.

    The transient-drive paths author real mates (and verify's pen sweep installs
    equations), so the reopened assembly (and its referenced children) are
    DIRTY. ``CloseAllDocuments(True)`` still pops the save modal for a dirty
    referenced child in 3DX R2026x -- headless, that hangs the run forever.
    This mirrors ``cut_release._discard_open_documents``: close the active doc
    by TITLE first (``CloseDoc`` discards a dirty doc without saving, and
    closing the assembly title drops its hidden components too), then
    ``CloseAllDocuments(True)`` as a backstop with nothing dirty left to prompt
    about. Bounded so a misbehaving session can't spin; an empty title is
    refused (``CloseDoc("")`` silently no-ops on assemblies and would leave the
    document resident)."""
    for _ in range(500):
        doc = adapter._attempt(lambda: _read_member(adapter.swApp, "IActiveDoc2"),
                               default=None)
        if doc is None:
            break
        title = str(_read_member(doc, "GetTitle") or "")
        if not title:
            raise RuntimeError(
                "active document has an empty title -- refusing CloseDoc(''), which "
                "silently no-ops on assemblies and would leave the document resident"
            )
        adapter._attempt(lambda t=title: adapter.swApp.CloseDoc(t), default=None)
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)


def load_dof_manifest(name: str) -> list[dict[str, Any]]:
    """Read the free-DOF drive specs for ``<name>.SLDASM`` (``[]`` if none)."""
    path = dof_manifest_path(name)
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("specs", [])


async def _rename_drive_mate(adapter: Any, mate: Any, key: str) -> str:
    """Rename a just-authored transient drive mate to ``DRIVE_<key>``.

    ``mate`` is the dict :func:`_assembly._mate` returns (it carries the SW
    feature ``name``). Renaming uses ``IFeature::Name`` via the adapter's
    ``rename_feature``. ``DRIVE_<key>`` must be unique in the tree (distinct
    keys) and free of SW-reserved characters. Returns the new name."""
    from solidworks_mcp.adapters.base import RenameFeatureParameters

    old = mate.get("name") if isinstance(mate, dict) else str(mate)
    if not old:
        raise RuntimeError(f"_rename_drive_mate: mate has no resolvable name ({mate!r})")
    new = f"{DRIVE_PREFIX}{key}"
    check(
        f"rename drive mate {old!r} -> {new!r}",
        await adapter.rename_feature(RenameFeatureParameters(old_name=old, new_name=new)),
    )
    return new


async def author_dof_drives(adapter: Any, specs: list[dict[str, Any]]) -> list[str]:
    """Author the given free-DOF drive specs on the ACTIVE assembly and rename
    each ``DRIVE_<key>``; return the new names.

    Used by verify:kinematics (and the mobility/motion diagnostics) to pin or
    sweep a freed operational DOF on a reopened model -- TRANSIENTLY, the caller
    discards the document unsaved. Reconstructs each :class:`MateEntityRef` from
    the recorded fields and authors the exact mate on the RECORDED side
    (``spec["flip"]`` -- the build's sign-derived seat, #185), with the original
    flip-recovery ``verify`` target as the safety net, then re-solves."""
    from solidworks_mcp.adapters.base import MateEntityRef

    names: list[str] = []
    for spec in specs:
        entities = [MateEntityRef(**e) for e in spec["entities"]]
        verify = None
        if spec.get("verify"):
            verify = (spec["verify"][0], list(spec["verify"][1]))
        witness = None
        if spec.get("witness"):
            # The recorded off-origin branch witness (#154): local point +
            # authored world position, so a flip-ambiguous angle replay fails
            # loud on the wrong lean exactly like the build would.
            witness = (list(spec["witness"][0]), list(spec["witness"][1]))
        res = await _mate(
            adapter,
            f"transient drive {spec['key']}",
            spec["kind"],
            entities,
            verify=verify,
            witness=witness,
            flip=bool(spec.get("flip", False)),
            **spec.get("params", {}),
        )
        names.append(await _rename_drive_mate(adapter, res, spec["key"]))
    if names:
        adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    return names
