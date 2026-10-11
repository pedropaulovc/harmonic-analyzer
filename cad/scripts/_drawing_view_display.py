"""Hidden-line drawing-view display modes and verified transitions.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
from _com import _early_bound


_SW_HLV = 1  # swDisplayMode_e.swHIDDEN_GREYED


_SW_HLR = 2  # swDisplayMode_e.swHIDDEN


def set_hidden_lines_removed(adapter: Any, view: Any) -> None:
    """Remove the hidden edges from ``view`` -- the print's default.

    The mirror of ``set_hidden_lines_visible``, and idempotent for the same
    two reasons: ``SetDisplayMode4`` returns False for a same-mode set (a
    no-op, not a failure), so the RESULT is what gets asserted, and passing
    through the other mode makes the call a real regen -- an annotation
    attached after placement can leave a view's edge set unregenerated.
    """
    bound = _early_bound(view, "IView")
    bound.SetDisplayMode4(False, _SW_HLV, False, False, True)
    mode = int(bound.GetDisplayMode2())
    if mode != _SW_HLV:
        raise RuntimeError(
            f"failed to transition drawing view through HLV (mode reads {mode})"
        )
    bound.SetDisplayMode4(False, _SW_HLR, False, False, True)
    mode = int(bound.GetDisplayMode2())
    if mode != _SW_HLR:
        raise RuntimeError(
            f"failed to set hidden-lines-removed drawing view (mode reads {mode})"
        )


def set_hidden_lines_visible(adapter: Any, view: Any) -> None:
    """Show hidden edges (greyed) in ``view`` -- for a view whose job is to
    communicate internal/cross-drilled features.

    Always passes through HLR first. ``SetDisplayMode4`` returns False for a
    same-mode set (a no-op, not a failure), and a view already reading HLV can
    still export WITHOUT its dashed edges: an annotation attached to it after
    placement (rocker-arm-support's seat finish symbol, 2026-09-09) leaves the
    HLV edge set unregenerated and ``UpdateViewDisplayGeometry`` does not
    rebuild it — only a real mode change does. The toggle makes the call
    idempotent AND a regen, so recipes re-assert it after annotating a view.
    """
    bound = _early_bound(view, "IView")
    bound.SetDisplayMode4(False, _SW_HLR, False, False, True)
    mode = int(bound.GetDisplayMode2())
    if mode != _SW_HLR:
        raise RuntimeError(
            f"failed to transition drawing view through HLR (mode reads {mode})"
        )
    bound.SetDisplayMode4(False, _SW_HLV, False, False, True)
    mode = int(bound.GetDisplayMode2())
    if mode != _SW_HLV:
        raise RuntimeError(
            f"failed to set hidden-lines-visible drawing view (mode reads {mode})"
        )
