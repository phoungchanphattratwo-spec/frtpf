"""
Add lazy imports at every call site for:
- _DeviceWorker  (settings_mixin.py)
- _MaxChangeWorker (auto_reg_mixin.py, account_mixin.py)
- SafeComboBox (gui.py, login_mixin.py, automation_mixin.py, account_mixin.py)
"""
import re

def read(p):
    with open(p, encoding='utf-8') as f: return f.read()

def write(p, c):
    with open(p, 'w', encoding='utf-8') as f: f.write(c)

def inject_before(content, pattern, import_line):
    """Insert `import_line` on the line before every match of `pattern`."""
    def replacer(m):
        indent = re.match(r'^(\s*)', m.group(0)).group(1)
        return indent + import_line + '\n' + m.group(0)
    return re.sub(pattern, replacer, content, flags=re.MULTILINE)

changes = []

# ── _DeviceWorker in settings_mixin.py ───────────────────────────────────────
p = 'src/ui/mixins/settings_mixin.py'
c = read(p)
if 'from src.workers.device_worker import DeviceWorker' not in c:
    c2 = inject_before(c,
        r'^\s+worker = _DeviceWorker\(',
        'from src.workers.device_worker import DeviceWorker as _DeviceWorker'
    )
    if c2 != c:
        write(p, c2); changes.append(f'_DeviceWorker lazy in {p}')

# ── _MaxChangeWorker in auto_reg_mixin.py ────────────────────────────────────
p = 'src/ui/mixins/auto_reg_mixin.py'
c = read(p)
if 'from src.workers.maxchange_worker import MaxChangeWorker' not in c:
    c2 = inject_before(c,
        r'^\s+self\._maxchange_worker = _MaxChangeWorker\(',
        'from src.workers.maxchange_worker import MaxChangeWorker as _MaxChangeWorker'
    )
    if c2 != c:
        write(p, c2); changes.append(f'_MaxChangeWorker lazy in {p}')

# ── _MaxChangeWorker in account_mixin.py ─────────────────────────────────────
p = 'src/ui/mixins/account_mixin.py'
c = read(p)
if 'from src.workers.maxchange_worker import MaxChangeWorker' not in c:
    c2 = inject_before(c,
        r'^\s+(?:self\._maxchange_worker|worker) = _MaxChangeWorker\(',
        'from src.workers.maxchange_worker import MaxChangeWorker as _MaxChangeWorker'
    )
    if c2 != c:
        write(p, c2); changes.append(f'_MaxChangeWorker lazy in {p}')

# ── SafeComboBox in gui.py ────────────────────────────────────────────────────
p = 'gui.py'
c = read(p)
if 'from src.ui.safe_combobox import SafeComboBox' not in c:
    # Add one import at the top of init_ui (first SafeComboBox usage)
    # Simpler: add a single lazy import right before the first SafeComboBox() call
    first_use = re.search(r'^(\s+)(?:self\.\w+ = |[\w]+ = )SafeComboBox\(\)', c, re.MULTILINE)
    if first_use:
        pos = first_use.start()
        indent = first_use.group(1)
        c = c[:pos] + indent + 'from src.ui.safe_combobox import SafeComboBox\n' + c[pos:]
        write(p, c); changes.append(f'SafeComboBox lazy in {p}')

# ── SafeComboBox in login_mixin.py ────────────────────────────────────────────
p = 'src/ui/mixins/login_mixin.py'
c = read(p)
if 'from src.ui.safe_combobox import SafeComboBox' not in c:
    first_use = re.search(r'^(\s+)\w+ = SafeComboBox\(\)', c, re.MULTILINE)
    if first_use:
        pos = first_use.start()
        indent = first_use.group(1)
        c = c[:pos] + indent + 'from src.ui.safe_combobox import SafeComboBox\n' + c[pos:]
        write(p, c); changes.append(f'SafeComboBox lazy in {p}')

# ── SafeComboBox in automation_mixin.py ──────────────────────────────────────
p = 'src/ui/mixins/automation_mixin.py'
c = read(p)
if 'from src.ui.safe_combobox import SafeComboBox' not in c:
    first_use = re.search(r'^(\s+)\w+ = SafeComboBox\(\)', c, re.MULTILINE)
    if first_use:
        pos = first_use.start()
        indent = first_use.group(1)
        c = c[:pos] + indent + 'from src.ui.safe_combobox import SafeComboBox\n' + c[pos:]
        write(p, c); changes.append(f'SafeComboBox lazy in {p}')

# ── SafeComboBox in account_mixin.py ─────────────────────────────────────────
p = 'src/ui/mixins/account_mixin.py'
c = read(p)
if 'from src.ui.safe_combobox import SafeComboBox' not in c:
    first_use = re.search(r'^(\s+)(?:self\.\w+ = |\w+ = )SafeComboBox\(\)', c, re.MULTILINE)
    if first_use:
        pos = first_use.start()
        indent = first_use.group(1)
        c = c[:pos] + indent + 'from src.ui.safe_combobox import SafeComboBox\n' + c[pos:]
        write(p, c); changes.append(f'SafeComboBox lazy in {p}')

for ch in changes:
    print('OK:', ch)
if not changes:
    print('Nothing to change (all already lazy or not found)')
