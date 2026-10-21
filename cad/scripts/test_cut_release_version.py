"""Offline regression tests for compact release numbering and Pillow APIs."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import tomllib
import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject

import cut_release
import trim_renders


def test_release_refuses_an_incomplete_or_stale_comparison_gallery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `gallery` task owns the showcase and fails loud, so staging must too:
    a missing overlay, or a gallery older than the geometry it claims to show,
    would publish a dishonest release."""
    comparisons = tmp_path / "comparisons"
    for name in ("render", "composite", "ref"):
        (comparisons / name).mkdir(parents=True)
    (comparisons / "manifest.json").write_text(
        json.dumps({"pairs": [{"id": "ch30"}]}), encoding="utf-8"
    )
    (comparisons / "scores.json").write_text(json.dumps({"ch30": 1.5}), "utf-8")
    (comparisons / "index.html").write_bytes(b"gallery")
    (comparisons / "ATTRIBUTION.md").write_bytes(b"credits")
    for relative in (
        "render/ch30.jpg",
        "composite/ch30_cad.jpg",
        "composite/ch30_blend.jpg",
        "ref/ch30.jpg",
    ):
        (comparisons / relative).write_bytes(b"jpg")
    scene = tmp_path / "harmonic-analyzer.json"
    scene.write_text("{}", encoding="utf-8")
    older = time.time() - 600
    os.utime(scene, (older, older))
    os.utime(comparisons / "manifest.json", (older, older))
    monkeypatch.setattr(cut_release, "COMPARISONS_DIR", comparisons)
    monkeypatch.setattr(cut_release, "SCENE_JSON", scene)

    stage = tmp_path / "stage"
    stage.mkdir()
    facts = cut_release.stage_comparisons(stage)
    assert facts["pairs"] == 1
    assert facts["mean_score"] == 1.5
    assert (stage / "comparisons" / "index.html").is_file()

    os.utime(comparisons / "scores.json", (older - 60, older - 60))
    with pytest.raises(SystemExit, match="doit gallery"):
        cut_release.stage_comparisons(stage)

    os.utime(comparisons / "scores.json", None)
    (comparisons / "composite" / "ch30_blend.jpg").unlink()
    with pytest.raises(SystemExit, match="doit gallery"):
        cut_release.stage_comparisons(stage)


def _tags(monkeypatch: pytest.MonkeyPatch, *tags: str) -> None:
    monkeypatch.setattr(cut_release, "_git", lambda *_args, **_kwargs: "\n".join(tags))


def test_existing_tags_ignores_legacy_semver(monkeypatch: pytest.MonkeyPatch) -> None:
    _tags(monkeypatch, "v0.20.0", "v9", "v21", "v01", "not-a-release")

    assert cut_release._existing_tags() == [9, 21]


def test_default_version_increments_latest_compact_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tags(monkeypatch, "v0.20.0", "v9", "v21")

    assert cut_release.resolve_version(None) == "v22"


def test_default_version_starts_at_v1_without_compact_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tags(monkeypatch, "v0.20.0", "v1.2.3")

    assert cut_release.resolve_version(None) == "v1"


def test_release_requires_configured_cad_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")

    cut_release.require_configured_revision("v22")
    with pytest.raises(SystemExit, match="does not match configured CAD Revision"):
        cut_release.require_configured_revision("v23")


@pytest.mark.parametrize("no_publish", [False, True])
@pytest.mark.parametrize(
    "detail",
    [
        "plan drawing.revision 'v21' does not match feature manifest drawing.revision 'v22'",
        "plan drawing.revision 'v21' does not match configured revision 'v22'",
    ],
)
def test_release_revision_mismatch_fails_before_staging_or_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    no_publish: bool, detail: str,
) -> None:
    """Preflight preserves the binder's diagnostic, including during dry runs."""
    stems = ("ch_rocker_arm", "ch_pivot_shaft")
    calls: list[tuple[str, Path, str]] = []
    cad = tmp_path / "cad"
    monkeypatch.setattr(cut_release, "CAD_ROOT", cad)
    monkeypatch.setattr(cut_release, "RELEASE_DIR", tmp_path / "release")
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
    monkeypatch.setattr(cut_release._process_plans, "MIGRATED_PLANS", ())
    monkeypatch.setattr(cut_release._process_plans, "TRAVELER_STEMS", stems)

    def check_plan_revision(stem: str, out: Path, *, revision: str) -> None:
        # The core helper's own tests exercise real synthetic plan/manifest bytes.
        # Here its error proves release ordering and forwarding of both inputs.
        calls.append((stem, out, revision))
        if stem == stems[-1]:
            raise cut_release._process_plans.PlanBindError(detail, line=9)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("revision mismatch reached release side effects")

    monkeypatch.setattr(
        cut_release._process_plans, "check_plan_revision", check_plan_revision,
    )
    monkeypatch.setattr(
        cut_release, "_start_release_log",
        lambda _version: (tmp_path / "release.log", lambda: None),
    )
    for name in (
        "_git", "_gh", "previous_tag", "bundle", "publish",
        "prepare_configured_revision_advance", "report_no_publish",
    ):
        monkeypatch.setattr(cut_release, name, forbidden)
    monkeypatch.setattr(trim_renders, "regenerate_readme_images", forbidden)
    argv = ["cut_release.py", "v22"]
    if no_publish:
        argv.append("--no-publish")
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as failure:
        cut_release.main()

    assert str(failure.value) == f"!!  process plan {stems[-1]}: line 9: {detail}"
    assert calls == [(stem, cad / "out", "v22") for stem in stems]


