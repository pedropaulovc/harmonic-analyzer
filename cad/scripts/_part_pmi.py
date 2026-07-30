"""Author a part's geometric controls as plain model annotations.

The PART build calls :func:`author_part_pmi` with the ``PartDatum`` /
``GeometricControl`` rows from its ``<part>_spec.py`` right before the final
save, so the shipped ``.SLDPRT`` carries its GD&T natively and the drawing
projects the same typed rows (``_drawing_common.project_part_pmi``) instead
of typing frozen per-sheet strings.

The annotations are ORDINARY model gtols / datum tags
(``IModelDoc2::InsertGtol`` / ``::InsertDatumTag2``), NOT DimXpert PMI.
DimXpert authoring worked (probed 2026-07-28) but its display layer is
hostile to automation — display positions are UI-drag-only (every COM setter
reverts at save), and FCFs on cylindrical faces are only legal in the
axis-perpendicular annotation view.  Plain annotations persist exactly on
the part.  Their shared typed spec is projected as native drawing annotations
because live SW 2026 constrains imported datum positions and interprets
imported FCF leader endpoints in model space (probed 2026-07-29,
``diagnostics/probe_pmi_plain_annotations.py``).

Part tier only: imports ``_common`` + ``_gtol_spec`` + the adapter — never a
drawing or assembly module (``check:partiso``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import _telemetry
from _common import _early_bound, _read_member
from _gtol_spec import (
    GTOL_SYMBOLS,
    ConeFace,
    CylinderFace,
    FaceSpec,
    GeometricControl,
    PartDatum,
    PlanarFace,
    SphereFace,
    TorusFace,
    gtol_frame_signature,
    validate_part_pmi,
)
from _surface_finish import SurfaceFinishControl
from solidworks_mcp.adapters.pywin32_adapter import null_callout

# swSurfaceTypes_e identities read via ISurface.Identity.
_SURFACE_PLANE = 4001
_SURFACE_CYLINDER = 4002
_SURFACE_CONE = 4003
_SURFACE_SPHERE = 4004
_SURFACE_TORUS = 4005

_GTOL_CURRENT_FORMAT = 2  # swGtolFormatType_e.GTOL_SW2022
_SELECT_FACE = 2  # swSelectType_e.swSelFACES


@dataclass(frozen=True)
class _FaceGeometry:
    face: Any
    identity: int
    parameters: tuple[float, ...]
    outward_normal: tuple[float, float, float] | None
    box: tuple[float, ...]


def _unit(vector: Sequence[float]) -> tuple[float, float, float]:
    x, y, z = (float(c) for c in vector)
    norm = (x * x + y * y + z * z) ** 0.5
    if norm == 0.0:
        raise ValueError("zero-length direction")
    return (x / norm, y / norm, z / norm)


def _face_geometry(face: Any) -> _FaceGeometry | None:
    face = _early_bound(face, "IFace2")
    surface = face.GetSurface()
    if surface is None:
        return None
    surface = _early_bound(surface, "ISurface")
    identity = int(_read_member(surface, "Identity"))
    if identity == _SURFACE_CYLINDER:
        return _FaceGeometry(
            face=face,
            identity=identity,
            parameters=tuple(_read_member(surface, "CylinderParams")),
            outward_normal=None,
            box=tuple(face.GetBox() or ()),
        )
    if identity == _SURFACE_CONE:
        return _FaceGeometry(
            face=face,
            identity=identity,
            parameters=tuple(_read_member(surface, "ConeParams2")),
            outward_normal=None,
            box=tuple(face.GetBox() or ()),
        )
    if identity == _SURFACE_PLANE:
        parameters = tuple(_read_member(surface, "PlaneParams"))
        normal = _unit(parameters[0:3])
        if bool(face.FaceInSurfaceSense()):
            normal = (-normal[0], -normal[1], -normal[2])
        return _FaceGeometry(
            face=face,
            identity=identity,
            parameters=parameters,
            outward_normal=normal,
            box=(),
        )
    if identity == _SURFACE_SPHERE:
        return _FaceGeometry(
            face=face,
            identity=identity,
            parameters=tuple(_read_member(surface, "SphereParams")),
            outward_normal=None,
            box=tuple(face.GetBox() or ()),
        )
    if identity == _SURFACE_TORUS:
        return _FaceGeometry(
            face=face,
            identity=identity,
            parameters=tuple(_read_member(surface, "TorusParams")),
            outward_normal=None,
            box=tuple(face.GetBox() or ()),
        )
    return _FaceGeometry(face, identity, (), None, ())


def _face_matches(geometry: _FaceGeometry, spec: FaceSpec) -> bool:
    tolerance_m = spec.tolerance_mm / 1000.0
    if isinstance(spec, CylinderFace):
        if geometry.identity != _SURFACE_CYLINDER:
            return False
        # CylinderParams: origin xyz, axis xyz, radius — meters.  The spec's
        # tolerance is a DIAMETER tolerance, so compare diameter to diameter.
        diameter_m = 2.0 * geometry.parameters[6]
        if abs(diameter_m - spec.diameter_mm / 1000.0) > tolerance_m:
            return False
        if spec.contains_x_mm is None and spec.contains_y_mm is None:
            return True
        if len(geometry.box) != 6:
            return False
        if spec.contains_x_mm is not None:
            x = spec.contains_x_mm / 1000.0
            if not geometry.box[0] - tolerance_m <= x <= geometry.box[3] + tolerance_m:
                return False
        if spec.contains_y_mm is not None:
            y = spec.contains_y_mm / 1000.0
            if not geometry.box[1] - tolerance_m <= y <= geometry.box[4] + tolerance_m:
                return False
        return True
    if isinstance(spec, ConeFace):
        if geometry.identity != _SURFACE_CONE:
            return False
        # ConeParams2: origin xyz, axis xyz, reference radius, half-angle,
        # reference direction xyz. The angle is radians.
        if abs(math.degrees(geometry.parameters[7]) - spec.half_angle_degrees) > (
            spec.tolerance_degrees
        ):
            return False
        if spec.contains_x_mm is None:
            return True
        if len(geometry.box) != 6:
            return False
        x = spec.contains_x_mm / 1000.0
        return geometry.box[0] - tolerance_m <= x <= geometry.box[3] + tolerance_m
    if isinstance(spec, PlanarFace):
        if geometry.identity != _SURFACE_PLANE or geometry.outward_normal is None:
            return False
        want = _unit(spec.normal)
        if sum(a * b for a, b in zip(geometry.outward_normal, want)) < 0.999:
            return False
        offset = sum(
            point * normal
            for point, normal in zip(geometry.parameters[3:6], geometry.outward_normal)
        )
        return abs(offset - spec.offset_mm / 1000.0) <= tolerance_m
    if isinstance(spec, SphereFace):
        if geometry.identity != _SURFACE_SPHERE:
            return False
        center = geometry.parameters[0:3]
        radius = geometry.parameters[3]
        if abs(2.0 * radius - spec.diameter_mm / 1000.0) > tolerance_m:
            return False
        if spec.center_mm is None:
            return True
        return all(
            abs(actual - expected / 1000.0) <= tolerance_m
            for actual, expected in zip(center, spec.center_mm)
        )
    if isinstance(spec, TorusFace):
        if geometry.identity != _SURFACE_TORUS:
            return False
        center = geometry.parameters[0:3]
        major_radius = geometry.parameters[6]
        minor_radius = geometry.parameters[7]
        if abs(major_radius - spec.major_radius_mm / 1000.0) > tolerance_m:
            return False
        if abs(minor_radius - spec.minor_radius_mm / 1000.0) > tolerance_m:
            return False
        if spec.center_mm is None:
            return True
        return all(
            abs(actual - expected / 1000.0) <= tolerance_m
            for actual, expected in zip(center, spec.center_mm)
        )
    raise TypeError(f"unsupported face spec: {spec!r}")


def _resolve_faces(model: Any, requests: dict[str, FaceSpec]) -> dict[str, Any]:
    """Resolve every face spec in one document traversal.

    The previous implementation retraversed every body and reread every
    surface once per annotation (36 traversals across the ten migrated parts).
    One traversal per part cuts that to ten and reads each face's COM geometry
    once, while keeping the exact-one-match contract per annotation.
    """
    matches: dict[str, list[Any]] = {label: [] for label in requests}
    part = _early_bound(model, "IPartDoc")
    for body in part.GetBodies2(0, False) or ():
        body = _early_bound(body, "IBody2")
        face = body.GetFirstFace()
        while face is not None:
            geometry = _face_geometry(face)
            if geometry is not None:
                for label, spec in requests.items():
                    if _face_matches(geometry, spec):
                        matches[label].append(geometry.face)
            face = _early_bound(face, "IFace2").GetNextFace()

    resolved: dict[str, Any] = {}
    for label, candidates in matches.items():
        if len(candidates) != 1:
            raise RuntimeError(
                f"{label}: face spec {requests[label]!r} matched "
                f"{len(candidates)} faces; the spec must identify exactly one"
            )
        resolved[label] = candidates[0]
    return resolved


def _select_face(model: Any, face: Any, *, label: str) -> None:
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select4(False, null_callout()):
        raise RuntimeError(f"{label}: face selection failed")


def _name_annotation(annotation: Any, *, name: str, label: str) -> Any:
    annotation = _early_bound(annotation, "IAnnotation")
    if not annotation.SetName(name):
        raise RuntimeError(f"{label}: failed to set unique annotation name {name!r}")
    if str(annotation.GetName() or "") != name:
        raise RuntimeError(
            f"{label}: annotation name did not persist "
            f"(read back {annotation.GetName()!r})"
        )
    return annotation


def _verify_attachment(annotation: Any, spec: FaceSpec, *, label: str) -> None:
    entities = tuple(annotation.GetAttachedEntities3() or ())
    entity_types = tuple(annotation.GetAttachedEntityTypes() or ())
    if len(entities) != 1 or entity_types != (_SELECT_FACE,) or entities[0] is None:
        raise RuntimeError(
            f"{label}: annotation attachment mismatch: "
            f"entities={len(entities)}, types={entity_types!r}; expected one face"
        )
    geometry = _face_geometry(entities[0])
    if geometry is None or not _face_matches(geometry, spec):
        raise RuntimeError(f"{label}: annotation attached to the wrong face")


def author_part_pmi(
    adapter: Any,
    *,
    datums: Sequence[PartDatum] = (),
    controls: Sequence[GeometricControl] = (),
    surface_finishes: Sequence[SurfaceFinishControl] = (),
) -> None:
    """Author ``datums`` then ``controls`` as plain model annotations."""
    if not datums and not controls and not surface_finishes:
        return
    validate_part_pmi(datums, controls)
    surface_keys = [control.key for control in surface_finishes]
    if len(surface_keys) != len(set(surface_keys)):
        raise ValueError("surface-finish keys must be unique within one part")
    model = adapter.currentModel
    requests = {datum.key: datum.face for datum in datums}
    requests.update({control.key: control.face for control in controls})
    requests.update(
        {f"surface:{control.key}": control.face for control in surface_finishes}
    )
    with _telemetry.span(
        "part.pmi",
        datums=len(datums),
        controls=len(controls),
        surface_finishes=len(surface_finishes),
    ):
        resolved_faces = _resolve_faces(model, requests)
        for datum in datums:
            face = resolved_faces[datum.key]
            _select_face(model, face, label=f"datum {datum.letter}")
            tag = model.InsertDatumTag2()
            if tag is None:
                raise RuntimeError(f"InsertDatumTag2 failed for datum {datum.letter}")
            tag = _early_bound(tag, "IDatumTag")
            if not tag.SetLabel(datum.letter):
                raise RuntimeError(f"datum {datum.letter}: SetLabel failed")
            if str(tag.GetLabel() or "") != datum.letter:
                raise RuntimeError(
                    f"datum {datum.letter}: label did not persist "
                    f"(read back {tag.GetLabel()!r})"
                )
            annotation = _name_annotation(
                tag.GetAnnotation(),
                name=datum.annotation_name,
                label=f"datum {datum.letter}",
            )
            _verify_attachment(annotation, datum.face, label=f"datum {datum.letter}")
            _telemetry.event("pmi.datum", letter=datum.letter)

        for control in controls:
            face = resolved_faces[control.key]
            _select_face(model, face, label=control.key)
            gtol = model.InsertGtol()
            if gtol is None:
                raise RuntimeError(f"InsertGtol failed for {control.key}")
            gtol = _early_bound(gtol, "IGtol")
            migrated = int(gtol.GetFormat()) != _GTOL_CURRENT_FORMAT
            if migrated:
                # InsertGtol instantiates an old-format empty gtol. SW 2026
                # drops the tolerance display if an EMPTY frame is converted
                # first and populated afterward (same pitfall
                # add_feature_control_frame documents), so seed the simple
                # compartments, THEN convert to the frame/XML format.
                datum_values = [*control.datums[:3], "", "", ""][:3]
                gtol.SetFrameSymbols2(
                    1,
                    f"<{GTOL_SYMBOLS[control.characteristic]}>",
                    control.tolerance_zone == "diametral",
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
            if int(gtol.GetFormat()) != _GTOL_CURRENT_FORMAT:
                raise RuntimeError(f"{control.key}: gtol remained in old format")

            frame_count = int(gtol.GetFrameCount() or 0)
            if frame_count == 0:
                if not gtol.AddFrame():
                    raise RuntimeError(f"{control.key}: failed to add current frame")
                frame_count = int(gtol.GetFrameCount() or 0)
            if frame_count != 1:
                raise RuntimeError(
                    f"{control.key}: expected one frame, found {frame_count}"
                )
            frame = gtol.GetFrame(1)
            if frame is None:
                raise RuntimeError(f"{control.key}: gtol has no frame")
            frame = _early_bound(frame, "IGtolFrame")
            if not migrated and not frame.SetSymbolXml(control.frame_xml):
                raise RuntimeError(
                    f"{control.key}: SOLIDWORKS rejected current frame XML"
                )
            applied = str(frame.GetSymbolXml() or "")
            if gtol_frame_signature(applied) != gtol_frame_signature(control.frame_xml):
                raise RuntimeError(
                    f"{control.key}: frame did not persist the spec "
                    f"(read back {applied[:120]!r})"
                )
            annotation = _name_annotation(
                gtol.GetAnnotation(),
                name=control.annotation_name,
                label=control.key,
            )
            _verify_attachment(annotation, control.face, label=control.key)
            if not bool(gtol.IsAttached()) or int(gtol.GetLeaderCount()) != 1:
                raise RuntimeError(
                    f"{control.key}: gtol attachment mismatch: "
                    f"attached={bool(gtol.IsAttached())}, "
                    f"leaders={gtol.GetLeaderCount()}"
                )
            _telemetry.event(
                "pmi.gtol",
                key=control.key,
                characteristic=control.characteristic,
                tolerance=control.tolerance,
            )

        for control in surface_finishes:
            label = f"surface:{control.key}"
            face = resolved_faces[label]
            _select_face(model, face, label=label)
            box = tuple(face.GetBox() or ())
            position = (
                (box[3] + 0.01, box[4] + 0.01, box[5] + 0.01)
                if len(box) == 6
                else (0.01, 0.01, 0.01)
            )
            symbol = model.Extension.InsertSurfaceFinishSymbol3(
                1,  # installed R2026x swSFMachining_Req
                1,  # swLeaderStyle_e.swSTRAIGHT
                *position,
                0,  # swSFLaySym_e.swSFNone
                1,  # swArrowStyle_e.swCLOSED_ARROWHEAD
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            )
            if symbol is None:
                raise RuntimeError(f"{label}: InsertSurfaceFinishSymbol3 failed")
            symbol = _early_bound(symbol, "ISFSymbol")
            roughness = f"Ra {control.roughness_ra}"
            if not symbol.SetText(8, roughness):
                raise RuntimeError(f"{label}: failed to set roughness")
            if control.production_method and not symbol.SetText(
                2, control.production_method
            ):
                raise RuntimeError(f"{label}: failed to set production method")
            if int(symbol.GetSymbol()) != 1:
                raise RuntimeError(f"{label}: machining-required symbol did not persist")
            if str(symbol.GetText(8) or "").strip() != roughness:
                raise RuntimeError(f"{label}: roughness did not persist")
            if control.production_method and str(symbol.GetText(2) or "").strip() != (
                control.production_method
            ):
                raise RuntimeError(f"{label}: production method did not persist")
            annotation = _name_annotation(
                symbol.GetAnnotation(),
                name=control.annotation_name,
                label=label,
            )
            _verify_attachment(annotation, control.face, label=label)
            if not bool(symbol.IsAttached()) or int(symbol.GetLeaderCount()) != 1:
                raise RuntimeError(
                    f"{label}: leader attachment mismatch: "
                    f"attached={bool(symbol.IsAttached())}, "
                    f"leaders={symbol.GetLeaderCount()}"
                )
            _telemetry.event(
                "pmi.surface_finish",
                key=control.key,
                roughness_um=control.roughness_um,
                production_method=control.production_method,
            )
        model.ClearSelection2(True)
        _telemetry.success(
            f"part PMI authored: {len(datums)} datums, {len(controls)} controls, "
            f"{len(surface_finishes)} surface finishes"
        )
