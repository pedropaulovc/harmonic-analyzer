"""The cone-train frame has ONE definition: drive_train_frame_geom.

build_drive_train_assembly places the train on it and build_paper_drive_assembly
pins its chain layout to the crank axis it derives. Both must read the module's
own objects -- a second copy in either script is exactly the drift this file
exists to catch (the paper-drive used to reach X_CRANK/Y_CRANK by importing the
whole drive-train assembly script, which folded that script into its recipe).
"""

from __future__ import annotations

import math

import pytest

import _chain
import build_drive_train_assembly as drive
import build_paper_drive_assembly as paper
import drive_train_frame_geom as frame

# Every name the drive-train takes from the frame module, the crank axis, the
# station datum and the whole incline set included.
FRAME_NAMES = (
    "Y_BASE_TOP",
    "Y_DRIVE",
    "DP_TRAIN",
    "ADDENDUM",
    "WORKING_DEPTH",
    "RADIUS_STEP",
    "CONE_T120_PITCH_R",
    "Z_PITCH",
    "X_DRUM",
    "Z_DRUM0",
    "SIN_I",
    "COS_I",
    "TAN_I",
    "SEC_I",
    "INCLINE_DEG",
    "SEAT_PITCH",
    "CONE_FACE",
    "CONE_FACE_STATION_REFERENCE",
    "DRUM_FACE",
    "DRUM_TIP_X",
    "PEN_EDGE_SLACK",
    "PEN_MID",
    "X_PITCH",
    "cone_seat",
    "SHAFT_T120_STATION",
    "CONE_ORIGIN",
    "cone_station",
    "POST_STATION",
    "X_CRANK",
    "Y_CRANK",
)


@pytest.mark.parametrize("name", FRAME_NAMES)
def test_drive_train_reads_the_frame_module_object(name: str) -> None:
    assert getattr(drive, name) is getattr(frame, name), (
        f"build_drive_train_assembly.{name} is a second definition; import it"
        " from drive_train_frame_geom"
    )


def test_paper_drive_reads_the_frame_crank_axis() -> None:
    assert paper.X_CRANK is frame.X_CRANK
    assert paper.Y_CRANK is frame.Y_CRANK


def test_chain_crank_centre_is_the_mirrored_frame_crank_axis() -> None:
    # Offline twin of build_paper_drive_assembly._assert_chain_layout, which
    # only runs inside a build.
    assert _chain.CRANK_CENTRE == (-frame.X_CRANK, frame.Y_CRANK)


def test_crank_axis_follows_its_derivation() -> None:
    assert frame.X_CRANK == frame.cone_station(frame.POST_STATION)[0]
    assert frame.SHAFT_T120_STATION == 25.0 + frame.CONE_FACE_STATION_REFERENCE / 2.0


def test_incline_set_is_one_consistent_angle() -> None:
    assert frame.SIN_I == frame.RADIUS_STEP / frame.Z_PITCH
    assert math.isclose(frame.SIN_I**2 + frame.COS_I**2, 1.0, abs_tol=1e-15)
    assert math.isclose(frame.TAN_I, frame.SIN_I / frame.COS_I, abs_tol=1e-15)
    assert math.isclose(frame.SEC_I, 1.0 / frame.COS_I, abs_tol=1e-15)
    assert math.isclose(
        frame.INCLINE_DEG, math.degrees(math.asin(frame.SIN_I)), abs_tol=1e-12
    )
    assert math.isclose(frame.SEAT_PITCH, frame.Z_PITCH * frame.COS_I, abs_tol=1e-15)
