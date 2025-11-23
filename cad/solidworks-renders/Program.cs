using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorksRenders;

namespace EccentricCamApp
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("Eccentric Cam Creator for SolidWorks");
            Console.WriteLine("====================================\n");

            ISldWorks? swApp = null;

            try
            {
                // Try to get a running instance of SolidWorks
                Console.WriteLine("Connecting to SolidWorks...");
                swApp = (ISldWorks?)Marshal.GetActiveObject("SldWorks.Application");

                if (swApp == null)
                {
                    Console.WriteLine("No running SolidWorks instance found. Starting SolidWorks...");

                    // Create a new instance of SolidWorks
                    Type? swType = Type.GetTypeFromProgID("SldWorks.Application");
                    if (swType == null)
                    {
                        Console.Error.WriteLine("ERROR: SolidWorks is not installed or not properly registered.");
                        return;
                    }

                    swApp = (ISldWorks?)Activator.CreateInstance(swType);
                    if (swApp == null)
                    {
                        Console.Error.WriteLine("ERROR: Failed to create SolidWorks instance.");
                        return;
                    }

                    // Make SolidWorks visible
                    swApp.Visible = true;
                }

                Console.WriteLine($"Connected to SolidWorks {swApp.RevisionNumber()}\n");

                // Create the eccentric cam
                Console.WriteLine("Creating eccentric cam part...");
                EccentricCam camCreator = new EccentricCam(swApp);
                IModelDoc2 camModel = camCreator.CreatePart();

                if (camModel != null)
                {
                    Console.WriteLine("SUCCESS: Eccentric cam created successfully!");
                    Console.WriteLine($"Model name: {camModel.GetTitle()}");

                    // Zoom to fit
                    camModel.ViewZoomtofit2();

                    Console.WriteLine("\nPart Details:");
                    Console.WriteLine("- Cam diameter: 2.0 inches");
                    Console.WriteLine("- Cam thickness: 0.4 inches");
                    Console.WriteLine("- Shaft diameter: 0.375 inches (3/8\")");
                    Console.WriteLine("- Eccentricity: 0.2 inches");
                    Console.WriteLine("- Keyway width: 0.125 inches (1/8\")");
                    Console.WriteLine("- Keyway depth: 0.06 inches");
                    Console.WriteLine("\nThe part is now open in SolidWorks.");
                    Console.WriteLine("Save the part using File > Save in SolidWorks.");
                }
                else
                {
                    Console.Error.WriteLine("ERROR: Failed to create eccentric cam.");
                }
            }
            catch (COMException comEx)
            {
                Console.Error.WriteLine($"COM ERROR: {comEx.Message}");
                Console.Error.WriteLine($"HRESULT: 0x{comEx.ErrorCode:X}");
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"ERROR: {ex.Message}");
                Console.Error.WriteLine($"Stack trace: {ex.StackTrace}");
            }

            Console.WriteLine("\nPress any key to exit...");
            Console.ReadKey();
        }
    }
}
