"""Measuring-stick stop block (MHA-MS-02): the model frame its feature export cites.

Feature-export only (export_features): no native build imports this module.
The block's dimensions live in ``ms_stop_spec``, shared with its stop plate
(MHA-MS-03), and ``build_ms_stop_block`` builds it in that frame:

- Origin: the corner where the LOCATING END (X = 0), the LOCATING EDGE
  underside (Y = 0) and the MHA-MS-03 mating face (Z = 0) meet.
- +X runs along the stick, from the locating end to the far end (X = .84).
- +Y runs from the thumbscrew underside (Y = 0) up to the roof top (Y = .56);
  the two .04 x 45 deg chamfers break the roof's end edges (X = 0 and
  X = .84 at Y = .56).
- +Z runs into the block from the mating face (Z = 0) to the back face
  (Z = .48). The plate covers the mating face from Z = -.040 to 0.
- The rebate runs through X and opens into the mating face: Z from 0 to .330,
  under the .09 roof (Y = .56 - .09 down .134), its roof-to-back corner
  controlled at R.003 MAX (the square 1/8 in carbide end mill's corner).
- The #4-40 thumbscrew tap runs +Y from the underside through the floor into
  the rebate; the two #2-56 plate taps run +Z, blind, from the mating face.
"""
