"""Motion-study mixin for PyWin32 SolidWorks operations.

Implements SOLIDWORKS Motion study automation on the active assembly:
create/activate a study and set its analysis type
(``IModelDocExtension::GetMotionStudyManager`` →
``IMotionStudyManager::CreateMotionStudy`` → ``IMotionStudy::StudyType``),
add a rotary/linear constant-speed motor and gravity
(``IMotionStudy::CreateDefinition`` → set the
``ISimulation*FeatureData`` members → ``IMotionStudy::CreateFeature``),
solve (``IMotionStudy::Calculate``), scrub to a time
(``IMotionStudy::SetTime`` — moves the components so callers can read each
one's transform) and export the animation (``IMotionStudy::SaveToAVI``).

It also adds the spring, damper and force feature elements the
MotionAnalysis solver balances (each via ``CreateDefinition`` → set
``ISimulation{Spring,Damper,Force}FeatureData`` members → ``CreateFeature``).

Units: gravity strength and the spring constant are SI (m/s², N/m — the
API's units, passed verbatim); motor speed is passed verbatim to
``ConstantSpeedMotor`` (RPM for a rotary motor, mm/s for a linear motor —
converted to m/s for the linear case); spring free length and coil
dimensions and entity pick points are millimetres (converted to metres);
spring free angle is degrees (converted to radians).

The Motion interfaces live in the SwMotionStudy type library, not
sldworks.tlb, so ``sw_type_info.flag_methods`` does not cover them. Their
zero-argument methods (``Activate``, ``Calculate``, ``CreateMotionStudy``)
use the cached exact-name fallback in ``sw_type_info.flag_method_names`` so
pywin32 invokes them instead of mis-resolving them as properties.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from .. import sw_type_info
from ..base import (
    AdapterResult,
    AdapterResultStatus,
    MotionDamperParameters,
    MotionExportParameters,
    MotionForceParameters,
    MotionGravityParameters,
    MotionMotorParameters,
    MotionSpringParameters,
    MotionStudyParameters,
    MotionStudyRefParameters,
    MotionTimeParameters,
)
from .assembly import (
    _component_cylindrical_face,
    _component_named_feature,
    _select_mate_entity,
)

try:
    import pythoncom  # noqa: F401
    import win32com.client  # noqa: F401
    import win32con  # noqa: F401
    import win32gui  # noqa: F401
except ImportError:  # pragma: no cover
    pythoncom = SimpleNamespace()
    win32com = SimpleNamespace(client=SimpleNamespace())
    win32con = SimpleNamespace()
    win32gui = SimpleNamespace()

# swMotionStudyType_e — defined only in the .NET interop, absent from the
# COM type library, so the values cannot be flagged/resolved at runtime.
# These are the documented bitmask values; create_motion_study writes the
# requested type then reads StudyType back to confirm it took (a wrong or
# unsupported type — e.g. motion_analysis without the SOLIDWORKS Motion
# add-in — does not stick, and is reported as an error rather than silently
# degrading to an Animation study).
_STUDY_TYPES = {
    "animation": 1,
    "physical_simulation": 2,  # Basic Motion
    "motion_analysis": 4,  # SOLIDWORKS Motion (CosmosMotion)
}

# swFeatureNameID_e (read live from the registered type library)
_FEAT_GRAVITY = 74
_FEAT_LINEAR_FORCE = 75
_FEAT_TORQUE = 76
_FEAT_LINEAR_MOTOR = 77
_FEAT_ROTARY_MOTOR = 78
_FEAT_LINEAR_MOTION_SPRING = 81
_FEAT_TORSIONAL_MOTION_SPRING = 82
_FEAT_LINEAR_DAMPER = 83
_FEAT_TORSIONAL_DAMPER = 84

_MOTOR_FEATURE = {"rotary": _FEAT_ROTARY_MOTOR, "linear": _FEAT_LINEAR_MOTOR}
_SPRING_FEATURE = {
    "linear": _FEAT_LINEAR_MOTION_SPRING,
    "torsional": _FEAT_TORSIONAL_MOTION_SPRING,
}
_DAMPER_FEATURE = {"linear": _FEAT_LINEAR_DAMPER, "torsional": _FEAT_TORSIONAL_DAMPER}
_FORCE_FEATURE = {"linear_force": _FEAT_LINEAR_FORCE, "torque": _FEAT_TORQUE}

# swSimulationForceFunctionType_e / swSimulationForceActionType_e
_FORCE_FUNCTION_CONSTANT = 0
_FORCE_ACTION_ONLY = 0
_FORCE_ACTION_AND_REACTION = 1

# swSimulationGravityAxis_e
_GRAVITY_AXES = {"x": 0, "y": 1, "z": 2}

# IAVIParameter.OutputType (swAnimationOutputType_e), keyed by file extension.
#
# Direct .avi (value 1) is NOT automatable: that path opens the Windows
# Video-Compression codec dialog, which has no API, so SaveToAVI returns false
# headlessly (works from the UI only because the user picks a codec there). The
# modern single-file video formats encode internally with no dialog and write a
# real, compact H.264 file headlessly — verified live on SW 2026: .mp4/.mkv/.flv
# all produce a valid ~40 KB H.264 video. .mp4 is the default/recommended.
_VIDEO_OUTPUT_TYPES = {".mp4": 7, ".mkv": 8, ".flv": 9}
# IAVIParameter.RendererType — swRendererType_Solidworks_Screen grabs the
# graphics framebuffer. The PhotoView/ray-trace renderer (1) needs an active
# render engine and makes the save return false when one isn't loaded.
_AVI_RENDERER_SCREEN = 0
# SaveToAVI returns true immediately and finishes writing the file on a
# background thread; poll until its size stops growing before returning.
_VIDEO_POLL_INTERVAL = 0.5
_VIDEO_STABLE_POLLS = 4
_VIDEO_WAIT_TIMEOUT = 300.0

# Zero-argument Motion methods pywin32 must invoke (not read as properties).
_MOTION_METHODS = (
    "CreateMotionStudy",
    "GetMotionStudy",
    "GetMotionStudyNames",
    "CreateAVIParameter",
    "ActivateMotionStudy",
    "Activate",
    "Calculate",
    "CreateDefinition",
    "CreateFeature",
    "GetSupportedStudyTypes",
    "SetDuration",
    "SetTime",
    "ConstantSpeedMotor",
    "OscillatingMotor",
    "SaveToAVI",
    "SetEndPoints",
    "Stop",
)


class SolidWorksMotionMixin:
    """Expose SolidWorks Motion-study methods via mixin-local helpers."""

    async def create_motion_study(
        self, params: MotionStudyParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _create_motion_study_impl(self, params)

    async def ensure_motion_addin(self) -> AdapterResult[dict[str, Any]]:
        return _ensure_motion_addin_impl(self)

    async def add_motor(
        self, params: MotionMotorParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _add_motor_impl(self, params)

    async def add_gravity(
        self, params: MotionGravityParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _add_gravity_impl(self, params)

    async def calculate_motion(
        self, params: MotionStudyRefParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _calculate_motion_impl(self, params)

    async def set_motion_time(
        self, params: MotionTimeParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _set_motion_time_impl(self, params)

    async def export_motion_video(
        self, params: MotionExportParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _export_motion_video_impl(self, params)

    async def list_motion_studies(self) -> AdapterResult[list[dict[str, Any]]]:
        return _list_motion_studies_impl(self)

    async def add_motion_spring(
        self, params: MotionSpringParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _add_motion_spring_impl(self, params)

    async def add_motion_damper(
        self, params: MotionDamperParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _add_motion_damper_impl(self, params)

    async def add_motion_force(
        self, params: MotionForceParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _add_motion_force_impl(self, params)


def _flag_motion_methods(obj: Any) -> None:
    """Flag the known Motion methods on a dispatch so pywin32 invokes them.

    Several Motion methods (``Calculate``, ``Activate`` …) are dual-marked
    and pywin32 resolves them as *property gets* — ``study.Calculate()`` then
    fails with ``TypeError: 'bool' object is not callable`` (the propget runs
    the method, returns its bool, and Python tries to call the bool).
    Exact-name flagging forces method dispatch.

    Each name is flagged individually and cached by ``flag_method_names``;
    unavailable manager-only/study-only names are skipped without preventing
    valid names such as ``Calculate`` from being registered.

    Args:
        obj: A Motion COM dispatch (manager or study).
    """
    sw_type_info.flag_method_names(obj, *_MOTION_METHODS)


def _motion_manager(adapter: Any) -> Any:
    """Return the active document's motion-study manager (or ``None``).

    ``IModelDocExtension::GetMotionStudyManager`` is present in the type
    library and vtable but absent from SolidWorks's ``IDispatch`` name table,
    so a by-name (late-bound) call raises ``com_error 'Member not found'``.
    The Extension is wrapped in its early-bound interface class
    (:func:`sw_type_info.early_bound`) so the call dispatches by dispid.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.

    Returns:
        Any: ``IMotionStudyManager`` dispatch or ``None``.
    """
    ext = adapter._attempt(lambda: adapter.currentModel.Extension, default=None)
    if ext is None:
        return None
    ext = sw_type_info.early_bound(ext, "IModelDocExtension")
    mgr = adapter._attempt(lambda: ext.GetMotionStudyManager(), default=None)
    if mgr is not None:
        _flag_motion_methods(mgr)
    return mgr


def _study_names(adapter: Any, mgr: Any) -> list[str]:
    """Return the current motion-study names.

    Args:
        adapter: Connected adapter.
        mgr: ``IMotionStudyManager`` dispatch.

    Returns:
        list[str]: Study names in tree order.
    """
    names = adapter._attempt(lambda: mgr.GetMotionStudyNames(), default=None)
    if not names:
        return []
    return [str(n) for n in names]


def _resolve_study(adapter: Any, mgr: Any, name: str) -> Any:
    """Resolve and activate a study by name (or the active study).

    Args:
        adapter: Connected adapter.
        mgr: ``IMotionStudyManager`` dispatch.
        name: Study name; empty uses ``adapter._active_motion_study``.

    Returns:
        Any: Activated ``IMotionStudy`` dispatch.

    Raises:
        Exception: When no study can be resolved.
    """
    target = name or getattr(adapter, "_active_motion_study", "")
    if not target:
        raise Exception(
            "No motion study specified and none is active; create_motion_study first"
        )
    study = adapter._attempt(lambda: mgr.GetMotionStudy(target), default=None)
    if study is None:
        raise Exception(f"Motion study {target!r} not found")
    _flag_motion_methods(study)
    adapter._attempt(lambda: study.Activate(), default=None)
    adapter._active_motion_study = target
    return study


def _selected_object(adapter: Any, mark: int = 1) -> Any:
    """Return a selected object (by mark) via the selection manager.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        mark: Selection mark to read back.

    Returns:
        Any: The selected COM dispatch or ``None``.
    """
    return adapter._attempt(
        lambda: adapter.currentModel.SelectionManager.GetSelectedObject6(mark, -1),
        default=None,
    )


def _select_two_endpoints(adapter: Any, endpoints: Any) -> tuple[Any, Any]:
    """Select two force-element endpoints under marks 1 and 2.

    Mirrors the Add Spring / Add Damper examples: each endpoint is selected
    with append so both stay in the selection list, then read back by mark
    for ``SetEndPoints``.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        endpoints: A two-element sequence of ``MateEntityRef``.

    Returns:
        tuple[Any, Any]: The two selected COM dispatches.

    Raises:
        Exception: When either endpoint cannot be selected.
    """
    adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
    for index, ref in enumerate(endpoints):
        if not _select_mate_entity(adapter, ref, index + 1):
            located = ref.name or ref.point
            raise Exception(f"Failed to select endpoint {index + 1} ({located!r})")
    first = _selected_object(adapter, 1)
    second = _selected_object(adapter, 2)
    if first is None or second is None:
        raise Exception("Endpoint selection returned null")
    return first, second


def _create_motion_study_impl(
    adapter: Any, params: MotionStudyParameters
) -> AdapterResult[dict[str, Any]]:
    """Create or re-select a motion study and set its analysis type.

    The study type is written then read back: SolidWorks silently keeps an
    Animation study when an unsupported type is requested (most commonly
    ``motion_analysis`` without the SOLIDWORKS Motion add-in), so a
    read-back mismatch is surfaced as an error.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Study name, type and duration.

    Returns:
        AdapterResult[dict[str, Any]]: Study name/type or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    type_value = _STUDY_TYPES.get(params.study_type)
    if type_value is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown study_type: {params.study_type!r} "
            f"(expected one of {sorted(_STUDY_TYPES)})",
        )

    def _operation() -> dict[str, Any]:
        mgr = _motion_manager(adapter)
        if mgr is None:
            raise Exception(
                "GetMotionStudyManager returned null (MotionManager unavailable)"
            )
        if params.name:
            study = adapter._attempt(
                lambda: mgr.GetMotionStudy(params.name), default=None
            )
            if study is None:
                raise Exception(f"Motion study {params.name!r} not found")
        else:
            before = set(_study_names(adapter, mgr))
            study = adapter._attempt(lambda: mgr.CreateMotionStudy(), default=None)
            if not _is_study(study):
                after = [n for n in _study_names(adapter, mgr) if n not in before]
                if not after:
                    raise Exception("CreateMotionStudy did not create a study")
                study = adapter._attempt(
                    lambda: mgr.GetMotionStudy(after[-1]), default=None
                )
            if study is None:
                raise Exception("CreateMotionStudy returned null")
        _flag_motion_methods(study)

        adapter._attempt(lambda: setattr(study, "StudyType", type_value))
        applied = adapter._attempt(lambda: int(study.StudyType), default=None)
        if applied != type_value:
            hint = (
                " (enable Tools > Add-Ins > SOLIDWORKS Motion)"
                if params.study_type == "motion_analysis"
                else ""
            )
            raise Exception(
                f"StudyType {params.study_type!r} did not take "
                f"(read back {applied}){hint}"
            )

        adapter._attempt(lambda: study.SetDuration(float(params.duration)))
        if params.activate:
            adapter._attempt(lambda: study.Activate(), default=None)
        name = str(adapter._attempt(lambda: study.Name, default="") or "")
        adapter._active_motion_study = name
        return {
            "name": name,
            "study_type": params.study_type,
            "duration": float(params.duration),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("create_motion_study", _operation),
    )


