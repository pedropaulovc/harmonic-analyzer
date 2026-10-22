"""Radial Hole Wizard placement and perpendicular-cylinder removal volumes.

Shared wizard definitions and committed thread metadata remain in ``_holes``;
planar-only consumers do not depend on this cylindrical implementation.
"""

from __future__ import annotations

import _telemetry
from _com import _early_bound
from _hole_spec import HoleSpec
from _holes import (
    SW_FM_HOLE_WZD,
    _ENDS,
    _KINDS,
    _STD_ANSI_INCH,
    _commit_definition_edits,
    _through_tap_metadata,
    _verify_tap_metadata,
)
from _visibility import blank_sketch_feature


def cross_hole_volume_mm3(
    hole_dia_mm: float, shaft_dia_mm: float, n: int = 20001
) -> float:
    """Removed volume of a radial THROUGH hole drilled diametrally through a
    full cylinder (perpendicular cylinder-cylinder intersection, axes
    crossing): V = integral 2*sqrt(R^2-x^2) * 2*sqrt(r^2-x^2) dx, numeric --
    no clean closed form. Probe-verified 228.39 measured vs 228.41 analytic
    (#9 through Ø12, diag_hole_wizard_cyl 2026-07-11)."""
    import math

    r, big_r = hole_dia_mm / 2.0, shaft_dia_mm / 2.0
    total = 0.0
    dx = 2.0 * r / (n - 1)
    for i in range(n):
        x = -r + i * dx
        w = 0.5 if i in (0, n - 1) else 1.0
        total += (
            w
            * 2.0
            * math.sqrt(max(big_r**2 - x * x, 0.0))
            * 2.0
            * math.sqrt(max(r**2 - x * x, 0.0))
        )
    return total * dx


