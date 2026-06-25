r"""Diagnostic: instrument the transgear-removable pin-hole dim failure in situ.

Replays the full build with ``_common.dimension_between`` patched to dump
sketch state, over-defining relations, and fallback attempts the moment the
``horizontal_distance pin hole +X`` dim fails (minimal repro attempts on a
bare/disc part all PASS — the failure needs the real gear context).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_transgear_pin.py
"""

from __future__ import annotations

import sys

import _common
import _telemetry
import build_transgear_removable as btr

_orig = _common.dimension_between


async def _patched(adapter, ref1, ref2, kind, value, label):
    try:
        return await _orig(adapter, ref1, ref2, kind, value, label)
    except RuntimeError as exc:
        _telemetry.warn(f"dim FAILED, dumping diagnostics: {exc}")
        st = await adapter.check_sketch_fully_defined()
        _telemetry.debug(f"state: {st.data if st.is_success else st.error!r}")
        over = await adapter.get_over_defining_relations()
        _telemetry.debug(f"over-defining: {over.data if over.is_success else over.error!r}")
        retry = await adapter.add_sketch_dimension(ref1, ref2, kind, value)
        _telemetry.debug(f"retry same dim: {retry.is_success}"
                         + ("" if retry.is_success else f" [{retry.error}]"))
        if retry.is_success:
            return retry
        aligned = await adapter.add_sketch_dimension(ref1, ref2, "distance", value)
        _telemetry.debug(f"aligned 'distance' fallback: {aligned.is_success}"
                         + ("" if aligned.is_success else f" [{aligned.error}]"))
        swapped = await adapter.add_sketch_dimension(ref2, ref1, kind, value)
        _telemetry.debug(f"swapped-operand retry: {swapped.is_success}"
                         + ("" if swapped.is_success else f" [{swapped.error}]"))
        raise


_common.dimension_between = _patched

if __name__ == "__main__":
    sys.exit(_common.run_build(btr.build))