def _is_study(obj: Any) -> bool:
    """Return ``True`` when ``obj`` looks like an ``IMotionStudy`` dispatch."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return False
    return True


def _ensure_motion_addin_impl(adapter: Any) -> AdapterResult[dict[str, Any]]:
    """Report whether Motion Analysis is available, loading the add-in.

    Attempts ``ISldWorks::LoadAddIn`` for the SOLIDWORKS Motion add-in, then
    reports the study types a fresh study supports. The authoritative check
    is the StudyType read-back in :func:`_create_motion_study_impl`; this
    method is a convenience to load the add-in up front.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.

    Returns:
        AdapterResult[dict[str, Any]]: Add-in/support state or error.
    """
    if not adapter.swApp:
        return AdapterResult(
            status=AdapterResultStatus.ERROR, error="No SolidWorks application"
        )

    def _operation() -> dict[str, Any]:
        # The SOLIDWORKS Motion add-in registers under a stable title; the
        # built-in add-ins load by title via LoadAddIn returning a non-zero
        # error when unavailable. Loading is best-effort — the StudyType
        # read-back in create_motion_study is the binding check.
        loaded = adapter._attempt(
            lambda: adapter.swApp.LoadAddIn("SOLIDWORKS Motion"), default=None
        )
        return {"load_addin_status": loaded}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("ensure_motion_addin", _operation),
    )


def _add_motor_impl(
    adapter: Any, params: MotionMotorParameters
) -> AdapterResult[dict[str, Any]]:
    """Add a rotary or linear constant-speed motor to a motion study.

    Mirrors the SolidWorks motor dialog: select the location/direction
    geometry, create the motor feature data, set its references and a
    constant speed, then create the feature.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Motor type, entity, speed and optional moving component.

    Returns:
        AdapterResult[dict[str, Any]]: Created motor feature or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    feature_id = _MOTOR_FEATURE.get(params.motor_type)
    if feature_id is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown motor_type: {params.motor_type!r} "
            f"(expected one of {sorted(_MOTOR_FEATURE)})",
        )

    def _operation() -> dict[str, Any]:
        mgr = _motion_manager(adapter)
        if mgr is None:
            raise Exception("MotionManager unavailable")
        study = _resolve_study(adapter, mgr, params.study_name)

        data = adapter._attempt(
            lambda: study.CreateDefinition(feature_id), default=None
        )
        if data is None:
            raise Exception("CreateDefinition failed for motor")

        adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
        selection = _resolve_motor_entity(adapter, params.entity)
        if selection is None:
            located = (
                params.entity.component or params.entity.name or params.entity.point
            )
            raise Exception(f"Failed to resolve motor entity ({located!r})")
        adapter._attempt(lambda: setattr(data, "DirectionReference", selection))
        adapter._attempt(lambda: setattr(data, "Location", selection))

        if params.component:
            comp = _resolve_component(adapter, params.component)
            if comp is not None:
                adapter._attempt(lambda: setattr(data, "RelativeComponent", comp))

        if params.motion_function == "oscillating":
            # OscillatingMotor(Displacement, Frequency): rotary displacement is
            # in degrees, linear displacement in metres (API is SI); frequency
            # in Hz. Linear amplitude arrives in mm -> convert to m.
            amp = float(params.amplitude)
            if params.motor_type == "linear":
                amp = amp / 1000.0
            adapter._attempt(
                lambda: data.OscillatingMotor(amp, float(params.frequency))
            )
        else:
            speed = float(params.speed)
            # Linear motor speed arrives in mm/s; the API is SI (m/s). Rotary
            # speed passes through (RPM, the rotary motor's native unit).
            if params.motor_type == "linear":
                speed = speed / 1000.0
            adapter._attempt(lambda: data.ConstantSpeedMotor(speed))
        if params.reverse:
            adapter._attempt(lambda: setattr(data, "ReverseDirection", True))

        feature = adapter._attempt(lambda: study.CreateFeature(data), default=None)
        if feature is None:
            raise Exception("CreateFeature failed for motor")
        adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
        return {
            "name": str(adapter._attempt(lambda: feature.Name, default="") or ""),
            "motor_type": params.motor_type,
            "speed": float(params.speed),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("add_motor", _operation),
    )


