import pefile
from pathlib import Path
import struct

def extract_icon(exe_path: Path, out_ico: Path):
    pe = pefile.PE(str(exe_path))
    rt_group_icon = []
    rt_icon = {}
    if not hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
        print('No resources found in exe')
        return False
    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if entry.name is None and entry.id == pefile.RESOURCE_TYPE['RT_GROUP_ICON']:
            # group icon
            for e in entry.directory.entries:
                for ee in e.directory.entries:
                    data_rva = ee.data.struct.OffsetToData
                    size = ee.data.struct.Size
                    data = pe.get_memory_mapped_image()[data_rva:data_rva+size]
                    rt_group_icon.append(data)
        if entry.name is None and entry.id == pefile.RESOURCE_TYPE['RT_ICON']:
            for e in entry.directory.entries:
                for ee in e.directory.entries:
                    data_rva = ee.data.struct.OffsetToData
                    size = ee.data.struct.Size
                    data = pe.get_memory_mapped_image()[data_rva:data_rva+size]
                    # resource ID is e.id
                    rt_icon[e.id] = data

    if not rt_group_icon:
        print('No group icon resource found')
        return False

    # parse first group icon
    grp = rt_group_icon[0]
    # ICONDIR header: 6 bytes
    reserved, type_, count = struct.unpack('<HHH', grp[:6])
    entries = []
    offset = 6
    for i in range(count):
        bWidth, bHeight, bColorCount, bReserved, wPlanes, wBitCount, dwBytesInRes, nID = struct.unpack('<BBBBHHIH', grp[offset:offset+14])
        entries.append((bWidth, bHeight, bColorCount, bReserved, wPlanes, wBitCount, dwBytesInRes, nID))
        offset += 14

    # Build ICO file
    ico_data = bytearray()
    # ICONDIR
    ico_data += struct.pack('<HHH', 0, 1, count)
    # placeholder for directory entries
    dir_entries = bytearray()
    image_data = bytearray()
    current_offset = 6 + 16 * count
    for e in entries:
        bWidth, bHeight, bColorCount, bReserved, wPlanes, wBitCount, dwBytesInRes, nID = e
        img = rt_icon.get(nID)
        if img is None:
            print(f'Icon resource id {nID} not found')
            return False
        # write directory entry
        dir_entries += struct.pack('<BBBBHHII', bWidth, bHeight, bColorCount, bReserved, wPlanes, wBitCount, len(img), current_offset)
        image_data += img
        current_offset += len(img)

    ico_data += dir_entries
    ico_data += image_data

    out_ico.write_bytes(ico_data)
    print(f'WROTE {out_ico}')
    return True

if __name__ == '__main__':
    exe = Path('dist') / 'CSCollectLicence.exe'
    out = Path('dist') / 'extracted_icon.ico'
    ok = extract_icon(exe, out)
    if ok:
        # compare file sizes
        orig = Path('assets') / 'logo.ico'
        if orig.exists():
            print('assets/logo.ico size:', orig.stat().st_size)
        if out.exists():
            print('extracted icon size:', out.stat().st_size)
    else:
        print('failed to extract icon')
