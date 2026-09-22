r"""Reproduction script: knife bearing support (book ch. 18, pp. 42-43).

The hardened-steel bearing block that suspends the summing lever's knife edge from the
top-frame casting's integral crossbar (hung by the stepped knife-hanger stud, whose
shoulder seats on the block top over a #10-24 tip in the block-top tap). The lever rocks as a FIRST-CLASS LEVER on the **top vertex line
of its hexagonal pivot trunnions** (build_summing_lever ``_hex_collar``); each
trunnion overhangs the lever body into one of these supports.

DESIGN (user direction, 2026-06-17, refs: ch30-p003, bore.png, ch18 p.43 photo):
a **circular bore around the hex trunnion**, so that *only the top knife edge
of the trunnion* contacts the bore -- the upper inner wall of the bore meets
the hex's top vertex line while every other facet clears. This is the true
knife-edge suspension: line contact at the ridge, free to rock, replacing the
M6.4 "diamond knife-bar in the lever tube bore" (which clashed with the lever's
solid pivot cylinder once the bore was removed). 2026-09-02 user re-read of
ch18 p.42: the block is an UNPAINTED HEAT-TREATED STEEL block (not brass) with
a CLOSE bore around the trunnion -- Ø12 over the 8.653 x 10.268 hex.  At
finished-size limits it clears the observed ±1.6-degree rocking sweep.

There are TWO supports, one per trunnion (placed front/back in the assembly at
|z| ~ 87). This single part is built once and placed twice.

Layout (part-local): origin = the **knife-edge contact line** = the hex top
vertex ridge (placed at machine (15, 984.83, +-87)); local Z = the bore/trunnion
axis, +Y up, +X across. The bore centre sits ``R_BORE`` below the origin so the
bore's upper inner wall lands on the ridge. The block rises from below the bore
up to just under the top-frame casting underside (999.7). The stepped hanger
stud's shoulder seats on the block top, and its #10-24 tip engages >= 1.5D of
the blind tap (knife_hanger_interface; user ruling 2026-09-22,
machining-dfm.md:73). A conventional 118-degree tap drill retains at least
0.50 mm of uninterrupted material above the bore at limits.

The named "knife axis" is the contact ridge line itself (part origin); the
assembly mates the lever's knife ridge (``Axis3@summing-lever``) coincident to
it, so the lever rocks about the true knife edge (not the cylinder centre).

Dimensions: cad/DIMENSIONS.md ch. 18. Bore size remains low-confidence
photo-derived geometry; its hard constraints are ridge contact and the observed
rocking sweep at finished-size limits.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_knife_mount.py
"""

from __future__ import annotations

import json
import math
import sys
from typing import Any

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from summing_lever_spec import HEX_H, HEX_W
from _holes import blind_hole_volume_mm3, find_planar_face, wizard_holes
from _drawing_marks import (
    _named_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
)
from _part_pmi import author_part_pmi
from knife_mount_spec import (
    BORE_DIAMETER_TOLERANCE_MM,
    BORE_FROM_TOP_TOLERANCE_MM,
    BORE_FROM_TOP,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    MATING_HEX_SIZE_PLUS_MM,
    REQUIRED_ROCK_SWEEP_DEG,
    STUD_TAP_CROWN_WEB_MM,
    STUD_TAP_DIA,
    STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM,
    STUD_TAP_DRILL_DEPTH_MM,
    STUD_TAP_PITCH_MM,
    STUD_TAP_POINT_HEIGHT_MM,
    STUD_TAP_SPEC,
    STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM,
    STUD_TAP_THREAD_DEPTH_MM,
    STUD_TAP_WORST_CASE_CROWN_WEB_MM,
    STUD_TAP_WORST_CASE_RUNOUT_MM,
    SURFACE_FINISHES,
)

from knife_hanger_interface import CASTING_UNDERSIDE_Y, MOUNT_GAP
import _telemetry

PART_NAME = "knife-mount"
# ch18 p.42 (2026-09-02 user re-read): an unpainted HEAT-TREATED steel block,
# not the brass of the earlier registry/DFM pass.
MATERIAL = "Plain Carbon Steel"
HARDENED_STEEL = (0.30, 0.30, 0.31)  # dark heat-treated grey, left unpainted

# --- knife-edge geometry (kept in sync with the lever's hex trunnion) -------
RIDGE_Y = HEX_H / 2.0  # hex top vertex above the pivot/cylinder centreline (5.134)