def _resolve_motor_entity(adapter: Any, ref: Any) -> Any:
    """Resolve the Location/DirectionReference entity for a motor.

    For a part nested in a flexible subassembly (``ref.component`` set), map the
    reference into assembly context and return the dispatch DIRECTLY — its
    ``Select4`` returns false there but the entity is still valid as a motor
    reference, and a hand-built selection string would mis-resolve to the top
    level. With ``name`` the named reference axis (or plane) is mapped via
    ``GetCorresponding`` (depth-agnostic, no face walk — preferred for a rotary
    motor on a part's axis); otherwise the largest/nearest cylindrical face is
    mapped via ``GetCorrespondingEntity``. Without ``component``, select by
    name/point and read the selection back (the documented motor-dialog flow).

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        ref: A ``MateEntityRef``.

    Returns:
        Any: The entity dispatch to use for the motor, or ``None``.
    """
    if ref.component and ref.name:
        return _component_named_feature(adapter, ref.component, ref.name)
    if ref.component:
        return _component_cylindrical_face(adapter, ref.component, ref.point or None)
    if not _select_mate_entity(adapter, ref, 1):
        return None
    return _selected_object(adapter)


def _resolve_component(adapter: Any, name: str) -> Any:
    """Resolve an assembly component dispatch by name.

    Args:
        adapter: Connected adapter.
        name: Component name as shown in the tree.

    Returns:
        Any: ``IComponent2`` dispatch or ``None``.
    """
    from .assembly import _qualify_entity_name

    qualified = _qualify_entity_name(adapter, name)
    selected = adapter._attempt(
        lambda: adapter.currentModel.Extension.SelectByID2(
            qualified, "COMPONENT", 0.0, 0.0, 0.0, False, 0, None, 0
        ),
        default=False,
    )
    if not selected:
        return None
    comp = adapter._attempt(
        lambda: adapter.currentModel.SelectionManager.GetSelectedObjectsComponent3(
            1, -1
        ),
        default=None,
    )
    adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
    return comp


