r"""LeverWire member contract of sh-vn-music-wire (MHA-SH-VN-56).

PURE DATA, no SolidWorks/COM imports. Its computed endpoints/yoke remain in
``sh_vn_music_wire_lever_geom``; layout consumers import that drawing-free
solver directly so BOM prose stays out of their geometry recipe closures.

The wire is purchased McMaster-Carr 9666K142 music wire (0.008 in, modelled
at that size on the Ø0.8 lane's centreline). The package drawing
``draw_sh_vn_music_wire`` prints only the supplier wire diameter; this member's
straight rest run is installed geometry, not a purchase dimension.
"""

from __future__ import annotations

from _mcmaster_9666k142 import DIA_IN

# The catalogue size (.008).
BOM_DESCRIPTION = f"LEVER WIRE, DIA {f'{DIA_IN:.3f}'.removeprefix('0')} IN"

# The balloon ring's station, as a fraction of the run from the drum end
# (build_sh_vn_music_wire.BalloonRingSplit): mid-run, on the free span between
# the wheel rim and the fixture, where MHA-MG-00's finished view balloons the
# wire. Shared so the drawing's balloon anchor and the build agree.
BALLOON_RING_FRACTION = 0.5
