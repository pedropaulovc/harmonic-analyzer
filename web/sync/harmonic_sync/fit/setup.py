"""One frozen mechanism setup per narrated interval, never per-part pose fitting.

``default_input(video_id)`` returns a complete SerializedMechanismInput, including
crankTurns. Synthesis uses squareWave(10)/10, reordered to physical stations
20..1; Analysis starts with the narrated ten-high/ten-low sampled square-wave
pattern at conservative chosen normalized magnitude0.4, not Fourier coefficients
or an exact displacement measurement. Its native built-clamp/zero-fixture prior
accepted all80 integer bank positions in targeted feasibility renders.

``fit_setup(client, segment, sample_dicts, *, group_ids, manual=False)`` uses
ONLY the first supplied sample: camera (render-resolution pixels), input,
width, height, presentation, boolean mask/edges, t and fixed turns. The caller
tries pending parameters at successive segment frames, freezing each at its
first locally independent observable attempt even if the chosen value wins.
An optional objective(ids) sees the FULL native RenderClient ID render.
Otherwise the loss is projection-conditioned silhouette/edge agreement, not
independently labelled source parts. Segment init overlays the carried sample
input; supplied fitted/manual provenance locks the authoritative carried values.
A manual call treats the whole sample input as authoritative without fitting.

Fit paths are amplitudes.N/phases.N (zero-based physical index), gearing,
magnification and setup.field. Discrete gearing and integer bank offset modulo
80 are enumerated; observable continuous fields use bounded Nelder-Mead.
All candidates go through the actual GLB/solveMechanism renderer. No proxy,
per-part adjustment or crank optimization exists here. Nonresponsive or locally
dependent fields stay pending in the caller, including the readout-only
meanLineAngleRad and null (auto-calibrated) counterHeightM. The caller validates
the entire segment with frozen values and excludes each group's fitting frames
from independent mechanics evidence. 'fitted' means an objective improved, not
that narration supplied an exact number or that kinematics were validated.

Bounds copy mechanics.ts/kinematics.ts, exported mechanics-data.ts and the
platen setup control in index.html. Counter's numeric search band is the
reference gooseneck shifted by the catalog free/maximum spring-length margins,
not a measured screw stop; native spring/equilibrium checks remain authoritative.
Phase/held-bank bounds span one exact kinematic period rather than an invented
mechanical stop. Malformed input, objective failure, an infeasible initial setup,
and unexpected native solver/browser failures propagate loudly. Explicit native
spring/closure/wire constraint failures of SEARCH CANDIDATES are rejected with
infinite cost and counted in evidence; they cannot become fitted runtime poses.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt
from scipy.optimize import minimize

GEARINGS = ("small-large", "medium-medium", "large-small")
SETUP_DEFAULTS = {
    "counterHeightM": None, "meanLineAngleRad": 0.0, "platenOffsetM": 0.0,
    "wireFixtureOffsetM": 0.0, "coneSwingRad": 0.0, "pinionCamRad": 0.0,
    "heldChannelTurns": 0.0, "driveCrankOffsetTurns": 0.0,
}
# web/src/mechanics-data.ts counter.referenceGooseneckYMm, reference.length_mm,
# freeLengthMm, maximumLengthMm; kinematics.ts magnifier clamp/anchor radii.
_COUNTER_REFERENCE = 1.1863569024416686
_COUNTER_LENGTH = 0.34969443255435453
BOUNDS = {
    "magnification": (66 / 39.85, 209 / 39.85),
    "setup.counterHeightM": (
        _COUNTER_REFERENCE + 0.254 - _COUNTER_LENGTH,
        _COUNTER_REFERENCE + 0.4216146 - _COUNTER_LENGTH,
    ),
    "setup.platenOffsetM": (-0.1, 0.1),
    "setup.wireFixtureOffsetM": (-0.0785, 0.037),
    "setup.coneSwingRad": (0.0, 0.08178707968774765),
    "setup.pinionCamRad": (-1.431579236152074, 0.0),
    "setup.heldChannelTurns": (0.0, 80.0),
    "setup.driveCrankOffsetTurns": (0.0, 79.0),
}



def default_input(video_id: str) -> dict[str, Any]:
    if video_id == "8KmVDxkia_w":
        amplitudes = [1 / k if k % 2 else 0.0 for k in range(20, 0, -1)]
    elif video_id == "6dW6VYXp9HM":
        # Twenty half-period samples in physical20..1 order. Choose the jump
        # endpoint high to match the narrated ten-high/ten-low setup graphic.
        amplitudes = [-0.4 if k > 10 else 0.4 for k in range(20, 0, -1)]
    else:
        raise ValueError(f"No narrated setup prior for video {video_id!r}")
    return {
        "crankTurns": 0.0, "amplitudes": amplitudes, "phases": [0.0] * 20,
        "gearing": "small-large", "magnification": 165 / 39.85,
        "setup": dict(SETUP_DEFAULTS),
    }


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{path} must be a finite number")
    return float(value)


def _path(path: Any) -> tuple[str, str | int | None]:
    if not isinstance(path, str):
        raise ValueError("Fit parameter names must be strings")
    if path in ("gearing", "magnification"):
        return path, None
    head, dot, tail = path.partition(".")
    if dot and head in ("amplitudes", "phases") and tail.isdigit() and str(int(tail)) == tail and 0 <= int(tail) < 20:
        return head, int(tail)
    if dot and head == "setup" and tail in SETUP_DEFAULTS:
        return head, tail
    raise ValueError(f"Unknown/forbidden fit parameter {path!r}; crankTurns is fixed")


def _get(state: dict[str, Any], path: str) -> Any:
    head, tail = _path(path)
    return state[head] if tail is None else state[head][tail]


def _set(state: dict[str, Any], path: str, value: Any) -> None:
    head, tail = _path(path)
    if tail is None:
        state[head] = value
    else:
        state[head][tail] = value


def _merge(base: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, Mapping):
        raise ValueError("Segment init must be an input object")
    state = deepcopy(base)
    unknown = set(patch) - {"amplitudes", "phases", "gearing", "magnification", "setup"}
    if unknown:
        raise ValueError(f"Invalid segment init fields: {sorted(unknown)}")
    for key, value in patch.items():
        if key == "setup":
            if not isinstance(value, Mapping) or set(value) - SETUP_DEFAULTS.keys():
                raise ValueError("Unknown setup field in segment init")
            state["setup"].update(value)
        else:
            state[key] = deepcopy(value)
    return state


def _validate(state: dict[str, Any]) -> None:
    if set(state) != {"crankTurns", "amplitudes", "phases", "gearing", "magnification", "setup"}:
        raise ValueError("Sample input must be a complete SerializedMechanismInput")
    _number(state["crankTurns"], "crankTurns")
    if state["gearing"] not in GEARINGS:
        raise ValueError("Unknown translational gearing")
    for name in ("amplitudes", "phases"):
        if not isinstance(state[name], (list, tuple)) or len(state[name]) != 20:
            raise ValueError(f"{name} needs exactly twenty physical-order values")
        state[name] = list(state[name])
        for j, value in enumerate(state[name]):
            number = _number(value, f"{name}.{j}")
            if name == "amplitudes" and not -1 <= number <= 1:
                raise ValueError(f"{name}.{j} is outside physical [-1,1]")
    if not isinstance(state["setup"], Mapping) or set(state["setup"]) != SETUP_DEFAULTS.keys():
        raise ValueError("Input needs every known setup field and no extra fields")
    for name, value in state["setup"].items():
        if name != "counterHeightM" or value is not None:
            _number(value, f"setup.{name}")
    for path, (lo, hi) in BOUNDS.items():
        # Absolute held-bank/drive offsets can be outside one period. Their
        # values are finite coordinates, not physical travel stops.
        if path in ("setup.heldChannelTurns", "setup.driveCrankOffsetTurns", "setup.counterHeightM"):
            continue
        if not lo <= _number(_get(state, path), path) <= hi:
            raise ValueError(f"{path} is outside physical/setup bounds [{lo}, {hi}]")


def _bounds(path: str, value: float) -> tuple[float, float]:
    if path.startswith("amplitudes."):
        return -1.0, 1.0
    if path.startswith("phases."):
        return value - math.pi, value + math.pi
    if path == "setup.heldChannelTurns":
        return value - 40.0, value + 40.0
    return BOUNDS[path]


def affected_groups(path: str, group_ids: Mapping[str, int]) -> list[str]:
    """Return conservative causal groups for excluding fit-frame evidence."""
    _path(path)
    if path == "setup.meanLineAngleRad":
        names = []
    elif path == "gearing" or path == "setup.platenOffsetM":
        names = ["platen-paper"]
    elif path == "magnification" or path == "setup.wireFixtureOffsetM":
        names = ["magnifier", "wheel-wire", "pen"]
    elif path == "setup.counterHeightM":
        names = ["springs", "summing", "magnifier", "wheel-wire", "pen"]
    else:
        # Bank, phase and amplitude motion propagates through the moving chain.
        names = [f"channel-{k}" for k in range(1, 21)] + [
            "amplitude-bars", "summing", "springs", "magnifier", "wheel-wire",
            "pen", "cones", "platen-paper",
        ]
    return [name for name in names if name in group_ids]


def _affected(path: str, group_ids: Mapping[str, int]) -> list[int]:
    return [group_ids[name] for name in affected_groups(path, group_ids)]


def fit_setup(
    client: Any, segment: Mapping[str, Any], sample_dicts: Sequence[Mapping[str, Any]],
    *, group_ids: Mapping[str, int], manual: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Attempt pending parameters at their first observable frame; preserve locks."""
    start = _number(segment["start"], "segment.start")
    end = _number(segment["end"], "segment.end")
    if start >= end or not isinstance(segment["id"], str) or not segment["id"]:
        raise ValueError("Segment needs an ID and a positive interval")
    requested = list(segment.get("fit", []))
    if len(requested) != len(set(requested)):
        raise ValueError("Duplicate fit parameter")
    for path in requested:
        _path(path)
    supplied_provenance = segment.get("provenance", {})
    if not isinstance(supplied_provenance, Mapping):
        raise ValueError("Segment provenance must be a flattened object")
    for path, source in supplied_provenance.items():
        _path(path)
        if source not in ("manual", "chosen", "fitted"):
            raise ValueError(f"Invalid provenance for {path}")
    if not sample_dicts:
        raise ValueError("Setup needs a carried-input sample, even for a held/non-machine interval")
    sample = sample_dicts[0]
    base = deepcopy(sample["input"])
    _validate(base)
    state = _merge(base, segment.get("init", {}))
    if manual:
        state = base
    state["crankTurns"] = _number(sample["turns"], "sample.turns")
    _validate(state)
    all_paths = [f"{name}.{j}" for name in ("amplitudes", "phases") for j in range(20)]
    all_paths += ["gearing", "magnification"] + [f"setup.{name}" for name in SETUP_DEFAULTS]
    provenance = {path: supplied_provenance.get(path, "manual" if manual else "chosen") for path in all_paths}
    # Previously fitted and manual parameters retain authoritative carried values.
    for path in all_paths:
        if provenance[path] in ("manual", "fitted"):
            _set(state, path, _get(base, path))
    evidence: dict[str, Any] = {
        "firstSampleOnly": True, "sampleTime": sample.get("t"),
        "fixedCrankTurns": state["crankTurns"], "requested": requested,
        "objectiveSource": "projection-conditioned", "notIdentified": {},
        "renders": 0, "optimizer": "bounded-Nelder-Mead/discrete-enumeration",
        "infeasibleCandidates": {}, "observable": [],
    }

    def finish(status: str) -> tuple[dict[str, Any], dict[str, Any]]:
        evidence["status"] = status
        runtime_input = deepcopy(state)
        del runtime_input["crankTurns"]
        return {"id": segment["id"], "start": start, "end": end, "input": runtime_input, "provenance": provenance}, evidence

    if manual:
        return finish("manual")
    active = []
    for path in requested:
        if provenance[path] in ("manual", "fitted"):
            evidence["notIdentified"][path] = f"{provenance[path]}-authoritative"
        elif path == "setup.meanLineAngleRad":
            evidence["notIdentified"][path] = "readout-only datum has no native projection effect"
        elif _get(state, path) is None:
            evidence["notIdentified"][path] = "auto-calibrated null setting, not a numeric measurement"
        elif path == "setup.heldChannelTurns" and state["setup"]["coneSwingRad"] == 0:
            evidence["notIdentified"][path] = "held bank ignored while engaged"
        elif path == "setup.driveCrankOffsetTurns" and state["setup"]["coneSwingRad"] != 0:
            evidence["notIdentified"][path] = "engaged offset ignored while disengaged"
        else:
            active.append(path)
    if not active:
        return finish("chosen")
    if not isinstance(group_ids, Mapping) or not group_ids or any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in group_ids.values()):
        raise ValueError("group_ids must map native render group names to positive IDs")
    width, height = sample["width"], sample["height"]
    if isinstance(width, bool) or isinstance(height, bool) or not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError("Sample render dimensions must be positive integers")
    mask, edges = np.asarray(sample["mask"]), np.asarray(sample["edges"])
    if mask.dtype != np.bool_ or edges.dtype != np.bool_ or mask.shape != (height, width) or edges.shape != mask.shape:
        raise ValueError("Sample mask/edges must be boolean arrays at render resolution")
    if not mask.any() or not edges.any():
        raise ValueError("Cannot fit setup against empty mask/edge support")
    presentation = sample["presentation"]
    if presentation not in ("native", "horizontal-mirror"):
        raise ValueError("Unknown sample presentation")
    _number(sample["t"], "sample.t")  # Pipeline selects the frame; no float-time ownership gate.
    custom = sample.get("objective")
    if custom is not None and not callable(custom):
        raise ValueError("Sample objective must be callable")
    edge_distance = distance_transform_edt(~edges)

    def render(candidate: dict[str, Any], *, search: bool = False) -> np.ndarray | None:
        _validate(candidate)
        evidence["renders"] += 1
        request = {"camera": sample["camera"], "input": candidate, "width": width, "height": height, "presentation": presentation}
        if search:
            ids = client.render_candidate_batch([request], shot_id=sample.get("shotId"), view_id=sample.get("viewId"))[0]
            rejected = evidence.setdefault("infeasibleCandidates", {})
            for reason, count in client.last_candidate_failures.items():
                rejected[reason] = rejected.get(reason, 0) + count
            if ids is None:
                return None
        else:
            ids = client.render(request, shot_id=sample.get("shotId"), view_id=sample.get("viewId"))
        ids = np.asarray(ids)
        if ids.shape != mask.shape or not np.issubdtype(ids.dtype, np.integer):
            raise ValueError("Native render returned invalid ID image")
        return ids

    def loss(ids: np.ndarray | None) -> float:
        if ids is None:
            return math.inf
        if custom is not None:
            return _number(custom(ids), "setup objective")
        projected = ids != 0
        if not projected.any():
            return 2.0
        union = np.count_nonzero(projected | mask)
        iou = np.count_nonzero(projected & mask) / union
        border = projected & ~binary_erosion(projected)
        reverse_distance = distance_transform_edt(~border)
        chamfer = (float(edge_distance[border].mean()) + float(reverse_distance[edges].mean())) / 2
        return 1 - iou + chamfer / math.hypot(width, height)

    initial_ids = render(state)
    initial_loss = loss(initial_ids)
    evidence["initialObjective"] = initial_loss
    # Perturbations must move the relevant projected native group where source
    # support exists. A render response wholly outside the source is not observed.
    observable = []
    responses: list[np.ndarray] = []
    for path in active:
        values = []
        if path == "gearing":
            values = [value for value in GEARINGS if value != state[path]]
        elif path == "setup.driveCrankOffsetTurns":
            values = [_get(state, path) + 1]
        else:
            value = _number(_get(state, path), path)
            lo, hi = _bounds(path, value)
            if not lo <= value <= hi:
                raise ValueError(f"Initial {path} lies outside its search bounds")
            step = (hi - lo) * 0.05
            values = [max(lo, value - step), min(hi, value + step)]
        relevant = _affected(path, group_ids)
        if not relevant:
            evidence["notIdentified"][path] = "native affected group unavailable"
            continue
        response = np.zeros(mask.shape, dtype=np.float32)
        for value in values:
            probe = deepcopy(state)
            _set(probe, path, value)
            probe_ids = render(probe, search=True)
            if probe_ids is None:
                continue
            support = mask & (np.isin(initial_ids, relevant) | np.isin(probe_ids, relevant))
            response += ((probe_ids != initial_ids) & support)
        norm = float(np.linalg.norm(response))
        if norm == 0:
            evidence["notIdentified"][path] = "no native projection response on visible source support"
            continue
        vector = response.reshape(-1) / norm
        if responses:
            basis = np.stack(responses, axis=1)
            coefficients = np.linalg.lstsq(basis, vector, rcond=1e-6)[0]
            if np.linalg.norm(vector - basis @ coefficients) < 0.05:
                evidence["notIdentified"][path] = "locally dependent on another requested parameter in this first frame"
                continue
        responses.append(vector)
        observable.append(path)
    evidence["observable"] = observable
    discrete = [path for path in observable if path in ("gearing", "setup.driveCrankOffsetTurns")]
    continuous = [path for path in observable if path not in discrete]
    bounds = [_bounds(path, _number(_get(state, path), path)) for path in continuous]
    best_state, best_loss = deepcopy(state), initial_loss
    # Enumerate each discrete coordinate once, holding the first-frame crank
    # fixed; do not run hundreds of continuous searches over the bank period.
    for path in discrete:
        discrete_base = deepcopy(best_state)
        choices = GEARINGS if path == "gearing" else [_get(discrete_base, path) + integer for integer in range(80)]
        for value in choices:
            candidate = deepcopy(discrete_base)
            _set(candidate, path, value)
            candidate_loss = loss(render(candidate, search=True))
            if candidate_loss < best_loss:
                best_state, best_loss = candidate, candidate_loss
    if continuous:
        candidate = deepcopy(best_state)
        x0 = np.array([(_get(candidate, path) - lo) / (hi - lo) for path, (lo, hi) in zip(continuous, bounds, strict=True)])

        def objective(x: np.ndarray) -> float:
            trial = deepcopy(candidate)
            for path, value, (lo, hi) in zip(continuous, x, bounds, strict=True):
                _set(trial, path, float(lo + value * (hi - lo)))
            return loss(render(trial, search=True))

        result = minimize(objective, x0, method="Nelder-Mead", bounds=[(0.0, 1.0)] * len(continuous), options={"maxfev": 400, "xatol": 0.002, "fatol": 0.0001})
        if not np.isfinite(result.fun):
            raise RuntimeError(f"Setup optimizer failed: {result.message}")
        evidence["optimization"] = {"discrete": {path: _get(candidate, path) for path in discrete}, "converged": bool(result.success), "message": str(result.message)}
        if result.fun < best_loss:
            best_loss = float(result.fun)
            for path, value, (lo, hi) in zip(continuous, result.x, bounds, strict=True):
                _set(candidate, path, float(lo + value * (hi - lo)))
            best_state = candidate
    if best_loss < initial_loss - 1e-8:
        state = best_state
        for path in observable:
            if _get(state, path) != _get(_merge(base, segment.get("init", {})), path):
                provenance[path] = "fitted"
    else:
        for path in observable:
            evidence["notIdentified"][path] = "no objective improvement; prior retained"
    # Commit only a strictly rendered native pose; candidate classification must
    # never excuse an invalid final chosen/runtime setup.
    render(state)
    evidence["finalObjective"] = best_loss
    evidence["fitted"] = [path for path, source in provenance.items() if source == "fitted"]
    return finish("fitted" if evidence["fitted"] else "chosen")
