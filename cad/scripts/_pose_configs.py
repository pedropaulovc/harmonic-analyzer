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
    4. Default active again, rebuild, transform snapshot must match exactly.
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
        assert_transforms_unchanged(adapter, rest, f"{REST_CONFIGURATION} after pose configurations")
