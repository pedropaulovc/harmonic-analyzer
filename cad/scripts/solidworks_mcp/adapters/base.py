"""Base adapter interface for SolidWorks integration.

Defines the common interface that all SolidWorks adapters must implement, following the
adapter pattern from the original TypeScript implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class AdapterHealth(BaseModel):
    """Health status information for adapters.

    Attributes:
        average_response_time (float): The average response time value.
        connection_status (str): The connection status value.
        error_count (int): The error count value.
        healthy (bool): The healthy value.
        last_check (datetime): The last check value.
        metrics (dict[str, Any] | None): The metrics value.
        success_count (int): The success count value.
    """

    healthy: bool
    last_check: datetime
    error_count: int
    success_count: int
    average_response_time: float
    connection_status: str
    metrics: dict[str, Any] | None = None

    def __getitem__(self, key: str) -> Any:
        """Build internal getitem.

        Args:
            key (str): The key value.

        Returns:
            Any: The result produced by the operation.
        """
        if key == "status":
            return "healthy" if self.healthy else "unhealthy"
        if key == "connected":
            return self.connection_status == "connected"
        if key == "adapter_type":
            return (self.metrics or {}).get("adapter_type")
        if key == "version":
            return (self.metrics or {}).get("version", "mock-1.0")
        if key == "uptime":
            return (self.metrics or {}).get("uptime", 0.0)
        return self.model_dump().get(key)

    def __contains__(self, key: str) -> bool:
        """Build internal contains.

        Args:
            key (str): The key value.

        Returns:
            bool: True if contains, otherwise False.
        """
        legacy_keys = {"status", "connected", "adapter_type", "version", "uptime"}
        if key in legacy_keys:
            return True
        return key in self.model_dump()


class AdapterResultStatus(StrEnum):
    """Result status for adapter operations.

    Attributes:
        ERROR (Any): The error value.
        SUCCESS (Any): The success value.
        TIMEOUT (Any): The timeout value.
        WARNING (Any): The warning value.
    """

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    TIMEOUT = "timeout"


@dataclass
class AdapterResult(Generic[T]):
    """Result wrapper for adapter operations.

    Attributes:
        data (T | None): The data value.
        error (str | None): The error value.
        execution_time (float | None): The execution time value.
        metadata (dict[str, Any] | None): The metadata value.
        status (AdapterResultStatus): The status value.
    """

    status: AdapterResultStatus
    data: T | None = None
    error: str | None = None
    execution_time: float | None = None
    metadata: dict[str, Any] | None = None

    @property
    def is_success(self) -> bool:
        """Check if operation was successful.

        Returns:
            bool: True if success, otherwise False.
        """
        return self.status == AdapterResultStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        """Check if operation had an error.

        Returns:
            bool: True if error, otherwise False.
        """
        return self.status == AdapterResultStatus.ERROR


# SolidWorks data models
class SolidWorksModel(BaseModel):
    """SolidWorks model information.

    Attributes:
        configuration (str | None): The configuration value.
        is_active (bool): The is active value.
        name (str): The name value.
        path (str): The path value.
        properties (dict[str, Any] | None): The properties value.
        type (str): The type value.
    """

    path: str
    name: str
    type: str  # "Part", "Assembly", "Drawing"
    is_active: bool
    configuration: str | None = None
    properties: dict[str, Any] | None = None

    def __getitem__(self, key: str) -> Any:
        """Build internal getitem.

        Args:
            key (str): The key value.

        Returns:
            Any: The result produced by the operation.
        """
        if key == "title":
            return self.name
        if key == "units":
            return (self.properties or {}).get("units")
        return self.model_dump().get(key)


class SolidWorksFeature(BaseModel):
    """SolidWorks feature information.

    Attributes:
        id (str | None): The id value.
        name (str): The name value.
        parameters (dict[str, Any] | None): The parameters value.
        parent (str | None): The parent value.
        properties (dict[str, Any] | None): The properties value.
        type (str): The type value.
    """

    name: str
    type: str
    id: str | None = None
    parent: str | None = None
    properties: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None

    def __getitem__(self, key: str) -> Any:
        """Build internal getitem.

        Args:
            key (str): The key value.

        Returns:
            Any: The result produced by the operation.
        """
        if self.parameters and key in self.parameters:
            return self.parameters.get(key)
        return self.model_dump().get(key)


class ExtrusionParameters(BaseModel):
    """Parameters for extrusion operations.

    Attributes:
        auto_select (bool): The auto select value.
        both_directions (bool): Extrude mid-plane (``swEndCondMidPlane``):
            ``depth`` is the TOTAL depth, split ``depth/2`` to each side of
            the sketch plane (live-verified: a 10 mm both-directions cut
            reaches only 5 mm into a body sitting on one side).
        depth (float): The depth value.
        draft_angle (float): The draft angle value.
        end_condition (str): The end condition value.
        feature_scope (bool): The feature scope value.
        merge_result (bool): The merge result value.
        reverse_direction (bool): The reverse direction value.
        thin_feature (bool): The thin feature value.
        thin_thickness (float | None): The thin thickness value.
        up_to_surface (str | None): The up to surface value.
    """

    depth: float
    draft_angle: float = 0.0
    reverse_direction: bool = False
    both_directions: bool = False
    thin_feature: bool = False
    thin_thickness: float | None = None
    auto_fillet_corners: bool = False
    fillet_corners_radius: float = 0.0
    end_condition: str = "Blind"
    up_to_surface: str | None = None
    merge_result: bool = True
    feature_scope: bool = False
    auto_select: bool = True
    selected_contours: list[tuple[float, float, float]] | None = None
    """Model-space points (metres), one per sketch region to cut. When set, the
    cut selects those ``SKETCHREGION`` contours instead of the whole sketch --
    the way a hand-built feature cuts only the triangles bounded by a sketch's
    construction diagonals. ``None`` cuts the full profile (default)."""
    start_offset: float = 0.0
    """Offset (mm) of the cut's START plane from the sketch plane. Non-zero
    switches the start condition to ``swStartOffset``, so the cut begins this
    far from the sketch instead of at it -- e.g. a pocket that leaves a central
    web by starting the through-cut partway across the body."""
    flip_start_offset: bool = False
    """When ``start_offset`` is set, flip which side of the sketch plane the
    offset start is measured toward."""


class RevolveParameters(BaseModel):
    """Parameters for revolve operations.

    Attributes:
        angle (float): The angle value.
        both_directions (bool): The both directions value.
        is_cut (bool): Revolve as a CUT (material removal) instead of a boss —
            ``FeatureRevolve2``'s ``IsCut``. Enables oblique cylindrical cuts
            (a bore at an arbitrary angle: sketch a centreline along the bore
            axis + a rectangle beside it, revolve-cut 360°) that an extruded
            cut cannot produce without an angled reference plane.
        merge_result (bool): The merge result value.
        reverse_direction (bool): The reverse direction value.
        thin_feature (bool): The thin feature value.
        thin_thickness (float | None): The thin thickness value.
    """

    angle: float
    reverse_direction: bool = False
    both_directions: bool = False
    is_cut: bool = False
    thin_feature: bool = False
    thin_thickness: float | None = None
    merge_result: bool = True


class SweepParameters(BaseModel):
    """Parameters for sweep operations.

    Attributes:
        merge_result (bool): The merge result value.
        path (str): The path value.
        twist_along_path (bool): The twist along path value.
        twist_angle (float): The twist angle value.
    """

    path: str
    twist_along_path: bool = False
    twist_angle: float = 0.0
    merge_result: bool = True


class LoftParameters(BaseModel):
    """Parameters for loft operations.

    Attributes:
        end_tangent (str | None): The end tangent value.
        guide_curves (list[str] | None): The guide curves value.
        merge_result (bool): The merge result value.
        profiles (list[str]): The profiles value.
        start_tangent (str | None): The start tangent value.
    """

    profiles: list[str]
    guide_curves: list[str] | None = None
    start_tangent: str | None = None
    end_tangent: str | None = None
    merge_result: bool = True


class MirrorFeatureParameters(BaseModel):
    """Parameters for a 3D mirror-feature operation.

    Mirrors existing features about a reference plane or planar face. Distinct
    from the sketch-level ``sketch_mirror`` (which reflects 2D sketch entities).

    Attributes:
        plane (str): Name of the mirror plane or planar face (e.g.
            ``"Right Plane"``). Selected under mark 2.
        features (list[str]): Names of the features to mirror (e.g.
            ``["Boss-Extrude1"]``). Selected under mark 1.
        geometry_pattern (bool): Mirror only the feature geometry rather than
            re-solving the whole feature.
        merge (bool): Merge resulting bodies into a single solid.
    """

    plane: str
    features: list[str]
    geometry_pattern: bool = False
    merge: bool = True


class CircularPatternParameters(BaseModel):
    """Parameters for a circular feature-pattern operation.

    Attributes:
        axis_point (list[float]): A point ``[x, y, z]`` in millimetres on the
            rotation-axis reference — a cylindrical face (uses its axis) or a
            linear edge. Selected under mark 1. Ignored when ``axis_name`` is
            given. Point selection projects through the view, so a point on
            an axis buried inside solid material picks the body face in front
            of it instead — prefer ``axis_name`` for reference axes.
        axis_name (str): Name of a reference axis feature (e.g. ``"Axis1"``)
            to rotate about. Takes precedence over ``axis_point``; the robust
            choice whenever the axis was created via ``create_axis``.
        features (list[str]): Names of the seed features to pattern. Selected
            under mark 4.
        count (int): Total number of instances, including the seed.
        angle (float): Total angular span in degrees when ``equal_spacing`` is
            true, otherwise the spacing between instances in degrees.
        equal_spacing (bool): Distribute instances equally across ``angle``.
        geometry_pattern (bool): Copy the seed feature's geometry verbatim
            instead of re-solving the feature at each instance. Required for
            reliable instances when the seed profile is equation-driven
            (per-instance re-solve of global-variable spline profiles produces
            corrupt slivers — observed live on SW 2026); also faster.
    """

    axis_point: list[float] = []
    axis_name: str = ""
    features: list[str]
    count: int
    angle: float = 360.0
    equal_spacing: bool = True
    geometry_pattern: bool = False


class LinearPatternParameters(BaseModel):
    """Parameters for a linear feature-pattern operation.

    Attributes:
        direction_point (list[float]): A point ``[x, y, z]`` in millimetres on
            or near the direction edge. Among the body's straight edges
            parallel to ``direction_vector``, the one nearest this point is
            selected under mark 1.
        direction_vector (list[float]): ``[x, y, z]`` giving the sense the
            instances march in from the seed, e.g. ``[1, 0, 0]`` for +X. Need
            not be unit length. It fixes both which edge is picked and
            ``FlipDir1``, so the result never depends on the active view.
        features (list[str]): Names of the seed features to pattern. Selected
            under mark 4.
        count (int): Total number of instances, including the seed.
        spacing (float): Distance between instances in millimetres.
    """

    direction_point: list[float]
    direction_vector: list[float]
    features: list[str]
    count: int
    spacing: float


class ShellParameters(BaseModel):
    """Parameters for a shell operation (hollow out a solid).

    Attributes:
        thickness (float): Wall thickness in millimetres.
        face_points (list[list[float]]): Points ``[x, y, z]`` in millimetres,
            one per face to remove (open the shell on). An empty list shells the
            body with no face removed (a closed hollow). Each is selected under
            mark 1.
        outward (bool): Add the thickness outward (grow the body) rather than
            inward.
    """

    thickness: float
    face_points: list[list[float]] = []
    outward: bool = False


class DraftParameters(BaseModel):
    """Parameters for a neutral-plane draft operation.

    Attributes:
        angle (float): Draft angle in degrees.
        neutral_plane (str): Name of the neutral plane or planar face that the
            draft pivots about (e.g. ``"Top Plane"``). Selected under mark 1.
        face_points (list[list[float]]): Points ``[x, y, z]`` in millimetres,
            one per face to draft. Each is selected under mark 2.
        flip (bool): Reverse the draft direction.
    """

    angle: float
    neutral_plane: str
    face_points: list[list[float]]
    flip: bool = False


class CreatePlaneParameters(BaseModel):
    """Parameters for a constraint-based reference-plane operation.

    Exactly one mode is used per call; the other mode's fields are ignored.

    Attributes:
        mode (str): One of ``"offset"`` (parallel to ``base_plane`` at
            ``offset``), ``"angle"`` (rotated ``angle`` about an edge from
            ``base_plane``), ``"three_point"`` (through three vertices), or
            ``"parallel_point"`` (parallel to ``base_plane`` through a vertex).
        base_plane (str): Name of the reference plane or planar face the new
            plane is built from (``offset``/``angle``/``parallel_point``).
        offset (float): Signed offset distance in millimetres (``offset``
            mode); a negative value builds the plane on the far side of
            ``base_plane`` (the side is carried by the sign, not a separate
            flag).
        angle (float): Rotation in degrees (``angle`` mode).
        edge_point (list[float]): Point ``[x, y, z]`` in millimetres on the
            pivot edge (``angle`` mode). Coordinate edge selection is
            VIEW-DEPENDENT (SolidWorks picks at the screen projection), so an
            edge sharing its projection with another can mis-select — prefer
            ``pivot_axis`` when a named reference axis is available.
        pivot_axis (str): Name of a reference-axis FEATURE (e.g. ``"Axis2"``)
            to rotate about instead of a picked edge (``angle`` mode).
            Name-based and therefore view-independent; wins over
            ``edge_point`` when both are given.
        points (list[list[float]]): Vertex points ``[x, y, z]`` in
            millimetres — three for ``three_point``, one for
            ``parallel_point``.
    """

    mode: str
    base_plane: str = ""
    offset: float = 0.0
    angle: float = 0.0
    edge_point: list[float] = []
    pivot_axis: str = ""
    points: list[list[float]] = []


class ImportDxfDwgParameters(BaseModel):
    """Parameters for importing a DXF/DWG file into the active part as a sketch.

    Wraps ``IFeatureManager::InsertDwgOrDxfFile2`` (import method
    ``swImportDxfDwg_ImportToExistingPart``): the named plane is selected, then
    the file's 2D geometry is inserted as a sketch feature on that plane. Import
    defaults are configured through ``ISldWorks::GetImportFileData`` /
    ``IImportDxfDwgData`` before the insert.

    Distances are millimetres; ``scale`` and ``position`` map the file's own
    units onto the model. SolidWorks computes sensible defaults for anything
    left ``None`` (paper size / sheet scale to fit, length unit from the file
    header), so a bare ``(file_path, plane)`` import is valid.

    Attributes:
        file_path (str): Absolute path to the ``.dxf``/``.dwg`` file.
        plane (str): Reference plane to place the sketch on (``"Front"`` …).
        scale (float | None): Uniform sheet scale applied to the imported
            geometry (``IImportDxfDwgData::SetSheetScale``). ``None`` lets
            SolidWorks fit the sheet to the data.
        position (list[float] | None): ``[x, y]`` translation in millimetres of
            the imported geometry's origin on the plane
            (``IImportDxfDwgData::SetPosition``). ``None`` keeps the file origin.
        merge_points (bool): Merge coincident endpoints so contours close
            (``SetMergePoints``); recommended for cut profiles.
        merge_distance (float): Merge tolerance in millimetres.
        import_dimensions (bool): Import DXF dimension entities as sketch
            dimensions. Off by default — the traced artwork carries none.
        import_hatch (bool): Import hatch fills. Off by default — hatch fills are
            not cuttable profiles; the outline contours define the cut regions.
        add_constraints (bool): Let SolidWorks infer sketch relations on the
            imported geometry. Off by default — inference on many near-collinear
            traced segments produces spurious horizontal/vertical relations.
    """

    file_path: str
    plane: str = "Front"
    scale: float | None = None
    position: list[float] | None = None
    merge_points: bool = True
    merge_distance: float = 0.002
    import_dimensions: bool = False
    import_hatch: bool = False
    add_constraints: bool = False


class RenameFeatureParameters(BaseModel):
    """Parameters for renaming a feature in the active document's tree.

    ``create_plane``/``create_axis`` only auto-name their features
    (``Plane1``/``Axis2`` …); rename gives them a stable, human-readable name so
    assemblies can select them as ``"<new_name>@<component>"`` independent of
    feature-creation order.

    Attributes:
        old_name (str): Current feature name (any ``@document`` qualifier is
            stripped before lookup).
        new_name (str): Replacement feature name.
    """

    old_name: str
    new_name: str


class CreateAxisParameters(BaseModel):
    """Parameters for a reference-axis operation.

    Exactly one mode is used per call; the other mode's fields are ignored.

    Attributes:
        mode (str): One of ``"two_planes"`` (intersection of two planes),
            ``"cylindrical_face"`` (axis of a cylinder/cone located by a point
            on it), ``"two_points"`` (through two vertices), or ``"edge"``
            (along a linear edge located by a point on it).
        planes (list[str]): Two plane names (``two_planes`` mode).
        face_point (list[float]): Point ``[x, y, z]`` in millimetres on the
            cylindrical face (``cylindrical_face`` mode).
        points (list[list[float]]): Two vertex points ``[x, y, z]`` in
            millimetres (``two_points`` mode).
        edge_point (list[float]): Point ``[x, y, z]`` in millimetres on the
            edge (``edge`` mode).
    """

    mode: str
    planes: list[str] = []
    face_point: list[float] = []
    points: list[list[float]] = []
    edge_point: list[float] = []


class CreateReferencePointParameters(BaseModel):
    """Parameters for a reference-point operation.

    Exactly one mode is used per call; the other mode's fields are ignored.

    Attributes:
        mode (str): One of ``"face_center"`` (center of a face located by a
            point on it), ``"arc_center"`` (center of a circular edge located
            by a point on it), or ``"along_curve"`` (one or more points along
            an edge located by a point on it).
        face_point (list[float]): Point ``[x, y, z]`` in millimetres on the
            face (``face_center`` mode).
        edge_point (list[float]): Point ``[x, y, z]`` in millimetres on the
            edge (``arc_center``/``along_curve`` modes).
        along (str): Distribution for ``along_curve`` — ``"distance"`` (at
            ``distance`` mm from the closer end), ``"percentage"`` (at
            ``percentage`` % of the length), or ``"evenly"`` (``count``
            evenly distributed points).
        distance (float): Distance in millimetres (``along == "distance"``).
        percentage (float): Percentage 0–100 (``along == "percentage"``).
        count (int): Number of points (``along == "evenly"``); 1 otherwise.
    """

    mode: str
    face_point: list[float] = []
    edge_point: list[float] = []
    along: str = "distance"
    distance: float = 0.0
    percentage: float = 0.0
    count: int = 1


class CreateCoordinateSystemParameters(BaseModel):
    """Parameters for a numerically positioned coordinate-system feature.

    Attributes:
        position (list[float]): Origin ``[x, y, z]`` in millimetres relative
            to the global origin.
        rotation (list[float]): Rotation ``[rx, ry, rz]`` in degrees about the
            global axes.
    """

    position: list[float] = [0.0, 0.0, 0.0]
    rotation: list[float] = [0.0, 0.0, 0.0]


class CreateEquationCurveParameters(BaseModel):
    """Parameters for an equation-driven sketch curve.

    Expressions are passed verbatim to SolidWorks (same syntax as the
    Equation Driven Curve sketch tool); lengths evaluate in **document
    units** -- NOT metres like the rest of the COM surface (live-verified
    on SW 2026: with an IPS part template a radius expression of ``0.05``
    yields a 0.05 in arc, not 50 mm). Trigonometric functions here take
    **radians**, unlike the equation manager's degree-based parser (see
    ``SetGlobalVariableParameters``). Expressions may reference equation
    manager globals by quoted name, e.g. ``"Rb" * (cos(t) + t * sin(t))``.

    Attributes:
        x_expression (str): ``x(t)`` for a parametric curve; empty string for
            an explicit ``y = f(x)`` curve.
        y_expression (str): ``y(t)`` (parametric) or ``f(x)`` (explicit).
        z_expression (str): ``z(t)`` for a 3D parametric curve; empty for 2D.
        range_start (str): Start of the ``t`` (or ``x``) range — a string so
            expressions like ``"-pi/2"`` or dimension names work.
        range_end (str): End of the range.
        is_angle_range (bool): ``True`` when the range represents an angle in
            radians.
        lock_start (bool): Lock the curve's start point.
        lock_end (bool): Lock the curve's end point.
    """

    x_expression: str = ""
    y_expression: str
    z_expression: str = ""
    range_start: str
    range_end: str
    is_angle_range: bool = False
    lock_start: bool = True
    lock_end: bool = True


class SetGlobalVariableParameters(BaseModel):
    """Parameters for adding or updating an equation-manager global variable.

    Equation-manager parser dialect (live-verified on SW 2026):
    trigonometric functions take **degrees** (``cos(60)`` = 0.5) and
    inverse trig returns degrees (``atn(1)`` = 45); ``sqr`` is the
    square ROOT (VBA-style). Length-valued results feed dimensions and
    equation-driven curves in document units. Note the asymmetry with
    ``CreateEquationCurveParameters`` expressions, which use radians.

    Attributes:
        name (str): Global variable name without quotes (e.g. ``ToothCount``).
        expression (str): Right-hand side, e.g. ``"24"`` or
            ``'"PitchDiameter" / "Module"'`` (referenced names in embedded
            double quotes).
        configuration (str): Configuration the assignment applies to; empty
            string applies it to all configurations.
    """

    name: str
    expression: str
    configuration: str = ""


class CreateEquationParameters(BaseModel):
    """Parameters for adding or updating a full driving equation.

    Attributes:
        equation (str): Complete equation with quoted names, e.g.
            ``'"D1@Boss-Extrude1" = "ToothCount" / "DiametralPitch"'``.
        configuration (str): Configuration the equation applies to; empty
            string applies it to all configurations.
    """

    equation: str
    configuration: str = ""


class CreateConfigurationParameters(BaseModel):
    """Parameters for creating a configuration.

    Attributes:
        name (str): New configuration name.
        comment (str): Comment shown in Configuration Properties.
        parent (str): Parent configuration name (derived configuration);
            empty for a top-level configuration.
        description (str): Configuration description text.
    """

    name: str
    comment: str = ""
    parent: str = ""
    description: str = ""


class MeasureEntityRef(BaseModel):
    """One entity to include in a measurement selection.

    Entities with caller-stable names (reference planes, axes, sketches)
    are located by ``name``; faces, edges and vertices have no stable name
    and are located by a ``point`` lying on them.

    Attributes:
        entity_type (str): ``SelectByID2`` entity-type string, e.g.
            ``"FACE"``, ``"EDGE"``, ``"VERTEX"``, ``"PLANE"``, ``"AXIS"``.
        name (str): Entity name for named entities; empty when locating by
            point.
        point (list[float]): ``[x, y, z]`` in millimetres on the entity;
            empty when locating by name.
    """

    entity_type: str
    name: str = ""
    point: list[float] = []


class MeasureParameters(BaseModel):
    """Parameters for a measurement over one or more selected entities.

    Attributes:
        entities (list[MeasureEntityRef]): Entities to measure — one for
            intrinsic properties (edge length, face area, circle diameter),
            two or more for relational ones (distance, angle).
        arc_option (str): Distance anchor for arcs/circles — ``"center"``
            (center to center), ``"minimum"`` or ``"maximum"``.
    """

    entities: list[MeasureEntityRef]
    arc_option: str = "center"


class ApplyMaterialParameters(BaseModel):
    """Parameters for assigning a material to a part.

    Attributes:
        material (str): Material name exactly as it appears in the database,
            e.g. ``"Plain Carbon Steel"``, ``"Brass"``, ``"Gray Cast Iron"``.
        database (str): Material database; empty for the default SolidWorks
            materials database, otherwise a ``.sldmat`` file name or path.
        configuration (str): Configuration to assign the material in; empty
            for the active configuration.
    """

    material: str
    database: str = ""
    configuration: str = ""


class AddThreadParameters(BaseModel):
    """Parameters for a cosmetic thread on a circular edge.

    Attributes:
        edge_point (list[float]): ``[x, y, z]`` in millimetres on the
            circular edge of the cylindrical face to thread.
        standard (str): Thread standard — one of ``"none"``, ``"ansi_inch"``,
            ``"ansi_metric"``, ``"iso"``, ``"din"``, ``"jis"``, ``"bsi"``,
            ``"helicoil_inch"``, ``"helicoil_metric"``.
        standard_type (str): Thread type within the standard, e.g.
            ``"Machine Threads"``.
        size (str): Thread size designation, e.g. ``"1/4-20"`` or ``"M6x1.0"``.
        diameter (float): Thread (minor/drill) diameter in millimetres.
        end_type (str): ``"blind"``, ``"blind_upto_next"``, ``"through"`` or
            ``"blind_2dia"``.
        depth (float): Thread depth in millimetres (blind end types only).
        note (str): Callout text shown in drawings.
    """

    edge_point: list[float]
    standard: str = "ansi_inch"
    standard_type: str = ""
    size: str = ""
    diameter: float = 0.0
    end_type: str = "blind"
    depth: float = 0.0
    note: str = ""


class TappedHoleParameters(BaseModel):
    """Parameters for a Hole Wizard *tapped* hole placed on a face by point.

    A real (``HoleWzd``) tapped hole — as opposed to a plain cut + cosmetic
    thread — so the model itself carries the thread designation and a drawing
    reads a native hole callout (e.g. ``#5-40 UNC-2B THRU``) with no hard-coded
    map. The hole is placed at the point on the selected face; ``through_all``
    drills the full body.

    Attributes:
        face_point (list[float]): ``[x, y, z]`` in millimetres on the face the
            hole enters. The hole location is that point's projection.
        size (str): Fastener size token, exactly as it appears in the Hole
            Wizard table for the standard (e.g. ``"#5-40"``, ``"1/4-20"``).
        standard (str): Hole Wizard standard — currently ``"ansi_inch"``.
        fastener_type (str): Fastener/hole type within the standard — currently
            ``"tapped_hole"``.
        end_type (str): ``"through_all"`` (only verified value today).
        hole_type (str): Generic Hole Wizard type — currently ``"tap"`` (a
            straight tapped hole).
    """

    face_point: list[float]
    size: str
    standard: str = "ansi_inch"
    fastener_type: str = "tapped_hole"
    end_type: str = "through_all"
    hole_type: str = "tap"


class CreateBomParameters(BaseModel):
    """Parameters for inserting a BOM table into the active document.

    Attributes:
        bom_type (str): ``"parts_only"``, ``"top_level"``, ``"indented"`` or
            ``"flattened"``.
        configuration (str): Configuration the BOM reflects; empty for the
            active configuration (SolidWorks has no implicit default).
        template (str): Path to a ``.sldbomtbt`` BOM template; empty to use
            the installed ``bom-standard`` template.
        file_path (str): CSV output path (``export_bom_csv`` only).
    """

    bom_type: str = "parts_only"
    configuration: str = ""
    template: str = ""
    file_path: str = ""


class InsertComponentParameters(BaseModel):
    """Parameters for inserting a component into the active assembly.

    Attributes:
        file_path (str): Path to the ``.sldprt``/``.sldasm`` file to insert.
            The file is preloaded (``ISldWorks::OpenDoc6``) because
            ``IAssemblyDoc::AddComponent5`` requires it in memory.
        position (list[float]): ``[x, y, z]`` component-origin position in
            assembly space, millimetres. Applied via an exact component
            transform (the ``AddComponent5`` coordinates are bounding-box
            relative and only approximate).
        rotation (list[float]): ``[rx, ry, rz]`` rotation in degrees applied
            about the assembly X, then Y, then Z axes.
        configuration (str): Configuration of the inserted component; empty
            for its active configuration.
    """

    file_path: str
    position: list[float] = [0.0, 0.0, 0.0]
    rotation: list[float] = [0.0, 0.0, 0.0]
    configuration: str = ""


class ComponentRefParameters(BaseModel):
    """Parameters referencing one component of the active assembly.

    Attributes:
        name (str): Component name with instance suffix, e.g. ``"shaft-1"``
            (``"sub-1/part-1"`` for a child of a subassembly). A trailing
            ``"@assembly"`` qualifier is accepted and added automatically
            when missing.
    """

    name: str


class ReplaceComponentParameters(BaseModel):
    """Parameters for replacing a component with another model.

    Attributes:
        name (str): Component to replace, e.g. ``"shaft-1"``. Must be a
            top-level component (API limitation of ``ReplaceComponents2``).
        file_path (str): Path to the replacement ``.sldprt``/``.sldasm``.
            Must not have the same file name as the replaced component.
        configuration (str): Configuration of the replacement to use; empty
            lets SolidWorks match configuration names.
        replace_all (bool): Replace every instance of the selected
            component's model, not just the selected instance.
        reattach_mates (bool): Re-attach existing mates to the replacement.
    """

    name: str
    file_path: str
    configuration: str = ""
    replace_all: bool = False
    reattach_mates: bool = True


class MoveComponentParameters(BaseModel):
    """Parameters for moving a component to a position in assembly space.

    Attributes:
        name (str): Component name, e.g. ``"shaft-1"``.
        position (list[float]): ``[x, y, z]`` in millimetres — the target
            component-origin position (``relative`` false) or a translation
            delta (``relative`` true). The component's rotation is preserved.
        relative (bool): Interpret ``position`` as a delta from the current
            position instead of an absolute target.
    """

    name: str
    position: list[float]
    relative: bool = False


class RotateComponentParameters(BaseModel):
    """Parameters for rotating a component about an axis in assembly space.

    Attributes:
        name (str): Component name, e.g. ``"shaft-1"``.
        angle (float): Rotation angle in degrees (right-hand rule about
            ``axis_vector``).
        axis_vector (list[float]): Direction of the rotation axis in
            assembly space (need not be unit length).
        axis_point (list[float]): ``[x, y, z]`` in millimetres — a point the
            rotation axis passes through.
        mode (str): ``"exact"`` sets the final transform directly
            (``SetTransformAndSolve3``) — mates re-solve but motion does NOT
            propagate through gear/rack-pinion/screw mates (the solver just
            accepts the new phase). ``"kinematic"`` additionally walks the
            assembly's gear mates breadth-first and rotates every coupled
            component about its own mate axis by the stored inverse ratio —
            use it to exercise gear trains deterministically.
    """

    name: str
    angle: float
    axis_vector: list[float] = [0.0, 0.0, 1.0]
    axis_point: list[float] = [0.0, 0.0, 0.0]
    mode: str = "exact"


class ComponentLinearPatternParameters(BaseModel):
    """Parameters for a local linear component pattern in an assembly.

    Attributes:
        components (list[str]): Seed component names, e.g. ``["gear-1"]``.
            Selected under mark 1 (assembly component patterns use marks
            swapped versus part feature patterns).
        count (int): Total number of instances, including the seeds.
        spacing (float): Distance between instances in millimetres.
        direction_name (str): Name of a feature usable as the direction
            reference (reference axis, linear edge owner); selected under
            mark 2. Takes precedence over ``direction_point``.
        direction_point (list[float]): ``[x, y, z]`` in millimetres on the
            direction reference (linear edge or axis); selected under mark 2.
        flip_direction (bool): Reverse the pattern direction
            (``FeatureLinearPattern5`` ``FlipDir1``). The direction reference
            fixes only the LINE; SolidWorks infers the sign, and the
            inference is not contractual — callers must verify instance
            transforms and retry flipped when the copies land on the wrong
            side.
    """

    components: list[str]
    count: int
    spacing: float
    direction_name: str = ""
    direction_point: list[float] = []
    flip_direction: bool = False


class ComponentCircularPatternParameters(BaseModel):
    """Parameters for a local circular component pattern in an assembly.

    Attributes:
        components (list[str]): Seed component names, e.g. ``["gear-1"]``.
            Selected under mark 1 (assembly component patterns use marks
            swapped versus part feature patterns).
        count (int): Total number of instances, including the seeds.
        angle (float): Total angular span in degrees when ``equal_spacing``
            is true, otherwise the spacing between instances in degrees.
        equal_spacing (bool): Distribute instances equally across ``angle``.
        axis_name (str): Name of a reference-axis feature to rotate about;
            selected under mark 2. Takes precedence over ``axis_point``.
        axis_point (list[float]): ``[x, y, z]`` in millimetres on the
            rotation-axis reference (cylindrical face, linear edge or axis);
            selected under mark 2.
    """

    components: list[str]
    count: int
    angle: float = 360.0
    equal_spacing: bool = True
    axis_name: str = ""
    axis_point: list[float] = []


class ComponentChainPatternParameters(BaseModel):
    """Parameters for a chain component pattern (roller chain, belt, etc.).

    Patterns one or two seed components (alternating, for connected linkage)
    along a sketch path via ``IFeatureManager::FeatureChainPattern``. The path
    must be a single connected sketch SEGMENT (e.g. a closed spline) selected as
    ``EXTSKETCHSEGMENT`` under mark 2 -- selecting the sketch feature yields an
    invalid definition. Each group's path-link entities are the seed's two pin
    axes; the alignment plane is a component plane parallel to the chain plane.

    Attributes:
        path_segment (str): Sketch-segment ref for the path, e.g.
            ``"Spline1@Sketch1"`` (selected as ``EXTSKETCHSEGMENT``, mark 2).
        group1_component (str): Group-1 seed component name (mark 1).
        group1_link1 (str): Group-1 first path-link ref, e.g. ``"Axis1@link-1"``
            (mark 256).
        group1_link2 (str): Group-1 second path-link ref (mark 512); required for
            distance-linkage and connected-linkage pitch methods.
        group1_plane (str): Group-1 alignment plane ref, e.g.
            ``"Front Plane@link-1"`` (mark 16384).
        group2_component (str): Group-2 seed component (mark 2048); connected
            linkage only. Empty selects a single-group pattern.
        group2_link1 (str): Group-2 first path-link (mark 4096).
        group2_link2 (str): Group-2 second path-link (mark 8192).
        group2_plane (str): Group-2 alignment plane (mark 32768).
        pitch_method (str): ``"distance"`` | ``"distance_linkage"`` |
            ``"connected_linkage"``.
        fill_path (bool): Fill the whole path (SolidWorks computes the count).
        count (int): Instance count when ``fill_path`` is false.
        spacing (float): Instance spacing in millimetres (distance methods).
        align_method (str): ``"tangent"`` (align to the curve) | ``"seed"``.
        options (str): ``"dynamic"`` (mate instances) | ``"static"``.
        flip_direction (bool): Reverse the traversal direction along the path.
    """

    path_segment: str
    group1_component: str
    group1_link1: str
    group1_link2: str = ""
    group1_plane: str = ""
    group2_component: str = ""
    group2_link1: str = ""
    group2_link2: str = ""
    group2_plane: str = ""
    pitch_method: str = "connected_linkage"
    fill_path: bool = True
    count: int = 0
    spacing: float = 0.0
    align_method: str = "tangent"
    options: str = "dynamic"
    flip_direction: bool = False


class BeltChainParameters(BaseModel):
    """Parameters for a Belt/Chain assembly feature (``swFmBeltAndChain``).

    Creates a SolidWorks Belt/Chain feature coupling two or more pulley/sprocket
    components: with ``engage_belt`` it adds the belt MATES that constrain the
    pulleys to rotate together at the ratio their diameters imply (the coupling
    is only meaningful when the pulleys are FREE, not grounded), plus a belt-path
    sketch. This is the rotation coupling; the visual chain links are a separate
    ``ComponentChainPatternParameters`` pattern.

    The pulley member SolidWorks wants is each pulley's cylindrical FACE (its
    rotation axis), NOT the component object — passing components makes
    ``CreateFeature`` silently return null. The impl resolves each named
    component to its largest-radius cylindrical face whose axis is parallel to
    ``pulley_axis`` (the belt-plane normal).

    Attributes:
        pulley_components (list[str]): Component names of the pulleys/sprockets
            in belt order, e.g. ``["transgear-removable-2",
            "transgear-removable-1"]`` (any ``@assembly`` qualifier is stripped).
            At least two are required.
        pulley_diameters (list[float]): Effective (pitch) belt diameter per
            pulley in MILLIMETRES, same order/length as ``pulley_components``.
            Sets the coupling ratio independent of the picked face's radius.
        location_plane (str): Assembly plane the belt lies in (normal to the
            pulley axes), e.g. ``"Front Plane"``. Resolved to its ``IRefPlane``.
        pulley_axis (str): ``"x"`` | ``"y"`` | ``"z"`` — the pulleys' shared
            rotation axis in assembly space; picks each pulley's coaxial
            cylindrical face. Defaults to ``"z"``.
        pulley_member_axes (list[str]): Named DATUM-AXIS entities (e.g.
            ``"Axis1@sprocket-1"``) to use as the pulley members instead of the
            cylindrical faces, one per pulley. REQUIRED for a correct
            ``engage_belt`` coupling ratio on toothed wheels: with a FACE
            member SolidWorks derives the coupling mate's per-pulley diameters
            from the picked face (the tooth-TIP cylinder) and IGNORES
            ``pulley_diameters`` for the mate — the definition commits them,
            the belt PATH honours them, but the ``MateBeltDim``'s dimensions
            stay face-derived and are not writable (measured live 2026-07-06:
            PulleyDiameters + ModifyDefinition, ModifyMemberParameters, an
            EngageBelt re-author, and direct mate-dimension writes all leave
            the tip ratio). An AXIS member has no diameter to steal, so the
            typed ``pulley_diameters`` drive the coupling exactly (the mate
            records them at RADIUS scale — half the typed value — so the
            post-create check compares ratios, not absolutes). Empty (the
            default) keeps the face route for plain cylindrical pulleys.
        flip_sides (list[bool]): Per-pulley belt-side flip; empty defaults to all
            ``False``. When set, same length as ``pulley_components``.
        engage_belt (bool): Create the belt coupling mates (the operational
            point). Defaults to ``True``.
        create_belt_part (bool): Insert a generated belt part. Defaults to
            ``False`` (the chain-link pattern is the visual).
        use_belt_thickness (bool): Honor a belt thickness. Defaults to ``False``.
        belt_thickness (float): Belt thickness in millimetres when
            ``use_belt_thickness`` is set.
        blank_sketch (bool): Hide the generated belt-path sketch after creation.
            Defaults to ``True`` (the sketch is construction scaffolding).
    """

    pulley_components: list[str]
    pulley_diameters: list[float]
    location_plane: str = "Front Plane"
    pulley_axis: str = "z"
    pulley_member_axes: list[str] = []
    flip_sides: list[bool] = []
    engage_belt: bool = True
    create_belt_part: bool = False
    use_belt_thickness: bool = False
    belt_thickness: float = 0.0
    blank_sketch: bool = True


class MateEntityRef(BaseModel):
    """A reference to one entity to mate, located by name or by point.

    Attributes:
        entity_type (str): ``SelectByID2`` entity-type string, e.g.
            ``"FACE"``, ``"EDGE"``, ``"PLANE"``, ``"AXIS"``, ``"VERTEX"``.
        name (str): Entity name for named entities. Inside a component the
            qualified form is ``"Plane1@shaft-1@assembly"``; a single
            ``"name@component"`` gets the assembly qualifier appended
            automatically. Empty when locating by point.
        point (list[float]): ``[x, y, z]`` in millimetres on the entity
            (view-dependent pick); empty when locating by name.
        mark (int): Explicit selection mark; 0 selects with the mate type's
            default mark (1 for standard mates, 16 for width, 8 for cam).
        component (str): Optional component whose geometry the entity belongs
            to, e.g. ``"drive-train-1/cylinder-gear-1"`` (the ``"sub/part"``
            slash path). When set, the entity is resolved in the part document
            and mapped into assembly context — robust for a part nested in a
            flexible subassembly, where hand-built ``name@a@b@title`` strings
            are malformed and ``SelectByID2`` silently mis-resolves (named
            selection works one level deep but fails at depth two). With
            ``name`` the named reference feature (e.g. ``"Axis3"``, a cam-lobe
            axis) maps via ``IComponent2.GetCorresponding`` — depth-agnostic
            and ~600x faster than a cylindrical-face walk on a fine gear.
            Without ``name`` (motor only) the largest/nearest cylindrical face
            maps via ``IComponent2.GetCorrespondingEntity`` (``point``
            disambiguates). Honored by mate entities and by the motor entity.
    """

    entity_type: str
    name: str = ""
    point: list[float] = []
    mark: int = 0
    component: str = ""


class AddMateParameters(BaseModel):
    """Parameters for adding a standard or mechanical mate.

    Attributes:
        mate_type (str): Standard: ``"coincident"``, ``"concentric"``,
            ``"perpendicular"``, ``"parallel"``, ``"tangent"``,
            ``"distance"``, ``"angle"``, ``"lock"`` or ``"width"``.
            Mechanical: ``"cam_follower"``, ``"gear"``, ``"rack_pinion"``
            or ``"screw"``.
        entities (list[MateEntityRef]): Entities to mate (two for standard
            mates; width mates take the two width faces plus the two tab
            faces).
        alignment (str): ``"aligned"``, ``"anti_aligned"`` or ``"closest"``.
        flip (bool): Flip to the other valid mate position (distance/angle).
        distance (float): Distance value in millimetres (distance mates).
        distance_limits (list[float]): ``[min, max]`` in millimetres for a
            limit-distance mate; empty for a fixed distance.
        angle (float): Angle value in degrees (angle mates).
        angle_limits (list[float]): ``[min, max]`` in degrees for a
            limit-angle mate; empty for a fixed angle.
        lock_rotation (bool): Lock component rotation (concentric mates).
        gear_ratio (list[float]): ``[numerator, denominator]`` tooth/ratio
            values for gear mates; empty derives the ratio from the
            selected geometry.
        pinion_pitch_diameter (float): Pinion pitch diameter in millimetres
            (rack_pinion mates); 0 leaves the SolidWorks default.
        rack_travel_per_revolution (float): Rack travel in millimetres per
            pinion revolution (rack_pinion mates, alternative to
            ``pinion_pitch_diameter``); 0 leaves the SolidWorks default.
        distance_per_revolution (float): Translation in millimetres per
            revolution (screw mates); 0 leaves the SolidWorks default.
    """

    mate_type: str
    entities: list[MateEntityRef]
    alignment: str = "closest"
    flip: bool = False
    distance: float = 0.0
    distance_limits: list[float] = []
    angle: float = 0.0
    angle_limits: list[float] = []
    lock_rotation: bool = False
    gear_ratio: list[float] = []
    pinion_pitch_diameter: float = 0.0
    rack_travel_per_revolution: float = 0.0
    distance_per_revolution: float = 0.0


class MateRefParameters(BaseModel):
    """Parameters referencing one mate feature by name.

    Attributes:
        name (str): Mate feature name as shown in the tree, e.g.
            ``"Coincident1"`` or ``"Concentric2"``.
    """

    name: str


class SuppressMateParameters(BaseModel):
    """Parameters for suppressing or unsuppressing a mate.

    Attributes:
        name (str): Mate feature name, e.g. ``"Coincident1"``.
        suppress (bool): ``True`` to suppress, ``False`` to unsuppress.
        component (str): Optional component whose subassembly document owns
            the mate, e.g. ``"drive-train-1"``. When set, the mate is
            resolved and suppressed inside that subassembly's model document
            instead of the top-level tree — the only way to free a
            driving-dimension mate that lives inside a flexible subassembly
            (its name, e.g. ``"Distance34"``, is the standalone name in the
            sub, not a qualified top-level name). The subassembly is not
            saved, so its on-disk fully-defined state is preserved.
        configuration (str): Optional configuration name to scope the
            suppression to. Empty (default) suppresses across **all**
            configurations (``swAllConfiguration``); a name suppresses only
            in that configuration (``swSpecifyConfiguration``), leaving the
            mate's state in every other configuration untouched — the basis
            for engagement states (``rest``/``cone_disengaged``/
            ``pinion_engaged``). The named configuration is made active for
            the ``IsSuppressed`` readback, then the prior active
            configuration is restored. Not supported together with
            ``component`` (a sub-document's own configurations are a separate
            namespace).
    """

    name: str
    suppress: bool = True
    component: str = ""
    configuration: str = ""


class SetComponentSolvingParameters(BaseModel):
    """Parameters for setting a subassembly component's solve mode.

    Attributes:
        name (str): Component name with instance suffix, e.g.
            ``"drive-train-1"`` (``"sub-1/inner-1"`` for a nested child).
        solving (str): ``"flexible"`` solves the subassembly's internal mates
            simultaneously with the parent (its parts move within their DOF —
            required for a parent motor or cross-assembly mate to drive parts
            inside it); ``"rigid"`` treats the subassembly as a single solid.
            A fixed subassembly cannot be flexible — float it first.
    """

    name: str
    solving: str = "flexible"


class SetComponentConfigurationParameters(BaseModel):
    """Parameters for setting which child configuration a component references.

    Attributes:
        name (str): Component name with instance suffix, e.g.
            ``"drive-train-1"`` (``"sub-1/inner-1"`` for a nested child).
        configuration (str): Name of the child configuration the component
            should reference in the assembly's **active** configuration. An
            empty string restores the component's default referenced
            configuration. Because the change is scoped to the active assembly
            configuration, the same component can reference different child
            configurations per assembly configuration — the basis for
            top-level engagement states (e.g. ``harmonic-analyzer``'s
            ``cone_disengaged`` config points ``drive-train-1`` at the
            drive-train's own ``cone_disengaged`` config, while ``Default``
            keeps it at ``Default``).
    """

    name: str
    configuration: str = ""


class MotionStudyParameters(BaseModel):
    """Parameters for creating (or re-selecting) a motion study.

    Attributes:
        name (str): Study name. Empty creates a new study and uses the
            SolidWorks-assigned name (returned in the result).
        study_type (str): ``"animation"``, ``"physical_simulation"``
            (Basic Motion) or ``"motion_analysis"`` (SOLIDWORKS Motion —
            the only type that solves spring/force/gravity dynamics;
            requires the SOLIDWORKS Motion add-in).
        duration (float): Study duration in seconds.
        activate (bool): Activate the study after creating it (required
            before adding simulation features).
    """

    name: str = ""
    study_type: str = "motion_analysis"
    duration: float = 5.0
    activate: bool = True


class MotionStudyRefParameters(BaseModel):
    """Parameters referencing one motion study by name.

    Attributes:
        name (str): Study name; empty targets the active study.
    """

    name: str = ""


class MotionMotorParameters(BaseModel):
    """Parameters for adding a motor to a motion study.

    Attributes:
        motor_type (str): ``"rotary"`` or ``"linear"``.
        entity (MateEntityRef): Face/edge/axis that fixes the motor's
            location and direction (selected by name or pick point), as in
            the SolidWorks motor dialog.
        speed (float): Constant speed — RPM for a rotary motor, millimetres
            per second for a linear motor.
        reverse (bool): Reverse the motor direction.
        component (str): Optional name of the moving component the motor
            drives (``RelativeComponent``); empty lets SolidWorks infer it
            from the selected face.
        study_name (str): Target study name; empty targets the active study.
    """

    motor_type: str = "rotary"
    entity: MateEntityRef
    speed: float = 10.0
    reverse: bool = False
    component: str = ""
    study_name: str = ""
    motion_function: str = "constant"
    amplitude: float = 0.0
    frequency: float = 0.0


class MotionGravityParameters(BaseModel):
    """Parameters for adding gravity to a motion study.

    Attributes:
        axis (str): Gravity axis ``"x"``, ``"y"`` or ``"z"``.
        strength (float): Gravitational acceleration in metres per second
            squared (SI); defaults to standard gravity.
        reverse (bool): Reverse the gravity direction along the axis.
        study_name (str): Target study name; empty targets the active study.
    """

    axis: str = "y"
    strength: float = 9.80665
    reverse: bool = True
    study_name: str = ""


class MotionTimeParameters(BaseModel):
    """Parameters for positioning a motion study at a point in time.

    Attributes:
        time (float): Time in seconds along the (calculated) study.
        study_name (str): Target study name; empty targets the active study.
    """

    time: float
    study_name: str = ""


class MotionExportParameters(BaseModel):
    """Parameters for exporting a motion study animation to a video file.

    Attributes:
        file_path (str): Output video path; the suffix picks the container —
            ``.mp4`` (recommended), ``.mkv`` or ``.flv``. ``.avi`` is rejected
            (SOLIDWORKS only writes it via the interactive codec dialog).
        study_name (str): Target study name; empty targets the active study.
        frames_per_second (float): Animation frame rate written to the file.
    """

    file_path: str
    study_name: str = ""
    frames_per_second: float = 25.0


class MotionSpringParameters(BaseModel):
    """Parameters for adding a spring force element to a motion study.

    A motion spring applies a force (linear) or torque (torsional) between
    two endpoints proportional to its stretch from the free length/angle.
    Unlike the cosmetic helical part geometry, this is a real force element
    the MotionAnalysis solver balances.

    Attributes:
        spring_type (str): ``"linear"`` or ``"torsional"``.
        endpoints (list[MateEntityRef]): The two endpoint entities (faces,
            edges or vertices), selected by name or pick point.
        spring_constant (float): Stiffness k — N/m for a linear spring,
            N·m/rad for a torsional spring (SI, passed verbatim).
        free_length (float | None): Linear spring rest length in millimetres
            (the spring exerts no force at this length); ``None`` keeps the
            modeled initial distance. Ignored for torsional springs.
        free_angle (float | None): Torsional spring rest angle in degrees;
            ``None`` keeps the modeled initial angle. Ignored for linear.
        damping_constant (float): When > 0, enables the spring's damper and
            sets its damping coefficient (N·s/m); 0 leaves the damper off.
        coil_diameter (float): Optional cosmetic mean coil diameter in mm
            (set when > 0).
        wire_diameter (float): Optional cosmetic wire diameter in mm
            (set when > 0).
        number_of_coils (float): Optional cosmetic active coil count
            (set when > 0).
        reverse (bool): Reverse the spring direction.
        study_name (str): Target study name; empty targets the active study.
    """

    spring_type: str = "linear"
    endpoints: list[MateEntityRef]
    spring_constant: float
    free_length: float | None = None
    free_angle: float | None = None
    damping_constant: float = 0.0
    coil_diameter: float = 0.0
    wire_diameter: float = 0.0
    number_of_coils: float = 0.0
    reverse: bool = False
    study_name: str = ""


class MotionDamperParameters(BaseModel):
    """Parameters for adding a damper force element to a motion study.

    A damper applies a resistive force (linear) or torque (torsional)
    between two endpoints proportional to their relative velocity.

    Attributes:
        damper_type (str): ``"linear"`` or ``"torsional"``.
        endpoints (list[MateEntityRef]): The two endpoint entities, selected
            by name or pick point.
        damping_constant (float): Damping coefficient — N·s/m for a linear
            damper, N·m·s/rad for a torsional damper (SI, passed verbatim).
        study_name (str): Target study name; empty targets the active study.
    """

    damper_type: str = "linear"
    endpoints: list[MateEntityRef]
    damping_constant: float
    study_name: str = ""


class MotionForceParameters(BaseModel):
    """Parameters for adding an applied force/torque to a motion study.

    Applies a constant-magnitude action force (linear) or torque about an
    axis (torsional) at a location on a component.

    Attributes:
        force_type (str): ``"linear_force"`` or ``"torque"``.
        action (MateEntityRef): The face/edge/vertex giving the force's
            action location (and, for a torque, its axis), selected by name
            or pick point.
        magnitude (float): Constant magnitude — newtons for a linear force,
            newton-metres for a torque (SI, passed verbatim).
        action_only (bool): ``True`` applies the force to one component only;
            ``False`` applies an action-and-reaction pair.
        reverse (bool): Reverse the force direction.
        study_name (str): Target study name; empty targets the active study.
    """

    force_type: str = "linear_force"
    action: MateEntityRef
    magnitude: float
    action_only: bool = True
    reverse: bool = False
    study_name: str = ""


class MassProperties(BaseModel):
    """Mass properties information.

    Attributes:
        center_of_mass (list[float]): The center of mass value.
        mass (float): The mass value.
        moments_of_inertia (dict[str, float]): The moments of inertia value.
        principal_axes (dict[str, list[float]] | None): The principal axes value.
        surface_area (float): The surface area value.
        volume (float): The volume value.
    """

    volume: float
    surface_area: float
    mass: float
    center_of_mass: list[float]  # [x, y, z]
    moments_of_inertia: dict[str, float]
    principal_axes: dict[str, list[float]] | None = None


class SolidWorksAdapter(ABC):
    """Base adapter interface for SolidWorks integration.

    Args:
        config (object | None): Configuration values for the operation. Defaults to None.

    Attributes:
        _metrics (Any): The metrics value.
        config (Any): The config value.
        config_dict (Any): The config dict value.
    """

    def __init__(self, config: object | None = None):
        """Initialize adapter with configuration.

        Args:
            config (object | None): Configuration values for the operation. Defaults to None.
        """
        if config is None:
            normalized_config: dict[str, Any] = {}
        elif isinstance(config, Mapping):
            normalized_config = dict(config)
        elif hasattr(config, "model_dump"):
            normalized_config = dict(config.model_dump())
        else:
            normalized_config = {}

        # Preserve original config object for compatibility with tests and
        # call sites that compare object identity/equality.
        self.config = config
        # Keep a normalized mapping for adapter internals.
        self.config_dict = normalized_config
        self._metrics = {
            "operations_count": 0,
            "errors_count": 0,
            "average_response_time": 0.0,
        }
        # SolidWorks-as-Code session logging. Set soc_session_id to enable
        # automatic ToolCallRecord writes for every adapter operation.
        self.soc_session_id: str | None = None
        self.soc_db_path: Path | None = None

    # Connection Management
    @abstractmethod
    async def connect(self) -> None:
        """Connect to SolidWorks application.

        Returns:
            None: None.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from SolidWorks application.

        Returns:
            None: None.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to SolidWorks.

        Returns:
            bool: True if connected, otherwise False.
        """
        pass

    @abstractmethod
    async def health_check(self) -> AdapterHealth:
        """Get adapter health status.

        Returns:
            AdapterHealth: The result produced by the operation.
        """
        pass

    # Model Operations
    @abstractmethod
    async def open_model(self, file_path: str) -> AdapterResult[SolidWorksModel]:
        """Open a SolidWorks model (part, assembly, or drawing).

        Args:
            file_path (str): Path to the target file.

        Returns:
            AdapterResult[SolidWorksModel]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def close_model(self, save: bool = False) -> AdapterResult[None]:
        """Close the current model.

        Args:
            save (bool): The save value. Defaults to False.

        Returns:
            AdapterResult[None]: The result produced by the operation.
        """
        pass

    async def save_file(self, file_path: str | None = None) -> AdapterResult[Any]:
        """Save the active model to the existing path or the provided path.

        Args:
            file_path (str | None): Path to the target file. Defaults to None.

        Returns:
            AdapterResult[Any]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="save_file is not implemented by this adapter",
        )

    @abstractmethod
    async def get_model_info(self) -> AdapterResult[dict[str, Any]]:
        """Get metadata for the active model.

        Returns:
            AdapterResult[dict[str, Any]]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def list_features(
        self, include_suppressed: bool = False
    ) -> AdapterResult[list[dict[str, Any]]]:
        """List model features from the feature tree.

        Args:
            include_suppressed (bool): The include suppressed value. Defaults to False.

        Returns:
            AdapterResult[list[dict[str, Any]]]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def list_configurations(self) -> AdapterResult[list[str]]:
        """List configuration names for the active model.

        Returns:
            AdapterResult[list[str]]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_part(
        self, name: str | None = None, units: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new part document.

        Args:
            name (str | None): The name value. Defaults to None.
            units (str | None): The units value. Defaults to None.

        Returns:
            AdapterResult[SolidWorksModel]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_assembly(
        self, name: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new assembly document.

        Args:
            name (str | None): The name value. Defaults to None.

        Returns:
            AdapterResult[SolidWorksModel]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_drawing(
        self, name: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new drawing document.

        Args:
            name (str | None): The name value. Defaults to None.

        Returns:
            AdapterResult[SolidWorksModel]: The result produced by the operation.
        """
        pass

    # Feature Operations
    @abstractmethod
    async def create_extrusion(
        self, params: ExtrusionParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create an extrusion feature.

        Args:
            params (ExtrusionParameters): The params value.

        Returns:
            AdapterResult[SolidWorksFeature]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_revolve(
        self, params: RevolveParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create a revolve feature.

        Args:
            params (RevolveParameters): The params value.

        Returns:
            AdapterResult[SolidWorksFeature]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_sweep(
        self, params: SweepParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create a sweep feature.

        Args:
            params (SweepParameters): The params value.

        Returns:
            AdapterResult[SolidWorksFeature]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def create_loft(
        self, params: LoftParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create a loft feature.

        Args:
            params (LoftParameters): The params value.

        Returns:
            AdapterResult[SolidWorksFeature]: The result produced by the operation.
        """
        pass

    # Sketch Operations
    @abstractmethod
    async def create_sketch(self, plane: str) -> AdapterResult[str]:
        """Create a new sketch on the specified plane.

        Args:
            plane (str): The plane value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def add_line(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> AdapterResult[str]:
        """Add a line to the current sketch.

        Args:
            x1 (float): The x1 value.
            y1 (float): The y1 value.
            x2 (float): The x2 value.
            y2 (float): The y2 value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def add_circle(
        self, center_x: float, center_y: float, radius: float
    ) -> AdapterResult[str]:
        """Add a circle to the current sketch.

        Args:
            center_x (float): The center x value.
            center_y (float): The center y value.
            radius (float): The radius value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def add_rectangle(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> AdapterResult[str]:
        """Add a rectangle to the current sketch.

        Args:
            x1 (float): The x1 value.
            y1 (float): The y1 value.
            x2 (float): The x2 value.
            y2 (float): The y2 value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        pass

    async def add_arc(
        self,
        center_x: float,
        center_y: float,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
    ) -> AdapterResult[str]:
        """Add an arc to the current sketch.

        Args:
            center_x (float): The center x value.
            center_y (float): The center y value.
            start_x (float): The start x value.
            start_y (float): The start y value.
            end_x (float): The end x value.
            end_y (float): The end y value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_arc is not implemented by this adapter",
        )

    async def add_spline(self, points: list[dict[str, float]]) -> AdapterResult[str]:
        """Add a spline through the provided points.

        Args:
            points (list[dict[str, float]]): The points value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_spline is not implemented by this adapter",
        )

    async def add_centerline(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> AdapterResult[str]:
        """Add a centerline to the current sketch.

        Args:
            x1 (float): The x1 value.
            y1 (float): The y1 value.
            x2 (float): The x2 value.
            y2 (float): The y2 value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_centerline is not implemented by this adapter",
        )

    async def add_polygon(
        self, center_x: float, center_y: float, radius: float, sides: int
    ) -> AdapterResult[str]:
        """Add a regular polygon to the current sketch.

        Args:
            center_x (float): The center x value.
            center_y (float): The center y value.
            radius (float): The radius value.
            sides (int): The sides value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_polygon is not implemented by this adapter",
        )

    async def add_ellipse(
        self,
        center_x: float,
        center_y: float,
        major_axis: float,
        minor_axis: float,
    ) -> AdapterResult[str]:
        """Add an ellipse to the current sketch.

        Args:
            center_x (float): The center x value.
            center_y (float): The center y value.
            major_axis (float): The major axis value.
            minor_axis (float): The minor axis value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_ellipse is not implemented by this adapter",
        )

    async def add_sketch_constraint(
        self,
        entity1: str,
        entity2: str | None,
        relation_type: str,
        entity3: str | None = None,
    ) -> AdapterResult[str]:
        """Apply a geometric constraint between sketch entities.

        Args:
            entity1 (str): The entity1 value.
            entity2 (str | None): The entity2 value.
            relation_type (str): The relation type value.
            entity3 (str | None): Third entity ID — only used by the
                ``symmetric`` relation (the centerline of symmetry). All
                other relation types reject a non-null ``entity3``.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_sketch_constraint is not implemented by this adapter",
        )

    async def add_sketch_dimension(
        self,
        entity1: str,
        entity2: str | None,
        dimension_type: str,
        value: float,
    ) -> AdapterResult[str]:
        """Add a sketch dimension.

        Args:
            entity1 (str): The entity1 value.
            entity2 (str | None): The entity2 value.
            dimension_type (str): The dimension type value.
            value (float): The value value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_sketch_dimension is not implemented by this adapter",
        )

    async def check_sketch_fully_defined(
        self, sketch_name: str | None = None
    ) -> AdapterResult[dict[str, Any]]:
        """Check whether a sketch is fully defined.

        Args:
            sketch_name (str | None): Optional sketch name to inspect. Defaults to None.

        Returns:
            AdapterResult[dict[str, Any]]: Definition status payload.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="check_sketch_fully_defined is not implemented by this adapter",
        )

    async def get_over_defining_relations(self) -> AdapterResult[dict[str, Any]]:
        """List the over-defining relations of the active sketch.

        Returns:
            AdapterResult[dict[str, Any]]: ``{"count": int, "relations":
            [{"relation_type": int, "relation_name": str | None}, ...]}``.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="get_over_defining_relations is not implemented by this adapter",
        )

    async def sketch_linear_pattern(
        self,
        entities: list[str],
        direction_x: float,
        direction_y: float,
        spacing: float,
        count: int,
    ) -> AdapterResult[str]:
        """Create a linear pattern of sketch entities.

        Args:
            entities (list[str]): The entities value.
            direction_x (float): The direction x value.
            direction_y (float): The direction y value.
            spacing (float): The spacing value.
            count (int): The count value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="sketch_linear_pattern is not implemented by this adapter",
        )

    async def sketch_circular_pattern(
        self,
        entities: list[str],
        angle: float,
        count: int,
    ) -> AdapterResult[str]:
        """Create a circular pattern of sketch entities around the sketch origin.

        The rotation axis is always the sketch origin — SW's
        ``CreateCircularSketchStepAndRepeat`` has no pattern-centre
        parameter and derives the axis from the seed's geometry. Place
        the seed entity at the desired radius from the origin.

        Args:
            entities (list[str]): The entities value.
            angle (float): The angle value.
            count (int): The count value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="sketch_circular_pattern is not implemented by this adapter",
        )

    async def sketch_mirror(
        self, entities: list[str], mirror_line: str
    ) -> AdapterResult[str]:
        """Mirror sketch entities about a mirror line.

        Args:
            entities (list[str]): The entities value.
            mirror_line (str): The mirror line value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="sketch_mirror is not implemented by this adapter",
        )

    async def sketch_offset(
        self,
        entities: list[str],
        offset_distance: float,
        reverse_direction: bool,
    ) -> AdapterResult[str]:
        """Offset sketch entities.

        Args:
            entities (list[str]): The entities value.
            offset_distance (float): The offset distance value.
            reverse_direction (bool): The reverse direction value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="sketch_offset is not implemented by this adapter",
        )

    async def add_sketch_circle(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        construction: bool = False,
    ) -> AdapterResult[str]:
        """Alias for add_circle used by some tool flows.

        Args:
            center_x (float): The center x value.
            center_y (float): The center y value.
            radius (float): The radius value.
            construction (bool): The construction value. Defaults to False.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return await self.add_circle(center_x, center_y, radius)

    async def create_cut(self, sketch_name: str, depth: float) -> AdapterResult[str]:
        """Create a cut feature from an existing sketch.

        Args:
            sketch_name (str): The sketch name value.
            depth (float): The depth value.

        Returns:
            AdapterResult[str]: The result produced by the operation.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_cut is not implemented by this adapter",
        )

    async def create_cut_extrude(
        self, params: ExtrusionParameters
    ) -> AdapterResult[Any]:
        """Create a cut-extrude feature from the active sketch.

        Cuts material from the current solid body using the active sketch profile.
        Equivalent to SolidWorks Insert > Cut > Extrude.

        Args:
            params (ExtrusionParameters): Depth and direction parameters.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_cut_extrude is not implemented by this adapter",
        )

    async def add_fillet(
        self,
        radius: float,
        edge_points: list[list[float]],
        propagate: bool = True,
    ) -> AdapterResult[Any]:
        """Add a fillet feature to edges located by coordinate.

        Rounds edges of the current solid body with the given radius. Each edge
        is located by a point ``[x, y, z]`` (millimetres) lying on it, since
        SolidWorks edges have no caller-stable name.

        Args:
            radius (float): Fillet radius in millimeters.
            edge_points (list[list[float]]): Points ``[x, y, z]`` in mm, one per
                edge to fillet.
            propagate (bool): Propagate the fillet along tangent-continuous
                edges (the UI default). Pass ``False`` and select every edge
                explicitly for a closed tangent-continuous loop — propagation
                fails to close on such loops (``FeatureFillet3`` returns null
                for any seed on them), while the same fillet succeeds with all
                loop edges selected and no propagation.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_fillet is not implemented by this adapter",
        )

    async def add_chamfer(
        self,
        distance: float,
        edge_points: list[list[float]],
        face_points: list[list[float]] | None = None,
        tangent_propagation: bool = False,
    ) -> AdapterResult[Any]:
        """Add an angle-distance (45°) chamfer to edges and/or whole faces.

        Args:
            distance (float): Chamfer distance in millimeters.
            edge_points (list[list[float]]): Points ``[x, y, z]`` in mm, one per
                edge to chamfer.
            face_points (list[list[float]] | None): Points ``[x, y, z]`` in mm,
                one per face whose edges are all chamfered. ``None`` chamfers
                only the listed edges.
            tangent_propagation (bool): Propagate the chamfer along
                tangent-connected edges (the GUI default).

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_chamfer is not implemented by this adapter",
        )

    async def mirror_feature(
        self, params: MirrorFeatureParameters
    ) -> AdapterResult[Any]:
        """Mirror existing features about a reference plane.

        Args:
            params (MirrorFeatureParameters): Mirror plane, features, options.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="mirror_feature is not implemented by this adapter",
        )

    async def circular_pattern_feature(
        self, params: CircularPatternParameters
    ) -> AdapterResult[Any]:
        """Create a circular pattern of features about an axis.

        Args:
            params (CircularPatternParameters): Axis, features, count, angle.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="circular_pattern_feature is not implemented by this adapter",
        )

    async def linear_pattern_feature(
        self, params: LinearPatternParameters
    ) -> AdapterResult[Any]:
        """Create a linear pattern of features along a direction.

        Args:
            params (LinearPatternParameters): Direction, features, count, spacing.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="linear_pattern_feature is not implemented by this adapter",
        )

    async def shell(self, params: ShellParameters) -> AdapterResult[Any]:
        """Hollow out the solid body, optionally removing faces.

        Args:
            params (ShellParameters): Thickness, faces to remove, direction.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="shell is not implemented by this adapter",
        )

    async def draft(self, params: DraftParameters) -> AdapterResult[Any]:
        """Apply a neutral-plane draft to selected faces.

        Args:
            params (DraftParameters): Angle, neutral plane, faces, direction.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="draft is not implemented by this adapter",
        )

    async def create_plane(self, params: CreatePlaneParameters) -> AdapterResult[Any]:
        """Create a constraint-based reference plane.

        Args:
            params (CreatePlaneParameters): Mode, references, distance/angle.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_plane is not implemented by this adapter",
        )

    async def create_axis(self, params: CreateAxisParameters) -> AdapterResult[Any]:
        """Create a reference axis.

        Args:
            params (CreateAxisParameters): Mode and references.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_axis is not implemented by this adapter",
        )

    async def import_dxf_dwg(
        self, params: ImportDxfDwgParameters
    ) -> AdapterResult[Any]:
        """Import a DXF/DWG file into the active part as a sketch feature.

        Selects ``params.plane`` and inserts the file's 2D geometry on it via
        ``IFeatureManager::InsertDwgOrDxfFile2``.

        Args:
            params (ImportDxfDwgParameters): File path, plane, scale/position,
                and import options.

        Returns:
            AdapterResult: Feature result (the inserted DXF/DWG sketch feature)
            or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="import_dxf_dwg is not implemented by this adapter",
        )

    async def rename_feature(
        self, params: RenameFeatureParameters
    ) -> AdapterResult[Any]:
        """Rename a feature in the active document's tree.

        Args:
            params (RenameFeatureParameters): Old and new feature names.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="rename_feature is not implemented by this adapter",
        )

    async def create_reference_point(
        self, params: CreateReferencePointParameters
    ) -> AdapterResult[Any]:
        """Create one or more reference points.

        Args:
            params (CreateReferencePointParameters): Mode, references,
                distribution.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_reference_point is not implemented by this adapter",
        )

    async def create_coordinate_system(
        self, params: CreateCoordinateSystemParameters
    ) -> AdapterResult[Any]:
        """Create a coordinate-system feature at a numeric position/rotation.

        Args:
            params (CreateCoordinateSystemParameters): Position and rotation.

        Returns:
            AdapterResult: Feature result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_coordinate_system is not implemented by this adapter",
        )

    async def create_equation_driven_curve(
        self, params: CreateEquationCurveParameters
    ) -> AdapterResult[str]:
        """Create an equation-driven curve in the active sketch.

        Args:
            params (CreateEquationCurveParameters): Expressions and range.

        Returns:
            AdapterResult[str]: Registered sketch-entity ID or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_equation_driven_curve is not implemented by this adapter",
        )

    async def set_global_variable(
        self, params: SetGlobalVariableParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Add or update a global variable in the equation manager.

        Args:
            params (SetGlobalVariableParameters): Name, expression, scope.

        Returns:
            AdapterResult[dict[str, Any]]: Equation index/text or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="set_global_variable is not implemented by this adapter",
        )

    async def create_equation(
        self, params: CreateEquationParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Add or update a driving equation in the equation manager.

        Args:
            params (CreateEquationParameters): Equation text and scope.

        Returns:
            AdapterResult[dict[str, Any]]: Equation index/text or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_equation is not implemented by this adapter",
        )

    async def create_configuration(
        self, params: CreateConfigurationParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Create a configuration on the active model.

        Args:
            params (CreateConfigurationParameters): Name and metadata.

        Returns:
            AdapterResult[dict[str, Any]]: Configuration name or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_configuration is not implemented by this adapter",
        )

    async def set_active_configuration(
        self, name: str
    ) -> AdapterResult[dict[str, Any]]:
        """Activate a configuration by name and rebuild.

        Args:
            name (str): Configuration name to activate.

        Returns:
            AdapterResult[dict[str, Any]]: Activation details or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="set_active_configuration is not implemented by this adapter",
        )

    async def measure(self, params: MeasureParameters) -> AdapterResult[dict[str, Any]]:
        """Measure the given entities (distances, lengths, areas, angles).

        Args:
            params (MeasureParameters): Entities and arc-distance option.

        Returns:
            AdapterResult[dict[str, Any]]: Measured values (millimetres,
            mm², degrees) or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="measure is not implemented by this adapter",
        )

    async def apply_material(
        self, params: ApplyMaterialParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Assign a material to the active part.

        Args:
            params (ApplyMaterialParameters): Material, database, scope.

        Returns:
            AdapterResult[dict[str, Any]]: Applied material details or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="apply_material is not implemented by this adapter",
        )

    async def add_thread(
        self, params: AddThreadParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Add a cosmetic thread to a circular edge.

        Args:
            params (AddThreadParameters): Edge location and thread spec.

        Returns:
            AdapterResult[dict[str, Any]]: Thread feature details or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_thread is not implemented by this adapter",
        )

    async def create_bom(
        self, params: CreateBomParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Insert a BOM table and return its contents.

        Args:
            params (CreateBomParameters): BOM type, configuration, template.

        Returns:
            AdapterResult[dict[str, Any]]: Table contents or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_bom is not implemented by this adapter",
        )

    async def export_bom_csv(
        self, params: CreateBomParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Insert a BOM table and write its contents to a CSV file.

        Args:
            params (CreateBomParameters): BOM options plus ``file_path``.

        Returns:
            AdapterResult[dict[str, Any]]: Export summary or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="export_bom_csv is not implemented by this adapter",
        )

    async def insert_component(
        self, params: InsertComponentParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Insert a component into the active assembly.

        Args:
            params (InsertComponentParameters): File, position, rotation,
                configuration.

        Returns:
            AdapterResult[dict[str, Any]]: Inserted component details or
            error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="insert_component is not implemented by this adapter",
        )

    async def remove_component(
        self, params: ComponentRefParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Delete a component from the active assembly.

        Args:
            params (ComponentRefParameters): Component name.

        Returns:
            AdapterResult[dict[str, Any]]: Removal confirmation or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="remove_component is not implemented by this adapter",
        )

    async def replace_component(
        self, params: ReplaceComponentParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Replace a component with another model.

        Args:
            params (ReplaceComponentParameters): Component, replacement file
                and options.

        Returns:
            AdapterResult[dict[str, Any]]: Replacement details or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="replace_component is not implemented by this adapter",
        )

    async def move_component(
        self, params: MoveComponentParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Move a component to a position in assembly space.

        Args:
            params (MoveComponentParameters): Component and target position.

        Returns:
            AdapterResult[dict[str, Any]]: Resulting position or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="move_component is not implemented by this adapter",
        )

    async def rotate_component(
        self, params: RotateComponentParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Rotate a component about an axis in assembly space.

        Args:
            params (RotateComponentParameters): Component, axis and angle.

        Returns:
            AdapterResult[dict[str, Any]]: Rotation confirmation or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="rotate_component is not implemented by this adapter",
        )

    async def fix_component(
        self, params: ComponentRefParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Fix a component (make it immovable).

        Args:
            params (ComponentRefParameters): Component name.

        Returns:
            AdapterResult[dict[str, Any]]: Fixed-state confirmation or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="fix_component is not implemented by this adapter",
        )

    async def float_component(
        self, params: ComponentRefParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Float a component (make it movable).

        Args:
            params (ComponentRefParameters): Component name.

        Returns:
            AdapterResult[dict[str, Any]]: Float-state confirmation or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="float_component is not implemented by this adapter",
        )

    async def pattern_components_linear(
        self, params: ComponentLinearPatternParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create a local linear component pattern in the active assembly.

        Args:
            params (ComponentLinearPatternParameters): Seeds, count, spacing
                and direction reference.

        Returns:
            AdapterResult[SolidWorksFeature]: Pattern feature or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pattern_components_linear is not implemented by this adapter",
        )

    async def pattern_components_circular(
        self, params: ComponentCircularPatternParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create a local circular component pattern in the active assembly.

        Args:
            params (ComponentCircularPatternParameters): Seeds, count, angle
                and axis reference.

        Returns:
            AdapterResult[SolidWorksFeature]: Pattern feature or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pattern_components_circular is not implemented by this adapter",
        )

    async def pattern_components_chain(
        self, params: ComponentChainPatternParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create a chain component pattern (roller chain, belt) in the active
        assembly along a sketch path.

        Args:
            params (ComponentChainPatternParameters): Path segment, one or two
                seed groups (component + path-links + alignment plane), pitch
                method, fill/count/spacing and options.

        Returns:
            AdapterResult[SolidWorksFeature]: Pattern feature or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="pattern_components_chain is not implemented by this adapter",
        )

    async def insert_belt_chain(
        self, params: BeltChainParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Create a Belt/Chain assembly feature coupling pulley/sprocket
        components in the active assembly.

        Args:
            params (BeltChainParameters): Pulley components + pitch diameters,
                belt-location plane, engage/create-belt-part flags.

        Returns:
            AdapterResult[SolidWorksFeature]: Belt feature or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="insert_belt_chain is not implemented by this adapter",
        )

    async def add_mate(
        self, params: AddMateParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Add a standard mate between selected entities.

        Args:
            params (AddMateParameters): Mate type, entities and options.

        Returns:
            AdapterResult[dict[str, Any]]: Created mate details or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_mate is not implemented by this adapter",
        )

    async def list_mates(self) -> AdapterResult[list[dict[str, Any]]]:
        """List the mates of the active assembly.

        Returns:
            AdapterResult[list[dict[str, Any]]]: One entry per mate (name,
            type, suppression state) or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="list_mates is not implemented by this adapter",
        )

    async def delete_mate(
        self, params: MateRefParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Delete a mate by feature name.

        Args:
            params (MateRefParameters): Mate feature name.

        Returns:
            AdapterResult[dict[str, Any]]: Deletion confirmation or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="delete_mate is not implemented by this adapter",
        )

    async def suppress_mate(
        self, params: SuppressMateParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Suppress or unsuppress a mate by feature name.

        Args:
            params (SuppressMateParameters): Mate name and target state.

        Returns:
            AdapterResult[dict[str, Any]]: Resulting state or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="suppress_mate is not implemented by this adapter",
        )

    async def set_component_solving(
        self, params: SetComponentSolvingParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Set a subassembly component's solve mode (rigid or flexible).

        Args:
            params (SetComponentSolvingParameters): Component name and mode.

        Returns:
            AdapterResult[dict[str, Any]]: Resulting solve mode or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="set_component_solving is not implemented by this adapter",
        )

    async def set_component_configuration(
        self, params: SetComponentConfigurationParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Set which child configuration a component references.

        Scoped to the assembly's active configuration, so the same component
        can reference different child configurations in different assembly
        configurations.

        Args:
            params (SetComponentConfigurationParameters): Component name and
                target child configuration name.

        Returns:
            AdapterResult[dict[str, Any]]: Resulting referenced configuration
            or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="set_component_configuration is not implemented by this adapter",
        )

    # Motion-study Operations
    async def create_motion_study(
        self, params: MotionStudyParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Create (or re-select) a motion study and set its analysis type.

        Args:
            params (MotionStudyParameters): Study name, type and duration.

        Returns:
            AdapterResult[dict[str, Any]]: Study name/type or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="create_motion_study is not implemented by this adapter",
        )

    async def ensure_motion_addin(self) -> AdapterResult[dict[str, Any]]:
        """Ensure the SOLIDWORKS Motion add-in is loaded.

        Returns:
            AdapterResult[dict[str, Any]]: Add-in load state or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="ensure_motion_addin is not implemented by this adapter",
        )

    async def add_motor(
        self, params: MotionMotorParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Add a rotary or linear constant-speed motor to a motion study.

        Args:
            params (MotionMotorParameters): Motor type, entity, speed.

        Returns:
            AdapterResult[dict[str, Any]]: Created motor feature or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_motor is not implemented by this adapter",
        )

    async def add_gravity(
        self, params: MotionGravityParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Add gravity to a motion study.

        Args:
            params (MotionGravityParameters): Axis, strength, direction.

        Returns:
            AdapterResult[dict[str, Any]]: Created gravity feature or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_gravity is not implemented by this adapter",
        )

    async def calculate_motion(
        self, params: MotionStudyRefParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Solve a motion study.

        Args:
            params (MotionStudyRefParameters): Target study name.

        Returns:
            AdapterResult[dict[str, Any]]: Calculation result or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="calculate_motion is not implemented by this adapter",
        )

    async def set_motion_time(
        self, params: MotionTimeParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Position a calculated motion study at a point in time.

        Args:
            params (MotionTimeParameters): Time in seconds and study name.

        Returns:
            AdapterResult[dict[str, Any]]: Applied time or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="set_motion_time is not implemented by this adapter",
        )

    async def export_motion_video(
        self, params: MotionExportParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Export a motion study animation to a single-file H.264 video.

        The container is chosen by the output path suffix (``.mp4``/``.mkv``/
        ``.flv``); ``.avi`` is not available headlessly.

        Args:
            params (MotionExportParameters): Output path and study name.

        Returns:
            AdapterResult[dict[str, Any]]: Output path or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="export_motion_video is not implemented by this adapter",
        )

    async def list_motion_studies(self) -> AdapterResult[list[dict[str, Any]]]:
        """List the motion studies of the active document.

        Returns:
            AdapterResult[list[dict[str, Any]]]: One entry per study or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="list_motion_studies is not implemented by this adapter",
        )

    async def add_motion_spring(
        self, params: MotionSpringParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Add a spring force element to a motion study.

        Args:
            params (MotionSpringParameters): Spring type, endpoints, k, L0.

        Returns:
            AdapterResult[dict[str, Any]]: Created spring feature or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_motion_spring is not implemented by this adapter",
        )

    async def add_motion_damper(
        self, params: MotionDamperParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Add a damper force element to a motion study.

        Args:
            params (MotionDamperParameters): Damper type, endpoints, c.

        Returns:
            AdapterResult[dict[str, Any]]: Created damper feature or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_motion_damper is not implemented by this adapter",
        )

    async def add_motion_force(
        self, params: MotionForceParameters
    ) -> AdapterResult[dict[str, Any]]:
        """Add an applied force/torque to a motion study.

        Args:
            params (MotionForceParameters): Force type, location, magnitude.

        Returns:
            AdapterResult[dict[str, Any]]: Created force feature or error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="add_motion_force is not implemented by this adapter",
        )

    @abstractmethod
    async def exit_sketch(self) -> AdapterResult[None]:
        """Exit sketch editing mode.

        Returns:
            AdapterResult[None]: The result produced by the operation.
        """
        pass

    async def blank_sketch(self, sketch: str) -> AdapterResult[None]:
        """Hide a named sketch (construction scaffolding that should not render).

        Args:
            sketch (str): The sketch feature name.

        Returns:
            AdapterResult[None]: SUCCESS once blanked, or an error.
        """
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="blank_sketch is not implemented by this adapter",
        )

    # Analysis Operations
    @abstractmethod
    async def get_mass_properties(self) -> AdapterResult[MassProperties]:
        """Get mass properties of the current model.

        Returns:
            AdapterResult[MassProperties]: The result produced by the operation.
        """
        pass

    # Export Operations
    @abstractmethod
    async def export_image(self, payload: dict) -> AdapterResult[dict]:
        """Export a viewport screenshot (PNG/JPG) of the current model.

        Payload keys: file_path (str): Absolute output path. width (int): Image width in pixels.
        height (int): Image height in pixels. view_orientation (str): One of "isometric",
        "front", "top", "right", "back", "bottom", "current".

        Args:
            payload (dict): The payload value.

        Returns:
            AdapterResult[dict]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def export_file(
        self, file_path: str, format_type: str
    ) -> AdapterResult[None]:
        """Export the current model to a file.

        Args:
            file_path (str): Path to the target file.
            format_type (str): The format type value.

        Returns:
            AdapterResult[None]: The result produced by the operation.
        """
        pass

    # Dimension Operations
    @abstractmethod
    async def get_dimension(self, name: str) -> AdapterResult[float]:
        """Get the value of a dimension.

        Args:
            name (str): The name value.

        Returns:
            AdapterResult[float]: The result produced by the operation.
        """
        pass

    @abstractmethod
    async def set_dimension(self, name: str, value: float) -> AdapterResult[None]:
        """Set the value of a dimension.

        Args:
            name (str): The name value.
            value (float): The value value.

        Returns:
            AdapterResult[None]: The result produced by the operation.
        """
        pass

    # Utility Methods
    def update_metrics(self, operation_time: float, success: bool) -> None:
        """Update adapter metrics.

        Args:
            operation_time (float): The operation time value.
            success (bool): The success value.

        Returns:
            None: None.
        """
        self._metrics["operations_count"] += 1
        if not success:
            self._metrics["errors_count"] += 1

        # Update average response time
        current_avg = self._metrics["average_response_time"]
        count = self._metrics["operations_count"]
        self._metrics["average_response_time"] = (
            current_avg * (count - 1) + operation_time
        ) / count

    def get_metrics(self) -> dict[str, Any]:
        """Get adapter metrics.

        Returns:
            dict[str, Any]: A dictionary containing the resulting values.
        """
        return self._metrics.copy()