def _add_gravity_impl(
    adapter: Any, params: MotionGravityParameters
) -> AdapterResult[dict[str, Any]]:
    """Add gravity to a motion study.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Axis, strength and direction.

    Returns:
        AdapterResult[dict[str, Any]]: Created gravity feature or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    axis = _GRAVITY_AXES.get(params.axis)
    if axis is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown axis: {params.axis!r} "
            f"(expected one of {sorted(_GRAVITY_AXES)})",
        )

    def _operation() -> dict[str, Any]:
        mgr = _motion_manager(adapter)
        if mgr is None:
            raise Exception("MotionManager unavailable")
        study = _resolve_study(adapter, mgr, params.study_name)
        data = adapter._attempt(
            lambda: study.CreateDefinition(_FEAT_GRAVITY), default=None
        )
        if data is None:
            raise Exception("CreateDefinition failed for gravity")
        adapter._attempt(lambda: setattr(data, "Axis", axis))
        adapter._attempt(lambda: setattr(data, "Strength", float(params.strength)))
        adapter._attempt(
            lambda: setattr(data, "ReverseDirection", bool(params.reverse))
        )
        feature = adapter._attempt(lambda: study.CreateFeature(data), default=None)
        if feature is None:
            raise Exception("CreateFeature failed for gravity")
        return {
            "name": str(adapter._attempt(lambda: feature.Name, default="") or ""),
            "axis": params.axis,
            "strength": float(params.strength),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("add_gravity", _operation),
    )


def _calculate_motion_impl(
    adapter: Any, params: MotionStudyRefParameters
) -> AdapterResult[dict[str, Any]]:
    """Solve a motion study.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Target study name.

    Returns:
        AdapterResult[dict[str, Any]]: Calculation result or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _operation() -> dict[str, Any]:
        mgr = _motion_manager(adapter)
        if mgr is None:
            raise Exception("MotionManager unavailable")
        study = _resolve_study(adapter, mgr, params.name)
        ok = adapter._attempt(lambda: study.Calculate(), default=False)
        if not ok:
            raise Exception("Motion study calculation failed")
        return {"name": adapter._active_motion_study, "calculated": True}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("calculate_motion", _operation),
    )


