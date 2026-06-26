r"""Tests for verify.py's freshness guard (no SolidWorks).

Run OUTSIDE the doit DAG, ``verify.py`` opens whatever ``.SLDASM`` is on disk with
no edge forcing a rebuild -- so an artefact whose sources moved scores SILENTLY
(a never-rebuilt pre-FootSeat ``frame`` passed every health gate and only tripped
component-count). ``_assert_fresh`` closes that gap by reusing doit's OWN ledger
(``cad/out/.doit.db``) + ``ContentChecker`` over each producer's CURRENT SOURCE
deps (build scripts/config), so a "stale" verdict means the sources moved without a
rebuild. Referenced ``.SLDPRT``/``.SLDASM`` artefacts are existence-checked only --
their bytes churn when a parent assembly re-saves nested docs (the parent-md5
cascade), which is build non-idempotency, not a source change. These tests exercise
the pure core SW-free::

    python cad/scripts/test_verify_freshness.py     # or: pytest cad/scripts/test_verify_freshness.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify  # noqa: E402

# Reuse doit's EXACT checker to build the stored states a real build would record.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root (dodo.py)
from dodo import ContentChecker  # noqa: E402


def _state(path: Path) -> list:
    """The [mtime, size, digest] triple doit's ContentChecker stores for a dep."""
    st = ContentChecker().get_state(str(path), None)  # current_state=None -> never None
    assert st is not None
    return list(st)


def _producer(tmp_path: Path, *, deps: list[Path], target_exists: bool = True):
    """A (task, current_deps, target) triple like ``_producers`` returns."""
    target = tmp_path / "widget.SLDPRT"
    if target_exists:
        target.write_text("artefact\n", encoding="utf-8")
    return ("part:widget", [str(d) for d in deps], str(target))


def test_current_tree_is_not_stale(tmp_path: Path) -> None:
    """A ledger whose recorded state matches disk (and target present) -> not stale."""
    dep = tmp_path / "build_widget.py"
    dep.write_text("A = 1\n", encoding="utf-8")
    prod = _producer(tmp_path, deps=[dep])
    db = {"part:widget": {"deps:": [str(dep)], str(dep): _state(dep)}}
    assert verify._stale_in_db(db, [prod]) == []


def test_changed_dep_is_flagged(tmp_path: Path) -> None:
    """A dep whose CONTENT moved since the recorded state is stale -- even when the
    recorded mtime is stale-but-present (the checkout/restore case)."""
    dep = tmp_path / "build_widget.py"
    dep.write_text("A = 1\n", encoding="utf-8")
    stored = [1.0, dep.stat().st_size, ContentChecker._digest(str(dep))]  # past mtime
    dep.write_text("A = 2  # geometry changed\n", encoding="utf-8")
    db = {"part:widget": {"deps:": [str(dep)], str(dep): stored}}
    stale = verify._stale_in_db(db, [_producer(tmp_path, deps=[dep])])
    assert stale and "build_widget.py changed" in stale[0]


def test_new_dep_absent_from_last_build_is_flagged(tmp_path: Path) -> None:
    """A dep present in the CURRENT graph but never recorded (added since the last
    build, e.g. a new hold-down part) is stale -- the Codex case that the original
    8-component frame hit, where lag-screw.SLDPRT was a new, unchecked dep."""
    old = tmp_path / "build_widget.py"
    old.write_text("A = 1\n", encoding="utf-8")
    new = tmp_path / "lag-screw.SLDPRT"
    new.write_text("body\n", encoding="utf-8")
    # Ledger only knows `old`; `new` is a current dep with no saved state.
    db = {"part:widget": {"deps:": [str(old)], str(old): _state(old)}}
    stale = verify._stale_in_db(db, [_producer(tmp_path, deps=[old, new])])
    assert stale and "new dep lag-screw.SLDPRT" in stale[0]


def test_missing_target_is_flagged(tmp_path: Path) -> None:
    """A producer whose output target vanished is stale even if every dep is current
    (doit rebuilds a task with a missing target) -- the other Codex case."""
    dep = tmp_path / "build_widget.py"
    dep.write_text("A = 1\n", encoding="utf-8")
    db = {"part:widget": {"deps:": [str(dep)], str(dep): _state(dep)}}
    prod = _producer(tmp_path, deps=[dep], target_exists=False)
    stale = verify._stale_in_db(db, [prod])
    assert stale and "target widget.SLDPRT missing" in stale[0]


