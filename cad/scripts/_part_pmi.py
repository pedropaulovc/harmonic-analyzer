"""Author a part's geometric controls as DimXpert model PMI.

The PART build calls :func:`author_part_pmi` with the ``PartDatum`` /
``GeometricControl`` rows from its ``<part>_spec.py`` right before the final
save, so the shipped ``.SLDPRT`` carries its GD&T natively and the drawing
IMPORTS it (``_drawing_common.import_part_pmi``) instead of typing frozen
per-sheet strings.  Everything here was probed live on the Makers seat
2026-07-28 (``diagnostics/probe_dimxpert_gtol.py`` Q1–Q5,
``diagnostics/probe_dimxpert_authoring.py``); the binding rules live in
``sw_type_info`` (the swdimxpert auxiliary typelib — DimXpert dispatches
expose no type info, so only the raw-``_oleobj_`` makepy wrap works).

Part tier only: imports ``_common`` + ``_gtol_spec`` + the adapter — never a
drawing or assembly module (``check:partiso``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import _telemetry
from _common import _early_bound, _read_member
from _gtol_spec import (
    DIMXPERT_GTOL_MEMBERS,
    CylinderFace,
    FaceSpec,
    GeometricControl,
    PartDatum,
    PlanarFace,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout

# swSurfaceTypes_e identities read via ISurface.Identity.
_SURFACE_PLANE = 4001
_SURFACE_CYLINDER = 4002

# swDimXpertAnnotationType_e.swDimXpertDatum
_ANNOTATION_DATUM = 150

# swDimXpertFeatureSelectorOption_e member names per face kind; the integer
# values are read off swdimxpert.tlb at author time (feature_selector_ids),
# never hard-coded — the offline API bundle does not ship this enum either.
_SELECTOR_MEMBER_BY_FACE = {PlanarFace: "Plane", CylinderFace: "Cylinder"}


def swdimxpert_tlb() -> Path:
    """Locate the installed swdimxpert type library."""
    roots = sorted(
        Path(r"C:\Program Files\Dassault Systemes").glob(
            "SOLIDWORKS*/SOLIDWORKS/swdimxpert.tlb"
        )
    ) + sorted(Path(r"C:\Program Files\SOLIDWORKS Corp").glob("SOLIDWORKS/swdimxpert.tlb"))
    if not roots:
        raise FileNotFoundError("swdimxpert.tlb not found in any SOLIDWORKS install")
    return roots[-1]


def gtol_type_ids() -> dict[str, int]:
    """Read ``swDimXpertGtolType_e`` off the installed type library.

    The offline API bundle ships no such enum file, so the mapping is SOURCED
    from the tlb — a SolidWorks upgrade that renumbers it fails loud here
    instead of silently inserting the wrong characteristic.
    """
    return _tlb_enum_members("swDimXpertGtolType_")


def feature_selector_ids() -> dict[str, int]:
    """Read ``swDimXpertFeatureSelectorOption_e`` off the installed typelib."""
    return _tlb_enum_members("swDimXpertFeatureSelectorOption_")


def _tlb_enum_members(prefix: str) -> dict[str, int]:
    import comtypes.client

    module = comtypes.client.GetModule(str(swdimxpert_tlb()))
    members = {
        name[len(prefix) :]: int(getattr(module, name))
        for name in dir(module)
        if name.startswith(prefix) and not name.endswith("_e")
    }
    if not members:
        raise RuntimeError(f"typelib exposes no {prefix}* members")
    return members


def _long_array(values: Sequence[int]):
    """Wrap ints as a ``VT_ARRAY | VT_I4`` VARIANT (the documented "array of
    long" shape; a bare list marshals as VT_ARRAY|VT_VARIANT)."""
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, [int(v) for v in values])


def _unit(vector: Sequence[float]) -> tuple[float, float, float]:
    x, y, z = (float(c) for c in vector)
    norm = (x * x + y * y + z * z) ** 0.5
    if norm == 0.0:
        raise ValueError("zero-length direction")
    return (x / norm, y / norm, z / norm)


def _resolve_face(model: Any, spec: FaceSpec, *, label: str) -> Any:
    """Return the ONE face matching ``spec``; 0 or >1 matches fail loud."""
    part = _early_bound(model, "IPartDoc")
    matches = []
    for body in part.GetBodies2(0, False) or ():
        face = _read_member(body, "GetFirstFace")
        while face:
            if _face_matches(face, spec):
                matches.append(face)
            face = _read_member(face, "GetNextFace")
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: face spec {spec!r} matched {len(matches)} faces; "
            "the spec must identify exactly one"
        )
    return matches[0]


