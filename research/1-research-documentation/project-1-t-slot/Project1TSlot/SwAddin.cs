using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
using SolidWorks.Interop.swpublished;
using SolidWorksTools;
using SolidWorksTools.File;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Reflection;
using System.Runtime.InteropServices;


namespace Project1TSlot
{
    /// <summary>
    /// Summary description for Project1TSlot.
    /// </summary>
    [Guid("e273dad7-9d94-4e0e-863c-5f0c558378f9"), ComVisible(true)]
    [SwAddin(
        Description = "Project1TSlot description",
        Title = "Project1TSlot",
        LoadAtStartup = true
        )]
    public class SwAddin : ISwAddin
    {
        #region Local Variables
        ISldWorks iSwApp = null;
        ICommandManager iCmdMgr = null;
        int addinID = 0;
        BitmapHandler iBmp;
        int registerID;

        public const int mainCmdGroupID = 5;
        public const int mainItemID1 = 0;
        public const int mainItemID2 = 1;
        public const int mainItemID3 = 2;
        public const int tnutItemID = 3;
        public const int flyoutGroupID = 91;

        string[] mainIcons = new string[6];
        string[] icons = new string[6];

        #region Event Handler Variables
        Hashtable openDocs = new Hashtable();
        SolidWorks.Interop.sldworks.SldWorks SwEventPtr = null;
        #endregion

        #region Property Manager Variables
        public UserPMPage ppage = null;
        #endregion


        // Public Properties
        public ISldWorks SwApp
        {
            get { return iSwApp; }
        }
        public ICommandManager CmdMgr
        {
            get { return iCmdMgr; }
        }

        public Hashtable OpenDocs
        {
            get { return openDocs; }
        }

        #endregion

        #region SolidWorks Registration
        [ComRegisterFunctionAttribute]
        public static void RegisterFunction(Type t)
        {
            #region Get Custom Attribute: SwAddinAttribute
            SwAddinAttribute SWattr = null;
            Type type = typeof(SwAddin);

            foreach (System.Attribute attr in type.GetCustomAttributes(false))
            {
                if (attr is SwAddinAttribute)
                {
                    SWattr = attr as SwAddinAttribute;
                    break;
                }
            }

            #endregion

            try
            {
                Microsoft.Win32.RegistryKey hklm = Microsoft.Win32.Registry.LocalMachine;
                Microsoft.Win32.RegistryKey hkcu = Microsoft.Win32.Registry.CurrentUser;

                string keyname = "SOFTWARE\\SolidWorks\\Addins\\{" + t.GUID.ToString() + "}";
                Microsoft.Win32.RegistryKey addinkey = hklm.CreateSubKey(keyname);
                addinkey.SetValue(null, 0);

                addinkey.SetValue("Description", SWattr.Description);
                addinkey.SetValue("Title", SWattr.Title);

                keyname = "Software\\SolidWorks\\AddInsStartup\\{" + t.GUID.ToString() + "}";
                addinkey = hkcu.CreateSubKey(keyname);
                addinkey.SetValue(null, Convert.ToInt32(SWattr.LoadAtStartup), Microsoft.Win32.RegistryValueKind.DWord);
            }
            catch (System.NullReferenceException nl)
            {
                Console.WriteLine("There was a problem registering this dll: SWattr is null. \n\"" + nl.Message + "\"");
                System.Windows.Forms.MessageBox.Show("There was a problem registering this dll: SWattr is null.\n\"" + nl.Message + "\"");
            }

            catch (System.Exception e)
            {
                Console.WriteLine(e.Message);

                System.Windows.Forms.MessageBox.Show("There was a problem registering the function: \n\"" + e.Message + "\"");
            }
        }

