using System;
using System.Runtime.InteropServices;

namespace SolidWorks.Interop.sldworks
{
    /// <summary>
    /// Interface representing fault entity error code functionality
    /// </summary>
    [ComImport]
    [Guid("YOUR-GUID-HERE")] // Replace with actual GUID from SOLIDWORKS type library
    [InterfaceType(ComInterfaceType.InterfaceIsDual)]
    public interface IFaultEntity
    {
        /// <summary>
        /// Gets the error for the fault for the specified entity.
        /// </summary>
        /// <param name="Index">0-based index number indicating the entity with the fault</param>
        /// <returns>Error as defined by swFaultEntityErrorCode_e; -1 indicates an unknown error</returns>
        /// <remarks>
        /// To determine the value for index, call IFaultEntity.Count before calling this property.
        /// Call IFaultEntity.Entity2 to get the entity.
        /// </remarks>
        [DispId(1)] // Replace with actual DispId if known
        int get_ErrorCode(int Index);

        /// <summary>
        /// Gets the number of fault entities
        /// </summary>
        int Count { get; }

        /// <summary>
        /// Gets the entity at the specified index
        /// </summary>
        /// <param name="Index">0-based index</param>
        /// <returns>Entity object</returns>
        object Entity2(int Index);
    }

    /// <summary>
    /// Error codes for fault entities as defined by swFaultEntityErrorCode_e
    /// </summary>
    public enum swFaultEntityErrorCode_e
    {
        // Add specific error codes from SOLIDWORKS API documentation
        swFaultEntityErrorCode_Unknown = -1,
        // Add other error codes as needed
    }

    /// <summary>
    /// Example implementation/wrapper class for IFaultEntity
    /// </summary>
    public class FaultEntityWrapper
    {
        private readonly IFaultEntity _faultEntity;

        public FaultEntityWrapper(IFaultEntity faultEntity)
        {
            _faultEntity = faultEntity ?? throw new ArgumentNullException(nameof(faultEntity));
        }

        /// <summary>
        /// Gets the error code for the fault at the specified index
        /// </summary>
        /// <param name="index">0-based index number indicating the entity with the fault</param>
        /// <returns>Error code; -1 indicates an unknown error</returns>
        public int GetErrorCode(int index)
        {
            if (index < 0 || index >= _faultEntity.Count)
            {
                throw new ArgumentOutOfRangeException(nameof(index),
                    $"Index must be between 0 and {_faultEntity.Count - 1}");
            }

            return _faultEntity.get_ErrorCode(index);
        }

        /// <summary>
        /// Gets the total number of fault entities
        /// </summary>
        public int Count => _faultEntity.Count;

        /// <summary>
        /// Gets the entity at the specified index
        /// </summary>
        public object GetEntity(int index)
        {
            if (index < 0 || index >= _faultEntity.Count)
            {
                throw new ArgumentOutOfRangeException(nameof(index),
                    $"Index must be between 0 and {_faultEntity.Count - 1}");
            }

            return _faultEntity.Entity2(index);
        }
    }
}