def wizard_hole_on_cylinder(
    adapter,
    spec: HoleSpec,
    point_mm,
    label: str,
    *,
    name: str = "",
    point_planes: tuple[str, ...],
) -> None:
    """ONE through wizard hole drilled RADIALLY into a cylindrical face at
    ``point_mm`` (a model point ON the face; the drill axis is the surface
    normal there, through the shaft axis).

    The planar-face path cannot serve a radial cross-hole (no planar face
    carries the drill axis); on a cylinder the wizard hangs its placement on
    a 3D sketch whose point coords ARE model coords, so no
    ModelToSketchTransform is involved (probe: diag_hole_wizard_cyl, volume
    exact to 0.01%). Through-all only -- a blind radial hole would need the
    HoleWizard5 positional path re-probed on a cylinder; through-next (stop
    at the next surface -- a crown tap that must end in the bore below it,
    not drill on through the casting) rides the same InitializeHole path with
    its own end condition, and a tap gets the same post-create thread
    class/termination write-back and readback as the planar path. Single-point: the
    wizard's auto point is moved onto the station; multi-point radial holes
    would each need their own feature anyway (one 3D-sketch point per face
    parameterization is untested).

    The face is selected by exact geometric containment of ``point_mm``:
    radial distance to the cylinder axis must equal the cylinder radius and
    the point must lie inside the trimmed face's bounding box. This prevents
    stepped shafts from silently drilling the largest, wrong-diameter land.
    """
    if spec.end not in ("through_all", "through_next"):
        raise ValueError(
            "wizard_hole_on_cylinder supports through_all and through_next only"
        )
    hole_type, fastener = _KINDS[spec.kind]

    model = adapter.currentModel
    model = _early_bound(model, "IModelDoc2")
    fm = model.FeatureManager
    fm = _early_bound(fm, "IFeatureManager")

    body = (_early_bound(model, "IPartDoc").GetBodies2(0, False) or [None])[0]
    body = _early_bound(body, "IBody2")
    point_m = tuple(float(value) / 1000.0 for value in point_mm)
    face_candidates = []
    tolerance_m = 1e-6
    for raw_face in body.GetFaces() or []:
        candidate = _early_bound(raw_face, "IFace2")
        surface = _early_bound(candidate.GetSurface(), "ISurface")
        if not surface.IsCylinder():
            continue
        params = tuple(float(value) for value in surface.CylinderParams)
        origin = params[:3]
        axis = params[3:6]
        radius = params[6]
        relative = tuple(point_m[i] - origin[i] for i in range(3))
        axial = sum(relative[i] * axis[i] for i in range(3))
        radial = tuple(relative[i] - axial * axis[i] for i in range(3))
        radial_distance = sum(value * value for value in radial) ** 0.5
        if abs(radial_distance - radius) > tolerance_m:
            continue
        box = tuple(float(value) for value in candidate.GetBox())
        if any(
            point_m[i] < box[i] - tolerance_m or point_m[i] > box[i + 3] + tolerance_m
            for i in range(3)
        ):
            continue
        face_candidates.append(candidate)
    if len(face_candidates) != 1:
        raise RuntimeError(
            f"hole wizard {label}: expected one cylindrical face containing "
            f"{point_mm}, found {len(face_candidates)}"
        )
    face = face_candidates[0]
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select2(False, 0):
        raise RuntimeError(f"hole wizard {label}: cylinder Select2 failed")
    _telemetry.debug(f"hole wizard {label}: cylinder selected, creating feature")

    data = fm.CreateDefinition(SW_FM_HOLE_WZD)
    data = _early_bound(data, "IWizardHoleFeatureData2")
    data.InitializeHole(hole_type, _STD_ANSI_INCH, fastener, spec.size, _ENDS[spec.end])
    feat = fm.CreateFeature(data)
    if feat is None:
        raise RuntimeError(
            f"hole wizard {label}: CreateFeature (cylinder) failed -- size "
            f"{spec.size!r} may be invalid for kind {spec.kind!r}"
        )
    feat = _early_bound(feat, "IFeature")
    _telemetry.debug(f"hole wizard {label}: feature created, placing point")

    # The placement is a 3D sketch with one auto point; its coords are model
    # coords -- pin it straight onto the station.
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    place = None
    sub = feat.GetFirstSubFeature()
    while sub is not None:
        sub = _early_bound(sub, "IFeature")
        if "Profile" in str(sub.GetTypeName2()):
            sk = sub.GetSpecificFeature2()
            sk = _early_bound(sk, "ISketch")
            if bool(sk.Is3D()) and len(sk.GetSketchPoints2() or []) == 1:
                place = (sub, sk)
                break
        sub = sub.GetNextSubFeature()
    if place is None:
        raise RuntimeError(f"hole wizard {label}: 3D placement sketch not found")
    sub, sk = place
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        str(sub.Name), "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"hole wizard {label}: cannot edit {sub.Name}")
    from _check import check
    from solidworks_mcp.adapters.solidworks.sketch import (
        _add_sketch_constraint_impl,
    )

    sketch_manager = _early_bound(model.SketchManager, "ISketchManager")
    part = _early_bound(adapter.currentModel, "IPartDoc")
    previous_sketch_manager = adapter.currentSketchManager
    adapter.currentSketchManager = sketch_manager
    editing_sketch = False
    active_error: BaseException | None = None
    try:
        model.EditSketch()
        editing_sketch = True
        pt = (sk.GetSketchPoints2() or [None])[0]
        pt = _early_bound(pt, "ISketchPoint")
        pt.SetCoords(
            point_mm[0] / 1000.0,
            point_mm[1] / 1000.0,
            point_mm[2] / 1000.0,
        )
        point_id = adapter._register_sketch_entity("Point", pt)
        for plane_name in point_planes:
            plane = part.FeatureByName(plane_name)
            if plane is None:
                raise RuntimeError(
                    f"hole wizard {label}: point plane {plane_name!r} not found"
                )
            plane_id = adapter._register_sketch_entity(
                "Plane", _early_bound(plane, "IFeature")
            )
            check(
                f"constrain radial hole placement {label} to {plane_name}",
                _add_sketch_constraint_impl(adapter, point_id, plane_id, "coincident"),
            )
    except BaseException as error:
        active_error = error
        raise
    finally:
        adapter.currentSketchManager = previous_sketch_manager
        if editing_sketch:
            try:
                model.EditSketch()
            except BaseException as cleanup_error:
                if active_error is None:
                    raise
                active_error.add_note(
                    f"hole wizard {label}: failed to exit placement sketch: "
                    f"{cleanup_error!r}"
                )
    _telemetry.debug(f"hole wizard {label}: point constrained, rebuilding")
    model.EditRebuild3()
    # Hidden by construction: a shown 3D placement sketch prints its point in
    # every render of the part and of each assembly that places it.
    blank_sketch_feature(model, sub, f"hole wizard {label}")
    if hole_type == 4:
        # Mirrors wizard_holes: only a non-blind tap needs the write-back (the
        # entry guard above refuses blind today), and every tap is read back.
        defn = _early_bound(feat.GetDefinition(), "IWizardHoleFeatureData2")
        if spec.end != "blind":
            defn = _commit_definition_edits(
                model, feat, defn, _through_tap_metadata(spec), label
            )
        _verify_tap_metadata(defn, spec, label)

    if name:
        try:
            feat.Name = name
        except Exception:  # noqa: BLE001
            _telemetry.warn(f"hole wizard {label}: rename to {name!r} failed")
    _telemetry.event(
        "hole_wizard.created",
        label=label,
        kind=spec.kind,
        size=spec.size,
        points=1,
        placement="cylindrical",
    )
    _telemetry.success(
        f"hole wizard {label}: radial {spec.size} {spec.kind} through cylinder"
    )
    return None
