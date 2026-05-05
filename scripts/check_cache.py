import json, os, tempfile
sf = os.path.join(tempfile.gettempdir(), 'frt_device_spoof_cache.json')
if os.path.exists(sf):
    print(open(sf).read())
else:
    print('No spoof cache')
