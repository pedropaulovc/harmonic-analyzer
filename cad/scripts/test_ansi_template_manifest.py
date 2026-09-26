"""SolidWorks-free pins on the true-ANSI template manifest."""

from __future__ import annotations

import ansi_template_manifest as manifest


def test_manifest_covers_the_measured_rebase() -> None:
    # v2 blast radius: 35 table rows over 34 preference names, expanded to 61
    # preference/option pairs, plus 65 text formats.
    pairs = [s for s in manifest.SETTINGS if s.kind != "text_format"]
    assert len(pairs) == 61
    assert manifest.DISTINCT_SETTINGS == 34
    assert manifest.TEXT_FORMATS == 65
    assert len({manifest.key(s) for s in manifest.SETTINGS}) == len(manifest.SETTINGS)


def test_every_row_is_a_real_change_with_a_reason() -> None:
    for setting in manifest.SETTINGS:
        assert setting.as_built != setting.iso_to_ansi, setting.name
        assert setting.why, setting.name
        expected = (
            setting.iso_to_ansi if setting.decision == "ansi" else setting.as_built
        )
        assert setting.target == expected, setting.name


def test_only_text_heights_are_restored() -> None:
    restored = {s.name for s in manifest.restores()}
    assert {"swDetailingDimFontHeight", "swDetailingNoteFontHeight"} <= restored
    assert all(
        s.kind == "text_format" or s.name.endswith("FontHeight")
        for s in manifest.restores()
    )
    heights = {s.target for s in manifest.SETTINGS if s.kind == "text_format"}
    assert heights == {(0.0035, 13), (0.00635, 24)}


def test_the_standard_moves_iso_to_ansi_on_every_type() -> None:
    standard = [
        s
        for s in manifest.SETTINGS
        if s.kind == "integer" and s.pref == manifest.STANDARD_PREF
    ]
    assert len(standard) == 23  # no option + 22 per-type options
    assert all(s.as_built == manifest.STANDARD_ISO for s in standard)
    assert all(s.target == manifest.STANDARD_ANSI for s in standard)
    assert manifest.REBASE_SEQUENCE == (manifest.STANDARD_ISO, manifest.STANDARD_ANSI)


def test_the_uppercase_toggles_are_never_written() -> None:
    forbidden = set(manifest.FORBIDDEN_TOGGLES.values())
    assert not {s.pref for s in manifest.SETTINGS if s.kind == "toggle"} & forbidden
