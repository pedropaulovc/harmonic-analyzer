"""Exact document-scoped identity for drawing-context SILHOUETTE entities only.

Transient ISldWorks.IsSame handles can differ for one silhouette. The native
drawing-extension IsSamePersistentID result is the identity predicate; byte
equality is never a substitute. Callers retain their exact view/face checks.
"""

from _common import _early_bound


def byte_reference(raw):
    if isinstance(raw, memoryview):
        try:
            if (
                raw.ndim != 1
                or raw.format != "B"
                or raw.itemsize != 1
                or not raw.contiguous
                or raw.nbytes == 0
            ):
                raise RuntimeError(
                    "native persistent reference is not a nonempty contiguous unsigned-byte view"
                )
            return tuple(raw)
        except ValueError as error:
            raise RuntimeError(
                "native persistent reference memoryview is released"
            ) from error
    if not isinstance(raw, (tuple, list, bytes)) or not raw:
        raise RuntimeError("native persistent reference is empty or has the wrong type")
    if any(type(value) is not int or not 0 <= value <= 255 for value in raw):
        raise RuntimeError("native persistent reference is not an unsigned-byte array")
    return tuple(raw)


def byte_variant(reference):
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, reference)


def require_same(drawing, expected, actual, *, label, evidence=None):
    """Compare two current drawing-context silhouette references, never source IDs."""
    if expected is None or actual is None:
        raise RuntimeError(f"{label}: null silhouette entity")
    model = _early_bound(drawing, "IModelDoc2")
    kind = model.GetType()
    if type(kind) is not int or kind != 3:
        raise RuntimeError(
            f"{label}: silhouette persistent identity requires a drawing"
        )
    extension = _early_bound(model.Extension, "IModelDocExtension")
    records = evidence if evidence is not None else {}
    references = []
    for name, entity in (("expected", expected), ("actual", actual)):
        row = records[name] = {}
        try:
            raw = extension.GetPersistReference3(entity)
            row["return_type"] = f"{type(raw).__module__}.{type(raw).__qualname__}"
            reference = byte_reference(raw)
        except Exception as error:
            row["error"] = repr(error)
            raise
        row["reference"] = reference
        references.append(reference)
    try:
        result = extension.IsSamePersistentID(
            *(byte_variant(value) for value in references)
        )
    except Exception as error:
        records["native_error"] = repr(error)
        raise
    records["native_result"] = result
    if type(result) is not int or result != 1:
        raise RuntimeError(f"{label}: native IsSamePersistentID returned {result!r}")
