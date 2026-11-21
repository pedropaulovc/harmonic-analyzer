"""Dimension enumeration, naming and equations.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

import math
import re
from typing import Any

import _telemetry
from _com import _bind, _com_invoke, _read_member
from _feature_tree import _feature_by_name


def _display_dimensions(feat: Any, owner: str | None = None):
    """Yield the RAW IDimension (:func:`_com_invoke`) of each display dimension
    of ``feat``, in creation order; :func:`_bind` one before writing to it.

    ``owner`` filters to dims whose ``FullName`` names that feature as the
    owning one (the middle ``@`` segment). A sketch created on a REFERENCE
    PLANE also enumerates the plane's own offset dim FIRST
    (``D1@<plane>@...``), which would shift positional renaming and trip the
    recorded-count guard -- proven live on cone-pivot-screw's HeadTop driver
    slot. Pass the feature's (post-rename) name to see only its own dims.

    No in-place method flagging: flagging one ``IFeature`` instance flips
    ``GetTypeName2`` to method dispatch on EVERY ``IFeature`` wrapper,
    including the fresh ones the adapter's ``create_cut_extrude`` walk reads
    as bare properties (the "Parameter not optional" cut failure). Raw calls
    by the generated wrapper's dispid touch no shared wrapper at all."""
    for disp in _feature_display_dimensions(feat):
        idim = _com_invoke(disp, "IDisplayDimension", "GetDimension2", 0)
        if owner is None or _dim_owner_feature(idim) == owner:
            yield idim


def _feature_display_dimensions(feat: Any):
    """Yield each display dimension of ``feat`` as a RAW dispatch
    (:func:`_com_invoke`), one round trip per step."""
    disp = _com_invoke(feat, "IFeature", "GetFirstDisplayDimension")
    for _ in range(1000):
        if disp is None:
            return
        yield disp
        disp = _com_invoke(feat, "IFeature", "GetNextDisplayDimension", disp)


def _dim_owner_feature(idim: Any) -> str:
    """The owning feature's name from a dim's ``FullName`` (``D1@Sketch1@Part``)."""
    parts = str(_com_invoke(idim, "IDimension", "FullName")).split("@")
    return parts[1] if len(parts) > 1 else ""


def _dim_value_mm(idim: Any) -> float:
    try:
        return float(_com_invoke(idim, "IDimension", "SystemValue")) * 1000.0
    except Exception:
        return float("nan")


def dump_dimensions(adapter: Any, feature_name: str) -> list[dict[str, Any]]:
    """Print and return every dimension of ``feature_name`` (full name + value).

    The introspection primitive behind 'edit in the GUI, harvest back into the
    script': run it on any feature to see exactly which named dimensions drive
    it and what they currently read."""
    feat = _feature_by_name(adapter, feature_name)
    rows: list[dict[str, Any]] = []
    for i, idim in enumerate(_display_dimensions(feat)):
        full = str(_com_invoke(idim, "IDimension", "FullName"))
        val = _dim_value_mm(idim)
        rows.append({"index": i, "full_name": full, "value_mm": val})
        _telemetry.debug(f"dim[{i}] {full} = {val:.4g} mm")
    return rows


def name_dimensions(
    adapter: Any, feature_name: str, names: list[str | None]
) -> list[str]:
    """Rename a feature's display dimensions, in creation order, to ``names``.

    ``names[i]`` renames the i-th dimension (``None`` leaves one untouched).
    Prints each ``old (value mm) -> new`` so a run reveals at a glance whether
    the creation order still matches what the ``define_*`` helpers emit -- if a
    sketch's dimensioning ever changes, cross-check against
    :func:`dump_dimensions`. Returns the new ``leaf@feature`` names."""
    feat = _feature_by_name(adapter, feature_name)
    dims = list(_display_dimensions(feat, feature_name))
    return _rename_dimensions(dims, feature_name, names)


def _rename_dimensions(
    dims: list[Any], feature_name: str, names: list[str | None]
) -> list[str]:
    """Rename ``feature_name``'s already-listed dims (``_display_dimensions``)."""
    if len(names) > len(dims):
        raise RuntimeError(
            f"name_dimensions {feature_name}: {len(names)} names for "
            f"{len(dims)} dimensions"
        )
    out: list[str] = []
    for idim, new in zip(dims, names, strict=False):
        old = str(_com_invoke(idim, "IDimension", "FullName"))
        val = _dim_value_mm(idim)
        if new is None:
            _telemetry.info(f"dim {old} = {val:.4g} mm (kept)")
            continue
        _bind(idim, "IDimension").Name = new
        out.append(f"{new}@{feature_name}")
        _telemetry.success(f"dim {old} = {val:.4g} mm -> {new}@{feature_name}")
    return out


