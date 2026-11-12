r"""Pure 92141A011 washer dimensions; isolate this SKU's cache inputs.

McMaster 92141A011: 18-8 stainless steel general-purpose flat washer for a
No. 10 screw, ID 0.203 in, OD 0.438 in, thickness 0.017 to 0.047 in, hardness
not rated, $3.79 per pack of 100 (https://www.mcmaster.com/92141A011/, read
live 2026-11-12). No diameter band is given. No vendor model was fetched.
"""

MM_PER_IN = 25.4

PART_NO = "92141A011"
ID = 0.203 * MM_PER_IN
OD = 0.438 * MM_PER_IN
THICKNESS_MIN = 0.017 * MM_PER_IN
THICKNESS_MAX = 0.047 * MM_PER_IN
# The catalogue range's nominal, the modelled washer.
MODEL_THICKNESS = 0.032 * MM_PER_IN
PACK_QUANTITY = 100
