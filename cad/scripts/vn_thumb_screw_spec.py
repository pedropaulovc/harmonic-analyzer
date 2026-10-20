"""McMaster 91882A221 supplier drawing presentation, separate from solid geometry.

Verified 2026-10-19:
https://www.mcmaster.com/mvC/Library/CAD2/20260707/5003FE53/91882A221_Steel%20Raised%20Knurled-Head%20Thumb%20ScrewX.GIF

The displayed inch values are rounded spellings, never replacement model
values: thread length remains exactly 7/16 inch and both heights 3/32 inch.
"""

from __future__ import annotations

SUPPLIER_UNITS = "in"
SUPPLIER_PRECISION = {
    "thread_length": 3,
    "head_height": 3,
    "collar_height": 3,
    "head_diameter": 3,
    "collar_diameter": 2,
    "thread_diameter": 3,
}
SUPPLIER_THREAD = "4-40"
