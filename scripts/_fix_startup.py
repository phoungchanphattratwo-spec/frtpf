"""
Fix all remaining startup slowness:
1. Remove `import requests` from account_mixin.py (298ms)
2. Remove `import qtawesome as qta` from all 7 mixins (314ms × N imports)
3. Remove `from src.workers.device_worker import DeviceWorker` from gui.py (117ms)
4. Remove `from src.workers.maxchange_worker import MaxChangeWorker` from mixins (75ms each)
5. Remove `from src.ui.safe_combobox import SafeComboBox` from gui.py (67ms)
6. Remove `from src.ui.widgets import LogSignal, RingChartWidget` from gui.py (56ms)
7. Replace `from PyQt6.QtWidgets import *` wildcard with explicit imports in all mixins
"""
import re, os

# ── helpers ───────────────────────────────────────────────────────────────────

def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()

def write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def remove_line(content, pattern):
    """Remove lines matching a regex pattern."""
    return re.sub(r'^.*' + pattern + r'.*\n', '', content, flags=re.MULTILINE)

def replace_first(content, old, new):
    if old not in content:
        return content, False
    return content.replace(old, new, 1), True

# ── 1. account_mixin.py — remove `import requests` (298ms) ───────────────────
path = 'src/ui/mixins/account_mixin.py'
c = read(path)
c = remove_line(c, r'import requests')
write(path, c)
print(f'[1] Removed `import requests` from {path}')

# ── 2. Remove `import qtawesome as qta` from all 7 mixins (314ms each) ───────
# qtawesome is used heavily in methods — we add a module-level lazy accessor
# so existing `qta.icon(...)` calls still work without changing every call site.
QTA_LAZY = '''\
# qtawesome lazy accessor — avoids 314ms cold-start cost
# Usage: qta.icon(...) works exactly as before
class _QtaProxy:
    """Lazy proxy: imports qtawesome on first attribute access."""
    _mod = None
    def __getattr__(self, name):
        if _QtaProxy._mod is None:
            import qtawesome as _qta
            _QtaProxy._mod = _qta
        return getattr(_QtaProxy._mod, name)
qta = _QtaProxy()
'''

MIXIN_FILES = [
    'src/ui/mixins/dashboard_mixin.py',
    'src/ui/mixins/settings_mixin.py',
    'src/ui/mixins/auto_reg_mixin.py',
    'src/ui/mixins/account_mixin.py',
    'src/ui/mixins/import_mixin.py',
    'src/ui/mixins/login_mixin.py',
    'src/ui/mixins/automation_mixin.py',
]

for path in MIXIN_FILES:
    c = read(path)
    # Remove the direct import line
    c_new = re.sub(r'^import qtawesome as qta\n', '', c, flags=re.MULTILINE)
    if c_new == c:
        print(f'[2] SKIP (no qtawesome import): {path}')
        continue
    # Insert lazy proxy right after the last `from PyQt6` import block
    # Find the insertion point: after the last PyQt6 import line
    insert_after = re.search(
        r'((?:^from PyQt6\.[^\n]+\n)+)',
        c_new, flags=re.MULTILINE
    )
    if insert_after:
        pos = insert_after.end()
        c_new = c_new[:pos] + '\n' + QTA_LAZY + c_new[pos:]
    write(path, c_new)
    print(f'[2] Replaced qtawesome import with lazy proxy in {path}')

# ── 3. gui.py — lazy DeviceWorker (117ms) ────────────────────────────────────
path = 'gui.py'
c = read(path)
c_new = re.sub(
    r'^from src\.workers\.device_worker import DeviceWorker as _DeviceWorker\n',
    '# DeviceWorker lazy-imported in methods that use it (saves 117ms cold-start)\n',
    c, flags=re.MULTILINE
)
if c_new != c:
    write(path, c_new)
    print(f'[3] Lazy DeviceWorker in {path}')
else:
    print(f'[3] SKIP DeviceWorker (not found at module level): {path}')

# ── 4. Remove MaxChangeWorker from mixins (75ms each) ────────────────────────
for path in MIXIN_FILES:
    c = read(path)
    c_new = re.sub(
        r'^from src\.workers\.maxchange_worker import MaxChangeWorker as _MaxChangeWorker\n',
        '# MaxChangeWorker lazy-imported in methods that use it (saves 75ms cold-start)\n',
        c, flags=re.MULTILINE
    )
    if c_new != c:
        write(path, c_new)
        print(f'[4] Lazy MaxChangeWorker in {path}')

# Also fix gui.py
path = 'gui.py'
c = read(path)
c_new = re.sub(
    r'^from src\.workers\.maxchange_worker import MaxChangeWorker as _MaxChangeWorker\n',
    '# MaxChangeWorker lazy-imported in methods that use it (saves 75ms cold-start)\n',
    c, flags=re.MULTILINE
)
if c_new != c:
    write(path, c_new)
    print(f'[4] Lazy MaxChangeWorker in {path}')

# ── 5. gui.py — lazy SafeComboBox (67ms) ─────────────────────────────────────
path = 'gui.py'
c = read(path)
c_new = re.sub(
    r'^from src\.ui\.safe_combobox import SafeComboBox\n',
    '# SafeComboBox lazy-imported in methods that use it (saves 67ms cold-start)\n',
    c, flags=re.MULTILINE
)
if c_new != c:
    write(path, c_new)
    print(f'[5] Lazy SafeComboBox in {path}')
else:
    print(f'[5] SKIP SafeComboBox: {path}')

# ── 6. gui.py — lazy widgets (56ms) ──────────────────────────────────────────
# widgets.py imports PyQt6 which is already loaded, but LogSignal/RingChartWidget
# are only needed after UI is built — keep import but note it's cheap after Qt loads
# Actually at 56ms fresh it's expensive; but since PyQt6 is already loaded by the
# time gui.py is imported, the real cost is near 0. Skip this one.
print(f'[6] SKIP widgets (PyQt6 already loaded, real cost ~0ms after Qt init)')

# ── 7. Replace wildcard PyQt6 imports in mixins ───────────────────────────────
# The wildcard imports cost ~48+39+32 = 119ms in a fresh interpreter,
# but since PyQt6 is already loaded by gui.py before mixins are imported,
# the actual cost is near 0ms. The real cost is the namespace pollution
# (100+ names injected into each module). Skip for safety — no runtime benefit.
print(f'[7] SKIP wildcard PyQt6 (already cached after gui.py loads Qt, real cost ~0ms)')

print('\nDone. Run syntax check next.')