        [ComUnregisterFunctionAttribute]
        public static void UnregisterFunction(Type t)
        {
            try
            {
                Microsoft.Win32.RegistryKey hklm = Microsoft.Win32.Registry.LocalMachine;
                Microsoft.Win32.RegistryKey hkcu = Microsoft.Win32.Registry.CurrentUser;

                string keyname = "SOFTWARE\\SolidWorks\\Addins\\{" + t.GUID.ToString() + "}";
                hklm.DeleteSubKey(keyname);

                keyname = "Software\\SolidWorks\\AddInsStartup\\{" + t.GUID.ToString() + "}";
                hkcu.DeleteSubKey(keyname);
            }
            catch (System.NullReferenceException nl)
            {
                Console.WriteLine("There was a problem unregistering this dll: " + nl.Message);
                System.Windows.Forms.MessageBox.Show("There was a problem unregistering this dll: \n\"" + nl.Message + "\"");
            }
            catch (System.Exception e)
            {
                Console.WriteLine("There was a problem unregistering this dll: " + e.Message);
                System.Windows.Forms.MessageBox.Show("There was a problem unregistering this dll: \n\"" + e.Message + "\"");
            }
        }

        #endregion

        #region ISwAddin Implementation
        public SwAddin()
        {
        }

        public bool ConnectToSW(object ThisSW, int cookie)
        {
            iSwApp = (ISldWorks)ThisSW;
            addinID = cookie;

            //Setup callbacks
            iSwApp.SetAddinCallbackInfo(0, this, addinID);

            #region Setup the Command Manager
            iCmdMgr = iSwApp.GetCommandManager(cookie);
            AddCommandMgr();
            #endregion

            #region Setup the Event Handlers
            SwEventPtr = (SolidWorks.Interop.sldworks.SldWorks)iSwApp;
            openDocs = new Hashtable();
            AttachEventHandlers();
            #endregion

            #region Setup Sample Property Manager
            AddPMP();
            #endregion

            return true;
        }

        public bool DisconnectFromSW()
        {
            RemoveCommandMgr();
            RemovePMP();
            DetachEventHandlers();

            System.Runtime.InteropServices.Marshal.ReleaseComObject(iCmdMgr);
            iCmdMgr = null;
            System.Runtime.InteropServices.Marshal.ReleaseComObject(iSwApp);
            iSwApp = null;
            //The addin _must_ call GC.Collect() here in order to retrieve all managed code pointers 
            GC.Collect();
            GC.WaitForPendingFinalizers();

            GC.Collect();
            GC.WaitForPendingFinalizers();

            return true;
        }
        #endregion

