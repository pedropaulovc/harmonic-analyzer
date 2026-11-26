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
    assert clip.text_width(
        "(schematic; the bar's ends run off the page)", 1000
    ) == pytest.approx(19255.7, abs=1)
    assert clip.text_width("Ø.196–.200 × 30° −Y", 1000) == pytest.approx(9407, abs=1)
    assert clip.text_width("X0, the left edge", 1000, bold=True) == pytest.approx(
        7669, abs=1
    )


def test_a_leader_through_its_own_label_is_found(tmp_path):
    found = clip.findings(
        _sheet(tmp_path, ("From the front, 2.6 px/mm: the block", _TIP_BLOCK))
    )
    assert [f.key for f in found] == [
        "LEADER | From the front, 2.6 px/mm: the block | on the vise bed"
    ]


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
    assert (
        clip.findings(_sheet(tmp_path, ("Picture key: removed this setup", key))) == []
    )


def test_the_baseline_admits_listed_findings_and_refuses_new_or_fixed_ones(tmp_path):
    sheet = _sheet(tmp_path, ("From the front, 2.6 px/mm: the block", _TIP_BLOCK))
    key = "LEADER | From the front, 2.6 px/mm: the block | on the vise bed"
    baseline = tmp_path / "picture-clip-baseline.toml"
    baseline.write_text(f'[plans.tip]\nfindings = ["{key}"]\n', encoding="utf-8")
    assert clip.check("tip", sheet, baseline) == []
    # Another plan carries no such entry: the same picture is new there.
    assert clip.check("other", sheet, baseline) == [f"new: {key} ((60,196)->(118,224))"]
    # Fixed: the entry must go, so the list only shrinks.
    fixed = _sheet(
        tmp_path,
        (
            "From the front, 2.6 px/mm: the block",
            _TIP_BLOCK.replace('y1="196"', 'y1="200"'),
        ),
    )
    assert clip.check("tip", fixed, baseline) == [
        f"fixed, so remove it from picture-clip-baseline.toml: {key}"
    ]


def test_a_leader_between_samples_is_still_found(tmp_path):
    # dt_cone_swing_platform/diagrams/plate.svg lines 21-22: the leader is
    # inside the label's box only for u in (0.128, 0.149) of its length, between
    # two of the 41 points the first gate sampled. The crossing is exact now.
    svg = (
        f'<svg {_NS} viewBox="0 0 760 492" font-size="13">'
        '<text class="label" x="350" y="250">1-2-3 blocks under the plate (dashed)</text>'
        '<line class="leader" x1="346" y1="246" x2="385" y2="210"/>'
        "</svg>"
    )
    assert [f.key for f in clip.findings(_sheet(tmp_path, ("plate", svg)))] == [
        "LEADER | plate | 1-2-3 blocks under the plate (dashed)"
    ]


def test_a_segment_only_touching_a_box_does_not_cross_it():
    box = (10.0, 10.0, 20.0, 20.0, "t")
    assert not clip._crosses(0, 10, 30, 10, box)  # along the top edge
    assert not clip._crosses(0, 0, 10, 10, box)  # ending on the corner
    assert not clip._crosses(0, 20, 20, 0, box)  # through the corner only
    assert clip._crosses(0, 15, 30, 15, box)
    assert clip._crosses(15, 15, 15, 15.5, box)  # wholly inside
    assert not clip._crosses(0, 0, 9, 30, box)


@pytest.mark.parametrize(
    "leader",
    [
        '<polyline class="leader" points="10,60 60,60 60,5"/>',
        '<g class="leader"><polyline points="10,60 60,60 60,5"/></g>',
        '<polygon class="leader" points="10,60 60,60 60,5"/>',
        '<path class="leader" d="M10 60 H60 V5"/>',
        '<path class="leader" d="m10 60 h50 v-55"/>',
        '<g class="leader" transform="translate(10 0)"><path d="M0 60 L50 60 L50 5 Z"/></g>',
        # A cubic, a quadratic and an arc all bulging up through the label.
        '<path class="leader" d="M10 60 C10 0 110 0 110 60"/>',
        '<path class="leader" d="M10 60 Q60 -20 110 60"/>',
        '<path class="leader" d="M10 60 A50 50 0 0 1 110 60"/>',
        # Relative, its flags run together into the next number.
        '<path class="leader" d="M10 60 a50 50 0 01100 0"/>',
    ],
)
def test_leaders_drawn_as_polylines_and_paths_are_found(tmp_path, leader):
    svg = f'<svg {_NS} viewBox="0 0 200 100" font-size="13"><text x="40" y="20">LABEL</text>{leader}</svg>'
    found = {f.key for f in clip.findings(_sheet(tmp_path, ("leader", svg)))}
    assert found == {"LEADER | leader | LABEL"}


