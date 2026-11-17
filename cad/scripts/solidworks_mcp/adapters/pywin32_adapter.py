"""PyWin32 SolidWorks adapter for Windows COM integration.

This adapter uses pywin32 to communicate with SolidWorks via COM, providing real
SolidWorks automation capabilities on Windows platforms.
"""

import asyncio
import contextlib
import os
import platform
import time
from collections.abc import Callable
from datetime import datetime
from types import SimpleNamespace
from typing import Any, TypeVar

from ..exceptions import SolidWorksMCPError
from . import sw_install, sw_type_info
from .base import (
    AdapterHealth,
    AdapterResult,
    AdapterResultStatus,
    SolidWorksAdapter,
)
from .com_variant import null_callout
from .solidworks import (
    SolidWorksAssemblyMixin,
    SolidWorksFeaturesMixin,
    SolidWorksIOMixin,
    SolidWorksManufacturingMixin,
    SolidWorksMeasureMixin,
    SolidWorksMotionMixin,
    SolidWorksParametricsMixin,
    SolidWorksReferenceGeometryMixin,
    SolidWorksSelectionMixin,
    SolidWorksSketchMixin,
)

try:
    import pythoncom
    import pywintypes
    import win32com.client

    PYWIN32_AVAILABLE = True
except ImportError:  # pragma: no cover
    # Keep names defined for tests that patch module attributes on non-Windows CI.
    pythoncom = SimpleNamespace()
    pywintypes = SimpleNamespace(com_error=Exception)
    win32com = SimpleNamespace(client=SimpleNamespace())
    PYWIN32_AVAILABLE = False


def _early_bound_application(arg: Any) -> Any:
    """Return the makepy-generated SolidWorks application wrapper.

    Wrap an existing ROT dispatch through its raw ``_oleobj_``; ``EnsureDispatch``
    cannot automate makepy for SolidWorks's ROT proxy (live error
    ``-2147319765 Element not found``).  A ProgID is dispatched first, then the
    same generated ``ISldWorks`` class is applied.  This uses known DISPIDs and
    typed return contracts without depending on ROT type-info discovery.
    """
    raw = win32com.client.Dispatch(arg) if isinstance(arg, str) else arg
    return sw_type_info.early_bound(raw, "ISldWorks")


from loguru import logger  # noqa: E402

T = TypeVar("T")

# Registry prefixes whose entity is a single sketch segment (not a group/list or
# a dimension/relation), eligible for derived-interface re-binding on register.
_SEGMENT_PREFIXES = frozenset(
    {"Line", "Arc", "Circle", "Spline", "Centerline", "Ellipse"}
)

# The DERIVED sketch-segment makepy classes a registered segment is bound to
# (`register_entity` -> `concrete_sketch_segment`). None of them declare
# `Select`/`Select2`/`Select4`, so a select must rebind them to `ISketchSegment`.
# (Sketch POINTS, by contrast, are `ISketchPoint`, which DOES declare them.)
_DERIVED_SKETCH_SEGMENT_INTERFACES = (
    "ISketchLine",
    "ISketchArc",
    "ISketchEllipse",
    "ISketchSpline",
)


def _load_pillow_image() -> Any:
    """Return ``PIL.Image`` when Pillow is installed, else ``None``.

    Pillow ships in the optional ``vision`` extra; screenshot capture uses it
    to convert ``SaveBMP`` output to the requested format. Module-level so
    tests can monkeypatch the import seam.
    """
    try:
        from PIL import Image

        return Image
    except ImportError:
        return None


