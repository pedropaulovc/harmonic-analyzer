"""Reference-geometry mixin for PyWin32 SolidWorks operations (Phase 3).

Implements constraint-based reference planes (``IFeatureManager::InsertRefPlane``),
reference axes (``IModelDoc2::InsertAxis2``), reference points
(``IFeatureManager::InsertReferencePoint``) and numerically positioned
coordinate systems
(``IFeatureManager::CreateCoordinateSystemUsingNumericalValues``).
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, cast

from .. import sw_type_info as _sw_type_info
from ..base import (
    AdapterResult,
    AdapterResultStatus,
    CreateAxisParameters,
    CreateCoordinateSystemParameters,
    CreatePlaneParameters,
    CreateReferencePointParameters,
    RenameFeatureParameters,
    SolidWorksFeature,
)
from .features import (
    _flag_feature_methods,
    _read_member,
    _resolve_feature,
    _select_by_point,
    _select_named_feature,
    _tree_snapshot,
    _TreeSnapshot,
)

# swRefPlaneReferenceConstraints_e (bitmask)
_PLANE_PARALLEL = 1
_PLANE_COINCIDENT = 4
_PLANE_DISTANCE = 8
_PLANE_ANGLE = 16
_PLANE_OPTION_FLIP = 256

# swRefPointType_e
_POINT_ALONG_CURVE = 2
_POINT_CENTER_EDGE = 3
_POINT_FACE_CENTER = 4

# swRefPointAlongCurveType_e
_ALONG_CURVE_TYPES = {"distance": 0, "percentage": 1, "evenly": 2}

_PLANE_MODES = ("offset", "angle", "three_point", "parallel_point")


def _offset_plane_distance(offset_mm: float) -> tuple[float, int]:
    """Resolve a signed offset-plane Distance constraint to ``(distance_m, flip_bits)``.

    ``IFeatureManager.InsertRefPlane``'s Distance constraint takes a positive
    magnitude; the *side* of the base plane is chosen by the ``OptionFlip`` bit,
    not by the sign of the distance. Passing a negative distance does not place
    the plane on the opposite side -- SOLIDWORKS clamps it to 0, collapsing the
    new plane onto the base. So a negative ``offset`` is converted to a positive
    magnitude with the ``OptionFlip`` bit set; a positive ``offset`` keeps the
    near side. The sign of ``offset`` is therefore the single knob that selects
    the side -- there is no separate ``flip`` flag.

    Args:
        offset_mm: Signed offset from the base plane, in millimetres. A negative
            value builds the plane on the far side of ``base_plane``.

    Returns:
        ``(distance_m, flip_bits)`` -- a non-negative distance in metres and the
        flip bits to OR into the Distance constraint.
    """
    distance_m = float(offset_mm) / 1000.0
    if distance_m < 0.0:
        return -distance_m, _PLANE_OPTION_FLIP
    return distance_m, 0


def _angle_plane_constraint(angle_deg: float) -> tuple[float, int]:
    """Resolve a signed angle-plane constraint to ``(angle_rad, flip_bits)``.

    The angled-plane analogue of :func:`_offset_plane_distance`: the *magnitude*
    of ``angle_deg`` is the tilt about the pivot edge and the *sign* selects
    which of the two valid angled planes is built. A negative angle sets the
    ``OptionFlip`` bit (the alternate plane -- exactly what the removed ``flip``
    flag used to reach for a positive angle); a positive angle keeps the near
    side. So, as with offset planes, the sign is the single side knob and there
    is no separate ``flip`` flag.

    Args:
        angle_deg: Signed tilt from the base plane, in degrees. A negative value
            builds the alternate angled plane.

    Returns:
        ``(angle_rad, flip_bits)`` -- a non-negative angle in radians and the
        flip bits to OR into the Angle constraint.
    """
    angle_rad = math.radians(abs(float(angle_deg)))
    if float(angle_deg) < 0.0:
        return angle_rad, _PLANE_OPTION_FLIP
    return angle_rad, 0
_AXIS_MODES = ("two_planes", "cylindrical_face", "two_points", "edge")
_POINT_MODES = ("face_center", "arc_center", "along_curve")


class SolidWorksReferenceGeometryMixin:
    """Expose SolidWorks reference-geometry methods via mixin-local helpers."""

    async def create_plane(
        self, params: CreatePlaneParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _create_plane_impl(self, params)

    async def create_axis(
        self, params: CreateAxisParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _create_axis_impl(self, params)

    async def rename_feature(
        self, params: RenameFeatureParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _rename_feature_impl(self, params)

    async def create_reference_point(
        self, params: CreateReferencePointParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _create_reference_point_impl(self, params)

    async def create_coordinate_system(
        self, params: CreateCoordinateSystemParameters
    ) -> AdapterResult[SolidWorksFeature]:
        return _create_coordinate_system_impl(self, params)


def _select_vertex(adapter: Any, point_mm: list[float], mark: int) -> bool:
    """Select a vertex located by its coordinates (millimetres).

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        point_mm: Vertex location ``[x, y, z]`` in millimetres.
        mark: Selection mark to apply.

    Returns:
        bool: ``True`` when the vertex was selected.
    """
    return _select_by_point(adapter, "VERTEX", point_mm, mark, True)


def _new_reference_feature(
    adapter: Any,
    returned: Any,
    before: _TreeSnapshot,
    type_name: str,
    parameters: dict[str, Any],
    failure: str,
    *,
    expect_many: bool = False,
) -> SolidWorksFeature:
    """Resolve a just-created reference feature and wrap it for the result.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        returned: Whatever the creating COM call returned (may be a bool or a
            non-feature object such as ``IRefPlane``).
        before: The tree captured before the call (``_tree_snapshot``).
        type_name: Feature ``type`` label for the result, which is also the
            ``IFeature.GetTypeName2`` of the feature the call creates.
        parameters: Input parameters echoed into the result.
        failure: Error message when no new feature can be resolved.
        expect_many: The call may create several ``type_name`` features;
            the newest is wrapped (see ``_resolve_feature``).

    Returns:
        SolidWorksFeature: Wrapper exposing the new feature's name.

    Raises:
        Exception: When the feature cannot be resolved in the tree.
    """
    feature = _resolve_feature(
        adapter,
        returned,
        before,
        frozenset({type_name}),
        expect_many=expect_many,
    )
    if not feature:
        raise Exception(failure)
    return SolidWorksFeature(
        name=str(_read_member(feature, "Name")),
        type=type_name,
        id=adapter._get_feature_id(feature),
        parameters=parameters,
        properties={"created": datetime.now().isoformat()},
    )


def _create_plane_impl(
    adapter: Any, params: CreatePlaneParameters
) -> AdapterResult[SolidWorksFeature]:
    """Create a constraint-based reference plane via ``InsertRefPlane``.

    Reference entities are selected under marks 0/1/2 (first/second/third)
    before the call, per the ``IFeatureManager::InsertRefPlane`` contract:

    - ``offset``: ``base_plane`` (mark 0); constraint ``Distance``
      (``+ OptionFlip`` for a negative, far-side ``offset``).
    - ``angle``: ``base_plane`` (mark 0) + pivot edge by point (mark 1);
      constraints ``Angle`` and ``Coincident``.
    - ``three_point``: three vertices (marks 0/1/2), ``Coincident`` each.
    - ``parallel_point``: ``base_plane`` (mark 0) + vertex (mark 1);
      constraints ``Parallel`` and ``Coincident``.

    Distances are millimetres (converted to metres); angles are degrees
    (converted to radians).

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        params: Plane parameters (mode, references, signed distance/angle).

    Returns:
        AdapterResult[SolidWorksFeature]: ``data.type == "RefPlane"`` on
        success.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` on selection
            failure or when the plane is not created.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if params.mode not in _PLANE_MODES:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"create_plane mode must be one of {_PLANE_MODES}, got {params.mode!r}",
        )
    if params.mode in ("offset", "angle", "parallel_point") and not params.base_plane:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"create_plane mode {params.mode!r} requires 'base_plane'",
        )
    if params.mode == "angle" and not params.edge_point and not params.pivot_axis:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_plane mode 'angle' requires 'edge_point' or 'pivot_axis'",
        )
    if params.mode == "three_point" and len(params.points) != 3:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_plane mode 'three_point' requires exactly 3 points",
        )
    if params.mode == "parallel_point" and len(params.points) != 1:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_plane mode 'parallel_point' requires exactly 1 point",
        )

    def _plane_operation() -> SolidWorksFeature:
        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        constraints = (0, 0.0, 0, 0.0, 0, 0.0)
        if params.mode == "offset":
            if not _select_named_feature(adapter, params.base_plane, 0, True):
                raise Exception(f"Failed to select base plane: {params.base_plane}")
            distance_m, dist_flip = _offset_plane_distance(params.offset)
            constraints = (
                _PLANE_DISTANCE | dist_flip,
                distance_m,
                0, 0.0, 0, 0.0,
            )
        elif params.mode == "angle":
            if not _select_named_feature(adapter, params.base_plane, 0, True):
                raise Exception(f"Failed to select base plane: {params.base_plane}")
            if params.pivot_axis:
                if not _select_named_feature(adapter, params.pivot_axis, 1, True):
                    raise Exception(
                        f"Failed to select pivot axis: {params.pivot_axis}"
                    )
            elif not _select_by_point(adapter, "EDGE", params.edge_point, 1, True):
                raise Exception(
                    f"Failed to select pivot edge at point {params.edge_point} (mm)"
                )
            angle_rad, angle_flip = _angle_plane_constraint(params.angle)
            constraints = (
                _PLANE_ANGLE | angle_flip,
                angle_rad,
                _PLANE_COINCIDENT, 0.0, 0, 0.0,
            )
        elif params.mode == "three_point":
            for mark, point in enumerate(params.points):
                if not _select_vertex(adapter, point, mark):
                    raise Exception(f"Failed to select vertex at point {point} (mm)")
            constraints = (
                _PLANE_COINCIDENT, 0.0,
                _PLANE_COINCIDENT, 0.0,
                _PLANE_COINCIDENT, 0.0,
            )
        else:  # parallel_point
            if not _select_named_feature(adapter, params.base_plane, 0, True):
                raise Exception(f"Failed to select base plane: {params.base_plane}")
            if not _select_vertex(adapter, params.points[0], 1):
                raise Exception(
                    f"Failed to select vertex at point {params.points[0]} (mm)"
                )
            constraints = (_PLANE_PARALLEL, 0.0, _PLANE_COINCIDENT, 0.0, 0, 0.0)

        feature_manager = adapter.currentModel.FeatureManager
        feature_manager = _flag_feature_methods(feature_manager, "IFeatureManager")
        before = _tree_snapshot(adapter)
        returned = feature_manager.InsertRefPlane(*constraints)
        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        return _new_reference_feature(
            adapter,
            returned,
            before,
            "RefPlane",
            {
                "mode": params.mode,
                "base_plane": params.base_plane,
                "offset": float(params.offset),
                "angle": float(params.angle),
            },
            "Failed to create reference plane",
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("create_plane", _plane_operation),
    )


def _create_axis_impl(
    adapter: Any, params: CreateAxisParameters
) -> AdapterResult[SolidWorksFeature]:
    """Create a reference axis via ``IModelDoc2::InsertAxis2``.

    ``InsertAxis2`` consumes the current selection set and returns only a
    bool, so the new axis is recovered by diffing the feature tree.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        params: Axis parameters (mode and references).

    Returns:
        AdapterResult[SolidWorksFeature]: ``data.type == "RefAxis"`` on
        success.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` on selection
            failure or when the axis is not created.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if params.mode not in _AXIS_MODES:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"create_axis mode must be one of {_AXIS_MODES}, got {params.mode!r}",
        )
    if params.mode == "two_planes" and len(params.planes) != 2:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_axis mode 'two_planes' requires exactly 2 plane names",
        )
    if params.mode == "cylindrical_face" and not params.face_point:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_axis mode 'cylindrical_face' requires 'face_point'",
        )
    if params.mode == "two_points" and len(params.points) != 2:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_axis mode 'two_points' requires exactly 2 points",
        )
    if params.mode == "edge" and not params.edge_point:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_axis mode 'edge' requires 'edge_point'",
        )

    def _axis_operation() -> SolidWorksFeature:
        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        if params.mode == "two_planes":
            for name in params.planes:
                if not _select_named_feature(adapter, name, 0, True):
                    raise Exception(f"Failed to select plane: {name}")
        elif params.mode == "cylindrical_face":
            if not _select_by_point(adapter, "FACE", params.face_point, 0, True):
                raise Exception(
                    f"Failed to select face at point {params.face_point} (mm)"
                )
        elif params.mode == "two_points":
            for point in params.points:
                if not _select_vertex(adapter, point, 0):
                    raise Exception(f"Failed to select vertex at point {point} (mm)")
        else:  # edge
            if not _select_by_point(adapter, "EDGE", params.edge_point, 0, True):
                raise Exception(
                    f"Failed to select edge at point {params.edge_point} (mm)"
                )

        model = adapter.currentModel
        model = _flag_feature_methods(model, "IModelDoc2")
        before = _tree_snapshot(adapter)
        returned = model.InsertAxis2(True)  # AutoSize
        adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        if not returned:
            raise Exception("Failed to create reference axis")
        return _new_reference_feature(
            adapter,
            None,  # InsertAxis2 returns a bool; resolve by tree diff
            before,
            "RefAxis",
            {
                "mode": params.mode,
                "planes": params.planes,
                "face_point": params.face_point,
                "points": params.points,
                "edge_point": params.edge_point,
            },
            "Reference axis created but not found in the feature tree",
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("create_axis", _axis_operation),
    )


