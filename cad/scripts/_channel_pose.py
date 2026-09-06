"""Channel construction pose handles and exact driver-bank release.

Imported directly by the channel builder, never re-exported through _cwm.
This keeps channel-only solver experiments out of the drive-train recipe.
The shared component lookup remains in _cwm; COM handles remain document-local.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from _common import _early_bound
from _cwm import _component
import _telemetry


@dataclass(frozen=True)
class PreparedComponentPoses:
    """Component handles and target transforms for one live assembly document.

    Prepare only after the copied components exist. The caller may change mates
    between resets, but must keep these components and the source document open.
    A reset performs the same ordered Transform2 writes as put_component_pose;
    it does not rebuild, add constraints, or change which DOF remain free.
    """

    _adapter: Any
    _model: Any
    _poses: tuple[tuple[Any, Any], ...]

    def groups(self, component_count: int) -> tuple[PreparedComponentPoses, ...]:
        """Partition ordered component slices without another COM lookup/allocation."""
        if component_count <= 0 or len(self._poses) % component_count:
            raise ValueError("prepared component poses require complete groups")
        return tuple(
            PreparedComponentPoses(
                self._adapter, self._model, self._poses[start:start + component_count]
            )
            for start in range(0, len(self._poses), component_count)
        )

    def apply(self) -> None:
        with _telemetry.span("cwm.pose_reset", components=len(self._poses)) as sp:
            if self._adapter.currentModel is not self._model:
                raise RuntimeError("prepared component poses: assembly document changed")
            written = 0
            try:
                for component, transform in self._poses:
                    component.Transform2 = transform
                    written += 1
            finally:
                sp.set_attribute("pose_writes", written)


def prepare_component_poses(
    adapter: Any, targets: Iterable[tuple[str, list[float]]]
) -> PreparedComponentPoses:
    """Resolve each component and allocate its target transform once, without moving it.

    Repeated resets between transient drivers previously looked up every component
    and allocated the identical IMathTransform again. Keeping these handles within
    the current document preserves the solver sequence while removing that work.
    """
    from solidworks_mcp.adapters.solidworks.assembly import _create_math_transform

    rows = list(targets)
    poses = []
    with _telemetry.span("cwm.pose_prepare", components=len(rows)) as sp:
        for name, array16 in rows:
            component = _component(adapter, name)
            transform = _create_math_transform(adapter, list(array16))
            poses.append((component, transform))
        sp.set_attribute("transform_allocations", len(poses))
    return PreparedComponentPoses(adapter, adapter.currentModel, tuple(poses))


@_telemetry.traced("cwm.delete_pose_driver_bank")
def delete_pose_driver_bank(
    adapter: Any, created_names: Iterable[str], *, expected_count: int
) -> None:
    """Delete exactly the temporary distance-mate bank in one native operation.

    Both channel spin_driver and distance_driver author MateDistanceDim. This
    deliberately accepts only that type, never MateGroup or component features;
    the caller must supply its newly created drivers, not structural mate names.
    Resolve the complete creation manifest before selecting anything. The caller
    owns the closing pose/mate-count/DOF/save gates; successful deletion cannot
    replace them.
    """
    names = tuple(created_names)
    if expected_count < 0 or len(names) != expected_count:
        raise ValueError(
            f"pose driver manifest count {len(names)} does not match {expected_count}"
        )
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("pose driver manifest requires nonempty feature names")
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("pose driver manifest contains duplicate feature names")
    span = _telemetry.trace.get_current_span()
    span.set_attribute("drivers", len(names))
    if not names:
        return
    model = adapter.currentModel
    assembly = _early_bound(model, "IAssemblyDoc")
    features = []
    for name in names:
        raw_feature = assembly.FeatureByName(name)
        if raw_feature is None:
            raise RuntimeError(f"pose driver to delete not found: {name!r}")
        feature = _early_bound(raw_feature, "IFeature")
        if str(feature.Name) != name:
            raise RuntimeError(f"pose driver lookup returned a different feature: {name!r}")
        feature_type = str(feature.GetTypeName2())
        if feature_type != "MateDistanceDim":
            raise RuntimeError(
                f"pose driver {name!r} has type {feature_type!r}, expected MateDistanceDim"
            )
        features.append(feature)

    model.ClearSelection2(True)
    try:
        for name, feature in zip(names, features, strict=True):
            if not feature.Select2(True, 0):
                raise RuntimeError(f"failed to select pose driver for delete: {name!r}")
        selection = _early_bound(model.SelectionManager, "ISelectionMgr")
        selected_count = int(selection.GetSelectedObjectCount2(-1))
        if selected_count != len(names):
            raise RuntimeError(
                f"pose driver deletion selection mismatch: {selected_count} != {len(names)}"
            )
        extension = _early_bound(model.Extension, "IModelDocExtension")
        with _telemetry.span("cwm.delete_pose_driver_bank.native", drivers=len(names)):
            # Zero preserves absorbed/child features. No EditDelete fallback.
            if not extension.DeleteSelection2(0):
                raise RuntimeError(f"native pose driver bank deletion failed ({len(names)} mates)")
        remaining = [name for name in names if assembly.FeatureByName(name) is not None]
        if remaining:
            raise RuntimeError(f"pose drivers still present after bank deletion: {remaining}")
    finally:
        model.ClearSelection2(True)