def _set_motion_time_impl(
    adapter: Any, params: MotionTimeParameters
) -> AdapterResult[dict[str, Any]]:
    """Position a calculated motion study at a point in time.

    After this, component transforms reflect the solved pose at ``time`` —
    callers read each component's transform to sample the motion.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Time in seconds and target study name.

    Returns:
        AdapterResult[dict[str, Any]]: Applied time or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _operation() -> dict[str, Any]:
        mgr = _motion_manager(adapter)
        if mgr is None:
            raise Exception("MotionManager unavailable")
        study = _resolve_study(adapter, mgr, params.study_name)
        adapter._attempt(lambda: study.SetTime(float(params.time)))
        return {"name": adapter._active_motion_study, "time": float(params.time)}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("set_motion_time", _operation),
    )


def _restore_sw_window(adapter: Any) -> None:
    """Un-minimise the SOLIDWORKS frame so the screen renderer has a viewport.

    ``RendererType_Solidworks_Screen`` grabs the OpenGL framebuffer; that grab
    yields blank/garbage frames when the window is minimised. Restoring (not
    stealing foreground) is enough. Handle obtained from
    ``ISldWorks::Frame::GetHWndx64`` — no title guessing. Best-effort: any
    failure is swallowed so export still attempts the render.
    """
    if not hasattr(win32gui, "ShowWindow"):
        return
    try:
        frame = sw_type_info.early_bound_or_flag(
            adapter.swApp.Frame(), "IFrame", "GetHWndx64", "GetHWnd"
        )
        try:
            hwnd = int(frame.GetHWndx64())
        except Exception:  # noqa: BLE001
            hwnd = int(frame.GetHWnd())
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    except Exception:  # noqa: BLE001 - rendering is still worth attempting
        pass


def _wait_for_video_file(out_path: Path) -> int:
    """Block until the video file stops growing, then return its size in bytes.

    SaveToAVI returns true immediately and finishes encoding on a background
    thread, so polling stops once the size holds steady across several polls
    (or the timeout hits). Returns 0 if nothing was written.
    """
    stable = 0
    last = -1
    deadline = time.monotonic() + _VIDEO_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        size = out_path.stat().st_size if out_path.exists() else 0
        if size > 0 and size == last:
            stable += 1
            if stable >= _VIDEO_STABLE_POLLS:
                break
        else:
            stable = 0
        last = size
        time.sleep(_VIDEO_POLL_INTERVAL)
    return out_path.stat().st_size if out_path.exists() else 0


def _export_motion_video_impl(
    adapter: Any, params: MotionExportParameters
) -> AdapterResult[dict[str, Any]]:
    """Export a calculated motion study to a single-file H.264 video.

    The container is inferred from ``params.file_path``'s suffix:
    ``.mp4`` (recommended), ``.mkv`` or ``.flv``. Legacy ``.avi`` is rejected
    because SOLIDWORKS only writes ``.avi`` through the interactive
    Video-Compression codec dialog (no API), so it can't be produced
    headlessly; the modern formats encode internally with no dialog.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Output path (extension picks the container), study name and
            frame rate.

    Returns:
        AdapterResult[dict[str, Any]]: Output path and byte size, or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _operation() -> dict[str, Any]:
        out_path = Path(params.file_path)
        output_type = _VIDEO_OUTPUT_TYPES.get(out_path.suffix.lower())
        if output_type is None:
            supported = ", ".join(sorted(_VIDEO_OUTPUT_TYPES))
            extra = (
                " — .avi can only be written via the interactive SOLIDWORKS "
                "Video-Compression codec dialog, so it is not available headlessly"
                if out_path.suffix.lower() == ".avi"
                else ""
            )
            raise Exception(
                f"Unsupported video format {out_path.suffix!r}; "
                f"use one of: {supported}{extra}"
            )
        mgr = _motion_manager(adapter)
        if mgr is None:
            raise Exception("MotionManager unavailable")
        study = _resolve_study(adapter, mgr, params.study_name)
        avi_params = adapter._attempt(lambda: mgr.CreateAVIParameter(), default=None)
        if avi_params is None:
            raise Exception("CreateAVIParameter returned null")
        adapter._attempt(lambda: setattr(avi_params, "OutputType", output_type))
        adapter._attempt(
            lambda: setattr(
                avi_params, "FramePerSecond", float(params.frames_per_second)
            )
        )
        adapter._attempt(lambda: setattr(avi_params, "SaveEntireAnimation", True))
        adapter._attempt(
            lambda: setattr(avi_params, "RendererType", _AVI_RENDERER_SCREEN)
        )
        _restore_sw_window(adapter)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            out_path.unlink()
        # Stop playback first or the save races the animator and returns false.
        adapter._attempt(lambda: study.Stop())
        ok = adapter._attempt(
            lambda: study.SaveToAVI(str(out_path), avi_params), default=False
        )
        if not ok:
            raise Exception(f"SaveToAVI returned false for {out_path}")
        size = _wait_for_video_file(out_path)
        if size == 0:
            raise Exception(
                f"SaveToAVI reported success but wrote no data to {out_path}"
            )
        return {
            "name": adapter._active_motion_study,
            "file_path": str(out_path),
            "bytes": size,
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("export_motion_video", _operation),
    )


