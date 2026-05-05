import json, os, tempfile, re

sf = os.path.join(tempfile.gettempdir(), 'frt_device_spoof_cache.json')
raw = open(sf).read()
# Find all JSON objects and merge them
matches = re.findall(r'\{[^{}]+\}', raw)
merged = {}
for m in matches:
    try:
        merged.update(json.loads(m))
    except: pass
with open(sf, 'w') as f:
    json.dump(merged, f, indent=2)
print('Fixed:', merged)
