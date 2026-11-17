"""Assembly component mixin for PyWin32 SolidWorks operations (Phase 7A).

Implements component management on the active assembly document: insertion
(``IAssemblyDoc::AddComponent5`` after an ``ISldWorks::OpenDoc6`` preload,
followed by an exact transform — the ``AddComponent5`` coordinates are
bounding-box relative and only approximate), removal, replacement
(``IAssemblyDoc::ReplaceComponents2``), precise move/rotate
(``IComponent2::SetTransformAndSolve3`` with a client-side composed
transform matrix), fix/float (``IAssemblyDoc::FixComponent`` /
``UnfixComponent``) and local component patterns
(``IFeatureManager::FeatureLinearPattern5`` / ``FeatureCircularPattern5``
— in assemblies these take components under mark 1 and the
direction/axis reference under mark 2, the marks swapped versus part
feature patterns).

Transform convention (``IMathTransform::ArrayData``, 16 doubles): elements
0-8 are a 3x3 rotational sub-matrix whose *rows* are the images of the
component's x/y/z axes in assembly space (i.e. the transpose of the
column-vector rotation matrix), elements 9-11 the translation in metres,
element 12 the scale, 13-15 unused.
"""

from __future__ import annotations

import math
import os
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

from .. import sw_type_info
from ..base import (
    AdapterResult,
    AdapterResultStatus,
    AddMateParameters,
    BeltChainParameters,
    ComponentChainPatternParameters,
    ComponentCircularPatternParameters,
    ComponentLinearPatternParameters,
    ComponentRefParameters,
    InsertComponentParameters,
    MateRefParameters,
    MoveComponentParameters,
    ReplaceComponentParameters,
    RotateComponentParameters,
    SetComponentConfigurationParameters,
    SetComponentSolvingParameters,
    SolidWorksFeature,
    SuppressMateParameters,
)
from ..com_variant import (
    bool_array,
    bstr_array,
    dispatch_array,
    double_array,
    null_callout,
    null_variant,
)
from .features import (
    _flag_feature_methods,
    _read_member,
    _resolve_feature,
    _select_named_feature,
    _select_reference_point,
    _tree_snapshot,
)

try:
    import pythoncom
    import win32com.client
except ImportError:  # pragma: no cover
    pythoncom = SimpleNamespace()
    win32com = SimpleNamespace(client=SimpleNamespace())

# swReplaceComponentsConfiguration_e
_REPLACE_CONFIG_MATCH_NAME = 0
_REPLACE_CONFIG_MANUALLY_SELECT = 1

_MODEL_EXTENSION_DOC_TYPES = {".sldprt": 1, ".sldasm": 2}  # swDocumentTypes_e

# swMateType_e — the standard (Phase 7B) and mechanical (Phase 7C) subsets
_MATE_TYPES = {
    "coincident": 0,
    "concentric": 1,
    "perpendicular": 2,
    "parallel": 3,
    "tangent": 4,
    "distance": 5,
    "angle": 6,
    "cam_follower": 9,
    "gear": 10,
    "width": 11,
    "rack_pinion": 13,
    "lock": 16,
    "screw": 17,
}

# swMateAlign_e
_MATE_ALIGNMENTS = {"aligned": 0, "anti_aligned": 1, "closest": 2}

# CreateMate mate-data interface per mate kind (cast target for late binding).
# Every mate is built via CreateMateData -> set the typed data object's
# properties -> CreateMate, superseding the obsolete AddMate5 primitive.
_MATE_DATA_INTERFACE = {
    "coincident": "ICoincidentMateFeatureData",
    "concentric": "IConcentricMateFeatureData",
    "perpendicular": "IPerpendicularMateFeatureData",
    "parallel": "IParallelMateFeatureData",
    "tangent": "ITangentMateFeatureData",
    "distance": "IDistanceMateFeatureData",
    "angle": "IAngleMateFeatureData",
    "cam_follower": "ICamFollowerMateFeatureData",
    "gear": "IGearMateFeatureData",
    "width": "IWidthMateFeatureData",
    "rack_pinion": "IRackPinionMateFeatureData",
    "lock": "ILockMateFeatureData",
    "screw": "IScrewMateFeatureData",
}

# Mate kinds whose typed data object exposes a MateAlignment property. The
# others (perpendicular/gear/lock/width) have no alignment knob.
_MATE_TYPES_WITH_ALIGNMENT = frozenset(
    {"coincident", "concentric", "parallel", "tangent",
     "distance", "angle", "cam_follower", "screw"}
)

# swMateWidthConstraintType_e — centered tab between the two width faces.
_WIDTH_CENTERED = 1

# AddMate5 selection marks: width tab faces 16, cam-follower 8, others 1
_MATE_DEFAULT_MARKS = {"width": 16, "cam_follower": 8}
# Rack-pinion mates need DIFFERENT marks per entity (a single default mark on
# both makes CreateMate reject the selection): rack=64, pinion=128, in that
# entity order (SOLIDWORKS *Create Rack and Pinion Mate* API example).
_RACK_PINION_MARKS = (64, 128)

# swRackPinionMateDistanceOptions_e
_RACK_PINION_PITCH_DIAMETER = 0
_RACK_PINION_TRAVEL_PER_REVOLUTION = 1

# swScrewMateDistanceOptions_e
_SCREW_DISTANCE_PER_REVOLUTION = 1

# swAddMateError_e
_MATE_ERRORS = {
    0: "unknown error",
    1: "no error",
    2: "unknown mate type",
    3: "unknown mate alignment",
    4: "incorrect selections for mate",
    5: "mate over-defines the assembly",
    6: "invalid gear ratios",
}

# swFeatureSuppressionAction_e / swInConfigurationOpts_e
_SUPPRESS_FEATURE = 0
_UNSUPPRESS_FEATURE = 1
_ALL_CONFIGURATIONS = 2
_SPECIFY_CONFIGURATION = 3

# IAssemblyDoc::CompConfigProperties5 — solve mode arguments.
# inComponentResolveStatus: swComponentResolveStatus_e (2 = fully resolved).
# inSolveMode: swComponentSolvingOption_e (0 = rigid, 1 = flexible).
_COMP_FULLY_RESOLVED = 2
_COMP_SOLVING = {"rigid": 0, "flexible": 1}
# IComponent2::Solving readback (swComponentSolvingOption_e).
_COMP_SOLVING_NAME = {0: "rigid", 1: "flexible"}
# swSolidBodies for IPartDoc::GetBodies2.
_SW_SOLID_BODY = 0


