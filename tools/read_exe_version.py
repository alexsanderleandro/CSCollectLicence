import pefile
p='dist\\CSCollectLicence.exe'
pe=pefile.PE(p)
try:
    st = getattr(pe, 'FileInfo', None)
    if not st:
        print('No FileInfo found')
    else:
        # FileInfo may be a list of entries or nested lists — handle both
        def walk(items):
            for fileinfo in items:
                if hasattr(fileinfo, 'Key') and fileinfo.Key == b'StringFileInfo':
                    for stt in getattr(fileinfo, 'StringTable', []):
                        for k,v in stt.entries.items():
                            print(f"{k.decode()} : {v.decode()}")
                elif isinstance(fileinfo, (list, tuple)):
                    walk(fileinfo)
        walk(st)
except Exception as e:
    print('error', e)
