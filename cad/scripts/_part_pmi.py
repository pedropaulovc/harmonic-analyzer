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

Part tier only: imports ``_com`` + the focused GD&T contracts and face
resolver + the adapter — never a drawing or assembly module (``check:partiso``).
"""

from __future__ import annotations

from typing import Any, Sequence

import _telemetry
from _com import _early_bound
from _gtol_controls import GeometricControl, PartDatum, validate_part_pmi
from _gtol_face import FaceSpec
from _gtol_face_read import face_geometry
from _gtol_face_resolve import resolve_faces
from _gtol_frame import gtol_frame_signature
from _gtol_symbols import GTOL_SYMBOLS
from _surface_finish import SurfaceFinishControl
from solidworks_mcp.adapters.pywin32_adapter import null_callout

_GTOL_CURRENT_FORMAT = 2  # swGtolFormatType_e.GTOL_SW2022
_SELECT_FACE = 2  # swSelectType_e.swSelFACES


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
    geometry = face_geometry(entities[0])
    if geometry is None or not spec.matches(geometry):
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
        resolved_faces = resolve_faces(model, requests)
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
            if control.native_attachment == "face":
                _select_face(model, face, label=label)
            else:
                model.ClearSelection2(True)
            box = tuple(face.GetBox() or ())
            position = (
                (box[3] + 0.01, box[4] + 0.01, box[5] + 0.01)
                if len(box) == 6
                else (0.01, 0.01, 0.01)
            )
            symbol = model.Extension.InsertSurfaceFinishSymbol3(
                1,  # installed R2026x swSFMachining_Req
                1 if control.native_attachment == "face" else 0,
                # swLeaderStyle_e.swSTRAIGHT / swNO_LEADER
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
            if control.native_attachment == "face":
                _verify_attachment(annotation, control.face, label=label)
                if not bool(symbol.IsAttached()) or int(symbol.GetLeaderCount()) != 1:
                    raise RuntimeError(
                        f"{label}: leader attachment mismatch: "
                        f"attached={bool(symbol.IsAttached())}, "
                        f"leaders={symbol.GetLeaderCount()}"
                    )
            else:
                attached = tuple(annotation.GetAttachedEntities3() or ())
                leader_style = int(annotation.GetLeaderStyle())
                if attached or bool(symbol.IsAttached()) or leader_style != 0:
                    raise RuntimeError(
                        f"{label}: model-owned symbol unexpectedly attached: "
                        f"entities={len(attached)}, attached={bool(symbol.IsAttached())}, "
                        f"leader_style={leader_style}, leaders={symbol.GetLeaderCount()}"
                    )
            _telemetry.event(
                "pmi.surface_finish",
                key=control.key,
                roughness_um=control.roughness_um,
                production_method=control.production_method,
                native_attachment=control.native_attachment,
            )
        model.ClearSelection2(True)
        _telemetry.success(
            f"part PMI authored: {len(datums)} datums, {len(controls)} controls, "
            f"{len(surface_finishes)} surface finishes"
        )
