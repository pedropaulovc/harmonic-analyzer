"""Controlled matrix: which {rebuild verb} x {save options} persists NeedsRebuild2=0.

Every trial starts from the SAME pristine-dirty source .SLDASM (a freshly cold-built
assembly that reopens NeedsRebuild2=1) and NEVER writes it:

  - "saveas" trials open the source, apply a rebuild verb, SaveAs3 to a unique temp
    target with the trial's options, close everything, reopen the TARGET and read
    NeedsRebuild2.
  - "save3" trials byte-copy the source to a unique temp name in the same folder,
    open the COPY, apply the verb, Save3(Silent) in place, reopen the copy.

Each trial asserts the source/copy opened with NeedsRebuild2==1 — a trial whose
source opened clean is marked INVALID (this is the confound that poisoned the
earlier probes: some of them saved the source in place, cleaning it for later
trials). The source md5 is checked at start and end.

Trial ordering doubles as the session-stickiness test: EditRebuild3 runs BEFORE any
ForceRebuild3 in the session, and again AFTER — if "Force poisons the session", the
second Edit trial would go dirty.

    HARMONIC_COM_SEAT=1 uv run python cad/scripts/diagnostics/probe_rebuild_matrix.py \
        C:/src/harmonic-analyzer/.claude/worktrees/main_control/cad/out/sldasm/frame.SLDASM
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import _early_bound, _read_member  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

OUT = Path(__file__).resolve().parents[3] / "cad" / "out" / "sldasm"

SILENT, COPY, AVOID = 1, 2, 8


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _nr(model) -> int:
    ext = _read_member(model, "Extension")
    v = _read_member(ext, "NeedsRebuild2")
    return int(v) if v is not None else -999


def _cfg_state(adapter, model) -> str:
    """Per-configuration NeedsRebuild / AddRebuildSaveMark summary."""
    names = adapter._attempt(lambda: model.GetConfigurationNames(), default=None) or []
    cfgmgr = _read_member(model, "ConfigurationManager")
    active = _read_member(cfgmgr, "ActiveConfiguration") if cfgmgr else None
    active_name = _read_member(_early_bound(active, "IConfiguration"), "Name") if active else "?"
    bits = []
    for n in names:
        cfg = adapter._attempt(lambda n=n: model.GetConfigurationByName(n), default=None)
        if cfg is None:
            bits.append(f"{n}:?")
            continue
        cfg = _early_bound(cfg, "IConfiguration")
        nrb = _read_member(cfg, "NeedsRebuild")
        mark = _read_member(cfg, "AddRebuildSaveMark")
        bits.append(f"{n}{'*' if n == active_name else ''}:needs={nrb} mark={mark}")
    return " | ".join(bits)


async def _open_fresh(adapter, path: Path):
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    await adapter.open_model(str(path))
    return _early_bound(adapter.currentModel, "IModelDoc2")


def _apply_verb(adapter, model, verb: str) -> list:
    ext = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
    rcs = []

    def call(fn):
        rcs.append(adapter._attempt(fn, default="EXC"))

    if verb == "none":
        pass
    elif verb == "force":
        call(lambda: model.ForceRebuild3(False))
    elif verb == "edit":
        call(lambda: model.EditRebuild3())
    elif verb == "force_then_edit":
        call(lambda: model.ForceRebuild3(False))
        call(lambda: model.EditRebuild3())
    elif verb == "edit_then_force":
        call(lambda: model.EditRebuild3())
        call(lambda: model.ForceRebuild3(False))
    elif verb == "ext_edit_all":
        call(lambda: ext.EditRebuildAll())
    elif verb == "ext_force_all":
        call(lambda: ext.ForceRebuildAll())
    elif verb == "ext_rebuild_1":  # swRebuildAll
        call(lambda: ext.Rebuild(1))
    elif verb == "ext_rebuild_2":  # swForceRebuildAll
        call(lambda: ext.Rebuild(2))
    elif verb == "force_then_ext1":
        call(lambda: model.ForceRebuild3(False))
        call(lambda: ext.Rebuild(1))
    elif verb == "force_then_editall":
        call(lambda: model.ForceRebuild3(False))
        call(lambda: ext.EditRebuildAll())
    elif verb == "force_then_forceall":
        call(lambda: model.ForceRebuild3(False))
        call(lambda: ext.ForceRebuildAll())
    elif verb == "forcetop":
        call(lambda: model.ForceRebuild3(True))
    elif verb == "force_then_mates":
        call(lambda: model.ForceRebuild3(False))
        call(lambda: ext.Rebuild(4))  # swUpdateMates
    elif verb == "force_then_flag_edit":
        call(lambda: model.ForceRebuild3(False))
        call(lambda: model.SetSaveFlag())
        call(lambda: model.EditRebuild3())
    elif verb == "force_markall":
        call(lambda: model.ForceRebuild3(False))
        cfgmgr = _early_bound(_read_member(model, "ConfigurationManager"), "IConfigurationManager")
        call(lambda: cfgmgr.AddRebuildSaveMark(2, ""))  # swAllConfiguration
    else:
        raise ValueError(verb)
    return rcs


RESULTS = []


async def _trial(adapter, src: Path, idx: int, verb: str, mode: str, opts: int):
    tag = f"{idx:02d} {mode:<6} verb={verb:<15} opts={opts}"
    t0 = time.time()
    tmp_files = []
    try:
        if mode == "save3":
            work = src.with_name(f"_mx{idx:02d}_ip.SLDASM")
            shutil.copy2(src, work)
            tmp_files.append(work)
            target = work
            model = await _open_fresh(adapter, work)
        else:
            model = await _open_fresh(adapter, src)
            target = src.with_name(f"_mx{idx:02d}_{verb}.SLDASM")
            tmp_files.append(target)

        opened = _nr(model)
        valid = opened == 1
        verb_rcs = _apply_verb(adapter, model, verb)
        inmem = _nr(model)

        if mode == "save3":
            rc = adapter._attempt(lambda: model.Save3(SILENT, 0, 0), default="EXC")
        else:
            if target.exists():
                target.unlink()
            rc = adapter._attempt(lambda: model.SaveAs3(str(target), 0, opts), default="EXC")

        reopened_model = await _open_fresh(adapter, target)
        reopen = _nr(reopened_model)
        cfg = _cfg_state(adapter, reopened_model)
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)

        line = (f"[{tag}] open={opened}{'' if valid else ' INVALID-SOURCE'} "
                f"verb_rc={verb_rcs!r} inmem={inmem} save_rc={rc!r} "
                f"REOPEN={reopen} {'CLEAN' if reopen == 0 else 'dirty'} "
                f"({time.time()-t0:.0f}s)  cfg[{cfg}]")
        (_telemetry.warn if not valid else _telemetry.info)(line)
        RESULTS.append((idx, mode, verb, opts, opened, inmem, reopen, valid))
    finally:
        for f in tmp_files:
            for _ in range(5):
                try:
                    if f.exists():
                        f.unlink()
                    break
                except PermissionError:
                    time.sleep(1)


async def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "frame"
    src = Path(arg) if arg.lower().endswith(".sldasm") else OUT / f"{arg}.SLDASM"
    src_md5 = _md5(src)
    _telemetry.info(f"source={src}\nsource md5={src_md5} size={src.stat().st_size}")

    adapter = PyWin32Adapter({})
    with _telemetry.span("probe.rebuild_matrix", target=str(src), stem=src.stem):
        await adapter.connect()

        # Baseline: open the source, dump state, close WITHOUT saving.
        model = await _open_fresh(adapter, src)
        _telemetry.info(f"[baseline] source opens NeedsRebuild2={_nr(model)}  "
                        f"cfg[{_cfg_state(adapter, model)}]")
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)

        B = SILENT | COPY | AVOID  # the build's options
        trials = [
            # -- stickiness ordering: edit BEFORE any force in this session --
            ("none", "saveas", B),
            ("edit", "saveas", B),
            ("force", "saveas", B),
            ("edit", "saveas", B),          # edit AGAIN after force ran in-session
            ("force_then_edit", "saveas", B),
            ("edit_then_force", "saveas", B),
            # -- all-config verbs --
            ("ext_edit_all", "saveas", B),
            ("ext_force_all", "saveas", B),
            ("ext_rebuild_1", "saveas", B),
            ("ext_rebuild_2", "saveas", B),
            ("force_markall", "saveas", B),
            # -- save-options sweep --
            ("force", "saveas", SILENT),
            ("force", "saveas", SILENT | COPY),
            ("force", "saveas", SILENT | AVOID),
            ("edit", "saveas", SILENT),
            ("edit", "saveas", SILENT | AVOID),
            ("none", "saveas", SILENT),
            # -- in-place Save3 on byte-copies --
            ("none", "save3", 0),
            ("force", "save3", 0),
            ("edit", "save3", 0),
        ]
        if len(sys.argv) > 2:  # optional subset: comma-separated verbs, saveas @ build opts
            wanted = sys.argv[2].split(",")
            trials = [(v, "saveas", B) for v in wanted]
        for i, (verb, mode, opts) in enumerate(trials, 1):
            await _trial(adapter, src, i, verb, mode, opts)

    end_md5 = _md5(src)
    mutated = end_md5 != src_md5
    msg = f"\nsource md5 end={end_md5} {'** MUTATED **' if mutated else 'UNCHANGED'}"
    (_telemetry.warn if mutated else _telemetry.success)(msg)
    _telemetry.info("\n=== SUMMARY (mode, verb, opts, open, inmem, REOPEN, valid) ===")
    for r in RESULTS:
        _telemetry.info(f"  #{r[0]:02d} {r[1]:<6} {r[2]:<15} opts={r[3]:<2} open={r[4]} inmem={r[5]} "
                        f"reopen={r[6]} {'CLEAN' if r[6] == 0 else 'dirty'}{'' if r[7] else '  INVALID'}")


if __name__ == "__main__":
    asyncio.run(main())