def test_release_refuses_placeholder_measurements_before_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preflight names every bound #1413 placeholder; a dry run refuses too."""
    plans = cut_release._process_plans
    measured = (
        '{ status = "measured", by = "' + plans.PLACEHOLDER_BY + '", '
        'date = "2026-10-12", instrument = "height gauge" }'
    )
    shop = tmp_path / "process" / "shop"
    shop.mkdir(parents=True)
    for name in plans.SHOP_FILES:
        (shop / name).write_text("version = 1\n", encoding="utf-8")
    (shop / "inventory.toml").write_text(
        f"[fixtures.test]\nheight_mm = {{ value = 18.5, measured = {measured} }}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(plans, "PROCESS_ROOT", shop.parent)
    monkeypatch.setattr(cut_release, "CAD_ROOT", tmp_path / "cad")
    monkeypatch.setattr(cut_release, "RELEASE_DIR", tmp_path / "release")
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
    monkeypatch.setattr(plans, "MIGRATED_PLANS", ())
    monkeypatch.setattr(plans, "TRAVELER_STEMS", ("ch_rocker_arm",))
    monkeypatch.setattr(plans, "check_plan_revision", lambda *_a, **_k: None)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("placeholder measurements reached release side effects")

    monkeypatch.setattr(
        cut_release,
        "_start_release_log",
        lambda _version: (tmp_path / "release.log", lambda: None),
    )
    for name in (
        "_git",
        "_gh",
        "previous_tag",
        "bundle",
        "publish",
        "prepare_configured_revision_advance",
        "report_no_publish",
    ):
        monkeypatch.setattr(cut_release, name, forbidden)
    monkeypatch.setattr(trim_renders, "regenerate_readme_images", forbidden)
    monkeypatch.setattr(sys, "argv", ["cut_release.py", "v22", "--no-publish"])

    with pytest.raises(SystemExit) as failure:
        cut_release.main()

    message = str(failure.value)
    assert message.startswith("!!  release refused: 1 placeholder values")
    assert plans.PLACEHOLDER_ISSUE in message
    assert message.endswith("\ninventory.toml:fixtures.test.height_mm.measured.by")


@pytest.fixture
def revision_plans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, ...]:
    """Synthetic migrated-held and enrolled plans; never mutate tracked sources."""
    stems = ("ch_rocker_arm", "ch_pivot_shaft")
    plans = {}
    for stem, quote in zip(stems, ('"', "'"), strict=True):
        plan = tmp_path / "process" / stem / "plan.toml"
        plan.parent.mkdir(parents=True)
        plan.write_bytes(
            (
                '# preserve v22 in prose\r\n[other]\r\nrevision = "v7"\r\n'
                f"[drawing] # title block\r\n  revision = {quote}v22{quote} # reserved\r\n"
                '[stock]\r\nrevision = "v9"\r\n'
            ).encode("utf-8")
        )
        plans[stem] = plan
    monkeypatch.setattr(cut_release._process_plans, "MIGRATED_PLANS", stems[:1])
    monkeypatch.setattr(cut_release._process_plans, "TRAVELER_STEMS", stems[1:])
    monkeypatch.setattr(cut_release._process_plans, "PROCESS_ROOT", tmp_path / "process")
    return tuple(plans.values())


def test_published_release_advances_tracked_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    revision_plans: tuple[Path, ...],
) -> None:
    source = tmp_path / "release.yaml"
    source.write_text("next_revision: v22\n", encoding="utf-8")
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
    originals = {plan: plan.read_bytes() for plan in revision_plans}
    historical = tmp_path / "process" / "synthetic_historical" / "plan.toml"
    historical.parent.mkdir(parents=True)
    historical_bytes = b'# provenance only\n[drawing]\nrevision = "v7"\n'
    historical.write_bytes(historical_bytes)

    assert cut_release.advance_configured_revision("v22") == "v23"
    assert source.read_text(encoding="utf-8") == "next_revision: v23\n"
    for plan, original in originals.items():
        assert plan.read_bytes() == original.replace(
            b'revision = "v22"', b'revision = "v23"'
        ).replace(b"revision = 'v22'", b"revision = 'v23'")
    assert historical.read_bytes() == historical_bytes


def test_revision_advance_is_staged_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    revision_plans: tuple[Path, ...],
) -> None:
    source = tmp_path / "release.yaml"
    source.write_bytes(b"next_revision: v22\n")
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
    originals = {plan: plan.read_bytes() for plan in revision_plans}
    # An enrolled migrated participant must not be prepared or installed twice.
    monkeypatch.setattr(
        cut_release._process_plans, "TRAVELER_STEMS",
        tuple(plan.parent.name for plan in (*revision_plans[::-1], revision_plans[-1])),
    )

    prepared = cut_release.prepare_configured_revision_advance("v22")
    try:
        assert prepared.next_version == "v23"
        assert [path for path, _ in prepared.updates] == [
            source, *revision_plans
        ]
        assert all(temporary.exists() for _, temporary in prepared.updates)
        assert source.read_bytes() == b"next_revision: v22\n"
        assert all(plan.read_bytes() == original for plan, original in originals.items())
        assert prepared.commit() == "v23"
    finally:
        prepared.discard()

    assert source.read_text(encoding="utf-8") == "next_revision: v23\n"
    for plan, original in originals.items():
        assert plan.read_bytes() == original.replace(
            b'revision = "v22"', b'revision = "v23"'
        ).replace(b"revision = 'v22'", b"revision = 'v23'")
    assert all(not temporary.exists() for _, temporary in prepared.updates)


@pytest.mark.parametrize("participant", [0, 1])
@pytest.mark.parametrize(
    "drawing",
    [
        '[drawing]\nname = "missing revision"\n',
        '[drawing]\nrevision = "v22"\nrevision = "v22"\n',
        '[drawing]\nrevision = "v22"\nrevision = "v21"\n',
        '[drawing]\nrevision = "v21"\n',
        '[other]\nrevision = "v22"\n',
        '[drawing]\nrevision = "v22"\n[drawing]\nrevision = "v22"\n',
    ],
)
def test_invalid_participant_revision_discards_every_prepared_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    revision_plans: tuple[Path, ...], drawing: str, participant: int,
) -> None:
    source = tmp_path / "release.yaml"
    source.write_bytes(b"next_revision: v22\n")
    revision_plans[participant].write_text(drawing, encoding="utf-8")
    originals = {
        path: path.read_bytes() for path in (source, *revision_plans)
    }
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")

    with pytest.raises(RuntimeError, match=r"\[drawing\]"):
        cut_release.prepare_configured_revision_advance("v22")

    for path, original in originals.items():
        assert path.read_bytes() == original
        assert not tuple(path.parent.glob(f".{path.name}.*.tmp"))


