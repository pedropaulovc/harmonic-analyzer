"""picture_clip: what it measures and finds on a rendered hobby traveler, and
the baseline ratchet prechips_traveler.py applies with it."""

from __future__ import annotations

import base64

import pytest

import picture_clip as clip

_NS = 'xmlns="http://www.w3.org/2000/svg"'
# dt_cone_tip_block's front view (prechips 0.11.52, main 2240826699), cut to
# the label and its leader: the leader starts on the baseline under "vise" and
# runs down through the word. Seen in the rendered picture, not only measured.
_TIP_BLOCK = (
    f'<svg {_NS} viewBox="0 0 760 420" font-family="Arial, Helvetica, sans-serif" font-size="13">'
    '<text class="label" x="20" y="180">spacer strip on end</text>'
    '<text class="label" x="20" y="196">on the vise bed</text>'
    '<line class="leader" x1="60" y1="196" x2="117.92" y2="224"/>'
    "</svg>"
)


def _sheet(tmp_path, *pictures: tuple[str, str]):
    """A hobby sheet embedding each (alt, svg) as prechips does."""
    images = "".join(
        f'<img src="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}" alt="{alt}">'
        for alt, svg in pictures
    )
    sheet = tmp_path / "traveler-hobby.html"
    sheet.write_text(f"<html><body>{images}</body></html>", encoding="utf-8")
    return sheet


def test_widths_are_arial_metrics():
    # Arial's advance widths (arial.ttf at 1000 units/em): the sheet's print font.
    assert clip.text_width("(schematic; the bar's ends run off the page)", 1000) == pytest.approx(19255.7, abs=1)
    assert clip.text_width("Ø.196–.200 × 30° −Y", 1000) == pytest.approx(9407, abs=1)
    assert clip.text_width("X0, the left edge", 1000, bold=True) == pytest.approx(7669, abs=1)


def test_a_leader_through_its_own_label_is_found(tmp_path):
    found = clip.findings(_sheet(tmp_path, ("From the front, 2.6 px/mm: the block", _TIP_BLOCK)))
    assert [f.key for f in found] == ["LEADER | From the front, 2.6 px/mm: the block | on the vise bed"]


def test_a_leader_starting_beside_its_label_passes(tmp_path):
    svg = _TIP_BLOCK.replace('x1="60" y1="196"', 'x1="60" y1="200"')
    assert clip.findings(_sheet(tmp_path, ("moved", svg))) == []


def test_text_past_the_picture_edge_is_a_clip(tmp_path):
    # 13 px Arial: this note is 250.3 px long; from x 640 it ends past 760.
    svg = f'<svg {_NS} viewBox="0 0 760 200" font-size="13"><text x="640" y="40">(schematic; the bar\'s ends run off the page)</text></svg>'
    (finding,) = clip.findings(_sheet(tmp_path, ("note", svg)))
    assert finding.kind == "CLIP" and finding.text.startswith("(schematic")
    fits = svg.replace('viewBox="0 0 760 200"', 'viewBox="0 0 900 200"')
    assert clip.findings(_sheet(tmp_path, ("note", fits))) == []


def test_transforms_place_text_and_a_halo_counts_once(tmp_path):
    # The same label drawn twice at one place (a halo under it) is not an
    # overlap; a copy moved by translate() lands where it is drawn.
    svg = (
        f'<svg {_NS} viewBox="0 0 400 400" font-size="13">'
        '<text x="20" y="40" stroke="#fff">OUTSIDE</text><text x="20" y="40">OUTSIDE</text>'
        '<text x="20" y="40" transform="translate(0 300)">OUTSIDE</text>'
        '<g transform="translate(0 30)"><text x="20" y="12">BACK</text></g>'
        "</svg>"
    )
    found = clip.findings(_sheet(tmp_path, ("halo", svg)))
    assert [f.key for f in found] == ["TEXT | halo | OUTSIDE / BACK"]


def test_the_picture_key_is_not_checked(tmp_path):
    key = f'<svg {_NS} viewBox="0 0 10 10"><text x="0" y="5">vise jaw, work holder</text></svg>'
    assert clip.findings(_sheet(tmp_path, ("Picture key: removed this setup", key))) == []


def test_the_baseline_admits_listed_findings_and_refuses_new_or_fixed_ones(tmp_path):
    sheet = _sheet(tmp_path, ("From the front, 2.6 px/mm: the block", _TIP_BLOCK))
    key = "LEADER | From the front, 2.6 px/mm: the block | on the vise bed"
    baseline = tmp_path / "picture-clip-baseline.toml"
    baseline.write_text(f'[plans.tip]\nfindings = ["{key}"]\n', encoding="utf-8")
    assert clip.check("tip", sheet, baseline) == []
    # Another plan carries no such entry: the same picture is new there.
    assert clip.check("other", sheet, baseline) == [f"new: {key} ((60,196)->(118,224))"]
    # Fixed: the entry must go, so the list only shrinks.
    fixed = _sheet(tmp_path, ("From the front, 2.6 px/mm: the block", _TIP_BLOCK.replace('y1="196"', 'y1="200"')))
    assert clip.check("tip", fixed, baseline) == [f"fixed, so remove it from picture-clip-baseline.toml: {key}"]


def test_the_repo_baseline_names_only_enrolled_plans_and_known_kinds():
    import tomllib

    import _process_plans

    with clip.BASELINE.open("rb") as handle:
        plans = tomllib.load(handle)["plans"]
    assert set(plans) <= set(_process_plans.enrolled_stems())
    for stem, entry in plans.items():
        assert entry["findings"], stem
        for key in entry["findings"]:
            kind, picture, text = key.split(" | ", 2)
            assert kind in {"CLIP", "TEXT", "LEADER"} and picture and text, key
