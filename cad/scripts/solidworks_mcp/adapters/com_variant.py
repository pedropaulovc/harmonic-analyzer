"""COM VARIANT marshalling helpers for pywin32 late binding.

SolidWorks calls take their arguments as VARIANTs. A few argument types do not
round-trip from plain Python values and need an explicit VARIANT wrapper, or the
call fails at the COM boundary. This module centralises those conversions so
every call site marshals them the same way.

It deliberately provides NO by-reference helper for ``[out]`` params. Under the
generated (makepy) wrapper this adapter uses, every ``[out]`` rides the RETURN
TUPLE -- ``ret, errors, warnings = doc.Save3(opts, 0, 0)`` -- and a byref VARIANT
passed there stays UNWRITTEN, which reads as "no data" rather than failing. The
former ``byref_long`` encoded the opposite, late-bound convention; it had no
callers left and was removed rather than left as a trap to reach for.

All helpers import ``pywin32`` lazily and degrade to a benign value when it is
unavailable (e.g. Linux CI running the mock suite), so importing this module is
safe on every platform.
"""

from __future__ import annotations

from typing import Any


def null_dispatch() -> Any:
    """Return the null value for an optional ``IDispatch`` object-pointer param.

    These calls now go through **early binding** (the makepy ``InvokeTypes``
    path), where a bare Python ``None`` is exactly what a typed ``VT_DISPATCH``
    slot expects: makepy marshals it to a null ``IDispatch`` and SolidWorks
    accepts it (probed live on SW 2026 — ``SelectByID2(…, None, 0)`` returns
    ``True``). The former ``VARIANT(VT_DISPATCH, None)`` was a *late*-binding
    requirement (dynamic ``Invoke`` rejected bare ``None`` as ``VT_NULL`` with
    ``Type mismatch``); under early-bound ``InvokeTypes`` that same VARIANT
    instead fails with ``TypeError: The Python instance can not be converted to
    a COM object``. Used for ``SelectByID2``'s ``Callout`` (see
    :func:`null_callout`) and ``IModelDocExtension::SaveAs2``'s ``ExportData``.

    Returns:
        Any: ``None`` — the null object pointer for a ``VT_DISPATCH`` param under
        makepy early binding (also inert for mock adapters, which never reach a
        real COM boundary).
    """
    return None


def null_variant() -> Any:
    """Return the null value for an optional ``System.object`` (VT_VARIANT) param.

    Unlike :func:`null_dispatch` (for a typed ``(9,x)`` ``VT_DISPATCH``
    object-pointer, where early-bound ``InvokeTypes`` wants a bare ``None``),
    this is for a param the type library declares as ``(12,x)`` **VT_VARIANT** —
    ``IEquationMgr::Add3``'s ``ConfigNames``, ``IFeature::SetSuppression2``'s
    ``Config_names``, ``IMeasure::Calculate``'s ``Entities`` (all "unused /
    use-selection" when null). For a VT_VARIANT slot pywin32 honors an explicit
    ``VARIANT`` wrapper, whereas a bare ``None`` marshals as ``VT_NULL`` and the
    call misbehaves (a silently-unset equation / suppression) — so the
    ``VARIANT(VT_DISPATCH, None)`` form is REQUIRED here under BOTH binding
    modes, the opposite of :func:`null_dispatch`.

    Returns:
        Any: ``VARIANT(VT_DISPATCH, None)`` on Windows with pywin32 available;
        plain ``None`` as a fallback otherwise (CI never reaches a real COM
        boundary).
    """
    try:
        import pythoncom
        from win32com.client import VARIANT

        return VARIANT(pythoncom.VT_DISPATCH, None)
    except Exception:
        return None


def null_callout() -> Any:
    """Return a typed-null ``Callout`` argument for ``SelectByID2``.

    ``IModelDocExtension::SelectByID2`` (and the ``IModelDoc2`` variant) take an
    optional ``Callout`` parameter typed as an ``ICallout`` object pointer.
    The failure mode of passing a bare ``None`` was long misattributed to
    "``SelectByID2`` is broken on this build" — see :func:`null_dispatch`.

    Returns:
        Any: See :func:`null_dispatch`.
    """
    return null_dispatch()