def test_revision_prepare_io_failure_discards_all_temps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    revision_plans: tuple[Path, ...],
) -> None:
    source = tmp_path / "release.yaml"
    source.write_bytes(b"next_revision: v22\n")
    originals = {
        path: path.read_bytes() for path in (source, *revision_plans)
    }
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
    flushes = 0
    fsync = os.fsync

    def refuse_last_fsync(descriptor: int) -> None:
        nonlocal flushes
        flushes += 1
        if flushes == len(originals):
            raise OSError("cannot flush last plan")
        fsync(descriptor)

    monkeypatch.setattr(os, "fsync", refuse_last_fsync)
    with pytest.raises(RuntimeError, match="could not prepare revision update"):
        cut_release.prepare_configured_revision_advance("v22")

    for path, original in originals.items():
        assert path.read_bytes() == original
        assert not tuple(path.parent.glob(f".{path.name}.*.tmp"))


def test_revision_install_reports_ordered_partial_install_and_discards_temps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    revision_plans: tuple[Path, ...],
) -> None:
    source = tmp_path / "release.yaml"
    source.write_bytes(b"next_revision: v22\n")
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
    prepared = cut_release.prepare_configured_revision_advance("v22")
    replace = os.replace
    installed = []

    def refuse_second_plan(temporary: Path, destination: Path) -> None:
        if destination == revision_plans[-1]:
            raise PermissionError("plan is read-only")
        replace(temporary, destination)
        installed.append(destination)

    monkeypatch.setattr(os, "replace", refuse_second_plan)
    try:
        with pytest.raises(RuntimeError, match="partial revision install") as failure:
            prepared.commit()
        assert installed == [source, revision_plans[0]]
        assert str(source) in str(failure.value)
        assert str(revision_plans[0]) in str(failure.value)
        assert str(revision_plans[1]) in str(failure.value)
        assert source.read_bytes() == b"next_revision: v23\n"
        assert (
            tomllib.loads(revision_plans[0].read_text())["drawing"]["revision"]
            == "v23"
        )
        assert (
            tomllib.loads(revision_plans[1].read_text())["drawing"]["revision"]
            == "v22"
        )
    finally:
        prepared.discard()
    assert all(not temporary.exists() for _, temporary in prepared.updates)


def test_empty_revision_scope_advances_only_release_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "release.yaml"
    source.write_bytes(b"next_revision: v22\r\n# unchanged\r\n")
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
    monkeypatch.setattr(cut_release._process_plans, "MIGRATED_PLANS", ())
    monkeypatch.setattr(cut_release._process_plans, "TRAVELER_STEMS", ())
    monkeypatch.setattr(
        cut_release._process_plans, "plan_path",
        lambda _stem: pytest.fail("empty revision scope opened a plan"),
    )

    assert cut_release.advance_configured_revision("v22") == "v23"
    assert source.read_bytes() == b"next_revision: v23\r\n# unchanged\r\n"


def test_empty_enrollment_still_advances_migrated_held_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    revision_plans: tuple[Path, ...],
) -> None:
    source = tmp_path / "release.yaml"
    source.write_bytes(b"next_revision: v22\n")
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
    monkeypatch.setattr(cut_release._process_plans, "TRAVELER_STEMS", ())
    held, unenrolled = revision_plans
    original_unenrolled = unenrolled.read_bytes()

    assert cut_release.advance_configured_revision("v22") == "v23"
    assert tomllib.loads(held.read_text())["drawing"]["revision"] == "v23"
    assert unenrolled.read_bytes() == original_unenrolled
    assert cut_release._process_plans.TRAVELER_STEMS == ()


@pytest.fixture
def revision_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    revision_plans: tuple[Path, ...],
) -> tuple[tuple[Path, ...], Path]:
    """Exercise real revision validation without COM or a qualified held export."""
    plans = cut_release._process_plans
    cad = tmp_path / "cad"
    native = cad / "out" / "sldasm"
    native.mkdir(parents=True)
    (native / f"{cut_release.TOP_ASSEMBLY}.SLDASM").write_bytes(b"synthetic native")
    scene = cad / "out" / "scene.json"
    scene.write_text('{"unit":"mm"}', encoding="utf-8")
    manifest, _step = plans.bundle_paths(revision_plans[1].parent.name, cad / "out")
    manifest.parent.mkdir(parents=True)
    manifest.write_text('[drawing]\nrevision = "v22"\n', encoding="utf-8")
    monkeypatch.setattr(cut_release, "CAD_ROOT", cad)
    monkeypatch.setattr(cut_release, "OUT_SLDASM", native)
    monkeypatch.setattr(cut_release, "SCENE_JSON", scene)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
    monkeypatch.setattr(cut_release, "_git", lambda *_a, **_k: "")
    monkeypatch.setattr(plans, "shop_placeholders", lambda: ())
    return revision_plans, manifest


@pytest.mark.parametrize("held_export", ["absent", "stale", "malformed"])
def test_preflight_checks_held_freshness_without_requiring_exports(
    revision_preflight, held_export: str
) -> None:
    sources, _manifest = revision_preflight
    plans = cut_release._process_plans
    held_manifest, _step = plans.bundle_paths(
        sources[0].parent.name, cut_release.CAD_ROOT / "out"
    )
    if held_export != "absent":
        held_manifest.parent.mkdir(parents=True)
        held_manifest.write_text(
            '[drawing]\nrevision = "v7"\n' if held_export == "stale" else "not TOML [",
            encoding="utf-8",
        )

    cut_release.preflight("v22", allow_dirty=False)
    assert plans.TRAVELER_STEMS == (sources[1].parent.name,)