def test_never_built_task_is_flagged(tmp_path: Path) -> None:
    """A producer task with no ledger entry has never been built through doit."""
    stale = verify._stale_in_db({}, [_producer(tmp_path, deps=[])])
    assert stale == ["part:widget (never built through doit)"]


def test_missing_dep_file_is_flagged(tmp_path: Path) -> None:
    """A current dep that no longer exists on disk is stale."""
    gone = tmp_path / "deleted.py"
    db = {"part:widget": {"deps:": [str(gone)], str(gone): [1.0, 1, "x"]}}
    stale = verify._stale_in_db(db, [_producer(tmp_path, deps=[gone])])
    assert stale and "missing dep deleted.py" in stale[0]


def test_artefact_dep_byte_churn_is_not_flagged(tmp_path: Path) -> None:
    """A referenced .SLDPRT/.SLDASM under cad/out whose BYTES changed is NOT staleness.
    SolidWorks re-saves every nested document when a parent assembly is fully rebuilt
    (the parent-md5 cascade) -- a re-insert/re-mate grows each child .SLDPRT even though
    the geometry is identical -- so content-checking it would fail every full build. Its
    real freshness is covered transitively via its own producer's SOURCE check."""
    import dodo

    art = tmp_path / "harmonic-base.SLDPRT"
    art.write_text("v1\n", encoding="utf-8")
    stored = _state(art)
    art.write_text("v2 -- re-saved in-context by a parent assembly, +446 bytes\n",
                   encoding="utf-8")
    db = {"part:widget": {"deps:": [str(art)], str(art): stored}}
    old = dodo.CAD_OUT
    dodo.CAD_OUT = tmp_path  # classify `art` as a build artefact (under cad/out)
    try:
        assert verify._stale_in_db(db, [_producer(tmp_path, deps=[art])]) == []
    finally:
        dodo.CAD_OUT = old


def test_artefact_dep_missing_is_still_flagged(tmp_path: Path) -> None:
    """Artefact deps skip CONTENT, not EXISTENCE: a referenced part missing from disk
    is a genuine break (the assembly points at something that isn't there)."""
    import dodo

    art = tmp_path / "harmonic-base.SLDPRT"  # never created -> missing
    db = {"part:widget": {"deps:": [str(art)], str(art): [1.0, 1, "x"]}}
    old = dodo.CAD_OUT
    dodo.CAD_OUT = tmp_path
    try:
        stale = verify._stale_in_db(db, [_producer(tmp_path, deps=[art])])
    finally:
        dodo.CAD_OUT = old
    assert stale and "missing dep harmonic-base.SLDPRT" in stale[0]


def test_producers_walk_refs_and_include_current_deps() -> None:
    """frame -> its parts; the top assembly -> sub-assemblies AND their parts. Deps are
    the CURRENT graph: frame must list lag-screw.SLDPRT (added with the hold-downs)."""
    frame = {t: (deps, tgt) for t, deps, tgt in verify._producers("frame")}
    assert "assembly:frame" in frame
    assert "part:rocker_arm_support" in frame and "part:harmonic_base" in frame
    frame_deps = [Path(d).name for d in frame["assembly:frame"][0]]
    assert "lag-screw.SLDPRT" in frame_deps  # the dep the old recorded-only loop missed

    top = {t for t, _, _ in verify._producers("harmonic-analyzer")}
    assert "assembly:harmonic_analyzer" in top
    assert any(t.startswith("assembly:") and t != "assembly:harmonic_analyzer" for t in top)
    assert any(t.startswith("part:") for t in top)  # recursed into a sub-assembly's parts


if __name__ == "__main__":
    import tempfile

    fs_tests = (
        test_current_tree_is_not_stale,
        test_changed_dep_is_flagged,
        test_new_dep_absent_from_last_build_is_flagged,
        test_missing_target_is_flagged,
        test_never_built_task_is_flagged,
        test_missing_dep_file_is_flagged,
        test_artefact_dep_byte_churn_is_not_flagged,
        test_artefact_dep_missing_is_still_flagged,
    )
    for fn in fs_tests:
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
    test_producers_walk_refs_and_include_current_deps()
    print("test_verify_freshness: all passed")
