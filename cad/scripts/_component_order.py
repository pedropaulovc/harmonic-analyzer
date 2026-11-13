"""Visit an assembly's components in one order on every seat (issue #2686).

``IAssemblyDoc.GetComponents``, ``IComponent2.GetChildren``,
``IView.GetVisibleComponents``, ``IBomTableAnnotation.GetComponents2`` and
``IDrawingComponent.GetChildren`` hand back the same components in an order
that differs between builds, even on one seat. A loop that follows that order
issues a different COM conversation on each build whenever what it asks of a
component depends on the component (a per-path cache, a filter, a conditional
write, a first match), and a drawing that places annotations in that order
prints differently.

The order used instead is the component's name, compared naturally: digit
runs as numbers, so ``part-2`` precedes ``part-10`` and a pattern's seed
``part-1`` precedes its instances. The name is persisted in the model, unique
among the components of one enumeration (a nested component's ``Name2``
carries its parents' path), and costs one property read. Natural rather than
plain text order keeps instance numbering in authored order, which the
Simplified-configuration pass relies on for its fewest writes: a seed read
before its pattern instances settles their configuration once.

Each element is bound and its name read in the order given, one bind and one
read per element and no other call, before the caller asks anything else, so
only those reads' answers follow the seat and a recording comparison can pair
the two seats' elements by name. Call these directly on the enumeration's
result.

An element that is ``None``, or whose name reads ``None`` or empty, raises
:class:`RuntimeError` here, naming the enumeration's interface and the
element's position: a component without a name can be neither ordered nor
identified, so no caller substitutes a placeholder name or skips it.

Not part of any part recipe: only assembly- and drawing-tier modules import
this.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from _com import _early_bound

_DIGITS = re.compile(r"([0-9]+)")


def natural_key(name: str) -> tuple[tuple[str | int, ...], str]:
    """``name`` split into text and number runs (every odd run a number), then
    the name itself, so ``-01`` and ``-1`` still order one way."""
    runs = _DIGITS.split(name)
    return tuple(int(run) if index % 2 else run for index, run in enumerate(runs)), name


def _named(
    elements: Iterable[Any] | None, interface: str, member: str
) -> list[tuple[str, Any]]:
    raws = tuple(elements or ())
    named = []
    for index, raw in enumerate(raws):
        if raw is None:
            raise RuntimeError(
                f"{interface} enumeration: element {index} of {len(raws)} is None"
            )
        element = _early_bound(raw, interface)
        value = getattr(element, member)
        name = "" if value is None else str(value)
        if not name:
            raise RuntimeError(
                f"{interface} enumeration: element {index} of {len(raws)} "
                f"has no {member} ({value!r})"
            )
        named.append((name, element))
    return sorted(named, key=lambda pair: natural_key(pair[0]))


def by_name(components: Iterable[Any] | None) -> list[tuple[str, Any]]:
    """Each of ``components`` bound as ``IComponent2`` with its ``Name2``, in
    natural name order."""
    return _named(components, "IComponent2", "Name2")


def drawing_components_by_name(
    drawing_components: Iterable[Any] | None,
) -> list[tuple[str, Any]]:
    """Each of ``drawing_components`` bound as ``IDrawingComponent`` with its
    ``Name``, in natural name order."""
    return _named(drawing_components, "IDrawingComponent", "Name")
