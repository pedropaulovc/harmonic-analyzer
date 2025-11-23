using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorksRenders;

namespace SolidWorksRenders
{
    class Program
    {
        static void Main(string[] args)
        {
            // TODO: In the future, this could be selected via command line args or config
            IPartCreator partCreator = CreatePartCreator(args);

            Console.WriteLine($"{partCreator.PartName} Creator for SolidWorks");
            Console.WriteLine(new string('=', partCreator.PartName.Length + 24) + "\n");

            ISldWorks? swApp = null;

            try
            {
                swApp = ConnectToSolidWorks();
                Console.WriteLine($"Connected to SolidWorks {swApp.RevisionNumber()}\n");

                // Create the part
                Console.WriteLine($"Creating {partCreator.PartName.ToLower()} part...");
                IModelDoc2 model = partCreator.CreatePart();

                if (model != null)
                {
                    Console.WriteLine($"SUCCESS: {partCreator.PartName} created successfully!");
                    Console.WriteLine($"Model name: {model.GetTitle()}");

                    // Zoom to fit
                    model.ViewZoomtofit2();

                    // Print part-specific details
                    partCreator.PrintPartDetails();

                    Console.WriteLine("\nThe part is now open in SolidWorks.");
                    Console.WriteLine("Save the part using File > Save in SolidWorks.");
                }
                else
                {
                    Console.Error.WriteLine($"ERROR: Failed to create {partCreator.PartName.ToLower()}.");
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

        /// <summary>
        /// Creates the appropriate part creator based on configuration
        /// In the future, this could read from args or a config file
        /// </summary>
        private static IPartCreator CreatePartCreator(string[] args)
        {
            // For now, we only have eccentric cam, but this is where you would
            // add logic to select different part types in the future
            ISldWorks swApp = ConnectToSolidWorks();
            return new EccentricCam(swApp);
        }

        /// <summary>
        /// Connects to a running SolidWorks instance or creates a new one
        /// </summary>
        private static ISldWorks ConnectToSolidWorks()
        {
            Console.WriteLine("Connecting to SolidWorks...");

            try
            {
                ISldWorks? swApp = (ISldWorks?)Marshal.GetActiveObject("SldWorks.Application");
                if (swApp != null)
                {
                    return swApp;
                }
            }
            catch (COMException)
            {
                // No running instance found, will create new one below
            }

            Console.WriteLine("No running SolidWorks instance found. Starting SolidWorks...");

            // Create a new instance of SolidWorks
            Type? swType = Type.GetTypeFromProgID("SldWorks.Application");
            if (swType == null)
            {
                throw new InvalidOperationException("SolidWorks is not installed or not properly registered.");
            }

            ISldWorks? newSwApp = (ISldWorks?)Activator.CreateInstance(swType);
            if (newSwApp == null)
            {
                throw new InvalidOperationException("Failed to create SolidWorks instance.");
            }

            // Make SolidWorks visible
            newSwApp.Visible = true;

            return newSwApp;
        }
    }
}
