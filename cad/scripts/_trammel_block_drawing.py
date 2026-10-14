"""Sheet layout and view helpers shared by the two trammel block drawings.

``draw_ch_rocker_arm_tl_trammel_pivot_block`` (MHA-CH-006-TL-14) and
``draw_ch_rocker_arm_tl_trammel_scriber_block`` (MHA-CH-006-TL-15) draw the
same 50 x 38.1 x 19.05 block at 2:1 in the same four views; a drawing script
may not import another, so the layout lives here.

Model frame (the block specs'): X along the block, Y up out of the top face
(the block is Y = -19.05..0), Z from edge A (0) to edge B (38.1). Third-angle
views: the top face above edge B (``*Front``, X right), the end view
(``*Right``, edge A on its right) right of edge B, and edge A (``*Back``,
X running left) beyond.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import visible_component_entities

import ch_rocker_arm_tl_trammel_spec as kit
from _com import _early_bound
from _drawing_common import rebuild_drawing

_PAPER_PER_MM = 0.002  # metres of sheet per model millimetre at 2:1


@dataclass(frozen=True)
class TrammelBlockSheet:
    """Sheet positions (metres) of model points in the four 2:1 views of a
    block spanning ``x0..x1`` along X; each view is placed by its centre."""

    x0: float
    x1: float
    top_center: tuple[float, float] = (0.110, 0.200)
    front_center: tuple[float, float] = (0.110, 0.105)
    right_center: tuple[float, float] = (0.230, 0.105)
    back_center: tuple[float, float] = (0.365, 0.105)

    @property
    def _xc(self) -> float:
        return 0.5 * (self.x0 + self.x1)

    def top(self, x: float, z: float) -> tuple[float, float]:
        """Top face: X right, edge A (Z = 0) at the view's top."""
        cx, cy = self.top_center
        return (
            round(cx + _PAPER_PER_MM * (x - self._xc), 4),
            round(cy + _PAPER_PER_MM * (0.5 * kit.BLOCK_WIDTH - z), 4),
        )

    def front(self, x: float, y: float) -> tuple[float, float]:
        """Edge B: X right, the top face at the view's top."""
        cx, cy = self.front_center
        return (
            round(cx + _PAPER_PER_MM * (x - self._xc), 4),
            round(cy + _PAPER_PER_MM * (y + 0.5 * kit.BLOCK_HEIGHT), 4),
        )

    def right(self, z: float, y: float) -> tuple[float, float]:
        """End view from +X: edge A (Z = 0) on the view's right."""
        cx, cy = self.right_center
        return (
            round(cx + _PAPER_PER_MM * (0.5 * kit.BLOCK_WIDTH - z), 4),
            round(cy + _PAPER_PER_MM * (y + 0.5 * kit.BLOCK_HEIGHT), 4),
        )

    def back(self, x: float, y: float) -> tuple[float, float]:
        """Edge A: X running left, the top face at the view's top."""
        cx, cy = self.back_center
        return (
            round(cx - _PAPER_PER_MM * (x - self._xc), 4),
            round(cy + _PAPER_PER_MM * (y + 0.5 * kit.BLOCK_HEIGHT), 4),
        )


def circle_edge(adapter: Any, view: Any, diameter_mm: float, label: str) -> Any:
    """The first visible circular edge of ``diameter_mm`` in ``view``."""
    radius_m = diameter_mm / 2000.0
    for component in (
        adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    ):
        for raw in visible_component_entities(view, component, 1) or ():
            edge = _early_bound(raw, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if (
                curve.IsCircle()
                and abs(float(curve.CircleParams[6]) - radius_m) <= 1e-6
            ):
                return edge
    raise RuntimeError(f"trammel block view shows no {label}")


_THREAD_LABEL_LAYER = "TRAMMEL-BLOCK-THREAD-LABEL-HIDDEN"


def hide_thread_labels(adapter: Any, view: Any) -> int:
    """Hide a view's cosmetic-thread labels; the hole callouts already state
    every thread (draw_dt_cone_tip_block's hidden-layer recipe, as in
    draw_ch_rocker_arm_tl_inspection_box)."""
    manager = _early_bound(adapter.currentModel.GetLayerManager(), "ILayerMgr")
    if (
        manager.GetLayer(_THREAD_LABEL_LAYER) is None
        and int(
            manager.AddLayer(_THREAD_LABEL_LAYER, "duplicate thread labels", 0, 0, 0)
        )
        != 1
    ):
        raise RuntimeError("failed to add the trammel block thread-label layer")
    layer = _early_bound(manager.GetLayer(_THREAD_LABEL_LAYER), "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("trammel block thread-label layer is not hidden")
    hidden = 0
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        kind = int(annotation.GetType())
        # swCosmeticThread, or the thread's own "Tapped Hole" label note.
        if kind != 1 and not (
            kind == 6
            and "Tapped Hole"
            in str(
                _early_bound(annotation.GetSpecificAnnotation(), "INote").GetText()
                or ""
            )
        ):
            continue
        annotation.Layer = _THREAD_LABEL_LAYER
        if str(annotation.Layer or "") != _THREAD_LABEL_LAYER:
            raise RuntimeError("trammel block cosmetic thread refused the hidden layer")
        hidden += 1
    rebuild_drawing(adapter, label="hide trammel block thread labels")
    return hidden


# draw_dt_cone_tip_block's r3 recipe: a jaw drilled full diameter until it
# opens into the slit states that extent in place of the native blind depth
# ("<HOLE-DEPTH> <hw-depth>"); the diameter stays the Hole Wizard variable.
_BLIND_DEPTH_TOKENS = re.compile(r"<HOLE-DEPTH>\s*<hw-depth>")


def blind_extent_definitions(
    definitions: dict[int, str], extent_text: str
) -> dict[int, str]:
    """Swap the one native blind-depth pair for ``extent_text``, loudly."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected blind callout parts: {definitions!r}")
    hits = {
        part: len(_BLIND_DEPTH_TOKENS.findall(text))
        for part, text in definitions.items()
    }
    if sorted(hits.values()) != [0, 0, 0, 1]:
        raise RuntimeError(
            f"blind callout has no single blind depth to replace: {definitions!r}"
        )
    updated = {
        part: _BLIND_DEPTH_TOKENS.sub(extent_text, text)
        for part, text in definitions.items()
    }
    rewritten = "\n".join(updated.values())
    if "<hw-depth>" in rewritten or "<HOLE-DEPTH>" in rewritten:
        raise RuntimeError(f"blind callout rewrite left a depth: {updated!r}")
    return updated


def set_blind_extent_text(display: Any, extent_text: str, diameter_mm: float) -> None:
    """State ``extent_text`` without severing the diameter's Hole Wizard
    variable (draw_dt_cone_tip_block's ``_set_pinch_clearance_callout_text``)."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = blind_extent_definitions(definitions, extent_text)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = "\n".join(str(display.GetText(part) or "") for part in (1, 2, 3, 4))
    if (
        persisted != updated
        or resolved.count(extent_text) != 1
        or "<HOLE-DEPTH>" in resolved
        or f"{diameter_mm:.2f}" not in resolved
    ):
        raise RuntimeError(
            f"blind callout extent {extent_text!r} did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
