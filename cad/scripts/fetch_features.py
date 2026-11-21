"""Fill ``cad/out/features/<stem>/`` from a published release; no SolidWorks, no farm.

``uv run --frozen python cad/scripts/fetch_features.py <stem> [<stem> ...]``
``uv run --frozen python cad/scripts/fetch_features.py --all [--release v51]``

Every part with its own drawing ships its feature bundle (the labelled STEPs,
their ``.faces.json`` face inventories once releases carry them, and the
``features.toml`` bound to them) in the release ZIP under ``features/<stem>/``,
from the first release cut with all-part bundles (the one after v50); earlier
releases carry only the parts whose drawing declared requirements, and asking
one for another part fails with "the release carries no ... bundle". This reads
only those members from the GitHub release asset with HTTP range requests (the
ZIP's central directory, then each member, through the comparison tool's
reader that release drawing diffs use), so one part costs a few MB rather than
the whole multi-GB bundle. The latest release is used unless ``--release``
names a tag.

Each fetched bundle must identify its part and bind its STEP's exact bytes
(``step``, ``step_sha256``); a bundle that does not is refused and nothing is
written. Its recipe is then diffed between the release's tagged commit and
the working tree:

- ``geometry`` inputs (``part:<stem>`` and the labelled-STEP export code,
  ``package:features:<stem>``) changed: the STEP itself may differ, so the
  bundle is STALE and needs a farm build of ``package:features:<stem>``;
- otherwise ``features.toml`` is rebound here from this checkout's
  declarations (``export_features.write_manifest`` over the fetched STEPs and
  inventories, exactly what ``package:manifest:<stem>`` runs), so new or
  changed ``requirement(...)`` declarations need no farm. A release made
  before face inventories shipped cannot be rebound; a declaration change
  against it is STALE.

A STALE bundle is reported with its findings and the command exits 2 without
writing it unless ``--accept-stale`` is given; declarations that do not bind
(a selector matching no face) exit 1.

With the bundle in place, the part's traveler and NC programs run seat-free
without doit (whose ``prechips:<stem>``/``cam:<stem>`` tasks would first try to
rebuild the bundle):

    uv run --frozen python cad/scripts/prechips_traveler.py <stem>
    uv run --frozen python cad/scripts/cam_nc.py <stem>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path
from typing import Any

import _config
import _telemetry
import export_features
from _export_feature_faces import FeatureFaceError, inventory_path
from _release_drawing_diff import release_zip_reader, safe_member_parts
from features_bound import FeaturesBoundError, validate_bundle

REPO = export_features.REPO
PROJECT_SLUG = "harmonic-analyzer"
# Releases live upstream; a fork's origin has none (release_diff.asset_url
# hardcodes the same repository).
UPSTREAM = "pedropaulovc/harmonic-analyzer"
_API = f"https://api.github.com/repos/{UPSTREAM}/releases/{{which}}"


class FetchError(RuntimeError):
    """The release, its asset or a bundle in it cannot be used."""


def _git(*args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=False
    )
    if done.returncode:
        raise FetchError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def release_asset(tag: str | None) -> tuple[str, str]:
    """The release's tag and the download URL of its ``<project>-<tag>.zip``."""
    which = "latest" if tag is None else f"tags/{tag}"
    headers = {"User-Agent": PROJECT_SLUG}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(_API.format(which=which), headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        release = json.load(response)
    name = f"{PROJECT_SLUG}-{release['tag_name']}.zip"
    for asset in release.get("assets", ()):
        if asset["name"] == name:
            return release["tag_name"], asset["browser_download_url"]
    raise FetchError(f"release {release['tag_name']} has no {name} asset")


def extract_bundles(
    reader: Any,
    url: str,
    directory: dict[str, dict],
    stems: list[str],
    destination: Path,
) -> None:
    """Copy each part's ``features/<stem>/`` members into ``destination/features/<stem>/``.

    Member names must be safe on Windows (``safe_member_parts``) and sit
    directly in the bundle directory; every target must resolve under it."""
    for stem in stems:
        prefix = f"features/{stem}/"
        members = [
            name
            for name in directory
            if name.startswith(prefix) and not name.endswith("/")
        ]
        if not members:
            raise FetchError(f"{stem}: the release carries no {prefix} bundle")
        root = (destination / "features" / stem).resolve()
        for name in members:
            try:
                parts = safe_member_parts(name)
            except ValueError as exc:
                raise FetchError(str(exc)) from None
            if len(parts) != 3:
                raise FetchError(f"{name}: unexpected nested bundle member")
            target = destination / "features" / stem / parts[2]
            if not target.resolve().is_relative_to(root):
                raise FetchError(f"{name}: escapes the bundle directory")
            reader.extract(url, directory[name], target)


def check_binding(stem: str, out: Path) -> None:
    """Refuse a bundle that does not identify its part or bind its STEP bytes."""
    manifest_path, step_path = export_features.bundle_paths(stem, out)
    try:
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(step_path.read_bytes()).hexdigest()
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise FetchError(f"{stem}: unreadable bundle ({exc})") from exc
    expected = (stem.replace("_", "-"), step_path.name, digest)
    recorded = (manifest.get("part"), manifest.get("step"), manifest.get("step_sha256"))
    if recorded != expected:
        raise FetchError(f"{stem}: bundle records {recorded}, its files are {expected}")


def recipe_files(stem: str) -> dict[str, str]:
    """Repo-relative tracked inputs of the part's keys, each labelled with what
    it can change: ``geometry`` (``part:<stem>`` and the labelled-STEP export
    code) or ``manifest`` (only ``package:manifest:<stem>``: notes, citations,
    declarations). Other parts' registry rows in the generic exporter's config
    closure cannot change this part's STEP and are left out."""
    sys.path.insert(0, str(REPO))
    import dodo  # noqa: PLC0415 - the graph's own key inputs, loaded only here

    out = (REPO / "cad" / "out").resolve()
    part = dodo._part_file_deps(dodo.SCRIPTS_DIR / f"build_{stem}.py", stem)
    exporter = [
        dep for dep in dodo._feature_export_file_deps(stem) if dep.endswith(".py")
    ]
    labelled: dict[str, str] = {}
    for label, deps in (
        ("manifest", dodo._feature_manifest_file_deps(stem)),
        ("geometry", [*part, *exporter]),
    ):
        for dep in deps:
            path = Path(dep).resolve()
            if path == Path(dodo.RELEASE_VERSION_FILE).resolve() or out in path.parents:
                continue
            if path.is_relative_to(REPO.resolve()):
                labelled[path.relative_to(REPO.resolve()).as_posix()] = label
    return dict(sorted(labelled.items()))


def rebind(stem: str, out: Path) -> None:
    """Rewrite ``stem``'s fetched ``features.toml`` from this checkout's
    declarations over the fetched STEPs and face inventories."""
    _manifest, step = export_features.bundle_paths(stem, out)
    missing = [
        path.name
        for path in export_features.exported_steps(stem, out)
        if not inventory_path(path).is_file()
    ]
    if missing:
        raise FetchError(f"{stem}: the release carries no face inventory for {missing}")
    export_features.write_manifest(stem, step, revision=_config.release_revision())


def changed_since(commit: str, files: list[str]) -> list[str]:
    """The ``files`` that differ between ``commit`` and the working tree."""
    changed: list[str] = []
    for start in range(0, len(files), 200):
        output = _git("diff", "--name-only", commit, "--", *files[start : start + 200])
        changed += [line for line in output.splitlines() if line]
    return sorted(set(changed))


def tag_commit(tag: str) -> str:
    try:
        return _git("rev-parse", f"{tag}^{{commit}}")
    except FetchError:
        _git("fetch", "--quiet", f"https://github.com/{UPSTREAM}.git", "tag", tag)
        return _git("rev-parse", f"{tag}^{{commit}}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("stems", nargs="*", help="parts (underscore or dashed stems)")
    parser.add_argument(
        "--all", action="store_true", help="every part with a feature bundle"
    )
    parser.add_argument("--release", help="release tag (default: the latest release)")
    parser.add_argument(
        "--out",
        type=Path,
        default=export_features.OUT,
        help="output root (default: cad/out)",
    )
    parser.add_argument(
        "--accept-stale",
        action="store_true",
        help="write bundles this checkout's recipe has moved past",
    )
    args = parser.parse_args(argv)
    stems = (
        list(export_features.SUPPORTED_PARTS)
        if args.all
        else [stem.replace("-", "_") for stem in args.stems]
    )
    unknown = sorted(set(stems) - set(export_features.SUPPORTED_PARTS))
    if not stems or unknown:
        parser.error(
            f"name parts with a feature bundle (unknown: {', '.join(unknown) or 'none given'})"
        )
    _telemetry.set_service("fetch-features")
    _telemetry.configure()

    try:
        tag, url = release_asset(args.release)
        commit = tag_commit(tag)
        head = _git("rev-parse", "HEAD")
        _telemetry.info(
            f"fetch-features: release {tag} (commit {commit[:12]}), checkout HEAD {head[:12]}",
            release=tag,
        )
        with tempfile.TemporaryDirectory(prefix="fetch-features-") as scratch:
            staging = Path(scratch)
            reader = release_zip_reader()
            try:
                directory = reader.central_dir(url)
                extract_bundles(reader, url, directory, stems, staging)
            except ValueError as exc:
                raise FetchError(f"release {tag}: {exc}") from exc
            stale: dict[str, list[str]] = {}
            rebound: list[str] = []
            for stem in stems:
                check_binding(stem, staging)
                recipe = recipe_files(stem)
                changed = changed_since(commit, list(recipe))
                findings = [
                    f"geometry input changed since {tag}: {name}"
                    for name in changed
                    if recipe[name] == "geometry"
                ]
                if not findings:
                    try:
                        rebind(stem, staging)
                        rebound.append(stem)
                    except FetchError as exc:
                        if changed:
                            findings += [
                                f"manifest input changed since {tag}: {name}"
                                for name in changed
                            ]
                            findings.append(f"cannot rebind offline: {exc}")
                try:
                    validate_bundle(stem, staging)
                except FeaturesBoundError as exc:
                    findings.append(
                        f"does not match this checkout's declarations: {exc}"
                    )
                if findings:
                    stale[stem] = findings
            for stem, findings in stale.items():
                _telemetry.warn(
                    f"fetch-features: STALE {stem} ({tag} bundle; needs a farm build of package:features:{stem} to be current)\n"
                    + "\n".join(f"  {finding}" for finding in findings),
                    stem=stem,
                    release=tag,
                )
            if stale and not args.accept_stale:
                _telemetry.error(
                    "fetch-features: nothing written; rerun with --accept-stale to use these bundles anyway"
                )
                return 2
            for stem in stems:
                source = staging / "features" / stem
                target = Path(args.out) / "features" / stem
                shutil.rmtree(target, ignore_errors=True)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, target)
                state = "STALE" if stem in stale else "current"
                how = (
                    ", features.toml rebound from this checkout"
                    if stem in rebound
                    else ""
                )
                _telemetry.info(
                    f"fetch-features: {stem}: {target} ({state} for this checkout{how})",
                    stem=stem,
                    release=tag,
                )
    except FeatureFaceError as exc:
        _telemetry.error(f"fetch-features: declarations do not bind: {exc}")
        return 1
    except (FetchError, OSError) as exc:
        _telemetry.error(f"fetch-features: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
