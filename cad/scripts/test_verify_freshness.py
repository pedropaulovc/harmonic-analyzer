r"""Tests for verify.py's freshness guard (no SolidWorks).

Run OUTSIDE the doit DAG, ``verify.py`` opens whatever ``.SLDASM`` is on disk with
no edge forcing a rebuild -- so an artefact whose sources moved scores SILENTLY
(a never-rebuilt pre-FootSeat ``frame`` passed every health gate and only tripped
component-count). ``_assert_fresh`` closes that gap by reusing doit's OWN ledger
(``cad/out/.doit.db``) + ``ContentChecker``, so a "stale" verdict here is exactly
what ``doit`` would rebuild. These tests exercise the pure core SW-free::

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


def test_current_tree_is_not_stale(tmp_path: Path) -> None:
    """A db whose recorded state matches disk yields no staleness."""
    dep = tmp_path / "build_widget.py"
    dep.write_text("A = 1\n", encoding="utf-8")
    db = {"part:widget": {"deps:": [str(dep)], str(dep): _state(dep)}}
    assert verify._stale_in_db(db, ["part:widget"]) == []


def test_changed_dep_is_flagged(tmp_path: Path) -> None:
    """A dep whose CONTENT moved since the recorded state is stale -- even when the
    recorded mtime is stale-but-present (the checkout/restore case)."""
    dep = tmp_path / "build_widget.py"
    dep.write_text("A = 1\n", encoding="utf-8")
    size = dep.stat().st_size
    # Recorded state: a past timestamp + the OLD content digest. Current file differs.
    stored = [1.0, size, ContentChecker._digest(str(dep))]
    dep.write_text("A = 2  # geometry changed\n", encoding="utf-8")
    db = {"part:widget": {"deps:": [str(dep)], str(dep): stored}}
    stale = verify._stale_in_db(db, ["part:widget"])
    assert stale and "build_widget.py changed" in stale[0]


def test_never_built_task_is_flagged() -> None:
    """A producer task with no ledger entry has never been built through doit."""
    stale = verify._stale_in_db({}, ["part:spring_hook"])
    assert stale == ["part:spring_hook (never built through doit)"]


def test_missing_dep_file_is_flagged(tmp_path: Path) -> None:
    """A recorded dep that no longer exists on disk is stale."""
    gone = tmp_path / "deleted.py"
    db = {"part:widget": {"deps:": [str(gone)], str(gone): [1.0, 1, "x"]}}
    stale = verify._stale_in_db(db, ["part:widget"])
    assert stale and "missing dep deleted.py" in stale[0]


def test_producer_tasks_walks_refs_transitively() -> None:
    """frame -> its parts; the top assembly -> its sub-assemblies AND their parts."""
    frame = verify._producer_tasks("frame")
    assert frame[0] == "assembly:frame"
    assert "part:rocker_arm_support" in frame and "part:harmonic_base" in frame

    top = verify._producer_tasks("harmonic-analyzer")
    assert "assembly:harmonic_analyzer" in top
    assert any(t.startswith("assembly:") and t != "assembly:harmonic_analyzer" for t in top)
    assert any(t.startswith("part:") for t in top)  # recursed into a sub-assembly's parts


if __name__ == "__main__":
    import tempfile

    for fn in (
        test_current_tree_is_not_stale,
        test_changed_dep_is_flagged,
        test_missing_dep_file_is_flagged,
    ):
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
    test_never_built_task_is_flagged()
    test_producer_tasks_walks_refs_transitively()
    print("test_verify_freshness: all passed")
