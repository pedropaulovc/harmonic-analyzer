r"""Diagnostic: photograph the live FeatureManager tree as an independent witness
to a COM dump.

``diag_dump_part.py`` walks the tree through COM. If that walk silently drops a
feature (a wrong early-bound flag, a swallowed exception), nothing in the JSON
says so -- the dump just looks complete. This is the second source: the tree the
user is actually looking at.

SolidWorks' FeatureManager is CUSTOM-DRAWN. It exposes panes but no
``TreeControl`` / ``TreeItemControl`` and no item text to UI Automation (probed
2026-07-24 on 2026 SP2.0: the tree lives under ``Tree Container Wnd`` ->
``AfxMDIFrame140u`` with empty ``Name`` at every depth), so there is nothing to
read programmatically -- hence a screenshot, read visually, rather than a text
dump. Icons are a bonus the COM walk cannot give: error/rebuild overlays,
suppression greying, and the rollback-bar position.

Read-only: it activates the window and captures bitmaps. No clicks, no
keystrokes -- nothing that can raise a modal dialog and wedge the COM seat.

``uiautomation`` is NOT a project dependency (this is the only thing that wants
it), so run it with an ephemeral one::

    uv run --with uiautomation python ^
        cad\scripts\diagnostics\diag_ui_feature_tree.py [out-prefix]

Writes ``<prefix>-tree.png`` (the FeatureManager panel) and ``<prefix>-window.png``
(the whole window, i.e. tree + graphics area, so the shape can be checked against
the geometry the dump implies). Defaults the prefix to ``sw-ui``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PREFIX = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sw-ui")

try:
    import uiautomation as auto
except ModuleNotFoundError:  # pragma: no cover - dependency is deliberate
    raise SystemExit(
        "uiautomation is not installed (deliberately -- it is not a project "
        "dependency). Re-run as:\n"
        "  uv run --with uiautomation python "
        "cad\\scripts\\diagnostics\\diag_ui_feature_tree.py"
    ) from None

auto.SetGlobalSearchTimeout(5)


def main() -> int:
    win = next((w for w in auto.GetRootControl().GetChildren()
                if "SOLIDWORKS" in (w.Name or "")), None)
    if win is None:
        print("no SolidWorks top-level window found -- is it running?")
        return 1
    print(f"window: {win.Name}")
    if ".SLD" not in (win.Name or ""):
        print("!! no document in the title bar -- nothing is open to photograph")

    win.SetActive()
    win.SetFocus()
    time.sleep(1.0)  # let the window finish repainting before BitBlt

    # The pane's depth under the top-level window is not stable (it hangs off
    # the active MDI child), so search by name rather than by a fixed level.
    def find(ctrl, name: str, depth: int = 0):
        if depth > 4:
            return None
        for child in ctrl.GetChildren():
            if (child.Name or "") == name:
                return child
            hit = find(child, name, depth + 1)
            if hit is not None:
                return hit
        return None

    tree = find(win, "Tree Container Wnd")
    if tree is None:
        print("!! Tree Container Wnd not found; capturing the window only")
    else:
        out = PREFIX.with_name(f"{PREFIX.name}-tree.png")
        tree.ToBitmap().ToFile(str(out))
        print(f"tree panel  -> {out}  {tree.BoundingRectangle}")

    out = PREFIX.with_name(f"{PREFIX.name}-window.png")
    win.ToBitmap().ToFile(str(out))
    print(f"full window -> {out}  {win.BoundingRectangle}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
