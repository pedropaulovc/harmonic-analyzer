"""Resolve the shared vendors' semantic occurrence references to live native names.

A selector such as ``@TNut:1`` is a role-local ordinal, not a SOLIDWORKS
component index. Nested selectors retain their native parent scope, for example
``dt-drive-train-1/@FootScrew:1``. Resolved names are valid only for the open
assembly; callers must not persist them as a cross-build identity map.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import PureWindowsPath
from typing import Any

import _telemetry
from _com import _early_bound
from _simplified_names import SIMPLIFIED_SUFFIX

# Only the configured members and the two same-stock drive-train roles need
# semantic references. Other ordinary components keep their native selectors.
REFERENCE_IDENTITIES: dict[str, tuple[str, str]] = {
    "InnerLink": ("sh-vn-chain-link", "InnerLink"),
    "OuterLink": ("sh-vn-chain-link", "OuterLink"),
    "LeverWire": ("sh-vn-music-wire", "LeverWire"),
    "PenWire": ("sh-vn-music-wire", "PenWire"),
    "HoldDownStud": ("sh-vn-clamping-kit-hardware", "HoldDownStud"),
    "TNut": ("sh-vn-clamping-kit-hardware", "TNut"),
    "FlangeNut": ("sh-vn-clamping-kit-hardware", "FlangeNut"),
    "FootScrew": ("sh-vn-fillister-screw-90280a108", "Default"),
    "SwingStopScrew": ("sh-vn-fillister-screw-90280a108", "Default"),
}
_REFERENCE = re.compile(r"(?P<role>[A-Za-z][A-Za-z0-9]*):[1-9][0-9]*\Z")


def member_configuration(configuration: str) -> str:
    """The selected member, with only its derived drawing suffix removed."""
    return configuration.removesuffix(SIMPLIFIED_SUFFIX)


def component_identity(component: Any) -> tuple[str, str]:
    """Read a physical native file and its selected, unsimplified member."""
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError("component has no native file path")
    return (
        PureWindowsPath(path).stem.casefold(),
        member_configuration(str(component.ReferencedConfiguration or "")),
    )


def semantic_reference_identity(selector: str) -> tuple[str, str] | None:
    """An explicit ``@Role:N`` selector's required file/member, or None."""
    leaf = selector.replace("\\", "/").rsplit("/", 1)[-1]
    if not leaf.startswith("@"):
        return None
    match = _REFERENCE.fullmatch(leaf[1:])
    if match is None or match["role"] not in REFERENCE_IDENTITIES:
        raise ValueError(f"invalid shared-component reference selector {selector!r}")
    return REFERENCE_IDENTITIES[match["role"]]


@_telemetry.traced("assembly.component_reference_names")
def component_reference_names(
    model: Any, expected: Mapping[str, tuple[str, str]]
) -> dict[str, str]:
    """Resolve every requested reference, proving its parent, file and member.

    References are read from native components, never inferred from Name2's
    allocator-controlled suffix. Duplicate references in the same parent scope,
    missing references and references attached to another member fail closed.
    """
    if not expected:
        return {}
    normalized: dict[str, tuple[str, str]] = {}
    for selector, (stem, configuration) in expected.items():
        canonical = selector.replace("\\", "/")
        required = semantic_reference_identity(canonical)
        if required is None:
            raise ValueError(f"not an explicit component-reference selector: {selector!r}")
        if canonical in normalized:
            raise ValueError(f"duplicate component-reference selector {canonical!r}")
        identity = (stem.casefold(), member_configuration(configuration))
        if identity != required:
            raise ValueError(
                f"component reference {canonical!r} requires {required!r}, "
                f"not declared identity {identity!r}"
            )
        normalized[canonical] = identity
    found: dict[str, str] = {}
    assembly = _early_bound(model, "IAssemblyDoc")
    for raw in assembly.GetComponents(False) or ():
        component = _early_bound(raw, "IComponent2")
        reference = str(component.ComponentReference or "")
        if not reference:
            continue
        name = str(component.Name2 or "").replace("\\", "/")
        parent, separator, _leaf = name.rpartition("/")
        selector = f"{parent}/@{reference}" if separator else f"@{reference}"
        if selector not in normalized:
            continue
        if selector in found:
            raise RuntimeError(
                f"component reference {selector!r} is duplicated by "
                f"{found[selector]!r} and {name!r}"
            )
        actual = component_identity(component)
        if actual != normalized[selector]:
            raise RuntimeError(
                f"component reference {selector!r} on {name!r} selects "
                f"{actual!r}, expected {normalized[selector]!r}"
            )
        if not name:
            raise RuntimeError(f"component reference {selector!r} has no native name")
        found[selector] = name
    missing = sorted(set(normalized) - found.keys())
    if missing:
        raise RuntimeError(f"missing native component references: {missing!r}")
    _telemetry.event("assembly.component_reference_binding", bindings=tuple(found.items()))
    return {selector: found[selector.replace("\\", "/")] for selector in expected}


def bind_component_selectors(model: Any, selectors: Iterable[str]) -> dict[str, str]:
    """Bind explicit semantic selectors; leave ordinary native names untouched."""
    selectors = tuple(dict.fromkeys(selectors))
    expected = {
        selector: identity
        for selector in selectors
        if (identity := semantic_reference_identity(selector)) is not None
    }
    names = component_reference_names(model, expected)
    return {selector: names.get(selector, selector) for selector in selectors}
