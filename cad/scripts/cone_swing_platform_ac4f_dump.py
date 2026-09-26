"""Fixture: leaf ac4f's describe_sheet dump of the one-sheet MHA-091 drawing.

The last single-sheet cone-swing-platform farm leaf (PR #929 at ac4fa6dd0, before
the sheet split) printed this from
``diagnostics.drawing_layout_audit.describe_sheet`` right before its layout
audit failed on two leader crossings: the tap callout RD2 across the notch plan
(Drawing View3) and the dowel callout RD3 across the profile plan (Drawing
View1).  ``test_cone_swing_platform_sheets_drawing`` rebuilds a
``SheetGeometry`` from it, splits it the way the two-sheet recipe does, and
judges both sheets with the planner's and the audit's own rules.

Sheet millimetres; y grows up the sheet.  Verbatim; do not edit.
"""

DUMP = """
sheet 'Sheet1': 431.8 x 279.4 mm
  inner border (zone margins): [12.7,12.7]..[419.1,266.7]mm
  glyph advance ratio: 0.723
  keep-out title-block: [216.0,0.0]..[431.8,66.0]mm
  view 'Drawing View1': [54.4,128.6]..[95.6,251.4]mm scale 1:2 mode 2 parent-display=False faceted-hlr=False type=7
  view 'Drawing View2': [159.4,128.6]..[200.6,251.4]mm scale 1:2 mode 2 parent-display=False faceted-hlr=False type=7
  view 'Drawing View3': [239.4,128.6]..[280.6,251.4]mm scale 1:2 mode 2 parent-display=False faceted-hlr=False type=7
  view 'Drawing View4': [331.0,179.3]..[409.0,230.7]mm scale 1:3 mode 2 parent-display=False faceted-hlr=False type=7
  view 'Section View A-A': [331.1,108.1]..[398.9,131.9]mm scale 2:1 mode 2 parent-display=False faceted-hlr=False type=2
  view 'Detail View B (2 : 1)': [49.1,10.6]..[117.9,79.4]mm scale 2:1 mode 1 parent-display=False faceted-hlr=False type=3
  view 'Detail View D (2 : 1)': [337.0,224.0]..[377.0,264.0]mm scale 2:1 mode 2 parent-display=False faceted-hlr=False type=3
  view 'Section View C-C': [250.7,103.5]..[321.8,121.0]mm scale 1:1 mode 2 parent-display=False faceted-hlr=False type=2
  dim 'NorthEastX' owner='Drawing View1' text[estimated]=[39.2,102.2]..[54.4,105.7]mm
      GetPosition=(45.00,105.00)mm
      line: (63.8,133.2)->(63.8,101.2)mm
      line: (71.8,133.7)->(71.8,101.2)mm
      leader: (63.8,102.2)->(39.2,102.2)mm
      line: (63.8,102.2)->(71.8,102.2)mm
      line: (71.8,102.2)->(78.1,102.2)mm
  dim 'NorthWestX' owner='Drawing View1' text[estimated]=[94.2,112.2]..[109.4,115.7]mm
      GetPosition=(100.00,115.00)mm
      line: (77.6,133.2)->(77.6,111.2)mm
      line: (71.8,133.7)->(71.8,111.2)mm
      leader: (77.6,112.2)->(105.8,112.2)mm
      line: (77.6,112.2)->(71.8,112.2)mm
      line: (71.8,112.2)->(65.4,112.2)mm
  dim 'SouthWestX' owner='Drawing View1' text[estimated]=[98.2,255.2]..[113.4,258.7]mm
      GetPosition=(104.00,258.00)mm
      line: (90.3,246.8)->(90.3,256.2)mm
      line: (71.8,133.7)->(71.8,256.2)mm
      leader: (90.3,255.2)->(109.8,255.2)mm
      line: (90.3,255.2)->(71.8,255.2)mm
  dim 'PlateLenDim' owner='Drawing View1' text[estimated]=[17.9,187.2]..[35.6,190.7]mm
      GetPosition=(25.00,190.00)mm
      line: (62.8,134.2)->(24.0,134.2)mm
      line: (89.3,245.8)->(24.0,245.8)mm
      leader: (25.0,134.2)->(25.0,187.2)mm
      line: (25.0,245.8)->(25.0,192.8)mm
  dim 'SouthEastX' owner='Drawing View1' text[estimated]=[39.2,256.2]..[54.4,259.7]mm
      GetPosition=(45.00,259.00)mm
      line: (59.8,246.8)->(59.8,257.2)mm
      line: (71.8,133.7)->(71.8,257.2)mm
      leader: (59.8,256.2)->(39.2,256.2)mm
      line: (59.8,256.2)->(71.8,256.2)mm
  dim 'PivotBearingReliefDia' owner='Drawing View1' text[estimated]=[82.9,138.5]..[100.6,142.0]mm
      GetPosition=(90.00,141.30)mm
      line: (69.2,133.7)->(69.2,139.5)mm
      line: (74.4,133.7)->(74.4,139.5)mm
      line: (69.2,138.5)->(62.8,138.5)mm
      line: (69.2,138.5)->(74.4,138.5)mm
      leader: (74.4,138.5)->(97.1,138.5)mm
  dim 'CornerSWR' owner='Drawing View1' text[estimated]=[104.1,246.2]..[119.2,249.7]mm
      GetPosition=(110.00,249.00)mm
      line: (89.9,243.8)->(102.5,246.2)mm
      line: (87.5,243.3)->(89.9,243.8)mm
      leader: (102.5,246.2)->(115.9,246.2)mm
  dim 'CornerSER' owner='Drawing View1' text[estimated]=[32.8,240.7]..[50.5,244.2]mm
      GetPosition=(40.00,243.50)mm
      leader: (60.0,240.1)->(48.8,240.7)mm
      line: (66.0,239.8)->(60.0,240.1)mm
      leader: (48.8,240.7)->(32.8,240.7)mm
  dim 'CornerNWR' owner='Drawing View1' text[estimated]=[96.1,127.2]..[111.2,130.7]mm
      GetPosition=(102.00,130.00)mm
      line: (77.5,136.3)->(94.5,127.2)mm
      line: (74.0,138.2)->(77.5,136.3)mm
      leader: (94.5,127.2)->(107.9,127.2)mm
  dim 'CornerNER' owner='Drawing View1' text[estimated]=[37.8,136.2]..[55.5,139.7]mm
      GetPosition=(45.00,139.00)mm
      leader: (63.7,138.2)->(53.8,136.2)mm
      line: (68.6,139.2)->(63.7,138.2)mm
      leader: (53.8,136.2)->(37.8,136.2)mm
  note 'DetailItem351' owner='Drawing View1' text[exact]=[78.3,234.3]..[135.9,247.6]mm
      GetPosition=(91.82,247.35)mm
      leader: (91.1,245.9)->(84.7,245.9)mm
      leader: (84.7,245.9)->(78.4,233.9)mm
  dim 'RD1' owner='Drawing View2' text[estimated]=[190.0,104.2]..[205.2,107.7]mm [203.0,104.2]..[228.2,107.7]mm [208.2,104.2]..[243.6,107.7]mm
      GetPosition=(215.00,107.00)mm
      line: (177.3,136.1)->(188.4,104.2)mm
      line: (176.2,139.3)->(177.3,136.1)mm
      leader: (188.4,104.2)->(240.0,104.2)mm
  dim 'RD2' owner='Drawing View2' text[estimated]=[178.1,266.4]..[185.7,269.9]mm [184.8,266.4]..[210.1,269.9]mm [190.1,266.4]..[225.5,269.9]mm [171.0,260.8]..[224.2,264.3]mm [155.9,255.2]..[249.5,258.7]mm [162.3,249.6]..[190.1,253.1]mm [171.7,249.6]..[197.0,253.1]mm [177.0,249.7]..[245.3,253.2]mm [164.1,244.0]..[192.0,247.5]mm [173.6,244.0]..[198.9,247.5]mm [178.9,244.1]..[244.6,247.6]mm
      GetPosition=(200.00,258.00)mm
      line: (169.1,235.8)->(154.3,244.0)mm
      line: (171.3,234.6)->(169.1,235.8)mm
      leader: (154.3,244.0)->(244.1,244.0)mm
  dim 'RD3' owner='Drawing View2' text[estimated]=[88.5,226.5]..[141.6,230.0]mm [91.0,221.0]..[141.6,224.5]mm [69.0,212.0]..[117.0,215.5]mm [112.2,211.9]..[137.5,215.4]mm [117.5,212.0]..[135.2,215.5]mm [131.7,216.4]..[134.3,219.9]mm [134.6,216.4]..[144.7,219.9]mm [134.6,211.9]..[144.7,215.4]mm [143.6,212.0]..[166.4,215.5]mm
      GetPosition=(117.00,222.00)mm
      leader: (174.9,226.5)->(166.6,211.9)mm
      line: (175.7,227.9)->(174.9,226.5)mm
      leader: (166.6,211.9)->(69.0,211.9)mm
  note 'DetailItem392' owner='Drawing View2' text[exact]=[132.8,139.7]..[174.7,154.9]mm
      GetPosition=(133.00,154.40)mm
      leader: (150.4,143.0)->(150.4,143.0)mm
      leader: (150.4,143.0)->(174.9,139.5)mm
      leader: (150.4,143.0)->(174.9,139.5)mm
  dim 'TipSlotZ' owner='Drawing View3' text[estimated]=[232.0,141.8]..[249.7,145.3]mm
      GetPosition=(239.13,144.59)mm
      line: (254.5,151.5)->(238.1,151.5)mm
      line: (252.9,137.7)->(238.1,137.7)mm
      line: (239.1,151.5)->(239.1,147.4)mm
      leader: (239.1,137.7)->(239.1,141.8)mm
  dim 'NorthEdgeZ' owner='Drawing View3' text[estimated]=[270.0,147.2]..[282.6,150.7]mm
      GetPosition=(270.00,150.00)mm
      line: (249.8,134.2)->(271.0,134.2)mm
      line: (252.9,137.7)->(271.0,137.7)mm
      leader: (279.1,147.2)->(270.0,147.2)mm
      leader: (270.0,147.2)->(270.0,137.7)mm
      line: (270.0,134.2)->(270.0,127.8)mm
  dim 'CapECx' owner='Drawing View3' text[estimated]=[258.1,255.2]..[275.8,258.7]mm
      GetPosition=(265.20,258.00)mm
      leader: (273.1,241.6)->(273.1,256.2)mm
      line: (256.8,133.7)->(256.8,256.2)mm
      leader: (273.1,255.2)->(279.5,255.2)mm
      leader: (273.1,255.2)->(256.8,255.2)mm
      line: (256.8,255.2)->(250.4,255.2)mm
  dim 'CapECz' owner='Drawing View3' text[estimated]=[318.6,167.2]..[338.8,170.7]mm
      GetPosition=(327.00,170.00)mm
      line: (274.1,240.6)->(328.0,240.6)mm
      line: (260.7,137.7)->(328.0,137.7)mm
      line: (327.0,240.6)->(327.0,172.8)mm
      leader: (327.0,137.7)->(327.0,167.2)mm
  surface-finish 'DetailItem382' owner='Section View A-A' text[estimated]=[326.0,105.6]..[336.8,108.1]mm
      GetPosition=(321.00,102.00)mm
      line: (319.8,102.0)->(327.3,102.0)mm
      line: (327.3,102.0)->(347.4,113.6)mm
      line: (321.0,102.0)->(318.8,105.7)mm
      line: (323.2,105.7)->(318.8,105.7)mm
      line: (321.0,102.0)->(325.2,109.1)mm
      line: (322.5,107.6)->(319.5,107.6)mm
      line: (325.2,109.1)->(335.7,109.1)mm
      leader: (319.8,102.0)->(327.3,102.0)mm
      leader: (327.3,102.0)->(347.4,113.6)mm
  surface-finish 'DetailItem383' owner='Section View A-A' text[estimated]=[380.0,138.6]..[390.8,141.1]mm
      GetPosition=(375.00,135.00)mm
      line: (373.8,135.0)->(381.4,135.0)mm
      line: (381.4,135.0)->(384.3,126.3)mm
      line: (375.0,135.0)->(372.8,138.8)mm
      line: (377.2,138.8)->(372.8,138.8)mm
      line: (375.0,135.0)->(379.2,142.1)mm
      line: (376.5,140.6)->(373.5,140.6)mm
      line: (379.2,142.1)->(389.7,142.1)mm
      leader: (373.8,135.0)->(381.4,135.0)mm
      leader: (381.4,135.0)->(384.3,126.3)mm
  dim 'PlateThk' owner='Section View A-A' text[estimated]=[309.5,131.8]..[324.7,135.3]mm [301.6,126.2]..[331.9,129.7]mm [305.7,120.7]..[326.0,124.2]mm
      GetPosition=(330.00,129.00)mm
      leader: (335.5,126.3)->(329.0,126.3)mm
      line: (335.5,113.6)->(329.0,113.6)mm
      line: (301.6,120.7)->(330.0,120.7)mm
      leader: (330.0,120.7)->(330.0,126.3)mm
      leader: (330.0,126.3)->(330.0,113.6)mm
  dim 'PivotBearingReliefDepth' owner='Section View A-A' text[estimated]=[395.0,127.2]..[415.2,130.7]mm
      GetPosition=(395.00,130.00)mm
      line: (380.0,113.6)->(396.0,113.6)mm
      line: (380.0,114.2)->(396.0,114.2)mm
      leader: (410.1,127.2)->(395.0,127.2)mm
      leader: (395.0,127.2)->(395.0,114.2)mm
      line: (395.0,113.6)->(395.0,107.3)mm
  note 'DetailItem362' owner='Section View A-A' text[exact]=[342.0,83.9]..[387.5,100.3]mm
      GetPosition=(365.00,100.00)mm
  note 'DetailItem384' owner='Section View A-A' text[exact]=[44.9,80.9]..[105.5,85.1]mm
      GetPosition=(45.00,85.00)mm
  note 'DetailItem385' owner='Section View A-A' text[exact]=[149.8,80.9]..[192.9,85.1]mm
      GetPosition=(150.00,85.00)mm
  note 'DetailItem386' owner='Section View A-A' text[exact]=[229.8,121.5]..[289.9,125.8]mm
      GetPosition=(230.15,125.50)mm
  note 'DetailItem387' owner='Section View A-A' text[exact]=[329.9,153.6]..[389.3,158.5]mm
      GetPosition=(330.00,158.00)mm
  note 'DetailItem388' owner='Section View A-A' text[exact]=[119.5,20.2]..[211.0,34.2]mm
      GetPosition=(120.00,34.00)mm
  dim 'TipSlotEastCx' owner='Detail View B (2 : 1)' text[estimated]=[57.7,71.2]..[72.9,74.7]mm
      GetPosition=(63.50,74.00)mm
      line: (78.5,46.0)->(78.5,72.2)mm
      line: (83.5,54.0)->(83.5,72.2)mm
      leader: (78.5,71.2)->(57.7,71.2)mm
      line: (78.5,71.2)->(83.5,71.2)mm
      line: (83.5,71.2)->(89.9,71.2)mm
  dim 'TipSlotWestCx' owner='Detail View B (2 : 1)' text[estimated]=[91.2,71.2]..[106.4,74.7]mm
      GetPosition=(97.00,74.00)mm
      line: (88.5,46.0)->(88.5,72.2)mm
      line: (83.5,54.0)->(83.5,72.2)mm
      leader: (88.5,71.2)->(102.8,71.2)mm
      line: (88.5,71.2)->(83.5,71.2)mm
      line: (83.5,71.2)->(77.2,71.2)mm
  dim 'TipSlotW' owner='Detail View B (2 : 1)' text[estimated]=[36.4,53.0]..[49.0,56.5]mm [45.4,57.5]..[47.9,61.0]mm [48.2,57.5]..[55.8,61.0]mm [48.2,53.0]..[55.8,56.5]mm
      GetPosition=(56.00,57.50)mm
      line: (77.5,41.0)->(55.0,41.0)mm
      line: (77.5,49.0)->(55.0,49.0)mm
      leader: (36.4,53.0)->(56.0,53.0)mm
      leader: (56.0,53.0)->(56.0,49.0)mm
      line: (56.0,41.0)->(56.0,49.0)mm
  dim 'TipCboreW' owner='Detail View B (2 : 1)' text[estimated]=[14.8,63.0]..[29.9,66.5]mm [26.4,67.5]..[28.9,71.0]mm [29.2,67.5]..[36.8,71.0]mm [29.2,63.0]..[36.8,66.5]mm
      GetPosition=(37.00,67.50)mm
      line: (77.5,38.5)->(36.0,38.5)mm
      line: (77.5,51.5)->(36.0,51.5)mm
      leader: (14.8,63.0)->(37.0,63.0)mm
      leader: (37.0,63.0)->(37.0,51.5)mm
      line: (37.0,38.5)->(37.0,51.5)mm
  note 'DetailItem364' owner='Detail View B (2 : 1)' text[exact]=[16.4,14.8]..[47.9,31.2]mm
      GetPosition=(32.36,31.12)mm
  note 'DetailItem389' owner='Detail View B (2 : 1)' text[exact]=[90.4,48.7]..[137.1,79.1]mm
      GetPosition=(121.00,78.50)mm
      leader: (120.2,77.7)->(120.2,77.7)mm
      leader: (120.2,77.7)->(90.5,48.5)mm
      leader: (120.2,77.7)->(90.5,48.5)mm
  note 'DetailItem390' owner='Detail View B (2 : 1)' text[exact]=[93.4,37.8]..[148.6,44.5]mm
      GetPosition=(121.00,44.50)mm
      leader: (120.2,43.1)->(120.2,43.1)mm
      leader: (120.2,43.1)->(93.8,41.3)mm
      leader: (120.2,43.1)->(93.8,41.3)mm
  dim 'NotchW' owner='Detail View D (2 : 1)' text[estimated]=[375.4,251.5]..[390.6,255.0]mm [387.0,256.0]..[389.6,259.5]mm [389.9,256.0]..[397.4,259.5]mm [389.9,251.5]..[397.4,255.0]mm
      GetPosition=(386.50,256.00)mm
      line: (359.3,251.7)->(386.1,247.3)mm
      line: (356.7,235.9)->(383.4,231.5)mm
      leader: (385.1,247.4)->(385.7,251.5)mm
      line: (382.4,231.6)->(385.1,247.4)mm
  dim 'NotchMouthAngle' owner='Detail View D (2 : 1)' text[estimated]=[352.7,257.2]..[365.3,260.7]mm
      GetPosition=(357.50,260.00)mm
      line: (364.1,251.9)->(365.4,263.0)mm
      line: (357.3,252.1)->(352.0,252.9)mm
      line: (365.3,262.0)->(362.3,262.0)mm
      leader: (354.8,257.2)->(353.0,252.8)mm
  note 'DetailItem370' owner='Detail View D (2 : 1)' text[exact]=[301.4,245.8]..[333.5,262.2]mm
      GetPosition=(317.69,262.10)mm
  note 'DetailItem391' owner='Detail View D (2 : 1)' text[exact]=[349.9,242.2]..[374.8,248.2]mm
      GetPosition=(373.00,245.50)mm
      leader: (372.4,244.4)->(372.4,244.4)mm
      leader: (372.4,244.4)->(350.1,248.0)mm
      leader: (372.4,244.4)->(350.1,248.0)mm
  dim 'TipCboreDepth' owner='Section View C-C' text[estimated]=[299.5,103.1]..[314.7,106.6]mm
      GetPosition=(299.50,105.90)mm
      line: (283.3,109.1)->(300.5,109.1)mm
      line: (283.3,112.1)->(300.5,112.1)mm
      leader: (311.1,103.1)->(299.5,103.1)mm
      leader: (299.5,103.1)->(299.5,109.1)mm
      line: (299.5,112.1)->(299.5,118.4)mm
  note 'DetailItem376' owner='Section View C-C' text[exact]=[255.9,81.5]..[302.0,97.9]mm
      GetPosition=(279.43,97.71)mm
"""