# --- bore: close around the hex trunnion, actual top-ridge line contact -----
R_BORE = 6.0  # Ø12 bore around the 8.653 x 10.268 hex trunnion
TOP_CLEAR = 0.0  # bore crown is tangent to the lever's top-vertex knife ridge
BORE_CY = TOP_CLEAR - R_BORE  # -6.0; upper inner wall lies on the knife axis

# --- block (bearing body, held to the crossbar) ----------------------------
# Axial depth. 2026-09-22 user decision: 18 (was 16) so the tap, located
# Depth/2 from one end face, keeps >= 1.2 mm of wall on both sides of the
# 1/2-13 thread at the printed bands (test_knife_mount_drawing). The #10-24
# tap that replaced it would also pass at 16; the user kept 18.
SUPPORT_Z_THICK = 18.0
BLK_HALF_X = 12.0  # bore wall + flank (24 across, photo-scaled)
WALL = 3.0  # material below the bore
BLK_BOT = BORE_CY - R_BORE - WALL  # -15.0

# Mount: the block top seat hangs MOUNT_GAP below the top-frame casting
# underside (the integral crossbar's flush lower face); the stepped knife-hanger
# stud's shoulder seats on that top face and carries the hang. CASTING_UNDERSIDE_Y
# and MOUNT_GAP come from knife_hanger_interface (the joint's seat plane).
KNIFE_Y = 979.7  # machine y of the pivot centreline (build_summing_assembly KNIFE)
CONTACT_Y = KNIFE_Y + RIDGE_Y  # machine y of the knife-edge contact line (984.834)
BLK_TOP = CASTING_UNDERSIDE_Y - CONTACT_Y - MOUNT_GAP  # exact local top 14.616


# --- hanger-stud tap: #10-24 UNC-2B blind in the block top ------------------
# A conventional 118-degree drill and bottoming tap take the stepped stud's
# #10-24 tip while their native depth bands (knife_hanger_interface) preserve
# an uninterrupted crown.



def _minimum_hex_rock_clearance_mm() -> float:
    """Return the worst noncontact-vertex clearance over the required sweep."""
    bore_radius = R_BORE - BORE_DIAMETER_TOLERANCE_MM / 2.0
    width = HEX_W + MATING_HEX_SIZE_PLUS_MM
    height = HEX_H + MATING_HEX_SIZE_PLUS_MM
    vertices = (
        (-width / 2.0, -height / 4.0),
        (-width / 2.0, -3.0 * height / 4.0),
        (0.0, -height),
        (width / 2.0, -3.0 * height / 4.0),
        (width / 2.0, -height / 4.0),
    )
    sweep = math.radians(REQUIRED_ROCK_SWEEP_DEG)
    clearance = math.inf
    for x, y in vertices:
        candidates = [-sweep, sweep]
        stationary = math.atan2(x, y)
        for half_turn in range(-2, 3):
            angle = stationary + half_turn * math.pi
            if -sweep <= angle <= sweep:
                candidates.append(angle)
        maximum_radius = max(
            math.sqrt(
                x * x
                + y * y
                + bore_radius * bore_radius
                + 2.0
                * bore_radius
                * (x * math.sin(angle) + y * math.cos(angle))
            )
            for angle in candidates
        )
        clearance = min(clearance, bore_radius - maximum_radius)
    return clearance


def _hole_dimension_inventory_entry(display, dimension) -> dict[str, object]:
    """Describe one native Hole Wizard display dimension for failure forensics."""
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    return {
        "full_name": str(dimension.FullName),
        "name": str(dimension.Name),
        "value_mm": float(dimension.SystemValue) * 1000.0,
        "dimension_type": int(dimension.GetType()),
        "reference": bool(dimension.IsReference()),
        "read_only": bool(dimension.ReadOnly),
        "display_type": int(display.GetType()),
        "hole_callout": bool(display.IsHoleCallout()),
        "tolerance_type": int(tolerance.Type),
        "tolerance_lower_mm": float(tolerance.GetMinValue()) * 1000.0,
        "tolerance_upper_mm": float(tolerance.GetMaxValue()) * 1000.0,
        "primary_precision": int(display.GetPrimaryPrecision2()),
        "tolerance_precision": int(display.GetPrimaryTolPrecision2()),
    }


