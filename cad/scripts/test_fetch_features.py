"""fetch_features: seat-free bundles from a release ZIP, read by byte range."""

from __future__ import annotations

import io
import tomllib
import zipfile
from pathlib import Path

import pytest

import _config
import _features_provenance
import export_features
import fetch_features
from _export_feature_faces import inventory_path
from _test_feature_bundles import bind_manifest, rewrite_step, write_bundle

UNDECLARED = "ch_amplitude_bar"
DECLARED = "ch_pivot_shaft"


def _release_zip(
    tmp_path: Path,
    stem: str,
    monkeypatch,
    *,
    tamper: bool = False,
    drop_feature: bool = False,
    inventories: bool = True,
    extra: tuple[str, ...] = (),
) -> bytes:
    """A release ZIP: a large unrelated member, then one bundle built by the
    real writer. The drawing's selectors are doubles that match the synthetic
    inventory, here and in the fetcher's offline rebind."""
    _manifest, step = export_features.bundle_paths(stem, tmp_path)
    selectors = write_bundle(stem, step)
    monkeypatch.setattr(
        export_features, "feature_selectors", lambda _stem, cfg=None: selectors[cfg]
    )
    manifest = bind_manifest(stem, step, selectors, revision=_config.release_revision())
    if drop_feature:
        # A release cut before the drawing declared its last feature.
        text = manifest.read_text(encoding="utf-8")
        last = list(tomllib.loads(text)["features"])[-1]
        table = tomllib.loads(text)
        del table["features"][last]
        manifest.write_text(export_features._toml(table), encoding="utf-8")
    if tamper:
        step.write_bytes(step.read_bytes() + b"/* drift */")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "solidworks/ha-harmonic-analyzer.SLDASM", bytes(range(256)) * 4096
        )
        for path in (step, manifest, *((inventory_path(step),) if inventories else ())):
            archive.writestr(f"features/{stem}/{path.name}", path.read_bytes())
        for name in extra:
            # ZipInfo() turns os.sep into "/"; keep the name byte-for-byte.
            info = zipfile.ZipInfo(name)
            info.filename = name
            archive.writestr(info, b"x")
    return buffer.getvalue()


def _serve(monkeypatch, content: bytes) -> list[tuple[int, int]]:
    """Answer range requests from ``content``, recording each byte range."""
    ranges: list[tuple[int, int]] = []

    class _Response(io.BytesIO):
        def __init__(self, data: bytes, start: int) -> None:
            super().__init__(data)
            self.status = 206
            self.headers = {
                "Content-Range": f"bytes {start}-{start + len(data) - 1}/{len(content)}"
            }

    def urlopen(request, timeout=None):
        first, _, last = (
            request.get_header("Range").removeprefix("bytes=").partition("-")
        )
        start, end = int(first), int(last) + 1
        ranges.append((start, end))
        return _Response(content[start:end], start)

    monkeypatch.setattr(fetch_features.urllib.request, "urlopen", urlopen)
    return ranges


def _release(
    monkeypatch,
    tmp_path: Path,
    stem: str = UNDECLARED,
    *,
    changed: tuple[str, ...] = (),
    **shape,
) -> list:
    ranges = _serve(
        monkeypatch, _release_zip(tmp_path / "published", stem, monkeypatch, **shape)
    )
    monkeypatch.setattr(
        fetch_features,
        "release_asset",
        lambda _tag: ("v99", "https://example.invalid/r.zip"),
    )
    monkeypatch.setattr(fetch_features, "tag_commit", lambda _tag: "a" * 40)
    monkeypatch.setattr(fetch_features, "_git", lambda *_args: "b" * 40)
    monkeypatch.setattr(
        _features_provenance,
        "recipe_files",
        lambda selected: {
            f"cad/scripts/build_{selected}.py": "geometry",
            f"cad/scripts/draw_{selected}.py": "manifest",
        },
    )
    monkeypatch.setattr(
        _features_provenance,
        "geometry_inputs",
        lambda selected: {f"cad/scripts/build_{selected}.py": "d1"},
    )
    monkeypatch.setattr(
        fetch_features, "changed_since", lambda _commit, _files: list(changed)
    )
    return ranges


def _stamp(stem: str) -> str:
    """The provenance table the doubles above make the rebind append."""
    return f'\n[geometry_inputs]\n"cad/scripts/build_{stem}.py" = "d1"\n'


