"""Offline contracts for the 64T against the v36 MHA-016's north side
(crank_boss_rim) and its SolidWorks positive control (gear64_post_measure).

The collar still seats the 64T's south face after its northward growth to
T120. Every post feature holds FLOOR_CLEARANCE_MM at print-worst, independent
of the northward face-width band.
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import cone_gear_shaft_spec as shaft
import cone_pivot_post_spec as post
import crank_boss_rim as rim
import crank_drive_gear_spec as gear64
import gear64_post_measure

FEATURES = {"crank boss", "head", "body", "cone boss end"}
SEATED = rim.seated_gear_offset()


def test_a_collar_thinned_past_the_margin_fails_the_boss_floor() -> None:
    # CollarWidth prints .XXX, so a single 0.001 step does NOT consume the
    # ~0.236 mm spare. A geometrically meaningful reduction does.
    thin = rim.THINNER_COLLAR
    new_offset = rim.seated_gear_offset(collar_thickness=thin)
    assert rim.THINNER_COLLAR_CLEARANCE < rim.FLOOR_CLEARANCE_MM
    assert "crank boss" in rim.worst_shortfalls(new_offset, collar_thickness=thin)
    assert rim.COLLAR_MARGIN_MM > 0.001


def test_the_seated_south_face_holds_the_floor_everywhere() -> None:
    worst = rim.clearances(gear_offset=SEATED)
    assert set(worst) == FEATURES
    assert rim.worst_shortfalls(SEATED) == {}
    assert min(worst, key=worst.get) == "crank boss"
    assert worst["crank boss"] == pytest.approx(0.486, abs=2e-3)
    assert gear64.FACE_WIDTH == pytest.approx(7.2113)
    assert gear64.DRAWING_PRECISION_BY_NAME["FaceWidth"] == 4


def test_the_floor_is_the_ruled_quarter_millimetre() -> None:
    assert rim.FLOOR_CLEARANCE_MM == 0.25


def test_the_64t_station_is_the_collar_stack() -> None:
    """#916 (Main's ruling (b), 2026-09-27): the 64T is set against MHA-014's
    thrust collar, which bears on the cone boss's north end; toward the post it
    moves by the boss end long (ConeBossLen's .XX row, half per end) and the
    collar thin (CollarWidth's row).  The two butts are closed nominally."""
    boss_end = rim._row(post.DRAWING_PRECISION_BY_NAME["ConeBossLen"]) / 2.0
    collar = rim._row(shaft.DRAWING_PRECISION_BY_NAME["CollarWidth"])
    assert rim.GEAR64_STATION_TOWARD_POST == pytest.approx(boss_end + collar)
    assert rim.collar_contacts(SEATED) == pytest.approx(0.0, abs=1e-9)
    with pytest.raises(ValueError, match="butts are open"):
        rim.clearances(gear_offset=SEATED + 0.1)


def test_the_face_width_band_never_moves_the_seated_south_face(monkeypatch) -> None:
    """The face-width band extends north; the entire post proof is invariant."""
    before = rim.clearances(gear_offset=SEATED)
    monkeypatch.setattr(gear64, "FACE_WIDTH_BAND", (5.0, -5.0))
    assert rim.clearances(gear_offset=SEATED) == pytest.approx(before, abs=1e-9)


@pytest.mark.parametrize(
    "term",
    ["CRANK_BOSS_NORTH", "CRANK_BOSS_GROWTH", "GEAR64_STATION_TOWARD_POST", "GEAR_TIP_GROWTH"],
)
def test_each_crank_boss_term_costs_margin(monkeypatch, term: str) -> None:
    """Every print-worst term on the governing stack is live: without it the
    crank boss reads farther."""
    booked = rim.clearances(gear_offset=SEATED)["crank boss"]
    monkeypatch.setattr(rim, term, 0.0)
    assert rim.clearances(gear_offset=SEATED)["crank boss"] > booked + 1e-3


def test_the_low_end_of_the_spacing_band_governs_the_boss(monkeypatch) -> None:
    """A lower crank axis sinks the boss deeper into the tip's sweep, so the
    band's low end (0, the nominal) is the worst one, and it is taken."""
    booked = rim.clearances(gear_offset=SEATED)["crank boss"]
    monkeypatch.setattr(rim, "CRANK_AXIS_Y_BAND", (rim.CRANK_AXIS_Y_BAND[-1],))
    assert rim.clearances(gear_offset=SEATED)["crank boss"] > booked + 1e-3


def test_the_coupled_cone_boss_end_is_the_collar_at_its_low_limit(monkeypatch) -> None:
    """The boss end rides with the gear through the collar, so whatever the
    station term, the worst air is the collar at its low limit."""
    low = shaft.COLLAR_THICKNESS - rim.COLLAR_WIDTH_SHORT
    for term in (0.0, rim.GEAR64_STATION_TOWARD_POST, 1.0):
        monkeypatch.setattr(rim, "GEAR64_STATION_TOWARD_POST", term)
        worst = rim.clearances(gear_offset=SEATED)
        assert worst["cone boss end"] == pytest.approx(low, abs=1e-3), term


def test_the_body_is_a_normal_distance_flush_with_the_cone_boss_end() -> None:
    """Where the tilted south face is the near surface the body reads the
    face's distance from the Ø42 body's tangent line, flush with the cone
    boss end (BLOCK_DIA == CONE_BOSS_LENGTH)."""
    nominal = rim.clearances(gear_offset=SEATED, worst=False)
    south = SEATED - gear64.FACE_WIDTH / 2.0
    assert nominal["body"] == pytest.approx(south - post.BLOCK_DIA / 2.0, abs=1e-3)
    assert nominal["body"] == pytest.approx(nominal["cone boss end"], abs=1e-3)


def test_past_a_cylinder_s_height_band_the_distance_runs_to_its_edge() -> None:
    """Below the head's lower edge the head is still there, at its edge
    circle: never read as infinitely far."""
    band = (10.0, 20.0)
    below = (0.0, 9.0, 23.0)  # 1.0 below the band, 3.0 radially outside r 20
    assert rim._post_cylinder(below, band, 20.0) == pytest.approx((3.0**2 + 1.0**2) ** 0.5)
    beside = (0.0, 15.0, 23.0)
    assert rim._post_cylinder(beside, band, 20.0) == pytest.approx(3.0)


# --- gear64_post_measure: the SolidWorks positive control ---------------------


def _measured(monkeypatch: pytest.MonkeyPatch, near_post_frame, distance_mm: float) -> dict:
    """Run gear64_post_measure against a fake ClosestDistance (makepy's
    convention: retval first, then the two [out] points, in metres)."""
    origin = (100.0, 50.0, -20.0)
    post_point = tuple((c + o) / 1000.0 for c, o in zip(near_post_frame, origin, strict=True))

    class Model:
        def ClosestDistance(self, a, b):
            return (distance_mm / 1000.0, (0.0, 0.0, 0.0), post_point)

        def GetComponentByName(self, name):
            return name

    monkeypatch.setattr(gear64_post_measure, "_early_bound", lambda obj, iface: Model())
    return gear64_post_measure.measure(
        SimpleNamespace(currentModel=object()), post_origin=origin, gear_offset=SEATED
    )


def _on_boss_face() -> tuple[float, float, float]:
    return (3.0, rim.CRANK_AXIS_Y - 5.0, post.CRANK_BOSS_NORTH_FACE)


def test_the_cross_check_names_the_feature_it_lands_on(monkeypatch) -> None:
    nominal = rim.clearances(gear_offset=SEATED, worst=False)
    record = _measured(monkeypatch, _on_boss_face(), nominal["crank boss"] + 0.1)
    assert record["measured_feature"] == "crank boss"
    assert record["predicted_feature"] == "crank boss"
    assert record["predicted_mm"] == pytest.approx(nominal["crank boss"], abs=1e-4)


def test_a_flush_tie_names_both_features() -> None:
    end = post.CONE_BOSS_LENGTH / 2.0
    on_pad_rim = (end * rim.SIN_I, post.CONE_BOSS_DIA / 2.0, end * rim.COS_I)
    assert set(gear64_post_measure.post_features_at(on_pad_rim)) == {"cone boss end", "body"}


def test_a_point_off_every_feature_is_unclassified() -> None:
    assert gear64_post_measure.post_features_at((0.0, 0.0, 60.0)) == ("unclassified",)


def test_the_cross_check_fails_when_the_gear_is_nearer(monkeypatch) -> None:
    """Nearer than the envelope by more than the limit: the analytic model
    misses material, so the build stops; within it, it passes."""
    limit = gear64_post_measure.UNDERCUT_LIMIT_MM
    predicted = _measured(monkeypatch, _on_boss_face(), 2.0)["predicted_mm"]
    with pytest.raises(RuntimeError, match="misses real material"):
        _measured(monkeypatch, _on_boss_face(), predicted - limit - 0.01)
    assert _measured(monkeypatch, _on_boss_face(), predicted - limit + 0.01)["delta_mm"] < 0.0


def test_the_cross_check_span_carries_every_feature_and_the_governing_one(monkeypatch) -> None:
    """The leaf's trace answers the whole stack without its console log."""
    spans: dict[str, dict] = {}

    @contextmanager
    def span(name: str, **attributes):
        recorded = spans.setdefault(name, dict(attributes))
        yield SimpleNamespace(set_attribute=recorded.__setitem__)

    monkeypatch.setattr(gear64_post_measure._telemetry, "span", span)
    record = _measured(monkeypatch, _on_boss_face(), 2.0)
    attributes = spans["verify.gear64_post_distance"]
    for key in ("measured_mm", "measured_feature", "predicted_mm", "predicted_feature", "delta_mm"):
        assert attributes[f"gear64_post.{key}"] == record[key]
    worst = rim.clearances(gear_offset=SEATED)
    for name in FEATURES:
        slug = name.replace(" ", "_")
        assert attributes[f"gear64_post.print_worst.{slug}"] == pytest.approx(worst[name], abs=1e-4)
        assert f"gear64_post.nominal.{slug}" in attributes
    assert attributes["gear64_post.print_worst_governing"] == "crank boss"
