r"""Saved assembly POSE configurations (2026-09-02, user directive).

The shipped ``Default`` configuration of every assembly is the FREE kinematic
model at the ch30 eight-view rest pose: each freed operational DOF carries NO
driver (its drive spec lives in the DOF manifest, see ``_assembly_postbuild``).
A pose configuration shows the same geometry POSED -- the amplitude fan of
ch15 p.30, the rocker sinusoid of the ch14 p.28 end views -- without
touching Default or the gates that prove it:

* every freed DOF's manifest drive is authored ONCE as a permanent
  ``POSE_<key>`` mate at its recorded rest value (nothing moves), then
  SUPPRESSED in Default (config-scoped, so Default stays exactly the free model
  ``verify:soundness`` proves) and UNSUPPRESSED in each pose configuration,
  where its dimension takes the pose value IN THAT CONFIGURATION ONLY
  (``IDimension::SetSystemValue3`` with ``swSetValue_InThisConfiguration``);
* mates that must NOT hold in a pose (the drive-train's gear mates while the
  cylinder gears carry their residual angles) are suppressed in that
  configuration only;
* fixed cosmetic components (the channel spring bank) are re-posed per
  configuration (float -> move/rotate -> fix in the active configuration);
* the whole thing is proven on the seat: a transform snapshot of Default taken
  before any configuration exists must read back unchanged after them all, and
  each pose is verified by the caller's readback + interference check.

Spiked 2026-09-02 on the real channel.SLDASM / drive-train.SLDASM (scratchpad
``spike_pose_configs.py`` / ``spike_gear_pose.py``): per-configuration mate
values, per-configuration fixed-component moves and per-configuration gear-mate
suppression all round-trip exactly (Default drift 0.0000).

Naming: ``POSE_`` is distinct from the transient ``DRIVE_`` mates
``verify:kinematics`` authors from the same specs, so both can coexist on a
reopened model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import _telemetry
from _assembly import _mate, component_names, component_transform
from _common import check, log

POSE_PREFIX = "POSE_"
REST_CONFIGURATION = "Default"

# IFeature::SetSuppression2 arguments (swFeatureSuppressionAction_e /
# swInConfigurationOpts_e) -- this-configuration scope only; the adapter's
# swSpecifyConfiguration path reads back false on a mate (spike 2026-09-02).
_SUPPRESS, _UNSUPPRESS = 0, 1
_THIS_CONFIGURATION = 1
# IDimension::SetSystemValue3 -- value in the ACTIVE configuration only.
_SET_IN_THIS_CONFIGURATION = 1


def pose_mate_name(key: str) -> str:
    return f"{POSE_PREFIX}{key}"


def pose_dim_name(key: str) -> str:
    return f"D1@{pose_mate_name(key)}"


@dataclass
class PoseMate:
    key: str
    name: str
    kind: str  # "distance" (mm) | "angle" (deg)
    rest: float  # the manifest's recorded rest value (mm / deg)


@dataclass
class PoseConfiguration:
    name: str
    comment: str
    values: dict[str, float] = field(default_factory=dict)  # key -> posed value (mm/deg)
    suppress_mates: list[str] = field(default_factory=list)  # extra mates OFF in this config
    hook: Callable[[Any], Awaitable[None]] | None = None  # runs with the config active, after the values
    verify: Callable[[Any], None] | None = None  # readback proof, config active, after the hook


def _rebuild(adapter: Any) -> None:
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)


def active_configuration(adapter: Any) -> str:
    from solidworks_mcp.adapters.solidworks.assembly import _config_name

    return _config_name(adapter.currentModel)


async def activate_configuration(adapter: Any, name: str) -> None:
    if active_configuration(adapter) != name:
        check(f"activate configuration {name!r}", await adapter.set_active_configuration(name))
    _rebuild(adapter)


async def create_configuration(adapter: Any, name: str, comment: str) -> None:
    from solidworks_mcp.adapters.base import CreateConfigurationParameters

    check(
        f"create configuration {name!r}",
        await adapter.create_configuration(CreateConfigurationParameters(name=name, comment=comment)),
    )


async def author_pose_mates(adapter: Any, specs: list[dict[str, Any]]) -> dict[str, PoseMate]:
    """Author every DOF-manifest spec as a permanent ``POSE_<key>`` mate at its
    RECORDED rest value (the model does not move; the ``verify`` readback guard
    of ``_mate`` proves it landed on the recorded side)."""
    from solidworks_mcp.adapters.base import MateEntityRef, RenameFeatureParameters

    out: dict[str, PoseMate] = {}
    with _telemetry.span("pose.author", count=len(specs)):
        for spec in specs:
            entities = [MateEntityRef(**e) for e in spec["entities"]]
            verify = (spec["verify"][0], list(spec["verify"][1])) if spec.get("verify") else None
            witness = (list(spec["witness"][0]), list(spec["witness"][1])) if spec.get("witness") else None
            res = await _mate(
                adapter,
                f"pose {spec['key']}",
                spec["kind"],
                entities,
                verify=verify,
                witness=witness,
                flip=bool(spec.get("flip", False)),
                **spec.get("params", {}),
            )
            old = res.get("name") if isinstance(res, dict) else str(res)
            new = pose_mate_name(spec["key"])
            check(
                f"rename pose mate {old!r} -> {new!r}",
                await adapter.rename_feature(RenameFeatureParameters(old_name=old, new_name=new)),
            )
            kind = spec["kind"]
            rest = float(spec["params"]["distance"] if kind == "distance" else spec["params"]["angle"])
            out[spec["key"]] = PoseMate(spec["key"], new, kind, rest)
        _rebuild(adapter)
    return out


async def set_mates_suppressed_in(
    adapter: Any, mates: list[str], suppressed: bool, configuration: str
) -> None:
    """Suppress/unsuppress ``mates`` in ONE configuration: activate it, apply
    with swThisConfiguration, rebuild once, read every state back, restore the
    prior active configuration."""
    from solidworks_mcp.adapters.solidworks.assembly import _mate_feature_by_name

    if not mates:
        return
    prior = active_configuration(adapter)
    await activate_configuration(adapter, configuration)
    action = _SUPPRESS if suppressed else _UNSUPPRESS
    feats = {}
    for name in mates:
        feat = _mate_feature_by_name(adapter, name, adapter.currentModel)
        if feat is None:
            raise RuntimeError(f"pose: mate {name!r} not found")
        rc = adapter._attempt(lambda f=feat: f.SetSuppression2(action, _THIS_CONFIGURATION, None), default=False)
        if not rc:
            raise RuntimeError(f"pose: SetSuppression2 rejected on {name!r} in {configuration!r}")
        feats[name] = feat
    _rebuild(adapter)
    wrong = [n for n, f in feats.items() if bool(adapter._attempt(lambda f=f: f.IsSuppressed(), default=None)) != suppressed]
    if wrong:
        raise RuntimeError(
            f"pose: {len(wrong)} mate(s) did not become {'suppressed' if suppressed else 'unsuppressed'}"
            f" in {configuration!r}: {wrong[:5]}"
        )
    log(f"pose: {len(mates)} mate(s) {'suppressed' if suppressed else 'live'} in {configuration!r}")
    if prior != configuration:
        await activate_configuration(adapter, prior)


def set_pose_value_in_active_configuration(adapter: Any, mate: PoseMate, value: float) -> None:
    """Set ``mate``'s dimension (mm for distance, deg for angle) in the ACTIVE
    configuration only."""
    dim = adapter.currentModel.Parameter(pose_dim_name(mate.key))
    if dim is None:
        raise RuntimeError(f"pose: dimension {pose_dim_name(mate.key)} not found")
    si = value / 1000.0 if mate.kind == "distance" else math.radians(value)
    rc = adapter._attempt(lambda: dim.SetSystemValue3(si, _SET_IN_THIS_CONFIGURATION, None), default=None)
    if rc not in (0, True):
        raise RuntimeError(f"pose: SetSystemValue3({pose_dim_name(mate.key)}, {value}) -> {rc!r}")


def set_distance_mate_value_in_active_configuration(
    adapter: Any, component: str, rest_mm: float, value_mm: float, *, label: str = ""
) -> None:
    """Set a NON-pose distance mate's value in the ACTIVE configuration only.

    The mate is the one distance mate on ``component`` currently at ``rest_mm``
    (``_cwm``'s value lookup -- copied slices carry SolidWorks-named mates, so
    the value is the only handle that survives CopyWithMates2). Used for the
    channel's J5 foot-on-arc coupling, whose radius is a POSE-dependent measure
    (the bar lifts onto its roof corner when the arm turns under it)."""
    from solidworks_mcp.adapters.solidworks.features import _read_member

    from _common import _flag_only
    from _cwm import _component_distance_mate

    mate = _component_distance_mate(adapter, component, rest_mm)
    _flag_only(mate, "DisplayDimension2")
    display = adapter._attempt(lambda: mate.DisplayDimension2(0), default=None)
    dim = _read_member(display, "GetDimension") if display is not None else None
    if dim is None:
        raise RuntimeError(f"pose: {component}: distance mate at {rest_mm:.3f} has no dimension")
    rc = adapter._attempt(lambda: dim.SetSystemValue3(value_mm / 1000.0, _SET_IN_THIS_CONFIGURATION, None), default=None)
    if rc not in (0, True):
        raise RuntimeError(f"pose: {label or component}: SetSystemValue3({value_mm:.4f}) -> {rc!r}")
    got = float(adapter._attempt(lambda: dim.SystemValue, default=float("nan"))) * 1000.0
    if abs(got - value_mm) > 1e-3:
        raise RuntimeError(f"pose: {label or component}: set {value_mm:.4f} read back {got:.4f}")
    _telemetry.event("pose.distance_mate", component=component, rest_mm=rest_mm, value_mm=value_mm, label=label)


def set_component_referenced_configuration(adapter: Any, component: str, configuration: str) -> None:
    """Point a sub-assembly instance at one of ITS configurations, in the ACTIVE
    top configuration only (``IComponent2::ReferencedConfiguration`` + rebuild,
    read back). The adapter's ``set_component_configuration``
    (``CompConfigProperties5``) reads back 'Default' on this seat in both
    Default and a fresh configuration (probe 2026-09-02); the documented
    property takes, per configuration (readback proves both)."""
    from _common import _early_bound

    def _comp():
        c = _early_bound(adapter.currentModel, "IAssemblyDoc").GetComponentByName(component)
        if c is None:
            raise RuntimeError(f"pose: component not found: {component!r}")
        return _early_bound(c, "IComponent2")

    _comp().ReferencedConfiguration = configuration
    _rebuild(adapter)
    got = str(_comp().ReferencedConfiguration)
    if got != configuration:
        raise RuntimeError(
            f"pose: {component} -> configuration {configuration!r} did not take (reads {got!r})"
        )
    _telemetry.event("pose.component_configuration", component=component, configuration=configuration)


def read_pose_value(adapter: Any, mate: PoseMate) -> float:
    dim = adapter.currentModel.Parameter(pose_dim_name(mate.key))
    si = float(adapter._attempt(lambda: dim.SystemValue, default=float("nan")))
    return si * 1000.0 if mate.kind == "distance" else math.degrees(si)


def snapshot_transforms(adapter: Any) -> dict[str, list[float]]:
    return {n: component_transform(adapter, n) for n in component_names(adapter)}


def assert_transforms_unchanged(
    adapter: Any, snapshot: dict[str, list[float]], label: str, tol_m: float = 1e-6
) -> None:
    """Every component must sit exactly where the snapshot put it (rotation
    entries and metre translations within ``tol_m``)."""
    worst = (0.0, "")
    for name, before in snapshot.items():
        after = component_transform(adapter, name)
        d = max(abs(a - b) for a, b in zip(after[:12], before[:12], strict=True))
        if d > worst[0]:
            worst = (d, name)
    if worst[0] > tol_m:
        raise RuntimeError(f"{label}: {worst[1]} moved by {worst[0] * 1000.0:.4f} mm -- Default is not the rest model anymore")
    log(f"{label}: {len(snapshot)} components unchanged (worst {worst[0] * 1000.0:.5f} mm)")


def yaw_deg(transform: list[float]) -> float:
    """Rotation of a component's local X axis about assembly Z (deg, -180..180)."""
    return math.degrees(math.atan2(transform[1], transform[0]))


