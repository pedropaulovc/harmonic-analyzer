"""Measuring-stick stop plate (MHA-MS-03): the model frame its feature export cites.

Feature-export only (export_features): no native build imports this module.
The plate's dimensions live in ``ms_stop_spec``, shared with its stop block
(MHA-MS-02), and ``build_ms_stop_plate`` builds it in that frame:

- Origin: the corner where the LOCATING END (X = 0), the LOCATING EDGE
  (Y = 0) and the face that seats on the MHA-MS-02 mating face (Z = 0) meet.
- +X runs along the stick, from the locating end to the far end (X = .84).
- +Y runs from the locating edge (Y = 0) up to the roof edge (Y = .56); the
  two .04 x 45 deg chamfers break the roof edge's corners (X = 0 and X = .84
  at Y = .56), matching the block's roof chamfers.
- -Z runs through the .040 sheet thickness, from the seating face (Z = 0) to
  the outer face (Z = -.040).
- The two #2 close clearance holes run through Z from the outer face.
"""
