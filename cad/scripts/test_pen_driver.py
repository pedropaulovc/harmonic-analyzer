"""The pen driver's equation chain, evaluated offline (#890). SolidWorks-free.

verify:kinematics sweeps a non-zero coefficient vector through the S1..S20
chain; HARMONIC_PEN_PROBE_DROP_LINK drops one link as an opt-in positive
control. These tests prove, without a seat, that the chain the driver writes
means the truth-model curve and that any droppable link moves the tip far past
the motion tolerance over the sweep.
"""

from __future__ import annotations

import math

import pytest

import _equation_eval as ev
import pen_driver
import truth_model
import verify

UNITLESS = ev.DocumentUnits.from_length_unit(0)  # the chain carries no units


def _tip_disp_mm(amps: list[float], theta_deg: float, dropped: int | None = None) -> float:
    """What the installed travel equation moves the tip, from rest, in mm."""

    def globals_at(crank_deg: float) -> dict[str, float]:
        values = {pen_driver.CRANK_GLOBAL: crank_deg}
        for name, expression in pen_driver.chain_links(amps, dropped):
            values[name] = ev.evaluate(expression, values.__getitem__, UNITLESS)
        return values

    def pen_y(crank_deg: float) -> float:
        return truth_model.magnify() * globals_at(crank_deg)["S20"]

    rest = pen_driver.rest_crank_deg()
    return pen_driver.scale_mm_per_unit(amps) * (pen_y(theta_deg) - pen_y(rest))


def test_the_chain_sums_every_harmonic() -> None:
    links = pen_driver.chain_links(truth_model.coefficients("square"))
    assert [name for name, _ in links] == [f"S{i}" for i in range(1, 21)]
    assert links[0][1].startswith("0 ")
    assert all(f'"S{i}" ' in links[i][1] for i in range(1, 20))


@pytest.mark.parametrize("preset", ["square", "sawtooth", "fundamental"])
def test_the_chain_means_the_truth_model(preset: str) -> None:
    amps = truth_model.coefficients(preset)
    for theta in verify._MOTION_SWEEP_DEG:
        want = pen_driver.expected_tip_disp_mm(math.radians(theta), amps)
        assert _tip_disp_mm(amps, theta) == pytest.approx(want, abs=1e-9)


def test_the_probe_preset_moves_the_tip() -> None:
    # A vacuous probe (all a_j = 0, the neutral config) would pass any chain.
    amps = truth_model.coefficients(verify._MOTION_PROBE_PRESET)
    stroke = max(abs(_tip_disp_mm(amps, t)) for t in verify._MOTION_SWEEP_DEG)
    assert stroke > 100 * verify._MOTION_TOL_MM


def test_a_dropped_link_writes_a_zero_term() -> None:
    amps = truth_model.coefficients("square")
    links = dict(pen_driver.chain_links(amps, dropped=20))
    assert links["S20"] == '"S19" + 0'
    assert "cos(" in links["S19"]


def test_every_droppable_link_breaks_the_probe_sweep() -> None:
    """HARMONIC_PEN_PROBE_DROP_LINK must turn probe-traces-truth red."""
    amps = truth_model.coefficients(verify._MOTION_PROBE_PRESET)
    for link, amp in enumerate(amps, start=1):
        if not amp:
            continue
        worst = max(
            abs(
                _tip_disp_mm(amps, theta, dropped=link)
                - pen_driver.expected_tip_disp_mm(math.radians(theta), amps)
            )
            for theta in verify._MOTION_SWEEP_DEG
        )
        assert worst > 10 * verify._MOTION_TOL_MM, f"S{link}"


@pytest.mark.parametrize(("value", "link"), [("", None), ("20", 20), (" 2 ", 2)])
def test_the_drop_link_diagnostic_reads_its_flag(
    monkeypatch: pytest.MonkeyPatch, value: str, link: int | None
) -> None:
    monkeypatch.setenv(verify.PEN_PROBE_DROP_LINK_ENV, value)
    assert verify._pen_probe_dropped_link() == link


@pytest.mark.parametrize("value", ["0", "21", "S20", "-1", "1"])
def test_the_drop_link_diagnostic_refuses_a_vacuous_link(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    # "1" is harmonic 20, even, so the square preset gives it no amplitude.
    monkeypatch.setenv(verify.PEN_PROBE_DROP_LINK_ENV, value)
    with pytest.raises(ValueError):
        verify._pen_probe_dropped_link()


def test_no_link_writes_a_double_operator_or_exponent() -> None:
    # The SOLIDWORKS parser rejects both; tiny amplitudes are where they appear.
    amps = [(-1) ** j * 1e-13 * j for j in range(20)]
    for _, expression in pen_driver.chain_links(amps):
        assert "e-" not in expression and "+ -" not in expression and "- -" not in expression
        ev.to_python(expression, UNITLESS)