def test_a_current_bundle_is_fetched_by_range_without_the_rest_of_the_zip(
    tmp_path: Path, monkeypatch
) -> None:
    ranges = _release(monkeypatch, tmp_path)
    out = tmp_path / "out"
    assert fetch_features.main([UNDECLARED, "--out", str(out)]) == 0
    manifest, step = export_features.bundle_paths(UNDECLARED, out)
    published = export_features.bundle_paths(UNDECLARED, tmp_path / "published")
    assert (
        manifest.read_bytes() == published[0].read_bytes() + _stamp(UNDECLARED).encode()
    )
    assert step.read_bytes() == published[1].read_bytes()
    assert (
        inventory_path(step).read_bytes() == inventory_path(published[1]).read_bytes()
    )
    # The 1 MiB unrelated member is never read.
    assert sum(end - start for start, end in ranges) < 1 << 20


def test_a_new_declaration_binds_to_the_released_step_without_a_farm(
    tmp_path: Path, monkeypatch
) -> None:
    _release(
        monkeypatch,
        tmp_path,
        DECLARED,
        drop_feature=True,
        changed=(f"cad/scripts/draw_{DECLARED}.py",),
    )
    out = tmp_path / "out"
    # Record the status line directly: whether an INFO record reaches caplog
    # depends on handlers an earlier test's _telemetry.configure() installed.
    said: list[str] = []
    monkeypatch.setattr(
        fetch_features._telemetry,
        "info",
        lambda message, **_fields: said.append(message),
    )
    assert fetch_features.main([DECLARED, "--out", str(out)]) == 0
    assert any("features.toml rebound from this checkout" in line for line in said)
    manifest, step = export_features.bundle_paths(DECLARED, out)
    published = export_features.bundle_paths(DECLARED, tmp_path / "published")
    assert step.read_bytes() == published[1].read_bytes()
    features = tomllib.loads(manifest.read_text(encoding="utf-8"))["features"]
    assert set(features) == set(export_features.feature_selectors(DECLARED))


@pytest.mark.parametrize("changed", [(), (f"cad/scripts/draw_{DECLARED}.py",)])
def test_a_release_without_inventories_is_always_stale(
    tmp_path: Path, monkeypatch, capsys, changed: tuple[str, ...]
) -> None:
    _release(monkeypatch, tmp_path, DECLARED, inventories=False, changed=changed)
    out = tmp_path / "out"
    assert fetch_features.main([DECLARED, "--out", str(out)]) == 2
    err = capsys.readouterr().err
    for name in changed:
        assert f"manifest input changed since v99: {name}" in err
    assert "release v99 predates face inventories" in err
    assert not (out / "features").exists()


