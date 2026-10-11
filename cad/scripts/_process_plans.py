"""Bind HA labels and fixture specs to strict, complete prechips travelers.

Tracked process inputs stay untouched. Only the generated copies under
``travelers/`` contain export-specific face references and fixture primitives.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import tomllib
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterator

from filelock import FileLock

from export_features import OUT as CAD_OUT
from export_features import bundle_paths

TRAVELER_STEMS: tuple[str, ...] = ()
PROCESS_ROOT = Path(__file__).resolve().parents[1] / "process"
SHOP_FILES = ("inventory.toml", "shop-policy.toml", "cutting-data.toml")
_LABEL = re.compile(r"HAF_(?P<feature>[A-Z0-9_]+)__P\d{2}")
_REF = re.compile(
    r"#[1-9]\d*/ADVANCED_FACE\[[1-9]\d*\]/(?P<label>HAF_[A-Z0-9_]+__P\d{2})"
)
_TL_STEM = re.compile(r"[a-z][a-z0-9_]*_tl_[a-z0-9_]+")


class PlanBindError(ValueError):
    """An authored plan or fixture cannot be bound without ambiguity."""

    def __init__(self, detail: str, line: int = 1, *, label: str | None = None):
        self.detail = detail
        self.line = line
        self.label = label
        super().__init__(f"line {line}: {detail}")


class TravelerIncomplete(ValueError):
    """A traveler does not certify its full plan-derived output inventory."""


def plan_path(stem: str) -> Path:
    return PROCESS_ROOT / stem / "plan.toml"


def shop_paths() -> tuple[Path, Path, Path]:
    return tuple(PROCESS_ROOT / "shop" / name for name in SHOP_FILES)


def traveler_dir(stem: str, out: Path = CAD_OUT) -> Path:
    return Path(out) / "travelers" / stem


def _load(path: Path) -> dict[str, Any]:
    return tomllib.loads(Path(path).read_bytes().decode("utf-8"))


def label_refs(manifest: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Index exact refs, rejecting labels whose feature does not own them."""
    result: dict[str, list[str]] = {}
    for feature, values in manifest["features"].items():
        faces = values.get("faces")
        if not isinstance(faces, list) or not faces:
            raise PlanBindError(f"{feature}: manifest has no bound face list")
        for ref in faces:
            match = _REF.fullmatch(ref) if isinstance(ref, str) else None
            if match is None:
                raise PlanBindError(f"{feature}: malformed face reference {ref!r}")
            label = match["label"]
            owner = _LABEL.fullmatch(label)["feature"].lower()
            if owner != feature:
                raise PlanBindError(
                    f"{label}: wrongly owned by feature {feature!r}", label=label
                )
            result.setdefault(label, []).append(ref)
    return {label: tuple(dict.fromkeys(refs)) for label, refs in result.items()}


def _strings(text: str) -> Iterator[tuple[int, int, bool]]:
    """Yield quoted TOML tokens and whether they occupy an array value.

    Comments and multiline prose are consumed, not searched. This keeps bracket
    characters in prose from changing the array context of subsequent labels.
    """
    index = 0
    containers: list[str] = []
    while index < len(text):
        char = text[index]
        if char == "#":
            end = text.find("\n", index)
            index = len(text) if end < 0 else end + 1
            continue
        if char in "\"'":
            start = index
            multiline = text.startswith(char * 3, index)
            delimiter = char * (3 if multiline else 1)
            index += len(delimiter)
            while index < len(text):
                if char == '"' and text[index] == "\\":
                    index += 2
                elif text.startswith(delimiter, index):
                    index += len(delimiter)
                    if multiline:
                        # TOML permits one or two quotes before the closing triple.
                        for _extra in range(2):
                            if not text.startswith(char, index):
                                break
                            index += 1
                    break
                else:
                    index += 1
            if not multiline:
                yield start, index, bool(containers and containers[-1] == "[")
            continue
        if char in "[{":
            containers.append(char)
        elif char in "]}" and containers:
            containers.pop()
        index += 1


def _check_revision(
    plan: dict[str, Any],
    manifest: dict[str, Any],
    text: str,
    revision: str | None = None,
) -> None:
    """Require the traveler's printed revision to identify its drawing."""
    authored = plan.get("drawing", {}).get("revision")
    exported = manifest.get("drawing", {}).get("revision")
    if (
        not isinstance(authored, str)
        or authored in {"", "unknown"}
        or authored != exported
        or revision is not None
        and authored != revision
    ):
        line = 1
        in_drawing = False
        for number, source_line in enumerate(text.splitlines(), start=1):
            if re.match(r"\s*\[drawing\]\s*(?:#.*)?$", source_line):
                in_drawing = True
            elif re.match(r"\s*\[", source_line):
                in_drawing = False
            if (
                in_drawing
                and re.match(r"\s*revision\s*=", source_line)
                or re.match(r"\s*drawing\s*=", source_line)
            ):
                line = number
                break
        expected = exported if revision is None else revision
        raise PlanBindError(
            f"drawing.revision {authored!r} differs from manifest {exported!r}"
            f" or configured revision {expected!r}",
            line,
        )