        #region UI Methods
        public void AddCommandMgr()
        {
            ICommandGroup cmdGroup;
            if (iBmp == null)
                iBmp = new BitmapHandler();
            Assembly thisAssembly;
            int cmdIndex0, cmdIndex1;
            string Title = "C# Addin", ToolTip = "C# Addin";


            int[] docTypes = new int[]{(int)swDocumentTypes_e.swDocASSEMBLY,
                                       (int)swDocumentTypes_e.swDocDRAWING,
                                       (int)swDocumentTypes_e.swDocPART};

            thisAssembly = System.Reflection.Assembly.GetAssembly(this.GetType());


            int cmdGroupErr = 0;
            bool ignorePrevious = false;

            object registryIDs;
            //get the ID information stored in the registry
            bool getDataResult = iCmdMgr.GetGroupDataFromRegistry(mainCmdGroupID, out registryIDs);

            int[] knownIDs = new int[3] { mainItemID1, mainItemID2, tnutItemID };

            if (getDataResult)
            {
                if (!CompareIDs((int[])registryIDs, knownIDs)) //if the IDs don't match, reset the commandGroup
                {
                    ignorePrevious = true;
                }
            }

            cmdGroup = iCmdMgr.CreateCommandGroup2(mainCmdGroupID, Title, ToolTip, "", -1, ignorePrevious, ref cmdGroupErr);

            // Add bitmaps to your project and set them as embedded resources or provide a direct path to the bitmaps.
            icons[0] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.toolbar20x.png", thisAssembly);
            icons[1] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.toolbar32x.png", thisAssembly);
            icons[2] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.toolbar40x.png", thisAssembly);
            icons[3] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.toolbar64x.png", thisAssembly);
            icons[4] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.toolbar96x.png", thisAssembly);
            icons[5] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.toolbar128x.png", thisAssembly);

            mainIcons[0] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.mainicon_20.png", thisAssembly);
            mainIcons[1] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.mainicon_32.png", thisAssembly);
            mainIcons[2] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.mainicon_40.png", thisAssembly);
            mainIcons[3] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.mainicon_64.png", thisAssembly);
            mainIcons[4] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.mainicon_96.png", thisAssembly);
            mainIcons[5] = iBmp.CreateFileFromResourceBitmap("Project1TSlot.mainicon_128.png", thisAssembly);

            cmdGroup.MainIconList = mainIcons;
            cmdGroup.IconList = icons;

            int menuToolbarOption = (int)(swCommandItemType_e.swMenuItem | swCommandItemType_e.swToolbarItem);
            cmdIndex0 = cmdGroup.AddCommandItem2("CreateCube", -1, "Create a cube", "Create cube", 0, "CreateCube", "", mainItemID1, menuToolbarOption);
            cmdIndex1 = cmdGroup.AddCommandItem2("Show PMP", -1, "Display sample property manager", "Show PMP", 2, "ShowPMP", "EnablePMP", mainItemID2, menuToolbarOption);
            int cmdIndex2 = cmdGroup.AddCommandItem2("Create PM-30MV T-Nut", -1, "Create a T-nut for PM-30MV milling machine", "Create T-Nut", 0, "CreateTNut", "", tnutItemID, menuToolbarOption);

            cmdGroup.HasToolbar = true;
            cmdGroup.HasMenu = true;
            cmdGroup.Activate();

            bool bResult;



            FlyoutGroup flyGroup = iCmdMgr.CreateFlyoutGroup2(flyoutGroupID, "Dynamic Flyout", "Flyout Tooltip", "Flyout Hint",
              cmdGroup.MainIconList, cmdGroup.IconList, "FlyoutCallback", "FlyoutEnable");


            flyGroup.AddCommandItem("FlyoutCommand 1", "test", 0, "FlyoutCommandItem1", "FlyoutEnableCommandItem1");

            flyGroup.FlyoutType = (int)swCommandFlyoutStyle_e.swCommandFlyoutStyle_Simple;


            foreach (int type in docTypes)
            {
                CommandTab cmdTab;

                cmdTab = iCmdMgr.GetCommandTab(type, Title);

                if (cmdTab != null & !getDataResult | ignorePrevious)//if tab exists, but we have ignored the registry info (or changed command group ID), re-create the tab.  Otherwise the ids won't matchup and the tab will be blank
                {
                    bool res = iCmdMgr.RemoveCommandTab(cmdTab);
                    cmdTab = null;
                }

                //if cmdTab is null, must be first load (possibly after reset), add the commands to the tabs
                if (cmdTab == null)
                {
                    cmdTab = iCmdMgr.AddCommandTab(type, Title);

                    CommandTabBox cmdBox = cmdTab.AddCommandTabBox();

                    int[] cmdIDs = new int[4];
                    int[] TextType = new int[4];

                    cmdIDs[0] = cmdGroup.get_CommandID(cmdIndex0);
                    TextType[0] = (int)swCommandTabButtonTextDisplay_e.swCommandTabButton_TextHorizontal;

                    cmdIDs[1] = cmdGroup.get_CommandID(cmdIndex1);
                    TextType[1] = (int)swCommandTabButtonTextDisplay_e.swCommandTabButton_TextHorizontal;

                    cmdIDs[2] = cmdGroup.get_CommandID(cmdIndex2);
                    TextType[2] = (int)swCommandTabButtonTextDisplay_e.swCommandTabButton_TextHorizontal;

                    cmdIDs[3] = cmdGroup.ToolbarId;
                    TextType[3] = (int)swCommandTabButtonTextDisplay_e.swCommandTabButton_TextHorizontal | (int)swCommandTabButtonFlyoutStyle_e.swCommandTabButton_ActionFlyout;

                    bResult = cmdBox.AddCommands(cmdIDs, TextType);



                    CommandTabBox cmdBox1 = cmdTab.AddCommandTabBox();
                    cmdIDs = new int[1];
                    TextType = new int[1];

                    cmdIDs[0] = flyGroup.CmdID;
                    TextType[0] = (int)swCommandTabButtonTextDisplay_e.swCommandTabButton_TextBelow | (int)swCommandTabButtonFlyoutStyle_e.swCommandTabButton_ActionFlyout;

                    bResult = cmdBox1.AddCommands(cmdIDs, TextType);

                    cmdTab.AddSeparator(cmdBox1, cmdIDs[0]);

                }

            }

            // Create a third-party icon in the context-sensitive menus of faces in parts
            // To see this menu, right click on any face in the part
            Frame swFrame;

            swFrame = iSwApp.Frame();
            bResult = swFrame.AddMenuPopupIcon3((int)swDocumentTypes_e.swDocPART, (int)swSelectType_e.swSelFACES, "third-party context-sensitive CSharp", addinID,
                                                "PopupCallbackFunction", "PopupEnable", "", cmdGroup.MainIconList);

            // create and register the shortcut menu
            registerID = iSwApp.RegisterThirdPartyPopupMenu();

            // add a menu break at the top of the shortcut menu
            bResult = iSwApp.AddItemToThirdPartyPopupMenu2(registerID, (int)swDocumentTypes_e.swDocPART, "Menu Break", addinID, "", "", "", "", "", (int)swMenuItemType_e.swMenuItemType_Break);

            // add a couple of items to the shortcut menu
            bResult = iSwApp.AddItemToThirdPartyPopupMenu2(registerID, (int)swDocumentTypes_e.swDocPART, "Test1", addinID, "TestCallback", "EnableTest", "", "Test1", mainIcons[0], (int)swMenuItemType_e.swMenuItemType_Default);
            bResult = iSwApp.AddItemToThirdPartyPopupMenu2(registerID, (int)swDocumentTypes_e.swDocPART, "Test2", addinID, "TestCallback", "EnableTest", "", "Test2", mainIcons[0], (int)swMenuItemType_e.swMenuItemType_Default);

            // add a separator bar to the shortcut menu
            bResult = iSwApp.AddItemToThirdPartyPopupMenu2(registerID, (int)swDocumentTypes_e.swDocPART, "separator", addinID, "", "", "", "", "", (int)swMenuItemType_e.swMenuItemType_Separator);

            // add another item to the shortcut menu
            bResult = iSwApp.AddItemToThirdPartyPopupMenu2(registerID, (int)swDocumentTypes_e.swDocPART, "Test3", addinID, "TestCallback", "EnableTest", "", "Test3", mainIcons[0], (int)swMenuItemType_e.swMenuItemType_Default);

            // add an icon to a menu bar of the shortcut menu
            bResult = iSwApp.AddItemToThirdPartyPopupMenu2(registerID, (int)swDocumentTypes_e.swDocPART, "", addinID, "TestCallback", "EnableTest", "", "NoOp", mainIcons[0], (int)swMenuItemType_e.swMenuItemType_Default);

            thisAssembly = null;

        }

