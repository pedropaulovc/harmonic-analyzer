"""Member-qualified neutral paths and part-owned purchased-member exports.

The parts registry owns the member inventory. Bare STEP/PNG files represent only
``default_configuration``; the other members use the existing mesh-key suffix.
Scene STL files remain scene-export owned and are qualified for every named member.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_SCHEMA = "harmonic-analyzer/part-member-neutral@1"


def step_export_preferences():
    """Create the shared AP214 baseline without loading seat dependencies on import."""
    from _preferences import PreferenceSpec

    # AP214 carries colours. Face/edge properties preserve feature-face names;
    # split periodic faces retain the representation used by feature bundles.
    return PreferenceSpec(
        label="step-export",
        integers={75: 214},  # swStepAP
        toggles={
            396: True,  # swStepExportSplitPeriodic
            397: True,  # swStepExportFaceEdgeProps
        },
    )


def mesh_key(stem: str, cfg: str) -> str:
    """Existing scene/STL key: non-Default configurations use a safe lowercase suffix."""
    if not cfg or cfg.lower() == "default":
        return stem
    safe = "".join(c if c.isalnum() else "-" for c in cfg.strip().lower()).strip("-")
    return f"{stem}--{safe}"


def member_export_paths(
    stem: str, configuration: str, default_configuration: str, out: Path | None = None,
) -> dict[str, Path]:
    """Pure physical paths for one logical member (no registry or COM imports).

    A named first member has a qualified STL but a bare STEP and PNG. This is an
    explicit per-format association, not permission to use the bare file for any
    other member. Historical resolvers supply their own declared default member.
    """
    root = Path(out) if out is not None else Path(__file__).resolve().parents[1] / "out"
    dashed = stem.replace("_", "-")
    mesh = mesh_key(dashed, configuration)
    neutral = dashed if configuration == default_configuration else mesh
    return {
        "step": root / "step" / f"{neutral}.STEP",
        "stl": root / "stl" / f"{mesh}.STL",
        "png": root / "png" / neutral / f"{neutral}_isometric.png",
    }


def member_configurations(stem: str) -> tuple[str, ...]:
    """Registry-declared heterogeneous members, with the bare-output member first."""
    import _config

    try:
        row = _config.parts(stem.replace("_", "-"))
    except KeyError:
        return ()
    quantities = row.get("configuration_quantities")
    if quantities is None:
        return ()
    default = row.get("default_configuration")
    if (not isinstance(quantities, dict) or not quantities
            or not isinstance(default, str) or default not in quantities
            or any(not isinstance(name, str)
                   or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name) is None
                   or not isinstance(quantity, int) or isinstance(quantity, bool)
                   or quantity <= 0 for name, quantity in quantities.items())):
        raise ValueError(f"{stem}: invalid configuration_quantities/default_configuration")
    names = (default, *(name for name in quantities if name != default))
    if len({mesh_key(stem, name) for name in names}) != len(names):
        raise ValueError(f"{stem}: colliding configuration export keys")
    return names


def configuration_export_paths(
    stem: str, out: Path | None = None,
) -> dict[str, dict[str, Path]]:
    """Every declared member's paths, derived only from the parts registry."""
    names = member_configurations(stem)
    return {name: member_export_paths(stem, name, names[0], out) for name in names}


def configuration_manifest_path(stem: str, out: Path | None = None) -> Path:
    root = Path(out) if out is not None else Path(__file__).resolve().parents[1] / "out"
    return root / "reports" / "part-neutral" / f"{stem.replace('_', '-')}.json"


def part_configuration_outputs(stem: str, out: Path | None = None) -> list[Path]:
    """Part-owned targets/cache payload; scene-owned configured STLs are excluded."""
    members = configuration_export_paths(stem, out)
    if not members:
        return []
    return [*(paths[kind] for paths in members.values() for kind in ("step", "png")),
            configuration_manifest_path(stem, out)]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path, root: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"part member neutral output missing/empty: {path}")
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
            "sha256": _sha256(path)}


def validate_member_exports(stem: str, out: Path | None = None) -> set[Path]:
    """Validate exact producer bytes against the existing native execution identity.

    Parent assembly saves can legitimately churn child-native bytes without
    changing ``.<stem>.execution``. The producer hashes the unchanged fresh native
    before dodo stamps that identity; consumers compare the certificate to that
    token, never to the subsequently saved native's raw bytes.
    """
    members = configuration_export_paths(stem, out)
    if not members:
        return set()
    root = next(iter(members.values()))["step"].parent.parent
    manifest = configuration_manifest_path(stem, root)
    dashed = stem.replace("_", "-")
    try:
        certificate = json.loads(manifest.read_text(encoding="utf-8"))
        identity = (root / "sldprt" / f".{dashed}.execution").read_text(encoding="utf-8").strip()
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"{dashed}: member export certificate/execution identity missing; "
            f"request an explicit reasoned cache refresh of part:{stem}"
        ) from exc
    expected_source = f"sldprt/{dashed}.SLDPRT"
    native = root / expected_source
    if (not isinstance(certificate, dict) or certificate.get("schema") != _SCHEMA
            or certificate.get("source") != expected_source
            or not re.fullmatch(r"[0-9a-f]{64}", identity)
            or certificate.get("execution_identity") != identity
            or not native.is_file() or native.stat().st_size == 0
            or certificate.get("default_configuration") != next(iter(members))
            or not isinstance(certificate.get("configurations"), dict)
            or set(certificate["configurations"]) != set(members)):
        raise RuntimeError(
            f"{dashed}: stale member export identity/inventory; "
            f"request an explicit reasoned cache refresh of part:{stem}"
        )
    outputs: set[Path] = set()
    for configuration, paths in members.items():
        records = certificate["configurations"][configuration]
        if not isinstance(records, dict) or set(records) != {"step", "png"}:
            raise RuntimeError(f"{dashed}/{configuration}: member export format inventory drifted")
        for kind in ("step", "png"):
            path = paths[kind]
            if records[kind] != _file_record(path, root):
                raise RuntimeError(
                    f"{dashed}/{configuration}: stale member {kind} bytes; "
                    f"request an explicit reasoned cache refresh of part:{stem}"
                )
            outputs.add(path)
    return outputs


