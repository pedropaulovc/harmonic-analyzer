"""Historical exact source-callout inventory at the stated baseline.

Imported by the fleet regression so check:recipe fingerprints this evidence.
This is test data, never a production source of callout values.
"""

INVENTORY = {
    "baseline": "51a3aecedd1f9c4618fa0bbffb0b528a50afebf1",
    "calls": [
        {
            "drawing": "draw_crank_arm",
            "builder": "build_crank_arm",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "ShaftBoreDia",
                    "text": "THRU - REAM 3/8 IN",
                    "owners": ["ShaftBoreProfile"],
                },
                {
                    "dimension": "DimpleDia",
                    "text": "0.5 DEEP",
                    "owners": ["DimpleProfile"],
                },
            ],
        },
        {
            "drawing": "draw_cone_tip_bushing",
            "builder": "build_cone_tip_bushing",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "BoreDiaDim",
                    "text": "1/32 IN THRU",
                    "owners": ["BoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_fulcrum_shaft",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_pivot_shaft",
            "expr": "{n: t for n, t in DIMENSION_CALLOUTS.items() if n in FRONT_KEEP}",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_pivot_shaft",
            "expr": "{n: t for n, t in DIMENSION_CALLOUTS.items() if n in RIGHT_KEEP}",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_pinion_lift_rod",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_pinion_lift_rod",
            "expr": "RIGHT_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_cylinder_gear_shaft",
            "expr": "{n: t for n, t in DIMENSION_CALLOUTS.items() if n in END_KEEP}",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_cylinder_gear_shaft",
            "expr": "{n: t for n, t in DIMENSION_CALLOUTS.items() if n in "
            "PROFILE_KEEP}",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_cone_lock_knob",
            "builder": "build_cone_lock_knob",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "StudDia",
                    "text": "1/4-20 UNC-2A",
                    "owners": ["StudProfile"],
                }
            ],
        },
        {
            "drawing": "draw_pinion_arbor",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_pinion_arbor",
            "builder": "build_pinion_arbor",
            "expr": "CAP_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "CapSagDim",
                    "text": "SR7.27 CROWN",
                    "owners": ["BackCapProfile"],
                }
            ],
        },
        {
            "drawing": "draw_transgear_stub",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_wheel_axle",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_column_clamp_front",
            "builder": "build_column_clamp_front",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "BoreDia",
                    "text": "THRU\nSLIP FIT ON <MOD-DIAM>25.4 COLUMN",
                    "owners": ["BoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_pinion_pivot_block",
            "builder": "build_pinion_pivot_block",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "PivotBoreDia",
                    "text": "THRU - REAM 1/4 IN",
                    "owners": ["BlockProfile"],
                },
                {
                    "dimension": "LiftBoreDia",
                    "text": "THRU - REAM 1/4 IN",
                    "owners": ["BlockProfile"],
                },
            ],
        },
        {
            "drawing": "draw_pen_v_block",
            "builder": "build_pen_v_block",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {"dimension": "Bore0Dia", "text": "2X THRU", "owners": ["BoreProfile"]},
                {
                    "dimension": "ScrewHoleDiaDim",
                    "text": "THRU",
                    "owners": ["ScrewHoleProfile"],
                },
                {
                    "dimension": "Chamfer2dx",
                    "text": "X 45 DEG, 2 PLACES",
                    "owners": ["OutlineProfile"],
                },
            ],
        },
        {
            "drawing": "draw_pen_rod",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_pen_rod",
            "expr": "TOP_DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_magnifying_lever",
            "builder": "build_magnifying_lever",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "DomeRadius",
                    "text": "FULL R, BOTH ENDS - Ø6 ROD",
                    "owners": ["RodProfile"],
                },
                {
                    "dimension": "RightDomeCentre",
                    "text": "TO FAR DOME CENTRE",
                    "owners": ["RodProfile"],
                },
            ],
        },
        {
            "drawing": "draw_magnifying_vertical_rod",
            "builder": "build_magnifying_vertical_rod",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "DomeRadius",
                    "text": "FULL R, BOTH ENDS - Ø5 ROD",
                    "owners": ["RodProfile"],
                },
                {
                    "dimension": "RightDomeCentre",
                    "text": "TO FAR DOME CENTRE",
                    "owners": ["RodProfile"],
                },
            ],
        },
        {
            "drawing": "draw_magnifying_clamp",
            "builder": "build_magnifying_clamp",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "LeverBoreDiaDim",
                    "text": "THRU - SLIP FIT Ø6 ROD",
                    "owners": ["LeverBoreProfile"],
                },
                {
                    "dimension": "RodBoreDiaDim",
                    "text": "THRU - SLIP FIT Ø5 ROD",
                    "owners": ["RodBoreProfile"],
                },
            ],
        },
        {
            "drawing": "draw_knife_mount",
            "builder": "build_knife_mount",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {"dimension": "BoreDia", "text": "THRU", "owners": ["BoreProfile"]}
            ],
        },
        {
            "drawing": "draw_magnifying_wheel",
            "builder": "build_magnifying_wheel",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "BoreDiaDim",
                    "text": "THRU - REAM",
                    "owners": ["BoreProfile"],
                },
                {
                    "dimension": "SpokeWidthDim",
                    "text": "6X SPOKE",
                    "owners": ["SpokeProfile"],
                },
            ],
        },
        {
            "drawing": "draw_magnifying_bracket",
            "builder": "build_magnifying_bracket",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "ArmWidth",
                    "text": "ARM WIDTH",
                    "owners": ["ArmProfile"],
                },
                {
                    "dimension": "ArmDepth",
                    "text": "ARM LENGTH",
                    "owners": ["ArmProfile"],
                },
                {
                    "dimension": "FlangeWidth",
                    "text": "FLANGE WIDTH",
                    "owners": ["FlangeProfile"],
                },
                {
                    "dimension": "FlangeDepth",
                    "text": "FLANGE DEPTH",
                    "owners": ["FlangeProfile"],
                },
            ],
        },
        {
            "drawing": "draw_connecting_rod",
            "builder": "build_connecting_rod",
            "expr": "{'StrapBoreDia': 'BORE'}",
            "location": "below",
            "rows": [
                {
                    "dimension": "StrapBoreDia",
                    "text": "BORE",
                    "owners": ["StrapBoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_pinion_bracket",
            "builder": "build_pinion_bracket",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "PivotBoreDia",
                    "text": "PIVOT BORE; THRU - REAM",
                    "owners": ["StrapProfile"],
                },
                {
                    "dimension": "ArborBoreDia",
                    "text": "ARBOR BORE; THRU - REAM",
                    "owners": ["StrapProfile"],
                },
                {
                    "dimension": "PinSeatCy",
                    "text": "PIN-SEAT AXIS ABOVE PIVOT-BORE AXIS",
                    "owners": ["PinSeatProfile"],
                },
                {
                    "dimension": "Depth",
                    "text": "ONE STRAP THICKNESS",
                    "owners": ["Strap"],
                },
                {
                    "dimension": "PinSeatDia",
                    "text": "H7; BLIND; FLAT BOTTOM\n"
                    "ENTRY ON THE STRAIGHT EDGE FACE\n"
                    "NEAREST THE PIVOT BORE",
                    "owners": ["PinSeatProfile"],
                },
                {
                    "dimension": "PinSeatCz",
                    "text": "FROM DATUM C",
                    "owners": ["PinSeatProfile"],
                },
                {
                    "dimension": "PinSeatDepth",
                    "text": "FULL-DIAMETER DEPTH",
                    "owners": ["PinSeat"],
                },
            ],
        },
        {
            "drawing": "draw_pinion_lever",
            "builder": "build_pinion_lever",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "HubBore",
                    "text": "FINAL REAM",
                    "owners": ["BarrelProfile"],
                },
                {
                    "dimension": "BoreDepth",
                    "text": "FULL-DIA DEPTH FROM B; FLAT BOTTOM",
                    "owners": ["Barrel"],
                },
                {
                    "dimension": "EndWall",
                    "text": "END WALL TO CROWN ROOT PLANE",
                    "owners": ["Wall"],
                },
                {
                    "dimension": "RodTipY",
                    "text": "FROM HUB AXIS",
                    "owners": ["RodProfile"],
                },
                {"dimension": "RodTipDia", "text": "AT TIP", "owners": ["RodProfile"]},
                {
                    "dimension": "GripHalfAngle",
                    "text": "GRIP HALF-ANGLE TO AXIS",
                    "owners": ["RodProfile"],
                },
                {
                    "dimension": "CapR",
                    "text": "SPHERICAL CROWN",
                    "owners": ["CapProfile"],
                },
            ],
        },
        {
            "drawing": "draw_pinion_cam",
            "builder": "build_pinion_cam",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "BoreDia",
                    "text": "FINAL REAM; THRU",
                    "owners": ["BoreProfile"],
                },
                {
                    "dimension": "CollarCy",
                    "text": "BOTH END FACES",
                    "owners": ["CollarProfile"],
                },
                {
                    "dimension": "BossProjection",
                    "text": "BEYOND DIA 10.32 OD",
                    "owners": ["SetPinBossProjection"],
                },
                {
                    "dimension": "BossCz",
                    "text": "A TO BOSS / TAP AXIS",
                    "owners": ["BossProfile"],
                },
            ],
        },
        {
            "drawing": "draw_pinion_cam_pin",
            "builder": "build_pinion_cam_pin",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {"dimension": "PinDia", "text": "FINAL SIZE", "owners": ["PinProfile"]},
                {
                    "dimension": "Depth",
                    "text": "SEATED FLAT END TO CROWN ROOT",
                    "owners": ["Pin"],
                },
                {"dimension": "CapR", "text": "OUTER CROWN", "owners": ["CapProfile"]},
            ],
        },
        {
            "drawing": "draw_pinion_pivot_shaft",
            "builder": "build_pinion_pivot_shaft",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "ShaftDia",
                    "text": "FINAL SIZE",
                    "owners": ["ShaftProfile"],
                },
                {
                    "dimension": "Depth",
                    "text": "CYLINDRICAL BODY\nBETWEEN CROWN ROOT CIRCLES",
                    "owners": ["Shaft"],
                },
            ],
        },
        {
            "drawing": "draw_pinion_handle",
            "builder": "build_pinion_handle",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "TubeId",
                    "text": "FINAL REAM",
                    "owners": ["TubeProfile"],
                },
                {"dimension": "GripLen", "text": "CYL. LENGTH", "owners": ["Grip"]},
                {"dimension": "TubeLen", "text": "BORE DEPTH", "owners": ["Tube"]},
                {"dimension": "RodSpan", "text": "OAL", "owners": ["Rod"]},
                {"dimension": "RodDia", "text": "PRESS ROD", "owners": ["RodProfile"]},
                {
                    "dimension": "RodHoleDia",
                    "text": "BODY HOLE; REAM THRU",
                    "owners": ["RodHoleProfile"],
                },
            ],
        },
        {
            "drawing": "draw_pinion_spring",
            "builder": "build_pinion_spring",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "FootLen",
                    "text": "TRUE LENGTH\nFREE END TO BEND TANGENCY",
                    "owners": ["SpringProfile"],
                },
                {
                    "dimension": "BendR",
                    "text": "INSIDE RADIUS",
                    "owners": ["SpringProfile"],
                },
                {
                    "dimension": "KinkR",
                    "text": "INSIDE RADIUS",
                    "owners": ["SpringProfile"],
                },
            ],
        },
        {
            "drawing": "draw_crank_handle",
            "builder": "build_crank_handle",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "PivotBoreDia",
                    "text": "THRU - REAM",
                    "owners": ["PivotBoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_cylinder_gear",
            "builder": "build_cylinder_gear",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "BoreDia",
                    "text": "THRU - REAM",
                    "owners": ["BoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_crank_drive_gear",
            "builder": "build_crank_drive_gear",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "BoreDia",
                    "text": "THRU - REAM",
                    "owners": ["BoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_crank_pinion",
            "builder": "build_crank_pinion",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "BoreDia",
                    "text": "THRU - REAM",
                    "owners": ["BoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_alignment_pinion",
            "builder": "build_alignment_pinion",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "ArborBoreDia",
                    "text": "THRU - REAM\nPRESS FIT",
                    "owners": ["ArborBoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_rack_pinion",
            "builder": "build_rack_pinion",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "BoreDia",
                    "text": "THRU - REAM",
                    "owners": ["BoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_transgear_feed_pinion",
            "builder": "build_transgear_feed_pinion",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "BoreDia",
                    "text": "THRU - REAM",
                    "owners": ["BoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_transgear_pinion",
            "builder": "build_transgear_pinion",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "BoreDia",
                    "text": "THRU - REAM",
                    "owners": ["BoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_cone_gear_shaft",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_cone_pivot_post",
            "builder": "build_cone_pivot_post",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "CrankBoreDia",
                    "text": "THRU",
                    "owners": ["CrankBoreProfile"],
                }
            ],
        },
        {
            "drawing": "draw_cone_tip_adjuster",
            "builder": "build_cone_tip_adjuster",
            "expr": "{name: text for name, text in DIMENSION_CALLOUTS.items() if name "
            "!= 'BodyDiaDim'}",
            "location": "below",
            "rows": [{"dimension": "CupDepth", "text": "DEEP", "owners": ["Cup"]}],
        },
        {
            "drawing": "draw_cone_tip_adjuster",
            "builder": "build_cone_tip_adjuster",
            "expr": "{'BodyDiaDim': DIMENSION_CALLOUTS['BodyDiaDim']}",
            "location": "above",
            "rows": [
                {
                    "dimension": "BodyDiaDim",
                    "text": "5/16-18 UNC-2A",
                    "owners": ["BodyProfile"],
                }
            ],
        },
        {
            "drawing": "draw_cone_tip_block",
            "builder": "build_cone_tip_block",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "PassageDiaDim",
                    "text": "THRU - CLEARANCE PASSAGE",
                    "owners": ["PassageProfile"],
                }
            ],
        },
        {
            "drawing": "draw_arbor_pedestal",
            "builder": "build_arbor_pedestal",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {"dimension": "BoreDia", "text": "THRU", "owners": ["BoreProfile"]}
            ],
        },
        {
            "drawing": "draw_crankshaft",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_fillister_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_fillister_screw",
            "builder": "build_fillister_screw",
            "expr": "SIDE_DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "ShankLg",
                    "text": "UNDERHEAD LENGTH",
                    "owners": ["Shank"],
                }
            ],
        },
        {
            "drawing": "draw_foot_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_bracket_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_clamp_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_slotted_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_lag_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_cone_pivot_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_cone_pivot_screw",
            "builder": "build_cone_pivot_screw",
            "expr": "SIDE_DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [
                {
                    "dimension": "ThreadLg",
                    "text": "#10-24 UNC-2A",
                    "owners": ["ThreadTail"],
                }
            ],
        },
        {
            "drawing": "draw_cone_tip_pinch_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_hanger_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_pen_set_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_swing_stop_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_thumb_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_frame_side_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_gooseneck_set_screw",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
        {
            "drawing": "draw_knife_hanger_stud",
            "expr": "DIMENSION_CALLOUTS",
            "location": "below",
            "rows": [],
        },
    ],
    "map_definitions": [
        {
            "drawing": "draw_crank_arm",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "ShaftBoreDia": "THRU - REAM 3/8 IN",\n'
                    '    "DimpleDia": "0.5 DEEP",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_cone_tip_bushing",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "BoreDiaDim": "1/32 IN THRU",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_cone_lock_knob",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "StudDia": f"{STUD_THREAD} UNC-2A",\n'
                    "}",
                    "dependencies": ["STUD_THREAD"],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_pinion_arbor",
            "spec_exists": True,
            "maps": [
                {
                    "name": "CAP_CALLOUTS",
                    "source": 'CAP_CALLOUTS = {"CapSagDim": f"SR{CAP_R:.2f} CROWN"}',
                    "dependencies": ["CAP_R"],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_column_clamp_front",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "BoreDia": "THRU\\nSLIP FIT ON '
                    '<MOD-DIAM>25.4 COLUMN",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_pinion_pivot_block",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "PivotBoreDia": "THRU - REAM 1/4 IN",\n'
                    '    "LiftBoreDia": "THRU - REAM 1/4 IN",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_pen_v_block",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "Bore0Dia": "2X THRU",\n'
                    '    "ScrewHoleDiaDim": "THRU",\n'
                    '    "Chamfer2dx": "X 45 DEG, 2 PLACES",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_magnifying_lever",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "DomeRadius": "FULL R, BOTH ENDS - Ø6 '
                    'ROD",\n'
                    '    "RightDomeCentre": "TO FAR DOME '
                    'CENTRE",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_magnifying_vertical_rod",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "DomeRadius": f"FULL R, BOTH ENDS - '
                    'Ø{ROD_DIA:g} ROD",\n'
                    '    "RightDomeCentre": "TO FAR DOME '
                    'CENTRE",\n'
                    "}",
                    "dependencies": ["ROD_DIA"],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_magnifying_clamp",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "LeverBoreDiaDim": "THRU - SLIP FIT Ø6 '
                    'ROD",\n'
                    '    "RodBoreDiaDim": "THRU - SLIP FIT Ø5 '
                    'ROD",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_knife_mount",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": 'DIMENSION_CALLOUTS = {\n    "BoreDia": "THRU",\n}',
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_magnifying_wheel",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "BoreDiaDim": "THRU - REAM",\n'
                    '    "SpokeWidthDim": "6X SPOKE",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_magnifying_bracket",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "ArmWidth": "ARM WIDTH",\n'
                    '    "ArmDepth": "ARM LENGTH",\n'
                    '    "FlangeWidth": "FLANGE WIDTH",\n'
                    '    "FlangeDepth": "FLANGE DEPTH",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_connecting_rod",
            "spec_exists": True,
            "maps": [],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_pinion_bracket",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "PivotBoreDia": "PIVOT BORE; THRU - '
                    'REAM",\n'
                    '    "ArborBoreDia": "ARBOR BORE; THRU - '
                    'REAM",\n'
                    '    "PinSeatCy": "PIN-SEAT AXIS ABOVE '
                    'PIVOT-BORE AXIS",\n'
                    '    "Depth": "ONE STRAP THICKNESS",\n'
                    '    "PinSeatDia": (\n'
                    '        "H7; BLIND; FLAT BOTTOM\\nENTRY ON '
                    'THE STRAIGHT EDGE FACE\\n"\n'
                    '        "NEAREST THE PIVOT BORE"\n'
                    "    ),\n"
                    '    "PinSeatCz": "FROM DATUM C",\n'
                    '    "PinSeatDepth": "FULL-DIAMETER DEPTH",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_pinion_lever",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "HubBore": "FINAL REAM",\n'
                    '    "BoreDepth": "FULL-DIA DEPTH FROM B; '
                    'FLAT BOTTOM",\n'
                    '    "EndWall": "END WALL TO CROWN ROOT '
                    'PLANE",\n'
                    '    "RodTipY": "FROM HUB AXIS",\n'
                    '    "RodTipDia": "AT TIP",\n'
                    '    "GripHalfAngle": "GRIP HALF-ANGLE TO '
                    'AXIS",\n'
                    '    "CapR": "SPHERICAL CROWN",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_pinion_cam",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "BoreDia": "FINAL REAM; THRU",\n'
                    '    "CollarCy": "BOTH END FACES",\n'
                    '    "BossProjection": f"BEYOND DIA '
                    '{CAM_OD:.2f} OD",\n'
                    '    "BossCz": "A TO BOSS / TAP AXIS",\n'
                    "}",
                    "dependencies": ["CAM_OD"],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_pinion_cam_pin",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "PinDia": "FINAL SIZE",\n'
                    '    "Depth": "SEATED FLAT END TO CROWN '
                    'ROOT",\n'
                    '    "CapR": "OUTER CROWN",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_pinion_pivot_shaft",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "ShaftDia": "FINAL SIZE",\n'
                    '    "Depth": "CYLINDRICAL BODY\\nBETWEEN '
                    'CROWN ROOT CIRCLES",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_pinion_handle",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "TubeId": "FINAL REAM",\n'
                    '    "GripLen": "CYL. LENGTH",\n'
                    '    "TubeLen": "BORE DEPTH",\n'
                    '    "RodSpan": "OAL",\n'
                    '    "RodDia": "PRESS ROD",\n'
                    '    "RodHoleDia": "BODY HOLE; REAM THRU",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_pinion_spring",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS: dict[str, str] = {\n"
                    '    "FootLen": "TRUE LENGTH\\nFREE END TO '
                    'BEND TANGENCY",\n'
                    '    "BendR": "INSIDE RADIUS",\n'
                    '    "KinkR": "INSIDE RADIUS",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_crank_handle",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "PivotBoreDia": "THRU - REAM",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_cylinder_gear",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    "    # The 9.525 +0.03/+0.05 reamed bore "
                    "against the arbor's\n"
                    "    # 9.525 +0.00/-0.02 journal guarantees "
                    "0.03..0.07 diametral clearance,\n"
                    "    # inside the project's 0.025..0.075 "
                    "shaft-in-bushing policy.\n"
                    '    "BoreDia": "THRU - REAM",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_crank_drive_gear",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    "    # Reamed slip fit on the crankshaft "
                    "journal (nominal-or-under, like the\n"
                    "    # arbor journals): min 0.03 diametral "
                    "clearance, inside the project's\n"
                    "    # 0.025..0.075 shaft-in-bushing policy. "
                    "Also settles which tolerance-block\n"
                    "    # row governs the bore (neither .XX "
                    "+/-0.51 nor DRILLED +0.10/0 -- the\n"
                    "    # model dimension's own limits do).\n"
                    '    "BoreDia": "THRU - REAM",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_crank_pinion",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    "    # Reamed slip fit on the crankshaft "
                    "journal (removable) (nominal-or-under, like "
                    "the\n"
                    "    # arbor journals): min 0.03 diametral "
                    "clearance, inside the project's\n"
                    "    # 0.025..0.075 shaft-in-bushing policy. "
                    "Also settles which tolerance-block\n"
                    "    # row governs the bore (neither .XX "
                    "+/-0.51 nor DRILLED +0.10/0 -- the\n"
                    "    # model dimension's own limits do).\n"
                    '    "BoreDia": "THRU - REAM",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_rack_pinion",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    "    # Reamed slip fit on the stud's turned "
                    "Ø5 front seat (nominal-or-under, like\n"
                    "    # the arbor journals): min 0.03 "
                    "diametral clearance, inside the project's\n"
                    "    # 0.025..0.075 shaft-in-bushing policy. "
                    "Also settles which tolerance-block\n"
                    "    # row governs the bore (neither .XX "
                    "+/-0.51 nor DRILLED +0.10/0 -- the\n"
                    "    # callout's own limits do).\n"
                    '    "BoreDia": "THRU - REAM",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_transgear_feed_pinion",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    "    # Reamed slip fit on the stud's turned "
                    "Ø5 front seat (nominal-or-under, like\n"
                    "    # the arbor journals): min 0.03 "
                    "diametral clearance, inside the project's\n"
                    "    # 0.025..0.075 shaft-in-bushing policy. "
                    "Also settles which tolerance-block\n"
                    "    # row governs the bore (neither .XX "
                    "+/-0.51 nor DRILLED +0.10/0 -- the\n"
                    "    # callout's own limits do).\n"
                    '    "BoreDia": "THRU - REAM",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_transgear_pinion",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    "    # Reamed slip fit on the knob shaft's "
                    "turned Ø5 seat (nominal-or-under, like\n"
                    "    # the arbor journals): min 0.03 "
                    "diametral clearance, inside the project's\n"
                    "    # 0.025..0.075 shaft-in-bushing policy. "
                    "Also settles which tolerance-block\n"
                    "    # row governs the bore (neither .XX "
                    "+/-0.51 nor DRILLED +0.10/0 -- the\n"
                    "    # callout's own limits do).\n"
                    '    "BoreDia": "THRU - REAM",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_cone_pivot_post",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": 'DIMENSION_CALLOUTS = {\n    "CrankBoreDia": "THRU",\n}',
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_cone_tip_adjuster",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "BodyDiaDim": f"{THREAD} UNC-2A",\n'
                    '    "CupDepth": "DEEP",\n'
                    "}",
                    "dependencies": ["THREAD"],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_cone_tip_block",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": "DIMENSION_CALLOUTS = {\n"
                    '    "PassageDiaDim": "THRU - CLEARANCE '
                    'PASSAGE",\n'
                    "}",
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_arbor_pedestal",
            "spec_exists": True,
            "maps": [
                {
                    "name": "DIMENSION_CALLOUTS",
                    "source": 'DIMENSION_CALLOUTS = {\n    "BoreDia": "THRU",\n}',
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_fillister_screw",
            "spec_exists": True,
            "maps": [
                {
                    "name": "SIDE_DIMENSION_CALLOUTS",
                    "source": 'SIDE_DIMENSION_CALLOUTS = {"ShankLg": '
                    '"UNDERHEAD LENGTH"}',
                    "dependencies": [],
                }
            ],
            "unresolved_spec_names": [],
        },
        {
            "drawing": "draw_cone_pivot_screw",
            "spec_exists": True,
            "maps": [
                {
                    "name": "SIDE_DIMENSION_CALLOUTS",
                    "source": "SIDE_DIMENSION_CALLOUTS = {\n"
                    '    "ThreadLg": THREAD_DESIGNATION,\n'
                    "}",
                    "dependencies": ["THREAD_DESIGNATION"],
                }
            ],
            "unresolved_spec_names": [],
        },
    ],
}