        public void RemoveCommandMgr()
        {
            iBmp.Dispose();

            iCmdMgr.RemoveCommandGroup(mainCmdGroupID);
            iCmdMgr.RemoveFlyoutGroup(flyoutGroupID);
        }

        public bool CompareIDs(int[] storedIDs, int[] addinIDs)
        {
            List<int> storedList = new List<int>(storedIDs);
            List<int> addinList = new List<int>(addinIDs);

            addinList.Sort();
            storedList.Sort();

            if (addinList.Count != storedList.Count)
            {
                return false;
            }
            else
            {

                for (int i = 0; i < addinList.Count; i++)
                {
                    if (addinList[i] != storedList[i])
                    {
                        return false;
                    }
                }
            }
            return true;
        }

        public Boolean AddPMP()
        {
            ppage = new UserPMPage(this);
            return true;
        }

        public Boolean RemovePMP()
        {
            ppage = null;
            return true;
        }

        #endregion

        #region UI Callbacks
        public void CreateCube()
        {
            //make sure we have a part open
            string partTemplate = iSwApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart);
            if ((partTemplate != null) && (partTemplate != ""))
            {
                IModelDoc2 modDoc = (IModelDoc2)iSwApp.NewDocument(partTemplate, (int)swDwgPaperSizes_e.swDwgPaperA2size, 0.0, 0.0);

                modDoc.InsertSketch2(true);
                modDoc.SketchRectangle(0, 0, 0, .1, .1, .1, false);
                //Extrude the sketch
                IFeatureManager featMan = modDoc.FeatureManager;
                featMan.FeatureExtrusion(true,
                    false, false,
                    (int)swEndConditions_e.swEndCondBlind, (int)swEndConditions_e.swEndCondBlind,
                    0.1, 0.0,
                    false, false,
                    false, false,
                    0.0, 0.0,
                    false, false,
                    false, false,
                    true,
                    false, false);
            }
            else
            {
                System.Windows.Forms.MessageBox.Show("There is no part template available. Please check your options and make sure there is a part template selected, or select a new part template.");
            }
        }

