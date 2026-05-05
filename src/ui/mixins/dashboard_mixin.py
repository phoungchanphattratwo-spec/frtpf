"""
DashboardMixin — Dashboard Mixin methods.

Mixin class — never instantiated directly.
MainWindow inherits from it to get these methods.
"""
from __future__ import annotations

from PyQt6.QtWidgets import *  # noqa: F401,F403
from PyQt6.QtCore import *     # noqa: F401,F403
from PyQt6.QtGui import *      # noqa: F401,F403

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

import os, json, threading, time, psutil

from src.i18n.engine import (
    translate as _T, register_widget as _reg,
    _CURRENT_LANG, _get_khmer_font, _REGISTRY as _I18N_REGISTRY,
)
from src.i18n.translations import TRANSLATIONS
from src.automation.url_normalizer import normalize_facebook_url, URL_TYPE_LABELS as _URL_TYPE_LABELS
from src.core.config import CONFIG_FILE

# Project root — 3 levels up from src/ui/mixins/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class DashboardMixin:
    """Mixin — methods are injected into MainWindow via multiple inheritance."""

    def create_stat_card(self, title, value, color, icon_name):
        """Create a statistics card widget."""
        card = QFrame()
        card.setFixedHeight(90)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border-radius: 0px;
                border-left: 3px solid {color};
            }}
        """)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Icon
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(icon_name, color=color).pixmap(32, 32))
        layout.addWidget(icon_label)
        
        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        value_label = QLabel(value)
        value_label.setObjectName("value_label")
        value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        text_layout.addWidget(value_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666666; font-size: 11px;")
        text_layout.addWidget(title_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        return card
    

    def clear_activity(self):
        """Clear the activity log."""
        self.activity_log.clear()
        self.add_activity("Activity log cleared")
    

    def reset_statistics(self):
        """Reset all statistics counters."""
        self.total_accounts = 0
        self.success_count = 0
        self.failed_count = 0
        self.working_count = 0
        self.issues_count = 0
        self.today_count = 0
        self.update_statistics_display()
        self.add_activity("Statistics reset")
    

    def load_dashboard_statistics(self):
        """Load statistics from account backup folder — I/O in background, UI on main thread."""
        import threading

        def _gather():
            total = working = pending = suspended = issues = today = 0
            try:
                from datetime import datetime
                today_str = datetime.now().strftime("%Y-%m-%d")
                backup_folder = os.path.join(_PROJECT_ROOT, "account_backup")
                if not os.path.exists(backup_folder):
                    return
                for folder in os.listdir(backup_folder):
                    json_file = os.path.join(backup_folder, folder, "account_info.json")
                    if os.path.exists(json_file):
                        try:
                            with open(json_file, 'r', encoding='utf-8') as f:
                                d = json.load(f)
                            total += 1
                            status = d.get('status', '').lower()
                            if 'active' in status:   working += 1
                            elif 'pending' in status: pending += 1
                            elif 'suspended' in status: suspended += 1; issues += 1
                            if d.get('created_date', '').startswith(today_str): today += 1
                        except Exception: pass
            except Exception as e:
                print(f"Error loading dashboard statistics: {e}")

            # Update UI on main thread
            from PyQt6.QtCore import QMetaObject, Qt
            self.total_accounts   = total
            self.working_count    = working
            self.pending_count    = pending
            self.suspended_count  = suspended
            self.issues_count     = issues
            self.today_count      = today
            QMetaObject.invokeMethod(self, "_apply_dashboard_statistics", Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=_gather, daemon=True).start()

    @pyqtSlot()
    def _apply_dashboard_statistics(self):
        """Apply gathered statistics to UI — runs on main thread."""
        try:
            self.update_statistics_display()
            self.add_activity(f"Loaded {self.total_accounts} accounts from backup")
        except Exception as e:
            print(f"Error applying dashboard statistics: {e}")
    

    def update_statistics_display(self):
        """Update the statistics labels on dashboard."""
        self.total_accounts_label.setText(str(self.total_accounts))
        self.working_label.setText(str(self.working_count))
        self.issues_label.setText(str(self.issues_count))
        self.today_label.setText(str(self.today_count))

        # Keep stat bar accounts card in sync
        if hasattr(self, 'stat_total_label'):
            self.stat_total_label.setText(str(self.total_accounts))
        
        # Update success rate
        if self.total_accounts > 0:
            rate = (self.working_count / self.total_accounts) * 100
            self.rate_label.setText(f"{rate:.0f}%")
            self.ring_chart.set_percentage(rate)
        else:
            self.rate_label.setText("0%")
            self.ring_chart.set_percentage(0)
        
        # Update category labels
        if hasattr(self, 'cat_active_label'):
            self.cat_active_label.setText(str(self.working_count))
            self.cat_pending_label.setText(str(self.pending_count))
            self.cat_suspended_label.setText(str(self.suspended_count))
            self.cat_new_label.setText(str(self.today_count))
    

    def add_activity(self, message):
        """Add activity to the dashboard activity log."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.activity_log.append(f"[{timestamp}] {message}")
    

    def update_dashboard_status(self, status, color="#888888"):
        """Update the dashboard status label."""
        if hasattr(self, 'dashboard_status_label'):
            self.dashboard_status_label.setText(status)
            self.dashboard_status_label.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;")
        

    def start_system_monitor(self):
        """Start timer to update system stats every second."""
        # Initialize net_io here (deferred from __init__) to avoid blocking startup
        if self.last_net_io is None:
            self.last_net_io = psutil.net_io_counters()
            self.last_net_time = time.time()
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.update_system_stats)
        self.monitor_timer.start(1000)
        # Don't call update_system_stats() immediately - ADB cold start blocks UI
        

    def update_system_stats(self):
        """Update CPU, RAM, Device Count, and Network speed."""
        if not hasattr(self, 'cpu_label') or not self.cpu_label:
            return
        
        try:
            current_time = time.time()
            
            # CPU
            cpu = psutil.cpu_percent(interval=0)
            self.cpu_label.setText(f"{cpu:.1f}%")
            
            # RAM
            ram = psutil.virtual_memory()
            self.ram_label.setText(f"{ram.percent:.1f}%")
            
            # Device Count — run ADB check in background every 15s, never block main thread
            if current_time - self.device_count_last_check >= 15:
                self.device_count_last_check = current_time  # reset immediately to prevent re-entry
                def _check_devices():
                    count = self._get_connected_device_count_sync()
                    if count is not None:
                        self.device_count_cache = count
                        try:
                            self.device_count_label.setText(f"{count} detected")
                        except RuntimeError:
                            pass
                threading.Thread(target=_check_devices, daemon=True).start()
            self.device_count_label.setText(f"{self.device_count_cache} detected")
            
            # Network speed
            current_net = psutil.net_io_counters()
            time_diff = current_time - self.last_net_time
            
            if time_diff > 0:
                download_speed = (current_net.bytes_recv - self.last_net_io.bytes_recv) / time_diff / 1024
                upload_speed = (current_net.bytes_sent - self.last_net_io.bytes_sent) / time_diff / 1024
                self.net_label.setText(f"↓{download_speed:.1f}  ↑{upload_speed:.1f} KB/s")
            
            self.last_net_io = current_net
            self.last_net_time = current_time
        except RuntimeError:
            # Label was deleted, stop the timer
            if hasattr(self, 'monitor_timer'):
                self.monitor_timer.stop()
    

    def _get_xiaowei_device_order(self):
        """Read device sort order from 效卫安卓投屏's IndexedDB. Returns {serial: sort_index} or {}."""
        try:
            import glob, shutil, tempfile, re as _re
            base = os.path.join(os.path.expandvars('%LOCALAPPDATA%'), 'xiaowei', 'EBWebView',
                                'Default', 'IndexedDB')
            # Find the tauri IndexedDB folder
            candidates = glob.glob(os.path.join(base, 'https_tauri.localhost_0.indexeddb.leveldb'))
            if not candidates:
                return {}
            ldb_dir = candidates[0]
            # Copy files to temp (some may be locked)
            tmp = tempfile.mkdtemp(prefix='frt_xw_')
            raw = b""
            for f in glob.glob(os.path.join(ldb_dir, '*')):
                try:
                    dst = os.path.join(tmp, os.path.basename(f))
                    shutil.copy2(f, dst)
                    raw += open(dst, 'rb').read()
                except: pass
            # Parse: \x06serial"\x10<serial>...\x04sortI<byte>
            pattern = rb'\x06serial\"\x10([a-zA-Z0-9]{8,20}).{0,300}?\x04sortI(.)'
            matches = _re.findall(pattern, raw, _re.DOTALL)
            result = {}
            for serial_b, sort_b in matches:
                serial = serial_b.decode('utf-8', errors='ignore')
                result[serial] = sort_b[0]
            # Cleanup temp
            try: shutil.rmtree(tmp)
            except: pass
            return result
        except Exception as e:
            print(f"[xiaowei] Error reading device order: {e}")
            return {}


    def _sync_xiaowei_device_order(self):
        """Sync 效卫's device order to frt_device_numbers.json and return the order dict."""
        import tempfile
        order = self._get_xiaowei_device_order()
        if not order:
            return {}
        # Save to frt_device_numbers.json so tables sort correctly
        num_file = os.path.join(tempfile.gettempdir(), "frt_device_numbers.json")
        try:
            existing = {}
            if os.path.exists(num_file):
                with open(num_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            existing.update(order)
            with open(num_file, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2)
        except: pass
        return order


    def _get_connected_device_count_sync(self):
        """Get number of connected ADB devices - synchronous version."""
        with self.device_count_lock:
            try:
                result = subprocess.run(
                    [self.adb_path, 'devices'],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    encoding='utf-8',
                    errors='ignore',
                    shell=False
                )
                if result.returncode == 0:
                    count = sum(
                        1 for line in result.stdout.strip().split('\n')[1:]
                        if line.strip() and line.strip().endswith('device')
                    )
                    return count
                return None
            except Exception:
                return None
    
