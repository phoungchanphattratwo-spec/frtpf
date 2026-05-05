import re, os, glob, shutil, tempfile, ctypes, ctypes.wintypes

# ── 1. Read IndexedDB for device order ──────────────────────────────────────
base = r'C:\Users\KLS COMPUTER\AppData\Local\xiaowei\EBWebView\Default\IndexedDB\https_tauri.localhost_0.indexeddb.leveldb'
tmp = tempfile.mkdtemp()
raw = b""
for f in glob.glob(os.path.join(base, '*')):
    try:
        dst = os.path.join(tmp, os.path.basename(f))
        shutil.copy2(f, dst)
        raw += open(dst, 'rb').read()
    except: pass

text = raw.decode('utf-8', errors='ignore')

# Pattern: "serial"\x10<serial_value>  ...  sortI<1byte_sort>
# From raw dump we saw: "\x06serial"\x10<serial>...\x04sortI\x06
pattern = rb'\x06serial\"\x10([a-zA-Z0-9]{8,20}).{0,300}?\x04sortI(.)'
matches = re.findall(pattern, raw, re.DOTALL)

print("=== Device Order from 效卫 IndexedDB ===")
devices = []
for serial_b, sort_b in matches:
    serial = serial_b.decode('utf-8', errors='ignore')
    sort_val = sort_b[0]  # byte value = sort order
    devices.append((sort_val, serial))

devices.sort()
for sort_val, serial in devices:
    print(f"  sort={sort_val:3d}  serial={serial}")

# ── 2. Read window titles ────────────────────────────────────────────────────
EnumWindows = ctypes.windll.user32.EnumWindows
GetWindowText = ctypes.windll.user32.GetWindowTextW
GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
IsWindowVisible = ctypes.windll.user32.IsWindowVisible

windows = []
def callback(hwnd, _):
    if IsWindowVisible(hwnd):
        length = GetWindowTextLength(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            GetWindowText(hwnd, buf, length + 1)
            title = buf.value
            if title: windows.append(title)
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
EnumWindows(WNDENUMPROC(callback), 0)

print("\n=== Window Titles (xiaowei related) ===")
for w in windows:
    if any(x in w.lower() for x in ['xiaowei', '效卫', '投屏', 'sm-', 'device', 'android']):
        print(f"  {w}")