def _rename_feature_impl(
    adapter: Any, params: RenameFeatureParameters
) -> AdapterResult[SolidWorksFeature]:
    """Rename a tree feature via ``IFeature::Name`` (a settable property).

    Resolves the feature with ``IModelDoc2::FeatureByName`` (the same lookup
    :func:`_select_named_feature` uses), then assigns the new name. Used to give
    auto-named reference planes/axes (``Plane1``/``Axis2`` …) stable, semantic
    names so assemblies can select them as ``"<new_name>@<component>"``.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        params: Old and new feature names (any ``@document`` qualifier on
            ``old_name`` is stripped before lookup).

    Returns:
        AdapterResult[SolidWorksFeature]: ``data.name == new_name`` on success.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` when the feature
            is not found or the rename does not take.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.old_name or not params.new_name:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="rename_feature requires non-empty 'old_name' and 'new_name'",
        )

    def _rename_operation() -> SolidWorksFeature:
        bare = params.old_name.split("@", 1)[0]
        feature = adapter._attempt(
            lambda: _sw_type_info.early_bound_doc(adapter.currentModel).FeatureByName(
                bare
            ),
            default=None,
        )
        if not feature:
            raise Exception(f"Feature not found: {params.old_name}")
        feature.Name = params.new_name
        if str(_read_member(feature, "Name")) != params.new_name:
            raise Exception(
                f"Rename did not take: {params.old_name!r} -> {params.new_name!r}"
            )
        return SolidWorksFeature(
            name=params.new_name,
            type="Rename",
            id=adapter._get_feature_id(feature),
            parameters={"old_name": params.old_name, "new_name": params.new_name},
            properties={"renamed": datetime.now().isoformat()},
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("rename_feature", _rename_operation),
    )


def _create_reference_point_impl(
    adapter: Any, params: CreateReferencePointParameters
) -> AdapterResult[SolidWorksFeature]:
    """Create reference point(s) via ``IFeatureManager::InsertReferencePoint``.

    Distances are millimetres (converted to metres); percentages pass through.
    ``along_curve`` with ``along == "evenly"`` can create several points —
    the result wraps the last created feature.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        params: Reference-point parameters (mode, references, distribution).

    Returns:
        AdapterResult[SolidWorksFeature]: ``data.type == "RefPoint"`` on
        success.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` on selection
            failure or when no point is created.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if params.mode not in _POINT_MODES:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=(
                f"create_reference_point mode must be one of {_POINT_MODES}, "
                f"got {params.mode!r}"
            ),
        )
    if params.mode == "face_center" and not params.face_point:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_reference_point mode 'face_center' requires 'face_point'",
        )
    if params.mode in ("arc_center", "along_curve") and not params.edge_point:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"create_reference_point mode {params.mode!r} requires 'edge_point'",
        )
    if params.mode == "along_curve" and params.along not in _ALONG_CURVE_TYPES:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=(
                "create_reference_point 'along' must be one of "
                f"{tuple(_ALONG_CURVE_TYPES)}, got {params.along!r}"
            ),
        )

    def _point_operation() -> SolidWorksFeature:
        count = 1
        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        if params.mode == "face_center":
            if not _select_by_point(adapter, "FACE", params.face_point, 0, True):
                raise Exception(
                    f"Failed to select face at point {params.face_point} (mm)"
                )
            args = (_POINT_FACE_CENTER, 0, 0.0, 1)
        elif params.mode == "arc_center":
            if not _select_by_point(adapter, "EDGE", params.edge_point, 0, True):
                raise Exception(
                    f"Failed to select edge at point {params.edge_point} (mm)"
                )
            args = (_POINT_CENTER_EDGE, 0, 0.0, 1)
        else:  # along_curve
            if not _select_by_point(adapter, "EDGE", params.edge_point, 0, True):
                raise Exception(
                    f"Failed to select edge at point {params.edge_point} (mm)"
                )
            along = _ALONG_CURVE_TYPES[params.along]
            value = {
                "distance": float(params.distance) / 1000.0,
                "percentage": float(params.percentage),
                "evenly": 0.0,
            }[params.along]
            count = int(params.count) if params.along == "evenly" else 1
            args = (_POINT_ALONG_CURVE, along, value, count)

        feature_manager = adapter.currentModel.FeatureManager
        feature_manager = _flag_feature_methods(feature_manager, "IFeatureManager")
        before = _tree_snapshot(adapter)
        returned = feature_manager.InsertReferencePoint(*args)
        adapter._attempt(
            lambda: adapter.currentModel.ClearSelection2(True), default=None
        )
        return _new_reference_feature(
            adapter,
            returned,
            before,
            "RefPoint",
            {
                "mode": params.mode,
                "along": params.along,
                "distance": float(params.distance),
                "percentage": float(params.percentage),
                "count": int(params.count),
            },
            "Failed to create reference point",
            # "evenly" distributes ``count`` points: several RefPoint
            # features, of which the result wraps the last (newest).
            expect_many=count > 1,
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation("create_reference_point", _point_operation),
    )


def _create_coordinate_system_impl(
    adapter: Any, params: CreateCoordinateSystemParameters
) -> AdapterResult[SolidWorksFeature]:
    """Create a coordinate system at numeric position/rotation.

    Uses ``IFeatureManager::CreateCoordinateSystemUsingNumericalValues``,
    which needs no selections. Position is millimetres (converted to metres);
    rotation is degrees (converted to radians and normalised into
    ``[0, 2*pi)`` as the API requires).

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        params: Coordinate-system parameters (position, rotation).

    Returns:
        AdapterResult[SolidWorksFeature]: ``data.type == "CoordSys"`` on
        success.

    Raises:
        Exception: Propagated through ``_handle_com_operation`` when the
            feature is not created.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if len(params.position) != 3 or len(params.rotation) != 3:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_coordinate_system requires 3-element position and rotation",
        )

    def _coordinate_system_operation() -> SolidWorksFeature:
        position_m = [float(value) / 1000.0 for value in params.position]
        rotation_rad = [
            math.radians(float(value)) % (2.0 * math.pi) for value in params.rotation
        ]
        use_rotation = any(value != 0.0 for value in rotation_rad)

        feature_manager = adapter.currentModel.FeatureManager
        feature_manager = _flag_feature_methods(feature_manager, "IFeatureManager")
        before = _tree_snapshot(adapter)
        returned = feature_manager.CreateCoordinateSystemUsingNumericalValues(
            True,  # UseLocation
            position_m[0],
            position_m[1],
            position_m[2],
            use_rotation,
            rotation_rad[0],
            rotation_rad[1],
            rotation_rad[2],
        )
        return _new_reference_feature(
            adapter,
            returned,
            before,
            "CoordSys",
            {
                "position": [float(value) for value in params.position],
                "rotation": [float(value) for value in params.rotation],
            },
            "Failed to create coordinate system",
        )

    return cast(
        AdapterResult[SolidWorksFeature],
        adapter._handle_com_operation(
            "create_coordinate_system", _coordinate_system_operation
        ),
    )
