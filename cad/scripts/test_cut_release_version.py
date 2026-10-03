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


def test_published_release_advances_tracked_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "release.yaml"
    source.write_text("next_revision: v22\n", encoding="utf-8")
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")

    assert cut_release.advance_configured_revision("v22") == "v23"
    assert source.read_text(encoding="utf-8") == "next_revision: v23\n"


def test_revision_advance_is_staged_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "release.yaml"
    source.write_text("next_revision: v22\n", encoding="utf-8")
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", source)
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")

    prepared = cut_release.prepare_configured_revision_advance("v22")
    try:
        assert prepared.next_version == "v23"
        assert prepared.temporary is not None
        assert prepared.temporary.exists()
        assert source.read_text(encoding="utf-8") == "next_revision: v22\n"
        assert prepared.commit() == "v23"
    finally:
        prepared.discard()

    assert source.read_text(encoding="utf-8") == "next_revision: v23\n"


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
                    pen_per_bar_at_min * nom.lever_r_built / nom.lever_r_min
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

    staged = cut_release.stage_readout_procedure(tmp_path, "v42")
    assert staged[0] == "READOUT.md"
    for rel in staged:
        assert (tmp_path / rel).is_file(), rel
    readout = (tmp_path / "READOUT.md").read_text(encoding="utf-8")
    assert "`docs/device-operation.md`" in readout
    assert "`cad/docs/device-operation.md`" not in readout.split("beside this file")[0]
    docs = cut_release.operating_docs()
    assert docs[0] == cut_release.OPERATING_DOC and "tolerance-policy.md" in docs
    relative = re.compile(r"\]\(((?!https?:|mailto:|#)[^)]+)\)")
    tagged = 0
    for name in docs:
        page = (tmp_path / "docs" / name).read_text(encoding="utf-8")
        for target in relative.findall(page):
            assert target.startswith("./"), f"{name} -> {target} escapes the bundle"
            assert (tmp_path / "docs" / target.split("#")[0]).is_file(), (
                f"{name} -> {target}"
            )
        tagged += page.count("/blob/v42/cad/")
    assert tagged >= 5  # the policy's config/script citations
    # the submodule scans are cited by repo path, never embedded or linked
    paper = (tmp_path / "docs" / "michelson-1898-trial-accuracy.md").read_text(
        encoding="utf-8"
    )
    assert "28_Michelsons_1898_Paper.pdf` (pinned references submodule)" in paper
    assert "/blob/v42/references/" not in paper


def test_staged_bundle_declares_its_sources_and_permitted_use(
    tmp_path, readout_report
):
    """The staged pages quote the 2014 book (short attributed excerpts) and
    cite the reference scans, so the bundle must carry that boundary itself:
    a downloader who never sees kickstarter/campaign/risks.md must still be
    told the 2014 book is non-commercial-use only, that no photograph or
    drawing from it is reproduced, and where the CC BY credits are."""
    staged = cut_release.stage_readout_procedure(tmp_path, "v42")
    assert "NOTICE.md" in staged
    notice = (tmp_path / "NOTICE.md").read_text(encoding="utf-8")
    assert "non-commercial purposes" in notice
    assert "Hammack" in notice and "2014" in notice
    assert "public domain" in notice  # the 1898 machine and paper
    assert "comparisons/ATTRIBUTION.md" in notice  # where the gallery lands
    assert "cad/comparisons/ATTRIBUTION.md" not in notice  # not the repo path
    assert "NOT included in this bundle" in notice  # the reference scans
    # the project's OWN artefacts stay MIT -- a zip-only reader must not read
    # the third-party restriction as covering the CAD, and the licence it is
    # told about has to be in the zip
    assert "MIT" in notice.split("public domain")[0]
    assert "LICENSE" in staged
    assert "MIT License" in (tmp_path / "LICENSE").read_text(encoding="utf-8")


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


def test_release_notes_report_the_native_pack_and_go_count() -> None:
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
    }

    notes = cut_release.release_notes("v42", facts)

    assert "native Pack-and-Go (137 referenced documents" in notes
    assert "99 referenced documents" not in notes


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
    scene = out / "boxes" / "harmonic-analyzer.json"
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
    monkeypatch.setattr(cut_release, "load_native_package", lambda: package)
    monkeypatch.setattr(cut_release, "stage_comparisons", lambda _stage: {})
    monkeypatch.setattr(cut_release, "stage_readout_procedure", lambda *_args: [])
    monkeypatch.setattr(cut_release, "_git", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        cut_release, "_git_provenance",
        lambda _version: {"commit_short": "offline", "tree_clean": True},
    )
    return out