def test_preflight_rejects_stale_held_revision_before_release_work(
    revision_preflight, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources, _manifest = revision_preflight
    sources[0].write_bytes(
        sources[0].read_bytes().replace(b'revision = "v22"', b'revision = "v21"')
    )

    def forbidden(*_a, **_k):
        pytest.fail("held revision mismatch reached release work")

    monkeypatch.setattr(cut_release, "_git", forbidden)
    with pytest.raises(
        SystemExit,
        match="process plan ch_rocker_arm: line 5:.*configured revision 'v22'",
    ):
        cut_release.preflight("v22", allow_dirty=False)


@pytest.mark.parametrize(
    ("authored", "exported"),
    [("v21", "v22"), ("v22", "v21"), ("v21", "v21"), ("v22", None)],
)
def test_preflight_keeps_enrolled_revision_validation_strict(
    revision_preflight, monkeypatch: pytest.MonkeyPatch,
    authored: str, exported: str | None,
) -> None:
    sources, manifest = revision_preflight
    plans = cut_release._process_plans
    # Enrollment keeps manifest validation even if the stem is also migrated.
    monkeypatch.setattr(plans, "MIGRATED_PLANS", tuple(p.parent.name for p in sources))
    sources[1].write_text(f'[drawing]\nrevision = "{authored}"\n', encoding="utf-8")
    if exported is None:
        manifest.unlink()
    else:
        manifest.write_text(f'[drawing]\nrevision = "{exported}"\n', encoding="utf-8")

    with pytest.raises(SystemExit, match="process plan ch_pivot_shaft:"):
        cut_release.preflight("v22", allow_dirty=False)


def test_explicit_compact_version_is_accepted() -> None:
    assert cut_release.resolve_version("v42") == "v42"


@pytest.mark.parametrize("version", ["v0", "v01", "v1.0.0", "22", "v-1"])
def test_invalid_explicit_versions_are_rejected(version: str) -> None:
    with pytest.raises(SystemExit, match="version must look like vNN"):
        cut_release.resolve_version(version)


def test_previous_tag_uses_compact_release_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tags(monkeypatch, "v0.20.0", "v9", "v21", "v25")

    assert cut_release.previous_tag("v22") == "v21"
    assert cut_release.previous_tag("v9") is None




@pytest.fixture
def readout_report(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    """A deterministic readout input without the report's Monte Carlo layer.

    The release tests exercise the real procedure renderer and bundle staging;
    error-budget tests own the report's numerical correctness.
    """
    import error_budget

    budget = error_budget.load_budget()
    nom = error_budget.nominal()
    capacity = 4.7
    pen_per_bar_at_min = nom.pen_half / capacity
    null_station_mm = -0.5
    report = {
        "nominal": nom.__dict__,
        "closed_form": {
            "mg-magnifier": {
                "ordinate_capacity_full_scale_bars": capacity,
                "lever_radius_min_mm": nom.lever_r_min,
                "lever_radius_built_mm": nom.lever_r_built,
                "wheel_ratio": nom.wheel_ratio,
                "pen_mm_per_full_scale_bar_at_min": pen_per_bar_at_min,
                "pen_mm_per_full_scale_bar_at_built": (
                    pen_per_bar_at_min
                    * error_budget.wire_moment_arm(nom, nom.lever_r_built)
                    / error_budget.wire_moment_arm(nom, nom.lever_r_min)
                ),
            },
            "readout": {
                "pen_half_stroke_mm": nom.pen_half,
                "assumed_reading_uncertainty_mm": float(
                    budget["reserved"]["readout"]["reading_uncertainty_mm"]
                ),
            },
        },
        "null_lift_ordinate": -null_station_mm / nom.d_max,
        "null_station_mm": null_station_mm,
        "station_setting_tolerance_mm": float(
            budget["critical_features"]["station_setting"]["tolerance"]
        ),
        "cam_home_phase": {"deg": nom.cam_home_deg},
        "cam_home_phase_waived": False,
        "closure": {"nominal_residual_mae": 0.01},
    }
    monkeypatch.setattr(error_budget, "build_report", lambda: report)
    return report


def test_staged_readout_procedure_references_resolve_inside_the_bundle(
    tmp_path, readout_report
):
    """READOUT.md sends the reader to the operating explanation; a release
    consumer has only the bundle, so that page -- and the pages IT cross-links
    with ./ -- must be staged beside it, every ./ link among them must resolve
    within the stage, and every link that points OUT of the bundle must be
    rewritten to something the reader can follow: a blob URL at the release
    tag for a tracked repo file, plain text naming the path for the
    non-redistributable references submodule. A relative link surviving into
    the zip would be dead on arrival."""
    import re
    from urllib.parse import unquote, urlsplit

    staged = cut_release.stage_readout_procedure(tmp_path, "v42")
    assert {"READOUT.md", "NOTICE.md", "LICENSE", "docs/device-operation.md"} <= set(staged)
    for rel in staged:
        assert (tmp_path / rel).is_file(), rel
    readout = (tmp_path / "READOUT.md").read_text(encoding="utf-8")
    readout_references = set(re.findall(r"`(docs/[^`]+\.md)`", readout))
    assert "docs/device-operation.md" in readout_references
    for target in readout_references:
        assert (tmp_path / target).is_file(), f"READOUT.md -> {target}"
    docs = cut_release.operating_docs()
    links = re.compile(r"\]\(([^)\s]+)[^)]*\)")
    repository_targets = set()
    for name in docs:
        page = (tmp_path / "docs" / name).read_text(encoding="utf-8")
        for target in links.findall(page):
            url = urlsplit(target)
            if url.scheme in {"https", "http", "mailto"} or target.startswith("#"):
                if url.netloc == "github.com" and "/blob/" in url.path:
                    provenance = re.fullmatch(r"/[^/]+/[^/]+/blob/v42/(.+)", url.path)
                    assert provenance is not None, f"{name} -> {target} lost its release tag"
                    source = unquote(provenance[1])
                    assert not source.startswith("references/"), target
                    assert (cut_release.REPO_ROOT / source).is_file(), target
                    repository_targets.add(source)
                continue
            assert target.startswith("./"), f"{name} -> {target} escapes the bundle"
            assert (tmp_path / "docs" / unquote(url.path)).is_file(), (
                f"{name} -> {target}"
            )
    assert "cad/config/error_budget.yaml" in repository_targets
    # Third-party scans keep their source paths, without dead submodule blob links.
    paper = (tmp_path / "docs" / "michelson-1898-trial-accuracy.md").read_text(
        encoding="utf-8"
    )
    sources = re.findall(r"`(references/[^`]+)`", paper)
    assert "references/albert-michelsons-harmonic-analyzer/28_Michelsons_1898_Paper.pdf" in sources


def test_staged_docs_reject_a_link_the_bundle_cannot_serve():
    """The rewrite is a GATE, not a best effort: a ./ link to an unstaged page,
    or a repo path that is not tracked at the tag, must fail the release."""
    with pytest.raises(RuntimeError, match="not staged"):
        cut_release.portable_links("[x](./gone.md)", "d.md", "v42", {"d.md"})
    with pytest.raises(RuntimeError, match="not tracked"):
        cut_release.portable_links(
            "[x](../config/no-such.yaml)", "d.md", "v42", {"d.md"}
        )
    # an UNTRACKED page is absent from the tag the provenance manifest pins
    # (preflight reads the tree with --untracked-files=no), so staging it would
    # publish documentation the release claims is not there
    with pytest.raises(RuntimeError, match="not tracked"):
        cut_release.require_tracked("cad/docs/not-a-page.md", "closure")
    cut_release.require_tracked("cad/docs/device-operation.md", "closure")


@pytest.mark.parametrize(
    "travelers",
    [[], ["travelers/ch_rocker_arm", "travelers/ch_pivot_shaft"]],
)
def test_release_notes_report_native_count_and_enrolled_travelers(
    travelers: list[str],
) -> None:
    """The native Pack-and-Go count and the neutral export inventory are two
    different numbers. They shared the ``documents`` key, so
    ``stage_release_neutral``'s inventory silently overwrote the COM-derived
    count and the notes advertised the wrong one (CodeRabbit, PR #770)."""
    facts = {
        "native_documents": 137,
        "documents": 99,
        "sw_revision": "35",
        "parts": 99,
        "assemblies": 8,
        "config_meshes": 22,
        "pngs": 107,
        "comparisons": {"pairs": 3, "mean_score": None},
        "size_mb": 42.0,
        "travelers": travelers,
    }

    notes = cut_release.release_notes("v42", facts)

    assert "native Pack-and-Go (137 referenced documents" in notes
    assert "99 referenced documents" not in notes
    assert ("- `travelers/`" in notes) == bool(travelers)
    for path in travelers:
        assert f"`{path}`" in notes


def _byte_record(path: Path) -> dict:
    content = path.read_bytes()
    return {
        "source": f"cad/out/{path.parent.name}/{path.name}",
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


@pytest.fixture
def feature_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Real baseline/feature copies and ZIP; isolate unrelated release producers."""
    import export_features
    import export_models
    from test_features_bound import bound_output

    out = bound_output(tmp_path)
    scene = out / "boxes" / f"{cut_release.TOP_ASSEMBLY}.json"
    scene.parent.mkdir()
    scene.write_bytes(b'{"unit":"mm"}')
    # The full export certifies its own bytes; the feature gate never reads this.
    certificate_path = out / "reports" / "release-neutral.json"
    certificate_path.parent.mkdir()
    certificate = {
        "schema": export_models.NEUTRAL_SCHEMA,
        "exporter": hashlib.md5(b"offline exporter identity").hexdigest(),
        "sources": {},
        "files": {
            f"{path.parent.name}/{path.name}": _byte_record(path)
            for path in (*sorted((out / "step").iterdir()), scene)
        },
    }
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
    inventory = {
        destination: tmp_path / record["source"]
        for destination, record in certificate["files"].items()
    }
    prepared = out / "release" / "native"
    native = prepared / "solidworks"
    drawings = prepared / "slddrw"
    native.mkdir(parents=True)
    drawings.mkdir()
    (native / "fixture.SLDPRT").write_bytes(b"prepared native fixture")
    package = {
        "out_dir": prepared.relative_to(tmp_path).as_posix(),
        "native_dir": native.relative_to(tmp_path).as_posix(),
        "drawing_dir": drawings.relative_to(tmp_path).as_posix(),
        "native_files": len(list(native.iterdir())),
        "drawing_files": len(list(drawings.iterdir())),
        "documents": len(list(native.iterdir())),
        "drawings": {},
        "solidworks_revision": "offline fixture",
    }
    monkeypatch.setattr(export_models, "REPO", tmp_path)
    monkeypatch.setattr(export_models, "NEUTRAL_MANIFEST", certificate_path)
    monkeypatch.setattr(export_models, "_exporter_digest", lambda: certificate["exporter"])
    monkeypatch.setattr(export_models, "part_stems", lambda: list(export_features.SUPPORTED_PARTS))
    monkeypatch.setattr(export_models, "ASSEMBLY_ORDER", ())
    monkeypatch.setattr(export_models, "all_scene_part_meshes", lambda _assemblies: {})
    monkeypatch.setattr(export_models, "_release_sources", lambda *_args: {})
    monkeypatch.setattr(export_models, "_release_inventory", lambda *_args: inventory)
    monkeypatch.setattr(cut_release, "CAD_ROOT", out.parent)
    monkeypatch.setattr(cut_release, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cut_release, "RELEASE_DIR", out / "release")
    monkeypatch.setattr(cut_release, "SCENE_JSON", scene)
    monkeypatch.setattr(cut_release, "DRAWING_OUTPUTS", {})
    monkeypatch.setattr(cut_release, "drawing_note_texts", set)
    monkeypatch.setattr(cut_release, "load_native_package", lambda: package)
    monkeypatch.setattr(cut_release, "stage_comparisons", lambda _stage: {})
    monkeypatch.setattr(cut_release, "stage_readout_procedure", lambda *_args: [])
    monkeypatch.setattr(cut_release, "_git", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(cut_release, "_gh", lambda *_args: "[]")
    monkeypatch.setattr(
        cut_release, "_git_provenance",
        lambda _version: {"commit_short": "offline", "tree_clean": True},
    )
    return out


def test_release_zip_keeps_exact_adjacent_feature_bundles(feature_release: Path) -> None:
    import export_features

    out = feature_release
    before_certificate = (out / "reports" / "release-neutral.json").read_bytes()
    expected = {
        path.relative_to(out).as_posix(): path.read_bytes()
        for path in (out / "features").rglob("*") if path.is_file()
    }

    zip_path, facts = cut_release.bundle("v38")

    with zipfile.ZipFile(zip_path) as archive:
        bundled = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if info.filename.startswith("features/") and not info.is_dir()
        }
        assert bundled == expected
        sums = {
            name: digest
            for digest, name in (
                line.split("  ", 1)
                for line in archive.read("SHA256SUMS.txt").decode().splitlines()
            )
        }
        for relative, content in expected.items():
            assert sums[relative] == hashlib.sha256(content).hexdigest()
            if relative.endswith("/features.toml"):
                manifest = tomllib.loads(content.decode("utf-8"))
                directory = Path(relative).parent.as_posix()
                # The bundle carries its manifest STEP plus one STEP per
                # configuration the part declares (export_features).
                configurations = {
                    f"{directory}/{Path(manifest['step']).stem}-{name}.STEP"
                    for name in export_features.step_configurations(Path(directory).name)
                }
                assert {name for name in expected if name.startswith(f"{directory}/")} == {
                    f"{directory}/{manifest['step']}", relative, *configurations,
                }
                adjacent = archive.read(f"{directory}/{manifest['step']}")
                full = archive.read(f"step/{manifest['step']}")
                # Full export consumes the validated producer's exact raw STEP.
                assert full == adjacent == (out / "step" / manifest["step"]).read_bytes()
                digest = hashlib.sha256(adjacent).hexdigest()
                assert digest == manifest["step_sha256"] == sums[f"step/{manifest['step']}"]
                assert digest == sums[f"{directory}/{manifest['step']}"]
                assert manifest["drawing"]["revision"] == "v38"
    assert set(facts["features"]) == set(expected)
    drawing_asset = Path(facts["drawing_diff"]["asset_path"])
    assert drawing_asset == zip_path.with_name("harmonic-analyzer-v38-drawing-diff.zip")
    with zipfile.ZipFile(drawing_asset) as archive:
        assert {"index.html", "summary.json"} <= set(archive.namelist())
    with zipfile.ZipFile(zip_path) as archive:
        assert not any("drawing-diff" in name for name in archive.namelist())
        assert not any(
            "drawing-diff" in line
            for line in archive.read("SHA256SUMS.txt").decode().splitlines()
        )
    assert facts["travelers"] == []
    assert (out / "reports" / "release-neutral.json").read_bytes() == before_certificate


def test_release_stages_baseline_but_never_seals_divergent_feature_producers(
    feature_release: Path,
) -> None:
    from _export_feature_faces import face_name
    from test_features_bound import _add_full_face

    out = feature_release
    full_step = _add_full_face(out, "ch_rocker_arm", face_name("pivot_bore", 2))
    certificate_path = out / "reports" / "release-neutral.json"
    certificate = json.loads(certificate_path.read_bytes())
    certificate["files"]["step/ch-rocker-arm.STEP"] = _byte_record(full_step)
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    with pytest.raises(RuntimeError):
        cut_release.bundle("v38")

    stage = out / "release" / "harmonic-analyzer-v38"
    assert (stage / "step" / full_step.name).read_bytes() == full_step.read_bytes()
    assert not (stage / "features").exists()
    assert not stage.with_suffix(".zip").exists()


def test_release_stages_enrolled_travelers_after_feature_binding(
    feature_release: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def stage_travelers(out: Path, stage: Path) -> list[Path]:
        assert out == feature_release
        assert (stage / "features" / "ch_rocker_arm" / "features.toml").is_file()
        traveler = stage / "travelers" / "ch_rocker_arm"
        traveler.mkdir(parents=True)
        (traveler / "traveler.html").write_bytes(b"verified strict traveler")
        return [traveler]

    monkeypatch.setattr(cut_release._process_plans, "stage_travelers", stage_travelers)
    zip_path, facts = cut_release.bundle("v38")

    assert facts["travelers"] == ["travelers/ch_rocker_arm"]
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.read("travelers/ch_rocker_arm/traveler.html") == (
            b"verified strict traveler"
        )


def test_release_never_seals_a_failed_traveler_verification(
    feature_release: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_travelers(_out: Path, _stage: Path) -> list[Path]:
        raise RuntimeError("traveler STEP digest mismatch")

    monkeypatch.setattr(cut_release._process_plans, "stage_travelers", refuse_travelers)
    with pytest.raises(RuntimeError, match="traveler STEP digest mismatch"):
        cut_release.bundle("v38")
    assert not (feature_release / "release" / "harmonic-analyzer-v38.zip").exists()


@pytest.fixture
def prepared_readme_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    revision_plans: tuple[Path, ...],
) -> tuple[Path, Path, Path]:
    """Real local picture staging; only CAD building and external publication are isolated."""
    release_dir = tmp_path / "release"
    release_root = release_dir / "harmonic-analyzer-v22"
    png = release_root / "png"
    for name in trim_renders.README_RENDERS:
        source = png / name / f"{name}_isometric.png"
        source.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (80, 80), "white")
        ImageDraw.Draw(image).rectangle((30, 30, 49, 49), fill="black")
        image.save(source)
    for name in trim_renders.README_DRAWINGS:
        Image.new("RGB", (72, 36), (12, 34, 56)).save(png / f"{name}_drawing.png")
    pdf = release_root / "pdf"
    pdf.mkdir()
    for pdf_name, _ in trim_renders.README_PDF_SHEETS.values():
        writer = PdfWriter()
        for rgb in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0)):
            page = writer.add_blank_page(width=72, height=36)
            content = DecodedStreamObject()
            content.set_data(f"{' '.join(map(str, rgb))} rg 0 0 72 36 re f".encode())
            page.replace_contents(content)
        with (pdf / pdf_name).open("wb") as target:
            writer.write(target)
    gltf = release_root / "gltf"
    gltf.mkdir()
    (gltf / "ha-harmonic-analyzer.glb").write_bytes(b"external renderer input")

    # The expensive graphics collaborator is isolated, but cropping, PDFium,
    # byte-for-byte drawings, image installation, and YAML replacement are real.
    def render_pose(_source: Path, target: Path, **_kwargs: object) -> None:
        Image.new("RGB", (20, 30), "blue").save(target)

    monkeypatch.setattr(trim_renders, "render_display_pose", render_pose)
    images = tmp_path / "tracked-images"
    images.mkdir()
    for name in trim_renders.README_IMAGE_NAMES:
        (images / name).write_bytes(b"previous release image")
    revision = tmp_path / "release.yaml"
    revision.write_bytes(b"next_revision: v22\n")
    native = tmp_path / "native"
    native.mkdir()
    (native / "ha-harmonic-analyzer.SLDASM").write_bytes(b"preflight input")
    scene = tmp_path / "scene.json"
    scene.write_text('{"unit":"mm"}', encoding="utf-8")
    zip_path = release_root.with_suffix(".zip")
    zip_path.write_bytes(b"prepared bundle")
    drawing_asset = zip_path.with_name("harmonic-analyzer-v22-drawing-diff.zip")
    drawing_facts = {
        "asset_path": str(drawing_asset),
        "prev": "v21",
        "images": [],
        "changed_drawings": [],
        "added_drawings": [],
        "removed_drawings": [],
        "unchanged_drawings": [],
    }
    with zipfile.ZipFile(drawing_asset, "w") as archive:
        archive.writestr("index.html", "<html>No drawing changes</html>")
        archive.writestr("summary.json", json.dumps(drawing_facts))
    facts = {
        "native_documents": 137,
        "sw_revision": "35",
        "parts": 99,
        "assemblies": 8,
        "config_meshes": 22,
        "pngs": 107,
        "comparisons": {"pairs": 3, "mean_score": None},
        "size_mb": 42.0,
        "drawing_diff": drawing_facts,
    }
    monkeypatch.setattr(cut_release, "RELEASE_DIR", release_dir)
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", revision)
    monkeypatch.setattr(cut_release, "OUT_SLDASM", native)
    monkeypatch.setattr(cut_release, "SCENE_JSON", scene)
    monkeypatch.setattr(cut_release, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
    # These image/publication tests have no feature manifests; revision validation
    # is exercised separately by the preflight regression above.
    monkeypatch.setattr(
        cut_release._process_plans, "check_plan_revision",
        lambda _stem, _out, *, revision: None,
    )
    # A fully remeasured shop; the placeholder refusal has its own regression.
    monkeypatch.setattr(cut_release._process_plans, "shop_placeholders", lambda: ())
    monkeypatch.setattr(trim_renders, "DOCS_IMAGES", images)
    monkeypatch.setattr(cut_release, "bundle", lambda *_args: (zip_path, facts))
    monkeypatch.setattr(cut_release, "_git", lambda *_args, **_kwargs: "")
    return release_root, images, revision


@pytest.mark.parametrize("publication", ["dry-run", "failed", "successful"])
def test_release_installs_images_and_revision_only_after_successful_publication(
    prepared_readme_release: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    publication: str,
) -> None:
    """Dry runs and gh failures cannot dirty the image/revision follow-up tree."""
    release_root, images, revision = prepared_readme_release
    plans = tuple(
        cut_release._process_plans.plan_path(stem)
        for stem in cut_release._process_plans.revision_stems()
    )
    original_revisions = {path: path.read_bytes() for path in (revision, *plans)}
    warnings: list[str] = []
    monkeypatch.setattr(cut_release._telemetry, "warn", warnings.append)

    def gh(*gh_args: str) -> str:
        assert str(release_root.with_name("harmonic-analyzer-v22-drawing-diff.zip")) in gh_args
        assert publication != "dry-run", "dry run reached external publication"
        assert revision.read_text(encoding="utf-8") == "next_revision: v22\n"
        assert all(
            path.read_bytes() == original
            for path, original in original_revisions.items()
        )
        for name in trim_renders.README_IMAGE_NAMES:
            assert (images / name).read_bytes() == b"previous release image"
        if publication == "failed":
            raise RuntimeError("asset publication failed")
        return "https://github.com/example/repo/releases/tag/v22"

    monkeypatch.setattr(cut_release, "_gh", gh)
    args = ["cut_release.py", "v22"]
    if publication == "dry-run":
        args.append("--no-publish")
    monkeypatch.setattr(sys, "argv", args)
    if publication == "failed":
        with pytest.raises(RuntimeError, match="asset publication failed"):
            cut_release.main()
    else:
        assert cut_release.main() == 0

    if publication == "successful":
        follow_up = next(
            message for message in warnings if "POST-RELEASE PR REQUIRED" in message
        )
        assert str(revision) in follow_up
        assert all(str(plan) in follow_up for plan in plans)
        assert revision.read_text(encoding="utf-8") == "next_revision: v23\n"
        for plan in plans:
            assert plan.read_bytes() == original_revisions[plan].replace(
                b'revision = "v22"', b'revision = "v23"'
            ).replace(b"revision = 'v22'", b"revision = 'v23'")
        assert (images / "dt-pinion-arbor-drawing.png").read_bytes() == (
            release_root / "png" / "dt-pinion-arbor_drawing.png"
        ).read_bytes()
        with Image.open(images / "fr-frame.png") as image:
            assert image.size == (68, 68)
        with Image.open(images / "dt-drive-train-assembly-sheet-4.png") as image:
            assert image.convert("RGB").getpixel((150, 75)) == (255, 255, 0)
        with Image.open(images / "fr-frame-assembly-sheet-3.png") as image:
            assert image.convert("RGB").getpixel((150, 75)) == (0, 0, 255)
    else:
        assert revision.read_text(encoding="utf-8") == "next_revision: v22\n"
        assert all(
            path.read_bytes() == original
            for path, original in original_revisions.items()
        )
        for name in trim_renders.README_IMAGE_NAMES:
            assert (images / name).read_bytes() == b"previous release image"
    assert not tuple(release_root.parent.glob(".v22-readme-images-*"))
    assert not tuple(revision.parent.glob(".release.yaml.*.tmp"))
    for plan in plans:
        assert not tuple(plan.parent.glob(".plan.toml.*.tmp"))


def test_missing_readme_artifact_fails_before_tag_or_publish(
    prepared_readme_release: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_root, images, revision = prepared_readme_release
    (release_root / "png" / "fr-frame" / "fr-frame_isometric.png").unlink()

    def git(*args: str, **_kwargs: object) -> str:
        if args[:2] == ("tag", "-a") or args[0] == "push":
            pytest.fail("missing README artifact reached tag/push")
        return ""

    monkeypatch.setattr(cut_release, "_git", git)
    monkeypatch.setattr(
        cut_release, "_gh", lambda *_args: pytest.fail("missing artifact reached publication")
    )
    monkeypatch.setattr(sys, "argv", ["cut_release.py", "v22"])

    with pytest.raises(FileNotFoundError, match="fr-frame_isometric.png"):
        cut_release.main()

    assert revision.read_text(encoding="utf-8") == "next_revision: v22\n"
    for stem in cut_release._process_plans.revision_stems():
        plan = cut_release._process_plans.plan_path(stem)
        assert tomllib.loads(plan.read_text())["drawing"]["revision"] == "v22"
    for name in trim_renders.README_IMAGE_NAMES:
        assert (images / name).read_bytes() == b"previous release image"


def test_postpublish_image_install_failure_preserves_revision_and_identifies_recovery(
    prepared_readme_release: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, images, revision = prepared_readme_release
    url = "https://github.com/example/repo/releases/tag/v22"
    monkeypatch.setattr(cut_release, "_gh", lambda *_args: url)
    replace = os.replace

    def refuse_image_install(source: Path, destination: Path) -> None:
        if Path(destination).parent == images:
            raise PermissionError("image destination is read-only")
        replace(source, destination)

    monkeypatch.setattr(os, "replace", refuse_image_install)
    monkeypatch.setattr(sys, "argv", ["cut_release.py", "v22"])

    with pytest.raises(RuntimeError) as failure:
        cut_release.main()

    message = str(failure.value)
    assert url in message
    assert (
        "uv run --frozen python cad/scripts/trim_renders.py "
        "--release-root cad/out/release/harmonic-analyzer-v22"
    ) in message
    assert "next_revision: v23" in message
    assert revision.read_text(encoding="utf-8") == "next_revision: v22\n"
    for name in trim_renders.README_IMAGE_NAMES:
        assert (images / name).read_bytes() == b"previous release image"
    assert not tuple(revision.parent.glob(".release.yaml.*.tmp"))
    for stem in cut_release._process_plans.revision_stems():
        plan = cut_release._process_plans.plan_path(stem)
        assert str(plan) in message
        assert tomllib.loads(plan.read_text())["drawing"]["revision"] == "v22"
        assert not tuple(plan.parent.glob(".plan.toml.*.tmp"))


def test_postpublish_partial_revision_install_names_all_recovery_paths(
    prepared_readme_release: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _images, revision = prepared_readme_release
    plans = tuple(
        cut_release._process_plans.plan_path(stem)
        for stem in cut_release._process_plans.revision_stems()
    )
    url = "https://github.com/example/repo/releases/tag/v22"
    monkeypatch.setattr(cut_release, "_gh", lambda *_args: url)
    replace = os.replace

    def refuse_last_plan(source: Path, destination: Path) -> None:
        if destination == plans[-1]:
            raise PermissionError("last plan is read-only")
        replace(source, destination)

    monkeypatch.setattr(os, "replace", refuse_last_plan)
    monkeypatch.setattr(sys, "argv", ["cut_release.py", "v22"])
    with pytest.raises(RuntimeError) as failure:
        cut_release.main()

    message = str(failure.value)
    assert url in message
    assert "partial revision install" in message
    assert "[drawing].revision" in message
    assert "v23" in message
    for path in (revision, *plans):
        assert str(path) in message
        assert not tuple(path.parent.glob(f".{path.name}.*.tmp"))
    assert revision.read_bytes() == b"next_revision: v23\n"
    assert tomllib.loads(plans[0].read_text())["drawing"]["revision"] == "v23"
    assert tomllib.loads(plans[1].read_text())["drawing"]["revision"] == "v22"


def test_drawing_baseline_failure_blocks_bundle_before_publication(
    feature_release: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args: str) -> str:
        raise RuntimeError("GitHub release API unavailable")

    monkeypatch.setattr(cut_release, "_gh", unavailable)
    with pytest.raises(RuntimeError, match="GitHub release API unavailable"):
        cut_release.bundle("v38")
    assert not (feature_release / "release" / "harmonic-analyzer-v38.zip").exists()


def test_missing_drawing_asset_blocks_tag_and_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("missing drawing ZIP reached git/gh publication")

    monkeypatch.setattr(cut_release, "_git", forbidden)
    monkeypatch.setattr(cut_release, "_gh", forbidden)
    facts = {"drawing_diff": {"asset_path": str(tmp_path / "missing-drawing-diff.zip")}}
    with pytest.raises(RuntimeError, match="required drawing-diff asset is missing"):
        cut_release.publish("v44", tmp_path / "cad.zip", facts, False)


def test_dry_run_reports_drawing_zip(
    prepared_readme_release: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    root, _images, _revision = prepared_readme_release
    zip_path, facts = cut_release.bundle("v22")
    cut_release.report_no_publish("v22", zip_path, facts)
    output = capsys.readouterr().out
    asset = root.with_name("harmonic-analyzer-v22-drawing-diff.zip")
    assert f"asset: {asset}" in caplog.text
    assert "/releases/download/v22/harmonic-analyzer-v22-drawing-diff.zip" in output


def test_published_logs_snapshot_includes_tag_and_push(
    prepared_readme_release: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _images, _revision = prepared_readme_release
    zip_path, facts = cut_release.bundle("v22")
    logs = root.parent / "task-logs"
    logs.mkdir()
    (logs / "task.log").write_text("task complete\n", encoding="utf-8")
    release_log = root.parent / "release.log"
    release_log.write_text("staging complete\n", encoding="utf-8")
    monkeypatch.setattr(cut_release, "LOGS_DIR", logs)

    def git(*args: str, **_kwargs: object) -> str:
        if args[0] in ("tag", "push"):
            with release_log.open("a", encoding="utf-8") as target:
                target.write(f"{args[0]} complete\n")
        return ""

    def gh(*args: str) -> str:
        asset = root.parent / "harmonic-analyzer-v22-logs.zip"
        assert str(asset) in args
        with zipfile.ZipFile(asset) as archive:
            lines = archive.read("release.log").decode("utf-8").splitlines()
        assert lines == ["staging complete", "tag complete", "push complete"]
        return "https://github.com/example/repo/releases/tag/v22"

    monkeypatch.setattr(cut_release, "_git", git)
    monkeypatch.setattr(cut_release, "_gh", gh)
    cut_release.publish("v22", zip_path, facts, False, release_log)
