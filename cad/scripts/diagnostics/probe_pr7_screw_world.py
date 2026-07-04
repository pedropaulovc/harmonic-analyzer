r"""Throwaway (PR7): where do the base-engaging screws sit in the saved
drive-train.SLDASM, world frame? The top-level gate reports all 8 fully
buried in the base -- compare each screw's world (x, z) against the base's
authored hole stations to see the misalignment's shape (x-flip? z-flip?).
"""

from __future__ import annotations

import asyncio

from _common import OUT_SLDASM, _flag, _read_member, log
from _assembly import component_transform


SCREWS = (
    "cone-pivot-screw-1",
    "swing-stop-screw-1",
    "slotted-screw-1",
    "slotted-screw-2",
    "slotted-screw-3",
    "slotted-screw-4",
    "foot-screw-1",
    "foot-screw-2",
)


async def main():
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    dt = (OUT_SLDASM / "drive-train.SLDASM").resolve()
    adapter = PyWin32Adapter({})
    await adapter.connect()
    await adapter.open_model(str(dt))
    doc = adapter.currentModel
    _flag(doc, "IModelDoc2")
    log(f"opened {str(_read_member(doc, 'GetTitle'))!r}")
    for name in SCREWS:
        try:
            a = component_transform(adapter, name)
            log(f"{name}: origin=({a[9]*1000:.2f}, {a[10]*1000:.2f}, {a[11]*1000:.2f})")
        except Exception as e:  # noqa: BLE001
            log(f"{name}: <{e}>")
    await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
