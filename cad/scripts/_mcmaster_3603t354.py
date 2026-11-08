"""Pure 3603T354 #18 solid brass single jack chain dimensions (mm).

McMaster "Jack Chain, Brass, Trade Size 18", read live on 2026-11-08: listed
inside length 0.39 in, thickness 0.05 in; its 2-D PDF prints the wire
.047 in.  McMaster publishes no eye inside diameter.  The modelled eye is the
Peco Fasteners #18 single-jack spec sheet's "Min. Eye Diameter B" (.115 in);
the Eastools #18 table's inside width (.110 in) is the smallest published eye
and McMaster's reference STEP's round eye (.1535 in; its other eye is a
.138 x .0715 lens) the largest.  STEP SHA-256
d8396f4e411f91cf8e9198d30bdf8b7a4e1346b97d022d81a2f007995f24152d.

Kept free of any project spec import, so the crank arm's spec and the keeper
chain's spec can both read it.
"""

PART_NO = "3603T354"
IN = 25.4

WIRE_DIA = 0.047 * IN
# NACM: the inside length is the chain pitch, link centre to link centre.
INSIDE_LENGTH = 0.39 * IN
EYE_ID = 0.115 * IN
EYE_ID_MIN = 0.110 * IN
EYE_ID_MAX = 0.1535 * IN
STEP_SHA256 = "d8396f4e411f91cf8e9198d30bdf8b7a4e1346b97d022d81a2f007995f24152d"


def eye_centre_spacing(eye_id: float) -> float:
    """Eye-centre spacing within a link: taut perpendicular eyes interlock one
    inside diameter apart, so the inside length is the spacing plus the ID."""
    return INSIDE_LENGTH - eye_id
