using System;
using SolidWorks.Interop.sldworks;

namespace SolidWorksRenders
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("SolidWorks Renders - Eccentric Cam Generator");
            Console.WriteLine("=============================================\n");

            try
            {
                // Create SolidWorks application instance
                Console.WriteLine("Starting SolidWorks...");
                ISldWorks swApp = new SldWorks();

                if (swApp == null)
                {
                    Console.WriteLine("ERROR: Failed to start SolidWorks application.");
                    Console.WriteLine("Please ensure SolidWorks is installed.");
                    return;
                }

                // Make SolidWorks visible
                swApp.Visible = true;

                Console.WriteLine($"Connected to SolidWorks {swApp.RevisionNumber()}\n");

                // Create the eccentric cam
                Console.WriteLine("Creating eccentric cam...");
                EccentricCam.Create(swApp);

                Console.WriteLine("\nDone! Check SolidWorks for the generated part.");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"\nERROR: {ex.Message}");
                Console.WriteLine($"Stack trace:\n{ex.StackTrace}");
            }
        }
    }
}