def check_plan_revision(
    stem: str,
    out: Path = CAD_OUT,
    *,
    manifest: Path | None = None,
    revision: str | None = None,
) -> None:
    """Validate tracked plan revision before a traveler or release does any work."""
    source = plan_path(stem)
    try:
        text = source.read_bytes().decode("utf-8")
        _check_revision(
            tomllib.loads(text),
            _load(manifest if manifest is not None else bundle_paths(stem, out)[0]),
            text,
            revision,
        )
    except PlanBindError:
        raise
    except (
        OSError,
        UnicodeError,
        tomllib.TOMLDecodeError,
        TypeError,
        AttributeError,
    ) as exc:
        raise PlanBindError(f"cannot validate revision in {source}: {exc}") from exc


def _bound_plan_bytes(
    stem: str,
    out: Path = CAD_OUT,
    *,
    manifest_data: dict[str, Any] | None = None,
    destination: Path | None = None,
) -> bytes:
    """Regenerate a bound plan in memory without mutating traveler generations."""
    source = plan_path(stem)
    manifest_path, _step = bundle_paths(stem, out)
    target = (
        traveler_dir(stem, out) / "plan.toml"
        if destination is None
        else Path(destination)
    )
    try:
        text = source.read_bytes().decode("utf-8")
        plan = tomllib.loads(text)
        manifest = _load(manifest_path) if manifest_data is None else manifest_data
        if plan.get("part") != manifest.get("part") or manifest.get(
            "part"
        ) != stem.replace("_", "-"):
            raise PlanBindError(f"{stem}: plan and manifest part identities differ")
        _check_revision(plan, manifest, text)
        try:
            refs = label_refs(manifest)
        except PlanBindError as exc:
            if exc.label is not None:
                for start, end, _in_array in _strings(text):
                    if (
                        tomllib.loads("value = " + text[start:end])["value"]
                        == exc.label
                    ):
                        raise PlanBindError(
                            exc.detail, text.count("\n", 0, start) + 1
                        ) from exc
            raise
        replacements: list[tuple[int, int, str]] = []
        features_count = 0
        for start, end, in_array in _strings(text):
            token = text[start:end]
            value = tomllib.loads("value = " + token)["value"]
            if text[end:].lstrip().startswith("="):
                continue  # A quoted key is not a face-reference value.
            # The root features assignment is the only non-label value changed.
            prefix = text[text.rfind("\n", 0, start) + 1 : start]
            if re.fullmatch(r"\s*features\s*=\s*", prefix):
                features_count += 1
                relative = os.path.relpath(
                    manifest_path.resolve(), target.parent.resolve()
                )
                replacements.append((start, end, json.dumps(Path(relative).as_posix())))
            elif _LABEL.fullmatch(value):
                line = text.count("\n", 0, start) + 1
                if value not in refs:
                    raise PlanBindError(f"unknown label {value!r}", line)
                exact = refs[value]
                if len(exact) > 1 and not in_array:
                    raise PlanBindError(
                        f"{value}: {len(exact)} faces cannot bind a scalar", line
                    )
                replacements.append(
                    (start, end, ", ".join(json.dumps(ref) for ref in exact))
                )
        if features_count != 1:
            raise PlanBindError("expected exactly one features string assignment")
        for start, end, replacement in reversed(replacements):
            text = text[:start] + replacement + text[end:]
    except PlanBindError:
        raise
    except (
        OSError,
        UnicodeError,
        tomllib.TOMLDecodeError,
        KeyError,
        TypeError,
        AttributeError,
    ) as exc:
        raise PlanBindError(f"cannot bind {source}: {exc}") from exc
    return text.encode("utf-8")


