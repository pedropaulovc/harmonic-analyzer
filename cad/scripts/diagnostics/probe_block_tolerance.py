"""Repro: which DimXpert block-tolerance doc-property prefs accept writes.

Backs the get-only claim in ``_common.apply_block_tolerances``: on this seat
(3DEXPERIENCE R2026x) the tolerance METHOD (637) and the linear Tolerance 1/2
VALUES (123/124, meters) set fine, while the decimals prefs (405/406) and the
angular value (126, radians) reject every write — ``SetUserPreference*``
returns False under both int encodings, options 0-3, before/after
ForceRebuild3, and on a saved document — despite the API help
(help.solidworks.com .../swconst/DP_DimXpert.htm) documenting them settable.
If a future SolidWorks version fixes them, this probe shows it and the
template-carried defaults in apply_block_tolerances can move into code.

Creates ONE scratch part and closes only it — safe next to open documents.

    uv run python cad/scripts/diagnostics/probe_block_tolerance.py
"""

from __future__ import annotations

import asyncio
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    _PREF_ANGULAR_VALUE,
    _PREF_DIMXPERT_METHOD,
    _PREF_OPT_NONE,
    _PREF_TOL1_DECIMALS,
    _PREF_TOL1_VALUE,
    _PREF_TOL2_DECIMALS,
    _PREF_TOL2_VALUE,
    _read_member,
)
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402

IN = 0.0254


def _report(label: str, settable: bool, ok: bool) -> None:
    """A write outcome: success when it matches the claim, warn when it deviates
    (a deviation means the get-only claim no longer holds on this seat)."""
    expected = ok if settable else not ok
    emit = _telemetry.success if expected else _telemetry.warn
    emit(f"{label}: ret={ok}" + ("" if expected else " (UNEXPECTED — claim drifted)"))


async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    try:
        await adapter.connect()
        res = await adapter.create_part()
        if not res.is_success:
            raise RuntimeError(f"create_part failed: {res.error}")
        model = adapter.currentModel
        ext = _read_member(model, "Extension")

        def show(tag: str) -> None:
            m = ext.GetUserPreferenceInteger(_PREF_DIMXPERT_METHOD, _PREF_OPT_NONE)
            d1 = ext.GetUserPreferenceInteger(_PREF_TOL1_DECIMALS, _PREF_OPT_NONE)
            d2 = ext.GetUserPreferenceInteger(_PREF_TOL2_DECIMALS, _PREF_OPT_NONE)
            v1 = ext.GetUserPreferenceDouble(_PREF_TOL1_VALUE, _PREF_OPT_NONE)
            v2 = ext.GetUserPreferenceDouble(_PREF_TOL2_VALUE, _PREF_OPT_NONE)
            a = ext.GetUserPreferenceDouble(_PREF_ANGULAR_VALUE, _PREF_OPT_NONE)
            _telemetry.info(
                f"[{tag}] method={m} tol1=({d1}, {v1!r}) tol2=({d2}, {v2!r}) ang={a!r}")

        show("defaults")

        _report("SETTABLE method->block",
                True, ext.SetUserPreferenceInteger(_PREF_DIMXPERT_METHOD, _PREF_OPT_NONE, 0))
        _report("SETTABLE tol1 value 0.02in",
                True, ext.SetUserPreferenceDouble(_PREF_TOL1_VALUE, _PREF_OPT_NONE, 0.02 * IN))
        _report("SETTABLE tol2 value 0.005in",
                True, ext.SetUserPreferenceDouble(_PREF_TOL2_VALUE, _PREF_OPT_NONE, 0.005 * IN))

        for opt in (0, 1, 2, 3):
            _report(f"get-only ang rad(1deg) opt={opt}",
                    False, ext.SetUserPreferenceDouble(_PREF_ANGULAR_VALUE, opt, math.radians(1.0)))
            _report(f"get-only tol1dec raw-3 opt={opt}",
                    False, ext.SetUserPreferenceInteger(_PREF_TOL1_DECIMALS, opt, 3))
            _report(f"get-only tol1dec enum-1 opt={opt}",
                    False, ext.SetUserPreferenceInteger(_PREF_TOL1_DECIMALS, opt, 1))
        model.ForceRebuild3(False)
        _report("get-only ang after ForceRebuild3",
                False, ext.SetUserPreferenceDouble(_PREF_ANGULAR_VALUE, _PREF_OPT_NONE, math.radians(1.0)))
        save_path = str(Path(tempfile.gettempdir()) / "probe_block_tol.SLDPRT")
        saved = await adapter.save_file(save_path)
        if not saved.is_success:
            raise RuntimeError(f"save failed: {saved.error}")
        _report("get-only ang on saved doc",
                False, ext.SetUserPreferenceDouble(_PREF_ANGULAR_VALUE, _PREF_OPT_NONE, math.radians(1.0)))
        _report("get-only ang deg-encoded on saved doc",
                False, ext.SetUserPreferenceDouble(_PREF_ANGULAR_VALUE, _PREF_OPT_NONE, 1.0))

        show("final")

        title = model.GetTitle
        title = title() if callable(title) else title
        adapter.swApp.QuitDoc(title)
        _telemetry.success(f"scratch part closed: {title}")
        return 0
    finally:
        await adapter.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