def test_release_zip_keeps_exact_adjacent_feature_bundles(feature_release: Path) -> None:
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
                assert {name for name in expected if name.startswith(f"{directory}/")} == {
                    f"{directory}/{manifest['step']}", relative,
                }
                adjacent = archive.read(f"{directory}/{manifest['step']}")
                full = archive.read(f"step/{manifest['step']}")
                # Independent exports: different raw bytes, the same face labels.
                assert full == (out / "step" / manifest["step"]).read_bytes() != adjacent
                assert hashlib.sha256(adjacent).hexdigest() == manifest["step_sha256"]
                assert manifest["drawing"]["revision"] == "v38"
    assert set(facts["features"]) == set(expected)
    assert (out / "reports" / "release-neutral.json").read_bytes() == before_certificate


def test_release_stages_baseline_but_never_seals_divergent_feature_producers(
    feature_release: Path,
) -> None:
    from _export_feature_faces import face_name
    from test_features_bound import _add_full_face

    out = feature_release
    full_step = _add_full_face(out, "rocker_arm", face_name("pivot_bore", 2))
    certificate_path = out / "reports" / "release-neutral.json"
    certificate = json.loads(certificate_path.read_bytes())
    certificate["files"]["step/rocker-arm.STEP"] = _byte_record(full_step)
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    with pytest.raises(RuntimeError, match="face labels differ"):
        cut_release.bundle("v38")

    stage = out / "release" / "harmonic-analyzer-v38"
    assert (stage / "step" / full_step.name).read_bytes() == full_step.read_bytes()
    assert not (stage / "features").exists()
    assert not stage.with_suffix(".zip").exists()


@pytest.fixture
def prepared_readme_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    revision.write_text("next_revision: v22\n", encoding="utf-8")
    native = tmp_path / "native"
    native.mkdir()
    (native / "ha-harmonic-analyzer.SLDASM").write_bytes(b"preflight input")
    scene = tmp_path / "scene.json"
    scene.write_text('{"unit":"mm"}', encoding="utf-8")
    zip_path = release_root.with_suffix(".zip")
    zip_path.write_bytes(b"prepared bundle")
    facts = {
        "native_documents": 137,
        "sw_revision": "35",
        "parts": 99,
        "assemblies": 8,
        "config_meshes": 22,
        "pngs": 107,
        "comparisons": {"pairs": 3, "mean_score": None},
        "size_mb": 42.0,
    }
    monkeypatch.setattr(cut_release, "RELEASE_DIR", release_dir)
    monkeypatch.setattr(cut_release, "RELEASE_VERSION_FILE", revision)
    monkeypatch.setattr(cut_release, "OUT_SLDASM", native)
    monkeypatch.setattr(cut_release, "SCENE_JSON", scene)
    monkeypatch.setattr(cut_release, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(cut_release._config, "release_revision", lambda: "v22")
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

    def gh(*_args: str) -> str:
        assert publication != "dry-run", "dry run reached external publication"
        assert revision.read_text(encoding="utf-8") == "next_revision: v22\n"
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
        assert revision.read_text(encoding="utf-8") == "next_revision: v23\n"
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
        for name in trim_renders.README_IMAGE_NAMES:
            assert (images / name).read_bytes() == b"previous release image"
    assert not tuple(release_root.parent.glob(".v22-readme-images-*"))
    assert not tuple(revision.parent.glob(".release.yaml.*.tmp"))


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
        "uv run python cad/scripts/trim_renders.py "
        "--release-root cad/out/release/harmonic-analyzer-v22"
    ) in message
    assert "next_revision: v23" in message
    assert revision.read_text(encoding="utf-8") == "next_revision: v22\n"
    for name in trim_renders.README_IMAGE_NAMES:
        assert (images / name).read_bytes() == b"previous release image"
    assert not tuple(revision.parent.glob(".release.yaml.*.tmp"))