def bind_plan(
    stem: str, out: Path = CAD_OUT, *, destination: Path | None = None
) -> Path:
    """Replace whole-string label values only; retain all other source bytes."""
    content = _bound_plan_bytes(stem, out, destination=destination)
    target = (
        traveler_dir(stem, out) / "plan.toml"
        if destination is None
        else Path(destination)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def _cad_tables(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if "cad" in node:
            yield node
        for value in node.values():
            yield from _cad_tables(value)
    elif isinstance(node, list):
        for value in node:
            yield from _cad_tables(value)


def _spec_module(table: dict[str, Any]) -> str:
    stem = table["cad"]
    if not isinstance(stem, str) or _TL_STEM.fullmatch(stem) is None:
        raise PlanBindError(f"invalid fixture TL stem {stem!r}")
    if "solids" in table:
        raise PlanBindError(f"{stem}: cad-tagged inventory table also declares solids")
    return stem + "_spec"


def shop_spec_modules() -> tuple[str, ...]:
    """The dynamically imported spec names that doit must fold as dependencies."""
    try:
        inventory = _load(shop_paths()[0])
        return tuple(sorted({_spec_module(table) for table in _cad_tables(inventory)}))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise PlanBindError(f"cannot read inventory: {exc}") from exc


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{ "
            + ", ".join(
                f"{_toml_value(key)} = {_toml_value(item)}"
                for key, item in value.items()
            )
            + " }"
        )
    raise PlanBindError(f"cannot serialize fixture value {value!r}")


def _shop_contents() -> tuple[bytes, bytes, bytes]:
    """Regenerate current tracked shop inputs without touching generated outputs."""
    from prechips.model import FixtureSolid
    from pydantic import ValidationError

    try:
        sources = shop_paths()
        inventory = _load(sources[0])
        for table in _cad_tables(inventory):
            module_name = _spec_module(table)
            try:
                module = importlib.import_module(module_name)
                solids = module.PRECHIPS_SOLIDS
            except (ImportError, AttributeError) as exc:
                raise PlanBindError(
                    f"{module_name}: missing module or PRECHIPS_SOLIDS ({exc})"
                ) from exc
            if not isinstance(solids, list) or not all(
                isinstance(solid, dict) for solid in solids
            ):
                raise PlanBindError(
                    f"{module_name}.PRECHIPS_SOLIDS must be a list of dicts"
                )
            for solid in solids:
                FixtureSolid.model_validate(solid)
            table["solids"] = solids
            del table["cad"]
        content = (
            "# Generated HA shop inputs; fixture solids come from their CAD specs.\n"
        )
        content += "".join(
            f"{_toml_value(key)} = {_toml_value(value)}\n"
            for key, value in inventory.items()
        )
        return (
            content.encode("utf-8"),
            sources[1].read_bytes(),
            sources[2].read_bytes(),
        )
    except PlanBindError:
        raise
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValidationError) as exc:
        raise PlanBindError(f"cannot bind shop: {exc}") from exc


def bind_shop(
    out: Path = CAD_OUT, *, directory: Path | None = None
) -> tuple[Path, Path, Path]:
    """Generate shop inputs, sourcing every cad-tagged solid from its TL spec."""
    contents = _shop_contents()
    directory = (
        Path(out) / "travelers" / "_shop" if directory is None else Path(directory)
    )
    targets = tuple(directory / name for name in SHOP_FILES)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        # All stems bind the same snapshot. Serialize first installation, then
        # leave identical files untouched so another stem's reader cannot see a
        # truncate/write window (or a Windows sharing violation on replacement).
        with FileLock(directory / ".bind.lock"):
            for target, content in zip(targets, contents, strict=True):
                if not target.is_file() or target.read_bytes() != content:
                    target.write_bytes(content)
    except OSError as exc:
        raise PlanBindError(f"cannot write bound shop: {exc}") from exc
    return targets


def _required_names(plan: dict[str, Any]) -> tuple[str, ...]:
    from prechips.report import inspection_sketch_names

    names = ("report.json", "traveler.html")
    names += tuple(
        f"setup-S{ordinal}.png"
        for ordinal, _setup in enumerate(plan["setups"], start=1)
    )
    names += inspection_sketch_names(plan)
    return names


def required_outputs(bound_plan: Path) -> tuple[Path, ...]:
    """Derive every render filename using the pinned prechips report API."""
    return tuple(
        Path(bound_plan).parent / name for name in _required_names(_load(bound_plan))
    )


def _verified_traveler_bytes(
    stem: str, out: Path = CAD_OUT, manifest: Path | None = None
) -> dict[Path, bytes]:
    """Snapshot and validate exactly the traveler and shop files a release ships."""
    directory = traveler_dir(stem, out)
    try:
        plan_path_bound = directory / "plan.toml"
        plan_bytes = plan_path_bound.read_bytes()
        plan = tomllib.loads(plan_bytes.decode("utf-8"))
        snapshots = {plan_path_bound: plan_bytes}
        for name in _required_names(plan):
            path = directory / name
            if not path.is_file():
                raise TravelerIncomplete(f"{stem}: missing {name}")
            snapshots[path] = path.read_bytes()
        report = json.loads(snapshots[directory / "report.json"])
        if report.get("expected_exit") != 0:
            raise TravelerIncomplete(f"{stem}: report expected_exit is not 0")
        manifest_path = (
            bundle_paths(stem, out)[0] if manifest is None else Path(manifest)
        )
        manifest_bytes = manifest_path.read_bytes()
        manifest_data = tomllib.loads(manifest_bytes.decode("utf-8"))
        if plan_bytes != _bound_plan_bytes(stem, out, manifest_data=manifest_data):
            raise TravelerIncomplete(
                f"{stem}: bound plan differs from current tracked plan"
            )
        shop_bytes = {}
        for name, expected_bytes in zip(SHOP_FILES, _shop_contents(), strict=True):
            path = Path(out) / "travelers" / "_shop" / name
            content = path.read_bytes()
            if content != expected_bytes:
                raise TravelerIncomplete(
                    f"{stem}: bound {name} differs from current shop inputs"
                )
            shop_bytes[name] = content
            snapshots[path] = content
        step_bytes = (manifest_path.parent / manifest_data["step"]).read_bytes()
        digest = hashlib.sha256(step_bytes).hexdigest()
        if (
            report.get("step_sha256") != digest
            or manifest_data.get("step_sha256") != digest
        ):
            raise TravelerIncomplete(
                f"{stem}: report step_sha256 differs from manifest or STEP"
            )
        records = report.get("inputs", {})
        inputs = {
            "plan": plan_bytes,
            "features": manifest_bytes,
            "inventory": shop_bytes["inventory.toml"],
            "shop_policy": shop_bytes["shop-policy.toml"],
            "cutting_data": shop_bytes["cutting-data.toml"],
            "step": step_bytes,
        }
        for kind, content in inputs.items():
            record = records.get(kind)
            if (
                not isinstance(record, dict)
                or record.get("sha256") != hashlib.sha256(content).hexdigest()
            ):
                raise TravelerIncomplete(
                    f"{stem}: {kind} input record missing or sha256 differs"
                )
        expected = {}
        for ordinal, setup in enumerate(plan["setups"], start=1):
            expected[f"setup-S{ordinal}.png"] = f"render:{setup['id']}"
            for op in setup["ops"]:
                if isinstance(op.get("inspection_views"), dict):
                    for requirement in op["inspection_views"]:
                        name = f"setup-S{ordinal}-op{op['op']}-{requirement}.png"
                        expected[name] = (
                            f"render:{setup['id']}:{op['op']}:{requirement}"
                        )
        for path, content in snapshots.items():
            if path.suffix != ".png":
                continue
            record = records.get(expected[path.name])
            if (
                not isinstance(record, dict)
                or record.get("path") != path.name
                or record.get("sha256") != hashlib.sha256(content).hexdigest()
            ):
                raise TravelerIncomplete(
                    f"{stem}: {path.name} render record missing or sha256 differs"
                )
        return snapshots
    except TravelerIncomplete:
        raise
    except (
        OSError,
        UnicodeError,
        tomllib.TOMLDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        AttributeError,
        PlanBindError,
    ) as exc:
        raise TravelerIncomplete(f"{stem}: cannot verify traveler ({exc})") from exc


def verify_traveler(
    stem: str, out: Path = CAD_OUT, manifest: Path | None = None
) -> None:
    """Require current input bytes, current authoring, exit zero, and all renders."""
    _verified_traveler_bytes(stem, out, manifest)


def traveler_complete(stem: str, out: Path = CAD_OUT) -> bool:
    try:
        verify_traveler(stem, out)
    except TravelerIncomplete:
        return False
    return True


def stage_travelers(out: Path, stage: Path) -> list[Path]:
    """Ship only verified byte snapshots, including their shared shop inputs."""
    import _telemetry

    with _telemetry.span("release.travelers_stage", stems=len(TRAVELER_STEMS)):
        pending: dict[Path, bytes] = {}
        for stem in TRAVELER_STEMS:
            snapshots = _verified_traveler_bytes(
                stem, out, bundle_paths(stem, stage)[0]
            )
            for path, content in snapshots.items():
                if path in pending and pending[path] != content:
                    raise TravelerIncomplete(
                        f"shop input {path.name} changed between travelers"
                    )
                pending[path] = content
        for source, content in pending.items():
            target = Path(stage) / source.relative_to(out)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return [traveler_dir(stem, stage) for stem in TRAVELER_STEMS]