def test_a_path_not_reaching_the_label_passes(tmp_path):
    svg = (
        f'<svg {_NS} viewBox="0 0 200 100" font-size="13"><text x="40" y="20">LABEL</text>'
        '<g class="leader"><path d="M10 60 C10 40 110 40 110 60 Z"/></g></svg>'
    )
    assert clip.findings(_sheet(tmp_path, ("leader", svg))) == []


def test_each_tspan_line_is_its_own_box(tmp_path):
    # dt_cone_gear_tl_phasing_comb/diagrams/inspect.svg: "seat" over "line".
    svg = (
        f'<svg {_NS} viewBox="0 0 200 200" font-size="13">'
        '<text x="14" y="92"><tspan x="14" y="92">seat</tspan><tspan x="14" y="110">line</tspan></text>'
        '<line class="leader" x1="0" y1="106" x2="60" y2="106"/>'
        "</svg>"
    )
    assert [f.key for f in clip.findings(_sheet(tmp_path, ("comb", svg)))] == [
        "LEADER | comb | line"
    ]


def test_text_anchor_inherits_from_a_group_and_style(tmp_path):
    # Anchored at its end on x 200, the label lies left of x 200: inside.
    for group in ('<g text-anchor="end">', '<g style="text-anchor: end">'):
        svg = f'<svg {_NS} viewBox="0 0 210 50" font-size="13">{group}<text x="200" y="20">a long label here</text></g></svg>'
        assert clip.findings(_sheet(tmp_path, ("anchor", svg))) == [], group
    started = f'<svg {_NS} viewBox="0 0 210 50" font-size="13"><g><text x="200" y="20">a long label here</text></g></svg>'
    assert [f.kind for f in clip.findings(_sheet(tmp_path, ("anchor", started)))] == [
        "CLIP"
    ]


def test_a_picture_without_a_viewbox_uses_its_size_or_is_a_finding(tmp_path):
    sized = f'<svg {_NS} width="100" height="50" font-size="13"><text x="80" y="20">past the edge</text></svg>'
    assert [f.key for f in clip.findings(_sheet(tmp_path, ("sized", sized)))] == [
        "CLIP | sized | past the edge"
    ]
    bare = f'<svg {_NS} font-size="13"><text x="10" y="20">ok</text></svg>'
    (finding,) = clip.findings(_sheet(tmp_path, ("bare", bare)))
    assert finding.kind == "CLIP" and "no viewBox" in finding.text


def test_the_baseline_counts_repeats_and_names_pictures_by_their_whole_alt(tmp_path):
    # Two leaders across one label in one picture need two entries.
    twice = _TIP_BLOCK.replace(
        "</svg>", '<line class="leader" x1="40" y1="186" x2="80" y2="196"/></svg>'
    )
    # Two pictures sharing their first 60 characters keep apart by their whole alt.
    long = "Across the jaws from the front, 4 px/mm, K behind: the block "
    sheet = _sheet(tmp_path, (long + "east", twice), (long + "width", _TIP_BLOCK))
    keys = [f.key for f in clip.findings(sheet)]
    once = f"LEADER | {long}east | on the vise bed"
    assert keys == [once, once, f"LEADER | {long}width | on the vise bed"]
    baseline = tmp_path / "picture-clip-baseline.toml"
    baseline.write_text(
        f'[plans.tip]\nfindings = ["{once}", "{keys[2]}"]\n', encoding="utf-8"
    )
    assert clip.check("tip", sheet, baseline) == [f"new: {once} ((40,186)->(80,196))"]
    baseline.write_text(
        f'[plans.tip]\nfindings = ["{once}", "{once}", "{keys[2]}"]\n', encoding="utf-8"
    )
    assert clip.check("tip", sheet, baseline) == []


def test_pictures_sharing_an_alt_are_named_by_their_place_on_the_sheet(tmp_path):
    sheet = _sheet(
        tmp_path, ("same", _TIP_BLOCK), ("other", _TIP_BLOCK), ("same", _TIP_BLOCK)
    )
    assert [f.picture for f in clip.findings(sheet)] == [
        "same (picture 1)",
        "other",
        "same (picture 3)",
    ]


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
