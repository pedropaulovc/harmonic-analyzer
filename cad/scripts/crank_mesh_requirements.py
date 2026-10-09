"""Source-owned crossed-crank stock-form requirements, not measured results.

The retained 0.62 screen is a supported-branch coverage floor, not an ideal
involute contact ratio. Main permits non-carrying-pair separation but requires
continuous carrying contact with no uncovered phase. The 0.005 mm handover
allowance is Main's conservative fallback, not a claimed elastic deflection.
"""

STOCK_FORM_COVERAGE_MIN = 0.62
UNCOVERED_PHASE_MAX_RAD = 0.0
HANDOVER_JUMP_MAX_MM = 0.005
ROW_ENGAGEMENT_MIN = 0.85
POSITIVE_BACKLASH_MIN_MM = 0.0
