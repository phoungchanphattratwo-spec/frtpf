"""
Facebook Lite Auto Registration Tool — MainWindow (PyQt6)

MainWindow inherits from mixin classes in src/ui/mixins/ for each feature area.
This file contains only the core window lifecycle methods.
Use main.py as the application entry point.
"""

import sys
import threading
# psutil lazy-imported in dashboard_mixin (saves 41ms cold-start)
import json
import os
import subprocess
# requests lazy-imported in methods that need HTTP (saves 298ms cold-start)
import time as time_module
import shutil
import tempfile
import re

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox, QFileDialog,
    QMessageBox, QFrame, QTabWidget, QTabBar, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QComboBox, QMenu, QListWidget,
    QListWidgetItem, QInputDialog, QAbstractItemView,
    QSizePolicy, QGridLayout, QScrollArea, QSpinBox, QRadioButton,
    QProgressDialog, QSplitter, QStyledItemDelegate, QStyle, QScrollBar,
    QMenuBar, QStatusBar, QLayout,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QObject, QTimer, QRectF, QSize, QThread, QPoint,
    QMetaObject, pyqtSlot, Q_ARG,
)
from PyQt6.QtGui import QFont, QPixmap, QPainter, QPen, QColor, QIcon
import qtawesome as qta

# Appium fully lazy — call _ensure_appium_imported() before any automation
# Importing appium at module level costs 300-700ms cold-start (Selenium chain)
UiAutomator2Options = None
AppiumBy = None
_appium_webdriver_module = None

def _ensure_appium_imported():
    """Lazy-load Appium. Call once before starting an automation session."""
    global UiAutomator2Options, AppiumBy, _appium_webdriver_module
    if _appium_webdriver_module is not None:
        return
    try:
        from appium import webdriver as _wd
        from appium.options.android import UiAutomator2Options as _opts
        from appium.webdriver.common.appiumby import AppiumBy as _by
        _appium_webdriver_module = _wd
        UiAutomator2Options = _opts
        AppiumBy = _by
    except ImportError as exc:
        print(f'[Appium] Import failed: {exc}')
import time

# ── src/ package imports ──────────────────────────────────────────────────────
from src.core.config import CONFIG_FILE, load_config, save_config
from src.core.subprocess_utils import safe_subprocess_run
from src.i18n.engine import (
    translate as _T, register_widget as _reg, apply_language, get_current_lang,
    _REGISTRY as _I18N_REGISTRY, _CURRENT_LANG, _get_khmer_font,
)
from src.i18n.translations import TRANSLATIONS
from src.automation.url_normalizer import normalize_facebook_url, URL_TYPE_LABELS as _URL_TYPE_LABELS
# FacebookRegistration lazy-imported inside methods that need it to avoid
# pulling in appium/selenium at startup (saves 300-700ms cold-start)
# DeviceWorker lazy-imported in methods that use it (saves 117ms cold-start)
# MaxChangeWorker lazy-imported in methods that use it (saves 75ms cold-start)
from src.ui.styles import DARK_STYLE
from src.ui.widgets import LogSignal, RingChartWidget
# SafeComboBox lazy-imported in methods that use it (saves 67ms cold-start)

# ── Mixin imports ─────────────────────────────────────────────────────────────
from src.ui.mixins.dashboard_mixin import DashboardMixin
from src.ui.mixins.settings_mixin import SettingsMixin
from src.ui.mixins.auto_reg_mixin import AutoRegMixin
from src.ui.mixins.account_mixin import AccountMixin
from src.ui.mixins.import_mixin import ImportMixin
from src.ui.mixins.login_mixin import LoginMixin
from src.ui.mixins.automation_mixin import AutomationMixin


