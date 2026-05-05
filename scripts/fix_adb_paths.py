content = open('gui.py', encoding='utf-8').read()

# Fix hardcoded adb paths in device changer methods (lines ~10000-10130)
# These are inside class methods so they should use self.adb_path
old = "'platform-tools\\\\adb.exe', '-s', device_id"
new = "self.adb_path, '-s', device_id"

count = content.count(old)
print(f"Found {count} occurrences of hardcoded adb path with device_id")
content = content.replace(old, new)

open('gui.py', 'w', encoding='utf-8').write(content)
print('Done')
