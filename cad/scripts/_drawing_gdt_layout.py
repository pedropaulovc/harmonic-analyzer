"""Native drawing GD&T display geometry and layout elements.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
from _drawing_layout_check import CollisionScope
from _drawing_layout_check import LayoutElement
import _telemetry
from _drawing_layout_audit import annotation_display
from _layout_audit import display_box
from _layout_audit import estimated_text_runs


# swAnnotationType_e for the native GD&T symbols the recipes place at explicit
# sheet coordinates (datum tags, feature-control frames, surface-finish symbols).
# None of these interfaces expose a real bounding box (IDisplayData returns only
# leader-polluted primitives in a non-sheet coordinate space), so each is boxed
# as a nominal square around its GetPosition anchor. That nominal box is reliable
# enough to catch a symbol placed clear OFF the sheet (overflow) but too coarse
# to assert an OVERLAP without false positives -- a datum tag placed beside its
# own feature-control frame, standard GD&T practice, would self-collide -- so the
# symbols get ``NONE`` collision scope (overflow-checked, overlap-exempt).
# (Codex #269 thread 5 overflow; overlap declined with this rationale.)
_ANNOT_DATUM = 2


_ANNOT_GTOL = 5


_ANNOT_SFSYM = 7


_SEL_DIMENSION = 14  # swSelectType_e.swSelDIMENSIONS


_GDT_TYPES = frozenset({_ANNOT_DATUM, _ANNOT_GTOL, _ANNOT_SFSYM})


# Fallback only, for an annotation whose geometry cannot be read. Every GD&T
# symbol that CAN be measured is (see _measured_gdt_box) -- a fixed square is
# wrong for an FCF by construction, since its width tracks its compartments.
_NOMINAL_GDT_HALF_M = 0.008


# A SURFACE-FINISH symbol is NOT centred on its anchor, so the symmetric box
# above is the wrong shape for it and silently under-reports.
# ``GetPosition`` returns the LEADER'S ATTACHMENT POINT -- the bottom vertex of
# the check-mark triangle -- and the whole body draws UP and to the RIGHT of it:
# triangle x [ax-0.006, ax+0.006] y [ay, ay+0.011]; the "Ra 1.6" text
# x [ax+0.013, ax+0.039] y [ay+0.010, ay+0.017]; the arm at y ~= ay+0.018.
# Boxed +/-8 mm about a point that is the symbol's own BOTTOM EDGE, the gate
# missed ~10 mm of body above and ~31 mm of text to the right: wheel_axle's Ra
# printed over the zone label while the audit stayed silent (its real top is
# ay+0.018 = 0.273, 5.6 mm past the rule, but the box topped out at 0.263).
# Measured independently on 3+ sheets by three agents; every sample draws
# up-right regardless of which side the target sits on (a leader running
# up-LEFT out of the vertex does not mirror the body), so the offsets are
# orientation-stable for ``add_surface_finish``'s SetLeader3(BENT, SMART) call.
# LEFT keeps the old 8 mm rather than the measured 7: strictly no less
# conservative than what it replaces, on every side.
_SF_BOX_LEFT_M = 0.008


_SF_BOX_RIGHT_M = 0.039


_SF_BOX_UP_M = 0.018


_SF_BOX_DOWN_M = 0.0


def _datum_is_dimension_attached(adapter: Any, annotation: Any) -> bool:
    """Whether a datum tag is attached to a display dimension.

    SolidWorks reports ``IDatumTag`` primitive coordinates for this attachment
    type in the dimension's local frame.  They must not be mixed with the
    sheet-space annotation position used by the layout audit.
    """
    attachment_types = (
        adapter._attempt(
            lambda: adapter._get_attr_or_call(annotation, "GetAttachedEntityTypes")
        )
        or ()
    )
    return _SEL_DIMENSION in (int(value) for value in attachment_types)


def _gdt_display(
    adapter: Any, annotation: Any, kind: int, *, name: str
) -> dict[str, Any] | None:
    """A datum tag's or feature-control frame's rendered ink, in sheet space.

    ``IAnnotation::GetDisplayData``, read by the shared layout audit's reader
    (``annotation_display``): lines, arcs, triangles and text runs where
    SolidWorks draws them. NOT the ``IGtol`` / ``IDatumTag`` primitives
    (``GetLineAtIndex`` and kin) this used to read -- on MHA-DT-019 at 4:1
    (pc-gdt-ink-diag, a89a13a7a) a leadered FCF's primitives are a crossed
    2h x 2h placeholder square at the leader's far end plus the leader's last
    run, never the frame, and a datum tag's box lies about (-9.9, -5.0) mm off
    its ink. The display data is where the PDF prints: knife-mount's datum A
    and its leadered three-compartment FCF match their PDF glyphs within
    0.15 mm (layoutcal d09c2b9eb).

    ``None``, with a ``gdt_box.fallback`` event naming the symbol and the
    reason, when there is nothing to read; the caller then falls back.
    A DATUM attached to a display dimension is one such case: its IDatumTag
    primitives were in the dimension's local frame, and whether its display
    data is sheet space is unmeasured, so it keeps the nominal box. A frame
    attached to a dimension reads its display data like any other: a nominal
    square is wrong for an FCF by construction.
    """
    if kind == _ANNOT_DATUM and _datum_is_dimension_attached(adapter, annotation):
        reason = "dimension-attached datum"
    else:
        display, refused = annotation_display(adapter, annotation)
        if display:
            return display
        reason = (
            f"no display data (refused {refused})" if refused else "no display data"
        )
    _telemetry.event("gdt_box.fallback", symbol=name, reason=reason)
    _telemetry.debug(f"{name}: GD&T box falls back to the nominal square: {reason}")
    return None


def _measured_gdt_box(
    adapter: Any, annotation: Any, kind: int, *, name: str
) -> tuple[float, float, float, float] | None:
    """Box a datum tag or feature-control frame from the ink it renders.

    ``_gdt_display``'s display data, every primitive and text run
    (``display_box``). Leader included: that is ink too, and it can cross a
    border on its own. Text below a frame ("BOTH CROWNS") is inside no frame
    line, so its run is boxed at the width SolidWorks reports; a run with
    none is estimated from its glyph count, with a ``gdt_box.text_estimated``
    event.
    """
    display = _gdt_display(adapter, annotation, kind, name=name)
    box = display_box(display) if display else None
    if display and box is None:
        _telemetry.event(
            "gdt_box.fallback", symbol=name, reason="display data draws nothing"
        )
    estimated = estimated_text_runs(display) if display else 0
    if estimated:
        _telemetry.event("gdt_box.text_estimated", symbol=name, runs=estimated)
    return None if box is None else (box.xmin, box.ymin, box.xmax, box.ymax)


def _gdt_element(
    adapter: Any, annotation: Any, name: str, kind: int
) -> LayoutElement | None:
    """Box a native GD&T symbol from its rendered geometry where possible.

    Given ``NONE`` collision scope -- a datum tag legitimately sits beside its
    own control frame, so these are overflow-checked only, never overlap-checked.

    Datum tags and feature-control frames are MEASURED (``_measured_gdt_box``).
    They have to be: an FCF's anchor is its frame's TOP-LEFT corner and its width
    grows with compartment count (measured: 41.6 mm for "Ø0.20|A|B|C" vs 32.2 mm
    for "0.10|A|B", both 7.0 mm tall), so the old symmetric ±8 mm square wasted
    8 mm above on empty sheet while missing ~34 mm of frame body to the right --
    a border crossing in an FCF's right half read clean. No fixed box can be
    right when the width depends on the text.

    A surface-finish symbol keeps its measured ``_SF_BOX_*`` constants, because
    measuring it would be WORSE: its "Ra 1.6" text overhangs the bar drawn above
    it by ~1.3 mm, and text is not among the primitives, so a geometry-derived
    box quietly clips it. The constants were measured off renders (which do show
    the text) and cover it. Same reason the box is asymmetric at all: the anchor
    is the leader's attachment at the body's bottom-left, so a symmetric box is
    the wrong SHAPE, not merely the wrong size, and once let an Ra print over the
    sheet border with the audit reporting clean.
    """
    position = adapter._attempt(
        lambda: adapter._get_attr_or_call(annotation, "GetPosition")
    )
    if not position:
        return None
    x, y = float(position[0]), float(position[1])
    if kind == _ANNOT_SFSYM:
        return LayoutElement(
            name,
            "gdt",
            x - _SF_BOX_LEFT_M,
            y - _SF_BOX_DOWN_M,
            x + _SF_BOX_RIGHT_M,
            y + _SF_BOX_UP_M,
            scope=CollisionScope.NONE,
        )
    measured = _measured_gdt_box(adapter, annotation, kind, name=name)
    if measured is not None:
        x0, y0, x1, y1 = measured
        return LayoutElement(name, "gdt", x0, y0, x1, y1, scope=CollisionScope.NONE)
    # No geometry came back (an unexpected kind, or a PMI-only annotation whose
    # GetSpecificAnnotation is None). Fall back to the nominal square rather than
    # dropping the symbol from the audit entirely -- a coarse box still catches
    # one placed clear off the sheet.
    half = _NOMINAL_GDT_HALF_M
    return LayoutElement(
        name, "gdt", x - half, y - half, x + half, y + half, scope=CollisionScope.NONE
    )