        public void PopupCallbackFunction()
        {
            bool bRet;

            bRet = iSwApp.ShowThirdPartyPopupMenu(registerID, 500, 500);
        }

        public int PopupEnable()
        {
            if (iSwApp.ActiveDoc == null)
                return 0;
            else
                return 1;
        }

        public void TestCallback()
        {
            Debug.Print("Test Callback, CSharp");
        }

        public int EnableTest()
        {
            if (iSwApp.ActiveDoc == null)
                return 0;
            else
                return 1;
        }

        public void ShowPMP()
        {
            if (ppage != null)
                ppage.Show();
        }

        public int EnablePMP()
        {
            if (iSwApp.ActiveDoc != null)
                return 1;
            else
                return 0;
        }

        public void FlyoutCallback()
        {
            FlyoutGroup flyGroup = iCmdMgr.GetFlyoutGroup(flyoutGroupID);
            flyGroup.RemoveAllCommandItems();

            flyGroup.AddCommandItem(System.DateTime.Now.ToLongTimeString(), "test", 0, "FlyoutCommandItem1", "FlyoutEnableCommandItem1");

        }
        public int FlyoutEnable()
        {
            return 1;
        }

        public void FlyoutCommandItem1()
        {
            iSwApp.SendMsgToUser("Flyout command 1");
        }

        public int FlyoutEnableCommandItem1()
        {
            return 1;
        }

        public void CreateTNut()
        {
            try
            {
                CreateTNutPart();
            }
            catch (Exception ex)
            {
                System.Windows.Forms.MessageBox.Show($"Error creating T-nut: {ex.Message}", "T-Nut Creator Error");
            }
        }

        /// <summary>
        /// Creates a T-nut part for PM-30MV milling machine
        /// Dimensions based on 14mm T-slot width and standard T-nut proportions
        /// </summary>
        public bool CreateTNutPart()
        {
            try
            {
                iSwApp.SendMsgToUser("Creating T-nut for PM-30MV...");
                
                // Get part template from user preferences
                string partTemplate = iSwApp.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart);
                iSwApp.SendMsgToUser($"Using part template: {partTemplate}");
                
                if (string.IsNullOrEmpty(partTemplate))
                {
                    System.Windows.Forms.MessageBox.Show("No part template found. Please set a default part template in SolidWorks options.");
                    return false;
                }

                // Create new part document
                iSwApp.SendMsgToUser("Creating new part document...");
                IModelDoc2 swModel = iSwApp.NewDocument(partTemplate, (int)swDwgPaperSizes_e.swDwgPaperA0size, 0.0, 0.0);

                if (swModel == null)
                {
                    System.Windows.Forms.MessageBox.Show("Failed to create new part document");
                    return false;
                }

                IPartDoc swPart = (IPartDoc)swModel;
                ISketchManager swSketchMgr = swModel.SketchManager;
                IFeatureManager swFeatMgr = swModel.FeatureManager;

                // Set units to millimeters
                iSwApp.SendMsgToUser("Setting units to millimeters...");
                swModel.Extension.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitSystem,
                                                         (int)swUserPreferenceOption_e.swDetailingNoOptionSpecified,
                                                         (int)swUnitSystem_e.swUnitSystem_MMGS);

                // Create T-nut geometry
                iSwApp.SendMsgToUser("Step 1: Creating T-nut head...");
                if (!CreateTNutHead(swModel, swSketchMgr, swFeatMgr)) return false;
                
                iSwApp.SendMsgToUser("Step 2: Creating T-nut slot...");
                if (!CreateTNutSlot(swModel, swSketchMgr, swFeatMgr)) return false;
                
                iSwApp.SendMsgToUser("Step 3: Creating thread hole...");
                if (!CreateThreadHole(swModel, swSketchMgr, swFeatMgr)) return false;

                // Rebuild the model
                iSwApp.SendMsgToUser("Rebuilding model...");
                swModel.EditRebuild3();