def bstr_array(values: list[str]) -> Any:
    """Return an array-of-strings VARIANT for ``string[]`` SAFEARRAY params.

    SolidWorks methods such as ``IEquationMgr::Add3`` take configuration-name
    lists typed as ``System.object`` holding a string array. Under late
    binding a bare Python list unpacks into N positional VARIANTs
    (``DISP_E_BADPARAMCOUNT``), so the list must be wrapped in a
    ``VT_ARRAY | VT_BSTR`` VARIANT.

    Args:
        values: The strings to marshal.

    Returns:
        Any: ``VARIANT(VT_ARRAY | VT_BSTR, values)`` on Windows with pywin32
        available; the plain list as a fallback otherwise (CI never reaches a
        real COM boundary).
    """
    try:
        import pythoncom
        from win32com.client import VARIANT

        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, values)
    except Exception:
        return values


def double_array(values: list[float]) -> Any:
    """Return an array-of-doubles VARIANT for ``double[]`` SAFEARRAY params.

    SolidWorks methods such as ``IMathUtility::CreateTransform`` take numeric
    arrays typed as ``System.object`` holding a double array. Under late
    binding a bare Python list marshals as ``VT_ARRAY | VT_VARIANT``, which
    ``CreateTransform`` silently ignores — it returns a valid **identity**
    transform instead of failing, so every downstream
    ``IComponent2::SetTransformAndSolve3`` "succeeds" without moving the
    component. The list must be wrapped as ``VT_ARRAY | VT_R8``.

    Args:
        values: The doubles to marshal.

    Returns:
        Any: ``VARIANT(VT_ARRAY | VT_R8, values)`` on Windows with pywin32
        available; the plain list as a fallback otherwise (CI never reaches a
        real COM boundary).
    """
    coerced = [float(v) for v in values]
    try:
        import pythoncom
        from win32com.client import VARIANT

        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, coerced)
    except Exception:
        return coerced


def dispatch_array(values: list[Any]) -> Any:
    """Return an array-of-objects VARIANT for ``object[]`` SAFEARRAY params.

    SolidWorks methods/properties such as
    ``IDistanceMateFeatureData::EntitiesToMate`` take an entity array typed as
    ``System.object`` holding an ``IDispatch`` array. Under late binding a bare
    Python list of dispatch objects does not marshal as a SAFEARRAY; it must be
    wrapped as ``VT_ARRAY | VT_DISPATCH`` (mirrors :func:`double_array` /
    :func:`bstr_array` for their element types).

    Args:
        values: The COM object pointers to marshal.

    Returns:
        Any: ``VARIANT(VT_ARRAY | VT_DISPATCH, values)`` on Windows with pywin32
        available; the plain list as a fallback otherwise (CI never reaches a
        real COM boundary).
    """
    try:
        import pythoncom
        from win32com.client import VARIANT

        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(values))
    except Exception:
        return list(values)


def bool_array(values: list[bool]) -> Any:
    """Return an array-of-booleans VARIANT for ``bool[]`` SAFEARRAY params.

    SolidWorks properties such as ``IBeltChainFeatureData::FlipSides`` take a
    ``System.object`` holding a boolean array. Under late binding a bare Python
    list marshals as ``VT_ARRAY | VT_VARIANT``, which the setter rejects; the
    list must be wrapped as ``VT_ARRAY | VT_BOOL`` (mirrors :func:`double_array`
    / :func:`dispatch_array` for their element types).

    Args:
        values: The booleans to marshal.

    Returns:
        Any: ``VARIANT(VT_ARRAY | VT_BOOL, values)`` on Windows with pywin32
        available; the plain list as a fallback otherwise (CI never reaches a
        real COM boundary).
    """
    coerced = [bool(v) for v in values]
    try:
        import pythoncom
        from win32com.client import VARIANT

        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, coerced)
    except Exception:
        return coerced


def empty_double_array() -> Any:
    """Return an empty array-of-doubles VARIANT for unused SAFEARRAY params.

    Some SolidWorks methods take an optional ``double[]`` (e.g. the ``Radii``
    argument of ``IModelDoc2::FeatureFillet3``, unused when the radius count is
    zero). Under late binding the correct typed-absent value is an empty
    ``VT_ARRAY | VT_R8`` VARIANT, not a bare ``None`` (which would marshal as
    ``VT_NULL`` — the same class of failure as :func:`null_callout`).

    Returns:
        Any: ``VARIANT(VT_ARRAY | VT_R8, [])`` on Windows with pywin32
        available; plain ``None`` as a fallback otherwise (CI never reaches a
        real COM boundary).
    """
    try:
        import pythoncom
        from win32com.client import VARIANT

        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [])
    except Exception:
        return None
