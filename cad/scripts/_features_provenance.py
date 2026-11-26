"""Whether a feature bundle's STEP was built from this checkout's geometry (#3668).

``features.toml`` binds its STEP's bytes (``step_sha256``), which proves the
bundle is self-consistent, not that it matches this tree: a bundle copied from
another worktree, or left behind by an older checkout, rendered travelers and
NC with old sizes and exit 0. So the bundle also records its geometry inputs:

``[geometry_inputs]`` maps each repo-relative ``geometry`` input of
:func:`recipe_files` (``part:<stem>`` and the labelled-STEP export code) to
its content digest as doit keys it (``dodo.ContentChecker``: a ``.py`` file's
syntax tree, a YAML file's parsed data, other text with Git's line endings).
A comment or docstring edit is not a geometry change; anything that would
rebuild the STEP is.

:func:`stamp` appends the table after ``export_features.write_manifest`` (in
``package:manifest:<stem>`` and in ``fetch_features``' rebind), from the tree
doing the binding: there the STEP is the one doit keyed on those same inputs.
:func:`features_current` recomputes the digests from this checkout and names
every input that differs. ``cam_nc.py``, ``prechips_traveler.py`` and
``fetch_features.py --check`` refuse (exit 2) a bundle that has no table or
does not match. There is no override: a stale bundle is rebuilt
(``package:features:<stem>`` on the farm when geometry changed, else
``package:manifest:<stem>``) or fetched current (``fetch_features.py``).

The commit the STEP was built from is not recorded: ``features.toml`` is an
input of every ``cam:*`` and ``prechips:*`` key, and a commit id would give
identical bundles bound in two checkouts different keys.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

import export_features

REPO = export_features.REPO
TABLE = "geometry_inputs"


class StaleBundle(ValueError):
    """A feature bundle this checkout's geometry has moved past, or one that
    does not say what it was built from."""


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


def geometry_inputs(stem: str) -> dict[str, str]:
    """Each ``geometry`` input of :func:`recipe_files` and its doit content
    digest, read from this checkout."""
    import dodo  # noqa: PLC0415 - recipe_files put the repo on the path

    return {
        name: dodo.ContentChecker._digest(str(REPO / name))
        for name, label in recipe_files(stem).items()
        if label == "geometry"
    }


def stamp(stem: str, out: Path) -> None:
    """Append ``[geometry_inputs]`` to ``stem``'s freshly written
    ``features.toml`` under ``out``."""
    path = export_features.bundle_paths(stem, out)[0]
    text = path.read_text(encoding="utf-8")
    if TABLE in tomllib.loads(text):
        raise StaleBundle(
            f"{path} already records {TABLE}: stamp only a freshly bound manifest"
        )
    lines = ["", f"[{TABLE}]"]
    lines += [
        f"{json.dumps(name)} = {json.dumps(digest)}"
        for name, digest in geometry_inputs(stem).items()
    ]
    partial = path.with_suffix(".toml.partial")
    partial.write_text(text + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    partial.replace(path)


def features_current(stem: str, out: Path) -> list[str]:
    """What makes ``stem``'s bundle under ``out`` not this checkout's: no
    bundle, no ``[geometry_inputs]``, or each input whose digest differs,
    appeared or went. Empty when the bundle is current."""
    path = export_features.bundle_paths(stem, out)[0]
    if not path.is_file():
        return [f"no bundle at {path}"]
    recorded = tomllib.loads(path.read_text(encoding="utf-8")).get(TABLE)
    if not isinstance(recorded, dict):
        return [f"{path} records no {TABLE}: bound before #3668 or by hand"]
    current = geometry_inputs(stem)
    findings = [
        f"geometry input changed since the bundle was built: {name}"
        for name in sorted(set(recorded) & set(current))
        if recorded[name] != current[name]
    ]
    findings += [
        f"new geometry input: {name}" for name in sorted(set(current) - set(recorded))
    ]
    findings += [
        f"no longer a geometry input: {name}"
        for name in sorted(set(recorded) - set(current))
    ]
    return findings


def require_current(stems: list[str], out: Path) -> None:
    """Raise :class:`StaleBundle` naming every part of ``stems`` whose bundle
    under ``out`` is not current, with what to run."""
    stale = {stem: found for stem in stems if (found := features_current(stem, out))}
    if stale:
        raise StaleBundle(
            "feature bundle not built from this checkout:\n"
            + "\n".join(
                f"  {stem}: {finding}"
                for stem, found in stale.items()
                for finding in found
            )
            + "\n  rebuild package:manifest:<part> (package:features:<part> on the farm when geometry changed)"
            f" or run fetch_features.py {' '.join(stale)}"
        )