class SolidWorksAssemblyMixin:
    """Expose SolidWorks assembly component methods via mixin-local helpers."""

    async def insert_component(
        self, params: InsertComponentParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _insert_component_impl(self, params)

    async def remove_component(
        self, params: ComponentRefParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _remove_component_impl(self, params)

    async def replace_component(
        self, params: ReplaceComponentParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _replace_component_impl(self, params)

    async def move_component(
        self, params: MoveComponentParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _move_component_impl(self, params)

    async def rotate_component(
        self, params: RotateComponentParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _rotate_component_impl(self, params)

    async def fix_component(
        self, params: ComponentRefParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _set_component_fixed_impl(self, params, fixed=True)

    async def float_component(
        self, params: ComponentRefParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _set_component_fixed_impl(self, params, fixed=False)

    async def pattern_components_linear(
        self, params: ComponentLinearPatternParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _pattern_components_linear_impl(self, params)

    async def pattern_components_circular(
        self, params: ComponentCircularPatternParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _pattern_components_circular_impl(self, params)

    async def pattern_components_chain(
        self, params: ComponentChainPatternParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _pattern_components_chain_impl(self, params)

    async def insert_belt_chain(
        self, params: BeltChainParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _insert_belt_chain_impl(self, params)

    async def add_mate(
        self, params: AddMateParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _add_mate_impl(self, params)

    async def list_mates(self) -> AdapterResult[list[dict[str, Any]]]:
        return _list_mates_impl(self)

    async def delete_mate(
        self, params: MateRefParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _delete_mate_impl(self, params)

    async def suppress_mate(
        self, params: SuppressMateParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _suppress_mate_impl(self, params)

    async def set_component_solving(
        self, params: SetComponentSolvingParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _set_component_solving_impl(self, params)

    async def set_component_configuration(
        self, params: SetComponentConfigurationParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _set_component_configuration_impl(self, params)


# ---------------------------------------------------------------------------
# Pure matrix helpers (column-vector convention: v' = R @ v)
# ---------------------------------------------------------------------------


def _mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """Multiply two 3x3 matrices (``a @ b``)."""
    return [
        [sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)
    ]


def _mat_vec(m: list[list[float]], v: list[float]) -> list[float]:
    """Apply a 3x3 matrix to a column vector (``m @ v``)."""
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def _unit_vector(v: list[float]) -> list[float]:
    """Normalize a 3-vector (raises on a zero vector)."""
    norm = math.sqrt(sum(float(c) ** 2 for c in v))
    if norm < 1e-12:
        raise Exception("Axis vector must be non-zero")
    return [float(c) / norm for c in v]


def _orientation_sign(a: list[float], b: list[float]) -> float:
    """+-1 depending on whether two axis directions point the same way.

    A non-negative dot product (including the near-perpendicular bevel
    case) keeps the sign; only a clearly opposed direction flips it.
    """
    return -1.0 if sum(x * y for x, y in zip(a, b, strict=True)) < 0.0 else 1.0


def _euler_xyz_matrix(rotation_deg: list[float]) -> list[list[float]]:
    """Rotation matrix for X-then-Y-then-Z extrinsic Euler angles in degrees.

    Column-vector convention: ``R = Rz @ Ry @ Rx`` maps component-space
    vectors to assembly space, applying the X rotation first.

    Args:
        rotation_deg: ``[rx, ry, rz]`` in degrees.

    Returns:
        list[list[float]]: 3x3 rotation matrix.
    """
    rx, ry, rz = (math.radians(float(a)) for a in rotation_deg)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mat_x = [[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]]
    mat_y = [[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]]
    mat_z = [[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]]
    return _mat_mul(mat_z, _mat_mul(mat_y, mat_x))


def _axis_angle_matrix(axis: list[float], angle_deg: float) -> list[list[float]]:
    """Rodrigues rotation matrix about an axis (column-vector convention).

    Args:
        axis: Rotation axis direction (any length, normalized here).
        angle_deg: Rotation angle in degrees (right-hand rule).

    Returns:
        list[list[float]]: 3x3 rotation matrix.

    Raises:
        Exception: When the axis vector is (near) zero length.
    """
    norm = math.sqrt(sum(float(c) ** 2 for c in axis))
    if norm < 1e-12:
        raise Exception("axis_vector must be non-zero")
    ux, uy, uz = (float(c) / norm for c in axis)
    theta = math.radians(float(angle_deg))
    c, s = math.cos(theta), math.sin(theta)
    t = 1.0 - c
    return [
        [c + ux * ux * t, ux * uy * t - uz * s, ux * uz * t + uy * s],
        [uy * ux * t + uz * s, c + uy * uy * t, uy * uz * t - ux * s],
        [uz * ux * t - uy * s, uz * uy * t + ux * s, c + uz * uz * t],
    ]


def _transform_array(
    rotation: list[list[float]], translation_m: list[float]
) -> list[float]:
    """Build the 16-element ``ArrayData`` for a rotation plus translation.

    The SolidWorks rotational sub-matrix rows are the images of the
    component axes — the transpose of the column-vector ``rotation``.

    Args:
        rotation: 3x3 column-vector rotation matrix (component → assembly).
        translation_m: ``[x, y, z]`` translation in metres.

    Returns:
        list[float]: 16-element transform array (scale 1).
    """
    return [
        rotation[0][0],
        rotation[1][0],
        rotation[2][0],
        rotation[0][1],
        rotation[1][1],
        rotation[2][1],
        rotation[0][2],
        rotation[1][2],
        rotation[2][2],
        translation_m[0],
        translation_m[1],
        translation_m[2],
        1.0,
        0.0,
        0.0,
        0.0,
    ]


# ---------------------------------------------------------------------------
# COM helpers
# ---------------------------------------------------------------------------


def _assembly_title(adapter: Any) -> str:
    """Read the active document's title without its file extension.

    ``SelectByID2`` component names are qualified as ``name@title``, where
    the title omits the ``.SLDASM`` extension for saved documents.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.

    Returns:
        str: Document title, extension stripped.
    """
    model = adapter.currentModel
    title = adapter._attempt(lambda: model.GetTitle(), default=None)
    if not isinstance(title, str) or not title:
        title = str(getattr(model, "Title", "") or "")
    root, ext = os.path.splitext(title)
    if ext.lower() in (".sldasm", ".sldprt"):
        return root
    return title


def _qualify_component(adapter: Any, name: str) -> str:
    """Append the ``@assembly`` qualifier to a component name when missing."""
    if "@" in name:
        return name
    return f"{name}@{_assembly_title(adapter)}"


def _select_component(adapter: Any, name: str, mark: int, append: bool) -> bool:
    """Select an assembly component by name via ``SelectByID2``.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        name: Component name, qualified automatically when needed.
        mark: Selection mark.
        append: ``True`` to add to the current selection set.

    Returns:
        bool: ``True`` when the component selected.
    """
    qualified = _qualify_component(adapter, name)
    return bool(
        adapter._attempt(
            lambda: adapter.currentModel.Extension.SelectByID2(
                qualified, "COMPONENT", 0.0, 0.0, 0.0, append, mark, null_callout(), 0
            ),
            default=False,
        )
    )


def _get_component(adapter: Any, name: str) -> Any:
    """Resolve an ``IComponent2`` via ``IAssemblyDoc::GetComponentByName``.

    ``GetComponentByName`` resolves only top-level instances on some SolidWorks
    versions (a nested ``"sub-1/part-1"`` path returns ``None``); the fallback
    scans ``GetComponents(False)`` (all components, including those nested in
    subassemblies) and matches on ``Name2``.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        name: Component name; any ``@assembly`` qualifier is stripped.

    Returns:
        Any: The component dispatch (flagged for ``IComponent2``) or ``None``.
    """
    bare = name.split("@", 1)[0]
    model = adapter.currentModel
    model = _flag_feature_methods(model, "IAssemblyDoc")
    component = adapter._attempt(lambda: model.GetComponentByName(bare), default=None)
    if component is None:
        component = _find_component_by_name2(adapter, bare)
    if component:
        component = _flag_feature_methods(component, "IComponent2")
    return component


def _find_component_by_name2(adapter: Any, name2: str) -> Any:
    """Find a component (including nested) by its full ``Name2`` path.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        name2: Full component path, e.g. ``"drive-train-1/crankshaft-1"``.

    Returns:
        Any: The matching ``IComponent2`` dispatch, or ``None``.
    """
    components = adapter._attempt(
        lambda: _flag_feature_methods(
            adapter.currentModel, "IAssemblyDoc"
        ).GetComponents(False),
        default=None,
    )
    for component in components or []:
        if str(_read_member(component, "Name2")) == name2:
            return component
    return None


def _component_name(adapter: Any, component: Any, fallback: str) -> str:
    """Read a component's path name (``Name2``), with a caller fallback."""
    name = _read_member(component, "Name2")
    if isinstance(name, str) and name:
        return name
    return fallback.split("@", 1)[0]


def _component_transform_array(adapter: Any, component: Any) -> list[float]:
    """Read a component's current 16-element transform array.

    Args:
        adapter: Connected adapter.
        component: ``IComponent2`` dispatch.

    Returns:
        list[float]: ``IMathTransform::ArrayData`` of ``Transform2``.

    Raises:
        Exception: When the transform cannot be read.
    """
    xform = _read_member(component, "Transform2")
    if xform is None:
        raise Exception("Failed to read the component transform")
    array = _read_member(xform, "ArrayData")
    if array is None:
        raise Exception("Failed to read the component transform array")
    values = [float(v) for v in array]
    if len(values) != 16:
        raise Exception(f"Unexpected transform array length: {len(values)}")
    return values


def _create_math_transform(adapter: Any, array16: list[float]) -> Any:
    """Create an ``IMathTransform`` from a 16-element array.

    Args:
        adapter: Connected adapter (for ``ISldWorks::GetMathUtility``).
        array16: Transform array per :func:`_transform_array`.

    Returns:
        Any: The math transform dispatch.

    Raises:
        Exception: When the math utility or transform cannot be created.
    """
    utility = adapter._attempt(lambda: adapter.swApp.GetMathUtility(), default=None)
    if utility is None:
        raise Exception("Failed to get the SolidWorks math utility")
    utility = _flag_feature_methods(utility, "IMathUtility")
    # The array MUST be a typed VT_ARRAY|VT_R8 VARIANT: a plain list marshals
    # as VT_ARRAY|VT_VARIANT, which CreateTransform silently ignores and
    # returns an identity transform instead of an error.
    xform = adapter._attempt(
        lambda: utility.CreateTransform(double_array(array16)), default=None
    )
    if xform is None:
        raise Exception("Failed to create the math transform")
    return xform


def _apply_component_transform(
    adapter: Any, component: Any, name: str, array16: list[float]
) -> list[float]:
    """Set a component's transform, solving mates, preserving fixed state.

    ``SetTransformAndSolve3`` refuses to move a fixed component, so a fixed
    one is floated for the move and re-fixed at the new position (the
    first component inserted into an assembly is auto-fixed).

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        component: ``IComponent2`` dispatch.
        name: Component name (for the fix/float selection).
        array16: Target transform array.

    Returns:
        list[float]: The component's transform array read back AFTER the
        solve — the mate solver may legitimately adjust the requested
        position, and reporting the target instead of the outcome is how the
        silent ``CreateTransform`` identity bug went unnoticed.

    Raises:
        Exception: When the transform cannot be applied.
    """
    model_doc = adapter.currentModel  # IModelDoc2 — for EditRebuild3
    model = _flag_feature_methods(model_doc, "IAssemblyDoc")  # Fix/UnfixComponent
    was_fixed = bool(_read_member(component, "IsFixed"))
    if was_fixed:
        if not _select_component(adapter, name, 0, False):
            raise Exception(f"Failed to select component to float: {name!r}")
        adapter._attempt(lambda: model.UnfixComponent())

    xform = _create_math_transform(adapter, array16)
    applied = adapter._attempt(
        lambda: component.SetTransformAndSolve3(xform, True), default=None
    )
    if not applied:
        applied = adapter._attempt(
            lambda: component.SetTransformAndSolve2(xform), default=None
        )

    if was_fixed and _select_component(adapter, name, 0, False):
        adapter._attempt(lambda: model.FixComponent())

    if not applied:
        raise Exception(f"Failed to set the transform of component {name!r}")
    adapter._attempt(lambda: model_doc.EditRebuild3())
    return _component_transform_array(adapter, component)


# swMateType_e value identifying gear mates when walking the mate graph.
_MATE_TYPE_GEAR = 10


def _rotate_component_exact(
    adapter: Any,
    component: Any,
    name: str,
    angle_deg: float,
    axis_vector: list[float],
    axis_point_mm: list[float],
) -> list[float]:
    """Rotate a component about an assembly-space axis via an exact transform.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        component: ``IComponent2`` dispatch.
        name: Component name (for the fix/float selection).
        angle_deg: Rotation angle in degrees (right-hand rule).
        axis_vector: Rotation-axis direction in assembly space.
        axis_point_mm: A point the axis passes through, in millimetres.

    Returns:
        list[float]: The transform array read back after the move.
    """
    rotation = _axis_angle_matrix(axis_vector, angle_deg)
    array = _component_transform_array(adapter, component)
    rows = [array[0:3], array[3:6], array[6:9]]
    new_rows = [_mat_vec(rotation, row) for row in rows]
    center_m = [float(c) / 1000.0 for c in axis_point_mm]
    offset = [array[9 + i] - center_m[i] for i in range(3)]
    rotated_offset = _mat_vec(rotation, offset)
    translation = [rotated_offset[i] + center_m[i] for i in range(3)]

    new_array = (
        new_rows[0]
        + new_rows[1]
        + new_rows[2]
        + translation
        + [array[12]]
        + [0.0, 0.0, 0.0]
    )
    return _apply_component_transform(adapter, component, name, new_array)


def _gear_mate_links(adapter: Any) -> list[dict[str, Any]]:
    """Read the assembly's unsuppressed gear mates as kinematic links.

    Each link carries the two component names, each side's rotation axis
    (``IMateEntity2::EntityParams`` — point + direction in assembly space,
    metres), the stored gear ratio and the ``Reverse`` flag.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.

    Returns:
        list[dict[str, Any]]: One entry per readable gear mate.
    """
    links: list[dict[str, Any]] = []
    for feature in _mate_group_subfeatures(adapter):
        if adapter._attempt(lambda f=feature: f.IsSuppressed(), default=False):
            continue
        mate = _read_member(feature, "GetSpecificFeature2")
        if mate is None:
            continue
        if int(adapter._attempt(lambda m=mate: m.Type, default=-1)) != _MATE_TYPE_GEAR:
            continue
        definition = _read_member(feature, "GetDefinition")
        numerator = float(_read_member(definition, "GearRatioNumerator") or 0.0)
        denominator = float(_read_member(definition, "GearRatioDenominator") or 0.0)
        reverse = bool(_read_member(definition, "Reverse"))
        sides: list[dict[str, Any]] = []
        for index in range(2):
            entity = adapter._attempt(lambda m=mate, i=index: m.MateEntity(i))
            if entity is None:
                break
            owner = _read_member(entity, "ReferenceComponent")
            owner_name = str(_read_member(owner, "Name2") or "") if owner else ""
            entity_params = _read_member(entity, "EntityParams")
            if not owner_name or not entity_params or len(entity_params) < 6:
                break
            sides.append(
                {
                    "component": owner_name,
                    "axis_point_mm": [float(v) * 1000.0 for v in entity_params[0:3]],
                    "axis_vector": [float(v) for v in entity_params[3:6]],
                }
            )
        if len(sides) != 2 or numerator <= 0.0 or denominator <= 0.0:
            continue
        if any(sum(c * c for c in side["axis_vector"]) < 1e-18 for side in sides):
            continue
        links.append(
            {
                "name": str(_read_member(feature, "Name")),
                "sides": sides,
                "numerator": numerator,
                "denominator": denominator,
                "reverse": reverse,
            }
        )
    return links


def _kinematic_rotate_component(
    adapter: Any, component: Any, name: str, params: RotateComponentParameters
) -> tuple[list[float], list[dict[str, Any]]]:
    """Rotate a component and propagate the motion through gear mates.

    SolidWorks gear mates do not transmit programmatic motion: the mate
    solver re-anchors the gear phase after any ``SetTransformAndSolve3``,
    and ``IDragOperator`` honours gear mates only erratically (live-tested
    on SW 2026: coupling depends chaotically on drag step size). Driving a
    mated gear train deterministically therefore takes explicit kinematics:
    rotate the input exactly, then walk the gear-mate graph breadth-first
    and rotate every coupled component about its own mate axis by the
    stored inverse ratio (external gears counter-rotate in world space;
    ``Reverse`` flips the sign). SolidWorks accepts the new phases without
    mate errors.

    Sign convention: every swing is tracked about the component's own
    mate-entity axis (``EntityParams`` direction). The entity directions
    are modelling artefacts — two meshing gears may record opposite axis
    vectors — so the coupling multiplies in the sign of the dot product
    between the two sides' directions: parallel-axis pairs then always
    counter-rotate in world space (live demo verified +45 in -> -90 out),
    and near-perpendicular (bevel) pairs keep the raw factor sign, where
    ``Reverse`` is the knob if the mesh runs the other way.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        component: ``IComponent2`` dispatch of the input component.
        name: Input component name.
        params: Axis (point in mm, direction), angle (deg).

    Returns:
        tuple[list[float], list[dict[str, Any]]]: The input component's
        read-back transform array and the propagated rotations
        (``[{"component", "angle", "mate"}, ...]`` — each angle is about
        that component's own mate axis).
    """
    applied = _rotate_component_exact(
        adapter, component, name, params.angle, params.axis_vector, params.axis_point
    )

    links = _gear_mate_links(adapter)
    # Per component: (swing in degrees, unit world axis the swing is about).
    swings: dict[str, tuple[float, list[float]]] = {
        name: (float(params.angle), _unit_vector(params.axis_vector))
    }
    queue = [name]
    propagated: list[dict[str, Any]] = []
    while queue:
        current = queue.pop(0)
        current_swing, current_axis = swings[current]
        for link in links:
            owners = [side["component"] for side in link["sides"]]
            if current not in owners:
                continue
            this_index = owners.index(current)
            other_index = 1 - this_index
            other = owners[other_index]
            if other in swings:
                continue
            # Stored num:den relates side 0 to side 1: live-verified on SW
            # 2026, omega_1 = -omega_0 * den/num (Reverse flips the sign).
            if this_index == 0:
                factor = -link["denominator"] / link["numerator"]
            else:
                factor = -link["numerator"] / link["denominator"]
            if link["reverse"]:
                factor = -factor
            this_axis = _unit_vector(link["sides"][this_index]["axis_vector"])
            other_axis = _unit_vector(link["sides"][other_index]["axis_vector"])
            # current_axis and this_axis are the same physical line; the
            # dot only carries the +-1 orientation between them.
            own_swing = current_swing * _orientation_sign(current_axis, this_axis)
            swing = own_swing * factor * _orientation_sign(this_axis, other_axis)
            partner = _get_component(adapter, other)
            if partner is None:
                raise Exception(
                    f"Gear mate {link['name']!r} references unknown component {other!r}"
                )
            side = link["sides"][other_index]
            _rotate_component_exact(
                adapter,
                partner,
                other,
                swing,
                side["axis_vector"],
                side["axis_point_mm"],
            )
            swings[other] = (swing, other_axis)
            propagated.append(
                {"component": other, "angle": swing, "mate": link["name"]}
            )
            queue.append(other)
    return applied, propagated


def _preload_component_file(adapter: Any, resolved_path: str) -> None:
    """Load a model into memory so ``AddComponent5`` can reference it.

    ``AddComponent5`` requires the source file to already be loaded in
    memory (per the API remarks), but it does *not* require the file to be
    displayed. We load it **invisibly** by bracketing ``OpenDoc6`` with
    ``ISldWorks::DocumentVisible(False/True)``: this is the documented
    pattern (see ``ISldWorks::OpenDoc6`` Remarks → "Avoid large increases in
    memory usage caused when adding parts to assemblies" and
    ``ISldWorks::DocumentVisible``). Loading hidden skips the per-document
    SceneGraph display buffers (2-3 MB even for trivial parts, not shared
    between parts and assemblies) and, because the part never becomes the
    active displayed document, avoids the UI flash and the need to switch
    the assembly back to the foreground.

    The visibility flag is restored in a ``finally`` so an unrelated open
    later in the session is unaffected even if the load raises. A document
    opened invisibly cannot subsequently be shown via ``IModelDoc2::Visible``
    (per the ``DocumentVisible`` Remarks); that is acceptable here because
    the part is only ever referenced as an assembly component.

    Args:
        adapter: Connected adapter.
        resolved_path: Absolute path to the ``.sldprt``/``.sldasm`` file.

    Raises:
        Exception: On unsupported extension or load failure.
    """
    doc_type = _MODEL_EXTENSION_DOC_TYPES.get(
        os.path.splitext(resolved_path)[1].lower()
    )
    if doc_type is None:
        raise Exception(
            f"Unsupported component file type: {resolved_path} "
            "(expected .sldprt or .sldasm)"
        )
    app = adapter.swApp
    adapter._attempt(lambda: app.DocumentVisible(False, doc_type), default=None)
    try:
        # Early-bound OpenDoc6 invokes by DISPID: pass literal 0 for the two
        # [out] errors/warnings slots and read the model back from the result
        # tuple (retval, errors, warnings). Passing a byref VARIANT here is a
        # late-binding idiom that InvokeTypes rejects.
        result = adapter._attempt(
            lambda: app.OpenDoc6(resolved_path, doc_type, 1, "", 0, 0),
            default=None,
        )
        loaded = result[0] if isinstance(result, tuple) else result
    finally:
        adapter._attempt(lambda: app.DocumentVisible(True, doc_type), default=None)
    if not loaded:
        loaded = adapter._attempt(
            lambda: app.GetOpenDocumentByName(resolved_path), default=None
        )
    if not loaded:
        raise Exception(f"Failed to preload component file: {resolved_path}")


def _activate_assembly(adapter: Any) -> None:
    """Re-activate the assembly document (best effort).

    Now that the preload loads the component invisibly (see
    ``_preload_component_file``) the part never becomes the active displayed
    document, so this is a defensive safeguard rather than a correction: it
    keeps the assembly in the foreground for later view-dependent operations
    regardless of how the COM session left things.
    """
    title = adapter._attempt(lambda: adapter.currentModel.GetTitle(), default=None)
    if not title:
        return
    # Early-bound ActivateDoc3 takes a literal 0 for its trailing [out] errors
    # slot; the (model, errors) result tuple is discarded (best-effort activate).
    adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(title, False, 2, 0),
        default=None,
    )


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


def _insert_component_impl(
    adapter: Any, params: InsertComponentParameters
) -> AdapterResult[dict[str, Any]]:
    """Insert a component via ``IAssemblyDoc::AddComponent5``.

    The file is preloaded with ``OpenDoc6`` (an ``AddComponent5``
    requirement), inserted at the origin, then positioned exactly with a
    composed transform — the ``AddComponent5`` X/Y/Z are bounding-box
    relative and only approximate per the API remarks.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: File, position (mm), rotation (deg XYZ), configuration.

    Returns:
        AdapterResult[dict[str, Any]]: Inserted component name, referenced
        configuration and pose, or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.file_path.strip():
        return AdapterResult(
            status=AdapterResultStatus.ERROR, error="file_path is required"
        )
    if len(params.position) != 3 or len(params.rotation) != 3:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="position and rotation must each be [x, y, z]",
        )

    def _insert_operation() -> dict[str, Any]:
        resolved = os.path.abspath(params.file_path)
        if not os.path.isfile(resolved):
            raise Exception(f"Component file not found: {resolved}")
        _preload_component_file(adapter, resolved)

        model = adapter.currentModel
        model = _flag_feature_methods(model, "IAssemblyDoc")
        component = model.AddComponent5(
            resolved,
            0,  # swAddComponentConfigOptions_CurrentSelectedConfig
            "",  # NewConfigName (unused for this option)
            bool(params.configuration),  # UseConfigForPartReferences
            params.configuration or "",
            0.0,
            0.0,
            0.0,
        )
        if not component:
            raise Exception(
                f"AddComponent5 failed for {resolved} (the file must load "
                "cleanly and the configuration must exist)"
            )
        component = _flag_feature_methods(component, "IComponent2")
        name = _component_name(adapter, component, os.path.basename(resolved))

        rotation = _euler_xyz_matrix(params.rotation)
        translation_m = [float(c) / 1000.0 for c in params.position]
        applied = _apply_component_transform(
            adapter, component, name, _transform_array(rotation, translation_m)
        )
        _activate_assembly(adapter)

        return {
            "name": name,
            "file_path": resolved,
            "configuration": str(
                _read_member(component, "ReferencedConfiguration") or ""
            ),
            "position": [v * 1000.0 for v in applied[9:12]],
            "rotation": [float(c) for c in params.rotation],
            "fixed": bool(_read_member(component, "IsFixed")),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("insert_component", _insert_operation),
    )


def _remove_component_impl(
    adapter: Any, params: ComponentRefParameters
) -> AdapterResult[dict[str, Any]]:
    """Delete a component via selection plus ``DeleteSelection2``.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Component name.

    Returns:
        AdapterResult[dict[str, Any]]: Removal confirmation or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.name.strip():
        return AdapterResult(status=AdapterResultStatus.ERROR, error="name is required")

    def _remove_operation() -> dict[str, Any]:
        model = adapter.currentModel
        component = _get_component(adapter, params.name)
        if component is None:
            raise Exception(f"Component not found: {params.name!r}")
        name = _component_name(adapter, component, params.name)

        adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        if not _select_component(adapter, name, 0, False):
            raise Exception(f"Failed to select component: {name!r}")
        deleted = adapter._attempt(
            lambda: model.Extension.DeleteSelection2(0), default=False
        )
        if not deleted:
            adapter._attempt(lambda: model.EditDelete(), default=None)
        if _get_component(adapter, name) is not None:
            raise Exception(f"Component {name!r} is still present after delete")
        return {"name": name, "removed": True}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("remove_component", _remove_operation),
    )


def _replace_component_impl(
    adapter: Any, params: ReplaceComponentParameters
) -> AdapterResult[dict[str, Any]]:
    """Replace a component via ``IAssemblyDoc::ReplaceComponents2``.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Component, replacement file and options.

    Returns:
        AdapterResult[dict[str, Any]]: Replacement summary or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.name.strip():
        return AdapterResult(status=AdapterResultStatus.ERROR, error="name is required")
    if not params.file_path.strip():
        return AdapterResult(
            status=AdapterResultStatus.ERROR, error="file_path is required"
        )

    def _replace_operation() -> dict[str, Any]:
        resolved = os.path.abspath(params.file_path)
        if not os.path.isfile(resolved):
            raise Exception(f"Replacement file not found: {resolved}")
        model = adapter.currentModel
        component = _get_component(adapter, params.name)
        if component is None:
            raise Exception(f"Component not found: {params.name!r}")
        name = _component_name(adapter, component, params.name)

        adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        if not _select_component(adapter, name, 0, False):
            raise Exception(f"Failed to select component: {name!r}")
        model = _flag_feature_methods(model, "IAssemblyDoc")
        config_choice = (
            _REPLACE_CONFIG_MANUALLY_SELECT
            if params.configuration
            else _REPLACE_CONFIG_MATCH_NAME
        )
        replaced = model.ReplaceComponents2(
            resolved,
            params.configuration,
            bool(params.replace_all),
            config_choice,
            bool(params.reattach_mates),
        )
        if not replaced:
            raise Exception(
                f"ReplaceComponents2 failed for {name!r} -> {resolved} (the "
                "component must be top-level and the replacement file name "
                "must differ from the replaced one)"
            )
        return {
            "name": name,
            "file_path": resolved,
            "configuration": params.configuration,
            "replace_all": bool(params.replace_all),
            "reattach_mates": bool(params.reattach_mates),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("replace_component", _replace_operation),
    )


def _move_component_impl(
    adapter: Any, params: MoveComponentParameters
) -> AdapterResult[dict[str, Any]]:
    """Move a component, preserving its rotation.

    Reads the current transform, rewrites the translation (absolute target
    or relative delta) and applies it with the mate solver.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Component and target position in millimetres.

    Returns:
        AdapterResult[dict[str, Any]]: Resulting position or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.name.strip():
        return AdapterResult(status=AdapterResultStatus.ERROR, error="name is required")
    if len(params.position) != 3:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="position must be [x, y, z] in millimetres",
        )

    def _move_operation() -> dict[str, Any]:
        component = _get_component(adapter, params.name)
        if component is None:
            raise Exception(f"Component not found: {params.name!r}")
        name = _component_name(adapter, component, params.name)

        array = _component_transform_array(adapter, component)
        position_m = [float(c) / 1000.0 for c in params.position]
        if params.relative:
            array[9:12] = [array[9 + i] + position_m[i] for i in range(3)]
        else:
            array[9:12] = position_m
        applied = _apply_component_transform(adapter, component, name, array)
        return {
            "name": name,
            "position": [v * 1000.0 for v in applied[9:12]],
            "relative": bool(params.relative),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("move_component", _move_operation),
    )


def _rotate_component_impl(
    adapter: Any, params: RotateComponentParameters
) -> AdapterResult[dict[str, Any]]:
    """Rotate a component about an axis in assembly space.

    Composes the rotation onto the current transform client-side: the
    rotational rows (axis images) and the translation are both rotated
    about ``axis_point``, then the result is applied with the mate solver.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Component, axis (point in mm, direction) and angle (deg).

    Returns:
        AdapterResult[dict[str, Any]]: Rotation summary or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.name.strip():
        return AdapterResult(status=AdapterResultStatus.ERROR, error="name is required")
    if len(params.axis_vector) != 3 or len(params.axis_point) != 3:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="axis_vector and axis_point must each be [x, y, z]",
        )
    if params.mode not in ("exact", "kinematic"):
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown rotate mode {params.mode!r}. Use 'exact' or 'kinematic'.",
        )

    def _rotate_operation() -> dict[str, Any]:
        component = _get_component(adapter, params.name)
        if component is None:
            raise Exception(f"Component not found: {params.name!r}")
        name = _component_name(adapter, component, params.name)

        propagated: list[dict[str, Any]] = []
        if params.mode == "kinematic":
            applied, propagated = _kinematic_rotate_component(
                adapter, component, name, params
            )
        else:
            applied = _rotate_component_exact(
                adapter,
                component,
                name,
                params.angle,
                params.axis_vector,
                params.axis_point,
            )
        return {
            "name": name,
            "angle": float(params.angle),
            "axis_vector": [float(c) for c in params.axis_vector],
            "axis_point": [float(c) for c in params.axis_point],
            "mode": params.mode,
            "position": [v * 1000.0 for v in applied[9:12]],
            "propagated": propagated,
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("rotate_component", _rotate_operation),
    )


def _set_component_fixed_impl(
    adapter: Any, params: ComponentRefParameters, fixed: bool
) -> AdapterResult[dict[str, Any]]:
    """Fix or float a component via ``FixComponent``/``UnfixComponent``.

    Both APIs act on the current selection and return nothing, so the
    resulting state is verified by reading ``IComponent2::IsFixed`` back.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Component name.
        fixed: ``True`` to fix, ``False`` to float.

    Returns:
        AdapterResult[dict[str, Any]]: Resulting fixed state or error.
    """
    operation = "fix_component" if fixed else "float_component"
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.name.strip():
        return AdapterResult(status=AdapterResultStatus.ERROR, error="name is required")

    def _fixed_operation() -> dict[str, Any]:
        model = adapter.currentModel
        component = _get_component(adapter, params.name)
        if component is None:
            raise Exception(f"Component not found: {params.name!r}")
        name = _component_name(adapter, component, params.name)

        adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        if not _select_component(adapter, name, 0, False):
            raise Exception(f"Failed to select component: {name!r}")
        model = _flag_feature_methods(model, "IAssemblyDoc")
        if fixed:
            adapter._attempt(lambda: model.FixComponent(), default=None)
        else:
            adapter._attempt(lambda: model.UnfixComponent(), default=None)

        resulting = bool(_read_member(component, "IsFixed"))
        if resulting != fixed:
            state = "fixed" if fixed else "floating"
            raise Exception(f"Component {name!r} did not become {state}")
        return {"name": name, "fixed": resulting}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation(operation, _fixed_operation),
    )


def _select_pattern_components(adapter: Any, components: list[str]) -> None:
    """Select pattern seed components under mark 1 (cleared selection).

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        components: Component names.

    Raises:
        Exception: When any component fails to select.
    """
    adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True), default=None)
    for name in components:
        if not _select_component(adapter, name, 1, True):
            raise Exception(f"Failed to select component to pattern: {name!r}")


def _pattern_components_linear_impl(
    adapter: Any, params: ComponentLinearPatternParameters
) -> AdapterResult[SolidWorksFeature]:
    """Local linear component pattern via ``FeatureLinearPattern5``.

    In assemblies the selection marks are swapped versus part feature
    patterns: components under mark 1, the direction reference under
    mark 2.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Seeds, count, spacing and direction reference.

    Returns:
        AdapterResult[SolidWorksFeature]: ``data.type == "LocalLinearPattern"``
        on success.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.components:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="Component pattern requires at least one component",
        )
    if params.count < 1:
        return AdapterResult(
            status=AdapterResultStatus.ERROR, error="count must be >= 1"
        )
    if not params.direction_name and not params.direction_point:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="Component pattern requires direction_name or direction_point",
        )

    def _linear_operation() -> SolidWorksFeature:
        _select_pattern_components(adapter, params.components)
        if params.direction_name:
            if not _select_named_feature(adapter, params.direction_name, 2, True):
                raise Exception(
                    f"Failed to select direction by name: {params.direction_name!r}"
                )
            direction_type = "FEATURE"
        else:
            direction_type = _select_reference_point(
                adapter, params.direction_point, 2, ("EDGE", "AXIS", "FACE")
            )
            if direction_type is None:
                raise Exception(
                    f"Failed to select direction at point {params.direction_point} "
                    "(mm); point at a linear edge or axis"
                )

        feature_manager = adapter.currentModel.FeatureManager
        feature_manager = _flag_feature_methods(feature_manager, "IFeatureManager")
        before = _tree_snapshot(adapter)
        feature = feature_manager.FeatureLinearPattern5(
            int(params.count),  # Num1 (incl. seed)
            float(params.spacing) / 1000.0,  # Spacing1 (metres)
            1,  # Num2 (direction 2 unused)
            0.0,  # Spacing2
            bool(params.flip_direction),  # FlipDir1
            False,  # FlipDir2
            "",  # DName1
            "",  # DName2
            False,  # GeometryPattern
            False,  # VaryInstance
            False,  # HasOffset1
            False,  # HasOffset2
            True,  # CtrlByNum1
            True,  # CtrlByNum2
            False,  # FromCentroid1
            False,  # FromCentroid2
            False,  # RevOffset1
            False,  # RevOffset2
            0.0,  # Offset1
            0.0,  # Offset2
            False,  # D2PatternSeedOnly
            False,  # SyncSubAssemblies
        )
        feature = _resolve_feature(
            adapter, feature, before, frozenset({"LocalLPattern"})
        )
        if not feature:
            raise Exception("Failed to create linear component pattern")

        return SolidWorksFeature(
            name=str(_read_member(feature, "Name")),
            type="LocalLinearPattern",
            id=adapter._get_feature_id(feature),
            parameters={
                "components": params.components,
                "count": int(params.count),
                "spacing": float(params.spacing),
                "direction_name": params.direction_name,
                "direction_point": params.direction_point,
                "direction_entity": direction_type,
            },
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("pattern_components_linear", _linear_operation),
    )


def _pattern_components_circular_impl(
    adapter: Any, params: ComponentCircularPatternParameters
) -> AdapterResult[SolidWorksFeature]:
    """Local circular component pattern via ``FeatureCircularPattern5``.

    In assemblies the selection marks are swapped versus part feature
    patterns: components under mark 1, the axis reference under mark 2.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Seeds, count, angle and axis reference.

    Returns:
        AdapterResult[SolidWorksFeature]: ``data.type ==
        "LocalCircularPattern"`` on success.
    """
    import math as _math

    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.components:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="Component pattern requires at least one component",
        )
    if params.count < 1:
        return AdapterResult(
            status=AdapterResultStatus.ERROR, error="count must be >= 1"
        )
    if not params.axis_name and not params.axis_point:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="Component pattern requires axis_name or axis_point",
        )

    def _circular_operation() -> SolidWorksFeature:
        _select_pattern_components(adapter, params.components)
        if params.axis_name:
            if not _select_named_feature(adapter, params.axis_name, 2, True):
                raise Exception(
                    f"Failed to select rotation axis by name: {params.axis_name!r}"
                )
            axis_type = "AXIS"
        else:
            axis_type = _select_reference_point(
                adapter, params.axis_point, 2, ("EDGE", "AXIS", "FACE")
            )
            if axis_type is None:
                raise Exception(
                    f"Failed to select rotation axis at point {params.axis_point} "
                    "(mm); point at a cylindrical face or a linear edge"
                )

        spacing_rad = _math.radians(float(params.angle))
        feature_manager = adapter.currentModel.FeatureManager
        feature_manager = _flag_feature_methods(feature_manager, "IFeatureManager")
        before = _tree_snapshot(adapter)
        feature = feature_manager.FeatureCircularPattern5(
            int(params.count),  # Number (incl. seed)
            spacing_rad,  # Spacing (radians; total angle when EqualSpacing)
            False,  # FlipDirection
            "NULL",  # DName
            False,  # GeometryPattern (component patterns copy bodies anyway)
            bool(params.equal_spacing),  # EqualSpacing
            False,  # VaryInstance
            False,  # SyncSubAssemblies
            False,  # BDir2
            False,  # BSymmetric
            0,  # Number2
            0.0,  # Spacing2
            "NULL",  # DName2
            False,  # EqualSpacing2
        )
        feature = _resolve_feature(
            adapter, feature, before, frozenset({"LocalCirPattern"})
        )
        if not feature:
            raise Exception("Failed to create circular component pattern")

        return SolidWorksFeature(
            name=str(_read_member(feature, "Name")),
            type="LocalCircularPattern",
            id=adapter._get_feature_id(feature),
            parameters={
                "components": params.components,
                "count": int(params.count),
                "angle": float(params.angle),
                "equal_spacing": bool(params.equal_spacing),
                "axis_name": params.axis_name,
                "axis_point": params.axis_point,
                "axis_entity": axis_type,
            },
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation(
            "pattern_components_circular", _circular_operation
        ),
    )


# swChainPatternPitchMethod_e / swChainPatternAlignment_e / swChainPatternOptions_e
_CHAIN_PITCH_METHOD = {"distance": 0, "distance_linkage": 1, "connected_linkage": 2}
_CHAIN_ALIGN = {"seed": 0, "tangent": 1}
_CHAIN_OPTIONS = {"static": 0, "dynamic": 1}

# swFeatureNameID_e.swFmBeltAndChain (verified via .NET reflection on
# SolidWorks.Interop.swconst.dll; swFmLocalChainPattern=112 cross-checked). A
# wrong value makes CreateDefinition return null.
_SW_FM_BELT_AND_CHAIN = 119
# CylinderParams axis-component index (params = [ox,oy,oz, ax,ay,az, radius]).
_PULLEY_AXIS_INDEX = {"x": 3, "y": 4, "z": 5}


def _pattern_components_chain_impl(
    adapter: Any, params: ComponentChainPatternParameters
) -> AdapterResult[SolidWorksFeature]:
    """Chain component pattern via ``IFeatureManager::FeatureChainPattern``.

    The documented ``CreateDefinition``/``CreateFeature`` route returns ``null``
    under pywin32 late binding (a feature-data marshaling quirk; it works only in
    early-bound C#/VBA). ``FeatureChainPattern`` is the one-call method that
    consumes the pre-selection and works. The path must be a single connected
    sketch SEGMENT (``EXTSKETCHSEGMENT``, mark 2) -- selecting the sketch feature
    yields an invalid definition. Marks: path 2 | g1 comp 1/link1 256/link2 512/
    plane 16384 | g2 comp 2048/link1 4096/link2 8192/plane 32768.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Path segment, one or two seed groups, pitch/fill/options.

    Returns:
        AdapterResult[SolidWorksFeature]: ``data.type == "LocalChainPattern"``.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if params.pitch_method not in _CHAIN_PITCH_METHOD:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown pitch_method: {params.pitch_method!r} "
            f"(expected one of {sorted(_CHAIN_PITCH_METHOD)})",
        )
    if not params.path_segment or not params.group1_component:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="path_segment and group1_component are required",
        )
    group2 = bool(params.group2_component)
    if params.pitch_method == "connected_linkage" and not group2:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="connected_linkage requires group2_component",
        )

    def _chain_operation() -> SolidWorksFeature:
        model = adapter.currentModel
        ext = model.Extension

        def sel(name: str, etype: str, mark: int, append: bool) -> None:
            ok = adapter._attempt(
                lambda: ext.SelectByID2(
                    name, etype, 0.0, 0.0, 0.0, append, mark, null_callout(), 0
                ),
                default=False,
            )
            if not ok:
                raise Exception(f"Failed to select {etype} {name!r} (mark {mark})")

        adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        # Path (mark 2): the sketch SEGMENT, not the sketch feature.
        sel(params.path_segment, "EXTSKETCHSEGMENT", 2, False)
        # Group 1.
        sel(_qualify_component(adapter, params.group1_component), "COMPONENT", 1, True)
        sel(_qualify_entity_name(adapter, params.group1_link1), "AXIS", 256, True)
        if params.group1_link2:
            sel(_qualify_entity_name(adapter, params.group1_link2), "AXIS", 512, True)
        if params.group1_plane:
            sel(_qualify_entity_name(adapter, params.group1_plane), "PLANE", 16384, True)
        # Group 2 (connected linkage).
        if group2:
            sel(_qualify_component(adapter, params.group2_component), "COMPONENT", 2048, True)
            sel(_qualify_entity_name(adapter, params.group2_link1), "AXIS", 4096, True)
            if params.group2_link2:
                sel(_qualify_entity_name(adapter, params.group2_link2), "AXIS", 8192, True)
            if params.group2_plane:
                sel(_qualify_entity_name(adapter, params.group2_plane), "PLANE", 32768, True)

        fm = model.FeatureManager
        fm = _flag_feature_methods(fm, "IFeatureManager")
        before = _tree_snapshot(adapter)
        # FeatureChainPattern(PitchMethod, FlipDirection, FillPath, Number,
        #   Spacing, GroupOneFlipPlane, GroupTwoChain, GroupTwoFlipPlane,
        #   AlignMethod, Options)
        feature = fm.FeatureChainPattern(
            _CHAIN_PITCH_METHOD[params.pitch_method],
            bool(params.flip_direction),
            bool(params.fill_path),
            int(params.count),
            float(params.spacing) / 1000.0,
            False,
            group2,
            False,
            _CHAIN_ALIGN.get(params.align_method, 1),
            _CHAIN_OPTIONS.get(params.options, 1),
        )
        feature = _resolve_feature(
            adapter, feature, before, frozenset({"LocalChainPattern"})
        )
        if not feature:
            raise Exception("Failed to create chain component pattern")

        return SolidWorksFeature(
            name=str(_read_member(feature, "Name")),
            type="LocalChainPattern",
            id=adapter._get_feature_id(feature),
            parameters={
                "path_segment": params.path_segment,
                "pitch_method": params.pitch_method,
                "fill_path": bool(params.fill_path),
                "count": int(params.count),
                "groups": 2 if group2 else 1,
            },
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("pattern_components_chain", _chain_operation),
    )


def _pulley_cylinder_face(adapter: Any, component: Any, axis_index: int) -> Any:
    """Return a pulley's rotation-axis cylindrical face (largest coaxial radius).

    The Belt/Chain feature's pulley member must be a cylindrical FACE, not the
    component object (passing components makes ``CreateFeature`` silently null).
    Walks the component body's faces for cylinders whose axis is ~parallel to
    the belt-plane normal (``axis_index`` into ``CylinderParams`` = [ox,oy,oz,
    ax,ay,az, r]) and returns the largest-radius one — the rim cylinder. The
    picked radius does not matter (``PulleyDiameters`` sets the coupling ratio);
    only the axis + centre are read from the face.

    Args:
        adapter: Connected adapter (for ``_attempt``).
        component: An ``IComponent2`` dispatch (already flagged).
        axis_index: 3/4/5 — which ``CylinderParams`` axis component to test.

    Returns:
        Any: the ``IFace2`` dispatch, or ``None`` if no coaxial cylinder found.
    """
    from .. import sw_type_info

    component = sw_type_info.early_bound_or_flag(
        component, "IComponent2", "GetBody"
    )
    body = adapter._attempt(lambda: _read_member(component, "GetBody"), default=None)
    if body is None:
        return None
    body = sw_type_info.early_bound_or_flag(body, "IBody2", "GetFaces")
    faces = adapter._attempt(lambda: _read_member(body, "GetFaces"), default=None) or []
    best_face = None
    best_radius = -1.0
    for face in faces:
        face = sw_type_info.early_bound_or_flag(face, "IFace2", "GetSurface")
        surf = adapter._attempt(
            lambda f=face: _read_member(f, "GetSurface"), default=None
        )
        if surf is None:
            continue
        surf = sw_type_info.early_bound_or_flag(
            surf, "ISurface", "IsCylinder"
        )
        if not adapter._attempt(
            lambda s=surf: _read_member(s, "IsCylinder"), default=False
        ):
            continue
        cyl = adapter._attempt(lambda s=surf: _read_member(s, "CylinderParams"), default=None)
        if not cyl:
            continue
        if abs(cyl[axis_index]) > 0.9 and cyl[6] > best_radius:
            best_face, best_radius = face, cyl[6]
    return best_face


def _insert_belt_chain_impl(
    adapter: Any, params: BeltChainParameters
) -> AdapterResult[SolidWorksFeature]:
    """Belt/Chain assembly feature via ``CreateDefinition``/``CreateFeature``.

    Couples two or more pulley/sprocket components so they rotate together at
    the ratio their ``pulley_diameters`` imply (``engage_belt`` adds the belt
    MATES — only meaningful when the pulleys are FREE). Unlike the chain
    *pattern* (which nulls under ``CreateFeature`` and uses the one-call
    ``FeatureChainPattern`` instead), the belt feature-data DOES create under
    pywin32 early binding — provided each pulley member is its cylindrical FACE,
    not the component object (passing components makes ``CreateFeature`` silently
    null; the setters lie pre-commit so "all props set" proves nothing).

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Pulley components + pitch diameters (mm), belt plane, flags.

    Returns:
        AdapterResult[SolidWorksFeature]: ``data.type == "BeltChain"``.
    """
    from .. import sw_type_info

    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    n = len(params.pulley_components)
    if n < 2:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="insert_belt_chain requires at least 2 pulley_components",
        )
    if len(params.pulley_diameters) != n:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pulley_diameters must match pulley_components length "
            f"({len(params.pulley_diameters)} != {n})",
        )
    if params.flip_sides and len(params.flip_sides) != n:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="flip_sides, when set, must match pulley_components length "
            f"({len(params.flip_sides)} != {n})",
        )
    if params.pulley_member_axes and len(params.pulley_member_axes) != n:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pulley_member_axes, when set, must match pulley_components "
            f"length ({len(params.pulley_member_axes)} != {n})",
        )
    axis_index = _PULLEY_AXIS_INDEX.get(params.pulley_axis.lower())
    if axis_index is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown pulley_axis: {params.pulley_axis!r} (expected x/y/z)",
        )

    def _belt_operation() -> SolidWorksFeature:
        model = adapter.currentModel

        # Resolve the pulley members: named datum AXES when given (the only
        # route that makes the EngageBelt coupling honour pulley_diameters on
        # toothed wheels -- see BeltChainParameters.pulley_member_axes), else
        # each pulley's rotation-axis cylindrical face.
        members = []
        if params.pulley_member_axes:
            ext = model.Extension
            selmgr = model.SelectionManager
            for axis_name in params.pulley_member_axes:
                qualified = _qualify_entity_name(adapter, axis_name)
                adapter._attempt(lambda: model.ClearSelection2(True), default=None)
                selected = adapter._attempt(
                    lambda q=qualified: ext.SelectByID2(
                        q, "AXIS", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
                    ),
                    default=False,
                )
                if not selected:
                    raise Exception(f"Pulley member axis not found: {qualified!r}")
                typed_selmgr = sw_type_info.early_bound_or_flag(
                    selmgr, "ISelectionMgr", "GetSelectedObject6"
                )
                entity = adapter._attempt(
                    lambda sm=typed_selmgr: sm.GetSelectedObject6(1, -1),
                    default=None,
                )
                if entity is None:
                    raise Exception(f"Could not fetch pulley axis: {qualified!r}")
                members.append(entity)
            adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        else:
            for name in params.pulley_components:
                component = _get_component(adapter, name)
                if component is None:
                    raise Exception(f"Pulley component not found: {name!r}")
                face = _pulley_cylinder_face(adapter, component, axis_index)
                if face is None:
                    raise Exception(
                        f"No {params.pulley_axis}-axis cylindrical face on "
                        f"pulley {name!r}"
                    )
                members.append(face)

        # Belt-location plane (normal to the pulley axes) -> IRefPlane.
        plane_feat = adapter._attempt(
            lambda: _flag_feature_methods(model, "IAssemblyDoc").FeatureByName(
                params.location_plane
            ),
            default=None,
        )
        if plane_feat is None:
            raise Exception(f"Belt-location plane not found: {params.location_plane!r}")
        plane_feat = sw_type_info.early_bound_or_flag(
            plane_feat, "IFeature", "GetSpecificFeature2"
        )
        ref_plane = adapter._attempt(
            lambda: _read_member(plane_feat, "GetSpecificFeature2"),
            default=None,
        )
        if ref_plane is None:
            raise Exception(
                f"Could not resolve {params.location_plane!r} to a reference plane"
            )

        fm = model.FeatureManager
        fm = _flag_feature_methods(fm, "IFeatureManager")
        data = adapter._attempt(
            lambda: fm.CreateDefinition(_SW_FM_BELT_AND_CHAIN), default=None
        )
        if data is None:
            raise Exception(
                f"CreateDefinition({_SW_FM_BELT_AND_CHAIN}) returned null "
                "(belt/chain feature definition)"
            )
        typed = sw_type_info.early_bound(data, "IBeltChainFeatureData")
        flips = params.flip_sides or [False] * n
        diameters_m = [d / 1000.0 for d in params.pulley_diameters]
        for attr, value in (
            ("PulleyComponents", dispatch_array(members)),
            ("PulleyDiameters", double_array(diameters_m)),
            ("FlipSides", bool_array(flips)),
            ("BeltLocationPlane", ref_plane),
            ("UseBeltThickness", bool(params.use_belt_thickness)),
            ("BeltThickness", float(params.belt_thickness) / 1000.0),
            ("CreateBeltPart", bool(params.create_belt_part)),
            ("EngageBelt", bool(params.engage_belt)),
        ):
            adapter._attempt(
                lambda t=typed, a=attr, v=value: setattr(t, a, v), default=None
            )

        # CreateFeature returns the IFeature it made. No tree diff stands in
        # for it: the belt/chain feature's GetTypeName2 is unverified, and
        # CreateBeltPart also adds a belt component, so a diff could not tell
        # the two apart.
        feature = adapter._attempt(lambda: fm.CreateFeature(data), default=None)
        if not feature or _read_member(feature, "Name") is None:
            errs = adapter._attempt(lambda: fm.GetCreateFeatureErrors(), default="?")
            raise Exception(f"Failed to create belt/chain feature (errors={errs})")

        feature_name = str(_read_member(feature, "Name"))

        # Verify the COUPLING, not the definition: the definition's
        # PulleyDiameters read back fine even when the EngageBelt mate is
        # wrong (with FACE members the MateBeltDim bakes the picked faces'
        # diameters and no definition-level route rewrites it -- measured
        # live). The mate's own D1/D2 dimensions ARE the coupling, so read
        # them and fail loud unless they match the request.
        if params.engage_belt:
            _verify_belt_mate_diameters(adapter, diameters_m)

        # Blank the auto-generated belt-path sketch (construction scaffolding).
        if params.blank_sketch:
            _blank_feature_sketches(adapter, feature)

        return SolidWorksFeature(
            name=feature_name,
            type="BeltChain",
            id=adapter._get_feature_id(feature),
            parameters={
                "pulleys": n,
                "diameters_mm": list(params.pulley_diameters),
                "engage_belt": bool(params.engage_belt),
                "create_belt_part": bool(params.create_belt_part),
            },
            properties={"created": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("insert_belt_chain", _belt_operation),
    )


def _verify_belt_mate_diameters(adapter: Any, diameters_m: list[float]) -> None:
    """Assert the just-created EngageBelt coupling mate carries the requested
    per-pulley diameter RATIOS, raising otherwise.

    The ``MateBeltDim`` mate's own ``D1``/``D2`` dimensions ARE the coupling
    ratio. With FACE pulley members SolidWorks bakes the picked faces'
    diameters into them (the tooth-tip cylinder on a sprocket) and IGNORES the
    definition's ``PulleyDiameters`` -- which still read back as requested, so
    a definition-level check passes while the coupling is wrong. Verified
    live (2026-07-06): PulleyDiameters + forced ModifyDefinition,
    ModifyMemberParameters, an EngageBelt re-author, and direct writes to the
    mate dimensions all leave the face-derived ratio. Only AXIS pulley members
    make the typed diameters drive the mate, and THIS check proves it on every
    build.

    Compared SCALE-invariant, as a sorted multiset: only the ratio couples the
    pulleys (the absolute feed lives in other mates), and the recorded scale
    varies by member kind -- a face-member mate stores DIAMETERS (measured
    0.028/0.052 for 0.014/0.026 tip radii) while an axis-member mate stores
    the typed values at HALF scale, i.e. radii (measured 0.012/0.024 for
    typed diameters 0.024/0.048; the coupling still measures the exact typed
    ratio). Order is not preserved by the mate either way.
    """
    from .. import sw_type_info

    belt_mates = [
        feat
        for feat in _mate_group_subfeatures(adapter)
        if _read_member(feat, "GetTypeName2") == "MateBeltDim"
    ]
    if not belt_mates:
        raise Exception("engage_belt set but no MateBeltDim coupling mate found")
    feat = belt_mates[-1]  # the just-created belt's mate
    dims: list[float] = []
    for dname in ("D1", "D2", "D3", "D4"):
        param = adapter._attempt(lambda f=feat, d=dname: f.Parameter(d), default=None)
        if param is None:
            break
        param = sw_type_info.early_bound_or_flag(param, "IDimension")
        value = adapter._attempt(lambda p=param: p.SystemValue, default=None)
        if value is not None:
            dims.append(float(value))
    expected = sorted(diameters_m)
    actual = sorted(dims)
    proportional = (
        len(actual) == len(expected)
        and all(v > 0.0 for v in actual)
        and all(v > 0.0 for v in expected)
        and all(
            abs(a / actual[0] - e / expected[0]) < 1e-4
            for a, e in zip(actual, expected, strict=True)
        )
    )
    if not proportional:
        raise Exception(
            "belt coupling mate diameters do NOT carry the requested ratio: "
            f"mate carries {actual}, requested {expected} -- with FACE pulley "
            "members SW bakes the picked faces' (tip) diameters into the mate; "
            "pass pulley_member_axes (datum axes) so pulley_diameters drive"
        )


def _blank_feature_sketches(adapter: Any, feature: Any) -> None:
    """Blank every sketch nested under ``feature`` (best-effort, never raises).

    The Belt/Chain feature generates a belt-path sketch as a sub-feature; it is
    construction scaffolding, so hide it. Walks the sub-feature chain, and for
    each sketch selects it and calls ``IModelDoc2::BlankSketch`` (blanks the
    selected sketch). Failures are swallowed — blanking is cosmetic.
    """
    from .. import sw_type_info

    feature = sw_type_info.early_bound_or_flag(
        feature, "IFeature", "GetFirstSubFeature"
    )
    model = adapter.currentModel
    ext = model.Extension
    sub = adapter._attempt(
        lambda: _read_member(feature, "GetFirstSubFeature"),
        default=None,
    )
    while sub is not None:
        sub = sw_type_info.early_bound_or_flag(
            sub, "IFeature", "GetTypeName2", "GetNextSubFeature"
        )
        type_name = _read_member(sub, "GetTypeName2")
        if type_name in ("ProfileFeature", "3DProfileFeature"):
            sk_name = str(_read_member(sub, "Name"))
            selected = adapter._attempt(
                lambda nm=sk_name: ext.SelectByID2(
                    nm, "SKETCH", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
                ),
                default=False,
            )
            if selected:
                adapter._attempt(lambda: model.BlankSketch(), default=None)
                adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        sub = adapter._attempt(
            lambda s=sub: _read_member(s, "GetNextSubFeature"),
            default=None,
        )


# ---------------------------------------------------------------------------
# Mates (Phase 7B)
# ---------------------------------------------------------------------------


def _qualify_entity_name(adapter: Any, name: str) -> str:
    """Complete a mate-entity name with the assembly qualifier when needed.

    ``SelectByID2`` names for entities inside a component take the form
    ``"Plane1@shaft-1@assembly"``. A caller passing ``"Plane1@shaft-1"``
    gets the assembly title appended; names with two ``@`` qualifiers (or
    none — assembly-level planes like ``"Front Plane"``) pass through.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        name: Entity name as provided by the caller.

    Returns:
        str: Fully qualified entity name.
    """
    if name.count("@") == 1:
        return f"{name}@{_assembly_title(adapter)}"
    return name


def _select_mate_entity(adapter: Any, ref: Any, mark: int) -> bool:
    """Select one mate entity by name or point under a selection mark.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        ref: A ``MateEntityRef``.
        mark: Selection mark to apply.

    Returns:
        bool: ``True`` when the entity selected.
    """
    if ref.component and ref.name:
        mapped = _component_named_feature(adapter, ref.component, ref.name)
        if mapped is None:
            return False
        return bool(adapter._attempt(lambda: mapped.Select2(True, mark), default=False))
    if ref.name:
        qualified = _qualify_entity_name(adapter, ref.name)
        return bool(
            adapter._attempt(
                lambda: adapter.currentModel.Extension.SelectByID2(
                    qualified,
                    ref.entity_type,
                    0.0,
                    0.0,
                    0.0,
                    True,
                    mark,
                    null_callout(),
                    0,
                ),
                default=False,
            )
        )
    if len(ref.point) == 3:
        x, y, z = (float(c) / 1000.0 for c in ref.point)
        return bool(
            adapter._attempt(
                lambda: adapter.currentModel.Extension.SelectByID2(
                    "", ref.entity_type, x, y, z, True, mark, null_callout(), 0
                ),
                default=False,
            )
        )
    return False


def _mate_group_subfeatures(adapter: Any, model: Any = None) -> list[Any]:
    """Collect the mate features inside the assembly's MateGroup folder(s).

    Mates do not appear in the top-level ``FirstFeature``/``GetNextFeature``
    walk — they are sub-features of the ``MateGroup`` feature, reached via
    ``GetFirstSubFeature``/``GetNextSubFeature``.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        model: Assembly model document to walk; defaults to
            ``adapter.currentModel``. Pass a subassembly's model document to
            reach mates that live inside a (flexible) subassembly.

    Returns:
        list[Any]: Mate feature dispatches in tree order.
    """
    mates: list[Any] = []
    model = model or adapter.currentModel
    model = _flag_feature_methods(model, "IModelDoc2")
    feature = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feature:
            break
        feature = _flag_feature_methods(feature, "IFeature")
        if _read_member(feature, "GetTypeName2") == "MateGroup":
            sub = _read_member(feature, "GetFirstSubFeature")
            for _ in range(5000):
                if not sub:
                    break
                sub = _flag_feature_methods(sub, "IFeature")
                mates.append(sub)
                sub = _read_member(sub, "GetNextSubFeature")
        feature = _read_member(feature, "GetNextFeature")
    return mates


def _mate_feature_by_name(adapter: Any, name: str, model: Any = None) -> Any:
    """Resolve a mate feature by its tree name.

    ``FeatureByName`` resolves mates too; the MateGroup walk is the
    fallback for builds where it does not reach sub-features.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        name: Mate feature name, e.g. ``"Coincident1"``.
        model: Model document to search; defaults to ``adapter.currentModel``.
            Pass a subassembly's model document to resolve a mate that lives
            inside it (e.g. a driving-dimension mate in a flexible sub).

    Returns:
        Any: The mate feature dispatch or ``None``.
    """
    model = model or adapter.currentModel
    feature = adapter._attempt(
        lambda: _flag_feature_methods(model, "IAssemblyDoc").FeatureByName(name),
        default=None,
    )
    if feature:
        return _flag_feature_methods(feature, "IFeature")
    for mate in _mate_group_subfeatures(adapter, model):
        if str(_read_member(mate, "Name")) == name:
            return mate
    return None


def _mate_names(adapter: Any) -> set[str]:
    """Return the current set of mate feature names."""
    return {
        str(_read_member(mate, "Name")) for mate in _mate_group_subfeatures(adapter)
    }


def _mate_feature_name(adapter: Any, mate: Any) -> str:
    """Name of a just-created mate, read straight off the ``AddMate5`` return.

    The returned mate dispatch also implements ``IFeature`` (one IDispatch
    serves both interfaces), so flagging it as a feature exposes ``Name``
    in ~20 ms. The before/after ``_mate_names`` diff this replaces walked
    the full feature tree twice at ~20 s per walk on a 30-mate assembly
    (measured live), making every mate O(existing mates). The MateGroup
    walk remains only as a fallback for a successful ``AddMate5`` that
    returns no dispatch (not observed live; newest mate is last in tree
    order).

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        mate: The ``AddMate5`` return value (may be ``None``).

    Returns:
        str: The mate feature name, or ``""`` when it cannot be resolved.
    """
    if mate is not None:
        mate = _flag_feature_methods(mate, "IFeature")
        name = adapter._attempt(lambda: mate.Name, default=None)
        if name:
            return str(name)
    mates = _mate_group_subfeatures(adapter)
    return str(_read_member(mates[-1], "Name")) if mates else ""


def _validate_mechanical_values(params: AddMateParameters) -> str:
    """Validate the Phase 7C mechanical value options of ``params``.

    Args:
        params: Mate parameters to validate.

    Returns:
        str: Error message, or empty when valid.
    """
    if params.gear_ratio:
        if params.mate_type != "gear":
            return "gear_ratio is only valid for gear mates"
        if len(params.gear_ratio) != 2:
            return "gear_ratio must be [numerator, denominator]"
        if any(float(value) <= 0 for value in params.gear_ratio):
            return "gear_ratio values must be positive"
    rack_values = (params.pinion_pitch_diameter, params.rack_travel_per_revolution)
    if any(rack_values) and params.mate_type != "rack_pinion":
        return (
            "pinion_pitch_diameter/rack_travel_per_revolution are only "
            "valid for rack_pinion mates"
        )
    if all(rack_values):
        return (
            "set either pinion_pitch_diameter or rack_travel_per_revolution, not both"
        )
    if params.mate_type == "rack_pinion" and not any(rack_values):
        return (
            "rack_pinion mates require pinion_pitch_diameter or "
            "rack_travel_per_revolution (CreateMate cannot derive the value the "
            "way AddMate5 did)"
        )
    if any(float(value) < 0 for value in rack_values):
        return "rack_pinion values must be positive"
    if params.distance_per_revolution and params.mate_type != "screw":
        return "distance_per_revolution is only valid for screw mates"
    if float(params.distance_per_revolution) < 0:
        return "distance_per_revolution must be positive"
    return ""


def _harvest_selected(adapter: Any, model: Any, count: int) -> list[Any]:
    """Return the first ``count`` selected objects as an entity list.

    ``CreateMate`` attaches entities to the typed mate-data object via its
    ``EntitiesToMate`` property (an ``IDispatch`` array) rather than consuming a
    live selection the way ``AddMate5`` did. The caller pre-selects each entity
    (reusing the existing per-mark selection logic); this harvests them back out
    of the selection set with ``ISelectionMgr::GetSelectedObject6`` (1-based
    index, ``-1`` = any mark), matching the *Create Limit Distance Mate* API
    example.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        model: The active assembly model document (selection already made).
        count: Number of selected entities to harvest.

    Returns:
        list[Any]: The resolved entity object pointers, in selection order.

    Raises:
        Exception: When the selection manager or any entity does not resolve.
    """
    # ``SelectionManager`` is an ``IModelDoc2`` property; callers pass an
    # ``IAssemblyDoc``-bound ``model``, so rebind to ``IModelDoc2`` to read it.
    sel_mgr = adapter._attempt(
        lambda: sw_type_info.early_bound(model, "IModelDoc2").SelectionManager,
        default=None,
    )
    if sel_mgr is None:
        raise Exception("SelectionManager unavailable for mate-entity harvest")
    sel_mgr = _flag_feature_methods(sel_mgr, "ISelectionMgr")
    entities: list[Any] = []
    for index in range(1, count + 1):
        entity = adapter._attempt(
            lambda i=index: sel_mgr.GetSelectedObject6(i, -1), default=None
        )
        if entity is None:
            raise Exception(f"Mate entity {index} did not resolve from the selection")
        entities.append(entity)
    return entities


def _create_standard_mate(
    adapter: Any, model: Any, params: AddMateParameters, mate_type: int
) -> Any:
    """Create a standard/mechanical mate via ``CreateMateData`` → ``CreateMate``.

    Supersedes the obsolete ``AddMate5``. The entities the caller pre-selected
    are harvested into the typed feature-data object's ``EntitiesToMate``; the
    type-specific properties (alignment, value, flip/reverse, limits) are set on
    the data object, and the mate is created from it. The side of a
    distance/angle mate is chosen by ``FlipDimension`` (in place, no
    delete-and-re-add); a gear/screw's sense by ``Reverse``.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        model: The active assembly model document.
        params: Mate type, alignment and value options.
        mate_type: ``swMateType_e`` value for the mate.

    Returns:
        The created mate ``IFeature``.

    Raises:
        Exception: When the feature-data or the mate cannot be created.
    """
    kind = params.mate_type
    data = adapter._attempt(lambda: model.CreateMateData(mate_type), default=None)
    if data is None:
        raise Exception(f"CreateMateData({mate_type}) returned None for {kind} mate")
    interface = _MATE_DATA_INTERFACE.get(kind)
    if interface:
        data = _flag_feature_methods(data, interface)

    entities = _harvest_selected(adapter, model, len(params.entities))
    if kind == "width":
        # Width mate: first two selections are the width faces, the rest the tab
        # faces to centre between them. Unexercised by this repo's assemblies —
        # kept for API parity, not live-verified.
        data.WidthSelection = dispatch_array(entities[:2])
        data.TabSelection = dispatch_array(entities[2:])
        data.ConstraintType = _WIDTH_CENTERED
    else:
        data.EntitiesToMate = dispatch_array(entities)

    if kind in _MATE_TYPES_WITH_ALIGNMENT:
        data.MateAlignment = _MATE_ALIGNMENTS[params.alignment]

    if kind == "distance":
        distance = float(params.distance) / 1000.0
        data.FlipDimension = bool(params.flip)
        data.Distance = distance
        if params.distance_limits:
            data.IsAdvancedMate = True
            data.MinimumDistance = float(params.distance_limits[0]) / 1000.0
            data.MaximumDistance = float(params.distance_limits[1]) / 1000.0
    elif kind == "angle":
        angle = math.radians(float(params.angle))
        data.FlipDimension = bool(params.flip)
        data.Angle = angle
        if params.angle_limits:
            data.IsAdvancedMate = True
            data.MinimumAngle = math.radians(float(params.angle_limits[0]))
            data.MaximumAngle = math.radians(float(params.angle_limits[1]))
    elif kind == "concentric":
        data.LockRotation = bool(params.lock_rotation)
    elif kind == "gear":
        numerator, denominator = (
            [float(value) for value in params.gear_ratio]
            if params.gear_ratio
            else (1.0, 1.0)
        )
        data.GearRatioNumerator = numerator
        data.GearRatioDenominator = denominator
        data.Reverse = bool(params.flip)
    elif kind == "screw":
        data.Reverse = bool(params.flip)
        if params.distance_per_revolution:
            data.RevolutionType = _SCREW_DISTANCE_PER_REVOLUTION
            data.RevolutionVal = float(params.distance_per_revolution) / 1000.0

    mate = adapter._attempt(lambda: model.CreateMate(data), default=None)
    if mate is None:
        status = adapter._attempt(lambda: int(data.ErrorStatus), default=None)
        reason = _MATE_ERRORS.get(status or 0, f"error status {status}")
        raise Exception(f"CreateMate failed for {kind} mate: {reason}")
    return mate


def _create_mechanical_mate(
    adapter: Any, model: Any, params: AddMateParameters, mate_type: int
) -> Any:
    """Create a rack-pinion mate carrying a pitch diameter / travel value.

    ``AddMate5`` creates a rack-pinion mate but has no parameter for the pitch
    diameter, and a follow-up ``IFeature::ModifyDefinition`` on the created mate
    fails ("ModifyDefinition failed for mate ...") -- the rack-pinion feature
    data cannot be re-edited that way. The official pattern (SOLIDWORKS *Create
    Rack and Pinion Mate* API example) is the ``CreateMateData`` -> set members
    -> ``CreateMate`` flow: build the typed feature-data object, set its value
    members up front, and create the mate from it. Entities are pre-selected by
    the caller under the proper marks (rack=64 / pinion=128).

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        model: The active assembly model document.
        params: Mate parameters carrying the mechanical value.
        mate_type: ``swMateType_e`` value for the mate.

    Returns:
        The created mate ``IFeature``.

    Raises:
        Exception: When the feature data or the mate cannot be created.
    """
    data = adapter._attempt(lambda: model.CreateMateData(mate_type), default=None)
    if data is None:
        raise Exception(f"CreateMateData({mate_type}) returned None")
    data = _flag_feature_methods(data, "IRackPinionMateFeatureData")
    if params.pinion_pitch_diameter:
        data.DiameterType = _RACK_PINION_PITCH_DIAMETER
        data.DiameterVal = float(params.pinion_pitch_diameter) / 1000.0
    else:
        data.DiameterType = _RACK_PINION_TRAVEL_PER_REVOLUTION
        data.DiameterVal = float(params.rack_travel_per_revolution) / 1000.0
    data.Reverse = bool(params.flip)
    mate = adapter._attempt(lambda: model.CreateMate(data), default=None)
    if mate is None:
        raise Exception(f"CreateMate failed for {params.mate_type} mate")
    return mate


def _add_mate_impl(
    adapter: Any, params: AddMateParameters
) -> AdapterResult[dict[str, Any]]:
    """Add a standard or mechanical mate via ``IAssemblyDoc::CreateMate``.

    Entities are pre-selected per mark (mark 1 by default; 16 for width tab
    faces, 8 for cam followers, 64/128 for rack/pinion) using the existing
    selection logic, then handed to :func:`_create_standard_mate`, which
    harvests them into a typed ``CreateMateData`` object's ``EntitiesToMate``,
    sets the type-specific properties (alignment, value, ``FlipDimension`` /
    ``Reverse`` for the side/sense, limits) and calls ``CreateMate``. This
    supersedes the obsolete ``AddMate5``. Rack-pinion mates that carry a pitch
    value keep their dedicated :func:`_create_mechanical_mate` builder.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Mate type, entities, alignment and value options.

    Returns:
        AdapterResult[dict[str, Any]]: Created mate name/type or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    mate_type = _MATE_TYPES.get(params.mate_type)
    if mate_type is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown mate_type: {params.mate_type!r} "
            f"(expected one of {sorted(_MATE_TYPES)})",
        )
    alignment = _MATE_ALIGNMENTS.get(params.alignment)
    if alignment is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown alignment: {params.alignment!r} "
            f"(expected one of {sorted(_MATE_ALIGNMENTS)})",
        )
    minimum_entities = 4 if params.mate_type == "width" else 2
    if len(params.entities) < minimum_entities:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"{params.mate_type} mate requires at least "
            f"{minimum_entities} entities",
        )
    for limits, label in (
        (params.distance_limits, "distance_limits"),
        (params.angle_limits, "angle_limits"),
    ):
        if limits and len(limits) != 2:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=f"{label} must be [min, max]",
            )
    mechanical_error = _validate_mechanical_values(params)
    if mechanical_error:
        return AdapterResult(status=AdapterResultStatus.ERROR, error=mechanical_error)

    def _mate_operation() -> dict[str, Any]:
        model = adapter.currentModel
        adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        default_mark = _MATE_DEFAULT_MARKS.get(params.mate_type, 1)
        for index, ref in enumerate(params.entities):
            # Rack-pinion needs a distinct mark per entity (rack 64, pinion 128);
            # other mates share one default mark. An explicit ref.mark still wins.
            if params.mate_type == "rack_pinion" and not ref.mark and index < 2:
                mark = _RACK_PINION_MARKS[index]
            else:
                mark = ref.mark or default_mark
            if not _select_mate_entity(adapter, ref, mark):
                located = ref.name or ref.point
                raise Exception(
                    f"Failed to select mate entity {index + 1} "
                    f"({ref.entity_type} at {located!r})"
                )

        # Rack-pinion mates must be built via CreateMateData -> CreateMate
        # (AddMate5 cannot set the value, and a follow-up ModifyDefinition on the
        # result fails). A pitch diameter / travel value is REQUIRED (enforced in
        # _validate_mechanical_values) since CreateMate cannot derive it, so every
        # rack_pinion routes here. Entities are already pre-selected above under
        # marks 64 (rack) / 128 (pinion).
        if params.mate_type == "rack_pinion":
            # ``model`` stays ``IModelDoc2``; ``CreateMate*`` need ``IAssemblyDoc``.
            mate = _create_mechanical_mate(
                adapter, _flag_feature_methods(model, "IAssemblyDoc"), params, mate_type
            )
            adapter._attempt(lambda: model.ClearSelection2(True), default=None)
            name = _mate_feature_name(adapter, mate)
            adapter._attempt(lambda: model.EditRebuild3())
            payload = {
                "name": name,
                "mate_type": params.mate_type,
                "alignment": params.alignment,
                "entities": len(params.entities),
            }
            if params.pinion_pitch_diameter:
                payload["pinion_pitch_diameter"] = float(params.pinion_pitch_diameter)
            if params.rack_travel_per_revolution:
                payload["rack_travel_per_revolution"] = float(
                    params.rack_travel_per_revolution
                )
            return payload

        # ``model`` stays ``IModelDoc2`` (for ClearSelection2/EditRebuild3);
        # ``CreateMate*`` are ``IAssemblyDoc`` members, so pass a doc-typed handle.
        mate = _create_standard_mate(
            adapter, _flag_feature_methods(model, "IAssemblyDoc"), params, mate_type
        )
        adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        name = _mate_feature_name(adapter, mate)
        adapter._attempt(lambda: model.EditRebuild3())
        payload = {
            "name": name,
            "mate_type": params.mate_type,
            "alignment": params.alignment,
            "entities": len(params.entities),
        }
        if params.gear_ratio:
            payload["gear_ratio"] = [float(value) for value in params.gear_ratio]
        if params.pinion_pitch_diameter:
            payload["pinion_pitch_diameter"] = float(params.pinion_pitch_diameter)
        if params.rack_travel_per_revolution:
            payload["rack_travel_per_revolution"] = float(
                params.rack_travel_per_revolution
            )
        if params.distance_per_revolution:
            payload["distance_per_revolution"] = float(params.distance_per_revolution)
        return payload

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("add_mate", _mate_operation),
    )


def _list_mates_impl(adapter: Any) -> AdapterResult[list[dict[str, Any]]]:
    """List the active assembly's mates from the MateGroup folder.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.

    Returns:
        AdapterResult[list[dict[str, Any]]]: ``name``/``type``/
        ``suppressed`` per mate.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _list_operation() -> list[dict[str, Any]]:
        mates: list[dict[str, Any]] = []
        for mate in _mate_group_subfeatures(adapter):
            mates.append(
                {
                    "name": str(_read_member(mate, "Name")),
                    "type": str(_read_member(mate, "GetTypeName2")),
                    "suppressed": bool(
                        adapter._attempt(lambda m=mate: m.IsSuppressed(), default=False)
                    ),
                }
            )
        return mates

    return cast(
        AdapterResult[list[dict[str, Any]]],
        adapter._handle_com_operation("list_mates", _list_operation),
    )


def _delete_mate_impl(
    adapter: Any, params: MateRefParameters
) -> AdapterResult[dict[str, Any]]:
    """Delete a mate by feature name (select + ``DeleteSelection2``).

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Mate feature name.

    Returns:
        AdapterResult[dict[str, Any]]: Deletion confirmation or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.name.strip():
        return AdapterResult(status=AdapterResultStatus.ERROR, error="name is required")

    def _delete_operation() -> dict[str, Any]:
        model = adapter.currentModel
        feature = _mate_feature_by_name(adapter, params.name)
        if feature is None:
            raise Exception(f"Mate not found: {params.name!r}")

        adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        if not adapter._attempt(lambda: feature.Select2(False, 0), default=False):
            raise Exception(f"Failed to select mate: {params.name!r}")
        deleted = adapter._attempt(
            lambda: model.Extension.DeleteSelection2(0), default=False
        )
        if not deleted:
            adapter._attempt(lambda: model.EditDelete(), default=None)
        # Verify absence via FeatureByName only: it resolves mates on this
        # build (the pre-delete lookup above uses it as the fast path), and
        # the MateGroup-walk alternative costs ~20 s at 30 mates — an
        # O(mates) tax on every successful delete just to prove absence.
        still_there = adapter._attempt(
            lambda: _flag_feature_methods(model, "IAssemblyDoc").FeatureByName(
                params.name
            ),
            default=None,
        )
        if still_there is not None:
            raise Exception(f"Mate {params.name!r} is still present after delete")
        return {"name": params.name, "removed": True}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("delete_mate", _delete_operation),
    )


def _config_name(model: Any) -> str:
    """Return ``model``'s active configuration name, or empty when unreadable."""
    try:
        manager = model.ConfigurationManager
        active = _read_member(manager, "ActiveConfiguration")
        return str(_read_member(active, "Name")) if active is not None else ""
    except Exception:
        return ""


def _suppress_mate_impl(
    adapter: Any, params: SuppressMateParameters
) -> AdapterResult[dict[str, Any]]:
    """Suppress/unsuppress a mate via ``IFeature::SetSuppression2``.

    By default the change applies across all configurations
    (``swAllConfiguration``, a typed-null names VARIANT — bare ``None``
    raises ``Type mismatch`` under pywin32 late binding). When
    ``params.configuration`` is set it scopes to that one configuration
    (``swSpecifyConfiguration`` + a BSTR SAFEARRAY), the basis for the
    engagement states where a gear mate is live in ``rest`` but suppressed in
    ``cone_disengaged``. ``IsSuppressed`` reports the **active**
    configuration's state, so for a scoped change the named configuration is
    activated for the readback and the prior active configuration restored.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Mate feature name, target state, and optional config scope.

    Returns:
        AdapterResult[dict[str, Any]]: Resulting state or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.name.strip():
        return AdapterResult(status=AdapterResultStatus.ERROR, error="name is required")
    if params.configuration and params.component:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="configuration scope is not supported together with component "
            "(a subassembly's configurations are a separate namespace)",
        )

    def _suppress_operation() -> dict[str, Any]:
        model = adapter.currentModel
        if params.component:
            comp = _get_component(adapter, params.component)
            if comp is None:
                raise Exception(f"Component not found: {params.component!r}")
            model = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
            if model is None:
                raise Exception(
                    f"Could not open the model document of {params.component!r}"
                )

        feature = _mate_feature_by_name(adapter, params.name, model)
        if feature is None:
            where = f" in {params.component!r}" if params.component else ""
            raise Exception(f"Mate not found: {params.name!r}{where}")

        action = _SUPPRESS_FEATURE if params.suppress else _UNSUPPRESS_FEATURE
        if params.configuration:
            which, names = _SPECIFY_CONFIGURATION, bstr_array([params.configuration])
        else:
            which, names = _ALL_CONFIGURATIONS, null_variant()
        adapter._attempt(
            lambda: feature.SetSuppression2(action, which, names),
            default=False,
        )

        # IsSuppressed reads the active configuration; activate the scoped
        # target for an honest readback, then restore what was active.
        prior = ""
        if params.configuration:
            prior = _config_name(model)
            if prior != params.configuration:
                if not adapter._attempt(
                    lambda: model.ShowConfiguration2(params.configuration),
                    default=False,
                ):
                    raise Exception(
                        f"Could not activate configuration {params.configuration!r} "
                        "to verify suppression"
                    )
        resulting = bool(
            adapter._attempt(lambda: feature.IsSuppressed(), default=False)
        )
        if params.configuration and prior and prior != params.configuration:
            adapter._attempt(lambda: model.ShowConfiguration2(prior), default=False)
        if resulting != params.suppress:
            state = "suppressed" if params.suppress else "unsuppressed"
            where = f" in {params.configuration!r}" if params.configuration else ""
            raise Exception(f"Mate {params.name!r} did not become {state}{where}")
        return {
            "name": params.name,
            "suppressed": resulting,
            "component": params.component,
            "configuration": params.configuration,
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("suppress_mate", _suppress_operation),
    )


def _set_component_solving_impl(
    adapter: Any, params: SetComponentSolvingParameters
) -> AdapterResult[dict[str, Any]]:
    """Set a subassembly component's solve mode via ``CompConfigProperties5``.

    Selects the component, applies the rigid/flexible solve mode across the
    fully-resolved state, and verifies it by reading ``IComponent2::Solving``
    back. A fixed subassembly silently refuses to go flexible — float and
    ground it first; the readback then surfaces the refusal as an error.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Component name and target solve mode.

    Returns:
        AdapterResult[dict[str, Any]]: Resulting solve mode or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    mode = _COMP_SOLVING.get(params.solving)
    if mode is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown solving mode: {params.solving!r} "
            f"(expected one of {sorted(_COMP_SOLVING)})",
        )

    def _operation() -> dict[str, Any]:
        asm = adapter.currentModel
        comp = _get_component(adapter, params.name)
        if comp is None:
            raise Exception(f"Component not found: {params.name!r}")
        adapter._attempt(lambda: asm.ClearSelection2(True))
        if not _select_component(adapter, params.name, 0, False):
            raise Exception(f"Failed to select component {params.name!r}")
        adapter._attempt(
            lambda: asm.CompConfigProperties5(
                _COMP_FULLY_RESOLVED, mode, True, False, "", False, False
            )
        )
        adapter._attempt(lambda: asm.ClearSelection2(True))
        solving = int(adapter._attempt(lambda: comp.Solving, default=-1))
        if solving != mode:
            raise Exception(
                f"Solve mode did not take for {params.name!r}: requested "
                f"{params.solving!r}, read back {_COMP_SOLVING_NAME.get(solving, solving)!r}"
                " (a fixed subassembly cannot be flexible — float it first)"
            )
        return {"name": params.name, "solving": _COMP_SOLVING_NAME[solving]}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("set_component_solving", _operation),
    )


def _set_component_configuration_impl(
    adapter: Any, params: SetComponentConfigurationParameters
) -> AdapterResult[dict[str, Any]]:
    """Set which child configuration a component references via
    ``CompConfigProperties5``, scoped to the active assembly configuration.

    Selects the component and applies the referenced-configuration change to
    the assembly's **active** configuration only, so the same component can
    point at a different child configuration in each assembly configuration --
    the mechanism behind top-level engagement states (e.g. a ``cone_disengaged``
    assembly config that references the drive-train's own ``cone_disengaged``).
    A non-empty ``configuration`` selects that child config; an empty string
    restores the component's default. The component's current solve mode is
    preserved (``CompConfigProperties5`` also carries it). The change is
    verified by reading ``IComponent2::ReferencedConfiguration`` back after an
    ``EditRebuild3`` (required for the change to take effect).

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Component name and target child configuration name.

    Returns:
        AdapterResult[dict[str, Any]]: Resulting referenced configuration or
        error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.name.strip():
        return AdapterResult(status=AdapterResultStatus.ERROR, error="name is required")

    def _operation() -> dict[str, Any]:
        asm = adapter.currentModel
        comp = _get_component(adapter, params.name)
        if comp is None:
            raise Exception(f"Component not found: {params.name!r}")
        # CompConfigProperties5 rewrites the solve mode too, so preserve it.
        solving = int(
            adapter._attempt(lambda: comp.Solving, default=_COMP_SOLVING["rigid"])
        )
        adapter._attempt(lambda: asm.ClearSelection2(True))
        if not _select_component(adapter, params.name, 0, False):
            raise Exception(f"Failed to select component {params.name!r}")
        adapter._attempt(
            lambda: asm.CompConfigProperties5(
                _COMP_FULLY_RESOLVED,
                solving,
                True,
                False,
                params.configuration,
                False,
                False,
            )
        )
        adapter._attempt(lambda: asm.ClearSelection2(True))
        # ReferencedConfiguration only reflects the change after a rebuild.
        adapter._attempt(lambda: asm.EditRebuild3())
        referenced = str(
            adapter._attempt(lambda: comp.ReferencedConfiguration, default="")
        )
        if params.configuration and referenced != params.configuration:
            raise Exception(
                f"Referenced configuration did not take for {params.name!r}: "
                f"requested {params.configuration!r}, read back {referenced!r} "
                "(does the component's model have a configuration by that name?)"
            )
        return {"name": params.name, "configuration": referenced}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("set_component_configuration", _operation),
    )


def _component_named_feature(adapter: Any, name: str, feature_name: str) -> Any:
    """Map a named feature inside a component into assembly context.

    Resolves the component (``"sub-1/part-1"`` slash path), reads the named
    feature off the component's part document as a base ``IFeature``, and
    returns ``IComponent2::GetCorresponding`` of it -- the assembly-context
    object a mate or motor can select via ``IFeature::Select2``.

    Unlike ``GetCorrespondingEntity`` (vertex/face/edge only), ``GetCorresponding``
    maps ANY persistent-reference object including a reference-axis or
    reference-plane ``IFeature``. This is depth-agnostic: the ``IComponent2``
    already encodes its full tree path, so a part nested two levels deep
    (part-in-sub-in-top) resolves where a hand-built ``name@part@sub@title``
    string silently fails. It also avoids the cylindrical-face walk
    (~600 s on a fine-toothed gear) -- mapping a named lobe axis takes ~1 s.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        name: Component name, e.g. ``"drive-train-1/cylinder-gear-1"``.
        feature_name: Reference-feature name in the part, e.g. ``"Axis3"``.

    Returns:
        Any: The corresponding object (a feature dispatch) in assembly
        context, or ``None`` when the component or feature is not found.
    """
    comp = _get_component(adapter, name)
    if comp is None:
        return None
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if part is None:
        return None
    feat = adapter._attempt(
        lambda p=part: sw_type_info.early_bound_doc(p).FeatureByName(feature_name),
        default=None,
    )
    if feat is None:
        return None
    mapped = adapter._attempt(lambda: comp.GetCorresponding(feat), default=None)
    if mapped is not None:
        mapped = _flag_feature_methods(mapped, "IFeature")
    return mapped


def _component_cylindrical_face(
    adapter: Any, name: str, point: list[float] | None = None
) -> Any:
    """Map a component's cylindrical face into assembly context.

    Iterates the component part's solid bodies, gathers cylindrical faces, and
    returns ``IComponent2::GetCorrespondingEntity`` of the chosen one — the
    assembly-context entity a rotary motor (or any axis reference) can use,
    robust for a part nested in a flexible subassembly. With ``point`` the face
    whose axis passes nearest that assembly-space point (millimetres) is chosen;
    otherwise the largest by area (the dominant journal/shaft).

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        name: Component name, e.g. ``"drive-train-1/crankshaft-1"``.
        point: Optional ``[x, y, z]`` in millimetres to disambiguate.

    Returns:
        Any: The corresponding ``IEntity`` (a face) in assembly context, or
        ``None`` when the component or a cylindrical face is not found.
    """
    comp = _get_component(adapter, name)
    if comp is None:
        return None
    part = adapter._attempt(lambda: comp.GetModelDoc2(), default=None)
    if part is None:
        return None
    bodies = adapter._attempt(
        lambda: sw_type_info.early_bound(part, "IPartDoc").GetBodies2(
            _SW_SOLID_BODY, False
        ),
        default=None,
    )
    if bodies is None:
        return None
    if not isinstance(bodies, (list, tuple)):
        bodies = [bodies]

    target = [c / 1000.0 for c in point] if point else None
    best_face = None
    best_key = None
    for body in bodies:
        if body is None:
            continue
        body = _flag_feature_methods(body, "IBody2")
        face = adapter._attempt(lambda b=body: b.GetFirstFace(), default=None)
        for _ in range(100000):
            if not face:
                break
            face = _flag_feature_methods(face, "IFace2")
            surface = adapter._attempt(lambda f=face: f.GetSurface(), default=None)
            if surface is not None:
                surface = _flag_feature_methods(surface, "ISurface")
                if bool(adapter._attempt(lambda s=surface: s.IsCylinder(), default=False)):
                    cyl = adapter._attempt(
                        lambda s=surface: s.CylinderParams, default=None
                    )
                    area = float(adapter._attempt(lambda f=face: f.GetArea(), default=0.0))
                    if cyl is not None:
                        key = _cylinder_rank(cyl, area, target)
                        if best_key is None or key > best_key:
                            best_key, best_face = key, face
            face = adapter._attempt(lambda f=face: f.GetNextFace(), default=None)
    if best_face is None:
        return None
    return adapter._attempt(
        lambda: comp.GetCorrespondingEntity(best_face), default=None
    )


def _cylinder_rank(
    cyl: Any, area: float, target: list[float] | None
) -> tuple[float, float]:
    """Ranking key for a cylindrical face (higher is better).

    ``CylinderParams`` is ``[ox, oy, oz, ax, ay, az, radius]`` (point on the
    axis, axis direction, radius) in metres. Without a target the key is the
    face area; with one it is the negative perpendicular distance from the
    target to the axis line (nearest axis wins), area breaking ties.
    """
    if target is None:
        return (area, 0.0)
    origin = [float(cyl[0]), float(cyl[1]), float(cyl[2])]
    axis = [float(cyl[3]), float(cyl[4]), float(cyl[5])]
    norm = math.sqrt(sum(c * c for c in axis)) or 1.0
    axis = [c / norm for c in axis]
    rel = [target[i] - origin[i] for i in range(3)]
    proj = sum(rel[i] * axis[i] for i in range(3))
    perp = [rel[i] - proj * axis[i] for i in range(3)]
    dist = math.sqrt(sum(c * c for c in perp))
    return (-dist, area)
