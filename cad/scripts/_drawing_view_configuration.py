"""Drawing-view configurations, exploded state and full-detail assertions.

Assembly and simplified-view drawings select configurations and exploded states
here without re-keying ordinary part sheets.
"""

from __future__ import annotations

import enum
from typing import Any

from _com import _early_bound
from _drawing_common import (
    _SW_SHADED,
    _SW_SHADED_EDGES,
    is_pictorial_orientation,
    rebuild_drawing,
)
from _simplified_names import simplified_name
import _telemetry


# Assembly drawing view configurations (the user's ruling, 2026-09-27, widened
# 2026-09-28): at a small scale the modeled gear teeth and screw threads print
# as a black mass wherever edges are inked, so EVERY view at 1:2 or smaller
# whose display draws edges (wireframe, HLV, HLR, their faceted forms, and
# shaded-with-edges) references the source assembly's derived "Default
# Simplified" (_assembly.sync_simplified_configuration), whatever it carries:
# an exploded view shows that configuration's own explode (the builders author
# it there too), and a BOM or balloons bind to its components, whose BOM
# identity is their parent's (_simplified_bom.child_bom_identity). Only a
# larger view, a pure SHADED one (tone, no edge ink) and the drawing's
# designated full-detail view keep the full-detail Default. Part drawings
# never call this.
ASSEMBLY_VIEW_CONFIGURATION = "Default"


SIMPLIFIED_VIEW_CONFIGURATION = simplified_name(ASSEMBLY_VIEW_CONFIGURATION)


SIMPLIFIED_MAX_SCALE = 0.5


_SW_DISPLAY_MODE_UNKNOWN = -1  # swDisplayMode_e.swDisplayModeUNKNOWN


class ViewRole(enum.Enum):
    """Whether an assembly view follows the scale policy or keeps full detail."""

    PLAIN = "plain"
    # The view that exists to show every modeled tooth and thread.
    FULL_DETAIL = "full-detail"


def view_configuration(
    scale: tuple[float, float], display_mode: int, role: ViewRole = ViewRole.PLAIN
) -> str:
    """The assembly configuration a drawing view references under the policy."""
    numerator, denominator = (float(value) for value in scale)
    if numerator <= 0.0 or denominator <= 0.0:
        raise ValueError(f"view scale must be positive, got {scale!r}")
    if display_mode == _SW_DISPLAY_MODE_UNKNOWN:
        raise ValueError(
            "view display mode reads unknown; its edge ink cannot be judged"
        )
    if (
        role is ViewRole.PLAIN
        and display_mode != _SW_SHADED
        and numerator / denominator <= SIMPLIFIED_MAX_SCALE + 1e-12
    ):
        return SIMPLIFIED_VIEW_CONFIGURATION
    return ASSEMBLY_VIEW_CONFIGURATION


@_telemetry.traced("drawing.view_configuration", label_param="label")
def apply_view_configuration(
    adapter: Any, view: Any, *, role: ViewRole = ViewRole.PLAIN, label: str
) -> str:
    """Point an assembly view at its policy configuration and read it back.

    Call once the view's scale and display mode are final and BEFORE anything
    attaches to its edges or components (dimensions, balloons, leaders, a
    BOM) or sets its exploded state (``set_view_exploded_state``): switching
    the configuration regenerates the view's geometry, and the explode shown
    is the referenced configuration's own. A pictorial view is judged
    shaded-with-edges, because ``finalize_drawing`` shades every one of them
    that way. A section or projected child follows its parent's configuration.
    """
    bound = _early_bound(view, "IView")
    scale = tuple(float(value) for value in bound.ScaleRatio)
    orientation = str(bound.GetOrientationName() or "")
    mode = (
        _SW_SHADED_EDGES
        if is_pictorial_orientation(orientation)
        else int(bound.GetDisplayMode2())
    )
    wanted = view_configuration(scale, mode, role)
    current = str(bound.ReferencedConfiguration)
    if current != wanted:
        bound.ReferencedConfiguration = wanted
        rebuild_drawing(adapter, label=f"{label} configuration")
        current = str(bound.ReferencedConfiguration)
        if current != wanted:
            raise RuntimeError(
                f"{label}: view references {current!r} after setting {wanted!r}"
            )
    _telemetry.annotate(
        configuration=wanted,
        scale=f"{scale[0]:g}:{scale[1]:g}",
        mode=mode,
        role=role.value,
    )
    return wanted


@_telemetry.traced("drawing.exploded_state", label_param="label")
def set_view_exploded_state(
    adapter: Any, view: Any, show: bool, *, configuration: str, label: str
) -> None:
    """Explode or collapse an assembly view in its policy configuration.

    ``IView.ShowExploded`` shows the explode of the configuration the view
    references, so this runs AFTER ``apply_view_configuration`` and refuses a
    view that does not reference ``configuration`` (its return). An exploded
    view that already reads exploded (its configuration was just switched) is
    collapsed first, so the explode shown is regenerated from the referenced
    configuration's own steps. Both states are read back.
    """
    bound = _early_bound(view, "IView")
    current = str(bound.ReferencedConfiguration)
    if current != configuration:
        raise RuntimeError(
            f"{label}: set the exploded state after apply_view_configuration; the view "
            f"references {current!r}, not {configuration!r}"
        )
    if show and bool(bound.IsExploded()):
        bound.ShowExploded(False)
        if bool(bound.IsExploded()):
            raise RuntimeError(
                f"{label}: exploded view did not collapse before re-exploding"
            )
    returned = bool(bound.ShowExploded(show))
    actual = bool(bound.IsExploded())
    if actual != show:
        raise RuntimeError(
            f"{label}: exploded-state readback is {actual}, expected {show}"
        )
    if show and not returned:
        raise RuntimeError(f"{label}: ShowExploded returned false")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: exploded-state rebuild failed")
    after = str(bound.ReferencedConfiguration)
    if after != configuration:
        raise RuntimeError(
            f"{label}: view references {after!r} after its exploded state was set, "
            f"not {configuration!r}"
        )
    _telemetry.annotate(configuration=configuration, exploded=actual)


def assert_full_detail_view(adapter: Any, *, label: str) -> None:
    """Every assembly drawing keeps at least one full-detail (Default) view."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    configurations = [
        str(_early_bound(raw_view, "IView").ReferencedConfiguration)
        for sheet_name in ddoc.GetSheetNames() or ()
        for raw_view in (
            _early_bound(ddoc.Sheet(str(sheet_name)), "ISheet").GetViews() or ()
        )
    ]
    if ASSEMBLY_VIEW_CONFIGURATION not in configurations:
        raise RuntimeError(
            f"{label}: no view shows the full-detail {ASSEMBLY_VIEW_CONFIGURATION!r} "
            f"configuration ({configurations!r})"
        )
    _telemetry.annotate(
        views=len(configurations),
        simplified=configurations.count(SIMPLIFIED_VIEW_CONFIGURATION),
    )
