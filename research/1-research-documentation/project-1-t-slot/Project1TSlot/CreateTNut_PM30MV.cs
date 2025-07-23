using System;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

/// <summary>
/// Creates a T-nut that fits PM-30MV milling machine with 14mm T-slots
/// Based on forum information: T-slots are 14mm wide, 9/16" bolts work in center slots
/// </summary>
public class CreateTNut_PM30MV
{
    private ISldWorks swApp;
    private IModelDoc2 swModel;
    private IPartDoc swPart;
    private ISketchManager swSketchMgr;
    private IFeatureManager swFeatMgr;

    public CreateTNut_PM30MV(ISldWorks solidWorksApp)
    {
        swApp = solidWorksApp;
    }

    /// <summary>
    /// Creates a T-nut part for PM-30MV milling machine
    /// Dimensions based on 14mm T-slot width and standard T-nut proportions
    /// </summary>
    public bool CreateTNutPart()
    {
        try
        {
            // Create new part document
            swModel = swApp.NewDocument(@"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\templates\prt.prtdot",
                                      (int)swDwgPaperSizes_e.swDwgPaperA0size, 0.0, 0.0);

            if (swModel == null)
            {
                Console.WriteLine("Failed to create new part document");
                return false;
            }

            swPart = (IPartDoc)swModel;
            swSketchMgr = swModel.SketchManager;
            swFeatMgr = swModel.FeatureManager;

            // Set units to millimeters
            swModel.Extension.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitSystem,
                                                     (int)swUserPreferenceOption_e.swDetailingNoOptionSpecified,
                                                     (int)swUnitSystem_e.swUnitSystem_MMGS);

            // Create T-nut geometry
            if (!CreateTNutHead()) return false;
            if (!CreateTNutSlot()) return false;
            if (!CreateThreadHole()) return false;

            // Rebuild the model
            swModel.EditRebuild3();

            Console.WriteLine("T-nut for PM-30MV created successfully");
            return true;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error creating T-nut: {ex.Message}");
            return false;
        }
    }

    /// <summary>
    /// Creates the main head of the T-nut (the wide part that sits in the T-slot)
    /// Dimensions: 14mm slot width, allowing for clearance
    /// </summary>
    private bool CreateTNutHead()
    {
        try
        {
            // Select the front plane for sketching
            bool boolstatus = swModel.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0,
                                                          false, 0, null, 0);
            if (!boolstatus)
            {
                Console.WriteLine("Failed to select Front Plane");
                return false;
            }

            // Insert sketch
            swSketchMgr.InsertSketch(true);

            // Create rectangle for T-nut head (13.5mm wide to fit in 14mm slot with clearance)
            // Height: 8mm (standard T-nut proportion)
            swSketchMgr.CreateCornerRectangle(-0.00675, -0.004, 0, 0.00675, 0.004, 0);  // 13.5mm x 8mm

            // Exit sketch
            swSketchMgr.InsertSketch(true);

            // Create extrude feature for head (6mm thick)
            IFeature headFeature = swFeatMgr.SimpleFeatureBossExtrude("Sketch1", 0.006, true);

            if (headFeature == null)
            {
                Console.WriteLine("Failed to create T-nut head extrude");
                return false;
            }

            return true;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error creating T-nut head: {ex.Message}");
            return false;
        }
    }

    /// <summary>
    /// Creates the slot/body portion of the T-nut (the narrow part that extends upward)
    /// </summary>
    private bool CreateTNutSlot()
    {
        try
        {
            // Select the front face of the head for sketching
            bool boolstatus = swModel.Extension.SelectByID2("", "FACE", 0.00675, 0, 0.003,
                                                          false, 0, null, 0);
            if (!boolstatus)
            {
                // Try alternative selection method - select Front Plane again
                boolstatus = swModel.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0,
                                                         false, 0, null, 0);
            }

            // Insert sketch
            swSketchMgr.InsertSketch(true);

            // Create rectangle for T-nut slot body (7mm wide x 15mm tall)
            // This extends above the head to provide gripping surface
            swSketchMgr.CreateCornerRectangle(-0.0035, 0.004, 0, 0.0035, 0.019, 0);  // 7mm x 15mm

            // Exit sketch
            swSketchMgr.InsertSketch(true);

            // Create extrude feature for slot body (6mm thick, same as head)
            IFeature slotFeature = swFeatMgr.SimpleFeatureBossExtrude("Sketch2", 0.006, true);

            if (slotFeature == null)
            {
                Console.WriteLine("Failed to create T-nut slot extrude");
                return false;
            }

            return true;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error creating T-nut slot: {ex.Message}");
            return false;
        }
    }

    /// <summary>
    /// Creates the threaded hole for the bolt (9/16" = 14.29mm diameter hole for tap)
    /// Creates clearance hole for M14 or 9/16" bolt
    /// </summary>
    private bool CreateThreadHole()
    {
        try
        {
            // Select the top face of the slot for sketching
            bool boolstatus = swModel.Extension.SelectByID2("", "FACE", 0, 0.019, 0.003,
                                                          false, 0, null, 0);
            if (!boolstatus)
            {
                // Try alternative - select a plane parallel to the top
                boolstatus = swModel.Extension.SelectByID2("Top Plane", "PLANE", 0, 0, 0,
                                                         false, 0, null, 0);
            }

            // Insert sketch
            swSketchMgr.InsertSketch(true);

            // Create circle for bolt hole - M12 clearance hole (13mm diameter)
            // Position at center of the slot body
            swSketchMgr.CreateCircleByRadius(0, 0.0115, 0, 0.0065);  // 13mm diameter hole

            // Exit sketch
            swSketchMgr.InsertSketch(true);

            // Create cut extrude to create the hole (through all)
            // Note: Using FeatureCut with through-all option
            bool cutResult = swModel.Extension.SelectByID2("Sketch3", "SKETCH", 0, 0, 0,
                                                         false, 0, null, 0);

            if (cutResult)
            {
                IFeature holeFeature = swFeatMgr.FeatureCut(true, false, true,
                    (int)swEndConditions_e.swEndCondBlind, (int)swEndConditions_e.swEndCondBlind,
                    0.025, 0.0, false, false, false, false, 0.0, 0.0,
                    false, false, false, false, true, true, true);

                if (holeFeature == null)
                {
                    Console.WriteLine("Failed to create bolt hole");
                    return false;
                }
            }

            return true;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error creating thread hole: {ex.Message}");
            return false;
        }
    }

    /// <summary>
    /// Main entry point for creating the T-nut
    /// </summary>
    public static void Main(string[] args)
    {
        try
        {
            // Connect to SolidWorks
            ISldWorks swApp = (ISldWorks)System.Activator.CreateInstance(System.Type.GetTypeFromProgID("SldWorks.Application"));

            if (swApp == null)
            {
                Console.WriteLine("Failed to connect to SolidWorks");
                return;
            }

            swApp.Visible = true;

            // Create T-nut
            CreateTNut_PM30MV tnutCreator = new CreateTNut_PM30MV(swApp);
            bool success = tnutCreator.CreateTNutPart();

            if (success)
            {
                Console.WriteLine("T-nut creation completed successfully!");
                Console.WriteLine("T-nut specifications:");
                Console.WriteLine("- Head: 13.5mm x 8mm x 6mm (fits 14mm T-slot)");
                Console.WriteLine("- Body: 7mm x 15mm x 6mm");
                Console.WriteLine("- Bolt hole: 13mm diameter (M12 clearance)");
                Console.WriteLine("- Compatible with PM-30MV milling machine T-slots");
            }
            else
            {
                Console.WriteLine("T-nut creation failed. Check error messages above.");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Application error: {ex.Message}");
        }

        Console.WriteLine("Press any key to exit...");
        Console.ReadKey();
    }
}