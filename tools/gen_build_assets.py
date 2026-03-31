import re
from pathlib import Path
import sys

def make_version_build():
    vp = Path('version.py')
    vt_path = Path('version.txt')
    out = Path('version_build.txt')
    if not vt_path.exists():
        print('version.txt not found; skipping version embed')
        return
    vp_text = vp.read_text(encoding='utf-8') if vp.exists() else ''
    m = re.search(r"VERSION\s*=\s*'([^']*)'", vp_text)
    ver_full = m.group(1).strip() if m else '0.0.0'
    ver_core = ver_full.split()[0]
    parts = ver_core.split('.')
    while len(parts) < 4:
        parts.append('0')
    parts = parts[:4]
    filevers = ','.join(str(int(p)) if p.isdigit() else '0' for p in parts)

    vt = vt_path.read_text(encoding='utf-8')
    vt = re.sub(r'filevers=\([^)]*\)', f'filevers=({filevers})', vt)
    vt = re.sub(r'prodvers=\([^)]*\)', f'prodvers=({filevers})', vt)
    vt = re.sub(r"FileVersion', '.*?'", f"FileVersion', '{ver_full}'", vt)
    vt = re.sub(r"ProductVersion', '.*?'", f"ProductVersion', '{ver_full}'", vt)
    # Force consistent product and file names to CSCollectLicence
    vt = re.sub(r"StringStruct\('InternalName', '.*?'\)", "StringStruct('InternalName', 'CSCollectLicence.exe')", vt)
    vt = re.sub(r"StringStruct\('OriginalFilename', '.*?'\)", "StringStruct('OriginalFilename', 'CSCollectLicence.exe')", vt)
    vt = re.sub(r"StringStruct\('ProductName', '.*?'\)", "StringStruct('ProductName', 'CSCollectLicence')", vt)
    out.write_text(vt, encoding='utf-8')
    print('WROTE version_build.txt')


def make_icon():
    png = Path('assets') / 'logo.png'
    ico = Path('assets') / 'logo.ico'
    if ico.exists():
        print('assets/logo.ico already exists')
        return
    if not png.exists():
        print('no assets/logo.png found; skipping icon generation')
        return
    try:
        from PIL import Image
    except Exception as e:
        print('Pillow not installed; cannot convert PNG to ICO')
        return
    im = Image.open(png)
    im.save(ico, format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
    print('WROTE assets/logo.ico')


def main():
    make_version_build()
    make_icon()


if __name__ == '__main__':
    main()
