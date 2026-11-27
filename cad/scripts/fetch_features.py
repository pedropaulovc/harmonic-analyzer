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
written. A release cut before face inventories shipped can be neither
rebound nor validated here, so its bundles are always STALE (and any older
than this exporter have changed geometry inputs anyway). Otherwise the recipe
is diffed between the release's tagged commit and the working tree:

- ``geometry`` inputs (``part:<stem>`` and the labelled-STEP export code,
  ``package:features:<stem>``) changed: the STEP itself may differ, so the
  bundle is STALE and needs a farm build of ``package:features:<stem>``;
- otherwise ``features.toml`` is rebound here from this checkout's
  declarations (``export_features.write_manifest`` over the fetched STEPs and
  inventories, exactly what ``package:manifest:<stem>`` runs), so new or
  changed ``requirement(...)`` declarations need no farm.

A STALE bundle is reported with its findings and the command exits 2 without
writing it; there is no override. Declarations that do not bind (a selector
matching no face) exit 1. A rebound ``features.toml`` records this checkout's
geometry inputs (``_features_provenance``), which ``cam_nc.py`` and
``prechips_traveler.py`` check before they read the bundle.

``uv run --frozen python cad/scripts/fetch_features.py --check <stem> [...]``
(or ``--check --all``) fetches nothing: it reports whether the bundles already
under ``--out`` (copied in, or left by an older checkout) were built from this
checkout's geometry, and exits 2 if any was not. ``--rebind`` in its place
also rebinds each current bundle's ``features.toml`` from this checkout's
declarations, keeping its geometry inputs: the seat-free step after a
``requirement(...)`` edit (``export_features.py <stem>`` alone writes no
geometry inputs, so the bundle it binds is refused).

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
import tempfile
import tomllib
import urllib.request
from pathlib import Path
from typing import Any

import _config
import _features_provenance
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


def rebind(stem: str, out: Path) -> None:
    """Rewrite ``stem``'s fetched ``features.toml`` from this checkout's
    declarations over the fetched STEPs and face inventories, recording this
    checkout's geometry inputs (the caller has found them unchanged since the
    release's commit)."""
    _manifest, step = export_features.bundle_paths(stem, out)
    missing = [
        path.name
        for path in export_features.exported_steps(stem, out)
        if not inventory_path(path).is_file()
    ]
    if missing:
        raise FetchError(f"{stem}: the release carries no face inventory for {missing}")
    export_features.write_manifest(stem, step, revision=_config.release_revision())
    _features_provenance.stamp(stem, out)


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
    local = parser.add_mutually_exclusive_group()
    local.add_argument(
        "--check",
        action="store_true",
        help="fetch nothing: report whether the bundles under --out are this checkout's",
    )
    local.add_argument(
        "--rebind",
        action="store_true",
        help="fetch nothing: rebind current bundles under --out to this checkout's declarations",
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
    if args.check or args.rebind:
        try:
            return check(stems, Path(args.out), rebind_current=args.rebind)
        except FeatureFaceError as exc:
            _telemetry.error(f"fetch-features: declarations do not bind: {exc}")
            return 1

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
            for stem in stems:
                check_binding(stem, staging)
                recipe = _features_provenance.recipe_files(stem)
                changed = changed_since(commit, list(recipe))
                findings = [
                    f"geometry input changed since {tag}: {name}"
                    for name in changed
                    if recipe[name] == "geometry"
                ]
                legacy = [
                    path.name
                    for path in export_features.exported_steps(stem, staging)
                    if not inventory_path(path).is_file()
                ]
                if legacy:
                    # Nothing here can rebind or validate it: always STALE.
                    findings += [
                        f"manifest input changed since {tag}: {name}"
                        for name in changed
                        if recipe[name] == "manifest"
                    ]
                    findings.append(
                        f"release {tag} predates face inventories (none for {', '.join(legacy)}): "
                        "cannot rebind or validate it offline; use a newer release"
                    )
                else:
                    if not findings:
                        rebind(stem, staging)
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
            if stale:
                _telemetry.error("fetch-features: nothing written")
                return 2
            for stem in stems:
                source = staging / "features" / stem
                target = Path(args.out) / "features" / stem
                shutil.rmtree(target, ignore_errors=True)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, target)
                _telemetry.info(
                    f"fetch-features: {stem}: {target} (current for this checkout, "
                    "features.toml rebound from this checkout)",
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


def check(stems: list[str], out: Path, *, rebind_current: bool = False) -> int:
    """``--check``: each bundle under ``out`` against this checkout, 2 if any
    is missing, does not bind its STEP or was built from other geometry.
    ``--rebind`` also rebinds each current one's ``features.toml`` from this
    checkout's declarations (after a ``requirement(...)`` edit), keeping its
    geometry inputs: in a scratch copy, the bundle's manifest replaced only
    once the copy binds and validates. A stale one is left as it is."""
    stale = 0
    for stem in stems:
        try:
            check_binding(stem, out)
            findings = _features_provenance.features_current(stem, out)
        except FetchError as exc:
            findings = [str(exc)]
        if findings:
            stale += 1
            _telemetry.warn(
                f"fetch-features: STALE {stem} ({out / 'features' / stem})\n"
                + "\n".join(f"  {finding}" for finding in findings),
                stem=stem,
            )
            continue
        how = ""
        if rebind_current:
            try:
                with tempfile.TemporaryDirectory(prefix="fetch-features-") as scratch:
                    staging = Path(scratch)
                    shutil.copytree(
                        out / "features" / stem, staging / "features" / stem
                    )
                    rebind(stem, staging)
                    validate_bundle(stem, staging)
                    manifest = export_features.bundle_paths(stem, out)[0]
                    partial = manifest.with_suffix(".toml.partial")
                    shutil.copyfile(
                        export_features.bundle_paths(stem, staging)[0], partial
                    )
                    partial.replace(manifest)
            except (FetchError, FeaturesBoundError) as exc:
                stale += 1
                _telemetry.warn(f"fetch-features: {stem}: {exc}", stem=stem)
                continue
            how = ", features.toml rebound from this checkout"
        _telemetry.info(
            f"fetch-features: {stem}: current for this checkout{how}", stem=stem
        )
    return 2 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