def _list_motion_studies_impl(adapter: Any) -> AdapterResult[list[dict[str, Any]]]:
    """List the motion studies of the active document.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.

    Returns:
        AdapterResult[list[dict[str, Any]]]: One entry per study or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _operation() -> list[dict[str, Any]]:
        mgr = _motion_manager(adapter)
        if mgr is None:
            raise Exception("MotionManager unavailable")
        studies: list[dict[str, Any]] = []
        for name in _study_names(adapter, mgr):
            study = adapter._attempt(lambda n=name: mgr.GetMotionStudy(n), default=None)
            study_type = (
                adapter._attempt(lambda s=study: int(s.StudyType), default=None)
                if study is not None
                else None
            )
            studies.append({"name": name, "study_type": study_type})
        return studies

    return cast(
        AdapterResult[list[dict[str, Any]]],
        adapter._handle_com_operation("list_motion_studies", _operation),
    )


def _add_motion_spring_impl(
    adapter: Any, params: MotionSpringParameters
) -> AdapterResult[dict[str, Any]]:
    """Add a spring force element between two endpoints.

    Mirrors the SolidWorks Add Spring flow: create the spring feature data,
    select and set the two endpoints, set the stiffness/free-length (and
    optional coil geometry and damper), then create the feature. Lengths are
    millimetres (converted to the API's metres); the spring constant is SI
    and passed verbatim.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Spring type, endpoints, stiffness and rest length.

    Returns:
        AdapterResult[dict[str, Any]]: Created spring feature or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    feature_id = _SPRING_FEATURE.get(params.spring_type)
    if feature_id is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown spring_type: {params.spring_type!r} "
            f"(expected one of {sorted(_SPRING_FEATURE)})",
        )
    if len(params.endpoints) != 2:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="a spring needs exactly two endpoints",
        )

    def _operation() -> dict[str, Any]:
        mgr = _motion_manager(adapter)
        if mgr is None:
            raise Exception("MotionManager unavailable")
        study = _resolve_study(adapter, mgr, params.study_name)
        data = adapter._attempt(
            lambda: study.CreateDefinition(feature_id), default=None
        )
        if data is None:
            raise Exception("CreateDefinition failed for spring")

        first, second = _select_two_endpoints(adapter, params.endpoints)
        adapter._attempt(lambda: data.SetEndPoints(first, second))

        adapter._attempt(
            lambda: setattr(data, "SpringConstant", float(params.spring_constant))
        )
        if params.spring_type == "linear" and params.free_length is not None:
            adapter._attempt(
                lambda: setattr(data, "FreeLength", float(params.free_length) / 1000.0)
            )
        if params.spring_type == "torsional" and params.free_angle is not None:
            adapter._attempt(
                lambda: setattr(data, "FreeAngle", math.radians(params.free_angle))
            )
        if params.coil_diameter > 0:
            adapter._attempt(
                lambda: setattr(data, "CoilDiameter", params.coil_diameter / 1000.0)
            )
        if params.wire_diameter > 0:
            adapter._attempt(
                lambda: setattr(data, "WireDiameter", params.wire_diameter / 1000.0)
            )
        if params.number_of_coils > 0:
            adapter._attempt(
                lambda: setattr(data, "NumberOfCoils", float(params.number_of_coils))
            )
        if params.damping_constant > 0:
            adapter._attempt(lambda: setattr(data, "HasDamper", True))
            adapter._attempt(
                lambda: setattr(data, "DampingConstant", float(params.damping_constant))
            )
        if params.reverse:
            adapter._attempt(lambda: setattr(data, "ReverseDirection", True))

        feature = adapter._attempt(lambda: study.CreateFeature(data), default=None)
        if feature is None:
            raise Exception("CreateFeature failed for spring")
        adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
        return {
            "name": str(adapter._attempt(lambda: feature.Name, default="") or ""),
            "spring_type": params.spring_type,
            "spring_constant": float(params.spring_constant),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("add_motion_spring", _operation),
    )


