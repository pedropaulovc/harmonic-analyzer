"""Sheet layout and view helpers shared by the two trammel block drawings.

``draw_ch_rocker_arm_tl_trammel_pivot_block`` (MHA-CH-006-TL-14) and
``draw_ch_rocker_arm_tl_trammel_scriber_block`` (MHA-CH-006-TL-15) draw the
same 50 x 38.1 x 19.05 block at 2:1 in the same four views plus section A-A
through a pinch screw; a drawing script may not import another, so the
layout lives here.

Model frame (the block specs'): X along the block, Y up out of the top face
(the block is Y = -19.05..0), Z from edge A (0) to edge B (38.1). Third-angle
views: the top face above edge B (``*Front``, X right), the end view
(``*Right``, edge A on its right) right of edge B, and edge A (``*Back``,
X running left) beyond.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import visible_component_entities

import ch_rocker_arm_tl_trammel_spec as kit
from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_edges import visible_view_entities
from _drawing_projection import model_point_in_view
from _drawing_sections import create_section_view
from _section_axis import position_section_caption

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


def circle_edge(
    adapter: Any,
    view: Any,
    diameter_mm: float,
    label: str,
    *,
    center_x_mm: float | None = None,
) -> Any:
    """The first visible circular edge of ``diameter_mm`` in ``view``.

    ``center_x_mm`` (model X) picks one of several equal holes, as
    draw_dt_cone_pivot_post's ``_circular_edge`` does: without it SolidWorks'
    enumeration order chooses, and a leader routed for one hole can cross
    another callout to reach the other.
    """
    radius_m = diameter_mm / 2000.0
    for component in (
        adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    ):
        for raw in visible_component_entities(view, component, 1) or ():
            edge = _early_bound(raw, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = curve.CircleParams
            if abs(float(params[6]) - radius_m) > 1e-6:
                continue
            if (
                center_x_mm is not None
                and abs(float(params[0]) * 1000.0 - center_x_mm) > 0.05
            ):
                continue
            return edge
    raise RuntimeError(f"trammel block view shows no {label}")


Point = tuple[float, float, float]


def straight_edge(
    view: Any, label: str, matches: Callable[[Point, Point], bool]
) -> Any:
    """The first visible edge whose two vertices (model mm) satisfy
    ``matches`` in either order (draw_dt_cone_swing_platform's
    ``_horizontal_section_edge`` reads section edges the same way)."""
    for raw in visible_view_entities(view, 1, label=f"trammel block {label}"):
        edge = _early_bound(raw, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        first, second = (
            tuple(
                float(value) * 1000.0
                for value in _early_bound(vertex, "IVertex").GetPoint()
            )
            for vertex in (start, end)
        )
        if matches(first, second) or matches(second, first):
            return edge
    raise RuntimeError(f"trammel block view shows no {label}")


def near(value: float, target: float) -> bool:
    """Model coordinates (mm) agree to the edge finder's 0.01 mm."""
    return abs(value - target) <= 0.01


def mm_in_view(
    adapter: Any, view: Any, xyz_mm: Point, *, label: str
) -> tuple[float, float]:
    """Sheet metres of a model point given in millimetres."""
    return model_point_in_view(
        adapter, view, tuple(value / 1000.0 for value in xyz_mm), label=label
    )


# The cutting line runs this far (model mm) past the top face and the
# bottom, so its arrows and letters stand clear of the outline.
SECTION_LINE_OVERRUN = 3.0