def _face_matches(face: Any, spec: FaceSpec) -> bool:
    surface = _read_member(face, "GetSurface")
    if surface is None:
        return False
    surface = _early_bound(surface, "ISurface")
    identity = int(_read_member(surface, "Identity"))
    tolerance_m = spec.tolerance_mm / 1000.0
    if isinstance(spec, CylinderFace):
        if identity != _SURFACE_CYLINDER:
            return False
        # CylinderParams: origin xyz, axis xyz, radius — meters.
        params = tuple(_read_member(surface, "CylinderParams"))
        if abs(params[6] - spec.diameter_mm / 2000.0) > tolerance_m:
            return False
        if spec.contains_y_mm is None:
            return True
        box = tuple(_early_bound(face, "IFace2").GetBox() or ())
        if len(box) != 6:
            return False
        y = spec.contains_y_mm / 1000.0
        return box[1] - tolerance_m <= y <= box[4] + tolerance_m
    if isinstance(spec, PlanarFace):
        if identity != _SURFACE_PLANE:
            return False
        # PlaneParams: normal xyz, root point xyz — meters. The surface normal
        # ignores which side the material is on; FaceInSurfaceSense flips it.
        params = tuple(_read_member(surface, "PlaneParams"))
        normal = _unit(params[0:3])
        if bool(_early_bound(face, "IFace2").FaceInSurfaceSense()):
            normal = (-normal[0], -normal[1], -normal[2])
        want = _unit(spec.normal)
        if sum(a * b for a, b in zip(normal, want)) < 0.999:
            return False
        offset = sum(p * n for p, n in zip(params[3:6], normal))
        return abs(offset - spec.offset_mm / 1000.0) <= tolerance_m
    raise TypeError(f"unsupported face spec: {spec!r}")


def _select_face(model: Any, face: Any, *, label: str) -> None:
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select4(False, null_callout()):
        raise RuntimeError(f"{label}: face selection failed")


def author_part_pmi(
    adapter: Any,
    *,
    datums: Sequence[PartDatum] = (),
    controls: Sequence[GeometricControl] = (),
) -> None:
    """Author ``datums`` then ``controls`` as DimXpert PMI on the current part.

    Datums must be listed in alphabetical order: DimXpert ASSIGNS identifiers
    in insertion order, and the read-back identifier is asserted against the
    spec letter so a silent renumber cannot ship a frame referencing the
    wrong datum.
    """
    if not datums and not controls:
        return
    model = adapter.currentModel
    ext = _read_member(model, "Extension")
    config = _read_member(_read_member(model, "GetActiveConfiguration"), "Name")
    with _telemetry.span(
        "part.pmi", datums=len(datums), controls=len(controls)
    ):
        manager = ext.DimXpertManager(str(config), True)
        if manager is None:
            raise RuntimeError("DimXpertManager returned None")
        dim_part = _early_bound(_read_member(manager, "DimXpertPart"), "IDimXpertPart")

        selector_ids = feature_selector_ids() if datums else {}
        for datum in datums:
            face = _resolve_face(model, datum.face, label=f"datum {datum.letter}")
            _select_face(model, face, label=f"datum {datum.letter}")
            option = _early_bound(
                dim_part.GetDimOption(), "IDimXpertDimensionOption"
            )
            option.DatumLength = datum.leader_length_m
            option.FeatureSelectorOptions = _long_array(
                [selector_ids[_SELECTOR_MEMBER_BY_FACE[type(datum.face)]]]
            )
            if not dim_part.InsertDatum(option):
                raise RuntimeError(f"InsertDatum failed for datum {datum.letter}")
            identifier = _last_datum_identifier(dim_part)
            if identifier != datum.letter:
                raise RuntimeError(
                    f"DimXpert assigned datum identifier {identifier!r}, spec "
                    f"expects {datum.letter!r} — author datums in alphabetical "
                    "order (identifiers are assigned by insertion order)"
                )
            _telemetry.event("pmi.datum", letter=datum.letter)

        type_ids = gtol_type_ids() if controls else {}
        for control in controls:
            face = _resolve_face(model, control.face, label=control.key)
            _select_face(model, face, label=control.key)
            member = DIMXPERT_GTOL_MEMBERS[control.characteristic]
            annotation = dim_part.InsertGtol(type_ids[member])
            if annotation is None:
                raise RuntimeError(f"InsertGtol failed for {control.key}")
            display = _early_bound(
                _read_member(annotation, "GetDisplayEntity"), "IAnnotation"
            )
            gtol = display.GetSpecificAnnotation()
            if gtol is None:
                raise RuntimeError(
                    f"{control.key}: DimXpert gtol has no specific annotation "
                    "(PMI-only display entity)"
                )
            gtol = _early_bound(gtol, "IGtol")
            frame = gtol.GetFrame(1)
            if frame is None:
                raise RuntimeError(f"{control.key}: DimXpert gtol has no frame")
            frame = _early_bound(frame, "IGtolFrame")
            if not frame.SetSymbolXml(control.frame_xml):
                raise RuntimeError(f"{control.key}: SetSymbolXml rejected")
            applied = str(frame.GetSymbolXml() or "")
            if control.tolerance not in applied:
                raise RuntimeError(
                    f"{control.key}: frame did not persist the tolerance "
                    f"(read back {applied[:120]!r})"
                )
            _telemetry.event(
                "pmi.gtol",
                key=control.key,
                characteristic=control.characteristic,
                tolerance=control.tolerance,
            )
        model.ClearSelection2(True)
        _telemetry.success(
            f"part PMI authored: {len(datums)} datums, {len(controls)} controls"
        )


def _last_datum_identifier(dim_part: Any) -> str:
    """Identifier of the most recently inserted DimXpert datum annotation."""
    latest = None
    for annotation in dim_part.GetAnnotations() or ():
        if int(_read_member(annotation, "Type")) == _ANNOTATION_DATUM:
            latest = annotation
    if latest is None:
        raise RuntimeError("no DimXpert datum annotation found after InsertDatum")
    return str(_read_member(latest, "Identifier") or "")