def _add_motion_damper_impl(
    adapter: Any, params: MotionDamperParameters
) -> AdapterResult[dict[str, Any]]:
    """Add a damper force element between two endpoints.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Damper type, endpoints and damping coefficient.

    Returns:
        AdapterResult[dict[str, Any]]: Created damper feature or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    feature_id = _DAMPER_FEATURE.get(params.damper_type)
    if feature_id is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown damper_type: {params.damper_type!r} "
            f"(expected one of {sorted(_DAMPER_FEATURE)})",
        )
    if len(params.endpoints) != 2:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="a damper needs exactly two endpoints",
        )

    def _operation() -> dict[str, Any]:
        mgr = _motion_manager(adapter)
        if mgr is None:
            raise Exception("MotionManager unavailable")
        study = _resolve_study(adapter, mgr, params.study_name)
        data = adapter._attempt(
            lambda: study.CreateDefinition(feature_id), default=None
        )
        if data is None:
            raise Exception("CreateDefinition failed for damper")
        first, second = _select_two_endpoints(adapter, params.endpoints)
        adapter._attempt(lambda: data.SetEndPoints(first, second))
        adapter._attempt(
            lambda: setattr(data, "DampingConstant", float(params.damping_constant))
        )
        feature = adapter._attempt(lambda: study.CreateFeature(data), default=None)
        if feature is None:
            raise Exception("CreateFeature failed for damper")
        adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
        return {
            "name": str(adapter._attempt(lambda: feature.Name, default="") or ""),
            "damper_type": params.damper_type,
            "damping_constant": float(params.damping_constant),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("add_motion_damper", _operation),
    )


def _add_motion_force_impl(
    adapter: Any, params: MotionForceParameters
) -> AdapterResult[dict[str, Any]]:
    """Add a constant applied force/torque at a location on a component.

    Mirrors the SolidWorks Create Force flow: create the force feature data,
    set the action type, select the action-location geometry and set it (plus
    the owning component as the reference), set a constant function value,
    then create the feature. Magnitude is SI and passed verbatim.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Force type, action location and magnitude.

    Returns:
        AdapterResult[dict[str, Any]]: Created force feature or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    feature_id = _FORCE_FEATURE.get(params.force_type)
    if feature_id is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown force_type: {params.force_type!r} "
            f"(expected one of {sorted(_FORCE_FEATURE)})",
        )

    def _operation() -> dict[str, Any]:
        mgr = _motion_manager(adapter)
        if mgr is None:
            raise Exception("MotionManager unavailable")
        study = _resolve_study(adapter, mgr, params.study_name)
        data = adapter._attempt(
            lambda: study.CreateDefinition(feature_id), default=None
        )
        if data is None:
            raise Exception("CreateDefinition failed for force")

        action_type = (
            _FORCE_ACTION_ONLY if params.action_only else _FORCE_ACTION_AND_REACTION
        )
        adapter._attempt(lambda: setattr(data, "ActionType", action_type))

        adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
        if not _select_mate_entity(adapter, params.action, 1):
            located = params.action.name or params.action.point
            raise Exception(f"Failed to select force action location ({located!r})")
        selection = _selected_object(adapter, 1)
        if selection is None:
            raise Exception("Force action-location selection returned null")
        adapter._attempt(lambda: setattr(data, "ActionLocation", selection))
        comp = adapter._attempt(
            lambda: adapter.currentModel.SelectionManager.GetSelectedObjectsComponent3(
                1, -1
            ),
            default=None,
        )
        if comp is not None:
            adapter._attempt(lambda: setattr(data, "ReferenceComponent", comp))

        adapter._attempt(
            lambda: setattr(data, "ForceFunctionType", _FORCE_FUNCTION_CONSTANT)
        )
        adapter._attempt(
            lambda: setattr(data, "FunctionConstantValue", float(params.magnitude))
        )
        if params.reverse:
            adapter._attempt(lambda: setattr(data, "ReverseDirection", True))

        feature = adapter._attempt(lambda: study.CreateFeature(data), default=None)
        if feature is None:
            raise Exception("CreateFeature failed for force")
        adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
        return {
            "name": str(adapter._attempt(lambda: feature.Name, default="") or ""),
            "force_type": params.force_type,
            "magnitude": float(params.magnitude),
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("add_motion_force", _operation),
    )