def _active_configuration(doc: Any) -> str:
    from _com import _read_member

    manager = _read_member(doc, "ConfigurationManager")
    active = _read_member(manager, "ActiveConfiguration") if manager is not None else None
    return str(_read_member(active, "Name") or "") if active is not None else ""


def _show_member(doc: Any, stem: str, configuration: str) -> None:
    if _active_configuration(doc) != configuration:
        if not doc.ShowConfiguration2(configuration) or _active_configuration(doc) != configuration:
            raise RuntimeError(f"{stem}: could not activate export member {configuration!r}")
    if not doc.ForceRebuild3(False) or not doc.EditRebuild3():
        raise RuntimeError(f"{stem}/{configuration}: member export rebuild failed")
    if _active_configuration(doc) != configuration:
        raise RuntimeError(f"{stem}: export member changed during rebuild: {configuration!r}")


async def export_member_configurations(
    adapter: Any, part_name: str, configurations: Iterable[str],
) -> None:
    """Produce all member STEP/PNG outputs on the verified reopened native part.

    Only the changed part task invokes this producer. No native save is allowed
    after this hook; dodo's existing post-build execution stamp must hash the same
    bytes certified here. A partial export has no certificate and cannot release.
    Export failures remain primary if default restoration or the native SHA guard
    also fails; cleanup errors are attached as notes. Cleanup-only failures raise
    and likewise prevent certification.
    """
    from _check import check
    from _part_save import set_isometric_view
    from _preferences import enforce_preferences

    part_name = part_name.replace("_", "-")
    members = configuration_export_paths(part_name)
    root = (next(iter(members.values()))["step"].parent.parent if members
            else Path(__file__).resolve().parents[1] / "out")
    manifest = configuration_manifest_path(part_name, root)
    manifest.unlink(missing_ok=True)
    names = tuple(members)
    if not names or tuple(configurations) != names:
        raise RuntimeError(f"{part_name}: native and registry export members differ")
    doc = adapter.currentModel
    default = names[0]
    if _active_configuration(doc) != default:
        raise RuntimeError(f"{part_name}: saved active export member must be {default!r}")
    native = root / "sldprt" / f"{part_name}.SLDPRT"
    if Path(doc.GetPathName()).resolve() != native.resolve():
        raise RuntimeError(f"{part_name}: export document is not the saved native part")
    before = _sha256(native)
    enforce_preferences(adapter, step_export_preferences())
    records: dict[str, dict[str, Any]] = {}
    try:
        for configuration, paths in members.items():
            _show_member(doc, part_name, configuration)
            step, png = paths["step"], paths["png"]
            step.parent.mkdir(parents=True, exist_ok=True)
            step.unlink(missing_ok=True)
            # Neutral SaveAs can otherwise export a reader's selected body subset.
            doc.ClearSelection2(True)
            rc = doc.SaveAs3(str(step.resolve()), 0, 1 | 8)  # Silent | AvoidRebuildOnSave
            if not step.is_file() or step.stat().st_size == 0:
                step.unlink(missing_ok=True)
                raise RuntimeError(f"{part_name}/{configuration}: STEP export failed (rc={rc!r})")
            set_isometric_view(adapter)
            png.parent.mkdir(parents=True, exist_ok=True)
            png.unlink(missing_ok=True)
            check(f"export member PNG {configuration}", await adapter.export_image({
                "file_path": str(png.resolve()), "format_type": "png",
                "width": 1600, "height": 1000, "view_orientation": "isometric",
            }))
            records[configuration] = {kind: _file_record(paths[kind], root)
                                      for kind in ("step", "png")}
    finally:
        primary_error = sys.exception()
        restoration_error = None
        try:
            _show_member(doc, part_name, default)
        except Exception as cleanup_error:
            if primary_error is None:
                restoration_error = cleanup_error
            else:
                primary_error.add_note(
                    f"Default member restoration failed: {type(cleanup_error).__name__}: {cleanup_error}"
                )
        try:
            if _sha256(native) != before:
                raise RuntimeError(f"{part_name}: native bytes changed during member export")
        except Exception as cleanup_error:
            pending_error = primary_error if primary_error is not None else restoration_error
            if pending_error is None:
                raise
            pending_error.add_note(
                f"Native SHA guard failed: {type(cleanup_error).__name__}: {cleanup_error}"
            )
        if primary_error is None and restoration_error is not None:
            raise restoration_error
    for configuration, paths in members.items():
        for kind in ("step", "png"):
            if records[configuration][kind] != _file_record(paths[kind], root):
                raise RuntimeError(f"{part_name}/{configuration}: member {kind} changed during export")
    certificate = {
        "schema": _SCHEMA, "source": native.relative_to(root).as_posix(),
        "execution_identity": before, "default_configuration": default,
        "configurations": records,
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_suffix(".json.partial")
    temporary.write_text(json.dumps(certificate, indent=1, sort_keys=True), encoding="utf-8")
    temporary.replace(manifest)
