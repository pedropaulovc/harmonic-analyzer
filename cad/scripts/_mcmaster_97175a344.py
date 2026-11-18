r"""Pure 97175A344 pull-out dowel dimensions; isolate this SKU's cache inputs.

McMaster 97175A344: pull-out dowel pin, high-strength 4140 alloy steel, 3/8 in
diameter, 3/4 in long, tapped 10-32 in one end, diameter +0.0001 to +0.0003 in
over nominal, Rockwell C47 minimum, ASME B18.8.2, 14,300 lbf double shear,
$3.81 each (https://www.mcmaster.com/97175A344/, read live 2026-11-12). The
page gives no tapped depth; ASME B18.8.2's 3/8 pull-out dowel taps 10-32 to a
full-thread depth of .255 in minimum (HVH Industrial pull-out dowel data
sheet, https://hvhindustrial.com/storage/pdfs/30_Dowel_Pin_Pull_Out.pdf, read
2026-11-12), which ``FULL_THREAD_DEPTH_MIN`` carries. Not vented: it is
pressed in a through hole. No vendor model was fetched.
"""

MM_PER_IN = 25.4

PART_NO = "97175A344"
DIA = 0.375 * MM_PER_IN  # nominal 3/8
DIA_BAND_IN = (0.0001, 0.0003)  # over nominal, the catalogue's
LENGTH = 0.75 * MM_PER_IN
THREAD = "#10-32"
THREAD_MAJOR = 0.190 * MM_PER_IN
THREAD_PITCH = MM_PER_IN / 32.0
FULL_THREAD_DEPTH_MIN = 0.255 * MM_PER_IN  # ASME B18.8.2, 3/8 pull-out
PRICE_EACH_USD = 3.81