def test_a_geometry_change_is_reported_stale_and_not_written(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _release(monkeypatch, tmp_path, changed=(f"cad/scripts/build_{UNDECLARED}.py",))
    out = tmp_path / "out"
    assert fetch_features.main([UNDECLARED, "--out", str(out)]) == 2
    err = capsys.readouterr().err
    assert f"STALE {UNDECLARED}" in err
    assert f"geometry input changed since v99: cad/scripts/build_{UNDECLARED}.py" in err
    assert not (out / "features").exists()
    # No override: the old flag is gone.
    with pytest.raises(SystemExit):
        fetch_features.main([UNDECLARED, "--out", str(out), "--accept-stale"])


def test_check_reports_a_copied_bundle_against_this_checkout(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _release(monkeypatch, tmp_path)
    out = tmp_path / "out"
    assert fetch_features.main([UNDECLARED, "--out", str(out)]) == 0
    assert fetch_features.main(["--check", UNDECLARED, "--out", str(out)]) == 0
    # A current bundle rebinds in place and keeps its geometry inputs.
    manifest = export_features.bundle_paths(UNDECLARED, out)[0]
    stamped = manifest.read_bytes()
    assert fetch_features.main(["--rebind", UNDECLARED, "--out", str(out)]) == 0
    assert manifest.read_bytes() == stamped
    # The checkout's geometry moves on: the bundle is stale, the input named.
    monkeypatch.setattr(
        _features_provenance,
        "geometry_inputs",
        lambda selected: {f"cad/scripts/build_{selected}.py": "d2"},
    )
    assert fetch_features.main(["--check", UNDECLARED, "--out", str(out)]) == 2
    assert (
        f"geometry input changed since the bundle was built: cad/scripts/build_{UNDECLARED}.py"
        in capsys.readouterr().err
    )
    # A stale one is neither rebound nor restamped.
    assert fetch_features.main(["--rebind", UNDECLARED, "--out", str(out)]) == 2
    assert manifest.read_bytes() == stamped
    # A bundle bound without the stamp (by hand, or before #3668) is refused.
    published = tmp_path / "published"
    assert fetch_features.main(["--check", UNDECLARED, "--out", str(published)]) == 2
    assert "records no geometry_inputs" in capsys.readouterr().err
    assert fetch_features.main(["--check", DECLARED, "--out", str(out)]) == 2
    assert "unreadable bundle" in capsys.readouterr().err


def test_trust_step_stamps_a_bundle_restored_from_a_farm_run(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _release(monkeypatch, tmp_path)
    published = export_features.bundle_paths(UNDECLARED, tmp_path / "published")
    # A farm run's out/features/<stem>/: the STEP and its inventory, copied by hand.
    out = tmp_path / "restored"
    manifest, step = export_features.bundle_paths(UNDECLARED, out)
    step.parent.mkdir(parents=True)
    step.write_bytes(published[1].read_bytes())
    inventory_path(step).write_bytes(inventory_path(published[1]).read_bytes())
    assert fetch_features.main(["--check", UNDECLARED, "--out", str(out)]) == 2
    capsys.readouterr()
    assert fetch_features.main(["--trust-step", UNDECLARED, "--out", str(out)]) == 0
    assert f"{UNDECLARED}: TRUSTING the STEP" in capsys.readouterr().err
    assert (
        manifest.read_bytes() == published[0].read_bytes() + _stamp(UNDECLARED).encode()
    )
    assert fetch_features.main(["--check", UNDECLARED, "--out", str(out)]) == 0
    # A stamped bundle is bound and stamped afresh, not refused as stamped.
    assert fetch_features.main(["--trust-step", UNDECLARED, "--out", str(out)]) == 0
    assert (
        manifest.read_bytes() == published[0].read_bytes() + _stamp(UNDECLARED).encode()
    )
    stamped = manifest.read_bytes()
    capsys.readouterr()
    # The checkout's geometry moves on: the manifest binds this very STEP to
    # other geometry inputs, so the STEP is provably stale and left as it is.
    monkeypatch.setattr(
        _features_provenance,
        "geometry_inputs",
        lambda selected: {f"cad/scripts/build_{selected}.py": "d2"},
    )
    assert fetch_features.main(["--trust-step", UNDECLARED, "--out", str(out)]) == 2
    err = capsys.readouterr().err
    assert "binds this STEP to other geometry inputs" in err
    assert "TRUSTING" not in err
    assert manifest.read_bytes() == stamped
    # A STEP restored over it with an inventory that is not its own: refused.
    original = step.read_bytes()
    step.write_bytes(original + b"/* drift */")
    assert fetch_features.main(["--trust-step", UNDECLARED, "--out", str(out)]) == 1
    assert manifest.read_bytes() == stamped
    step.write_bytes(original)
    # A manifest that no longer binds the STEP says nothing about it: trusted.
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            tomllib.loads(stamped.decode())["step_sha256"], "0" * 64
        ),
        encoding="utf-8",
    )
    assert fetch_features.main(["--trust-step", UNDECLARED, "--out", str(out)]) == 0
    assert manifest.read_text(encoding="utf-8").endswith(
        f'"cad/scripts/build_{UNDECLARED}.py" = "d2"\n'
    )
    # No inventory beside the STEP: named as such, not written.
    inventory_path(step).unlink()
    restamped = manifest.read_bytes()
    capsys.readouterr()
    assert fetch_features.main(["--trust-step", UNDECLARED, "--out", str(out)]) == 1
    err = capsys.readouterr().err
    assert f"{UNDECLARED}: no face inventory for ['{step.name}']" in err
    assert manifest.read_bytes() == restamped
    # Nothing restored: refused, nothing written.
    assert fetch_features.main(["--trust-step", DECLARED, "--out", str(out)]) == 1
    assert not (out / "features" / DECLARED).exists()
    with pytest.raises(SystemExit):
        fetch_features.main(["--trust-step", "--check", UNDECLARED, "--out", str(out)])


MEMBERED = "dt_cone_gear_tl_arbor_collar"


def test_trust_step_refuses_while_a_member_step_is_still_bound_to_other_geometry(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    # #3737: a two-member part restored whole, stamped, then the geometry moves
    # and only the primary STEP is restored from a newer farm run.
    _release(monkeypatch, tmp_path, MEMBERED)
    published = tmp_path / "published"
    out = tmp_path / "restored"
    manifest, step = export_features.bundle_paths(MEMBERED, out)
    members = export_features.member_step_paths(MEMBERED, out)
    assert len(members) == 2
    step.parent.mkdir(parents=True)
    for restored in export_features.exported_steps(MEMBERED, out):
        source = published / "features" / MEMBERED / restored.name
        restored.write_bytes(source.read_bytes())
        inventory_path(restored).write_bytes(inventory_path(source).read_bytes())
    assert fetch_features.main(["--trust-step", MEMBERED, "--out", str(out)]) == 0
    stamped = manifest.read_bytes()
    monkeypatch.setattr(
        _features_provenance,
        "geometry_inputs",
        lambda selected: {f"cad/scripts/build_{selected}.py": "d2"},
    )
    rewrite_step(step, step.read_bytes() + b"\n/* rebuilt */")
    capsys.readouterr()
    assert fetch_features.main(["--trust-step", MEMBERED, "--out", str(out)]) == 2
    err = capsys.readouterr().err
    assert "binds this STEP to other geometry inputs" in err
    assert "TRUSTING" not in err
    assert manifest.read_bytes() == stamped
    # One member restored too: the other still binds, still refused.
    first, second = members.values()
    rewrite_step(first, first.read_bytes() + b"\n/* rebuilt */")
    assert fetch_features.main(["--trust-step", MEMBERED, "--out", str(out)]) == 2
    assert manifest.read_bytes() == stamped
    # Every STEP restored: nothing binds the old geometry, so it is trusted.
    rewrite_step(second, second.read_bytes() + b"\n/* rebuilt */")
    capsys.readouterr()
    assert fetch_features.main(["--trust-step", MEMBERED, "--out", str(out)]) == 0
    assert f"{MEMBERED}: TRUSTING the STEP" in capsys.readouterr().err
    assert manifest.read_text(encoding="utf-8").endswith(
        f'"cad/scripts/build_{MEMBERED}.py" = "d2"\n'
    )


def test_a_bundle_that_does_not_bind_its_step_is_refused(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _release(monkeypatch, tmp_path, tamper=True)
    out = tmp_path / "out"
    assert fetch_features.main([UNDECLARED, "--out", str(out)]) == 1
    assert "bundle records" in capsys.readouterr().err
    assert not (out / "features").exists()


@pytest.mark.parametrize(
    "member",
    [
        f"features/{UNDECLARED}/..\\..\\x",
        f"features/{UNDECLARED}/C:x",
        f"features/{UNDECLARED}/sub/x",
    ],
)
def test_an_unsafe_or_nested_bundle_member_is_refused(
    tmp_path: Path, monkeypatch, capsys, member: str
) -> None:
    _release(monkeypatch, tmp_path, extra=(member,))
    out = tmp_path / "out"
    assert fetch_features.main([UNDECLARED, "--out", str(out)]) == 1
    err = capsys.readouterr().err
    assert repr(member) in err or member in err
    assert not (out / "features").exists()


def test_unknown_parts_are_refused() -> None:
    with pytest.raises(SystemExit) as refused:
        fetch_features.main(["fr_vn_lag_screw"])
    assert refused.value.code == 2


def test_geometry_inputs_read_the_real_graph() -> None:
    # The real graph, no doubles: a part keyed on its fastener-catalog rows.
    stem = "dt_cone_tip_end_screw"
    inputs = _features_provenance.geometry_inputs(stem)
    assert f"cad/scripts/build_{stem}.py" in inputs
    assert f"cad/out/.fastener-catalog/part-{stem}.digest" in inputs
    # Cutting a release bumps release.yaml without changing any geometry.
    assert "cad/config/release.yaml" not in inputs
    recipe = _features_provenance.recipe_files(stem)
    assert recipe["cad/scripts/_fastener_catalog.py"] == "geometry"
    assert "cad/config/release.yaml" not in recipe
