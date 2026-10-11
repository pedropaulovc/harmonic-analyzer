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
import shutil
import tomllib
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterator

from filelock import FileLock
from prechips.model import FixtureSolid
from prechips.report import inspection_sketch_names
from pydantic import ValidationError

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
    arrays = 0
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
                yield start, index, arrays > 0
            continue
        if char == "[":
            arrays += 1
        elif char == "]":
            arrays -= 1
        index += 1


def bind_plan(stem: str, out: Path = CAD_OUT) -> Path:
    """Replace whole-string label values only; retain all other source bytes."""
    source = plan_path(stem)
    manifest_path, _step = bundle_paths(stem, out)
    try:
        text = source.read_bytes().decode("utf-8")
        plan = tomllib.loads(text)
        manifest = _load(manifest_path)
        if plan.get("part") != manifest.get("part") or manifest.get(
            "part"
        ) != stem.replace("_", "-"):
            raise PlanBindError(f"{stem}: plan and manifest part identities differ")
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
                    manifest_path.resolve(), traveler_dir(stem, out).resolve()
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
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise PlanBindError(f"cannot bind {source}: {exc}") from exc
    target = traveler_dir(stem, out) / "plan.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))
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


def bind_shop(out: Path = CAD_OUT) -> tuple[Path, Path, Path]:
    """Generate shop inputs, sourcing every cad-tagged solid from its TL spec."""
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
        contents = (
            content.encode("utf-8"),
            sources[1].read_bytes(),
            sources[2].read_bytes(),
        )
    except PlanBindError:
        raise
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValidationError) as exc:
        raise PlanBindError(f"cannot bind shop: {exc}") from exc
    directory = Path(out) / "travelers" / "_shop"
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


def required_outputs(bound_plan: Path) -> tuple[Path, ...]:
    """Derive every render filename using the pinned prechips report API."""
    plan = _load(bound_plan)
    directory = Path(bound_plan).parent
    names = ("report.json", "traveler.html")
    names += tuple(
        f"setup-S{ordinal}.png"
        for ordinal, _setup in enumerate(plan["setups"], start=1)
    )
    names += inspection_sketch_names(plan)
    return tuple(directory / name for name in names)


def verify_traveler(
    stem: str, out: Path = CAD_OUT, manifest: Path | None = None
) -> None:
    """Require exit zero, all plan renders, and the manifest's exact STEP digest."""
    directory = traveler_dir(stem, out)
    try:
        outputs = required_outputs(directory / "plan.toml")
        for path in outputs:
            if not path.is_file():
                raise TravelerIncomplete(f"{stem}: missing {path.name}")
        report = json.loads((directory / "report.json").read_bytes())
        if report.get("expected_exit") != 0:
            raise TravelerIncomplete(f"{stem}: report expected_exit is not 0")
        manifest_data = _load(
            manifest if manifest is not None else bundle_paths(stem, out)[0]
        )
        digest = manifest_data.get("step_sha256")
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or report.get("step_sha256") != digest
        ):
            raise TravelerIncomplete(
                f"{stem}: report step_sha256 differs from manifest"
            )
        plan = _load(directory / "plan.toml")
        records = report.get("inputs", {})
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
        for path in outputs:
            if path.suffix != ".png":
                continue
            record = records.get(expected[path.name])
            if (
                not isinstance(record, dict)
                or record.get("path") != path.name
                or record.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest()
            ):
                raise TravelerIncomplete(
                    f"{stem}: {path.name} render record missing or sha256 differs"
                )
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
    ) as exc:
        raise TravelerIncomplete(f"{stem}: cannot verify traveler ({exc})") from exc


def traveler_complete(stem: str, out: Path = CAD_OUT) -> bool:
    try:
        verify_traveler(stem, out)
    except TravelerIncomplete:
        return False
    return True


def stage_travelers(out: Path, stage: Path) -> list[Path]:
    """Verify every enrolled traveler against staged features before copying any."""
    for stem in TRAVELER_STEMS:
        verify_traveler(stem, out, manifest=bundle_paths(stem, stage)[0])
    staged = []
    for stem in TRAVELER_STEMS:
        target = traveler_dir(stem, stage)
        shutil.copytree(traveler_dir(stem, out), target, dirs_exist_ok=True)
        staged.append(target)
    return staged