def _parse_vb_module_name(macro_path: str) -> str:
    """Read ``Attribute VB_Name = "..."`` from a SolidWorks text macro file.

    Falls back to the file stem (e.g. ``paper_airplane`` for ``paper_airplane.swp``), then
    to ``"SolidWorksMacro"`` which is the name used by the macro recorder.

    Args:
        macro_path (str): The macro path value.

    Returns:
        str: The resulting text value.
    """
    try:
        with open(macro_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.lower().startswith("attribute vb_name"):
                    # Attribute VB_Name = "SolidWorksMacro"
                    _, _, rhs = line.partition("=")
                    return rhs.strip().strip('"').strip("'")
    except OSError:
        pass
    stem = os.path.splitext(os.path.basename(macro_path))[0]
    if stem and not stem.startswith(".") and stem.strip("."):
        return stem
    return "SolidWorksMacro"


class _ComSessionCoordinator:
    """Coordinate COM apartment initialisation and SolidWorks application lifecycle.

    This collaborator is responsible for the low-level mechanics of connecting
    to the SolidWorks COM server: initialising the COM apartment, acquiring the
    ``SldWorks.Application`` object (with retries), waiting for the server to
    become ready, toggling automation preferences, and tearing everything down
    cleanly on disconnect.

    It is instantiated once inside ``PyWin32Adapter.__init__`` and accessed
    via ``self._com_coordinator``.

    Attributes:
        _adapter: Back-reference to the owning ``PyWin32Adapter`` instance.
    """

    def __init__(self, adapter: "PyWin32Adapter") -> None:
        """Store a back-reference to the owning adapter.

        Args:
            adapter: The ``PyWin32Adapter`` instance that created this
                coordinator.  Must remain alive for the full lifetime of the
                coordinator.
        """
        self._adapter = adapter

    def initialize_com_apartment(self) -> None:
        """Initialise the COM apartment via ``pythoncom.CoInitialize``.

        Safe to call multiple times; subsequent calls are no-ops if the
        apartment is already initialised (tracked via
        ``adapter._com_initialized``).

        Side Effects:
            Sets ``adapter._com_initialized`` to ``True`` on first call.
        """
        if self._adapter._com_initialized:
            return
        pythoncom.CoInitialize()
        self._adapter._com_initialized = True

    def uninitialize_com_apartment(self) -> None:
        """Release the COM apartment via ``pythoncom.CoUninitialize``.

        Only called when this coordinator was the one that initialised the
        apartment (``adapter._com_initialized`` is ``True``).  Resets the
        flag afterwards so reconnect attempts work correctly.

        Side Effects:
            Sets ``adapter._com_initialized`` to ``False``.
        """
        if not self._adapter._com_initialized:
            return
        pythoncom.CoUninitialize()
        self._adapter._com_initialized = False

    async def acquire_solidworks_application(self) -> Any:
        """Acquire a live SolidWorks COM application object.

        Attaching to an already-running instance works for every edition and
        never raises the 3DEXPERIENCE launch dialog, so that is always tried
        first.  When nothing is running, the launch strategy is resolved from
        the installed edition (see :mod:`solidworks_mcp.adapters.sw_install`):

        * **Standard install** — cold-start the ``SldWorks.Application`` COM
          class through its generated makepy wrapper.
        * **3DEXPERIENCE / "for Makers" edition** — start through the Platform
          desktop shortcut (a bare COM/exe cold-start only pops the modal
          "must be launched from the 3DEXPERIENCE Platform" dialog and exits),
          then attach over COM.
        * **Makers edition with no shortcut found** — raise an actionable
          error rather than triggering that dialog.

        Returns:
            Any: The live ``SldWorks.Application`` COM object.

        Raises:
            SolidWorksMCPError: When acquisition fails, or the Makers edition is
                installed but cannot be started automatically.

        Side Effects:
            Sets ``adapter.swApp`` to the acquired COM object.
        """
        self._adapter.swApp = None

        app = self._attach_to_running_application()
        if app is not None:
            self._adapter.swApp = app
            return app

        # A SolidWorks process may already be running but not yet attachable
        # (still registering its Running Object Table entry, or parked on a
        # startup dialog). Launching another instance here pops the "Another
        # session of SOLIDWORKS may already be running" journal warning, so poll
        # for attach instead of starting a duplicate.
        if sw_install.is_solidworks_process_running():
            return await self._await_running_application()

        # No instance is running — validate how this install must be started
        # before blindly cold-starting it.
        strategy, shortcut = sw_install.resolve_launch_strategy()

        if strategy is sw_install.LaunchStrategy.PLATFORM_REQUIRED:
            raise SolidWorksMCPError(
                "SolidWorks 'for Makers' (3DEXPERIENCE) edition is installed but no "
                "running instance was found and no 3DEXPERIENCE Platform launch "
                "shortcut could be located. Start SOLIDWORKS Design from the "
                "3DEXPERIENCE Platform (or its desktop shortcut), then retry — this "
                "edition cannot be launched directly via COM or sldworks.exe."
            )

        if strategy is sw_install.LaunchStrategy.PLATFORM_SHORTCUT:
            return await self._launch_via_platform_and_attach(shortcut)

        return await self._cold_start_application()

    def _attach_to_running_application(self) -> Any | None:
        """Bind to an already-running SolidWorks instance, if there is one.

        Uses ``GetActiveObject`` and wraps the returned ROT dispatch in the
        generated ``ISldWorks`` wrapper.

        Returns:
            Any | None: The early-bound COM object, or ``None`` when no instance
            is running (or the bind fails for any reason).
        """
        try:
            raw = win32com.client.GetActiveObject("SldWorks.Application")
        except Exception:
            return None
        return _early_bound_application(raw) if raw is not None else None

    async def _cold_start_application(self) -> Any:
        """Cold-start a standard SolidWorks install via the COM class.

        Retries up to 8 times, sleeping 1 second between attempts so a slow
        launch has time to register its COM class.

        Returns:
            Any: The live ``SldWorks.Application`` COM object.

        Raises:
            SolidWorksMCPError: After all retries are exhausted.
        """
        last_error: Exception | None = None
        for _ in range(8):
            try:
                app = _early_bound_application("SldWorks.Application")
                if app is not None:
                    self._adapter.swApp = app
                    return app
            except pywintypes.com_error as dispatch_error:
                last_error = dispatch_error

            await asyncio.sleep(1.0)

        if last_error is not None:
            raise SolidWorksMCPError(str(last_error))
        raise SolidWorksMCPError("SolidWorks COM application instance is None")

    async def _launch_via_platform_and_attach(self, shortcut: Any) -> Any:
        """Launch the Makers edition via its Platform shortcut, then attach.

        Args:
            shortcut: The Platform launch shortcut path resolved by
                :func:`sw_install.find_platform_shortcut`.

        Returns:
            Any: The live ``SldWorks.Application`` COM object.

        Raises:
            SolidWorksMCPError: When the launch is fired but no licensed COM
                instance becomes attachable within the timeout.
        """
        sw_install.launch_via_platform_shortcut(shortcut)
        app = await self._poll_for_running_application()
        if app is not None:
            return app

        raise SolidWorksMCPError(
            "Launched SolidWorks via the 3DEXPERIENCE Platform shortcut "
            f"({shortcut}) but no COM instance became available within 60s. "
            "Confirm the 3DEXPERIENCE session is signed in and dismiss any "
            "startup dialogs, then retry."
        )

    async def _await_running_application(self) -> Any:
        """Attach to a SolidWorks process that is up but not yet COM-attachable.

        Polls without ever launching a second instance, so it cannot trigger the
        duplicate-session journal warning.

        Returns:
            Any: The live ``SldWorks.Application`` COM object.

        Raises:
            SolidWorksMCPError: When the running process never becomes
                COM-attachable within the timeout.
        """
        app = await self._poll_for_running_application()
        if app is not None:
            return app

        raise SolidWorksMCPError(
            "A SolidWorks process is running but did not become COM-attachable "
            "within 60s. Dismiss any startup dialogs (e.g. the journal-file "
            "warning or a 3DEXPERIENCE login prompt); if it persists, restart "
            "SolidWorks via the 3DEXPERIENCE Platform."
        )

    async def _poll_for_running_application(self, attempts: int = 60) -> Any | None:
        """Poll ``GetActiveObject`` until a running instance attaches.

        The Platform splash can take ~30 s to hand off a licensed session, so the
        default window is 60 seconds at a 1-second cadence.

        Args:
            attempts: Number of 1-second poll cycles before giving up.

        Returns:
            Any | None: The attached COM object, or ``None`` on timeout. Sets
            ``adapter.swApp`` on success.
        """
        for _ in range(attempts):
            await asyncio.sleep(1.0)
            app = self._attach_to_running_application()
            if app is not None:
                self._adapter.swApp = app
                return app
        return None

    async def wait_for_server_ready(self, app: Any) -> None:
        """Poll until the SolidWorks COM server is responsive.

        Reads ``app.RevisionNumber`` up to 10 times with 0.5-second pauses
        between attempts.  This guards against race conditions when SolidWorks
        is still loading after the COM object is first obtained.

        Args:
            app: The ``SldWorks.Application`` COM object returned by
                :meth:`acquire_solidworks_application`.

        Raises:
            SolidWorksMCPError: If the server does not respond within
                10 × 0.5 s = 5 seconds.
        """
        if not hasattr(app, "RevisionNumber"):
            return

        for _ in range(10):
            revision = self._adapter._attempt(
                lambda: self._adapter._get_attr_or_call(app, "RevisionNumber"),
                default=None,
            )
            if revision is not None:
                return
            await asyncio.sleep(0.5)

        raise SolidWorksMCPError(
            "SolidWorks COM server did not become ready in time. "
            "Confirm SolidWorks is fully launched and dismiss any startup dialogs."
        )

    @staticmethod
    def set_automation_preferences(app: Any, *, interactive: bool) -> None:
        """Toggle the SolidWorks warning and question dialog preferences.

        Sets user preference toggles 150 and 149 to suppress (or restore)
        popup dialogs during automated workflows. Also manages the
        sketch-dimension input toggles so sketch dimensions do not require the
        interactive Modify confirmation while automation is active.

        Verified against the SolidWorks 2026 constants type library, the
        relevant sketch-dimension toggles are:

        * ``swInputDimValOnCreate`` = 10
        * ``swSketchAcceptNumericInput`` = 372
        * ``swSketchCreateDimensionOnlyWhenEntered`` = 520
        * ``swScaleSketchOnFirstDimension`` = 642

        These stay disabled for the full automation session instead of being
        toggled around individual dimension calls, because once SolidWorks
        enters the modal approval flow, extra COM cleanup chatter tends to make
        recovery less reliable.

        Should be called with ``interactive=False`` immediately after
        connecting and ``interactive=True`` before disconnecting.

        Args:
            app: The live ``SldWorks.Application`` COM object.
            interactive: When ``False``, dialogs are suppressed for
                unattended operation.  When ``True``, normal interactive
                behaviour is restored.
        """
        app.SetUserPreferenceToggle(150, interactive)
        app.SetUserPreferenceToggle(149, interactive)
        if not interactive:
            app.SetUserPreferenceToggle(10, False)
            app.SetUserPreferenceToggle(372, False)
            app.SetUserPreferenceToggle(520, False)
            app.SetUserPreferenceToggle(642, False)

    async def connect(self) -> None:
        """Orchestrate the full SolidWorks connection sequence.

        Performs in order:

        1. Initialise the COM apartment.
        2. Acquire the ``SldWorks.Application`` COM object (with retries).
        3. Wait for the server to become ready.
        4. Make the application window visible.
        5. Suppress interactive dialogs for automation.

        On any failure the adapter state is cleaned up (``swApp`` set to
        ``None``, COM apartment uninitialised) before re-raising.

        Raises:
            SolidWorksMCPError: Wraps any underlying COM or timeout error.
        """
        try:
            self.initialize_com_apartment()
            app = await self.acquire_solidworks_application()
            await self.wait_for_server_ready(app)
            app.Visible = True
            self.set_automation_preferences(app, interactive=False)
        except Exception as exc:
            self._adapter.swApp = None
            self.uninitialize_com_apartment()
            raise SolidWorksMCPError(f"Failed to connect to SolidWorks: {exc}") from exc

    async def disconnect(self) -> None:
        """Clear session state and release the COM apartment.

        Resets all adapter model/sketch references to ``None`` and always
        uninitialises the COM apartment via ``finally`` so the apartment is
        freed even if the SolidWorks process is already unstable.

        Disconnect deliberately avoids additional UI preference COM calls.
        Real SolidWorks sessions can hit RPC teardown failures when toggles are
        restored during shutdown, so automation-safe preferences are applied on
        connect and left untouched during disconnect.

        Side Effects:
            Sets ``adapter.currentModel``, ``adapter.currentSketch``,
            ``adapter.currentSketchManager``, and ``adapter.swApp`` to
            ``None``.  Clears the sketch entity registry.  Calls
            ``CoUninitialize``.
        """
        try:
            self._adapter.currentModel = None
            self._adapter.currentSketch = None
            self._adapter.currentSketchManager = None
            self._adapter._reset_sketch_entity_registry()
            self._adapter.swApp = None
        finally:
            self.uninitialize_com_apartment()


class _SketchGeometryService:
    """Manage transient sketch-entity storage and provide geometry helpers.

    Maintains a per-sketch registry that maps stable string IDs (e.g.
    ``"Line_1"``, ``"Circle_3"``) to live SolidWorks COM entity objects.  The
    registry is reset each time a new sketch is opened or closed.

    Also provides geometry primitives used by the sketch-dimension pipeline:
    coordinate extraction, segment endpoint reading, shared-vertex detection,
    and smart-dimension placement-point calculation.

    Attributes:
        _adapter: Back-reference to the owning ``PyWin32Adapter`` instance.
    """

    def __init__(self, adapter: "PyWin32Adapter") -> None:
        """Store a back-reference to the owning adapter.

        Args:
            adapter: The ``PyWin32Adapter`` instance that created this
                service.  Provides access to ``_sketch_entities`` and
                ``_sketch_entity_counter``.
        """
        self._adapter = adapter

    def reset_registry(self) -> None:
        """Clear the sketch entity registry and reset the ID counter.

        Should be called at the start of every new sketch (via
        ``adapter._reset_sketch_entity_registry``) so that entity IDs from a
        previous sketch do not bleed into the current session.

        Side Effects:
            Clears ``adapter._sketch_entities``, drops the cached
            ``adapter._sketch_origin_point``, and sets
            ``adapter._sketch_entity_counter`` to ``0``.
        """
        self._adapter._sketch_entities.clear()
        self._adapter._sketch_entity_centers.clear()
        self._adapter._sketch_origin_point = None
        self._adapter._sketch_entity_counter = 0

    def register_entity(self, prefix: str, entity: Any) -> str:
        """Store a COM entity handle and return a stable string identifier.

        Increments the counter, derives an ID of the form
        ``"<prefix>_<counter>"`` (e.g. ``"Line_3"``), stores the entity in
        ``adapter._sketch_entities``, and returns the ID so callers can
        reference the entity in later dimension or constraint calls.

        Args:
            prefix: Descriptor for the entity type, e.g. ``"Line"``,
                ``"Circle"``, ``"Arc"``, ``"Rectangle"``.
            entity: Live SolidWorks COM entity object returned by the
                ``SketchManager`` create call.

        Returns:
            str: Stable entity ID, e.g. ``"Circle_2"``.

        Example::

            line_id = service.register_entity("Line", sw_line_obj)
            # line_id == "Line_1"
        """
        self._adapter._sketch_entity_counter += 1
        entity_id = f"{prefix}_{self._adapter._sketch_entity_counter}"
        # Re-bind single segments to their derived interface up front, so every
        # downstream reader (point/dimension/constraint resolution) sees an
        # ISketchLine/ISketchArc/… with its point accessors as declared methods
        # rather than the base ISketchSegment makepy wraps the create-call return
        # in. Groups (rectangle/polygon -> list) and non-segments (dimension/
        # relation) are stored untouched.
        if prefix in _SEGMENT_PREFIXES and not isinstance(entity, (list, tuple)):
            entity = sw_type_info.concrete_sketch_segment(entity)
        self._adapter._sketch_entities[entity_id] = entity
        return entity_id

    def select_entity(self, entity: Any, append: bool) -> bool:
        """Select a COM entity in the SolidWorks selection manager.

        Tries three COM selection methods in decreasing API version order:
        ``Select4`` (modern), ``Select2`` (legacy), ``Select`` (oldest).  The
        first call that returns a truthy value terminates the search.

        Args:
            entity: Live SolidWorks COM sketch entity object (line, arc,
                circle, etc.).
            append: When ``True``, the entity is added to the existing
                selection set.  When ``False``, existing selections are
                cleared first.

        Returns:
            bool: ``True`` if any of the three select methods succeeded;
            ``False`` if all failed or raised.
        """
        # Bind to the interface that declares ``Select``/``Select2``/``Select4``
        # for THIS entity's type, so the select resolves by DISPID:
        #  - a registered segment is bound to a DERIVED ``ISketchArc``/
        #    ``ISketchLine``/… (which declares no ``Select*``) -> ``ISketchSegment``
        #    (``Select4`` DISPID 65562);
        #  - a sketch POINT already carries them (``ISketchPoint``, ``Select4``
        #    DISPID 25) and passes through untouched.
        # NEVER rebind a segment to ``IEntity``: its ``Select4`` (65556) aliases
        # ``ISketchSegment.Select2`` on the object's dispinterface.
        target = entity
        if any(
            sw_type_info.is_early_bound(entity, iface)
            for iface in _DERIVED_SKETCH_SEGMENT_INTERFACES
        ):
            target = sw_type_info.early_bound(entity, "ISketchSegment")
        selected = self._adapter._attempt(
            lambda: bool(target.Select4(append, None)),
            default=False,
        )
        if selected:
            return True

        selected = self._adapter._attempt(
            lambda: bool(target.Select2(append, 0)),
            default=False,
        )
        if selected:
            return True

        return bool(
            self._adapter._attempt(
                lambda: bool(target.Select(append)),
                default=False,
            )
        )

    def set_display_dimension_value(self, display_dim: Any, value_mm: float) -> None:
        """Set the numeric value of a display-dimension object.

        Converts the value from millimetres to metres and tries three COM
        paths in order:

        1. ``GetDimension2(0).SetSystemValue3(value_m, 1, None)`` — modern.
        2. ``GetDimension().SetSystemValue2(value_m, 1)`` — legacy.
        3. Direct ``SystemValue`` property assignment — oldest.

        Args:
            display_dim: SolidWorks display-dimension COM object returned by
                ``Extension.AddDimension``.
            value_mm: Desired dimension value in **millimetres**.  Converted
                to metres internally.
        """
        value_m = value_mm / 1000.0
        dimension_obj = self._adapter._attempt(
            lambda: display_dim.GetDimension2(0), default=None
        )
        if dimension_obj is None:
            dimension_obj = self._adapter._attempt(
                lambda: display_dim.GetDimension(), default=None
            )
        if dimension_obj is None:
            dimension_obj = display_dim

        if (
            self._adapter._attempt(
                lambda: dimension_obj.SetSystemValue3(value_m, 1, None), default=None
            )
            is not None
        ):
            return
        if (
            self._adapter._attempt(
                lambda: dimension_obj.SetSystemValue2(value_m, 1), default=None
            )
            is not None
        ):
            return

        if hasattr(dimension_obj, "SystemValue"):
            dimension_obj.SystemValue = value_m

    def point_xyz(self, point_obj: Any) -> tuple[float, float, float] | None:
        """Extract the XYZ coordinates from a SolidWorks point-like COM object.

        Tries two access patterns:

        1. Direct attribute access — ``point_obj.X``, ``point_obj.Y``,
           ``point_obj.Z`` (``IMathPoint``, ``IVertex``).
        2. Method call — ``point_obj.GetCoords()`` returning a sequence of
           at least three numbers.

        All values are in **metres** (SolidWorks internal units).

        Args:
            point_obj: Any COM object that might expose XYZ coordinates.
                ``None`` is accepted and returns ``None`` immediately.

        Returns:
            tuple[float, float, float] | None: ``(x, y, z)`` in metres, or
            ``None`` when no coordinate pattern matches.
        """
        if point_obj is None:
            return None

        if (
            hasattr(point_obj, "X")
            and hasattr(point_obj, "Y")
            and hasattr(point_obj, "Z")
        ):
            x = self._adapter._attempt(lambda: float(point_obj.X), default=None)
            y = self._adapter._attempt(lambda: float(point_obj.Y), default=None)
            z = self._adapter._attempt(lambda: float(point_obj.Z), default=None)
            if x is not None and y is not None and z is not None:
                return (x, y, z)

        coords = self._adapter._attempt(lambda: point_obj.GetCoords(), default=None)
        if isinstance(coords, (list, tuple)) and len(coords) >= 3:
            return (float(coords[0]), float(coords[1]), float(coords[2]))

        return None

    def set_point_xyz(self, point_obj: Any, x: float, y: float, z: float) -> bool:
        """Set coordinates on a SolidWorks point-like COM object.

        Tries ``SetCoords(x, y, z)`` first (modern API), then
        ``SetCoords2(x, y, z)`` (older variant).  All values should be in
        **metres**.

        Args:
            point_obj: COM point object to update, or ``None``.
            x: New X coordinate in metres.
            y: New Y coordinate in metres.
            z: New Z coordinate in metres.

        Returns:
            bool: ``True`` when a setter call succeeded; ``False`` otherwise
            (including when ``point_obj`` is ``None``).
        """
        if point_obj is None:
            return False
        if (
            self._adapter._attempt(lambda: point_obj.SetCoords(x, y, z), default=None)
            is not None
        ):
            return True
        if (
            self._adapter._attempt(lambda: point_obj.SetCoords2(x, y, z), default=None)
            is not None
        ):
            return True
        return False

    def read_segment_endpoints(
        self, entity: Any
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        """Read the start and end coordinates of a sketch line or arc segment.

        Reads ``entity.GetStartPoint`` and ``entity.GetEndPoint``. On an
        unflagged dispatch these resolve as properties (bare access returns
        the coordinate tuple); once ``sw_type_info.flag_methods`` has touched
        the entity — e.g. after a point ref like ``"Line_1.end"`` resolved on
        it — they resolve as methods and bare access returns a bound method
        instead (verified live on SW 2026, same drift class as issue #29).
        Both resolutions are handled.

        Args:
            entity: SolidWorks ``ISketchLine`` or ``ISketchArc`` COM object.

        Returns:
            tuple[tuple, tuple] | None: ``((x1, y1, z1), (x2, y2, z2))`` in
            metres, or ``None`` when the attributes are absent or empty.
        """

        def _coords(member: str) -> Any | None:
            value = self._adapter._attempt(
                lambda: getattr(entity, member)(), default=None
            )
            if value is not None:
                return value
            raw = self._adapter._attempt(lambda: getattr(entity, member), default=None)
            return None if callable(raw) else raw

        start = _coords("GetStartPoint")
        end = _coords("GetEndPoint")
        if (
            isinstance(start, tuple)
            and len(start) >= 3
            and isinstance(end, tuple)
            and len(end) >= 3
        ):
            return (
                (float(start[0]), float(start[1]), float(start[2])),
                (float(end[0]), float(end[1]), float(end[2])),
            )
        return None

    def segment_point_objects(self, entity: Any) -> tuple[Any | None, Any | None]:
        """Return the COM point objects at the start and end of a segment.

        Unlike :meth:`read_segment_endpoints`, this returns the raw COM
        objects (``ISketchPoint``) rather than coordinate tuples, so they can
        be used in selection calls for angular dimensioning.

        Args:
            entity: SolidWorks sketch segment COM object.

        Returns:
            tuple[Any | None, Any | None]: ``(start_point_obj, end_point_obj)``;
            either element may be ``None`` if the accessor is absent.
        """
        self._adapter._attempt(
            lambda: sw_type_info.flag_methods(
                entity, "ISketchArc", "ISketchLine", "ISketchSpline"
            ),
            default=0,
        )

        def _point(member: str) -> Any | None:
            # Flagged method call first (the resolution probed live on
            # SW 2026); bare property access kept as the legacy fallback
            # for unflagged dispatches.
            value = self._adapter._attempt(
                lambda: getattr(entity, member)(), default=None
            )
            if value is not None:
                return value
            raw = self._adapter._attempt(lambda: getattr(entity, member), default=None)
            return None if callable(raw) else raw

        return (_point("GetStartPoint2"), _point("GetEndPoint2"))

    def shared_segment_vertex(
        self, entity1: Any, entity2: Any
    ) -> tuple[Any, Any, Any] | None:
        """Find a vertex point shared by two sketch segments.

        Compares all four endpoint-object pairs (2 from each segment) using a
        coordinate tolerance of 1e-6 m.  Used by the angular-dimension
        pipeline to locate the pivot vertex between two lines.

        Args:
            entity1: First SolidWorks sketch segment COM object.
            entity2: Second SolidWorks sketch segment COM object.

        Returns:
            tuple[Any, Any, Any] | None: ``(shared_point_obj, point1_obj,
            point2_obj)`` where ``shared_point_obj`` is the common vertex
            (same object as ``point1_obj`` in current implementation), or
            ``None`` when no shared vertex is found.
        """
        points1 = self.segment_point_objects(entity1)
        points2 = self.segment_point_objects(entity2)
        tol = 1e-6
        for point1 in points1:
            xyz1 = self.point_xyz(point1)
            if xyz1 is None:
                continue
            for point2 in points2:
                xyz2 = self.point_xyz(point2)
                if xyz2 is None:
                    continue
                if (
                    abs(xyz1[0] - xyz2[0]) <= tol
                    and abs(xyz1[1] - xyz2[1]) <= tol
                    and abs(xyz1[2] - xyz2[2]) <= tol
                ):
                    return (point1, point1, point2)
        return None

    def smart_dimension_direction(self, dx: float, dy: float) -> int:
        """Map a 2-D direction vector to a SolidWorks dimension-direction constant.

        The dominant axis determines horizontal vs vertical; within each axis
        the sign selects left/right or up/down.

        Args:
            dx: Horizontal component of the dimension normal vector.
            dy: Vertical component of the dimension normal vector.

        Returns:
            int: One of the four ``swSmartDimensionDirection*`` constants
            from ``adapter.constants``:
            ``swSmartDimensionDirectionRight``,
            ``swSmartDimensionDirectionLeft``,
            ``swSmartDimensionDirectionUp``, or
            ``swSmartDimensionDirectionDown``.
        """
        if abs(dx) >= abs(dy):
            return (
                self._adapter.constants["swSmartDimensionDirectionRight"]
                if dx >= 0.0
                else self._adapter.constants["swSmartDimensionDirectionLeft"]
            )
        return (
            self._adapter.constants["swSmartDimensionDirectionUp"]
            if dy >= 0.0
            else self._adapter.constants["swSmartDimensionDirectionDown"]
        )

    def single_line_dimension_placement(
        self, entity: Any
    ) -> tuple[float, float, float, int] | None:
        """Compute the text-placement point and direction for a linear dimension.

        Reads the segment midpoint, computes the outward normal (perpendicular
        to the segment direction), offsets the placement point by 35 % of the
        segment length (clamped to 10–20 mm), and converts the normal to a
        SolidWorks dimension-direction constant.

        Args:
            entity: SolidWorks ``ISketchLine`` or ``ISketchArc`` COM object.

        Returns:
            tuple[float, float, float, int] | None:
            ``(text_x, text_y, text_z, direction)`` in metres, or ``None``
            when endpoint data is unavailable.

        Example::

            placement = service.single_line_dimension_placement(line_obj)
            if placement:
                text_x, text_y, text_z, direction = placement
        """
        endpoints = self.read_segment_endpoints(entity)
        if endpoints is None:
            return None

        (x1, y1, z1), (x2, y2, z2) = endpoints
        dx = x2 - x1
        dy = y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        if length <= 1e-9:
            return None

        mid_x = (x1 + x2) / 2.0
        mid_y = (y1 + y2) / 2.0
        mid_z = (z1 + z2) / 2.0

        normal_x = -dy / length
        normal_y = dx / length
        offset = max(0.01, min(0.02, length * 0.35))
        text_x = mid_x + normal_x * offset
        text_y = mid_y + normal_y * offset
        direction = self.smart_dimension_direction(normal_x, normal_y)
        return (text_x, text_y, mid_z, direction)

    def angular_dimension_placement(
        self, entity1: Any, entity2: Any
    ) -> tuple[float, float, float, int] | None:
        """Compute the text-placement point for an angular dimension between two lines.

        Detects the shared vertex, derives the two ray directions, bisects
        the angle, offsets the placement point by 15–30 mm along the bisector
        (clamped to 60 % of the shorter leg), and converts the bisector to a
        dimension-direction constant.

        Args:
            entity1: First SolidWorks sketch-line COM object.
            entity2: Second SolidWorks sketch-line COM object (must share a
                vertex with ``entity1``).

        Returns:
            tuple[float, float, float, int] | None:
            ``(text_x, text_y, text_z, direction)`` in metres, or ``None``
            when no shared vertex is found or segment data is unavailable.
        """
        endpoints1 = self.read_segment_endpoints(entity1)
        endpoints2 = self.read_segment_endpoints(entity2)
        if endpoints1 is None or endpoints2 is None:
            return None

        pts1 = endpoints1
        pts2 = endpoints2
        tol = 1e-6
        vertex = None
        ray1 = None
        ray2 = None
        for p1 in pts1:
            for p2 in pts2:
                if (
                    abs(p1[0] - p2[0]) <= tol
                    and abs(p1[1] - p2[1]) <= tol
                    and abs(p1[2] - p2[2]) <= tol
                ):
                    vertex = p1
                    ray1 = pts1[1] if pts1[0] == p1 else pts1[0]
                    ray2 = pts2[1] if pts2[0] == p2 else pts2[0]
                    break
            if vertex is not None:
                break

        if vertex is None or ray1 is None or ray2 is None:
            return None

        v1x = ray1[0] - vertex[0]
        v1y = ray1[1] - vertex[1]
        v2x = ray2[0] - vertex[0]
        v2y = ray2[1] - vertex[1]
        l1 = (v1x * v1x + v1y * v1y) ** 0.5
        l2 = (v2x * v2x + v2y * v2y) ** 0.5
        if l1 <= 1e-9 or l2 <= 1e-9:
            return None

        b1x = v1x / l1
        b1y = v1y / l1
        b2x = v2x / l2
        b2y = v2y / l2
        bis_x = b1x + b2x
        bis_y = b1y + b2y
        if abs(bis_x) <= 1e-9 and abs(bis_y) <= 1e-9:
            bis_x = -b1y
            bis_y = b1x

        bis_len = (bis_x * bis_x + bis_y * bis_y) ** 0.5
        bis_x /= bis_len
        bis_y /= bis_len
        offset = max(0.015, min(0.03, min(l1, l2) * 0.6))
        text_x = vertex[0] + bis_x * offset
        text_y = vertex[1] + bis_y * offset
        direction = self.smart_dimension_direction(bis_x, bis_y)
        return (text_x, text_y, vertex[2], direction)


class _DocumentRoutingService:
    """Resolve document identity and select the export-target document.

    Provides two helpers that isolate the policy for identifying which COM
    document object to use during export operations.  The service prefers the
    SolidWorks ``ActiveDoc`` when it matches the adapter\'s current model, and
    falls back gracefully when path or title data is unavailable.

    Attributes:
        _adapter: Back-reference to the owning ``PyWin32Adapter`` instance.
    """

    def __init__(self, adapter: "PyWin32Adapter") -> None:
        """Store a back-reference to the owning adapter.

        Args:
            adapter: The ``PyWin32Adapter`` instance that created this
                service.
        """
        self._adapter = adapter

    def document_identity(self, document: Any) -> tuple[str | None, str | None]:
        """Return the normalised absolute path and display title for a COM document.

        Tries ``document.GetPathName()`` first; falls back to
        ``getattr(document, 'GetPathName', None)`` for COM objects that expose
        the path as a property rather than a method.  Applies the same
        two-step pattern for ``GetTitle``.

        Args:
            document: A SolidWorks ``IModelDoc2`` COM object, or ``None``.

        Returns:
            tuple[str | None, str | None]: ``(absolute_path, title)`` where
            ``absolute_path`` is ``os.path.abspath`` normalised and
            ``title`` is the raw display title.  Either element is ``None``
            when the corresponding attribute is absent or empty.
        """
        if document is None:
            return None, None

        raw_path = self._adapter._attempt(lambda: document.GetPathName(), default=None)
        if raw_path is None:
            raw_path = self._adapter._attempt(
                lambda: getattr(document, "GetPathName", None), default=None
            )
        path_value = str(raw_path).strip() if raw_path else ""
        normalized_path = os.path.abspath(path_value) if path_value else None

        raw_title = self._adapter._attempt(lambda: document.GetTitle(), default=None)
        if raw_title is None:
            raw_title = self._adapter._attempt(
                lambda: getattr(document, "GetTitle", None), default=None
            )
        title_value = str(raw_title).strip() if raw_title else ""

        return normalized_path, title_value or None

    def resolve_export_target_doc(self) -> Any:
        """Resolve the safest document to use for export operations.

        Policy (in order):

        1. If ``adapter.currentModel`` is ``None``, use ``swApp.ActiveDoc``.
        2. If ``swApp.ActiveDoc`` is ``None``, use ``adapter.currentModel``.
        3. If both have path strings and the paths match, prefer
           ``swApp.ActiveDoc`` (it may have a more up-to-date state).
        4. If both have title strings that match, prefer ``swApp.ActiveDoc``.
        5. Otherwise fall back to ``adapter.currentModel``.

        Returns:
            Any: The SolidWorks ``IModelDoc2`` COM object to use for export,
            or ``None`` when neither ``swApp`` nor ``currentModel`` is set.
        """
        active_doc = (
            getattr(self._adapter.swApp, "ActiveDoc", None)
            if self._adapter.swApp
            else None
        )
        if self._adapter.currentModel is None:
            return active_doc
        if active_doc is None:
            return self._adapter.currentModel

        current_path, current_title = self.document_identity(self._adapter.currentModel)
        active_path, active_title = self.document_identity(active_doc)

        if current_path and active_path:
            return (
                active_doc
                if current_path == active_path
                else self._adapter.currentModel
            )
        if current_title and active_title and current_title == active_title:
            return active_doc
        return self._adapter.currentModel


class _FeatureSelectionService:
    """Encapsulate feature-selection strategies and name-candidate expansion.

    SolidWorks allows features to be selected by bare name or by the
    ``<name>@<document>`` qualified syntax.  Several selection APIs also
    exist with different levels of support across SolidWorks versions.
    This service centralises all of that complexity so the main adapter
    methods stay thin.

    Attributes:
        _adapter: Back-reference to the owning ``PyWin32Adapter`` instance.
    """

    def __init__(self, adapter: "PyWin32Adapter") -> None:
        """Store a back-reference to the owning adapter.

        Args:
            adapter: The ``PyWin32Adapter`` instance that created this
                service.
        """
        self._adapter = adapter

    @staticmethod
    def normalize_feature_name(raw_name: str | None) -> str:
        """Normalise a feature name for case-insensitive comparison.

        Strips surrounding whitespace and quotes then converts to
        ``casefold``-lowercase so that mixed-case names such as
        ``'Boss-Extrude1'``, ``" boss-extrude1 "`` and ``'"Boss-Extrude1"'``
        all compare equal.

        Args:
            raw_name: Raw feature name string, or ``None``.

        Returns:
            str: Normalised name.  Empty string when ``raw_name`` is
            ``None`` or blank.

        Example::

            svc.normalize_feature_name('"Boss-Extrude1"') == 'boss-extrude1'
        """
        return str(raw_name or "").strip().strip('"').casefold()

    def build_feature_candidate_names(
        self, feature_name: str, target_doc: Any
    ) -> list[str]:
        """Build a list of bare and document-qualified selection candidates.

        SolidWorks requires the ``"<name>@<document>"`` syntax for
        ``SelectByID2`` on assembly contexts.  This method tries to read the
        document title and produces both bare and qualified variants so that
        callers do not need to duplicate that logic.

        Args:
            feature_name: The bare feature name as supplied by the caller
                (e.g. ``"Boss-Extrude1"``).
            target_doc: SolidWorks ``IModelDoc2`` COM object whose title is
                used to form the qualified name.  Errors reading the title
                are silently swallowed.

        Returns:
            list[str]: Candidate list, always including ``feature_name`` as
            the first element.  Qualified variants are appended when a non-
            empty title is available.  Example::

                ["Boss-Extrude1", "Boss-Extrude1@Part1", "Boss-Extrude1@Part1.SLDPRT"]
        """
        doc_title = ""
        doc_stem = ""
        try:
            raw_title = str(target_doc.GetTitle() or "").strip()
            if raw_title:
                doc_title = raw_title
                doc_stem = raw_title.rsplit(".", 1)[0]
        except Exception:
            pass

        candidates: list[str] = [feature_name]
        if doc_stem:
            candidates.append(f"{feature_name}@{doc_stem}")
        if doc_title and doc_title != doc_stem:
            candidates.append(f"{feature_name}@{doc_title}")
        return candidates

    def try_select_by_extension(
        self,
        target_doc: Any,
        candidate_names: list[str],
        feature_name: str,
    ) -> dict[str, Any] | None:
        """Attempt feature selection via ``Extension.SelectByID2``.

        Iterates the Cartesian product of ``candidate_names`` × entity-type
        strings.  Entity types tried (in order): ``"BODYFEATURE"``,
        ``"COMPONENT"``, ``"SKETCH"``, ``"PLANE"``, ``"MATE"``, ``""`` (auto).
        Returns on the first successful selection.

        Args:
            target_doc: SolidWorks ``IModelDoc2`` COM object.
            candidate_names: Ordered list of name strings to try (bare and
                qualified variants from :meth:`build_feature_candidate_names`).
            feature_name: The original caller-supplied name, included in the
                result payload for traceability.

        Returns:
            dict[str, Any] | None: On success, a result dict with keys
            ``selected``, ``feature_name``, ``selected_name``,
            ``entity_type``.  ``None`` when all attempts fail.
        """
        entity_types = ["BODYFEATURE", "COMPONENT", "SKETCH", "PLANE", "MATE", ""]
        for candidate in candidate_names:
            for entity_type in entity_types:
                try:
                    selected = target_doc.Extension.SelectByID2(
                        candidate, entity_type, 0, 0, 0, False, 0, null_callout(), 0
                    )
                    if selected:
                        return {
                            "selected": True,
                            "feature_name": feature_name,
                            "selected_name": candidate,
                            "entity_type": entity_type or "auto",
                        }
                except Exception:
                    continue
        return None

    def try_select_by_component(
        self,
        target_doc: Any,
        candidate_names: list[str],
        feature_name: str,
    ) -> dict[str, Any] | None:
        """Attempt component selection for assembly-context features.

        Calls ``target_doc.GetComponentByName`` (when available) and then
        tries three selector methods on the resulting component object:
        ``Select4(False, None, False)``, ``Select(False,)``, and
        ``Select2(False, 0)``.

        This path handles assembly components that are not reachable through
        ``SelectByID2`` alone.

        Args:
            target_doc: SolidWorks ``IAssemblyDoc`` or ``IModelDoc2`` COM
                object.
            candidate_names: List of candidate name strings.  Only the part
                before the first ``@`` is used as the component name.
            feature_name: Original caller-supplied name for the result
                payload.

        Returns:
            dict[str, Any] | None: Success dict (same schema as
            :meth:`try_select_by_extension`) or ``None`` when not applicable
            or all attempts fail.
        """
        # ``GetComponentByName`` is an ``IAssemblyDoc`` member; ``target_doc`` may
        # be an ``IModelDoc2`` handle. Rebind to the concrete doc interface — an
        # assembly resolves to ``IAssemblyDoc`` (has it), a part to ``IPartDoc``
        # (does not), so the ``getattr(..., None)`` guard short-circuits for parts.
        typed_doc = sw_type_info.early_bound_doc(target_doc)
        get_component_by_name = getattr(typed_doc, "GetComponentByName", None)
        if not callable(get_component_by_name):
            return None

        for candidate in candidate_names:
            component_name = candidate.split("@", 1)[0]
            component = self._adapter._attempt(
                lambda name=component_name: get_component_by_name(name),
                default=None,
            )
            if component is None:
                continue
            for method_name, args in [
                ("Select4", (False, None, False)),
                ("Select", (False,)),
                ("Select2", (False, 0)),
            ]:
                selector = getattr(component, method_name, None)
                if not callable(selector):
                    continue
                try:
                    if bool(selector(*args)):
                        return {
                            "selected": True,
                            "feature_name": feature_name,
                            "selected_name": component_name,
                            "entity_type": f"component:{method_name}",
                        }
                except Exception:
                    continue
        return None

    def try_select_by_feature_tree(
        self,
        target_doc: Any,
        feature_name: str,
        candidate_names: list[str],
    ) -> dict[str, Any] | None:
        """Walk the SolidWorks feature tree and select the first matching feature.

        Iterates via ``FirstFeature`` / ``GetNextFeature`` (up to 10 000
        features as a runaway guard) and compares each feature\'s ``Name``
        attribute against the normalised candidate set.  Matching is
        case-insensitive and also strips the ``@document`` qualifier.

        This is the most expensive selection strategy and is only attempted
        after :meth:`try_select_by_extension` and
        :meth:`try_select_by_component` have both failed.

        Args:
            target_doc: SolidWorks ``IModelDoc2`` COM object.
            feature_name: Original caller-supplied name for the result
                payload.
            candidate_names: Candidate names used to build the normalised
                match set.

        Returns:
            dict[str, Any] | None: Success dict (same schema as
            :meth:`try_select_by_extension`) with ``entity_type`` set to
            ``"feature-tree"``, or ``None`` when no match is found.
        """
        normalized_candidates = {
            self.normalize_feature_name(c)
            for c in candidate_names
            if self.normalize_feature_name(c)
        }
        normalized_bases = {c.split("@", 1)[0] for c in normalized_candidates if c}

        feature = self._adapter._attempt(lambda: target_doc.FirstFeature())
        guard = 0
        while feature and guard < 10000:
            guard += 1
            feature_ref = feature
            tree_name = self._adapter._attempt(
                lambda current_feature=feature_ref: str(current_feature.Name or ""),
                default="",
            )
            if self._matches_candidate_name(
                tree_name, normalized_candidates, normalized_bases
            ):
                try:
                    if feature.Select2(False, 0):
                        return {
                            "selected": True,
                            "feature_name": feature_name,
                            "selected_name": tree_name or feature_name,
                            "entity_type": "feature-tree",
                        }
                except Exception:
                    pass
            next_feature = self._adapter._attempt(
                lambda current_feature=feature_ref: current_feature.GetNextFeature()
            )
            if next_feature is None:
                break
            feature = next_feature
        return None

    @classmethod
    def _matches_candidate_name(
        cls,
        raw_name: str | None,
        normalized_candidates: set[str],
        normalized_bases: set[str],
    ) -> bool:
        """Check whether a raw feature name matches candidate name sets.

        Args:
            raw_name: Name read from the feature tree.
            normalized_candidates: Full normalized candidate names.
            normalized_bases: Candidate names with any ``@doc`` suffix removed.

        Returns:
            bool: ``True`` when name matches either full or base candidate sets.
        """
        normalized_name = cls.normalize_feature_name(raw_name)
        if not normalized_name:
            return False
        if normalized_name in normalized_candidates:
            return True
        return normalized_name.split("@", 1)[0] in normalized_bases

    def select_feature(self, feature_name: str) -> dict[str, Any]:
        """Run all feature-selection strategies and return best-effort payload.

        Args:
            feature_name: Feature name requested by caller.

        Returns:
            dict[str, Any]: Selection result payload.
        """
        target_doc = self._adapter.currentModel
        candidate_names = self.build_feature_candidate_names(feature_name, target_doc)

        result = self.try_select_by_extension(target_doc, candidate_names, feature_name)
        if result:
            return result

        result = self.try_select_by_component(target_doc, candidate_names, feature_name)
        if result:
            return result

        result = self.try_select_by_feature_tree(
            target_doc, feature_name, candidate_names
        )
        if result:
            return result

        return {
            "selected": False,
            "feature_name": feature_name,
            "selected_name": feature_name,
        }

    def list_features(self, include_suppressed: bool = False) -> list[dict[str, Any]]:
        """Enumerate model features using primary and fallback traversal paths.

        Args:
            include_suppressed: Include suppressed features when ``True``.

        Returns:
            list[dict[str, Any]]: Ordered feature descriptors.
        """
        features: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        feature = self._adapter._attempt(
            lambda: self._adapter._get_attr_or_call(
                self._adapter.currentModel, "FirstFeature"
            )
        )
        feature = sw_type_info.early_bound_or_flag(
            feature,
            "IFeature",
            "GetTypeName2",
            "IsSuppressed",
            "GetNextFeature",
        )
        pos = 0
        guard = 0
        while feature and guard < 10000:
            self._append_feature_to(features, seen, feature, pos, include_suppressed)
            pos += 1
            guard += 1
            next_feature = self._adapter._attempt(
                lambda current_feature=feature: self._adapter._get_attr_or_call(
                    current_feature, "GetNextFeature"
                )
            )
            if next_feature is None:
                break
            feature = sw_type_info.early_bound_or_flag(
                next_feature,
                "IFeature",
                "GetTypeName2",
                "IsSuppressed",
                "GetNextFeature",
            )

        if features:
            return features

        feature_manager = getattr(self._adapter.currentModel, "FeatureManager", None)
        count = self._adapter._attempt(
            lambda: int(feature_manager.GetFeatureCount(True) or 0), default=0
        )
        # FeatureByPositionReverse is ZERO-based: 0 is the last feature.
        for reverse_pos in range(count):
            feature = self._adapter._attempt(
                lambda pos=reverse_pos: (
                    self._adapter.currentModel.FeatureByPositionReverse(pos)
                )
            )
            if feature is None:
                continue
            feature = sw_type_info.early_bound_or_flag(
                feature, "IFeature", "GetTypeName2", "IsSuppressed"
            )
            self._append_feature_to(
                features,
                seen,
                feature,
                count - 1 - reverse_pos,
                include_suppressed,
            )

        return features

    def _append_feature_to(
        self,
        features: list[dict[str, Any]],
        seen: set[tuple[str, str]],
        feature: Any,
        position: int,
        include_suppressed: bool,
    ) -> None:
        """Append one feature descriptor when dedupe and suppression rules allow.

        Args:
            features: Output list being populated.
            seen: Dedupe set of ``(name, type)`` keys.
            feature: Feature COM object.
            position: Display position index.
            include_suppressed: Include suppressed entries when ``True``.
        """
        name = str(getattr(feature, "Name", ""))
        feature_type = str(
            self._adapter._attempt(
                lambda: self._adapter._get_attr_or_call(feature, "GetTypeName2"),
                default="Unknown",
            )
        )
        dedupe_key = (name, feature_type)
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)

        suppressed = self._is_feature_suppressed(feature)
        if not include_suppressed and suppressed:
            return

        features.append(
            {
                "name": name,
                "type": feature_type,
                "suppressed": suppressed,
                "position": position,
            }
        )

    def _is_feature_suppressed(self, feature: Any) -> bool:
        """Determine feature suppression state across COM API variants.

        Args:
            feature: Feature COM object.

        Returns:
            bool: ``True`` when feature is suppressed.
        """
        suppressed_direct = self._adapter._attempt(
            lambda: self._adapter._get_attr_or_call(feature, "IsSuppressed"),
            default=None,
        )
        if suppressed_direct is not None:
            return bool(suppressed_direct)

        suppressed_result = self._adapter._attempt(
            lambda: feature.IsSuppressed2(0, []), default=None
        )
        if isinstance(suppressed_result, (tuple, list)):
            return bool(suppressed_result[0]) if suppressed_result else False
        return bool(suppressed_result) if suppressed_result is not None else False


class PyWin32Adapter(
    SolidWorksSketchMixin,
    SolidWorksAssemblyMixin,
    SolidWorksFeaturesMixin,
    SolidWorksReferenceGeometryMixin,
    SolidWorksParametricsMixin,
    SolidWorksMeasureMixin,
    SolidWorksMotionMixin,
    SolidWorksManufacturingMixin,
    SolidWorksIOMixin,
    SolidWorksSelectionMixin,
    SolidWorksAdapter,
):
    """SolidWorks adapter using pywin32 COM integration.

    This adapter provides direct COM integration with SolidWorks using pywin32, enabling
    real-time automation and control of SolidWorks applications on Windows.

    Args:
        config (dict[str, Any] | None): Configuration values for the operation. Defaults to
                                        None.

    Raises:
        SolidWorksMCPError: PyWin32Adapter requires Windows platform.

    Attributes:
        constants (Any): The constants value.

    Example:
                        ```python
                        adapter = PyWin32Adapter({'timeout': 30})
                        result = await adapter.connect()
                        if result.status == AdapterResultStatus.SUCCESS:
                            print("Connected to SolidWorks successfully")
                        ```
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize PyWin32Adapter with configuration.

        Args:
            config (dict[str, Any] | None): Configuration values for the operation. Defaults to
                                            None.

        Returns:
            None: None.

        Raises:
            SolidWorksMCPError: PyWin32Adapter requires Windows platform.

        Example:
                            ```python
                            config = {
                                "timeout": 30,
                                "auto_connect": True,
                                "startup_timeout": 60
                            }
                            adapter = PyWin32Adapter(config)
                            ```
        """
        if not PYWIN32_AVAILABLE:  # pragma: no cover
            raise SolidWorksMCPError(
                "pywin32 is not available. Install with: pip install pywin32"
            )

        if platform.system() != "Windows":  # pragma: no cover
            raise SolidWorksMCPError("PyWin32Adapter requires Windows platform")

        super().__init__(config)

        self.swApp: Any | None = None
        self.currentModel: Any | None = None
        self.currentSketch: Any | None = None
        self.currentSketchManager: Any | None = None
        self._last_sketch_name: str | None = None
        self._sketch_count: int = 0  # incremented each time a sketch is created
        self._sketch_entities: dict[str, Any] = {}
        # Cached (center_x_mm, center_y_mm) for entities whose center can't be
        # recovered via ``GetCenterPoint`` — currently polygons, which register
        # as a SAFEARRAY of segment handles (no single dispatch to read from).
        # ``sketch_circular_pattern`` reads this to derive the seed-to-axis
        # offset for polygon seeds.
        self._sketch_entity_centers: dict[str, tuple[float, float]] = {}
        # Cached origin EXTSKETCHPOINT dispatch for the active sketch,
        # resolved lazily by the "origin" entity ref (see
        # solidworks.sketch._resolve_origin_point). Per-sketch: cleared by
        # ``reset_registry``.
        self._sketch_origin_point: Any | None = None
        self._sketch_entity_counter = 0
        self._com_initialized = False

        # COM constants (equivalent to SolidWorks API constants)
        self.constants = {
            # Document types
            "swDocPART": 1,
            "swDocASSEMBLY": 2,
            "swDocDRAWING": 3,
            # Selection types
            "swSelFACES": 1,
            "swSelEDGES": 2,
            "swSelVERTICES": 3,
            "swSelSKETCHSEGS": 4,
            "swSelSKETCHPOINTS": 5,
            "swSelDATUMPLANES": 6,
            # Feature end conditions
            "swEndCondBlind": 0,
            "swEndCondThroughAll": 1,
            "swEndCondUpToNext": 2,
            "swEndCondUpToSurface": 3,
            "swEndCondOffset": 4,
            "swEndCondUpToVertex": 5,
            "swEndCondMidPlane": 6,
            "swEndCondThroughAllBoth": 9,
            # Dimension preferences / directions
            "swInputDimValOnCreate": 10,
            "swSketchAcceptNumericInput": 372,
            "swSketchCreateDimensionOnlyWhenEntered": 520,
            "swScaleSketchOnFirstDimension": 642,
            "swSmartDimensionDirectionRight": 0,
            "swSmartDimensionDirectionUp": 1,
            "swSmartDimensionDirectionLeft": 2,
            "swSmartDimensionDirectionDown": 3,
        }

        self._session_coordinator = _ComSessionCoordinator(self)
        self._sketch_geometry = _SketchGeometryService(self)
        self._document_routing = _DocumentRoutingService(self)
        self._feature_selector = _FeatureSelectionService(self)

    def _initialize_com_apartment(self) -> None:
        """Initialize COM apartment once per adapter lifetime until disconnect.

        This helper keeps COM initialization balanced and explicit so failure paths can
        deterministically release COM resources.
        """
        self._session_coordinator.initialize_com_apartment()

    def _uninitialize_com_apartment(self) -> None:
        """Uninitialize COM apartment when it was initialized by this adapter."""
        self._session_coordinator.uninitialize_com_apartment()

    async def _acquire_solidworks_application(self) -> Any:
        """Acquire a running SolidWorks COM server or start one with retries.

        Returns:
            Any: SolidWorks application COM object.

        Raises:
            SolidWorksMCPError: If no application instance can be obtained.
        """
        return await self._session_coordinator.acquire_solidworks_application()

    async def _wait_for_server_ready(self, app: Any) -> None:
        """Wait until the SolidWorks COM server reports readiness.

        Args:
            app: SolidWorks application COM object.

        Raises:
            SolidWorksMCPError: If readiness probe times out.
        """
        await self._session_coordinator.wait_for_server_ready(app)

    def _set_automation_preferences(self, app: Any, *, interactive: bool) -> None:
        """Toggle SolidWorks warning/question prompts for automation safety.

        Args:
            app: SolidWorks application COM object.
            interactive: ``True`` restores dialogs, ``False`` suppresses them.
        """
        self._session_coordinator.set_automation_preferences(
            app, interactive=interactive
        )

    async def connect(self) -> None:
        """Connect to SolidWorks COM and prepare automation-safe session state.

        Raises:
            SolidWorksMCPError: If connection or readiness checks fail.
        """
        await self._session_coordinator.connect()

    async def disconnect(self) -> None:
        """Disconnect from SolidWorks application.

        Properly disconnects from SolidWorks COM interface and cleans up resources. This method
        should always be called when finished to prevent memory leaks.

        Note: - Clears references to current model and application - Uninitialize COM apartment
        - Does not close SolidWorks application itself

        Returns:
            None: None.

        Example:
                            ```python
                            try:
                                await adapter.connect()
                                # ... do work ...
                            finally:
                                await adapter.disconnect()
                            ```
        """
        await self._session_coordinator.disconnect()

    def is_connected(self) -> bool:
        """Check if connected to SolidWorks.

        Returns:
            bool: True if connected, otherwise False.

        Example:
                            ```python
                            if adapter.is_connected():
                                print("Ready to automate SolidWorks")
                            else:
                                await adapter.connect()
                            ```
        """
        return self.swApp is not None

    async def health_check(self) -> AdapterHealth:
        """Get adapter health status.

        Performs comprehensive health check including connection status, operation metrics, and
        SolidWorks application responsiveness.

        Returns:
            AdapterHealth: The result produced by the operation.

        Example:
                            ```python
                            health = await adapter.health_check()
                            if health.healthy:
                                print(f"Adapter healthy, {health.success_count} operations completed")
                            else:
                                print(f"Adapter unhealthy: {health.error_count} errors")
                            ```
        """
        healthy = self.is_connected()

        # Support both callable COM method and property-style RevisionNumber.
        sw_version: str | None = None
        if self.swApp:
            sw_version = self._attempt(
                lambda: self._get_attr_or_call(self.swApp, "RevisionNumber")
            )

        # Try a simple operation to verify connection
        if healthy:
            healthy = sw_version is not None

        return AdapterHealth(
            healthy=healthy,
            last_check=datetime.now(),
            error_count=int(self._metrics["errors_count"]),
            success_count=int(
                self._metrics["operations_count"] - self._metrics["errors_count"]
            ),
            average_response_time=self._metrics["average_response_time"],
            connection_status="connected" if healthy else "disconnected",
            metrics={
                "adapter_type": "pywin32",
                "sw_version": sw_version or "Unknown",
                "current_model": self.currentModel.GetTitle()
                if self.currentModel
                else None,
            },
        )

    def _handle_com_operation(
        self,
        operation_name: str,
        operation_func: Callable[..., T],
        *operation_args: Any,
        **operation_kwargs: Any,
    ) -> AdapterResult[T]:
        """Helper to handle COM operations with error handling and timing.

        Wraps COM operations with comprehensive error handling, performance metrics, and
        standardized result formatting. All SolidWorks COM calls should use this.

        Args:
            operation_name (str): The operation name value.
            operation_func (Callable[[], T]): The operation func value.

        Returns:
            AdapterResult[T]: The result produced by the operation.

        Example:
                            ```python
                            result = self._handle_com_operation(
                                "create_sketch",
                                lambda: self.swApp.ActiveDoc.SketchManager.InsertSketch(True)
                            )
                            if result.status == AdapterResultStatus.SUCCESS:
                                print("Sketch created successfully")
                            ```
        """
        start_time = time.time()

        try:
            result = operation_func(*operation_args, **operation_kwargs)
            execution_time = time.time() - start_time
            self.update_metrics(execution_time, True)
            return AdapterResult(
                status=AdapterResultStatus.SUCCESS,
                data=result,
                execution_time=execution_time,
            )
        except pywintypes.com_error as e:
            execution_time = time.time() - start_time
            self.update_metrics(execution_time, False)
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=f"COM error in {operation_name}: {e}",
                execution_time=execution_time,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            self.update_metrics(execution_time, False)
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=f"Error in {operation_name}: {e}",
                execution_time=execution_time,
            )

    def _attempt(
        self, operation: Callable[[], T], default: T | None = None
    ) -> T | None:
        """Build internal attempt.

        Keep non-critical fallback handling in one place instead of scattering broad try/except
        blocks throughout operation code.

        Args:
            operation (Callable[[], T]): Callable object executed by the helper.
            default (T | None): Fallback value returned when the operation fails. Defaults to
                                None.

        Returns:
            T | None: The result produced by the operation.
        """
        try:
            return operation()
        except Exception:
            return default

    def _attempt_with_error(
        self, operation: Callable[[], T]
    ) -> tuple[T | None, Exception | None]:
        """Build internal attempt with error.

        Args:
            operation (Callable[[], T]): Callable object executed by the helper.

        Returns:
            tuple[T | None, Exception | None]: A tuple containing the resulting values.
        """
        try:
            return operation(), None
        except Exception as exc:
            return None, exc

    def _get_attr_or_call(self, obj: Any, attr_name: str) -> Any:
        """Read COM attribute exposed as a property or zero-arg method.

        Args:
            obj (Any): The obj value.
            attr_name (str): The attr name value.

        Returns:
            Any: The result produced by the operation.
        """
        attr = getattr(obj, attr_name, None)
        return attr() if callable(attr) else attr

    def _get_feature_id(self, feature: Any) -> str:
        """Extract a stable string feature ID from COM feature objects.

        Some SolidWorks COM bindings return an int-like value from GetID(), while others return
        a .NET object exposing ToString().

        Args:
            feature (Any): The feature value.

        Returns:
            str: The resulting text value.
        """
        feature_id_getter = getattr(feature, "GetID", None)
        feature_id_value = (
            feature_id_getter() if callable(feature_id_getter) else feature_id_getter
        )
        to_string = getattr(feature_id_value, "ToString", None)
        return str(to_string() if callable(to_string) else feature_id_value)

    def _reset_sketch_entity_registry(self) -> None:
        """Clear transient sketch entity handles tracked for dimensioning."""
        self._sketch_geometry.reset_registry()

    def _register_sketch_entity(self, prefix: str, entity: Any) -> str:
        """Store sketch entity COM handle and return a stable entity identifier."""
        return self._sketch_geometry.register_entity(prefix, entity)

    def _select_sketch_entity(self, entity: Any, append: bool) -> bool:
        """Select a sketch entity using compatible COM select methods."""
        return self._sketch_geometry.select_entity(entity, append)

    def _set_display_dimension_value(self, display_dim: Any, value_mm: float) -> None:
        """Set created display dimension to the requested value in meters."""
        self._sketch_geometry.set_display_dimension_value(display_dim, value_mm)

    def _set_view_orientation(
        self, target_doc: Any, orientation: str, view_const: int
    ) -> None:
        """Set SolidWorks view orientation with graceful fallback.

        ShowNamedView2 can fail for assemblies with lightweight components,
        but screenshot can still succeed with current view. Logs warning on failure.

        Args:
            target_doc: SolidWorks model document
            orientation: Orientation name (for logging)
            view_const: SolidWorks view constant (1-9)

        Returns:
            None (operation always succeeds or fails silently)
        """
        try:
            target_doc.ShowNamedView2("", view_const)
        except Exception as exc:
            logger.warning(
                "[pywin32.export_image] ShowNamedView2({}) failed ({}), "
                "continuing with current view",
                orientation,
                exc,
            )

    def _zoom_to_fit(self, target_doc: Any) -> None:
        """Zoom model to fit viewport with fallback.

        Tries IModelDoc2.ViewZoomToFit2() first; falls back to
        IModelView.ZoomToFit() on the active view. Logs warning if both fail.

        Args:
            target_doc: SolidWorks model document

        Returns:
            None (operation always succeeds or fails silently)
        """
        try:
            # makepy spells it ``ViewZoomtofit2`` (lowercase ``f``); the mixed-case
            # ``ViewZoomToFit2`` misses the declared DISPID method and would resolve
            # through the late-bound fallback.
            target_doc.ViewZoomtofit2()
        except Exception:
            try:
                active_view = target_doc.ActiveView
                if active_view is not None:
                    active_view.ZoomToFit()
            except Exception as exc:
                logger.warning(
                    "[pywin32.export_image] ZoomToFit failed ({}), "
                    "screenshot may be zoomed out",
                    exc,
                )

    def _activate_target_doc(self, target_doc: Any) -> Any:
        """Bring ``target_doc``'s window to the foreground before capture.

        Both viewport capture paths (``SaveBMP`` and the ``SaveAs3`` image
        fallback) render the *active* window. With several documents open,
        exporting a background document silently yields the foreground
        document's pixels — including whatever stale view its hidden window
        last rendered.

        Args:
            target_doc: SolidWorks model document to activate.

        Returns:
            The activated document COM object, or ``target_doc`` unchanged
            when activation is not possible (e.g. identity unknown).
        """
        import ntpath

        path, title = self._document_identity(target_doc)
        # SolidWorks paths are always Windows-style; ntpath keeps the
        # basename split correct when the mock suite runs on Linux CI.
        name = ntpath.basename(path) if path else title
        if not name:
            return target_doc
        # Early-bound ISldWorks::ActivateDoc3 returns (model, errors): pass literal
        # 0 for the [out] Errors and consume the tuple. The retval is a DYNAMIC
        # dispatch (no resultCLSID), so rebind it to IModelDoc2 before handing it to
        # SaveBMP/SaveAs3 -- a raw tuple here silently defeated the activation this
        # method exists for.
        result = self._attempt(
            # swRebuildOnActivation_e.swDontRebuildActiveDoc = 1
            lambda: self.swApp.ActivateDoc3(name, False, 1, 0),
            default=None,
        )
        if not result:
            return target_doc
        activated, _errors = result
        if activated is None:
            return target_doc
        return sw_type_info.early_bound(activated, "IModelDoc2")

    def _save_screenshot_with_savebmp(
        self, target_doc: Any, resolved_path: str, width: int, height: int
    ) -> bool:
        """Capture the current view via ``IModelDoc2::SaveBMP``.

        ``SaveBMP`` is the only screenshot API that honours an explicit pixel
        size, but it always writes BMP. Non-BMP targets are captured to a
        temporary ``.bmp`` and converted with Pillow (optional ``vision``
        extra); without Pillow this returns ``False`` so the caller falls
        back to ``SaveAs3`` (window-sized render).

        Args:
            target_doc: SolidWorks model document
            resolved_path: Full path where to save image
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            True if file was created, False otherwise.
        """
        ext = os.path.splitext(resolved_path)[1].lower()
        if ext == ".bmp":
            try:
                success = target_doc.SaveBMP(resolved_path, width, height)
                return bool(success) and os.path.exists(resolved_path)
            except Exception as exc:
                logger.debug(
                    "[pywin32.export_image] SaveBMP failed ({}), "
                    "trying SaveAs3 image export",
                    exc,
                )
                return False

        image_module = _load_pillow_image()
        if image_module is None:
            logger.debug(
                "[pywin32.export_image] Pillow unavailable; falling back to "
                "SaveAs3 (window-sized render, requested dimensions ignored)"
            )
            return False

        tmp_path = resolved_path + ".capture.bmp"
        try:
            success = target_doc.SaveBMP(tmp_path, width, height)
            if not bool(success) or not os.path.exists(tmp_path):
                return False
            with image_module.open(tmp_path) as img:
                img.save(resolved_path)
            return os.path.exists(resolved_path)
        except Exception as exc:
            logger.debug(
                "[pywin32.export_image] SaveBMP capture/convert failed ({}), "
                "trying SaveAs3 image export",
                exc,
            )
            return False
        finally:
            with contextlib.suppress(OSError):
                os.remove(tmp_path)

    def _save_screenshot_with_saveas3(
        self, target_doc: Any, resolved_path: str
    ) -> None:
        """Final fallback: SaveAs3 with image extension for screenshot.

        SolidWorks determines export format from file extension (.png, .jpg, .bmp, etc.).
        This path works on all SolidWorks versions without needing COM vtable access.

        Args:
            target_doc: SolidWorks model document
            resolved_path: Full path where to save image

        Raises:
            RuntimeError: If SaveAs3 fails or file is not created.
        """
        try:
            target_doc.SaveAs3(
                resolved_path, 0, 2
            )  # swSaveAsCurrentVersion=0, Silent=2
            if os.path.exists(resolved_path):
                return
        except Exception as exc:
            logger.debug(
                "[pywin32.export_image] SaveAs3 failed: {}",
                exc,
            )

        raise RuntimeError(f"All screenshot methods failed for {resolved_path}")

    def _document_identity(self, document: Any) -> tuple[str | None, str | None]:
        """Return normalized path and title for a SolidWorks document.

        Args:
            document: SolidWorks document COM object.

        Returns:
            Tuple of normalized absolute path and title, either may be ``None``.
        """
        return self._document_routing.document_identity(document)

    def _resolve_export_target_doc(self) -> Any:
        """Choose the document that export operations should target.

        Prefer the adapter's tracked model. Use ``ActiveDoc`` only when it is the same
        document, which preserves the typed COM surface without exporting a different
        SolidWorks window that happens to be active.
        """
        return self._document_routing.resolve_export_target_doc()

    @contextlib.contextmanager
    def _image_capture_defaults(self, target_doc: Any):
        """Disable image-only floor effects without changing the caller's session.

        Drawings have no configuration scene; parts and assemblies may have no
        scene assigned. Never persist these transient changes with scene.Modify
        or a native-document save. AO and appearances remain untouched.
        """
        app = sw_type_info.early_bound(self.swApp, "ISldWorks")
        doc = sw_type_info.early_bound(target_doc, "IModelDoc2")
        preferences = {
            name: sw_type_info.constant(name)
            for name in (
                "swDisplayShadowsInShadedMode",
                "swDisplayRealViewGraphics",
            )
        }
        original = {
            name: bool(app.GetUserPreferenceToggle(value))
            for name, value in preferences.items()
        }
        scene = None
        if doc.GetType() in (
            sw_type_info.constant("swDocPART"),
            sw_type_info.constant("swDocASSEMBLY"),
        ):
            manager = sw_type_info.early_bound(
                doc.ConfigurationManager, "IConfigurationManager"
            )
            configuration = manager.ActiveConfiguration
            if configuration is None:
                raise RuntimeError("Image target has no active configuration")
            configuration = sw_type_info.early_bound(configuration, "IConfiguration")
            scene = configuration.GetScene()
            if scene is not None:
                scene = sw_type_info.early_bound(scene, "ISwScene")
        reflections = bool(scene.FloorReflections) if scene is not None else None

        def set_preference(name: str, enabled: bool) -> None:
            # ISldWorks.SetUserPreferenceToggle returns void, not a success flag.
            app.SetUserPreferenceToggle(preferences[name], enabled)
            if bool(app.GetUserPreferenceToggle(preferences[name])) != enabled:
                raise RuntimeError(f"Failed to set {name} to {enabled}")

        def set_reflections(enabled: bool) -> None:
            scene.FloorReflections = enabled
            if bool(scene.FloorReflections) != enabled:
                raise RuntimeError(f"Failed to set scene FloorReflections to {enabled}")

        # Register before each mutation: a setter may change state then throw.
        # ExitStack attempts every restoration even if an earlier one fails.
        with contextlib.ExitStack() as restore:
            restore.callback(doc.GraphicsRedraw2)
            for name in preferences:
                restore.callback(set_preference, name, original[name])
                set_preference(name, False)
            if scene is not None:
                restore.callback(set_reflections, reflections)
                set_reflections(False)
            doc.GraphicsRedraw2()
            yield

    async def export_image(self, payload: dict) -> AdapterResult[dict]:
        """Export a screenshot of the current model to a PNG/JPG file.

        Payload keys (matching ExportImageInput): file_path (str): Output path including
        extension. format_type (str): "png" or "jpg". Default "png". width (int): Pixel width.
        Default 1280. height (int): Pixel height. Default 720. view_orientation (str): "front" |
        "top" | "right" | "isometric" | "current".

        Args:
            payload (dict): The payload value.

        Returns:
            AdapterResult[dict]: The result produced by the operation.

        Raises:
            RuntimeError: If the operation cannot be completed.
        """
        if not self.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )
        if not self.swApp:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="SolidWorks not connected"
            )

        orientation = str(payload.get("view_orientation", "current")).lower()
        file_path = payload.get("file_path", "")
        width = int(payload.get("width", 1280))
        height = int(payload.get("height", 720))

        # Map orientation names to SolidWorks swStandardViews_e constants
        _VIEW_CONSTANTS = {
            "front": 1,  # swFrontView
            "back": 2,  # swBackView
            "left": 3,  # swLeftView
            "right": 4,  # swRightView
            "top": 5,  # swTopView
            "bottom": 6,  # swBottomView
            "isometric": 7,  # swIsometricView
            "dimetric": 8,  # swDimetricView
            "trimetric": 9,  # swTriMetricView
        }

        def _screenshot_operation() -> dict:
            """Build internal screenshot operation.

            Returns:
                dict: A dictionary containing the resulting values.

            Raises:
                RuntimeError: If the operation cannot be completed.
            """

            import os as _os

            resolved = _os.path.abspath(file_path)
            _os.makedirs(_os.path.dirname(resolved), exist_ok=True)

            # Capture renders the ACTIVE window's viewport, so the target doc
            # must be in the foreground or another open document's (stale)
            # view gets exported instead.
            target_doc = self._activate_target_doc(self._resolve_export_target_doc())

            # Ensure SolidWorks window is focused so the viewport is rendered.
            # Required for both view changes and bitmap capture.
            self._attempt(lambda: self.swApp.Frame.SetFocus())

            # Set view orientation if requested. "current" captures the
            # viewport 1:1 (like SolidWorks' own image export) so a
            # caller-staged camera (orientation/scale/translation) survives.
            if orientation != "current" and orientation in _VIEW_CONSTANTS:
                view_const = _VIEW_CONSTANTS[orientation]
                self._set_view_orientation(target_doc, orientation, view_const)
                # Zoom to fit so the model fills the viewport before capture
                self._zoom_to_fit(target_doc)

            with self._image_capture_defaults(target_doc):
                # Try screenshot methods in order: SaveBMP (sized) → SaveAs3
                saved = self._save_screenshot_with_savebmp(
                    target_doc, resolved, width, height
                )
                if not saved:
                    self._save_screenshot_with_saveas3(target_doc, resolved)
                    saved = _os.path.exists(resolved)

                if not saved:
                    raise RuntimeError(
                        f"All screenshot methods produced no output for {resolved}"
                    )

            return {
                "file_path": resolved,
                "format": _os.path.splitext(resolved)[1].lstrip(".").upper() or "PNG",
                "dimensions": f"{width}x{height}",
                "view": orientation,
            }

        return self._handle_com_operation("export_image", _screenshot_operation)

    def _prepare_stl_export_data(self) -> Any | None:
        """Prepare ISTLExportData for STL export with merged bodies option.

        Attempts to get and configure STL export settings from swApp.
        Returns None if swApp is unavailable or if COM operation fails.

        Returns:
            ISTLExportData object or None if unavailable/failed.
        """
        if self.swApp is None:
            return None

        try:
            # swExportDataFileType_e.swExportSTL = 2
            stl_data = self.swApp.GetExportFileData(2)
            if stl_data is None:
                return None

            # Configure for merged single-file export (best for assemblies)
            self._attempt(lambda: setattr(stl_data, "Merge", True))
            # swExportBodiesAs = 0 → swExportAsOneFile
            self._attempt(lambda: setattr(stl_data, "ExportBodiesAs", 0))

            return stl_data
        except Exception:
            return None

    def _save_stl_with_extension(
        self, ext: Any, stl_data: Any | None, resolved_path: str
    ) -> bool:
        """Attempt STL export using Extension.SaveAs2 with optional ISTLExportData.

        ``IModelDocExtension::SaveAs2`` takes 8 required parameters:
        ``(Name, Version, Options, ExportData: IDispatch,
        ReferencePrefixOrSuffixText: str, AddTextAsPrefix: bool,
        byref Errors, byref Warnings)``. Under late binding the optional-object
        and by-reference parameters need typed VARIANTs — bare ``None`` (or a
        wrong-typed placeholder) marshals as ``VT_NULL`` and SolidWorks rejects
        the call with ``Type mismatch`` (issue #28, same class as the
        ``SelectByID2`` Callout fix).

        Tries SaveAs2 with stl_data first (enables body merging); falls back to
        a typed-null ExportData if marshalling the ISTLExportData pointer fails.

        Args:
            ext: Extension object from target document
            stl_data: Optional ISTLExportData configuration
            resolved_path: Full path where to save STL file

        Returns:
            True if file was created, False otherwise.
        """
        from .com_variant import null_dispatch

        def _save(export_data: Any) -> Any:
            # swSaveAsVersion_e.swSaveAsCurrentVersion = 0
            # swSaveAsOptions_e.swSaveAsOptions_Silent = 2
            # Early-bound IModelDocExtension::SaveAs2 returns its two [out] codes in
            # the tuple (ok, errors, warnings): pass literal 0 for those slots and
            # consume the tuple (the byref-VARIANT idiom left `ok` a truthy tuple, so
            # the failure warning could never fire).
            result = ext.SaveAs2(resolved_path, 0, 2, export_data, "", False, 0, 0)
            ok, errors, warnings = (
                result if isinstance(result, tuple) else (result, None, None)
            )
            if not ok:
                logger.warning(
                    "[pywin32.export_file] Extension.SaveAs2 returned False "
                    "(errors={}, warnings={})",
                    errors,
                    warnings,
                )
            return ok

        try:
            try:
                _save(stl_data if stl_data is not None else null_dispatch())
            except Exception:
                # Fallback: typed-null ExportData (ISTLExportData* may not
                # marshal through IDispatch::Invoke on some builds).
                _save(null_dispatch())

            return os.path.exists(resolved_path)
        except Exception as exc:
            logger.warning(
                "[pywin32.export_file] Extension.SaveAs2 failed: {}",
                str(exc),
            )
            return False

    def _save_stl_with_fallback(self, target_doc: Any, resolved_path: str) -> None:
        """Fallback STL export using SaveAs3 if SaveAs2 didn't create file.

        Args:
            target_doc: SolidWorks model document
            resolved_path: Full path to save file to

        Raises:
            Exception: If both SaveAs2 and SaveAs3 fail to produce file.
        """
        logger.warning(
            "[pywin32.export_file] SaveAs2 did not produce {}, falling back to SaveAs3",
            resolved_path,
        )
        try:
            target_doc.SaveAs3(
                resolved_path,
                0,  # swSaveAsCurrentVersion
                2,  # swSaveAsOptions_Silent
            )
        except Exception as exc:
            logger.warning(
                "[pywin32.export_file] SaveAs3 also failed: {}",
                str(exc),
            )

        if not os.path.exists(resolved_path):
            raise Exception(
                f"STL export failed for {resolved_path} "
                "(tried Extension.SaveAs2 and SaveAs3)"
            )

    async def export_file(
        self, file_path: str, format_type: str
    ) -> AdapterResult[None]:
        """Export the current model to a file.

        Args:
            file_path (str): Path to the target file.
            format_type (str): The format type value.

        Returns:
            AdapterResult[None]: The result produced by the operation.

        Raises:
            Exception: If the operation cannot be completed.
            RuntimeError: No active SolidWorks document for export.
        """
        if not self.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _export_operation() -> None:
            """Build internal export operation.

            Returns:
                None: None.

            Raises:
                Exception: If the operation cannot be completed.
                RuntimeError: No active SolidWorks document for export.
            """
            format_map = {
                "step": 0,  # swSaveAsSTEP
                "iges": 1,  # swSaveAsIGS
                "stl": 2,  # swSaveAsSTL
                "pdf": 3,  # swSaveAsPDF
                "dwg": 4,  # swSaveAsDWG
                "jpg": 5,  # swSaveAsJPEG
                "glb": 41,  # swSaveAsGLTF (binary GLTF, SW 2023+)
                "gltf": 41,  # same enum value, text GLTF
            }

            format_lower = format_type.lower()
            if format_lower not in format_map:
                raise Exception(f"Unsupported export format: {format_type}")

            resolved_path = os.path.abspath(file_path)
            os.makedirs(os.path.dirname(resolved_path), exist_ok=True)

            if os.path.exists(resolved_path):
                self._attempt(lambda: os.remove(resolved_path))

            # Prefer swApp.ActiveDoc — more reliably typed than the late-bound
            # IDispatch reference stored in self.currentModel after OpenDoc6.
            # Use getattr so tests can pass a SimpleNamespace without ActiveDoc.
            target_doc = (
                getattr(self.swApp, "ActiveDoc", None) if self.swApp else None
            ) or self.currentModel

            # ----------------------------------------------------------------
            # STL export: use Extension.SaveAs2 + ISTLExportData
            # for both parts AND assemblies.  SaveAs3 with format=2 works for
            # parts but is unreliable for assemblies (only exports first body).
            # ----------------------------------------------------------------
            if format_lower == "stl":
                # For assemblies, resolve lightweight components first so all
                # geometry is available for the mesh export.
                self._attempt(lambda: target_doc.ResolveAllLightweightComponents(True))

                ext = getattr(target_doc, "Extension", None)
                if ext is None:
                    raise RuntimeError("No Extension object available for STL export")

                stl_data = self._prepare_stl_export_data()
                if not self._save_stl_with_extension(ext, stl_data, resolved_path):
                    # SaveAs2 didn't produce file — try SaveAs3 fallback
                    self._save_stl_with_fallback(target_doc, resolved_path)

                return None

            # ----------------------------------------------------------------
            # All other formats — classic SaveAs3 path.
            # SaveAs3 signature: SaveAs3(FileName, Version, Options)
            # Version = 0 means "current version" (swSaveAsCurrentVersion).
            # SolidWorks infers the export format from the file extension, so
            # we must NOT pass the format-enum value as the Version argument.
            # ----------------------------------------------------------------
            _ = format_map[format_lower]  # validate format is known; value unused
            logger.debug(
                "[pywin32.export_file] SaveAs3 {} (version=0, options=Silent)",
                resolved_path,
            )
            success = target_doc.SaveAs3(
                resolved_path,
                0,  # swSaveAsCurrentVersion — format inferred from file extension
                2,  # swSaveAsOptions_Silent
            )

            if not success and not os.path.exists(resolved_path):
                raise Exception(
                    f"SaveAs3 returned False and no file produced: {resolved_path}"
                )

            return None

        return self._handle_com_operation("export_file", _export_operation)

    def _get_document_type(self) -> str:
        """Helper method to get document type.

        Returns:
            str: The resulting text value.
        """
        if not self.currentModel:
            return "Unknown"

        doc_type = self.currentModel.GetType()
        type_map = {1: "Part", 2: "Assembly", 3: "Drawing"}
        return type_map.get(doc_type, "Unknown")

    def _invoke_run_macro2(
        self, macro_path: str, module_name: str, proc_name: str
    ) -> dict[str, Any]:
        """Call swApp.RunMacro2 and parse the result into a result dict.

        Args:
            macro_path: Absolute path to the VBA macro file.
            module_name: VB module name (parsed from the file or stem fallback).
            proc_name: Entry-point procedure name, typically "main".

        Returns:
            dict[str, Any]: {"macro_path", "module_name", "errors"} on success.

        Raises:
            SolidWorksMCPError: If RunMacro2 reports failure.
        """
        result = self.swApp.RunMacro2(macro_path, module_name, proc_name, 0, 0)
        if isinstance(result, (list, tuple)):
            success, errors = result[0], result[1]
        else:
            success, errors = bool(result), 0
        if not success:
            raise SolidWorksMCPError(
                f"RunMacro2 failed for {macro_path}, module={module_name!r}, errors={errors}"
            )
        return {
            "macro_path": macro_path,
            "module_name": module_name,
            "errors": errors,
        }

    async def execute_macro(
        self, params: dict[str, Any]
    ) -> AdapterResult[dict[str, Any]]:
        """Provide execute macro support for the py win32 adapter.

        Args:
            params (dict[str, Any]): The params value.

        Returns:
            AdapterResult[dict[str, Any]]: The result produced by the operation.

        Raises:
            SolidWorksMCPError: If the operation cannot be completed.
        """
        macro_path = params.get("macro_path") or params.get("macro_file") or ""
        if not macro_path:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No macro_path provided"
            )
        if not os.path.isfile(macro_path):
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=f"Macro file not found: {macro_path}",
            )

        def _run() -> dict[str, Any]:
            """Resolve module/proc names and delegate to _invoke_run_macro2.

            Returns:
                dict[str, Any]: A dictionary containing the resulting values.

            Raises:
                SolidWorksMCPError: If the operation cannot be completed.
            """
            module_name = _parse_vb_module_name(macro_path)
            proc_name = params.get("proc_name", "main")
            return self._invoke_run_macro2(macro_path, module_name, proc_name)

        return self._handle_com_operation("execute_macro", _run)