def _tolerance_hole_depth(
    adapter,
    feature_name: str,
    dimension_token: str,
    deviations_mm: tuple[float, float],
) -> None:
    """Apply and read back one native Hole Wizard depth tolerance in the part."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    feature = model.FeatureByName(feature_name)
    if feature is None:
        raise RuntimeError(f"missing Hole Wizard feature {feature_name!r}")
    feature = _early_bound(feature, "IFeature")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError(f"{feature_name}: Hole Wizard definition is unavailable")
    definition = _early_bound(definition, "IWizardHoleFeatureData2")
    matches = []
    thread_depth_candidates = []
    inventory = []
    display = feature.GetFirstDisplayDimension()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        dimension = display.GetDimension()
        if dimension is not None:
            dimension = _early_bound(dimension, "IDimension")
            full_name = str(dimension.FullName)
            normalized = "".join(
                character for character in full_name.lower() if character.isalnum()
            )
            entry = _hole_dimension_inventory_entry(display, dimension)
            inventory.append(entry)
            if dimension_token in normalized:
                matches.append((display, dimension))
            owner = full_name.split("@", 2)
            if (
                dimension_token == "fullthreaddepth"
                and len(owner) >= 2
                and owner[1].lower().startswith("hole thread")
                and int(display.GetType()) == 2
                and not bool(dimension.ReadOnly)
                and abs(
                    float(dimension.SystemValue) - float(definition.ThreadDepth)
                )
                <= 1e-9
            ):
                thread_depth_candidates.append((display, dimension, entry))
        display = feature.GetNextDisplayDimension(display)

    semantic_rename = None
    if not matches and dimension_token == "fullthreaddepth":
        if len(thread_depth_candidates) == 1:
            display, dimension, entry = thread_depth_candidates[0]
            prior_full_name = str(dimension.FullName)
            dimension.Name = "Full Thread Depth"
            renamed_full_name = str(dimension.FullName)
            renamed_normalized = "".join(
                character
                for character in renamed_full_name.lower()
                if character.isalnum()
            )
            if "fullthreaddepth" not in renamed_normalized:
                raise RuntimeError(
                    f"{feature_name}: semantic thread-depth rename did not persist: "
                    f"{renamed_full_name!r}"
                )
            entry["renamed_full_name"] = renamed_full_name
            semantic_rename = {
                "from": prior_full_name,
                "to": renamed_full_name,
            }
            matches.append((display, dimension))
        elif thread_depth_candidates:
            semantic_rename = {
                "candidate_count": len(thread_depth_candidates),
                "status": "ambiguous",
            }

    evidence = {
        "event": "native_hole_dimension_inventory",
        "feature": feature_name,
        "requested_token": dimension_token,
        "definition": {
            "TapDrillDepth_mm": float(definition.TapDrillDepth) * 1000.0,
            "ThreadDepth_mm": float(definition.ThreadDepth) * 1000.0,
        },
        "semantic_rename": semantic_rename,
        "dimensions": inventory,
    }
    _telemetry.info(json.dumps(evidence, sort_keys=True))
    if len(matches) != 1:
        raise RuntimeError(
            f"{feature_name}: expected one {dimension_token} display dimension, "
            f"found {len(matches)}; native evidence: "
            f"{json.dumps(evidence, sort_keys=True)}"
        )
    display, dimension = matches[0]
    lower_mm, upper_mm = deviations_mm
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 2  # swTolBILAT
    if not tolerance.SetValues(lower_mm / 1000.0, upper_mm / 1000.0):
        raise RuntimeError(
            f"{feature_name} {dimension_token}: rejected native depth tolerance"
        )
    lower = float(tolerance.GetMinValue()) * 1000.0
    upper = float(tolerance.GetMaxValue()) * 1000.0
    if (
        int(tolerance.Type) != 2
        or abs(lower - lower_mm) > 1e-6
        or abs(upper - upper_mm) > 1e-6
    ):
        raise RuntimeError(
            f"{feature_name} {dimension_token}: tolerance readback "
            f"{lower:+.3f}/{upper:+.3f} mm"
        )
    display.SetPrecision3(2, -1, 2, -1)
    if (
        int(display.GetPrimaryPrecision2()) != 2
        or int(display.GetPrimaryTolPrecision2()) != 2
    ):
        raise RuntimeError(
            f"{feature_name} {dimension_token}: depth precision did not persist"
        )
    readback = feature.GetDefinition()
    if readback is None:
        raise RuntimeError(
            f"{feature_name} {dimension_token}: definition unavailable after tolerance"
        )
    readback = _early_bound(readback, "IWizardHoleFeatureData2")
    if (
        abs(float(readback.TapDrillDepth) - float(definition.TapDrillDepth)) > 1e-9
        or abs(float(readback.ThreadDepth) - float(definition.ThreadDepth)) > 1e-9
    ):
        raise RuntimeError(
            f"{feature_name} {dimension_token}: depth nominal changed while "
            "authoring its tolerance"
        )


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


# swDimensionDrivenState_e. A sketch dimension reads DRIVING (2) as authored
# and DRIVEN (1) once an equation owns its value -- the equation, not the
# sketch, is then its single driver. Measured on the farm (knife-cc-5,
# 3c7efb27): TapFromEnd, BlockWidth and Depth all read 2 up to the deferred
# equations and 1 after them, IsReference() False throughout, and the sheet
# prints all three plain. So "driving" is asserted at authoring, and after
# the equations the dimension must share the equation-owned state of the
# BlockWidth control -- never a bare "== 2" that every equation fails.
_DIMENSION_DRIVING = 2
_DIMENSION_DRIVEN = 1
# swConstraintType_e: the placement point's only relations -- vertical to the
# sketch origin (on the bore centreline) and the 9.00 distance to the near
# end edge. A coincident (9) would own the thickness DOF instead.
_TAP_PLACEMENT_RELATIONS = sorted([26, 1])  # VERTPOINTS, DISTANCE
_SW_FULLY_CONSTRAINED = 3  # swConstrainedStatus_e


def _tap_placement(adapter: Any) -> tuple[Any, Any, Any, str]:
    """The StudTap wizard's placement subfeature and sketch.

    The same subfeature walk ``_holes`` uses to place the wizard points: Hole
    Wizard placement dimensions live one level below the recipe-named feature.
    """
    model = adapter.currentModel
    part = _early_bound(model, "IPartDoc")
    feature = part.FeatureByName("StudTap")
    if feature is None:
        raise RuntimeError("hanger-stud tap: StudTap feature not found")
    sub = _early_bound(feature, "IFeature").GetFirstSubFeature()
    while sub is not None:
        sub = _early_bound(sub, "IFeature")
        if str(sub.GetTypeName2()) == "ProfileFeature":
            sketch = _early_bound(sub.GetSpecificFeature2(), "ISketch")
            if len(sketch.GetSketchPoints2() or []) == 1:
                return model, sub, sketch, str(sub.Name)
        sub = sub.GetNextSubFeature()
    raise RuntimeError("hanger-stud tap: wizard placement sketch not found")


def _model_point_in_placement(
    adapter: Any, sketch: Any, model_point_mm: list[float]
) -> tuple[float, float, float]:
    """Forward-map a model point into the placement sketch's coordinates.

    The same ``ModelToSketchTransform`` product ``_holes`` derives for the
    wizard points, so the tap's solved position and its intended model station
    are compared in one coordinate space instead of trusted.
    """
    import pythoncom
    from win32com.client import VARIANT

    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    array = VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        [value / 1000.0 for value in model_point_mm],
    )
    mapped = _early_bound(
        _early_bound(math_util.CreatePoint(array), "IMathPoint").MultiplyTransform(xform),
        "IMathPoint",
    )
    return tuple(float(value) for value in mapped.ArrayData)[:3]


def _assert_tap_station(adapter: Any, sketch: Any) -> None:
    """The tap must still sit at x=0 on the extrusion mid-plane.

    The solved placement point against the model station (0, BLK_TOP, 0)
    mapped into the same sketch -- one space, no assumption about the sketch
    origin's model position.
    """
    point = _early_bound((sketch.GetSketchPoints2() or [None])[0], "ISketchPoint")
    solved = adapter._point_xyz(point)
    expected = _model_point_in_placement(adapter, sketch, [0.0, BLK_TOP, 0.0])
    if solved is None or any(
        abs(got - want) > 1e-7 for got, want in zip(solved, expected, strict=True)
    ):
        raise RuntimeError(
            f"hanger-stud tap: placement moved off the mid-plane station: "
            f"solved {solved}, expected {expected}"
        )


def _assert_tap_from_end(dimension: Any) -> None:
    """A DRIVING 9.00 mm dimension -- read back, never assumed."""
    state = int(dimension.DrivenState)
    if state != _DIMENSION_DRIVING:
        raise RuntimeError(
            "hanger-stud tap: tap-from-end dimension authored "
            f"{'driven (reference)' if state == 1 else f'state {state}'}, not driving"
        )
    measured_mm = abs(float(dimension.SystemValue)) * 1000.0
    if abs(measured_mm - SUPPORT_Z_THICK / 2.0) > 1e-5:
        raise RuntimeError(
            f"hanger-stud tap: tap-from-end reads {measured_mm:.4f} mm, "
            f"expected {SUPPORT_Z_THICK / 2.0:.4f} mm"
        )


async def _dimension_tap_from_end(adapter: Any) -> tuple[str, str]:
    """Author the tap's thickness-direction location as a DRIVING model dim.

    The wizard's placement sketch sits on the top face with its origin on the
    model origin's projection -- the tap's own station, since the block
    extrudes symmetrically about it -- so ``_holes`` cannot dimension the
    placement (a zero coordinate may not carry a distance dimension), which is
    why the sheet had to print ``(9.00)`` as a reference. Hold the tap on the
    bore centreline with the one axis relation and dimension the point from
    the block's near END edge instead: 9.00 mm, driving, from the outer face
    the machinist asked for, owned by the model like every other marked dim.
    """
    from _common import check
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    from solidworks_mcp.adapters.solidworks.sketch import (
        _add_sketch_constraint_impl,
    )

    model, _sub, sketch, place_name = _tap_placement(adapter)
    point = _early_bound((sketch.GetSketchPoints2() or [None])[0], "ISketchPoint")

    # The 9.00 measures from the block's OUTER (near) end face: pick its edge
    # inside the top face by endpoint midpoint -- never by coordinate
    # SelectByID2, which mis-resolves on end faces (see _holes's header).
    top_face = find_planar_face(model, (0.0, 1.0, 0.0), [[0.0, BLK_TOP, 0.0]])
    near_edge = None
    for raw_edge in top_face.GetEdges() or ():
        edge = _early_bound(raw_edge, "IEdge")
        ends = [
            tuple(float(value) for value in _early_bound(v, "IVertex").GetPoint())
            for v in (edge.GetStartVertex(), edge.GetEndVertex())
            if v is not None
        ]
        if len(ends) != 2:
            continue
        mid = [sum(pair) / 2.0 for pair in zip(*ends)]
        if abs(mid[0]) < 1e-7 and abs(mid[2] + SUPPORT_Z_THICK / 2000.0) < 1e-7:
            near_edge = edge
            break
    if near_edge is None:
        raise RuntimeError("hanger-stud tap: block near end edge not found")

    sm = _early_bound(model.SketchManager, "ISketchManager")
    previous_sketch_manager = adapter.currentSketchManager
    adapter.currentSketchManager = sm
    adapter._sketch_origin_point = None
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        place_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"hanger-stud tap: cannot edit {place_name}")
    editing = False
    try:
        model.EditSketch()
        editing = True
        # SolidWorks resets swInputDimValOnCreate on every sketch entry: the
        # Modify dialog would block the unattended session (the same per-call
        # re-assert the adapter's add_sketch_dimension makes).
        adapter._attempt(lambda: adapter.swApp.SetUserPreferenceToggle(10, False))
        adapter._attempt(lambda: adapter.swApp.SetUserPreferenceToggle(372, False))
        adapter._attempt(lambda: adapter.swApp.SetUserPreferenceToggle(520, False))
        point_id = adapter._register_sketch_entity("Point", point)
        check(
            "tap on the bore centreline",
            _add_sketch_constraint_impl(adapter, point_id, "origin", "vertical_points"),
        )
        # Raw COM, narrowly: adapter.add_sketch_dimension cannot dimension a
        # point against an EDGE -- its distance types hard-require two point
        # refs (sketch.py:1467-1490) and this 9.00 must measure to the block's
        # near end edge. Mixed selection is the same shape as that helper's own
        # _try_create_angular_dimension (sketch.py:1508-1548).
        model.ClearSelection2(True)
        if not adapter._select_sketch_entity(point, append=False):
            raise RuntimeError("hanger-stud tap: placement point selection failed")
        if not _early_bound(near_edge, "IEntity").Select2(True, 0):
            raise RuntimeError("hanger-stud tap: near end edge selection failed")
        text = (0.0, BLK_TOP / 1000.0, -SUPPORT_Z_THICK / 4000.0)
        display = adapter._attempt(lambda: model.AddDimension2(*text), default=None)
        if display is None:
            display = adapter._attempt(
                lambda: model.Extension.AddDimension(
                    *text, adapter.constants["swSmartDimensionDirectionUp"]
                ),
                default=None,
            )
        if display is None:
            raise RuntimeError("hanger-stud tap: tap-from-end dimension did not insert")
        dimension = (
            adapter._attempt(lambda: display.GetDimension2(0), default=None)
            or adapter._attempt(lambda: display.GetDimension(), default=None)
            or display
        )
        dimension = _early_bound(dimension, "IDimension")
        target_m = SUPPORT_Z_THICK / 2000.0
        if (
            adapter._attempt(
                lambda: dimension.SetSystemValue3(target_m, 1, None), default=None
            )
            is None
            and adapter._attempt(
                lambda: dimension.SetSystemValue2(target_m, 1), default=None
            )
            is None
        ):
            dimension.SystemValue = target_m
        dimension.Name = "TapFromEnd"
        if str(dimension.Name) != "TapFromEnd":
            raise RuntimeError("hanger-stud tap: tap-from-end rename did not persist")
        _assert_tap_from_end(dimension)
        _assert_tap_station(adapter, sketch)
        await ensure_fully_defined(adapter, "hanger-stud tap placement")
    finally:
        adapter.currentSketchManager = previous_sketch_manager
        if editing:
            model.EditSketch()
    if not model.EditRebuild3():
        raise RuntimeError("hanger-stud tap: placement rebuild failed")
    return f"TapFromEnd@{place_name}", '"SupportZThick" / 2'


def _equations_for(adapter: Any, lhs: str) -> list[str]:
    """Every equation whose left-hand side is exactly ``lhs``."""
    from solidworks_mcp.adapters.solidworks.parametrics import (
        _equation_manager,
        _read_member,
    )

    # The same flagged manager + GetCount read the adapter's own
    # _equation_index_by_lhs uses (GetCount resolves as a property or a method
    # depending on the dispatch).
    manager = _equation_manager(adapter)
    matches = []
    for index in range(int(_read_member(manager, "GetCount") or 0)):
        text = str(manager.Equation(index) or "")
        if text.partition("=")[0].strip() == lhs:
            matches.append(text)
    return matches


def _assert_tap_from_end_contract(adapter: Any) -> None:
    """After the deferred equations and the final rebuild.

    The volume gates prove the cut did not move; this proves the 9.00 has ONE
    owner and it is not a reference dimension: exactly one equation drives
    ``TapFromEnd``, the dimension reads the same equation-owned state as the
    BlockWidth control (see ``_DIMENSION_DRIVEN``), IsReference() is False,
    the placement sketch is fully defined by the vertical relation plus the
    9.00 alone (no coincident owns the DOF), and the tap still sits on the
    mid-plane station. The drawing proves the sheet prints it unparenthesized.
    """
    _, _, sketch, place_name = _tap_placement(adapter)
    _display, dimension = _named_dimension(adapter, "StudTap", "TapFromEnd")
    _control_display, control = _named_dimension(adapter, "BlockProfile", "BlockWidth")
    equations = _equations_for(adapter, f'"TapFromEnd@{place_name}"')
    relations = sorted(
        int(_early_bound(raw, "ISketchRelation").GetRelationType())
        for raw in (
            _early_bound(sketch.RelationManager, "ISketchRelationManager").GetRelations(0)
            or ()
        )  # swAll
        if raw is not None
    )
    evidence = {
        "event": "tap_from_end_contract",
        "driven_state": int(dimension.DrivenState),
        "control_driven_state": int(control.DrivenState),
        "is_reference": bool(dimension.IsReference()),
        "equations": equations,
        "relations": relations,
        "constrained_status": int(sketch.GetConstrainedStatus()),
        "value_mm": abs(float(dimension.SystemValue)) * 1000.0,
    }
    _telemetry.info(json.dumps(evidence, sort_keys=True))
    problems = []
    if len(equations) != 1:
        problems.append(f"expected one TapFromEnd equation, found {equations}")
    if evidence["driven_state"] != _DIMENSION_DRIVEN:
        problems.append("TapFromEnd is not equation-owned (DrivenState != 1)")
    if evidence["driven_state"] != evidence["control_driven_state"]:
        problems.append("TapFromEnd's state differs from the BlockWidth control")
    if evidence["is_reference"]:
        problems.append("TapFromEnd became a reference dimension")
    if relations != _TAP_PLACEMENT_RELATIONS:
        problems.append(
            f"placement relations {relations} != {_TAP_PLACEMENT_RELATIONS}"
        )
    if evidence["constrained_status"] != _SW_FULLY_CONSTRAINED:
        problems.append("placement sketch is not fully defined")
    if abs(evidence["value_mm"] - SUPPORT_Z_THICK / 2.0) > 1e-5:
        problems.append(f"TapFromEnd reads {evidence['value_mm']:.6f} mm")
    if problems:
        raise RuntimeError(
            "hanger-stud tap: tap-from-end contract failed: "
            + "; ".join(problems)
            + f" -- {json.dumps(evidence, sort_keys=True)}"
        )
    _assert_tap_station(adapter, sketch)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the bore radius + its top clearance,
    # the block half-width / wall / axial thickness, and the local block top. The
    # derived globals (BoreCy / BlkBot) are equations of the primitives so the
    # bore centre and block bottom track when a primitive changes. The mm suffix
    # is load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 12.7 = 12.7 in, 25.4x too big).
    await set_global(adapter, "RBore", f"{R_BORE}mm")
    await set_global(adapter, "TopClear", f"{TOP_CLEAR}mm")
    await set_global(adapter, "SupportZThick", f"{SUPPORT_Z_THICK}mm")
    await set_global(adapter, "BlkHalfX", f"{BLK_HALF_X}mm")
    await set_global(adapter, "Wall", f"{WALL}mm")
    await set_global(adapter, "BlkTop", f"{BLK_TOP}mm")
    await set_global(adapter, "BoreCy", '"TopClear" - "RBore"')
    await set_global(adapter, "BlkBot", '"BoreCy" - "RBore" - "Wall"')

    # Each sketch records its dim names + drive equations as the define_* helper
    # emits them; the equations are collected here and applied in one deferred
    # batch at the end (every target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Bearing block and knife bore: one actual Front-plane profile with an
    # outer rectangle and inner circle, extruded symmetrically about the tap's
    # axial centre plane. BoreFromSide and BoreFromTop directly drive the real
    # bore centre relative to the real block profile; there are no detached
    # manufacturing-dimension replicas.
    block_dims = SketchDims()
    check("create_sketch block and bore", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLK_HALF_X, BLK_BOT),
        (BLK_HALF_X, BLK_BOT),
        (BLK_HALF_X, BLK_TOP),
        (-BLK_HALF_X, BLK_TOP),
    ]
    block = await add_line_chain(adapter, block_rect)
    await define_rectilinear_chain(
        adapter,
        block,
        block_rect,
        label="block",
        dims=block_dims,
        names=["BlockWidth", "BlockHeight", "BoreFromSide", "BlockAnchorZ"],
        drives=[
            '2 * "BlkHalfX"',
            '"BlkTop" - "BlkBot"',
            '"BlkHalfX"',
            '-"BlkBot"',
        ],
    )
    set_sketch_direct_db(adapter, True)
    try:
        bore_result = await adapter.add_circle(0.0, BORE_CY, R_BORE)
    finally:
        set_sketch_direct_db(adapter, False)
    bore = check("add actual knife-bore circle", bore_result)
    check(
        "align knife-bore and hanger-tap centreline",
        await adapter.add_sketch_constraint(
            f"{bore}.center", "origin", "vertical_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{block[2]}.start",
        f"{bore}.center",
        "vertical_distance",
        BORE_FROM_TOP,
        "actual bore from top seat",
    )
    block_dims.record("BoreFromTop", '"BlkTop" - "BoreCy"')
    check(
        "dimension actual knife-bore diameter",
        await adapter.add_sketch_dimension(
            bore, None, "diameter", 2.0 * R_BORE
        ),
    )
    block_dims.record("BoreDia", '2 * "RBore"')
    await ensure_fully_defined(adapter, "block and bore profile")
    check("exit_sketch block and bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block_dims.apply(adapter, "BlockProfile")
    check(
        "extrude block with knife bore",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SUPPORT_Z_THICK, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Block")
    depth_dim = name_dimensions(adapter, "Block", ["Depth"])
    drive_jobs += [(depth_dim[0], '"SupportZThick"')]
    expected = (
        2.0 * BLK_HALF_X * (BLK_TOP - BLK_BOT)
        - math.pi * R_BORE**2
    ) * SUPPORT_Z_THICK
    vol = await _volume(adapter)
    _telemetry.info(f"volume after block and bore: {vol:.1f} mm^3")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"block-and-bore volume {vol:.1f} != {expected:.1f}")

    # The bore crown and lever ridge share the named knife axis: actual contact,
    # not the former 0.25-mm modeled gap.
    hex_top = 0.0
    contact_error = (BORE_CY + R_BORE) - hex_top
    if abs(contact_error) > 1e-9:
        raise RuntimeError(f"knife contact error is {contact_error:.6f} mm")
    # Every noncontact vertex must remain inside the minimum finished bore for
    # the complete observed rock range, with both trunnion sizes at maximum
    # material.  The former static 0.5-mm shoulder threshold had no mechanical
    # basis and rejected the valid nominal contact geometry.
    rock_clearance = _minimum_hex_rock_clearance_mm()
    if rock_clearance <= 0.0:
        raise RuntimeError(
            "hex trunnion interferes with the knife bore over "
            f"+/-{REQUIRED_ROCK_SWEEP_DEG:g} degrees: "
            f"{rock_clearance:.6f} mm clearance at limits"
        )
    _telemetry.info(
        "knife trunnion clearance at size and motion limits: "
        f"{rock_clearance:.6f} mm"
    )

    # Hanger-stud tap: native #10-24 blind bottoming tap on the trunnion-axis
    # centreline.  HoleWizard5 reads depth as the cylindrical drill shoulder;
    # its ordinary 118-degree point ends above the functional bore crown.
    tap_runout = STUD_TAP_DRILL_DEPTH_MM - STUD_TAP_THREAD_DEPTH_MM
    two_pitches = 2.0 * STUD_TAP_PITCH_MM
    if tap_runout < two_pitches or STUD_TAP_WORST_CASE_RUNOUT_MM < two_pitches:
        raise RuntimeError(
            "stud tap has insufficient bottoming-tap lead: "
            f"{tap_runout:.4f} mm nominal, "
            f"{STUD_TAP_WORST_CASE_RUNOUT_MM:.4f} mm at limits"
        )
    tap_crown_web = (
        BLK_TOP
        - (BORE_CY + R_BORE)
        - STUD_TAP_DRILL_DEPTH_MM
        - STUD_TAP_POINT_HEIGHT_MM
    )
    if abs(tap_crown_web - STUD_TAP_CROWN_WEB_MM) > 1e-9:
        raise RuntimeError(
            "stud tap crown-web contract drifted: "
            f"model {tap_crown_web:.4f} mm, spec {STUD_TAP_CROWN_WEB_MM:.4f} mm"
        )
    if (
        tap_crown_web < 0.5
        or STUD_TAP_WORST_CASE_CROWN_WEB_MM < 0.5
    ):
        raise RuntimeError(
            "stud tap crown web is insufficient: "
            f"{tap_crown_web:.4f} mm nominal, "
            f"{STUD_TAP_WORST_CASE_CROWN_WEB_MM:.4f} mm at limits"
        )
    wizard_holes(
        adapter,
        STUD_TAP_SPEC,
        [[0.0, BLK_TOP, 0.0]],
        (0.0, 1.0, 0.0),
        f"hanger-stud tapped hole ({STUD_TAP_SPEC.size})",
        name="StudTap",
        # No placement_dims: _holes' zero-coordinate relation would pin the
        # tap coincident to the sketch origin (the tap IS that station -- the
        # block extrudes symmetrically about it), leaving no free coordinate
        # for the driving 9.00 the sheet must print. _dimension_tap_from_end
        # authors it right below, from the block's near end face.
        # no expect_dia_mm: a BLIND hole's definition reads 0.0 for both
        # diameter knobs on this seat (the tripwire is through-hole only);
        # the pinned dia is what HoleWizard5 was handed, and the volume
        # gate below proves the cut.
    )
    drive_jobs.append(await _dimension_tap_from_end(adapter))
    _tolerance_hole_depth(
        adapter,
        "StudTap",
        "tapdrilldepth",
        STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM,
    )
    _tolerance_hole_depth(
        adapter,
        "StudTap",
        "fullthreaddepth",
        STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM,
    )
    expected -= blind_hole_volume_mm3(STUD_TAP_DIA, STUD_TAP_DRILL_DEPTH_MM)
    vol = await _volume(adapter)
    _telemetry.info(f"volume after stud tap: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"stud tap volume {vol:.1f} != {expected:.1f}")

    # Named axis = the knife-edge contact ridge line (part origin, along Z). The
    # assembly mates Axis3@summing-lever (the hex ridge) coincident to it.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "knife axis")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: each equation evaluates to the value just built, so
    # the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven knife mount (equations neutral)", expected, 0.01 * expected
    )
    _assert_tap_from_end_contract(adapter)


    await apply_material(adapter, MATERIAL)
    # ch18 p.42: heat-treated and left unpainted -- a dark grey, not the
    # database steel's bright render nor the frame's green.
    await apply_color(adapter, HARDENED_STEEL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    set_dimension_symmetric_tolerance(
        adapter,
        "BlockProfile",
        "BoreDia",
        BORE_DIAMETER_TOLERANCE_MM,
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "BlockProfile",
        "BoreFromTop",
        BORE_FROM_TOP_TOLERANCE_MM,
    )
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
