"""Author a part's geometric controls as plain model annotations.

The PART build calls :func:`author_part_pmi` with the ``PartDatum`` /
``GeometricControl`` rows from its ``<part>_spec.py`` right before the final
save, so the shipped ``.SLDPRT`` carries its GD&T natively and the drawing
IMPORTS it (``_drawing_common.import_part_pmi``) instead of typing frozen
per-sheet strings.

The annotations are ORDINARY model gtols / datum tags
(``IModelDoc2::InsertGtol`` / ``::InsertDatumTag2``), NOT DimXpert PMI.
DimXpert authoring worked (probed 2026-07-28) but its display layer is
hostile to automation — display positions are UI-drag-only (every COM setter
reverts at save), FCFs on cylindrical faces are only legal in the
axis-perpendicular annotation view, and imported frames stack at the view
centre.  Plain annotations have none of those pathologies: ``SetPosition2``
persists exactly on both the part and the sheet (probed 2026-07-29,
``diagnostics/probe_pmi_plain_annotations.py``; see
``memory/dimxpert-pmi-placement.md``).

Part tier only: imports ``_common`` + ``_gtol_spec`` + the adapter — never a
drawing or assembly module (``check:partiso``).
"""

from __future__ import annotations

from typing import Any, Sequence

import _telemetry
from _common import _early_bound, _read_member
from _gtol_spec import (
    GTOL_SYMBOLS,
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

_GTOL_CURRENT_FORMAT = 2  # swGtolFormatType_e.GTOL_SW2022


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
    """Author ``datums`` then ``controls`` as plain model annotations."""
    if not datums and not controls:
        return
    model = adapter.currentModel
    with _telemetry.span("part.pmi", datums=len(datums), controls=len(controls)):
        for datum in datums:
            face = _resolve_face(model, datum.face, label=f"datum {datum.letter}")
            _select_face(model, face, label=f"datum {datum.letter}")
            tag = model.InsertDatumTag2()
            if tag is None:
                raise RuntimeError(
                    f"InsertDatumTag2 failed for datum {datum.letter}"
                )
            tag = _early_bound(tag, "IDatumTag")
            if not tag.SetLabel(datum.letter):
                raise RuntimeError(f"datum {datum.letter}: SetLabel failed")
            if str(tag.GetLabel() or "") != datum.letter:
                raise RuntimeError(
                    f"datum {datum.letter}: label did not persist "
                    f"(read back {tag.GetLabel()!r})"
                )
            _telemetry.event("pmi.datum", letter=datum.letter)

        for control in controls:
            face = _resolve_face(model, control.face, label=control.key)
            _select_face(model, face, label=control.key)
            gtol = model.InsertGtol()
            if gtol is None:
                raise RuntimeError(f"InsertGtol failed for {control.key}")
            gtol = _early_bound(gtol, "IGtol")
            if int(gtol.GetFormat()) != _GTOL_CURRENT_FORMAT:
                # InsertGtol instantiates an old-format empty gtol. SW 2026
                # drops the tolerance display if an EMPTY frame is converted
                # first and populated afterward (same pitfall
                # add_feature_control_frame documents), so seed the simple
                # compartments, THEN convert to the frame/XML format.
                datum_values = [*control.datums[:3], "", "", ""][:3]
                gtol.SetFrameSymbols2(
                    1,
                    f"<{GTOL_SYMBOLS[control.characteristic]}>",
                    control.diameter,
                    "",
                    False,
                    "",
                    "",
                    "",
                    "",
                )
                if not gtol.SetFrameValues2(1, control.tolerance, "", *datum_values):
                    raise RuntimeError(f"{control.key}: SetFrameValues2 failed")
                if not gtol.CanConvertFormat():
                    raise RuntimeError(
                        f"{control.key}: gtol cannot convert to current format"
                    )
                conversion_error = int(gtol.ConvertFormat())
                if conversion_error != 0:
                    raise RuntimeError(
                        f"{control.key}: ConvertFormat error {conversion_error}"
                    )
            frame = gtol.GetFrame(1)
            if frame is None:
                raise RuntimeError(f"{control.key}: gtol has no frame")
            applied = str(_early_bound(frame, "IGtolFrame").GetSymbolXml() or "")
            if (
                f"<ToleranceSymbol>{GTOL_SYMBOLS[control.characteristic]}<"
                not in applied
                or control.tolerance not in applied
            ):
                raise RuntimeError(
                    f"{control.key}: frame did not persist the spec "
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
