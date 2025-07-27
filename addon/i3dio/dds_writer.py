import numpy as np
import struct
from .debugging import addon_logger as logger


DDS_MAGIC = b'DDS '

# DDS_HEADER flags
DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PIXELFORMAT = 0x1000
DDSD_MIPMAPCOUNT = 0x20000
DDSD_DEPTH = 0x800000

# DDS_PIXELFORMAT flags
DDPF_FOURCC = 0x4

# DDSCAPS flags
DDSCAPS_TEXTURE = 0x1000

# DX10 specific constants
DXGI_FORMAT_R16G16B16A16_FLOAT = 10
DDS_RESOURCE_DIMENSION_TEXTURE2D = 3


def write_dds_dx10(filepath: str, arr: np.ndarray) -> None:
    """
    Write a DX10 DDS (R16G16B16A16_FLOAT, 2D array) from numpy array
    arr: shape (array_size, Z, Y, X, 4), dtype float16
    """
    array_size, height, width, channels = arr.shape
    assert channels == 4, "Channels must be 4 (RGBA)"
    assert arr.dtype == np.float16, "Must be float16 array"

    def dword(value: int) -> bytes:
        return struct.pack('<I', value)

    dwFlags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_MIPMAPCOUNT | DDSD_DEPTH

    header = bytearray()
    header += dword(124)      # dwSize
    header += dword(dwFlags)  # Flags
    header += dword(height)   # Height
    header += dword(width)    # Width
    header += dword(0)        # dwPitchOrLinearSize
    header += dword(0)        # dwDepth
    header += dword(0)        # dwMipMapCount

    # Giants specific
    reserved1 = [0] * 11
    reserved1[0] = 0x288AE8D9  # GS_DDS_HEADER_EXT_MAGIC_TAG
    reserved1[2] = 0x2         # DDS_EXTENDED_ALLOW_RAW
    header += b''.join(dword(x) for x in reserved1)

    # DDS_PIXELFORMAT (32 bytes)
    header += dword(32)               # dwSize
    header += dword(DDPF_FOURCC)      # dwFlags
    header += b'DX10'                 # dwFourCC
    header += dword(0)                # dwRGBBitCount
    header += dword(0)                # dwRBitMask
    header += dword(0)                # dwGBitMask
    header += dword(0)                # dwBBitMask
    header += dword(0)                # dwABitMask

    header += dword(DDSCAPS_TEXTURE)  # dwCaps
    header += dword(0)                # dwCaps2
    header += dword(0)                # dwCaps3
    header += dword(0)                # dwCaps4
    header += dword(0)                # dwReserved2

    # DDS_HEADER_DXT10 (20 bytes)
    DXGI_FORMAT_R16G16B16A16_FLOAT = 10
    DDS_RESOURCE_DIMENSION_TEXTURE2D = 3
    header_dx10 = bytearray()
    header_dx10 += dword(DXGI_FORMAT_R16G16B16A16_FLOAT)    # dxgiFormat
    header_dx10 += dword(DDS_RESOURCE_DIMENSION_TEXTURE2D)  # resourceDimension
    header_dx10 += dword(0)                                 # miscFlag
    header_dx10 += dword(array_size)                        # arraySize
    header_dx10 += dword(0)                                 # miscFlags2

    # Write array slices sequentially as required by DDS spec
    data = arr.tobytes(order='C')

    logger.info(f"Writing DDS file: {filepath}")
    logger.debug(f"DDS shape: {arr.shape}, dtype: {arr.dtype}")
    with open(filepath, 'wb') as f:
        f.write(DDS_MAGIC)
        f.write(header)
        f.write(header_dx10)
        f.write(data)
    logger.info(f"Wrote DDS file to {filepath} with shape {arr.shape} and dtype {arr.dtype}")


# Example usage:
if __name__ == "__main__":
    arr = np.zeros((2, 4, 4, 4), dtype=np.float16)  # array_size=2, height=4, width=4, RGBA
    arr[0, 0, 0] = [1, 2, 3, 4]
    write_dds_dx10("test.dds", arr)