# A literal with a unit, as builders write them (``f"{value}mm"``).
_UNIT_LITERAL = re.compile(
    r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(mm|in|deg)\s*"
)
# How far SolidWorks' evaluation may sit from a literal, in the document unit
# it answers in: eight decimal places round by at most 5e-9 (issue #889).
_LITERAL_READBACK_TOL = 1e-8
# swUserPreferenceIntegerValue_e.swUnitsLinear / swUnitsAngular, and the
# millimetres (swLengthUnit_e) or degrees (swAngleUnit_e) in one document unit.
_UNITS_LINEAR = 47
_UNITS_ANGULAR = 51
_MM_PER_LENGTH_UNIT = {0: 1.0, 1: 10.0, 2: 1000.0, 3: 25.4}  # mm, cm, m, in
_DEG_PER_ANGLE_UNIT = {0: 1.0, 3: 180.0 / math.pi}  # degrees, radians


def _literal_in_document_units(
    adapter: Any, number: float, unit: str
) -> tuple[float, str]:
    """``number unit`` in the active document's unit for that quantity, which
    is the unit ``IEquationMgr::Value`` answers in, and that unit's name."""
    extension = _read_member(adapter.currentModel, "Extension")
    if unit == "deg":
        kind, preference, table = "angle", _UNITS_ANGULAR, _DEG_PER_ANGLE_UNIT
    else:
        kind, preference, table = "length", _UNITS_LINEAR, _MM_PER_LENGTH_UNIT
        number *= 25.4 if unit == "in" else 1.0
    code = int(extension.GetUserPreferenceInteger(preference, 0))
    if code not in table:
        raise RuntimeError(f"document {kind} unit {code} has no readback scale")
    return number / table[code], f"{kind} unit {code}"


@_telemetry.traced("param.global", label_param="name")
def set_global(adapter: Any, name: str, expr: str | float) -> float:
    """Add or update an equation-manager global variable; returns its value.

    Centralises the pen-driver pattern. ``expr`` is the equation-manager
    expression (a literal like ``197`` or a formula like ``"ColumnX" +
    "RailWidth" / 2``); the dialect takes degrees for trig and ``sqr`` is the
    square root (see SetGlobalVariableParameters).

    A literal with a unit (``12.5182deg``, ``14.6mm``, ``0.25in``) is read
    back against its intended value: the equation manager rounds a global to
    the document's decimal places for its unit and answers the rounded value
    as if exact (``ConeIncline = 12.5182deg`` evaluated 12.52 at two angular
    places, issue #889). More than ``_LITERAL_READBACK_TOL`` off, in the
    document unit the value comes back in, raises. Formulas are not gated."""
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    res = adapter.set_global_variable(
        SetGlobalVariableParameters(name=name, expression=str(expr))
    )
    if not res.is_success:
        raise RuntimeError(f"set_global {name}={expr!r}: {res.error}")
    value = res.data.get("value") if res.data else None
    _telemetry.success(f"global {name} = {expr}  -> {value}")
    evaluated = float(value) if value is not None else float("nan")
    literal = _UNIT_LITERAL.fullmatch(str(expr))
    if literal is not None:
        intended, unit = _literal_in_document_units(
            adapter, float(literal.group(1)), literal.group(2)
        )
        if not abs(evaluated - intended) <= _LITERAL_READBACK_TOL:
            raise RuntimeError(
                f"set_global {name}={expr!r}: evaluated {evaluated!r}, intended "
                f"{intended!r} in document {unit} (rounded to the document's "
                "decimal places?)"
            )
    return evaluated


@_telemetry.traced("param.dimension", label_param="dim_name")
def drive_dimension(adapter: Any, dim_name: str, expr: str | float) -> None:
    """Bind a (named) dimension to an equation expression, e.g.::

        drive_dimension(adapter, "OuterWidth@OuterProfile", '2 * "OuterX"')

    so editing the ``OuterX`` global reshapes the part. ``dim_name`` is the
    ``leaf@feature`` form returned by :func:`name_dimensions`."""
    from solidworks_mcp.adapters.base import CreateEquationParameters

    equation = f'"{dim_name}" = {expr}'
    res = adapter.create_equation(CreateEquationParameters(equation=equation))
    if not res.is_success:
        raise RuntimeError(f"drive_dimension {equation!r}: {res.error}")
    _telemetry.success(f"equation {equation}")