class MainWindow(
    DashboardMixin,
    SettingsMixin,
    AutoRegMixin,
    AccountMixin,
    ImportMixin,
    LoginMixin,
    AutomationMixin,
    QMainWindow,
):
    """
    Main application window.

    Feature methods live in the mixin classes above.
    This class contains only window lifecycle: __init__, init_ui,
    load_settings, save_settings, closeEvent, and window-drag handlers.
    """

    # ── Cross-thread signals ──────────────────────────────────────────────────
    _install_result_signal = pyqtSignal(str, str)
    _vpn_signal            = pyqtSignal(str, str)
    _ip_check_signal       = pyqtSignal(str, str, str, str, str, str, str, str)
    _proxy_update_signal   = pyqtSignal(str, str)
    _vpn_done_signal       = pyqtSignal(int)
    _vpn_progress_signal   = pyqtSignal(int, str)  # value, label_text
    _spoof_update_signal   = pyqtSignal(str, str)
    _load_table_signal     = pyqtSignal(object, object, object)
    _show_dialog_signal    = pyqtSignal(str, str)
    _seed_status_signal    = pyqtSignal(str, str, str)  # uid, text, color
    _device_scan_signal    = pyqtSignal(list)  # device list
    _login_devices_signal  = pyqtSignal(list)  # login tab device list
    _auto_reg_devices_signal = pyqtSignal(list)  # auto reg tab device list
    _seed_devices_signal   = pyqtSignal(list)  # automation tab device list

    def _fix_email_fields_on_startup(self):
        """Fix missing email fields by extracting from cookies.
        Runs entirely in a background thread — never touches the UI."""
        import threading

        def _run():
            backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'account_backup')
            if not os.path.exists(backup_dir):
                return
            updated = 0
            try:
                for folder_name in os.listdir(backup_dir):
                    folder_path = os.path.join(backup_dir, folder_name)
                    if not os.path.isdir(folder_path):
                        continue
                    info_path = os.path.join(folder_path, 'account_info.json')
                    if not os.path.exists(info_path):
                        continue
                    try:
                        with open(info_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if data.get('email', '').strip():
                            continue  # already has email
                        cookies = data.get('cookies', '')
                        if '|' in cookies and '@' in cookies:
                            for part in cookies.split('|'):
                                part = part.strip().split()[0] if ' ' in part else part.strip()
                                if '@' in part and '.' in part and 'c_user' not in part:
                                    data['email'] = part
                                    with open(info_path, 'w', encoding='utf-8') as f:
                                        json.dump(data, f, indent=4)
                                    updated += 1
                                    break
                    except Exception:
                        pass
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    def __init__(self):
        super().__init__()
        
        # Fix email fields on startup - background only, NOT called directly here
        
        self._install_result_signal.connect(self._show_install_result)
        self._vpn_signal.connect(self._on_vpn_status)
        self._ip_check_signal.connect(self._show_ip_dialog)
        self._proxy_update_signal.connect(self._update_proxy_in_table_ui)
        self._vpn_done_signal.connect(self._on_vpn_all_done)
        self._load_table_signal.connect(self._on_load_table_data)
        self._show_dialog_signal.connect(self._on_show_dialog)
        self._spoof_update_signal.connect(self._update_spoof_in_table_ui)
        self._seed_status_signal.connect(self._seed_set_status_slot)
        self._device_scan_signal.connect(self._apply_device_list)
        self._login_devices_signal.connect(self._apply_login_devices)
        self._auto_reg_devices_signal.connect(self._apply_auto_reg_devices)
        self._seed_devices_signal.connect(self._apply_seed_devices)
        self.setWindowTitle("Facebook Register Tool v1.1.0")
        self.setMinimumSize(1400, 750)
        self.resize(1400, 750)
        self.registration = None
        self.worker_thread = None
        
        # Set adb_path - check platform-tools folder relative to script location
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Check for nested platform-tools structure first (common extraction pattern)
        adb_exe = os.path.join(base_dir, "platform-tools", "platform-tools", "adb.exe")
        if os.path.exists(adb_exe):
            self.adb_path = adb_exe
        else:
            # Check for direct platform-tools structure
            adb_exe = os.path.join(base_dir, "platform-tools", "adb.exe")
            if os.path.exists(adb_exe):
                self.adb_path = adb_exe
            else:
                # Fall back to system PATH
                self.adb_path = "adb"
        
        # devices_loaded is True only after user explicitly loads/saves devices this session
        self.devices_loaded = False
        # net_io initialized lazily in start_system_monitor to avoid blocking __init__
        self.last_net_io = None
        self.last_net_time = time.time()
        self.device_count_cache = 0
        self.device_count_last_check = time.time()  # Initialize to current time
        self.device_count_lock = threading.Lock()  # Lock for ADB device checks
        self.drag_pos = None
        
        # Remove default title bar and make frameless
        # Add NoDropShadowWindowHint to remove Windows shadow that causes black bar
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        self.init_ui()
        self.load_settings()
        
        # Initialize batch rotation settings
        self._batch_mode_enabled = False
        self._batch_size = 20
        self._batch_cooldown = 60
        self._batch_auto_clear = True
        self._batch_auto_backup = False
        
        # Defer all heavy startup work so the window shows immediately
        QTimer.singleShot(0,    self.start_system_monitor)
        QTimer.singleShot(300,  self._auto_load_devices_on_startup)

        # Run I/O heavy tasks in background threads
        threading.Thread(target=self._fix_email_fields_on_startup, daemon=True).start()
        threading.Thread(target=self._load_login_queue_bg, daemon=True).start()
        threading.Thread(target=self._load_dashboard_statistics_bg, daemon=True).start()
        threading.Thread(target=self._auto_detect_apk_bg, daemon=True).start()
        
        # Ensure title bar stays on top — fire a few times after startup then stop.
        # A 1-second repeating timer that calls raise_() every tick is wasteful
        # and causes unnecessary repaint cycles on the main thread.
        self._title_bar_raise_count = 0
        self._title_bar_timer = QTimer()
        self._title_bar_timer.timeout.connect(self._ensure_title_bar_on_top)
        self._title_bar_timer.start(500)  # fire at 0.5s, 1s, 1.5s then stop

        # Force layout recalculation once after window is shown
        QTimer.singleShot(100, self._fix_layout_on_startup)

        # Raise title bar once after window is shown
        QTimer.singleShot(150, lambda: self.title_bar.raise_())
    
    def _fix_layout_on_startup(self):
        """Force layout recalculation to fix black bar issue."""
        try:
            if hasattr(self, 'centralWidget'):
                self.centralWidget().updateGeometry()
            self.updateGeometry()
            self.update()
            QApplication.processEvents()
            if hasattr(self, 'title_bar'):
                self.title_bar.raise_()
        except:
            pass
    
    def _ensure_title_bar_on_top(self):
        """Raise title bar a few times after startup, then stop the timer."""
        if hasattr(self, 'title_bar'):
            self.title_bar.raise_()
        self._title_bar_raise_count = getattr(self, '_title_bar_raise_count', 0) + 1
        if self._title_bar_raise_count >= 6:  # ~3 seconds total, then done
            self._title_bar_timer.stop()

    def _load_login_queue_bg(self):
        """Load login queue in background — no sleep, fires immediately."""
        try:
            from PyQt6.QtCore import QTimer as _QTimer
            _QTimer.singleShot(0, self._load_login_queue)
        except Exception:
            pass

    def _load_dashboard_statistics_bg(self):
        """Load dashboard statistics — reduced delay from 1000ms to 200ms."""
        import time as _time
        _time.sleep(0.2)
        try:
            from PyQt6.QtCore import QTimer as _QTimer
            _QTimer.singleShot(0, self.load_dashboard_statistics)
        except Exception:
            pass

    def _auto_detect_apk_bg(self):
        """Auto-detect APK in background — no sleep, fires immediately."""
        try:
            from PyQt6.QtCore import QTimer as _QTimer
            _QTimer.singleShot(0, self.auto_detect_apk)
        except Exception:
            pass
    
    def _hide_mystery_widgets(self):
        """Hide any mystery widgets that are children of MainWindow but not the central widget."""
        for child in self.children():
            # Skip the layout, menubar, statusbar, and central widget
            if isinstance(child, (QLayout, QMenuBar, QStatusBar)):
                continue
            if child == self.centralWidget():
                continue
            # Hide any other widget (this is the mystery black overlay)
            if hasattr(child, 'setVisible') and hasattr(child, 'isVisible'):
                if child.isVisible():
                    child.setVisible(False)
                    child.setGeometry(0, 0, 0, 0)
                    try:
                        child.deleteLater()
                    except:
                        pass
    

    def auto_detect_apk(self):
        """Auto-detect APK file in the tool's directory."""
        # Only auto-detect if APK path is empty or file doesn't exist
        current_apk = self.apk_input.text().strip()
        if current_apk and os.path.exists(current_apk):
            return  # Already have valid APK
        
        # Search for APK files in the tool's directory
        tool_dir = os.path.dirname(os.path.abspath(__file__))
        apk_files = [f for f in os.listdir(tool_dir) if f.endswith('.apk')]
        
        if apk_files:
            # Prefer Facebook Lite APK if found
            fb_apk = None
            for apk in apk_files:
                if 'facebook' in apk.lower() or 'fb' in apk.lower():
                    fb_apk = apk
                    break
            
            # Use Facebook APK or first APK found
            selected_apk = fb_apk if fb_apk else apk_files[0]
            apk_path = os.path.join(tool_dir, selected_apk)
            self.apk_input.setText(apk_path)
            self.add_activity(f"Auto-detected APK: {selected_apk}")
    

    def load_settings(self):
        """Load settings from config file.

        Phase 1 (runs now, synchronous): language, simple fields, device changer,
        VPN, active tab index — nothing that requires dynamic tabs to exist.

        Phase 2 (deferred): open saved dynamic tabs one by one, then populate
        their fields once they exist.
        """
        try:
            if not os.path.exists(CONFIG_FILE):
                return
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            import traceback
            print(f"Error loading settings: {e}")
            traceback.print_exc()
            return

        # ── Store for deferred phase ──────────────────────────────────────
        self.saved_config = config

        # ── Phase 1: fast, no tab dependency ─────────────────────────────
        try:
            saved_lang = config.get('language', 'EN')
            if saved_lang in TRANSLATIONS:
                apply_language(saved_lang)

            self.apk_input.setText(config.get('apk_path', ''))
            if hasattr(self, 'apk_orig_input'):
                self.apk_orig_input.setText(config.get('apk_orig_path', ''))
            self.device_input.setText(config.get('device_id', ''))
            self._saved_selected_device_ids = set(config.get('selected_device_ids', []))

            # Device Changer settings (always-visible checkboxes)
            for attr, key, default in [
                ('enable_device_changer_checkbox', 'device_changer_enabled', True),
                ('change_android_id_checkbox',     'change_android_id',      True),
                ('change_device_model_checkbox',   'change_device_model',    True),
                ('change_build_fingerprint_checkbox', 'change_build_fingerprint', True),
                ('change_serial_checkbox',         'change_serial',          True),
                ('change_mac_address_checkbox',    'change_mac_address',     True),
            ]:
                if hasattr(self, attr):
                    getattr(self, attr).setChecked(config.get(key, default))

            # VPN settings
            if hasattr(self, 'enable_vpn_checkbox'):
                self.enable_vpn_checkbox.setChecked(config.get('vpn_enabled', False))
            if hasattr(self, 'vpn_mode_combo'):
                idx = self.vpn_mode_combo.findText(config.get('vpn_mode', 'Select Location'))
                if idx >= 0:
                    self.vpn_mode_combo.setCurrentIndex(idx)
            if hasattr(self, 'vpn_server_combo'):
                vpn_idx = config.get('vpn_location_index', 0)
                if vpn_idx < self.vpn_server_combo.count():
                    self.vpn_server_combo.setCurrentIndex(vpn_idx)
            if hasattr(self, 'vpn_user_input'):
                self.vpn_user_input.setText(config.get('vpn_username', ''))
            if hasattr(self, 'vpn_pass_input'):
                self.vpn_pass_input.setText(config.get('vpn_password', ''))

        except Exception as e:
            print(f"[settings] Phase-1 error: {e}")

        # ── Phase 2: open saved tabs deferred, then populate their fields ─
        dynamic_tabs   = config.get('dynamic_tabs', [])
        active_tab_raw = config.get('active_tab', 0)

        # Build canonical name → English name map (used for active_tab resolution)
        _tab_canonical_map = {}
        for _key, _en_name in [
            ("tab_auto_reg",      "Auto Registration"),
            ("tab_account",       "Accounts and Devices"),
            ("btn_accounts",      "Accounts and Devices"),
            ("tab_accounts_only", "Accounts"),
            ("btn_accounts_only", "Accounts"),
            ("tab_import",        "Import"),
            ("tab_login",         "Login"),
            ("tab_automation",    "Automation"),
            ("tab_dashboard",     "Dashboard"),
            ("tab_custom",        "Custom"),
            ("tab_settings",      "Settings"),
        ]:
            for _lang in TRANSLATIONS:
                _v = TRANSLATIONS[_lang].get(_key)
                if _v:
                    _tab_canonical_map[_v.strip()] = _en_name

        def _resolve_active_tab():
            """Return the current index of the saved active tab (name or legacy int)."""
            if isinstance(active_tab_raw, str) and active_tab_raw:
                # Direct name match (current format)
                for i in range(self.tab_widget.count()):
                    if self.tab_widget.tabText(i).strip() == active_tab_raw:
                        return i
                # Canonical match (handles translated tab names saved in old configs)
                for i in range(self.tab_widget.count()):
                    if _tab_canonical_map.get(self.tab_widget.tabText(i).strip()) == active_tab_raw:
                        return i
                return 0
            # Legacy numeric index
            try:
                idx = int(active_tab_raw)
                return idx if idx < self.tab_widget.count() else 0
            except (TypeError, ValueError):
                return 0

        if not dynamic_tabs:
            # No tabs to restore — just set active tab index
            QTimer.singleShot(0, lambda: self.tab_widget.setCurrentIndex(_resolve_active_tab()))
            return

        _TAB_GAP = 60   # ms between each tab open — keeps UI responsive

        # Build a set of all translated names for each tab so restore works
        # regardless of which language was active when the config was saved.
        def _all_names(*keys):
            names = set()
            for key in keys:
                for lang in TRANSLATIONS:
                    val = TRANSLATIONS[lang].get(key)
                    if val:
                        names.add(val.strip())
            return names

        _auto_reg_names   = _all_names("tab_auto_reg")   | {"Auto Registration"}
        _account_names    = _all_names("tab_account", "btn_accounts") | {"Accounts and Devices"}
        _accounts_names   = _all_names("tab_accounts_only", "btn_accounts_only") | {"Accounts"}
        _import_names     = _all_names("tab_import")     | {"Import"}
        _login_names      = _all_names("tab_login")      | {"Login"}
        _automation_names = _all_names("tab_automation") | {"Automation"}

        def _open_one(name):
            """Open a single tab by name — handles any translated variant."""
            if name in _auto_reg_names:
                self.open_auto_registration_tab()
            elif name in _account_names:
                self.open_account_tab()
            elif name in _accounts_names:
                self.open_accounts_only_tab()
            elif name in _import_names:
                self.open_import_tab()
            elif name in _login_names:
                self.open_login_tab()
            elif name in _automation_names:
                self.open_automation_tab()

        def _after_all_tabs_open():
            """Called once after all tabs have been opened — populate their fields."""
            self._restore_tab_fields(config)
            self.tab_widget.setCurrentIndex(_resolve_active_tab())

        total = len(dynamic_tabs)
        for i, tab_name in enumerate(dynamic_tabs):
            QTimer.singleShot(i * _TAB_GAP, lambda n=tab_name: _open_one(n))

        # Fire field population after the last tab has had time to build
        QTimer.singleShot(total * _TAB_GAP + 100, _after_all_tabs_open)

    def _restore_tab_fields(self, config):
        """Populate fields inside dynamic tabs — called after all tabs are open."""
        try:
            if hasattr(self, 'first_name_input'):
                self.first_name_input.setText(config.get('first_name', ''))
            if hasattr(self, 'seed_post_url_input'):
                self._restore_seeding_state(config)
            if hasattr(self, 'last_name_input'):
                self.last_name_input.setText(config.get('last_name', ''))
                self.email_input.setText(config.get('email', ''))
                self.email_list_input.setText(config.get('email_list', ''))
                self.password_input.setText(config.get('password', ''))
                self.birthday_input.setText(config.get('birthday', ''))
                self.gender_input.setCurrentText(config.get('gender', 'Male'))
                self.phone_input.setText(config.get('phone', ''))
                self.profile_pic_input.setText(config.get('profile_pic', ''))

                if hasattr(self, 'email_display'):
                    self.update_email_display()

                for attr, key, default in [
                    ('use_email_checkbox',       'use_email',       True),
                    ('use_phone_checkbox',        'use_phone',       False),
                    ('auto_names_checkbox',       'auto_names',      False),
                    ('random_phone_checkbox',     'random_phone',    False),
                    ('random_password_checkbox',  'random_password', False),
                    ('reg_novary_checkbox',       'reg_novary',      False),
                    ('verification_checkbox',     'verification',    False),
                    ('safety_mode_checkbox',      'safety_mode',     True),
                ]:
                    if hasattr(self, attr):
                        w = getattr(self, attr)
                        w.blockSignals(True)
                        w.setChecked(config.get(key, default))
                        w.blockSignals(False)

                # Trigger state updates
                if hasattr(self, 'use_email_checkbox') or hasattr(self, 'use_phone_checkbox'):
                    self.toggle_signup_method()
                if hasattr(self, 'random_phone_checkbox') and self.random_phone_checkbox.isChecked():
                    self.toggle_random_phone(True)
                if hasattr(self, 'random_password_checkbox') and self.random_password_checkbox.isChecked():
                    self.toggle_random_password(True)
                if hasattr(self, 'auto_names_checkbox') and self.auto_names_checkbox.isChecked():
                    self.toggle_auto_names(True)

                if hasattr(self, 'country_code_input'):
                    cc = config.get('country_code', '+1 (US/Canada)')
                    idx = self.country_code_input.findText(cc)
                    if idx >= 0:
                        self.country_code_input.setCurrentIndex(idx)
                    else:
                        self.country_code_input.setCurrentText(cc)

                if hasattr(self, 'app_selection_input'):
                    sel = config.get('app_selection', 'Facebook Lite')
                    idx = self.app_selection_input.findText(sel)
                    if idx >= 0:
                        self.app_selection_input.setCurrentIndex(idx)

                if hasattr(self, 'delay_input'):
                    try:
                        v = config.get('action_delay', 2.0)
                        if hasattr(self.delay_input, 'setValue'):
                            self.delay_input.setValue(int(float(v)))
                        else:
                            self.delay_input.setText(str(v))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[settings] Tab-field restore error: {e}")
    

    def _safe_widget_val(self, attr, method, default):
        """Safely call a method on a widget that may be destroyed."""
        try:
            w = getattr(self, attr, None)
            if w is None:
                return default
            return getattr(w, method)()
        except Exception:
            return default


    def _get_seeding_react_comments(self):
        """Get list of (text, checked) from the react comment scroll area"""
        result = []
        try:
            layout = getattr(self, '_seed_react_comment_layout', None)
            if not layout: return result
            for i in range(layout.count() - 1):  # skip stretch
                item = layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), QCheckBox):
                    result.append({'text': item.widget().text(), 'checked': item.widget().isChecked()})
        except: pass
        return result


    def _get_seeding_account_uids(self):
        """Get list of (uid, name, status) from seeding account table"""
        result = []
        try:
            t = getattr(self, 'seeding_account_table', None)
            if not t: return result
            for r in range(t.rowCount()):
                uid  = t.item(r, 1).text() if t.item(r, 1) else ''
                name = t.item(r, 2).text() if t.item(r, 2) else ''
                stat = t.item(r, 3).text() if t.item(r, 3) else 'Ready'
                if uid: result.append({'uid': uid, 'name': name, 'status': stat})
        except: pass
        return result


    def _restore_seeding_state(self, config):
        """Restore seeding panel state from config"""
        try:
            if hasattr(self, 'seed_post_url_input'):
                self.seed_post_url_input.setText(config.get('seeding_post_url', ''))
            if hasattr(self, 'seed_comment_url_input'):
                self.seed_comment_url_input.setText(config.get('seeding_comment_url', ''))
            if hasattr(self, 'seed_comment_input'):
                self.seed_comment_input.setPlainText(config.get('seeding_comment_text', ''))
            if hasattr(self, 'seeding_stack'):
                self.seeding_stack.setCurrentIndex(config.get('seeding_mode', 0))
            if hasattr(self, 'seed_delay_min'):
                self.seed_delay_min.setValue(config.get('seeding_delay_min', 3))
            if hasattr(self, 'seed_delay_max'):
                self.seed_delay_max.setValue(config.get('seeding_delay_max', 8))
            if hasattr(self, 'seed_repeat_spin'):
                self.seed_repeat_spin.setValue(config.get('seeding_repeat', 1))
            reactions = config.get('seeding_reactions', {})
            for key, attr in [('like','seed_react_like_cb'),('love','seed_react_love_cb'),
                               ('care','seed_react_care_cb'),('haha','seed_react_haha_cb'),
                               ('wow','seed_react_wow_cb'),('sad','seed_react_sad_cb'),
                               ('angry','seed_react_angry_cb')]:
                if hasattr(self, attr): getattr(self, attr).setChecked(reactions.get(key, key == 'like'))
            if hasattr(self, 'seed_share_cb'):
                self.seed_share_cb.setChecked(config.get('seeding_share', False))
            # Restore react comments
            comments = config.get('seeding_react_comments', [])
            if comments and hasattr(self, '_seed_react_comment_layout'):
                _cb_style = """QCheckBox { color: #cccccc; font-size: 15px; font-family: 'Khmer OS', 'Noto Sans Khmer', 'Leelawadee UI', Arial, sans-serif; background: transparent; spacing: 8px; }
                    QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #3d3d3d; background: #252525; }
                    QCheckBox::indicator:checked { background: #4CAF50; border-color: #4CAF50; }"""
                for c in comments:
                    cb = QCheckBox(c.get('text', '')); cb.setChecked(c.get('checked', True))
                    cb.setStyleSheet(_cb_style); cb.setMinimumHeight(32)
                    count = self._seed_react_comment_layout.count()
                    self._seed_react_comment_layout.insertWidget(count - 1, cb)
            # Restore accounts
            accounts = config.get('seeding_accounts', [])
            if accounts and hasattr(self, 'seeding_account_table'):
                self.seeding_account_table.setRowCount(0)
                for i, acc in enumerate(accounts):
                    row = self.seeding_account_table.rowCount()
                    self.seeding_account_table.insertRow(row)
                    self.seeding_account_table.setRowHeight(row, 36)
                    n_item = QTableWidgetItem(str(i+1)); n_item.setForeground(QColor("#555555")); n_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    u_item = QTableWidgetItem(acc.get('uid','')); u_item.setForeground(QColor("#4CAF50"))
                    nm_item = QTableWidgetItem(acc.get('name','')); nm_item.setForeground(QColor("#cccccc"))
                    s_item = QTableWidgetItem(acc.get('status','Ready')); s_item.setForeground(QColor("#555555"))
                    for col, item in enumerate([n_item, u_item, nm_item, s_item]):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        self.seeding_account_table.setItem(row, col, item)
                self.auto_seed_account_badge.setText(f"{len(accounts)} accounts")
                self._seed_stat_total.setText(f"Total: {len(accounts)}")
        except Exception as e:
            print(f"Error restoring seeding state: {e}")


    def save_settings(self):
        """Save settings to config file."""
        try:
            # Load existing config to preserve fields like account_categories
            existing_config = load_config()
            
            # Get dynamic tab names (tabs after the 3 main tabs).
            # Normalize to canonical English names so the config is language-agnostic —
            # Qt may also append a trailing space when a close button is set via setTabButton.
            _tab_canonical = {}
            for _key, _en_name in [
                ("tab_auto_reg",      "Auto Registration"),
                ("tab_account",       "Accounts and Devices"),
                ("btn_accounts",      "Accounts and Devices"),
                ("tab_accounts_only", "Accounts"),
                ("btn_accounts_only", "Accounts"),
                ("tab_import",        "Import"),
                ("tab_login",         "Login"),
                ("tab_automation",    "Automation"),
            ]:
                for _lang in TRANSLATIONS:
                    _translated = TRANSLATIONS[_lang].get(_key)
                    if _translated:
                        _tab_canonical[_translated.strip()] = _en_name
            # Also map English names to themselves
            for _en in ("Auto Registration", "Accounts and Devices", "Accounts",
                        "Import", "Login", "Automation"):
                _tab_canonical[_en] = _en

            dynamic_tabs = []
            for i in range(3, self.tab_widget.count()):
                name = self.tab_widget.tabText(i).strip()
                if name:
                    dynamic_tabs.append(_tab_canonical.get(name, name))
            
            config = {
                'apk_path': self.apk_input.text(),
                'apk_orig_path': getattr(self, 'apk_orig_input', None) and self.apk_orig_input.text() or '',
                'device_id': self.device_input.text(),
                'first_name': getattr(self, 'first_name_input', None) and self.first_name_input.text() or '',
                'last_name': getattr(self, 'last_name_input', None) and self.last_name_input.text() or '',
                'email': getattr(self, 'email_input', None) and self.email_input.text() or '',
                'email_list': getattr(self, 'email_list_input', None) and self.email_list_input.text() or '',
                'password': getattr(self, 'password_input', None) and self.password_input.text() or '',
                'birthday': getattr(self, 'birthday_input', None) and self.birthday_input.text() or '',
                'gender': getattr(self, 'gender_input', None) and self.gender_input.currentText() or '',
                'phone': getattr(self, 'phone_input', None) and self.phone_input.text() or '',
                'profile_pic': getattr(self, 'profile_pic_input', None) and self.profile_pic_input.text() or '',
                'use_email': getattr(self, 'use_email_checkbox', None) and self.use_email_checkbox.isChecked() or True,
                'use_phone': getattr(self, 'use_phone_checkbox', None) and self.use_phone_checkbox.isChecked() or False,
                'auto_names': getattr(self, 'auto_names_checkbox', None) and self.auto_names_checkbox.isChecked() or False,
                'random_phone': getattr(self, 'random_phone_checkbox', None) and self.random_phone_checkbox.isChecked() or False,
                'random_password': getattr(self, 'random_password_checkbox', None) and self.random_password_checkbox.isChecked() or False,
                'reg_novary': getattr(self, 'reg_novary_checkbox', None) and self.reg_novary_checkbox.isChecked() or False,
                'verification': getattr(self, 'verification_checkbox', None) and self.verification_checkbox.isChecked() or False,
                'country_code': getattr(self, 'country_code_input', None) and self.country_code_input.currentText() or '+1 (US/Canada)',
                'app_selection': getattr(self, 'app_selection_input', None) and self.app_selection_input.currentText() or 'Facebook Lite',
                'action_delay': float(getattr(self, 'delay_input', None) and self.delay_input.text() or 2.0),
                'safety_mode': getattr(self, 'safety_mode_checkbox', None) and self.safety_mode_checkbox.isChecked() or True,
                'active_tab': self.tab_widget.tabText(self.tab_widget.currentIndex()).strip(),
                'dynamic_tabs': dynamic_tabs,
                # Device Changer Settings
                'device_changer_enabled': getattr(self, 'enable_device_changer_checkbox', None) and self.enable_device_changer_checkbox.isChecked() or True,
                'change_android_id': getattr(self, 'change_android_id_checkbox', None) and self.change_android_id_checkbox.isChecked() or True,
                'change_device_model': getattr(self, 'change_device_model_checkbox', None) and self.change_device_model_checkbox.isChecked() or True,
                'change_build_fingerprint': getattr(self, 'change_build_fingerprint_checkbox', None) and self.change_build_fingerprint_checkbox.isChecked() or True,
                'change_serial': getattr(self, 'change_serial_checkbox', None) and self.change_serial_checkbox.isChecked() or True,
                'change_mac_address': getattr(self, 'change_mac_address_checkbox', None) and self.change_mac_address_checkbox.isChecked() or True,
                # VPN Settings
                'vpn_enabled': self._safe_widget_val('enable_vpn_checkbox', 'isChecked', False),
                'vpn_mode': self._safe_widget_val('vpn_mode_combo', 'currentText', 'Select Location'),
                'vpn_location': self._safe_widget_val('vpn_server_combo', 'currentText', ''),
                'vpn_location_index': self._safe_widget_val('vpn_server_combo', 'currentIndex', 0),
                'vpn_username': self._safe_widget_val('vpn_user_input', 'text', ''),
                'vpn_password': self._safe_widget_val('vpn_pass_input', 'text', ''),
                # Selected device IDs from Device Settings dialog
                'selected_device_ids': [cb.text() for cb in self.device_checkboxes if cb.isChecked()],
                # Language setting
                'language': _CURRENT_LANG[0],
                # Seeding state
                'seeding_post_url': getattr(self, 'seed_post_url_input', None) and self.seed_post_url_input.text() or '',
                'seeding_comment_url': getattr(self, 'seed_comment_url_input', None) and self.seed_comment_url_input.text() or '',
                'seeding_comment_text': getattr(self, 'seed_comment_input', None) and self.seed_comment_input.toPlainText() or '',
                'seeding_mode': getattr(self, 'seeding_stack', None) and self.seeding_stack.currentIndex() or 0,
                'seeding_react_comments': self._get_seeding_react_comments(),
                'seeding_accounts': self._get_seeding_account_uids(),
                'seeding_delay_min': getattr(self, 'seed_delay_min', None) and self.seed_delay_min.value() or 3,
                'seeding_delay_max': getattr(self, 'seed_delay_max', None) and self.seed_delay_max.value() or 8,
                'seeding_repeat': getattr(self, 'seed_repeat_spin', None) and self.seed_repeat_spin.value() or 1,
                'seeding_reactions': {
                    'like':  getattr(self, 'seed_react_like_cb',  None) and self.seed_react_like_cb.isChecked()  or False,
                    'love':  getattr(self, 'seed_react_love_cb',  None) and self.seed_react_love_cb.isChecked()  or False,
                    'care':  getattr(self, 'seed_react_care_cb',  None) and self.seed_react_care_cb.isChecked()  or False,
                    'haha':  getattr(self, 'seed_react_haha_cb',  None) and self.seed_react_haha_cb.isChecked()  or False,
                    'wow':   getattr(self, 'seed_react_wow_cb',   None) and self.seed_react_wow_cb.isChecked()   or False,
                    'sad':   getattr(self, 'seed_react_sad_cb',   None) and self.seed_react_sad_cb.isChecked()   or False,
                    'angry': getattr(self, 'seed_react_angry_cb', None) and self.seed_react_angry_cb.isChecked() or False,
                },
                'seeding_share': getattr(self, 'seed_share_cb', None) and self.seed_share_cb.isChecked() or False,
            }
            
            # Preserve account_categories from existing config
            if 'account_categories' in existing_config:
                config['account_categories'] = existing_config['account_categories']
            
            # Preserve auto_load_device from existing config
            if 'auto_load_device' in existing_config:
                config['auto_load_device'] = existing_config['auto_load_device']

            # Preserve auto_restart_screen from existing config
            if 'auto_restart_screen' in existing_config:
                config['auto_restart_screen'] = existing_config['auto_restart_screen']
            
            # Use the proper save_config function
            save_config(config)
        except PermissionError as e:
            # Only catch permission errors, let other errors propagate
            print(f"Warning: Could not save settings due to permission error: {e}")
            print("Settings will not persist after restart.")
        except Exception as e:
            # Log other errors but don't crash
            print(f"Error saving settings: {e}")
    

    def closeEvent(self, event):
        """Save settings when closing the application."""
        self.save_settings()
        event.accept()
    
    def showEvent(self, event):
        """Ensure title bar stays on top when window is shown."""
        super().showEvent(event)
        # CRITICAL: Hide mystery widget immediately when window is shown
        self._hide_mystery_widgets()
        # Force layout recalculation to fix black bar
        if hasattr(self, 'centralWidget'):
            cw = self.centralWidget()
            if cw:
                cw.setGeometry(0, 0, self.width(), self.height())
                cw.updateGeometry()
        self.updateGeometry()
        QApplication.processEvents()
        if hasattr(self, 'title_bar'):
            self.title_bar.raise_()
    
    def resizeEvent(self, event):
        """Ensure central widget fills entire window on resize."""
        super().resizeEvent(event)
        if hasattr(self, 'centralWidget'):
            cw = self.centralWidget()
            if cw:
                cw.setGeometry(0, 0, self.width(), self.height())
    
    def focusInEvent(self, event):
        """Ensure title bar stays on top when window gains focus."""
        super().focusInEvent(event)
        if hasattr(self, 'title_bar'):
            self.title_bar.raise_()
    

    def init_ui(self):
        # CRITICAL FIX: Hide QMainWindow's default menu bar and status bar
        self.menuBar().hide()
        self.statusBar().hide()
        
        # Force central widget to fill entire window - no margins!
        self.setContentsMargins(0, 0, 0, 0)
        
        central = QWidget()
        central.setObjectName("CENTRAL_WIDGET")
        central.setStyleSheet("background-color: #1e1e1e;")
        self.setCentralWidget(central)
        
        outer_layout = QVBoxLayout(central)
        outer_layout.setSpacing(0)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        
        # Custom Title Bar
        title_bar = QFrame()
        title_bar.setObjectName("TITLE_BAR")
        title_bar.setFixedHeight(60)  # Slightly taller for better proportions
        title_bar.setStyleSheet("""
            QFrame#TITLE_BAR {
                background-color: #1a1a1a;
                border-bottom: 1px solid #2d2d2d;
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 0, 15, 0)
        title_layout.setSpacing(0)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # Logo
        import os
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", "logo.png")
        logo_label = QLabel()
        if os.path.exists(logo_path):
            logo_pixmap = QPixmap(logo_path)
            logo_label.setPixmap(logo_pixmap.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            logo_label.setText("🔵")
        logo_label.setStyleSheet("border: none;")
        title_layout.addWidget(logo_label)
        
        title_layout.addSpacing(12)
        
        # App title
        app_title = QLabel("Facebook Register Tool")
        app_title.setStyleSheet("""
            color: #ffffff;
            font-weight: 600;
            font-size: 15px;
            border: none;
            letter-spacing: 0.3px;
        """)
        title_layout.addWidget(app_title)
        _reg(app_title, "app_title")
        self.setWindowTitle(_T("app_title"))
        _I18N_REGISTRY.append((self, "app_title", "window_title"))

        # Set taskbar / window icon to the cat logo
        _icon_base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        _cat_ico = os.path.join(_icon_base, "logo", "logo.png")
        if os.path.exists(_cat_ico):
            self.setWindowIcon(QIcon(_cat_ico))
            QApplication.instance().setWindowIcon(QIcon(_cat_ico))

        title_layout.addSpacing(30)
        
        # Info pills container - ultra clean design
        info_container = QWidget()
        info_container.setStyleSheet("background: transparent; border: none;")
        info_layout = QHBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)
        
        # Version pill - minimal design
        version_pill = QLabel("v1.1.0")
        version_pill.setStyleSheet("""
            QLabel {
                background-color: rgba(76, 175, 80, 0.12);
                color: #4CAF50;
                border: none;
                border-radius: 11px;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
        """)
        info_layout.addWidget(version_pill)
        
        # Expiry pill - shows days remaining from license
        expiry_text, expiry_color, expiry_bg = self._get_expiry_display()
        expiry_pill = QLabel(expiry_text)
        expiry_pill.setStyleSheet(f"""
            QLabel {{
                background-color: {expiry_bg};
                color: {expiry_color};
                border: none;
                border-radius: 11px;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }}
        """)
        expiry_pill.setToolTip("License Expiration Date")
        info_layout.addWidget(expiry_pill)
        
        # Tool ID pill - yellow/orange design
        tool_id_pill = QLabel(f"ID: {self._get_tool_id()}")
        tool_id_pill.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 179, 0, 0.12);
                color: #FFB300;
                border: none;
                border-radius: 11px;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
                font-family: 'Consolas', 'SF Mono', monospace;
            }
        """)
        tool_id_pill.setToolTip("Unique Tool Identifier")
        info_layout.addWidget(tool_id_pill)
        
        title_layout.addWidget(info_container)
        
        title_layout.addStretch()
        
        # Action buttons - clean icon buttons
        actions_container = QWidget()
        actions_container.setStyleSheet("background: transparent; border: none;")
        actions_layout = QHBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        
        # License button - premium gold accent
        license_btn = QPushButton()
        license_btn.setIcon(qta.icon('fa5s.shield-alt', color='#FFB300'))
        license_btn.setIconSize(QSize(17, 17))
        license_btn.setFixedSize(38, 38)
        license_btn.setToolTip("License Information")
        license_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        license_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 179, 0, 0.1);
                border: 1px solid rgba(255, 179, 0, 0.2);
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(255, 179, 0, 0.2);
                border: 1px solid rgba(255, 179, 0, 0.4);
            }
            QPushButton:pressed {
                background-color: rgba(255, 179, 0, 0.3);
            }
        """)
        license_btn.clicked.connect(lambda: self._show_license_info())
        actions_layout.addWidget(license_btn)
        
        # Contact button - Telegram blue
        contact_btn = QPushButton()
        contact_btn.setIcon(qta.icon('fa5b.telegram', color='#29B6F6'))
        contact_btn.setIconSize(QSize(19, 19))
        contact_btn.setFixedSize(38, 38)
        contact_btn.setToolTip("Contact Support")
        contact_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        contact_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(41, 182, 246, 0.1);
                border: 1px solid rgba(41, 182, 246, 0.2);
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(41, 182, 246, 0.2);
                border: 1px solid rgba(41, 182, 246, 0.4);
            }
            QPushButton:pressed {
                background-color: rgba(41, 182, 246, 0.3);
            }
        """)
        contact_btn.clicked.connect(lambda: self._open_telegram_link())
        actions_layout.addWidget(contact_btn)
        
        title_layout.addWidget(actions_container)
        
        title_layout.addSpacing(20)
        
        # Elegant separator with background
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.12);
                border: none;
                max-width: 1px;
                min-width: 1px;
            }
        """)
        separator.setFixedHeight(32)
        separator.setFixedWidth(1)
        title_layout.addWidget(separator)
        
        title_layout.addSpacing(12)
        
        # Window control buttons - macOS style with colored backgrounds
        # Minimize button (Yellow/Orange)
        min_btn = QPushButton()
        min_btn.setIcon(qta.icon('fa5s.minus', color='#ffffff'))
        min_btn.setIconSize(QSize(12, 12))
        min_btn.setFixedSize(42, 42)
        min_btn.setToolTip("Minimize")
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #FB8C00;
            }
            QPushButton:pressed {
                background-color: #F57C00;
            }
        """)
        min_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(min_btn)
        
        title_layout.addSpacing(6)
        
        # Maximize/Restore button (Green)
        self.max_btn = QPushButton()
        self.max_btn.setIcon(qta.icon('fa5s.square', color='#ffffff'))
        self.max_btn.setIconSize(QSize(12, 12))
        self.max_btn.setFixedSize(42, 42)
        self.max_btn.setToolTip("Maximize")
        self.max_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.max_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
        """)
        self.max_btn.clicked.connect(self.toggle_maximize)
        title_layout.addWidget(self.max_btn)
        
        title_layout.addSpacing(6)
        
        # Close button (Red)
        close_btn = QPushButton()
        close_btn.setIcon(qta.icon('fa5s.times', color='#ffffff'))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setFixedSize(42, 42)
        close_btn.setToolTip("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:pressed {
                background-color: #c62828;
            }
        """)
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        
        title_layout.addSpacing(8)
        
        # Store title bar reference for z-ordering management
        self.title_bar = title_bar
        
        outer_layout.addWidget(title_bar)
        
        # Add explicit spacer between title bar and content
        outer_layout.addSpacing(10)
        
        # Content area
        content_widget = QWidget()
        content_widget.setObjectName("CONTENT_WIDGET")
        content_widget.setContentsMargins(0, 0, 0, 0)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(10)
        content_layout.setContentsMargins(20, 10, 20, 20)
        
        # System Monitor Cards
        monitor_layout = QHBoxLayout()
        monitor_layout.setSpacing(8)

        def _stat_card(obj_name, icon, color, title, val_attr):
            # outer wrapper for the left accent bar
            wrapper = QFrame()
            wrapper.setObjectName(f"{obj_name}_wrap")
            wrapper.setFixedHeight(70)
            wrapper.setStyleSheet(f"QFrame#{obj_name}_wrap {{ background: #1e1e1e; border: 1px solid #3d3d3d; border-radius: 6px; }}")
            wl = QHBoxLayout(wrapper)
            wl.setContentsMargins(14, 0, 14, 0)
            wl.setSpacing(12)
            ico_lbl = QLabel()
            ico_lbl.setPixmap(qta.icon(icon, color=color).pixmap(20, 20))
            ico_lbl.setStyleSheet("background: transparent;")
            wl.addWidget(ico_lbl)
            txt = QVBoxLayout()
            txt.setSpacing(2)
            t = QLabel(title.upper())
            t.setStyleSheet("color: #666666; font-size: 9px; font-weight: bold; letter-spacing: 0.6px; background: transparent;")
            v = QLabel("—")
            v.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: bold; background: transparent;")
            txt.addWidget(t)
            txt.addWidget(v)
            wl.addLayout(txt)
            wl.addStretch()
            setattr(self, val_attr, v)
            return wrapper

        monitor_layout.addWidget(_stat_card("scCPU",  'fa5s.microchip',     '#4CAF50', 'CPU',      'cpu_label'),  1)
        monitor_layout.addWidget(_stat_card("scRAM",  'fa5s.memory',        '#2196F3', 'RAM',      'ram_label'),  1)
        monitor_layout.addWidget(_stat_card("scDEV",  'fa5s.mobile-alt',    '#FF9800', 'Devices',  'device_count_label'),  1)
        monitor_layout.addWidget(_stat_card("scNET",  'fa5s.wifi',          '#E91E63', 'Network',  'net_label'),  1)
        monitor_layout.addWidget(_stat_card("scACCT", 'fa5s.layer-group',   '#4CAF50', 'Accounts', 'stat_total_label'), 1)

        content_layout.addLayout(monitor_layout)
        
        # Add small spacer to ensure separation from title bar
        content_layout.addSpacing(5)
        
        # Tab Widget
        self.tab_widget = QTabWidget()
        # Prevent tab widget from overlaying title bar
        self.tab_widget.setDocumentMode(False)
        # Ensure tab widget doesn't extend beyond its bounds
        self.tab_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                border-top: 1px solid #3d3d3d;
                background-color: #1e1e1e;
                position: relative;
                margin-top: 0px;
            }
            QTabBar {
                qproperty-drawBase: 0;
            }
            QTabBar::tab {
                background-color: #363636;
                color: #888888;
                padding: 10px 15px;
                margin-right: 2px;
                margin-top: 0px;
                border-radius: 0px;
                min-width: 180px;
                max-width: 180px;
                height: 20px;
            }
            QTabBar::tab:selected {
                background-color: rgba(76, 175, 80, 0.3);
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background-color: rgba(76, 175, 80, 0.3);
                color: #ffffff;
            }
        """)
        
        # Fix tab bar height to prevent resizing when adding/removing tabs
        # Keep it at or below title bar height (45px) to prevent overlay
        self.tab_widget.tabBar().setFixedHeight(40)
        
        # Ensure title bar stays on top when switching tabs
        self.tab_widget.currentChanged.connect(lambda: self.title_bar.raise_() if hasattr(self, 'title_bar') else None)
        
        # Initialize counters
        self.total_accounts = 0
        self.success_count = 0
        self.failed_count = 0
        self.working_count = 0
        self.issues_count = 0
        self.today_count = 0
        self.pending_count = 0
        self.suspended_count = 0
        
        # Dashboard Tab
        dashboard_tab = QWidget()
        dashboard_tab.setStyleSheet("background-color: #161616;")
        dashboard_layout = QVBoxLayout(dashboard_tab)
        dashboard_layout.setSpacing(0)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)

        # ── Top bar ───────────────────────────────────────────────────────
        dash_topbar = QFrame()
        dash_topbar.setFixedHeight(56)
        dash_topbar.setStyleSheet("QFrame { background: #1e1e1e; border: none; border-bottom: 1px solid #2a2a2a; }")
        dash_topbar_l = QHBoxLayout(dash_topbar)
        dash_topbar_l.setContentsMargins(24, 0, 20, 0)
        dash_topbar_l.setSpacing(8)
        _tb_title = _reg(QLabel(), "overview", "text")
        _tb_title.setStyleSheet("color: #4CAF50; font-size: 15px; font-weight: bold; background: transparent;")
        dash_topbar_l.addWidget(_tb_title)
        self._lbl_overview = _tb_title
        dash_topbar_l.addStretch()
        import datetime as _dt
        _date_lbl = QLabel(_dt.datetime.now().strftime("%A, %d %B %Y"))
        _date_lbl.setStyleSheet("color: #777777; font-size: 11px; background: transparent;")
        dash_topbar_l.addWidget(_date_lbl)
        dashboard_layout.addWidget(dash_topbar)

        # ── Main body: left content + right sidebar ───────────────────────
        dash_body_outer = QHBoxLayout()
        dash_body_outer.setSpacing(0)
        dash_body_outer.setContentsMargins(0, 0, 0, 0)

        # ── LEFT: scrollable main content ─────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setStyleSheet("""
            QScrollArea { background: #161616; border: none; }
            QScrollBar:vertical { background: #161616; width: 5px; border-radius: 2px; }
            QScrollBar::handle:vertical { background: #2a2a2a; border-radius: 2px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        left_content = QWidget()
        left_content.setStyleSheet("background: #161616;")
        left_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_vbox = QVBoxLayout(left_content)
        left_vbox.setSpacing(20)
        left_vbox.setContentsMargins(24, 24, 16, 24)

        # ── KPI cards ─────────────────────────────────────────────────────
        def _kpi(icon, color, title_key, attr):
            card = QFrame()
            card.setFixedHeight(100)
            r,g,b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
            card.setObjectName("kpiCard")
            card.setStyleSheet(f"""
                QFrame#kpiCard {{
                    background: #1e1e1e;
                    border: 1px solid #252525;
                    border-radius: 8px;
                }}
                QFrame#kpiCard QFrame {{
                    border: none;
                }}
                QFrame#kpiCard QLabel {{
                    border: none;
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(18, 14, 18, 14)
            cl.setSpacing(6)

            top = QHBoxLayout()
            top.setSpacing(0)
            lbl = _reg(QLabel(), title_key, "text")
            lbl.setStyleSheet("color: #666666; font-size: 10px; font-weight: bold; letter-spacing: 0.8px; background: transparent;")
            top.addWidget(lbl)
            top.addStretch()
            ico_lbl = QLabel()
            ico_lbl.setPixmap(qta.icon(icon, color=color).pixmap(16, 16))
            ico_lbl.setStyleSheet("background: transparent;")
            top.addWidget(ico_lbl)
            cl.addLayout(top)

            num = QLabel("0")
            num.setStyleSheet(f"color: #ffffff; font-size: 32px; font-weight: bold; background: transparent; line-height: 1;")
            cl.addWidget(num)

            # accent bottom bar
            bar = QFrame()
            bar.setFixedHeight(3)
            bar.setStyleSheet(f"background: {color}; border-radius: 2px; border: none;")
            card_outer = QFrame()
            card_outer.setStyleSheet("background: transparent; border: none;")
            co_l = QVBoxLayout(card_outer)
            co_l.setSpacing(0)
            co_l.setContentsMargins(0, 0, 0, 0)
            co_l.addWidget(card)
            co_l.addWidget(bar)
            setattr(self, attr, num)
            return card_outer

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        kpi_row.addWidget(_kpi('fa5s.layer-group',          '#4CAF50', 'kpi_total',  'total_accounts_label'), 1)
        kpi_row.addWidget(_kpi('fa5s.check-circle',         '#4CAF50', 'kpi_active', 'working_label'),        1)
        kpi_row.addWidget(_kpi('fa5s.exclamation-triangle', '#f44336', 'kpi_issues', 'issues_label'),         1)
        kpi_row.addWidget(_kpi('fa5s.calendar-day',         '#FF9800', 'kpi_today',  'today_label'),          1)
        left_vbox.addLayout(kpi_row)

        # ── Middle row: ring chart + status + quick actions ───────────────
        mid_row = QHBoxLayout()
        mid_row.setSpacing(12)

        # Ring chart
        ring_card = QFrame()
        ring_card.setObjectName("ringCard")
        ring_card.setFixedWidth(190)
        ring_card.setStyleSheet("QFrame#ringCard { background: #1e1e1e; border: 1px solid #252525; border-radius: 8px; }")
        ring_cl = QVBoxLayout(ring_card)
        ring_cl.setContentsMargins(16, 16, 16, 16)
        ring_cl.setSpacing(6)
        _rl_title = _reg(QLabel(), "success_rate", "text")
        _rl_title.setStyleSheet("color: #666666; font-size: 10px; font-weight: bold; letter-spacing: 0.8px; background: transparent;")
        _rl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ring_cl.addWidget(_rl_title)
        self._lbl_success_rate = _rl_title
        self.ring_chart = RingChartWidget()
        self.ring_chart.setFixedSize(100, 100)
        ring_cl.addWidget(self.ring_chart, alignment=Qt.AlignmentFlag.AlignCenter)
        self.rate_label = QLabel("0%")
        self.rate_label.setStyleSheet("color: #4CAF50; font-size: 26px; font-weight: bold; background: transparent;")
        self.rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ring_cl.addWidget(self.rate_label)
        mid_row.addWidget(ring_card)

        # Status breakdown
        status_card = QFrame()
        status_card.setObjectName("statusCard")
        status_card.setStyleSheet("QFrame#statusCard { background: #1e1e1e; border: 1px solid #252525; border-radius: 8px; }")
        status_cl = QVBoxLayout(status_card)
        status_cl.setContentsMargins(18, 16, 18, 16)
        status_cl.setSpacing(14)
        _st_title = _reg(QLabel(), "account_breakdown", "text")
        _st_title.setStyleSheet("color: #666666; font-size: 10px; font-weight: bold; letter-spacing: 0.8px; background: transparent;")
        status_cl.addWidget(_st_title)
        self._lbl_acct_breakdown = _st_title

        def _breakdown_row(label_key, color, attr):
            rw = QHBoxLayout()
            rw.setSpacing(10)
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
            rw.addWidget(dot)
            lb = _reg(QLabel(), label_key, "text")
            lb.setFixedWidth(72)
            lb.setStyleSheet("color: #aaaaaa; font-size: 12px; background: transparent;")
            rw.addWidget(lb)
            track = QFrame()
            track.setFixedHeight(4)
            track.setStyleSheet("background: #252525; border-radius: 2px; border: none;")
            rw.addWidget(track, 1)
            num = QLabel("0")
            num.setFixedWidth(32)
            num.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            num.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold; background: transparent;")
            rw.addWidget(num)
            status_cl.addLayout(rw)
            setattr(self, attr, num)

        _breakdown_row("status_active",    "#4CAF50", "cat_active_label")
        _breakdown_row("status_pending",   "#FF9800", "cat_pending_label")
        _breakdown_row("status_suspended", "#f44336", "cat_suspended_label")
        _breakdown_row("status_new",       "#888888", "cat_new_label")
        mid_row.addWidget(status_card, 1)

        # Quick actions
        qa_card = QFrame()
        qa_card.setObjectName("qaCard")
        qa_card.setFixedWidth(180)
        qa_card.setStyleSheet("QFrame#qaCard { background: #1e1e1e; border: 1px solid #252525; border-radius: 8px; }")
        qa_cl = QVBoxLayout(qa_card)
        qa_cl.setContentsMargins(14, 16, 14, 16)
        qa_cl.setSpacing(8)
        _qa_title = _reg(QLabel(), "quick_actions", "text")
        _qa_title.setStyleSheet("color: #666666; font-size: 10px; font-weight: bold; letter-spacing: 0.8px; background: transparent;")
        qa_cl.addWidget(_qa_title)
        self._lbl_quick_actions = _qa_title

        def _qa_btn(icon, label_key, slot, primary=False):
            btn = QPushButton()
            _reg(btn, label_key, "text")
            btn.setIcon(qta.icon(icon, color='#ffffff' if primary else '#aaaaaa'))
            btn.setFixedHeight(36)
            if primary:
                btn.setStyleSheet("""
                    QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 6px; font-size: 11px; font-weight: bold; }
                    QPushButton:hover { background: #45a049; }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton { background: #252525; color: #aaaaaa; border: 1px solid #3a3a3a; border-radius: 6px; font-size: 11px; }
                    QPushButton:hover { border-color: #4CAF50; color: #ffffff; background: #2a2a2a; }
                """)
            if slot:
                btn.clicked.connect(slot)
            qa_cl.addWidget(btn)

        _qa_btn('fa5s.file-import',  'btn_import',      self.open_import_tab if hasattr(self, 'open_import_tab') else None, primary=True)
        _qa_btn('fa5s.user-plus',    'btn_add_account', self.open_import_tab)
        _qa_btn('fa5s.sync-alt',     'btn_refresh',     self.load_main_account_tab if hasattr(self, 'load_main_account_tab') else None)
        _qa_btn('fa5s.file-export',  'btn_export',      self.export_accounts if hasattr(self, 'export_accounts') else None)
        mid_row.addWidget(qa_card)
        left_vbox.addLayout(mid_row, 1)

        left_scroll.setWidget(left_content)
        dash_body_outer.addWidget(left_scroll, 1)

        # ── RIGHT: activity log sidebar ───────────────────────────────────
        right_sidebar = QFrame()
        right_sidebar.setFixedWidth(300)
        right_sidebar.setStyleSheet("QFrame { background: #1a1a1a; border: none; border-left: 1px solid #2a2a2a; }")
        right_sb_l = QVBoxLayout(right_sidebar)
        right_sb_l.setSpacing(0)
        right_sb_l.setContentsMargins(0, 0, 0, 0)

        # Sidebar header
        sb_header = QFrame()
        sb_header.setFixedHeight(48)
        sb_header.setStyleSheet("QFrame { background: #1a1a1a; border: none; border-bottom: 1px solid #2a2a2a; }")
        sb_header_l = QHBoxLayout(sb_header)
        sb_header_l.setContentsMargins(16, 0, 12, 0)
        sb_header_l.setSpacing(8)
        _sb_ico = QLabel()
        _sb_ico.setPixmap(qta.icon('fa5s.terminal', color='#4CAF50').pixmap(12, 12))
        _sb_ico.setStyleSheet("background: transparent;")
        sb_header_l.addWidget(_sb_ico)
        _sb_lbl = _reg(QLabel(), "activity_log", "text")
        _sb_lbl.setStyleSheet("color: #cccccc; font-size: 12px; font-weight: bold; background: transparent;")
        sb_header_l.addWidget(_sb_lbl)
        self._lbl_activity_log = _sb_lbl
        sb_header_l.addStretch()
        clear_btn = _reg(QPushButton(), "btn_clear", "text")
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #3d3d3d; border: 1px solid #2a2a2a; border-radius: 3px; font-size: 10px; padding: 0 8px; }
            QPushButton:hover { border-color: #f44336; color: #f44336; }
        """)
        clear_btn.clicked.connect(self.clear_activity)
        sb_header_l.addWidget(clear_btn)
        right_sb_l.addWidget(sb_header)

        log_wrapper = QWidget()
        log_wrapper.setStyleSheet("background: #1a1a1a;")
        log_wrapper_l = QVBoxLayout(log_wrapper)
        log_wrapper_l.setContentsMargins(8, 8, 8, 8)
        log_wrapper_l.setSpacing(0)

        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setStyleSheet("""
            QTextEdit {
                background: #141414;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                color: #4CAF50;
                font-family: 'Consolas', 'JetBrains Mono', 'Cascadia Code', 'Courier New', monospace;
                font-size: 11px;
                padding: 10px;
            }
            QScrollBar:vertical { background: #141414; width: 5px; border-radius: 2px; }
            QScrollBar::handle:vertical { background: #2a2a2a; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        log_wrapper_l.addWidget(self.activity_log)
        right_sb_l.addWidget(log_wrapper, 1)
        dash_body_outer.addWidget(right_sidebar)

        dash_body_widget = QWidget()
        dash_body_widget.setStyleSheet("background: #161616;")
        dash_body_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        dash_body_widget.setLayout(dash_body_outer)
        dashboard_layout.addWidget(dash_body_widget, 1)

        # Compat labels
        self.dashboard_status_label = QLabel()
        self.device_status_label    = QLabel()
        self.last_activity_label    = QLabel()
        self.success_label          = self.working_label
        self.failed_label           = self.issues_label
        self.status_items           = {}
        
        # Custom Tab
        custom_tab = QWidget()
        custom_tab.setStyleSheet("background: #161616;")
        custom_main_layout = QVBoxLayout(custom_tab)
        custom_main_layout.setSpacing(0)
        custom_main_layout.setContentsMargins(0, 0, 0, 0)

        # Top bar
        custom_topbar = QFrame()
        custom_topbar.setObjectName("customTopbar")
        custom_topbar.setFixedHeight(56)
        custom_topbar.setStyleSheet("QFrame#customTopbar { background: #1e1e1e; border: none; border-bottom: 1px solid #2a2a2a; }")
        custom_topbar_l = QHBoxLayout(custom_topbar)
        custom_topbar_l.setContentsMargins(24, 0, 20, 0)
        _ct_title = QLabel("Tools")
        _ct_title.setStyleSheet("color: #4CAF50; font-size: 15px; font-weight: bold; background: transparent;")
        custom_topbar_l.addWidget(_ct_title)
        custom_topbar_l.addStretch()
        custom_main_layout.addWidget(custom_topbar)

        # Body
        custom_body = QWidget()
        custom_body.setStyleSheet("background: #161616;")
        custom_body_l = QHBoxLayout(custom_body)
        custom_body_l.setSpacing(16)
        custom_body_l.setContentsMargins(24, 24, 24, 24)

        def _tool_card(title_key, icon, items):
            """items = list of (icon, label_key, slot) or None for coming-soon"""
            card = QFrame()
            card.setObjectName(f"toolCard_{title_key}")
            card.setStyleSheet(f"QFrame#toolCard_{title_key} {{ background: #1e1e1e; border: 1px solid #252525; border-radius: 8px; }}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)

            # Card header
            hdr = QFrame()
            hdr.setObjectName(f"toolCardHdr_{title_key}")
            hdr.setFixedHeight(44)
            hdr.setStyleSheet(f"QFrame#toolCardHdr_{title_key} {{ background: #252526; border: none; border-bottom: 1px solid #2a2a2a; border-radius: 8px 8px 0 0; }}")
            hdr_l = QHBoxLayout(hdr)
            hdr_l.setContentsMargins(16, 0, 16, 0)
            hdr_l.setSpacing(8)
            ico_lbl = QLabel()
            ico_lbl.setPixmap(qta.icon(icon, color='#4CAF50').pixmap(14, 14))
            ico_lbl.setStyleSheet("background: transparent;")
            hdr_l.addWidget(ico_lbl)
            title_lbl = _reg(QLabel(), title_key, "text")
            title_lbl.setStyleSheet("color: #cccccc; font-size: 12px; font-weight: bold; background: transparent;")
            hdr_l.addWidget(title_lbl)
            hdr_l.addStretch()
            cl.addWidget(hdr)

            # Content area
            content = QWidget()
            content.setStyleSheet("background: transparent;")
            content_l = QVBoxLayout(content)
            content_l.setContentsMargins(16, 16, 16, 16)
            content_l.setSpacing(8)

            if items is None:
                ph = _reg(QLabel(), "coming_soon", "text")
                ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
                ph.setStyleSheet("color: #3d3d3d; font-size: 12px; background: transparent;")
                content_l.addWidget(ph)
                content_l.addStretch()
            else:
                for btn_icon, btn_label_key, slot in items:
                    btn = QPushButton()
                    _reg(btn, btn_label_key, "text")
                    btn.setIcon(qta.icon(btn_icon, color='#ffffff'))
                    btn.setFixedHeight(38)
                    btn.setStyleSheet("""
                        QPushButton {
                            background: #4CAF50;
                            color: #ffffff;
                            border: none;
                            border-radius: 6px;
                            font-size: 12px;
                            font-weight: bold;
                            text-align: left;
                            padding-left: 8px;
                        }
                        QPushButton:hover { background: #45a049; }
                        QPushButton:pressed { background: #3d8b40; }
                    """)
                    if slot:
                        btn.clicked.connect(slot)
                    content_l.addWidget(btn)
                content_l.addStretch()

            cl.addWidget(content, 1)
            return card

        custom_body_l.addWidget(_tool_card(
            "card_interact", "fa5s.bolt",
            [('fa5s.user-plus', 'btn_auto_reg', self.open_auto_registration_tab)]
        ), 1)

        custom_body_l.addWidget(_tool_card(
            "card_group", "fa5s.users",
            None
        ), 1)

        custom_body_l.addWidget(_tool_card(
            "card_seeding", "fa5s.seedling",
            [('fa5s.robot', 'btn_automation', self.open_automation_tab)]
        ), 1)

        custom_body_l.addWidget(_tool_card(
            "card_navigate", "fa5s.compass",
            [
                ('fa5s.address-book', 'btn_accounts',  self.open_account_tab),
                ('fa5s.file-import',  'btn_import',     self.open_import_tab),
                ('fa5s.sign-in-alt',  'btn_login',      self.open_login_tab),
                ('fa5s.users',        'btn_accounts_only', self.open_accounts_only_tab),
            ]
        ), 1)

        custom_main_layout.addWidget(custom_body, 1)

        
        # Settings Tab - Redesigned
        settings_tab = QWidget()
        settings_tab.setStyleSheet("background: #161616;")
        settings_main_layout = QVBoxLayout(settings_tab)
        settings_main_layout.setSpacing(0)
        settings_main_layout.setContentsMargins(0, 0, 0, 0)

        # Top bar
        settings_topbar = QFrame()
        settings_topbar.setObjectName("settingsTopbar")
        settings_topbar.setFixedHeight(56)
        settings_topbar.setStyleSheet("QFrame#settingsTopbar { background: #1e1e1e; border: none; border-bottom: 1px solid #2a2a2a; }")
        settings_topbar_l = QHBoxLayout(settings_topbar)
        settings_topbar_l.setContentsMargins(24, 0, 20, 0)
        _st_title = _reg(QLabel(), "settings", "text")
        _st_title.setStyleSheet("color: #4CAF50; font-size: 15px; font-weight: bold; background: transparent;")
        settings_topbar_l.addWidget(_st_title)
        self._lbl_settings_title = _st_title
        settings_topbar_l.addStretch()

        _adv_btn = _reg(QPushButton(), "btn_advanced_config", "text")
        _adv_btn.setIcon(qta.icon('fa5s.sliders-h', color='#ffffff'))
        _adv_btn.setFixedHeight(32)
        _adv_btn.setStyleSheet("""
            QPushButton { background: #252526; color: #cccccc; border: 1px solid #3d3d3d; border-radius: 5px; font-size: 12px; padding: 0 14px; }
            QPushButton:hover { border-color: #4CAF50; color: #ffffff; }
        """)
        _adv_btn.clicked.connect(self.open_advanced_config_dialog)
        settings_topbar_l.addWidget(_adv_btn)
        self._btn_adv_config = _adv_btn
        settings_main_layout.addWidget(settings_topbar)

        # Scrollable body
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        settings_scroll.setStyleSheet("""
            QScrollArea { background: #161616; border: none; }
            QScrollBar:vertical { background: #161616; width: 5px; border-radius: 2px; }
            QScrollBar::handle:vertical { background: #2a2a2a; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        settings_body = QWidget()
        settings_body.setStyleSheet("background: #161616;")
        settings_body_l = QHBoxLayout(settings_body)
        settings_body_l.setSpacing(16)
        settings_body_l.setContentsMargins(24, 24, 24, 24)
        settings_body_l.setAlignment(Qt.AlignmentFlag.AlignTop)

        def _settings_card(obj_name, icon, title_key):
            card = QFrame()
            card.setObjectName(obj_name)
            card.setStyleSheet(f"QFrame#{obj_name} {{ background: #1e1e1e; border: 1px solid #252525; border-radius: 8px; }}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)
            hdr = QFrame()
            hdr.setObjectName(f"{obj_name}_hdr")
            hdr.setFixedHeight(44)
            hdr.setStyleSheet(f"QFrame#{obj_name}_hdr {{ background: #252526; border: none; border-bottom: 1px solid #2a2a2a; border-radius: 8px 8px 0 0; }}")
            hdr_l = QHBoxLayout(hdr)
            hdr_l.setContentsMargins(16, 0, 16, 0)
            hdr_l.setSpacing(8)
            ico = QLabel()
            ico.setPixmap(qta.icon(icon, color='#4CAF50').pixmap(14, 14))
            ico.setStyleSheet("background: transparent;")
            hdr_l.addWidget(ico)
            ttl = _reg(QLabel(), title_key, "text")
            ttl.setStyleSheet("color: #cccccc; font-size: 12px; font-weight: bold; background: transparent;")
            hdr_l.addWidget(ttl)
            hdr_l.addStretch()
            cl.addWidget(hdr)
            body = QWidget()
            body.setStyleSheet("background: transparent;")
            body_l = QVBoxLayout(body)
            body_l.setContentsMargins(16, 16, 16, 16)
            body_l.setSpacing(10)
            cl.addWidget(body)
            return card, body_l, ttl

        _field_style = """
            QLineEdit {
                background: #252526; border: 1px solid #3d3d3d; border-radius: 4px;
                padding: 0 10px; color: #cccccc; font-size: 12px;
            }
            QLineEdit:focus { border-color: #4CAF50; }
        """
        _combo_style_s = """
            QComboBox {
                background: #252526; border: 1px solid #3d3d3d; border-radius: 4px;
                padding: 0 10px; color: #cccccc; font-size: 12px;
            }
            QComboBox:hover { border-color: #4CAF50; }
            QComboBox::drop-down { border: none; width: 22px; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #888888; margin-right: 8px; }
            QComboBox QAbstractItemView { background: #252526; border: 1px solid #3d3d3d; color: #cccccc; selection-background-color: #2a4a2a; }
        """
        _lbl_s  = "color: #666666; font-size: 11px; background: transparent;"
        _green_s = """
            QPushButton { background: #4CAF50; color: #fff; border: none; border-radius: 6px; font-size: 12px; font-weight: bold; padding: 0 14px; }
            QPushButton:hover { background: #45a049; }
            QPushButton:pressed { background: #3d8b40; }
        """
        _ghost_s = """
            QPushButton { background: #252526; color: #aaaaaa; border: 1px solid #3d3d3d; border-radius: 6px; font-size: 12px; padding: 0 14px; }
            QPushButton:hover { border-color: #4CAF50; color: #ffffff; }
        """

        # Card 1: Device & Connection
        card1, c1, _sc1_ttl = _settings_card("settingsCard1", "fa5s.mobile-alt", "device_connection")
        self._lbl_sc_device = _sc1_ttl
        
        # Facebook Lite APK with logo
        fb_lite_row = QHBoxLayout(); fb_lite_row.setSpacing(8)
        fb_lite_logo = QLabel()
        fb_lite_logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", "Facebook_Lite.png")
        if os.path.exists(fb_lite_logo_path):
            # Create circular pixmap
            fb_lite_pixmap = QPixmap(fb_lite_logo_path).scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            circular = QPixmap(24, 24)
            circular.fill(Qt.GlobalColor.transparent)
            painter = QPainter(circular)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, 24, 24)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.drawPixmap(0, 0, fb_lite_pixmap)
            painter.end()
            fb_lite_logo.setPixmap(circular)
        fb_lite_row.addWidget(fb_lite_logo)
        apk_lbl = _reg(QLabel(), "lbl_fb_lite_apk", "text"); apk_lbl.setStyleSheet(_lbl_s)
        fb_lite_row.addWidget(apk_lbl); fb_lite_row.addStretch()
        c1.addLayout(fb_lite_row)
        
        apk_row = QHBoxLayout(); apk_row.setSpacing(6)
        self.apk_input = QLineEdit()
        self.apk_input.setPlaceholderText("Path to Facebook Lite .apk...")
        self.apk_input.setFixedHeight(32); self.apk_input.setStyleSheet(_field_style)
        apk_row.addWidget(self.apk_input)
        self.browse_btn = QPushButton()
        self.browse_btn.setIcon(qta.icon('fa5s.folder-open', color='#ffffff'))
        self.browse_btn.setFixedSize(32, 32); self.browse_btn.setStyleSheet(_green_s)
        self.browse_btn.clicked.connect(self.browse_apk)
        apk_row.addWidget(self.browse_btn); c1.addLayout(apk_row)

        # Facebook Original APK with logo
        fb_orig_row = QHBoxLayout(); fb_orig_row.setSpacing(8)
        fb_orig_logo = QLabel()
        fb_orig_logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", "Facebook_Logo.png")
        if os.path.exists(fb_orig_logo_path):
            # Create circular pixmap
            fb_orig_pixmap = QPixmap(fb_orig_logo_path).scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            circular = QPixmap(24, 24)
            circular.fill(Qt.GlobalColor.transparent)
            painter = QPainter(circular)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, 24, 24)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.drawPixmap(0, 0, fb_orig_pixmap)
            painter.end()
            fb_orig_logo.setPixmap(circular)
        fb_orig_row.addWidget(fb_orig_logo)
        apk_orig_lbl = _reg(QLabel(), "lbl_fb_orig_apk", "text"); apk_orig_lbl.setStyleSheet(_lbl_s)
        fb_orig_row.addWidget(apk_orig_lbl); fb_orig_row.addStretch()
        c1.addLayout(fb_orig_row)
        
        apk_orig_row = QHBoxLayout(); apk_orig_row.setSpacing(6)
        self.apk_orig_input = QLineEdit()
        self.apk_orig_input.setPlaceholderText("Path to Facebook Original .apk or folder...")
        self.apk_orig_input.setFixedHeight(32); self.apk_orig_input.setStyleSheet(_field_style)
        apk_orig_row.addWidget(self.apk_orig_input)
        browse_orig_btn = QPushButton()
        browse_orig_btn.setIcon(qta.icon('fa5s.folder-open', color='#ffffff'))
        browse_orig_btn.setFixedSize(32, 32); browse_orig_btn.setStyleSheet(_green_s)
        browse_orig_btn.clicked.connect(self.browse_apk_orig)
        apk_orig_row.addWidget(browse_orig_btn); c1.addLayout(apk_orig_row)
        app_lbl = _reg(QLabel(), "lbl_fb_app", "text"); app_lbl.setStyleSheet(_lbl_s); c1.addWidget(app_lbl)
        from src.ui.safe_combobox import SafeComboBox
        self.app_selection_input = SafeComboBox()
        self.app_selection_input.addItems(["Facebook Lite", "Facebook (Original)", "Messenger"])
        self.app_selection_input.setFixedHeight(32); self.app_selection_input.setStyleSheet(_combo_style_s)
        c1.addWidget(self.app_selection_input)
        self.panel1_device_count_label = _reg(QLabel(), "no_devices", "text")
        self.panel1_device_count_label.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        c1.addWidget(self.panel1_device_count_label)
        self.device_list_widget = QWidget(); self.device_list_widget.setVisible(False)
        self.device_list_layout = QVBoxLayout(self.device_list_widget); self.device_list_layout.setContentsMargins(0,0,0,0)
        self.device_checkboxes = []
        self.no_devices_label = QLabel("No devices detected."); self.no_devices_label.setVisible(False)
        self.device_input = QLineEdit(); self.device_input.setVisible(False)
        dev_btn = _reg(QPushButton(), "btn_device_settings", "text")
        dev_btn.setIcon(qta.icon('fa5s.cog', color='#ffffff'))
        dev_btn.setFixedHeight(36); dev_btn.setStyleSheet(_green_s)
        dev_btn.clicked.connect(self.open_device_settings_dialog)
        c1.addWidget(dev_btn); c1.addStretch()
        self._btn_device_settings = dev_btn
        settings_body_l.addWidget(card1, 1)

        # Card 2: Device Spoofing
        card2, c2, _sc2_ttl = _settings_card("settingsCard2", "fa5s.user-secret", "device_spoofing")
        self._lbl_sc_spoofing = _sc2_ttl
        spoof_row = QHBoxLayout(); spoof_row.setSpacing(8)
        spoof_lbl2 = _reg(QLabel(), "lbl_enable_spoofing", "text"); spoof_lbl2.setStyleSheet("color: #cccccc; font-size: 12px; background: transparent;")
        spoof_row.addWidget(spoof_lbl2); spoof_row.addStretch()
        self.enable_device_changer_checkbox = QCheckBox()
        self.enable_device_changer_checkbox.setChecked(True)
        self.enable_device_changer_checkbox.setStyleSheet("""
            QCheckBox::indicator { width: 36px; height: 18px; border-radius: 9px; background: #4CAF50; }
            QCheckBox::indicator:unchecked { background: #3d3d3d; }
        """)
        self.enable_device_changer_checkbox.toggled.connect(self.update_device_changer_status)
        spoof_row.addWidget(self.enable_device_changer_checkbox); c2.addLayout(spoof_row)
        desc2 = QLabel("Changes device identifiers to avoid detection")
        desc2.setStyleSheet("color: #555555; font-size: 11px; background: transparent;"); desc2.setWordWrap(True)
        c2.addWidget(desc2)
        mode_lbl2 = _reg(QLabel(), "lbl_change_mode", "text"); mode_lbl2.setStyleSheet(_lbl_s); c2.addWidget(mode_lbl2)
        self.device_changer_mode = SafeComboBox()
        self.device_changer_mode.addItems(["Per Account", "Per Session", "Fixed Device"])
        self.device_changer_mode.setFixedHeight(32); self.device_changer_mode.setStyleSheet(_combo_style_s)
        c2.addWidget(self.device_changer_mode)
        for attr in ['change_android_id_checkbox','change_device_model_checkbox',
                     'change_build_fingerprint_checkbox','change_serial_checkbox','change_mac_address_checkbox']:
            cb = QCheckBox(); cb.setChecked(True); cb.setVisible(False); setattr(self, attr, cb)
        self.spoof_build_checkbox  = self.change_build_fingerprint_checkbox
        self.spoof_serial_checkbox = self.change_serial_checkbox
        self.spoof_mac_checkbox    = self.change_mac_address_checkbox
        self.spoof_imei_checkbox   = QCheckBox(); self.spoof_imei_checkbox.setVisible(False)
        self.spoof_android_id_checkbox = self.change_android_id_checkbox
        adv_btn2 = _reg(QPushButton(), "btn_advanced_settings", "text")
        adv_btn2.setIcon(qta.icon('fa5s.sliders-h', color='#ffffff'))
        adv_btn2.setFixedHeight(36); adv_btn2.setStyleSheet(_green_s)
        adv_btn2.clicked.connect(self.open_device_changer_advanced_settings); c2.addWidget(adv_btn2)
        test_btn2 = _reg(QPushButton(), "btn_test_device", "text")
        test_btn2.setIcon(qta.icon('fa5s.sync-alt', color='#aaaaaa'))
        test_btn2.setFixedHeight(36); test_btn2.setStyleSheet(_ghost_s)
        test_btn2.clicked.connect(self.test_device_changer); c2.addWidget(test_btn2)
        c2.addStretch(); settings_body_l.addWidget(card2, 1)

        # Card 3: Automation & Performance
        card3, c3, _sc3_ttl = _settings_card("settingsCard3", "fa5s.robot", "automation_perf")
        self._lbl_sc_automation = _sc3_ttl
        summary_label = QLabel("Delay: 3s  |  Accounts: 1  |  Performance: Standard")
        summary_label.setStyleSheet("color: #555555; font-size: 11px; background: transparent;"); summary_label.setWordWrap(True)
        c3.addWidget(summary_label); self.automation_summary_label = summary_label
        self.delay_input = QSpinBox(); self.delay_input.setRange(1,60); self.delay_input.setValue(3); self.delay_input.setVisible(False)
        self.delay_input.valueChanged.connect(self.update_automation_summary)
        self.account_count_input = QSpinBox(); self.account_count_input.setRange(1,100); self.account_count_input.setValue(1); self.account_count_input.setVisible(False)
        self.account_count_input.valueChanged.connect(self.update_automation_summary)
        self.parallel_execution_checkbox = QCheckBox(); self.parallel_execution_checkbox.setVisible(False)
        self.parallel_execution_checkbox.toggled.connect(self.update_automation_summary)
        self.auto_retry_checkbox = QCheckBox(); self.auto_retry_checkbox.setChecked(True); self.auto_retry_checkbox.setVisible(False)
        auto_btn3 = _reg(QPushButton(), "btn_automation_settings", "text")
        auto_btn3.setIcon(qta.icon('fa5s.cog', color='#ffffff'))
        auto_btn3.setFixedHeight(36); auto_btn3.setStyleSheet(_green_s)
        auto_btn3.clicked.connect(self.open_automation_settings_dialog); c3.addWidget(auto_btn3)
        c3.addStretch(); settings_body_l.addWidget(card3, 1)
        self._btn_automation_settings = auto_btn3

        # Card 4: VPN
        card4, c4, _sc4_ttl = _settings_card("settingsCard4", "fa5s.shield-alt", "vpn_section")
        self._lbl_sc_vpn = _sc4_ttl
        
        # OpenVPN logo at the top
        openvpn_logo_row = QHBoxLayout(); openvpn_logo_row.setSpacing(0)
        openvpn_logo_row.addStretch()
        openvpn_logo_label = QLabel()
        openvpn_logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo", "openvpn.png")
        if os.path.exists(openvpn_logo_path):
            # Create circular OpenVPN logo (larger for visual impact)
            openvpn_pixmap = QPixmap(openvpn_logo_path).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            circular = QPixmap(48, 48)
            circular.fill(Qt.GlobalColor.transparent)
            painter = QPainter(circular)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, 48, 48)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.drawPixmap(0, 0, openvpn_pixmap)
            painter.end()
            openvpn_logo_label.setPixmap(circular)
            openvpn_logo_label.setStyleSheet("margin: 8px 0px;")
        openvpn_logo_row.addWidget(openvpn_logo_label)
        openvpn_logo_row.addStretch()
        c4.addLayout(openvpn_logo_row)

        # Enable VPN toggle row
        vpn_enable_row = QHBoxLayout(); vpn_enable_row.setSpacing(8)
        vpn_enable_lbl = _reg(QLabel(), "lbl_enable_vpn", "text"); vpn_enable_lbl.setStyleSheet("color: #cccccc; font-size: 12px; background: transparent;")
        vpn_enable_row.addWidget(vpn_enable_lbl); vpn_enable_row.addStretch()
        self.enable_vpn_checkbox = QCheckBox()
        self.enable_vpn_checkbox.setChecked(False)
        self.enable_vpn_checkbox.setStyleSheet("""
            QCheckBox::indicator { width: 36px; height: 18px; border-radius: 9px; background: #3d3d3d; }
            QCheckBox::indicator:checked { background: #4CAF50; }
        """)
        vpn_enable_row.addWidget(self.enable_vpn_checkbox)
        c4.addLayout(vpn_enable_row)

        # Status row
        vpn_status_row = QHBoxLayout(); vpn_status_row.setSpacing(8)
        vpn_status_lbl = _reg(QLabel(), "lbl_phone_vpn", "text"); vpn_status_lbl.setStyleSheet("color: #cccccc; font-size: 12px; background: transparent;")
        vpn_status_row.addWidget(vpn_status_lbl); vpn_status_row.addStretch()
        self.vpn_status_dot = QLabel(); self.vpn_status_dot.setFixedSize(10, 10)
        self.vpn_status_dot.setStyleSheet("background: #555555; border-radius: 5px;")
        vpn_status_row.addWidget(self.vpn_status_dot)
        self.vpn_status_val = QLabel("Disconnected")
        self.vpn_status_val.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        vpn_status_row.addWidget(self.vpn_status_val)
        c4.addLayout(vpn_status_row)

        # Advanced Settings button
        vpn_adv_btn = QPushButton("  Advanced Settings")
        vpn_adv_btn.setIcon(qta.icon('fa5s.cog', color='#ffffff'))
        vpn_adv_btn.setFixedHeight(36); vpn_adv_btn.setStyleSheet(_green_s)
        vpn_adv_btn.clicked.connect(self.open_vpn_advanced_settings)
        c4.addWidget(vpn_adv_btn)

        # Main action buttons
        vpn_connect_btn = _reg(QPushButton(), "btn_connect_phone", "text")
        vpn_connect_btn.setIcon(qta.icon('fa5s.plug', color='#ffffff'))
        vpn_connect_btn.setFixedHeight(36); vpn_connect_btn.setStyleSheet(_green_s)
        self.vpn_connect_btn = vpn_connect_btn
        vpn_connect_btn.clicked.connect(self._connect_vpn); c4.addWidget(vpn_connect_btn)
        self._btn_vpn_connect = vpn_connect_btn

        vpn_disconnect_btn = _reg(QPushButton(), "btn_disconnect_phone", "text")
        vpn_disconnect_btn.setIcon(qta.icon('fa5s.times-circle', color='#aaaaaa'))
        vpn_disconnect_btn.setFixedHeight(36); vpn_disconnect_btn.setStyleSheet(_ghost_s)
        vpn_disconnect_btn.clicked.connect(self._disconnect_vpn); c4.addWidget(vpn_disconnect_btn)
        self._btn_vpn_disconnect = vpn_disconnect_btn

        c4.addStretch()
        settings_body_l.addWidget(card4, 1)

        settings_scroll.setWidget(settings_body)
        settings_main_layout.addWidget(settings_scroll, 1)

        # Account Tab (created at startup but closable)
        account_tab = QWidget()
        account_tab.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)  # Prevent deletion when tab is closed
        account_tab.setStyleSheet("background-color: #1e1e1e;")
        account_tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        account_main_layout = QVBoxLayout(account_tab)
        account_main_layout.setSpacing(0)
        account_main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add spacer at top to prevent dropdowns from covering title bar
        top_spacer = QWidget()
        top_spacer.setFixedHeight(20)
        top_spacer.setStyleSheet("background-color: #1e1e1e;")
        account_main_layout.addWidget(top_spacer)

        # Toolbar — matches login/import tab style
        toolbar = QFrame()
        toolbar.setFixedHeight(56)
        toolbar.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-bottom: 1px solid #3d3d3d; }")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(20, 0, 16, 0)
        toolbar_layout.setSpacing(8)

        _ghost_btn_style = """
            QPushButton {
                background-color: #2d2d2d; color: #cccccc;
                border: 1px solid #3d3d3d; border-radius: 4px;
                font-size: 12px; font-weight: 600; padding: 0 14px;
            }
            QPushButton:hover { border-color: #4CAF50; color: #4CAF50; background-color: #333333; }
            QPushButton:pressed { background-color: #2a2a2a; }
        """

        # Search box
        self.account_search_input = QLineEdit()
        self.account_search_input.setPlaceholderText("Search...")
        self.account_search_input.setFixedHeight(32)
        self.account_search_input.setFixedWidth(160)
        self.account_search_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 0 10px;
                color: #cccccc;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #4CAF50; }
            QLineEdit:hover { border-color: #4CAF50; }
        """)
        toolbar_layout.addWidget(self.account_search_input)

        _combo_style = """
            QComboBox {
                background: #2d2d2d; border: 1px solid #3d3d3d; border-radius: 4px;
                padding: 0 8px; color: #cccccc; font-size: 11px;
                min-width: 90px; height: 32px;
            }
            QComboBox:hover { border-color: #4CAF50; }
            QComboBox::drop-down { border: none; width: 18px; }
            QComboBox::down-arrow { image: none; border-left: 4px solid transparent;
                border-right: 4px solid transparent; border-top: 5px solid #888; margin-right: 5px; }
            QComboBox QAbstractItemView { background: #252526; border: 1px solid #3d3d3d;
                color: #cccccc; selection-background-color: #4CAF50; selection-color: #fff; }
        """

        # Category filter
        self.account_category_filter = SafeComboBox()
        self.account_category_filter.addItems(["All", "Email", "Phone", "---"])
        for cat in self.load_custom_categories():
            self.account_category_filter.addItem(cat)
        self.account_category_filter.setStyleSheet(_combo_style)
        toolbar_layout.addWidget(self.account_category_filter)

        # Status filter - TEMPORARILY DISABLED to prevent dropdown overlay issue
        # TODO: Re-enable once dropdown positioning is fixed
        # self.account_status_filter = SafeComboBox()
        # self.account_status_filter.addItems(["All Status", "Active", "Idle"])
        # self.account_status_filter.setStyleSheet(_combo_style)
        # toolbar_layout.addWidget(self.account_status_filter)

        # Categories management button
        categories_btn = QPushButton(_T("btn_categories"))
        categories_btn.setFixedHeight(32)
        categories_btn.setStyleSheet(_ghost_btn_style)
        categories_btn.clicked.connect(self.manage_categories)
        toolbar_layout.addWidget(categories_btn)

        toolbar_layout.addStretch()

        _stat_style = "QLabel { background: transparent; color: #555555; font-size: 11px; font-weight: 500; padding: 0 8px; border: none; border-right: 1px solid #3d3d3d; }"
        _stat_sel_style = "QLabel { background: transparent; color: #4CAF50; font-size: 11px; font-weight: 500; padding: 0 8px; border: none; border-right: 1px solid #3d3d3d; }"

        self.acct_total_label = QLabel("0 accounts")
        self.acct_total_label.setStyleSheet(_stat_style)
        toolbar_layout.addWidget(self.acct_total_label)

        self.acct_selected_label = QLabel("0 selected")
        self.acct_selected_label.setStyleSheet(_stat_sel_style)
        toolbar_layout.addWidget(self.acct_selected_label)

        self.dev_total_label = QLabel("0 devices")
        self.dev_total_label.setStyleSheet(_stat_style)
        toolbar_layout.addWidget(self.dev_total_label)

        self.dev_selected_label = QLabel("0 selected")
        self.dev_selected_label.setStyleSheet(_stat_sel_style)
        self.dev_selected_label.setStyleSheet(self.dev_selected_label.styleSheet().replace("border-right: 1px solid #3d3d3d;", "border: none;"))
        toolbar_layout.addWidget(self.dev_selected_label)

        # Keep old stats_label for compatibility
        self.stats_label = self.dev_total_label

        load_devices_btn = QPushButton("  Load Devices")
        load_devices_btn.setIcon(qta.icon('fa5s.mobile-alt', color='#cccccc'))
        load_devices_btn.setFixedHeight(32)
        load_devices_btn.setStyleSheet(_ghost_btn_style)
        load_devices_btn.clicked.connect(self.auto_load_devices_to_account_tab)
        toolbar_layout.addWidget(load_devices_btn)

        refresh_account_btn = QPushButton()
        refresh_account_btn.setIcon(qta.icon('fa5s.sync-alt', color='#ffffff'))
        refresh_account_btn.setFixedSize(32, 32)
        refresh_account_btn.setToolTip("Refresh")
        refresh_account_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: #ffffff;
                border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        toolbar_layout.addWidget(refresh_account_btn)

        account_main_layout.addWidget(toolbar)

        # Split Panel Layout: Left (Accounts) | Right (Devices)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(16)
        splitter.setStyleSheet("""
            QSplitter {
                background-color: #1e1e1e;
            }
            QSplitter::handle {
                background-color: #1e1e1e;
                width: 16px;
            }
            QSplitter::handle:hover {
                background-color: #2a2a2a;
            }
        """)

        # ═══ LEFT PANEL: ACCOUNTS TABLE ═══
        left_panel = QFrame()
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Accounts Table
        self.account_table = QTableWidget()
        self.account_table.setColumnCount(12)
        self.account_table.setHorizontalHeaderLabels([
            "#", "UID", "Password", "Email", "Phone", "Name",
            "Pass/Mail", "Token", "Cookie", "2FA", "Created", "Category"
        ])
        self.account_table.setStyleSheet("""
            QTableWidget {
                background-color: #2d2d2d;
                border: none;
                color: #ffffff;
                font-size: 12px;
                gridline-color: transparent;
                selection-background-color: rgba(76, 175, 80, 0.2);
            }
            QTableWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #3d3d3d;
                background-color: transparent;
            }
            QTableWidget::item:selected {
                background-color: rgba(76, 175, 80, 0.3);
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #252526;
                color: #4CAF50;
                padding: 10px 12px;
                border: none;
                border-bottom: 2px solid #4CAF50;
                font-weight: bold;
                font-size: 11px;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background-color: #666666; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background-color: transparent;
                height: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background-color: #555555;
                border-radius: 5px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover { background-color: #666666; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """)
        acct_header = self.account_table.horizontalHeader()
        # Set all columns to ResizeToContents so text is never cut off
        acct_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # # column stays fixed
        acct_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # UID
        acct_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Password
        acct_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Email
        acct_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Phone
        acct_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Name
        acct_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Pass/Mail
        acct_header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Cookie
        acct_header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # 2FA
        acct_header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)  # Created
        acct_header.resizeSection(0, 44)    # # column fixed width
        acct_header.setHighlightSections(False)
        acct_header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # Enable horizontal scrolling with smooth behavior
        self.account_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.account_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.account_table.horizontalScrollBar().setSingleStep(10)
        self.account_table.horizontalScrollBar().setPageStep(100)
        
        self.account_table.verticalHeader().setVisible(False)
        self.account_table.verticalHeader().setDefaultSectionSize(44)
        self.account_table.setSortingEnabled(False)
        self.account_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.account_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.account_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.account_table.setShowGrid(False)
        self.account_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.account_table.setAlternatingRowColors(False)

        # Allow left-click on selected row to deselect
        def _acct_press(event):
            from PyQt6.QtCore import Qt as _Qt
            if event.button() == _Qt.MouseButton.LeftButton:
                idx = self.account_table.indexAt(event.pos())
                if idx.isValid() and self.account_table.selectionModel().isSelected(idx):
                    self.account_table.clearSelection()
                    event.accept()
                    return
            QTableWidget.mousePressEvent(self.account_table, event)
        self.account_table.mousePressEvent = _acct_press

        # Update selected count labels on selection change
        def _update_acct_sel():
            n = len(self.account_table.selectionModel().selectedRows())
            self.acct_selected_label.setText(f"{n} selected" if n else "0 selected")
        self.account_table.itemSelectionChanged.connect(_update_acct_sel)
        self.account_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.account_table.customContextMenuRequested.connect(self.show_account_context_menu)
        self.account_table.itemSelectionChanged.connect(self.on_account_selected)

        # Allow left-click on selected row to deselect (right-click keeps selection for context menu)
        def _acct_press(event):
            from PyQt6.QtCore import Qt as _Qt
            if event.button() == _Qt.MouseButton.LeftButton:
                idx = self.account_table.indexAt(event.pos())
                if idx.isValid() and self.account_table.selectionModel().isSelected(idx):
                    self.account_table.clearSelection()
                    event.accept()
                    return
            QTableWidget.mousePressEvent(self.account_table, event)
        self.account_table.mousePressEvent = _acct_press

        class _AcctLeftBorderDelegate(QStyledItemDelegate):
            def paint(self, painter, option, index):
                super().paint(painter, option, index)
                if index.column() == 0:
                    if option.state & QStyle.StateFlag.State_Selected:
                        painter.save()
                        painter.setClipping(False)
                        painter.setPen(QPen(QColor("#4CAF50"), 4))
                        x = option.rect.left() + 2
                        painter.drawLine(x, option.rect.top(), x, option.rect.bottom())
                        painter.restore()
        self.account_table.setItemDelegate(_AcctLeftBorderDelegate(self.account_table))

        left_layout.addWidget(self.account_table, 1)
        splitter.addWidget(left_panel)

        # ═══ RIGHT PANEL: DEVICES TABLE ═══
        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Devices Table
        self.devices_table = QTableWidget()
        self.devices_table.setColumnCount(7)
        self.devices_table.setHorizontalHeaderLabels([
            "#", "Device ID", "Model", "Proxy", "Status", "Assigned UID", "Device Changer"
        ])
        self.devices_table.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                border: none;
                color: #4CAF50;
                font-size: 12px;
                gridline-color: transparent;
                selection-background-color: transparent;
                outline: none;
            }
            QTableWidget::item {
                padding: 10px 12px;
                border: none;
                border-bottom: 1px solid #383838;
            }
            QTableWidget::item:selected {
                background-color: rgba(76, 175, 80, 0.15);
                color: #4CAF50;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #888888;
                padding: 8px 12px;
                border: none;
                border-bottom: 1px solid #3d3d3d;
                font-weight: 600;
                font-size: 10px;
                text-transform: uppercase;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #3d3d3d;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background-color: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background-color: transparent;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #3d3d3d;
                border-radius: 4px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover { background-color: #4CAF50; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """)
        dev_header = self.devices_table.horizontalHeader()
        # Set all columns to ResizeToContents so text is never cut off
        dev_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # # column stays fixed
        dev_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Device ID
        dev_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Model
        dev_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Proxy
        dev_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Status
        dev_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Assigned UID
        dev_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Device Changer
        dev_header.resizeSection(0, 44)    # # column fixed width
        
        # Enable horizontal scrolling with smooth behavior
        self.devices_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.devices_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.devices_table.horizontalScrollBar().setSingleStep(10)
        self.devices_table.horizontalScrollBar().setPageStep(100)

        class _LeftBorderDelegate(QStyledItemDelegate):
            def paint(self, painter, option, index):
                super().paint(painter, option, index)
                if index.column() == 0:
                    if option.state & QStyle.StateFlag.State_Selected:
                        painter.save()
                        painter.setClipping(False)
                        painter.setPen(QPen(QColor("#4CAF50"), 4))
                        x = option.rect.left() + 2
                        painter.drawLine(x, option.rect.top(), x, option.rect.bottom())
                        painter.restore()
        self.devices_table.setItemDelegate(_LeftBorderDelegate(self.devices_table))
        self.devices_table.itemSelectionChanged.connect(self.on_device_selected)

        # Update selected count label on selection change
        def _update_dev_sel():
            n = len(self.devices_table.selectionModel().selectedRows())
            if hasattr(self, 'dev_selected_label'):
                self.dev_selected_label.setText(f"{n} selected" if n else "0 selected")
        self.devices_table.itemSelectionChanged.connect(_update_dev_sel)
        dev_header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.devices_table.verticalHeader().setDefaultSectionSize(44)
        self.devices_table.verticalHeader().setVisible(False)
        self.devices_table.setSortingEnabled(True)
        self.devices_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.devices_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.devices_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.devices_table.setShowGrid(False)
        self.devices_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.devices_table.setAlternatingRowColors(False)
        self.devices_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.devices_table.customContextMenuRequested.connect(self.show_device_context_menu)

        right_layout.addWidget(self.devices_table, 1)
        splitter.addWidget(right_panel)

        # Wrap splitter in a container with padding so panels don't touch edges
        splitter_container = QWidget()
        splitter_container.setStyleSheet("background-color: #1e1e1e;")
        splitter_container_layout = QVBoxLayout(splitter_container)
        splitter_container_layout.setContentsMargins(12, 8, 12, 8)
        splitter_container_layout.addWidget(splitter)
        account_main_layout.addWidget(splitter_container, 1)

        # Connect signals
        self.account_search_input.textChanged.connect(self.filter_main_account_tab)
        self.account_category_filter.currentTextChanged.connect(self.filter_main_account_tab)
        # self.account_status_filter.currentTextChanged.connect(self.filter_main_account_tab)  # Disabled - filter removed
        refresh_account_btn.clicked.connect(self.load_main_account_tab)

        # Store reference - parent is self to prevent GC, tab added on demand
        self.main_account_tab = account_tab
        self.account_tab_index = -1
        
        # Import Accounts Tab
        import_tab = QWidget()
        import_tab.setStyleSheet("background-color: #1e1e1e;")
        import_main_layout = QVBoxLayout(import_tab)
        import_main_layout.setSpacing(0)
        import_main_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar — matches login tab style
        import_toolbar = QFrame()
        import_toolbar.setFixedHeight(56)
        import_toolbar.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-bottom: 1px solid #3d3d3d; }")
        import_toolbar_layout = QHBoxLayout(import_toolbar)
        import_toolbar_layout.setContentsMargins(20, 0, 16, 0)
        import_toolbar_layout.setSpacing(10)

        import_title = QLabel("Import Accounts")
        import_title.setStyleSheet("color: #4CAF50; font-size: 15px; font-weight: bold; background: transparent;")
        import_toolbar_layout.addWidget(import_title)
        import_toolbar_layout.addStretch()

        self.import_stats_label = QLabel("Ready to import")
        self.import_stats_label.setStyleSheet("QLabel { background: transparent; color: #555555; font-size: 11px; font-weight: 500; padding: 0; border: none; }")
        import_toolbar_layout.addWidget(self.import_stats_label)

        clear_import_btn = QPushButton()
        clear_import_btn.setIcon(qta.icon('fa5s.trash-alt', color='#f44336'))
        clear_import_btn.setFixedSize(32, 32)
        clear_import_btn.setToolTip("Clear")
        clear_import_btn.setStyleSheet("""
            QPushButton { background-color: #1e1e1e; border: 1px solid #2a2a2a; border-radius: 4px; }
            QPushButton:hover { background-color: #252525; border-color: #3e3e42; }
        """)
        clear_import_btn.clicked.connect(self.clear_import_form)
        import_toolbar_layout.addWidget(clear_import_btn)

        import_main_layout.addWidget(import_toolbar)
        
        # 2-Panel Layout
        panels_layout = QHBoxLayout()
        panels_layout.setSpacing(0)
        panels_layout.setContentsMargins(0, 0, 0, 0)

        # ── LEFT PANEL: Preview Table ─────────────────────────────────────
        left_panel = QFrame()
        left_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-right: 1px solid #3d3d3d; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Preview sub-toolbar
        preview_bar = QFrame()
        preview_bar.setFixedHeight(40)
        preview_bar.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-bottom: 1px solid #3d3d3d; }")
        preview_bar_layout = QHBoxLayout(preview_bar)
        preview_bar_layout.setContentsMargins(16, 0, 16, 0)
        preview_bar_layout.setSpacing(8)
        preview_title = QLabel("PREVIEW")
        preview_title.setStyleSheet("color: #555555; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; background: transparent;")
        preview_bar_layout.addWidget(preview_title)
        preview_bar_layout.addStretch()
        self.preview_info_label = QLabel("")
        self.preview_info_label.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        preview_bar_layout.addWidget(self.preview_info_label)
        left_layout.addWidget(preview_bar)

        # Preview Table
        self.import_preview_table = QTableWidget()
        self.import_preview_table.setColumnCount(10)
        self.import_preview_table.setHorizontalHeaderLabels(["UID", "Name", "Email", "Phone", "Password", "Birthday", "Gender", "Device", "Status", "Notes"])
        self.import_preview_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                border: none;
                color: #cccccc;
                font-size: 12px;
                gridline-color: #2d2d2d;
                selection-background-color: rgba(76,175,80,0.2);
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2d2d2d;
            }
            QTableWidget::item:selected {
                background-color: rgba(76,175,80,0.3);
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #252526;
                color: #4CAF50;
                padding: 10px 8px;
                border: none;
                border-bottom: 2px solid #4CAF50;
                font-weight: bold;
                font-size: 11px;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #3d3d3d;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background-color: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #3d3d3d;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover { background-color: #4CAF50; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """)
        imp_header = self.import_preview_table.horizontalHeader()
        for i in range(9):  # All columns except last
            imp_header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        # Last column stretches to fill remaining space
        imp_header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        imp_header.setHighlightSections(False)
        self.import_preview_table.verticalHeader().setVisible(False)
        self.import_preview_table.setShowGrid(False)
        self.import_preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.import_preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.import_preview_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Enable horizontal scrolling with smooth behavior (same as account table)
        self.import_preview_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.import_preview_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.import_preview_table.horizontalScrollBar().setSingleStep(10)
        left_layout.addWidget(self.import_preview_table)

        # ── RIGHT PANEL: Configuration ────────────────────────────────────
        right_panel = QFrame()
        right_panel.setFixedWidth(500)
        right_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; }")

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: #1e1e1e; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #3d3d3d; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        right_content = QWidget()
        right_content.setStyleSheet("background-color: #1e1e1e;")
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(4)

        # ── helpers ───────────────────────────────────────────────────────
        def _imp_slabel(text):
            l = QLabel(text)
            l.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; background: transparent; padding: 8px 0 4px 0;")
            return l

        _imp_input_style = """
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px 10px;
                color: #cccccc;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #4CAF50; }
        """

        # FILE SELECTION
        right_layout.addWidget(_imp_slabel("FILE SELECTION"))

        # Radio buttons
        radio_row = QHBoxLayout()
        radio_row.setSpacing(16)
        _radio_style = """
            QRadioButton { color: #cccccc; font-size: 12px; spacing: 6px; background: transparent; }
            QRadioButton::indicator { width: 14px; height: 14px; border: 1px solid #3d3d3d; border-radius: 7px; background: #2d2d2d; }
            QRadioButton::indicator:checked { background-color: #4CAF50; border-color: #4CAF50; }
            QRadioButton::indicator:hover { border-color: #4CAF50; }
        """
        self.import_type_file = QRadioButton("File (CSV/JSON)")
        self.import_type_file.setChecked(True)
        self.import_type_file.setStyleSheet(_radio_style)
        self.import_type_folder = QRadioButton("Folder (TAR)")
        self.import_type_folder.setStyleSheet(_radio_style)
        self.import_type_custom = QRadioButton("Custom Paste")
        self.import_type_custom.setStyleSheet(_radio_style)
        radio_row.addWidget(self.import_type_file)
        radio_row.addWidget(self.import_type_folder)
        radio_row.addWidget(self.import_type_custom)
        radio_row.addStretch()
        right_layout.addLayout(radio_row)

        right_layout.addSpacing(4)

        # File path input (for File/Folder modes)
        self.import_file_path = QLineEdit()
        self.import_file_path.setPlaceholderText("No file/folder selected...")
        self.import_file_path.setReadOnly(True)
        self.import_file_path.setFixedHeight(36)
        self.import_file_path.setStyleSheet(_imp_input_style)
        right_layout.addWidget(self.import_file_path)

        # Custom paste text area (for Custom Paste mode)
        self.import_custom_text = QTextEdit()
        self.import_custom_text.setPlaceholderText("Paste your account data here...\n\nSupported formats:\n• uid|password|2fa|cookie|token\n• uid,password,email,phone\n• Any delimiter: | , ; or tab\n\nExample:\n61587123456|mypass123|ABCD1234|c_user=123;xs=abc|token123\n61587789012|pass456|EFGH5678|c_user=456;xs=def|token456")
        self.import_custom_text.setFixedHeight(150)
        self.import_custom_text.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                color: #cccccc;
                font-size: 11px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QTextEdit:focus { border-color: #4CAF50; }
        """)
        self.import_custom_text.setVisible(False)
        # Auto-validate when text changes (with debounce)
        self.import_custom_text.textChanged.connect(self._on_custom_text_changed)
        right_layout.addWidget(self.import_custom_text)

        right_layout.addSpacing(4)

        browse_btn = QPushButton("  Browse")
        browse_btn.setIcon(qta.icon('fa5s.folder-open', color='#ffffff'))
        browse_btn.setFixedHeight(38)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: #ffffff;
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        browse_btn.clicked.connect(self.browse_import_file)
        self.import_browse_btn = browse_btn
        right_layout.addWidget(browse_btn)

        # Connect radio buttons to toggle UI
        self.import_type_file.toggled.connect(self.toggle_import_mode)
        self.import_type_folder.toggled.connect(self.toggle_import_mode)
        self.import_type_custom.toggled.connect(self.toggle_import_mode)

        self.file_info_label = QLabel("")
        self.file_info_label.setStyleSheet("color: #555555; font-size: 11px; background: transparent;")
        self.file_info_label.setWordWrap(True)
        self.file_info_label.setVisible(False)
        right_layout.addWidget(self.file_info_label)

        # Divider
        right_layout.addSpacing(8)
        _d1 = QFrame(); _d1.setFrameShape(QFrame.Shape.HLine)
        _d1.setStyleSheet("background: #3d3d3d; border: none; max-height: 1px;")
        right_layout.addWidget(_d1)

        # SETTINGS
        right_layout.addWidget(_imp_slabel("SETTINGS"))

        # Initialize import format settings with defaults
        self.import_format_type = "CSV (Standard)"
        self.import_delimiter = ","
        self.import_has_header = True

        advanced_settings_btn = QPushButton("  Advanced Settings")
        advanced_settings_btn.setIcon(qta.icon('fa5s.sliders-h', color='#cccccc'))
        advanced_settings_btn.setFixedHeight(38)
        advanced_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d; color: #cccccc;
                border: 1px solid #3d3d3d; border-radius: 4px;
                font-size: 12px; font-weight: 600;
            }
            QPushButton:hover { border-color: #4CAF50; color: #4CAF50; background-color: #333333; }
        """)
        advanced_settings_btn.clicked.connect(self.open_import_advanced_settings)
        right_layout.addWidget(advanced_settings_btn)

        # Divider
        right_layout.addSpacing(8)
        _d2 = QFrame(); _d2.setFrameShape(QFrame.Shape.HLine)
        _d2.setStyleSheet("background: #3d3d3d; border: none; max-height: 1px;")
        right_layout.addWidget(_d2)

        # VALIDATION
        right_layout.addWidget(_imp_slabel("VALIDATION"))

        validate_btn = QPushButton("  Validate File")
        validate_btn.setIcon(qta.icon('fa5s.check-circle', color='#cccccc'))
        validate_btn.setFixedHeight(38)
        validate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d; color: #cccccc;
                border: 1px solid #3d3d3d; border-radius: 4px;
                font-size: 12px; font-weight: 600;
            }
            QPushButton:hover { border-color: #4CAF50; color: #4CAF50; background-color: #333333; }
        """)
        validate_btn.clicked.connect(self.validate_import_file)
        right_layout.addWidget(validate_btn)

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #555555; font-size: 11px; background: transparent; padding: 2px 0;")
        self.validation_label.setWordWrap(True)
        right_layout.addWidget(self.validation_label)

        right_layout.addStretch()

        # Divider before import button
        _d3 = QFrame(); _d3.setFrameShape(QFrame.Shape.HLine)
        _d3.setStyleSheet("background: #3d3d3d; border: none; max-height: 1px;")
        right_layout.addWidget(_d3)
        right_layout.addSpacing(8)

        # Import button
        self.import_accounts_btn = QPushButton("  Import Accounts")
        self.import_accounts_btn.setIcon(qta.icon('fa5s.file-import', color='#ffffff'))
        self.import_accounts_btn.setEnabled(False)
        self.import_accounts_btn.setFixedHeight(44)
        self.import_accounts_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: #ffffff;
                border: none; border-radius: 4px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover:enabled { background-color: #45a049; }
            QPushButton:pressed:enabled { background-color: #3d8b40; }
            QPushButton:disabled { background-color: #2d2d2d; color: #555555; border: 1px solid #3d3d3d; }
        """)
        self.import_accounts_btn.clicked.connect(self.import_accounts)
        right_layout.addWidget(self.import_accounts_btn)

        right_scroll.setWidget(right_content)
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(0)
        right_panel_layout.addWidget(right_scroll)

        panels_layout.addWidget(left_panel, 1)
        panels_layout.addWidget(right_panel)
        import_main_layout.addLayout(panels_layout)

        self.main_import_tab = import_tab
        
        # Login Tab - Professional web-app style
        login_tab = QWidget()
        login_tab.setStyleSheet("background-color: #0f0f0f;")
        login_main_layout = QHBoxLayout(login_tab)
        login_main_layout.setSpacing(0)
        login_main_layout.setContentsMargins(0, 0, 0, 0)

        # ── Left Panel: Account Queue (65% width) ─────────────────────────
        left_panel = QFrame()
        left_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-right: 1px solid #3d3d3d; }")
        left_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_panel.setMinimumWidth(400)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(0)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Top toolbar
        left_toolbar = QFrame()
        left_toolbar.setFixedHeight(56)
        left_toolbar.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-bottom: 1px solid #3d3d3d; }")
        left_toolbar_layout = QHBoxLayout(left_toolbar)
        left_toolbar_layout.setContentsMargins(20, 0, 16, 0)
        left_toolbar_layout.setSpacing(10)

        # Title + count
        left_title = QLabel("Account Queue")
        left_title.setStyleSheet("color: #4CAF50; font-size: 15px; font-weight: bold; background: transparent;")
        left_toolbar_layout.addWidget(left_title)

        self.queue_count_badge = QLabel("0 accounts")
        self.queue_count_badge.setStyleSheet("QLabel { background-color: transparent; color: #444444; font-size: 11px; font-weight: 500; padding: 0px; border: none; }")
        left_toolbar_layout.addWidget(self.queue_count_badge)
        left_toolbar_layout.addStretch()

        # Toolbar action buttons
        select_account_btn = QPushButton("Add Account")
        select_account_btn.setIcon(qta.icon('fa5s.plus', color='#ffffff'))
        select_account_btn.setFixedHeight(32)
        select_account_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                padding: 0 14px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        select_account_btn.clicked.connect(self.select_account_for_login)
        left_toolbar_layout.addWidget(select_account_btn)

        clear_queue_btn = QPushButton()
        clear_queue_btn.setIcon(qta.icon('fa5s.trash-alt', color='#f44336'))
        clear_queue_btn.setFixedSize(32, 32)
        clear_queue_btn.setToolTip("Clear all")
        clear_queue_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e1e1e;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #252525; border-color: #3e3e42; }
        """)
        clear_queue_btn.clicked.connect(self.clear_login_queue)
        left_toolbar_layout.addWidget(clear_queue_btn)

        left_layout.addWidget(left_toolbar)

        # Login Queue Table
        self.login_queue_table = QTableWidget()
        self.login_queue_table.setColumnCount(8)
        self.login_queue_table.setHorizontalHeaderLabels(["Name", "UID", "Phone", "Password", "Device Info", "Assigned To", "Status", "Date"])
        self.login_queue_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                color: #ffffff;
                font-size: 12px;
                gridline-color: #2d2d2d;
                selection-background-color: rgba(76, 175, 80, 0.2);
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2d2d2d;
            }
            QTableWidget::item:selected {
                background-color: rgba(76, 175, 80, 0.3);
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #4CAF50;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #4CAF50;
                font-weight: bold;
                font-size: 12px;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666666;
            }
        """)
        header = self.login_queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)           # Name — fills space
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)             # UID
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)             # Phone
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)             # Password
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)             # Device Info
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)             # Assigned To
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)             # Status
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)             # Date
        header.resizeSection(1, 130)   # UID
        header.resizeSection(2, 110)   # Phone
        header.resizeSection(3, 90)    # Password
        header.resizeSection(4, 100)   # Device Info
        header.resizeSection(5, 130)   # Assigned To (wider for full device ID)
        header.resizeSection(6, 80)    # Status
        header.resizeSection(7, 90)    # Date
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.login_queue_table.verticalHeader().setDefaultSectionSize(52)
        self.login_queue_table.verticalHeader().setVisible(False)
        self.login_queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.login_queue_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.login_queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.login_queue_table.setShowGrid(False)
        self.login_queue_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.login_queue_table.setAlternatingRowColors(False)
        self.login_queue_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.login_queue_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.login_queue_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.login_queue_table.setMaximumHeight(16777215)  # Qt's QWIDGETSIZE_MAX - no artificial limit
        left_layout.addWidget(self.login_queue_table, 1)  # stretch factor 1

        # Bottom stats bar
        left_stats_bar = QFrame()
        left_stats_bar.setFixedHeight(40)
        left_stats_bar.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-top: 1px solid #3d3d3d; }")
        left_stats_layout = QHBoxLayout(left_stats_bar)
        left_stats_layout.setContentsMargins(20, 0, 20, 0)
        left_stats_layout.setSpacing(20)

        self._lstat_total = QLabel("Total: 0")
        self._lstat_done  = QLabel("Done: 0")
        self._lstat_fail  = QLabel("Failed: 0")
        for _lbl, _col in [(self._lstat_total, "#555555"), (self._lstat_done, "#4CAF50"), (self._lstat_fail, "#f44336")]:
            _lbl.setStyleSheet(f"color: {_col}; font-size: 11px; font-weight: 500; background: transparent;")
            left_stats_layout.addWidget(_lbl)
        left_stats_layout.addStretch()
        left_layout.addWidget(left_stats_bar)

        login_main_layout.addWidget(left_panel, 65)
        
        # ── Right Panel: Controls (35% width) ────────────────────────────
        right_panel = QFrame()
        right_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; }")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Top bar — same height as left toolbar
        right_top_bar = QFrame()
        right_top_bar.setFixedHeight(56)
        right_top_bar.setStyleSheet("QFrame { background-color: #1e1e1e; border: none; border-bottom: 1px solid #3d3d3d; }")
        right_top_bar_layout = QHBoxLayout(right_top_bar)
        right_top_bar_layout.setContentsMargins(16, 0, 16, 0)
        right_top_bar_layout.setSpacing(10)
        right_title = QLabel("Controls")
        right_title.setStyleSheet("color: #4CAF50; font-size: 15px; font-weight: bold; background: transparent;")
        right_top_bar_layout.addWidget(right_title)
        right_top_bar_layout.addStretch()
        self.login_status_label = QLabel("Idle")
        self.login_status_label.setStyleSheet("QLabel { background-color: transparent; color: #555555; font-size: 11px; font-weight: 500; padding: 0px; border: none; }")
        right_top_bar_layout.addWidget(self.login_status_label)
        right_layout.addWidget(right_top_bar)

        # Scrollable content area
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 6px; background: #1e1e1e; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #3d3d3d; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #4CAF50; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        right_content = QWidget()
        right_content.setStyleSheet("background-color: #1e1e1e;")
        rc = QVBoxLayout(right_content)
        rc.setSpacing(4)
        rc.setContentsMargins(16, 16, 16, 16)

        # ── helpers ───────────────────────────────────────────────────────
        def _slabel(text):
            l = QLabel(text)
            l.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; background: transparent; padding: 6px 0 4px 0;")
            return l

        _input_style = """
            QComboBox, QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 12px;
            }
            QComboBox:hover, QLineEdit:hover { border-color: #4CAF50; }
            QComboBox:focus, QLineEdit:focus { border-color: #4CAF50; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #888888;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                color: #ffffff;
                selection-background-color: rgba(76,175,80,0.2);
                outline: none;
                padding: 4px;
            }
        """

        # Device selection container with refresh button in corner
        device_container = QWidget()
        device_container.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
        """)
        device_container_layout = QVBoxLayout(device_container)
        device_container_layout.setContentsMargins(0, 0, 0, 0)
        device_container_layout.setSpacing(0)
        
        # Header with DEVICE label and refresh button
        header_widget = QWidget()
        header_widget.setStyleSheet("background-color: transparent; border: none;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(8)
        
        device_label = QLabel("DEVICE")
        device_label.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; background: transparent; border: none;")
        header_layout.addWidget(device_label)
        
        header_layout.addStretch()
        
        refresh_devices_btn = QPushButton()
        refresh_devices_btn.setIcon(qta.icon('fa5s.sync-alt', color='#888888'))
        refresh_devices_btn.setFixedSize(24, 24)
        refresh_devices_btn.setToolTip("Refresh devices")
        refresh_devices_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_devices_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { 
                background-color: #3d3d3d;
            }
        """)
        refresh_devices_btn.clicked.connect(self._refresh_all_devices)
        header_layout.addWidget(refresh_devices_btn)
        
        device_container_layout.addWidget(header_widget)
        
        # Separator line
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #3d3d3d; border: none;")
        device_container_layout.addWidget(separator)
        
        # Device table with Proxy and Device Changer columns
        self.login_device_select = QTableWidget()
        self.login_device_select.setColumnCount(3)
        self.login_device_select.setHorizontalHeaderLabels(["Device", "Proxy", "Device Changer"])
        self.login_device_select.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.login_device_select.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.login_device_select.verticalHeader().setVisible(False)
        self.login_device_select.setShowGrid(False)
        self.login_device_select.horizontalHeader().setStretchLastSection(True)
        self.login_device_select.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.login_device_select.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.login_device_select.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                border: none;
                color: #e0e0e0;
                font-size: 12px;
                gridline-color: transparent;
                selection-background-color: transparent;
                outline: none;
            }
            QTableWidget::item {
                padding: 6px 10px;
                border: none;
                border-bottom: 1px solid #383838;
            }
            QTableWidget::item:selected {
                background-color: rgba(76, 175, 80, 0.15);
                color: #4CAF50;
            }
            QTableWidget::item:hover { background-color: transparent; }
            QTableWidget::item:selected:hover {
                background-color: rgba(76, 175, 80, 0.15);
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #888888;
                font-size: 11px;
                padding: 4px 10px;
                border: none;
                border-bottom: 1px solid #3d3d3d;
                font-weight: 600;
                text-transform: uppercase;
            }
        """)
        self.login_device_select.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        device_container_layout.addWidget(self.login_device_select)
        
        device_container.setFixedHeight(240)
        dev_row = QHBoxLayout()
        dev_row.addWidget(device_container)
        rc.addLayout(dev_row)

        # 2-Column Layout using HBoxLayout
        two_col_row = QHBoxLayout()
        two_col_row.setSpacing(10)
        two_col_row.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # LEFT COLUMN - Verification Method
        left_col_widget = QWidget()
        left_col = QVBoxLayout(left_col_widget)
        left_col.setSpacing(8)
        left_col.setContentsMargins(0, 0, 0, 0)
        
        left_col.addWidget(_slabel("VERIFICATION METHOD"))
        
        self.verification_method = SafeComboBox()
        self.verification_method.addItems(["Auto Detect", "SMS Code", "Email Code", "2FA Authenticator", "Backup Codes", "Security Questions"])
        self.verification_method.setStyleSheet(_input_style)
        self.verification_method.setFixedHeight(38)
        left_col.addWidget(self.verification_method)

        # Verification code (hidden)
        self.verification_code_label = QLabel("VERIFICATION CODE")
        self.verification_code_label.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; background: transparent; padding: 6px 0 4px 0;")
        self.verification_code_label.setVisible(False)
        left_col.addWidget(self.verification_code_label)
        
        code_row = QHBoxLayout()
        code_row.setSpacing(6)
        self.verification_code_input = QLineEdit()
        self.verification_code_input.setPlaceholderText("Enter code...")
        self.verification_code_input.setStyleSheet(_input_style)
        self.verification_code_input.setFixedHeight(38)
        self.verification_code_input.setVisible(False)
        code_row.addWidget(self.verification_code_input)
        self.submit_code_btn = QPushButton("Submit")
        self.submit_code_btn.setFixedHeight(38)
        self.submit_code_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 0 16px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.submit_code_btn.setVisible(False)
        self.submit_code_btn.clicked.connect(self.submit_verification_code)
        code_row.addWidget(self.submit_code_btn)
        left_col.addLayout(code_row)
        
        two_col_row.addWidget(left_col_widget, 1)
        
        # RIGHT COLUMN - Actions
        right_col_widget = QWidget()
        right_col = QVBoxLayout(right_col_widget)
        right_col.setSpacing(8)
        right_col.setContentsMargins(0, 0, 0, 0)
        
        right_col.addWidget(_slabel("ACTIONS"))
        
        # Advanced Settings Button
        self.advanced_settings_btn = QPushButton("  Advanced Settings")
        self.advanced_settings_btn.setIcon(qta.icon('fa5s.cog', color='#888888'))
        self.advanced_settings_btn.setFixedHeight(36)
        self.advanced_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888888;
                font-size: 12px;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                text-align: left;
                padding-left: 8px;
            }
            QPushButton:hover { 
                border-color: #4CAF50; 
                color: #4CAF50;
                background-color: #2d2d2d;
            }
        """)
        self.advanced_settings_btn.clicked.connect(self._open_advanced_settings)
        right_col.addWidget(self.advanced_settings_btn)
        
        two_col_row.addWidget(right_col_widget, 1)
        
        # Add the 2-column row to main layout
        rc.addLayout(two_col_row)
        
        rc.addSpacing(12)
        
        # Restore and Login buttons - FULL WIDTH below both columns
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        self.restore_session_btn = QPushButton("  Restore Session")
        self.restore_session_btn.setIcon(qta.icon('fa5s.cloud-download-alt', color='#ffffff'))
        self.restore_session_btn.setFixedHeight(44)
        self.restore_session_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                text-align: center;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
            QPushButton:disabled { background-color: #2d2d2d; color: #555555; border: 1px solid #3d3d3d; }
        """)
        self.restore_session_btn.setToolTip("Push saved Facebook session to device (requires root)")
        self.restore_session_btn.clicked.connect(self.start_login_process)
        buttons_row.addWidget(self.restore_session_btn)

        self.login_btn = QPushButton("  Start Login")
        self.login_btn.setIcon(qta.icon('fa5s.sign-in-alt', color='#ffffff'))
        self.login_btn.setFixedHeight(44)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                text-align: center;
            }
            QPushButton:hover { background-color: #333333; border-color: #4CAF50; color: #4CAF50; }
            QPushButton:disabled { color: #555555; border-color: #2d2d2d; }
        """)
        self.login_btn.clicked.connect(self.start_login_process)
        buttons_row.addWidget(self.login_btn)
        
        rc.addLayout(buttons_row)

        rc.addStretch()

        # Stop button pinned at bottom
        self.stop_login_btn = QPushButton("  Stop Process")
        self.stop_login_btn.setIcon(qta.icon('fa5s.stop-circle', color='#f44336'))
        self.stop_login_btn.setFixedHeight(36)
        self.stop_login_btn.setEnabled(False)
        self.stop_login_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #f44336;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                text-align: center;
            }
            QPushButton:hover { border-color: #f44336; background-color: #2d2d2d; }
            QPushButton:disabled { color: #3d3d3d; border-color: #2d2d2d; }
        """)
        self.stop_login_btn.clicked.connect(self.stop_login_process)
        rc.addWidget(self.stop_login_btn)

        right_scroll.setWidget(right_content)
        right_layout.addWidget(right_scroll)

        login_main_layout.addWidget(right_panel, 35)
        
        # Store reference to login tab widget
        self.main_login_tab = login_tab
        
        # Automation Tab - built via helper
        self.main_automation_tab = self._build_automation_tab()
        
        # Add tabs
        self.tab_widget.addTab(dashboard_tab, "Dashboard")
        self.tab_widget.addTab(custom_tab, "Custom")
        self.tab_widget.addTab(settings_tab, "Settings")
        
        # Account, Login, and Automation tabs will be added dynamically when needed or restored from config
        self.account_tab_index = -1
        self.import_tab_index = -1
        self.login_tab_index = -1
        self.automation_tab_index = -1
        
        # Set tab bar to not expand - keeps tabs same size
        self.tab_widget.tabBar().setExpanding(False)
        
        # Add invisible spacer to first 3 main tabs (Dashboard, Custom, Settings)
        for i in range(3):
            spacer = QLabel()
            spacer.setFixedWidth(20)
            spacer.setStyleSheet("background: transparent;")
            self.tab_widget.tabBar().setTabButton(i, QTabBar.ButtonPosition.RightSide, spacer)
        
        content_layout.addWidget(self.tab_widget)
        outer_layout.addWidget(content_widget)
        
        # Force immediate layout calculation to prevent black bar
        self.updateGeometry()
        central.updateGeometry()
        outer_layout.activate()
        QApplication.processEvents()
        
        # Force layout calculation before showing
        central.updateGeometry()
        outer_layout.update()
        
        # Ensure title bar is on top after all widgets are added
        self.title_bar.raise_()
        
        # Register all i18n widgets after UI is built
        self._register_i18n_widgets()
        

    def _register_i18n_widgets(self):
        """Register all main UI widgets for language switching."""
        pairs = [
            # Dashboard
            ("_lbl_overview",       "overview"),
            ("_lbl_success_rate",   "success_rate"),
            ("_lbl_acct_breakdown", "account_breakdown"),
            ("_lbl_quick_actions",  "quick_actions"),
            ("_lbl_activity_log",   "activity_log"),
            # Settings
            ("_lbl_settings_title", "settings"),
            ("_btn_adv_config",     "btn_advanced_config"),
            ("_lbl_sc_device",      "device_connection"),
            ("_lbl_sc_spoofing",    "device_spoofing"),
            ("_lbl_sc_automation",  "automation_perf"),
            ("_lbl_sc_vpn",         "vpn_section"),
            ("_btn_device_settings","btn_device_settings"),
            ("_btn_automation_settings", "btn_automation_settings"),
            ("_btn_vpn_connect",    "btn_connect_phone"),
            ("_btn_vpn_disconnect", "btn_disconnect_phone"),
        ]
        for attr, key in pairs:
            w = getattr(self, attr, None)
            if w:
                _reg(w, key)
        
        # CRITICAL FIX: Hide mystery widget immediately after UI is built
        # This prevents the black overlay from showing at all
        QTimer.singleShot(0, self._hide_mystery_widgets)


    def apply_global_language(self, lang: str):
        """Public method to switch language and refresh all registered widgets + tabs."""
        apply_language(lang)
        # Update static tabs
        _tab_keys = ["tab_dashboard", "tab_custom", "tab_settings"]
        for i, k in enumerate(_tab_keys):
            if i < self.tab_widget.count():
                self.tab_widget.setTabText(i, _T(k))
        # Update dynamic tabs
        _dyn_map = {
            "tab_account": list(TRANSLATIONS[l]["tab_account"] for l in TRANSLATIONS),
            "tab_login": list(TRANSLATIONS[l]["tab_login"] for l in TRANSLATIONS),
            "tab_automation": list(TRANSLATIONS[l]["tab_automation"] for l in TRANSLATIONS),
            "tab_import": list(TRANSLATIONS[l]["tab_import"] for l in TRANSLATIONS),
            "tab_auto_reg": list(TRANSLATIONS[l]["tab_auto_reg"] for l in TRANSLATIONS),
        }
        for i in range(self.tab_widget.count()):
            txt = self.tab_widget.tabText(i)
            for key, all_names in _dyn_map.items():
                if txt in all_names:
                    self.tab_widget.setTabText(i, _T(key))
                    break


    def mousePressEvent(self, event):
        # Only allow dragging from title bar area (top 55 pixels)
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 55:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            event.ignore()
            

    def mouseMoveEvent(self, event):
        # Only move if drag started from title bar
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos and event.position().y() <= 55:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
        else:
            event.ignore()
    

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setIcon(qta.icon('fa5s.square', color='#ffffff'))
            self.max_btn.setToolTip("Maximize")
        else:
            self.showMaximized()
            self.max_btn.setIcon(qta.icon('fa5s.compress', color='#ffffff'))
            self.max_btn.setToolTip("Restore")
    
    def _open_telegram_link(self):
        """Open Telegram contact link in default browser"""
        import webbrowser
        try:
            webbrowser.open("https://t.me/ftoolpro")
            self.add_activity("Opened Telegram contact link")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open link: {e}")
    
    def _get_expiry_display(self):
        """Read license file and return (text, color, bg_color) for expiry pill."""
        try:
            import json, os
            from datetime import datetime, timezone
            license_file = os.path.join(os.path.expanduser('~'), '.frt_license.json')
            if os.path.exists(license_file):
                with open(license_file, 'r') as f:
                    data = json.load(f)
                expiry_str = data.get('expiry_date', '')
                if expiry_str:
                    expiry_dt = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    days_left = (expiry_dt - now).days

                    # Check if it's a lifetime license (more than 50 years = 18250 days)
                    if days_left > 18250:
                        return "Lifetime", "#4CAF50", "rgba(76,175,80,0.12)"
                    elif days_left < 0:
                        return "Expired", "#ef4444", "rgba(239,68,68,0.12)"
                    elif days_left <= 7:
                        return f"⚠ {days_left}d left", "#ef4444", "rgba(239,68,68,0.12)"
                    elif days_left <= 30:
                        return f"Exp: {days_left}d left", "#FFA726", "rgba(255,152,0,0.12)"
                    else:
                        return f"Exp: {days_left}d left", "#4CAF50", "rgba(76,175,80,0.12)"
        except Exception:
            pass
        return "Licensed", "#4CAF50", "rgba(76,175,80,0.12)"

    def _get_tool_id(self) -> str:
        """Read the unique machine/tool ID from the local license cache.
        Falls back to computing it fresh via the same algorithm as LicenseManager."""
        try:
            license_file = os.path.join(os.path.expanduser('~'), '.frt_license.json')
            if os.path.exists(license_file):
                with open(license_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Prefer machine_id (the real device fingerprint stored on activation)
                mid = data.get('machine_id') or data.get('tool_id') or data.get('app_id')
                if mid:
                    return mid
        except Exception:
            pass
        # Fallback: recompute the same hash LicenseManager uses
        try:
            import platform, socket, hashlib, uuid as _uuid
            mac = ':'.join(['{:02x}'.format((_uuid.getnode() >> e) & 0xff)
                            for e in range(0, 2 * 6, 2)][::-1])
            hostname = socket.gethostname()
            system = platform.system()
            machine_string = f"{mac}-{hostname}-{system}"
            return hashlib.sha256(machine_string.encode()).hexdigest()[:16].upper()
        except Exception:
            pass
        return "UNKNOWN"

    def _get_license_data(self) -> dict:
        """Load the full local license cache as a dict (empty dict if missing)."""
        try:
            license_file = os.path.join(os.path.expanduser('~'), '.frt_license.json')
            if os.path.exists(license_file):
                with open(license_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _show_license_info(self):
        """Show modern redesigned license information dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("License Information")
        dialog.setFixedSize(580, 520)
        
        # Remove default title bar for custom design
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Custom title bar
        title_bar = QFrame()
        title_bar.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        title_bar.setFixedHeight(50)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(20, 0, 15, 0)
        
        # Dialog icon and title
        dialog_icon = QLabel()
        dialog_icon.setPixmap(qta.icon('fa5s.shield-alt', color='#FFB300').pixmap(20, 20))
        title_bar_layout.addWidget(dialog_icon)
        
        title_bar_layout.addSpacing(10)
        
        dialog_title = QLabel("License Information")
        dialog_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600; background: transparent;")
        title_bar_layout.addWidget(dialog_title)
        
        title_bar_layout.addStretch()
        
        # Close button
        close_title_btn = QPushButton()
        close_title_btn.setIcon(qta.icon('fa5s.times', color='#888888'))
        close_title_btn.setIconSize(QSize(14, 14))
        close_title_btn.setFixedSize(32, 32)
        close_title_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_title_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """)
        
        # Store original icon colors
        close_title_btn._normal_icon = qta.icon('fa5s.times', color='#888888')
        close_title_btn._hover_icon = qta.icon('fa5s.times', color='#ffffff')
        
        # Override enter/leave events
        def on_close_enter(event):
            close_title_btn.setIcon(close_title_btn._hover_icon)
            QPushButton.enterEvent(close_title_btn, event)
        
        def on_close_leave(event):
            close_title_btn.setIcon(close_title_btn._normal_icon)
            QPushButton.leaveEvent(close_title_btn, event)
        
        close_title_btn.enterEvent = on_close_enter
        close_title_btn.leaveEvent = on_close_leave
        close_title_btn.clicked.connect(dialog.reject)
        title_bar_layout.addWidget(close_title_btn)
        
        layout.addWidget(title_bar)
        
        # Main content area
        content = QWidget()
        content.setStyleSheet("background: #1a1a1a;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 25, 30, 25)
        content_layout.setSpacing(20)
        
        # Status badge at top
        status_container = QHBoxLayout()
        status_badge = QLabel("● ACTIVE LICENSE")
        status_badge.setStyleSheet("""
            QLabel {
                background-color: rgba(76, 175, 80, 0.15);
                color: #4CAF50;
                border-radius: 16px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1px;
            }
        """)
        status_container.addWidget(status_badge)
        status_container.addStretch()
        
        edition_label = QLabel("Professional Edition")
        edition_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.4);
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.5px;
        """)
        status_container.addWidget(edition_label)
        
        content_layout.addLayout(status_container)
        
        content_layout.addSpacing(10)
        
        # License details grid
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(15)
        
        # Create info items
        def create_info_item(icon, icon_color, label, value):
            item = QFrame()
            item.setStyleSheet("""
                QFrame {
                    background-color: rgba(255, 255, 255, 0.04);
                    border: none;
                    border-radius: 12px;
                }
            """)
            item.setFixedHeight(85)
            
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(20, 15, 20, 15)
            item_layout.setSpacing(8)
            
            # Icon and label row
            top_row = QHBoxLayout()
            top_row.setSpacing(10)
            
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon(icon, color=icon_color).pixmap(20, 20))
            icon_label.setStyleSheet("background: transparent;")
            top_row.addWidget(icon_label)
            
            label_text = QLabel(label)
            label_text.setStyleSheet("""
                color: rgba(255, 255, 255, 0.5);
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
                background: transparent;
            """)
            top_row.addWidget(label_text)
            top_row.addStretch()
            
            item_layout.addLayout(top_row)
            
            # Value
            value_text = QLabel(value)
            value_text.setStyleSheet(f"""
                color: {icon_color};
                font-size: 15px;
                font-weight: 600;
                letter-spacing: 0.3px;
                background: transparent;
            """)
            item_layout.addWidget(value_text)
            
            return item
        
        # Add items to grid (2 columns)
        lic = self._get_license_data()
        _tool_id   = lic.get('machine_id') or lic.get('tool_id') or self._get_tool_id()
        _user_name = lic.get('user_name') or 'Unknown'
        _version   = lic.get('app_version') or '1.1.0'
        try:
            from datetime import datetime, timezone as _tz
            _expiry_raw = lic.get('expiry_date', '')
            if _expiry_raw:
                _expiry_dt = datetime.fromisoformat(_expiry_raw.replace('Z', '+00:00'))
                # Check if it's a lifetime license (more than 50 years)
                days_until_expiry = (_expiry_dt - datetime.now(_tz.utc)).days
                if days_until_expiry > 18250:  # 50 years
                    _expiry_str = 'Never (Lifetime)'
                else:
                    _expiry_str = _expiry_dt.strftime('%b %d, %Y')
            else:
                _expiry_str = 'Never (Lifetime)'
        except Exception:
            _expiry_str = lic.get('expiry_date', 'N/A')

        grid_layout.addWidget(create_info_item('fa5s.fingerprint', '#FFB300', 'TOOL ID', _tool_id), 0, 0)
        grid_layout.addWidget(create_info_item('fa5s.code-branch', '#29B6F6', 'VERSION', _version), 0, 1)
        grid_layout.addWidget(create_info_item('fa5s.user-circle', '#AB47BC', 'REGISTERED TO', _user_name), 1, 0)
        grid_layout.addWidget(create_info_item('fa5s.calendar-check', '#66BB6A', 'EXPIRES ON', _expiry_str), 1, 1)
        
        content_layout.addWidget(grid_widget)
        
        content_layout.addSpacing(5)
        
        # Support section
        support_frame = QFrame()
        support_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(41, 182, 246, 0.08),
                    stop:1 rgba(41, 182, 246, 0.12));
                border: none;
                border-radius: 12px;
            }
        """)
        support_layout = QHBoxLayout(support_frame)
        support_layout.setContentsMargins(20, 16, 20, 16)
        support_layout.setSpacing(15)
        
        telegram_icon = QLabel()
        telegram_icon.setPixmap(qta.icon('fa5b.telegram', color='#29B6F6').pixmap(28, 28))
        telegram_icon.setStyleSheet("background: transparent;")
        support_layout.addWidget(telegram_icon)
        
        support_text_widget = QWidget()
        support_text_widget.setStyleSheet("background: transparent;")
        support_text_layout = QVBoxLayout(support_text_widget)
        support_text_layout.setContentsMargins(0, 0, 0, 0)
        support_text_layout.setSpacing(3)
        
        support_label = QLabel("Need Help?")
        support_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px; font-weight: 600; background: transparent;")
        support_text_layout.addWidget(support_label)
        
        support_link = QLabel('<a href="https://t.me/ftoolpro" style="color: #29B6F6; text-decoration: none; font-weight: 600; font-size: 13px;">Contact @ftoolpro on Telegram</a>')
        support_link.setOpenExternalLinks(True)
        support_link.setStyleSheet("background: transparent;")
        support_text_layout.addWidget(support_link)
        
        support_layout.addWidget(support_text_widget)
        support_layout.addStretch()
        
        content_layout.addWidget(support_frame)
        
        layout.addWidget(content)
        
        # Footer with buttons
        footer = QWidget()
        footer.setStyleSheet("""
            background: #1a1a1a;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(30, 20, 30, 20)
        footer_layout.setSpacing(12)
        
        # Copy button
        copy_btn = QPushButton("Copy Tool ID")
        copy_btn.setIcon(qta.icon('fa5s.copy', color='#29B6F6'))
        copy_btn.setIconSize(QSize(16, 16))
        copy_btn.setFixedHeight(44)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(41, 182, 246, 0.15);
                color: #29B6F6;
                border: 1px solid rgba(41, 182, 246, 0.3);
                border-radius: 10px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(41, 182, 246, 0.25);
                border: 1px solid rgba(41, 182, 246, 0.4);
            }
            QPushButton:pressed {
                background-color: rgba(41, 182, 246, 0.35);
            }
        """)
        copy_btn.clicked.connect(lambda: self._copy_tool_id())
        footer_layout.addWidget(copy_btn)
        
        footer_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(44)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 0 32px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.18);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """)
        close_btn.clicked.connect(dialog.accept)
        footer_layout.addWidget(close_btn)
        
        layout.addWidget(footer)
        
        dialog.exec()
    
    def _copy_tool_id(self):
        """Copy tool ID to clipboard"""
        try:
            real_id = self._get_tool_id()
            clipboard = QApplication.clipboard()
            clipboard.setText(real_id)
            self.add_activity(f"Tool ID copied to clipboard: {real_id}")
            QMessageBox.information(self, "Copied", f"Tool ID copied to clipboard!\n\n{real_id}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not copy: {e}")


# Entry point moved to main.py
# This file only contains the MainWindow class
# Run the application with: python main.py