def wrap_deg(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


async def repose_fixed_component(
    adapter: Any, name: str, position_mm: list[float], rotate_deg: float = 0.0,
    axis: list[float] | None = None,
) -> None:
    """Move a FIXED component in the ACTIVE configuration only: float, place its
    origin at ``position_mm`` (absolute), rotate by ``rotate_deg`` about ``axis``
    through the new origin, fix again. Other configurations keep their own
    stored position (spike B)."""
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        MoveComponentParameters,
        RotateComponentParameters,
    )

    check(f"float {name}", await adapter.float_component(ComponentRefParameters(name=name)))
    check(
        f"move {name}",
        await adapter.move_component(MoveComponentParameters(name=name, position=list(position_mm), relative=False)),
    )
    if abs(rotate_deg) > 1e-9:
        check(
            f"rotate {name} {rotate_deg:+.3f} deg",
            await adapter.rotate_component(
                RotateComponentParameters(
                    name=name, angle=rotate_deg, axis_vector=list(axis or [0.0, 0.0, 1.0]),
                    axis_point=list(position_mm),
                )
            ),
        )
    check(f"fix {name}", await adapter.fix_component(ComponentRefParameters(name=name)))


async def install_pose_configurations(
    adapter: Any,
    pose_mates: dict[str, PoseMate],
    configs: list[PoseConfiguration],
    *,
    interference: Callable[[Any], None] | None = None,
) -> None:
    """Create the pose configurations on the ACTIVE (Default) assembly.

    1. snapshot Default; create every configuration (each inherits the rest
       model with the POSE mates live at rest -- nothing moves);
    2. suppress every POSE mate in Default (the shipped free model);
    3. per configuration: all POSE mates live, ``suppress_mates`` off, the
       posed values set, rebuild, ``hook``, ``verify``, ``interference``;
    4. Default active again: re-pin every DOF at rest (POSE mates live at
       their Default = rest values, rebuild, snapshot check), free them again,
       rebuild; the transform snapshot must match exactly.
    """
    names = [m.name for m in pose_mates.values()]
    with _telemetry.span("pose.install", configurations=len(configs), pose_mates=len(names)):
        await activate_configuration(adapter, REST_CONFIGURATION)
        rest = snapshot_transforms(adapter)
        for cfg in configs:
            await create_configuration(adapter, cfg.name, cfg.comment)
        await set_mates_suppressed_in(adapter, names, True, REST_CONFIGURATION)
        for cfg in configs:
            with _telemetry.span("pose.configure", configuration=cfg.name, values=len(cfg.values)):
                await set_mates_suppressed_in(adapter, names, False, cfg.name)
                if cfg.suppress_mates:
                    await set_mates_suppressed_in(adapter, cfg.suppress_mates, True, cfg.name)
                await activate_configuration(adapter, cfg.name)
                for key, value in cfg.values.items():
                    set_pose_value_in_active_configuration(adapter, pose_mates[key], value)
                _rebuild(adapter)
                if cfg.hook is not None:
                    await cfg.hook(adapter)
                    _rebuild(adapter)
                if cfg.verify is not None:
                    cfg.verify(adapter)
                if interference is not None:
                    interference(adapter)
                _telemetry.info(f"pose configuration {cfg.name!r}: {len(cfg.values)} value(s) posed and verified")
        await activate_configuration(adapter, REST_CONFIGURATION)
        # Re-pin the rest pose before trusting it: the free chain's stored
        # positions can come back on another solver branch after the posed
        # configurations (third seat run: rocker-arm-14 returned 128 mm away,
        # the rocker/rod two-circle closure's mirror branch). Drive every DOF
        # to its recorded rest value once more (the POSE mates were authored
        # at rest, so their Default values ARE the rest pose), then free them.
        with _telemetry.span("pose.repin_rest", pose_mates=len(names)):
            await set_mates_suppressed_in(adapter, names, False, REST_CONFIGURATION)
            _rebuild(adapter)
            assert_transforms_unchanged(adapter, rest, f"{REST_CONFIGURATION} re-pinned at rest")
            await set_mates_suppressed_in(adapter, names, True, REST_CONFIGURATION)
            _rebuild(adapter)
        assert_transforms_unchanged(adapter, rest, f"{REST_CONFIGURATION} after pose configurations")