def create_pinch_section(
    adapter: Any,
    front: Any,
    pinch_x: float,
    *,
    view_xy: tuple[float, float],
    caption_xy: tuple[float, float],
    scale: tuple[int, int],
) -> Any:
    """Section A-A through a pinch screw's axis, cut on edge B's view.

    Shows the clearance passage, the slit and the tapped jaw together
    (drawing-guidelines rule 9). Only the cut face prints
    (draw_dt_cone_swing_platform's sections), and the section looks along +X
    so edge A prints on its left and the bar slot opens upward: with
    screen-right r and screen-up u the sight line is u x r, which runs along
    +X exactly when model +Z prints rightward and model +Y upward
    (``_look_holddown_section_south``'s sign test).
    """
    top = mm_in_view(
        adapter,
        front,
        (pinch_x, SECTION_LINE_OVERRUN, kit.BLOCK_WIDTH),
        label="section line top",
    )
    bottom = mm_in_view(
        adapter,
        front,
        (pinch_x, -kit.BLOCK_HEIGHT - SECTION_LINE_OVERRUN, kit.BLOCK_WIDTH),
        label="section line bottom",
    )
    section = create_section_view(
        adapter,
        front,
        line_start=top,
        line_end=bottom,
        view_xy=view_xy,
        section_label="A",
        scale=scale,
        label="trammel block pinch-screw section",
    )
    cut = _early_bound(section.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="pinch section cut face only")
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pinch section did not keep cut-face-only display")

    def screen_axes() -> tuple[float, float]:
        base = mm_in_view(adapter, section, (pinch_x, -5.0, 10.0), label="A-A origin")
        east = mm_in_view(adapter, section, (pinch_x, -5.0, 11.0), label="A-A +z")
        up = mm_in_view(adapter, section, (pinch_x, -4.0, 10.0), label="A-A +y")
        return east[0] - base[0], up[1] - base[1]

    east, up = screen_axes()
    if east * up < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="pinch section looks along +X")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("pinch section cut direction did not persist")
        east, up = screen_axes()
    if not (east > 0.0 and up > 0.0):
        raise RuntimeError(
            f"pinch section does not look along +X with the top face up "
            f"(+Z sheet dx {east}, +Y sheet dy {up})"
        )
    # Reversing the cut mirrors the section about its position (farm r4: its
    # ink landed a section width right of view_xy, over the isometric), so
    # the view is recentred on its outline before the caption is placed.
    _center_on_outline(adapter, section, view_xy, label="pinch section")
    position_section_caption(adapter, section, caption_xy, label="trammel block")
    return section


def _center_on_outline(
    adapter: Any, view: Any, target: tuple[float, float], *, label: str
) -> None:
    """Move ``view`` so its outline (its ink) is centred on ``target``
    (draw_ch_rocker_arm_tl_profile_fixture's recipe)."""
    view = _early_bound(view, "IView")
    for _attempt in range(3):
        outline = tuple(float(value) for value in view.GetOutline())
        center = ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)
        if math.dist(center, target) < 0.0002:
            return
        position = tuple(float(value) for value in view.Position)
        moved = [position[axis] + target[axis] - center[axis] for axis in range(2)]
        if not view.SetViewPosition(double_array(moved), False):
            raise RuntimeError(f"failed to position {label}")
        rebuild_drawing(adapter, label=f"center {label}")
    raise RuntimeError(f"{label} outline did not settle on {target!r}")


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


# draw_pd_transgear_arm's tap_callout_definitions: the title block's
# "THREADS UNC/UNF CLASS 2A/2B" already states the class.
_THREAD_CLASS = re.compile(r"\s*(?:-\s*)?<hw-threadclass>\s*", re.IGNORECASE)


def thread_class_free_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Drop the one native thread-class token; every Hole Wizard variable
    stays."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    thread_parts = [
        part for part, text in definitions.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(
            f"tap thread line is not in one callout part: {definitions!r}"
        )
    part = thread_parts[0]
    without_class = re.sub(r" {2,}", " ", _THREAD_CLASS.sub(" ", definitions[part]))
    updated = dict(definitions)
    updated[part] = without_class.rstrip()
    return updated


def strip_thread_class(display: Any, *, label: str) -> None:
    """Print a tap callout without its title-block thread class, loudly."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = thread_class_free_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = "\n".join(str(native.GetText(part) or "") for part in (1, 2, 3, 4))
    if persisted != updated or re.search(r"\b2B\b", resolved) or "UNC" not in resolved:
        raise RuntimeError(
            f"{label} thread class did not leave the callout: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
