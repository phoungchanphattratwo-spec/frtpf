"""Measure actual cold-start import time for each heavy module."""
import subprocess, sys, time

imports = [
    ('requests',         'import requests'),
    ('psutil',           'import psutil'),
    ('qtawesome',        'import qtawesome as qta'),
    ('PyQt6.QtWidgets.*','from PyQt6.QtWidgets import *'),
    ('PyQt6.QtCore.*',   'from PyQt6.QtCore import *'),
    ('PyQt6.QtGui.*',    'from PyQt6.QtGui import *'),
    ('translations',     'from src.i18n.translations import TRANSLATIONS'),
    ('i18n.engine',      'from src.i18n.engine import translate'),
    ('url_normalizer',   'from src.automation.url_normalizer import normalize_facebook_url'),
    ('device_worker',    'from src.workers.device_worker import DeviceWorker'),
    ('maxchange_worker', 'from src.workers.maxchange_worker import MaxChangeWorker'),
    ('subprocess_utils', 'from src.core.subprocess_utils import patch_subprocess'),
    ('styles',           'from src.ui.styles import DARK_STYLE'),
    ('widgets',          'from src.ui.widgets import LogSignal'),
    ('safe_combobox',    'from src.ui.safe_combobox import SafeComboBox'),
]

script_tpl = """
import time as t_
s_ = t_.perf_counter()
{stmt}
print(t_.perf_counter()-s_)
"""

results = []
for name, stmt in imports:
    code = script_tpl.format(stmt=stmt)
    r = subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True, text=True, timeout=20
    )
    try:
        ms = float(r.stdout.strip()) * 1000
    except Exception:
        ms = -1
    results.append((name, ms))

results.sort(key=lambda x: -x[1])
print('Import costs (fresh interpreter, ms):')
print('-' * 55)
for name, ms in results:
    bar = '#' * max(0, int(ms / 5))
    flag = '  <-- LAZY?' if ms > 30 else ''
    print(f'  {ms:7.1f}ms  {name:30s}{flag}')
print('-' * 55)
total = sum(ms for _, ms in results if ms > 0)
print(f'  TOTAL: {total:.0f}ms')