                iSwApp.SendMsgToUser("T-nut creation completed successfully!");
                System.Windows.Forms.MessageBox.Show("T-nut for PM-30MV created successfully!\n\nSpecifications:\n- Head: 13.5mm x 8mm x 6mm (fits 14mm T-slot)\n- Body: 7mm x 15mm x 6mm\n- Bolt hole: 13mm diameter (M12 clearance)\n- Compatible with PM-30MV milling machine T-slots", "T-Nut Creator");
                return true;
            }
            catch (Exception ex)
            {
                iSwApp.SendMsgToUser($"EXCEPTION in CreateTNutPart: {ex.Message}");
                System.Windows.Forms.MessageBox.Show($"Error creating T-nut: {ex.Message}\n\nStack trace: {ex.StackTrace}", "T-Nut Creator Error");
                return false;
            }
        }

        /// <summary>
        /// Creates the main head of the T-nut (the wide part that sits in the T-slot)
        /// Dimensions: 14mm slot width, allowing for clearance
        /// </summary>
        private bool CreateTNutHead(IModelDoc2 swModel, ISketchManager swSketchMgr, IFeatureManager swFeatMgr)
        {
            try
            {
                // Select the front plane for sketching
                iSwApp.SendMsgToUser("  Selecting Front Plane for head...");
                bool boolstatus = swModel.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0,
                                                              false, 0, null, 0);
                if (!boolstatus)
                {
                    iSwApp.SendMsgToUser("  FAILED: Could not select Front Plane for T-nut head");
                    return false;
                }

                // Insert sketch
                iSwApp.SendMsgToUser("  Inserting sketch for head...");
                swSketchMgr.InsertSketch(true);

                // Create rectangle for T-nut head (13.5mm wide to fit in 14mm slot with clearance)
                // Height: 8mm (standard T-nut proportion)
                iSwApp.SendMsgToUser("  Creating rectangle 13.5mm x 8mm...");
                swSketchMgr.CreateCornerRectangle(-0.00675, -0.004, 0, 0.00675, 0.004, 0);  // 13.5mm x 8mm

                // Exit sketch
                iSwApp.SendMsgToUser("  Exiting sketch...");
                swSketchMgr.InsertSketch(true);

                // Create extrude feature for head (6mm thick)
                iSwApp.SendMsgToUser("  Creating extrude feature 6mm thick...");
                IFeature headFeature = swFeatMgr.FeatureExtrusion2(true, false, false, 
                    (int)swEndConditions_e.swEndCondBlind, (int)swEndConditions_e.swEndCondBlind, 
                    0.006, 0.0, false, false, false, false, 0.0, 0.0, false, false, false, false, true, true, true, 
                    (int)swStartConditions_e.swStartSketchPlane, 0.0, false);

                if (headFeature == null)
                {
                    iSwApp.SendMsgToUser("  FAILED: FeatureExtrusion2 returned null for head");
                    return false;
                }

                iSwApp.SendMsgToUser("  Head created successfully!");
                return true;
            }
            catch (Exception ex)
            {
                iSwApp.SendMsgToUser($"  EXCEPTION in CreateTNutHead: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Creates the slot/body portion of the T-nut (the narrow part that extends upward)
        /// </summary>
        private bool CreateTNutSlot(IModelDoc2 swModel, ISketchManager swSketchMgr, IFeatureManager swFeatMgr)
        {
            try
            {
                // Select the Front Plane for sketching the slot body
                iSwApp.SendMsgToUser("  Selecting Front Plane for slot...");
                bool boolstatus = swModel.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0,
                                                              false, 0, null, 0);
                if (!boolstatus)
                {
                    iSwApp.SendMsgToUser("  FAILED: Could not select Front Plane for slot");
                    return false;
                }

                // Insert sketch
                iSwApp.SendMsgToUser("  Inserting sketch for slot...");
                swSketchMgr.InsertSketch(true);

                // Create rectangle for T-nut slot body (7mm wide x 15mm tall)
                // This extends above the head to provide gripping surface
                iSwApp.SendMsgToUser("  Creating rectangle 7mm x 15mm...");
                swSketchMgr.CreateCornerRectangle(-0.0035, 0.004, 0, 0.0035, 0.019, 0);  // 7mm x 15mm

                // Exit sketch
                iSwApp.SendMsgToUser("  Exiting slot sketch...");
                swSketchMgr.InsertSketch(true);

                // Create extrude feature for slot body (6mm thick, same as head)
                iSwApp.SendMsgToUser("  Creating slot extrude feature 6mm thick...");
                IFeature slotFeature = swFeatMgr.FeatureExtrusion2(true, false, false, 
                    (int)swEndConditions_e.swEndCondBlind, (int)swEndConditions_e.swEndCondBlind, 
                    0.006, 0.0, false, false, false, false, 0.0, 0.0, false, false, false, false, true, true, true, 
                    (int)swStartConditions_e.swStartSketchPlane, 0.0, false);

                if (slotFeature == null)
                {
                    iSwApp.SendMsgToUser("  FAILED: FeatureExtrusion2 returned null for slot");
                    return false;
                }

                iSwApp.SendMsgToUser("  Slot created successfully!");
                return true;
            }
            catch (Exception ex)
            {
                iSwApp.SendMsgToUser($"  EXCEPTION in CreateTNutSlot: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Creates the threaded hole for the bolt (9/16" = 14.29mm diameter hole for tap)
        /// Creates clearance hole for M14 or 9/16" bolt
        /// </summary>
        private bool CreateThreadHole(IModelDoc2 swModel, ISketchManager swSketchMgr, IFeatureManager swFeatMgr)
        {
            try
            {
                // Select the Front Plane for sketching the hole (same as the other sketches)
                iSwApp.SendMsgToUser("  Selecting Front Plane for hole...");
                bool boolstatus = swModel.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0,
                                                              false, 0, null, 0);
                if (!boolstatus)
                {
                    iSwApp.SendMsgToUser("  FAILED: Could not select Front Plane for hole");
                    return false;
                }

                // Insert sketch
                iSwApp.SendMsgToUser("  Inserting sketch for hole...");
                swSketchMgr.InsertSketch(true);

                // Create circle for bolt hole - M12 clearance hole (13mm diameter)
                // Position at center of the slot body, centered horizontally and vertically in the slot
                iSwApp.SendMsgToUser("  Creating circle 13mm diameter at Y=11.5mm...");
                swSketchMgr.CreateCircleByRadius(0, 0.0115, 0, 0.0065);  // 13mm diameter hole, centered at Y=11.5mm

                // Exit sketch
                iSwApp.SendMsgToUser("  Exiting hole sketch...");
                swSketchMgr.InsertSketch(true);

                // Create cut extrude to create the hole (through all in both directions)
                iSwApp.SendMsgToUser("  Creating cut feature (through all)...");
                IFeature holeFeature = swFeatMgr.FeatureCut4(true, false, false, 
                    (int)swEndConditions_e.swEndCondThroughAll, (int)swEndConditions_e.swEndCondThroughAll,
                    0.0, 0.0, false, false, false, false, 0.0, 0.0, false, false, false, false, false, true, true, true, false, false, 
                    (int)swStartConditions_e.swStartSketchPlane, 0.0, false, false);

                if (holeFeature == null)
                {
                    iSwApp.SendMsgToUser("  FAILED: FeatureCut4 returned null for hole");
                    iSwApp.SendMsgToUser("  Check: sketch valid, geometry exists, cut parameters correct");
                    return false;
                }

                iSwApp.SendMsgToUser("  Hole created successfully!");
                return true;
            }
            catch (Exception ex)
            {
                iSwApp.SendMsgToUser($"  EXCEPTION in CreateThreadHole: {ex.Message}");
                return false;
            }
        }
        #endregion

        #region Event Methods
        public bool AttachEventHandlers()
        {
            AttachSwEvents();
            //Listen for events on all currently open docs
            AttachEventsToAllDocuments();
            return true;
        }

        private bool AttachSwEvents()
        {
            try
            {
                SwEventPtr.ActiveDocChangeNotify += new DSldWorksEvents_ActiveDocChangeNotifyEventHandler(OnDocChange);
                SwEventPtr.DocumentLoadNotify2 += new DSldWorksEvents_DocumentLoadNotify2EventHandler(OnDocLoad);
                SwEventPtr.FileNewNotify2 += new DSldWorksEvents_FileNewNotify2EventHandler(OnFileNew);
                SwEventPtr.ActiveModelDocChangeNotify += new DSldWorksEvents_ActiveModelDocChangeNotifyEventHandler(OnModelChange);
                SwEventPtr.FileOpenPostNotify += new DSldWorksEvents_FileOpenPostNotifyEventHandler(FileOpenPostNotify);
                return true;
            }
            catch (Exception e)
            {
                Console.WriteLine(e.Message);
                return false;
            }
        }



        private bool DetachSwEvents()
        {
            try
            {
                SwEventPtr.ActiveDocChangeNotify -= new DSldWorksEvents_ActiveDocChangeNotifyEventHandler(OnDocChange);
                SwEventPtr.DocumentLoadNotify2 -= new DSldWorksEvents_DocumentLoadNotify2EventHandler(OnDocLoad);
                SwEventPtr.FileNewNotify2 -= new DSldWorksEvents_FileNewNotify2EventHandler(OnFileNew);
                SwEventPtr.ActiveModelDocChangeNotify -= new DSldWorksEvents_ActiveModelDocChangeNotifyEventHandler(OnModelChange);
                SwEventPtr.FileOpenPostNotify -= new DSldWorksEvents_FileOpenPostNotifyEventHandler(FileOpenPostNotify);
                return true;
            }
            catch (Exception e)
            {
                Console.WriteLine(e.Message);
                return false;
            }

        }

        public void AttachEventsToAllDocuments()
        {
            ModelDoc2 modDoc = (ModelDoc2)iSwApp.GetFirstDocument();
            while (modDoc != null)
            {
                if (!openDocs.Contains(modDoc))
                {
                    AttachModelDocEventHandler(modDoc);
                }
                else if (openDocs.Contains(modDoc))
                {
                    bool connected = false;
                    DocumentEventHandler docHandler = (DocumentEventHandler)openDocs[modDoc];
                    if (docHandler != null)
                    {
                        connected = docHandler.ConnectModelViews();
                    }
                }

                modDoc = (ModelDoc2)modDoc.GetNext();
            }
        }

        public bool AttachModelDocEventHandler(ModelDoc2 modDoc)
        {
            if (modDoc == null)
                return false;

            DocumentEventHandler docHandler = null;

            if (!openDocs.Contains(modDoc))
            {
                switch (modDoc.GetType())
                {
                    case (int)swDocumentTypes_e.swDocPART:
                        {
                            docHandler = new PartEventHandler(modDoc, this);
                            break;
                        }
                    case (int)swDocumentTypes_e.swDocASSEMBLY:
                        {
                            docHandler = new AssemblyEventHandler(modDoc, this);
                            break;
                        }
                    case (int)swDocumentTypes_e.swDocDRAWING:
                        {
                            docHandler = new DrawingEventHandler(modDoc, this);
                            break;
                        }
                    default:
                        {
                            return false; //Unsupported document type
                        }
                }
                docHandler.AttachEventHandlers();
                openDocs.Add(modDoc, docHandler);
            }
            return true;
        }

        public bool DetachModelEventHandler(ModelDoc2 modDoc)
        {
            DocumentEventHandler docHandler;
            docHandler = (DocumentEventHandler)openDocs[modDoc];
            openDocs.Remove(modDoc);
            modDoc = null;
            docHandler = null;
            return true;
        }

        public bool DetachEventHandlers()
        {
            DetachSwEvents();

            //Close events on all currently open docs
            DocumentEventHandler docHandler;
            int numKeys = openDocs.Count;
            object[] keys = new Object[numKeys];

            //Remove all document event handlers
            openDocs.Keys.CopyTo(keys, 0);
            foreach (ModelDoc2 key in keys)
            {
                docHandler = (DocumentEventHandler)openDocs[key];
                docHandler.DetachEventHandlers(); //This also removes the pair from the hash
                docHandler = null;
            }
            return true;
        }
        #endregion

        #region Event Handlers
        //Events
        public int OnDocChange()
        {
            return 0;
        }

        public int OnDocLoad(string docTitle, string docPath)
        {
            return 0;
        }

        int FileOpenPostNotify(string FileName)
        {
            AttachEventsToAllDocuments();
            return 0;
        }

        public int OnFileNew(object newDoc, int docType, string templateName)
        {
            AttachEventsToAllDocuments();
            return 0;
        }

        public int OnModelChange()
        {
            return 0;
        }

        #endregion
    }

}
